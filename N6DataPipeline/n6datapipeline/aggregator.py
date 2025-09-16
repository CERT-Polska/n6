# Copyright (c) 2013-2025 NASK. All rights reserved.

import collections
import datetime
import contextlib
import functools
import io
import itertools
import json
import os
import os.path
import pickle
import signal
import tempfile
import weakref
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import (
    BinaryIO,
    ClassVar,
    Union,
)

from pika.exceptions import AMQPError
from typing_extensions import Self

from n6datapipeline.base import (
    LegacyQueuedBase,
    n6AMQPCommunicationError,
    n6QueueProcessingException,
)
from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    ascii_str,
    get_unseen_cause_or_context_exc,
    make_exc_ascii_str,
)
from n6lib.config import (
    ConfigError,
    ConfigMixin,
)
from n6lib.datetime_helpers import (
    timestamp_from_datetime,
    parse_iso_datetime_to_utc,
)
from n6lib.file_helpers import (
    AnyPath,
    FileAccessor,
    as_path,
)
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.record_dict import RecordDict


LOGGER = get_logger(__name__)


# time to wait for the next event before suppressed event is generated
AGGREGATE_WAIT = datetime.timedelta(hours=12)

# time after which a source is considered inactive (cleanup should be triggered)
SOURCE_INACTIVITY_TIMEOUT = datetime.timedelta(hours=24)

# in seconds, tick between checks of inactive sources
TICK_TIMEOUT = 3600

# pickle protocol version (used to store the aggregator's state...)
STATE_PICKLE_PROTOCOL = 5


class AggregatorStateIntegrityError(Exception):

    """
    To be raised when it seems that the aggregator state files might be
    corrupted/desynchronized.
    """

    @staticmethod
    @contextlib.contextmanager
    def causing_fatal_exit():
        try:
            yield
        except AggregatorStateIntegrityError as exc:
            error_msg = (
                f'Aggregator state integrity error ({ascii_str(exc)}), '
                f'concerning the data stored in the aggregator data '
                f'file and/or the payload storage file! Sorry, you may '
                f'need to deal with the problem manually! (it may even '
                f'mean, in the worst case, that the only option is to '
                f'delete the aggregator state data files to let them '
                f'be re-created from scratch, accepting that the '
                f'previous aggregation state has been lost)')
            with contextlib.suppress(Exception):
                LOGGER.critical(error_msg)
            raise SystemExit(error_msg) from exc


class PayloadHandle:

    __slots__ = ('offset', 'size')

    # * Interface for `PayloadStorage` (it sets/gets these instance attrs):

    offset: int
    size: int

    # * Public interface (mainly for `HiFreqEventData`):

    @classmethod
    def from_payload(cls, payload: dict) -> Self:
        payload_bytes = cls._bytes_from_payload(payload)
        return cls(payload_bytes)

    @classmethod
    def from_payload_bytes(cls, payload_bytes: bytes) -> Self:
        # It is used to handle the legacy *aggregator data* file format...
        if not payload_bytes:
            raise AggregatorStateIntegrityError('empty payload bytes?!')
        return cls(payload_bytes)

    def load(self) -> dict:
        payload_storage = PayloadStorage.get_existing_instance()
        payload_bytes = payload_storage.load_payload_bytes(self)
        return self._payload_from_bytes(payload_bytes)

    # * Non-public initializer:

    def __init__(self, payload_bytes: bytes):
        payload_storage = PayloadStorage.get_existing_instance()
        payload_storage.save_payload_bytes(self, payload_bytes)
        assert hasattr(self, 'offset')
        assert hasattr(self, 'size')

    # * Pickle hooks:

    def __getstate__(self) -> tuple[int, int]:
        return self.offset, self.size

    def __setstate__(self, state: tuple[int, int]) -> None:
        self.offset, self.size = state

    # * Private helpers:

    @staticmethod
    def _bytes_from_payload(payload: dict, *,
                            # (param below: just a micro-optimization hack...)
                            __pickle=functools.partial(
                                pickle.dumps,
                                protocol=STATE_PICKLE_PROTOCOL,
                            )) -> bytes:
        return b'P' + __pickle(payload)

    @staticmethod
    def _payload_from_bytes(payload_bytes: bytes, *,
                            # (params below: just a micro-optimization hack...)
                            __startswith=bytes.startswith,
                            __decompress=zlib.decompress,
                            __unpickle=pickle.loads) -> dict:
        if __startswith(payload_bytes, b'C'):                           # noqa
            # Handling the legacy *compressed* payload bytes format...
            payload_bytes = __decompress(payload_bytes[1:])
        assert __startswith(payload_bytes, b'P')                        # noqa
        return __unpickle(payload_bytes[1:])


class PayloadStorage:

    # (see `PayloadHandle._bytes_from_payload()`/`._payload_from_bytes()`...)
    _PAYLOAD_BYTES_PREFIXES = (b'P', b'C')

    _get_instance: ClassVar[
        Callable[[], Union[Self, None]]
    ] = staticmethod(lambda: None)

    _payload_storage_path: Path
    _payload_storage_file: io.BufferedRandom
    _payload_handles: list[PayloadHandle]

    # * Public interface:

    def __init__(self, payload_storage_path: AnyPath) -> None:
        cls = self.__class__
        if cls._get_instance() is not None:
            raise RuntimeError(
                f'active instance of {cls.__qualname__} already exists',
            )
        actual_path = as_path(payload_storage_path)
        actual_path.touch(0o600, exist_ok=True)
        self._payload_storage_path = actual_path
        self._payload_storage_file = actual_path.open('r+b')
        self._payload_handles = []
        cls._get_instance = weakref.ref(self)

    @classmethod
    def get_existing_instance(cls) -> Self:
        inst = cls._get_instance()
        if inst is None:
            raise RuntimeError(f'no active instance of {cls.__qualname__}')
        return inst

    def associate_with_aggr_data(self, aggr_data: 'AggregatorData') -> bool:
        # Because of certain gory details related to the legacy
        # *aggregator data* format, the instance of `PayloadStorage`
        # must already exist when the instance of `AggregatorData` is
        # being unpickled. But once the `AggregatorData` instance is
        # ready (unpickled or created from scratch), this method needs
        # to be invoked -- in particular, to get the unpickled list of
        # *payload handles* from that `AggregatorData` instance...
        # TODO later: simplify the stuff once we can stop supporting the legacy format...

        # Note: `self` and `aggr_data` always need to share
        # the same *payload handles* list (the same object!).
        if hasattr(aggr_data, 'payload_handles'):
            assert not self._payload_handles
            self._payload_handles = aggr_data.payload_handles
            shall_shrink = True
        else:
            # Just handling the legacy *aggregator data* file format...
            # Note: in this case, `self._payload_handles` was already
            # populated (during unpickling the aggregator data file).
            aggr_data.payload_handles = self._payload_handles
            shall_shrink = False
        return shall_shrink

    def shrink_disk_space(self,
                          new_payload_storage_writer: BinaryIO,
                          aggr_data: 'AggregatorData') -> None:

        # This method, if used, needs to be invoked *within*
        # the `new_payload_storage_writer`'s *with* block...
        # After that, *beyond* that *with* block, the method
        # `reopen_payload_storage_file()` needs to be invoked
        # (see: `AggregatorDataManager.maintain_state()`).

        old_payload_storage_file = self._payload_storage_file
        read = self._read_payload_bytes

        assert self._payload_handles is aggr_data.payload_handles
        old_payload_handle_list = self._payload_handles
        old_payload_handle_list.reverse()

        still_relevant_payload_handles = frozenset(
            event.payload_handle
            for sd in aggr_data.sources.values()
                for event in itertools.chain(sd.groups.values(), sd.buffer.values()))

        prev_old_offset = -1
        prev_size = 1

        new_payload_storage_writer.seek(0)
        new_payload_handle_list = []
        new_offset = 0

        while True:
            try:
                payload_handle = old_payload_handle_list.pop()
            except IndexError:
                break

            if payload_handle not in still_relevant_payload_handles:
                continue

            old_offset, size = payload_handle.offset, payload_handle.size

            if not (old_offset >= (prev_old_offset + prev_size) > prev_old_offset):
                raise AggregatorStateIntegrityError(
                    f'payload-storage-related data corruption or '
                    f'desynchronization?! [{old_offset=}, '
                    f'{prev_old_offset=}, {prev_size=}]',
                )
            old_payload_storage_file.seek(old_offset)
            payload_bytes = read(old_payload_storage_file, size)

            new_payload_storage_writer.write(payload_bytes)
            new_payload_handle_list.append(payload_handle)
            payload_handle.offset = new_offset

            prev_old_offset, prev_size = old_offset, size
            new_offset += size

        new_payload_storage_writer_pos = new_payload_storage_writer.tell()
        if new_payload_storage_writer_pos != new_offset:
            raise AggregatorStateIntegrityError(
                f'payload-storage-related data corruption or '
                f'desynchronization?! [{new_offset=}, '
                f'{new_payload_storage_writer_pos=}]',
            )

        assert self._payload_handles is aggr_data.payload_handles is old_payload_handle_list
        self._payload_handles = aggr_data.payload_handles = new_payload_handle_list

    def reopen_payload_storage_file(self) -> None:
        # This method needs to be invoked *after* `shrink_disk_space()`
        # -- *beyond* the `new_payload_storage_writer`'s *with* block!
        # (see: `AggregatorDataManager.maintain_state()`)
        self._payload_storage_file.close()
        self._payload_storage_file = self._payload_storage_path.open('r+b')

    def load_payload_bytes(self, payload_handle: PayloadHandle) -> bytes:
        # Note: this method is invoked in `PayloadHandle.load()`.
        self._payload_storage_file.seek(payload_handle.offset)
        return self._read_payload_bytes(self._payload_storage_file, payload_handle.size)

    def save_payload_bytes(self, payload_handle: PayloadHandle, payload_bytes: bytes) -> None:
        # Note: this method is invoked in `PayloadHandle.__init__()`.
        assert payload_bytes
        payload_storage_file = self._payload_storage_file
        payload_storage_file.seek(0, 2)  # (jump to the end of the file)
        try:
            size = payload_storage_file.write(payload_bytes)
        except Exception as exc:
            raise AggregatorStateIntegrityError(
                f'an exception occurred when writing '
                f'to the payload storage file! '
                f'[{make_exc_ascii_str(exc)}]'
            ) from exc
        offset = payload_storage_file.tell() - size
        payload_handle_list = self._payload_handles
        if payload_handle_list:
            prev_offset = payload_handle_list[-1].offset
            prev_size = payload_handle_list[-1].size
            if not (offset >= (prev_offset + prev_size) > prev_offset):
                raise AggregatorStateIntegrityError(
                    f'payload-storage-related data corruption or '
                    f'desynchronization?! [newest {offset=}, '
                    f'{prev_offset=}, {prev_size=}]',
                )
        assert size > 0
        payload_handle.offset = offset
        payload_handle.size = size
        payload_handle_list.append(payload_handle)

    def clear(self) -> None:
        self._payload_storage_file.truncate(0)
        self._payload_handles.clear()

    def close(self) -> None:
        try:
            cls = self.__class__
            if cls._get_instance() is self:
                cls._get_instance = staticmethod(lambda: None)   # noqa
        finally:
            self._payload_storage_file.close()

    # * Private helpers:

    @classmethod
    def _read_payload_bytes(cls, payload_storage_file: BinaryIO, size: int) -> bytes:
        assert size > 0
        payload_bytes = payload_storage_file.read(size)
        if len(payload_bytes) != size or not payload_bytes.startswith(cls._PAYLOAD_BYTES_PREFIXES):
            raise AggregatorStateIntegrityError(
                f'payload-storage-related data corruption or '
                f'desynchronization?! [{payload_bytes[:1]=}, '
                f'{len(payload_bytes)=}, expected {size=}]',
            )
        return payload_bytes

    # * Tests-only interface (*not* a part of the public interface):

    @classmethod
    def _make_for_tests(cls, path=None, aggr_data=None) -> Self:
        if path is None:
            tmp_dir = tempfile.TemporaryDirectory(prefix='n6aggregator-ps-test-')
            path = f'{tmp_dir.name}/test.payload-storage'
        else:
            tmp_dir = None

        instance = cls(path)
        if aggr_data is not None:
            instance.associate_with_aggr_data(aggr_data)
        if tmp_dir is not None:
            # (keep this `TemporaryDirectory` object alive, preventing
            # it from removing the temporary directory prematurely)
            instance.__tmp_dir = tmp_dir
        return instance


class HiFreqEventData:

    r"""
    `HiFreqEventData` is a helper data class.

    Its instances represent particular aggregated events (aka, *event
    groups*) -- during the aggregation process (see, especially, the
    `SourceData.process_event()` method et consortes...). Huge numbers
    of `HiFreqEventData` instances need to be kept in memory, so an
    effort has been made to reduce their memory consumption as much as
    possible (see the implementation...).

    The following example demonstrates the operations the
    `HiFreqEventData`'s public interface exposes:

    >>> payload_storage = PayloadStorage._make_for_tests()  # (needs to exist)
    >>> payload = {
    ...     'time': '2023-03-04 05:06:07',
    ...     'address': [{'ip': '10.20.30.40'}, {'ip': '10.20.123.124', 'cc': 'PL', 'asn': 54321}],
    ...     'name': 'Ala ma kota',
    ...     '_group': 'Ala ma kota_10.20.30.40',
    ... }
    >>> event = HiFreqEventData(payload)
    >>> event.first
    datetime.datetime(2023, 3, 4, 5, 6, 7)
    >>> event.until
    datetime.datetime(2023, 3, 4, 5, 6, 7)
    >>> event.until = datetime.datetime(2023, 3, 5, 6, 6, 47)
    >>> event.until
    datetime.datetime(2023, 3, 5, 6, 6, 47)
    >>> event.count
    1
    >>> event.count = 123
    >>> event.count
    123
    >>> expected_dict = {
    ...     'time': '2023-03-04 05:06:07',
    ...     'address': [{'ip': '10.20.30.40'}, {'ip': '10.20.123.124', 'cc': 'PL', 'asn': 54321}],
    ...     'name': 'Ala ma kota',
    ...     '_group': 'Ala ma kota_10.20.30.40',
    ...     '_first_time':  '2023-03-04 05:06:07',
    ...     'count': 123,
    ...     'until': '2023-03-05 06:06:47',
    ... }
    >>> event.to_dict() == expected_dict
    True

    Below, we check pickling and unpickling:

    >>> event_pickled = pickle.dumps(event)
    >>> event_unpickled = pickle.loads(event_pickled)
    >>> event_unpickled.first
    datetime.datetime(2023, 3, 4, 5, 6, 7)
    >>> event_unpickled.until
    datetime.datetime(2023, 3, 5, 6, 6, 47)
    >>> event_unpickled.count
    123
    >>> event_unpickled.to_dict() == expected_dict
    True
    >>> event_unpickled._initial_payload == payload
    True

    ***

    Below, we examine a property intended to be used only by the
    `PayloadStorage`'s stuff (and, therefore, *not* being a part
    of the public interface):

    >>> isinstance(event.payload_handle, PayloadHandle)
    True

    ***

    Below, we check a semi-private operation (intended to be used only
    in tests, *not* being a part of the public interface):

    >>> event._initial_payload == payload
    True

    ***

    >>> payload_storage.close()
    """

    __slots__ = ('_first_ts', '_until_ts', '_payload_handle', 'count')

    _first_ts: float
    _until_ts: float
    _payload_handle: PayloadHandle

    # * Interface for `PayloadStorage` only:

    @property
    def payload_handle(self) -> PayloadHandle:
        return self._payload_handle

    # * Public interface:

    count: int

    def __init__(self, payload: dict):
        # Note: keeping `float` and `bytes` objects, rather that
        # `datetime` and `dict` objects, lets us save a significant
        # amount of memory. Even more is saved thanks to saving the
        # pickled payload in an on-disk storage...
        first_timestamp = self._timestamp_from_iso_formatted_dt(payload['time'])
        self._first_ts = first_timestamp
        self._until_ts = first_timestamp
        self._payload_handle = PayloadHandle.from_payload(payload)
        self.count = 1  # XXX: see ticket #6243

    @property
    def first(self, *,
              # (param below: just a micro-optimization hack...)
              __dt_from_timestamp=datetime.datetime.utcfromtimestamp) -> datetime.datetime:
        return __dt_from_timestamp(self._first_ts)

    @property
    def until(self, *,
              # (param below: just a micro-optimization hack...)
              __dt_from_timestamp=datetime.datetime.utcfromtimestamp) -> datetime.datetime:
        return __dt_from_timestamp(self._until_ts)

    @until.setter
    def until(self, until_dt: datetime.datetime, *,
              # (param below: just a micro-optimization hack...)
              __timestamp_from_dt=timestamp_from_datetime) -> None:
        self._until_ts = __timestamp_from_dt(until_dt)

    def to_dict(self, *,
                # (param below: just a micro-optimization hack...)
                __str=datetime.datetime.__str__) -> dict:
        result = self._payload_handle.load()
        result['count'] = self.count
        result['until'] = __str(self.until)                             # noqa
        result['_first_time'] = __str(self.first)                       # noqa
        return result

    # * Pickle hooks:

    def __getstate__(self) -> tuple:
        return self._first_ts, self._until_ts, self._payload_handle, self.count

    def __setstate__(self, state: tuple) -> None:
        self._first_ts, self._until_ts, payload_handle, self.count = state
        if isinstance(payload_handle, bytes):
            # The legacy *aggregator data* file format: with payload bytes.
            payload_handle = PayloadHandle.from_payload_bytes(payload_handle)
        self._payload_handle = payload_handle

    # * Private helpers:

    @staticmethod
    def _timestamp_from_iso_formatted_dt(iso_formatted_dt: str, *,
                                         # (params below: just a micro-optimization hack...)
                                         __timestamp_from_dt=timestamp_from_datetime,
                                         __parse_iso_formatted_dt=parse_iso_datetime_to_utc,
                                         ) -> float:
        return __timestamp_from_dt(__parse_iso_formatted_dt(iso_formatted_dt))

    # * Tests-only interface (*not* a part of the public interface):

    @property
    def _initial_payload(self) -> dict:
        return self._payload_handle.load()


class SourceData:

    def __init__(self, time_tolerance):
        self.time = None  # current time tracked for source (based on event time)
        self.last_active = None  # real-time-based, used to trigger inactive source cleanup
        self.groups = collections.OrderedDict()  # groups aggregated for the source
        self.buffer = collections.OrderedDict()  # keeps events until `time_tolerance` passes
        self.time_tolerance = time_tolerance

    def update_time(self, data_time):
        if data_time > self.time:
            self.time = data_time
        self.last_active = datetime.datetime.utcnow()

    def process_event(self, data):
        data_time = parse_iso_datetime_to_utc(data['time'])
        group = data['_group']
        event = self.groups.get(group)
        if self.time is None:
            self.time = data_time
        if data_time + self.time_tolerance < self.time:
            if event is None or event.first > data_time:
                LOGGER.error('Event out of order. Ignoring. Data: %s', data)
                raise n6QueueProcessingException('Event out of order.')
            else:
                LOGGER.info('Event out of order, but not older than group\'s first event, '
                            'so it will be added to existing aggregate group. Data: %s', data)
                event.until = max(event.until, data_time)
                event.count += 1  # XXX: see ticket #6243
                return False

        if event is None:
            if data_time < self.time:
                # unordered event, self.buffer may contain suppressed event
                LOGGER.debug("Unordered event of the '%s' group, '%s' source within time "
                             "tolerance. Check and update buffer.", group, data['source'])
                buffered_event = self.buffer.get(group)
                if buffered_event is not None:
                    buffered_event.count += 1  # XXX: see ticket #6243
                    self.buffer[group] = buffered_event
                    return False
            # Event not seen before - add new event to group
            LOGGER.debug("A new group '%s' for '%s' source began to be aggregated, "
                         "first event is being generated.", group, data['source'])
            self.groups[group] = HiFreqEventData(data)  # XXX: see ticket #6243
            self.update_time(data_time)
            return True

        event_until = event.until

        if (data_time > event_until + AGGREGATE_WAIT
              or data_time.date() > self.time.date()):
            LOGGER.debug("A suppressed event is generated for the '%s' group of "
                         "'%s' source due to passing of %s hours between events.",
                         group, data['source'], AGGREGATE_WAIT)
            # 24 hour aggregation or AGGREGATE_WAIT time passed between events in group
            self.groups[group] = HiFreqEventData(data)  # XXX: see ticket #6243
            self.groups.move_to_end(group)
            self.buffer[group] = event
            self.update_time(data_time)
            return True

        # Event for existing group and still aggregating
        LOGGER.debug("Event is being aggregated in the '%s' group of the '%s' source.",
                     group, data['source'])
        event.count += 1  # XXX: see ticket #6243
        if data_time > event_until:
            event.until = data_time
        self.groups.move_to_end(group)
        self.update_time(data_time)
        return False

    def generate_suppressed_events(self):
        cutoff_time = self.time - AGGREGATE_WAIT
        cutoff_check_complete = False
        for_cleanup = []
        for k, v in self.groups.items():
            v_until = v.until
            if cutoff_check_complete or v_until >= cutoff_time:
                cutoff_check_complete = True
                if v_until.date() == self.time.date():
                    break
            for_cleanup.append(k)
            self.buffer[k] = v
        for k in for_cleanup:
            del self.groups[k]
        return self._generate_suppressed_events_from_buffer()

    def _generate_suppressed_events_from_buffer(self):
        cutoff_time = self.time - self.time_tolerance
        for_cleanup = []
        for k, v in self.buffer.items():
            if v.until >= cutoff_time:
                break
            for_cleanup.append(k)
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        for k in for_cleanup:
            del self.buffer[k]

    def generate_suppressed_events_after_inactive(self):
        for v in self.buffer.values():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        for v in self.groups.values():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        self.groups.clear()
        self.buffer.clear()
        self.last_active = datetime.datetime.utcnow()

    __repr__ = attr_repr('groups', 'buffer')


class AggregatorData:

    def __init__(self):
        # These data attributes are to be pickled:
        self.sources = {}
        self.payload_handles = []  # <- Shared with the `PayloadStorage` instance.

    def get_or_create_sourcedata(self,
                                 event,
                                 time_tolerance):
        source = event['source']
        sd = self.sources.get(source)
        if sd is None:
            sd = SourceData(time_tolerance)
            self.sources[source] = sd
        return sd

    def get_sourcedata(self, event):
        # event['source'] exists because it was created in
        # `Aggregator.process_event()` where `process_new_message(data)`
        # is run before `generate_suppressed_events_for_source(data)`.
        return self.sources[event['source']]

    __repr__ = attr_repr('sources')


class AggregatorDataManager:

    def __init__(self,
                 dbpath,
                 time_tolerance,
                 time_tolerance_per_source):

        self.aggr_data_fac = FileAccessor(dbpath)
        self.payload_storage_fac = FileAccessor(
            self.aggr_data_fac.path.with_suffix('.payload-storage'),
        )
        self.aggr_data = None
        self.payload_storage = None

        self.time_tolerance = time_tolerance
        self.time_tolerance_per_source = time_tolerance_per_source

        shall_shrink = self.restore_state()
        self.maintain_state(shall_shrink)

    @AggregatorStateIntegrityError.causing_fatal_exit()
    def restore_state(self):
        assert self.aggr_data is None
        assert self.payload_storage is None

        # TODO later: make the creation of the `PayloadStorage` instance be done
        #             *after* unpickling/creating the `AggregatorData` instance,
        #             and merge `PayloadStorage.associate_with_aggr_data()` into
        #             `PayloadStorage.__init__()` + get rid of `shall_shrink`!
        #             (once we can stop supporting the legacy format...)
        self.payload_storage = PayloadStorage(self.payload_storage_fac.path)
        try:
            with self.aggr_data_fac.binary_reader() as aggr_data_reader:
                self.aggr_data = pickle.load(aggr_data_reader)
        except FileNotFoundError as exc:
            LOGGER.warning(
                'The aggregator data file does not exist (%s). '
                'Initializing a new empty state...',
                make_exc_ascii_str(exc))
            self.aggr_data = AggregatorData()
            shall_shrink = self.payload_storage.associate_with_aggr_data(self.aggr_data)
            self.payload_storage.clear()
        except BaseException as exc:
            with contextlib.suppress(Exception):
                LOGGER.error(
                    'Failed to restore the aggregator state from %a '
                    '(%s). Depending on the problem, you may need '
                    'to deal with it manually!',
                    str(self.aggr_data_fac.path),
                    make_exc_ascii_str(exc))
            raise
        else:
            LOGGER.info(
                'Restored the aggregator state from %a.',
                str(self.aggr_data_fac.path),
            )
            shall_shrink = self.payload_storage.associate_with_aggr_data(self.aggr_data)
        return shall_shrink

    @AggregatorStateIntegrityError.causing_fatal_exit()
    def maintain_state(self, shall_shrink):
        assert self.aggr_data is not None
        assert self.payload_storage is not None

        if not shall_shrink:
            # TODO later: get rid of the `shall_shrink` arg and this `if` block!
            #             (once we can stop supporting the legacy format...)
            try:
                with self.aggr_data_fac.binary_atomic_writer() as aggr_data_writer:
                    pickle.dump(self.aggr_data, aggr_data_writer, STATE_PICKLE_PROTOCOL)  # noqa
            except BaseException as exc:
                with contextlib.suppress(Exception):
                    LOGGER.error(
                        'Most probably, failed to update the aggregator '
                        'state in %a (%a). However, the old saved state, '
                        'if any, should be kept intact.',
                        str(self.aggr_data_fac.path),
                        make_exc_ascii_str(exc))
                raise
            else:
                LOGGER.info(
                    'Updated the aggregator state in %a.',
                    str(self.aggr_data_fac.path),
                )
                self.payload_storage.reopen_payload_storage_file()
            return

        sigint_handler = signal.getsignal(signal.SIGINT)
        exc_causing_integrity_problem = False
        try:
            with self.payload_storage_fac.binary_atomic_writer() as payload_storage_writer:
                with self.aggr_data_fac.binary_atomic_writer() as aggr_data_writer:
                    self.payload_storage.shrink_disk_space(payload_storage_writer, self.aggr_data)
                    pickle.dump(self.aggr_data, aggr_data_writer, STATE_PICKLE_PROTOCOL)  # noqa
                    # Let's block Ctrl+C for this critical short moment...
                    sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
                exc_causing_integrity_problem = True
            exc_causing_integrity_problem = False
            signal.signal(signal.SIGINT, sigint_handler)
        except BaseException as exc:
            if exc_causing_integrity_problem:
                with contextlib.suppress(Exception):
                    LOGGER.error(
                        'Most probably, failed to update *consistently* '
                        'the aggregator state in %a and %a (%a). You '
                        'may need to deal with this problem manually!',
                        str(self.aggr_data_fac.path),
                        str(self.payload_storage_fac.path),
                        make_exc_ascii_str(exc))
                raise AggregatorStateIntegrityError(
                    f'state consistency problem: the aggregator data file '
                    f'{str(self.aggr_data_fac.path)!a} (over)written '
                    f'successfully, while an exception occurred when '
                    f'trying to (over)write the payload storage file '
                    f'{str(self.payload_storage_fac.path)!a}! '
                    f'[{make_exc_ascii_str(exc)}]'
                ) from exc
            else:
                with contextlib.suppress(Exception):
                    LOGGER.error(
                        'Most probably, failed to update the aggregator '
                        'state in %a and %a (%a). However, the old saved '
                        'state should be kept intact.',
                        str(self.aggr_data_fac.path),
                        str(self.payload_storage_fac.path),
                        make_exc_ascii_str(exc))
                raise
        else:
            LOGGER.info(
                'Updated the aggregator state in %a and %a.',
                str(self.aggr_data_fac.path),
                str(self.payload_storage_fac.path),
            )
            self.payload_storage.reopen_payload_storage_file()
        finally:
            signal.signal(signal.SIGINT, sigint_handler)

    @AggregatorStateIntegrityError.causing_fatal_exit()
    def store_state(self):
        assert self.aggr_data is not None
        assert self.payload_storage is not None

        self.payload_storage.close()
        try:
            with self.aggr_data_fac.binary_atomic_writer() as aggr_data_writer:
                pickle.dump(self.aggr_data, aggr_data_writer, STATE_PICKLE_PROTOCOL)    # noqa
        except BaseException as exc:
            with contextlib.suppress(Exception):
                LOGGER.error(
                    'Most probably, failed to save the aggregator '
                    'state to %a (%a). However, the old saved state '
                    'should be kept intact.',
                    str(self.aggr_data_fac.path),
                    make_exc_ascii_str(exc))
            raise
        else:
            LOGGER.info(
                'Saved the aggregator state to %a.',
                str(self.aggr_data_fac.path),
            )

    def process_new_message(self, data):
        """
        Process a message and check it against the database to detect
        a suppressed event -- adding a new entry to the database if
        necessary (new), or updating an existing entry.

        Returns:
            `True`:
                if the first event in the group has been received
                (so it should *not* be suppressed).
            `False`:
                if a subsequent event in the group has been received (so
                it *should* be suppressed + its count should be updated).
        """

        source_data = self.aggr_data.get_or_create_sourcedata(
            data,
            self.time_tolerance_per_source.get(data['source']) or self.time_tolerance,
        )
        result = source_data.process_event(data)
        return result

    def generate_suppressed_events_for_source(self, data):
        """
        Called after each event in a given source was processed.
        Yields suppressed events.
        """
        source_data = self.aggr_data.get_sourcedata(data)
        yield from source_data.generate_suppressed_events()

    def generate_suppressed_events_after_timeout(self):
        """Scans all stored sources and based on real time
         (i.e. source has been inactive for defined time)
        generates suppressed events for inactive sources
        """
        LOGGER.debug('Detecting inactive sources after tick timout')
        now = datetime.datetime.utcnow()
        for source_data in self.aggr_data.sources.values():
            LOGGER.debug('Checking source: %a', source_data)
            if source_data.last_active + SOURCE_INACTIVITY_TIMEOUT < now:
                LOGGER.debug('Source inactive. Generating suppressed events')
                for event_type, event in source_data.generate_suppressed_events_after_inactive():
                    LOGGER.debug('%a: %a', event_type, event)
                    yield event_type, event


class Aggregator(ConfigMixin, LegacyQueuedBase):

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'aggregator',
        'accepted_event_types': [
            'hifreq',
        ],
    }
    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    config_spec = '''
        [aggregator]
        dbpath
        time_tolerance :: int
        time_tolerance_per_source = {} :: py_namespaces_dict

        # approximate number of processed aggregation groups that causes
        # restart of the aggregator machinery -- to shrink the disk space
        # occupied by the payload storage file (and, possibly, to perform
        # other necessary maintenance operations...)
        finished_groups_count_triggering_restart = 10_000_000 :: int
    '''

    def __init__(self, **kwargs):
        config = self.config = self.get_config_section()
        config['dbpath'] = os.path.expanduser(config['dbpath'])
        dbpath_dirname = os.path.dirname(config['dbpath'])
        try:
            os.makedirs(dbpath_dirname, 0o700)
        except OSError:
            pass
        super(Aggregator, self).__init__(**kwargs)
        # state dir doesn't exist
        if not os.path.isdir(dbpath_dirname):
            raise Exception(f'stopping the aggregator - the state '
                            f'directory does not exist; its path: '
                            f'{config["dbpath"]!a}')
        # state directory exists, but we have no write access to it
        if not os.access(dbpath_dirname, os.W_OK):
            raise Exception(f'stopping the aggregator - write access '
                            f'to the state directory needed; its path: '
                            f'{config["dbpath"]!a}')
        self.db = AggregatorDataManager(
            config['dbpath'],
            time_tolerance=datetime.timedelta(seconds=config['time_tolerance']),
            time_tolerance_per_source=self._prepare_time_tolerance_per_source(config),
        )
        self.timeout_id = None   # id of the 'tick' timeout that executes source cleanup
        self._finished_groups_count = 0

    def _prepare_time_tolerance_per_source(self, config):
        try:
            return {
                source: datetime.timedelta(seconds=time_tolerance)
                for source, time_tolerance in config['time_tolerance_per_source'].items()}
        except Exception as exc:
            raise ConfigError('problem with option `time_tolerance_per_source`') from exc

    def run(self):
        try:
            super().run()
        except BaseException as exc:
            if self._is_caused_by_sigint_or_amqp_problem(exc):
                self.db.store_state()
                try:
                    self.stop()
                except Exception as e:
                    LOGGER.error(
                        f'Suppressing an exception from {self.stop.__qualname__} (%s). '
                        f'Note that the aggregator state has already been saved anyway.',
                        make_exc_ascii_str(e), exc_info=True)
            else:
                LOGGER.error(
                    f'Exiting because of an unexpected exception (%s). '
                    f'The aggregator state will *not* be saved!',
                    make_exc_ascii_str(exc))
            raise
        else:
            self.db.store_state()

    def _is_caused_by_sigint_or_amqp_problem(self, exc):
        seen_exceptions = set()
        while (isinstance(exc, SystemExit) and
               (c := get_unseen_cause_or_context_exc(exc, seen_exceptions)) is not None):
            exc = c
        return isinstance(exc, (KeyboardInterrupt, AMQPError, n6AMQPCommunicationError))

    @AggregatorStateIntegrityError.causing_fatal_exit()
    def input_callback(self, routing_key, body, properties):
        record_dict = RecordDict.from_json(body)
        with self.setting_error_event_info(record_dict):
            data = dict(record_dict)
            if '_group' not in data:
                raise n6QueueProcessingException("Hi-frequency source missing '_group' field.")
            self.process_event(data)

        if self._should_restart():
            self.trigger_inner_stop_trying_gracefully_shutting_input_then_output()

    def process_event(self, data):
        """
        Process an incoming event (got from the AMQP input queue(s)),
        performing event aggregation, and publishing the event if that
        is necessary. It may also trigger generation and publication of
        other suppressed events originating from the same *source*...
        """
        do_publish_new_message = self.db.process_new_message(data)
        if do_publish_new_message:
            self.publish_event(('event', data))
        for event_type, event in self.db.generate_suppressed_events_for_source(data):
            if event is not None:
                self.publish_event((event_type, event))
            self._finished_groups_count += 1

    def start_publishing(self):
        """
        Ensure that triggering generation and publication of suppressed
        events will be attempted periodically for all relevant *sources*
        -- independently of whether and when incoming events appear...
        """
        self.set_timeout()

    def set_timeout(self):
        LOGGER.debug('Setting tick timeout')
        self.timeout_id = self._connection.add_timeout(TICK_TIMEOUT, self.on_timeout)

    @AggregatorStateIntegrityError.causing_fatal_exit()
    def on_timeout(self):
        LOGGER.debug('Tick passed')
        for event_type, event in self.db.generate_suppressed_events_after_timeout():
            if event is not None:
                self.publish_event((event_type, event))
            self._finished_groups_count += 1

        if self._should_restart():
            self.trigger_inner_stop_trying_gracefully_shutting_input_then_output(immediately=True)
        else:
            self.set_timeout()

    def _should_restart(self):
        count_triggering_restart = self.config['finished_groups_count_triggering_restart']
        return self._finished_groups_count >= count_triggering_restart > 0

    def publish_event(self, data):
        """Publish the given event to the output AMQP exchange."""
        event_type, payload = data
        if event_type is None:
            return
        cleaned_payload = self._get_cleaned_payload(event_type, payload)
        source_provider, source_channel = cleaned_payload['source'].split('.')
        rk = f'{event_type}.aggregated.{source_provider}.{source_channel}'
        body = json.dumps(cleaned_payload)
        self.publish_output(routing_key=rk, body=body)

    def _get_cleaned_payload(self, event_type, payload):
        cleaned_payload = payload.copy()
        cleaned_payload['type'] = event_type
        cleaned_payload.pop('_group', None)

        ####################################################################
        # This is a *temporary hack* to clean data already put into the    #
        # aggregator state by an old -- pre-#8814 -- code...               #
        from n6lib.record_dict import RecordDict
        RecordDict._update_given_data_by_pipelining_items_thru_rd(
            cleaned_payload,
            keys=('dip', 'address', 'enriched', 'name', 'id', 'category', 'source'))
        # ^^^ to be removed!!! ^^ to be removed!!! ^^ to be removed!!! ^^^ #   see ticket #8899
        ####################################################################

        return cleaned_payload


def main():
    with logging_configured():
        if os.environ.get('n6integration_test'):
            # for debugging only
            import logging
            import sys
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.addHandler(logging.StreamHandler(stream=sys.__stdout__))

        while True:
            a = Aggregator()
            a.run()


if __name__ == '__main__':
    main()

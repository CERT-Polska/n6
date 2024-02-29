# Copyright (c) 2013-2023 NASK. All rights reserved.

import collections
import pickle
import datetime
import json
import os
import os.path
import zlib
from typing import Union

from n6datapipeline.base import (
    LegacyQueuedBase,
    n6QueueProcessingException,
)
from n6lib.common_helpers import (
    make_exc_ascii_str,
    open_file,
)
from n6lib.config import (
    ConfigError,
    ConfigMixin,
)
from n6lib.datetime_helpers import (
    timestamp_from_datetime,
    parse_iso_datetime_to_utc,
)
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.record_dict import RecordDict
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


# time to wait for the next event before suppressed event is generated
AGGREGATE_WAIT = datetime.timedelta(hours=12)

# time after which a source is considered inactive (cleanup should be triggered)
SOURCE_INACTIVITY_TIMEOUT = datetime.timedelta(hours=24)

# in seconds, tick between checks of inactive sources
TICK_TIMEOUT = 3600


class HiFreqEventData:

    r"""
    `HiFreqEventData` is a helper data class.

    Its instances represent particular aggregated events (aka, *event
    groups*) -- during the aggregation process (see, especially, the
    `SourceData.process_event()` method et consortes...). Huge numbers
    of `HiFreqEventData` instances need to be kept in memory, so an
    effort has been made to reduce their memory consumption as much as
    possible (in particular, an on-the-fly compression and decompression
    are employed to achieve that; see the implementation...).

    The following example demonstrates the operations the
    `HiFreqEventData`'s public interface exposes:

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

    Below, we check unpickling from a pickled representation made with
    an older implementation:

    >>> event_pickled_by_old_impl = (
    ...     b'\x80\x04\x95?\x01\x00\x00\x00\x00\x00\x00\x8c\x19n6datapipeline'
    ...     b'.aggregator\x94\x8c\x0fHiFreqEventData\x94\x93\x94)\x81\x94}\x94'
    ...     b'(\x8c\x05until\x94\x8c\x08datetime\x94\x8c\x08datetime\x94\x93'
    ...     b'\x94C\n\x07\xe7\x03\x05\x06\x06/\x00\x00\x00\x94\x85\x94R\x94'
    ...     b'\x8c\x05first\x94h\x08C\n\x07\xe7\x03\x04\x05\x06\x07\x00\x00'
    ...     b'\x00\x94\x85\x94R\x94\x8c\x05count\x94K{\x8c\x07payload\x94}'
    ...     b'\x94(\x8c\x04time\x94\x8c\x132023-03-04 05:06:07\x94\x8c\x07'
    ...     b'address\x94]\x94(}\x94\x8c\x02ip\x94\x8c\x0b10.20.30.40\x94s}'
    ...     b'\x94(h\x18\x8c\r10.20.123.124\x94\x8c\x02cc\x94\x8c\x02PL\x94'
    ...     b'\x8c\x03asn\x94M1\xd4ue\x8c\x04name\x94\x8c\x0bAla ma kota\x94'
    ...     b'\x8c\x06_group\x94\x8c\x17Ala ma kota_10.20.30.40\x94uub.')
    >>> event_unpickled_from_old = pickle.loads(event_pickled_by_old_impl)
    >>> event_unpickled_from_old.first
    datetime.datetime(2023, 3, 4, 5, 6, 7)
    >>> event_unpickled_from_old.until
    datetime.datetime(2023, 3, 5, 6, 6, 47)
    >>> event_unpickled_from_old.count
    123
    >>> event_unpickled_from_old.to_dict() == expected_dict
    True
    >>> event_unpickled_from_old._initial_payload == payload
    True

    ***

    Below, we check a semi-private operation (intended to be used only
    in tests, *not* being a part of the public interface):

    >>> event._initial_payload == payload
    True

    ***

    Below, we check some gory internal details (*not* being a part of
    the public interface!):

    >>> event._payload_bytes.startswith(b'C')    # case of compressed pickle
    True
    >>> event2 = HiFreqEventData({'time': '2023-03-04 05:06:07'})
    >>> event2._payload_bytes.startswith(b'P')   # case of non-compressed pickle (too short)
    True
    """

    __slots__ = ('_first_ts', '_until_ts', '_payload_bytes', 'count')

    # * Public constructor:

    def __init__(self, payload: dict):
        # Note: storing `float` and `bytes` objects, rather that
        # `datetime` and `dict` objects, lets us save a significant
        # amount of memory.
        first_timestamp = self._timestamp_from_iso_formatted_dt(payload['time'])
        self._first_ts = first_timestamp
        self._until_ts = first_timestamp
        self._payload_bytes = self._bytes_from_payload(payload)
        self.count = 1  # XXX: see ticket #6243

    _first_ts: float
    _until_ts: float
    _payload_bytes: bytes

    # * Public interface of instances:

    count: int

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
                __str=datetime.datetime.__str__) -> dict:
        result = self._payload_from_bytes(self._payload_bytes)
        result['count'] = self.count
        result['until'] = __str(self.until)                             # noqa
        result['_first_time'] = __str(self.first)                       # noqa
        return result

    # * Pickle hooks:

    def __getstate__(self) -> tuple[float, float, bytes, int]:
        return self._first_ts, self._until_ts, self._payload_bytes, self.count

    def __setstate__(self, state: Union[KwargsDict, tuple[float, float, bytes, int]]) -> None:
        if isinstance(state, dict):
            # Legacy state (from older implementation of `HiFreqEventData`):
            assert state.keys() >= {'payload', 'first', 'until', 'count'}, state
            self._first_ts = timestamp_from_datetime(state['first'])
            self._until_ts = timestamp_from_datetime(state['until'])
            self._payload_bytes = self._bytes_from_payload(state['payload'])
            self.count = state['count']
        else:
            self._first_ts, self._until_ts, self._payload_bytes, self.count = state

    # * Private helpers:

    @staticmethod
    def _timestamp_from_iso_formatted_dt(iso_formatted_dt: str, *,
                                         # (params below: just a micro-optimization hack...)
                                         __timestamp_from_dt=timestamp_from_datetime,
                                         __parse_iso_formatted_dt=parse_iso_datetime_to_utc,
                                         ) -> float:
        return __timestamp_from_dt(__parse_iso_formatted_dt(iso_formatted_dt))

    @staticmethod
    def _bytes_from_payload(payload: dict, *,
                            # (params below: just a micro-optimization hack...)
                            __pickle=pickle.dumps,
                            __compress=zlib.compress,
                            __len=bytes.__len__) -> bytes:
        payload_bytes = b'P' + __pickle(payload)
        compressed = b'C' + __compress(payload_bytes)
        if __len(compressed) < __len(payload_bytes):                    # noqa
            payload_bytes = compressed
        return payload_bytes

    @staticmethod
    def _payload_from_bytes(payload_bytes: bytes, *,
                            # (params below: just a micro-optimization hack...)
                            __unpickle=pickle.loads,
                            __decompress=zlib.decompress,
                            __startswith=bytes.startswith) -> dict:
        if __startswith(payload_bytes, b'C'):                           # noqa
            payload_bytes = __decompress(payload_bytes[1:])
        return __unpickle(payload_bytes[1:])

    # * Unit-tests-only interface (*not* a part of the public interface):

    @property
    def _initial_payload(self) -> dict:
        return self._payload_from_bytes(self._payload_bytes)


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
        for _, v in self.buffer.items():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        for _, v in self.groups.items():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        self.groups.clear()
        self.buffer.clear()
        self.last_active = datetime.datetime.utcnow()

    def __repr__(self):
        return repr(self.groups)


class AggregatorData:

    def __init__(self):
        self.sources = {}

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

    def __repr__(self):
        return repr(self.sources)


class AggregatorDataWrapper:

    _STATE_PICKLE_PROTOCOL = 4

    def __init__(self,
                 dbpath,
                 time_tolerance,
                 time_tolerance_per_source):
        self.aggr_data = None
        self.dbpath = dbpath
        self.time_tolerance = time_tolerance
        self.time_tolerance_per_source = time_tolerance_per_source
        self.restore_state()

    def restore_state(self):
        try:
            with open_file(self.dbpath, 'rb') as f:
                self.aggr_data = pickle.load(f)
        except FileNotFoundError as exc:
            LOGGER.warning(
                'Could not load the aggregator state (%s). '
                'Initializing a new empty state...',
                make_exc_ascii_str(exc))
            self.aggr_data = AggregatorData()
        except Exception as exc:
            LOGGER.error(
                'Could not load the aggregator state from %a (%s). '
                'You may need to deal with the problem manually!',
                self.dbpath, make_exc_ascii_str(exc))
            raise
        else:
            LOGGER.info('Loaded the aggregator state from %a.', self.dbpath)

    def store_state(self):
        try:
            with open_file(self.dbpath, 'wb') as f:
                pickle.dump(self.aggr_data, f, self._STATE_PICKLE_PROTOCOL)
        except OSError as exc:
            LOGGER.error(
                'Failed to save the aggregator state to %a (%s). '
                'Proceeding without having it saved, but the '
                'component may not work correctly anymore!',
                self.dbpath, make_exc_ascii_str(exc))
            # XXX: Should we still proceed despite this error?
        else:
            LOGGER.info('Saved the aggregator state to %a.', self.dbpath)

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
    '''

    def __init__(self, **kwargs):
        config = self.get_config_section()
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
        self.db = AggregatorDataWrapper(
            config['dbpath'],
            time_tolerance=datetime.timedelta(seconds=config['time_tolerance']),
            time_tolerance_per_source=self._prepare_time_tolerance_per_source(config),
        )
        self.timeout_id = None   # id of the 'tick' timeout that executes source cleanup

    def _prepare_time_tolerance_per_source(self, config):
        try:
            return {
                source: datetime.timedelta(seconds=time_tolerance)
                for source, time_tolerance in config['time_tolerance_per_source'].items()}
        except Exception as exc:
            raise ConfigError('problem with option `time_tolerance_per_source`') from exc

    def input_callback(self, routing_key, body, properties):
        record_dict = RecordDict.from_json(body)
        with self.setting_error_event_info(record_dict):
            data = dict(record_dict)
            if '_group' not in data:
                raise n6QueueProcessingException("Hi-frequency source missing '_group' field.")
            self.process_event(data)

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

    def on_timeout(self):
        LOGGER.debug('Tick passed')
        for event_type, event in self.db.generate_suppressed_events_after_timeout():
            if event is not None:
                self.publish_event((event_type, event))
        self.set_timeout()

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

    def stop(self):
        self.db.store_state()
        super(Aggregator, self).stop()


def main():
    with logging_configured():
        if os.environ.get('n6integration_test'):
            # for debugging only
            import logging
            import sys
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.addHandler(logging.StreamHandler(stream=sys.__stdout__))
        a = Aggregator()
        try:
            a.run()
        except KeyboardInterrupt:
            a.stop()
            raise


if __name__ == '__main__':
    main()

# Copyright (c) 2016-2024 NASK. All rights reserved.

"""
Generic MISP collector.
"""

import argparse
import contextlib
import json
import time
from collections.abc import AsyncIterator
from datetime import (
    timedelta,
    datetime,
)
from typing import (
    Optional,
    TypedDict,
    Union,
)
from urllib.parse import urljoin

from dateutil.tz import gettz
from pymisp import PyMISP
import requests

from n6datasources.collectors.base import (
    BaseCollector,
    BaseDownloadingCollector,
    StatefulCollectorMixin,
    add_collector_entry_point_functions,
)
from n6lib.common_helpers import (
    ascii_str,
    exiting_on_exception,
)
from n6lib.config import (
    Config,
    ConfigSection,
)
from n6lib.datetime_helpers import (
    ReactionToProblematicTime,
    datetime_with_tz_to_utc,
)
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import (
    Jsonable,
    JsonableDict,
    JsonableSeq,
    KwargsDict,
)


LOGGER = get_logger(__name__)


class SampleDownloadFailure(Exception):
    """An auxiliary exception class (used internally by `MispCollector`)."""


# TODO: Update this class to use the modern PyMISP's interfaces... + upgrade PyMISP version!
#       + analyze (& fix?) if we can switch to more reliable mechanism than "last minutes"...

class MispCollector(StatefulCollectorMixin, BaseDownloadingCollector, BaseCollector):

    #
    # Fundamental declarations

    raw_type = 'stream'
    content_type = 'application/json'  # <- Used after the `self._reset_raw_type(for_samples=True)`
                                       #    invocation (made in `_process_samples_stuff()`...).
    output_queue = [
        {
            'exchange': 'raw',
            'exchange_type': 'topic',
        },
        {
            'exchange': 'sample',
            'exchange_type': 'topic',
        },
    ]


    #
    # Config-related stuff

    # (note: we deliberately do *not* use `combined_config_spec()` here)
    config_spec_pattern = '''
        # Note: when running the `n6collector_misp` script, you
        # specify the config section name as the sole positional
        # command-line argument.
        #
        # So you can have, in you config file(s), any number of
        # configurations of the `n6collector_misp` script -- each
        # in a separate config section of a distinct name. Then
        # multiple instances of `n6collector_misp` can be run in
        # parallel without any problem, provided that their
        # `source_provider` values differ.

        [{config_section_name_from_cmdline_arg}]

        # The 1st segment of the source identifier (the 2nd is always `misp`).
        source_provider :: str

        # The MISP API's base URL.
        misp_url :: str

        # Your individual MISP API key.
        misp_key :: str

        # Should the MISP API's SSL certificate be verified?
        misp_verifycert = yes :: bool

        # How far do we want to reach into the past when the collector
        # is run for the first time? (in days)
        days_for_first_run :: int

        # The minimum TLP, so no event will have assigned a TLP below
        # this value. If not left empty, it must be one of the values
        # defined by the `MispCollector.ALLOWED_TLP_VALUES` constant
        # (matched in a case-insensitive manner).
        minimum_tlp = :: tlp

        # --------------------------------------------------------------
        # Note: *the following four options* concern only downloading
        # samples' binary data.

        # The URL path specifying the location of MISP attribute files
        # (to be joined to the value of `misp_url`, together with sample
        # ids, to form URLs from which binary samples will be downloaded).
        sample_path = /attributes/downloadAttachment/download/ :: str

        # When a retryable download failure occurs for a sample, how
        # many extra attempts to download it are allowed to be made
        # (each after a few-seconds delay).
        download_retries = 3 :: int

        # A Python dict literal specifying custom headers for all sample
        # download requests (note, however, that the `Authorization`
        # header will always, automatically, be set to the value of
        # the `misp_key` option).
        base_request_headers = {{}} :: py_namespaces_dict

        # After what time (in days) the lack of any sample download
        # success (when there is anything to download) should become
        # fatal (that is, should cause that execution of the collector
        # script finishes with a non-zero exit code).
        max_acceptable_days_of_continuous_download_failures = 3 :: int
        # --------------------------------------------------------------

        # The default value of the following option should be OK in most
        # cases (you may want to try increasing it in your configuration
        # file if there are problems with AMQP connection timeouts...).
        heartbeat_interval = 60 :: int

        # A standard collector-state-loading-and-saving-related setting
        # (`StatefulCollectorMixin`-specific); its default value should
        # be OK in nearly all cases.
        state_dir = ~/.n6state :: path
    '''

    ALLOWED_TLP_VALUES = (
        'white',
        'green',
        'amber',
        'red',
    )

    @property
    def custom_converters(self) -> dict:
        return super().custom_converters | {'tlp': self._convert_tlp}

    @classmethod
    def _convert_tlp(cls, s: str) -> Optional[str]:
        if not s:
            return None
        tlp = s.lower()
        if tlp not in cls.ALLOWED_TLP_VALUES:
            valid_listing = ', '.join(map(ascii, cls.ALLOWED_TLP_VALUES))
            raise ValueError(
                f'not a valid TLP indicator (if not left empty, '
                f'it should be one of: {valid_listing})')
        return tlp

    def get_config_spec_format_kwargs(self) -> KwargsDict:
        # (note: the `self._config_section_name_from_cmdline_arg`
        # attribute has been set in `__init__()`)
        return super().get_config_spec_format_kwargs() | {
            'config_section_name_from_cmdline_arg': self._config_section_name_from_cmdline_arg}

    def get_config_from_config_full(self, *,
                                    config_full: Config,
                                    collector_class_name: str) -> ConfigSection:
        # (note: the `self._config_section_name_from_cmdline_arg`
        # attribute has been set in `__init__()`)
        return config_full[self._config_section_name_from_cmdline_arg]


    #
    # Various constants

    SAMPLE_META_KEYS = (
        'category',
        'comment',
        'uuid',
        'event_id',
        'timestamp',
        'to_ids',
        'value',
        'distribution',
        'type',
        'id',
    )

    STATE_KEYS = (
        'events_last_proc_datetime',
        'samples_last_proc_datetime',
        'already_processed_sample_ids',
    )


    #
    # Static typing helpers

    class StateDict(TypedDict):
        events_last_proc_datetime: datetime
        samples_last_proc_datetime: datetime
        already_processed_sample_ids: set[int]

    assert tuple(StateDict.__annotations__) == STATE_KEYS


    #
    # Attributes/properties, initialization, command-line args, etc.

    _config_section_name_from_cmdline_arg: str
    _base_sample_url: str

    _now: datetime
    _state: StateDict
    _overdue_samples_to_publish: bool
    _misp: PyMISP

    _misp_events: Optional[JsonableSeq]
    _misp_events_output_components: Optional[tuple[str, bytes, KwargsDict]]

    @property
    def _sample_exchange(self) -> str:
        return self.output_queue[1]['exchange']

    def __init__(self, **kwargs):
        # (see `get_arg_parser()` below...)
        self._config_section_name_from_cmdline_arg = self.cmdline_args.n6config_section_name

        super().__init__(**kwargs)

        self._base_sample_url = urljoin(
            self.config['misp_url'],
            self.config['sample_path'])

        # To be set in `run_collection()`:
        self._now = None                              # noqa
        self._state = None                            # noqa
        self._overdue_samples_to_publish = None       # noqa
        self._misp = None                             # noqa

        # To be set in `_fetch_and_prepare_misp_events_related_stuff()`:
        self._misp_events = None
        self._misp_events_output_components = None

    @classmethod
    def get_arg_parser(cls) -> argparse.ArgumentParser:
        arg_parser = super().get_arg_parser()
        arg_parser.add_argument(
            'n6config_section_name',
            help=(
                'the configuration section name to be used by '
                'the MISP collector (for example, "misp_circl")'))
        return arg_parser


    #
    # `BaseCollector.get_output_components()`-invoked hooks

    def get_source(self, **processed_data) -> str:
        return f'{self.config["source_provider"]}.misp'

    def get_output_data_body(self, *, body: bytes, **rest_kwargs) -> bytes:
        return body

    def get_output_prop_kwargs(self, *,
                               pub_sample_metadata: Optional[dict] = None,
                               **rest_kwargs) -> KwargsDict:
        properties = super().get_output_prop_kwargs(**rest_kwargs)
        minimum_tlp = self.config['minimum_tlp']
        if minimum_tlp or pub_sample_metadata:
            properties['headers'].setdefault('meta', dict())
            if minimum_tlp:
                properties['headers']['meta']['minimum_tlp'] = minimum_tlp
            if pub_sample_metadata:
                properties['headers']['meta']['misp'] = {
                    key: pub_sample_metadata[key] for key in self.SAMPLE_META_KEYS
                    if key in pub_sample_metadata}
        return properties


    #
    # Implementation of the actual collector activity

    def run_collection(self) -> None:
        LOGGER.info('Collector activity started.')
        self._reset_raw_type()
        self._now = datetime.utcnow().replace(microsecond=0)
        self._state = self.load_state()
        self._overdue_samples_to_publish = self._are_there_overdue_samples_to_publish()
        self._misp = self._make_misp_client()
        if self._fetch_and_prepare_misp_events_related_stuff():
            super().run_collection()
        LOGGER.info('Collector activity finishes without a fatal error.')

    # * Customization of `StatefulCollectorMixin`-inherited stuff:

    def load_state(self) -> StateDict:
        state = super().load_state()
        if not isinstance(state, dict):
            raise TypeError(
                f'encountered a wrong state: not a dict ({state=!a})')
        if state.keys() != set(self.STATE_KEYS):
            valid_keys_listing = ', '.join(map(ascii, self.STATE_KEYS))
            raise ValueError(
                f'encountered a wrong state: its keys should be '
                f'exactly: {valid_keys_listing} (whereas {state=!a})')
        if state['samples_last_proc_datetime'] > state['events_last_proc_datetime']:
            raise ValueError(
                f'encountered a wrong state: the last sample '
                f'publication datetime should be the same as '
                f'or earlier than the last event publication '
                f'datetime (whereas {state=!a})')
        return state

    def make_default_state(self) -> StateDict:
        initial_datetime = self._now - timedelta(days=self.config['days_for_first_run'])
        return {
            'events_last_proc_datetime': initial_datetime,
            'samples_last_proc_datetime': initial_datetime,
            'already_processed_sample_ids': set(),
        }

    # (Py2-to-Py3-state-transition-related)
    def get_py2_pickle_load_kwargs(self):
        # We need to use the `latin1` encoding to be able to unpickle
        # any Py2-pickled `datetime` objects (see: #8278 and #8717).
        return dict(encoding='latin1')

    # (Py2-to-Py3-state-transition-related)
    def adjust_state_from_py2_pickle(self, py2_state: dict) -> StateDict:
        self._check_py2_state_keys(py2_state)
        self._check_py2_state_value_types(py2_state)
        self._check_py2_state_datetime_values(py2_state)
        return {
            # Differences between Py3's vs. Py2's state dicts:
            # * `datetime` objects are still naive (timezone-unaware),
            #   but whereas in Py2 they represented local time, in Py3
            #   they represent UTC time;
            # * in Py3, a `set` (instead of a `list`) of `int` numbers
            #   is used to store identifiers of processed samples;
            # * state dict keys are different.
            'events_last_proc_datetime': self.__as_utc(py2_state['events_publishing_datetime']),
            'samples_last_proc_datetime': self.__as_utc(py2_state['samples_publishing_datetime']),
            'already_processed_sample_ids': set(py2_state['last_published_samples']),
        }

    def _check_py2_state_keys(self, py2_state: dict) -> None:
        if py2_state.keys() != {
            'events_publishing_datetime',
            'samples_publishing_datetime',
            'last_published_samples',
        }:
            raise NotImplementedError(
                f"unexpected set of Py2 state keys: "
                f"{', '.join(map(ascii, py2_state.keys()))}")

    def _check_py2_state_value_types(self, py2_state: dict) -> None:
        if not isinstance(py2_state['events_publishing_datetime'], datetime):
            raise NotImplementedError(
                f"unexpected {type(py2_state['events_publishing_datetime'])=!a}")
        if not isinstance(py2_state['samples_publishing_datetime'], datetime):
            raise NotImplementedError(
                f"unexpected {type(py2_state['samples_publishing_datetime'])=!a}")
        if not isinstance(py2_state['last_published_samples'], list):
            raise NotImplementedError(
                f"unexpected {type(py2_state['last_published_samples'])=!a}")
        if not all(isinstance(sample_id, int)
                   for sample_id in py2_state['last_published_samples']):
            raise NotImplementedError(
                f"unexpected non-int value(s) found in "
                f"{py2_state['last_published_samples']=!a}")

    def _check_py2_state_datetime_values(self, py2_state: dict) -> None:
        if py2_state['events_publishing_datetime'].tzinfo is not None:
            raise NotImplementedError(
                f"unexpected non-None tzinfo of "
                f"{py2_state['events_publishing_datetime']=!a}")
        if py2_state['samples_publishing_datetime'].tzinfo is not None:
            raise NotImplementedError(
                f"unexpected non-None tzinfo of "
                f"{py2_state['samples_publishing_datetime']=!a}")

    @staticmethod
    def __as_utc(naive_local_dt: datetime) -> datetime:
        # Let's obtain the local timezone (hopefully, the same in which
        # `naive_local_dt` was made in Py2 using `datetime.now()`...).
        tz = gettz()
        if tz is None:
            raise RuntimeError('could not get the local timezone')
        naive_utc_dt = datetime_with_tz_to_utc(
            naive_local_dt,
            tz,  # (<- its DST, if any, will be applied as appropriate)
            on_ambiguous_time=ReactionToProblematicTime.PICK_THE_EARLIER,
            on_non_existent_time=ReactionToProblematicTime.PICK_THE_EARLIER)
        assert naive_utc_dt.tzinfo is None
        return naive_utc_dt

    # * Activity phase #1: preparations and event collection:

    def _make_misp_client(self) -> PyMISP:
        return PyMISP(
            url=self.config['misp_url'],
            key=self.config['misp_key'],
            ssl=self.config['misp_verifycert'])

    def _are_there_overdue_samples_to_publish(self) -> bool:
        state = self._state
        if state['samples_last_proc_datetime'] < state['events_last_proc_datetime']:
            return True
        else:
            # (this equality is guaranteed thanks to the previous state validation)
            assert state['samples_last_proc_datetime'] == state['events_last_proc_datetime']
            return False

    def _fetch_and_prepare_misp_events_related_stuff(self) -> bool:
        if misp_events := self._fetch_misp_events(self._state['events_last_proc_datetime']):
            LOGGER.info(
                'Fetched %d event(s). They are to be published...',
                len(misp_events))
            body = self._as_json_output_body(misp_events)
            self._misp_events = misp_events
            self._misp_events_output_components = self.get_output_components(body=body)
            return True  # Let's move on to activity phase #2...
        else:
            self._misp_events = None
            self._misp_events_output_components = None
            self._state['events_last_proc_datetime'] = self._now
            if self._overdue_samples_to_publish:
                LOGGER.info(
                    'No new events, but there are overdue '
                    'malware samples to publish.')
                self.save_state(self._state)
                return True  # Let's move on to activity phase #2...
            else:
                LOGGER.info(
                    'No events or malware samples to publish.')
                self._set_samples_state_to_finished()
                self.save_state(self._state)
                return False  # Let's end the collector activity now (gracefully).

    @staticmethod
    def _as_json_output_body(data: Jsonable) -> bytes:
        return json.dumps(data).encode('ascii')

    # * Activity phase #2: event publishing and sample collection/publishing:

    @exiting_on_exception
    def start_publishing(self) -> None:
        super().start_publishing()
        self.start_iterative_publishing()

    async def publish_iteratively(self) -> None:
        if self._misp_events_output_components:
            await self._do_publish_events(self._misp_events_output_components)
        await self._process_samples_stuff()

    async def _do_publish_events(self, output_components: tuple[str, bytes, KwargsDict]) -> None:
        self.publish_output(*output_components)
        await self.PubIterFlushOut
        self._state['events_last_proc_datetime'] = self._now
        self.save_state(self._state)
        LOGGER.info('Published the event(s).')

    async def _process_samples_stuff(self) -> None:
        self._reset_raw_type(for_samples=True)
        self._verify_sample_exchange_declared()
        since = self._state['samples_last_proc_datetime']
        if misp_events_for_samples := self._get_misp_events_for_samples(since):
            if sample_metadata_seq := self._get_sample_metadata_seq(misp_events_for_samples):
                (ok_downloads,
                 failed_downloads) = await self._download_and_publish_samples(sample_metadata_seq)
                considered_finished = self._recap_downloads(ok_downloads, failed_downloads, since)
                if not considered_finished:
                    # Let's leave the samples-related state as unfinished.
                    return
            else:
                LOGGER.info('No malware samples to publish since %s.', since)
        await self.PubIterFlushOut
        self._set_samples_state_to_finished()
        self.save_state(self._state)

    def _verify_sample_exchange_declared(self) -> None:
        if self._sample_exchange not in self._declared_output_exchanges:
            LOGGER.warning(
                'The exchange %a is not declared! Any malware samples '
                'that could be processed and published will *not* be '
                'processed/published now (note: they may be processed '
                'and published during a future collector run, as '
                '*overdue* samples; we leave a saved state that will '
                'make it possible, provided that the exchange is '
                'declared).', self._sample_exchange)
            raise RuntimeError(
                f'exchange {self._sample_exchange!a} is not declared, '
                f'so no samples could be processed (note: they might '
                f'be processed in the future; see the related recent '
                f'WARNING log message for additional comment on that)')

    def _get_misp_events_for_samples(self, since: datetime) -> Optional[JsonableSeq]:
        if self._overdue_samples_to_publish:
            misp_events_for_samples = self._fetch_misp_events(since)
            if not misp_events_for_samples:
                LOGGER.warning(
                    'The loaded state indicates that there should be '
                    'overdue samples to publish, since %s. However, '
                    'according to the queried MISP system, there are '
                    'no events and no associated malware samples to '
                    'download for that period.', since)
                return None
            LOGGER.info(
                'Preparing for downloading and publishing malware '
                'samples, including overdue samples since %s.', since)
        else:
            assert self._misp_events
            misp_events_for_samples = self._misp_events
            LOGGER.info(
                'Preparing for downloading and publishing new '
                'malware samples, since %s.', since)
        assert misp_events_for_samples
        return misp_events_for_samples

    def _get_sample_metadata_seq(self, misp_events_for_samples: JsonableSeq) -> list[JsonableDict]:
        # Extract metadata dicts for those MISP attributes whose type
        # corresponds to the malware samples.
        sample_metadata_seq = []
        attribute_lists = (
            x['Event']['Attribute']   # noqa
            for x in misp_events_for_samples)
        for attr_list in attribute_lists:
            attr_list: list[JsonableDict]
            for attr in attr_list:
                if attr['type'] == 'malware-sample' and 'id' in attr:
                    sample_id = self._get_sample_id(attr)
                    if sample_id not in self._state['already_processed_sample_ids']:
                        sample_metadata_seq.append(attr)
        return sample_metadata_seq

    def _get_sample_id(self, sample_metadata: JsonableDict) -> int:
        return int(sample_metadata['id'])

    async def _download_and_publish_samples(self, sample_metadata_seq: list[JsonableDict],
                                            ) -> tuple[int, int]:
        ok_downloads = 0
        failed_downloads = 0
        async for sample in self._iter_download_samples(sample_metadata_seq):
            if sample is None:
                failed_downloads += 1
                continue
            ok_downloads += 1
            sample_metadata, sample_body = sample
            output_components = self.get_output_components(
                body=sample_body,
                pub_sample_metadata=sample_metadata)
            await self._do_publish_sample(output_components, sample_metadata)
        return ok_downloads, failed_downloads

    async def _iter_download_samples(self, sample_metadata_seq: list[JsonableDict],
                                     ) -> AsyncIterator[Union[None, tuple[JsonableDict, bytes]]]:
        for sample_metadata in sample_metadata_seq:
            # (let the *iterative publishing* machinery take control for a moment)
            await self.PubIter

            url = self._get_sample_url(sample_metadata)
            try:
                sample_body = await self._download_sample(url)
            except SampleDownloadFailure as exc:
                sample_id = self._get_sample_id(sample_metadata)
                LOGGER.warning(
                    'Cannot download the sample whose id is %d (%s)',
                    sample_id, exc)
                yield None
            else:
                assert isinstance(sample_body, bytes)
                yield sample_metadata, sample_body

    def _get_sample_url(self, sample_metadata: JsonableDict) -> str:
        return urljoin(self._base_sample_url, sample_metadata['id'])

    async def _do_publish_sample(self,
                                 output_components: tuple[str, bytes, KwargsDict],
                                 sample_metadata: JsonableDict) -> None:
        self.publish_output(*output_components, exchange=self._sample_exchange)
        await self.PubIterFlushOut
        sample_id = self._get_sample_id(sample_metadata)
        self._state['already_processed_sample_ids'].add(sample_id)
        self.save_state(self._state)
        LOGGER.info('Published the malware sample (id=%d).', sample_id)

    def _recap_downloads(self,
                         ok_downloads: int,
                         failed_downloads: int,
                         since: datetime) -> bool:
        attempts = ok_downloads + failed_downloads
        assert attempts
        if ok_downloads:
            considered_finished = True
            if failed_downloads:
                LOGGER.warning(
                    'Out of %d sample downloads (since: %s), %d '
                    'were successful and %d were *not*! It needs '
                    'to be emphasized that those %d undownloaded '
                    'samples *will be lost!* (i.e., there will '
                    'be *no* further attempts to download them).',
                    attempts, since, ok_downloads, failed_downloads,
                    failed_downloads)
            else:
                assert attempts == ok_downloads
        else:
            assert attempts == failed_downloads
            considered_finished = False
            LOGGER.warning(
                "Attempted to download %d samples (since: %s), "
                "but *all* those downloads failed; that's why "
                "the concerned samples are to be treated as "
                "*overdue* ones (we leave a saved state reflecting "
                "that), so that it will be possible to process "
                "and publish them during future collector run(s).",
                attempts, since)
            max_days = self.config['max_acceptable_days_of_continuous_download_failures']
            if self._now - since > timedelta(days=max_days):
                raise RuntimeError(
                    f'continuous sample download failures have '
                    f'been being observed for samples from more '
                    f'than {max_days} days (see the related recent '
                    f'WARNING log messages for more information...)')
        return considered_finished

    # * Internal helpers related to both activity phases:

    def _reset_raw_type(self, for_samples=False):
        if for_samples:
            self.raw_type = 'file'
        else:
            with contextlib.suppress(AttributeError):
                del self.raw_type
            assert self.raw_type == self.__class__.raw_type

    def _set_samples_state_to_finished(self) -> None:
        # Update the state dict to indicate that downloading and
        # publishing of malware samples have been finished.
        self._state['samples_last_proc_datetime'] = self._now
        self._state['already_processed_sample_ids'].clear()


    #
    # MISP data fetching helpers

    _LAST_TIME_LEEWAY_MINUTES = 15

    _MAX_SECONDS_BETWEEN_SAMPLE_DOWNLOAD_ATTEMPTS = 10
    _RETRYABLE_HTTP_ERROR_CODES = frozenset({500, 502, 503, 504})

    def _fetch_misp_events(self, since: datetime) -> Optional[JsonableSeq]:
        # Try to download from the MISP source the events since the
        # given date+time. Return `None` if there are no new events.
        last = self._get_misp_search_arg_last(since)
        if misp_events := self._misp.search(last=last).get('response'):
            return misp_events
        return None

    def _get_misp_search_arg_last(self, since: datetime) -> str:
        minutes_strict = (self._now - since).total_seconds() / 60
        minutes = minutes_strict + self._LAST_TIME_LEEWAY_MINUTES
        return f'{minutes:.0f}m'

    async def _download_sample(self, url: str) -> bytes:
        # Try to download a malware sample binary data from the given
        # URL. Raise `SampleDownloadFailure` if the sample does not
        # exist, or it could not be downloaded for another cause...
        allowed_attempts = max(1, self.config['download_retries'] + 1)
        fail_descr = '<unknown cause>'
        for i in range(allowed_attempts):
            if i > 0:
                # (let the *iterative publishing* machinery take control for a moment)
                await self.PubIter

                # (let's sleep for a few seconds...)
                delay = min(2 ** i, self._MAX_SECONDS_BETWEEN_SAMPLE_DOWNLOAD_ATTEMPTS)
                LOGGER.info(
                    'A retryable error occurred while trying '
                    'to download a sample (%s). Retrying in %d '
                    'seconds...', fail_descr, delay)
                time.sleep(delay)

            # (let the *iterative publishing* machinery take control for a moment)
            await self.PubIter

            try:
                sample_body = self.download(
                    url,
                    retries=0,
                    custom_request_headers=self._prepare_sample_download_request_headers())

            except (requests.Timeout, requests.ConnectionError) as exc:
                fail_descr = self._format_sample_download_fail_descr(url, exc, attempts=i+1)
                continue

            except requests.HTTPError as exc:
                fail_descr = self._format_sample_download_fail_descr(url, exc, attempts=i+1)
                if exc.response.status_code in self._RETRYABLE_HTTP_ERROR_CODES:
                    continue
                raise SampleDownloadFailure(fail_descr) from exc

            except OSError as exc:
                fail_descr = self._format_sample_download_fail_descr(url, exc, attempts=i+1)
                raise SampleDownloadFailure(fail_descr) from exc

            else:
                # OK, downloaded successfully! :-)

                assert isinstance(sample_body, bytes)
                LOGGER.info(
                    'Downloaded a %d-bytes malware sample from %a.',
                    len(sample_body), url)

                return sample_body

            finally:
                # Prevent `BaseDownloadingCollector.get_output_prop_kwargs()`
                # from adding the AMQP meta header `http_last_modified`:
                self._http_last_modified = None

        # We have tried `allowed_attempts` times without success... :-(
        assert str(allowed_attempts) in fail_descr
        raise SampleDownloadFailure(fail_descr)

    def _prepare_sample_download_request_headers(self) -> dict[str, str]:
        # Note that -- when preparing actual HTTP request headers -- the
        # machinery provided by `BaseDownloadingCollector` automatically
        # uses the dict which is the value of the `base_request_headers`
        # config option to provide defaults... In other words, both the
        # `base_request_headers` dict and the following dict are used,
        # and the item from the following dict has a higher priority (i.e.,
        # shadows the same-named header from `base_request_headers`, if
        # any).
        return {
            'Authorization': self.config['misp_key'],
        }

    def _format_sample_download_fail_descr(self,
                                           url: str,
                                           exc: Exception,
                                           attempts: int) -> str:
        attempts_part = (
            f'after {attempts} download attempts '
            if attempts != 1 else '')
        exc_part = ascii_str(
            f'{type(exc).__qualname__}: '
            f'{str(exc) or "<download failure>"}')
        return f'[{attempts_part}from {url!a}] {exc_part}'


add_collector_entry_point_functions(__name__)

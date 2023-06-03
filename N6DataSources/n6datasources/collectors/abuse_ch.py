# Copyright (c) 2014-2023 NASK. All rights reserved.

"""
Collectors: `abuse-ch.feodotracker`, `abuse-ch.ssl-blacklist`,
`abuse-ch.urlhaus-urls`, `abuse-ch.urlhaus-payloads-urls`,
`abuse-ch.urlhaus-payload-samples`.
"""

import datetime
import operator
from collections.abc import (
    Iterator,
    MutableSequence,
    Sequence,
)
from io import BytesIO
from urllib.parse import urljoin
from zipfile import ZipFile

import json
from typing import (
    Any,
    Optional,
)

import more_itertools

from n6datasources.collectors.base import (
    BaseDownloadingTimeOrderedRowsCollector,
    BaseTwoPhaseCollector,
    BaseDownloadingCollector,
    StatefulCollectorMixin,
    add_collector_entry_point_functions,
)
from n6lib.common_helpers import (
    FilePagedSequence,
    make_exc_ascii_str,
)
from n6lib.config import (
    combined_config_spec,
    ConfigError,
)
from n6lib.csv_helpers import (
    extract_field_from_csv_row,
    split_csv_row,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger
from n6lib.unpacking_helpers import iter_unzip_from_bytes


LOGGER = get_logger(__name__)


class _BaseAbuseChDownloadingTimeOrderedRowsCollector(BaseDownloadingTimeOrderedRowsCollector):

    row_time_legacy_state_key = None
    time_field_index = None

    def load_state(self):
        state = super().load_state()
        if self.row_time_legacy_state_key and self.row_time_legacy_state_key in state:
            # got `state` in a legacy form
            row_time = self.normalize_row_time(state[self.row_time_legacy_state_key])
            state = {
                # note: one or a few rows (those containing this "boundary"
                # time value) will be duplicated, but we can live with that
                self._NEWEST_ROW_TIME_STATE_KEY: row_time,
                self._NEWEST_ROWS_STATE_KEY: set(),
                self._ROWS_COUNT_KEY: None,
            }
        return state

    def pick_raw_row_time(self, row):
        return extract_field_from_csv_row(row, column_index=self.time_field_index).strip()

    def clean_row_time(self, raw_row_time):
        return self.normalize_row_time(raw_row_time)

    def should_row_be_used(self, row):
        if not super().should_row_be_used(row):
            return False
        try:
            # FIXME: remove code duplication (almost the same operations
            #        are in `pick_raw_row_time()` and `clean_row_time()`)
            raw_row_time = extract_field_from_csv_row(row, column_index=self.time_field_index)
            self.normalize_row_time(raw_row_time)
            return True
        except ValueError:
            return False

    def normalize_row_time(self, raw_row_time):
        return str(parse_iso_datetime_to_utc(raw_row_time))


class AbuseChFeodoTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '202110'

    time_field_index = 0

    def get_source(self, **processed_data) -> str:
        return 'abuse-ch.feodotracker'

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


class AbuseChSslBlacklistCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):
    # Note that, contrary to its name, it is an *event-based* source

    raw_format_version_tag = '201902'

    row_time_legacy_state_key = 'time'
    time_field_index = 0

    def get_source(self, **processed_data) -> str:
        return 'abuse-ch.ssl-blacklist'

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


class AbuseChUrlhausUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '202001'
    raw_type = 'stream'

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        api_url :: str
        api_retries = 3 :: int
    ''')

    time_field_index = 1

    CSV_FILENAME = 'csv.txt'

    def get_source(self, **processed_data) -> str:
        return 'abuse-ch.urlhaus-urls'

    def obtain_orig_data(self):
        data = self.download(self.config['url'])
        [(_, all_rows)] = iter_unzip_from_bytes(data, filenames=[self.CSV_FILENAME])
        return all_rows

    def obtain_input_pile(self, **_kwargs: dict) -> Optional[list[dict]]:
        self._state = self.load_state()
        orig_data = self.obtain_orig_data()
        all_rows = self.all_rows_from_orig_data(orig_data)
        fresh_rows = self.get_fresh_rows_only(all_rows)
        if fresh_rows:
            abuse_inf_dicts = self._obtain_abuse_info_dicts(fresh_rows)
            return abuse_inf_dicts
        return None

    def _obtain_abuse_info_dicts(self, fresh_rows: list[str]) -> list[dict]:
        abuse_info_dicts = [self._make_abuse_info_dict(row) for row in fresh_rows[:5]]
        return abuse_info_dicts

    def _make_abuse_info_dict(self, row: str) -> dict:
        abuse_info_dict = self._convert_row_to_info_dict(row)
        url_id = abuse_info_dict['url_id']
        url_info = self._fetch_url_info_from_api(url_id)
        abuse_info_dict['url_info_from_api'] = json.loads(url_info)
        return abuse_info_dict

    def _convert_row_to_info_dict(self, row: str) -> dict:
        row_fields = split_csv_row(row)
        return {
            'url_id': row_fields[0],
            'dateadded': row_fields[1],
            'url': row_fields[2],
            'url_status': row_fields[3],
            'threat': row_fields[4],
            'tags': row_fields[5],
            'urlhaus_link': row_fields[6],
            'reporter': row_fields[7],
        }

    def _fetch_url_info_from_api(self, url_id: str) -> bytes:
        return self.download(method='POST',
                             url=self.config['api_url'],
                             data={'urlid': url_id},
                             retries=self.config['api_retries'])

    def generate_input_data_dicts(self, abuse_dicts: dict, /) -> dict:
        yield {'abuse_dicts': abuse_dicts}

    def get_output_data_body(self, *, abuse_dicts, **kwargs) -> bytes:
        return json.dumps(abuse_dicts).encode()

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


class AbuseChUrlhausPayloadsUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    time_field_index = 0

    CSV_FILENAME = 'payload.txt'

    def get_source(self, **processed_data):
        return 'abuse-ch.urlhaus-payloads-urls'

    # note that since Apr 2020 AbuseCh changed input format for this
    # source - now it is .zip file with .txt inside
    def obtain_orig_data(self):
        data = self.download(self.config['url'])
        return data

    def obtain_input_pile(self, **_kwargs: dict) -> Optional[list[dict]]:
        self._state = self.load_state()
        orig_data = self.obtain_orig_data()
        [(_, all_rows)] = iter_unzip_from_bytes(orig_data)
        all_rows = self.all_rows_from_orig_data(all_rows)
        fresh_rows = self.get_fresh_rows_only(all_rows)
        if fresh_rows:
            return fresh_rows
        return None

    def generate_input_data_dicts(self, fresh_rows: list, /) -> dict:
        for chunk in more_itertools.chunked(fresh_rows, 20000):
            yield {'fresh_rows': chunk}

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


class AbuseChUrlhausPayloadSamplesCollector(StatefulCollectorMixin,
                                            BaseDownloadingCollector,
                                            BaseTwoPhaseCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        payload_summaries_url :: str
        payload_info_url :: str
        payload_dl_url :: str
        samples_per_run :: int
        max_samples_in_memory :: int
    ''')

    raw_type = 'file'
    content_type = 'application/octet-stream'

    output_queue = {
        'exchange': 'sample',
        'exchange_type': 'topic'
    }

    SAMPLE_EXCHANGE_META_HEADER_KEYS = [
        'md5_hash',
        'sha256_hash',
        'signature',
        'firstseen',
        'lastseen',
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._samples_per_run: int = self._get_samples_per_run()
        self._state: Optional[dict] = None
        self._today: datetime.date = datetime.datetime.today().date()
        self._payload_sample_and_headers_pairs: FilePagedSequence = FilePagedSequence(
            page_size=self.config['max_samples_in_memory'],
        )

    def run_collection(self) -> None:
        with self._payload_sample_and_headers_pairs:
            super().run_collection()

    def _get_samples_per_run(self) -> int:
        if not 0 < self.config['samples_per_run'] <= 1000:
            raise ConfigError(
                f'`samples_per_run` should be in range 1-1000, not '
                f'{self.config["samples_per_run"]}')
        return self.config['samples_per_run']

    def make_default_state(self) -> dict:
        return {
            self._today: set()
        }

    def obtain_input_pile(self) -> Optional[Sequence[tuple[bytes, dict]]]:
        LOGGER.info("%s's main activity started", self.__class__.__name__)
        self._state = self.load_state()
        self._maintain_state()
        all_recent_payload_summaries = self._fetch_recent_payload_summaries()
        payload_sample_and_headers_pairs = self._payload_sample_and_headers_pairs
        payload_sample_and_headers_pairs: MutableSequence[tuple[bytes, dict]]
        assert not payload_sample_and_headers_pairs
        for payload_summary in all_recent_payload_summaries:
            if len(payload_sample_and_headers_pairs) >= self._samples_per_run:
                assert len(payload_sample_and_headers_pairs) == self._samples_per_run
                break
            payload_name = payload_summary['sha256_hash']
            LOGGER.info("Processing payload: %a", payload_name)
            payload_info_dict = self._obtain_payload_info_dict(payload_name)
            if payload_info_dict is None:
                continue
            LOGGER.info("Payload info dict obtained")
            payload_sample = self._obtain_payload_sample(payload_name)
            if payload_sample is None:
                continue
            LOGGER.info("Payload sample obtained")
            payload_headers = self._obtain_meta_headers(payload_info_dict)
            LOGGER.info("Payload meta headers obtained")
            self._state[self._today].add(payload_name)
            payload_sample_and_headers_pairs.append((payload_sample, payload_headers))
        if payload_sample_and_headers_pairs:
            return payload_sample_and_headers_pairs
        return None

    def _maintain_state(self) -> None:
        """
        We can only obtain payloads from the last three days (max 1000 records),
        and they are not grouped/sorted together, it is important to maintain
        order in the state, so we will be able to keep it small during longer
        period of time.

        Each key represents a day (datetime object) containing a set with
        payload names (sha256 hash). Each day which is older than four days
        (we add one extra day to state just to be sure that we do not miss
        any records) should be removed from the state. Each time collector
        runs, it checks every payload if it exists in the state (so, basically,
        it iterates through each day and checks if particular sha256 hash exists
        in one of the day's sets).
        """
        days_to_keep = 4
        oldest_day_to_keep = self._today - datetime.timedelta(days_to_keep)
        self._state = {
            day: payloads for day, payloads in self._state.items()
            if day >= oldest_day_to_keep
        }
        self._state.setdefault(self._today, set())
        self.save_state(self._state)

    def _fetch_recent_payload_summaries(self) -> list[dict]:
        # We expect to obtain only payloads from the past 3 days,
        # but no more than 1000 samples.
        # (see: https://urlhaus-api.abuse.ch/#payloads-recent)
        data = json.loads(self.download(method='GET',
                                        url=self.config['payload_summaries_url']))
        return data['payloads']

    def _obtain_payload_info_dict(self, payload_name: str) -> Optional[dict]:
        if not self._should_payload_be_processed(payload_name):
            return None
        payload_info = self._fetch_payload_info(payload_name)
        if payload_info is None:
            return None
        payload_info_dict = self._extract_payload_info_dict(payload_name,
                                                            payload_info)
        return payload_info_dict

    def _should_payload_be_processed(self, payload_name: str) -> bool:
        """
        Check based on collector's state whether payload should be processed,
        or it was already processed before. See more information about this
        process in self._maintain_state() method.
        """
        for day in self._state:
            if payload_name in self._state[day]:
                return False
        return True

    def _fetch_payload_info(self, payload_name: str) -> Optional[bytes]:
        try:
            payload_info = self.download(method='POST',
                                         url=self.config['payload_info_url'],
                                         data={'sha256_hash': payload_name})
            return payload_info
        except Exception as exc:
            LOGGER.warning('Could not get payload info (%s). '
                           'Payload name: %a.',
                           exc,
                           payload_name)
            return None

    def _extract_payload_info_dict(self,
                                   payload_name: str,
                                   payload_info: bytes,
                                   ) -> Optional[dict]:
        try:
            payload_info_dict = json.loads(payload_info)
            query_status = payload_info_dict['query_status']
        except Exception as exc:
            LOGGER.warning('Skipping the payload because of weird/'
                           'unexpected problem with its info dict (%s). '
                           'Payload name: %a.',
                           make_exc_ascii_str(exc),
                           payload_name)
            return None
        if query_status != 'ok':
            LOGGER.warning('Skipping the payload because of invalid '
                           '`query_status` in its info dict: %a. '
                           'Payload name: %a.',
                           query_status,
                           payload_name)
            return None
        return payload_info_dict

    def _obtain_payload_sample(self, payload_name: str) -> Optional[bytes]:
        try:
            payload_archive = self._fetch_payload_archive(payload_name)
            extracted_payload = self._extract_payload(payload_archive,
                                                      payload_name)
        except Exception as exc:
            LOGGER.warning('Could not obtain payload sample (%s). '
                           'Payload name: %a.',
                           make_exc_ascii_str(exc),
                           payload_name)
            return None
        return extracted_payload

    def _fetch_payload_archive(self, sha256_hash: str) -> bytes:
        payload_url = urljoin(self.config['payload_dl_url'], sha256_hash)
        payload_archive = self.download(method='GET',
                                        url=payload_url)
        return payload_archive

    def _extract_payload(self,
                         payload_archive: bytes,
                         payload_name: str,
                         ) -> bytes:
        with ZipFile(BytesIO(payload_archive)) as zf:
            return zf.read(payload_name)

    def _obtain_meta_headers(self, payload_info_dict: dict) -> dict:
        meta_headers = {'tlp': 'white'}
        meta_headers.update(
            self._iter_meta_headers_from_toplevel_items(payload_info_dict))
        firstseen_url = self._get_firstseen_url(payload_info_dict)
        if firstseen_url:
            meta_headers['url'] = firstseen_url
        return meta_headers

    def _iter_meta_headers_from_toplevel_items(self,
                                               payload_info_dict: dict,
                                               ) -> Iterator[tuple[str, Any]]:
        for key in self.SAMPLE_EXCHANGE_META_HEADER_KEYS:
            if key in payload_info_dict:
                if payload_info_dict[key] is not None:
                    yield key, payload_info_dict[key]
                else:
                    LOGGER.warning(
                        'Value for meta header key %a is null '
                        '(concerns payload with sha256_hash=%a)',
                        key,
                        payload_info_dict['sha256_hash'])
            else:
                LOGGER.warning(
                    'Missing value for meta header key %a '
                    '(concerns payload with sha256_hash=%a)',
                    key,
                    payload_info_dict['sha256_hash'])

    def _get_firstseen_url(self, payload_info_dict: dict) -> Optional[str]:
        events = payload_info_dict.get('urls')
        if events:
            events_sorted_by_firstseen_and_id = sorted(
                events,
                key=operator.itemgetter('firstseen', 'url_id')
            )
            firstseen_event = events_sorted_by_firstseen_and_id[0]
            return firstseen_event['url']
        return None

    def generate_input_data_dicts(
            self,
            payload_sample_and_headers_pairs: Sequence[tuple[bytes, dict]],
            /) -> Iterator[dict[str, Any]]:
        for payload_sample, payload_headers in payload_sample_and_headers_pairs:
            yield {
                'payload_sample': payload_sample,
                'payload_headers': payload_headers,
            }

    def get_source(self, **processed_data) -> str:
        return 'abuse-ch.urlhaus-payload-samples'

    def get_output_data_body(self,
                             *,
                             payload_sample: bytes,
                             **processed_data) -> bytes:
        return payload_sample

    def get_output_prop_kwargs(self,
                               *,
                               payload_headers: dict,
                               **processed_data) -> dict:
        prop_kwargs = super().get_output_prop_kwargs(**processed_data)  # noqa
        prop_kwargs['headers'].setdefault('meta', dict())
        prop_kwargs['headers']['meta'].update(payload_headers)
        return prop_kwargs

    def after_completed_publishing(self) -> None:
        super().after_completed_publishing()
        self.save_state(self._state)


add_collector_entry_point_functions(__name__)

# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
Collectors: abuse-ch.feodotracker (TODO: other `abuse-ch` collectors...).
"""

from n6datasources.collectors.base import (
    BaseDownloadingTimeOrderedRowsCollector,
    add_collector_entry_point_functions,
)
from n6lib.csv_helpers import extract_field_from_csv_row
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class _BaseAbuseChDownloadingTimeOrderedRowsCollector(BaseDownloadingTimeOrderedRowsCollector):

    pickle_protocol = 2  # (for interoperability with the Py2 version)

    row_time_legacy_state_key = None
    time_field_index = None

    @property
    def source_config_section(self):
        return 'abusech_{}'.format(self.get_source_channel().replace('-', '_'))

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
            }
        return state

    def pick_raw_row_time(self, row):
        return extract_field_from_csv_row(row, column_index=self.time_field_index).strip()

    def clean_row_time(self, raw_row_time):
        return self.normalize_row_time(raw_row_time)

    def normalize_row_time(self, raw_row_time):
        return str(parse_iso_datetime_to_utc(raw_row_time))


class AbuseChFeodoTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '202110'

    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'feodotracker'

    def all_rows_from_orig_data(self, orig_data):
        all_rows = super().all_rows_from_orig_data(orig_data)
        return reversed(all_rows)

    def should_row_be_used(self, row):
        if not row.strip() or row.startswith('#'):
            return False
        try:
            raw_row_time = extract_field_from_csv_row(row, column_index=self.time_field_index)
            self.normalize_row_time(raw_row_time)
            return True
        except ValueError:
            return False


add_collector_entry_point_functions(__name__)

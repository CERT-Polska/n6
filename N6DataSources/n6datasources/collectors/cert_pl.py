# Copyright (c) 2020-2023 NASK. All rights reserved.

"""
Collectors: `cert-pl.shield`.
"""

from n6datasources.collectors.base import (
    BaseDownloadingTimeOrderedRowsCollector,
    add_collector_entry_point_functions,
)
from n6lib.csv_helpers import extract_field_from_csv_row
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


class CertPlShieldCollector(BaseDownloadingTimeOrderedRowsCollector):

    _ID_FIELD_INDEX = 0
    _TIME_FIELD_INDEX = 2

    def get_source(self, **processed_data):
        return 'cert-pl.shield'

    def should_row_be_used(self, row):
        if not row.strip():
            return False
        try:
            int(extract_field_from_csv_row(row,
                                           column_index=self._ID_FIELD_INDEX,
                                           delimiter='\t'))
            return True
        except ValueError:
            return False

    def pick_raw_row_time(self, row):
        return extract_field_from_csv_row(row,
                                          column_index=self._TIME_FIELD_INDEX,
                                          delimiter='\t').strip()

    def clean_row_time(self, raw_row_time):
        return str(parse_iso_datetime_to_utc(raw_row_time))

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


add_collector_entry_point_functions(__name__)

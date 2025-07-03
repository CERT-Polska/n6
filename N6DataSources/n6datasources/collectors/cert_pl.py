# Copyright (c) 2020-2025 NASK. All rights reserved.

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

    raw_format_version_tag = '202505'

    _ID_FIELD_INDEX = 0
    _TIME_FIELD_INDEX = 2

    # Warning: the configuration specification is manually overridden
    # here. Consequently, any changes to it made in superclasses will
    # *not* be propagated to this collector. The reason we override the
    # the configuration specification for this collector is that we need
    # the `url` and `row_count_mismatch_is_fatal` values to be hardcoded
    # (see `set_configuration()` below...) rather than kept customizable.
    config_spec_pattern = '''
        [{collector_class_name}]
        base_request_headers = {{}} :: py_namespaces_dict
        download_retries = 3 :: int
        download_timeout = (12.1, 25) :: download_timeout
        heartbeat_interval = 60 :: int
        state_dir = ~/.n6state :: path
    '''

    def set_configuration(self):
        super().set_configuration()
        self.config['url'] = 'https://hole.cert.pl/domains/v2/domains.csv'
        self.config['row_count_mismatch_is_fatal'] = False
        assert self.config_full[self.__class__.__name__] is self.config

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

    def _generate_count_mismatch_problems(self, prev_rows_count, rows_count, fresh_rows):
        # We deliberately override this method to restrict its operation
        # to duplicate checks on new rows - any checks related to existing
        # rows are skipped, since the source only provides data from
        # the last six months.
        if len(fresh_rows) != len(set(fresh_rows)):
            yield 'Found duplicates among the fresh rows.'

    # * Py2-to-Py3-state-transition-related:

    def get_py2_pickle_load_kwargs(self):
        return (
            super().get_py2_pickle_load_kwargs()
            # Here we are consistent with `BaseDownloadingTimeOrderedRowsCollector`:
            | dict(encoding='utf-8', errors='surrogateescape'))


add_collector_entry_point_functions(__name__)

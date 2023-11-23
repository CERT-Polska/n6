# Copyright (c) 2020-2023 NASK. All rights reserved.

"""
Parser: `sblam.spam`.
"""

import re
from datetime import timedelta

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


EXPIRES_DAYS = 7

# Sample datetime from source: `2020-04-23 03:59:01`
SBLAM_SPAM_DATETIME_REGEX = re.compile(r'''
        (\d{4}-\d{1,2}-\d{1,2}       # date
        [ ]
        \d{2}:\d{2}:\d{2})           # time
        ''', re.ASCII | re.VERBOSE)


class SblamSpamParser(BlackListParser):

    default_binding_key = "sblam.spam"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "spam",
    }

    bl_current_time_regex_group = 1
    bl_current_time_regex = SBLAM_SPAM_DATETIME_REGEX

    def parse(self, data):
        raw_events = data['csv_raw_rows']
        sblam_time = self.get_bl_current_time_from_data(data, parsed=None)
        expires = sblam_time + timedelta(days=EXPIRES_DAYS)
        for ip_record in raw_events:
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['address'] = {'ip': ip_record}
                    parsed['time'] = sblam_time
                    parsed['expires'] = expires
                except AdjusterError:
                    continue
                yield parsed


add_parser_entry_point_functions(__name__)

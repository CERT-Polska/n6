# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Parsers: `greensnow-co.list-txt`.
"""

import datetime

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


class GreenSnowCoListTxtParser(BlackListParser):

    default_binding_key = 'greensnow-co.list-txt'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    EXPIRES_DAYS = 2

    def parse(self, data):
        raw_events = data['csv_raw_rows']
        time = data['properties.timestamp']
        expires = parse_iso_datetime_to_utc(time) + datetime.timedelta(days=self.EXPIRES_DAYS)
        for ip_record in raw_events:
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['address'] = {'ip': ip_record}
                    parsed['time'] = time
                    parsed['expires'] = expires
                except AdjusterError:
                    continue
                yield parsed


add_parser_entry_point_functions(__name__)

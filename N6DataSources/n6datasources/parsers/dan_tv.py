# Copyright (c) 2019-2023 NASK. All rights reserved.

"""
Parser: `dan-tv.tor`.
"""

import csv
import datetime

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


EXPIRES_DAYS = 2


class DanTvTorParser(BlackListParser):

    default_binding_key = "dan-tv.tor"

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'tor',
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        timestamp = data['properties.timestamp']
        for row in rows:
            # there is nothing else in each row than `ip` field
            ip = row[0]
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['address'] = {'ip': ip}
                    parsed['time'] = timestamp
                    parsed['expires'] = (
                            parse_iso_datetime_to_utc(timestamp) +
                            datetime.timedelta(days=EXPIRES_DAYS))
                except AdjusterError:
                    continue
                yield parsed


add_parser_entry_point_functions(__name__)

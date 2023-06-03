# Copyright (c) 2015-2023 NASK. All rights reserved.

"""
Parser: `openphish.web`.
"""

import csv
import datetime
from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.csv_helpers import strip_fields
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class OpenphishWebBlParser(BlackListParser):

    default_binding_key = 'openphish.web-bl'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    EXPIRES_DAYS = 2

    def parse(self, data):
        raw_urls = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for url in raw_urls:
            with self.new_record_dict(data) as parsed:
                parsed['url'] = strip_fields(''.join(url))
                parsed['time'] = data['properties.timestamp']
                parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp'])
                                     + datetime.timedelta(days=self.EXPIRES_DAYS))
                yield parsed


class OpenphishWebParser(BlackListParser):

    default_binding_key = 'openphish.web'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    EXPIRES_DAYS = 2

    def parse(self, data):
        raw_urls = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for url in raw_urls:
            with self.new_record_dict(data) as parsed:
                parsed['url'] = strip_fields(''.join(url))
                parsed['time'] = data['properties.timestamp']
                parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp'])
                                     + datetime.timedelta(days=self.EXPIRES_DAYS))
                yield parsed


add_parser_entry_point_functions(__name__)

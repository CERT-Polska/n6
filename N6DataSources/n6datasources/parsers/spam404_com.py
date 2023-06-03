# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Parsers: `spam404-com.scam-list`, `spam404-com.scam-list-bl`.
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


EXPIRES_DAYS = 7


class Spam404ComScamListBlParser(BlackListParser):

    default_binding_key = 'spam404-com.scam-list-bl'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }


    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        timestamp = data['properties.timestamp']
        for row in rows:
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['fqdn'] = row[0].strip()
                    parsed['time'] = timestamp
                    parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp'])
                                         + datetime.timedelta(days=EXPIRES_DAYS))
                except AdjusterError:
                    continue
                yield parsed


class Spam404ComScamListParser(BlackListParser):
    # Note: this is a legacy parser.

    default_binding_key = 'spam404-com.scam-list'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }


    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        timestamp = data['properties.timestamp']
        for row in rows:
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['fqdn'] = row[0].strip()
                    parsed['time'] = timestamp
                    parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp'])
                                         + datetime.timedelta(days=EXPIRES_DAYS))
                except AdjusterError:
                    continue
                yield parsed


add_parser_entry_point_functions(__name__)

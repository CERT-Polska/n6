# Copyright (c) 2020-2023 NASK. All rights reserved.

"""
Parser: `darklist-de.bl`.
"""

import csv
import re
from datetime import timedelta

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)

EXPIRES_DAYS = 7

DARKLIST_DE_IP_REGEX = re.compile(r'''
        (
            (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})  # IP
            (/\d{1,2})?                           # network
        )
        ''', re.VERBOSE)

# Sample datetime from source: `21.04.2020 08:15`
DARKLIST_DE_DATETIME_REGEX = re.compile(r'''
        (\d{1,2}\.\d{1,2}\.\d{4}       # date
        [ ]
        \d{2}:\d{2})                   # time
        ''', re.VERBOSE)


class DarklistDeBlParser(BlackListParser):

    default_binding_key = "darklist-de.bl"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }

    bl_current_time_regex_group = 1
    bl_current_time_format = '%d.%m.%Y %H:%M'
    bl_current_time_regex = DARKLIST_DE_DATETIME_REGEX

    def parse(self, data):
        raw_events = csv.reader(data['csv_raw_rows'], quotechar='"')
        for record in raw_events:
            ip_record = DARKLIST_DE_IP_REGEX.search("".join(record))
            if not ip_record:
                continue
            with self.new_record_dict(data) as parsed:
                parsed['address'] = {'ip': ip_record.group(2)}
                # simple duck check to see if we might have ip
                # in cidr notation (full validation will be
                # done by record dict)
                if ip_record.group(3):
                    parsed['ip_network'] = ip_record.group(1)
                darklist_time = self.get_bl_current_time_from_data(data, parsed)
                parsed['time'] = darklist_time
                parsed['expires'] = darklist_time + timedelta(days=EXPIRES_DAYS)
                yield parsed


add_parser_entry_point_functions(__name__)

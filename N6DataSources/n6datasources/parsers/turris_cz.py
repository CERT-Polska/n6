# Copyright (c) 2016-2024 NASK. All rights reserved.

"""
Parser: `turris-cz.greylist-csv`.
"""

import csv
import datetime

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.record_dict import AdjusterError
from n6sdk.regexes import IPv4_STRICT_DECIMAL_REGEX

class TurrisCzGreylistCsv202401Parser(BlackListParser):

    default_binding_key = 'turris-cz.greylist-csv.202401'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scanning',
    }

    EXPIRES_DAYS = 8
    TIMESTRING_FORMAT = "%Y-%m-%d %H:%M:%S"

    def parse(self, data):
        turris_cz_time = data['meta']['http_last_modified']
        expires_time = datetime.datetime.strptime(
            turris_cz_time, self.TIMESTRING_FORMAT
        ) + datetime.timedelta(days=self.EXPIRES_DAYS)
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')

        for ip_record in rows:
            # collect only rows with valid ip in first column
            if IPv4_STRICT_DECIMAL_REGEX.match(ip_record[0]):
                ip, tags = ip_record
                with self.new_record_dict(data) as parsed:
                    try:
                        parsed['address'] = {'ip': ip}
                        parsed['time'] = turris_cz_time
                        parsed['expires'] = expires_time
                        parsed['name'] = f'{tags} scan'
                    except AdjusterError as e:
                        continue
                    yield parsed


add_parser_entry_point_functions(__name__)

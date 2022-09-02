# Copyright (c) 2014-2021 NASK. All rights reserved.

"""
Parsers: `abuse-ch.feodotracker.202110` (TODO: other `abuse-ch` parsers...).
"""

import csv

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class AbuseChFeodoTracker202110Parser(BaseParser):

    default_binding_key = 'abuse-ch.feodotracker.202110'

    constant_items = {
            'restriction': 'public',
            'confidence': 'medium',
            'category': 'cnc',
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # first_seen_utc,dst_ip,dst_port,c2_status,last_online,malware
            t, ip, dport, _, _, name = row
            with self.new_record_dict(data) as parsed:
                parsed.update({
                    'time': t,
                    'address': {'ip': ip},
                    'dport': dport,
                    'name': name,
                })
                yield parsed


add_parser_entry_point_functions(__name__)

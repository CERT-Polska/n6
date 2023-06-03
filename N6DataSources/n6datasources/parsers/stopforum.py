# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Parser: `stopforum.spam`.
"""

import csv

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class StopForumSpamParser(BaseParser):

    default_binding_key = 'stopforum.spam'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'spam',
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            ip, _, time = row
            with self.new_record_dict(data) as parsed:
                parsed['address'] = {'ip': ip}
                parsed['time'] = time
                yield parsed


add_parser_entry_point_functions(__name__)

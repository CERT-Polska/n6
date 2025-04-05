# Copyright (c) 2013-2025 NASK. All rights reserved.

import csv
import datetime

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


class PhishtankVerifiedParser(BlackListParser):

    default_binding_key = "phishtank.verified"
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    def parse(self, data):
        rows = csv.DictReader(data['csv_raw_rows'], quotechar='"')
        for event in rows:
            with self.new_record_dict(data) as parsed:
                parsed.update({
                    'time': event['submission_time'],
                    'url': event["url"],
                    'target': event['target'],
                    'expires': (parse_iso_datetime_to_utc(data['properties.timestamp']) +
                                datetime.timedelta(days=1)),
                })
                yield parsed


add_parser_entry_point_functions(__name__)


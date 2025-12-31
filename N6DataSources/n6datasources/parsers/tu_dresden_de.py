# Copyright (c) 2025 NASK. All rights reserved.

"""
Parsers: `tu-dresden-de.resolvers`.
"""

import json
from typing import Generator
from dateutil.parser import parse

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,

)
from n6lib.record_dict import RecordDict


class TuDresdenDeResolversParser(BaseParser):

    default_binding_key = 'tu-dresden-de.resolvers'

    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'low',
        'category': 'amplifier',
        'proto': 'udp',
        'dport': 53,
    }

    def parse(self, data) -> Generator[RecordDict, any, None]:
        raw_events = json.loads(data['raw'])
        for event in raw_events:
            with self.new_record_dict(data) as parsed:
                parsed['time'] = self._clean_event_time(event['timestamp_request'])
                parsed['address'] = {"ip": event['queried_ip']}
                parsed['name'] = 'resolver_type: ' + event['resolver_type']
                parsed['additional_data'] = 'replying_ip: ' + event['replying_ip']
                yield parsed

    def _clean_event_time(self, raw_event_time) -> str:
        parsed_raw_event_time = parse(raw_event_time)
        return str(parsed_raw_event_time.strftime('%Y-%m-%dT%H:%M:%S'))


add_parser_entry_point_functions(__name__)

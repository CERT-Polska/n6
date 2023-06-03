# Copyright (c) 2015-2023 NASK. All rights reserved.

"""
Parser: `blueliv.map`.
"""

import datetime
import json

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


LOGGER = get_logger(__name__)


CATEGORIES = {
    'MALWARE': 'malurl',
    'C_AND_C': 'cnc',
    'BACKDOOR': 'backdoor',
    'EXPLOIT_KIT': 'malurl',
    'PHISHING': 'phish',
}

IGNORED_TYPES = ['TOR_IP']

NAMES = {'MALWARE': 'binary', 'EXPLOIT_KIT': 'exploit-kit'}

EXPIRES_DAYS = 2


class BluelivMapParser(BlackListParser):

    default_binding_key = "blueliv.map"
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        '_do_not_resolve_fqdn_to_ip': True,
    }

    def parse(self, data):
        raw_events = json.loads(data['raw'])
        for event in raw_events:
            with self.new_record_dict(data) as parsed:
                parsed['time'] = data['properties.timestamp']
                parsed['url'] = event['url']
                category = CATEGORIES.get(event['type'])
                if not category:
                    if event['type'] not in IGNORED_TYPES:
                        LOGGER.warning('Unknown type received: %a. The event will be ignored.',
                                       event['type'])
                    continue
                parsed['category'] = category
                if parsed['category'] == 'malurl':
                    parsed['name'] = NAMES[event['type']]
                try:
                    parsed['address'] = {'ip': event['ip']}
                except KeyError:
                    LOGGER.warning("No ip in data")
                parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp']) +
                                     datetime.timedelta(days=EXPIRES_DAYS))
                yield parsed


add_parser_entry_point_functions(__name__)

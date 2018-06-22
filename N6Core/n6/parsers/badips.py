# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import sys
from datetime import datetime, timedelta

from n6.parsers.generic import BlackListTabDataParser, entry_point_factory
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


class BadipsServerExploitListParser(BlackListTabDataParser):

    _time_delta = timedelta(days=2)

    default_binding_key = 'badips-com.server-exploit-list'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'server-exploit',
    }
    field_sep = ';'

    def process_row_fields(self, data, parsed, ip, name, *fields):
        parsed['name'] = name
        parsed['address'] = {'ip': ip}
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = parse_iso_datetime_to_utc(parsed['time']) + self._time_delta


entry_point_factory(sys.modules[__name__])

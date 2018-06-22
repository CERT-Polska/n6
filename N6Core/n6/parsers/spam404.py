# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import sys

from n6.parsers.generic import (
    BlackListTabDataParser,
    entry_point_factory,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class Spam404Parser(BlackListTabDataParser):

    default_binding_key = 'spam404-com.scam-list'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }

    _time_delta = datetime.timedelta(days=8)

    field_sep = None
    skip_blank_rows = True

    def process_row_fields(self, data, parsed, fqdn):
        parsed['fqdn'] = fqdn.strip()
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp'])
                             + self._time_delta)
        return parsed


entry_point_factory(sys.modules[__name__])

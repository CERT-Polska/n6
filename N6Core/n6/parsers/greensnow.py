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


class GreenSnowParser(BlackListTabDataParser):

    default_binding_key = 'greensnow-co.list-txt'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    field_sep = None

    def process_row_fields(self, data, parsed, ip):
        parsed['address'] = {'ip': ip}
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = parse_iso_datetime_to_utc(data['properties.timestamp']) + \
                            datetime.timedelta(days=2)
        return parsed


entry_point_factory(sys.modules[__name__])

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


class DnsBhMalwareDomainsCom201412Parser(BlackListTabDataParser):

    default_binding_key = 'dns-bh.malwaredomainscom.201412'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    ignored_row_prefixes = '#'
    field_sep = "\t"

    def process_row_fields(self, data, parsed,
                           _empty, _next_date, fqdn, *fields):
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp']) +
                             datetime.timedelta(days=2))
        parsed['fqdn'] = fqdn


# parser for data (already enriched) from the old system...
class DnsBhMalwareDomainsComParser(BlackListTabDataParser):

    default_binding_key = 'dns-bh.malwaredomainscom'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    ignored_row_prefixes = '#'
    field_sep = "\t"

    def process_row_fields(self, data, parsed,
                           ip, _asn, _next_date, fqdn, _type, _origin, _dateverified, *fields):
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp']) +
                             datetime.timedelta(days=2))
        parsed['fqdn'] = fqdn
        parsed['address'] = {'ip': ip}


entry_point_factory(sys.modules[__name__])

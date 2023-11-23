# Copyright (c) 2014-2023 NASK. All rights reserved.

"""
Parsers: `spamhaus.bots`, `spamhaus.drop`, `spamhaus.edrop`.
"""

import csv
import re
from datetime import (
    datetime,
    timedelta,
)

from n6datasources.parsers.base import (
    BaseParser,
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.csv_helpers import (
    split_csv_row,
    strip_fields,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class _BaseSpamhausBlacklistParser(BlackListParser):

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    EXPIRES_DAYS = 2

    bl_current_time_regex = re.compile(r"Last-Modified:[ ]*"
                                       r"(?P<datetime>\w{3},[ ]*\d{1,2}[ ]*\w{3}[ ]*"
                                       r"\d{4}[ ]*(\d{2}:?){3}[ ]*GMT)",
                                       re.ASCII | re.IGNORECASE)
    bl_current_time_format = "%a, %d %b %Y %H:%M:%S GMT"

    def parse(self, data):
        raw_events = csv.reader(data['csv_raw_rows'], quotechar='"')
        for row in raw_events:
            row = row[0]
            if row.startswith(';'):
                continue
            fields = split_csv_row(row, delimiter=';')
            if len(fields) == 2:
                cidr, sbl = strip_fields(fields)
            elif len(fields) == 3:
                _, cidr, sbl = strip_fields(fields)
            else:
                raise ValueError('Incorrect amount of fields. Probably source has changed its format')
            with self.new_record_dict(data) as parsed:
                parsed['time'] = data['properties.timestamp']
                parsed['expires'] = (parse_iso_datetime_to_utc(data['properties.timestamp']) +
                                     timedelta(days=self.EXPIRES_DAYS))
                parsed['ip_network'] = cidr
                parsed['additional_data'] = sbl
                parsed['address'] = {'ip': self._ip_from_network(cidr)}
                yield parsed

    @staticmethod
    def _ip_from_network(ip_network):
        ip, cidr = ip_network.split('/')
        if 0 <= int(cidr) <= 32:
            return ip
        else:
            raise ValueError


class SpamhausDropParser(_BaseSpamhausBlacklistParser):

    default_binding_key = 'spamhaus.drop'


class SpamhausEdrop202303Parser(_BaseSpamhausBlacklistParser):

    default_binding_key = 'spamhaus.edrop'


class SpamhausBotsParser(BaseParser):

    default_binding_key = 'spamhaus.bots'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            if row[0].startswith(';'):
                continue
            ip, _asn, _cc, timestamp, name, fqdn, dip, dport, sport, proto = strip_fields(row)
            with self.new_record_dict(data) as parsed:
                parsed['time'] = datetime.utcfromtimestamp(int(timestamp))
                parsed['address'] = {'ip': ip}
                if name:
                    parsed['name'] = name
                if fqdn:
                    parsed['fqdn'] = fqdn
                if dip:
                    parsed['dip'] = dip
                if dport:
                    parsed['dport'] = dport
                if sport:
                    parsed['sport'] = sport
                if proto:
                    parsed['proto'] = proto
                yield parsed


add_parser_entry_point_functions(__name__)

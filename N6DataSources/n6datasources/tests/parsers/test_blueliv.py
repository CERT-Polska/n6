# Copyright (c) 2015-2023 NASK. All rights reserved.

import datetime
import json
import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.blueliv import BluelivMapParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestBluelivMapParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'blueliv.map'
    PARSER_CLASS = BluelivMapParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        '_do_not_resolve_fqdn_to_ip': True
    }
    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          datetime.timedelta(days=2))

    def cases(self):
        yield (
            json.dumps(
                [
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example1.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:00+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-05-24T04:03:22+0000',
                        'lastSeenAt': '2015-08-26T00:55:02+0000',
                        'ip': '1.1.1.1',
                        'latitude': 11.1111,
                        'type': 'MALWARE',
                     },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example2.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:04+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-08-11T10:48:59+0000',
                        'lastSeenAt': '2015-08-26T00:54:35+0000',
                        'ip': '2.2.2.2',
                        'latitude': 11.1111,
                        'type': 'C_AND_C',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example3.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:04+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-08-11T10:48:59+0000',
                        'lastSeenAt': '2015-08-26T00:54:35+0000',
                        'ip': '3.3.3.3',
                        'latitude': 11.1111,
                        'type': 'TOR_IP',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example4.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:04+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-08-11T10:48:59+0000',
                        'lastSeenAt': '2015-08-26T00:54:35+0000',
                        'ip': '3.3.3.3',
                        'latitude': 11.1111,
                        'type': 'NEW_UNKNOWN',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example5.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:04+0000',
                        'longitude': 11.1111,
                        'firstSeenAt': '2015-08-11T10:48:59+0000',
                        'lastSeenAt': '2015-08-26T00:54:35+0000',
                        'ip': '3.3.3.3',
                        'latitude': 38.0,
                        'type': 'PHISHING',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example6.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:04+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-06-01T12:00:07+0000',
                        'lastSeenAt': '2015-08-26T00:55:04+0000',
                        'ip': '4.4.4.4',
                        'latitude': 11.1111,
                        'type': 'BACKDOOR',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example7.com',
                        'country': 'US',
                        'updatedAt': '2015-08-26T01:00:08+0000',
                        'longitude': -11.1111,
                        'firstSeenAt': '2015-05-09T22:01:00+0000',
                        'lastSeenAt': '2015-08-26T00:55:10+0000',
                        'ip': '5.5.5.5',
                        'latitude': 11.1111,
                        'type': 'EXPLOIT_KIT',
                    },
                    {
                        'status': 'ONLINE',
                        'url': 'http://www.example8.com',
                        'lastSeenAt': '2015-09-04T13:43:21+0000',
                        'firstSeenAt': '2015-08-17T08:03:23+0000',
                        'updatedAt': '2015-09-04T13:49:08+0000',
                        'type': 'MALWARE',
                    },
                ],
            ).encode('utf-8'),
            [
                dict(
                    self.get_bl_items(1, 6),
                    category='malurl',
                    name='binary',
                    address=[{'ip': '1.1.1.1'}],
                    url='http://www.example1.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 6),
                    category='cnc',
                    address=[{'ip': '2.2.2.2'}],
                    url='http://www.example2.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(3, 6),
                    category='phish',
                    address=[{'ip': '3.3.3.3'}],
                    url='http://www.example5.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(4, 6),
                    category='backdoor',
                    address=[{'ip': '4.4.4.4'}],
                    url='http://www.example6.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(5, 6),
                    category='malurl',
                    name='exploit-kit',
                    address=[{'ip': '5.5.5.5'}],
                    url='http://www.example7.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(6, 6),
                    category='malurl',
                    name='binary',
                    url='http://www.example8.com',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ],
        )

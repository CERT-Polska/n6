# Copyright (c) 2016-2025 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.turris_cz import TurrisCzGreylistCsv202401Parser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.record_dict import BLRecordDict


class TestTurrisCzGreylistCsv202401Parser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'turris-cz.greylist-csv'
    PARSER_CLASS = TurrisCzGreylistCsv202401Parser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scanning',
    }
    PARSER_RAW_FORMAT_VERSION_TAG = '202401'
    
    http_last_modified = "2023-12-21 10:14:00"
    expires_time = "2023-12-23 10:14:00"  # 2 day later
    MESSAGE_EXTRA_HEADERS = {'meta': {'http_last_modified': http_last_modified}}

    def cases(self):
        yield (
            # 2 header lines, 6 valid ips with tags, 2 invalid ips (ipv6)
            (
                b'# For the terms of use see https://view.sentinel.turris.cz/greylist-data/LICENSE.txt\n'
                b'Address,Tags\n'
                b'0.0.0.1,telnet\n'
                b'0.0.0.2,telnet\n'
                b'0.0.0.3,telnet\n'
                b'0.0.0.4,telnet\n'
                b'0.0.0.5,telnet\n'
                b'0.0.0.0.0.0.0.16,http_scan\n'
                b'0.0.0.0.0.0.0.32,dns\n'
                b'0.0.0.6,\"ftp,http,smtp,telnet\"'
            ),
            [
                dict(
                    self.get_bl_items(1, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.1"}],
                    expires=self.expires_time,
                    name='telnet scan',
                ),
                dict(
                    self.get_bl_items(2, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.2"}],
                    expires=self.expires_time,
                    name='telnet scan',
                ),
                dict(
                    self.get_bl_items(3, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.3"}],
                    expires=self.expires_time,
                    name='telnet scan',
                ),
                dict(
                    self.get_bl_items(4, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.4"}],
                    expires=self.expires_time,
                    name='telnet scan',
                ),
                dict(
                    self.get_bl_items(5, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.5"}],
                    expires=self.expires_time,
                    name='telnet scan',
                ),
                dict(
                    self.get_bl_items(6, 6, self.http_last_modified),
                    time=self.http_last_modified,
                    address=[{'ip': "0.0.0.6"}],
                    expires=self.expires_time,
                    name='ftp,http,smtp,telnet scan',
                )
            ],
        )

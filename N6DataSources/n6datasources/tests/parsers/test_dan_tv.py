# Copyright (c) 2019-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.dan_tv import DanTvTorParser
from n6datasources.parsers.base import BlackListParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin

from n6lib.record_dict import BLRecordDict


class TestDanTvTorParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'dan-tv.tor'
    PARSER_CLASS = DanTvTorParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'tor',
    }

    download_time = "2014-01-10 10:14:00"
    expires_time = "2014-01-12 10:14:00"

    def cases(self):
        yield (
            (
                b"1.1.1.1\n"
                b"2.2.2.2\n"
                b"1a1a:1a1a:0000:0000:1a1a:1a1a:1a1a:1111\n"
                b"2b2b:2b2b:0002:0000:0000:0000:0000:002b"
            ),
            [
                dict(
                    self.get_bl_items(1, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "1.1.1.1"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(2, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "2.2.2.2"}],
                    expires=self.expires_time,
                )
            ],
        )

        yield (
            (
                b"1a1a:1a1a:0000:0000:0000:0000:0000:001a\n"
                b"2b2b:2b2b:0000:0000:0000:0000:0000:002b\n"
                b"3.3.3.3\n"
                b"4.4.4.4"
            ),
            [
                dict(
                    self.get_bl_items(1, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "3.3.3.3"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(2, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "4.4.4.4"}],
                    expires=self.expires_time,
                )
            ],
        )

        yield (
            (
                b"5.5.5.5\n"
                b"2b2b:2b2b:0000:0000:0000:0000:0000:002b\n"
                b"6.6.6.6"
            ),
            [
                dict(
                    self.get_bl_items(1, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "5.5.5.5"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(2, 2, self.download_time),
                    time=self.download_time,
                    address=[{'ip': "6.6.6.6"}],
                    expires=self.expires_time,
                )
            ],
        )

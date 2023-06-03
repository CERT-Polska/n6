# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.greensnow_co import GreenSnowCoListTxtParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestGreenSnowCoListTxtParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'greensnow-co.list-txt'
    PARSER_CLASS = GreenSnowCoListTxtParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created)
                          + datetime.timedelta(days=2))

    def cases(self):
        yield (
            b'1.1.1.1\n'
            b'2.2.2.2\n'
            b'3.3.3.3\n'
            b'4.4.4.4\n'
            b'invalid_row\n'
            b'5.5.5.5\n'
            b'6.6.6.6\n'
            b'7.7.7.7\n',
            [
                dict(
                    self.get_bl_items(1, 7),
                    address=[{'ip': '1.1.1.1'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(2, 7),
                    address=[{'ip': '2.2.2.2'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(3, 7),
                    address=[{'ip': '3.3.3.3'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(4, 7),
                    address=[{'ip': '4.4.4.4'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(5, 7),
                    address=[{'ip': '5.5.5.5'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(6, 7),
                    address=[{'ip': '6.6.6.6'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
                dict(
                    self.get_bl_items(7, 7),
                    address=[{'ip': '7.7.7.7'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
            ],
        )

        # Invalid data
        yield (
            b"# Invalid data\n"
            b"everywhere...\n",
            ValueError
        )

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import unittest

from n6.parsers.generic import BlackListTabDataParser
from n6.parsers.greensnow import GreenSnowParser
from n6.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestGreenSnowParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'greensnow-co.list-txt'
    PARSER_CLASS = GreenSnowParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created)
                          + datetime.timedelta(days=2))

    def cases(self):
        yield (
            '1.1.1.1\n'
            '2.2.2.2\n'
            '3.3.3.3\n',
            [
                dict(
                    self.get_bl_items(1, 3),
                    address=[{'ip': '1.1.1.1'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),

                dict(
                    self.get_bl_items(2, 3),
                    address=[{'ip': '2.2.2.2'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),

                dict(
                    self.get_bl_items(3, 3),
                    address=[{'ip': '3.3.3.3'}],
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
            ]
        )

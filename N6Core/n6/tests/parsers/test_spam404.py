# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import datetime
import unittest

from n6.parsers.generic import BlackListTabDataParser
from n6.parsers.spam404 import Spam404Parser
from n6.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestSpam404Parser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'spam404-com.scam-list'
    PARSER_CLASS = Spam404Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }

    MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          datetime.timedelta(days=8))

    def cases(self):
        yield (
            'example-1.com \n'
            'example-2.com \n'
            'example-3.com \n'
            ,
            [
                dict(
                    self.get_bl_items(1, 3),
                    fqdn='example-1.com',
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),

                dict(
                    self.get_bl_items(2, 3),
                    fqdn='example-2.com',
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),

                dict(
                    self.get_bl_items(3, 3),
                    fqdn='example-3.com',
                    time=self.message_created,
                    expires=self.MESSAGE_EXPIRES,
                ),
            ]
        )

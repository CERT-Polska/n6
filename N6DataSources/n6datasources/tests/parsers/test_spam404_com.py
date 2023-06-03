# Copyright (c) 2016-2023 NASK. All rights reserved.

import datetime
import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.spam404_com import (
    Spam404ComScamListParser,
    Spam404ComScamListBlParser,
)
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestSpam404ComScamListBlParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'spam404-com.scam-list-bl'
    PARSER_CLASS = Spam404ComScamListBlParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }

    MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          datetime.timedelta(days=7))

    def cases(self):
        yield (
            b'example-1.com \n'
            b'example-2.com \n'
            b'example-3.com \n'
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


class TestSpam404ComScamListParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'spam404-com.scam-list'
    PARSER_CLASS = Spam404ComScamListParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scam',
    }

    MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          datetime.timedelta(days=7))

    def cases(self):
        yield (
            b'example-1.com \n'
            b'example-2.com \n'
            b'example-3.com \n'
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

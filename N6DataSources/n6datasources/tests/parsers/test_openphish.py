# Copyright (c) 2015-2023 NASK. All rights reserved.

import datetime
import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.openphish import (
    OpenphishWebBlParser,
    OpenphishWebParser,
)
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestOpenphishWebBlParser(ParserTestMixin, unittest.TestCase):
    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created)
                          + datetime.timedelta(days=2))

    RECORD_DICT_CLASS = BLRecordDict
    PARSER_SOURCE = 'openphish.web-bl'
    PARSER_CLASS = OpenphishWebBlParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    def cases(self):
        yield (
            b'http://www.example1.com/\n'
            b'http://www.example2.com/wp-includes/js/jquery/upgrade/newwells/\n'
            b'http://www.example3.com/ wp-includes/js/jquery/upgrade/newwells/ \n'
            b'http://www.example4.com/\twp-includes/js/jquery/upgrade/newwells/\n',
            [
                dict(
                    self.get_bl_items(1, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example1.com/',
                ),
                dict(
                    self.get_bl_items(2, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example2.com/wp-includes/js/jquery/upgrade/newwells/',
                ),
                dict(
                    self.get_bl_items(3, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example3.com/ wp-includes/js/jquery/upgrade/newwells/',
                ),
                dict(
                    self.get_bl_items(4, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example4.com/\twp-includes/js/jquery/upgrade/newwells/',
                ),
            ],
        )


class TestOpenphishWebParser(ParserTestMixin, unittest.TestCase):
    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created)
                          + datetime.timedelta(days=2))

    RECORD_DICT_CLASS = BLRecordDict
    PARSER_SOURCE = 'openphish.web'
    PARSER_CLASS = OpenphishWebParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    def cases(self):
        yield (
            b'http://www.example1.com/\n'
            b'http://www.example2.com/wp-includes/js/jquery/upgrade/newwells/\n'
            b'http://www.example3.com/ wp-includes/js/jquery/upgrade/newwells/ \n'
            b'http://www.example4.com/\twp-includes/js/jquery/upgrade/newwells/\n',
            [
                dict(
                    self.get_bl_items(1, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example1.com/',
                ),
                dict(
                    self.get_bl_items(2, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example2.com/wp-includes/js/jquery/upgrade/newwells/',
                ),
                dict(
                    self.get_bl_items(3, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example3.com/ wp-includes/js/jquery/upgrade/newwells/',
                ),
                dict(
                    self.get_bl_items(4, 4),
                    time=self.message_created,
                    expires=self.message_expires,
                    url='http://www.example4.com/\twp-includes/js/jquery/upgrade/newwells/',
                ),
            ],
        )

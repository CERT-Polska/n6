# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import unittest
from datetime import timedelta

from n6.parsers.badips import BadipsServerExploitListParser
from n6.parsers.generic import BlackListTabDataParser
from n6.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


def _cases_for_badips_server_exploit_list_parser(self):
    yield ('123.123.123.123;test ssh attack',
           [
               dict(
                   self.get_bl_items(1, 1),
                   address=[{'ip': '123.123.123.123'}],
                   name='test ssh attack',
                   time=self.message_created,
                   expires=self.message_expires)
           ])
    yield ('123.123.123.123;test ssh attack\n222.222.222.222;test ssh attack',
           [
               dict(
                   self.get_bl_items(1, 2),
                   address=[{'ip': '123.123.123.123'}],
                   name='test ssh attack',
                   time=self.message_created,
                   expires=self.message_expires),
               dict(
                   self.get_bl_items(2, 2),
                   address=[{'ip': '222.222.222.222'}],
                   name='test ssh attack',
                   time=self.message_created,
                   expires=self.message_expires)
           ])


class TestBadipsServerExploitListParser(ParserTestMixin, unittest.TestCase):

    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CLASS = BadipsServerExploitListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'server-exploit',
    }
    RECORD_DICT_CLASS = BLRecordDict
    PARSER_SOURCE = 'badips-com.server-exploit-list'

    cases = _cases_for_badips_server_exploit_list_parser

    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          timedelta(days=2))

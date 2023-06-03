# Copyright (c) 2020-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.sblam import SblamSpamParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.record_dict import BLRecordDict


class TestSblamSpamParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'sblam.spam'
    PARSER_CLASS = SblamSpamParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'spam',
    }

    ips_time = '2020-04-23 03:59:01'

    # This value should be changed alongside
    # `EXPIRES_DAYS` variable in the parsers module
    expires_time = '2020-04-30 03:59:01'

    def cases(self):
        # Typical cases, we expect to yield 6 events (last one is not a valid IP record)
        yield (
            (
                b"# HTTP spam sources identified by http://sblam.com.\n"
                b"# Generated 2020-04-23 03:59:01\n"
                b"# This is a list of HTML form (comment) spammers--not for blocking e-mail spam!\n"
                b"1.1.1.1\n"
                b"2.2.2.2\n"
                b"3.3.3.3\n"
                b"4.4.4.4\n"
                b"5.5.5.5\n"
                b"6.6.6.6\n"
                b"1111.2222.3333.4444"
            ),
            [
                dict(
                    self.get_bl_items(1, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "1.1.1.1"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(2, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "2.2.2.2"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(3, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "3.3.3.3"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(4, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "4.4.4.4"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(5, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "5.5.5.5"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(6, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "6.6.6.6"}],
                    expires=self.expires_time,
                ),
            ],
        )

        # Invalid data
        yield (
            b"# HTTP spam sources identified by http://sblam.com.\n"
            b"# Generated 2020-04-23 03:59:01\n"
            b"# This is a list of HTML form (comment) spammers--not for blocking e-mail spam!\n",
            ValueError
        )

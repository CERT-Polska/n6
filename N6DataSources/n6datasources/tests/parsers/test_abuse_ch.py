# Copyright (c) 2014-2022 NASK. All rights reserved.

import unittest

from n6datasources.parsers.abuse_ch import AbuseChFeodoTracker202110Parser
from n6datasources.parsers.base import BaseParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestAbuseChFeodotracker202110Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.feodotracker'
    PARSER_CLASS = AbuseChFeodoTracker202110Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'cnc'
    }

    def cases(self):
        yield (
            b'2019-05-27 13:36:27,0.0.0.0,447,online,2019-05-28,TrickBot\n'
            b'this, is, one, very, wrong, line\n'
            b'2019-05-25 01:30:36,0.0.0.0,443,online,2019-05-27,Heodo\n'
            b'2019-05-16 19:43:27,0.0.0.0,8080,online,2019-05-22,Heodo\n',
            [
                {
                    'name': 'trickbot',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 447,
                    'time': '2019-05-27 13:36:27',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 443,
                    'time': '2019-05-25 01:30:36',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 8080,
                    'time': '2019-05-16 19:43:27',
                },
            ]
        )

        yield (
            b'INVALID_DATA',
            ValueError
        )

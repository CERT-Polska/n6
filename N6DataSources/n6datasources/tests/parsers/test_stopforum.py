# Copyright (c) 2016-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.stopforum import StopForumSpamParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestStopForumParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'stopforum.spam'
    PARSER_CLASS = StopForumSpamParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'spam',
    }

    def cases(self):
        yield (
            b'"1.1.1.1","206","2016-10-02 15:16:47"\n'
            b'"2.2.2.2","659","2016-10-03 09:56:28"\n',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    time='2016-10-02 15:16:47',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    time='2016-10-03 09:56:28',
                ),
            ],
        )

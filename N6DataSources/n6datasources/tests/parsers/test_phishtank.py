# Copyright (c) 2013-2025 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BlackListParser
from n6datasources.parsers.phishtank import PhishtankVerifiedParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.record_dict import BLRecordDict


class TestPhishtankVerifiedParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'phishtank.verified'
    PARSER_CLASS = PhishtankVerifiedParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'phish',
    }

    RECORD_DICT_CLASS = BLRecordDict

    def cases(self):
        yield (
            b"""phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target
2222220,http://example1-phish.com/phish,http://www.phishtank.com/phish_detail.php?phish_id=2222220,2017-04-26T09:03:57+00:00,yes,2017-04-26T10:48:17+00:00,yes,Group
2222221,http://example2-phish.com/phish,http://www.phishtank.com/phish_detail.php?phish_id=2222221,2023-04-26T07:40:51+00:00,yes,2017-04-26T10:26:27+00:00,yes,Other
2222222,http://example3-phish.com/phish,http://www.phishtank.com/phish_detail.php?phish_id=2222222,2017-04-26T06:37:50+00:00,yes,2017-04-26T09:23:04+00:00,yes,"Other2"
"""
            ,
            [
                dict(
                    self.get_bl_items(1, 3, bl_current_time="2014-01-10 10:14:00"),
                    url="http://example1-phish.com/phish",
                    time="2017-04-26 09:03:57",
                    target="Group",
                    expires="2014-01-11 10:14:00",
                ),
                dict(
                    self.get_bl_items(2, 3, bl_current_time="2014-01-10 10:14:00"),
                    url="http://example2-phish.com/phish",
                    time="2023-04-26 07:40:51",
                    target="Other",
                    expires="2014-01-11 10:14:00",
                ),
                dict(
                     self.get_bl_items(3, 3, bl_current_time="2014-01-10 10:14:00"),
                     url="http://example3-phish.com/phish",
                     time="2017-04-26 06:37:50",
                     target="Other2",
                     expires="2014-01-11 10:14:00",
                ),
            ]
        )

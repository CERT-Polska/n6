# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import unittest

from n6.parsers.packetmail import (
    PacketmailOthersParser,
    PacketmailRatwareParser,
    PacketmailScanningParser,
    _PacketmailBaseParser,
)
from n6.tests.parsers._parser_test_mixin import ParserTestMixIn


class TestPacketmailScanningParser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'packetmail-net.list'
    PARSER_CLASS = PacketmailScanningParser
    PARSER_BASE_CLASS = _PacketmailBaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scanning',
        'origin': 'honeypot',
    }

    def cases(self):
        yield (
            '#\n'
            '\n'
            '# IP; last_seen; context; cumulative history\n'
            '1.1.1.1; 2016-10-17 10:00:04; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 1\n'
            '2.2.2.2; 2016-10-17 10:02:48; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 5\n'
            '3.3.3.3; 2016-11-17 10:05:38; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 1\n',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    time='2016-10-17 08:00:04',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    time='2016-10-17 08:02:48',
                ),
                dict(
                    address=[{'ip': '3.3.3.3'}],
                    time='2016-11-17 09:05:38',
                ),
            ]
        )

class TestPacketmailRatwareParser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'packetmail-net.ratware-list'
    PARSER_CLASS = PacketmailRatwareParser
    PARSER_BASE_CLASS = _PacketmailBaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'spam',
        'origin': 'honeypot',
    }

    def cases(self):
        yield (
            '#\n'
            '\n'
            '# IP; last_seen; context\n'
            '1.1.1.1; 2016-10-18 08:35:46; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'
            '2.2.2.2; 2016-10-18 08:36:19; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'
            '3.3.3.3; 2016-11-18 08:54:43; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    time='2016-10-18 06:35:46',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    time='2016-10-18 06:36:19',
                ),
                dict(
                    address=[{'ip': '3.3.3.3'}],
                    time='2016-11-18 07:54:43',
                ),
            ]
        )


class TestPacketmailOthersParser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'packetmail-net.others-list'
    PARSER_CLASS = PacketmailOthersParser
    PARSER_BASE_CLASS = _PacketmailBaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
        'origin': 'honeypot',
    }

    def cases(self):
        yield (
            '#\n'
            '\n'
            '# This list was last updated on Thu Oct 20 03:05:05 CDT 2016\n'
            '3	11111111111	2016-10-06 07:34:34	11111111111	2016-10-06 14:20:28	1.1.1.1\n'
            '4	11111111111	2016-10-06 01:30:10	11111111111	2016-10-06 15:36:10	2.2.2.2\n'
            '3	11111111111	2016-10-06 00:58:29	11111111111	2016-11-06 15:36:10	3.3.3.3\n',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    time='2016-10-06 12:20:28',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    time='2016-10-06 13:36:10',
                ),
                dict(
                    address=[{'ip': '3.3.3.3'}],
                    time='2016-11-06 14:36:10',
                ),
            ]
        )

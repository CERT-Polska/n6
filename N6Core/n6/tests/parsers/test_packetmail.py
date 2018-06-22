# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

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
            '79.23.3.105; 2016-10-17 10:00:04; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 1\n'
            '211.51.97.227; 2016-10-17 10:02:48; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 5\n'
            '122.116.202.181; 2016-11-17 10:05:38; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 1\n',
            [
                dict(
                    address=[{'ip': '79.23.3.105'}],
                    time='2016-10-17 08:00:04',
                ),
                dict(
                    address=[{'ip': '211.51.97.227'}],
                    time='2016-10-17 08:02:48',
                ),
                dict(
                    address=[{'ip': '122.116.202.181'}],
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
            '23.103.200.99; 2016-10-18 08:35:46; Hangup, ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'
            '172.245.173.206; 2016-10-18 08:36:19; Hangup, ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'
            '191.242.74.131; 2016-11-18 08:54:43; Hangup, ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n',
            [
                dict(
                    address=[{'ip': '23.103.200.99'}],
                    time='2016-10-18 06:35:46',
                ),
                dict(
                    address=[{'ip': '172.245.173.206'}],
                    time='2016-10-18 06:36:19',
                ),
                dict(
                    address=[{'ip': '191.242.74.131'}],
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
            '3	1475757274	2016-10-06 07:34:34	1475781628	2016-10-06 14:20:28	207.182.142.68\n'
            '4	1475735410	2016-10-06 01:30:10	1475786170	2016-10-06 15:36:10	37.59.39.53\n'
            '3	1475733509	2016-10-06 00:58:29	1475786170	2016-11-06 15:36:10	50.63.117.96\n',
            [
                dict(
                    address=[{'ip': '207.182.142.68'}],
                    time='2016-10-06 12:20:28',
                ),
                dict(
                    address=[{'ip': '37.59.39.53'}],
                    time='2016-10-06 13:36:10',
                ),
                dict(
                    address=[{'ip': '50.63.117.96'}],
                    time='2016-11-06 14:36:10',
                ),
            ]
        )

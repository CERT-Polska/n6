# -*- coding: utf-8 -*-

# Copyright (c) 2013-2020 NASK. All rights reserved.

import unittest

from n6.parsers.packetmail import (
    PacketmailOthersParser,
    PacketmailRatwareParser,
    PacketmailScanningParser,
    _PacketmailBaseParser,
)
from n6.tests.parsers._parser_test_mixin import ParserTestMixin


class TestPacketmailScanningParser(ParserTestMixin, unittest.TestCase):

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
                ' 1; Cumulative honeypot hits for IP over all days: 1\n'

            # DST-related corner case: impossible (non-existent) time
            '4.4.4.4; 2020-03-29 02:45:01; Honeypot hits in 3600 hash-collection seconds:'
                ' 1; Cumulative honeypot hits for IP over all days: 1\n'

            # DST-related corner case: ambiguous time
            '5.5.5.5; 2020-10-25 02:38:02; Honeypot hits in 3600 hash-collection seconds:'
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
                dict(
                    address=[{'ip': '4.4.4.4'}],
                    time='2020-03-29 01:45:01',
                ),
                dict(
                    address=[{'ip': '5.5.5.5'}],
                    time='2020-10-25 01:38:02',
                ),
            ]
        )

class TestPacketmailRatwareParser(ParserTestMixin, unittest.TestCase):

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
            '3.3.3.3; 2016-11-18 08:54:43; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'

            # DST-related corner case: impossible (non-existent) time
            '4.4.4.4; 2020-03-29 02:45:01; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n'

            # DST-related corner case: ambiguous time
            '5.5.5.5; 2020-10-25 02:38:02; ignores RFC 5321 MAIL FROM/RCPT TO greeting delay values\n',

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
                dict(
                    address=[{'ip': '4.4.4.4'}],
                    time='2020-03-29 01:45:01',
                ),
                dict(
                    address=[{'ip': '5.5.5.5'}],
                    time='2020-10-25 01:38:02',
                ),
            ]
        )


class TestPacketmailOthersParser(ParserTestMixin, unittest.TestCase):

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
            '3\t11111111111\t2016-10-06 07:34:34\t11111111111\t2016-10-06 14:20:28\t1.1.1.1\n'
            '4\t11111111111\t2016-10-06 01:30:10\t11111111111\t2016-10-06 15:36:10\t2.2.2.2\n'
            '3\t11111111111\t2016-10-06 00:58:29\t11111111111\t2016-11-06 15:36:10\t3.3.3.3\n'

            # DST-related corner case: impossible (non-existent) time
            '3\t11111111111\txxxx-xx-xx xx:xx:xx\t11111111111\t2020-03-29 02:45:01\t4.4.4.4\n'

            # DST-related corner case: ambiguous time
            '3\t11111111111\txxxx-xx-xx xx:xx:xx\t11111111111\t2020-10-25 02:38:02\t5.5.5.5\n',

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
                dict(
                    address=[{'ip': '4.4.4.4'}],
                    time='2020-03-29 01:45:01',
                ),
                dict(
                    address=[{'ip': '5.5.5.5'}],
                    time='2020-10-25 01:38:02',
                ),
            ]
        )

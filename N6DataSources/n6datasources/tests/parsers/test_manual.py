# Copyright (c) 2013-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6datasources.parsers.manual import ManualParser


class _ManualParserTestMixIn(ParserTestMixin):

    def test_basics(self):
        # We skip checking parser's binding key because this parser might use
        # two different source channels.
        self.assertIn(self.PARSER_BASE_CLASS, self.PARSER_CLASS.__bases__)
        self.assertEqual(self.PARSER_CLASS.constant_items,
                         self.PARSER_CONSTANT_ITEMS)


class TestManualParserUnrestricted(_ManualParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'manual.unrestricted'
    PARSER_CLASS = ManualParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {}
    # Headers sent from ManualCollector (below command which might be used to run collector):
    # n6collector_manual --source_channel unrestricted --category bots --confidence low --restriction public --origin c2 --field_sep ',' --comment_prefix '#' --column_spec 'time,ip,-,-,dip,fqdn'
    MESSAGE_EXTRA_HEADERS = {
        'meta': {
            'event_base': {
                'category': 'bots',
                'confidence': 'low',
                'restriction': 'public',
                'origin': 'c2',
            },
            'parsing_info': {
                'field_separator': ',',
                'comment_prefix': '#',
                'column_spec': 'time,ip,-,-,dip,fqdn',
                'time_format': '%Y-%m-%d %H:%M:%S'
            },
        }
    }

    def cases(self):
        yield (
            b'# Uczestnicy botnetu abcd\n'
            b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain\n'
            b'2015-07-03 12:00:00,1.1.1.1,AS654321,CA,2.2.2.2,example-1.com\n'
            b'2015-07-03 13:00:00,3.3.3.3,AS1234,SE,4.4.4.4,example-2.com\n'
            b'2015-07-03 14:00:00,5.5.5.5,AS5678,US,6.6.6.6,example-3.com\n'
            ,
            [
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'1.1.1.1'}],
                    fqdn=u'example-1.com',
                    source=u'manual.unrestricted',
                    time=u'2015-07-03 12:00:00',
                    dip=u'2.2.2.2',
                ),
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'3.3.3.3'}],
                    fqdn=u'example-2.com',
                    source=u'manual.unrestricted',
                    time=u'2015-07-03 13:00:00',
                    dip=u'4.4.4.4',
                ),
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'5.5.5.5'}],
                    fqdn=u'example-3.com',
                    source=u'manual.unrestricted',
                    time=u'2015-07-03 14:00:00',
                    dip=u'6.6.6.6',
                ),
            ]
        )


class TestManualParserPl(_ManualParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'manual.pl'
    PARSER_CLASS = ManualParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {}
    # Headers sent from ManualCollector (below command which might be used to run collector):
    # n6collector_manual --source_channel pl --category bots --confidence low --restriction public --origin c2 --field_sep ',' --comment_prefix '#' --column_spec 'time,ip,-,-,dip,fqdn'
    MESSAGE_EXTRA_HEADERS = {
        'meta': {
            'event_base': {
                'category': 'bots',
                'confidence': 'low',
                'restriction': 'public',
                'origin': 'c2',
            },
            'parsing_info': {
                'field_separator': ',',
                'comment_prefix': '#',
                'column_spec': 'time,ip,-,-,dip,fqdn',
                'time_format': '%Y-%m-%d %H:%M:%S'
            },
        }
    }

    def cases(self):
        yield (
            b'# Uczestnicy botnetu abcd\n'
            b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain\n'
            b'2015-07-03 12:00:00,1.1.1.1,AS654321,CA,2.2.2.2,example-1.com\n'
            b'2015-07-03 13:00:00,3.3.3.3,AS1234,SE,4.4.4.4,example-2.com\n'
            b'2015-07-03 14:00:00,5.5.5.5,AS5678,US,6.6.6.6,example-3.com\n'
            ,
            [
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'1.1.1.1'}],
                    fqdn=u'example-1.com',
                    source=u'manual.pl',
                    time=u'2015-07-03 12:00:00',
                    dip=u'2.2.2.2',
                ),
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'3.3.3.3'}],
                    fqdn=u'example-2.com',
                    source=u'manual.pl',
                    time=u'2015-07-03 13:00:00',
                    dip=u'4.4.4.4',
                ),
                dict(
                    category=u'bots',
                    origin=u'c2',
                    confidence=u'low',
                    restriction=u'public',
                    address=[{u'ip': u'5.5.5.5'}],
                    fqdn=u'example-3.com',
                    source=u'manual.pl',
                    time=u'2015-07-03 14:00:00',
                    dip=u'6.6.6.6',
                ),
            ]
        )


class TestManualParserPlInvalidFieldSeparator(_ManualParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'manual.pl'
    PARSER_CLASS = ManualParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {}
    # Headers sent from ManualCollector (below command which might be used to run collector):
    # n6collector_manual --source_channel pl --category bots --confidence low --restriction public --origin c2 --field_sep ';' --comment_prefix '#' --column_spec 'time,ip,-,-,dip,fqdn'
    # (Notice, that field separator does not match the one provide with data!)
    MESSAGE_EXTRA_HEADERS = {
        'meta': {
            'event_base': {
                'category': 'bots',
                'confidence': 'low',
                'restriction': 'public',
                'origin': 'c2',
            },
            'parsing_info': {
                'field_separator': ';',
                'comment_prefix': '#',
                'column_spec': 'time,ip,-,-,dip,fqdn',
                'time_format': '%Y-%m-%d %H:%M:%S'
            },
        }
    }

    def cases(self):
        # Invalid field separator, we expect to raise a ValueError
        yield (
            b'# Uczestnicy botnetu abcd\n'
            b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain\n'
            b'2015-07-03 12:00:00,1.1.1.1,AS654321,CA,2.2.2.2,example-1.com\n'
            b'2015-07-03 13:00:00,3.3.3.3,AS1234,SE,4.4.4.4,example-2.com\n'
            b'2015-07-03 14:00:00,5.5.5.5,AS5678,US,6.6.6.6,example-3.com\n'
            ,
            ValueError
        )

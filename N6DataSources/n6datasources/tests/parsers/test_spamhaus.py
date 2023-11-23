# Copyright (c) 2014-2023 NASK. All rights reserved.

import datetime
import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6datasources.parsers.spamhaus import (
    SpamhausBotsParser,
    SpamhausDropParser,
    SpamhausEdrop202303Parser,
    _BaseSpamhausBlacklistParser,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestSpamhausDropParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'spamhaus.drop'
    PARSER_CLASS = SpamhausDropParser
    PARSER_BASE_CLASS = _BaseSpamhausBlacklistParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }
    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                          datetime.timedelta(days=2))

    def cases(self):
        yield (
            b'; Spamhaus DROP List 26/08/13 - (c) 2013 The Spamhaus Project\n'
            b'; http://www.spamhaus.org/drop/drop.txt\n'
            b'; Last-Modified: Mon, 26 Aug 2013 08:44:20 GMT\n'
            b'; Expires: Mon, 26 Aug 2013 08:11:03 GMT\n'
            b'1.1.1.1/1 ; ExampleAdditionalData1\n'
            b'ABC123 ; 2.2.2.2/2 ; ExampleAdditionalData2\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 2, bl_current_time='2013-08-26 08:44:20'),
                    address=[{'ip': '1.1.1.1'}],
                    ip_network='1.1.1.1/1',
                    additional_data='ExampleAdditionalData1',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 2, bl_current_time='2013-08-26 08:44:20'),
                    address=[{'ip': '2.2.2.2'}],
                    ip_network='2.2.2.2/2',
                    additional_data='ExampleAdditionalData2',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )


class TestSpamhausEdrop202303Parser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'spamhaus.edrop'
    PARSER_RAW_FORMAT_VERSION_TAG = '202303'
    PARSER_CLASS = SpamhausEdrop202303Parser
    PARSER_BASE_CLASS = _BaseSpamhausBlacklistParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }
    message_expires = str(parse_iso_datetime_to_utc(ParserTestMixin.message_created)
                          + datetime.timedelta(days=2))

    def cases(self):
        yield (
            b'; Spamhaus EDROP List 2023/03/20 - (c) 2023 The Spamhaus Project\n'
            b'; https://www.spamhaus.org/drop/edrop.txt\n'
            b'; Last-Modified: Sat, 18 Mar 2023 12:49:39 GMT\n'
            b'; Expires: Tue, 21 Mar 2023 10:01:09 GMT\n'
            b'1.1.1.1/24 ; SBL11111111\n'
            b'2.2.2.2/24 ; SBL22222222\n'
            b'AdditionalField ; 3.3.3.3/24 ; SBL33333333\n'
            b'4.4.4.4/24 ; SBL44444444\n'
            b'AdditionalField ; 5.5.5.5/24 ; SBL55555555\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 5, bl_current_time='2023-03-18 12:49:39'),
                    address=[{'ip': '1.1.1.1'}],
                    ip_network='1.1.1.1/24',
                    additional_data='SBL11111111',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 5, bl_current_time='2023-03-18 12:49:39'),
                    address=[{'ip': '2.2.2.2'}],
                    ip_network='2.2.2.2/24',
                    additional_data='SBL22222222',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(3, 5, bl_current_time='2023-03-18 12:49:39'),
                    address=[{'ip': '3.3.3.3'}],
                    ip_network='3.3.3.3/24',
                    additional_data='SBL33333333',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(4, 5, bl_current_time='2023-03-18 12:49:39'),
                    address=[{'ip': '4.4.4.4'}],
                    ip_network='4.4.4.4/24',
                    additional_data='SBL44444444',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(5, 5, bl_current_time='2023-03-18 12:49:39'),
                    address=[{'ip': '5.5.5.5'}],
                    ip_network='5.5.5.5/24',
                    additional_data='SBL55555555',
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )


class TestSpamhausBotsParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'spamhaus.bots'
    PARSER_CLASS = SpamhausBotsParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    def cases(self):
        yield (
            b'; Bots filtered by last 24 hours, prepared for EXAMPLE-COMPANY on UTC = Fri Mar 24 12:00:07 2023\n'
            b'; Copyright 0xC2 0xA9 2023 The Spamhaus Project Ltd. All rights reserved.\n'
            b'; No re-distribution or public access allowed without Spamhaus permission.\n'
            b'; Fields description:\n'
            b';\n'
            b'; 1 - Infected IP\n'
            b'; 2 - ASN\n'
            b'; 3 - Country Code\n'
            b'; 4 - Lastseen Timestamp (in UTC)\n'
            b'; 5 - Bot Name\n'
            b';   Command & Control (C&C) information, if available:\n'
            b'; 7 - Remote IP (connecting to)\n'
            b'; 8 - Remote Port (connecting to)\n'
            b'; 9 - Local Port\n'
            b'; 10 - Protocol\n'
            b';   Additional fields may be added in the future without notice\n'
            b';\n'
            b'; ip, asn, country, lastseen, botname, domain, remote_ip, remote_port, local_port, protocol\n'
            b';\n'
            b'1.1.1.1, AS12345, PL, 1672875838, andromeda, example1.com, 1.1.1.2, 80, 49260, tcp\n'
            b'2.2.2.2, AS56789, PL, 1672858468, tinba, example2.com, 2.2.2.3, 80, 48258, tcp\n'
            b'3.3.3.3, AS54321, PL, 1672873997, nymaim, example3.com, 3.3.3.4, 80, 46963, tcp\n',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    name='andromeda',
                    fqdn='example1.com',
                    dip='1.1.1.2',
                    dport=80,
                    sport=49260,
                    proto='tcp',
                    time='2023-01-04 23:43:58',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    name='tinba',
                    fqdn='example2.com',
                    dip='2.2.2.3',
                    dport=80,
                    sport=48258,
                    proto='tcp',
                    time='2023-01-04 18:54:28',
                ),
                dict(
                    address=[{'ip': '3.3.3.3'}],
                    name='nymaim',
                    fqdn='example3.com',
                    dip='3.3.3.4',
                    dport=80,
                    sport=46963,
                    proto='tcp',
                    time='2023-01-04 23:13:17',
                ),
            ]
        )

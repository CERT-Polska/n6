# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import unittest

from n6.parsers.generic import BlackListTabDataParser
from n6.tests.parsers._parser_test_mixin import ParserTestMixIn
from n6.parsers.dns_bh import (
    DnsBhMalwareDomainsCom201412Parser,
    DnsBhMalwareDomainsComParser,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.record_dict import BLRecordDict


class TestDnsBhMalwareDomainsCom201412Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'dns-bh.malwaredomainscom'
    PARSER_CLASS = DnsBhMalwareDomainsCom201412Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    message_expires = str((parse_iso_datetime_to_utc(ParserTestMixIn.message_created)
                           + datetime.timedelta(days=2)))

    def cases(self):
        yield ("""##     If you do not accept these term, then do not use this information.
##    For noncommercial use only. Using this information indicates you agree to be bound by these terms.
##    nextvalidation    domain    type    original_reference-why_it_was_listed    dateverified
##        notice    notice    duplication is not permitted
\t20130601\tair-komplex.hu\tattackpage\tsafebrowsing.clients.google.com\t20110506\t20101201
\t20130601\tmmtrf.com\tattackpage\tsafebrowsing.clients.google.com\t20110630\t20101031
\t20130601\tmtxa.net\tattackpage\tsafebrowsing.clients.google.com\t20110630\t20101031
"""
            ,
            [
                dict(
                     self.get_bl_items(1, 3),
                     fqdn="air-komplex.hu",
                     time=self.message_created,
                     expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 3),
                    fqdn="mmtrf.com",
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(3, 3),
                    fqdn="mtxa.net",
                    time=self.message_created,
                    expires=self.message_expires,
                ),
             ]
          )


class TestDnsBhMalwareDomainsComParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'dns-bh.malwaredomainscom'
    PARSER_CLASS = DnsBhMalwareDomainsComParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    message_expires = str((parse_iso_datetime_to_utc(ParserTestMixIn.message_created)
                           + datetime.timedelta(days=2)))

    def cases(self):
        yield ("""84.2.35.134\t15545\t20130601\tair-komplex.hu\tattackpage\tsafebrowsing.clients.google.com\t20110506\t20101201\t
141.8.226.5\t\t20130601\tmmtrf.com\tattackpage\tsafebrowsing.clients.google.com\t20110630\t20101031\t
176.74.176.167\t13768\t20130601\tmtxa.net\tattackpage\tsafebrowsing.clients.google.com\t20110630\t20101031\t
"""
            ,
            [
                dict(
                     self.get_bl_items(1, 3),
                     fqdn="air-komplex.hu",
                     address=[{'ip':'84.2.35.134'}],
                     time=self.message_created,
                     expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 3),
                    fqdn="mmtrf.com",
                    address=[{'ip':'141.8.226.5'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(3, 3),
                    fqdn="mtxa.net",
                    address=[{'ip':'176.74.176.167'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
             ]
          )

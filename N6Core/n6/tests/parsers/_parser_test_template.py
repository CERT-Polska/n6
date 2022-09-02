# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import unittest

from n6lib.record_dict import (
    BLRecordDict,
)
from n6.parsers.generic import (
#    BaseParser,
#    BlackListParser,
#    AggregatedEventParser,
    TabDataParser,
    BlackListTabDataParser,
)
from n6.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc

from n6.parsers.xxxxxxxx import (
#    MyAggregatedEventParser,
    MyBLParser,
    MyEventParser,
    MyMailBLParser,
)


class TestMyEventParser(ParserTestMixin, unittest.TestCase):

    """
    The template for testing parsers for event-based sources.
    """

    PARSER_SOURCE = 'my.event'
    PARSER_CLASS = MyEventParser
    PARSER_BASE_CLASS = TabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': '',
        'confidence': '',
        #'category': '',
        #'_do_not_resolve_fqdn_to_ip': True,
    }

    def cases(self):
        yield (
            '01\t1.2.3.4\n'
            '02\t1.2.3.4,5.6.7.8\n'
            ,
            [
                dict(
                    address={'ip': '1.2.3.4'},
                    time=self.message_created,
                ),
                dict(
                    address=[{'ip': '1.2.3.4'}, {'ip': '5.6.7.8'}],
                    time=self.message_created,
                ),
            ]
        )
        #yield (
        #    'some erroneous data\n',
        #    SomeError,
        #)


class TestMyBLParser(ParserTestMixin, unittest.TestCase):

    """
    The template for testing blacklist parsers.

    If the tested parser receives messages with a meta
    header 'http_last_modified' (set by a collector,
    if the downloaded data has an HTTP 'Last-Modified'
    header), then the `MESSAGE_EXTRA_HEADERS` should
    have this header set accordingly.
    """

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'my.bl'
    PARSER_CLASS = MyBLParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': '',
        'confidence': '',
        #'category': '',
        #'_do_not_resolve_fqdn_to_ip': True,
    }
    # `http_last_modified` should be set, if the source is provided
    # with the HTTP `Last-Modified` header
    MESSAGE_EXTRA_HEADERS = {
        'meta': {'http_last_modified': '2017-01-12 12:02:04'}
    }
    message_expires = (parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                       datetime.timedelta(days=2))

    def cases(self):
        # Events from this set of data will have their
        # `_bl-current-time` attribute fetched from the
        # `http_last_modified` AMQP meta header.
        yield (
            '01\t1.2.3.4\n'
            '02\t1.2.3.4,5.6.7.8\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 2),
                    address={'ip': '1.2.3.4'},
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 2),
                    address=[{'ip': '1.2.3.4'}, {'ip': '5.6.7.8'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )
        yield (
            # Events from this set of data can have their
            # `_bl-current-time` attribute's value taken
            # from the data. For these events, the `bl_current_time`
            # keyword argument passed into `get_bl_items()` method
            # should be set accordingly.
            '# This is an example blacklist source,\n'
            '# Feed generated at: 2017-01-20 12:02:03.\n'
            '01\t1.2.3.4\n'
            '02\t1.2.3.4,5.6.7.8\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 2, bl_current_time="2017-01-20 12:02:03"),
                    address={'ip': '1.2.3.4'},
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 2, bl_current_time="2017-01-20 12:02:03"),
                    address=[{'ip': '1.2.3.4'}, {'ip': '5.6.7.8'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )
        #yield (
        #    'some erroneous data\n',
        #    SomeError,
        #)


class TestMyMailBLParser(ParserTestMixin, unittest.TestCase):

    """
    The template for testing e-mail sourced blacklist parsers.

    The `MESSAGE_EXTRA_HEADERS` attribute should contain
    a meta header `mail_time`, which indicates the time,
    the message was created.
    """

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'my.mail-bl'
    PARSER_CLASS = MyMailBLParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': '',
        'confidence': '',
        #'category': '',
        #'_do_not_resolve_fqdn_to_ip': True,
    }
    # `mail_time` should be set for the mail sources
    MESSAGE_EXTRA_HEADERS = {
        'meta': {'mail_time': '2017-01-12 12:02:04'}
    }
    message_expires = (parse_iso_datetime_to_utc(ParserTestMixin.message_created) +
                       datetime.timedelta(days=2))

    def cases(self):
        # Events from this set of data will have their
        # `_bl-current-time` attribute fetched from the
        # `mail_time` AMQP meta header.
        yield (
            '01\t1.2.3.4\n'
            '02\t1.2.3.4,5.6.7.8\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 2),
                    address={'ip': '1.2.3.4'},
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 2),
                    address=[{'ip': '1.2.3.4'}, {'ip': '5.6.7.8'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )
        yield (
            # Events from this set of data can have their
            # `_bl-current-time` attribute's value taken
            # from the e-mail's content. For these events,
            # the `bl_current_time` keyword argument passed
            # into `get_bl_items()` method should be set accordingly.
            '# This is an example e-mail blacklist source,\n'
            '# Mail generated at: 2017-01-20 12:02:03.\n'
            '01\t1.2.3.4\n'
            '02\t1.2.3.4,5.6.7.8\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 2, bl_current_time="2017-01-20 12:02:03"),
                    address={'ip': '1.2.3.4'},
                    time=self.message_created,
                    expires=self.message_expires,
                ),
                dict(
                    self.get_bl_items(2, 2, bl_current_time="2017-01-20 12:02:03"),
                    address=[{'ip': '1.2.3.4'}, {'ip': '5.6.7.8'}],
                    time=self.message_created,
                    expires=self.message_expires,
                ),
            ]
        )

# -*- coding: utf-8 -*-

# Copyright (c) 2014-2022 NASK. All rights reserved.

import datetime
import functools
import json

import pika
from mock import patch, sentinel                                                 #3: ->unittest.mock...

from n6.parsers.generic import (                                                 #3: n6.parsers.generic->n6datasources.parsers.base
    BaseParser,
    AggregatedEventParser,
    BlackListParser,
)
from n6lib.class_helpers import FalseIfOwnerClassNameMatchesRegex
from n6lib.record_dict import RecordDict
from n6lib.unit_test_helpers import TestCaseMixin


#
# Helper mix-ins for parser test cases
                                                                                 #3: adjust ad types, especially of string-like stuff, and ad interface/internals differences...
class ParserTestMixin(TestCaseMixin):

    # Prevent pytest *from treating* those subclasses of this class that
    # are base/mixin (abstract) classes *as concrete test classes*.
    __test__ = FalseIfOwnerClassNameMatchesRegex(r'\A(_.*Base|.*ParserTestMix[Ii]n\Z)')


    MESSAGE_TIMESTAMP = 1389348840  # '2014-01-10 10:14:00'
    message_created = str(datetime.datetime.utcfromtimestamp(MESSAGE_TIMESTAMP))

    MESSAGE_ID = '0123456789abcdef0123456789abcdef'  # like an md5 hash

    # Please remember to set it when testing such blacklist parsers
    # that determine the `_bl-current-time` event attribute from
    # message headers (such as 'mail_time' or 'http_last_modified'...).
    MESSAGE_EXTRA_HEADERS = {}

    RECORD_DICT_CLASS = RecordDict

    PARSER_SOURCE = sentinel.not_set
    PARSER_RAW_FORMAT_VERSION_TAG = sentinel.not_set

    PARSER_CLASS = sentinel.not_set
    PARSER_BASE_CLASS = sentinel.not_set
    PARSER_CONSTANT_ITEMS = sentinel.not_set

    # it can be overridden in subclasses
    # (e.g. with 'assertItemsEqual' -- to disable checking of event ordering)             #3: 'assertItemsEqual' -> `assertCountEqual`
    ASSERT_RESULTS_EQUAL = 'assertEqual'

    def test_basics(self):
        self.assertIn(self.PARSER_BASE_CLASS, self.PARSER_CLASS.__bases__)
        source_from_default_binding_key = '.'.join(self.PARSER_CLASS.default_binding_key.
                                                   split(".")[:2])
        self.assertEqual(source_from_default_binding_key,
                         self.PARSER_SOURCE)
        self.assertEqual(self.PARSER_CLASS.constant_items,
                         self.PARSER_CONSTANT_ITEMS)

    def test__input_callback(self):
        assert_results_equal = getattr(self, self.ASSERT_RESULTS_EQUAL)
        for raw_data, expected in self.cases():
            parser = self.PARSER_CLASS.__new__(self.PARSER_CLASS)
            self._patch_the_postprocess_parsed_method(parser)
            with patch.object(parser, 'publish_output') as publish_output_mock:
                (input_properties,
                 input_rk,
                 expected_output_rk) = self._make_amqp_properties_and_routing_keys()
                if isinstance(expected, type) and issubclass(expected, BaseException):
                    expected_error = expected
                    with self.assertRaises(expected_error):
                        parser.input_callback(input_rk, raw_data, input_properties)
                    self.assertEqual(publish_output_mock.mock_calls, [])
                else:
                    expected_results = list(self._iter_expected_results(expected))
                    parser.input_callback(input_rk, raw_data, input_properties)
                    actual_results = list(self._iter_actual_results(publish_output_mock,
                                                                    expected_output_rk))
                    assert_results_equal(actual_results, expected_results)

    def _patch_the_postprocess_parsed_method(self, parser):
        orig_postprocess_parsed = parser.postprocess_parsed
        # a wrapper that adds some assertions:
        @functools.wraps(orig_postprocess_parsed)
        def patched_postprocess_parsed(data, parsed, *args, **kwargs):
            self.assertIs(type(parsed), self.RECORD_DICT_CLASS)
            parsed = orig_postprocess_parsed(data, parsed, *args, **kwargs)
            self.assertIs(type(parsed), self.RECORD_DICT_CLASS)
            return parsed
        parser.postprocess_parsed = patched_postprocess_parsed

    def _make_amqp_properties_and_routing_keys(self):
        input_properties = pika.BasicProperties(**{
            'message_id': self.MESSAGE_ID,
            'type': 'rather-not-used-by-parsers :-)',
            'timestamp': self.MESSAGE_TIMESTAMP,
            'headers': dict(
                **self.MESSAGE_EXTRA_HEADERS),
        })
        if issubclass(self.PARSER_CLASS, BlackListParser):
            assert not issubclass(self.PARSER_CLASS, AggregatedEventParser)
            event_type = 'bl'
        elif issubclass(self.PARSER_CLASS, AggregatedEventParser):
            event_type = 'hifreq'
        else:
            event_type = 'event'
        input_rk = self.PARSER_SOURCE
        if self.PARSER_RAW_FORMAT_VERSION_TAG is not sentinel.not_set:
            input_rk = input_rk + '.' + self.PARSER_RAW_FORMAT_VERSION_TAG
        expected_output_rk = (event_type + '.parsed.' + self.PARSER_SOURCE)
        return input_properties, input_rk, expected_output_rk

    def _iter_expected_results(self, variable_results):
        for record in variable_results:
            record_dict = self.RECORD_DICT_CLASS()
            record_dict.update(self.PARSER_CONSTANT_ITEMS)
            record_dict.update({'rid': self.MESSAGE_ID,
                                'source': self.PARSER_SOURCE})
            # note: here we modify the underlying pure dict by hand
            # (not using RecordDict's methods):
            record_dict._dict.update(record)
            record_dict._dict.setdefault('id', self._compute_id(record_dict))
            yield record_dict._dict

    def _iter_actual_results(self, publish_output_mock, expected_output_rk):
        for attr, args, kwargs in publish_output_mock.mock_calls:
            self.assertEqual(attr, '')
            self.assertEqual(args, ())
            self.assertEqual(set(kwargs), {'routing_key', 'body'})
            self.assertEqual(kwargs['routing_key'], expected_output_rk)
            actual_output_data = json.loads(kwargs['body'])
            yield actual_output_data

    def _compute_id(self, record_dict):
        # NOTE: concerning the expected value of the `id` event attribute --
        # it is just being computed using the standard mechanism provided by
        # BaseParser, so the test does prove that `id` is generated by the
        # tested parser in the same way, but nothing more...
        aux_parser = BaseParser.__new__(BaseParser)
        return aux_parser.get_output_message_id(record_dict.copy())

    def cases(self):
        """
        Implement it in the actual test case class as a generator.

        Yields:
            Pairs (2-element tuples), each consisting of 2 items:

            0) raw input data body (str),

            1) one of:

               a list of dicts containing variable items of
               output data bodies expected to be passed (as
               JSON-ed strings) into publish_output() [here
               "variable items" means: all items except: 'id',
               'rid', 'source' and parser's `constant_items`]

               or

               the class of the exception that is expected
               to be raised.
        """
        raise NotImplementedError

    def get_bl_items(self, item_no, total, bl_current_time=None):
        """
        Helper method for black-list-event parser cases.

        Args:
            `item_no` (int):
                number of expected blacklist item.
            `total` (int):
                total number of expected blacklist items.
            `bl_current_time` (str or None; default: None):
                if not None: the value to be used to override
                the expected value of the `_bl-current-time`
                event attribute (by default determined by
                the _get_expected_bl_current_time() method).

        Returns:
            A dict of expected blacklist-specific items.
        """
        if not bl_current_time:
            bl_current_time = self._get_expected_bl_current_time()
        return {
            "_bl-series-id": self.MESSAGE_ID,
            "_bl-series-total": total,
            "_bl-series-no": item_no,
            "_bl-time": self.message_created,
            "_bl-current-time": bl_current_time,
        }

    def _get_expected_bl_current_time(self):
        """
        Get a datetime that is expected to be set as
        the `_bl-current-time` attribute (getting it in a way
        similar to what real parser classes do).
        """
        if 'meta' in self.MESSAGE_EXTRA_HEADERS:
            if 'mail_time' in self.MESSAGE_EXTRA_HEADERS['meta']:
                return self.MESSAGE_EXTRA_HEADERS['meta'].get('mail_time')
            if 'http_last_modified' in self.MESSAGE_EXTRA_HEADERS['meta']:
                return self.MESSAGE_EXTRA_HEADERS['meta'].get('http_last_modified')
        return self.message_created

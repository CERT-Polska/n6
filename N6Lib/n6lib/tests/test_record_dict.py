# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import collections
import copy
import cPickle
import datetime
import itertools
import operator
import random
import re
import sys
import unittest
from UserDict import IterableUserDict

from mock import (
    MagicMock,
    Mock,
    call,
    patch,
    sentinel as sen,
)

from n6lib.class_helpers import AsciiMixIn
from n6lib.common_helpers import CIDict, picklable
from n6lib.const import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    RESTRICTION_ENUMS,
    STATUS_ENUMS,
    TYPE_ENUMS,
    CATEGORY_TO_NORMALIZED_NAME,
)
from n6lib.data_spec import FieldValueTooLongError
from n6lib.datetime_helpers import FixedOffsetTimezone
from n6lib.record_dict import (
    # exception classes:
    AdjusterError,

    # helpers/decorators:
    chained,
    applied_for_nonfalse,
    preceded_by,
    adjuster_factory,

    # adjuster factories:
    ensure_in,
    ensure_in_range,
    ensure_isinstance,
    ensure_validates_by_regexp,
    make_adjuster_using_data_spec,
    make_adjuster_applying_value_method,
    make_adjuster_applying_callable,
    make_multiadjuster,
    make_dict_adjuster,

    # generic and auxiliary adjusters:
    rd_adjuster,
    unicode_adjuster,
    unicode_surrogateescape_adjuster,
    ipv4_preadjuster,
    url_preadjuster,

    # record dict classes
    RecordDict,
    BLRecordDict,
)
from n6lib.unit_test_helpers import TestCaseMixin


# helper container for RecordDict.__setitem__ test case data
S = collections.namedtuple('_RecordDict__setitem__test_case_data',
                           ('result', 'inputs'))


class TestAdjusterError(unittest.TestCase):

    def test(self):
        self.assertTrue(issubclass(AdjusterError, Exception))
        self.assertTrue(issubclass(AdjusterError, AsciiMixIn))


class TestAdjusterHelpers(unittest.TestCase):

    def setUp(self):
        self.a = Mock(return_value=sen.a, __name__='a', _factory_names={'x', 'y'})
        self.b = Mock(return_value=sen.b, __name__='b')
        self.c = Mock(return_value=sen.c, __name__='c', _factory_names={'z'})
        del self.b._factory_names  # b does not have the `_factory_names` attr

    def test__chained(self):
        adj = chained(self.a, self.b, self.c)
        self.assertEqual(adj._factory_names, {'x', 'y', 'z'})
        self._test_combined_adjuster_call(adj)

    def test__applied_for_nonfalse(self):
        adj = applied_for_nonfalse(self.a)
        self.assertEqual(adj._factory_names, {'x', 'y'})
        result = adj(sen.self, [])
        self.assertEqual(result, [])
        self.assertFalse(self.a.mock_calls)
        result = adj(sen.self, [sen.value])
        self.assertIs(result, sen.a)
        self.a.assert_called_once_with(sen.self, [sen.value])

    def test__preceded_by(self):
        adj = preceded_by(self.a, self.b)(self.c)
        self.assertEqual(adj._factory_names, {'x', 'y', 'z'})
        self._test_combined_adjuster_call(adj)

    def test__adjuster_factory(self):
        @adjuster_factory
        def chained2(self, value, *adjusters_to_call, **foo_bar):
            for adj in adjusters_to_call:
                value = adj(self, value)
            return value
        adj = chained2(self.a, self.b, self.c, x=sen.foo)
        self.assertEqual(adj._factory_names, {'chained2'})
        self._test_combined_adjuster_call(adj)

    def _test_combined_adjuster_call(self, adj):
        result = adj(sen.self, sen.value)
        self.a.assert_called_once_with(sen.self, sen.value)
        self.b.assert_called_once_with(sen.self, sen.a)
        self.c.assert_called_once_with(sen.self, sen.b)
        self.assertIs(result, sen.c)


class TestAdjusterFactories(unittest.TestCase):

    def test__ensure_in(self):
        adj = ensure_in((4, 5, 6))
        self._test_value_in_4_5_6(adj)

    def test__ensure_in_range(self):
        adj = ensure_in_range(4, 7)
        self._test_value_in_4_5_6(adj)

    def _test_value_in_4_5_6(self, adj):
        s = sen.self
        with self.assertRaises(ValueError):
            adj(s, 3)
        self.assertEqual(adj(s, 4), 4)
        self.assertEqual(adj(s, 5), 5)
        self.assertEqual(adj(s, 6), 6)
        with self.assertRaises(ValueError):
            adj(s, 7)

    def test__ensure_isinstance(self):
        adj = ensure_isinstance(int)
        result = adj(sen.self, 2)
        self.assertEqual(result, 2)
        with self.assertRaises(TypeError):
            adj(sen.self, 2.0)

    def test__ensure_validates_by_regexp__with_re_pattern(self):
        adj = ensure_validates_by_regexp('456')
        self._test_regexp_validation(adj)

    def test__ensure_validates_by_regexp__with_re_compiled(self):
        adj = ensure_validates_by_regexp(re.compile('456'))
        self._test_regexp_validation(adj)

    def _test_regexp_validation(self, adj):
        result = adj(sen.self, '123456789')
        self.assertEqual(result, '123456789')
        result = adj(sen.self, u'123456789')
        self.assertEqual(result, u'123456789')
        with self.assertRaises(ValueError):
            adj(sen.self, '56789')
        with self.assertRaises(TypeError):
            adj(sen.self, 56789)

    def test__make_adjuster_using_data_spec__mocked_field__not_too_long(self):
        rd_mock = MagicMock()
        rd_mock.data_spec.foo.clean_result_value.return_value = sen.result
        adj = make_adjuster_using_data_spec('foo')
        result = adj(rd_mock, sen.input)
        self.assertIs(result, sen.result)
        self.assertEqual(rd_mock.data_spec.foo.clean_result_value.mock_calls, [
            call(sen.input),
        ])

    def test__make_adjuster_using_data_spec__mocked_field__error_on_too_long(self):
        for factory_kwargs in [
            dict(),
            dict(on_too_long=None),
        ]:
            rd_mock = MagicMock()
            rd_mock.data_spec.foo.clean_result_value.side_effect = FieldValueTooLongError(
                field=sen.x,
                checked_value=sen.y,
                max_length=sen.z)
            adj = make_adjuster_using_data_spec('foo', **factory_kwargs)
            with self.assertRaises(FieldValueTooLongError):
                adj(rd_mock, sen.input)
            self.assertEqual(rd_mock.data_spec.foo.clean_result_value.mock_calls, [
                call(sen.input),
            ])

    def test__make_adjuster_using_data_spec__mocked_field__callable_on_too_long(self):
        on_too_long_callable = MagicMock()
        on_too_long_callable.return_value = sen.cut_input
        clean_exc = FieldValueTooLongError(
            field=sen.field,
            checked_value=sen.input_from_exc,
            max_length=17)
        rd_mock = MagicMock()
        rd_mock.data_spec.foo.clean_result_value.side_effect = [clean_exc, sen.result]
        adj = make_adjuster_using_data_spec('foo', on_too_long=on_too_long_callable)
        with patch('n6lib.record_dict.LOGGER') as LOGGER_mock:
            result = adj(rd_mock, sen.input)
        self.assertIs(result, sen.result)
        self.assertEqual(rd_mock.data_spec.foo.clean_result_value.mock_calls, [
            call(sen.input),
            call(sen.cut_input),
        ])
        on_too_long_callable.assert_called_once_with(sen.input_from_exc, 17)
        self.assertEqual(LOGGER_mock.warning.call_count, 1)

    def test__make_adjuster_using_data_spec__mocked_field__err_callable_on_too_long(self):
        on_too_long_callable = MagicMock()
        on_too_long_callable.side_effect = callback_exc = ZeroDivisionError
        clean_exc = FieldValueTooLongError(
            field=sen.field,
            checked_value=sen.input_from_exc,
            max_length=17)
        rd_mock = MagicMock()
        rd_mock.data_spec.foo.clean_result_value.side_effect = [clean_exc, sen.result]
        adj = make_adjuster_using_data_spec('foo', on_too_long=on_too_long_callable)
        with patch('n6lib.record_dict.LOGGER') as LOGGER_mock:
            with self.assertRaises(callback_exc) as cm:
                adj(rd_mock, sen.input)
        self.assertTrue(getattr(cm.exception, 'propagate_it_anyway', False))
        self.assertEqual(rd_mock.data_spec.foo.clean_result_value.mock_calls, [
            call(sen.input),
        ])
        on_too_long_callable.assert_called_once_with(sen.input_from_exc, 17)
        self.assertEqual(LOGGER_mock.warning.call_count, 1)

    def test__make_adjuster_using_data_spec__example_field(self):
        rd = RecordDict()

        # too_long=None (default)
        adj = make_adjuster_using_data_spec('source')
        result = adj(rd, '0123456789abcde.-edcba9876543210')
        self.assertEqual(result, u'0123456789abcde.-edcba9876543210')
        self.assertIsInstance(result, unicode)
        with self.assertRaises(FieldValueTooLongError):
            adj(rd, '0123456789abcde.-edcba9876543210' + 'a')
        result = adj(rd, 'x.y')
        self.assertEqual(result, u'x.y')
        self.assertIsInstance(result, unicode)

        # too_long=<a callable object>
        adj = make_adjuster_using_data_spec(
            'source',
            on_too_long=lambda value, max_length: '{}.-long'.format(max_length))
        result = adj(rd, '0123456789abcde.-edcba9876543210' + 'a')
        self.assertEqual(result, u'32.-long')
        self.assertIsInstance(result, unicode)
        result = adj(rd, 'x.' + 'y' * 30)
        self.assertEqual(result, u'x.' + u'y' * 30)
        self.assertIsInstance(result, unicode)
        result = adj(rd, 'x.y')
        self.assertEqual(result, u'x.y')
        self.assertIsInstance(result, unicode)

    def test__make_adjuster_applying_value_method(self):
        adj = make_adjuster_applying_value_method('lower')
        result = adj(sen.self, 'ABC')
        self.assertEqual(result, 'abc')
        adj = make_adjuster_applying_value_method('format', 'B', c='C')
        result = adj(sen.self, 'A{0}{c}')
        self.assertEqual(result, 'ABC')

    def test__make_adjuster_applying_callable(self):
        adj = make_adjuster_applying_callable(int)
        result = adj(sen.self, '128')
        self.assertEqual(result, 128)
        adj = make_adjuster_applying_callable(int, base=16)
        result = adj(sen.self, '80')
        self.assertEqual(result, 128)

    def test__make_multiadjuster(self):
        adj = make_multiadjuster(chained(
                ensure_isinstance(str),
                make_adjuster_applying_value_method('lower')))
        # passing singular value
        result = adj(sen.self, 'ABC')
        self.assertEqual(result, ['abc'])
        with self.assertRaises(TypeError):
            adj(sen.self, u'ABC')
        # passing sequence of values
        result = adj(sen.self, ('ABC', 'DEF'))
        self.assertEqual(result, ['abc', 'def'])
        with self.assertRaises(TypeError):
            adj(sen.self, ('ABC', u'DEF'))
        # ...and with argumentless version:
        adj = make_multiadjuster()
        # passing singular value
        result = adj(sen.self, sen.value)
        self.assertEqual(result, [sen.value])
        # passing sequence of values
        result = adj(sen.self, [sen.val1, sen.val2])
        self.assertEqual(result, [sen.val1, sen.val2])

    def test__make_dict_adjuster(self):
        adj = make_dict_adjuster(
            foo=ensure_in([2, 3, 4]),
            SPAM=chained(
                ensure_isinstance(str),
                make_adjuster_applying_value_method('lower')))
        result = adj(sen.self, dict(SPAM='BAR'))
        self.assertEqual(result, dict(SPAM='bar'))
        result = adj(sen.self, dict(completely_different='BAR'))
        self.assertEqual(result, dict(completely_different='BAR'))
        result = adj(sen.self, dict(foo=2, SPAM='BAR', another=42.0))
        self.assertEqual(result, dict(foo=2, SPAM='bar', another=42.0))
        with self.assertRaises(ValueError):
            adj(sen.self, dict(foo=22222222, SPAM='BAR', another=42.0))
        # passing not-a-dict
        with self.assertRaises(TypeError):
            adj(sen.self, [('foo', 2), ('SPAM', 'BAR'), ('another', 42.0)])


class TestGenericAdjusters(unittest.TestCase):

    def test__rd_adjuster(self):
        with self.assertRaises(TypeError):
            rd_adjuster(sen.self, 'test')
        rd = RecordDict()
        result = rd_adjuster(sen.self, rd)
        self.assertEqual(result, rd)

    def test__unicode_adjuster(self):
        # unicode unchanged
        result = unicode_adjuster(sen.self, u'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, unicode)
        # UTF-8-encoded str -> unicode
        result = unicode_adjuster(sen.self, 'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, unicode)
        # illegal (non-UTF-8-or-ASCII) encoding
        with self.assertRaises(ValueError):
            unicode_adjuster(sen.self, u'ąBć #'.encode('latin2'))
        # illegal types
        with self.assertRaises(TypeError):
            unicode_adjuster(sen.self, datetime.datetime.now())
        with self.assertRaises(TypeError):
            unicode_adjuster(sen.self, None)

    def test__unicode_surrogateescape_adjuster(self):
        # unicode unchanged
        result = unicode_surrogateescape_adjuster(sen.self, u'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, unicode)
        # UTF-8-encoded str -> unicode
        result = unicode_surrogateescape_adjuster(sen.self, 'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, unicode)
        # non-UTF-8-or-ASCII encoding -> unicode with binary mess embedded
        result = unicode_surrogateescape_adjuster(sen.self, '\xb1B\xe6 #')
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, unicode)
        # unicode with binary mess embedded -> unchanged
        result = unicode_surrogateescape_adjuster(sen.self, u'\udcb1B\udce6 #')
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, unicode)
        # already UTF-8-encoded (from unicode with binary mess embedded) -> unicode
        result = unicode_surrogateescape_adjuster(sen.self, '\xed\xb2\xb1B\xed\xb3\xa6 #')
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, unicode)
        # illegal types
        with self.assertRaises(TypeError):
            unicode_surrogateescape_adjuster(sen.self, datetime.datetime.now())
        with self.assertRaises(TypeError):
            unicode_surrogateescape_adjuster(sen.self, None)

    def test__ipv4_preadjuster(self):
        result = ipv4_preadjuster(sen.self, '100.101.102.103')
        self.assertEqual(result, '100.101.102.103')
        result = ipv4_preadjuster(sen.self, ' 100 . 101\t.\n102 . 103 ')
        self.assertEqual(result, '100.101.102.103')
        result = ipv4_preadjuster(sen.self, 1684366951)
        self.assertEqual(result, '100.101.102.103')
        with self.assertRaises(ValueError):
            ipv4_preadjuster(sen.self, '1684366951')
        with self.assertRaises(ValueError):
            ipv4_preadjuster(sen.self, '100.101.102.103.100')
        with self.assertRaises(ValueError):
            ipv4_preadjuster(sen.self, '100.101.102.1030')
        with self.assertRaises(ValueError):
            ipv4_preadjuster(sen.self, '100.101.102')
        with self.assertRaises(ValueError):
            ipv4_preadjuster(sen.self, 168436695123456789)
        with self.assertRaises(TypeError):
            ipv4_preadjuster(sen.self, datetime.datetime.now())

    def test__url_preadjuster(self):
        result = url_preadjuster(sen.self, u'HTTP://www.EXAMPLĘ.com')
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, 'HTTP://www.EXAMPLĘ.com')
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, u'hxxp://www.EXAMPLĘ.com')
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, 'hXXps://www.EXAMPLĘ.com')
        self.assertEqual(result, u'https://www.EXAMPLĘ.com')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, u'FXP://www.EXAMPLĘ.com')
        self.assertEqual(result, u'ftp://www.EXAMPLĘ.com')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, 'blAbla+HA-HA.ojoj:()[]!@#:%^&*shKi→ś')
        self.assertEqual(result, u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś')
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, 'url:// \xee oraz \xdd')
        self.assertEqual(result, u'url:// \udcee oraz \udcdd')  # surrogate-escaped
        self.assertIsInstance(result, unicode)
        result = url_preadjuster(sen.self, u'url:// \udcee oraz \udcdd')  # surrogate-escaped
        self.assertEqual(result, u'url:// \udcee oraz \udcdd')        # the same
        self.assertIsInstance(result, unicode)
        for bad_value in [
                ''
                'example.com',
                'http-//example.com/',
                u'http : //example.com ',
                u'h??p://example.com/',
                'ħŧŧþ://example.com/',
                u'ħŧŧþ://example.com/',
        ]:
            with self.assertRaises(ValueError):
                url_preadjuster(sen.self, bad_value)


class TestRecordDict(TestCaseMixin, unittest.TestCase):

    rd_class = RecordDict
    enum_collections = dict(
        origin=ORIGIN_ENUMS,
        restriction=RESTRICTION_ENUMS,
        confidence=CONFIDENCE_ENUMS,
        category=CATEGORY_ENUMS,
        proto=PROTO_ENUMS,
        status=STATUS_ENUMS,
        type=TYPE_ENUMS,
    )
    datetime_field_keys = 'time', 'until', 'expires', '_bl-time'
    md5_hexdigest_field_keys = 'id', 'rid', 'md5', 'replaces', '_bl-series-id'
    unsigned_16bit_int_field_keys = 'sport', 'dport'
    unlimited_int_field_keys = '_bl-series-no', '_bl-series-total'

    # base for several record dict initialization fixtures
    only_required = dict(
        id=(32 * '3'),
        rid=(32 * '4'),
        source='foo.bar',
        restriction='public',
        confidence='low',
        category='malurl',
        time='2013-07-12 11:30:00',
    )

    def setUp(self):
        # some fixtures
        self.rd = self.rd_class()
        self.some_md5_mixedcase = 2 * '1234567890aBcDEf'
        self.some_md5 = self.some_md5_mixedcase.lower()

        assert self.only_required.viewkeys() == self.rd_class.required_keys
        self.with_optional = dict(
            self.only_required,
            dip='127.0.0.3',
            _do_not_resolve_fqdn_to_ip=False,    # internal flag
        )
        self.with_custom = dict(
            self.only_required,
            dip='127.0.0.3',
            additional_data='additional-\xdd-data',
            ip_network=('33.144.255.177', 25),
        )
        self.with_custom_2 = self.rd_with_custom = self.rd_class(
            dict(
                self.only_required,
                dip='127.0.0.3',
                additional_data=u'additional-\udcdd-data',
                ip_network='33.144.255.177/25',
            ),
        )
        self.with_address_empty = dict(
            self.only_required,
            address=[],
        )
        self.with_address1 = dict(
            self.only_required,
            address=[dict(ip='127.0.0.1')],
        )
        self.with_address1_singular = dict(
            self.only_required,
            address=dict(ip='127.0.0.1'),
        )
        self.with_address2 = dict(
            self.only_required,
            address=[
                dict(ip='127.0.0.1'),
                dict(ip='127.0.0.2',
                     cc='PL',
                     asn=1),
            ],
        )
        self.some_init_args = [
            {},
            self.only_required,
            self.with_optional,
            self.with_address1,
            self.with_address2,
        ]
        self.rd_class._already_logged_nonstandard_names.clear()

    def test__init(self):
        for arg in (self.with_address1_singular,                      # mapping
                    self.with_address1_singular.iteritems(),          # iterator
                    list(self.with_address1_singular.iteritems())):   # sequence
            rd = self.rd_class(arg)
            self.assertEqual(rd, self.with_address1)
            self.assertFalse(rd.log_nonstandard_names)
            self.assertIsNone(rd.context_manager_error_callback)

    def test__init__empty(self):
        for init_args in [(),            # no args
                          ({},),         # mapping
                          ([],),         # sequence
                          (iter([]),)]:  # iterator
            rd = self.rd_class(*init_args)
            self.assertEqual(rd, {})
            self.assertFalse(rd.log_nonstandard_names)
            self.assertIsNone(rd.context_manager_error_callback)

    def test__init__log_nonstandard_names__being_false(self):
        rd = self.rd_class(
            self.with_address1_singular,
            log_nonstandard_names=False)
        self.assertEqual(rd, self.with_address1)
        self.assertFalse(rd.log_nonstandard_names)

    def test__init__log_nonstandard_names__being_true(self):
        rd = self.rd_class(
            self.with_address1_singular,
            log_nonstandard_names=True)
        self.assertEqual(rd, self.with_address1)
        self.assertTrue(rd.log_nonstandard_names)

    def test__init__context_manager_error_callback(self):
        rd = self.rd_class(
            self.with_address1_singular,
            context_manager_error_callback=sen.cm_error_callback)
        self.assertEqual(rd, self.with_address1)
        self.assertIs(rd.context_manager_error_callback, sen.cm_error_callback)

    def test_copying(self):
        class Subclass(self.rd_class):
            pass
        def _callback(arg):
            pass
        for cls in (self.rd_class, Subclass):
            for log_nonstandard_names in (False, True):
                for callback in (None, _callback):
                    for copy_op in (operator.methodcaller('copy'), copy.copy, copy.deepcopy):
                        rd = cls(
                            {'client': ['a', 'b'], 'address': [{'ip': '1.2.3.4'}]},
                            log_nonstandard_names=log_nonstandard_names,
                            context_manager_error_callback=callback)
                        rd2 = copy_op(rd)
                        self.assertIs(type(rd2), cls)
                        self.assertEqual(rd, rd2)
                        if log_nonstandard_names:
                            self.assertTrue(rd2.log_nonstandard_names)
                        else:
                            self.assertFalse(rd2.log_nonstandard_names)
                        self.assertIs(
                            rd2.context_manager_error_callback,
                            callback)
                        # it is always a deep copy:
                        self.assertEqual(rd['client'], rd2['client'])
                        self.assertIsNot(rd['client'], rd2['client'])
                        self.assertEqual(rd['address'], rd2['address'])
                        self.assertIsNot(rd['address'], rd2['address'])
                        self.assertEqual(rd['address'][0], rd2['address'][0])
                        self.assertIsNot(rd['address'][0], rd2['address'][0])

    def test_picklability(self):
        @picklable
        class Subclass(self.rd_class):
            pass
        @picklable
        def _callback(arg):
            pass
        for cls in (self.rd_class, Subclass):
            for log_nonstandard_names in (False, True):
                for callback in (None, _callback):
                    for pickle_proto in (0, 1, 2):
                        rd = cls(
                            self.with_address2,
                            log_nonstandard_names=log_nonstandard_names,
                            context_manager_error_callback=callback)
                        rd2 = cPickle.loads(cPickle.dumps(rd, pickle_proto))
                        assert rd2 is not rd
                        self.assertIs(type(rd2), cls)
                        self.assertEqual(rd, rd2)
                        if log_nonstandard_names:
                            self.assertTrue(rd2.log_nonstandard_names)
                        else:
                            self.assertFalse(rd2.log_nonstandard_names)
                        self.assertIs(
                            rd2.context_manager_error_callback,
                            callback)

    def test__get_ready_dict(self):
        rd = self.rd_class(self.with_address1_singular)
        assert rd == self.with_address1
        ready_dict = rd.get_ready_dict()
        self.assertIs(type(ready_dict), dict)
        self.assertEqual(ready_dict, self.with_address1)

        rd = self.rd_class(self.only_required)
        assert rd == self.only_required
        ready_dict = rd.get_ready_dict()
        self.assertIs(type(ready_dict), dict)
        self.assertEqual(ready_dict, self.only_required)

    def test__get_ready_dict__2(self):
        ready_dict = self.rd_with_custom.get_ready_dict()
        self.assertIs(type(ready_dict), dict)
        self.assertEqual(ready_dict, dict(
            self.only_required,
            dip=u'127.0.0.3',
            additional_data=u'additional-\udcdd-data',
            ip_network=u'33.144.255.177/25',
            __preserved_custom_keys__=['additional_data', 'ip_network'],  ### <- LEGACY ITEM (to be removed later)
        ))

    def test__get_ready_dict__missing_keys(self):
        required_keys = list(self.only_required)
        for keys in itertools.chain.from_iterable(
                itertools.combinations(required_keys, i)
                for i in xrange(len(required_keys))):
            init_mapping = {k: self.only_required[k] for k in keys}
            rd = self.rd_class(init_mapping)
            assert rd == init_mapping
            with self.assertRaises(ValueError):
                rd.get_ready_dict()

    def test__iter_db_items(self):
        expected_db_item_lists = dict(
            only_required=[
                dict(self.only_required),
            ],
            with_optional=[
                dict(self.only_required,
                     dip="127.0.0.3"),
            ],
            with_custom=[
                dict(self.only_required,
                     dip="127.0.0.3",
                     custom=dict(
                         additional_data=u'additional-\udcdd-data',
                         ip_network=u'33.144.255.177/25')),
            ],
            with_custom_2=[
                dict(self.only_required,
                     dip="127.0.0.3",
                     custom=dict(
                         additional_data=u'additional-\udcdd-data',
                         ip_network=u'33.144.255.177/25')),
            ],
            with_address_empty=[
                dict(self.only_required),
            ],
            with_address1=[
                dict(self.with_address1,
                     address=[
                         dict(ip="127.0.0.1"),
                     ],
                     ip="127.0.0.1")
            ],
            with_address2=[
                dict(self.with_address2,
                     address=[
                         dict(ip="127.0.0.1"),
                         dict(ip="127.0.0.2",
                              cc='PL',
                              asn=1),
                     ],
                     ip="127.0.0.1"),
                dict(self.with_address2,
                     address=[
                         dict(ip="127.0.0.1"),
                         dict(ip="127.0.0.2",
                              cc='PL',
                              asn=1),
                     ],
                     ip="127.0.0.2",
                     cc='PL',
                     asn=1),
            ],
        )
        for fixture_key, expected_db_items in sorted(expected_db_item_lists.items()):
            data = getattr(self, fixture_key)
            rd = self.rd_class(data)
            iterator = rd.iter_db_items()
            db_items = list(iterator)
            self.assertIsInstance(iterator, collections.Iterator)
            self.assertItemsEqual(db_items, expected_db_items)
            if data.get('address'):
                self.assertEqual(len(db_items), len(data['address']))
            else:
                self.assertEqual(len(db_items), 1)

    def _test_setitem_valid(self, key, values):
        # `values` can be:
        # * S(<expected result value>, <tuple of input values>)
        # * S(<expected result value>, <single input value>)
        # * a tuple of such S instances
        # * a tuple of values (each being a both-input-and-expected-result value)
        # * a single value (being a both-input-and-expected-result value)
        if isinstance(values, S):
            result_and_input_values = [values]
        elif isinstance(values, tuple):
            if all(isinstance(v, S) for v in values):
                result_and_input_values = values
            else:
                assert not any(isinstance(v, S) for v in values)
                result_and_input_values = zip(values, values)
        else:
            result_and_input_values = [(values, values)]
        for result_val, input_values in result_and_input_values:
            if not isinstance(input_values, tuple):
                input_values = (input_values,)
            for val in input_values:
                rd = self.rd_class(random.choice(self.some_init_args))
                rd[key] = val
                self.assertIn(key, rd)
                actual_result_val = rd[key]
                self.assertEqualIncludingTypes(actual_result_val, result_val)

    def _test_setitem_adjuster_error(self, key, values):
        # `values` can be:
        # * a tuple of input values
        # * a single input value
        if not isinstance(values, tuple):
            values = (values,)
        for val in values:
            rd = self.rd_class(random.choice(self.some_init_args))
            with self.assertRaises(AdjusterError):
                rd[key] = val

    def test__setitem__md5_hexdigest_fields(self):
        for key in self.md5_hexdigest_field_keys:
            self._test_setitem_valid(key, (
                S(u'0123456789abcdef' * 2, (
                    '0123456789abcdef' * 2,
                    '0123456789aBCDEF' * 2,
                )),
                S(u'0123456789abcdef' * 2, (
                    u'0123456789abcdef' * 2,
                    u'0123456789aBCDEF' * 2,
                )),
            ))
            self._test_setitem_adjuster_error(key, (
                '0123456789ABCDEF' * 2 + '0',    # too long
                (u'0123456789ABCDEF' * 2)[:-1],  # too short
                u'0123456789abcdeX' * 2,         # illegal chars
                123,                             # wrong type
                None,
            ))

    def test__setitem__sha1(self):
        self._test_setitem_valid('sha1', (
            S(u'0123456789abcdef0123' * 2, (
                '0123456789abcdef0123' * 2,
                '0123456789aBCDEF0123' * 2,
            )),
            S(u'0123456789abcdef0123' * 2, (
                u'0123456789abcdef0123' * 2,
                u'0123456789aBCDEF0123' * 2,
            )),
        ))
        self._test_setitem_adjuster_error('sha1', (
            u'0123456789ABCDEF0123' * 2 + '0',  # too long
            ('0123456789ABCDEF0123' * 2)[:-1],  # too short
            u'0123456789abcdef' * 2,
            '0123456789abcdeX0123' * 2,         # illegal chars
            0x123456789abcdef,                  # bad type
            None,
        ))

    def test__setitem__source(self):
        self._test_setitem_valid('source', (
            S(u'foo-foo.bar', (
                'foo-foo.bar',
                u'foo-foo.bar',
            )),
            S(u'-spam.ha--m--', (
                '-spam.ha--m--',
                u'-spam.ha--m--',
            )),
            S(u'x.' + 30 * u'y', (  # 32-characters-long
                'x.' + 30 * u'y',
                u'x.' + 30 * u'y'
            )),
        ))
        self._test_setitem_adjuster_error('source', (
            'foo-foo',            # no dot
            u'foo-foo.bar.spam',  # more than one dot
            'Foo-FOO.bar',        # illegal characters (here: uppercase letters)
            u'foo_foo.bar',       # illegal character (here: underscore)
            'foo-foo.',           # no characters after the dot
            u'.bar',              # no characters before the dot
            '.',                  # lone dot
            u'x.' + 31 * u'y'     # too long (33 characters)
            '',                   # empty string
            123,                  # not a string
            None,
        ))

    def test__setitem__enum_fields(self):
        for key, enums in sorted(self.enum_collections.iteritems()):
            assert isinstance(enums, tuple) and all(isinstance(v, str) for v in enums)
            self._test_setitem_valid(key, tuple(
                S(result=unicode(v),
                  inputs=(v, unicode(v)))
                for v in enums
            ))
            self._test_setitem_adjuster_error(key, (
                'foo',
                u'bar',
                enums[0] + 'x',
                123,
                None,
            ))

    def test__setitem__count(self):
        self._test_setitem_valid('count', (
            S(0, (0, 0L, '0', u'0', '00000')),
            S(10, (10, 10L, '10', u'10', '00010')),
            S(32767, (32767, 32767L, '32767', u'32767')),
        ))
        self._test_setitem_adjuster_error('count', (
            -1, -1L, '-1', u'-1',
            32768, 32768L, '32768', u'32768',
            'aaa', '0x10', '', None, datetime.datetime.now(),
        ))

    def test__setitem__count_actual(self):
        self._test_setitem_valid('count_actual', (
            S(0, (0, 0L, '0', u'0', '00000')),
            S(10, (10, 10L, '10', u'10', '00010')),
            S(9007199254740991, (9007199254740991, 9007199254740991L,
                                 '9007199254740991', u'9007199254740991')),
        ))
        self._test_setitem_adjuster_error('count_actual', (
            -1, -1L, '-1', u'-1',
            9007199254740992, 9007199254740992L, '9007199254740992', u'9007199254740992',
            'aaa', '0x10', '', None, datetime.datetime.now(),
        ))

    def test__setitem__unsigned_16bit_int_fields(self):
        for key in self.unsigned_16bit_int_field_keys:
            self._test_setitem_valid(key, (
                S(0, (0, 0L, '0', u'0', '00000')),
                S(10, (10, 10L, '10', u'10', '00010')),
                S(65535, (65535, 65535L, '65535', u'65535')),
            ))
            self._test_setitem_adjuster_error(key, (
                -1, -1L, '-1', u'-1',
                65536, 65536L, '65536', u'65536',
                'aaa', '0x10', '', None, datetime.datetime.now(),
            ))

    def test__setitem__unlimited_int_fields(self):
        for key in self.unlimited_int_field_keys:
            self._test_setitem_valid(key, (
                S(0, (0, 0L, '0', u'0', '00000')),
                S(10, (10, 10L, '10', u'10', '00010')),
                S(655357, (655357, 655357L, '655357', u'655357')),
                S(int(sys.maxint - 1), int(sys.maxint - 1)),
                S(int(sys.maxint), int(sys.maxint)),
                S(int(sys.maxint + 1), int(sys.maxint + 1)),
                S(int(-sys.maxint - 1), int(-sys.maxint - 1)),
                S(int(-sys.maxint), int(-sys.maxint)),
                S(int(-sys.maxint + 1), int(-sys.maxint + 1)),
                S(6553500000000111111112222222233333333L, (
                    6553500000000111111112222222233333333L,
                    '6553500000000111111112222222233333333',
                    u'6553500000000111111112222222233333333')),
                S(-6553500000000111111112222222233333333L, (
                    -6553500000000111111112222222233333333L,
                    '-6553500000000111111112222222233333333',
                    u'-6553500000000111111112222222233333333')),
            ))
            self._test_setitem_adjuster_error(key, (
                'aaa', '0x10', '', None, datetime.datetime.now(),
            ))

    def test__setitem__datetime_fields(self):
        for key in self.datetime_field_keys:
            self._test_setitem_valid(key, (
                S('2013-06-13 10:02:00', (
                    datetime.datetime(2013, 6, 13, 10, 2),
                    '2013-06-13 10:02:00',
                    u'2013-06-13T10:02',
                    '2013-06-13 10:02Z',
                    u'2013-06-13T10:02:00.0000000000000000000000000000000Z',
                )),
                S('2013-06-13 10:02:04',
                        datetime.datetime(2013, 6, 13, 10, 2, 4)),
                S('2013-06-13 10:02:04.123456',
                        datetime.datetime(2013, 6, 13, 10, 2, 4, 123456)),
                S('2013-06-13 08:02:04',
                        datetime.datetime(2013, 6, 13, 10, 2, 4,
                                          tzinfo=FixedOffsetTimezone(120))),
                S('2013-06-13 08:02:04.123400',
                        u'2013-06-13T10:02:04.1234+02:00'),
                S('2013-06-13 11:32:00',
                        '2013-06-13 10:02:00-01:30'),
            ))
            self._test_setitem_adjuster_error(key, (
                '2013-06-13 25:02',
                '2013-06-13  10:02:04',
                123,
                None,
            ))

    def test__setitem__address(self):
        self._test_setitem_valid('address', (
            S([], (
                [],
                (),
            )),
            S([{u'ip': u'1.2.3.4'}], (
                [{'ip': '1.2.3.4'}],
                ({'ip': '1.2.3.4'},),
                {'ip': '1.2.3.4'},
                [IterableUserDict({'ip': '1.2.3.4'})],
                IterableUserDict({'ip': '1.2.3.4'}),
            )),
            S([{u'ip': u'100.101.102.103', u'cc': u'PL', u'asn': 123}], (
                [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': 123}],
                ({'ip': u' 100.101. 102 .103 ', 'cc': 'pl', 'asn': '123'},),
                {'ip': 1684366951, 'cc': 'pL', 'asn': '0.123'},
                [IterableUserDict({'ip': 1684366951, 'cc': 'pL', 'asn': '0.123'})],
                IterableUserDict({'ip': 1684366951, 'cc': 'pL', 'asn': '0.123'}),
            )),
            S([
                {u'ip': u'1.2.3.4', u'cc': u'PL', u'asn': 123},
                {u'ip': u'1.2.3.5', u'cc': u'PL', u'asn': 0},
                {u'ip': u'1.2.3.6', u'cc': u'PL', u'asn': 0},
                {u'ip': u'1.2.3.7', u'cc': u'PL', u'asn': 1},
                {u'ip': u'1.2.3.8', u'cc': u'PL', u'asn': 0x10000},
                {u'ip': u'1.2.3.9', u'cc': u'PL', u'asn': 0xffff},
                {u'ip': u'1.2.3.10', u'cc': u'PL', u'asn': 0xffff0000},
                {u'ip': u'111.122.133.144', u'cc': u'US', u'asn': 1234567},
                {u'ip': u'111.122.133.145', u'cc': u'US', u'asn': 1234567},
                {u'ip': u'111.122.133.146', u'cc': u'US', u'asn': 809087598},
            ], [
                {'ip': u'1.2.3.4', 'cc': 'PL', u'asn': 123L},
                {u'ip': u'1.2.3.5', 'cc': 'PL', 'asn': 0},
                {'ip': '1.2.3.6', 'cc': u'PL', 'asn': '0.0'},
                {u'ip': '1.2.3.7', 'cc': 'PL', u'asn': u'0.1'},
                {'ip': u'1.2.3.8', 'cc': 'PL', 'asn': '1.0'},
                {u'ip': u'1.2.3.9', 'cc': u'PL', 'asn': '0.65535'},
                {'ip': '1.2.3.10', 'cc': 'PL', u'asn': u'65535.0'},
                {u'ip': '111.122.133.144', 'cc': 'US', 'asn': 1234567},
                {'ip': u'111.122.133.145', 'cc': u'US', 'asn': '1234567'},
                {u'ip': u'111.122.133.146', u'cc': u'US', u'asn': u'12345.45678'},
            ]),
        ))
        self._test_setitem_adjuster_error('address', (
            [{'cc': 'PL', 'asn': 123}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': 123, 'xxx': 'spam'},
            [{'ip': '100.101.102.1031', 'cc': 'PL', 'asn': 123}],
            {'ip': '1684366951', 'cc': 'PL', 'asn': 123},
            [{'ip': None, 'cc': 'PL', 'asn': 123}],
            [
                {'ip': '1.2.3.4', 'cc': 'PL', 'asn': 123},
                {'ip': '1.2.3.444', 'cc': 'PL', 'asn': 123},
            ],
            {'ip': '100.101.102.103', 'cc': 'P', 'asn': 123},
            [{'ip': '100.101.102.103', 'cc': 'PRL', 'asn': 123}],
            {'ip': '100.101.102.103', 'cc': '11', 'asn': 123},
            [{'ip': '100.101.102.103', 'cc': 11, 'asn': 123}],
            {'ip': '100.101.102.103', 'cc': '', 'asn': 123},
            [{'ip': '100.101.102.103', 'cc': None, 'asn': 123}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': -1},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': 0x100000000}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': '0.65536'},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': '65536.0'}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': 'asdf'},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': '0.0.0'}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': '-1'},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': 'asdf'}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': '0.-1'},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': '-1.0'}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': '0x1.0xf'},
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': None}],
            [
                {'ip': '1.2.3.4', 'cc': 'PL', 'asn': 123},
                {'ip': '1.2.3.4', 'cc': 'PL', 'asn': 123},  # duplicate ip
            ],
            '1.2.3.4',
            123,
            None,
        ))

    def test__setitem__dip(self):
        self._test_setitem_valid('dip', (
            S(u'0.0.0.0', (0, 0L, '0.0.0.0', u'0.0.0.0')),
            S(u'0.0.0.10', (10, 10L, '0.0.0.10', u'0.0.0.10')),
            S(u'100.101.102.103', (
                '100.101.102.103',
                u'100.101.102.103',
                ' 100 . 101 . 102.103',
                u' 100.101. 102 .103 ',
                ' 100 . 101\t.\n102 . 103 ',
                1684366951,
            )),
        ))
        self._test_setitem_adjuster_error('dip', (
            '1684366951',
            u'100.101.102.103.100',
            '100.101.102.1030',
            u'100.101.102',
            168436695123456789,
            ['100.101.102.103'],
            datetime.datetime.now(),
            '10',
            '',
            None,
        ))

    def test__setitem__url__valid_or_too_long(self):
        self._test_setitem_valid('url', (
            S(u'http://www.EXAMPLĘ.com', (
                u'HTTP://www.EXAMPLĘ.com',
                'HTTP://www.EXAMPLĘ.com',
                u'hxxp://www.EXAMPLĘ.com',
                'hXXp://www.EXAMPLĘ.com',
            )),
            S(u'https://www.EXAMPLĘ.com', (
                u'HTTPS://www.EXAMPLĘ.com',
                'htTPS://www.EXAMPLĘ.com',
                u'hxxps://www.EXAMPLĘ.com',
                'hXXpS://www.EXAMPLĘ.com',
            )),
            S(u'ftp://www.EXAMPLĘ.com', (
                u'FXP://www.EXAMPLĘ.com',
                'ftp://www.EXAMPLĘ.com',
            )),
            S(u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś', (
                'blAbla+HA-HA.ojoj:()[]!@#:%^&*shKi→ś',
                u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś',
            )),
            S(u'url:// \udcee oraz \udcdd', (
                'url:// \xee oraz \xdd',
                u'url:// \udcee oraz \udcdd',
            )),
            S(u'url:' + 2044 * u'\udcdd', (
                'url:' + 2044 * '\xdd',
                u'url:' + 2044 * u'\udcdd',
                'url:' + 2045 * '\xdd',       # too long -> cut right
                u'url:' + 2045 * u'\udcdd',   # too long -> cut right
                'url:' + 20000 * '\xdd',      # too long -> cut right
                u'url:' + 20000 * u'\udcdd',  # too long -> cut right
            )),
        ))

    def test__setitem__url__skipping_invalid(self):
        rd = self.rd_class()
        for invalid in [
                ''
                'example.com',
                'http-//example.com/',
                u'http : //example.com ',
                u'http : //example.com ' + 3000 * u'x:',
                u'h??p://example.com/',
                'ħŧŧþ://example.com/',
                u'ħŧŧþ://example.com/',
                '',
                'example.com',
                u'http : //example.com ',
                datetime.datetime.now(),
                None,
        ]:
            rd['url'] = invalid
            self.assertNotIn('url', rd)

    def test__setitem__fqdn__valid_or_too_long(self):
        self._test_setitem_valid('fqdn', (
            S(u'www.example.com', (
                u'www.example.com',
                'www.EXAMPLE.com',
                u'www.EXAMPLE.com',
            )),
            S(u'com', (
                'CoM',
                u'CoM',
                'com'
            )),
            S(u'www.xn--xmpl-bta2jf.com', (
                # internationalized domain names (unicode or UTF-8-decodable str)...
                'www.ĘxĄmplę.Com',
                u'www.ęxąmplę.Com',
            )),
            S(u'www.{}.com'.format('a' * 63), (
                'www.{}.com'.format('a' * 63),
                'www.{}.com'.format('A' * 63),
                u'www.{}.com'.format('a' * 63),
                u'www.{}.com'.format('A' * 63),
            )),
            S(u'www.-_mahnamana_muppetshow_.-com', (
                'www.-_Mahnamana_MuppetShow_.-com',
                u'www.-_Mahnamana_MuppetShow_.-com',
            )),
            S(u'x.' * 126 + u'pl', (       # result length: 254
                'x.' * 126 + 'pl',         # input length: 254
                u'x.' * 126 + u'pl',
                # too long -> cut from left, then strip the leading '.':
                'x.' * 127 + 'pl',         # input length: 256
                u'x.' * 127 + u'pl',
                'x.' * 1000 + 'pl',        # input length: some big even number
                u'x.' * 1000 + u'pl',
            )),
            S(u'x.' * 124 + u'xn--2da', (  # result length: 255
                'x.' * 124 + 'ą',          # input length: 255
                u'x.' * 124 + u'ą',
                # too long -> cut from left (no leading '.' to strip in this case):
                'x.' * 125 + 'ą',          # input length: 257
                u'x.' * 125 + u'ą',
                'x.' * 1000 + 'ą',         # input length: some big odd number
                u'x.' * 1000 + u'ą',
            )),
        ))

    def test__setitem__fqdn__skipping_invalid(self):
        rd = self.rd_class()
        for invalid in [
                '',
                u'www...example.com',
                ' www.example.com',
                u'example.com ',
                'exam\xee\xddple.com',  # non-utf-8 data
                'exam\xee\xddple.com'.decode('utf-8', 'surrogateescape'),
                u'www.{}.com'.format('e' * 64),  # single label too long
                datetime.datetime.now(),
                None,
        ]:
            rd['fqdn'] = invalid
            self.assertNotIn('fqdn', rd)

    def test__setitem__client(self):
        self._test_setitem_valid('client', (
            S([], (
                [],
                (),
            )),
            S([u''], (
                '',
                u'',
                [''],
                (u'',),
            )),
            S([u'abc żó#'], (
                'abc żó#',
                u'abc żó#',
                ('abc żó#',),
                [u'abc żó#'],
            )),
            S([u'\udcee \udcdd'], (
                u'\udcee \udcdd',
                [u'\udcee \udcdd'],
            )),
            S([u'abc żó#', u'\udcee \udcdd'], (
                [u'abc żó#', u'\udcee \udcdd'],
                ['abc żó#', u'\udcee \udcdd'],
                [u'\udcee \udcdd', u'abc żó#'],
                [u'\udcee \udcdd', 'abc żó#'],
            )),
            S([u'a', u'x' * 32], (
                ['a', 'x' * 32],
                [u'a', u'x' * 32],
                ['x' * 32, u'a'],
                [u'x' * 32, 'a'],
            )),
        ))
        self._test_setitem_adjuster_error('client', (
            '\xee \xdd',        # <- non-utf-8 str
            ['a', 'x' * 33],    # <- too long item
            [u'a', u'x' * 33],  # <- too long item
            {u'abc żó#'},
            123,
            [123],
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__target(self):
        self._test_setitem_valid('target', (
            S(u'', ('', u'')),
            S(u'abc żó#', ('abc żó#', u'abc żó#')),
            S(u'\udcee \udcdd', u'\udcee \udcdd'),
            S(u'A' + 99 * u'ż', (
                'A' + 99 * 'ż',
                u'A' + 99 * u'ż',
                # too long -> cut right
                'A' + 100 * 'ż',
                u'A' + 100 * u'ż',
                'A' + 1000 * 'ż',
                u'A' + 1000 * u'ż',
            )),
        ))
        self._test_setitem_adjuster_error('target', (
            '\xee \xdd',  # <- non-utf-8 str
            ['abc żó#'],
            {u'abc żó#'},
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem___do_not_resolve_fqdn_to_ip(self):
        self._test_setitem_valid('_do_not_resolve_fqdn_to_ip', (
            True,
            False,
        ))
        self._test_setitem_adjuster_error('_do_not_resolve_fqdn_to_ip', (
            1,
            0,
            '1',
            '0',
            'true',
            'false',
            'True',
            'False',
            '',
            None,
        ))

    def test__setitem___parsed_old(self):
        rd = RecordDict()
        self._test_setitem_valid('_parsed_old', rd)
        self._test_setitem_adjuster_error('_parsed_old', {})

    def test__setitem___group(self):
        self._test_setitem_valid('_group', (
            S(u'', ('', u'')),
            S(u'abc-def$%^&*', ('abc-def$%^&*', u'abc-def$%^&*')),
        ))
        self._test_setitem_adjuster_error('_group', (
            '\xdd',
            123,
            None,
            ['a'],
            {},
            datetime.datetime.now(),
        ))

    def test__setitem__enriched(self):
        nondict_mapping = CIDict({'1.2.3.4': ['asn', 'cc']})
        nondict_mapping_empty = CIDict()
        self._test_setitem_valid('enriched', (
            S(([], {}), (
                ([], {}),
                [(), {}],
                [[], nondict_mapping_empty],
            )),
            S(([u'fqdn'], {}), (
                [['fqdn'], {}],
                ((u'fqdn',), {}),
                [('fqdn',), nondict_mapping_empty],
            )),
            S(([], {u'1.2.3.4': [u'asn', u'cc']}), (
                ((), {u'1.2.3.4': ['cc', 'asn']}),
                ([], {'1.2.3.4': [u'asn', 'cc', 'asn']}),
                [(), nondict_mapping],
            )),
            S(([u'fqdn'], {u'1.2.3.4': [u'asn', u'cc']}), (
                (['fqdn'], {u'1.2.3.4': ['asn', 'cc']}),
                (('fqdn',), {'1.2.3.4': [u'cc', u'asn', 'asn']}),
                [(u'fqdn',), nondict_mapping],
            )),
            S(([u'fqdn'], {u'1.2.3.44': [u'cc'], u'5.6.7.8': [u'asn', u'cc', u'ip']}), (
                ([u'fqdn'], {u'1.2.3.44': [u'cc', 'cc'], u'5.6.7.8': [u'cc', u'asn', u'ip']}),
                [('fqdn',), CIDict({'1.2.3.44': ['cc'], '5.6.7.8': ('ip', 'ip', 'cc', 'asn')})],
            )),
        ))
        self._test_setitem_adjuster_error('enriched', (
            # wrong item counts
            (),
            [],
            ([],),
            [{'1.2.3.4': ['asn', 'cc']}],
            ([], {}, {}),
            # wrong types
            (None, {}),
            ([], None),
            (['fqdn'], None),
            (['fqdn'], {None: ['asn', 'cc']}),
            (['fqdn'], {'1.2.3.4': None}),
            (['fqdn'], {'1.2.3.4': ['asn', None]}),
            ([None], {}),
            # wrong keys/values
            (['url'], {'1.2.3.4': ['asn', 'cc']}),
            (['fqdn'], {'1.2.3.444': ['asn', 'cc']}),
            (['fqdn'], {'1.2.3.4': ['url', 'cc']}),
        ))

    def test__setitem__adip(self):
        self._test_setitem_valid('adip', (
            S(u'x.0.0.0', (
                'x.0.0.0',
                'X.0.0.0',
                u'x.0.0.0',
                u'X.0.0.0',
            )),
            S(u'x.255.255.255', (
                'x.255.255.255',
                'X.255.255.255',
                u'x.255.255.255',
                u'X.255.255.255',
            )),
            S(u'x.2.133.4', (
                'x.2.133.4',
                'X.2.133.4',
                u'x.2.133.4',
                u'X.2.133.4',
            )),
            S(u'x.x.33.244', (
                'x.x.33.244',
                'x.X.33.244',
                'X.x.33.244',
                'X.X.33.244',
                u'x.x.33.244',
                u'x.X.33.244',
                u'X.x.33.244',
                u'X.X.33.244',
            )),
            S(u'x.x.x.255', (
                'x.x.x.255',
                u'X.X.X.255',
                'x.X.x.255',
                u'X.X.x.255',
            )),
            S(u'x.251.x.94', (
                'x.251.x.94',
                u'x.251.X.94',
                'X.251.x.94',
                u'X.251.X.94',
            )),
            S(u'x.x.x.x', (
                u'x.x.x.x',
                'X.X.X.X',
                u'x.x.X.X',
                'X.x.X.x',
            )),
        ))
        self._test_setitem_adjuster_error('adip', (
            # non anonymized
            '1.2.3.4',
            u'255.255.255.255',
            '0.0.0.0',
            u'192.168.10.255',
            # too big numbers
            u'x.x.x.910',
            'x.256.33.44',
            u'X.1000.1000.1000',
            # various defects
            '11.x.22.33',
            u'11.22.x.x',
            'xx.11.22.33',
            u'xx.11.xx.33',
            '11223344',
            u'x223344',
            '11.22.33',
            u'x.22.33',
            '.x.22.33.44',
            u'x.22...33.44',
            'x.22.33.44.',
            u'x.22.33.44.55',
            'x.022.33.44',
            u'xx.1.2.3',
            'x.2.00.3',
            u'x.2.3.00',
            'x.22.033.44',
            u' x.22.33.44',
            'x.22.33.44 ',
            u'x.22. 33.44',
            'x.22 .33.44',
            u'x.22.33.44/28',
            'x.-22.33.44',
            u'example.com',
            'X.2.133.4.',
            u'y.2.133.4',
            '',
            '1684366951',
            1684366951,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__additional_data(self):
        self._test_setitem_valid('additional_data', (
            S(u'', ('', u'')),
            S(u'AbĆ', ('AbĆ', u'AbĆ')),
            S(u'\udcdd', ('\xdd', '\xed\xb3\x9d', u'\udcdd')),
            S(u'a' + u'\udcdd' * 2999, (
                'a' + '\xdd' * 2999,
                'a' + '\xed\xb3\x9d' * 2999,
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                'a' + '\xdd' * 3000,
                'a' + '\xed\xb3\x9d' * 3000,
                u'a' + u'\udcdd' * 3000,
                'a' + '\xdd' * 10000,
                'a' + '\xed\xb3\x9d' * 10000,
                u'a' + u'\udcdd' * 10000,
            )),
        ))
        self._test_setitem_valid('additional_data', (
            # values of other types passed untouched
            ['\xdd' * 10000],
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__alternative_fqdns(self):
        self._test_setitem_valid('alternative_fqdns', (
            S([u''], ('', u'', [''], [u''])),
            S([u'AbĆ'], ('AbĆ', u'AbĆ', ['AbĆ'], [u'AbĆ'])),
            S([u'\udcdd'], (
                '\xdd',
                '\xed\xb3\x9d',
                u'\udcdd',
                ['\xdd'],
                ['\xed\xb3\x9d'],
                [u'\udcdd'],
            )),
            S([u'abc', u'\udcdd'], (
                ['abc', '\xdd'],
                (u'abc', '\xed\xb3\x9d'),
                ('abc', u'\udcdd'),
                [u'abc', u'\udcdd'],
            )),
            S([u'abc', u'\udcdd' * 2999 + u'a'], (
                ['abc', '\xdd' * 2999 + 'a'],
                [u'abc', '\xed\xb3\x9d' * 2999 + 'a'],
                ['abc', u'\udcdd' * 2999 + u'a'],
                # too long -> cut from left...
                ['abc', '\xdd' * 3000 + 'a'],
                [u'abc', '\xed\xb3\x9d' * 3000 + 'a'],
                ['abc', u'\udcdd' * 3000 + u'a'],
                [u'abc', u'\udcdd' * 10000 + u'a'],
                ['abc', '\xed\xb3\x9d' * 10000 + 'a'],
                ['abc', '\xed\xb3\x9d' * 10001 + 'a'],
                ['abc', '\xed\xb3\x9d' * 10002 + 'a'],
            )),
            S([u'x.' * 1498 + u'com'],  # result length: 2999
              (
                'x.' * 1498 + 'com',    # input length: 2999
                u'x.' * 1498 + u'com',
                # too long -> cut from left, then strip the leading '.'
                'x.' * 1499 + 'com',    # input length: 3001
                u'x.' * 1499 + u'com',
                'x.' * 10000 + 'com',   # input length: some big odd number
                u'x.' * 10000 + u'com',
            )),
        ))
        self._test_setitem_adjuster_error('alternative_fqdns', (
            123,
            [u'abc', 123],
            [123, 'abc'],
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__description(self):
        self._test_setitem_valid('description', (
            S(u'', ('', u'')),
            S(u'AbĆ', ('AbĆ', u'AbĆ')),
            S(u'\udcdd', ('\xdd', '\xed\xb3\x9d', u'\udcdd')),
            S(u'a' + u'\udcdd' * 2999, (
                'a' + '\xdd' * 2999,
                'a' + '\xed\xb3\x9d' * 2999,
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                'a' + '\xdd' * 3000,
                'a' + '\xed\xb3\x9d' * 3000,
                u'a' + u'\udcdd' * 3000,
                'a' + '\xdd' * 10000,
                'a' + '\xed\xb3\x9d' * 10000,
                u'a' + u'\udcdd' * 10000,
            )),
        ))
        self._test_setitem_adjuster_error('description', (
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__ip_network(self):
        self._test_setitem_valid('ip_network', (
            S(u'1.101.2.102/4', (
                '1.101.2.102/4',
                u'1.101.2.102/4',
                ('1.101.2.102', 4),
                [u'1.101.2.102', 4L],
                ('1.101.2.102', '4'),
            )),
            S(u'0.0.0.0/0', (
                '0.0.0.0/0',
                u'0.0.0.0/0',
                ('0.0.0.0', 0),
                [u'0.0.0.0', 0L],
                ('0.0.0.0', u'0'),
            )),
            S(u'255.255.255.255/32', (
                '255.255.255.255/32',
                u'255.255.255.255/32',
                ('255.255.255.255', 32),
                [u'255.255.255.255', 32L],
                ('255.255.255.255', u'32'),
            )),
        ))
        self._test_setitem_adjuster_error('ip_network', (
            'x.256.256.256/32',
            u'256.256.256.256/32',
            '255.255.255.255/33',
            u'255.255.255.255/x',
            '255.255. 255.255/32',
            u'\t255.255.255.255/32',
            '255.255.255.255 /32',
            u'255.255.255.255/ 32',
            ' 255.255.255.255/32',
            u'255.255.255.255/32 ',
            '255.255.255.0255/32',
            u'255.255.255.255/032',
            '255.255.255.0xff/32',
            u'255.255.255.255/0x20',
            '255.255.255.255/00',
            u'255.255.255.255/',
            '255.255.255.255',
            u'255.255.255/32'
            '255.255.255.255.255/32'
            u'/32',
            '255/32',
            u'32',
            '',
            (u'256.256.256.256', 32),
            ('255.255.255.255', 33),
            (u'255.255.255.255', '0x4'),
            ('255.255.255.255', '04'),
            (u'123.166.77.88.99', 4),
            ('166.77.88', 4),
            (u'1.2.3.25 ', 12),
            ('1.2.3.0xff', 22),
            ('', 22),
            ('1.2.3.4', ''),
            (123, 22),
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__min_amplification(self):
        self._test_setitem_valid('min_amplification', (
            S(u'', ('', u'')),
            S(u'AbĆ', ('AbĆ', u'AbĆ')),
            S(u'\udcdd', ('\xdd', '\xed\xb3\x9d', u'\udcdd')),
            S(u'a' + u'\udcdd' * 2999, (
                'a' + '\xdd' * 2999,
                'a' + '\xed\xb3\x9d' * 2999,
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                'a' + '\xdd' * 3000,
                'a' + '\xed\xb3\x9d' * 3000,
                u'a' + u'\udcdd' * 3000,
                'a' + '\xdd' * 10000,
                'a' + '\xed\xb3\x9d' * 10000,
                'a' + '\xed\xb3\x9d' * 10001,
                'a' + '\xed\xb3\x9d' * 10002,
                u'a' + u'\udcdd' * 10000,
            )),
        ))
        self._test_setitem_adjuster_error('min_amplification', (
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__urls_matched(self):
        urls1 = ['http://żażółć.com/?=\xdd', u'ftp://foo/ł']
        cleaned_urls1 = [u'ftp://foo/ł', u'http://żażółć.com/?=\udcdd']
        urls2 = (10000 * 'u',)
        cleaned_urls2 = [10000 * u'u']
        self._test_setitem_valid('urls_matched', (
            S({u'o1': cleaned_urls1, u'o2': cleaned_urls2}, (
                {'o1': urls1, 'o2': urls2},
                {u'o1': urls1, 'o2': urls2},
                {u'o1': urls1, u'o2': urls2},
                IterableUserDict({'o1': urls1, u'o2': urls2}),
            )),
        ))
        self._test_setitem_adjuster_error('urls_matched', (
            {},
            IterableUserDict(),
            {'o1': urls1, 'o2': []},
            {'o1': urls1, 33 * 'o': urls2},
            {'o1': urls1, None: urls2},
            urls1,
            set({'foo', 'bar'}),
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__name__without_category(self):
        rd = self.rd_class()
        with self.assertRaises(RuntimeError):
            rd['name'] = 'citadel'

    def test__setitem__name__with_normalization(self):
        assert 'bots' in CATEGORY_TO_NORMALIZED_NAME
        for category in CATEGORY_TO_NORMALIZED_NAME:
            # standard
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in ['citadel', u'citadel', 'CItaDEl', u'CItaDEl']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], 'citadel')
                    self.assertIsInstance(rd['name'], unicode)
                self.assertEqual(logger.mock_calls, [])

            # with regexp-based normalization
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in ['irc-bot', 'IRC-Bot',
                             u'irc-botnet', u'IRC-BotNet',
                             'ircboTnet', 'ircbot', 'iRc',
                             u'irc_bot', u'irc&botNET']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], 'irc-bot')
                    self.assertIsInstance(rd['name'], unicode)
                self.assertEqual(logger.mock_calls, [])

            # non-standard name -> logging warning
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                logger.getChild.side_effect = lambda cat: getattr(logger, cat)
                category_sublogger_call = getattr(call, category)
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in ['citaDDDel', u'ciTAdddEL', '  irc-bot  ',
                             u'IRC--Bół', 'tralalalala', u'irc--bół']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], name.lower())
                    self.assertIsInstance(rd['name'], unicode)

                # ...and also for non-standard very long names:
                for name in ['MAX-łong' * 31 + 'MAX-łon',            # max length
                             u'MAX-łong' * 31 + u'MAX-łonG',         # too long
                             'MAX-łong' * 31 + 'MAX-łonG',           # too long
                             u'max-łong' * 31 + u'max-łonGGGGGGG']:  # too long
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'max-łong' * 31 + u'max-łon')
                    self.assertIsInstance(rd['name'], unicode)

                self.assertEqual(logger.mock_calls, [
                    # NOTE: repeated names are not logged
                    # (it's checked after applying lower(), max-length-cut etc.)

                    call.getChild(category),
                    category_sublogger_call.warning('citadddel'),

                    call.getChild(category),
                    category_sublogger_call.warning('  irc-bot  '),

                    call.getChild(category),
                    category_sublogger_call.warning('irc--b\\xf3\\u0142'),

                    call.getChild(category),
                    category_sublogger_call.warning('tralalalala'),

                    call.getChild(category),
                    category_sublogger_call.warning('max-\\u0142ong' * 31 + 'max-\\u0142on'),
                ])

            # exactly the same but with `log_nonstandard_names` being false -> no logging
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                logger.getChild.side_effect = lambda cat: getattr(logger, cat)
                category_sublogger_call = getattr(call, category)
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=False)
                for name in ['citaDDDel', u'ciTAdddEL', '  irc-bot  ',
                             u'IRC--Bół', 'tralalalala', u'irc--bół']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], name.lower())
                    self.assertIsInstance(rd['name'], unicode)
                for name in ['MAX-łong' * 31 + 'MAX-łon',            # max length
                             u'MAX-łong' * 31 + u'MAX-łonG',         # too long
                             'MAX-łong' * 31 + 'MAX-łonG',           # too long
                             u'max-łong' * 31 + u'max-łonGGGGGGG']:  # too long
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'max-łong' * 31 + u'max-łon')
                    self.assertIsInstance(rd['name'], unicode)
                self.assertEqual(logger.mock_calls, [])

            # for long names, but with regexp-based normalization
            # (applied after lower(), before max-length-cut)
            # that returns some non-standard names (normally it should
            # not happen, but we still test such a case to check the
            # order of processing operations...)
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                logger.getChild.side_effect = lambda cat: getattr(logger, cat)
                category_sublogger_call = getattr(call, category)
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in ['MAX-long' * 31 + 'MAX-lon',            # max length (255)
                             u'MAX-long' * 31 + u'MAX-lonG',         # too long (256)
                             'max-LONG' * 31 + 'MAX-lonG',           # too long (256 again)
                             u'Max-long' * 31 + u'max-lonGGGGGGG',   # too long (262)
                             'short']:
                    with patch.dict(
                            'n6lib.record_dict.NAME_NORMALIZATION',
                            {
                                'm': [
                                    (re.compile(r'\A[\-a-z]{255}\Z'), 'Length:255.'),
                                    (re.compile(r'\A[\-a-z]{256}\Z'), 'Length:256.'),
                                    (re.compile(r'\A[\-a-z]{262}\Z'), 'Length:262.'),
                                ],
                                's': [
                                    (re.compile('\Ashort\Z'), 'Length:5.' * 300),
                                ],
                            }):
                        rd['name'] = name
                        self.assertTrue(rd['name'].startswith('Length:{}.'.format(len(name))))
                        self.assertTrue(len(rd['name']) <= 255)
                        self.assertIsInstance(rd['name'], unicode)
                self.assertEqual(logger.mock_calls, [
                    # NOTE: repeated names are not logged
                    # (it's checked after applying lower(), max-length-cut etc.)

                    call.getChild(category),
                    category_sublogger_call.warning('Length:255.'),

                    call.getChild(category),
                    category_sublogger_call.warning('Length:256.'),

                    call.getChild(category),
                    category_sublogger_call.warning('Length:262.'),

                    call.getChild(category),
                    category_sublogger_call.warning(('Length:5.' * 300)[:255]),
                ])

            # invalid name (bad type, non-utf8, empty) -> skipping
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in [True, 'blablabla\xee', '', u'']:
                    rd['name'] = name
                    self.assertNotIn('name', rd)
                self.assertEqual(logger.mock_calls, [])

    def test__setitem__name__without_normalization(self):
        categories = (set(CATEGORY_ENUMS) - set(CATEGORY_TO_NORMALIZED_NAME))
        assert categories
        for category in categories:
            # valid name -> setting without normalization
            rd = self.rd_class({'category': category})
            for name in [
                    'spyeye', u'spyeye',
                    'SPYeye', u'spYEYe',
                    255 * 'X', 255 * u'X']:
                rd['name'] = name
                self.assertEqual(rd['name'], name)
                self.assertIsInstance(rd['name'], unicode)

            # too long name -> right-cutting
            rd = self.rd_class({'category': category})
            for name, resultant_name in [
                    (255 * 'Ł' + 'A', 255 * u'Ł'),
                    (255 * u'Ł' + u'A', 255 * u'Ł'),
                    (300 * 'błablaB', 36 * u'błablaB' + u'bła')]:
                assert len(resultant_name) == 255
                assert isinstance(resultant_name, unicode)
                rd['name'] = name
                self.assertEqual(rd['name'], resultant_name)
                self.assertIsInstance(rd['name'], unicode)

            # invalid name (bad type, non-utf8, empty) -> skipping
            rd = self.rd_class({'category': category})
            for name in [True, 'blablabla\xee', '', u'']:
                rd['name'] = name
                self.assertNotIn('name', rd)

    def test__setitem__illegal_key(self):
        rd = self.rd_class()
        with self.assertRaises(RuntimeError):
            rd['some_illegal_key'] = 'foo'

    def test_append_item_to_multiadjusted_attr(self):
        rd = self.rd_class()
        with self.assertRaises(AdjusterError):
            rd.append_address({'ip': '1.2.3.1234567'})
        self.assertEqual(rd, {})

        rd.append_address({'ip': '1.2.3.4'})
        self.assertEqual(rd, {'address': [{'ip': '1.2.3.4'}]})

        rd.append_address({'ip': '1.2.3.80'})
        self.assertEqual(rd, {'address': [{'ip': '1.2.3.4'}, {'ip': '1.2.3.80'}]})

        with self.assertRaises(AdjusterError):
            rd.append_address({'ip': '1.2.3.1234567'})
        self.assertEqual(rd, {'address': [{'ip': '1.2.3.4'}, {'ip': '1.2.3.80'}]})

    def test_no_appender_for_nonmultiadjusted_attr(self):
        rd = self.rd_class()
        with self.assertRaises(AttributeError):
            rd.append_dip

    def _asserts_for_reused_context_manager(self, rd):
        entered_again = False
        with self.assertRaises(TypeError):
            with rd as enter_result:
                self.assertIs(enter_result, rd)
                self.assertTrue(rd.used_as_context_manager)
                self.assertFalse(hasattr(rd, 'context_manager_error_callback'))
                entered_again = True
        self.assertTrue(entered_again)
        self.assertTrue(rd.used_as_context_manager)
        self.assertFalse(hasattr(rd, 'context_manager_error_callback'))

    def _asserts_for_context_manager__exc_propagated(self, rd, error_callback, exc_type):
        self.assertFalse(rd.used_as_context_manager)
        self.assertTrue(hasattr(rd, 'context_manager_error_callback'))
        self.assertIs(rd.context_manager_error_callback, error_callback)
        entered = False
        with self.assertRaises(exc_type):
            with rd as enter_result:
                self.assertIs(enter_result, rd)
                self.assertTrue(rd.used_as_context_manager)
                self.assertTrue(hasattr(rd, 'context_manager_error_callback'))
                self.assertIs(rd.context_manager_error_callback, error_callback)
                entered = True
                raise exc_type('foo')
        self.assertTrue(entered)
        self.assertTrue(rd.used_as_context_manager)
        self.assertFalse(hasattr(rd, 'context_manager_error_callback'))
        self._asserts_for_reused_context_manager(rd)

    def _asserts_for_context_manager__no_exc_propagated(self, rd, error_callback, exc_type):
        self.assertFalse(rd.used_as_context_manager)
        self.assertTrue(hasattr(rd, 'context_manager_error_callback'))
        self.assertIs(rd.context_manager_error_callback, error_callback)
        entered = False
        with rd as enter_result:
            self.assertIs(enter_result, rd)
            self.assertTrue(rd.used_as_context_manager)
            self.assertTrue(hasattr(rd, 'context_manager_error_callback'))
            self.assertIs(rd.context_manager_error_callback, error_callback)
            entered = True
            if exc_type is not None:
                raise exc_type('foo')
        self.assertTrue(entered)
        self.assertTrue(rd.used_as_context_manager)
        self.assertFalse(hasattr(rd, 'context_manager_error_callback'))
        self._asserts_for_reused_context_manager(rd)

    def test_context_manager__without_error_callback(self):
        self._asserts_for_context_manager__exc_propagated(
            self.rd_class(),
            error_callback=None,
            exc_type=ZeroDivisionError)

    def test_context_manager__without_error_callback__no_error(self):
        self._asserts_for_context_manager__no_exc_propagated(
            self.rd_class(),
            error_callback=None,
            exc_type=None)

    def test_context_manager__with_error_callback_returning_True(self):
        exc_type = ZeroDivisionError
        error_callback_memo = []
        def error_callback(exc):
            self.assertIsInstance(exc, exc_type)
            error_callback_memo.append(sen.called)
            return True
        self._asserts_for_context_manager__no_exc_propagated(
            self.rd_class(context_manager_error_callback=error_callback),
            error_callback,
            exc_type)
        self.assertEqual(error_callback_memo, [sen.called])

    def test_context_manager__with_error_callback_returning_False(self):
        exc_type = ZeroDivisionError
        error_callback_memo = []
        def error_callback(exc):
            self.assertIsInstance(exc, exc_type)
            error_callback_memo.append(sen.called)
            return False
        self._asserts_for_context_manager__exc_propagated(
            self.rd_class(context_manager_error_callback=error_callback),
            error_callback,
            exc_type)
        self.assertEqual(error_callback_memo, [sen.called])

    def test_context_manager__with_error_callback_returning_True__no_error(self):
        error_callback_memo = []
        def error_callback(exc):
            error_callback_memo.append(sen.called)
            return True
        self._asserts_for_context_manager__no_exc_propagated(
            self.rd_class(context_manager_error_callback=error_callback),
            error_callback,
            exc_type=None)
        self.assertEqual(error_callback_memo, [])

    def test_context_manager__with_error_callback_returning_False__no_error(self):
        error_callback_memo = []
        def error_callback(exc):
            error_callback_memo.append(sen.called)
            return False
        self._asserts_for_context_manager__no_exc_propagated(
            self.rd_class(context_manager_error_callback=error_callback),
            error_callback,
            exc_type=None)
        self.assertEqual(error_callback_memo, [])

    ## maybe TODO later:
    # test other methods...


class TestBLRecordDict(TestRecordDict):

    rd_class = BLRecordDict
    only_required = dict(
        TestRecordDict.only_required,
        expires='2013-09-12 11:30:00',
    )

# Copyright (c) 2013-2023 NASK. All rights reserved.

import collections
import collections.abc as collections_abc
import copy
import pickle
import datetime
import itertools
import operator
import random
import re
import sys
import unittest
from collections import UserDict
from unittest.mock import (
    MagicMock,
    Mock,
    call,
    patch,
    sentinel as sen,
)

from n6lib.class_helpers import AsciiMixIn
from n6lib.common_helpers import (
    CIDict,
    as_bytes,
    as_unicode,
    picklable,
)
from n6lib.const import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    RESTRICTION_ENUMS,
    STATUS_ENUMS,
    EVENT_TYPE_ENUMS,
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
    unicode_surrogate_pass_and_esc_adjuster,
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

    def test__ensure_validates_by_regexp__with_re_pattern_str(self):
        adj = ensure_validates_by_regexp(u'456')
        self._test_regexp_validation_str(adj)

    def test__ensure_validates_by_regexp__with_re_compiled_str(self):
        adj = ensure_validates_by_regexp(re.compile(u'456'))
        self._test_regexp_validation_str(adj)

    def _test_regexp_validation_str(self, adj):
        result = adj(sen.self, u'123456789')
        self.assertEqual(result, u'123456789')
        with self.assertRaises(ValueError):
            adj(sen.self, u'56789')
        with self.assertRaises(TypeError):
            adj(sen.self, 56789)
        with self.assertRaises(TypeError):
            adj(sen.self, b'123456789')
        with self.assertRaises(TypeError):
            adj(sen.self, bytearray(b'123456789'))

    def test__ensure_validates_by_regexp__with_re_pattern_bytes(self):
        adj = ensure_validates_by_regexp(b'456')
        self._test_regexp_validation_bytes(adj)

    def test__ensure_validates_by_regexp__with_re_compiled_bytes(self):
        adj = ensure_validates_by_regexp(re.compile(b'456'))
        self._test_regexp_validation_bytes(adj)

    def _test_regexp_validation_bytes(self, adj):
        result = adj(sen.self, b'123456789')
        self.assertEqual(result, b'123456789')
        ba = bytearray(b'123456789')
        result = adj(sen.self, ba)
        self.assertIs(result, ba)
        with self.assertRaises(ValueError):
            adj(sen.self, b'56789')
        with self.assertRaises(TypeError):
            adj(sen.self, 56789)
        with self.assertRaises(TypeError):
            adj(sen.self, u'123456789')

    def test__make_adjuster_using_data_spec__mocked_field__not_too_long(self):
        rd_mock = MagicMock()
        rd_mock.data_spec.foo.sensitive = False
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
            rd_mock.data_spec.foo.sensitive = False
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
        rd_mock.data_spec.foo.sensitive = False
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
        rd_mock.data_spec.foo.sensitive = False
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
        self.assertIsInstance(result, str)
        with self.assertRaises(FieldValueTooLongError):
            adj(rd, '0123456789abcde.-edcba9876543210' + 'a')
        result = adj(rd, 'x.y')
        self.assertEqual(result, u'x.y')
        self.assertIsInstance(result, str)

        # too_long=<a callable object>
        adj = make_adjuster_using_data_spec(
            'source',
            on_too_long=lambda value, max_length: '{}.-long'.format(max_length))
        result = adj(rd, '0123456789abcde.-edcba9876543210' + 'a')
        self.assertEqual(result, u'32.-long')
        self.assertIsInstance(result, str)
        result = adj(rd, 'x.' + 'y' * 30)
        self.assertEqual(result, u'x.' + u'y' * 30)
        self.assertIsInstance(result, str)
        result = adj(rd, 'x.y')
        self.assertEqual(result, u'x.y')
        self.assertIsInstance(result, str)

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
                ensure_isinstance(bytes),
                make_adjuster_applying_value_method('lower')))
        # passing singular value
        result = adj(sen.self, b'ABC')
        self.assertEqual(result, [b'abc'])
        with self.assertRaises(TypeError):
            adj(sen.self, u'ABC')
        # passing sequence of values
        result = adj(sen.self, (b'ABC', b'DEF'))
        self.assertEqual(result, [b'abc', b'def'])
        with self.assertRaises(TypeError):
            adj(sen.self, (b'ABC', u'DEF'))
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
        with self.assertRaises(TypeError):
            adj(sen.self, dict(foo=2, SPAM=bytearray(b'BAR'), another=42.0))
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
        # str unchanged
        result = unicode_adjuster(sen.self, u'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        # UTF-8-encoded bytes/bytearray -> str
        result = unicode_adjuster(sen.self, u'ąBć #'.encode('utf-8'))
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        result = unicode_adjuster(sen.self, bytearray(u'ąBć #'.encode('utf-8')))
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        # illegal (non-UTF-8-or-ASCII) encoding
        with self.assertRaises(ValueError):
            unicode_adjuster(sen.self, u'ąBć #'.encode('latin2'))
        # illegal types
        with self.assertRaises(TypeError):
            unicode_adjuster(sen.self, datetime.datetime.now())
        with self.assertRaises(TypeError):
            unicode_adjuster(sen.self, None)

    def test__unicode_surrogate_pass_and_esc_adjuster(self):
        # str unchanged
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, u'ąBć #')
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        # UTF-8-encoded bytes/bytearray -> str
        b1 = u'ąBć #'.encode('utf-8')
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, b1)
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, bytearray(b1))
        self.assertEqual(result, u'ąBć #')
        self.assertIsInstance(result, str)
        # bytes/bytearray including non-UTF-8 mess -> str with binary mess encoded as surrogates
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, b'\xb1B\xe6 #')
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, str)
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, bytearray(b'\xb1B\xe6 #'))
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, str)
        # str with binary mess embedded -> unchanged
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, u'\udcb1B\udce6 #')
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, str)
        # quasi-UTF-8-encoded bytes/bytearray (with binary mess encoded as surrogates) -> str...
        b2 = b'\xed\xb2\xb1B\xed\xb3\xa6 #'
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, b2)
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, str)
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, bytearray(b2))
        self.assertEqual(result, u'\udcb1B\udce6 #')
        self.assertIsInstance(result, str)
        # str with (more eventful) binary mess embedded -> unchanged
        weird_string = (
            u'\udcdd\udced\udced\udcb2'  # mess converted to surrogates
            u'\udcb1'        # surrogate '\udcb1'
            u'\udced\udcb2'  # mess converted to surrogates
            u'\udced'        # mess converted to surrogate
            u'B'             # proper code point (ascii 'B')
            u'\ud7ff'        # proper code point '\ud7ff' (smaller than smallest surrogate)
            u'\udced\udca0'  # mess converted to surrogates
            u'\x7f'          # proper code point (ascii DEL)
            u'\ud800'        # surrogate '\ud800' (smallest one)
            u'\udfff'        # surrogate '\udfff' (biggest one) [note: *not* merged with one above]
            u'\udcee\udcbf\udcc0'  # mess converted to surrogates
            u'\ue000'        # proper code point '\ue000' (bigger than biggest surrogate)
            u'\udce6'        # mess converted to surrogate
            u'\udced'        # mess converted to surrogate
            u'\udced\udcb3'  # mess converted to surrogates
            u'\udce6'        # surrogate '\udce6'
            u'\udc80'        # mess converted to surrogate
            u'#'             # proper code point (ascii '#')
            u'\udcf0'        # mess converted to surrogate
            u'\udcf0\udc90'  # mess converted to surrogates
            u'\udcf0\udc90\udc8f'  # mess converted to surrogates
            u'\U000103ff'    # proper code point '\U000103ff' (non-BMP one)
            u'\udcf0\udc90\udc8f'  # mess converted to surrogates
            u' '             # proper code point (ascii ' ')
            u'\udced\udcb3')  # mess converted to surrogates
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, weird_string)
        self.assertEqual(result, weird_string)
        self.assertIsInstance(result, str)
        # bytes/bytearray incl. non-UTF-8 mess + quasi-UTF-8 with mess encoded as surrogates -> str
        weird_bytes = (
            b'\xdd\xed\xed\xb2'  # mess
            b'\xed\xb2\xb1'  # encoded surrogate '\udcb1'
            b'\xed\xb2'      # mess
            b'\xed'          # mess
            b'B'             # encoded proper code point (ascii 'B')
            b'\xed\x9f\xbf'  # encoded proper code point '\ud7ff' (smaller than smallest surrogate)
            b'\xed\xa0'      # mess
            b'\x7f'          # encoded proper code point (ascii DEL)
            b'\xed\xa0\x80'  # encoded surrogate '\ud800' (smallest one)
            b'\xed\xbf\xbf'  # encoded surrogate '\udfff' (biggest one)
            b'\xee\xbf\xc0'  # mess
            b'\xee\x80\x80'  # encoded proper code point '\ue000' (bigger than biggest surrogate)
            b'\xe6'          # mess
            b'\xed'          # mess
            b'\xed\xb3'      # mess
            b'\xed\xb3\xa6'  # encoded surrogate '\udce6'
            b'\x80'          # mess
            b'#'             # encoded proper code point (ascii '#')
            b'\xf0'          # mess
            b'\xf0\x90'      # mess
            b'\xf0\x90\x8f'  # mess
            b'\xf0\x90\x8f\xbf'  # encoded proper code point '\U000103ff' (non-BMP one)
            b'\xf0\x90\x8f'  # mess
            b' '             # encoded proper code point (ascii ' ')
            b'\xed\xb3')     # mess (starts like a proper surrogate but is too short)
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, weird_bytes)
        self.assertEqual(result, weird_string)
        self.assertIsInstance(result, str)
        result = unicode_surrogate_pass_and_esc_adjuster(sen.self, bytearray(weird_bytes))
        self.assertEqual(result, weird_string)
        self.assertIsInstance(result, str)
        # illegal types
        with self.assertRaises(TypeError):
            unicode_surrogate_pass_and_esc_adjuster(sen.self, datetime.datetime.now())
        with self.assertRaises(TypeError):
            unicode_surrogate_pass_and_esc_adjuster(sen.self, None)

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
        with self.assertRaises(TypeError):
            ipv4_preadjuster(sen.self, b'100.101.102.103')
        with self.assertRaises(TypeError):
            ipv4_preadjuster(sen.self, 1684366951.0)

    def test__url_preadjuster(self):
        result = url_preadjuster(sen.self, u'HTTP://www.EXAMPLĘ.com')
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, u'HTTP://www.EXAMPLĘ.com'.encode('utf-8'))
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, u'hxxp://www.EXAMPLĘ.com')
        self.assertEqual(result, u'http://www.EXAMPLĘ.com')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, bytearray(u'hXXps://www.EXAMPLĘ.com'.encode('utf-8')))
        self.assertEqual(result, u'https://www.EXAMPLĘ.com')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, u'FXP://www.EXAMPLĘ.com')
        self.assertEqual(result, u'ftp://www.EXAMPLĘ.com')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, u'blAbla+HA-HA.ojoj:()[]!@#:%^&*shKi→ś'.encode('utf-8'))
        self.assertEqual(result, u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś')
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, b'url:// \xee oraz \xdd')
        self.assertEqual(result, u'url:// \udcee oraz \udcdd')  # surrogate-escaped
        self.assertIsInstance(result, str)
        result = url_preadjuster(sen.self, u'url:// \udcee oraz \udcdd')  # surrogate-escaped
        self.assertEqual(result, u'url:// \udcee oraz \udcdd')        # the same
        self.assertIsInstance(result, str)
        for bad_value in [
                b''
                b'example.com',
                bytearray(b'http-//example.com/'),
                u'http : //example.com ',
                u'h??p://example.com/',
                u'ħŧŧþ://example.com/'.encode('utf-8'),
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
        type=EVENT_TYPE_ENUMS,
    )
    datetime_field_keys = 'time', 'until', 'expires', '_bl-time'
    flag_field_keys = 'ignored', 'block',
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

        assert self.only_required.keys() == self.rd_class.required_keys
        self.with_optional = dict(
            self.only_required,
            dip='127.0.0.3',
            _do_not_resolve_fqdn_to_ip=False,    # internal flag
        )
        self.with_custom = dict(
            self.only_required,
            dip='127.0.0.3',
            additional_data=b'additional-\xdd-data',
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
        self.with_url_data_1 = dict(
            self.only_required,
            url='foo:bar',
            # (as set by the code of a *parser*)
            _url_data=dict(
                orig=(
                    'http://\u0106ma.eXample.COM:80/'
                    '\udcdd\ud800Ala-ma-kota\U0010ffff\udccc'),
                norm_options=dict(
                    merge_surrogate_pairs=True,
                    empty_path_slash=True,
                    remove_ipv6_zone=True,
                ),
            ),
        )
        self.with_url_data_2 = dict(
            self.only_required,
            url='foo:bar',
            # (as set by the code of a *parser*)
            _url_data=dict(
                orig=(bytearray(
                    b'http://\xc4\x86ma.eXample.COM:80/'
                    b'\xed\xb3\x9d\xed\xa0\x80Ala-ma-kota\xf4\x8f\xbf\xbf\xcc')),
                norm_options=dict(
                    merge_surrogate_pairs=True,
                    remove_ipv6_zone=True,
                ),
            ),
        )
        self.with_url_data_3 = dict(
            self.only_required,
            url='foo:bar',
            # (as processed at later stages than the *parser* stage)
            _url_data=dict(
                orig_b64=(
                    'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                    'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                norm_options=dict(
                    unicode_str=True,
                    merge_surrogate_pairs=False,
                ),
            ),
        )
        self.with_url_data_ready = dict(  # *LEGACY*, to be removed...
            self.only_required,
            url='foo:bar',
            _url_data_ready=dict(
                url_orig=(
                    'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                    'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                url_norm_opts=dict(
                    transcode1st=True,
                    epslash=True,
                    rmzone=True,
                ),
            ),
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
                    iter(self.with_address1_singular.items()),        # iterator
                    list(self.with_address1_singular.items())):       # sequence
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
                    for pickle_proto in range(0, pickle.HIGHEST_PROTOCOL + 1):
                        rd = cls(
                            self.with_address2,
                            log_nonstandard_names=log_nonstandard_names,
                            context_manager_error_callback=callback)
                        rd2 = pickle.loads(pickle.dumps(rd, pickle_proto))
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
        ))

    def test__get_ready_dict__missing_keys(self):
        required_keys = list(self.only_required)
        for keys in itertools.chain.from_iterable(
                itertools.combinations(required_keys, i)
                for i in range(len(required_keys))):
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
            with_url_data_1=[
                dict(
                    self.only_required,
                    url='SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd',
                    custom=dict(
                        url_data=dict(
                            orig_b64=(
                                'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                            norm_brief='emru',  # ('u' added automatically because orig was `str`)
                        ),
                    ),
                ),
            ],
            with_url_data_2=[
                dict(
                    self.only_required,
                    url='SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd',
                    custom=dict(
                        url_data=dict(
                            orig_b64=(
                                'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_zA=='),
                            norm_brief='mr',  # ('u' not added because orig was binary)
                        ),
                    ),
                ),
            ],
            with_url_data_3=[
                dict(
                    self.only_required,
                    url='SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd',
                    custom=dict(
                        url_data=dict(
                            orig_b64=(
                                'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                            norm_brief='u',
                        ),
                    ),
                ),
            ],
            with_url_data_ready=[  # *LEGACY*, to be removed...
                dict(
                    self.only_required,
                    url='SY:http://\u0106ma.example.com/\ufffdAla-ma-kota\ufffd',
                    custom=dict(
                        url_data=dict(
                            url_orig=(
                                'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                            url_norm_opts=dict(
                                transcode1st=True,
                                epslash=True,
                                rmzone=True,
                            ),
                        ),
                    ),
                ),
            ],
        )
        for fixture_key, expected_db_items in sorted(expected_db_item_lists.items()):
            data = getattr(self, fixture_key)
            rd = self.rd_class(data)
            iterator = rd.iter_db_items()
            db_items = list(iterator)
            self.assertIsInstance(iterator, collections_abc.Iterator)
            self.assertCountEqual(db_items, expected_db_items)
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
                result_and_input_values = list(zip(values, values))
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
                    b'0123456789abcdef' * 2,
                    bytearray(b'0123456789aBCDEF') * 2,
                )),
                S(u'0123456789abcdef' * 2, (
                    u'0123456789abcdef' * 2,
                    u'0123456789aBCDEF' * 2,
                )),
            ))
            self._test_setitem_adjuster_error(key, (
                b'0123456789ABCDEF' * 2 + b'0',  # too long
                (u'0123456789ABCDEF' * 2)[:-1],  # too short
                u'0123456789abcdef' * 4,         # too long (sha256-like value)
                u'0123456789abcdef0123' * 2,     # too long (sha1-like value)
                u'0123456789abcdeX' * 2,         # illegal chars
                123,                             # wrong type
                None,
            ))

    def test__setitem__sha1(self):
        self._test_setitem_valid('sha1', (
            S(u'0123456789abcdef0123' * 2, (
                bytearray(b'0123456789abcdef0123') * 2,
                b'0123456789aBCDEF0123' * 2,
            )),
            S(u'0123456789abcdef0123' * 2, (
                u'0123456789abcdef0123' * 2,
                u'0123456789aBCDEF0123' * 2,
            )),
        ))
        self._test_setitem_adjuster_error('sha1', (
            u'0123456789ABCDEF0123' * 2 + '0',   # too long
            (b'0123456789ABCDEF0123' * 2)[:-1],  # too short
            u'0123456789abcdef' * 2,             # too short (md5-like value)
            u'0123456789abcdef' * 4,             # too long (sha256-like value)
            b'0123456789abcdeX0123' * 2,         # illegal chars
            0x123456789abcdef,                   # bad type
            None,
        ))

    def test__setitem__sha256(self):
        self._test_setitem_valid('sha256', (
            S(u'0123456789abcdef' * 4, (
                b'0123456789abcdef' * 4,
                bytearray(b'0123456789aBCDEF') * 4,
            )),
            S(u'0123456789abcdef' * 4, (
                u'0123456789abcdef' * 4,
                u'0123456789aBCDEF' * 4,
            )),
        ))
        self._test_setitem_adjuster_error('sha256', (
            u'0123456789ABCDEF' * 4 + '0',   # too long
            (b'0123456789ABCDEF' * 4)[:-1],  # too short
            u'0123456789abcdef' * 2,         # too short (md5-like value)
            bytearray(b'0123456789abcdef0123') * 2,     # too short (sha1-like value)
            u'0123456789abcdeX' * 4,         # illegal chars
            0x123456789abcdef,               # bad type
            None,
        ))

    def test__setitem__source(self):
        self._test_setitem_valid('source', (
            S(u'foo-foo.bar', (
                u'foo-foo.bar',
                b'foo-foo.bar',
                bytearray(b'foo-foo.bar'),
            )),
            S(u'-spam.ha--m--', (
                u'-spam.ha--m--',
                b'-spam.ha--m--',
                bytearray(b'-spam.ha--m--'),
            )),
            S(u'x.' + 30 * u'y', (  # 32-characters-long
                u'x.' + 30 * u'y',
                b'x.' + 30 * b'y',
                bytearray(b'x.' + 30 * b'y'),
            )),
        ))
        self._test_setitem_adjuster_error('source', (
            b'foo-foo',           # no dot
            u'foo-foo.bar.spam',  # more than one dot
            bytearray(b'Foo-FOO.bar'),       # illegal characters (here: uppercase letters)
            u'foo_foo.bar',       # illegal character (here: underscore)
            b'foo-foo.',          # no characters after the dot
            u'.bar',              # no characters before the dot
            b'.',                 # lone dot
            u'x.' + 31 * u'y',    # too long (33 characters)
            b'',                  # empty
            u'',                  # empty
            123,                  # not a str/bytes/bytearray
            None,
        ))

    def test__setitem__enum_fields(self):
        for key, enums in sorted(self.enum_collections.items()):
            assert isinstance(enums, tuple) and all(isinstance(v, str) for v in enums)
            self._test_setitem_valid(key, tuple(
                S(as_unicode(v), (as_unicode(v), as_bytes(v), bytearray(as_bytes(v))))
                for v in enums))
            self._test_setitem_adjuster_error(key, (
                u'bar',
                b'foo',
                bytearray(b'foo'),
                enums[0] + 'x',
                123,
                None,
            ))

    def test__setitem__count(self):
        self._test_setitem_valid('count', (
            S(0, (0, b'0', u'0', u'00000')),
            S(10, (10, bytearray(b'10'), u'10', u'00010')),
            S(4294967295, (4294967295, u'4294967295', u'00004294967295',
                           b'0004294967295', bytearray(b'4294967295'))),
        ))
        self._test_setitem_adjuster_error('count', (
            -1, b'-1', u'-1',
            4294967296, b'4294967296', u'4294967296',
            u'aaa', bytearray(b'aaa'), u'0x10', b'\x10', u'', b'',
            None, datetime.datetime.now(),
        ))

    def test__setitem__count_actual(self):
        self._test_setitem_valid('count_actual', (
            S(0, (0, bytearray(b'0'), u'0', u'00000')),
            S(10, (10, b'10', u'10', u'00010')),
            S(4294967295, (4294967295, u'4294967295', u'00004294967295',
                           b'4294967295', bytearray(b'0004294967295'))),
        ))
        self._test_setitem_adjuster_error('count_actual', (
            -1, b'-1', u'-1',
            4294967296, b'4294967296', u'4294967296',
            b'aaa', bytearray(b'0x10'), u'', b'\x10',
            None, datetime.datetime.now(),
        ))

    def test__setitem__unsigned_16bit_int_fields(self):
        for key in self.unsigned_16bit_int_field_keys:
            self._test_setitem_valid(key, (
                S(0, (0, b'0', u'0', u'00000')),
                S(10, (10, b'10', u'10', u'00010')),
                S(65535, (65535, b'65535', u'65535')),
            ))
            self._test_setitem_adjuster_error(key, (
                -1, b'-1', u'-1',
                65536, b'65536', u'65536',
                u'aaa', b'0x10', u'', b'\x10',
                None, datetime.datetime.now(),
            ))

    def test__setitem__unlimited_int_fields(self):
        for key in self.unlimited_int_field_keys:
            self._test_setitem_valid(key, (
                S(0, (0, b'0', u'0', u'00000')),
                S(10, (10, b'10', u'10', u'00010')),
                S(655357, (655357, bytearray(b'655357'), u'655357')),
                S(int(sys.maxsize - 1), int(sys.maxsize - 1)),
                S(int(sys.maxsize), int(sys.maxsize)),
                S(int(sys.maxsize + 1), int(sys.maxsize + 1)),
                S(int(-sys.maxsize - 1), int(-sys.maxsize - 1)),
                S(int(-sys.maxsize), int(-sys.maxsize)),
                S(int(-sys.maxsize + 1), int(-sys.maxsize + 1)),
                S(6553500000000111111112222222233333333, (
                    6553500000000111111112222222233333333,
                    b'6553500000000111111112222222233333333',
                    u'6553500000000111111112222222233333333')),
                S(-6553500000000111111112222222233333333, (
                    -6553500000000111111112222222233333333,
                    bytearray(b'-6553500000000111111112222222233333333'),
                    u'-6553500000000111111112222222233333333')),
            ))
            self._test_setitem_adjuster_error(key, (
                b'aaa', u'0x10', b'', None, datetime.datetime.now(),
            ))

    def test__setitem__datetime_fields(self):
        for key in self.datetime_field_keys:
            self._test_setitem_valid(key, (
                S('2013-06-13 10:02:00', (
                    datetime.datetime(2013, 6, 13, 10, 2),
                    b'2013-06-13 10:02:00',
                    u'2013-06-13T10:02',
                    bytearray(b'2013-06-13 10:02Z'),
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
                        b'2013-06-13 10:02:00-01:30'),
            ))
            self._test_setitem_adjuster_error(key, (
                u'2013-06-13 25:02',
                b'2013-06-13  10:02:04',
                123,
                None,
            ))

    def test__setitem__flag_fields(self):
        for key in self.flag_field_keys:
            self._test_setitem_valid(key, (
                S(True, 'true'),
                S(True, 'TRUE'),
                S(True, 'True'),
                S(True, '1'),
                S(True, 'y'),
                S(True, 'yes'),
                S(True, 'on'),
                S(True, 't'),
                S(True, True),
                S(True, 1),
                S(False, 'false'),
                S(False, 'FALSE'),
                S(False, 'False'),
                S(False, 'f'),
                S(False, '0'),
                S(False, 'off'),
                S(False, 'no'),
                S(False, 'n'),
                S(False, False),
                S(False, 0),
            ))
            self._test_setitem_adjuster_error(key, (
                'this_is_not_a_flag',
                'ffalse',
                'TTrue',
                'Truee',
                '1235',
                '2',
                1235,
                2,
                -1,
                None,
                [True],
                ['False'],
                [0],
            ))

    def test__setitem__address(self):
        self._test_setitem_valid('address', (
            S([], (
                [],
                (),
            )),
            S([{u'ip': u'1.2.3.4'}], (
                [{'ip': '1.2.3.4'}],
                {'ip': '1.2.3.4'},
                [UserDict({'ip': '1.2.3.4'})],
                UserDict({'ip': '1.2.3.4'}),
            )),
            S([{u'ip': u'100.101.102.103', u'cc': u'PL', u'asn': 123}], (
                [{'ip': '100.101.102.103', 'cc': b'PL', 'asn': 123}],
                ({'ip': u' 100.101. 102 .103 ', 'cc': bytearray(b'pl'), 'asn': u'123'},),
                {'ip': 1684366951, 'cc': u'pL', 'asn': b'0.123'},
                [UserDict({'ip': 1684366951, 'cc': u'pL', 'asn': u'ASN\t0.123'})],
                UserDict({'ip': 1684366951, 'cc': b'pL', 'asn': bytearray(b'0.123')}),
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
                {u'ip': u'111.122.133.146', u'cc': u'US', u'asn': 1234567},
                {u'ip': u'111.122.133.147', u'cc': u'US', u'asn': 1234567},
                {u'ip': u'111.122.133.148', u'cc': u'US', u'asn': 809087598},
                {u'ip': u'111.122.133.149', u'cc': u'US', u'asn': 809087598},
            ], [
                {'ip': u'1.2.3.4', 'cc': b'PL', u'asn': 123},
                {'ip': u'1.2.3.5', 'cc': bytearray(b'PL'), 'asn': 0},
                {'ip': u'1.2.3.6', 'cc': u'PL', 'asn': b'0.0'},
                {'ip': u'1.2.3.7', 'cc': b'PL', u'asn': u'as0.1'},
                {'ip': u'1.2.3.8', 'cc': b'PL', 'asn': b'1.0'},
                {'ip': u'1.2.3.9', 'cc': u'PL', 'asn': bytearray(b'0.65535')},
                {'ip': u'1.2.3.10', 'cc': 'PL', u'asn': u'65535.0'},
                {'ip': u'111.122.133.144', 'cc': b'US', 'asn': 1234567},
                {'ip': u'111.122.133.145', 'cc': u'US', 'asn': b'1234567'},
                {'ip': u'111.122.133.146', 'cc': u'US', 'asn': u'1234567'},
                {'ip': u'111.122.133.147', 'cc': b'US', 'asn': b'As1234567'},
                {'ip': u'111.122.133.148', u'cc': u'US', u'asn': u'as12345.45678'},
                {'ip': u'111.122.133.149', u'cc': u'US', u'asn': bytearray(b'12345.45678')},
            ]),
        ))
        self._test_setitem_adjuster_error('address', (
            [{'cc': 'PL', 'asn': 123}],
            {'ip': '100.101.102.103', 'cc': 'PL', 'asn': 123, 'xxx': 'spam'},
            [{'ip': '100.101.102.1031', 'cc': 'PL', 'asn': 123}],
            {'ip': '0.0.0.0', 'cc': 'PL', 'asn': 123},       # (disallowed: "no IP" placeholder)
            [{'ip': '0.00.000.0', 'cc': 'PL', 'asn': 123}],  # (disallowed: "no IP" placeholder)
            {'ip': '00.00.00.00', 'cc': 'PL', 'asn': 123},   # (disallowed: "no IP" placeholder)
            [{'ip': 0, 'cc': 'PL', 'asn': 123}],             # (disallowed: "no IP" placeholder)
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
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': 'as.0.0'}],
            [{'ip': '100.101.102.103', 'cc': 'PL', 'asn': ' as 0.0'}],
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
            S(u'0.0.0.1', (1, u'0.0.0.1')),
            S(u'0.0.0.10', (10, u'0.0.0.10')),
            S(u'100.101.102.103', (
                u'100.101.102.103',
                u' 100 . 101 . 102.103',
                ' 100.101. 102 .103 ',
                ' 100 . 101\t.\n102 . 103 ',
                1684366951,
            )),
        ))
        self._test_setitem_adjuster_error('dip', (
            '1684366951',
            '100.101.102.103.100',
            '100.101.102.1030',
            '0.0.0.0',               # (disallowed: "no IP" placeholder)
            '00.0.0.00',             # (disallowed: "no IP" placeholder)
            0,                       # (disallowed: "no IP" placeholder)
            u'100.101.102',
            168436695123456789,
            ['100.101.102.103'],
            datetime.datetime.now(),
            '10',
            '',
            bytearray(b'0.0.0.10'),
            b'',
            None,
        ))

    def test__setitem__url__valid_or_too_long(self):
        self._test_setitem_valid('url', (
            S(u'http://www.EXAMPLĘ.com', (
                u'HTTP://www.EXAMPLĘ.com',
                u'HTTP://www.EXAMPLĘ.com'.encode('utf-8'),
                u'hxxp://www.EXAMPLĘ.com',
                u'hXXp://www.EXAMPLĘ.com'.encode('utf-8'),
                bytearray(u'hXXp://www.EXAMPLĘ.com'.encode('utf-8')),
            )),
            S(u'https://www.EXAMPLĘ.com', (
                u'HTTPS://www.EXAMPLĘ.com',
                u'htTPS://www.EXAMPLĘ.com'.encode('utf-8'),
                u'hxxps://www.EXAMPLĘ.com',
                bytearray(u'hXXpS://www.EXAMPLĘ.com'.encode('utf-8')),
            )),
            S(u'ftp://www.EXAMPLĘ.com', (
                u'FXP://www.EXAMPLĘ.com',
                u'ftp://www.EXAMPLĘ.com'.encode('utf-8'),
                bytearray(u'ftp://www.EXAMPLĘ.com'.encode('utf-8')),
            )),
            S(u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś', (
                u'blAbla+HA-HA.ojoj:()[]!@#:%^&*shKi→ś',
                u'blabla+ha-ha.ojoj:()[]!@#:%^&*shKi→ś'.encode('utf-8'),
                bytearray(u'blAbla+HA-HA.ojoj:()[]!@#:%^&*shKi→ś'.encode('utf-8')),
            )),
            S(u'url:// \udcee oraz \udcdd', (
                u'url:// \udcee oraz \udcdd',
                b'url:// \xee oraz \xdd',
                bytearray(b'url:// \xee oraz \xdd'),
            )),
            S(u'url:' + 2044 * u'\udcdd', (
                u'url:' + 2044 * u'\udcdd',
                b'url:' + 2044 * b'\xdd',
                u'url:' + 2045 * u'\udcdd',            # too long -> cut right
                b'url:' + 2045 * b'\xdd',              # too long -> cut right
                u'url:' + 20000 * u'\udcdd',           # too long -> cut right
                bytearray(b'url:' + 20000 * b'\xdd'),  # too long -> cut right
            )),
        ))

    def test__setitem__url__skipping_invalid(self):
        rd = self.rd_class()
        for invalid in [
                u'',
                b'',
                bytearray(b''),
                u'example.com',
                b'example.com',
                bytearray(b'http-//example.com/'),
                u'http : //example.com ',
                u'http : //example.com ' + 3000 * u'x:',
                u'h??p://example.com/',
                u'ħŧŧþ://example.com/',
                u'ħŧŧþ://example.com/'.encode('utf-8'),
                u'http : //example.com ',
                datetime.datetime.now(),
                None,
        ]:
            rd['url'] = invalid
            self.assertNotIn('url', rd)

    def test__setitem___url_data(self):
        self._test_setitem_valid('_url_data', (
            S(
                dict(
                    orig_b64=(
                        'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                        'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                    norm_options=dict(
                        unicode_str=True,  # (<- always `True` if given `orig` was a `str`)
                        merge_surrogate_pairs=False,
                        empty_path_slash=True,
                    ),
                ),
                (
                    # (as set by the code of a *parser*)
                    dict(
                        orig=(
                            'http://\u0106ma.eXample.COM:80/'
                            '\udcdd\ud800Ala-ma-kota\U0010ffff\udccc'),
                        norm_options=dict(
                            # (no need to provide `unicode_str` -- inferred from type of `orig`)
                            merge_surrogate_pairs=False,
                            empty_path_slash=True,
                        ),
                    ),
                    dict(
                        orig=(
                            'http://\u0106ma.eXample.COM:80/'
                            '\udcdd\ud800Ala-ma-kota\U0010ffff\udccc'),
                        norm_options=dict(
                            unicode_str=True,
                            merge_surrogate_pairs=False,
                            empty_path_slash=True,
                        ),
                    ),
                    # (as processed at later stages than the *parser* stage)
                    dict(
                        orig_b64=(
                            'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                            'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        norm_options=CIDict(  # (<- non-`dict` mapping is OK)
                            unicode_str=True,  # (<- here needed because of no `orig`)
                            merge_surrogate_pairs=False,
                            empty_path_slash=True,
                        ),
                    ),
                ),
            ),
            S(
                dict(
                    orig_b64='aHR0cDovL2Zvby5iYXIv',
                    norm_options=dict(
                        unicode_str=False,  # (<- always `False` if given `orig` was binary)
                    ),
                ),
                (
                    # (as set by the code of a *parser*)
                    dict(
                        orig=b'http://foo.bar/',
                        norm_options=dict(),  # (<- empty `norm_options` is perfectly OK)
                        # (^ no need to provide `unicode_str` -- inferred from type of `orig`)
                    ),
                    dict(
                        orig=bytearray(b'http://foo.bar/'),
                        norm_options=dict(
                            unicode_str=False,
                        ),
                    ),
                    # (as processed at later stages than the *parser* stage)
                    dict(
                        orig_b64='aHR0cDovL2Zvby5iYXIv',
                        norm_options=dict(
                            unicode_str=False,  # (<- here needed because of no `orig`)
                        ),
                    ),
                ),
            ),
            S(
                dict(
                    orig_b64=(
                        'aHR0cMSGbWEuZVhhbXBsZS5DT006ODAv'
                        '7bOd7aCAQWxhLW1hLWtvdGH0j7-_zA=='),
                    norm_options=dict(
                        unicode_str=False,  # (<- always `False` if given `orig` was binary)
                        empty_path_slash=True,
                    ),
                ),
                (
                    # (as set by the code of a *parser*)
                    CIDict(  # (<- non-`dict` mapping is OK)
                        orig=(bytearray(
                            b'http\xc4\x86ma.eXample.COM:80/'
                            b'\xed\xb3\x9d\xed\xa0\x80Ala-ma-kota\xf4\x8f\xbf\xbf\xcc')),
                        norm_options=dict(
                            # (no need to provide `unicode_str` -- inferred from type of `orig`)
                            empty_path_slash=True,
                        ),
                    ),
                    dict(
                        orig=(
                            b'http\xc4\x86ma.eXample.COM:80/'
                            b'\xed\xb3\x9d\xed\xa0\x80Ala-ma-kota\xf4\x8f\xbf\xbf\xcc'),
                        norm_options=dict(
                            unicode_str=False,
                            empty_path_slash=True,
                        ),
                    ),
                    # (as processed at later stages than the *parser* stage)
                    dict(
                        orig_b64=(
                            'aHR0cMSGbWEuZVhhbXBsZS5DT006ODAv'
                            '7bOd7aCAQWxhLW1hLWtvdGH0j7-_zA=='),
                        norm_options=dict(
                            unicode_str=False,  # (<- here needed because of no `orig`)
                            empty_path_slash=True,
                        ),
                    ),
                ),
            ),
            S(
                dict(
                    orig_b64=(
                        'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                        'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_zA=='),
                    norm_options=dict(
                        unicode_str=False,
                        remove_ipv6_zone=False,
                    ),

                    # Note: if `orig_b64` (rather than `orig`) is given
                    # (that typically happens at later processing stages
                    # than the *parser* stage) then any extra items are
                    # passed through without error -- to ease transition
                    # if new keys are supported in the future...
                    extra_item='blah-blah-blah...',
                    and_another_one=[{b'!'}],
                ),
                dict(
                    orig_b64=(
                        'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                        'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_zA=='),
                    norm_options=dict(
                        unicode_str=False,  # (<- here needed because of no `orig`)
                        remove_ipv6_zone=False,
                    ),
                    extra_item='blah-blah-blah...',
                    and_another_one=[{b'!'}],
                ),
            ),
        ))
        self._test_setitem_adjuster_error('_url_data', (
            dict(),                                  # missing keys...
            dict(orig=b'http://foo.bar/'),           # missing key: `norm_options`
            dict(orig_b64='aHR0cDovL2Zvby5iYXIv'),   # missing key: `norm_options`
            dict(norm_options=dict()),               # missing key: `orig` or `orig_b64`
            dict(
                orig=b'http://foo.bar/',             # *either* `orig` *or* `orig_b64`
                orig_b64='aHR0cDovL2Zvby5iYXIv',     # should be present, but *not both*
                norm_options=dict(),
            ),
            dict(
                orig=b'http://foo.bar/',
                norm_options=dict(),
                extra_item=42,                       # <- extra (unknown) key when `orig` given
            ),
            dict(
                orig='http://foo.bar/',
                norm_options=dict(
                    unicode_str=False,               # <- `False` is wrong when `orig` is a `str`
                ),
            ),
            dict(
                orig=b'http://foo.bar/',
                norm_options=dict(
                    unicode_str=True,                # <- `True` is wrong when `orig` is binary
                ),
            ),
            dict(
                orig=bytearray(b'http://foo.bar/'),
                norm_options=dict(
                    unicode_str=True,                # <- `True` is wrong when `orig` is binary
                ),
            ),
            dict(
                orig_b64='aHR0+DovL2Zvby/iYXIv',     # <- non-URL-safe-Base64-variant character(s)
                norm_options=dict(),
            ),
            dict(
                orig='',                             # <- empty
                norm_options=dict(),
            ),
            dict(
                orig=b'',                            # <- empty
                norm_options=dict(),
            ),
            dict(
                orig=bytearray(b''),                 # <- empty
                norm_options=dict(),
            ),
            dict(
                orig_b64='',                         # <- empty
                norm_options=dict(),
            ),
            dict(
                orig_b64=('0' * (2**17 + 4)),        # <- too long
                norm_options=dict(),
            ),
            dict(
                orig=(b'x' * (2**19)),               # <- too long
                norm_options=dict(),
            ),
            dict(
                orig=bytearray(b'x' * (2**19)),      # <- too long
                norm_options=dict(),
            ),
            dict(
                orig=('x' * (2**19)),                # <- too long
                norm_options=dict(),
            ),
            dict(
                orig={b'http://foo.bar/'},           # <- wrong type (`set` instead of: `str`,
                norm_options=dict(),                 #                `bytes` or `bytearray`)
            ),
            dict(
                orig_b64=['aHR0cDovL2Zvby5iYXIv'],   # <- wrong type (`list` instead of `str`)
                norm_options=dict(),
            ),
            dict(
                orig_b64=b'aHR0cDovL2Zvby5iYXIv',    # <- wrong type (`bytes` instead of `str`)
                norm_options=dict(),
            ),
            dict(
                orig=b'http://foo.bar/',
                norm_options=[],                     # <- wrong type (`list` instead of `dict`)
            ),
            dict(
                orig_b64='aHR0cDovL2Zvby5iYXIv',
                norm_options='d',                    # <- wrong type (`str` instead of `dict`)
            ),
            dict(
                orig=b'http://foo.bar/',
                norm_options=dict(
                    remove_ipv6_zone=1,              # <- wrong type (`int` instead of `bool`)
                ),
            ),
            # wrong types of the whole value (should be `dict`):
            b'http://foo.bar/',
            'aHR0cDovL2Zvby5iYXIv',
            [('orig', b'http://foo.bar/'), ('norm_options', dict())],
            {'orig_b64', 'norm_options'},
            1684366951,
            datetime.datetime.now(),
            None,
        ))

    def test__setitem__fqdn__valid_or_too_long(self):
        self._test_setitem_valid('fqdn', (
            S(u'www.example.com', (
                u'www.example.com',
                b'www.EXAMPLE.com',
                u'www.EXAMPLE.com',
                bytearray(b'www.example.com'),
            )),
            S(u'com', (
                b'CoM',
                u'CoM',
                bytearray(b'com'),
            )),
            S(u'www.xn--xmpl-bta2jf.com', (
                # internationalized domain names (str or UTF-8-decodable bytes/bytearray)...
                u'www.ęxąmplę.Com',
                u'www.ĘxĄmplę.Com'.encode('utf-8'),
                bytearray(u'www.ęxĄmplĘ.Com'.encode('utf-8')),
            )),
            S(u'www.{}.com'.format('a' * 63), (
                u'www.{}.com'.format('a' * 63),
                u'www.{}.com'.format('A' * 63),
                u'www.{}.com'.format('a' * 63).encode('utf-8'),
                bytearray(u'www.{}.com'.format('A' * 63).encode('utf-8')),
            )),
            S(u'www.-_mahnamana_muppetshow_.-com', (
                u'www.-_Mahnamana_MuppetShow_.-com',
                b'www.-_Mahnamana_MuppetShow_.-com',
                bytearray(b'www.-_Mahnamana_MuppetShow_.-com'),
            )),
            S(u'x.' * 126 + u'pl', (         # result length: 254
                u'x.' * 126 + u'pl',         # input length: 254
                b'x.' * 126 + b'pl',
                bytearray(b'x.' * 126 + b'pl'),
                # too long -> cut from left, then strip the leading '.':
                u'x.' * 127 + u'pl',         # input length: 256
                b'x.' * 127 + b'pl',
                bytearray(b'x.' * 127 + b'pl'),
                u'x.' * 1000 + u'pl',        # input length: some big even number
                b'x.' * 1000 + b'pl',
                bytearray(b'x.' * 1000 + b'pl'),
            )),
            S(u'x.' * 124 + u'xn--2da', (    # result length: 255
                u'x.' * 124 + u'ą',          # input length: 255
                b'x.' * 124 + u'ą'.encode('utf-8'),
                bytearray(b'x.' * 124 + u'ą'.encode('utf-8')),
                # too long -> cut from left (no leading '.' to strip in this case):
                u'x.' * 125 + u'ą',          # input length: 257
                b'x.' * 125 + u'ą'.encode('utf-8'),
                bytearray(b'x.' * 125 + u'ą'.encode('utf-8')),
                u'x.' * 1000 + u'ą',          # input length: some big odd number
                b'x.' * 1000 + u'ą'.encode('utf-8'),
                bytearray(b'x.' * 1000 + u'ą'.encode('utf-8')),
            )),
        ))

    def test__setitem__fqdn__skipping_invalid(self):
        rd = self.rd_class()
        for invalid in [
                u'',
                b'',
                bytearray(b''),
                u'www...example.com',
                b' www.example.com',
                bytearray(b' www.example.com'),
                u'example.com ',
                b'exam\xee\xddple.com',  # non-utf-8 data
                bytearray(b'exam\xee\xddple.com'),
                b'exam\xee\xddple.com'.decode('utf-8', 'surrogateescape'),
                u'www.{}.com'.format('e' * 64),  # single label too long
                bytearray('www.{}.com'.format('e' * 64).encode('utf-8')),
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
                b'',
                u'',
                [bytearray(b'')],
                (u'',),
            )),
            S([u'abc żó#'], (
                bytearray(u'abc żó#'.encode('utf-8')),
                u'abc żó#',
                (u'abc żó#'.encode('utf-8'),),
                [u'abc żó#'],
            )),
            S([u'\udcee \udcdd'], (
                u'\udcee \udcdd',
                [u'\udcee \udcdd'],
            )),
            S([u'abc żó#', u'\udcee \udcdd'], (
                [u'abc żó#', u'\udcee \udcdd'],
                [u'abc żó#'.encode('utf-8'), u'\udcee \udcdd'],
                [u'\udcee \udcdd', u'abc żó#'],
                [u'\udcee \udcdd', bytearray(u'abc żó#'.encode('utf-8'))],
            )),
            S([u'a', u'x' * 32], (
                [b'a', b'x' * 32],
                [u'a', u'x' * 32],
                [bytearray(b'x' * 32), u'a'],
                [u'x' * 32, b'a'],
            )),
        ))
        self._test_setitem_adjuster_error('client', (
            b'\xee \xdd',       # <- non-utf-8 mess
            [b'a', b'x' * 33],  # <- too long item
            [u'a', bytearray(b'x' * 33)],  # <- too long item
            [u'a', u'x' * 33],  # <- too long item
            {u'abc żó#'},
            123,
            [123],
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__target(self):
        self._test_setitem_valid('target', (
            S(u'', (u'', b'', bytearray(b''))),
            S(u'abc żó#', (u'abc żó#', u'abc żó#'.encode('utf-8'))),
            S(u'\udcee \udcdd', u'\udcee \udcdd'),
            S(u'A' + 99 * u'ż', (
                b'A' + 99 * u'ż'.encode('utf-8'),
                u'A' + 99 * u'ż',
                # too long -> cut right
                bytearray(b'A' + 100 * u'ż'.encode('utf-8')),
                u'A' + 100 * u'ż',
                b'A' + 1000 * u'ż'.encode('utf-8'),
                u'A' + 1000 * u'ż',
            )),
        ))
        self._test_setitem_adjuster_error('target', (
            bytearray(b'\xee \xdd'),  # <- non-utf-8 mess
            [u'abc żó#'.encode('utf-8')],
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
            b'1',
            b'0',
            'true',
            'false',
            'True',
            'False',
            '',
            bytearray(b''),
            None,
        ))

    def test__setitem___parsed_old(self):
        rd = RecordDict()
        self._test_setitem_valid('_parsed_old', rd)
        self._test_setitem_adjuster_error('_parsed_old', {})

    def test__setitem___group(self):
        self._test_setitem_valid('_group', (
            S(u'', (u'', b'', bytearray(b''))),
            S(u'abc-def$%^&*', (u'abc-def$%^&*', b'abc-def$%^&*', bytearray(b'abc-def$%^&*'))),
        ))
        self._test_setitem_adjuster_error('_group', (
            b'\xdd',
            123,
            None,
            ['a'],
            {},
            datetime.datetime.now(),
        ))

    def test__setitem__enriched(self):
        nondict_mapping = CIDict({'1.2.3.4': ['asn', b'cc']})
        nondict_mapping_empty = CIDict()
        self._test_setitem_valid('enriched', (
            S(([], {}), (
                ([], {}),
                [(), {}],
                [[], nondict_mapping_empty],
            )),
            S(([u'fqdn'], {}), (
                [['fqdn'], {}],
                ((b'fqdn',), {}),
                [('fqdn',), nondict_mapping_empty],
            )),
            S(([], {u'1.2.3.4': [u'asn', u'cc']}), (
                ((), {'1.2.3.4': [b'cc', b'asn']}),
                ([], {b'1.2.3.4': [u'asn', 'cc', 'asn']}),
                [(), nondict_mapping],
            )),
            S(([u'fqdn'], {u'1.2.3.4': [u'asn', u'cc']}), (
                (['fqdn'], {'1.2.3.4': ['asn', 'cc']}),
                [('fqdn',), {'1.2.3.4': ['cc', 'asn', b'asn']}],
                ([b'fqdn'], {'1.2.3.4': ['asn', b'cc']}),
                [['fqdn'], {b'1.2.3.4': ['asn', 'cc']}],
                (['fqdn'], {'1.2.3.4': [bytearray(b'asn'), bytearray(b'cc')]}),
                [[bytearray(b'fqdn')], {b'1.2.3.4': [b'asn', b'cc']}],
                (('fqdn',), nondict_mapping),
            )),
            S(([u'fqdn'], {u'1.2.3.44': [u'cc'], u'5.6.7.8': [u'asn', u'cc', u'ip']}), (
                [[b'fqdn'], {b'1.2.3.44': [b'cc', u'cc'], b'5.6.7.8': [b'cc', u'asn', b'ip']}],
                ([u'fqdn'], {u'1.2.3.44': [u'cc', u'cc'], u'5.6.7.8': [u'cc', u'asn', u'ip']}),
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
            (['fqdn'], {'0.0.0.0': ['asn', 'cc']}),     # (disallowed: "no IP" placeholder)
            (['fqdn'], {'0.0.0.000': ['asn', 'cc']}),   # (disallowed: "no IP" placeholder)
            (['fqdn'], {'1.2.3.4': ['url', 'cc']}),
        ))

    def test__setitem__adip(self):
        self._test_setitem_valid('adip', (
            S(u'x.0.0.0', (
                b'x.0.0.0',
                b'X.0.0.0',
                u'x.0.0.0',
                u'X.0.0.0',
            )),
            S(u'x.255.255.255', (
                b'x.255.255.255',
                bytearray(b'X.255.255.255'),
                u'x.255.255.255',
                u'X.255.255.255',
            )),
            S(u'x.2.133.4', (
                b'x.2.133.4',
                b'X.2.133.4',
                u'x.2.133.4',
                u'X.2.133.4',
            )),
            S(u'x.x.33.244', (
                b'x.x.33.244',
                b'x.X.33.244',
                b'X.x.33.244',
                b'X.X.33.244',
                u'x.x.33.244',
                u'x.X.33.244',
                u'X.x.33.244',
                u'X.X.33.244',
            )),
            S(u'x.x.x.255', (
                b'x.x.x.255',
                u'X.X.X.255',
                b'x.X.x.255',
                u'X.X.x.255',
            )),
            S(u'x.251.x.94', (
                b'x.251.x.94',
                u'x.251.X.94',
                b'X.251.x.94',
                u'X.251.X.94',
            )),
            S(u'x.x.x.x', (
                u'x.x.x.x',
                b'X.X.X.X',
                u'x.x.X.X',
                bytearray(b'X.x.X.x'),
            )),
        ))
        self._test_setitem_adjuster_error('adip', (
            # non anonymized
            b'1.2.3.4',
            u'255.255.255.255',
            bytearray(b'0.0.0.0'),
            u'192.168.10.255',
            # too big numbers
            u'x.x.x.910',
            b'x.256.33.44',
            u'X.1000.1000.1000',
            # various defects
            b'11.x.22.33',
            u'11.22.x.x',
            b'xx.11.22.33',
            u'xx.11.xx.33',
            b'11223344',
            u'x223344',
            b'11.22.33',
            u'x.22.33',
            bytearray(b'.x.22.33.44'),
            u'x.22...33.44',
            b'x.22.33.44.',
            u'x.22.33.44.55',
            b'x.022.33.44',
            u'xx.1.2.3',
            b'x.2.00.3',
            u'x.2.3.00',
            b'x.22.033.44',
            u' x.22.33.44',
            b'x.22.33.44 ',
            u'x.22. 33.44',
            b'x.22 .33.44',
            u'x.22.33.44/28',
            b'x.-22.33.44',
            u'example.com',
            b'X.2.133.4.',
            u'y.2.133.4',
            '',
            bytearray(b''),
            '1684366951',
            1684366951,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__additional_data(self):
        self._test_setitem_valid('additional_data', (
            S(u'', (u'', b'', bytearray(b''))),
            S(u'AbĆ', (u'AbĆ', u'AbĆ'.encode('utf-8'), bytearray(u'AbĆ'.encode('utf-8')))),
            S(u'\udcdd', (u'\udcdd', b'\xdd', b'\xed\xb3\x9d', bytearray(b'\xdd'))),
            S(u'a' + u'\udcdd' * 2999, (
                b'a' + b'\xdd' * 2999,
                b'a' + b'\xed\xb3\x9d' * 2999,
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                b'a' + b'\xdd' * 3000,
                bytearray(b'a' + b'\xed\xb3\x9d' * 3000),
                u'a' + u'\udcdd' * 3000,
                b'a' + b'\xdd' * 10000,
                b'a' + b'\xed\xb3\x9d' * 10000,
                u'a' + u'\udcdd' * 10000,
            )),
        ))
        self._test_setitem_valid('additional_data', (
            # values of other types passed untouched
            [b'\xdd' * 10000],
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__alternative_fqdns(self):
        self._test_setitem_valid('alternative_fqdns', (
            S([u''], (b'', u'', [bytearray(b'')], [u''])),
            S([u'AbĆ'], (
                u'AbĆ',
                bytearray(u'AbĆ'.encode('utf-8')),
                [u'AbĆ'],
                [u'AbĆ'.encode('utf-8')])),
            S([u'\udcdd'], (
                b'\xdd',
                bytearray(b'\xed\xb3\x9d'),
                u'\udcdd',
                [bytearray(b'\xdd')],
                [b'\xed\xb3\x9d'],
                [u'\udcdd'],
            )),
            S([u'abc', u'\udcdd'], (
                [b'abc', b'\xdd'],
                [bytearray(b'abc'), bytearray(b'\xdd')],
                (u'abc', b'\xed\xb3\x9d'),
                (b'abc', u'\udcdd'),
                [u'abc', u'\udcdd'],
            )),
            S([u'abc', u'\udcdd' * 2999 + u'a'], (
                [b'abc', b'\xdd' * 2999 + b'a'],
                [u'abc', bytearray(b'\xed\xb3\x9d' * 2999 + b'a')],
                [b'abc', u'\udcdd' * 2999 + u'a'],
                # too long -> cut from left...
                [b'abc', b'\xdd' * 3000 + b'a'],
                [u'abc', b'\xed\xb3\x9d' * 3000 + b'a'],
                [b'abc', u'\udcdd' * 3000 + u'a'],
                [u'abc', u'\udcdd' * 10000 + u'a'],
                [b'abc', b'\xed\xb3\x9d' * 10000 + b'a'],
                [bytearray(b'abc'), bytearray(b'\xed\xb3\x9d' * 10001 + b'a')],
                [b'abc', b'\xed\xb3\x9d' * 10002 + b'a'],
            )),
            S([u'x.' * 1498 + u'com'],               # result length: 2999
              (
                b'x.' * 1498 + b'com',               # input length: 2999
                u'x.' * 1498 + u'com',
                # too long -> cut from left, then strip the leading '.'
                b'x.' * 1499 + b'com',               # input length: 3001
                u'x.' * 1499 + u'com',
                bytearray(b'x.' * 10000 + b'com'),   # input length: some big odd number
                u'x.' * 10000 + u'com',
            )),
        ))
        self._test_setitem_adjuster_error('alternative_fqdns', (
            123,
            [u'abc', 123],
            [123, b'abc'],
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__description(self):
        self._test_setitem_valid('description', (
            S(u'', (u'', b'', bytearray(b''))),
            S(u'AbĆ', (u'AbĆ', u'AbĆ'.encode('utf-8'), bytearray(u'AbĆ'.encode('utf-8')))),
            S(u'\udcdd', (b'\xdd', b'\xed\xb3\x9d', u'\udcdd')),
            S(u'a' + u'\udcdd' * 2999, (
                b'a' + b'\xdd' * 2999,
                b'a' + b'\xed\xb3\x9d' * 2999,
                bytearray(b'a' + b'\xed\xb3\x9d' * 2999),
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                b'a' + b'\xdd' * 3000,
                b'a' + b'\xed\xb3\x9d' * 3000,
                bytearray(b'a' + b'\xed\xb3\x9d' * 3000),
                u'a' + u'\udcdd' * 3000,
                b'a' + b'\xdd' * 10000,
                bytearray(b'a' + b'\xdd' * 10000),
                b'a' + b'\xed\xb3\x9d' * 10000,
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
                b'1.101.2.102/4',
                u'1.101.2.102/4',
                (b'1.101.2.102', 4),
                [u'1.101.2.102', 4],
                (b'1.101.2.102', b'4'),
                (u'1.101.2.102', u'4'),
                (u'1.101.2.102', b'4'),
                (u'1.101.2.102', bytearray(b'4')),
                (bytearray(b'1.101.2.102'), b'4'),
                (bytearray(b'1.101.2.102'), u'4'),
                (bytearray(b'1.101.2.102'), bytearray(b'4')),
            )),
            S(u'0.0.0.0/0', (
                b'0.0.0.0/0',
                u'0.0.0.0/0',
                (bytearray(b'0.0.0.0'), 0),
                [u'0.0.0.0', 0],
                (b'0.0.0.0', u'0'),
            )),
            S(u'255.255.255.255/32', (
                b'255.255.255.255/32',
                u'255.255.255.255/32',
                (bytearray(b'255.255.255.255'), 32),
                [u'255.255.255.255', 32],
                (b'255.255.255.255', u'32'),
            )),
        ))
        self._test_setitem_adjuster_error('ip_network', (
            b'x.256.256.256/32',
            u'256.256.256.256/32',
            b'255.255.255.255/33',
            u'255.255.255.255/x',
            b'255.255. 255.255/32',
            u'\t255.255.255.255/32',
            b'255.255.255.255 /32',
            u'255.255.255.255/ 32',
            bytearray(b' 255.255.255.255/32'),
            u'255.255.255.255/32 ',
            b'255.255.255.0255/32',
            u'255.255.255.255/032',
            b'255.255.255.0xff/32',
            u'255.255.255.255/0x20',
            b'255.255.255.255/00',
            u'255.255.255.255/',
            b'255.255.255.255',
            u'255.255.255/32',
            b'255.255.255.255.255/32',
            u'/32',
            b'255/32',
            u'32',
            b'',
            u'',
            (u'256.256.256.256', 32),
            (b'255.255.255.255', 33),
            (u'255.255.255.255', b'0x4'),
            (b'255.255.255.255', u'04'),
            (u'255.255.255.255', u'04'),
            (b'255.255.255.255', b'04'),
            (bytearray(b'123.166.77.88.99'), 4),
            (u'123.166.77.88.99', 4),
            (b'166.77.88', 4),
            (u'1.2.3.25 ', 12),
            (b'1.2.3.0xff', 22),
            (b'', 22),
            (u'', 22),
            (b'1.2.3.4', b''),
            (bytearray(b'1.2.3.4'), bytearray(b'')),
            (b'1.2.3.4', u''),
            (u'1.2.3.4', u''),
            (u'1.2.3.4', b''),
            (u'1.2.3.4', bytearray(b'')),
            (123, 22),
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__min_amplification(self):
        self._test_setitem_valid('min_amplification', (
            S(u'', (u'', b'', bytearray(b''))),
            S(u'AbĆ', (u'AbĆ', u'AbĆ'.encode('utf-8'), bytearray(u'AbĆ'.encode('utf-8')))),
            S(u'\udcdd', (b'\xdd', b'\xed\xb3\x9d', u'\udcdd')),
            S(u'a' + u'\udcdd' * 2999, (
                bytearray(b'a' + b'\xdd' * 2999),
                b'a' + b'\xed\xb3\x9d' * 2999,
                u'a' + u'\udcdd' * 2999,
                # too long -> cut from right
                bytearray(b'a' + b'\xdd' * 3000),
                b'a' + b'\xed\xb3\x9d' * 3000,
                u'a' + u'\udcdd' * 3000,
                b'a' + b'\xdd' * 10000,
                bytearray(b'a' + b'\xed\xb3\x9d' * 10000),
                b'a' + b'\xed\xb3\x9d' * 10001,
                bytearray(b'a' + b'\xed\xb3\x9d' * 10002),
                u'a' + u'\udcdd' * 10000,
            )),
        ))
        self._test_setitem_adjuster_error('min_amplification', (
            123,
            None,
            datetime.datetime.now(),
        ))

    def test__setitem__urls_matched(self):
        urls1 = [u'http://żażółć.com/?='.encode('utf-8') + b'\xdd', u'ftp://foo/ł']
        cleaned_urls1 = [u'ftp://foo/ł', u'http://żażółć.com/?=\udcdd']
        urls2 = (10000 * bytearray(b'u'),)
        cleaned_urls2 = [10000 * u'u']
        self._test_setitem_valid('urls_matched', (
            S({u'o1': cleaned_urls1, u'o2': cleaned_urls2}, (
                {'o1': urls1, 'o2': urls2},
                {u'o1': urls1, 'o2': urls2},
                {u'o1': urls1, u'o2': urls2},
                UserDict({'o1': urls1, u'o2': urls2}),
            )),
        ))
        self._test_setitem_adjuster_error('urls_matched', (
            {},
            UserDict(),
            {'o1': urls1, 'o2': []},
            {'o1': urls1, 33 * 'o': urls2},
            {'o1': urls1, None: urls2},
            urls1,
            {'foo', 'bar'},
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
                for name in [b'citadel', u'citadel', bytearray(b'CItaDEl'), u'CItaDEl']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'citadel')
                    self.assertIsInstance(rd['name'], str)
                self.assertEqual(logger.mock_calls, [])

            # with regexp-based normalization
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in [b'irc-bot', b'IRC-Bot',
                             u'irc-botnet', u'IRC-BotNet',
                             b'ircboTnet', bytearray(b'ircbot'), b'iRc',
                             u'irc_bot', u'irc&botNET']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], 'irc-bot')
                    self.assertIsInstance(rd['name'], str)
                self.assertEqual(logger.mock_calls, [])

            # non-standard name -> logging warning
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                logger.getChild.side_effect = lambda cat: getattr(logger, cat)
                category_sublogger_call = getattr(call, category)
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=True)
                for name in [b'citaDDDel',
                             u'ciTAdddEL',
                             bytearray(b'  irc-bot  '),
                             u'irC--B??',
                             b'tralalalala']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], as_unicode(name).lower())
                    self.assertIsInstance(rd['name'], str)
                for name in [u'IRC--Bół',
                             u'IRC--bóŁ'.encode('utf-8'),
                             u'irc--bół',
                             bytearray(u'irc--bół'.encode('utf-8'))]:
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'irc--b??')
                    self.assertIsInstance(rd['name'], str)

                # ...and also for non-standard very long names:
                for name in [u'MAX-łong' * 31 + u'MAX-łon',          # max length
                             u'MAX-łong'.encode('utf-8') * 31 + u'MAX-łon'.encode('utf-8'),
                             bytearray(u'MAX-łong'.encode('utf-8') * 31
                                       + u'MAX-Łon'.encode('utf-8')),
                             u'MAX-Łong' * 31 + u'MAX-łonG',         # too long
                             u'MAX-łong'.encode('utf-8') * 31 + u'MAX-łonG'.encode('utf-8'),
                             bytearray(u'MAX-łong'.encode('utf-8') * 31
                                       + u'MAX-łonG'.encode('utf-8')),
                             u'max-łong' * 31 + u'max-łonGGGGGGG']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'max-?ong' * 31 + u'max-?on')
                    self.assertIsInstance(rd['name'], str)

                self.assertEqual(logger.mock_calls, [
                    # NOTE: repeated names are not logged
                    # (it's checked after applying lower(), max-length-cut etc.)

                    call.getChild(category),
                    category_sublogger_call.warning('citadddel'),

                    call.getChild(category),
                    category_sublogger_call.warning('  irc-bot  '),

                    call.getChild(category),
                    category_sublogger_call.warning('irc--b??'),

                    call.getChild(category),
                    category_sublogger_call.warning('tralalalala'),

                    call.getChild(category),
                    category_sublogger_call.warning('max-?ong' * 31 + 'max-?on'),
                ])

            # exactly the same but with `log_nonstandard_names` being false -> no logging
            with patch('n6lib.record_dict.NONSTANDARD_NAMES_LOGGER') as logger:
                logger.getChild.side_effect = lambda cat: getattr(logger, cat)
                category_sublogger_call = getattr(call, category)
                rd = self.rd_class(
                    {'category': category},
                    log_nonstandard_names=False)
                for name in [b'citaDDDel',
                             u'ciTAdddEL',
                             bytearray(b'  irc-bot  '),
                             b'tralalalala']:
                    rd['name'] = name
                    self.assertEqual(rd['name'], as_unicode(name).lower())
                    self.assertIsInstance(rd['name'], str)
                for name in [u'IRC--Bół',
                             u'IRC--bóŁ'.encode('utf-8'),
                             u'irc--bół',
                             bytearray(u'irc--bół'.encode('utf-8'))]:
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'irc--b??')
                    self.assertIsInstance(rd['name'], str)
                for name in [u'MAX-łong' * 31 + u'MAX-łon',          # max length
                             u'MAX-łong'.encode('utf-8') * 31 + u'MAX-łon'.encode('utf-8'),
                             bytearray(u'MAX-łong'.encode('utf-8') * 31
                                       + u'MAX-łon'.encode('utf-8')),
                             u'MAX-łong' * 31 + u'MAX-łonG',         # too long
                             u'MAX-łong'.encode('utf-8') * 31 + u'MAX-łonG'.encode('utf-8'),
                             bytearray(u'MAX-łong'.encode('utf-8') * 31
                                       + u'MAX-łonG'.encode('utf-8')),
                             u'max-łong' * 31 + u'max-łonGGGGGGG']:  # too long
                    rd['name'] = name
                    self.assertEqual(rd['name'], u'max-?ong' * 31 + u'max-?on')
                    self.assertIsInstance(rd['name'], str)
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
                for name in [u'MAX-long' * 31 + u'MAX-lon',          # max length (255)
                             b'MAX-long' * 31 + b'MAX-lon',          # max length (255 again)
                             bytearray(b'MAX-long' * 31 + b'MAX-lon'),  # max length (255 again)
                             u'MAX-long' * 31 + u'MAX-lonG',         # too long (256)
                             b'max-LONG' * 31 + b'MAX-lonG',         # too long (256 again)
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
                                    (re.compile(r'\Ashort\Z'), 'Length:5.' * 300),
                                ],
                            }):
                        rd['name'] = name
                        self.assertTrue(rd['name'].startswith('Length:{}.'.format(len(name))))
                        self.assertTrue(len(rd['name']) <= 255)
                        self.assertIsInstance(rd['name'], str)
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
                for name in [True, b'blablabla\xee', b'', u'']:
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
                    b'spyeye',
                    u'spyeye',
                    bytearray(b'SPYeye'),
                    u'spYEYe',
                    255 * b'X',
                    255 * u'X']:
                rd['name'] = name
                self.assertEqual(rd['name'], as_unicode(name))
                self.assertIsInstance(rd['name'], str)

            # too long name -> right-cutting
            rd = self.rd_class({'category': category})
            for name, resultant_name in [
                    (255 * u'Ł'.encode('utf-8') + b'A',
                     255 * u'?'),

                    (255 * u'?' + u'A',
                     255 * u'?'),

                    (bytearray(300 * u'błablaB'.encode('utf-8')),
                     36 * u'b?ablaB' + u'b?a')]:

                assert len(resultant_name) == 255
                assert isinstance(resultant_name, str)
                rd['name'] = name
                self.assertEqual(rd['name'], resultant_name)
                self.assertIsInstance(rd['name'], str)

            # invalid name (bad type, non-utf8, empty) -> skipping
            rd = self.rd_class({'category': category})
            for name in [True, b'blablabla\xee', b'', u'']:
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
            rd.append_dip  # noqa

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

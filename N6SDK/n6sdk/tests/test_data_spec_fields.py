# Copyright (c) 2014-2025 NASK. All rights reserved.

import collections
import copy
import datetime
import decimal
import unittest
from unittest.mock import sentinel as sen

from n6sdk.data_spec.fields import (
    Field,
    DateTimeField,
    FlagField,
    UnicodeField,
    HexDigestField,
    MD5Field,
    SHA1Field,
    SHA256Field,
    UnicodeEnumField,
    UnicodeLimitedField,
    UnicodeLimitedByHypotheticalUTF8BytesLengthField,
    UnicodeRegexField,
    SourceField,
    IPv4Field,
    IPv6Field,
    AnonymizedIPv4Field,
    IPv4NetField,
    IPv6NetField,
    CCField,
    URLSubstringField,
    URLField,
    DomainNameSubstringField,
    DomainNameField,
    EmailSimplifiedField,
    IntegerField,
    ASNField,
    PortField,
    IBANSimplifiedField,
    ListOfDictsField,
    AddressField,
    DirField,
    ExtendedAddressField,
)
from n6sdk.datetime_helpers import FixedOffsetTimezone
from n6sdk.exceptions import (
    FieldValueError,
    FieldValueTooLongError,
)
from n6sdk.tests._generic_helpers import TestCaseMixin



#
# Some mix-ins and helpers
#

class FieldTestMixin(TestCaseMixin):

    CLASS = None              # must be set in concrete test case classes
    INIT_KWARGS_BASE = None   # can be set in concrete test case classes

    def test__clean_param_value(self):
        for init_kwargs, given, expected in self.cases__clean_param_value():
            assert isinstance(given, str)
            init_kwargs = dict(self.INIT_KWARGS_BASE or {}, **init_kwargs)
            f = self.CLASS(**init_kwargs)
            if isinstance(expected, type) and issubclass(
                  expected, BaseException):
                with self.assertRaises(expected) as cm:
                    f.clean_param_value(given)
                self.assertIs(type(cm.exception), expected,
                              f"{repr(cm.exception)=!s}; {str(cm.exception)=!s}")
            else:
                cleaned_value = f.clean_param_value(given)
                self.assertEqualIncludingTypes(cleaned_value, expected)

    def test__clean_result_value(self):
        for init_kwargs, given, expected in self.cases__clean_result_value():
            init_kwargs = dict(self.INIT_KWARGS_BASE or {}, **init_kwargs)
            deep_copy_of_given = copy.deepcopy(given)
            f = self.CLASS(**init_kwargs)
            if isinstance(expected, type) and issubclass(
                  expected, BaseException):
                with self.assertRaises(expected) as cm:
                    f.clean_result_value(given)
                self.assertIs(type(cm.exception), expected,
                              f"{repr(cm.exception)=!s}; {str(cm.exception)=!s}")
            else:
                cleaned_value = f.clean_result_value(given)
                self.assertEqualIncludingTypes(cleaned_value, expected)
            # ensure that the given value has not been modified
            self.assertEqualIncludingTypes(deep_copy_of_given, given)


class ArbitraryObject(object):
    # the copying methods are provided here to support the
    # deepcopy-based check in FieldTestMixin.test__clean_result_value()
    def __copy__(self): return self
    def __deepcopy__(self, memo): return self


class case(collections.namedtuple('case', 'init_kwargs, given, expected')):

    def __new__(cls, **kwargs):
        if 'init_kwargs' not in kwargs:
            kwargs['init_kwargs'] = {}
        return super(case, cls).__new__(cls, **kwargs)


#
# Tests of some generic field features
#

class TestInitKwargsAndAttributes(TestCaseMixin, unittest.TestCase):

    class _SuperField(Field):
        foo = sen.foo

    class MyField(_SuperField):
        bar = sen.bar

    def _check_std_attrs(self, f,
                         in_result=None,
                         in_params=None,
                         single_param=False,
                         extra_params={},
                         custom_info={}):
        self.assertIs(f.in_result, in_result)
        self.assertIs(f.in_params, in_params)
        self.assertIs(bool(f.single_param), bool(single_param))
        self.assertIsInstance(f.single_param, bool)
        self.assertEqualIncludingTypes(f.extra_params, extra_params)
        self.assertEqualIncludingTypes(f.custom_info, custom_info)

    def test_no_init_kwargs(self):
        f = self.MyField()
        self.assertIs(f.foo, sen.foo)
        self.assertIs(f.bar, sen.bar)
        self.assertEqualIncludingTypes(f._init_kwargs, {})
        self._check_std_attrs(f)

    def test_all_cls_attr_init_kwargs(self):
        f = self.MyField(foo=sen.custom_foo, bar=sen.custom_bar)
        self.assertIs(f.foo, sen.custom_foo)
        self.assertIs(f.bar, sen.custom_bar)
        self.assertEqualIncludingTypes(f._init_kwargs,
                                       dict(foo=sen.custom_foo,
                                            bar=sen.custom_bar))
        self._check_std_attrs(f)

    def test_standard_attr_init_kwargs(self):
        f = self.MyField(in_result='required',
                         in_params='optional',
                         single_param=True,
                         extra_params=dict(a=sen.a),
                         custom_info=dict(b=sen.b))
        self._check_std_attrs(f,
                              in_result='required',
                              in_params='optional',
                              single_param=True,
                              extra_params=dict(a=sen.a),
                              custom_info=dict(b=sen.b))
        self.assertEqualIncludingTypes(f._init_kwargs,
                                       dict(in_result='required',
                                            in_params='optional',
                                            single_param=True,
                                            extra_params=dict(a=sen.a),
                                            custom_info=dict(b=sen.b)))

    def test_various_attr_init_kwargs(self):
        f = self.MyField(in_result='optional',
                         foo=sen.custom_foo)
        self.assertIs(f.foo, sen.custom_foo)
        self.assertIs(f.bar, sen.bar)
        self._check_std_attrs(f, in_result='optional')
        self.assertEqualIncludingTypes(f._init_kwargs,
                                       dict(in_result='optional',
                                            foo=sen.custom_foo))

    def test_illegal_init_kwargs(self):
        with self.assertRaises(TypeError):
            self.MyField(booo=sen.custom_boo)
        with self.assertRaises(TypeError):
            self.MyField(foo=sen.custom_foo, booo=sen.custom_boo)
        with self.assertRaises(TypeError):
            Field(foo=sen.custom_foo)
        with self.assertRaises(TypeError):
            Field(bar=sen.custom_bar)
        with self.assertRaises(TypeError):
            Field(booo=sen.custom_booo)

    def test_legal_in_params_values(self):
        for value in ('optional', 'required', None):
            f = self.MyField(in_params=value)
            self.assertEqualIncludingTypes(f.in_params, value)

    def test_legal_in_result_values(self):
        for value in ('optional', 'required', None):
            f = self.MyField(in_result=value)
            self.assertEqualIncludingTypes(f.in_result, value)

    def test_illegal_in_params_values(self):
        for value in ('OPTIONAL', False, True, 'blablabla'):
            with self.assertRaises(ValueError):
                self.MyField(in_params=value)

    def test_illegal_in_result_values(self):
        for value in ('OPTIONAL', False, True, 'blablabla'):
            with self.assertRaises(ValueError):
                self.MyField(in_result=value)


#
# Test of particular field types
#

class TestDateTimeField(FieldTestMixin, unittest.TestCase):

    CLASS = DateTimeField

    def cases__clean_param_value(self):
        yield case(
            given='2014-04-01 01:07',
            expected=datetime.datetime(2014, 4, 1, 1, 7),
        )
        yield case(
            given='2014-04-01 01:07:42.123456',
            expected=datetime.datetime(2014, 4, 1, 1, 7, 42, 123456),
        )
        yield case(
            init_kwargs={'keep_sec_fraction': False},
            given='2014-04-01 01:07:42.123456',
            expected=datetime.datetime(2014, 4, 1, 1, 7, 42),
        )
        yield case(
            given='2014-04-01 01:07:42.123456+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42, 123456),
        )
        yield case(
            init_kwargs={'keep_sec_fraction': False},
            given='2014-04-01 01:07:42.123456+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42),
        )
        yield case(
            given='2014-04-01 01:07:42+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42),
        )
        yield case(
            given='2015-05-02T24:00',
            expected=datetime.datetime(2015, 5, 3, 0, 0),
        )
        yield case(
            given='2015-05-01',
            expected=FieldValueError,
        )
        yield case(
            given='2014-04-01T01:07:42.123456+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42, 123456),
        )
        yield case(
            given='2014-04-01T01:07+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 0),
        )
        yield case(
            given='20140401T010742',
            expected=datetime.datetime(2014, 4, 1, 1, 7, 42),
        )
        yield case(
            given='20140401T010742+02:00',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42),
        )
        yield case(
            given='20140401010742',
            expected=FieldValueError,
        )
        yield case(
            given='  2014-04-01 01:07:42.123456+02:00  ',
            expected=datetime.datetime(2014, 3, 31, 23, 7, 42, 123456),
        )
        yield case(
            given='2014-04-01      01:07:42.123456+02:00',
            expected=FieldValueError,
        )
        yield case(
            given='ąę',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='2014-04-01T01:07:42.123456+02:002014-04-01T01:07:42.123456+02:00',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        for c in self.cases__clean_param_value():
            yield c
            yield c._replace(given=c.given.encode('utf-8'))
            yield c._replace(given=bytearray(c.given.encode('utf-8')))
        yield case(
            given=b'\xdd',
            expected=FieldValueError,
        )
        dt = datetime.datetime(2014, 3, 31, 23, 7, 42, 123456)
        tz_dt = datetime.datetime(2014, 4, 1, 1, 7, 42, 123456,
                                  tzinfo=FixedOffsetTimezone(120))  # (+02:00)
        yield case(
            given=dt,
            expected=dt,
        )
        yield case(
            init_kwargs={'keep_sec_fraction': False},
            given=dt,
            expected=dt.replace(microsecond=0),
        )
        yield case(
            given=tz_dt,
            expected=dt,
        )
        yield case(
            init_kwargs={'keep_sec_fraction': False},
            given=tz_dt,
            expected=dt.replace(microsecond=0),
        )
        yield case(
            given=12345,
            expected=TypeError,
        )


class TestFlagField(FieldTestMixin, unittest.TestCase):

    CLASS = FlagField

    def cases__clean_param_value(self):
        raw_value_types = (str,)
        for c in self._common_cases(raw_value_types, exc_class=FieldValueError):
            yield c
        yield case(
            given='',
            expected=True,
        )
        yield case(
            init_kwargs={'enable_empty_param_as_true': True},
            given='',
            expected=True,
        )
        yield case(
            init_kwargs={'enable_empty_param_as_true': False},
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        class SomeClass(object):
            def __init__(self, s):
                self._s = s
            def __str__(self):
                return str(self._s)
            def __repr__(self):
                return '{}({!r})'.format(self.__class__.__name__, self._s)
            def __eq__(self, other):
                return isinstance(other, SomeClass) and self._s == other._s
            def __ne__(self, other):
                return not (self == other)
        raw_value_types = (str, bytes, bytearray, SomeClass)
        for c in self._common_cases(raw_value_types, exc_class=ValueError):
            yield c
        yield case(
            given=True,
            expected=True,
        )
        yield case(
            given=1,
            expected=True,
        )
        yield case(
            given=False,
            expected=False,
        )
        yield case(
            given=0,
            expected=False,
        )
        yield case(
            given=b'',
            expected=ValueError,
        )
        yield case(
            given='',
            expected=ValueError,
        )
        yield case(
            given=[1, 2, 3],
            expected=ValueError,
        )
        yield case(
            given=None,
            expected=ValueError,
        )

    def _common_cases(self, raw_value_types, exc_class):
        def as_tp_instance(tp, val):
            if tp in (bytes, bytearray):
                return tp(str(val).encode('utf-8'))
            return tp(val)

        for tp in raw_value_types:
            # correct input cases:
            for raw_value_base, cleaned_value in [
                ('1', True),
                ('y', True),
                ('yes', True),
                ('t', True),
                ('true', True),
                ('on', True),
                ('Y', True),
                ('YES', True),
                ('T', True),
                ('TRUE', True),
                ('ON', True),
                ('Yes', True),
                ('trUe', True),
                ('oN', True),
                ('0', False),
                ('n', False),
                ('no', False),
                ('f', False),
                ('false', False),
                ('off', False),
                ('N', False),
                ('NO', False),
                ('F', False),
                ('FALSE', False),
                ('OFF', False),
                ('No', False),
                ('fAlSe', False),
                ('ofF', False),
            ]:
                yield case(
                    given=as_tp_instance(tp, raw_value_base),
                    expected=cleaned_value,
                )
            # erroneous input cases:
            for raw_value_base in [
                'o',
                'ye',
                'Truth',
                '2',
                '11',
                '-1',
            ]:
                yield case(
                    given=as_tp_instance(tp, raw_value_base),
                    expected=exc_class,
                )


class TestUnicodeField(FieldTestMixin, unittest.TestCase):

    CLASS = UnicodeField

    def cases__clean_param_value(self):
        yield case(
            given='ascii',
            expected='ascii',
        )
        yield case(
            given='kąŧ¹²³',
            expected='kąŧ¹²³',
        )
        yield case(
            given='nń\uabcd\U00010000',
            expected='nń\uabcd\U00010000',
        )
        yield case(
            given='123abc   '*100000,
            expected='123abc   '*100000,
        )
        yield case(
            given=' ',
            expected=' ',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        some_chars = ''.join(map(chr, (list(range(1000)) + list(range(2 ** 16, 2 ** 16 + 1000)))))
        yield case(
            given=some_chars,
            expected=some_chars,
        )
        # (`encoding` and `decode_error_handling` are irrelevant to `str` input)
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given='fąfara',
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given='fąfara',
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given='dd\udcdd\udcee',
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given='ąń',
            expected='ąń',
        )
        yield case(
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given='\udcdd \U00010000',
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udcdd \U00010000',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given='\udcdd \ud800\udc00',
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udcdd \ud800\udc00',
            expected='\ufffd \U00010000',
        )

    def cases__clean_result_value(self):
        yield case(
            given='ascii',
            expected='ascii',
        )
        yield case(
            given=b'ascii',
            expected='ascii',
        )
        yield case(
            given=bytearray(b'ascii'),
            expected='ascii',
        )
        yield case(
            given='kąŧ¹²³',
            expected='kąŧ¹²³',
        )
        yield case(
            given=b'k\xc4\x85\xc5\xa7\xc2\xb9\xc2\xb2\xc2\xb3',
            expected='kąŧ¹²³',
        )
        yield case(
            given=bytearray(b'k\xc4\x85\xc5\xa7\xc2\xb9\xc2\xb2\xc2\xb3'),
            expected='kąŧ¹²³',
        )
        yield case(
            given='nń\uabcd\U00010000',
            expected='nń\uabcd\U00010000',
        )
        yield case(
            given=b'n\xc5\x84\xea\xaf\x8d\xf0\x90\x80\x80',
            expected='nń\uabcd\U00010000',
        )
        yield case(
            given=bytearray(b'n\xc5\x84\xea\xaf\x8d\xf0\x90\x80\x80'),
            expected='nń\uabcd\U00010000',
        )
        yield case(
            given='123abc   '*100000,
            expected='123abc   '*100000,
        )
        yield case(
            given=b'123abc   '*100000,
            expected='123abc   '*100000,
        )
        yield case(
            given=bytearray(b'123abc   '*100000),
            expected='123abc   '*100000,
        )
        yield case(
            given=' ',
            expected=' ',
        )
        yield case(
            given=b' ',
            expected=' ',
        )
        yield case(
            given=bytearray(b' '),
            expected=' ',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            given=b'',
            expected='',
        )
        yield case(
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': False},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': False},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=b' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'disallow_empty': True},
            given=bytearray(b' '),
            expected=' ',
        )
        some_chars = ''.join(map(chr, (list(range(1000)) + list(range(2 ** 16, 2 ** 16 + 1000)))))
        yield case(
            given=some_chars,
            expected=some_chars,
        )
        yield case(
            given=some_chars.encode('utf-8'),
            expected=some_chars,
        )
        yield case(
            given=bytearray(some_chars.encode('utf-8')),
            expected=some_chars,
        )
        # `encoding` is irrelevant to `str` input...
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given='fąfara',
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given='fąfara',
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given='dd\udcdd\udcee',
            expected='dd\udcdd\udcee',
        )
        # ...but it *is relevant* to binary input...
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=b'f\xc4\x85fara',
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=bytearray(b'f\xc4\x85fara'),
            expected='fąfara',
        )
        yield case(
            init_kwargs={'encoding': 'latin-1'},
            given=b'f\xc4\x85fara',
            expected='f\xc4\x85fara',
        )
        yield case(
            init_kwargs={'encoding': 'latin-1'},
            given=bytearray(b'f\xc4\x85fara'),
            expected='f\xc4\x85fara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given=b'f\xc4\x85fara',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given=bytearray(b'f\xc4\x85fara'),
            expected=FieldValueError,
        )
        # ...and `decode_error_handling` is also *relevant* to binary input
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'replace'},
            given=b'f\xc4\x85fara',
            expected='f\ufffd\ufffdfara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'replace'},
            given=bytearray(b'f\xc4\x85fara'),
            expected='f\ufffd\ufffdfara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'ignore'},
            given=b'f\xc4\x85fara',
            expected='ffara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'ignore'},
            given=bytearray(b'f\xc4\x85fara'),
            expected='ffara',
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'ascii'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'replace'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected='dd\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'encoding': 'ascii', 'decode_error_handling': 'replace'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected='dd\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'ignore'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected='dd',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'ignore'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected='dd',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'surrogateescape'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'dd\xdd\xee',                              # non-UTF-8
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'dd\xdd\xee'),                   # non-UTF-8
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=b'dd\xed\xb3\x9d\xed\xb3\xae',              # quasi-UTF-8 with lone surrogates
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'utf-8'},
            given=bytearray(b'dd\xed\xb3\x9d\xed\xb3\xae'),   # quasi-UTF-8 with lone surrogates
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'ignore'},
            given=b'dd\xed\xb3\x9d\xed\xb3\xae',              # non-UTF-8 with lone surrogates
            expected='dd',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'ignore'},
            given=bytearray(b'dd\xed\xb3\x9d\xed\xb3\xae'),   # quasi-UTF-8 with lone surrogates
            expected='dd',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'surrogatepass'},
            given=b'dd\xed\xb3\x9d\xed\xb3\xae',              # non-UTF-8 with lone surrogates
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8', 'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'dd\xed\xb3\x9d\xed\xb3\xae'),   # quasi-UTF-8 with lone surrogates
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8',
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'dd\xed\xb3\x9d\xed\xb3\xae',              # quasi-UTF-8 with lone surrogates
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'utf-8',
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'dd\xed\xb3\x9d\xed\xb3\xae'),   # quasi-UTF-8 with lone surrogates
            expected='dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'encoding': 'ascii',                 # (as noted above, `encoding`
                         'decode_error_handling': 'ignore'},  # and `decode_error_handling`
            given='ąń',                                       # are irrelevant to `str` input...)
            expected='ąń',
        )
        yield case(
            init_kwargs={'encoding': 'ascii',                 # (...but, of course, they are
                         'decode_error_handling': 'ignore'},  # *relevant* to binary input)
            given=b'\xc4\x85\xc5\x84',
            expected='',
        )
        yield case(
            init_kwargs={'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=bytearray(b'\xc4\x85\xc5\x84'),
            expected='',
        )
        yield case(
            init_kwargs={'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b'\xc4\x85\xc5\x84',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b'\xc4\x85\xc5\x84'),
            expected=FieldValueError,
        )
        yield case(
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            given=b'\xf0\x90\x80\x80',
            expected='\U00010000',
        )
        yield case(
            given=bytearray(b'\xf0\x90\x80\x80'),
            expected='\U00010000',
        )
        yield case(
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\U00010000',
        )
        yield case(
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given='\udcdd \U00010000',
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given=b'\xed\xb3\x9d \xf0\x90\x80\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb3\x9d \xf0\x90\x80\x80'),
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xed\xb3\x9d \xf0\x90\x80\x80',
            expected='\udced\udcb3\udc9d \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xf0\x90\x80\x80'),
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given=bytearray(b'\xdd \xf0\x90\x80\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xdd \xf0\x90\x80\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xf0\x90\x80\x80'),
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xf0\x90\x80\x80',
            expected='\udcdd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udcdd \U00010000',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=b'\xed\xb3\x9d \xf0\x90\x80\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb3\x9d \xf0\x90\x80\x80'),
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xed\xb3\x9d \xf0\x90\x80\x80',
            expected='\ufffd\ufffd\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xf0\x90\x80\x80'),
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=bytearray(b'\xdd \xf0\x90\x80\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xdd \xf0\x90\x80\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xf0\x90\x80\x80'),
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xf0\x90\x80\x80',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given='\udcdd \ud800\udc00',
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given=bytearray(b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80',
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80'),
            expected='\udced\udcb3\udc9d \udced\udca0\udc80\udced\udcb0\udc80',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80',
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': False},
            given=b'\xdd \xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xdd \xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xed\xa0\x80\xed\xb0\x80',
            expected='\udcdd \udced\udca0\udc80\udced\udcb0\udc80',
        )
        yield case(
            init_kwargs={'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xa0\x80\xed\xb0\x80'),
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given='\udcdd \ud800\udc00',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=bytearray(b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80'),
            expected='\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xed\xa0\x80\xed\xb0\x80',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'replace_surrogates': True},
            given=b'\xdd \xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xdd \xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xed\xa0\x80\xed\xb0\x80',
            expected='\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xa0\x80\xed\xb0\x80'),
            expected='\ufffd \U00010000',
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


# TODO:
# * improve test cases (+ remove redundant ones)
# * add __init__ method test
class TestHexDigestField(FieldTestMixin, unittest.TestCase):

    CLASS = HexDigestField
    INIT_KWARGS_BASE = {'num_of_characters': 32, 'hash_algo_descr': 'MD5'}

    def cases__clean_param_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE397' + '0',     # too long
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39',            # too short
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04ZZ5B0F767GG73EE397',           # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=32 * ' ',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'024a00e7c2ef04ee5b0f767ba73ee397'),
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'026A00E7C2EF04EE5B0F767BA73EE397'),
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04ee5B0F767BA73EE397'),
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE397' + '0',     # too long
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE397' + b'0',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE397' + b'0'),
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39',             # too short
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE39',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE39'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04ZZ5B0F767GG73EE397',    # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04ZZ5B0F767GG73EE397',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04ZZ5B0F767GG73EE397'),
            expected=FieldValueError,
        )
        yield case(
            given=32 * ' ',
            expected=FieldValueError,
        )
        yield case(
            given=32 * b' ',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(32 * b' '),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


# TODO: improve test cases (+ remove redundant ones)
class TestMD5Field(FieldTestMixin, unittest.TestCase):

    CLASS = MD5Field

    def cases__clean_param_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE397' + '0',     # too long
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39',            # too short
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04ZZ5B0F767GG73EE397',           # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=32 * ' ',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'024a00e7c2ef04ee5b0f767ba73ee397',
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'024a00e7c2ef04ee5b0f767ba73ee397'),
            expected='024a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'026A00E7C2EF04EE5B0F767BA73EE397',
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'026A00E7C2EF04EE5B0F767BA73EE397'),
            expected='026a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=b'023A00E7C2EF04ee5B0F767BA73EE397',
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04ee5B0F767BA73EE397'),
            expected='023a00e7c2ef04ee5b0f767ba73ee397',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE397' + '0',     # too long
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE397' + b'0',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE397' + b'0'),
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39',             # too short
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE39',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE39'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04ZZ5B0F767GG73EE397',    # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04ZZ5B0F767GG73EE397',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04ZZ5B0F767GG73EE397'),
            expected=FieldValueError,
        )
        yield case(
            given=32 * ' ',
            expected=FieldValueError,
        )
        yield case(
            given=32 * b' ',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(32 * b' '),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestSHA1Field(FieldTestMixin, unittest.TestCase):

    CLASS = SHA1Field

    def cases__clean_param_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee39701762354',
            expected='024a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE39701762354',
            expected='026a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE39701762354',
            expected='023a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39701762354' + '1',     # too long
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE3970176235',            # too short
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='023a00e7c2ef04zz5b0f767ba73ee39701762354',           # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=40 * ' ',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='024a00e7c2ef04ee5b0f767ba73ee39701762354',
            expected='024a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=b'024a00e7c2ef04ee5b0f767ba73ee39701762354',
            expected='024a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=bytearray(b'024a00e7c2ef04ee5b0f767ba73ee39701762354'),
            expected='024a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='026A00E7C2EF04EE5B0F767BA73EE39701762354',
            expected='026a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=b'026A00E7C2EF04EE5B0F767BA73EE39701762354',
            expected='026a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=bytearray(b'026A00E7C2EF04EE5B0F767BA73EE39701762354'),
            expected='026a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='023A00E7C2EF04ee5B0F767BA73EE39701762354',
            expected='023a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=b'023A00E7C2EF04ee5B0F767BA73EE39701762354',
            expected='023a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04ee5B0F767BA73EE39701762354'),
            expected='023a00e7c2ef04ee5b0f767ba73ee39701762354',
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE39701762354' + '1',     # too long
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE39701762354' + b'1',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE39701762354' + b'1'),
            expected=FieldValueError,
        )
        yield case(
            given='023A00E7C2EF04EE5B0F767BA73EE3970176235',             # too short
            expected=FieldValueError,
        )
        yield case(
            given=b'023A00E7C2EF04EE5B0F767BA73EE3970176235',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023A00E7C2EF04EE5B0F767BA73EE3970176235'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            given='023a00e7c2ef04zz5b0f767ba73ee39701762354',    # illegal chars
            expected=FieldValueError,
        )
        yield case(
            given=b'023a00e7c2ef04zz5b0f767ba73ee39701762354',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'023a00e7c2ef04zz5b0f767ba73ee39701762354'),
            expected=FieldValueError,
        )
        yield case(
            given=40 * ' ',
            expected=FieldValueError,
        )
        yield case(
            given=40 * b' ',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(40 * b' '),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestSHA256Field(FieldTestMixin, unittest.TestCase):

    CLASS = SHA256Field

    def cases__clean_param_value(self):
        yield case(
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given='9f86D081884c7d659a2FEAA0C55AD015A3BF4F1B2B0B822cd15d6c15b0F00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given='9F86D081884C7D659A2FEAA0C55AD015A3BF4F1B2B0B822CD15D6C15B0F00A08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            # too long
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08' + '12',
            expected=FieldValueError,
        )
        yield case(
            # too short
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            # illegal chars
            given='9f86d081884c7d659a2zzzz0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected=FieldValueError,
        )
        yield case(
            given=64 * ' ',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=bytearray(b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'),
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given='9f86D081884c7d659a2FEAA0C55AD015A3BF4F1B2B0B822cd15d6c15b0F00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=b'9f86D081884c7d659a2FEAA0C55AD015A3BF4F1B2B0B822cd15d6c15b0F00a08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=bytearray(b'9f86D081884c7d659a2FEAA0C55AD015A3BF4F1B2B0B822cd15d6c15b0F00a08'),
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given='9F86D081884C7D659A2FEAA0C55AD015A3BF4F1B2B0B822CD15D6C15B0F00A08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=b'9F86D081884C7D659A2FEAA0C55AD015A3BF4F1B2B0B822CD15D6C15B0F00A08',
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        yield case(
            given=bytearray(b'9F86D081884C7D659A2FEAA0C55AD015A3BF4F1B2B0B822CD15D6C15B0F00A08'),
            expected='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
        )
        # too long
        yield case(
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08' + '12',
            expected=FieldValueError,
        )
        yield case(
            given=b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08' + b'12',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'
                            + b'12'),
            expected=FieldValueError,
        )
        # too short
        yield case(
            given='9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a',
            expected=FieldValueError,
        )
        yield case(
            given=b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        # illegal chars
        yield case(
            given='9f86d081884c7d659a2zzzz0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected=FieldValueError,
        )
        yield case(
            given=b'9f86d081884c7d659a2\xc5\xbczzz0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'9f86d081884c7d659a2zzzz0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'),
            expected=FieldValueError,
        )
        yield case(
            given=64 * ' ',
            expected=FieldValueError,
        )
        yield case(
            given=64 * b' ',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(64 * b' '),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


# TODO: add __init__ method test
class TestUnicodeEnumField(FieldTestMixin, unittest.TestCase):

    CLASS = UnicodeEnumField
    INIT_KWARGS_BASE = {'enum_values': [b'ABC', '123', bytearray(b'en um')]}

    def cases__clean_param_value(self):
        yield case(
            given='ABC',
            expected='ABC',
        )
        yield case(
            given='123',
            expected='123',
        )
        yield case(
            given='en um',
            expected='en um',
        )
        yield case(
            given='NOT in enum',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), b'123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), b'123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', b'123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        # (note: `enum_values` items being bytes/bytearray are always decoded using UTF-8)
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), b'123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), b'123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', b'123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['\x0c\r\x0e', b'123', 'enum']},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', b'123', 'enum']},
            given='\udcdd',
            expected='\udcdd',
        )

    def cases__clean_result_value(self):
        yield case(
            given='ABC',
            expected='ABC',
        )
        yield case(
            given=b'123',
            expected='123',
        )
        yield case(
            given=bytearray(b'en um'),
            expected='en um',
        )
        yield case(
            given='NOT in enum',
            expected=FieldValueError,
        )
        yield case(
            given=b'NOT in enum',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'NOT in enum'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum']},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum']},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum']},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum']},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum']},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum']},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum']},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        # (note: `enum_values` items being bytes/bytearray are always decoded using UTF-8)
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['ąść'.encode('utf-8'), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('iso-8859-2')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': [bytearray('ąść'.encode('utf-8')), '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść'.encode('iso-8859-2'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['ąść', '123', 'enum'],
                         'encoding': 'iso-8859-2'},
            given='ąść'.encode('iso-8859-2'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'enum_values': ['\x0c\r\x0e', '123', 'enum']},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'enum_values': ['\x0c\r\x0e', '123', 'enum']},
            given=b'\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'enum_values': ['\x0c\r\x0e', '123', 'enum']},
            given=bytearray(b'\x0c\r\x0e'),
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum']},
            given='\udcdd',
            expected='\udcdd',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum']},
            given=b'\xdd',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum']},
            given=bytearray(b'\xdd'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum'],
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd',
            expected='\udcdd',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum'],
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd'),
            expected='\udcdd',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum'],
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd',
            expected='\udcdd',
        )
        yield case(
            init_kwargs={'enum_values': ['\udcdd', '123', 'enum'],
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd'),
            expected='\udcdd',
        )
        yield case(
            init_kwargs={'enum_values': ['123']},
            given=123,
            expected=TypeError,
        )
        yield case(
            init_kwargs={'enum_values': ['123']},
            given=None,
            expected=TypeError,
        )


# TODO: add __init__ method test
class TestUnicodeLimitedField(FieldTestMixin, unittest.TestCase):

    CLASS = UnicodeLimitedField

    def cases__clean_param_value(self):
        yield case(
            init_kwargs={'max_length': 1},
            given='a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given='*\uabcd&'*1000,
            expected='*\uabcd&'*1000,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given='*\uabcd&'*1000 + '*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 3, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='ą',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        # (`encoding` and `decode_error_handling` are irrelevant to `str` input)
        yield case(
            init_kwargs={'max_length': 3, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 2, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3, 'replace_surrogates': False},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 2, 'replace_surrogates': False},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3, 'replace_surrogates': True},
            given='\udcdd \udcee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_length': 2, 'replace_surrogates': True},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2, 'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_length': 1, 'replace_surrogates': True},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=' \uabcd ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd\uabcd',
            expected='\uabcd\uabcd',
        )

    def cases__clean_result_value(self):
        yield case(
            init_kwargs={'max_length': 1},
            given='a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'a'),
            expected='a',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=b'abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=bytearray(b'abc'),
            expected='abc',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=b'abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray(b'abc'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given='*\uabcd&'*1000,
            expected='*\uabcd&'*1000,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given=b'*\xea\xaf\x8d&'*1000,
            expected='*\uabcd&'*1000,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given=bytearray(b'*\xea\xaf\x8d&'*1000),
            expected='*\uabcd&'*1000,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given='*\uabcd&'*1000 + '*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given=b'*\xea\xaf\x8d&'*1000 + b'*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3000},
            given=bytearray(b'*\xea\xaf\x8d&'*1000 + b'*'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 3, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3, 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3, 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': False},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': False},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=b' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_length': 1, 'disallow_empty': True},
            given=bytearray(b' '),
            expected=' ',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'  '),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='ą',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'\xc4\x85',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'\xc4\x85'),
            expected='ą',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=b'\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=bytearray(b'\x0c\r\x0e'),
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=b'\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray(b'\x0c\r\x0e'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        # `encoding` is irrelevant to `str` input...
        yield case(
            init_kwargs={'max_length': 3, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_length': 2, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        # ...but it *is relevant* to binary input
        yield case(
            init_kwargs={'max_length': 2, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3, 'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 4, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 5, 'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 6, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected='\xc4\x85\u0139\x9b\xc4\x87',
        )
        # `decode_error_handling` is irrelevant to `str` input...
        yield case(
            init_kwargs={'max_length': 3},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        # ...but it *is relevant* to binary input
        yield case(
            init_kwargs={'max_length': 3},
            given=b'\xdd \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=b'\xdd \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': False},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': False},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': False},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True},
            given='\udcdd \udcee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_length': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'\xf0\x90\x80\x80',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'\xf0\x90\x80\x80'),
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_length': 1},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 1,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=' \uabcd ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=b' \xea\xaf\x8d ',
            expected='  ',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=bytearray(b' \xea\xaf\x8d '),
            expected='  ',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd\uabcd',
            expected='\uabcd\uabcd',
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b'\xea\xaf\x8d\xea\xaf\x8d',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b'\xea\xaf\x8d\xea\xaf\x8d'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_length': 6},
            given=123,
            expected=TypeError,
        )
        yield case(
            init_kwargs={'max_length': 6},
            given=None,
            expected=TypeError,
        )


# TODO: add __init__ method test
class TestUnicodeLimitedByHypotheticalUTF8BytesLengthField(FieldTestMixin, unittest.TestCase):

    CLASS = UnicodeLimitedByHypotheticalUTF8BytesLengthField

    def cases__clean_param_value(self):
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given='\uabcd'*1000,
            expected='\uabcd'*1000,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given='\uabcd'*1000 + '*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='ą',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='ą',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        # (`encoding` and `decode_error_handling` are irrelevant to `str` input)
        yield case(
            init_kwargs={'max_utf8_bytes': 6, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\u2013',
            expected='\u2013',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='\u2013',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7, 'replace_surrogates': False},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6, 'replace_surrogates': False},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7, 'replace_surrogates': True},
            given='\udcdd \udcee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6, 'replace_surrogates': True},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\U00010000',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4, 'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'replace_surrogates': True},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6, 'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5, 'replace_surrogates': True},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 10},
            given='\udcdd \ud800\udc00',
            expected='\udcdd \ud800\udc00',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 9},
            given='\udcdd \ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 8, 'replace_surrogates': True},
            given='\udcdd \ud800\udc00',
            expected='\ufffd \U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7, 'replace_surrogates': True},
            given='\udcdd \ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=' \uabcd ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=' \uabcd',
            expected=' \uabcd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected='\uabcd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected=FieldValueError,  # (not `FieldValueTooLongError` here...!)
        )

    def cases__clean_result_value(self):
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=b'a',
            expected='a',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=bytearray(b'a'),
            expected='a',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=b'abc',
            expected='abc',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=bytearray(b'abc'),
            expected='abc',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=b'abc',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=bytearray(b'abc'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given='\uabcd'*1000,
            expected='\uabcd'*1000,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given=b'\xea\xaf\x8d'*1000,
            expected='\uabcd'*1000,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given=bytearray(b'\xea\xaf\x8d'*1000),
            expected='\uabcd'*1000,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given='\uabcd'*1000 + '*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given=b'\xea\xaf\x8d'*1000 + b'*',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3000},
            given=bytearray(b'\xea\xaf\x8d'*1000 + b'*'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': False},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': False},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=b' ',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1, 'disallow_empty': True},
            given=bytearray(b' '),
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=b'  ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=bytearray(b'  '),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='ą',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=b'\xc4\x85',
            expected='ą',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=bytearray(b'\xc4\x85'),
            expected='ą',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given='ą',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=b'\xc4\x85',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1},
            given=bytearray(b'\xc4\x85'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=b'\x0c\r\x0e',
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=bytearray(b'\x0c\r\x0e'),
            expected='\x0c\r\x0e',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=b'\x0c\r\x0e',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=bytearray(b'\x0c\r\x0e'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='ąść'.encode('utf-8'),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=bytearray('ąść'.encode('utf-8')),
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        # `encoding` is irrelevant to `str` input...
        yield case(
            init_kwargs={'max_utf8_bytes': 6, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected='ąść',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5, 'encoding': 'iso-8859-2'},
            given='ąść',
            expected=FieldValueTooLongError,
        )
        # ...but it *is relevant* to binary input
        yield case(
            init_kwargs={'max_utf8_bytes': 2, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3, 'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 10, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 11, 'encoding': 'iso-8859-2'},
            given=bytearray('ąść'.encode('utf-8')),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 12, 'encoding': 'iso-8859-2'},
            given='ąść'.encode('utf-8'),
            expected='\xc4\x85\u0139\x9b\xc4\x87',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\u2013',
            expected='\u2013',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=b'\xe2\x80\x93',
            expected='\u2013',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=bytearray(b'\xe2\x80\x93'),
            expected='\u2013',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given='\u2013',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=b'\xe2\x80\x93',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2},
            given=bytearray(b'\xe2\x80\x93'),
            expected=FieldValueTooLongError,
        )
        # `decode_error_handling` is irrelevant to `str` input...
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        # ...but it *is relevant* to binary input
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given=b'\xdd \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=b'\xdd \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False},
            given='\udcdd \udcee',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected='\udcdd \udcee',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': False},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': False},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': False},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xdd \xed\xb3\xae',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': False,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xed\xb3\x9d \xee'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True},
            given='\udcdd \udcee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 7,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected='\ufffd \ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given='\udcdd \udcee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=bytearray(b'\xdd \xed\xb3\xae'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True,
                         'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'\xed\xb3\x9d \xee',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given='\U00010000',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given=b'\xf0\x90\x80\x80',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4},
            given=bytearray(b'\xf0\x90\x80\x80'),
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given='\U00010000',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=b'\xf0\x90\x80\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3},
            given=bytearray(b'\xf0\x90\x80\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='\ud800\udc00',  # valid surrogate pair
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\ud800\udc00',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'replace_surrogates': True},
            given='\ud800\udc00',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'replace_surrogates': True},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected='\U00010000',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'replace_surrogates': True},
            given='\ud800\udc00',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'replace_surrogates': True},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xa0\x80\xed\xb0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xa0\x80\xed\xb0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given='\udc00\ud800',  # not a valid surrogate pair
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\udc00\ud800',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given='\udc00\ud800',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected='\ufffd\ufffd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'replace_surrogates': True},
            given='\udc00\ud800',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'replace_surrogates': True},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'replace_surrogates': True},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=b'\xed\xb0\x80\xed\xa0\x80',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 5,
                         'replace_surrogates': True,
                         'decode_error_handling': 'surrogatepass'},
            given=bytearray(b'\xed\xb0\x80\xed\xa0\x80'),
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=' \uabcd ',
            expected=FieldValueTooLongError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=b' \xea\xaf\x8d ',
            expected='  ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=bytearray(b' \xea\xaf\x8d '),
            expected='  ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=' \uabcd',
            expected=' \uabcd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 4,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b' \xea\xaf\x8d'),
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 1,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b' \xea\xaf\x8d',
            expected=' ',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected='\uabcd',
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b'\xea\xaf\x8d'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 3,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b'\xea\xaf\x8d',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected=FieldValueError,  # (not `FieldValueTooLongError` here...!)
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b'\xea\xaf\x8d'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 2,
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b'\xea\xaf\x8d',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=123,
            expected=TypeError,
        )
        yield case(
            init_kwargs={'max_utf8_bytes': 6},
            given=None,
            expected=TypeError,
        )


# TODO: add __init__ method test
class TestUnicodeRegexField(FieldTestMixin, unittest.TestCase):

    CLASS = UnicodeRegexField

    def cases__clean_param_value(self):
        yield case(
            init_kwargs={'regex': r'axc'},
            given='abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c',
                         'error_msg_template': '"{}" is not a valid value'},
            given='abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'error_msg_template': '"{}" is not a valid value'},
            given='abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c'},
            given='abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?'},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z', 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=' ',
            expected=FieldValueError,
        )
        # (`encoding` and `decode_error_handling` are irrelevant to `str` input)
        yield case(
            init_kwargs={'regex': r'axc',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given='ax\uabcdc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given='\uabcd',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            init_kwargs={'regex': r'axc'},
            given='abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc'},
            given=b'abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc'},
            given=bytearray(b'abbbc'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c',
                         'error_msg_template': '"{}" is not a valid value'},
            given='abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c',
                         'error_msg_template': '"{}" is not a valid value'},
            given=b'abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c',
                         'error_msg_template': '"{}" is not a valid value'},
            given=bytearray(b'abbbc'),
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'error_msg_template': '"{}" is not a valid value'},
            given='abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'error_msg_template': '"{}" is not a valid value'},
            given=b'abbbc',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'error_msg_template': '"{}" is not a valid value'},
            given=bytearray(b'abbbc'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c'},
            given='abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c'},
            given=b'abbbc',
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'ab{3}c'},
            given=bytearray(b'abbbc'),
            expected='abbbc',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?'},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?'},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?'},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': False},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': False},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': False},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'(foo)?', 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given='',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=b'',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=bytearray(b''),
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z', 'disallow_empty': True},
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z', 'disallow_empty': True},
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z', 'disallow_empty': True},
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=' ',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=b' ',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z'},
            given=bytearray(b' '),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'encoding': 'ascii',                 # `encoding` and
                         'decode_error_handling': 'ignore'},  # `decode_error_handling` are
            given='ax\uabcdc',                                # irrelevant to `str` input...
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'encoding': 'ascii',                 # ...but, of course, they are
                         'decode_error_handling': 'ignore'},  # *relevant* to binary input
            given=b'ax\xea\xaf\x8dc',
            expected='axc',
        )
        yield case(
            init_kwargs={'regex': r'axc',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=bytearray(b'ax\xea\xaf\x8dc'),
            expected='axc',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given='\uabcd',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=b'\xea\xaf\x8d',
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore'},
            given=bytearray(b'\xea\xaf\x8d'),
            expected='',
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given='\uabcd',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=b'\xea\xaf\x8d',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'\A\Z',
                         'encoding': 'ascii',
                         'decode_error_handling': 'ignore',
                         'disallow_empty': True},
            given=bytearray(b'\xea\xaf\x8d'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'regex': r'123'},
            given=123,
            expected=TypeError,
        )
        yield case(
            init_kwargs={'regex': r'123'},
            given=None,
            expected=TypeError,
        )


class TestSourceField(FieldTestMixin, unittest.TestCase):

    CLASS = SourceField

    def cases__clean_param_value(self):
        yield case(
            given='foo-foo.bar',
            expected='foo-foo.bar',
        )
        yield case(
            given='-spam.ha--m--',
            expected='-spam.ha--m--',
        )
        yield case(
            given='x.' + 30 * 'y',
            expected='x.' + 30 * 'y',
        )
        yield case(
            given='x.y',
            expected='x.y',
        )
        yield case(
            given='foo-foo',          # no dot
            expected=FieldValueError,
        )
        yield case(
            given='foo-foo.bar.spam',  # more than one dot
            expected=FieldValueError,
        )
        yield case(
            given='Foo-FOO.bar',      # illegal characters (here: uppercase letters)
            expected=FieldValueError,
        )
        yield case(
            given='foo_foo.bar',       # illegal character (here: underscore)
            expected=FieldValueError,
        )
        yield case(
            given='foo-foo.',         # no characters after the dot
            expected=FieldValueError,
        )
        yield case(
            given='.bar',              # no characters before the dot
            expected=FieldValueError,
        )
        yield case(
            given='.',                # lone dot
            expected=FieldValueError,
        )
        yield case(
            given='x.' + 31 * 'y',     # too long
            expected=FieldValueTooLongError,
        )
        yield case(
            given='',                 # empty
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='foo-foo.bar',
            expected='foo-foo.bar',
        )
        yield case(
            given=b'-spam.ha--m--',
            expected='-spam.ha--m--',
        )
        yield case(
            given='x.' + 30 * 'y',
            expected='x.' + 30 * 'y',
        )
        yield case(
            given=bytearray(b'x.y'),
            expected='x.y',
        )
        yield case(
            given='foo-foo',           # no dot
            expected=FieldValueError,
        )
        yield case(
            given=b'foo-foo.bar.spam',  # more than one dot
            expected=FieldValueError,
        )
        yield case(
            given='Foo-FOO.bar',       # illegal characters (here: uppercase letters)
            expected=FieldValueError,
        )
        yield case(
            given=b'foo_foo.bar',       # illegal character (here: underscore)
            expected=FieldValueError,
        )
        yield case(
            given='foo-foo.',          # no characters after the dot
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'.bar'),   # no characters before the dot
            expected=FieldValueError,
        )
        yield case(
            given='.',                 # lone dot
            expected=FieldValueError,
        )
        yield case(
            given=b'x.' + 31 * b'y',   # too long
            expected=FieldValueTooLongError,
        )
        yield case(
            given='',                  # empty
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestIPv4Field(FieldTestMixin, unittest.TestCase):

    CLASS = IPv4Field

    def cases__clean_param_value(self):
        yield case(
            given='123.45.67.8',
            expected='123.45.67.8',
        )
        yield case(
            given='0.0.0.1',
            expected='0.0.0.1',
        )
        yield case(
            given='255.255.255.255',
            expected='255.255.255.255',
        )
        yield case(
            given='123.45.67.08',
            expected=FieldValueError,
        )
        yield case(
            given='123.045.67.8',
            expected=FieldValueError,
        )
        yield case(
            given=' 255.255.255.255',
            expected=FieldValueError
        )
        yield case(
            given='255.255.255.255 ',
            expected=FieldValueError
        )
        yield case(
            given='256.256.256.256',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.256',
            expected=FieldValueError
        )
        yield case(
            given='23.456.111.123',
            expected=FieldValueError
        )
        yield case(
            given='123.123.111.12.',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.ff',
            expected=FieldValueError
        )
        yield case(
            given='1.44.22.44',
            expected='1.44.22.44',
        )
        yield case(
            given='1.1.22.44',
            expected='1.1.22.44',
        )
        yield case(
            given='2.34.22.44',
            expected='2.34.22.44',
        )
        yield case(
            given='2.3U.22.44',
            expected=FieldValueError,
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given='1234',
            expected=FieldValueError,
        )
        yield case(
            given='192.168.56.1/20',
            expected=FieldValueError,
        )
        yield case(
            given='192.168.56. 1',
            expected=FieldValueError,
        )
        yield case(
            given='192 .168.56.1',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given=b'123.45.67.8',
            expected='123.45.67.8',
        )
        yield case(
            given='0.0.0.1',
            expected='0.0.0.1',
        )
        yield case(
            given=bytearray(b'255.255.255.255'),
            expected='255.255.255.255',
        )
        yield case(
            given='123.045.67.8',
            expected=FieldValueError,
        )
        yield case(
            given=b'0123.45.67.8',
            expected=FieldValueError,
        )
        yield case(
            given='123.45.67.08',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'0.0.00.0'),
            expected=FieldValueError,
        )
        yield case(
            given=' 255.255.255.255',
            expected=FieldValueError
        )
        yield case(
            given=b'255.255.255.255 ',
            expected=FieldValueError
        )
        yield case(
            given='256.256.256.256',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'1.2.3.256'),
            expected=FieldValueError
        )
        yield case(
            given='23.456.111.123',
            expected=FieldValueError
        )
        yield case(
            given=b'123.123.111.12.',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'1.2.3.ff'),
            expected=FieldValueError
        )
        yield case(
            given=b'1.44.22.44',
            expected='1.44.22.44',
        )
        yield case(
            given='1.1.22.44',
            expected='1.1.22.44',
        )
        yield case(
            given='2.34.22.44',
            expected='2.34.22.44',
        )
        yield case(
            given='2.3U.22.44',
            expected=FieldValueError,
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given='1234',
            expected=FieldValueError,
        )
        yield case(
            given='192.168.56.1/20',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'192.168.56. 1'),
            expected=FieldValueError,
        )
        yield case(
            given='192 .168.56.1',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestIPv6Field(FieldTestMixin, unittest.TestCase):

    CLASS = IPv6Field

    def cases__clean_param_value(self):
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='2001:db8:85a3:0:0:8a2e:370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='2001:0DB8:85A3:0000:0000:8A2E:0370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='2001:0db8:85a3::8a2e:370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='2001:0Db8:85A3::8a2e:370:7334',
            expected='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:0000:0000',
            expected='0000:0000:0000:0000:0000:0000:0000:0000',
        )
        yield case(
            given='::',
            expected='0000:0000:0000:0000:0000:0000:0000:0000',
        )
        yield case(
            given='::7f7f:7f7f',
            expected='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
        )
        yield case(
            given='::127.127.127.127',
            expected='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:127.127.127.127',
            expected='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
            expected='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
        )
        yield case(
            given='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff',
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff',
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF',
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff',
        )
        yield case(
            given='FFFF:FFFF:FFFF:0FFFF:FFFF:FFFF:FFFF:FFFF',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:ffff:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given=' 2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334 ',
            expected=FieldValueError
        )
        yield case(
            given=' 2001:db8:85a3::8a2e:370:7334',
            expected=FieldValueError
        )
        yield case(
            given='2001:db8:85a3::8a2e:370:7334 ',
            expected=FieldValueError
        )
        yield case(
            given='gggg:gggg:gggg:gggg:gggg:gggg:gggg:gggg',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:73345',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:bb85a3:0000:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3::0000:8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:::8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8::85a3:8a2e::7334:',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.127.',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.0127',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.07',
            expected=FieldValueError
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given='1234',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/64',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370: 7334',
            expected=FieldValueError,
        )
        yield case(
            given='2001 :0db8:85a3:0000:0000:8a2e:0370:7334',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3: :8a2e:0370: 7334',
            expected=FieldValueError,
        )
        yield case(
            given='123.45.67.8',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            expected='2001:db8:85a3::8a2e:370:7334',
        )
        yield case(
            given=bytearray(b'2001:db8:85a3:0:0:8a2e:370:7334'),
            expected='2001:db8:85a3::8a2e:370:7334',
        )
        yield case(
            given=b'2001:0DB8:85A3:0000:0000:8A2E:0370:7334',
            expected='2001:db8:85a3::8a2e:370:7334',
        )
        yield case(
            given='2001:0db8:85a3::8a2e:370:7334',
            expected='2001:db8:85a3::8a2e:370:7334',
        )
        yield case(
            given='2001:0Db8:85A3::8a2e:370:7334',
            expected='2001:db8:85a3::8a2e:370:7334',
        )
        yield case(
            given=b'0000:0000:0000:0000:0000:0000:0000:0000',
            expected='::',
        )
        yield case(
            given='::',
            expected='::',
        )
        yield case(
            given=bytearray(b'::7f7f:7f7f'),
            expected='::7f7f:7f7f',
        )
        yield case(
            given='::127.127.127.127',
            expected='::7f7f:7f7f',
        )
        yield case(
            given=b'0000:0000:0000:0000:0000:0000:127.127.127.127',
            expected='::7f7f:7f7f',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:7f7f:7f7f',
            expected='::7f7f:7f7f',
        )
        yield case(
            given=bytearray(b'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'),
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff',
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF',
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff',
        )
        yield case(
            given=b'FFFF:FFFF:FFFF:0FFFF:FFFF:FFFF:FFFF:FFFF',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:ffff:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'2001:00db8:85a3:8a2e:0370:7334'),
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given=b' 2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334 ',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b' 2001:db8:85a3::8a2e:370:7334'),
            expected=FieldValueError
        )
        yield case(
            given='2001:db8:85a3::8a2e:370:7334 ',
            expected=FieldValueError
        )
        yield case(
            given=b'gggg:gggg:gggg:gggg:gggg:gggg:gggg:gggg',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:73345',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'2001:0db8:bb85a3:0000:0000:8a2e:0370:7334'),
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given=b'2001:0db8:85a3::0000:8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:::8a2e:0370:7334:',
            expected=FieldValueError
        )
        yield case(
            given=b'2001:0db8::85a3:8a2e::7334:',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.127.',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.0127',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.07',
            expected=FieldValueError
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'1234'),
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/64',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'2001:0db8:85a3:0000:0000:8a2e:0370: 7334'),
            expected=FieldValueError,
        )
        yield case(
            given=b'2001 :0db8:85a3:0000:0000:8a2e:0370:7334',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'2001:0db8:85a3: :8a2e:0370: 7334'),
            expected=FieldValueError,
        )
        yield case(
            given='123.45.67.8',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestAnonymizedIPv4Field(FieldTestMixin, unittest.TestCase):

    CLASS = AnonymizedIPv4Field

    def cases__clean_param_value(self):
        yield case(
            given='x.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given='X.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given='X.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given='x.x.0.1',
            expected='x.x.0.1',
        )
        yield case(
            given='x.0.x.1',
            expected='x.0.x.1',
        )
        yield case(
            given='X.0.X.1',
            expected='x.0.x.1',
        )
        yield case(
            given='X.0.X.1',
            expected='x.0.x.1',
        )
        yield case(
            given='x.x.255.x',
            expected='x.x.255.x',
        )
        yield case(
            given='x.X.x.255',
            expected='x.x.x.255',
        )
        yield case(
            given='x.00.x.1',
            expected=FieldValueError,
        )
        yield case(
            given='X.0.X.01',
            expected=FieldValueError,
        )
        yield case(
            given='x.x.x.256',
            expected=FieldValueError,
        )
        yield case(
            given='x.x.x.-1',
            expected=FieldValueError,
        )
        yield case(
            given=' x.x.x.255',
            expected=FieldValueError,
        )
        yield case(
            given='x.x.x.255 ',
            expected=FieldValueError,
        )
        yield case(
            given='255.255.255.x',
            expected=FieldValueError
        )
        yield case(
            given='1.2.x.x',
            expected=FieldValueError
        )
        yield case(
            given='32.123.234.56',  # not anonymized
            expected=FieldValueError
        )
        yield case(
            given='x.456.111.123',
            expected=FieldValueError
        )
        yield case(
            given='x.123.x.12.',    # extra dot
            expected=FieldValueError
        )
        yield case(
            given='x.x.x.ff',
            expected=FieldValueError
        )
        yield case(
            given='x.x.x.x',
            expected='x.x.x.x'
        )
        yield case(
            given='X.X.X.X',
            expected='x.x.x.x'
        )
        yield case(
            given='x.X.x.X',
            expected='x.x.x.x'
        )
        yield case(
            given='X.X.x.x',
            expected='x.x.x.x'
        )
        yield case(
            given='x.x.x.x.x',
            expected=FieldValueError
        )
        yield case(
            given='x.44.22.33.55',
            expected=FieldValueError,
        )
        yield case(
            given='1.x.12.33',
            expected=FieldValueError,
        )
        yield case(
            given='x.12.33',
            expected=FieldValueError,
        )
        yield case(
            given='\u0120.66.22.44',
            expected=FieldValueError,
        )
        yield case(
            given='x.123.45.1/20',
            expected=FieldValueError,
        )
        yield case(
            given='169090601',
            expected=FieldValueError,
        )
        yield case(
            given='x.45.67.8.',
            expected=FieldValueError,
        )
        yield case(
            given='y.45.67.8',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='x.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given=b'x.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given='X.234.5.67',
            expected='x.234.5.67',
        )
        yield case(
            given=bytearray(b'X.234.5.67'),
            expected='x.234.5.67',
        )
        yield case(
            given='x.x.0.1',
            expected='x.x.0.1',
        )
        yield case(
            given=b'x.0.x.1',
            expected='x.0.x.1',
        )
        yield case(
            given='X.0.X.1',
            expected='x.0.x.1',
        )
        yield case(
            given=bytearray(b'X.0.X.1'),
            expected='x.0.x.1',
        )
        yield case(
            given='x.x.255.x',
            expected='x.x.255.x',
        )
        yield case(
            given=b'x.X.x.255',
            expected='x.x.x.255',
        )
        yield case(
            given='x.00.x.1',
            expected=FieldValueError,
        )
        yield case(
            given=b'x.0.x.01',
            expected=FieldValueError,
        )
        yield case(
            given='x.x.x.256',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'x.x.x.-1'),
            expected=FieldValueError,
        )
        yield case(
            given=' x.x.x.255',
            expected=FieldValueError,
        )
        yield case(
            given=b'x.x.x.255 ',
            expected=FieldValueError,
        )
        yield case(
            given='255.255.255.x',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'1.2.x.x'),
            expected=FieldValueError
        )
        yield case(
            given='32.123.234.56',  # not anonymized
            expected=FieldValueError
        )
        yield case(
            given=b'x.456.111.123',
            expected=FieldValueError
        )
        yield case(
            given='x.123.x.12.',    # extra dot
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'x.x.x.ff'),
            expected=FieldValueError
        )
        yield case(
            given='x.x.x.x',
            expected='x.x.x.x'
        )
        yield case(
            given=b'X.X.X.X',
            expected='x.x.x.x'
        )
        yield case(
            given='x.X.x.X',
            expected='x.x.x.x'
        )
        yield case(
            given=bytearray(b'X.X.x.x'),
            expected='x.x.x.x'
        )
        yield case(
            given='x.x.x.x.x',
            expected=FieldValueError
        )
        yield case(
            given=b'x.44.22.33.55',
            expected=FieldValueError,
        )
        yield case(
            given='1.x.12.33',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'x.12.33'),
            expected=FieldValueError,
        )
        yield case(
            given='\u0120.66.22.44',
            expected=FieldValueError,
        )
        yield case(
            given=b'x.123.45.1/20',
            expected=FieldValueError,
        )
        yield case(
            given='169090601',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'x.45.67.8.'),
            expected=FieldValueError,
        )
        yield case(
            given='y.45.67.8',
            expected=FieldValueError,
        )
        yield case(
            given=169090601,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestIPv4NetField(FieldTestMixin, unittest.TestCase):

    CLASS = IPv4NetField

    # XXX: shouldn't we change the behavior
    #      to trim the host (non-network) bits?

    def cases__clean_param_value(self):
        yield case(
            given='1.23.4.56/4',
            expected=('1.23.4.56', 4),
        )
        yield case(
            given='0.0.0.0/0',
            expected=('0.0.0.0', 0),
        )
        yield case(
            given='255.255.255.255/32',
            expected=('255.255.255.255', 32),
        )
        yield case(
            given='256.256.256.256/32',  # bad address
            expected=FieldValueError,
        )
        yield case(
            given='10.46.111.123/32',
            expected=('10.46.111.123', 32)
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='10.46.111.123',
            expected=('10.46.111.123', 32)
        )
        yield case(
            given='123.123.111.12/33',   # bad network
            expected=FieldValueError
        )
        yield case(
            given='255.255.255.255/33',  # bad network
            expected=FieldValueError,
        )
        yield case(
            given='10.166.77.88.99/4',   # bad address
            expected=FieldValueError,
        )
        yield case(
            given='10.166.88/4',         # bad address
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='10.166.88',           # bad address
            expected=FieldValueError,
        )
        yield case(
            given='1.2.3.4',             # no network
            expected=FieldValueError,
        )
        yield case(
            given='1.2.3.25 /12',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.25/ 12',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.25./12',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.0xff/22',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.07/22',             # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='1.2.3.07',                # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            given='0.0.0.0/00',              # leading 0 in network not allowed
            expected=FieldValueError,
        )
        yield case(
            given='255.255.255.255/00032',   # leading 0 in network not allowed
            expected=FieldValueError,
        )
        yield case(
            given='123/22',
            expected=FieldValueError,
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        # str/bytes/bytearray given
        yield case(
            given='1.23.4.56/4',
            expected='1.23.4.56/4',
        )
        yield case(
            given=b'1.23.4.56/4',
            expected='1.23.4.56/4',
        )
        yield case(
            given='0.0.0.0/0',
            expected='0.0.0.0/0',
        )
        yield case(
            given=bytearray(b'0.0.0.0/0'),
            expected='0.0.0.0/0',
        )
        yield case(
            given='255.255.255.255/32',
            expected='255.255.255.255/32',
        )
        yield case(
            given=b'255.255.255.255/32',
            expected='255.255.255.255/32',
        )
        yield case(
            given='256.256.256.256/32',  # bad address
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'10.46.111.123/32'),
            expected='10.46.111.123/32'
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='10.46.111.123',
            expected='10.46.111.123/32'
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given=b'10.46.111.123',
            expected='10.46.111.123/32'
        )
        yield case(
            given='123.123.111.12/33',    # bad network
            expected=FieldValueError
        )
        yield case(
            given=b'255.255.255.255/33',  # bad network
            expected=FieldValueError,
        )
        yield case(
            given='10.166.77.88.99/4',    # bad address
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'10.166.88/4'),  # bad address
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='10.166.77',            # bad address
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given=b'10.166.77',           # bad address
            expected=FieldValueError,
        )
        yield case(
            given='1.2.3.4',              # no network
            expected=FieldValueError,
        )
        yield case(
            given=b'1.2.3.4/',            # no network
            expected=FieldValueError,
        )
        yield case(
            given='1.23.4.56/4/5',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'1.2.3.25 /12'),
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.25/ 12',
            expected=FieldValueError
        )
        yield case(
            given=b'1.2.3.25./12',
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.0xff/22',
            expected=FieldValueError
        )
        yield case(
            given=b'1.2.3.07/22',        # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given='1.2.3.07',            # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            init_kwargs={'accept_bare_ip': True},
            given=b'1.2.3.07',           # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            given='1.2.3.7/022',         # leading 0 in network not allowed
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'1.2.3.07/022'),
            expected=FieldValueError
        )
        yield case(
            given='123/22',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'123/22'),
            expected=FieldValueError
        )
        yield case(
            given='123',
            expected=FieldValueError
        )
        yield case(
            given=b'123',
            expected=FieldValueError
        )
        yield case(
            given='',
            expected=FieldValueError
        )
        yield case(
            given=b'',
            expected=FieldValueError
        )
        # non-str/bytes/bytearray iterable given
        yield case(
            given=('1.23.4.56', 4),
            expected='1.23.4.56/4',
        )
        yield case(
            given=['1.23.4.56', '4'],
            expected='1.23.4.56/4',
        )
        yield case(
            given=('1.2.3.7', 22),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(b'1.2.3.7', 22),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(bytearray(b'1.2.3.7'), 22),
            expected='1.2.3.7/22'
        )
        yield case(
            given=('1.2.3.7', '22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(b'1.2.3.7', '22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(bytearray(b'1.2.3.7'), '22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=('1.2.3.7', b'22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(b'1.2.3.7', b'22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(bytearray(b'1.2.3.7'), b'22'),
            expected='1.2.3.7/22'
        )
        yield case(
            given=('1.2.3.7', bytearray(b'22')),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(b'1.2.3.7', bytearray(b'22')),
            expected='1.2.3.7/22'
        )
        yield case(
            given=(bytearray(b'1.2.3.7'), bytearray(b'22')),
            expected='1.2.3.7/22'
        )
        yield case(
            given=('0.0.0.0', 0),
            expected='0.0.0.0/0',
        )
        yield case(
            given=('0.0.0.0', '0'),
            expected='0.0.0.0/0',
        )
        yield case(
            given=['255.255.255.255', 32],
            expected='255.255.255.255/32',
        )
        yield case(
            given=('255.255.255.255', '32'),
            expected='255.255.255.255/32',
        )
        yield case(
            given=('256.256.256.256', 32),    # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('10.46.111.123', '32'),
            expected='10.46.111.123/32'
        )
        yield case(
            given=('123.123.111.12', '33'),   # bad network
            expected=FieldValueError
        )
        yield case(
            given=('255.255.255.255', 33),    # bad network
            expected=FieldValueError,
        )
        yield case(
            given=('10.166.77.88.99', 4),     # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('10.166.88', 4),           # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('1.2.3.25',),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.25', 12, 13),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.25 ', 12),
            expected=FieldValueError
        )
        yield case(
            given=(' 1.2.3.25', 12),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.25.', 12),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.0xff', 22),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.07', 22),    # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.07', '22'),   # leading 0 in ip not allowed
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.7', '022'),   # leading 0 in network not allowed
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.07', '022'),
            expected=FieldValueError
        )
        yield case(
            given=('123', 22),
            expected=FieldValueError
        )
        yield case(
            given=('123', '22'),
            expected=FieldValueError
        )
        yield case(
            given=('', 22),
            expected=FieldValueError
        )
        yield case(
            given=('1.2.3.4', ''),
            expected=FieldValueError
        )
        yield case(
            given=(123, 22),
            expected=FieldValueError
        )
        yield case(
            given=(123, '22'),
            expected=FieldValueError
        )
        yield case(
            given=123,
            expected=FieldValueError,
        )
        yield case(
            given=None,
            expected=FieldValueError,
        )


class TestIPv6NetField(FieldTestMixin, unittest.TestCase):

    CLASS = IPv6NetField

    # XXX: shouldn't we change the behavior
    #      to trim the host (non-network) bits?

    def cases__clean_param_value(self):
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='2001:0db8:85a3:00:00:8a2e:370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='2001:db8:85a3:0:0:8a2e:370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='2001:0DB8:85A3:0000:0000:8A2E:0370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='2001:0db8:85a3::8a2e:370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='2001:0Db8:85A3::8a2e:370:7334/64',
            expected=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:0000:0000/0',
            expected=('0000:0000:0000:0000:0000:0000:0000:0000', 0),
        )
        yield case(
            given='::/0',
            expected=('0000:0000:0000:0000:0000:0000:0000:0000', 0),
        )
        yield case(
            given='::7f7f:7f7f/16',
            expected=('0000:0000:0000:0000:0000:0000:7f7f:7f7f', 16),
        )
        yield case(
            given='::127.127.127.127/16',
            expected=('0000:0000:0000:0000:0000:0000:7f7f:7f7f', 16),
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:127.127.127.127/16',
            expected=('0000:0000:0000:0000:0000:0000:7f7f:7f7f', 16),
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:7f7f:7f7f/16',
            expected=('0000:0000:0000:0000:0000:0000:7f7f:7f7f', 16),
        )
        yield case(
            given='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
            expected=('ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff', 128),
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF/128',
            expected=('ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff', 128),
        )
        yield case(
            given='FFFF:FFFF:FFFF:0FFFF:FFFF:FFFF:FFFF:FFFF/128',
            expected=FieldValueError,
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF/0128',
            expected=FieldValueError,
        )
        yield case(
            given='gggg:gggg:gggg:gggg:gggg:gggg:gggg:gggg/128',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/129',  # bad network
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/f0',    # bad network
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:ffff:0000:8a2e:0370:7334/64',  # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:8a2e:0370:7334/64',         # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:::8a2e:0370:7334/64',            # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001::0db8:85a3::8a2e:0370:7334/64',            # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334',       # no network
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/',      # no network
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/64/65',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334 /12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/ 12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:/12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:012',
            expected=FieldValueError
        )
        yield case(
            given='123.45.67.8/12',
            expected=FieldValueError,
        )
        yield case(
            given='123/12',
            expected=FieldValueError
        )
        yield case(
            given='123',
            expected=FieldValueError
        )
        yield case(
            given='',
            expected=FieldValueError
        )

    def cases__clean_result_value(self):
        # str/bytes/bytearray given
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/64',
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=b'2001:0db8:85a3:0000:0000:8a2e:0370:7334/64',
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given='2001:db8:85a3:0:0:8a2e:370:7334/64',
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=bytearray(b'2001:0DB8:85A3:0000:0000:8A2E:0370:7334/64'),
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given='2001:0db8:85a3::8a2e:370:7334/64',
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=b'2001:0Db8:85A3::8a2e:370:7334/64',
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:0000:0000/0',
            expected='::/0',
        )
        yield case(
            given=bytearray(b'::/0'),
            expected='::/0',
        )
        yield case(
            given=b'::7f7f:7f7f/16',
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given='::127.127.127.127/16',
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=bytearray(b'0000:0000:0000:0000:0000:0000:127.127.127.127/16'),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given='0000:0000:0000:0000:0000:0000:7f7f:7f7f/16',
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=b'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF/128',
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
        )
        yield case(
            given=bytearray(b'FFFF:FFFF:FFFF:0FFFF:FFFF:FFFF:FFFF:FFFF/128'),
            expected=FieldValueError,
        )
        yield case(
            given='FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF/0128',
            expected=FieldValueError,
        )
        yield case(
            given=b'gggg:gggg:gggg:gggg:gggg:gggg:gggg:gggg/128',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.127./16',
            expected=FieldValueError
        )
        yield case(
            given=b'::127.127.127.0127/16',
            expected=FieldValueError
        )
        yield case(
            given='::127.127.127.07/16',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/129',   # bad network
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'2001:0db8:85a3:0000:0000:8a2e:0370:7334/f0'),    # bad network
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:ffff:0000:8a2e:0370:7334/64',  # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:8a2e:0370:7334/64',         # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:::8a2e:0370:7334/64',            # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001::0db8:85a3::8a2e:0370:7334/64',            # bad address
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334',       # no network
            expected=FieldValueError,
        )
        yield case(
            given=b'2001:0db8:85a3:0000:0000:8a2e:0370:7334/64/65',
            expected=FieldValueError,
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334 /12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334/ 12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:/12',
            expected=FieldValueError
        )
        yield case(
            given='2001:0db8:85a3:0000:0000:8a2e:0370:7334:012',
            expected=FieldValueError
        )
        yield case(
            given=b'123.45.67.8/12',
            expected=FieldValueError,
        )
        yield case(
            given='123/12',
            expected=FieldValueError
        )
        yield case(
            given=bytearray(b'123/12'),
            expected=FieldValueError
        )
        yield case(
            given='123',
            expected=FieldValueError
        )
        yield case(
            given=b'123',
            expected=FieldValueError
        )
        yield case(
            given='',
            expected=FieldValueError
        )
        yield case(
            given=b'',
            expected=FieldValueError
        )
        # non-str/bytes/bytearray iterable given
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', '64'),
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=('2001:db8:85a3:0:0:8a2e:370:7334', 64),
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=['2001:0DB8:85A3:0000:0000:8A2E:0370:7334', '64'],
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=['2001:0db8:85a3::8a2e:370:7334', 64],
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=['2001:0Db8:85A3::8a2e:370:7334', '64'],
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=('0000:0000:0000:0000:0000:0000:0000:0000', 0),
            expected='::/0',
        )
        yield case(
            given=('::', 0),
            expected='::/0',
        )
        yield case(
            given=(b'::', 0),
            expected='::/0',
        )
        yield case(
            given=(bytearray(b'::'), 0),
            expected='::/0',
        )
        yield case(
            given=('::', '0'),
            expected='::/0',
        )
        yield case(
            given=(b'::', '0'),
            expected='::/0',
        )
        yield case(
            given=(bytearray(b'::'), '0'),
            expected='::/0',
        )
        yield case(
            given=('::', b'0'),
            expected='::/0',
        )
        yield case(
            given=(b'::', b'0'),
            expected='::/0',
        )
        yield case(
            given=(bytearray(b'::'), b'0'),
            expected='::/0',
        )
        yield case(
            given=('::', bytearray(b'0')),
            expected='::/0',
        )
        yield case(
            given=(b'::', bytearray(b'0')),
            expected='::/0',
        )
        yield case(
            given=(bytearray(b'::'), bytearray(b'0')),
            expected='::/0',
        )
        yield case(
            given=('::7f7f:7f7f', 16),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=('::127.127.127.127', 16),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=('::127.127.127.127', '16'),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=('0000:0000:0000:0000:0000:0000:127.127.127.127', 16),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=('0000:0000:0000:0000:0000:0000:7f7f:7f7f', 16),
            expected='::7f7f:7f7f/16',
        )
        yield case(
            given=('ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff', 128),
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
        )
        yield case(
            given=('FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF:FFFF', 128),
            expected='ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128',
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
            expected='2001:db8:85a3::8a2e:370:7334/64',
        )
        yield case(
            given=('2001:0db8:85a3:00000:0000:08a2e:0370:7334', 64),
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:00000:0000:8a2e:0370:7334', 64),
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:00000:0000:8a2e:0370:7334', '064'),
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:08a2e:0370:7334', '064'),
            expected=FieldValueError,
        )
        yield case(
            given=('gggg:gggg:gggg:gggg:gggg:gggg:gggg:gggg', 128),
            expected=FieldValueError
        )
        yield case(
            given=('::127.127.127.127.', 16),
            expected=FieldValueError
        )
        yield case(
            given=('::127.127.127.0127', '16'),
            expected=FieldValueError
        )
        yield case(
            given=('::127.127.127.07', 16),
            expected=FieldValueError
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 129),  # bad network
            expected=FieldValueError
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 'f0'),
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:ffff:0000:8a2e:0370:7334', 64),  # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:8a2e:0370:7334', 64),         # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:::8a2e:0370:7334', 64),           # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('2001::0db8:85a3::8a2e:0370:7334', 64),            # bad address
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334',),      # no network
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64, 65),
            expected=FieldValueError,
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334/64', 65),
            expected=FieldValueError,
        )
        yield case(
            given=(' 2001:0db8:85a3:0000:0000:8a2e:0370:7334', 64),
            expected=FieldValueError
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334 ', 64),
            expected=FieldValueError
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334:', 64),
            expected=FieldValueError
        )
        yield case(
            given=('123.45.67.8', 12),
            expected=FieldValueError,
        )
        yield case(
            given=('', 64),
            expected=FieldValueError
        )
        yield case(
            given=('2001:0db8:85a3:0000:0000:8a2e:0370:7334', ''),
            expected=FieldValueError
        )
        yield case(
            given=(123, 64),
            expected=FieldValueError
        )
        yield case(
            given=(123, '64'),
            expected=FieldValueError
        )
        yield case(
            given=('123', 64),
            expected=FieldValueError
        )
        yield case(
            given=('123', '64'),
            expected=FieldValueError
        )
        yield case(
            given=123,
            expected=FieldValueError,
        )
        yield case(
            given=None,
            expected=FieldValueError,
        )


class TestCCField(FieldTestMixin, unittest.TestCase):

    CLASS = CCField

    def cases__clean_param_value(self):
        yield case(
            given='PL',
            expected='PL',
        )
        yield case(
            given='PL',
            expected='PL',
        )
        yield case(
            given='pl',
            expected='PL',
        )
        yield case(
            given='pL',
            expected='PL',
        )
        yield case(
            given='PRL',
            expected=FieldValueError,
        )
        yield case(
            given='PRL',
            expected=FieldValueError,
        )
        yield case(
            given='P1',
            expected='P1',  # ok
        )
        yield case(
            given='1P',
            expected=FieldValueError,
        )
        yield case(
            given='PL0',
            expected=FieldValueError,
        )
        yield case(
            given='1.23.4.56/4',
            expected=FieldValueError,
        )
        yield case(
            given='123',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='PL',
            expected='PL',
        )
        yield case(
            given=b'PL',
            expected='PL',
        )
        yield case(
            given='pl',
            expected='PL',
        )
        yield case(
            given=bytearray(b'pL'),
            expected='PL',
        )
        yield case(
            given='PRL',
            expected=FieldValueError,
        )
        yield case(
            given=b'PRL',
            expected=FieldValueError,
        )
        yield case(
            given='P1',
            expected='P1',  # ok
        )
        yield case(
            given=bytearray(b'P1'),
            expected='P1',  # ok
        )
        yield case(
            given='1P',
            expected=FieldValueError,
        )
        yield case(
            given=b'PL0',
            expected=FieldValueError,
        )
        yield case(
            given='1.23.4.56/4',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'123'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestURLField(FieldTestMixin, unittest.TestCase):

    CLASS = URLField

    def cases__clean_param_value(self):
        yield case(
            given='http://www.test.pl',
            expected='http://www.test.pl',
        )
        yield case(
            given='http://www.test.pl/cgi-bin/foo.pl',
            expected='http://www.test.pl/cgi-bin/foo.pl',
        )
        yield case(
            given='http://www.test.pl/cgi/bin/foo.pl?debug=1&id=123',
            expected='http://www.test.pl/cgi/bin/foo.pl?debug=1&id=123',
        )
        yield case(
            given=('http://www.TEST.pl/cgi-bin/bar.pl?mode=browse&amp;'
                   'debug=%20123&amp;id=k-%5D'),
            expected=('http://www.TEST.pl/cgi-bin/bar.pl?mode=browse&amp;'
                      'debug=%20123&amp;id=k-%5D'),
        )
        yield case(
            given='http://tęst.pl\udcdd',
            expected='http://t\u0119st.pl\udcdd',
        )
        yield case(
            given='http://test.pl',
            expected='http://test.pl',
        )
        yield case(
            given=('http://example.net/search.php?q=разные+авторы\r\n'),
            expected=('http://example.net/search.php?q=разные+авторы\r\n'),
        )
        yield case(
            given='http://example.net/search.php?\t',
            expected='http://example.net/search.php?\t',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            given='https://' + 'x.pl'*1000,  # too long
            expected=FieldValueTooLongError,
        )
        yield case(
            given='https://' + 'x'*2040,     # len 2048
            expected='https://' + 'x'*2040,
        )
        yield case(
            given='https://x' + 'x'*2040,    # too long (2049)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='https://dd\udcdd\udcee',
            expected='https://dd\udcdd\udcee',
        )

    def cases__clean_result_value(self):
        yield case(
            given='http://www.test.pl',
            expected='http://www.test.pl',
        )
        yield case(
            given=b'http://www.test.pl/cgi-bin/foo.pl',
            expected='http://www.test.pl/cgi-bin/foo.pl',
        )
        yield case(
            given='http://www.test.pl/cgi/bin/foo.pl?debug=1&id=123',
            expected='http://www.test.pl/cgi/bin/foo.pl?debug=1&id=123',
        )
        yield case(
            given=bytearray(b'http://www.TEST.pl/cgi-bin/bar.pl?mode='
                            b'browse&amp;debug=%20123&amp;id=k-%5D'),
            expected=('http://www.TEST.pl/cgi-bin/bar.pl?mode=browse&amp;'
                      'debug=%20123&amp;id=k-%5D'),
        )
        yield case(
            given=b'http://t\xc4\x99st.pl\xdd',
            expected='http://t\u0119st.pl\udcdd',
        )
        yield case(
            given='http://tęst.pl\udcdd',
            expected='http://t\u0119st.pl\udcdd',
        )
        yield case(
            given=b'http://test.pl',
            expected='http://test.pl',
        )
        yield case(
            given=('http://example.net/search.php?q=разные+авторы\r\n'),
            expected=('http://example.net/search.php?q=разные+авторы\r\n'),
        )
        yield case(
            given=('http://example.net/search.php?q=разные+авторы\r\n'.encode('utf-8')),
            expected=('http://example.net/search.php?q=разные+авторы\r\n'),
        )
        yield case(
            given='http://example.net/search.php?\t',
            expected='http://example.net/search.php?\t',
        )
        yield case(
            given=b'',
            expected='',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            given=bytearray(b'https://' + b'x.pl'*1000),  # too long
            expected=FieldValueTooLongError,
        )
        yield case(
            given='https://' + 'x.pl'*1000,  # too long
            expected=FieldValueTooLongError,
        )
        yield case(
            given=b'https://' + b'x'*2040,     # len 2048
            expected='https://' + 'x'*2040,
        )
        yield case(
            given=b'https://x' + b'x'*2040,    # too long (2049)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='https://' + 'x'*2040,     # len 2048
            expected='https://' + 'x'*2040,
        )
        yield case(
            given='https://x' + 'x'*2040,    # too long (2049)
            expected=FieldValueTooLongError,
        )
        yield case(
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected='https://\udcdc\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'utf8_surrogatepass_and_surrogateescape'},
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected='https://\udcdc\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'ignore'},
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected = 'https://dd',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'ignore'},
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected = 'https://dd',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'ignore'},
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected = 'https://',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'strict'},
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'strict'},
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'strict'},
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogateescape'},
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogateescape'},
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected='https://dd\udced\udcb3\udc9d\udced\udcb3\udcae',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogateescape'},
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected='https://\udcdc\udced\udcb3\udc9d\udced\udcb3\udcae',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=b'https://dd\xdd\xee',                    # non-UTF-8
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=b'https://dd\xed\xb3\x9d\xed\xb3\xae',    # quasi-UTF-8 with lone surrogates
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            init_kwargs={'decode_error_handling': 'surrogatepass'},
            given=b'https://\xdc\xed\xb3\x9d\xed\xb3\xae',  # mixed
            expected=FieldValueError,
        )
        weird_string = (
            '\udcdd\udced\udced\udcb2'  # mess converted to surrogates
            '\udcb1'        # surrogate '\udcb1'
            '\udced\udcb2'  # mess converted to surrogates
            '\udced'        # mess converted to surrogate
            'B'             # proper code point (ascii 'B')
            '\ud7ff'        # proper code point '\ud7ff' (smaller than smallest surr.)
            '\udced\udca0'  # mess converted to surrogates
            '\x7f'          # proper code point (ascii DEL)
            '\ud800'        # surrogate '\ud800' (smallest one)
            '\udfff'        # surrogate '\udfff' (biggest one) [note: *not* merged with one above]
            '\udcee\udcbf\udcc0'  # mess converted to surrogates
            '\ue000'        # proper code point '\ue000' (bigger than biggest surr.)
            '\udce6'        # mess converted to surrogate
            '\udced'        # mess converted to surrogate
            '\udced\udcb3'  # mess converted to surrogates
            '\udce6'        # surrogate '\udce6'
            '\udc80'        # mess converted to surrogate
            '#'             # proper code point (ascii '#')
            '\udcf0'        # mess converted to surrogate
            '\udcf0\udc90'  # mess converted to surrogates
            '\udcf0\udc90\udc8f'  # mess converted to surrogates
            '\U000103ff'    # proper code point '\U000103ff' (non-BMP one)
            '\udcf0\udc90\udc8f'  # mess converted to surrogates
            ' '             # proper code point (ascii ' ')
            '\udced\udcb3')  # mess converted to surrogates
        yield case(
            given=(
                b'\xdd\xed\xed\xb2'  # mess
                b'\xed\xb2\xb1'  # encoded surrogate '\udcb1'
                b'\xed\xb2'      # mess
                b'\xed'          # mess
                b'B'             # encoded proper code point (ascii 'B')
                b'\xed\x9f\xbf'  # encoded proper code point '\ud7ff' (smaller than smallest surr.)
                b'\xed\xa0'      # mess
                b'\x7f'          # encoded proper code point (ascii DEL)
                b'\xed\xa0\x80'  # encoded surrogate '\ud800' (smallest one)
                b'\xed\xbf\xbf'  # encoded surrogate '\udfff' (biggest one)
                b'\xee\xbf\xc0'  # mess
                b'\xee\x80\x80'  # encoded proper code point '\ue000' (bigger than biggest surr.)
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
                b'\xed\xb3'),    # mess (starts like a proper surrogate but is too short)
            expected=weird_string,
        )
        yield case(
            given='https://dd\udcdd\udcee',
            expected='https://dd\udcdd\udcee',
        )
        yield case(
            given=weird_string,
            expected=weird_string,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestURLSubstringField(TestURLField):

    CLASS = URLSubstringField


class TestDomainNameSubstringField(FieldTestMixin, unittest.TestCase):

    CLASS = DomainNameSubstringField

    def cases__clean_param_value(self):
        yield case(
            given='test.pl',
            expected='test.pl',
        )
        yield case(
            given='-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given='abcx' + '.m' * 126,  # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='yyy' + '.x' * 126,   # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given='abc.' + 'm' * 64,    # single label too long
            expected=FieldValueError,
        )
        yield case(
            given='abc.' + 'm' * 63,     # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given='Test.fałszyWa.DOmena.example.com',
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='mMm.WWW.pl',
            expected='mmm.www.pl',
        )
        yield case(
            given='qQq. pl. . .',
            expected='qqq. pl. . .',
        )
        yield case(
            given='life_does_not_work_according_to.rfc',
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            given='!@#$%^&*()+=[]',
            expected='!@#$%^&*()+=[]',
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl',
            expected='xn--!@#$%^&*()+=[]-owb6a.pl',
        )

    def cases__clean_result_value(self):
        yield case(
            given='test.pl',
            expected='test.pl',
        )
        yield case(
            given=b'test.pl',
            expected='test.pl',
        )
        yield case(
            given=bytearray(b'test.pl'),
            expected='test.pl',
        )
        yield case(
            given='-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given=b'-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given='abcx' + '.m' * 126,    # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given=b'abcx' + b'.m' * 126,   # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='yyy' + '.x' * 126,      # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given=bytearray(b'yyy' + b'.x' * 126),     # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given='abc.' + 'm' * 64,       # single label too long
            expected=FieldValueError,
        )
        yield case(
            given=b'abc.' + b'm' * 64,     # single label too long
            expected=FieldValueError,
        )
        yield case(
            given='abc.' + 'm' * 63,       # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given=b'abc.' + b'm' * 63,     # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given='Test.fałszyWa.DOmena.example.com',
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='test.fałszywa.domena.example.com'.encode('utf-8'),
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given=bytearray('Test.fałszyWa.DOmena.example.com'.encode('utf-8')),
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='mMm.WWW.pl',
            expected='mmm.www.pl',
        )
        yield case(
            given=b'qQq. pl. . .',
            expected='qqq. pl. . .',
        )
        yield case(
            given='life_does_not_work_according_to.rfc',
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given=bytearray(b'life_does_not_work_according_to.rfc'),
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given='',
            expected='',
        )
        yield case(
            given=b'',
            expected='',
        )
        yield case(
            given='!@#$%^&*()+=[]',
            expected='!@#$%^&*()+=[]',
        )
        yield case(
            given=bytearray(b'!@#$%^&*()+=[]'),
            expected='!@#$%^&*()+=[]',
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl',
            expected='xn--!@#$%^&*()+=[]-owb6a.pl',
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl'.encode('utf-8'),
            expected='xn--!@#$%^&*()+=[]-owb6a.pl',
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestDomainNameField(FieldTestMixin, unittest.TestCase):

    CLASS = DomainNameField

    def cases__clean_param_value(self):
        yield case(
            given='test.pl',
            expected='test.pl',
        )
        yield case(
            given='-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given='abcx' + '.m' * 126,  # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='yyy' + '.x' * 126,   # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given='abc.' + 'm' * 63,     # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given='abc.' + 'm' * 64,    # single label too long
            expected=FieldValueError,
        )
        yield case(
            given='Test.fałszyWa.DOmena.example.com',
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='mMm.WWW.pl',
            expected='mmm.www.pl',
        )
        yield case(
            given='qQq. pl. . .',
            expected=FieldValueError,
        )
        yield case(
            given='life_does_not_work_according_to.rfc',
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given='192.168.0.1.foo',
            expected='192.168.0.1.foo',
        )
        yield case(
            given='something.example.f123',
            expected='something.example.f123',
        )
        yield case(
            given='192.168.0.1',             # TLD cannot consist of digits only
            expected=FieldValueError,
        )
        yield case(
            given='something.example.123',  # TLD cannot consist of digits only
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='!@#$%^&*()+=[]ąć',
            expected=FieldValueError,
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='test.pl',
            expected='test.pl',
        )
        yield case(
            given=b'test.pl',
            expected='test.pl',
        )
        yield case(
            given=bytearray(b'test.pl'),
            expected='test.pl',
        )
        yield case(
            given='-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given=b'-te--st-.p-l',
            expected='-te--st-.p-l',
        )
        yield case(
            given='abcx' + '.m' * 126,      # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given=bytearray(b'abcx' + b'.m' * 126),    # too long (>255)
            expected=FieldValueTooLongError,
        )
        yield case(
            given='yyy' + '.x' * 126,       # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given=b'yyy' + b'.x' * 126,     # ok, len 255
            expected='yyy' + '.x' * 126,
        )
        yield case(
            given='abc.' + 'm' * 63,        # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given=bytearray(b'abc.' + b'm' * 63),     # ok, single label len 63
            expected='abc.' + 'm' * 63,
        )
        yield case(
            given='abc.' + 'm' * 64,        # single label too long
            expected=FieldValueError,
        )
        yield case(
            given=b'abc.' + b'm' * 64,      # single label too long
            expected=FieldValueError,
        )
        yield case(
            given='Test.fałszyWa.DOmena.example.com',
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='test.fałszywa.domena.example.com'.encode('utf-8'),
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given=bytearray('Test.fałszyWa.DOmena.example.com'.encode('utf-8')),
            expected='test.xn--faszywa-ojb.domena.example.com',
        )
        yield case(
            given='mMm.WWW.pl',
            expected='mmm.www.pl',
        )
        yield case(
            given=b'qQq. pl. . .',
            expected=FieldValueError,
        )
        yield case(
            given='life_does_not_work_according_to.rfc',
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given=b'life_does_not_work_according_to.rfc',
            expected='life_does_not_work_according_to.rfc',
        )
        yield case(
            given='something.example.f123',
            expected='something.example.f123',
        )
        yield case(
            given=bytearray(b'192.168.0.1.foo'),
            expected='192.168.0.1.foo',
        )
        yield case(
            given='something.example.123',   # TLD cannot consist of digits only
            expected=FieldValueError,
        )
        yield case(
            given=b'192.168.0.1',            # TLD cannot consist of digits only
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given='!@#$%^&*()+=[]ąć',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'!@#$%^&*()+=[]'),
            expected=FieldValueError,
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl',
            expected=FieldValueError,
        )
        yield case(
            given='!@#$%^&*()+=[]ąć.pl'.encode('utf-8'),
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


# TODO: improve test cases
# (especially add some without min/max limits)
class TestIntegerField(FieldTestMixin, unittest.TestCase):

    CLASS = IntegerField

    def cases__clean_param_value(self):
        init_kwargs = {
            'min_value': 10,
            'max_value': 123,
        }
        yield case(
            init_kwargs=init_kwargs,
            given='11',
            expected=11,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='10',
            expected=10,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='9',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='09',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='123',
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='124',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-2',
            expected=-2,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-02',
            expected=-2,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-3',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-03',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='0x1',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': 10,
                         'max_value': 123000000000000000000000},
            given='123000000000000000000000',
            expected=123000000000000000000000,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='123.0',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='0-1',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='1.5',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        init_kwargs = {
            'min_value': 10,
            'max_value': 123,
        }
        yield case(
            init_kwargs=init_kwargs,
            given='11',
            expected=11,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'11',
            expected=11,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=bytearray(b'10'),
            expected=10,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='10',
            expected=10,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'9',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=bytearray(b'09'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='09',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='123',
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'123',
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='124',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'124',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-2',
            expected=-2,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given=bytearray(b'-02'),
            expected=-2,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='-3',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given=b'-03',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given='0x1',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': 10,
                         'max_value': 123000000000000000000000},
            given=bytearray(b'123000000000000000000000'),
            expected=123000000000000000000000,
        )
        yield case(
            init_kwargs={'min_value': 10,
                         'max_value': 123000000000000000000000},
            given='123000000000000000000000',
            expected=123000000000000000000000,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'123.0',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='123.0',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=bytearray(b'0-1'),
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given='1.5',
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=11,
            expected=11,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=10,
            expected=10,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=9,
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=123,
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=124,
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given=-2,
            expected=-2,
        )
        yield case(
            init_kwargs={'min_value': -2,
                         'max_value': 123,
                         'error_msg_template': '"{}" is not valid'},
            given=-3,
            expected=FieldValueError,
        )
        yield case(
            init_kwargs={'min_value': 10,
                         'max_value': 123000000000000000000000},
            given=123000000000000000000000,
            expected=123000000000000000000000,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=123,
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=123.0,
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=decimal.Decimal(123),
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=decimal.Decimal('123.0'),
            expected=123,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=123.1,
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=decimal.Decimal('123.1'),
            expected=FieldValueError,
        )
        yield case(
            given=None,
            expected=FieldValueError,
        )
        yield case(
            init_kwargs=init_kwargs,
            given=None,
            expected=FieldValueError,
        )


class TestASNField(FieldTestMixin, unittest.TestCase):

    CLASS = ASNField

    def cases__clean_param_value(self):
        yield case(
            given='0',
            expected=0,
        )
        yield case(
            given='0.0',
            expected=0,
        )
        yield case(
            given='1',
            expected=1,
        )
        yield case(
            given='0.1',
            expected=1,
        )
        yield case(
            given='1234',
            expected=1234,
        )
        yield case(
            given='0.1234',
            expected=1234,
        )
        yield case(
            given='AS1234',
            expected=1234,
        )
        yield case(
            given='AS 0.1234',
            expected=1234,
        )
        yield case(
            given='Asn  \t  0.1234',
            expected=1234,
        )
        yield case(
            given='asn1234',
            expected=1234,
        )
        yield case(
            given='65535',
            expected=65535,
        )
        yield case(
            given='0.65535',
            expected=65535,
        )
        yield case(
            given='0.65536',
            expected=FieldValueError,
        )
        yield case(
            given='42.65536',
            expected=FieldValueError,
        )
        yield case(
            given='65536',
            expected=65536,
        )
        yield case(
            given='1.0',
            expected=65536,
        )
        yield case(
            given='65537',
            expected=65537,
        )
        yield case(
            given='1.1',
            expected=65537,
        )
        yield case(
            given='-1',
            expected=FieldValueError,
        )
        yield case(
            given='0.-1',
            expected=FieldValueError,
        )
        yield case(
            given='-1.0',
            expected=FieldValueError,
        )
        yield case(
            given='65535.0',
            expected=0xffff << 16,
        )
        yield case(
            given='65535.1',
            expected=(0xffff << 16) + 1,
        )
        yield case(
            given='4294967295',   # max
            expected=4294967295,
        )
        yield case(
            given='65535.65535',  # max
            expected=4294967295,
        )
        yield case(
            given='4294967296',   # max + 1
            expected=FieldValueError,
        )
        yield case(
            given='65536.0',
            expected=FieldValueError,
        )
        yield case(
            given='65536.1',
            expected=FieldValueError,
        )
        yield case(
            given='65536.65536',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='\x01',
            expected=FieldValueError,
        )
        yield case(
            given='\x00',
            expected=FieldValueError,
        )
        yield case(
            given='asdf',
            expected=FieldValueError,
        )
        yield case(
            given='0.0.0',
            expected=FieldValueError,
        )
        yield case(
            given='0x1.0xf',
            expected=FieldValueError,
        )
        yield case(
            given='0xFF',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='0',
            expected=0,
        )
        yield case(
            given=b'0',
            expected=0,
        )
        yield case(
            given=bytearray(b'0'),
            expected=0,
        )
        yield case(
            given='0.0',
            expected=0,
        )
        yield case(
            given=b'0.0',
            expected=0,
        )
        yield case(
            given='1',
            expected=1,
        )
        yield case(
            given=bytearray(b'1'),
            expected=1,
        )
        yield case(
            given='0.1',
            expected=1,
        )
        yield case(
            given=b'0.1',
            expected=1,
        )
        yield case(
            given='0.1234',
            expected=1234,
        )
        yield case(
            given=bytearray(b'1234'),
            expected=1234,
        )
        yield case(
            given='AS1234',
            expected=1234,
        )
        yield case(
            given=b'AS 0.1234',
            expected=1234,
        )
        yield case(
            given='asn  \t  0.1234',
            expected=1234,
        )
        yield case(
            given=bytearray(b'Asn\n\r\n0.1234'),
            expected=1234,
        )
        yield case(
            given='asn1234',
            expected=1234,
        )
        yield case(
            given=b'65535',
            expected=65535,
        )
        yield case(
            given='65535',
            expected=65535,
        )
        yield case(
            given=bytearray(b'0.65535'),
            expected=65535,
        )
        yield case(
            given='0.65535',
            expected=65535,
        )
        yield case(
            given=b'0.65536',
            expected=FieldValueError,
        )
        yield case(
            given='0.65536',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'42.65536'),
            expected=FieldValueError,
        )
        yield case(
            given='42.65536',
            expected=FieldValueError,
        )
        yield case(
            given=b'65536',
            expected=65536,
        )
        yield case(
            given='65536',
            expected=65536,
        )
        yield case(
            given=bytearray(b'1.0'),
            expected=65536,
        )
        yield case(
            given='65537',
            expected=65537,
        )
        yield case(
            given=b'1.1',
            expected=65537,
        )
        yield case(
            given='-0',   # XXX: should it be allowed?
            expected=0,
        )
        yield case(
            given=bytearray(b'-1'),
            expected=FieldValueError,
        )
        yield case(
            given='0.-1',
            expected=FieldValueError,
        )
        yield case(
            given=b'-1.0',
            expected=FieldValueError,
        )
        yield case(
            given='65535.0',
            expected=0xffff << 16,
        )
        yield case(
            given=bytearray(b'65535.1'),
            expected=(0xffff << 16) + 1,
        )
        yield case(
            given='65534.65535',
            expected=(0xffff << 16) - 1,
        )
        yield case(
            given=b'4294967295',   # max
            expected=4294967295,
        )
        yield case(
            given='4294967295',    # max
            expected=4294967295,
        )
        yield case(
            given=bytearray(b'65535.65535'),   # max
            expected=4294967295,
        )
        yield case(
            given='65535.65535',   # max
            expected=4294967295,
        )
        yield case(
            given=b'4294967296',   # max + 1
            expected=FieldValueError,
        )
        yield case(
            given='4294967296',    # max + 1
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'65536.0'),
            expected=FieldValueError,
        )
        yield case(
            given='65536.1',
            expected=FieldValueError,
        )
        yield case(
            given=b'65536.65536',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b''),
            expected=FieldValueError,
        )
        yield case(
            given='\x01',
            expected=FieldValueError,
        )
        yield case(
            given=b'\x01',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'\x01'),
            expected=FieldValueError,
        )
        yield case(
            given='\x00',
            expected=FieldValueError,
        )
        yield case(
            given=b'\x00',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'\x00'),
            expected=FieldValueError,
        )
        yield case(
            given='asdf',
            expected=FieldValueError,
        )
        yield case(
            given=b'0.0.0',
            expected=FieldValueError,
        )
        yield case(
            given='0x1.0xf',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'0xFF'),
            expected=FieldValueError,
        )
        yield case(
            given=-1,
            expected=FieldValueError,
        )
        yield case(
            given=0,
            expected=0,
        )
        yield case(
            given=1234,
            expected=1234,
        )
        yield case(
            given=65535,
            expected=65535,
        )
        yield case(
            given=65536,
            expected=65536,
        )
        yield case(
            given=4294967295,  # max
            expected=4294967295,
        )
        yield case(
            given=4294967296,  # max + 1
            expected=FieldValueError,
        )
        yield case(
            given=0.1,
            expected=FieldValueError,
        )
        yield case(
            given=decimal.Decimal('0.1'),
            expected=FieldValueError,
        )
        yield case(
            given=123.0,
            expected=FieldValueError,
        )
        yield case(
            given=decimal.Decimal(123),
            expected=FieldValueError,
        )
        yield case(
            given=None,
            expected=FieldValueError,
        )


class TestPortField(FieldTestMixin, unittest.TestCase):

    CLASS = PortField

    def cases__clean_param_value(self):
        yield case(
            given='0',       # min
            expected=0,
        )
        yield case(
            given='1',
            expected=1,
        )
        yield case(
            given='-1',
            expected=FieldValueError,
        )
        yield case(
            given='65535',   # max
            expected=65535,
        )
        yield case(
            given='65536',   # max + 1
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given='1F',
            expected=FieldValueError,
        )
        yield case(
            given='0.1',
            expected=FieldValueError,
        )
        yield case(
            given='1.0',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='0',        # min
            expected=0,
        )
        yield case(
            given=b'0',       # min
            expected=0,
        )
        yield case(
            given=bytearray(b'0'),       # min
            expected=0,
        )
        yield case(
            given='1',
            expected=1,
        )
        yield case(
            given=b'1',
            expected=1,
        )
        yield case(
            given=bytearray(b'1'),
            expected=1,
        )
        yield case(
            given='-1',
            expected=FieldValueError,
        )
        yield case(
            given=b'-1',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'-1'),
            expected=FieldValueError,
        )
        yield case(
            given='65535',    # max
            expected=65535,
        )
        yield case(
            given=b'65535',   # max
            expected=65535,
        )
        yield case(
            given=bytearray(b'65535'),   # max
            expected=65535,
        )
        yield case(
            given='65536',    # max + 1
            expected=FieldValueError,
        )
        yield case(
            given=b'65536',   # max + 1
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'65536'),   # max + 1
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given='1F',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'0.1'),
            expected=FieldValueError,
        )
        yield case(
            given='1.0',
            expected=FieldValueError,
        )
        yield case(
            given=-1,
            expected=FieldValueError,
        )
        yield case(
            given=0,
            expected=0,
        )
        yield case(
            given=65535,
            expected=65535,
        )
        yield case(
            given=65536,
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=123,
        )
        yield case(
            given=123.0,
            expected=123,
        )
        yield case(
            given=decimal.Decimal('123.0'),
            expected=123,
        )
        yield case(
            given=123.1,
            expected=FieldValueError,
        )
        yield case(
            given=decimal.Decimal('123.1'),
            expected=FieldValueError,
        )
        yield case(
            given=None,
            expected=FieldValueError,
        )


class TestEmailSimplifiedField(FieldTestMixin, unittest.TestCase):

    CLASS = EmailSimplifiedField

    def cases__clean_param_value(self):
        yield case(
            given='foo@example.com',
            expected='foo@example.com',
        )
        yield case(
            given='Gęślą@jaźń.coM',
            expected='Gęślą@jaźń.coM',
        )
        yield case(
            given='example.com',
            expected=FieldValueError,
        )
        yield case(
            given='foo@ab' + '.c' * 124,
            expected='foo@ab' + '.c' * 124,
        )
        yield case(
            given='foo@abx' + '.c' * 124,
            expected=FieldValueTooLongError,
        )
        yield case(
            given=' foo@example.com',
            expected=FieldValueError,
        )
        yield case(
            given='foo@example.com ',
            expected=FieldValueError,
        )
        yield case(
            given='foo @ example.com',
            expected=FieldValueError,
        )
        yield case(
            given='foo bar@example.com',
            expected=FieldValueError,
        )
        yield case(
            given='foo@exam ple.com',
            expected=FieldValueError,
        )
        yield case(
            given='@',
            expected=FieldValueError,
        )
        yield case(
            given='a@b@example.com',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='foo@example.com',
            expected='foo@example.com',
        )
        yield case(
            given=b'foo@example.com',
            expected='foo@example.com',
        )
        yield case(
            given=bytearray(b'foo@example.com'),
            expected='foo@example.com',
        )
        yield case(
            given='Gęślą@jaźń.coM',
            expected='Gęślą@jaźń.coM',
        )
        yield case(
            given='Gęślą@jaźń.coM'.encode('utf-8'),
            expected='Gęślą@jaźń.coM',
        )
        yield case(
            given=bytearray('Gęślą@jaźń.coM'.encode('utf-8')),
            expected='Gęślą@jaźń.coM',
        )
        yield case(
            given='example.com',
            expected=FieldValueError,
        )
        yield case(
            given=b'example.com',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'example.com'),
            expected=FieldValueError,
        )
        yield case(
            given='foo@ab' + '.c' * 124,
            expected='foo@ab' + '.c' * 124,
        )
        yield case(
            given=b'foo@ab' + b'.c' * 124,
            expected='foo@ab' + '.c' * 124,
        )
        yield case(
            given=bytearray(b'foo@ab' + b'.c' * 124),
            expected='foo@ab' + '.c' * 124,
        )
        yield case(
            given='foo@abx' + '.c' * 124,
            expected=FieldValueTooLongError,
        )
        yield case(
            given=b'foo@abx' + b'.c' * 124,
            expected=FieldValueTooLongError,
        )
        yield case(
            given=bytearray(b'foo@abx' + b'.c' * 124),
            expected=FieldValueTooLongError,
        )
        yield case(
            given=' foo@example.com',
            expected=FieldValueError,
        )
        yield case(
            given=b' foo@example.com',
            expected=FieldValueError,
        )
        yield case(
            given='foo@example.com ',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'foo @ example.com'),
            expected=FieldValueError,
        )
        yield case(
            given='foo bar@example.com',
            expected=FieldValueError,
        )
        yield case(
            given=b'foo@exam ple.com',
            expected=FieldValueError,
        )
        yield case(
            given='@',
            expected=FieldValueError,
        )
        yield case(
            given=bytearray(b'a@b@example.com'),
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        yield case(
            given=b'',
            expected=FieldValueError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestIBANSimplifiedField(FieldTestMixin, unittest.TestCase):

    CLASS = IBANSimplifiedField

    def cases__clean_param_value(self):
        yield case(
            given='GB34WEST1234567890',
            expected='GB34WEST1234567890',
        )
        yield case(
            given='gb34west1234567890',
            expected='GB34WEST1234567890',
        )
        yield case(
            given='gb34WEst1234567890',
            expected='GB34WEST1234567890',
        )
        yield case(
            given='GB34',
            expected=FieldValueError,
        )
        yield case(
            given='34WEST1234567890',
            expected=FieldValueError,
        )
        yield case(
            given='GBWEST1234567890',
            expected=FieldValueError,
        )
        yield case(
            given='GBX34WEST1234567890',
            expected=FieldValueError,
        )
        yield case(
            given='G234WEST1234567890',
            expected=FieldValueError,
        )
        yield case(
            given='GB 34 WEST 1234 5678 90',
            expected=FieldValueError,
        )
        yield case(
            given=' GB34WEST1234567890',
            expected=FieldValueError,
        )
        yield case(
            given='GB34WEST1234567890 ',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        for c in self.cases__clean_param_value():
            yield c
            yield c._replace(given=c.given.encode('utf-8'))
            yield c._replace(given=bytearray(c.given.encode('utf-8')))
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


class TestListOfDictsField(FieldTestMixin, unittest.TestCase):

    CLASS = ListOfDictsField

    def cases__clean_param_value(self):
        yield case(
            given='no implementation',
            expected=TypeError,
        )

    def cases__clean_result_value(self):
        obj = ArbitraryObject()
        yield case(
            given=[{'foo': b'12.23.45.56', 'bar': {1234: 'X'}, 'spam': obj}, {}],
            expected=[{'foo': b'12.23.45.56', 'bar': {1234: 'X'}, 'spam': obj}, {}],
        )
        yield case(
            given=[{'foo': b'12.23.45.56'}],
            expected=[{'foo': b'12.23.45.56'}],
        )
        yield case(
            given=[{'foo': bytearray(b'12.23.45.56')}],
            expected=[{'foo': bytearray(b'12.23.45.56')}],
        )
        yield case(
            given=[{'foo': '12.23.45.56'}],
            expected=[{'foo': '12.23.45.56'}],
        )
        yield case(
            given=[{'fooł': b'12.23.45.56'}],
            expected=ValueError,  # 'fooł' is not an ASCII-only str
        )
        yield case(
            given=[{'fooł'.encode('utf-8'): b'12.23.45.56'}],
            expected=TypeError,   # 'fooł'.encode('utf-8') is not an ASCII-only str
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field}},
            given=[{'foo': b'12.23.45.56'}],
            expected=[{'foo': '12.23.45.56'}],
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field}},
            given=[{'foo': '12.23.45.56'}],
            expected=[{'foo': '12.23.45.56'}],
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': UnicodeField}},
            given=[{'foo': 'łódź'.encode('utf-8')}],
            expected=[{'foo': 'łódź'}],
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': UnicodeField}},
            given=[{'bar': 'łódź'.encode('utf-8')}],
            expected=ValueError,  # 'bar' not in key_to_subfield_factory
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field}},
            given=[{'foo': b'12.23.45.56', 'bar': 'łódź'.encode('utf-8')}],
            expected=ValueError,  # 'bar' not in key_to_subfield_factory
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {None: IPv4Field}},
            given=[{'bar': 'łódź'.encode('utf-8')}],
            expected=FieldValueError,  # 'łódź'.encode('utf-8') is not a valid IPv4 address
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field, None: IPv4Field}},
            given=[{'foo': b'12.23.45.56', 'bar': 'łódź'.encode('utf-8')}],
            expected=FieldValueError,  # 'łódź'.encode('utf-8') is not a valid IPv4 address
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {None: UnicodeField}},
            given=[{'bar': 'łódź'.encode('utf-8')}],
            expected=[{'bar': 'łódź'}],
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field, None: UnicodeField}},
            given=[{'bar': 'łódź'.encode('utf-8')}],
            expected=[{'bar': 'łódź'}],
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field, None: UnicodeField}},
            given=[{'foo': b'12.23.45.56', 'bar': 'łódź'.encode('utf-8')}],
            expected=[{'foo': '12.23.45.56', 'bar': 'łódź'}],
        )
        yield case(
            init_kwargs={'allow_empty': True},
            given=[],
            expected=[],
        )
        yield case(
            init_kwargs={
                'allow_empty': True,
                'key_to_subfield_factory': {'foo': IPv4Field},
            },
            given=[],
            expected=[],
        )
        yield case(
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': b'12.23.45.56'}],
            expected=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': b'12.23.45.56'}],
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('bar',),
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('bar',),
                'key_to_subfield_factory': {'foo': IPv4Field, 'bar': IntegerField},
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=[{'foo': '12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': b'12.23.45.56'}],
            expected=ValueError,
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
            },
            given=[{'foo': '12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=ValueError,
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
                'key_to_subfield_factory': {'foo': IPv4Field, 'bar': IntegerField},
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': b'12.23.45.56'}],
            expected=ValueError,
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
                'key_to_subfield_factory': {'foo': IPv4Field, 'bar': IntegerField},
            },
            given=[{'foo': '12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=ValueError,
        )
        yield case(
            init_kwargs={
                'must_be_unique': ('foo',),
                'key_to_subfield_factory': {'foo': IPv4Field, 'bar': IntegerField},
            },
            given=[{'foo': b'12.23.45.56', 'bar': 3}, {'foo': '12.23.45.56'}],
            expected=ValueError,
        )
        yield case(
            given=[],
            expected=ValueError,
        )
        yield case(
            init_kwargs={'key_to_subfield_factory': {'foo': IPv4Field}},
            given=[],
            expected=ValueError,
        )
        yield case(
            given=['abc'],
            expected=TypeError,
        )
        yield case(
            given=[[]],
            expected=TypeError,
        )
        yield case(
            given='abc',
            expected=TypeError,
        )
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            init_kwargs={'must_be_unique': None},
            given=[{'foo': b'12.23.45.56'}],
            expected=TypeError,
        )


# TODO: improve test cases (+ remove redundant ones)
class TestAddressField(FieldTestMixin, unittest.TestCase):

    CLASS = AddressField

    def cases__clean_param_value(self):
        yield case(
            given='no implementation',
            expected=TypeError,
        )

    def cases__clean_result_value(self):
        yield case(
            given=[{'ip': '12.23.45.56'}],
            expected=[{'ip': '12.23.45.56'}],
        )
        yield case(
            given=[{'ip': b'12.23.45.56', 'cc': b'PL', 'asn': 123}],
            expected=[{'ip': '12.23.45.56', 'cc': 'PL', 'asn': 123}],
        )
        yield case(
            given=({'ip': b'12.23.45.56', 'cc': b'PL', 'asn': b'0.123'},),
            expected=[{'ip': '12.23.45.56', 'cc': 'PL', 'asn': 123}],
        )
        yield case(
            given=[{'ip': '12.23.45.56', 'cc': 'pL', 'asn': 123}],
            expected=[{'ip': '12.23.45.56', 'cc': 'PL', 'asn': 123}],
        )
        yield case(
            given=(
                {'ip': '12.23.45.56', 'cc': 'pL', 'asn': 2 ** 32 - 1},),
            expected=[
                {'ip': '12.23.45.56', 'cc': 'PL', 'asn': 2 ** 32 - 1}],
        )
        yield case(
            given=[
                {'ip': '12.23.45.56', 'cc': b'pl', 'asn': b'123'},
                {'ip': '78.90.122.134', 'asn': '12345678'},
            ],
            expected=[
                {'ip': '12.23.45.56', 'cc': 'PL', 'asn': 123},
                {'ip': '78.90.122.134', 'asn': 12345678},
            ],
        )
        yield case(
            # bad ip
            given=[{'ip': '12.23.45.', 'cc': b'PL', 'asn': 123}],
            expected=FieldValueError,
        )
        yield case(
            # ip must be a str or bytes/bytearray
            given=[
                {'ip': ['12.23.45.56', '12.23.45.45'],
                 'cc': 'PL', 'asn': 123}],
            expected=TypeError,
        )
        yield case(
            # bad cc
            given=[{'ip': '12.23.45.56', 'cc': 'PRL', 'asn': 123}],
            expected=FieldValueError,
        )
        yield case(
            # bad asn
            given=[{'ip': '12.23.45.56', 'cc': 'PL', 'asn': 2 ** 32}],
            expected=FieldValueError,
        )
        yield case(
            # illegal key
            given=[
                {'ip': '12.23.45.56', 'cc': 'PL', 'asn': 123,
                 'fqdn': 'www.example.com'}],
            expected=ValueError,
        )
        yield case(
            # illegal key b'asn' (also its type is wrong...)
            given=[{'ip': b'12.23.45.56', 'cc': b'PL', b'asn': 123}],
            expected=ValueError,
        )
        class _EqualToStrASN:
            def __eq__(self, other): return other == 'asn'
            def __hash__(self): return hash('asn')
        yield case(
            # key *equal* to 'asn' string but of wrong type (!)
            given=[{'ip': b'12.23.45.56', 'cc': b'PL', _EqualToStrASN(): 123}],
            expected=TypeError,
        )
        yield case(
            # missing 'ip' key
            given=[{'cc': 'pl', 'asn': 123}],
            expected=ValueError,
        )
        yield case(
            # 'ip' value not unique
            given=[
                {'ip': '12.23.45.56', 'cc': 'pl', 'asn': '123'},
                {'ip': '12.23.45.56', 'asn': '12345678'},
            ],
            expected=ValueError,
        )
        yield case(
            # empty sequence
            given=[],
            expected=ValueError,
        )
        yield case(
            init_kwargs={'allow_empty': True},
            given=[],
            expected=[],
        )
        yield case(
            # not a mapping in the sequence
            given=['123'],
            expected=TypeError,
        )
        yield case(
            # not a non-string sequence
            given={'123'},
            expected=TypeError,
        )
        yield case(
            # not a non-string sequence
            given='123',
            expected=TypeError,
        )


class TestDirField(FieldTestMixin, unittest.TestCase):

    CLASS = DirField

    def cases__clean_param_value(self):
        yield case(
            given='src',
            expected='src',
        )
        yield case(
            given='dst',
            expected='dst',
        )
        yield case(
            given='DST',
            expected=FieldValueError,
        )
        yield case(
            given='foooo',
            expected=FieldValueError,
        )
        yield case(
            given='',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        for c in self.cases__clean_param_value():
            yield c
            yield c._replace(given=c.given.encode('utf-8'))
            yield c._replace(given=bytearray(c.given.encode('utf-8')))
        yield case(
            given=123,
            expected=TypeError,
        )
        yield case(
            given=None,
            expected=TypeError,
        )


# TODO: improve test cases (+ remove redundant ones)
class TestExtendedAddressField(TestAddressField):

    CLASS = ExtendedAddressField

    def cases__clean_result_value(self):
        for c in super(TestExtendedAddressField, self).cases__clean_result_value():
            yield c

        yield case(
            given=[{'ipv6': '2001:0db8:85a3:0000:0000:8a2e:0370:7334'}],
            expected=[{'ipv6': '2001:db8:85a3::8a2e:370:7334'}],
        )
        yield case(
            given=[{
                'ipv6': b'2001:0DB8:85A3:0000:0000:8A2E:0370:7334',
                'cc': b'pL',
                'asn': 123,
            }],
            expected=[{
                'ipv6': '2001:db8:85a3::8a2e:370:7334',
                'cc': 'PL',
                'asn': 123,
            }],
        )
        yield case(
            given=[
                {'ipv6': '2001:0db8:85a3:0000:0000:8a2e:0370:7334', 'cc': 'pl', 'dir': b'dst'},
                {'ipv6': '0000::0001', 'dir': 'src', 'rdns': 'example.com'},
                {'ip': '12.23.45.56', 'dir': 'src', 'cc': b'pl', 'asn': '123'},
            ],
            expected=[
                {'ipv6': '2001:db8:85a3::8a2e:370:7334', 'cc': 'PL', 'dir': 'dst'},
                {'ipv6': '::1', 'dir': 'src', 'rdns': 'example.com'},
                {'ip': '12.23.45.56', 'dir': 'src', 'cc': 'PL', 'asn': 123},
            ],
        )
        yield case(
            # bad ipv6
            given=[{
                'ip': '2001:0db8:85a3:0000:0000:8a2e:0370:7334:',
                'cc': 'PL',
                'asn': 123,
            }],
            expected=FieldValueError,
        )
        yield case(
            # ipv6 must be a str or bytes/bytearray
            given=[{
                'ipv6': ['2001:0db8:85a3:0000:0000:8a2e:0370:7334'],
                'cc': 'PL',
                'asn': 123,
            }],
            expected=TypeError,
        )
        yield case(
            # illegal key
            given=[{
                'ipv6': '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
                'illegal': 'foo',
            }],
            expected=ValueError,
        )
        yield case(
            # 'ip' value not unique
            given=[
                {'ipv6': '2001:0db8:85a3:0000:0000:8a2e:0370:7334', 'cc': 'pl', 'dir': 'dst'},
                {'ipv6': '0000::0001', 'dir': 'src', 'rdns': 'example.com'},
                {'ip': '12.23.45.56', 'dir': 'src', 'cc': 'pl', 'asn': '123'},
                {'ip': b'12.23.45.56', 'dir': 'src', 'cc': 'pl', 'asn': '123'},
            ],
            expected=ValueError,
        )
        yield case(
            # 'ipv6' value not unique
            given=[
                {'ipv6': '0000:0000:0000:0000:0000:0000:0000:0001', 'cc': 'pl', 'dir': 'dst'},
                {'ipv6': b'0000::0001', 'dir': 'src', 'rdns': 'example.com'},
                {'ip': '12.23.45.56', 'dir': 'src', 'cc': 'pl', 'asn': '123'},
            ],
            expected=ValueError,
        )
        yield case(
            # bad dir
            given=[{'ip': '12.23.45.56', 'dir': 'fooo'}],
            expected=FieldValueError,
        )
        yield case(
            # bad rdns
            given=[{'ip': '12.23.45.56', 'rdns': '.example.com'}],
            expected=FieldValueError,
        )
        yield case(
            # both 'ip' and 'ipv6' keys present
            given=[{'ip': '12.23.45.56',
                    'ipv6': '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
                    'cc': 'pl',
                    'asn': 123}],
            expected=ValueError,
        )


# TODO: add dedicated ResultListFieldMixin tests
# TODO: add dedicated DictResultField tests
# (now these classes are tested only indirectly by the
# ListOfDictsField/AddressField/ExtendedAddressField tests)

# class Test(FieldTestMixin, unittest.TestCase):
#
#     CLASS =
#
#     def cases__clean_param_value(self):
#         yield case(
#         )
#
#     def cases__clean_result_value(self):
#         yield case(
#         )

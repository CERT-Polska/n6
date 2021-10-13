# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections.abc as collections_abc
import copy
import datetime
import functools
import unittest
from unittest.mock import (
    ANY,
    patch,
)

from unittest_expander import (
    expand,
    foreach,
)

from n6sdk.class_helpers import (
    attr_required,
)
from n6sdk.data_spec import (
    AllSearchableDataSpec,
    DataSpec,
    Ext,
)
from n6sdk.data_spec.fields import (
    AnonymizedIPv4Field,
    ASNField,
    CCField,
    DateTimeField,
    DomainNameField,
    DomainNameSubstringField,
    EmailSimplifiedField,
    ExtendedAddressField,
    IBANSimplifiedField,
    IntegerField,
    IPv4Field,
    IPv4NetField,
    IPv6Field,
    IPv6NetField,
    ListOfDictsField,
    MD5Field,
    PortField,
    SHA1Field,
    SHA256Field,
    SourceField,
    UnicodeField,
    UnicodeEnumField,
    UnicodeLimitedField,
    URLField,
    URLSubstringField,
)
from n6sdk.datetime_helpers import (
    FixedOffsetTimezone,
)
from n6sdk.exceptions import (
    ParamKeyCleaningError,
    ParamValueCleaningError,
    ResultKeyCleaningError,
    ResultValueCleaningError
)
from n6sdk.tests._generic_helpers import (
    TestCaseMixin,
    CustomImmutableSet,
    CustomMutableSet,
)



#
# Helper decorators
#

def for_various_result_types_of__filter_by_which(test_meth):

    # Taking into consideration that the data specification's
    # overridable method `filter_by_which()` is required to return a
    # container that is either a *dict items view* or a *set-like*
    # object, we want to ensure that the methods which call
    # `filter_by_which()` handle the call results properly for various
    # types of these results (i.e., regardless of whether the result is
    # a *dict items view* or a *set-like* object; regardless of whether
    # the object is an instance of a builtin type or of a custom one;
    # and regardless of whether the object is mutable or immutable...).
    #
    # By wrapping with this decorator a test of a data specification's
    # method which uses `filter_by_which()` call results *and* by
    # decorating the test case class that contains such a test with
    # `@unittest_expander.expand` -- we ensure that the method will be
    # tested for various kinds of types of `filter_by_which()` call
    # results.

    @foreach([
        None,
        lambda iterable: dict(iterable).items(),
        lambda iterable: collections_abc.ItemsView(dict(iterable)),
        frozenset,
        set,
        CustomImmutableSet,
        CustomMutableSet,
    ])
    @functools.wraps(test_meth)
    def decorated_test_meth(self, result_type_adjuster):
        if result_type_adjuster is None:
            test_meth(self)
            return
        called = []
        wrapped = _make_wrapped__filter_by_which(
            result_type_adjuster,
            called,
            orig=self.base_data_spec_class.filter_by_which)
        with patch.object(self.base_data_spec_class, 'filter_by_which', wrapped):
            assert not called, 'bug in the test'
            test_meth(self)
            assert called, 'bug in the test'

    def _make_wrapped__filter_by_which(result_type_adjuster, called, orig):
        @staticmethod
        def wrapped(*args, **kwargs):
            called.append(None)
            orig_result = orig(*args, **kwargs)
            return result_type_adjuster(orig_result)
        return wrapped

    return decorated_test_meth



#
# Mix-ins for test case classes
#

class MixinBase(TestCaseMixin):

    DEL = object()  # a 'do-not-include-me' sentinel value used here and there

    base_data_spec_class = None  # to be set in actual mix-ins or concrete classes

    key_to_field_type = {
        'id': UnicodeLimitedField,
        'source': SourceField,
        'restriction': UnicodeEnumField,
        'confidence': UnicodeEnumField,
        'category': UnicodeEnumField,
        'time': DateTimeField,
        'time.min': DateTimeField,
        'time.max': DateTimeField,
        'time.until': DateTimeField,

        'address': ExtendedAddressField,
        'ip': IPv4Field,
        'ip.net': IPv4NetField,
        'ipv6': IPv6Field,
        'ipv6.net': IPv6NetField,
        'asn': ASNField,
        'cc': CCField,

        'active.min': DateTimeField,
        'active.max': DateTimeField,
        'active.until': DateTimeField,
        'expires': DateTimeField,
        'replaces': UnicodeLimitedField,
        'status': UnicodeEnumField,

        'count': IntegerField,
        'until': DateTimeField,

        'action': UnicodeLimitedField,
        'adip': AnonymizedIPv4Field,
        'dip': IPv4Field,
        'dport': PortField,
        'email': EmailSimplifiedField,
        'fqdn': DomainNameField,
        'fqdn.sub': DomainNameSubstringField,
        'iban': IBANSimplifiedField,
        'injects': ListOfDictsField,
        'md5': MD5Field,
        'modified': DateTimeField,
        'modified.max': DateTimeField,
        'modified.min': DateTimeField,
        'modified.until': DateTimeField,
        'name': UnicodeLimitedField,
        'origin': UnicodeEnumField,
        'phone': UnicodeLimitedField,
        'proto': UnicodeEnumField,
        'registrar': UnicodeLimitedField,
        'sha1': SHA1Field,
        'sha256': SHA256Field,
        'sport': PortField,
        'target': UnicodeLimitedField,
        'url': URLField,
        'url.sub': URLSubstringField,
        'url_pattern': UnicodeLimitedField,
        'username': UnicodeLimitedField,
        'x509fp_sha1': SHA1Field,
    }

    @property
    def optional_keys(self):
        return self.keys - self.required_keys

    @attr_required('base_data_spec_class')
    def setUp(self):
        data_spec_class = self.get_data_spec_class()
        self.ds = data_spec_class()
        self._selftest_assertions()
        self._given_dicts_and_their_deep_copies = []

    def tearDown(self):
        # ensure that raw param/result dicts (if any) have not been modified
        for d, dcopy in self._given_dicts_and_their_deep_copies:
            self.assertEqualIncludingTypes(dcopy, d)

    def get_data_spec_class(self):
        return self.base_data_spec_class

    def get_example_given_dict_keys_to_be_omitted(self):
        return set()

    def _selftest_assertions(self):
        assert self.keys <= set(self.key_to_field_type)
        assert self.required_keys <= self.keys
        assert self.required_keys <= set(self.example_given_dict)
        omitted = self.get_example_given_dict_keys_to_be_omitted()
        non_omitted = set(self.example_given_dict) - omitted
        assert non_omitted <= self.keys
        assert set(self.example_cleaned_dict) == non_omitted

    def _given_dict(self, **kwargs):
        d = dict(self.example_given_dict, **kwargs)
        d = {k: v for k, v in d.items()
             if v is not self.DEL}
        self._given_dicts_and_their_deep_copies.append(
            (d, copy.deepcopy(d)))
        return d

    def _cleaned_dict(self, **kwargs):
        d = dict(self.example_cleaned_dict, **kwargs)
        return {k: v for k, v in d.items()
                if v is not self.DEL}

    def _test_illegal_keys(self, clean_method):
        given_dict = self._given_dict(
            **dict.fromkeys(self.example_illegal_keys))
        with self.assertRaises(self.key_cleaning_error) as cm:
            clean_method(given_dict)
        exc = cm.exception
        self.assertEqual(exc.illegal_keys, self.example_illegal_keys)
        self.assertEqual(exc.missing_keys, set())

    def _test_missing_keys(self, clean_method):
        if not self.example_missing_keys:
            assert not self.required_keys
            return
        given_dict = self._given_dict(
            **dict.fromkeys(self.example_missing_keys, self.DEL))
        with self.assertRaises(self.key_cleaning_error) as cm:
            clean_method(given_dict)
        exc = cm.exception
        self.assertEqual(exc.illegal_keys, set())
        self.assertEqual(exc.missing_keys, self.example_missing_keys)

    def _test_field_specs(self, field_specs, expected_keys):
        self.assertIsInstance(field_specs, dict)
        self.assertEqualIncludingTypes(
            sorted(field_specs),
            sorted(expected_keys))
        for key, field in field_specs.items():
            self.assertIs(field, getattr(self.ds, key))
            self.assertIs(type(field), self.key_to_field_type[key])


class ParamCleanMixin(MixinBase):

    def get_example_given_dict_keys_to_be_omitted(self):
        return {key for key, value in self.example_given_dict.items()
                if value == []}


class AllSearchableParamCleanMixin(ParamCleanMixin):

    # param-fields-related

    base_data_spec_class = AllSearchableDataSpec

    key_cleaning_error = ParamKeyCleaningError

    keys = {
        'id', 'source', 'restriction', 'confidence', 'category',
        'time.min', 'time.max', 'time.until',

        'ip', 'ip.net', 'ipv6', 'ipv6.net', 'asn', 'cc',

        'active.min', 'active.max', 'active.until',
        'replaces', 'status',

        'action', 'dip', 'dport', 'email', 'fqdn', 'fqdn.sub',
        'iban', 'modified.max', 'modified.min', 'modified.until',
        'name', 'md5', 'sha1', 'sha256', 'origin', 'phone', 'proto',
        'registrar', 'sport', 'target', 'url', 'url.sub',
        'url_pattern', 'username', 'x509fp_sha1',
    }

    required_keys = set()

    single_param_keys = {
        'time.min', 'time.max', 'time.until',
        'active.min', 'active.max', 'active.until',
        'modified.min', 'modified.max', 'modified.until',
    }

    example_given_dict = {
        'id': ['aaaaa', 'bbb'],
        'category': ['bots'],
        'source': ['some.source', 'some.otherrrrrrrrrrrrrrrrrrrrrrr'],
        'confidence': ['high', 'medium'],
        'ip': ['100.101.102.103'],
        'ipv6': ['2001:db8:85a3::8a2e:370:7334'],
        'cc': ['PL', 'US'],
        'dip': ['0.10.20.30'],
        'foo.bar.spam.ham.unknown': [],  # empty list so param should be treated as non-existent
        'registrar': ['Foo Bar'],
        'asn': ['AS 80000', '1'],
        'dport': ['1234'],
        'ip.net': ['100.101.102.103/32', '1.2.3.4/7'],
        'ipv6.net': ['2001:db8:85a3::8a2e:370:7334/128'],
        'time.min': ['2014-04-01 01:07:42+02:00'],
        'time.max': [],                   # empty list so param should be treated as non-existent
        'iban': [],                      # empty list so param should be treated as non-existent
        'modified.until': ['2014-04-01 01:07:42+02:00'],
        'active.min': ['2015-05-02T24:00'],
        'phone': ['abc', '+48123456789'],
        'url_pattern': ['!@#$%^&* ()'],
        'url': ['http://www.ołówek.EXAMPLĘ.com/\udcdd-TRALALą.html'],
        'fqdn': ['www.test.org', 'www.ołówek.EXAMPLĘ.com'],
        'url.sub': [('xx' + 682 * '\udccc')],
        'fqdn.sub': ['ołówek'],
    }

    example_cleaned_dict = {
        # (values have been transformed into 1-or-many-element-lists)

        # (str values)
        'id': ['aaaaa', 'bbb'],
        'category': ['bots'],
        'source': ['some.source', 'some.otherrrrrrrrrrrrrrrrrrrrrrr'],
        'confidence': ['high', 'medium'],
        'ip': ['100.101.102.103'],
        'ipv6': ['2001:0db8:85a3:0000:0000:8a2e:0370:7334'],
        'cc': ['PL', 'US'],
        'dip': ['0.10.20.30'],
        'registrar': ['Foo Bar'],

        # (numbers converted to int)
        'asn': [80000, 1],
        'dport': [1234],

        # (IP network specs converted to (IP address, number) pairs)
        'ip.net': [('100.101.102.103', 32), ('1.2.3.4', 7)],
        'ipv6.net': [('2001:0db8:85a3:0000:0000:8a2e:0370:7334', 128)],

        # (a TZ +02:00 datetime converted to UTC)
        'time.min': [datetime.datetime(2014, 3, 31, 23, 7, 42)],
        'modified.until': [datetime.datetime(2014, 3, 31, 23, 7, 42)],

        # (24:00 on 2nd of May converted to 00:00 on 3rd of May)
        'active.min': [datetime.datetime(2015, 5, 3)],

        'phone': ['abc', '+48123456789'],

        'url_pattern': ['!@#$%^&* ()'],

        # (lone surrogates preserved)
        'url': ['http://www.ołówek.EXAMPLĘ.com/\udcdd-TRALALą.html'],
        'url.sub': ['xx' + 682 * '\udccc'],

        # (domain name IDNA-encoded)
        'fqdn': ['www.test.org', 'www.xn--owek-qqa78b.xn--exampl-14a.com'],
        'fqdn.sub': ['xn--owek-qqa78b'],
    }

    example_illegal_keys = {
        'foo',
        'illegal',
        'address',  # 'address' is a result-only field
    }

    example_missing_keys = set()

    def _selftest_assertions(self):
        super(AllSearchableParamCleanMixin, self)._selftest_assertions()
        assert self.single_param_keys <= self.keys


class NoSearchableParamCleanMixin(ParamCleanMixin):

    base_data_spec_class = DataSpec

    key_cleaning_error = ParamKeyCleaningError

    keys = set()
    required_keys = set()
    single_param_keys = set()

    example_given_dict = {
        # empty lists so these params should be treated as non-existent
        'foo.bar.spam.ham.unknown': [],
        'time.max': [],
        'iban': [],
    }
    example_cleaned_dict = {}
    example_illegal_keys = AllSearchableParamCleanMixin.keys.copy()
    example_missing_keys = set()


class ResultCleanMixin(MixinBase):

    # result-fields-related

    base_data_spec_class = DataSpec

    key_cleaning_error = ResultKeyCleaningError

    keys = {
        'id', 'source', 'restriction', 'confidence', 'category', 'time',
        'address',

        'expires', 'replaces', 'status',

        'count', 'until',

        'action', 'adip', 'dip', 'dport', 'email', 'fqdn',
        'iban', 'injects', 'modified', 'name', 'md5', 'sha1', 'sha256',
        'origin', 'phone', 'proto', 'registrar', 'sport',
        'target', 'url', 'url_pattern', 'username', 'x509fp_sha1',
    }

    required_keys = {
        'id', 'source', 'restriction', 'confidence', 'category', 'time',
    }

    example_given_dict = {
        'id': b'aaaaa',
        'source': bytearray(b'some.source-eeeeeeeeeeeeeeeeeeee'),
        'restriction': b'public',
        'confidence': 'low',
        'category': 'bots',
        'adip': 'x.10.20.30',
        'url_pattern': b'!@#$%^&* ()',
        'address': [
            {
                'ip': '100.101.102.103',
                'cc': bytearray(b'PL'),
                'asn': 80000,
            },
            {
                'ip': b'10.0.255.128',
                'cc': 'US',
                'asn': 10000,
            },
        ],
        'dport': 1234,
        'time': datetime.datetime(
            2014, 4, 1, 1, 7, 42,              # a TZ-aware datetime
            tzinfo=FixedOffsetTimezone(120)),  # (timezone UTC+02:00)
        'url': b'http://www.o\xc5\x82\xc3\xb3wek.EXAMPL\xc4\x98.com/\xdd-TRALAL\xc4\x85.html',
        'fqdn': 'www.ołówek.EXAMPLĘ.com',
    }

    example_cleaned_dict = {
        # (bytes/bytearray values have been converted to str)
        'id': 'aaaaa',
        'source': 'some.source-eeeeeeeeeeeeeeeeeeee',
        'restriction': 'public',
        'confidence': 'low',
        'category': 'bots',
        'adip': 'x.10.20.30',
        'url_pattern': '!@#$%^&* ()',

        'address': [
            {
                'ip': '100.101.102.103',
                'cc': 'PL',
                'asn': 80000,  # int
            },
            {
                'ip': '10.0.255.128',
                'cc': 'US',
                'asn': 10000,  # int
            },
        ],
        'dport': 1234,  # int

        # (a naive datetime -- TZ +02:00 converted to UTC)
        'time': datetime.datetime(2014, 3, 31, 23, 7, 42),

        # (UTF-8 characters decoded; non-UTF-8 URL bytes surrogate-escaped)
        'url': 'http://www.ołówek.EXAMPLĘ.com/\udcdd-TRALALą.html',

        # (domain name IDNA-encoded)
        'fqdn': 'www.xn--owek-qqa78b.xn--exampl-14a.com',
    }

    example_illegal_keys = {
        'foo',
        'illegal',
        'ip',
    }

    example_missing_keys = {
        'id',
        'restriction',
    }


#
# Similar mix-ins for tests of a DataSpec/AllSearchableDataSpec subclass
# (with extended/removed/replaced/added fields)

class SubclassMixinBase(MixinBase):

    # adjusting test class attributes to match the above data spec subclass
    key_to_field_type = MixinBase.key_to_field_type.copy()
    del key_to_field_type['category']
    del key_to_field_type['active.max']
    del key_to_field_type['fqdn.sub']
    key_to_field_type.update({
        'dport': IntegerField,
        'active.min': IntegerField,
        'justnew': UnicodeField,
        'singular': UnicodeField,
    })

    def get_data_spec_class(self):
        class DataSpecSubclass(self.base_data_spec_class):
            id = Ext(                        # extended
                in_params='required',
                # (note: `in_result` left as 'required')
                max_length=3,
            )
            category = None                  # removed (masked)
            dport = IntegerField(            # replaced
                in_params='optional',
                in_result=None,
                min_value=10000,
                max_value=65535,
            )
            justnew = UnicodeField(          # added
                in_params='optional',
                in_result='required',
            )
            singular = UnicodeField(         # added
                in_params='optional',
                in_result=None,
                single_param=True,           # (single-value-only param)
            )
            notused = UnicodeField()     # not used because not tagged as
                                         # `in_params` and/or `in_results`

            url = Ext(                       # extended
                extra_params=Ext(            #  extended
                    sub=Ext(                 #   extended
                        max_length=100,
                        in_params='required',
                        # (note: `in_result` left as None)
                    )
                ),
                in_params=None,
                # (note: `in_result` left as 'optional')
                custom_info=dict(
                    tralala=dict(ham='spam'),
                ),
            )
            active = Ext(                    # extended
                extra_params=Ext(            #  extended
                    min=IntegerField(        #   replaced
                        in_params='optional',
                        # (note: `in_result` left as None)
                    ),
                    max=None,                #   removed (masked)
                )
            )
            fqdn = Ext(                      # extended
                extra_params={},             #  replaced (removing 'fqdn.sub')
                in_result='required',
                # (note: `in_params` left as 'optional')
            )
        return DataSpecSubclass


class SubclassParamCleanMixin(SubclassMixinBase, AllSearchableParamCleanMixin):

    # param-fields-related

    keys = AllSearchableParamCleanMixin.keys.copy()
    keys -= {'category', 'url', 'fqdn.sub', 'active.max'}
    keys |= {'justnew', 'singular'}

    required_keys = {'id', 'url.sub'}

    single_param_keys = AllSearchableParamCleanMixin.single_param_keys.copy()
    single_param_keys -= {'active.min', 'active.max'}
    single_param_keys |= {'singular'}

    example_given_dict = AllSearchableParamCleanMixin.example_given_dict.copy()
    del example_given_dict['category']
    del example_given_dict['url']
    del example_given_dict['fqdn.sub']
    example_given_dict.update({
        'id': ['aaa', 'bbb'],
        'dport': ['12345'],
        'active.min': ['9876543210', '-123'],
        'url.sub': [100 * '\udccc'],
        'justnew': ['xyz', '123'],
        'singular': ['xyz'],
    })

    example_cleaned_dict = AllSearchableParamCleanMixin.example_cleaned_dict.copy()
    del example_cleaned_dict['category']
    del example_cleaned_dict['url']
    del example_cleaned_dict['fqdn.sub']
    example_cleaned_dict.update({
        'id': ['aaa', 'bbb'],
        'dport': [12345],
        'active.min': [9876543210, -123],
        'url.sub': [100 * '\udccc'],
        'justnew': ['xyz', '123'],
        'singular': ['xyz'],
    })

    example_illegal_keys = {
        'foo',
        'illegal',
        'category',
        'active.max',
        'url',
        'fqdn.sub',
        'notused',
        'address',
    }

    example_missing_keys = {
        'id',
        'url.sub',
    }


class SubclassResultCleanMixin(SubclassMixinBase, ResultCleanMixin):

    # result-fields-related

    keys = ResultCleanMixin.keys.copy()
    keys -= {'category', 'dport'}
    keys |= {'justnew'}

    required_keys = ResultCleanMixin.required_keys.copy()
    required_keys -= {'category'}
    required_keys |= {'justnew', 'fqdn'}

    example_given_dict = ResultCleanMixin.example_given_dict.copy()
    del example_given_dict['category']
    del example_given_dict['dport']
    example_given_dict.update({
        'id': 'aaa',
        'justnew': b'xyzxyz',
    })

    example_cleaned_dict = ResultCleanMixin.example_cleaned_dict.copy()
    del example_cleaned_dict['category']
    del example_cleaned_dict['dport']
    example_cleaned_dict.update({
        'id': 'aaa',
        'justnew': 'xyzxyz',
    })

    example_illegal_keys = {
        'foo',
        'illegal',
        'category',
        'dport',
        'notused',
        'ip',
    }

    example_missing_keys = {
        'id',
        'restriction',
        'justnew',
        'fqdn',
    }


#
# Additional mix-ins that provide some typical test methods

class MixInProvidingTestMethodsFor__clean_param_dict(MixinBase):

    def test_valid(self):
        given_dict = self._given_dict()
        cleaned = self.ds.clean_param_dict(given_dict)
        expected_cleaned = self._cleaned_dict()
        self.assertEqualIncludingTypes(cleaned, expected_cleaned)

    def test_valid_ignoring_some_keys(self):
        given_dict = self._given_dict(ip='badvalue', illegal='spam')
        cleaned = self.ds.clean_param_dict(
            given_dict,
            ignored_keys=['ip', 'illegal'])
        expected_cleaned = self._cleaned_dict(ip=self.DEL)
        self.assertEqualIncludingTypes(cleaned, expected_cleaned)

    def test_illegal_keys(self):
        self._test_illegal_keys(self.ds.clean_param_dict)

    def test_missing_keys(self):
        self._test_missing_keys(self.ds.clean_param_dict)


@expand
class MixInProvidingTestMethodsFor__param_field_specs(MixinBase):

    @for_various_result_types_of__filter_by_which
    def test_all(self):
        field_specs = self.ds.param_field_specs()
        self._test_field_specs(
            field_specs,
            expected_keys=self.keys)

    @for_various_result_types_of__filter_by_which
    def test_all_without_multi(self):
        field_specs = self.ds.param_field_specs(multi=False)
        self._test_field_specs(
            field_specs,
            expected_keys=self.single_param_keys)

    @for_various_result_types_of__filter_by_which
    def test_all_without_single(self):
        field_specs = self.ds.param_field_specs(single=False)
        self._test_field_specs(
            field_specs,
            expected_keys=(self.keys - self.single_param_keys))

    @for_various_result_types_of__filter_by_which
    def test_all_without_multi_and_without_single(self):
        field_specs = self.ds.param_field_specs(multi=False, single=False)
        # always must be empty
        self._test_field_specs(
            field_specs,
            expected_keys=set())

    @for_various_result_types_of__filter_by_which
    def test_required(self):
        field_specs = self.ds.param_field_specs('required')
        self._test_field_specs(
            field_specs,
            expected_keys=self.required_keys)

    @for_various_result_types_of__filter_by_which
    def test_required_without_multi(self):
        field_specs = self.ds.param_field_specs('required', multi=False)
        self._test_field_specs(
            field_specs,
            expected_keys=(self.required_keys & self.single_param_keys))

    @for_various_result_types_of__filter_by_which
    def test_required_without_single(self):
        field_specs = self.ds.param_field_specs('required', single=False)
        self._test_field_specs(
            field_specs,
            expected_keys=(self.required_keys - self.single_param_keys))

    @for_various_result_types_of__filter_by_which
    def test_required_without_multi_and_without_single(self):
        field_specs = self.ds.param_field_specs(
            'required', multi=False, single=False)
        # always must be empty
        self._test_field_specs(
            field_specs,
            expected_keys=set())

    @for_various_result_types_of__filter_by_which
    def test_optional(self):
        field_specs = self.ds.param_field_specs('optional')
        self._test_field_specs(
            field_specs,
            expected_keys=self.optional_keys)

    @for_various_result_types_of__filter_by_which
    def test_optional_without_multi(self):
        field_specs = self.ds.param_field_specs('optional', multi=False)
        self._test_field_specs(
            field_specs,
            expected_keys=(self.optional_keys & self.single_param_keys))

    @for_various_result_types_of__filter_by_which
    def test_optional_without_single(self):
        field_specs = self.ds.param_field_specs('optional', single=False)
        self._test_field_specs(
            field_specs,
            expected_keys=(self.optional_keys - self.single_param_keys))

    @for_various_result_types_of__filter_by_which
    def test_optional_without_multi_and_without_single(self):
        field_specs = self.ds.param_field_specs(
            'optional', multi=False, single=False)
        # always must be empty
        self._test_field_specs(
            field_specs,
            expected_keys=set())



#
# Concrete test cases
#

#
# Param-fields-related:

class TestDataSpec_clean_param_dict(
        NoSearchableParamCleanMixin,
        MixInProvidingTestMethodsFor__clean_param_dict,
        unittest.TestCase):
    pass


class TestDataSpec_param_field_specs(
        NoSearchableParamCleanMixin,
        MixInProvidingTestMethodsFor__param_field_specs,
        unittest.TestCase):
    pass


class TestAllSearchableDataSpec_clean_param_dict(
        AllSearchableParamCleanMixin,
        MixInProvidingTestMethodsFor__clean_param_dict,
        unittest.TestCase):

    def test_invalid_value__source_too_long(self):
        given_dict = self._given_dict(
            source=['some.source', 'some.otherrrrrrrrrrrrrrrrrrrrrrr' + 'x'])
        with self.assertRaises(ParamValueCleaningError) as cm:
            self.ds.clean_param_dict(given_dict)
        exc = cm.exception
        self.assertEqual(exc.error_info_seq, [
            ('source', 'some.otherrrrrrrrrrrrrrrrrrrrrrrx', ANY),
        ])
        self.assertIsInstance(exc.error_info_seq[0][2], Exception)

    def test_several_invalid_values(self):
        given_dict = self._given_dict(**{
            # not in enum set
            'confidence': ['high', 'medium', 'INVALID'],
            # invalid IPv4 (333 > 255)
            'ip': ['333.101.102.103'],
            # invalid CIDR IPv4 network spec (33 > 32, 333 > 255)
            'ip.net': ['100.101.102.103/33', '333.2.3.4/1'],
            # invalid country code ('!' not allowed)
            'cc': ['!!', 'US'],
            # IP starts with an anonymized octet
            'dip': ['x.20.30.40'],
            # too big number
            'asn': ['4294967297'],
            # too small number
            'dport': ['-1234'],
            # invalid time
            'time.min': ['2014-04-01 61:61:61+02:00'],
            # multiple values of single-value-only param
            'time.max': ['2015-04-01 01:07:42+02:00', '2015-04-02 11:07:42+02:00'],
            # invalid date
            'active.max': ['2015-05-99T15:25'],
            # too long URL
            'url': [(2049 * 'x')],
            # too long URL substring
            'url.sub': [(2049 * 'x')],
            # too long label in a domain name
            'fqdn': ['www.test.org,www.ołówekkkkkkkkkkkkkkkkkkkkkkkkkkk'
                     'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk'
                     'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk.EXAMPLĘ.com'],
        })
        with self.assertRaises(ParamValueCleaningError) as cm:
            self.ds.clean_param_dict(given_dict)
        exc = cm.exception
        self.assertEqual(sorted(exc.error_info_seq), sorted([
            ('confidence', 'INVALID', ANY),
            ('ip', '333.101.102.103', ANY),
            ('ip.net', '100.101.102.103/33', ANY),
            ('ip.net', '333.2.3.4/1', ANY),
            ('cc', '!!', ANY),
            ('dip', ANY, ANY),
            ('asn', ANY, ANY),
            ('dport', ANY, ANY),
            ('time.min', '2014-04-01 61:61:61+02:00', ANY),
            ('time.max', ['2015-04-01 01:07:42+02:00', '2015-04-02 11:07:42+02:00'], ANY),
            ('active.max', '2015-05-99T15:25', ANY),
            ('url', ANY, ANY),
            ('url.sub', ANY, ANY),
            ('fqdn', ANY, ANY),
        ]))
        self.assertTrue(all(
            (
                isinstance(info[1], str) or (
                    isinstance(info[1], list) and
                    info[1] and
                    all(isinstance(it, str) for it in info[1]))
            ) and isinstance(info[2], Exception)
            for info in exc.error_info_seq))


class TestAllSearchableDataSpec_param_field_specs(
        AllSearchableParamCleanMixin,
        MixInProvidingTestMethodsFor__param_field_specs,
        unittest.TestCase):
    pass


class TestAllSearchableDataSpecSubclass_clean_param_dict(
        SubclassParamCleanMixin,
        TestAllSearchableDataSpec_clean_param_dict):
    """
    Like TestAllSearchableDataSpec_clean_param_dict
    but for an AllSearchableDataSpec subclass.
    """

    def test_several_invalid_values(self):
        given_dict = self._given_dict(**{
            'id': ['aaaaa', 'bbb'],         # 'aaaaa' is too long
            'confidence': ['high', 'medium', 'INVALID'],
            'dport': ['1234'],             # the number is too low
            'url.sub': [101 * 'x'],         # too long
            'singular': ['xyz', 'abc'],     # multiple values of single-value-only param
        })
        with self.assertRaises(ParamValueCleaningError) as cm:
            self.ds.clean_param_dict(given_dict)
        exc = cm.exception
        self.assertEqual(sorted(exc.error_info_seq), sorted([
            ('id', 'aaaaa', ANY),
            ('confidence', 'INVALID', ANY),
            ('dport', '1234', ANY),
            ('url.sub', 101 * 'x', ANY),
            ('singular', ['xyz', 'abc'], ANY),
        ]))
        self.assertTrue(all(
            (
                isinstance(info[1], str) or (
                    isinstance(info[1], list) and
                    info[1] and
                    all(isinstance(it, str) for it in info[1]))
            ) and isinstance(info[2], Exception)
            for info in exc.error_info_seq))


class TestAllSearchableDataSpecSubclass_param_field_specs(
        SubclassParamCleanMixin,
        TestAllSearchableDataSpec_param_field_specs):
    """
    Like TestAllSearchableDataSpec_param_field_specs
    but for an AllSearchableDataSpec subclass.
    """


#
# Result-fields-related:

class TestDataSpec_clean_result_dict(ResultCleanMixin, unittest.TestCase):

    def test_valid(self):
        given_dict = self._given_dict()
        cleaned = self.ds.clean_result_dict(given_dict)
        expected_cleaned = self._cleaned_dict()
        self.assertEqualIncludingTypes(cleaned, expected_cleaned)

    def test_valid_ignoring_some_keys(self):
        given_dict = self._given_dict(address='badvalue', illegal='spam')
        cleaned = self.ds.clean_result_dict(
            given_dict,
            ignored_keys=['address', 'illegal'])
        expected_cleaned = self._cleaned_dict(address=self.DEL)
        self.assertEqualIncludingTypes(cleaned, expected_cleaned)

    def test_illegal_keys(self):
        self._test_illegal_keys(self.ds.clean_result_dict)

    def test_missing_keys(self):
        self._test_missing_keys(self.ds.clean_result_dict)

    def test_invalid_value__source_too_long(self):
        given_dict = self._given_dict(
            source='some.otherrrrrrrrrrrrrrrrrrrrrrr' + 'x')
        with self.assertRaises(ResultValueCleaningError) as cm:
            self.ds.clean_result_dict(given_dict)
        exc = cm.exception
        self.assertEqual(exc.error_info_seq, [
            ('source', 'some.otherrrrrrrrrrrrrrrrrrrrrrrx', ANY),
        ])
        self.assertIsInstance(exc.error_info_seq[0][2], Exception)

    def test_several_invalid_values(self):
        given_dict = self._given_dict(**{
            # not in enum set
            'confidence': 'INVALID',
            'address': [
                {
                    # invalid IPv4 (333 > 255)
                    'ip': b'333.101.102.103',
                }
            ],
            # IP does not stard with an anonymized octet
            'adip': '10.20.30.40',
            # too big number
            'dport': 65536,
            # not a valid date + time specification
            'time': b'2014-04-01 25:30:22',
            # too long URL
            'url': (2049 * b'x'),
            # too long label in a domain name
            'fqdn': 'www.test.org,www.ołówekkkkkkkkkkkkkkkkkkkkkkkkkkk'
                    'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk'
                    'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk.EXAMPLĘ.com',
            # not an MD5 hex-digest
            'md5': 'aaa',
        })
        with self.assertRaises(ResultValueCleaningError) as cm:
            self.ds.clean_result_dict(given_dict)
        exc = cm.exception
        self.assertEqual(sorted(exc.error_info_seq), sorted([
            ('confidence', 'INVALID', ANY),
            ('address', [{'ip': b'333.101.102.103'}], ANY),
            ('adip', ANY, ANY),
            ('dport', ANY, ANY),
            ('time', ANY, ANY),
            ('url', ANY, ANY),
            ('fqdn', ANY, ANY),
            ('md5', ANY, ANY),
        ]))
        self.assertTrue(all(isinstance(info[2], Exception)
                            for info in exc.error_info_seq))


@expand
class TestDataSpec_result_field_specs(ResultCleanMixin, unittest.TestCase):

    @for_various_result_types_of__filter_by_which
    def test_all(self):
        field_specs = self.ds.result_field_specs()
        self._test_field_specs(
            field_specs,
            expected_keys=self.keys)

    @for_various_result_types_of__filter_by_which
    def test_required(self):
        field_specs = self.ds.result_field_specs('required')
        self._test_field_specs(
            field_specs,
            expected_keys=self.required_keys)

    @for_various_result_types_of__filter_by_which
    def test_optional(self):
        field_specs = self.ds.result_field_specs('optional')
        self._test_field_specs(
            field_specs,
            expected_keys=(self.optional_keys))


class TestDataSpecSubclass_clean_result_dict(SubclassResultCleanMixin,
                                             TestDataSpec_clean_result_dict):
    """Like TestDataSpec_clean_result_dict but for a DataSpec subclass."""

    def test_several_invalid_values(self):
        given_dict = self._given_dict(**{
            'id': 'aaaaa',            # 'aaaaa' is too long
            'justnew': b'xyz\xdd,123',  # non-UTF-8 value
            # too long label in domain name:
            'fqdn': ('www.ołówekkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk'
                      'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk'
                      'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk.EXAMPLĘ.com'),
        })
        with self.assertRaises(ResultValueCleaningError) as cm:
            self.ds.clean_result_dict(given_dict)
        exc = cm.exception
        self.assertEqual(sorted(exc.error_info_seq), sorted([
            ('id', 'aaaaa', ANY),
            ('justnew', b'xyz\xdd,123', ANY),
            ('fqdn', ANY, ANY),
        ]))
        self.assertTrue(all(isinstance(info[2], Exception)
                            for info in exc.error_info_seq))


class TestDataSpecSubclass_result_field_specs(SubclassResultCleanMixin,
                                              TestDataSpec_result_field_specs):
    """Like TestDataSpec_result_field_specs but for a DataSpec subclass."""


#
# Others:

class TestDataSpecSubclass__field_custom_info(SubclassMixinBase,
                                              unittest.TestCase):

    base_data_spec_class = DataSpec

    def _selftest_assertions(self):
        pass

    def test(self):
        self.assertEqual(self.ds.url.custom_info, dict(
            tralala=dict(ham='spam'),
        ))

    def test_ext(self):
        class AnotherDataSpec(self.get_data_spec_class()):
            url = Ext(                       # extended
                custom_info=Ext(             #  extended
                    tralala=Ext(             #   extended
                        blabla=123,
                    ),
                    foo='bar',
                ),
            )
        ads = AnotherDataSpec()
        self.assertEqual(ads.url.custom_info, dict(
            tralala=dict(
                ham='spam',
                blabla=123,
            ),
            foo='bar',
        ))

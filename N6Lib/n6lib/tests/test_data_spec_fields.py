# Copyright (c) 2013-2021 NASK. All rights reserved.

import unittest

from unittest_expander import (
    expand,
    foreach,
)

import n6lib.data_spec.fields as n6_fields
import n6sdk.data_spec.fields as sdk_fields
import n6sdk.tests.test_data_spec_fields as sdk_tests
from n6lib.common_helpers import as_bytes
from n6sdk.exceptions import FieldValueError
from n6sdk.tests.test_data_spec_fields import (
    FieldTestMixin,
    case,
)



#
# Auxiliary constants
#

NAMES_OF_FIELD_CLASSES_CORRELATED_WITH_SDK_ONES = frozenset([
    'FieldForN6',
    'AddressFieldForN6',
    'AnonymizedIPv4FieldForN6',
    'ASNFieldForN6',
    'CCFieldForN6',
    'DateTimeFieldForN6',
    'DictResultFieldForN6',
    'DomainNameFieldForN6',
    'DomainNameSubstringFieldForN6',
    'EmailSimplifiedFieldForN6',
    'FlagFieldForN6',
    'HexDigestFieldForN6',
    'IBANSimplifiedFieldForN6',
    'IntegerFieldForN6',
    'IPv4FieldForN6',
    'IPv4NetFieldForN6',
    'ListOfDictsFieldForN6',
    'MD5FieldForN6',
    'PortFieldForN6',
    'SHA1FieldForN6',
    'SHA256FieldForN6',
    'SourceFieldForN6',
    'URLFieldForN6',
    'URLSubstringFieldForN6',
    'UnicodeFieldForN6',
    'UnicodeEnumFieldForN6',
    'UnicodeLimitedFieldForN6',
    'UnicodeRegexFieldForN6',
])

NAMES_OF_N6_SPECIFIC_FIELD_CLASSES = frozenset([
    '_ClientOrgIdFieldForN6',
    '_InsideCritURLFieldForN6',
    '_ListOfInsideCritURLsFieldForN6',
    'ClientFieldForN6',
    'URLBase64FieldForN6',
    'URLsMatchedFieldForN6',
    'SomeUnicodeFieldForN6',
    'SomeUnicodeListFieldForN6',
    'SomeFieldForN6',
    'EnrichedFieldForN6',
])

assert not (
    NAMES_OF_FIELD_CLASSES_CORRELATED_WITH_SDK_ONES &
    NAMES_OF_N6_SPECIFIC_FIELD_CLASSES)

ALL_NAMES_OF_FIELD_CLASSES_FOR_N6 = (
    NAMES_OF_FIELD_CLASSES_CORRELATED_WITH_SDK_ONES |
    NAMES_OF_N6_SPECIFIC_FIELD_CLASSES)



#
# Various helpers
#

def _make_sdk_based_case_cls(field_cls_name):
    field_cls = getattr(n6_fields, field_cls_name)
    corresponding_sdk_name = field_cls_name[:-len('ForN6')]
    sdk_test_cls = getattr(sdk_tests, 'Test' + corresponding_sdk_name)
    assert sdk_test_cls.__name__ == 'Test' + corresponding_sdk_name, 'bug in the test'

    class test_cls(sdk_test_cls):
        CLASS = field_cls

    test_cls.__name__ = test_cls_name = sdk_test_cls.__name__ + 'ForN6'
    return test_cls_name, test_cls



#
# Actual tests
#

@expand
class TestFieldTypes(unittest.TestCase):

    def test_basic_consistency(self):
        all_field_classes_for_n6 = {
            name: getattr(n6_fields, name)
            for name in ALL_NAMES_OF_FIELD_CLASSES_FOR_N6}
        self.assertEqual(all_field_classes_for_n6, {
            name: field_cls
            for name, field_cls in vars(n6_fields).items()
            if name.endswith('FieldForN6')})
        for name, field_cls in all_field_classes_for_n6.items():
            self.assertIsInstance(field_cls, type)
            self.assertEqual(field_cls.__name__, name)


    @foreach(ALL_NAMES_OF_FIELD_CLASSES_FOR_N6)
    def test_method_resolution_order(self, field_cls_name):
        assert field_cls_name.endswith('FieldForN6'), 'bug in the test'
        field_cls = getattr(n6_fields, field_cls_name)
        mro = field_cls.__mro__
        assert mro[0] is field_cls, 'bug in the test'
        assert mro[-1] is object, 'bug in the test'
        index_of_FieldForN6 = mro.index(n6_fields.FieldForN6)
        index_of_Field = mro.index(sdk_fields.Field)
        self.assertEqual(index_of_Field, index_of_FieldForN6 + 1)


    @foreach(NAMES_OF_FIELD_CLASSES_CORRELATED_WITH_SDK_ONES)
    def test_correlation_with_sdk_classes(self, field_cls_name):
        assert field_cls_name.endswith('FieldForN6'), 'bug in the test'
        field_cls = getattr(n6_fields, field_cls_name)
        corresponding_sdk_name = field_cls_name[:-len('ForN6')]
        corresponding_sdk_cls = getattr(sdk_fields, corresponding_sdk_name)
        self.assertEqual(corresponding_sdk_cls.__name__, corresponding_sdk_name)
        self.assertTrue(issubclass(corresponding_sdk_cls, sdk_fields.Field))
        self.assertTrue(issubclass(field_cls, corresponding_sdk_cls))


#
# Tests of n6lib versions of field classes defined in SDK

# ugly hack but saves a lot of redundant typing :-)
globals().update(
    _make_sdk_based_case_cls(name)
    for name in NAMES_OF_FIELD_CLASSES_CORRELATED_WITH_SDK_ONES
    # the SDK field classes `Field` and `DictResultField` do not have
    # dedicated test classes within the SDK test suite:
    if name not in ('FieldForN6', 'DictResultFieldForN6'))


#
# Tests of n6lib-specific field classes

### TODO:

# class TestClientFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.ClientFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...


class TestURLBase64FieldForN6(FieldTestMixin, unittest.TestCase):

    CLASS = n6_fields.URLBase64FieldForN6

    def cases__clean_param_value(self):
        yield case(
            given='http://www.test.pl',
            expected=FieldValueError,
        )
        yield case(
            given=u'HTtp://www.test.pl/cgi-bin/foo.pl?',
            expected=FieldValueError,
        )
        yield case(
            given='aHRUUDovL3d3dy50ZXN0LnBs',
            expected=b'htTP://www.test.pl',
        )
        yield case(
            given='aHRUUDovL3d3dy50ZXN0LnBs\r\n',  # with trailing `\r\n`
            expected=b'htTP://www.test.pl',
        )
        yield case(
            given='aHRUUDovL3d3dy50ZXN0LnBs%0D%0A',  # with trailing `\r\n`, %-encoded
            expected=b'htTP://www.test.pl',
        )
        yield case(
            given='aHRUUDovL3d3dy50ZXN0LnBs%250D%250A',  # with trailing `\r\n`, 2 x %-encoded
            expected=b'htTP://www.test.pl',
        )
        yield case(
            given='aHRUUDovL3d3dy50ZXN0LnBs%25250D%25250A',  # with trailing `\r\n`, 3 x %-encoded
            expected=b'htTP://www.test.pl',
        )
        yield case(
            given=u'SFR0cDovL3d3dy50ZXN0LnBsL2NnaS1iaW4vZm9vLnBsPw==',
            expected=b'HTtp://www.test.pl/cgi-bin/foo.pl?',
        )
        yield case(
            given=u'aHR0cDovL3d3dy50ZXN0LcSHLnBsL2NnaS9iaW4vZm9vLnBsP2RlYnVnPTEmaWQ9MTIz',
            expected=as_bytes('http://www.test-ć.pl/cgi/bin/foo.pl?debug=1&id=123'),
        )
        yield case(
            given=(
                'aHR0cDovL3d3dy5URVNULcSGLnBsL2NnaS1iaW4vYmFyLnBsP21vZGU9YnJvd3NlJm'
                'FtcDtkZWJ1Zz0lMjAxMjMmYW1wO2lkPWstJTVE'),
            expected=as_bytes(
                'http://www.TEST-Ć.pl/cgi-bin/bar.pl?mode=browse&amp;'
                'debug=%20123&amp;id=k-%5D'),
        )
        yield case(
            given='aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci_dP3E9z4DFk8SZwqnDn-KGkDMjdHJhbGFsYQk=',
            expected=(
                b'http://t\xc4\x99st.pl/f\xc3\xb3\xc3\xb3/Bar/\xdd'
                b'?q=\xcf\x80\xc5\x93\xc4\x99\xc2\xa9\xc3\x9f\xe2\x86\x903#tralala\t'),
        )
        # the same but encoded with standard Base64 (not the required URL-safe-Base64)
        yield case(
            given=u'aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci/dP3E9z4DFk8SZwqnDn+KGkDMjdHJhbGFsYQk=',
            expected=FieldValueError,
        )
        yield case(
            given=u'aHR0cDovL3Rlc3QucGw=',
            expected=b'http://test.pl',
        )
        # the same with redundant padding
        yield case(
            given='aHR0cDovL3Rlc3QucGw==',
            expected=b'http://test.pl',
        )
        yield case(
            given=u'aHR0cDovL3Rlc3QucGw===',
            expected=b'http://test.pl',
        )
        # the same with redundant padding and ignored characters after it
        yield case(
            given='aHR0cDovL3Rlc3QucGw===abcdef',
            expected=b'http://test.pl',
        )
        yield case(
            given=u'aHR0cDovL3Rlc3QucGw=========abcdef',
            expected=b'http://test.pl',
        )
        # the same with redundant padding and illegal characters after it
        yield case(
            given='aHR0cDovL3Rlc3QucGw===ąć/',
            expected=FieldValueError,
        )
        yield case(
            given=u'aHR0cDovL3Rlc3QucGw=========ąć/',
            expected=FieldValueError,
        )
        # the same with missing padding
        yield case(
            given=u'aHR0cDovL3Rlc3QucGw',
            expected=FieldValueError,
        )
        yield case(
            given=(
                'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
                '_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg=='),
            expected=as_bytes(
                'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        )
        # the same with additional %-encoding:
        yield case(
            given=(
                'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
                '_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg%3D%3D'),
            expected=as_bytes(
                'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        )
        # the same with 2 x additional %-encoding (2nd is overzealous and lowercase-based):
        yield case(
            given=(
                'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%48%41'
                '%5fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%2dKJoMKywrMNCg%253D%253D'),
            expected=as_bytes(
                'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        )
        # the same with 3 x additional %-encoding (2nd is overzealous and lowercase-based):
        yield case(
            given=(
                'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%2548%2541'
                '%255fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%252dKJoMKywrMNCg%25253D%25253D'),
            expected=as_bytes(
                'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        )
        yield case(
            given='',
            expected=FieldValueError,
        )
        # containing non-UTF-8 bytes
        yield case(
            given='aHR0cHM6Ly9kZN3u',
            expected=b'https://dd\xdd\xee',
        )
        # as UTF-8 with low surrogates already encoded
        yield case(
            given='aHR0cHM6Ly9kZO2zne2zrg==',
            expected=as_bytes('https://dd\udcdd\udcee'),
        )
        # the `%` character not being part of %-encoded stuff
        yield case(
            given='%AZ',
            expected=FieldValueError,
        )
        yield case(
            given='aHR0cDovL3Rlc3QucGw=%a',
            expected=FieldValueError,
        )

    def cases__clean_result_value(self):
        yield case(
            given='whatever',
            expected=TypeError,
        )
        ### TODO later? uncomment and adjust these test cases to the new implementation...
        # yield case(
        #     given=b'http://www.test.pl',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=u'HTtp://www.test.pl/cgi-bin/foo.pl?',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=b'aHRUUDovL3d3dy50ZXN0LnBs',
        #     expected=u'htTP://www.test.pl',
        # )
        # yield case(
        #     given=u'SFR0cDovL3d3dy50ZXN0LnBsL2NnaS1iaW4vZm9vLnBsPw==',
        #     expected=u'HTtp://www.test.pl/cgi-bin/foo.pl?',
        # )
        # yield case(
        #     given=b'aHR0cDovL3d3dy50ZXN0LcSHLnBsL2NnaS9iaW4vZm9vLnBsP2RlYnVnPTEmaWQ9MTIz',
        #     expected=u'http://www.test-ć.pl/cgi/bin/foo.pl?debug=1&id=123',
        # )
        # yield case(
        #     given=u'aHR0cDovL3d3dy50ZXN0LcSHLnBsL2NnaS9iaW4vZm9vLnBsP2RlYnVnPTEmaWQ9MTIz',
        #     expected=u'http://www.test-ć.pl/cgi/bin/foo.pl?debug=1&id=123',
        # )
        # yield case(
        #     given=(b'aHR0cDovL3d3dy5URVNULcSGLnBsL2NnaS1iaW4vYmFyLnBsP21vZGU9YnJvd3NlJm'
        #            b'FtcDtkZWJ1Zz0lMjAxMjMmYW1wO2lkPWstJTVE'),
        #     expected=(u'http://www.TEST-Ć.pl/cgi-bin/bar.pl?mode=browse&amp;'
        #               u'debug=%20123&amp;id=k-%5D'),
        # )
        # yield case(
        #     given=(u'aHR0cDovL3d3dy5URVNULcSGLnBsL2NnaS1iaW4vYmFyLnBsP21vZGU9YnJvd3NlJm'
        #            u'FtcDtkZWJ1Zz0lMjAxMjMmYW1wO2lkPWstJTVE'),
        #     expected=(u'http://www.TEST-Ć.pl/cgi-bin/bar.pl?mode=browse&amp;'
        #               u'debug=%20123&amp;id=k-%5D'),
        # )
        # yield case(
        #     given=b'aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci_dP3E9z4DFk8SZwqnDn-KGkDMjdHJhbGFsYQk=',
        #     expected=u'http://tęst.pl/fóó/Bar/\udcdd?q=πœę©ß←3#tralala\t',
        # )
        # yield case(
        #     given=u'aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci_dP3E9z4DFk8SZwqnDn-KGkDMjdHJhbGFsYQk=',
        #     expected=u'http://tęst.pl/fóó/Bar/\udcdd?q=πœę©ß←3#tralala\t',
        # )
        # # the same but encoded with standard Base64 (not the required URL-safe-Base64)
        # yield case(
        #     given=b'aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci/dP3E9z4DFk8SZwqnDn+KGkDMjdHJhbGFsYQk=',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=u'aHR0cDovL3TEmXN0LnBsL2bDs8OzL0Jhci/dP3E9z4DFk8SZwqnDn+KGkDMjdHJhbGFsYQk=',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=b'aHR0cDovL3Rlc3QucGw=',
        #     expected=u'http://test.pl',
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw=',
        #     expected=u'http://test.pl',
        # )
        # # the same with redundant padding
        # yield case(
        #     given=b'aHR0cDovL3Rlc3QucGw==',
        #     expected=u'http://test.pl',
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw===',
        #     expected=u'http://test.pl',
        # )
        # # the same with redundant padding and ignored characters after it
        # yield case(
        #     given=b'aHR0cDovL3Rlc3QucGw===abcdef',
        #     expected=u'http://test.pl',
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw=========abcdef',
        #     expected=u'http://test.pl',
        # )
        # # the same with redundant padding and illegal characters after it
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw===ąć/'.encode('utf-8'),
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw=========ąć/',
        #     expected=FieldValueError,
        # )
        # # the same with missing padding
        # yield case(
        #     given=b'aHR0cDovL3Rlc3QucGw',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=(b'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
        #            b'_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg=='),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # yield case(
        #     given=(u'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
        #            u'_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg=='),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # # the same with additional %-encoding:
        # yield case(
        #     given=(b'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
        #            b'_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg%3D%3D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # yield case(
        #     given=(u'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5waHA'
        #            u'_cT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI-KJoMKywrMNCg%3D%3D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # # the same with 2 x additional %-encoding (2nd is overzealous and lowercase-based):
        # yield case(
        #     given=(b'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%48%41'
        #            b'%5fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%2dKJoMKywrMNCg%253D%253D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # yield case(
        #     given=(u'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%48%41'
        #            u'%5fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%2dKJoMKywrMNCg%253D%253D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # # the same with 3 x additional %-encoding (2nd is overzealous and lowercase-based):
        # yield case(
        #     given=(b'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%2548%2541'
        #            b'%255fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%252dKJoMKywrMNCg%25253D%25253D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # yield case(
        #     given=(u'aHR0cDovL2V4YW1wbGUubmV0L3NlYXJjaC5wa%2548%2541'
        #            u'%255fcT3OtM65zrHPhs6_z4HOtc-EzrnOus-Mz4IhI%252dKJoMKywrMNCg%25253D%25253D'),
        #     expected=(u'http://example.net/search.php?q=διαφορετικός!#≠²³\r\n'),
        # )
        # yield case(
        #     given=b'',
        #     expected=u'',
        # )
        # yield case(
        #     given=u'',
        #     expected=u'',
        # )
        # # containing non-UTF-8 characters (-> to low surrogates)
        # yield case(
        #     given=b'aHR0cHM6Ly9kZN3u',
        #     expected=u'https://dd\udcdd\udcee',
        # )
        # yield case(
        #     given=u'aHR0cHM6Ly9kZN3u',
        #     expected=u'https://dd\udcdd\udcee',
        # )
        # # as UTF-8 with low surrogates already encoded
        # yield case(
        #     given=b'aHR0cHM6Ly9kZO2zne2zrg==',
        #     expected=u'https://dd\udcdd\udcee',
        # )
        # yield case(
        #     given=u'aHR0cHM6Ly9kZO2zne2zrg==',
        #     expected=u'https://dd\udcdd\udcee',
        # )
        # # the `%` character not being part of %-encoded stuff
        # yield case(
        #     given=b'%AZ',
        #     expected=FieldValueError,
        # )
        # yield case(
        #     given=u'aHR0cDovL3Rlc3QucGw=%a',
        #     expected=FieldValueError,
        # )
        # # incorrect type
        # yield case(
        #     given=123,
        #     expected=TypeError,
        # )
        # yield case(
        #     given=None,
        #     expected=TypeError,
        # )


# class TestURLsMatchedFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.URLsMatchedFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...


# class TestSomeUnicodeFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.SomeUnicodeFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...


# class TestSomeUnicodeListFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.SomeUnicodeListFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...


# class TestSomeFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.SomeFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...


# class TestEnrichedFieldForN6(FieldTestMixin, unittest.TestCase):

#     CLASS = n6_fields.EnrichedFieldForN6

#     def cases__clean_param_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...

#     def cases__clean_result_value(self):
#         ...
#         yield case(
#             given='',
#             expected=TypeError,
#         )
#         ...



if __name__ == '__main__':
    unittest.main()

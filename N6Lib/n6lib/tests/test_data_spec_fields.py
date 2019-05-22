# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest

from unittest_expander import (
    expand,
    foreach,
)

import n6lib.data_spec.fields as n6_fields
import n6sdk.data_spec.fields as sdk_fields
import n6sdk.tests.test_data_spec_fields as sdk_tests
#from n6sdk.tests.test_data_spec_fields import (
#    FieldTestMixin,
#    case,
#)



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

def _make_sdk_based_test_cls(field_cls_name):
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
            for name, field_cls in vars(n6_fields).iteritems()
            if name.endswith('FieldForN6')})
        for name, field_cls in all_field_classes_for_n6.iteritems():
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
    _make_sdk_based_test_cls(name)
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
#         for c in self.cases__clean_param_value():
#             yield c
#         ...


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
#         for c in self.cases__clean_param_value():
#             yield c
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
#         for c in self.cases__clean_param_value():
#             yield c
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
#         for c in self.cases__clean_param_value():
#             yield c
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
#         for c in self.cases__clean_param_value():
#             yield c
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
#         for c in self.cases__clean_param_value():
#             yield c
#         ...



if __name__ == '__main__':
    unittest.main()

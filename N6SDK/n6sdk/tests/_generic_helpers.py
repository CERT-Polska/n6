# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections.abc as collections_abc
import unittest.mock as mock


class TestCaseMixin(object):

    def assertEqualIncludingTypes(self, first, second, msg=None):
        self.assertEqual(first, second, msg=msg)
        if first is not mock.ANY and second is not mock.ANY:
            self.assertIs(type(first), type(second),
                          'type of {!a} ({}) is not type of {!a} ({})'
                          .format(first, type(first), second, type(second)))
        if (isinstance(first, collections_abc.Sequence)
              and not isinstance(first, (bytes, bytearray, str))):
            for val1, val2 in zip(first, second):
                self.assertEqualIncludingTypes(val1, val2)
        elif isinstance(first, collections_abc.Set):
            for val1, val2 in zip(sorted(first, key=self._safe_sort_key),
                                  sorted(second, key=self._safe_sort_key)):
                self.assertEqualIncludingTypes(val1, val2)
        elif isinstance(first, collections_abc.Mapping):
            for key1, key2 in zip(sorted(first.keys(), key=self._safe_sort_key),
                                  sorted(second.keys(), key=self._safe_sort_key)):
                self.assertEqualIncludingTypes(key1, key2)
            for key in first:
                self.assertEqualIncludingTypes(first[key], second[key])

    @staticmethod
    def _safe_sort_key(obj):
        # when sorting, using this function as the `key` argument
        # prevents -- practically always -- from ordering values of
        # types that are incompatible in terms of ordering
        t = type(obj)
        return t.__name__, id(t), obj


class _CustomSetMixin(object):

    def __init__(self, it):
        self._elements = set(it)

    def __contains__(self, value):
        return value in self._elements

    def __iter__(self):
        return iter(self._elements)

    def __len__(self):
        return len(self._elements)


class CustomImmutableSet(_CustomSetMixin, collections_abc.Set):
    pass


class CustomMutableSet(_CustomSetMixin, collections_abc.MutableSet):

    def add(self, value):
        self._elements.add(value)

    def discard(self, value):
        self._elements.discard(value)

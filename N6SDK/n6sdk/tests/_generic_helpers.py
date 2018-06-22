# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 NASK. All rights reserved.


import collections


class TestCaseMixin(object):

    def assertEqualIncludingTypes(self, first, second, msg=None):
        self.assertEqual(first, second)
        self.assertIs(type(first), type(second),
                      'type of {!r} ({}) is not type of {!r} ({})'
                      .format(first, type(first), second, type(second)))
        if isinstance(first, collections.Sequence) and not isinstance(first, basestring):
            for val1, val2 in zip(first, second):
                self.assertEqualIncludingTypes(val1, val2)
        elif isinstance(first, collections.Set):
            for val1, val2 in zip(sorted(first, key=self._safe_sort_key),
                                  sorted(second, key=self._safe_sort_key)):
                self.assertEqualIncludingTypes(val1, val2)
        elif isinstance(first, collections.Mapping):
            for key1, key2 in zip(sorted(first.iterkeys(), key=self._safe_sort_key),
                                  sorted(second.iterkeys(), key=self._safe_sort_key)):
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


class CustomImmutableSet(_CustomSetMixin, collections.Set):
    pass


class CustomMutableSet(_CustomSetMixin, collections.MutableSet):

    def add(self, value):
        self._elements.add(value)

    def discard(self, value):
        self._elements.discard(value)

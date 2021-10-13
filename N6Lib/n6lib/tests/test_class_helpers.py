# Copyright (c) 2013-2021 NASK. All rights reserved.

import unittest

from n6lib.class_helpers import all_subclasses, attr_repr


class Test__all_subclasses(unittest.TestCase):

    def test(self):
        class Z(object): pass
        class Y(object): pass
        class X(Z): pass
        class XY(X, Y): pass
        class XZ(X, Z): pass
        class YZ(Y, Z): pass
        class XYZ_A(X, Y, Z): pass
        class XYZ_B(X, Y, Z): pass
        class XYZ_A1(XYZ_A): pass
        class XYZ_A2(XYZ_A): pass
        class XYZ_A12(XYZ_A1, XYZ_A2): pass
        class XYZ_A1_AB(XYZ_A1, XYZ_A, XYZ_B): pass
        class XYZ_XZ_A1(XZ, XYZ_A1): pass
        class XYZ_XZ_A12(XZ, XYZ_A12): pass
        class XYZ_XZ_A1_AB(XYZ_XZ_A1, XYZ_A1_AB): pass

        self.assertEqual(all_subclasses(Z),
                         {X, XY, XZ, YZ, XYZ_A, XYZ_B,
                          XYZ_A1, XYZ_A2, XYZ_A12, XYZ_A1_AB,
                          XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(Y),
                         {XY, YZ, XYZ_A, XYZ_B,
                          XYZ_A1, XYZ_A2, XYZ_A12, XYZ_A1_AB,
                          XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(X),
                         {XY, XZ, XYZ_A, XYZ_B,
                          XYZ_A1, XYZ_A2, XYZ_A12, XYZ_A1_AB,
                          XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XY),
                         set())

        self.assertEqual(all_subclasses(XZ),
                         {XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(YZ),
                         set())

        self.assertEqual(all_subclasses(XYZ_A),
                         {XYZ_A1, XYZ_A2, XYZ_A12, XYZ_A1_AB,
                          XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XYZ_B),
                         {XYZ_A1_AB, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XYZ_A1),
                         {XYZ_A12, XYZ_A1_AB,
                          XYZ_XZ_A1, XYZ_XZ_A12, XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XYZ_A2),
                         {XYZ_A12, XYZ_XZ_A12})

        self.assertEqual(all_subclasses(XYZ_A12),
                         {XYZ_XZ_A12})

        self.assertEqual(all_subclasses(XYZ_A1_AB),
                         {XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XYZ_XZ_A1),
                         {XYZ_XZ_A1_AB})

        self.assertEqual(all_subclasses(XYZ_XZ_A1_AB),
                         set())


class Test__attr_repr(unittest.TestCase):

    def test(self):
        class Foo(object):
            a = 'aaa'
            foo = 'foooo'
            __repr__ = attr_repr('a')

        class Spam(Foo):
            __repr__ = attr_repr('bar', 'foo', 'spam', 'ham')

            spam = 42
            ham = 43
            blabla = 'blablaaaa'

            def __init__(self):
                self.ham = 44
                self.bar = 'bar'
                self.huhuhu = 'huhuhuuuu'

        f = Foo()
        self.assertEqual(repr(f), "<Test__attr_repr.test.<locals>"
                                  ".Foo a='aaa'>")

        s = Spam()
        self.assertEqual(repr(s),
                         "<Test__attr_repr.test.<locals>"
                         ".Spam bar='bar', foo='foooo', spam=42, ham=44>")

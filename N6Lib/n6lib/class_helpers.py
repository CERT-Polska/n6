# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import functools
import sys
import types

# for backward-compatibility and/or for convenience, the `AsciiMixIn`
# class (imported from n6sdk.encoding_helpers) as well as the
# singleton() and attr_required() decorators (imported from
# n6sdk.class_helpers) are also accessible via this module
from n6sdk.encoding_helpers import AsciiMixIn
from n6sdk.class_helpers import (
    singleton,
    attr_required,
)



ORDINARY_MAGIC_METHOD_NAMES = frozenset({
    '__call__',
    '__getattr__',
    '__lt__', '__le__', '__gt__', '__ge__', '__eq__', '__ne__', '__hash__',
    '__getitem__', '__setitem__', '__delitem__', '__contains__', '__missing__',
    '__iter__', '__len__', '__reversed__',
    '__str__', '__format__',
    '__enter__', '__exit__',
    '__complex__', '__int__', '__float__', '__index__',
    '__trunc__', '__divmod__', '__rdivmod__', '__neg__', '__pos__', '__abs__',
    '__invert__',
    '__and__', '__xor__', '__or__',
    '__add__', '__sub__', '__mul__', '__floordiv__', '__truediv__', '__pow__',
    '__mod__', '__lshift__', '__rshift__',
    '__iand__', '__ixor__', '__ior__',
    '__iadd__', '__isub__', '__imul__', '__ifloordiv__', '__itruediv__', '__ipow__',
    '__imod__', '__ilshift__', '__irshift__',
    '__rand__', '__rxor__', '__ror__',
    '__radd__', '__rsub__', '__rmul__', '__rfloordiv__', '__rtruediv__', '__rpow__',
    '__rmod__', '__rlshift__', '__rrshift__',
    '__reduce__', '__reduce_ex__',
    '__getnewargs__', '__getstate__', '__setstate__',
} | (
        {
            '__bool__', '__next__',
            '__length_hint__',
            '__bytes__', '__fspath__',
            '__round__', '__floor__', '__ceil__',
            '__matmul__', '__imatmul__', '__rmatmul__',
            '__getnewargs_ex__',
        } if sys.version_info[0] >= 3
        else {
            '__nonzero__', 'next',
            '__cmp__', '__coerce__',
            '__getslice__', '__setslice__',
            '__unicode__', '__long__',
            '__oct__', '__hex__',
            '__div__', '__idiv__', '__rdiv__',
            '__getinitargs__',
        }
    )
)
DIAGNOSTIC_MAGIC_METHOD_NAMES = frozenset({
    '__repr__', '__dir__', '__sizeof__',
})
ATTR_ACCESS_SHADOWING_MAGIC_METHOD_NAMES = frozenset({
    # (note: '__getattr__' is not here because it is a non-intrusive
    # fallback method, not attribute access *shadowing* method like
    # the following ones)
    '__getattribute__', '__setattr__', '__delattr__',
})
ATTR_DESCRIPTOR_MAGIC_METHOD_NAMES = frozenset({
    '__get__', '__set__', '__delete__',
} | (
        {'__set_name__'} if sys.version_info[0] >= 3
        else frozenset()
    )
)
INSTANCE_LIFECYCLE_MAGIC_METHOD_NAMES = frozenset({
    '__new__', '__init__', '__del__',
})
OBSCURE_FLOAT_SPECIFIC_MAGIC_METHOD_NAMES = frozenset({
    '__getformat__', '__setformat__',
})
ASYNC_STUFF_MAGIC_METHOD_NAMES = (
    frozenset({
        '__await__',
        '__aiter__', '__anext__',
        '__aenter__', '__aexit__',
    }) if sys.version_info[0] >= 3
    else frozenset()
)
CLASS_AND_METACLASS_MAGIC_METHOD_NAMES = frozenset({
    '__instancecheck__', '__subclasscheck__',
} | (
        {
            '__init_subclass__', '__subclasses__',
            '__mro_entries__', '__class_getitem__',
            '__prepare__',
        } if sys.version_info[0] >= 3
        else frozenset()
    )
)
ALL_MAGIC_METHOD_NAMES = (ORDINARY_MAGIC_METHOD_NAMES |
                          DIAGNOSTIC_MAGIC_METHOD_NAMES |
                          ATTR_ACCESS_SHADOWING_MAGIC_METHOD_NAMES |
                          ATTR_DESCRIPTOR_MAGIC_METHOD_NAMES |
                          INSTANCE_LIFECYCLE_MAGIC_METHOD_NAMES |
                          OBSCURE_FLOAT_SPECIFIC_MAGIC_METHOD_NAMES |
                          ASYNC_STUFF_MAGIC_METHOD_NAMES |
                          CLASS_AND_METACLASS_MAGIC_METHOD_NAMES)



def subclass_with_mixin(mixin_cls, decorated_cls=None):
    """
    Create a subclass of `decorated_cls` with `mixin_cls` mixed-in.

    >>> import abc
    >>> class MixIn(object):
    ...     x = 789
    ...     def m(self):
    ...         return super(MixIn, self).m() + 1
    ...
    >>> @subclass_with_mixin(MixIn)
    ... class C(object):
    ...     __metaclass__ = abc.ABCMeta
    ...     def m(self):
    ...         return 42
    ...
    >>> obj = C()
    >>> obj.m()
    43
    >>> C.x
    789
    >>> C.__mro__  # doctest: +ELLIPSIS
    (<class '...C'>, <class '...MixIn'>, <class '...C'>, <type 'object'>)
    >>> type(C)
    <class 'abc.ABCMeta'>
    """
    if decorated_cls is None:
        return functools.partial(subclass_with_mixin, mixin_cls)
    metaclass = type(decorated_cls)
    name = decorated_cls.__name__
    base_classes = (mixin_cls, decorated_cls)
    attributes = {'__doc__': decorated_cls.__doc__,
                  '__module__': decorated_cls.__module__}
    if '__slots__' in vars(decorated_cls):
        attributes['__slots__'] = ()
    return metaclass(name, base_classes, attributes)


def all_subclasses(cls):
    """
    Return a set of all direct and indirect subclasses of the given class.
    """
    ### IMPORTANT: When modifying this function's code
    #   please update also its copy in N6Core/setup.py
    #   (copied because this function cannot be imported there).
    direct_subclasses = cls.__subclasses__()
    return set(direct_subclasses).union(
            indirect
            for direct in direct_subclasses
                for indirect in all_subclasses(direct))


def attr_repr(*attr_names):
    """
    Make a __repr__() implementation based on given attribute names.

    Any number of positional args:
        Names of instance attributes and/or class attributes.

    Returns:
        A function being the requested __repr__() implementation.

    >>> class A(object):
    ...    __repr__ = attr_repr('x', 'y')
    ...    x = 1
    ...    def __init__(self):
    ...        self.y = 'qwerty'
    >>> a = A()
    >>> a
    <A x=1, y='qwerty'>
    """
    format_repr = ('<{0.__class__.__name__} ' +
                   ', '.join('%s={0.%s!r}' % (name, name)
                             for name in attr_names) +
                   '>').format
    def __repr__(self):
        return format_repr(self)
    return __repr__


def get_class_name(instance_or_class):
    """
    Gen the name of the given class or of the class of the given instance.

    >>> class NewStyle(object): pass
    >>> class OldStyle: pass
    >>> n = NewStyle()
    >>> o = OldStyle()
    >>> get_class_name(NewStyle)
    'NewStyle'
    >>> get_class_name(OldStyle)
    'OldStyle'
    >>> get_class_name(n)
    'NewStyle'
    >>> get_class_name(o)
    'OldStyle'
    """
    return (
        instance_or_class.__name__
        if isinstance(instance_or_class, (type, types.ClassType))
        else instance_or_class.__class__.__name__)


def instance(cls, constructor_args=(), constructor_kwargs=None):
    """
    A class decorator that instantiates the class.

    >>> @instance
    ... class Something(object):
    ...     def __init__(self):
    ...         self.x = 42
    ...     def __getitem__(self, key):
    ...         return key.upper()
    ...
    >>> Something.x
    42
    >>> Something['foo']
    'FOO'
    >>> Something.__class__.__name__
    'Something'

    >>> @instance.initialized_with(43, ham='spam')
    ... class Something2(object):
    ...     def __init__(self, x, ham):
    ...         self.x = x
    ...         self.our_ham = ham
    ...     def __getitem__(self, key):
    ...         return key.upper()
    ...
    >>> Something2.x
    43
    >>> Something2.our_ham
    'spam'
    >>> Something2['foo']
    'FOO'
    >>> Something2.__class__.__name__
    'Something2'
    """
    if constructor_kwargs is None:
        constructor_kwargs = {}
    return cls(*constructor_args, **constructor_kwargs)

def __initialized_with(*constructor_args, **constructor_kwargs):
    return functools.partial(
        instance,
        constructor_args=constructor_args,
        constructor_kwargs=constructor_kwargs)

instance.initialized_with = __initialized_with



if __name__ == "__main__":
    import doctest
    doctest.testmod()

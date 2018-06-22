# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import functools
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

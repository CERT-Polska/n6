# Copyright (c) 2013-2021 NASK. All rights reserved.

import re

# For backward-compatibility and/or convenience, the `AsciiMixIn` class,
# imported from n6sdk.encoding_helpers, as well as the a few decorators
# and helpers imported from n6sdk.class_helpers, are also accessible via
# this module.
from n6sdk.encoding_helpers import AsciiMixIn
from n6sdk.class_helpers import (
    singleton,
    attr_required,
    is_seq,
    is_seq_or_set,
)



ORDINARY_MAGIC_METHOD_NAMES = frozenset({
    '__call__',
    '__getattr__',
    '__set_name__',
    '__enter__', '__exit__',
    '__str__', '__format__',
    '__bytes__', '__fspath__',
    '__bool__',
    '__len__', '__length_hint__',
    '__next__', '__iter__', '__reversed__',
    '__getitem__', '__setitem__', '__delitem__', '__contains__', '__missing__',
    '__hash__',
    '__eq__', '__ne__',
    '__lt__', '__le__', '__gt__', '__ge__',
    '__complex__', '__int__', '__float__', '__index__',
    '__trunc__', '__round__', '__floor__', '__ceil__',
    '__divmod__', '__rdivmod__',
    '__neg__', '__pos__', '__abs__',
    '__invert__',
    '__and__', '__or__', '__xor__',
    '__add__', '__sub__', '__mul__', '__floordiv__', '__truediv__',
    '__pow__', '__mod__', '__matmul__',
    '__lshift__', '__rshift__',
    '__iand__', '__ior__', '__ixor__',
    '__iadd__', '__isub__', '__imul__', '__ifloordiv__', '__itruediv__',
    '__ipow__', '__imod__', '__imatmul__',
    '__ilshift__', '__irshift__',
    '__rand__', '__ror__', '__rxor__',
    '__radd__', '__rsub__', '__rmul__', '__rfloordiv__', '__rtruediv__',
    '__rpow__', '__rmod__', '__rmatmul__',
    '__rlshift__', '__rrshift__',
    '__reduce__', '__reduce_ex__',
    '__getnewargs__', '__getnewargs_ex__', '__getstate__', '__setstate__',
})
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
})
INSTANCE_LIFECYCLE_MAGIC_METHOD_NAMES = frozenset({
    '__new__', '__init__', '__del__',
})
OBSCURE_FLOAT_SPECIFIC_MAGIC_METHOD_NAMES = frozenset({
    '__getformat__', '__setformat__',
})
ASYNC_STUFF_MAGIC_METHOD_NAMES = frozenset({
    '__await__',
    '__aiter__', '__anext__',
    '__aenter__', '__aexit__',
})
CLASS_AND_METACLASS_MAGIC_METHOD_NAMES = frozenset({
    '__instancecheck__', '__subclasscheck__',
    '__init_subclass__', '__subclasses__',
    '__mro_entries__', '__class_getitem__',
    '__prepare__',
})
ALL_MAGIC_METHOD_NAMES = (ORDINARY_MAGIC_METHOD_NAMES |
                          DIAGNOSTIC_MAGIC_METHOD_NAMES |
                          ATTR_ACCESS_SHADOWING_MAGIC_METHOD_NAMES |
                          ATTR_DESCRIPTOR_MAGIC_METHOD_NAMES |
                          INSTANCE_LIFECYCLE_MAGIC_METHOD_NAMES |
                          OBSCURE_FLOAT_SPECIFIC_MAGIC_METHOD_NAMES |
                          ASYNC_STUFF_MAGIC_METHOD_NAMES |
                          CLASS_AND_METACLASS_MAGIC_METHOD_NAMES)



class FalseIfOwnerClassNameMatchesRegex(object):

    """
    >>> class A(object):
    ...     a = FalseIfOwnerClassNameMatchesRegex('A')
    ...     b = FalseIfOwnerClassNameMatchesRegex('B')
    ...
    >>> A.a
    False
    >>> A().a
    False
    >>> A.b
    True
    >>> A().b
    True
    >>> class B(A):
    ...     pass
    ...
    >>> B.a
    True
    >>> B().a
    True
    >>> B.b
    False
    >>> B().b
    False
    """

    def __init__(self, regex):
        if isinstance(regex, str):
            regex = re.compile(regex)
        if not hasattr(regex, 'search') or not hasattr(regex, 'match'):
            raise TypeError('{!a} does not look like a regex object')
        self.__regex = regex

    def __get__(self, instance, owner=None):
        if owner is None:
            return True
        assert hasattr(owner, '__name__')
        return not self.__regex.search(owner.__name__)



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
    format_repr = ('<{0.__class__.__qualname__} ' +
                   ', '.join('%s={0.%s!r}' % (name, name)
                             for name in attr_names) +
                   '>').format
    format_repr_fallback = object.__repr__

    def __repr__(self):
        # noinspection PyBroadException
        try:
            return format_repr(self)
        except Exception:
            return format_repr_fallback(self)

    return __repr__


def properly_negate_eq(self, other):
    """
    A general-purpose implementation of the `__ne__()` (*not equal*)
    special method that makes use of an existing implementation of the
    `__eq__()` (*equal*) special method, negating its result unless the
    result is `NotImplemented` (then just returning `NotImplemented`).

    That is the same what Python 3's `object.__ne__()` does, so -- in
    Python 3 -- when you implement equality comparisons in your class
    you typically need to provide the `__eq__()` method and nothing
    more. However, occasionally -- quite likely when subclasses, mixins
    and all that inheritance-related mess come into play -- it may be
    necessary to explicitly provide the behavior described above by
    assigning this function to the `__ne__` attribute of your class, to
    override some other implementation of `__ne__()` (provided by some
    class that contributes to the inheritance hierarchy) which shadowed
    the original `object.__ne__()`.

    Example use:

        class MyFancyEqualityMixin(object):

            def __eq__(self, other):
                if ...some checks and decision...:
                    return ...True|False... # We say: "OK, the answer is..."
                return NotImplemented       # We say: "Don't know. Maybe `other` knows?"

            __ne__ = properly_negate_eq     # Negate __eq__() but say "Don't know..." if necessary.
    """
    # Note: After migration to Python 3 we can replace the following
    # code just with: `return object.__ne__(self, other)`.
    equal = self.__eq__(other)
    if equal is NotImplemented:
        return equal
    return not equal


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
        if isinstance(instance_or_class, type)
        else instance_or_class.__class__.__name__)



if __name__ == "__main__":
    import doctest
    doctest.testmod()

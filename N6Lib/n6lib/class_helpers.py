# Copyright (c) 2013-2022 NASK. All rights reserved.

import re
from collections.abc import (
    Iterator,
    Sequence,
    Set,
)
from typing import (
    Any,
    ClassVar,
    Final,
    Optional,
    Protocol,
)

from n6lib.typing_helpers import T
from n6sdk.encoding_helpers import ascii_str

# For backward-compatibility and/or convenience, the `AsciiMixIn` class,
# imported from `n6sdk.encoding_helpers`, as well as a few decorators
# and helpers imported from `n6sdk.class_helpers`, are also accessible
# via this module.
from n6sdk.encoding_helpers import AsciiMixIn   # noqa
from n6sdk.class_helpers import (
    singleton,      # noqa
    attr_required,  # noqa
    is_seq,         # noqa
    is_seq_or_set,  # noqa
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



class CombinedWithSuper:

    r"""
    A descriptor that makes it possible to *extend* class attributes
    along the inheritance hierarchy -- much like methods can be
    *extended* by using `super()`.

    ***

    For example, the value of some attribute (let's name it `attr`) of
    a certain class (let's name it `Root`) is extended by the value of
    the same-named attribute of a subclass of `Root` (let's name it `A`);
    the resultant *combined value* is what you actually obtain when you
    attempt to get the attribute from the subclass (or from an instance
    of it)... It is easier to show it than to explain it:

    >>> class Root:
    ...     attr = CombinedWithSuper({'x': 3, 'y': 4, 'z': 5, 'root': '!'})
    ...
    >>> class A(Root):
    ...     attr = CombinedWithSuper({'x': 33, 'y': 44, 'a': 'AA'})
    ...
    >>> Root.attr
    {'x': 3, 'y': 4, 'z': 5, 'root': '!'}
    >>> A.attr
    {'x': 33, 'y': 44, 'z': 5, 'root': '!', 'a': 'AA'}

    As noted above, access via an instance is also possible. The results
    are the same as above:

    >>> Root().attr
    {'x': 3, 'y': 4, 'z': 5, 'root': '!'}
    >>> A().attr
    {'x': 33, 'y': 44, 'z': 5, 'root': '!', 'a': 'AA'}

    One obvious question is: *how exactly are the declared attribute
    values combined?* The answer is that, by default, the `|` operator
    is used to do this (note: in the case of two dicts that operator
    creates a fresh dict updated with their contents, and in the case of
    `int` or `enum.Flag`-like objects it combines them using *bitwise
    OR*), *unless* the values being combined are instances of a
    *sequence* type (such as `list`, `tuple`, `str`, `bytes`, etc.) --
    then the `+` operator is applied, e.g.:

    >>> class AltRoot:
    ...     attr = CombinedWithSuper([1, 2, 3])
    ...
    >>> class AltSubclass(AltRoot):
    ...     attr = CombinedWithSuper([4, 5, 6])
    ...
    >>> AltRoot.attr
    [1, 2, 3]
    >>> AltSubclass.attr
    [1, 2, 3, 4, 5, 6]

    Any exception (e.g., `TypeError`) from the combining operation just
    bubbles up:

    >>> class Incompatible(A):
    ...     attr = CombinedWithSuper({'spam', 'ham'})  # (`<dict> | <set>` must cause `TypeError`)
    ...
    >>> Incompatible.attr     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    `A.attr` is a dict and `Incompatible.attr` is a set; they cannot be
    combined using `|`, so `TypeError` has been raised.

    Obviously, we get the same behavior when accessing the attribute via
    an instance:

    >>> Incompatible().attr   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    ***

    Continuing our story, let us (completely indepentently from `A`)
    extend the same attribute in another subclass of `Root`, name it
    `B`:

    >>> class B(Root):
    ...     attr = CombinedWithSuper({'x': 333, 'z': 555, 'b': 'BBB'})
    ...
    >>> B.attr
    {'x': 333, 'y': 4, 'z': 555, 'root': '!', 'b': 'BBB'}

    And now the best part... Multiple inheritance -- when the
    [diamond problem](https://en.wikipedia.org/wiki/Multiple_inheritance#The_diamond_problem)
    is involved -- is supported perfectly, in the same way it
    is supported when you extend methods using `super()`!

    >>> class BA(B, A):
    ...     attr = CombinedWithSuper({'x': 33333333})
    ...
    >>> BA.attr
    {'x': 33333333, 'y': 44, 'z': 555, 'root': '!', 'a': 'AA', 'b': 'BBB'}

    Note that `A` and `B`, with their respective attributes, do not need
    to know anything about each other.

    Of course, we obtain the same result when accessing the attribute
    via an instance:

    >>> BA().attr
    {'x': 33333333, 'y': 44, 'z': 555, 'root': '!', 'a': 'AA', 'b': 'BBB'}

    ***

    When creating a `CombinedWithSuper` descriptor object, it is also
    possible to omit the value argument -- and still the values of the
    superclasses' `attr` will be properly combined:

    >>> class BA2(B, A):
    ...     attr = CombinedWithSuper()
    ...
    >>> BA2.attr
    {'x': 333, 'y': 44, 'z': 555, 'root': '!', 'a': 'AA', 'b': 'BBB'}

    In fact, we would get the same result just by refraining from
    setting `BA2.attr` (`attr`s from the superclasses would still be
    properly combined in the same way as above):

    >>> class BA2(B, A):
    ...     pass
    ...
    >>> BA2.attr
    {'x': 333, 'y': 44, 'z': 555, 'root': '!', 'a': 'AA', 'b': 'BBB'}

    ***

    But is it possible to *customize how exactly all that value
    extension (combination) is done?*

    Yes, it is... Please read on.

    ***

    The `CombinedWithSuper` constructor accepts the following arguments.

    Args/kwargs:

        `value` (optional):

            The value wrapped in `CombinedWithSuper(...)`; it will
            be set as the `value` field of this `CombinedWithSuper`
            instance; also referred to as the *local value*.

            Whenever the `CombinedWithSuper` instance's `__get__()` is
            invoked as a part of (class- or instance-) attribute lookup,
            this `value` (aka *local value*) is used to "extend" the
            *value from super* (i.e., the value got from the superclass
            attribute lookup, see below), or just becomes the result of
            that invocation if there is no *value from super*.

            The `value` argument is optional. If not given, the `value`
            field is set to a special marker, `CombinedWithSuper.MISSING`,
            which denotes the lack of a value (then attribute lookups
            will behave as if the attribute this `CombinedWithSuper`
            instance refers to did not exist, so that the *value from
            super* will be the lookup result, if present; see below...).

    Kwargs (*keyword-only*):

        `value_combiner` (optional):

            A *value combiner*, that is, a 2-argument callable -- to
            be called in the `CombinedWithSuper.__get__()` descriptor
            method to obtain the *combined value* of the attribute the
            descriptor refers to. The resultant *combined value* is
            supposed to be derived from the two positional arguments
            passed in to the *value combiner*:

            * (1) *value from super* -- the attribute value obtained
              from the superclass (with a `super()`-based lookup, by the
              `CombinedWithSuper.__get__()`'s machinery);

            * (2) *local value* -- the value wrapped in this instance
              of `CombinedWithSuper` (see the constructor's argument
              `value`, described earlier).

            How exactly these two arguments are combined by a particular
            *value combiner* depends solely on its implementation. One
            *important advice:* a value combiner should *never* mutate
            (modify in-place) any of the given argument values.

            It is guaranteed that neither of these two arguments is
            `CombinedWithSuper.MISSING` -- this is the condition for
            a *value combiner* to be called at all. (More precisely:
            if both the *value from super* and the *local value* are
            missing then `AttributeError` is raised -- and, obviously,
            the *value combiner* is *not* called. If only one of those
            values is missing then the other one becomes the `__get__()`'s
            return value, still *without* calling the *value combiner*.)

            If a *value combiner* succeeds, the result becomes
            the return value of the corresponding invocation of
            `CombinedWithSuper.__get__()`, *unless* the result is
            the `CombinedWithSuper.MISSING` marker (see below).

            If a *value combiner* is unable to combine certain pair of
            values (in particular, because of what their types are), it
            should raise an exception (for example, `TypeError`).

            A *value combiner* can simulate the lack of the handled
            attribute -- by returning the `CombinedWithSuper.MISSING`
            marker object; that will make the relevant `__get__()` call
            raise `AttributeError` (important: it should *not* be raised
            by the *value combiner* itself -- doing so would cause
            `RuntimeError`). Note that an `AttributeError` propagated
            from a `CombinedWithSuper`'s `__get__()` indicates that
            the attribute is missing *from the point of view of this
            particular class* in the inheritance hierarchy; `__get__()`
            of a `CombinedWithSuper` instance attached to some subclass
            may still silence this error.

            Any other exception will just bubble up, breaking the whole
            attribute lookup operation.

            See also further parts of the docs (in particular, the
            relevant code examples), and also the docs of the methods
            `get_resultant_value()` and `get_combined_value()`.

            The default value of `value_combiner` (accessible directly
            as `CombinedWithSuper.default_value_combiner`) is a callable
            that tries to combine its arguments (*value from super* and
            *local value*) by using:

            * the `+` operator -- *if* both arguments are instances
              (real or "virtual") of `collections.abc.Sequence` (note
              that, even though many `Sequence` subtypes -- such as
              `list`, `tuple`, `str`, `bytes`, etc. -- support the `+`
              operator, the `Sequence` abstract base class itself does
              not guarantee that support);

            * the `|` operator -- in any other case.

            Good candidates for your custom `value_combiner` are various
            binary operators (such as `operator.or_`, `operator.add`,
            etc.), and any other callables able to take two positional
            arguments and provide some kind of merger/fusion/combination
            of them, *without* modifying the original argument objects
            (an example of a function that meets these requirements is
            `n6lib.common_helpers.merge_mappings_recursively()`).

    ***

    Each instance of `CombinedWithSuper` has the following public
    fields (typically, they are not needed outside of the code of
    `CombinedWithSuper`, but ocasionally may appear to be useful).

    All of them *should be treated as read-only ones* (i.e., even
    if that is technically possible, their values should *not* be
    overwritten or deleted by any code outside of `CombinedWithSuper`
    and its subclasses, if any).

    * `fixed_owner` -- initially set to `None` but, typically,
      immediately after creation of the owning class (i.e., the
      class whose attribute is this instance of `CombinedWithSuper`),
      the field is automatically set to that class, thanks to the
      mechanism of `__set_name__()` (see:
      https://docs.python.org/3/reference/datamodel.html#object.__set_name__)).

    * `name` -- a string being the name of the attribute this
      `CombinedWithSuper` instance refers to; initially set to `None`
      but, typically, immediately after creation of the owning class
      (aka *fixed owner*), the field is automatically set to the
      relevant attribute name, also thanks to the mechanism of
      `__set_name__()`.

    * `value` -- *either* the value wrapped in this `CombinedWithSuper`
      instance, if the instance was created by calling the constructor
      with that value (aka *local value*) as the `value` argument; *or*
      the `CombinedWithSuper.MISSING` marker, if the instance was
      created by calling the constructor without passing the `value`
      argument (meaning that there is no *local value*; see the earlier
      description of the constructor's argument `value`).

    * `value_combiner` -- the callable passed to the constructor, or the
      default *value combiner* if nothing was passed; see the earlier
      description of the constructor's argument `value_combiner`.

    >>> descriptor = CombinedWithSuper(42)
    >>> isinstance(descriptor, CombinedWithSuper)
    True
    >>> descriptor
    <unready CombinedWithSuper(...)>
    >>> descriptor.fixed_owner is None
    True
    >>> descriptor.name is None
    True
    >>> descriptor.value
    42
    >>> descriptor.value_combiner is CombinedWithSuper.default_value_combiner
    True
    >>> class C:
    ...     # Note: typically, *unlike here*, you invoke the
    ...     # `CombinedWithSuper` constructor directly in the
    ...     # body of the owning class (rather than using a
    ...     # `CombinedWithSuper` instance created earlier).
    ...     foo = descriptor
    ...
    >>> C.__dict__['foo'] is descriptor
    True
    >>> descriptor
    <C.foo's CombinedWithSuper(...)>
    >>> descriptor.fixed_owner is C
    True
    >>> descriptor.name
    'foo'
    >>> descriptor.value
    42
    >>> descriptor.value_combiner is CombinedWithSuper.default_value_combiner
    True
    >>> C.foo
    42
    >>> C().foo
    42

    >>> def my_custom_value_combiner(a, b):
    ...     return f'{a} <-> {b}'
    ...
    >>> class D(C):
    ...     nothing = CombinedWithSuper()  # (here: no wrapped value)
    ...     foo = CombinedWithSuper('abcd', value_combiner=my_custom_value_combiner)
    ...
    >>> descriptor2 = D.__dict__['nothing']
    >>> descriptor2
    <D.nothing's CombinedWithSuper(...)>
    >>> descriptor2.fixed_owner is D
    True
    >>> descriptor2.name
    'nothing'
    >>> descriptor2.value
    CombinedWithSuper.MISSING
    >>> descriptor2.value_combiner is CombinedWithSuper.default_value_combiner
    True
    >>> hasattr(D, 'nothing')
    False
    >>> hasattr(D(), 'nothing')
    False
    >>> descriptor3 = D.__dict__['foo']
    >>> descriptor3
    <D.foo's CombinedWithSuper(...)>
    >>> descriptor3.fixed_owner is D
    True
    >>> descriptor3.name
    'foo'
    >>> descriptor3.value
    'abcd'
    >>> descriptor3.value_combiner is my_custom_value_combiner
    True
    >>> D.foo
    '42 <-> abcd'
    >>> D().foo
    '42 <-> abcd'

    ***

    A few notes on the machinery engaged in `CombinedWithSuper`-powered
    attribute lookups (you can skip these notes if you are not interested
    in such details):

    * the special method `__get__()` is always (for all Python
      descriptors) invoked with these two positional arguments:

      * (1) `owner_inst` -- the object on which the whole lookup has
        been initiated (then its type is always `owner`, see below), or
        `None` if the lookup is a *class attribute* one (i.e., not an
        *instance attribute* one);

      * (2) `owner` -- the class on which the whole lookup has been
        initiated; you can consider it as *always* present and *always*
        being a real class, i.e., *never* being `None` or `type(None)`
        (technically speaking, it *may* be omitted in some circumstances
        when the lookup is an *instance attribute* one, but then the
        `CombinedWithSuper`'s implementation of `__get__()` sets it to
        the type of `owner_inst`);

    * each of the earlier examples of `BA.attr`/`BA().attr` lookups
      involved exactly four instances of `CombinedWithSuper` (they were
      assigned to: `Root.attr`, `A.attr`, `B.attr` and `BA.attr`), and
      exactly four invocations of the `__get__()` method, one *per each*
      of those instances; note, however, that all four invocations shared
      *the same* `owner` (which was the "outermost" class, that is, `BA`)
      and *the same* `owner_inst` (which was the involved instance of
      `BA` in the case of an *instance attribute* lookup, or just `None`
      in the case of a *class attribute* lookup);

    * in the earlier examples of `BA.attr`/`BA().attr` lookups, each of
      the four involved instances of `CombinedWithSuper` (assigned to:
      `Root.attr`, `A.attr`, `B.attr`, `BA.attr`) had the `fixed_owner`
      field set to the corresponding class, respectively: `Root`, `A`,
      `B` or `BA` (see also: the earlier description of the `fixed_owner`
      field).

    * the relation between `owner` and `fixed_owner` is always such
      that the former is a (direct or indirect) subclass of the latter
      (including -- but not limited to -- the case when they are the
      same class);

    * the *value from super* (see the earlier description of the
      constructor's argument `value_combiner`...) is obtained by
      getting the relevant attribute from the *super object* (see
      the next bullet point) in the `CombinedWithSuper`'s method
      `get_value_from_super()`;

    * the *super object* is created by calling `super(fixed_owner, owner)`
      or `super(fixed_owner, owner_inst)` (the latter if the lookup is an
      *instance attribute* one), and then passed as the `super_obj`
      keyword argument to the `CombinedWithSuper`'s methods:
      `get_value_from_super()`, `get_resultant_value()` and
      `get_combined_value()` (see their docs).

    See also:

    * https://docs.python.org/3/reference/datamodel.html#implementing-descriptors
    * https://rhettinger.wordpress.com/2011/05/26/super-considered-super/

    ***

    For an advanced customization you may want to create a subclass
    of `CombinedWithSuper` -- to extend:

    * some (or all) of the methods: `get_value_from_super()`,
      `get_resultant_value()` and `get_combined_value()` (see
      their docs), and/or

    * some (or all) of the special methods this class implements
      (`__init__()`, `__repr__()`, `__set_name__()` and, last but
      not least, `__get__()`).

    ***

    A few more complex (and somewhat contrived) examples:

    >>> import contextlib, operator, re
    >>> class _DebugHelper:
    ...
    ...     _INITIAL_INDENT = 0
    ...     _SPACES_PER_INDENT = 2
    ...     _SEPARATOR_LINE = '-' * 16
    ...
    ...     def __init__(self):
    ...         self._cur_indent = self._INITIAL_INDENT
    ...         self._log_lines = []
    ...
    ...     def is_unindented(self):
    ...         return self._cur_indent == self._INITIAL_INDENT
    ...
    ...     @contextlib.contextmanager
    ...     def indent(self):
    ...         self._cur_indent += self._SPACES_PER_INDENT
    ...         try:
    ...             yield
    ...         finally:
    ...             self._cur_indent -= self._SPACES_PER_INDENT
    ...             if self.is_unindented():
    ...                 self._log_lines.append(self._SEPARATOR_LINE)
    ...
    ...     def log(self, s):
    ...         indent_string = ' ' * self._cur_indent
    ...         self._log_lines.append(indent_string + s)
    ...
    ...     def dump(self):
    ...         if self._log_lines:
    ...             self._log_lines.insert(0, self._SEPARATOR_LINE)
    ...         self._log_lines.insert(0, '[ BEGIN ]')
    ...         self._log_lines.append('[ END ]')
    ...         print('\n'.join(self._log_lines))
    ...         self._log_lines.clear()
    ...
    >>> debug = _DebugHelper()
    >>> class MyCombinedWithSuper(CombinedWithSuper):
    ...
    ...     def __get__(self, owner_inst, owner_if_not_omitted=None):
    ...         # The only expected (correct) invocations of `__get__(...)` are:
    ...         # * `__get__(<owner instance>, <owner class>)`  # <- instance lookup
    ...         # * `__get__(<owner instance>)`                 # <- instance lookup (equivalent)
    ...         # * `__get__(None, <owner class>)`              # <- class lookup
    ...         # (see: https://docs.python.org/3/reference/datamodel.html#object.__get__)
    ...         assert (owner_inst is not None
    ...                 or owner_if_not_omitted is not None), 'incorrect `__get__(...)` call!'
    ...         if debug.is_unindented():
    ...             lookup_owner_obj = (owner_inst if owner_inst is not None   # <- instance lookup
    ...                                 else owner_if_not_omitted)             # <- class lookup
    ...             debug.log(f'* getting `{lookup_owner_obj!r}.{self.name}`')
    ...         debug.log(f'└ calling '
    ...                   f'`{self!r}.__get__({owner_inst!r}, {owner_if_not_omitted!r})`')
    ...         with debug.indent():
    ...             try:
    ...                 return super().__get__(owner_inst, owner_if_not_omitted)
    ...             except BaseException as exc:
    ...                 debug.log(f'-> exception `{type(exc).__qualname__}`')
    ...                 raise
    ...
    ...     def get_value_from_super(self, *, super_obj, **rest_kwargs):
    ...         super_args_repr = f'{super_obj.__thisclass__!r}, {super_obj.__self__!r}'  # noqa
    ...         debug.log(f'* getting `super({super_args_repr}).{self.name}`')
    ...         value_from_super = self.MISSING
    ...         error_type = None
    ...         try:
    ...             value_from_super = super().get_value_from_super(super_obj=super_obj,
    ...                                                             **rest_kwargs)
    ...         except AttributeError as exc:
    ...             self._log_values(self.MISSING)
    ...             raise
    ...         else:
    ...             self._log_values(value_from_super)
    ...             return value_from_super
    ...
    ...     def _log_values(self, value_from_super):
    ...         debug.log(f'* no value from super'
    ...                   if value_from_super is self.MISSING
    ...                   else f'* value from super is `{value_from_super!r}`')
    ...         debug.log(f'* no local value'
    ...                   if self.value is self.MISSING
    ...                   else f'* local value is `{self.value!r}`')
    ...
    ...     def get_resultant_value(self, *args, **kwargs):
    ...         resultant_value = super().get_resultant_value(*args, **kwargs)
    ...         debug.log(f'-> `{resultant_value!r}`')
    ...         return resultant_value
    ...
    ...     def get_combined_value(self, *, value_from_super, **rest_kwargs):
    ...         value_combiner_name = getattr(self.value_combiner, '__name__', '<???>')
    ...         debug.log(f'* calling '
    ...                   f'`{value_combiner_name}({value_from_super!r}, {self.value!r})`')
    ...         return super().get_combined_value(value_from_super=value_from_super,
    ...                                           **rest_kwargs)
    ...
    >>> MY_ATTRIBUTE_ERROR_TRIGGER = 'MY_ATTRIBUTE_ERROR_TRIGGER'
    >>> MY_MISSING_TRIGGER = 'MY_MISSING_TRIGGER'
    >>> MY_REPLACE_TRIGGER = 'MY_REPLACE_TRIGGER'
    >>> def my_contrived_combiner(value_from_super, local_value):
    ...     # A value combiner is never called if `value_from_super` or
    ...     # `local_value` is the `CombinedWithSuper.MISSING` marker.
    ...     assert (value_from_super is not CombinedWithSuper.MISSING
    ...             and local_value is not CombinedWithSuper.MISSING)
    ...     if local_value == MY_ATTRIBUTE_ERROR_TRIGGER:
    ...         # Raising `AttributeError` in a value combiner will
    ...         # make `CombinedWithSuper.get_combined_value()` raise
    ...         # `RuntimeError` (see the docs of that method).
    ...         raise AttributeError('ha ha ha!')
    ...     if local_value == MY_MISSING_TRIGGER:
    ...         # Returning the `CombinedWithSuper.MISSING` marker
    ...         # object from a value combiner will make the method
    ...         # `CombinedWithSuper.get_combined_value()` raise
    ...         # `AttributeError` (see the docs of that method).
    ...         return CombinedWithSuper.MISSING
    ...         # ^ Note that an `AttributeError` propagated through
    ...         # `__get__()` of a `CombinedWithSuper` may be *silenced*
    ...         # if the local `CombinedWithSuper` instance is not the
    ...         # outermost one, i.e., if its `fixed_owner` is not the
    ...         # `owner` passed in to `__get__()`, i.e., if `__get__()`
    ...         # has been called as a part of a *superclass lookup*
    ...         # attempted by another instance of `CombinedWithSuper`
    ...         # whose `value` is not the *CombinedWithSuper.MISSING*
    ...         # marker (and whose `fixed_owner` is a subclass of the
    ...         # local `CombinedWithSuper`'s `fixed_owner`).
    ...         # ^ Let's look at some fragments of the code presented
    ...         # below, namely -- those with classes named `I` and `J`
    ...         # (where `J` is a subclass of `I`, and both `I` and `J`
    ...         # have their `li` set to distinct `MyCombinedWithSuper`
    ...         # instances): for example, during the `J.li` lookup an
    ...         # `AttributeError` from `I.li`'s `__get__(None, J)` is
    ...         # silenced by `J.li`'s `__get__(None, J)`.
    ...     if local_value == MY_REPLACE_TRIGGER:
    ...         # No actual combination. Everything is replaced with `[42]`:
    ...         return [42]
    ...     # Actual combination (here: using the `+` operator):
    ...     return value_from_super + local_value
    ...
    >>> class _ShortReprMeta(type):  # (just for shorter class reprs...)
    ...     def __repr__(cls):
    ...         return f'{cls.__qualname__}'
    ...
    >>> class E(metaclass=_ShortReprMeta):
    ...     def __repr__(self):
    ...         # (just for shorter instance reprs...)
    ...         return f'{self.__class__.__qualname__}()'
    ...     # Note: even though here the `li` attribute is *not* wrapped
    ...     # in `CombinedWithSuper(...)`, it can still be extended with
    ...     # `CombinedWithSuper(...)`s in subclasses. However, normally
    ...     # -- for better composability (e.g., with any future mixin
    ...     # classes) and just for simplicity -- it is recommended to
    ...     # consistently wrap all involved values throughout the whole
    ...     # class hierarchy, including such a "root attribute" (without
    ...     # treating it in any special way).
    ...     li = [1, 2]   # (<- it could be set here to `CombinedWithSuper([1, 2])`)
    ...
    >>> class EChild(E):
    ...     pass
    ...
    >>> class F(EChild):
    ...     li = MyCombinedWithSuper([3, 4],
    ...                              value_combiner=my_contrived_combiner)
    ...     some_flag = MyCombinedWithSuper(re.ASCII)       # (no *value combiner* => default one)
    ...
    >>> class FChild(F):
    ...     some_flag = MyCombinedWithSuper(re.IGNORECASE)  # (no *value combiner* => default one)
    ...
    >>> class G(FChild):
    ...     li = MyCombinedWithSuper(value=[5, 6],
    ...                              value_combiner=my_contrived_combiner)
    ...
    >>> E.__mro__ == (E, object)
    True
    >>> F.__mro__ == (F, EChild, E, object)
    True
    >>> G.__mro__ == (G, FChild, F, EChild, E, object)
    True
    >>> [1, 2] == E.li == E().li == EChild.li == EChild().li
    True
    >>> debug.dump()  # (note: nothing logged because E's `li` is *not* a `MyCombinedWithSuper`)
    [ BEGIN ]
    [ END ]
    >>> [1, 2, 3, 4] == F.li == F().li == FChild.li == FChild().li
    True
    >>> [1, 2, 3, 4, 5, 6] == G.li == G().li
    True
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `F.li`
    └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, F)`
      * getting `super(F, F).li`
      * value from super is `[1, 2]`
      * local value is `[3, 4]`
      * calling `my_contrived_combiner([1, 2], [3, 4])`
      -> `[1, 2, 3, 4]`
    ----------------
    * getting `F().li`
    └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(F(), F)`
      * getting `super(F, F()).li`
      * value from super is `[1, 2]`
      * local value is `[3, 4]`
      * calling `my_contrived_combiner([1, 2], [3, 4])`
      -> `[1, 2, 3, 4]`
    ----------------
    * getting `FChild.li`
    └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, FChild)`
      * getting `super(F, FChild).li`
      * value from super is `[1, 2]`
      * local value is `[3, 4]`
      * calling `my_contrived_combiner([1, 2], [3, 4])`
      -> `[1, 2, 3, 4]`
    ----------------
    * getting `FChild().li`
    └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(FChild(), FChild)`
      * getting `super(F, FChild()).li`
      * value from super is `[1, 2]`
      * local value is `[3, 4]`
      * calling `my_contrived_combiner([1, 2], [3, 4])`
      -> `[1, 2, 3, 4]`
    ----------------
    * getting `G.li`
    └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(None, G)`
      * getting `super(G, G).li`
      └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, G)`
        * getting `super(F, G).li`
        * value from super is `[1, 2]`
        * local value is `[3, 4]`
        * calling `my_contrived_combiner([1, 2], [3, 4])`
        -> `[1, 2, 3, 4]`
      * value from super is `[1, 2, 3, 4]`
      * local value is `[5, 6]`
      * calling `my_contrived_combiner([1, 2, 3, 4], [5, 6])`
      -> `[1, 2, 3, 4, 5, 6]`
    ----------------
    * getting `G().li`
    └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(G(), G)`
      * getting `super(G, G()).li`
      └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(G(), G)`
        * getting `super(F, G()).li`
        * value from super is `[1, 2]`
        * local value is `[3, 4]`
        * calling `my_contrived_combiner([1, 2], [3, 4])`
        -> `[1, 2, 3, 4]`
      * value from super is `[1, 2, 3, 4]`
      * local value is `[5, 6]`
      * calling `my_contrived_combiner([1, 2, 3, 4], [5, 6])`
      -> `[1, 2, 3, 4, 5, 6]`
    ----------------
    [ END ]
    >>> (hasattr(E, 'some_flag')
    ...  or hasattr(E(), 'some_flag')
    ...  or hasattr(EChild, 'some_flag')
    ...  or hasattr(EChild(), 'some_flag'))
    False
    >>> debug.dump()  # (E and EChild just do *not* have a `some_flag` attribute)
    [ BEGIN ]
    [ END ]
    >>> re.ASCII == F.some_flag == F().some_flag
    True
    >>> re.ASCII | re.IGNORECASE  \
    ...  == FChild.some_flag == FChild().some_flag == G.some_flag == G().some_flag
    True
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `F.some_flag`
    └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(None, F)`
      * getting `super(F, F).some_flag`
      * no value from super
      * local value is `re.ASCII`
      -> `re.ASCII`
    ----------------
    * getting `F().some_flag`
    └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(F(), F)`
      * getting `super(F, F()).some_flag`
      * no value from super
      * local value is `re.ASCII`
      -> `re.ASCII`
    ----------------
    * getting `FChild.some_flag`
    └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(None, FChild)`
      * getting `super(FChild, FChild).some_flag`
      └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(None, FChild)`
        * getting `super(F, FChild).some_flag`
        * no value from super
        * local value is `re.ASCII`
        -> `re.ASCII`
      * value from super is `re.ASCII`
      * local value is `re.IGNORECASE`
      * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
      -> `re.ASCII|re.IGNORECASE`
    ----------------
    * getting `FChild().some_flag`
    └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(FChild(), FChild)`
      * getting `super(FChild, FChild()).some_flag`
      └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(FChild(), FChild)`
        * getting `super(F, FChild()).some_flag`
        * no value from super
        * local value is `re.ASCII`
        -> `re.ASCII`
      * value from super is `re.ASCII`
      * local value is `re.IGNORECASE`
      * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
      -> `re.ASCII|re.IGNORECASE`
    ----------------
    * getting `G.some_flag`
    └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(None, G)`
      * getting `super(FChild, G).some_flag`
      └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(None, G)`
        * getting `super(F, G).some_flag`
        * no value from super
        * local value is `re.ASCII`
        -> `re.ASCII`
      * value from super is `re.ASCII`
      * local value is `re.IGNORECASE`
      * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
      -> `re.ASCII|re.IGNORECASE`
    ----------------
    * getting `G().some_flag`
    └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(G(), G)`
      * getting `super(FChild, G()).some_flag`
      └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(G(), G)`
        * getting `super(F, G()).some_flag`
        * no value from super
        * local value is `re.ASCII`
        -> `re.ASCII`
      * value from super is `re.ASCII`
      * local value is `re.IGNORECASE`
      * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
      -> `re.ASCII|re.IGNORECASE`
    ----------------
    [ END ]

    And now, again, multiple inheritance (with a "diamond"...):

    >>> class I(EChild):
    ...     li = MyCombinedWithSuper(MY_MISSING_TRIGGER,
    ...                              value_combiner=my_contrived_combiner)
    ...     some_flag = MyCombinedWithSuper()            # (<- no wrapped value, default combiner)
    ...
    >>> class J(I):
    ...     li = MyCombinedWithSuper([123456789],
    ...                              value_combiner=my_contrived_combiner)
    ...
    >>> class K(EChild):
    ...     li = MyCombinedWithSuper(MY_REPLACE_TRIGGER,
    ...                              value_combiner=my_contrived_combiner)
    ...     some_flag = MyCombinedWithSuper(value_combiner=operator.or_)   # (<- no wrapped value)
    ...
    >>> class GK(G, K):
    ...     li = MyCombinedWithSuper([2021, 2022],
    ...                              value_combiner=my_contrived_combiner)
    ...     some_flag = MyCombinedWithSuper(re.VERBOSE,
    ...                                     value_combiner=operator.or_)
    ...
    >>> I.__mro__ == (I, EChild, E, object)
    True
    >>> J.__mro__ == (J, I, EChild, E, object)
    True
    >>> K.__mro__ == (K, EChild, E, object)
    True
    >>> GK.__mro__ == (GK, G, FChild, F, K, EChild, E, object)
    True
    >>> hasattr(I, 'li') or hasattr(I(), 'li')
    False
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `I.li`
    └ calling `<I.li's MyCombinedWithSuper(...)>.__get__(None, I)`
      * getting `super(I, I).li`
      * value from super is `[1, 2]`
      * local value is `'MY_MISSING_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_MISSING_TRIGGER')`
      -> exception `AttributeError`
    ----------------
    * getting `I().li`
    └ calling `<I.li's MyCombinedWithSuper(...)>.__get__(I(), I)`
      * getting `super(I, I()).li`
      * value from super is `[1, 2]`
      * local value is `'MY_MISSING_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_MISSING_TRIGGER')`
      -> exception `AttributeError`
    ----------------
    [ END ]
    >>> [123456789] == J.li == J().li
    True
    >>> [42] == K.li == K().li
    True
    >>> [42, 3, 4, 5, 6, 2021, 2022] == GK.li == GK().li
    True
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `J.li`
    └ calling `<J.li's MyCombinedWithSuper(...)>.__get__(None, J)`
      * getting `super(J, J).li`
      └ calling `<I.li's MyCombinedWithSuper(...)>.__get__(None, J)`
        * getting `super(I, J).li`
        * value from super is `[1, 2]`
        * local value is `'MY_MISSING_TRIGGER'`
        * calling `my_contrived_combiner([1, 2], 'MY_MISSING_TRIGGER')`
        -> exception `AttributeError`
      * no value from super
      * local value is `[123456789]`
      -> `[123456789]`
    ----------------
    * getting `J().li`
    └ calling `<J.li's MyCombinedWithSuper(...)>.__get__(J(), J)`
      * getting `super(J, J()).li`
      └ calling `<I.li's MyCombinedWithSuper(...)>.__get__(J(), J)`
        * getting `super(I, J()).li`
        * value from super is `[1, 2]`
        * local value is `'MY_MISSING_TRIGGER'`
        * calling `my_contrived_combiner([1, 2], 'MY_MISSING_TRIGGER')`
        -> exception `AttributeError`
      * no value from super
      * local value is `[123456789]`
      -> `[123456789]`
    ----------------
    * getting `K.li`
    └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(None, K)`
      * getting `super(K, K).li`
      * value from super is `[1, 2]`
      * local value is `'MY_REPLACE_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
      -> `[42]`
    ----------------
    * getting `K().li`
    └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(K(), K)`
      * getting `super(K, K()).li`
      * value from super is `[1, 2]`
      * local value is `'MY_REPLACE_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
      -> `[42]`
    ----------------
    * getting `GK.li`
    └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(None, GK)`
      * getting `super(GK, GK).li`
      └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(None, GK)`
        * getting `super(G, GK).li`
        └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, GK)`
          * getting `super(F, GK).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(None, GK)`
            * getting `super(K, GK).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[3, 4]`
          * calling `my_contrived_combiner([42], [3, 4])`
          -> `[42, 3, 4]`
        * value from super is `[42, 3, 4]`
        * local value is `[5, 6]`
        * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
        -> `[42, 3, 4, 5, 6]`
      * value from super is `[42, 3, 4, 5, 6]`
      * local value is `[2021, 2022]`
      * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
      -> `[42, 3, 4, 5, 6, 2021, 2022]`
    ----------------
    * getting `GK().li`
    └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
      * getting `super(GK, GK()).li`
      └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
        * getting `super(G, GK()).li`
        └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
          * getting `super(F, GK()).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
            * getting `super(K, GK()).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[3, 4]`
          * calling `my_contrived_combiner([42], [3, 4])`
          -> `[42, 3, 4]`
        * value from super is `[42, 3, 4]`
        * local value is `[5, 6]`
        * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
        -> `[42, 3, 4, 5, 6]`
      * value from super is `[42, 3, 4, 5, 6]`
      * local value is `[2021, 2022]`
      * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
      -> `[42, 3, 4, 5, 6, 2021, 2022]`
    ----------------
    [ END ]
    >>> (hasattr(I, 'some_flag')
    ...  or hasattr(I(), 'some_flag')
    ...  or hasattr(J, 'some_flag')
    ...  or hasattr(J(), 'some_flag')
    ...  or hasattr(K, 'some_flag')
    ...  or hasattr(K(), 'some_flag'))       # [sic]
    False
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `I.some_flag`
    └ calling `<I.some_flag's MyCombinedWithSuper(...)>.__get__(None, I)`
      * getting `super(I, I).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    * getting `I().some_flag`
    └ calling `<I.some_flag's MyCombinedWithSuper(...)>.__get__(I(), I)`
      * getting `super(I, I()).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    * getting `J.some_flag`
    └ calling `<I.some_flag's MyCombinedWithSuper(...)>.__get__(None, J)`
      * getting `super(I, J).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    * getting `J().some_flag`
    └ calling `<I.some_flag's MyCombinedWithSuper(...)>.__get__(J(), J)`
      * getting `super(I, J()).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    * getting `K.some_flag`
    └ calling `<K.some_flag's MyCombinedWithSuper(...)>.__get__(None, K)`
      * getting `super(K, K).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    * getting `K().some_flag`
    └ calling `<K.some_flag's MyCombinedWithSuper(...)>.__get__(K(), K)`
      * getting `super(K, K()).some_flag`
      * no value from super
      * no local value
      -> exception `AttributeError`
    ----------------
    [ END ]
    >>> re.ASCII | re.IGNORECASE | re.VERBOSE == GK.some_flag == GK().some_flag
    True
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `GK.some_flag`
    └ calling `<GK.some_flag's MyCombinedWithSuper(...)>.__get__(None, GK)`
      * getting `super(GK, GK).some_flag`
      └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(None, GK)`
        * getting `super(FChild, GK).some_flag`
        └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(None, GK)`
          * getting `super(F, GK).some_flag`
          └ calling `<K.some_flag's MyCombinedWithSuper(...)>.__get__(None, GK)`
            * getting `super(K, GK).some_flag`
            * no value from super
            * no local value
            -> exception `AttributeError`
          * no value from super
          * local value is `re.ASCII`
          -> `re.ASCII`
        * value from super is `re.ASCII`
        * local value is `re.IGNORECASE`
        * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
        -> `re.ASCII|re.IGNORECASE`
      * value from super is `re.ASCII|re.IGNORECASE`
      * local value is `re.VERBOSE`
      * calling `or_(re.ASCII|re.IGNORECASE, re.VERBOSE)`
      -> `re.ASCII|re.IGNORECASE|re.VERBOSE`
    ----------------
    * getting `GK().some_flag`
    └ calling `<GK.some_flag's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
      * getting `super(GK, GK()).some_flag`
      └ calling `<FChild.some_flag's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
        * getting `super(FChild, GK()).some_flag`
        └ calling `<F.some_flag's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
          * getting `super(F, GK()).some_flag`
          └ calling `<K.some_flag's MyCombinedWithSuper(...)>.__get__(GK(), GK)`
            * getting `super(K, GK()).some_flag`
            * no value from super
            * no local value
            -> exception `AttributeError`
          * no value from super
          * local value is `re.ASCII`
          -> `re.ASCII`
        * value from super is `re.ASCII`
        * local value is `re.IGNORECASE`
        * calling `default_value_combiner(re.ASCII, re.IGNORECASE)`
        -> `re.ASCII|re.IGNORECASE`
      * value from super is `re.ASCII|re.IGNORECASE`
      * local value is `re.VERBOSE`
      * calling `or_(re.ASCII|re.IGNORECASE, re.VERBOSE)`
      -> `re.ASCII|re.IGNORECASE|re.VERBOSE`
    ----------------
    [ END ]

    One special case is that the `CombinedWithSuper.MISSING` marker as a
    *value from super* makes the `get_resultant_value()` method behave
    as if the relevant attribute was not present in any of the super
    classes:

    >>> class L(EChild):
    ...     li = CombinedWithSuper.MISSING
    ...
    >>> class M(L):
    ...     li = MyCombinedWithSuper(987654321)
    ...
    >>> L.__mro__ == (L, EChild, E, object)
    True
    >>> M.__mro__ == (M, L, EChild, E, object)
    True
    >>> CombinedWithSuper.MISSING is L.li is L().li
    True
    >>> debug.dump()
    [ BEGIN ]
    [ END ]
    >>> 987654321 == M.li == M().li
    True
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `M.li`
    └ calling `<M.li's MyCombinedWithSuper(...)>.__get__(None, M)`
      * getting `super(M, M).li`
      * no value from super
      * local value is `987654321`
      -> `987654321`
    ----------------
    * getting `M().li`
    └ calling `<M.li's MyCombinedWithSuper(...)>.__get__(M(), M)`
      * getting `super(M, M()).li`
      * no value from super
      * local value is `987654321`
      -> `987654321`
    ----------------
    [ END ]

    Some exception-related cases:

    >>> class WrongMixin(metaclass=_ShortReprMeta):
    ...     li = MyCombinedWithSuper([123, 456],
    ...                              # (lists do *not* support `|` => expecting `TypeError`)
    ...                              value_combiner=operator.or_)
    ...
    >>> class WrongGK(WrongMixin, GK):
    ...     pass
    ...
    >>> WrongGK.__mro__ == (  # (note: here `WrongMixin` is near the beginning of the MRO)
    ...     WrongGK, WrongMixin, GK, G, FChild, F, K, EChild, E, object)
    True
    >>> WrongGK.li     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> WrongGK().li   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `WrongGK.li`
    └ calling `<WrongMixin.li's MyCombinedWithSuper(...)>.__get__(None, WrongGK)`
      * getting `super(WrongMixin, WrongGK).li`
      └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(None, WrongGK)`
        * getting `super(GK, WrongGK).li`
        └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(None, WrongGK)`
          * getting `super(G, WrongGK).li`
          └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, WrongGK)`
            * getting `super(F, WrongGK).li`
            └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(None, WrongGK)`
              * getting `super(K, WrongGK).li`
              * value from super is `[1, 2]`
              * local value is `'MY_REPLACE_TRIGGER'`
              * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
              -> `[42]`
            * value from super is `[42]`
            * local value is `[3, 4]`
            * calling `my_contrived_combiner([42], [3, 4])`
            -> `[42, 3, 4]`
          * value from super is `[42, 3, 4]`
          * local value is `[5, 6]`
          * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
          -> `[42, 3, 4, 5, 6]`
        * value from super is `[42, 3, 4, 5, 6]`
        * local value is `[2021, 2022]`
        * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
        -> `[42, 3, 4, 5, 6, 2021, 2022]`
      * value from super is `[42, 3, 4, 5, 6, 2021, 2022]`
      * local value is `[123, 456]`
      * calling `or_([42, 3, 4, 5, 6, 2021, 2022], [123, 456])`
      -> exception `TypeError`
    ----------------
    * getting `WrongGK().li`
    └ calling `<WrongMixin.li's MyCombinedWithSuper(...)>.__get__(WrongGK(), WrongGK)`
      * getting `super(WrongMixin, WrongGK()).li`
      └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(WrongGK(), WrongGK)`
        * getting `super(GK, WrongGK()).li`
        └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(WrongGK(), WrongGK)`
          * getting `super(G, WrongGK()).li`
          └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(WrongGK(), WrongGK)`
            * getting `super(F, WrongGK()).li`
            └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(WrongGK(), WrongGK)`
              * getting `super(K, WrongGK()).li`
              * value from super is `[1, 2]`
              * local value is `'MY_REPLACE_TRIGGER'`
              * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
              -> `[42]`
            * value from super is `[42]`
            * local value is `[3, 4]`
            * calling `my_contrived_combiner([42], [3, 4])`
            -> `[42, 3, 4]`
          * value from super is `[42, 3, 4]`
          * local value is `[5, 6]`
          * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
          -> `[42, 3, 4, 5, 6]`
        * value from super is `[42, 3, 4, 5, 6]`
        * local value is `[2021, 2022]`
        * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
        -> `[42, 3, 4, 5, 6, 2021, 2022]`
      * value from super is `[42, 3, 4, 5, 6, 2021, 2022]`
      * local value is `[123, 456]`
      * calling `or_([42, 3, 4, 5, 6, 2021, 2022], [123, 456])`
      -> exception `TypeError`
    ----------------
    [ END ]

    Note, however, that in the example below `WrongMixin.li` is not even
    touched (so its value combiners are never invoked) -- because `E.li`
    is *not* a `CombinedWithSuper`, so `WrongMixin.li` is *shadowed*
    (rather than *extended*) by it:

    >>> class GKThenWrong(GK, WrongMixin):
    ...     pass
    ...
    >>> GKThenWrong.__mro__ == (  # (note: here `WrongMixin` is near the end of the MRO, after `E`)
    ...     GKThenWrong, GK, G, FChild, F, K, EChild, E, WrongMixin, object)
    True
    >>> GKThenWrong.li
    [42, 3, 4, 5, 6, 2021, 2022]
    >>> GKThenWrong().li
    [42, 3, 4, 5, 6, 2021, 2022]
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `GKThenWrong.li`
    └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(None, GKThenWrong)`
      * getting `super(GK, GKThenWrong).li`
      └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(None, GKThenWrong)`
        * getting `super(G, GKThenWrong).li`
        └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, GKThenWrong)`
          * getting `super(F, GKThenWrong).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(None, GKThenWrong)`
            * getting `super(K, GKThenWrong).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[3, 4]`
          * calling `my_contrived_combiner([42], [3, 4])`
          -> `[42, 3, 4]`
        * value from super is `[42, 3, 4]`
        * local value is `[5, 6]`
        * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
        -> `[42, 3, 4, 5, 6]`
      * value from super is `[42, 3, 4, 5, 6]`
      * local value is `[2021, 2022]`
      * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
      -> `[42, 3, 4, 5, 6, 2021, 2022]`
    ----------------
    * getting `GKThenWrong().li`
    └ calling `<GK.li's MyCombinedWithSuper(...)>.__get__(GKThenWrong(), GKThenWrong)`
      * getting `super(GK, GKThenWrong()).li`
      └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(GKThenWrong(), GKThenWrong)`
        * getting `super(G, GKThenWrong()).li`
        └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(GKThenWrong(), GKThenWrong)`
          * getting `super(F, GKThenWrong()).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(GKThenWrong(), GKThenWrong)`
            * getting `super(K, GKThenWrong()).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[3, 4]`
          * calling `my_contrived_combiner([42], [3, 4])`
          -> `[42, 3, 4]`
        * value from super is `[42, 3, 4]`
        * local value is `[5, 6]`
        * calling `my_contrived_combiner([42, 3, 4], [5, 6])`
        -> `[42, 3, 4, 5, 6]`
      * value from super is `[42, 3, 4, 5, 6]`
      * local value is `[2021, 2022]`
      * calling `my_contrived_combiner([42, 3, 4, 5, 6], [2021, 2022])`
      -> `[42, 3, 4, 5, 6, 2021, 2022]`
    ----------------
    [ END ]

    And, below, the `WrongMixin` class is somewhere in the middle of
    `__mro__` of the attribute lookup owner class (`GWrongK`):

    >>> class WrongK(WrongMixin, K):
    ...     pass
    ...
    >>> class GWrongK(G, WrongK):
    ...     pass
    ...
    >>> GWrongK.__mro__ == (
    ...     GWrongK, G, FChild, F, WrongK, WrongMixin, K, EChild, E, object)
    True
    >>> GWrongK.li     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> GWrongK().li   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `GWrongK.li`
    └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(None, GWrongK)`
      * getting `super(G, GWrongK).li`
      └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(None, GWrongK)`
        * getting `super(F, GWrongK).li`
        └ calling `<WrongMixin.li's MyCombinedWithSuper(...)>.__get__(None, GWrongK)`
          * getting `super(WrongMixin, GWrongK).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(None, GWrongK)`
            * getting `super(K, GWrongK).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[123, 456]`
          * calling `or_([42], [123, 456])`
          -> exception `TypeError`
        -> exception `TypeError`
      -> exception `TypeError`
    ----------------
    * getting `GWrongK().li`
    └ calling `<G.li's MyCombinedWithSuper(...)>.__get__(GWrongK(), GWrongK)`
      * getting `super(G, GWrongK()).li`
      └ calling `<F.li's MyCombinedWithSuper(...)>.__get__(GWrongK(), GWrongK)`
        * getting `super(F, GWrongK()).li`
        └ calling `<WrongMixin.li's MyCombinedWithSuper(...)>.__get__(GWrongK(), GWrongK)`
          * getting `super(WrongMixin, GWrongK()).li`
          └ calling `<K.li's MyCombinedWithSuper(...)>.__get__(GWrongK(), GWrongK)`
            * getting `super(K, GWrongK()).li`
            * value from super is `[1, 2]`
            * local value is `'MY_REPLACE_TRIGGER'`
            * calling `my_contrived_combiner([1, 2], 'MY_REPLACE_TRIGGER')`
            -> `[42]`
          * value from super is `[42]`
          * local value is `[123, 456]`
          * calling `or_([42], [123, 456])`
          -> exception `TypeError`
        -> exception `TypeError`
      -> exception `TypeError`
    ----------------
    [ END ]

    A value combiner should not raise `AttributeError`. If it does then
    such an exception is replaced with `RuntimeError`:

    >>> class AlsoWrong(EChild):
    ...     li = MyCombinedWithSuper(MY_ATTRIBUTE_ERROR_TRIGGER,
    ...                              value_combiner=my_contrived_combiner)
    ...
    >>> AlsoWrong.__mro__ == (AlsoWrong, EChild, E, object)
    True
    >>> AlsoWrong.li     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> AlsoWrong().li   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> debug.dump()
    [ BEGIN ]
    ----------------
    * getting `AlsoWrong.li`
    └ calling `<AlsoWrong.li's MyCombinedWithSuper(...)>.__get__(None, AlsoWrong)`
      * getting `super(AlsoWrong, AlsoWrong).li`
      * value from super is `[1, 2]`
      * local value is `'MY_ATTRIBUTE_ERROR_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_ATTRIBUTE_ERROR_TRIGGER')`
      -> exception `RuntimeError`
    ----------------
    * getting `AlsoWrong().li`
    └ calling `<AlsoWrong.li's MyCombinedWithSuper(...)>.__get__(AlsoWrong(), AlsoWrong)`
      * getting `super(AlsoWrong, AlsoWrong()).li`
      * value from super is `[1, 2]`
      * local value is `'MY_ATTRIBUTE_ERROR_TRIGGER'`
      * calling `my_contrived_combiner([1, 2], 'MY_ATTRIBUTE_ERROR_TRIGGER')`
      -> exception `RuntimeError`
    ----------------
    [ END ]
    """


    class __MISSING(object):
        """
        The `CombinedWithSuper.MISSING` marker is used to denote the
        lack of a `CombinedWithSuper`'s `value`.

        See the docs of `CombinedWithSuper` for more information.
        """
        __str__ = __repr__ = lambda self: f'{CombinedWithSuper.__qualname__}.MISSING'

    MISSING: Final = __MISSING()


    class ValueCombiner(Protocol):
        """
        A *value combiner* is a callable invoked to obtain a *combined
        value*, i.e., a value derived from: (1) the *value from super*
        and (2) the *local value* (in the context of execution of
        `CombinedWithSuper`'s `__get__()`). If a *value combiner* is
        unable to combine certain pair of values (e.g., because of their
        types) it should raise an exception (e.g., `TypeError`).

        See the docs of `CombinedWithSuper` for more information.
        """
        def __call__(self, value_from_super, local_value, /) -> Any:
            ...

    @staticmethod
    def default_value_combiner(value_from_super, local_value, /):
        if isinstance(value_from_super, Sequence) and isinstance(local_value, Sequence):
            return value_from_super + local_value  # noqa
        else:
            return value_from_super | local_value


    fixed_owner: type
    name: str
    value: Any
    value_combiner: ValueCombiner

    def __init__(self,
                 value: Any = MISSING,
                 *,
                 value_combiner: ValueCombiner = default_value_combiner.__func__):  # noqa
        self.fixed_owner = None   # noqa   # to be set in `__set_name__()`
        self.name = None          # noqa   # to be set in `__set_name__()`
        self.value = value
        self.value_combiner = value_combiner

    def __repr__(self) -> str:
        qualifier = (f"{self.fixed_owner.__qualname__}.{self.name}'s"
                     if self.fixed_owner is not None and self.name is not None
                     else 'unready')
        stem = f'{self.__class__.__qualname__}(...)'
        return f'<{qualifier} {stem}>'

    def __set_name__(self,
                     fixed_owner: type,
                     name: str,
                     /) -> None:
        self._verify_unready()
        self.fixed_owner = fixed_owner
        self.name = name

    def __get__(self,
                owner_inst: Optional[T],
                owner_if_not_omitted: Optional[type[T]] = None,
                /) -> Any:
        self._verify_ready()
        owner = self._get_verified_owner(owner_inst, owner_if_not_omitted)
        super_obj = self._get_super(owner_inst, owner)
        value_from_super = self.get_value_from_super(
            super_obj=super_obj,
            owner_inst=owner_inst,
            owner=owner)
        return self.get_resultant_value(
            value_from_super=value_from_super,
            super_obj=super_obj,
            owner_inst=owner_inst,
            owner=owner)

    def _verify_unready(self) -> None:
        if self.fixed_owner is not None or self.name is not None:
            raise RuntimeError(
                f'{self!a}.__set_name__('
                f'{self.fixed_owner!a}, {self.name!a}'
                f') already called')

    def _verify_ready(self) -> None:
        if self.fixed_owner is None or self.name is None:
            raise RuntimeError(
                f'{self!a} is not ready '
                f'(`__set_name__()` not called?)')

    def _get_verified_owner(self,
                            owner_inst: Optional[T],
                            owner_if_not_omitted: Optional[type[T]]) -> type[T]:
        if owner_if_not_omitted is None:
            if owner_inst is None:
                raise TypeError(
                    f'incorrect call to {self!a}.__get__() '
                    f'(only None values given)')
            owner = type(owner_inst)
        else:
            owner = owner_if_not_omitted
            if owner is not type(owner_inst) and owner_inst is not None:
                raise TypeError(
                    f'{self!a}.__get__({owner_inst!a}, {owner!a}) '
                    f'is not a correct call because the 1st argument '
                    f'is *not* None *and* the 2nd argument is *not* '
                    f'the type of the 1st argument')
        assert owner is not None
        assert owner is type(owner_inst) or owner_inst is None
        return owner

    def _get_super(self, owner_inst: Optional[T], owner: type[T]) -> super:
        if owner_inst is not None:
            return super(self.fixed_owner, owner_inst)
        else:
            return super(self.fixed_owner, owner)

    def get_value_from_super(self, *,
                             super_obj: super,
                             owner_inst: Optional[T],  # noqa
                             owner: type[T]) -> Any:   # noqa
        """
        Try to get the relevant attribute (i.e., whose name is equal to
        the value of this `CombinedWithSuper` instance's `name` field)
        from the given *super object* (the `super_obj` argument).

        The default implementation of this method behaves as follows:

        * if the operation causes an exception then it is propagated,
          unless it is an `AttributeError` -- if it is, then:

          * if the *local value* is missing (i.e., if this
            `CombinedWithSuper` instance's `value` is the
            `CombinedWithSuper.MISSING` marker) then `AttributeError`
            is raised (propagated);

          * otherwise -- return the `CombinedWithSuper.MISSING` marker
            object (indicating that there is no *value from super* that
            could be combined with the *local value*);

        * if the operation is successful then its result is returned
          (obviously).

        This method is invoked by the `CombinedWithSuper.__get__()`'s
        machinery.

        This method can be extended in subclasses, e.g., to modify or
        enrich the lookup process, possibly taking into account the
        context represented by the rest of the method's arguments:

        * `owner_inst` -- the object on which the whole attribute
           lookup has been initiated, or `None`;

        * `owner` -- the class on which the whole attribute lookup has
           been initiated.

        For more information on these arguments -- see the "A few notes
        on the machinery..." fragment of the docs of this class.
        """
        try:
            return getattr(super_obj, self.name)
        except AttributeError:
            if self.value is self.MISSING:
                # If both *value from super* and *local value*
                # are missing then `AttributeError` is raised.
                raise
            return self.MISSING

    def get_resultant_value(self, *,
                            value_from_super,
                            super_obj: super,
                            owner_inst: Optional[T],
                            owner: type[T]) -> Any:
        """
        Get a value, or raise an exception, that will be
        returned/propagated as the result of the enclosing
        invocation of `__get__()`.

        This method is invoked by the `CombinedWithSuper.__get__()`'s
        machinery (unless an exception from the earlier invocation of
        the `get_value_from_super()` method broke the flow).

        What the default implementation of this method does depends on
        presence of the *value from super* and the *local value*:

        * if both are missing -- i.e., if both `value_from_super` and
          this `CombinedWithSuper` instance's `value` are set to the
          `CombinedWithSuper.MISSING` marker -- then `AttributeError` is
          raised (note that, normally, this case is hardly possible
          because, under such conditions, the default implementation of
          the `get_value_from_super()` method would have already raised
          `AttributeError` -- and then this method would *not* be
          invoked at all);

        * if only `value_from_super` is `CombinedWithSuper.MISSING`
          then this `CombinedWithSuper` instance's `value` (the
          *local value*) is returned;

        * if only this `CombinedWithSuper` instance's `value` is
          `CombinedWithSuper.MISSING` then `value_from_super` is
          returned;

        * if both are present -- i.e., if *neither* `value_from_super`
          *nor* this `CombinedWithSuper` instance's `value` is
          the `CombinedWithSuper.MISSING` marker -- then the
          `get_combined_value()` method is invoked and the result
          of that invocation is returned; any exception from that
          invocation is propagated.

        This method can be extended in subclasses, e.g., to modify or
        enrich preparation of the result, possibly taking into account
        the context represented by the rest of the method's arguments:

        * `super_obj` -- the *super object* used to obtain the given
          *value from super*;

        * `owner_inst` -- the object on which the whole lookup has
           been initiated, or `None`;

        * `owner` -- the class on which the whole lookup has been
           initiated.

        For more information on these arguments -- see the "A few notes
        on the machinery..." fragment of the docs of this class.
        """
        if value_from_super is self.MISSING:
            if self.value is self.MISSING:
                raise AttributeError(
                    f'no value of the {self.name!a} attribute of '
                    f'{owner_inst if owner_inst is not None else owner!a}')
            return self.value
        elif self.value is self.MISSING:
            return value_from_super
        else:
            return self.get_combined_value(
                value_from_super=value_from_super,
                super_obj=super_obj,
                owner_inst=owner_inst,
                owner=owner)

    def get_combined_value(self, *,
                           value_from_super,
                           super_obj: super,  # noqa
                           owner_inst: Optional[T],
                           owner: type[T]) -> Any:
        """
        Try to combine the *value from super* with the *local value* --
        by calling this `CombinedWithSuper` instance's `value_combiner`
        (passing to it the given `value_from_super` argument and this
        `CombinedWithSuper` instance's `value`).

        The default implementation of this method behaves as follows:

        * if the operation causes an exception then it is propagated,
          unless it is an `AttributeError` -- if it is, `RuntimeError`
          is raised (to prevent unnoticed bugs caused by propagation of
          accidental `AttributeError`s);

        * if the operation is successful then its result is returned,
          unless it is the `CombinedWithSuper.MISSING` marker -- if it
          is, `AttributeError` is raised (*not* being replaced with
          `RuntimeError` in such a case).

        This method is invoked by the `get_resultant_value()` method.

        Beware that the default implementation of this method assumes
        that it is invoked *only* if both the *value from super* and the
        *local value* are present, i.e., that it is *never* invoked if
        `value_from_super` *or* this `CombinedWithSuper` instance's
        `value` is set to the `CombinedWithSuper.MISSING` marker.

        This method can be extended in subclasses, e.g., to modify or
        enrich the process of value combination, possibly taking into
        account the context represented by the rest of the method's
        arguments:

        * `super_obj` -- the *super object* used to obtain the given
          *value from super*;

        * `owner_inst` -- the object on which the whole lookup has
           been initiated, or `None`;

        * `owner` -- the class on which the whole lookup has been
           initiated.

        For more information on these arguments -- see the "A few notes
        on the machinery..." fragment of the docs of this class.
        """
        assert (value_from_super is not self.MISSING
                and self.value is not self.MISSING)
        try:
            combined_value = self.value_combiner(value_from_super, self.value)
        except AttributeError as exc:
            raise RuntimeError('value combiner raised AttributeError') from exc
        else:
            if combined_value is self.MISSING:
                raise AttributeError(
                    f'no (combined) value of the {self.name!a} attribute of '
                    f'{owner_inst if owner_inst is not None else owner!a}')
            return combined_value



class FalseIfOwnerClassNameMatchesRegex:

    """
    >>> class A:
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

    def __get__(self, owner_inst, owner=None):
        if owner is None:
            if owner_inst is None:
                raise TypeError(
                    f'incorrect call to {self!a}.__get__() '
                    f'(only None values given)')
            owner = type(owner_inst)
        assert hasattr(owner, '__name__')
        return not self.__regex.search(owner.__name__)



class UnsupportedClassAttributesMixin:

    """
    A mixin that makes it possible to declare class attributes that are
    *explicitly unsupported* (so that a `TypeError` will be raised if any
    of them is present and set to a non-`None` value).

    To use the mixin, just make your class inherit from it and set the
    `unsupported_class_attributes` class attribute to a set of attribute
    names (possibly wrapped in `CombinedWithSuper`), e.g.:

    >>> class MyClass(UnsupportedClassAttributesMixin):
    ...     unsupported_class_attributes = {'spam', 'parrot'}
    ...     legal = 42
    ...     spam = 1
    ...     parrot = 'Norwegian Blue'                                          # doctest: +ELLIPSIS
    ...
    Traceback (most recent call last):
      ...
    TypeError: ... attributes of the MyClass class ...: 'parrot', 'spam'

    >>> class MyClass(UnsupportedClassAttributesMixin):
    ...     unsupported_class_attributes = CombinedWithSuper(frozenset({'spam', 'parrot'}))
    ...     legal = 42
    ...
    >>> class MySubclass(MyClass):
    ...     spam = 2                                                           # doctest: +ELLIPSIS
    ...
    Traceback (most recent call last):
      ...
    TypeError: ... attributes of the MySubclass class ...: 'spam'

    >>> class AnotherClass(UnsupportedClassAttributesMixin):
    ...     spam = None
    ...     parrot = 'Budgerigar'
    ...
    >>> class Subclass(AnotherClass):
    ...     pass
    ...
    >>> class SubSubclass(Subclass):
    ...     unsupported_class_attributes = {'parrot', 'spam', 'cheese_shop'}   # doctest: +ELLIPSIS
    ...
    Traceback (most recent call last):
      ...
    TypeError: ... attributes of the SubSubclass class ...: 'parrot'

    The error message can be customized by setting the
    `unsupported_class_attributes_error_message_pattern`
    attribute, e.g.:

    >>> class SubSubclass(Subclass):
    ...     unsupported_class_attributes = {'parrot', 'spam', 'cheese_shop'}
    ...     unsupported_class_attributes_error_message_pattern = (
    ...         'i hop-sa-sa ({attr_names_repr}), '
    ...         'i tra-la-la: {cls.__qualname__} '
    ...         '<< {cls.__mro__[1].__qualname__} '
    ...         '<< {cls.__mro__[2].__qualname__}')
    ...
    Traceback (most recent call last):
      ...
    TypeError: i hop-sa-sa ('parrot'), i tra-la-la: SubSubclass << Subclass << AnotherClass
    """

    # Can be overridden/extended in subclasses.
    unsupported_class_attributes: ClassVar[Set[str]] = CombinedWithSuper(frozenset())

    # Can be overridden in subclasses -- to customize the `TypeError`'s
    # message (when illegal attributes are found then the error message
    # will be obtained by invoking the `format()` method on the value of
    # the `unsupported_class_attributes_error_message_pattern` attribute
    # with the following keyword arguments passed in: `cls` -- set to the
    # owner class; `attr_names_repr` -- set to a string representing the
    # names of those illegal attributes).
    unsupported_class_attributes_error_message_pattern: ClassVar[str] = (
        'the following unsupported attributes of the {cls.__qualname__} '
        'class are set to non-None values: {attr_names_repr}')

    def __init_subclass__(cls, /, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        attr_names = sorted(cls.__find_illegal_attrs())
        if attr_names:
            raise TypeError(ascii_str(
                cls.unsupported_class_attributes_error_message_pattern.format(
                    cls=cls,
                    attr_names_repr=', '.join(map(repr, attr_names)))))

    @classmethod
    def __find_illegal_attrs(cls) -> Iterator[str]:
        unsupported_class_attributes = cls.unsupported_class_attributes
        if isinstance(unsupported_class_attributes, str):
            unsupported_class_attributes = {unsupported_class_attributes}
        for attr_name in unsupported_class_attributes:
            if getattr(cls, attr_name, None) is not None:
                yield attr_name



class __LackOfImpl:

    """
    `LackOf` is a singleton object whose truth value is false, and for
    whom all comparison operations evaluate to false (let us emphasize
    this: both `==` and `!=`, `>` and `<=`, `>=` and `<` -- all of them
    evaluate to false, whatever object `LackOf` is compared to; also if
    that object is `LackOf` itself).

    >>> LackOf
    <lack of>
    >>> bool(LackOf)
    False
    >>> whatever = 123.456  # <- Could be nearly any object, in particular any `int `/`float`.
    >>> LackOf == whatever
    False
    >>> LackOf != whatever
    False
    >>> LackOf < whatever
    False
    >>> LackOf <= whatever
    False
    >>> LackOf >= whatever
    False
    >>> LackOf > whatever
    False
    >>> whatever == LackOf
    False
    >>> whatever != LackOf
    False
    >>> whatever < LackOf
    False
    >>> whatever <= LackOf
    False
    >>> whatever >= LackOf
    False
    >>> whatever > LackOf
    False
    >>> LackOf == LackOf
    False
    >>> LackOf != LackOf
    False
    >>> LackOf < LackOf
    False
    >>> LackOf <= LackOf
    False
    >>> LackOf >= LackOf
    False
    >>> LackOf > LackOf
    False
    """

    def __false(*_): return False
    __bool__ = __false
    __eq__ = __ne__ = __false
    __lt__ = __le__ = __ge__ = __gt__ = __false

    def __repr__(self):
        return '<lack of>'

LackOf = __LackOfImpl()



def all_subclasses(cls):
    """
    Return a set of all direct and indirect subclasses of the given class.
    """
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


def call_new_of_super(super_obj, cls, /, *args, **kwargs):
    r"""
    A helper useful for making your implementation(s) of `__new__()`
    *cooperative-inheritance*-friendly, when what defines the arguments
    accepted by the constructor is still the signature(s) of `__init__()`,
    *not* of `__new__()` (see the explanations and examples below...).

    Args (positional arguments):
        `super_obj`:
            The object returned by the `super()` call made in your
            implementation of `__new__()`. The superclass's `__new__()`
            will be obtained by getting the `__new__` attribute from
            `super_obj`.
        `cls`:
            The type object taken by your implementation of `__new__()`
            as the first argument -- to be passed to the superclass's
            `__new__()` as the first argument.
        Any other positional arguments:
            To be passed (after `cls`) to the superclass's `__new__()`
            *unless* it is `object.__new__()`.

    Any kwargs (keyword arguments):
        To be passed to the superclass's `__new__()` *unless* it is
        `object.__new__()`.

    Returns:
        The return value from the superclass's `__new__(...)` call.

    Raises:
        Any exceptions from the superclass's `__new__(...)` call (note,
        however, that `TypeError` signalling excessive arguments to
        `object.__new__()` is avoided -- by special casing calls to
        `object.__new__()`).

    The legitimate use of this helper is when you define your custom
    implementation(s) of `__new__()` -- being **additional** to existing
    implementation(s) of `__init__()`, i.e., when you want that it is
    the `__init__()` signature(s) what define(s) the arguments accepted
    by your constructor(s), to avoid un-DRY duplication of information
    from your `__init__()` signature(s) in the signature(s) of your
    `__new__()` (such duplication is particularly troublesome when
    implementations of those methods are scattered across different
    classes along the inheritance hierarchy).

    In such cases, just make your implementation of `__new__()` accept:
    `cls` as the first (positional) argument, and arbitrary keyword
    arguments, i.e., `**kwargs` (and, optionally, *also* arbitrary
    positional arguments after `cls`, i.e., `*args`); and then pass them
    all to such a call: `call_new_of_super(super(), cls, **kwargs)` (or,
    respectively, `call_new_of_super(super(), cls, *args, **kwargs)`) --
    which should be made instead of `super().__new__(cls, **kwargs)` (or,
    respectively, instead of `super().__new__(cls, *args, **kwargs)``).

    **Note however** that then the superclass's `__new__()` -- *unless*
    it is `object.__new__()` -- is required to be able to deal with
    constructor arguments specific to any subclasses (typically,
    introduced by signatures of their `__init__()`s). *Hint:* also
    superclasses' implementations of `__new__()` can deal with that
    by using this helper.

    Thanks to using this technique consistently, all `**kwargs` (or
    `*args` and `**kwargs`, if you choose such a call scheme) taken
    by the constructor can be seemlessly propagated to consecutive
    implementations of `__new__()` along the inheritance hierarchy,
    *but* -- thanks to this helper -- avoiding `TypeError` when the
    next superclass providing an implementation of `__new__()` is
    `object` (which is always the root of any inheritance hierarchy in
    Python; note that `object.__new__()`, in a general case, does not
    accept any arguments except `cls` as the sole positional argument).

    **Warning:** you should **avoid** using this helper when *what
    is defining the arguments accepted by constructor(s)* is the
    implementation(s) of `__new__()` (rather than of `__init__()`) (for
    example, when there are no custom implementations of `__init__()` at
    all) -- because then you would lose the normal validation of sets
    of arguments passed to constructor(s) (because methods with `*args,
    **kwargs`-like signatures accept everything without any complaint).
    In such cases you should rather use some [traditional techniques of
    cooperative inheritance](https://rhettinger.wordpress.com/2011/05/26/super-considered-super/).

    ***

    What this helper actually does is to identify the superclass's
    implementation of `__new__()`, and then invoke it with `cls` as
    the first positional argument and:

    * with *no* other arguments -- if `__new__` is `object.__new__`;

    * with the given `*args` (if any) as positional arguments and the
      given `**kwargs` (if any) as keyword arguments -- if `__new__` is
      anything but `object.__new__`.

    Thaks to the latter, your class becomes more open to cooperative
    inheritance (see the examples below).

    ***

    See also:

    * https://stackoverflow.com/questions/19718062/determine-whether-super-new-will-be-object-new-in-python-3

    A curious reader may also want to familiarize themselves with the
    comment referred to by this URL:

    * https://github.com/python/cpython/blob/v3.9.9/Objects/typeobject.c#L3813
      (considering that the *warning* mentioned in the comment became an
      *error* in Py3, even though the comment has not been updated to
      reflect that; see also the `if` instructions at the beginning of
      each of the `object_init()` and `object_new()` definitions below
      that comment).

    ***

    A few example uses of this helper:

    >>> class MyReprMixin:
    ...     def __new__(cls, /,
    ...                 *args,       # <- positional-only
    ...                 **kwargs):   # <- keyword-only
    ...         new = call_new_of_super(super(), cls, *args, **kwargs)
    ...         # (^ instead of faulty `new = super().__new__(cls, *args, **kwargs)`)
    ...         arg_reprs = [repr(value) for value in args]
    ...         kwarg_reprs = [f'{name}={value!r}' for name, value in kwargs.items()]
    ...         new._constructor_arguments_repr = ', '.join(arg_reprs + kwarg_reprs)
    ...         return new
    ...
    ...     def __repr__(self):
    ...         return f"{type(self).__qualname__}({self._constructor_arguments_repr})"
    ...
    >>> class MyFoo(MyReprMixin):
    ...     def __init__(self,
    ...                  msg, /,    # <- positional-only
    ...                  *, foo):   # <- keyword-only
    ...         ...
    ...
    >>> class MySpam(MyReprMixin):
    ...     def __init__(self,
    ...                  a, b, c, /,              # <- positional-only
    ...                  *, bar, baz, **kwargs):  # <- keyword-only
    ...         super().__init__(**kwargs)
    ...         self.a_b_c = a + b + c
    ...         self.bar_baz = len(bar) + len(baz)
    ...
    >>> my_foo = MyFoo('Ho-ho!', foo=42)
    >>> my_foo
    MyFoo('Ho-ho!', foo=42)
    >>> my_spam = MySpam(1, 2, 3, bar="'X'", baz='"XYZ"')
    >>> my_spam
    MySpam(1, 2, 3, bar="'X'", baz='"XYZ"')
    >>> my_spam.a_b_c
    6
    >>> my_spam.bar_baz
    8

    >>> import functools, operator
    >>> class MyExtendedSpam(MySpam):
    ...     def __new__(cls, /,
    ...                 *args,       # <- positional-only
    ...                 **kwargs):   # <- keyword-only
    ...         new = call_new_of_super(super(), cls, *args, **kwargs)
    ...         # (^ instead of faulty `new = super().__new__(cls, *args, **kwargs)`)
    ...         new.product_of_positional_arg_values = functools.reduce(operator.mul, args)
    ...         return new
    ...
    ...     def __init__(self,
    ...                  a, b, c, /,               # <- positional-only
    ...                  *, spam, ham, **kwargs):  # <- keyword-only
    ...         super().__init__(a, b, c, **kwargs)
    ...         self.spam_ham = spam + ham
    ...
    >>> my_ext_spam = MyExtendedSpam(7, 8, 9, bar='A', baz='B', spam='C', ham='D')
    >>> my_ext_spam
    MyExtendedSpam(7, 8, 9, bar='A', baz='B', spam='C', ham='D')
    >>> my_ext_spam.a_b_c
    24
    >>> my_ext_spam.bar_baz
    2
    >>> my_ext_spam.spam_ham
    'CD'
    >>> my_ext_spam.product_of_positional_arg_values
    504

    Note that missing and excessive arguments are detected (thanks to
    properly designed `__init__()` signatures):

    >>> MyExtendedSpam(7, 8, bar='A', baz='B', spam='C', ham='D'             # missing pos. arg `c`
    ...                )  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> MyExtendedSpam(7, 8, 9, 10, bar='A', baz='B', spam='C', ham='D'      # excessive pos. arg
    ...                )  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> MyExtendedSpam(7, 8, 9, bar='A', spam='C', ham='D'                   # missing kwarg `baz`
    ...                )  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> MyExtendedSpam(7, 8, 9, bar='A', baz='B', spam='C', ham='D', x='X'   # illegal kwarg `x`
    ...                )  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    ***

    A few more examples -- involving multiple inheritance designed in a
    *cooperative* way:

    >>> class Root:
    ...     def __init__(self, *, r, **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.r = r
    ...
    ...     def __repr__(self):
    ...         return f'<{type(self).__qualname__}: {vars(self)}>'
    ...
    >>> class A(Root):
    ...     def __new__(cls, /, **kwargs):
    ...         hi_val = max(kwargs.values())
    ...         if hi_val < 1:
    ...             return 'I need more...'
    ...         return call_new_of_super(super(), cls, **kwargs)
    ...
    ...     def __init__(self, *, a, **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.a = a
    ...
    >>> A.__mro__ == (A, Root, object)
    True
    >>> A(r=0, a=0)
    'I need more...'
    >>> A(r=1, a=0)
    <A: {'r': 1, 'a': 0}>
    >>> A(r=4, a=4)
    <A: {'r': 4, 'a': 4}>

    >>> class B(Root):
    ...     def __new__(cls, /, **kwargs):
    ...         lo_val = min(kwargs.values())
    ...         if lo_val > 3:
    ...             return 42
    ...         return call_new_of_super(super(), cls, **kwargs)
    ...
    ...     def __init__(self, *, b, **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.b = b
    ...
    >>> B.__mro__ == (B, Root, object)
    True
    >>> B(r=0, b=0)
    <B: {'r': 0, 'b': 0}>
    >>> B(r=4, b=3)
    <B: {'r': 4, 'b': 3}>
    >>> B(r=4, b=4)
    42

    >>> class BA(B, A):
    ...     def __init__(self, *, ba, **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.ba = ba
    ...
    >>> BA.__mro__ == (BA, B, A, Root, object)
    True
    >>> BA(r=0, a=0, b=0, ba=0)
    'I need more...'
    >>> BA(r=0, a=0, b=0, ba=1)
    <BA: {'r': 0, 'a': 0, 'b': 0, 'ba': 1}>
    >>> BA(r=3, a=4, b=4, ba=4)
    <BA: {'r': 3, 'a': 4, 'b': 4, 'ba': 4}>
    >>> BA(r=4, a=4, b=4, ba=4)
    42

    >>> class Extra:
    ...     def __new__(cls, /, **kwargs):
    ...         new = call_new_of_super(super(), cls, **kwargs)
    ...         new.the_sum = sum(kwargs.values())
    ...         return new
    ...
    >>> extra_obj = Extra()
    >>> extra_obj.the_sum
    0

    >>> class BAX(BA, Extra):
    ...     pass
    ...
    >>> BAX.__mro__ == (BAX, BA, B, A, Root, Extra, object)
    True
    >>> BAX(r=-100, a=-10, b=-1, ba=0)
    'I need more...'
    >>> BAX(r=1, a=2, b=3, ba=4)
    <BAX: {'the_sum': 10, 'r': 1, 'a': 2, 'b': 3, 'ba': 4}>
    >>> BAX(r=-100, a=0, b=1000, ba=25)
    <BAX: {'the_sum': 925, 'r': -100, 'a': 0, 'b': 1000, 'ba': 25}>
    >>> BAX(r=5, a=6, b=7, ba=8)
    42

    And here, as in earlier examples, missing and excessive arguments
    are detected -- thanks to properly designed `__init__()` signatures:

    >>> A(r=1)  # missing `a`                                   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> B(r=1, a=2, b=3)  # illegal `a`                         # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> BA(r=1, a=2, b=3)  # missing `ba`                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> BAX(r=1, a=2, b=3, ba=4, c=5)  # illegal `c`            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    ...of course, provided that we get to the point of calling
    `__init__()` at all... (Sometimes it may turn out that `__new__()`
    can do more than you would like! `;-)`)

    >>> A(sakduyfgskdafj=0)
    'I need more...'
    >>> BAX(qwertweyrqwetr=77)
    42
    """
    super_new_method = super_obj.__new__
    if super_new_method is object.__new__:
        return super_new_method(cls)
    return super_new_method(cls, *args, **kwargs)  # noqa


def properly_negate_eq(self, other):
    """
    A general-purpose implementation of the `__ne__()` (*not equal*)
    special method which makes use of an existing implementation of the
    `__eq__()` (*equal*) special method, negating its result unless the
    result is `NotImplemented` (then just returning `NotImplemented`).

    That is the same what Python 3's `object.__ne__()` does, so -- in
    Python 3 -- when you implement equality comparisons in your class
    you typically need to provide the `__eq__()` method and nothing
    more. However, occasionally -- quite likely when subclasses, mixins
    and all that inheritance-related mess come into play -- it may be
    necessary to explicitly provide the behavior described above, by
    assigning this function to the `__ne__` attribute of your class, to
    override some other implementation of `__ne__()` (provided by some
    class that contributes to the inheritance hierarchy) which shadowed
    the original `object.__ne__()`. In such cases use this implementation
    of `__ne__` just by placing `__ne__ = properly_negate_eq` in the body
    of your class definition (you could get the same result by setting
    `__ne__ = object.__ne__`, but `__ne__ = properly_negate_eq` seems
    more readable, especially because of all this description `:-)`).

    Example use is presented below...

    Let's define a mixin class that makes use of `properly_negate_eq`:

    >>> class SensibleFooEqualityMixin:
    ...
    ...     foo = None
    ...
    ...     def __eq__(self, other):
    ...         other_foo = getattr(other, 'foo', None)
    ...         if self.foo is None or other_foo is None:
    ...             return NotImplemented     # <- We say: "Don't know. Maybe `other` knows?"
    ...         return self.foo == other_foo  # <- We say: "OK, the answer is..."
    ...
    ...     __ne__ = properly_negate_eq  # <- Negate __eq__() but say "Don't know..." if necessary.

    Now let's assume we have a class with implementations of `__eq__()`
    and `__ne__()` that we cannot change, say:

    >>> class SillyFooClass:
    ...
    ...     silly_eq_result = True
    ...     silly_ne_result = False
    ...
    ...     def __init__(self, foo):
    ...         self.foo = foo
    ...
    ...     def __eq__(self, other):
    ...         return self.silly_eq_result
    ...
    ...     def __ne__(self, other):
    ...         return self.silly_ne_result
    ...
    ...     #... some other methods...

    ...and we want to have a subclass of it, but with the implementation
    of (in)equality tests from our mixin:

    >>> class MyFooClass(SensibleFooEqualityMixin, SillyFooClass):
    ...     pass

    And -- voilà:

    >>> m1 = MyFooClass(1)
    >>> m1 == m1
    True
    >>> m1 != m1
    False
    >>> m1_0 = MyFooClass(1.0)  # equal to m1
    >>> m1 == m1_0
    True
    >>> m1 != m1_0
    False
    >>> m2 = MyFooClass(2)  # not equal to m1
    >>> m1 == m2
    False
    >>> m1 != m2
    True
    >>> mn = MyFooClass(None)
    >>> m1 == mn  # both sides give NotImplemented => fallback to object identity test
    False
    >>> m1 != mn  # (same as above: object identity test)
    True
    >>> mn == m1  # (same as above: object identity test)
    False
    >>> mn != m1  # (same as above: object identity test)
    True
    >>> mn == mn  # (same as above: object identity test)
    True
    >>> mn != mn  # (same as above: object identity test)
    False
    >>> s1 = SillyFooClass(1)
    >>> m1 == s1
    True
    >>> m1 != s1
    False
    >>> m2 == s1
    False
    >>> m2 != s1
    True
    >>> s1 == m2  # (note: type of m2 is subclass of type of s1 => m2.__eq__ takes precedence)
    False
    >>> s1 != m2  # (note: type of m2 is subclass of type of s1 => m2.__ne__ takes precedence)
    True

    And look at this (in particular, noting that `mn.__ne__()` properly
    gets and returns `NotImplemented` from `mn.__eq__()` -- so that
    `s1.__ne__()` is allowed to speak):

    >>> mn == s1  # mn.__eq__ gives NotImplemented => using s1.__eq__
    True
    >>> mn != s1  # mn.__ne__ gives NotImplemented => using s1.__ne__
    False
    >>> s1 == mn  # mn.__eq__ takes precedence, but it gives NotImplemented => using s1.__eq__
    True
    >>> s1 != mn  # mn.__ne__ takes precedence, but it gives NotImplemented => using s1.__ne__
    False
    >>> s1.silly_eq_result = False  # (let's demonstrate that really s1's __eq__/__ne__ are used)
    >>> mn == s1
    False
    >>> mn != s1
    False
    >>> s1.silly_eq_result = True
    >>> s1.silly_ne_result = True
    >>> mn == s1
    True
    >>> mn != s1
    True
    """
    return object.__ne__(self, other)


def get_class_name(instance_or_class):
    """
    Gen the name of the given class or of the class of the given instance.

    >>> class SpamHam: pass
    >>> s = SpamHam()
    >>> get_class_name(SpamHam)
    'SpamHam'
    >>> get_class_name(s)
    'SpamHam'
    """
    return (
        instance_or_class.__name__
        if isinstance(instance_or_class, type)
        else instance_or_class.__class__.__name__)



if __name__ == "__main__":
    import doctest
    doctest.testmod()

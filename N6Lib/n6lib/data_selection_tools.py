# Copyright (c) 2015-2023 NASK. All rights reserved.

"""
This module provides tools to express *data selection conditions*; by
formulating a *condition* we specify which event data records shall be
*selected*, that is -- depending on the context -- which ones shall be
*chosen* (when filtering a data stream) or *searched for* (when querying
a database). See the docs of the `Cond` base class for more details.

This module contains the following public stuff:

* `CondBuilder`
  -- a class providing the main tool to create condition objects

* Condition classes:

  * abstract ones:

    * `Cond` (the base condition class)
    * `CompoundCond` (base: `Cond`)
    * `CompoundMultiCond` (base: `CompoundCond`)
    * `RecItemCond` (base: `Cond`)
    * `RecItemParamCond` (base: `RecItemCond`)

  * concrete ones:

    * `NotCond` (base: `CompoundCond`)
      -- representing the `NOT` Boolean operator

    * `AndCond` and `OrCond` (base: `CompoundMultiCond`)
      -- representing the `AND` and `OR` Boolean operators

    * `EqualCond` (base: `RecItemParamCond`)
      -- representing the `== ...` condition

    * `GreaterCond` and `GreaterOrEqualCond` (base: `RecItemParamCond`)
      -- representing the `> ...` and `>= ...` conditions

    * `LessCond` and `LessOrEqualCond` (base: `RecItemParamCond`)
      -- representing the `< ...` and `<= ...` conditions

    * `InCond` (base: `RecItemParamCond`)
      -- representing the `IN the ... collection` condition

    * `BetweenCond` (base: `RecItemParamCond`)
      -- representing the `>= ... AND <= ...` condition

    * `ContainsSubstringCond` (base: `RecItemParamCond`)
      -- representing the `contains the ... substring` condition

    * `IsTrueCond` (base: `RecItemCond`)
      -- representing the `is TRUE` condition

    * `IsNullCond` (base: `RecItemCond`)
      -- representing the `is missing/is NULL` condition

    * `FixedCond` (base: `Cond`)
      -- representing a constant Boolean value: `TRUE` or `FALSE`

* `CondVisitor` and `CondTransformer`
  -- base classes for tools to process condition objects (e.g., to
  create data selection predicate functions, or to generate SQL queries,
  or to transform condition objects according to any custom rules...)

* Predicate-based data selection tools:

  * `CondPredicateMaker` (base: `CondVisitor`)
    -- a visitor class to make data selection predicates (e.g., for the
    `n6anonymizer` component) from given conditions

  * `RecordWrapperForPredicates`
    -- a wrapper class to make a `dict`/`RecordDict` usable with
    predicates produced by a `CondPredicateMaker`

* Condition-optimization/adjustment-related tools:

  * `CondFactoringTransformer` (base: `CondTransformer`)
  * `CondEqualityMergingTransformer` (base: `CondTransformer`)
  * `CondDeMorganTransformer` (base: `CondTransformer`)

(For more information -- see the docs of those classes.)

Note: some of the classes provided by this module make heavy use of
the `n6lib.common_helpers.OPSet` class -- which is an order-preserving
implementation of `collections.abc.Set`, i.e., such an implementation
that remembers the element insertion order (to learn more about how it
behaves, see the docs of `OPSet` itself).
"""

import collections
import functools
import itertools
from collections.abc import (
    Callable,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from operator import eq, gt, ge, lt, le
from typing import (
    Any,
    ClassVar,
    Generic,
    NoReturn,
    Optional,
    TypeVar,
    Union,
    overload,
)

from n6lib.class_helpers import (
    attr_required,
    call_new_of_super,
)
from n6lib.common_helpers import (
    OPSet,
    ascii_str,
    ip_str_to_int,
    iter_altered,
)


#
# Condition builder class
#

class CondBuilder:

    r"""
    A tool to construct *condition* objects.

    Data selection *conditions* are represented by instances of concrete
    subclasses of the `Cond` class (`AndCond`, `OrCond`, `NotCond`,
    `EqualCond`, `IsNullCond`, `ContainsSubstringCond` and others --
    see the docs of the `Cond` base class and of its subclasses...).

    Instances of those classes cannot be created directly. Typically,
    instead of that, you need to use the interface provided by this
    class -- it offers a mini-DSL to create such instances in a
    convenient way.

    Let the examples speak:

    >>> cond_builder = CondBuilder()

    >>> cond_builder['asn'] == 42
    <EqualCond: 'asn', 42>

    >>> cond_builder['asn'] > 42
    <GreaterCond: 'asn', 42>

    >>> cond_builder['asn'] >= 42
    <GreaterOrEqualCond: 'asn', 42>

    >>> cond_builder['asn'] < 42
    <LessCond: 'asn', 42>

    >>> cond_builder['asn'] <= 42
    <LessOrEqualCond: 'asn', 42>

    >>> cond_builder['asn'].in_([1, 42, 12345])
    <InCond: 'asn', {1, 42, 12345}>

    >>> cond_builder['asn'].between((1, 7654321))
    <BetweenCond: 'asn', (1, 7654321)>
    >>> cond_builder['asn'].between(1, 7654321)  # (two-argument convenience form)
    <BetweenCond: 'asn', (1, 7654321)>

    >>> cond_builder['url'].contains_substring('tp://sp')
    <ContainsSubstringCond: 'url', 'tp://sp'>

    >>> cond_builder['ignored'].is_true()
    <IsTrueCond: 'ignored'>

    >>> cond_builder['url'].is_null()
    <IsNullCond: 'url'>

    >>> cond1 = cond_builder['asn'] < 42
    >>> cond1
    <LessCond: 'asn', 42>
    >>> cond2 = cond_builder['url'].is_null()
    >>> cond2
    <IsNullCond: 'url'>

    >>> cond_builder.not_(cond1)
    <NotCond: <LessCond: 'asn', 42>>

    >>> cond_builder.and_(cond1, cond2)
    <AndCond: <LessCond: 'asn', 42>, <IsNullCond: 'url'>>

    >>> cond_builder.or_(cond1, cond2)
    <OrCond: <LessCond: 'asn', 42>, <IsNullCond: 'url'>>

    >>> cond_builder.true()
    <FixedCond: True>

    >>> cond_builder.false()
    <FixedCond: False>

    >>> repr(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             cond_builder['ip'] == '123.124.125.126',
    ...             cond_builder['asn'] >= 42,
    ...             cond_builder['count'].between(1, 1000),
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder.and_([     # (alternative call style: 1 iterable of subconditions)
    ...                 cond_builder.or_([
    ...                     cond_builder['url'].contains_substring('tp://exampl\u0119.'),
    ...                     cond_builder.not_([
    ...                         cond_builder['cc'].is_null(),
    ...                     ]),
    ...                 ]),
    ...                 cond_builder['asn'].in_([1, 42, 12345]),
    ...             ]),
    ...         ),
    ...     ),
    ... ) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'ip', '123.124.125.126'>, "
    ...             "<GreaterOrEqualCond: 'asn', 42>, "
    ...             "<BetweenCond: 'count', (1, 1000)>>, "
    ...         "<NotCond: "
    ...             "<AndCond: "
    ...                 "<OrCond: "
    ...                     "<ContainsSubstringCond: 'url', 'tp://exampl\u0119.'>, "
    ...                     "<NotCond: "
    ...                         "<IsNullCond: 'cc'>>>, "
    ...                 "<InCond: 'asn', {1, 42, 12345}>>>>")
    True


    Note that `None` is not allowed as an operand (or an operand's
    item):

    >>> cond_builder['asn'] == None                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'] > None                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'] >= None                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'] < None                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'] <= None                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'].in_(None)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'].in_([1, None, 12345])        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should not contain None)

    >>> cond_builder['asn'].between(None)                # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> cond_builder['asn'].between((1, None))           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (interval endpoint value must not be None)

    >>> cond_builder['asn'].between(None, 7654321)       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (interval endpoint value must not be None)

    >>> cond_builder['url'].contains_substring(None)     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)


    Also, note that the `!=` operator is not supported:

    >>> cond_builder['asn'] != 42
    Traceback (most recent call last):
      ...
    TypeError: the `!=` operation is not supported

    The rationale is that the behavior of the SQL `!=` operator, when
    *NULL* values are involved (with the *three-valued logic*-based
    *NULL*-propagating behavior), is confusingly different from the
    behavior of the Python `!=` operator when `None` values are involved
    (note that even if we banned `None` as the right hand side operand
    -- as we do for all supported operators -- the problem could still
    occur for the left hand side operand, that is, when values of the
    concerned field in some records being searched through were *NULL*).
    By leaving the `!=` operator unsupported, we avoid a lot of potential
    confusion.

    See also: the "Pure Boolean (two-valued) logic" and "Keys missing
    from data records" sections of the docs of the `Cond` class.
    """

    class RecItemCondBuilder:

        """
        An auxiliary class that implements a part of the `CondBuilder`'s
        mini-DSL. Every `<CondBuilder object>[<some record key>]` lookup
        produces an instance of this class, on which certain methods and
        operators (e.g.: `==`, `<`, `>`, `in_()`, `is_null()`...) can be
        invoked to construct *record-item-concerned* condition objects
        (see the docs of `RecItemCond` and its subclasses; also, see the
        main docs of `CondBuilder`).
        """

        def __init__(self, rec_key: str):
            self._rec_key = rec_key

        __hash__ = None

        def __eq__(self, op_param: Hashable, /) -> 'EqualCond':
            return EqualCond._make(self._rec_key, op_param)              # noqa

        # (unsupported; see the rationale in the docs of `CondBuilder`...)
        def __ne__(self, _) -> NoReturn:
            raise TypeError('the `!=` operation is not supported')

        def __gt__(self, op_param: Hashable, /) -> 'GreaterCond':
            return GreaterCond._make(self._rec_key, op_param)            # noqa

        def __ge__(self, op_param: Hashable, /) -> 'GreaterOrEqualCond':
            return GreaterOrEqualCond._make(self._rec_key, op_param)     # noqa

        def __lt__(self, op_param: Hashable, /) -> 'LessCond':
            return LessCond._make(self._rec_key, op_param)               # noqa

        def __le__(self, op_param: Hashable, /) -> 'LessOrEqualCond':
            return LessOrEqualCond._make(self._rec_key, op_param)        # noqa

        def in_(self, op_param: Iterable[Hashable], /) -> 'Union[InCond, EqualCond, FixedCond]':
            return InCond._make(self._rec_key, op_param)                 # noqa

        @overload
        def between(self, op_param: Iterable[Hashable], /) -> 'BetweenCond':
            # The basic `between()`'s call variant: `op_param`
            # specified as one positional argument -- expected
            # to be a `(<min value>, <max value>)` tuple, or an
            # iterable convertible to such a tuple.
            ...

        @overload
        def between(self, min_value: Hashable, max_value: Hashable, /) -> 'BetweenCond':
            # Another call variant, added for convenience: the
            # `op_param` items, `<min value>` and `<max value>`,
            # specified as two separate positional arguments.
            ...

        def between(self, *args):
            arg_count = len(args)
            if arg_count == 1:
                op_param = args[0]
            elif arg_count == 2:
                op_param = args
            else:
                raise TypeError(
                    f'the between() method takes 1 or 2 '
                    f'arguments ({arg_count} given)')
            return BetweenCond._make(self._rec_key, op_param)            # noqa

        def contains_substring(self, op_param: str, /) -> 'ContainsSubstringCond':
            return ContainsSubstringCond._make(self._rec_key, op_param)  # noqa

        def is_true(self) -> 'IsTrueCond':
            return IsTrueCond._make(self._rec_key)                       # noqa

        def is_null(self) -> 'IsNullCond':
            return IsNullCond._make(self._rec_key)                       # noqa


    def __getitem__(self, rec_key: str) -> RecItemCondBuilder:
        return self.RecItemCondBuilder(rec_key)


    @overload
    def not_(self, subcond: 'Cond', /,
             ) -> 'Cond': ...              # (note: result may be any `Cond`, not always `NotCond`)

    @overload
    def not_(self, subcond: Iterable['Cond'], /,   # The iterable should yield exactly one `Cond`.
             ) -> 'Cond': ...              # (note: result may be any `Cond`, not always `NotCond`)

    def not_(self, subcond):
        return NotCond._make(subcond)                                    # noqa


    @overload
    def and_(self, *subconditions: 'Cond',
             ) -> 'Cond': ...              # (note: result may be any `Cond`, not always `AndCond`)

    @overload
    def and_(self, subconditions: Iterable['Cond'], /,
            ) -> 'Cond': ...               # (note: result may be any `Cond`, not always `AndCond`)

    def and_(self, *subconditions):
        return AndCond._make(*subconditions)                             # noqa


    @overload
    def or_(self, *subconditions: 'Cond',
            ) -> 'Cond': ...               # (note: result may be any `Cond`, not always `OrCond`)

    @overload
    def or_(self, subconditions: Iterable['Cond'], /,
            ) -> 'Cond': ...               # (note: result may be any `Cond`, not always `OrCond`)

    def or_(self, *subconditions):
        return OrCond._make(*subconditions)                              # noqa


    def true(self) -> 'FixedCond':
        return FixedCond._make(True)                                     # noqa

    def false(self) -> 'FixedCond':
        return FixedCond._make(False)                                    # noqa


#
# Data selection condition classes
#

#
# Abstract condition classes

class Cond(Hashable):

    """
    The base class for data selection *conditions*.


    This documentation consists of the following sections:

    * "Basics"
    * "Compound conditions"
    * "Specific features of constructors"
    * "Pure Boolean (two-valued) logic"
    * "Keys missing from data records"


    Basics
    ======

    Every *condition* object, i.e., an instance of a concrete subclass
    of this class:

    * represents an abstract *data selection condition* -- defining which
      event data records shall be selected (when being filtered/searched);
      for example, "those whose `asn` is *equal to* 12345, or whose `url`
      *contains* the substring `'tp://'`, provided that their `modified`
      is *greater than or equal to* `2016-10-21T22:35:45` and `category`
      is *not* equal to any item *in* `('bots', 'cnc', 'malurl')`";

    * provides informative `repr()`, including details of the selection
      condition it represents;

    * supports the `==` and `!=` operations -- any two *condition*
      objects which compare *equal* represent selection conditions that
      are *logically equivalent* (note, however, that not every two
      condition objects representing logically equivalent conditions
      compare equal);

    * is hashable (so it can be used as a key in a `dict` or an element
      of a `set`);

    * exposes certain public attributes (read-only ones -- see the next
      bullet point...):

      1) `init_args` -- which is a tuple of the arguments that have been
         used to initialize the instance (already *after* any automatic
         adaptations, coercions, etc. -- enforced on instance creation
         by some subclasses of `Cond`); all tuple items are required to
         be hashable;

      2) attributes specific to a particular subclass of `Cond` (see
         the docs of subclasses);

    * should *always* be considered *immutable* -- especially all its
      attributes should be treated as *read-only* ones (you should
      *never* try to replace or mutate their values -- even if it is
      technically possible);

    * can be passed to `copy()` or `deepcopy()` functions from the
      standard library's `copy` module -- but the result is always the
      same object that has been passed in (note: that should not matter,
      considering immutability of condition objects -- see the previous
      bullet point);

    * can be pickled and unpickled.

    Note that every instance of a `Cond` subclass, taken on its own,
    represents a data selection condition as an abstract entity. That
    is, it does not implement any "concrete" activity like predicate
    evaluation (checking whether certain data record satisfies the
    condition) or SQL query generation; to do such stuff you need to
    process your condition object(s) with an appropriate *visitor* --
    see the `CondVisitor` class and its subclasses (not necessarily
    only those defined in this module...).

    Important: `Cond` and its subclasses do not provide any public
    constructors (any direct instantiation attempts cause `TypeError`).
    There are three different (though equivalent in terms of results)
    ways to create an instance of a concrete subclass of `Cond` -- each
    intended to be used within a different kind of code:

    1) in a client code, that is, in any code that makes use of this
       module (just as a library) -- use only the interface provided by
       the `CondBuilder` class (see its docs);

    2) in the implementation of any `CondVisitor` subclass (if needed) --
       call the `<visitor instance>.make_cond()` method (see the docs of
       the `CondVisitor` class and, especially, of the `CondVisitor`'s
       method `make_cond()`);

    3) *only* in the internals and tests of this module -- call the
       `<concrete Cond subclass>._make()` non-public constructor.

    Let the examples speak:

    >>> cond_builder = CondBuilder()
    >>> ge1 = (cond_builder['asn'] >= 42)
    >>> ge1
    <GreaterOrEqualCond: 'asn', 42>

    >>> some_visitor = CondTransformer()
    >>> ge2 = some_visitor.make_cond(GreaterOrEqualCond, 'asn', 42)
    >>> ge2
    <GreaterOrEqualCond: 'asn', 42>

    >>> ge3 = GreaterOrEqualCond._make('asn', 42)
    >>> ge3
    <GreaterOrEqualCond: 'asn', 42>

    Note: if some condition objects represent exactly *the same abstract
    selection condition*, they are perfectly equivalent and, therefore,
    are *equal to each other* (no matter in which way they were created).

    >>> ge1 == ge2 == ge3 == ge1 == ge3 == ge2 == ge1
    True
    >>> ge1 != ge2 or ge2 != ge3 or ge3 != ge1 or ge1 != ge3 or ge3 != ge2 or ge2 != ge1
    False

    In other words, *equality* of condition objects implies *logical
    equivalence* of the abstract selection conditions they represent.

    Here we should add: *accurate to types*, i.e., assuming that values
    in data records being selected are equivalent if they compare equal,
    even if their types are different (e.g., `42` == `42.0`):

    >>> ge3 == (cond_builder['asn'] >= 42.0)   # (because `42` == `42.0`)
    True

    Also, note that the implication referred to above is not two-way,
    i.e., *logical equivalence* of abstract selection conditions does
    *not* imply *equality* of condition objects that represent them,
    i.e., there can be abstract selection conditions which are
    *logically equivalent* but whose representations as condition
    objects are *not equal* to each other, e.g.:

    >>> asn_3_or_greater = (cond_builder['asn'] >= 3)
    >>> asn_3_or_greater_alt = cond_builder.or_(cond_builder['asn'] == 3, cond_builder['asn'] > 3)
    >>> asn_3_or_greater == asn_3_or_greater_alt   # (logically equivalent but *not equal*)
    False

    >>> asn_not_1_or_2 = cond_builder.not_(cond_builder.or_(
    ...     cond_builder['asn'] == 1,
    ...     cond_builder['asn'] == 2))
    >>> asn_not_1_or_2_alt = cond_builder.and_(
    ...     cond_builder.not_(cond_builder['asn'] == 1),
    ...     cond_builder.not_(cond_builder['asn'] == 2))
    >>> asn_not_1_or_2 == asn_not_1_or_2_alt   # (logically equivalent but *not equal*)
    False

    >>> asn_1_or_2 = cond_builder['asn'].in_([1, 2])
    >>> asn_1_or_2_alt = cond_builder.or_(cond_builder['asn'] == 1, cond_builder['asn'] == 2)
    >>> asn_1_or_2 == asn_1_or_2_alt   # (logically equivalent but *not equal*)
    False

    Now, let's see more examples of simple conditions of various types...

    >>> between1 = cond_builder['count'].between(1, 100)
    >>> between2 = some_visitor.make_cond(BetweenCond, 'count', (1, 100))
    >>> between3 = BetweenCond._make('count', (1, 100))
    >>> between1
    <BetweenCond: 'count', (1, 100)>
    >>> between2
    <BetweenCond: 'count', (1, 100)>
    >>> between3
    <BetweenCond: 'count', (1, 100)>
    >>> between1 == between2 == between3 == between1 == between3 == between2 == between1
    True
    >>> (between1 != between2 or between2 != between3 or between3 != between1
    ...  or between1 != between3 or between3 != between2 or between2 != between1)
    False
    >>> (between1 == (cond_builder['count'].between(0j+1, 100.0))            # (because 1 == 0j+1
    ...  and not between1 != (cond_builder['count'].between(0j+1, 100.0)))   # and 100 == 100.0)
    True
    >>> between1 == ge1 or ge1 == between1
    False
    >>> between1 != ge1 and ge1 != between1
    True

    *Note* that -- no matter in which way instances of concrete `Cond`
    subclasses are created -- you construct them *only using positional
    arguments* (i.e., you should *not* pass any keyword arguments to
    `Cond._make()`, or to `CondVisitor.make_cond()`, or to the interface
    of a `CondBuilder` -- even if that appeared technically possible in
    some cases!).

    >>> ge4 = (cond_builder['asn'] >= 456)
    >>> ge4
    <GreaterOrEqualCond: 'asn', 456>
    >>> ge4 == GreaterOrEqualCond._make('asn', 456)
    True
    >>> ge4 == ge1 or ge4 == ge2 or ge4 == ge3
    False
    >>> ge1 == ge4 or ge2 == ge4 or ge3 == ge4
    False
    >>> ge4 != ge1 and ge4 != ge2 and ge4 != ge3
    True
    >>> ge1 != ge4 and ge2 != ge4 and ge3 != ge4
    True

    >>> ge5 = (cond_builder['Asn'] >= 456)
    >>> ge5 == ge4 or ge4 == ge5
    False
    >>> ge5 != ge4 and ge4 != ge5
    True

    >>> gt1 = (cond_builder['asn'] > 42)
    >>> gt1
    <GreaterCond: 'asn', 42>
    >>> gt1 == GreaterCond._make('asn', 42) == some_visitor.make_cond(GreaterCond, 'asn', 42)
    True
    >>> gt1 == ge1 or gt1 == ge2 or gt1 == ge3 or gt1 == ge4
    False
    >>> ge1 == gt1 or ge2 == gt1 or ge3 == gt1 or ge4 == gt1
    False
    >>> gt1 != ge1 and gt1 != ge2 and gt1 != ge3 and gt1 != ge4
    True
    >>> ge1 != gt1 and ge2 != gt1 and ge3 != gt1 and ge4 != gt1
    True

    >>> eq1 = (cond_builder['asn'] == 42)
    >>> eq1
    <EqualCond: 'asn', 42>
    >>> eq1 == some_visitor.make_cond(EqualCond, 'asn', 42) == EqualCond._make('asn', 42)
    True
    >>> eq1 == ge1 or eq1 == ge2 or eq1 == ge3 or eq1 == ge4 or eq1 == gt1
    False
    >>> ge1 == eq1 or ge2 == eq1 or ge3 == eq1 or ge4 == eq1 or gt1 == eq1
    False
    >>> eq1 != ge1 and eq1 != ge2 and eq1 != ge3 and eq1 != ge4 and eq1 != gt1
    True
    >>> ge1 != eq1 and ge2 != eq1 and ge3 != eq1 and ge4 != eq1 and gt1 != eq1
    True

    >>> le1 = (cond_builder['asn'] <= 42)
    >>> lt1 = (cond_builder['asn'] < 42)
    >>> le1
    <LessOrEqualCond: 'asn', 42>
    >>> lt1
    <LessCond: 'asn', 42>
    >>> le1 == some_visitor.make_cond(LessOrEqualCond, 'asn', 42) == le1
    True
    >>> lt1 == some_visitor.make_cond(LessCond, 'asn', 42) == lt1
    True
    >>> le1 == lt1 or lt1 == le1 or le1 == eq1 or eq1 == le1 or lt1 == eq1 or eq1 == lt1
    False
    >>> le1 != lt1 and lt1 != le1 and le1 != eq1 and eq1 != le1 and lt1 != eq1 and eq1 != lt1
    True

    >>> flag = cond_builder['ig'].is_true()
    >>> flag
    <IsTrueCond: 'ig'>
    >>> flag == IsTrueCond._make('ig') == flag == some_visitor.make_cond(IsTrueCond, 'ig')
    True
    >>> flag == cond_builder['ig'].is_null() or cond_builder['ig'].is_null() == flag
    False
    >>> flag != cond_builder['ig'].is_null() or cond_builder['ig'].is_null() != flag
    True

    >>> missing = cond_builder['asn'].is_null()
    >>> missing
    <IsNullCond: 'asn'>
    >>> missing == IsNullCond._make('asn') == missing == some_visitor.make_cond(IsNullCond, 'asn')
    True
    >>> missing == eq1 or eq1 == missing or missing == le1 or le1 == missing
    False
    >>> missing != eq1 and eq1 != missing or missing != le1 and le1 != missing
    True

    >>> in1 = cond_builder['asn'].in_([42, 456])
    >>> in2 = cond_builder['asn'].in_([42, 457])
    >>> in3 = cond_builder['xy'].in_([42, 456])
    >>> csub = cond_builder['xy'].contains_substring('42')
    >>> in1
    <InCond: 'asn', {42, 456}>
    >>> in2
    <InCond: 'asn', {42, 457}>
    >>> in3
    <InCond: 'xy', {42, 456}>
    >>> csub
    <ContainsSubstringCond: 'xy', '42'>
    >>> InCond._make('asn', (42, 456)) == some_visitor.make_cond(InCond, 'asn', (42, 456)) == in1
    True
    >>> InCond._make('asn', (42, 457)) == some_visitor.make_cond(InCond, 'asn', (457, 42)) == in2
    True
    >>> InCond._make('xy', (456, 42.0)) == some_visitor.make_cond(InCond, 'xy', (42, 456)) == in3
    True
    >>> csub == ContainsSubstringCond._make('xy', '42') == csub
    True
    >>> in1 == in2 or in1 == in3 or in2 == in1 or in2 == in3 or in3 == in1 or in3 == in2
    False
    >>> in1 == csub or csub == in1 or in1 == eq1 or eq1 == in1 or in1 == missing or missing == in1
    False
    >>> in1 != in2 and in1 != in3 and in3 != in1 and in2 != in3 and in3 != in1 and in3 != in2
    True
    >>> (in1 != csub and csub != in1 and in1 != eq1 and eq1 != in1
    ...  and in1 != missing and missing != in1)
    True
    >>> in3_ = cond_builder['xy'].in_([42, 456.0, 456, 42, 42.0, 456+0j])
    >>> in3_  # Note: `InCond`'s operation parameter's duplicate items are *automatically omitted*.
    <InCond: 'xy', {42, 456.0}>
    >>> InCond._make('xy', (456, 42.0)) == some_visitor.make_cond(InCond, 'xy', (42, 456)) == in3_
    True
    >>> in3 == in3_ and in3_ == in3 and not (in3 != in3_) and not (in3_ != in3)
    True

    Note: in the case of `InCond`, the order of items of the given
    operation parameter iterable is *preserved* but, at the same time,
    is *irrelevant* for equality of condition objects...

    >>> InCond._make('asn', (1, 2, 3))
    <InCond: 'asn', {1, 2, 3}>
    >>> InCond._make('asn', (3, 2, 1))
    <InCond: 'asn', {3, 2, 1}>
    >>> (InCond._make('asn', (1, 2, 3)) == InCond._make('asn', (3, 2, 1))
    ...  and not (InCond._make('asn', (1, 2, 3)) != InCond._make('asn', (3, 2, 1))))
    True
    >>> (InCond._make('asn', (1, 2, 3)) == InCond._make('asn', (3.0, 2.0, 1.0, 2.0, 3.0))
    ...  == cond_builder['asn'].in_([2, 3+0j, 1]) == cond_builder['asn'].in_([1, 3, 2.0, 3.0, 1.0])
    ...  == some_visitor.make_cond(InCond, 'asn', (3, 1.0, 2+0j)))
    True

    >>> alwaystrue1 = cond_builder.true()
    >>> alwaystrue2 = some_visitor.make_cond(FixedCond, True)
    >>> alwaystrue3 = FixedCond._make(True)
    >>> alwaystrue1
    <FixedCond: True>
    >>> alwaystrue2
    <FixedCond: True>
    >>> alwaystrue3
    <FixedCond: True>
    >>> alwaystrue1 == alwaystrue2 == alwaystrue3
    True
    >>> alwaystrue1 != alwaystrue2 or alwaystrue1 != alwaystrue3
    False
    >>> alwaysfalse = FixedCond._make(False)
    >>> alwaystrue1 == alwaysfalse
    False
    >>> alwaystrue1 != alwaysfalse
    True

    >>> (eq1 == eq1 and gt1 == gt1 and ge1 == ge1 and lt1 == lt1 and le1 == le1
    ...  and in1 == in1 and between1 == between1 and csub == csub and missing == missing
    ...  and flag == flag and alwaystrue1 == alwaystrue1 and alwaysfalse == alwaysfalse)
    True
    >>> (eq1 != eq1 or gt1 != gt1 or ge1 != ge1 or lt1 != lt1 or le1 != le1
    ...  or in1 != in1 or between1 != between1 or csub != csub or missing != missing
    ...  or flag != flag or alwaystrue1 != alwaystrue1 or alwaysfalse != alwaysfalse)
    False

    >>> GreaterOrEqualCond('asn', 42)      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: cannot create GreaterOrEqualCond instances directly...

    >>> FixedCond(True)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: cannot create FixedCond instances directly...

    >>> OrCond(ge1, ge2, ge4)              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: cannot create OrCond instances directly...

    >>> ge1.rec_key
    'asn'
    >>> ge1.op_param
    42
    >>> ge1.init_args
    ('asn', 42)

    >>> in1.rec_key
    'asn'
    >>> in1.op_param
    OPSet([42, 456])
    >>> in1.init_args
    ('asn', OPSet([42, 456]))

    >>> between1.rec_key
    'count'
    >>> between1.op_param
    (1, 100)
    >>> between1.init_args
    ('count', (1, 100))

    >>> alwaystrue1.truthness
    True
    >>> alwaystrue1.init_args
    (True,)

    >>> cond_builder['address'] == ['1.2.3.4']                          # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ...hashable...

    >>> some_visitor.make_cond(InCond, 'cc', ['PL', 'JP', 'EN'])
    <InCond: 'cc', {'PL', 'JP', 'EN'}>
    >>> some_visitor.make_cond(InCond, 'cc', (['PL'], ['JP'], ['EN']))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ...hashable...

    >>> BetweenCond._make('asn', [1, 2])
    <BetweenCond: 'asn', (1, 2)>
    >>> BetweenCond._make('asn', [[1], [2]])                            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ...hashable...

    >>> di = {ge1: 'foo'}
    >>> di
    {<GreaterOrEqualCond: 'asn', 42>: 'foo'}
    >>> di[ge2] = 'Blabla'
    >>> di
    {<GreaterOrEqualCond: 'asn', 42>: 'Blabla'}
    >>> di[ge3] = 'BAR'
    >>> di
    {<GreaterOrEqualCond: 'asn', 42>: 'BAR'}
    >>> len(di)
    1
    >>> di[ge4] = 'SPAM'
    >>> len(di)
    2
    >>> di[between3] = 'SPAM-HAM'
    >>> len(di)
    3
    >>> di[between2] = 'HAM-SPAM'
    >>> len(di)
    3
    >>> di[between1] = 'HAM'
    >>> len(di)
    3
    >>> di.update([(alwaystrue1, 'T1'),
    ...            (alwaystrue2, 'T2'),
    ...            (alwaystrue3, 'T3')])
    >>> len(di)
    4
    >>> di[GreaterOrEqualCond._make('asn', 42)]
    'BAR'
    >>> di[GreaterOrEqualCond._make('asn', 456)]
    'SPAM'
    >>> di[BetweenCond._make('count', (1, 100))]
    'HAM'
    >>> di[BetweenCond._make('count', (1, 101))]
    Traceback (most recent call last):
      ...
    KeyError: <BetweenCond: 'count', (1, 101)>
    >>> di[FixedCond._make(True)]
    'T3'

    >>> import copy
    >>> copy.copy(ge1) is ge1
    True
    >>> copy.copy(alwaysfalse) is alwaysfalse
    True
    >>> copy.deepcopy(ge1) is ge1
    True
    >>> copy.deepcopy(alwaysfalse) is alwaysfalse
    True

    >>> import pickle
    >>> eq1pi = pickle.loads(pickle.dumps(eq1, pickle.HIGHEST_PROTOCOL))
    >>> gt1pi = pickle.loads(pickle.dumps(gt1, pickle.HIGHEST_PROTOCOL))
    >>> ge1pi = pickle.loads(pickle.dumps(ge1, pickle.HIGHEST_PROTOCOL))
    >>> lt1pi = pickle.loads(pickle.dumps(lt1, pickle.HIGHEST_PROTOCOL))
    >>> le1pi = pickle.loads(pickle.dumps(le1, pickle.HIGHEST_PROTOCOL))
    >>> in1pi = pickle.loads(pickle.dumps(in1, pickle.HIGHEST_PROTOCOL))
    >>> between1pi = pickle.loads(pickle.dumps(between1, pickle.HIGHEST_PROTOCOL))
    >>> csubpi = pickle.loads(pickle.dumps(csub, pickle.HIGHEST_PROTOCOL))
    >>> missingpi = pickle.loads(pickle.dumps(missing, pickle.HIGHEST_PROTOCOL))
    >>> alwaystrue1pi = pickle.loads(pickle.dumps(alwaystrue1, pickle.HIGHEST_PROTOCOL))
    >>> alwaysfalsepi = pickle.loads(pickle.dumps(alwaysfalse, pickle.HIGHEST_PROTOCOL))

    >>> (eq1pi == eq1 and gt1pi == gt1 and ge1pi == ge1 and lt1pi == lt1 and le1pi == le1
    ...  and in1pi == in1 and between1pi == between1 and csubpi == csub and missingpi == missing
    ...  and alwaystrue1pi == alwaystrue1 and alwaysfalsepi == alwaysfalse)
    True
    >>> (eq1 == eq1pi and gt1 == gt1pi and ge1 == ge1pi and lt1 == lt1pi and le1 == le1pi
    ...  and in1 == in1pi and between1 == between1pi and csub == csubpi and missing == missingpi
    ...  and alwaystrue1 == alwaystrue1pi and alwaysfalse == alwaysfalsepi)
    True
    >>> (eq1pi is not eq1 and gt1pi is not gt1 and ge1pi is not ge1 and lt1pi is not lt1
    ...  and le1pi is not le1 and in1pi is not in1 and between1pi is not between1
    ...  and csubpi is not csub and missingpi is not missing
    ...  and alwaystrue1pi is not alwaystrue1 and alwaysfalsepi is not alwaysfalse)
    True

    >>> (eq1pi != eq1 or gt1pi != gt1 or ge1pi != ge1 or lt1pi != lt1 or le1pi != le1
    ...  or in1pi != in1 or between1pi != between1 or csubpi != csub or missingpi != missing
    ...  or alwaystrue1pi != alwaystrue1 or alwaysfalsepi != alwaysfalse)
    False
    >>> (eq1 != eq1pi or gt1 != gt1pi or ge1 != ge1pi or lt1 != lt1pi or le1 != le1pi
    ...  or in1 != in1pi or between1 != between1pi or csub != csubpi or missing != missingpi
    ...  or alwaystrue1 != alwaystrue1pi or alwaysfalse != alwaysfalsepi)
    False

    >>> (eq1pi == gt1pi or gt1pi == ge1pi or ge1pi == lt1pi or lt1pi == le1pi or le1pi == in1pi
    ...  or in1pi == between1pi or between1pi == csubpi or csubpi == missingpi
    ...  or missingpi == alwaystrue1pi or alwaystrue1pi == alwaysfalsepi)
    False

    >>> ge1pi.rec_key
    'asn'
    >>> ge1pi.op_param
    42
    >>> ge1pi.init_args
    ('asn', 42)

    >>> in1pi.rec_key
    'asn'
    >>> in1pi.op_param
    OPSet([42, 456])
    >>> in1pi.op_param == in1.op_param and in1pi.op_param is not in1.op_param
    True
    >>> in1pi.init_args
    ('asn', OPSet([42, 456]))
    >>> in1pi.init_args == in1.init_args and in1pi.init_args is not in1.init_args
    True

    >>> between1pi.rec_key
    'count'
    >>> between1pi.op_param
    (1, 100)
    >>> between1pi.init_args
    ('count', (1, 100))

    >>> alwaystrue1pi.truthness
    True
    >>> alwaystrue1pi.init_args
    (True,)


    Compound conditions
    ===================

    Certain types of conditions -- namely: `NotCond`, `AndCond` and
    `OrCond` -- are compound ones, i.e., you can use them to combine
    various conditions to produce tree-like structures. For example:

    >>> simple1 = cond_builder['url'].is_null()
    >>> simple1
    <IsNullCond: 'url'>
    >>> simple2 = cond_builder['ip'] == '1.2.3.4'
    >>> simple2
    <EqualCond: 'ip', '1.2.3.4'>
    >>> simple3 = cond_builder['asn'] <= 42
    >>> simple3
    <LessOrEqualCond: 'asn', 42>

    >>> not1 = cond_builder.not_(simple1)
    >>> not1
    <NotCond: <IsNullCond: 'url'>>
    >>> not1.subcond
    <IsNullCond: 'url'>
    >>> not1.subconditions
    OPSet([<IsNullCond: 'url'>])
    >>> not1.init_args
    (OPSet([<IsNullCond: 'url'>]),)

    >>> and1 = cond_builder.and_(simple3, simple1)
    >>> and1
    <AndCond: <LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>>
    >>> and1.subconditions
    OPSet([<LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>])
    >>> and1.init_args
    (OPSet([<LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>]),)

    >>> or1 = cond_builder.or_(simple2, simple3)
    >>> or1
    <OrCond: <EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>>
    >>> or1.subconditions
    OPSet([<EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>])
    >>> or1.init_args
    (OPSet([<EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>]),)

    >>> cond_builder.or_(
    ...     not1,
    ...     and1,
    ...     cond_builder.not_(or1),
    ... ) == cond_builder.or_(
    ...     cond_builder.not_(
    ...         cond_builder['url'].is_null(),
    ...     ),
    ...     cond_builder.and_(
    ...         cond_builder['asn'] <= 42,
    ...         cond_builder['url'].is_null(),
    ...     ),
    ...     cond_builder.not_(
    ...         cond_builder.or_(
    ...             cond_builder['ip'] == '1.2.3.4',
    ...             cond_builder['asn'] <= 42,
    ...         ),
    ...     ),
    ... )
    True

    >>> not1 == not1
    True
    >>> not1 != not1
    False
    >>> not1 == cond_builder.not_(simple1)
    True
    >>> not1 != cond_builder.not_(simple1)
    False

    >>> and1 == and1 and or1 == or1
    True
    >>> and1 != and1 or or1 != or1
    False
    >>> and1 == cond_builder.and_(simple3, simple1) and or1 == cond_builder.or_(simple2, simple3)
    True
    >>> and1 != cond_builder.and_(simple3, simple1) or or1 != cond_builder.or_(simple2, simple3)
    False
    >>> and1 == cond_builder.and_(
    ...     simple3,
    ...     cond_builder['url'].is_null(),
    ... ) == cond_builder.and_(
    ...     cond_builder['asn'] <= 42,
    ...     simple1,
    ... ) == cond_builder.and_(
    ...     cond_builder['asn'] <= 42,
    ...     cond_builder['url'].is_null(),
    ... ) == cond_builder.and_(
    ...     # (note: still equal because 42.0 == 42)
    ...     cond_builder['asn'] <= 42.0,
    ...     cond_builder['url'].is_null(),
    ... ) == AndCond._make(
    ...     LessOrEqualCond._make('asn', 42),
    ...     IsNullCond._make('url'),
    ... ) == some_visitor.make_cond(
    ...     AndCond,
    ...     some_visitor.make_cond(LessOrEqualCond, 'asn', 42),
    ...     some_visitor.make_cond(IsNullCond, 'url'),
    ... ) == cond_builder.and_([        # (alternative call style: 1 iterable of subconditions)
    ...     cond_builder['asn'] <= 42,
    ...     cond_builder['url'].is_null(),
    ... ]) == AndCond._make([           # (alternative call style: 1 iterable of subconditions)
    ...     LessOrEqualCond._make('asn', 42),
    ...     IsNullCond._make('url'),
    ... ]) == some_visitor.make_cond(
    ...     AndCond, [                  # (alternative call style: 1 iterable of subconditions)
    ...         some_visitor.make_cond(LessOrEqualCond, 'asn', 42),
    ...         some_visitor.make_cond(IsNullCond, 'url'),
    ...     ],
    ... )
    True
    >>> and1 != cond_builder.and_(
    ...     simple3,
    ...     cond_builder['fqdn'].is_null(),
    ... )
    True
    >>> and1 != AndCond._make(
    ...     LessOrEqualCond._make('asn', 123456789),
    ...     IsNullCond._make('url'),
    ... )
    True
    >>> and1 != some_visitor.make_cond(
    ...     AndCond,
    ...     some_visitor.make_cond(LessOrEqualCond, 'count', 42),
    ...     some_visitor.make_cond(IsNullCond, 'url'),
    ... )
    True
    >>> and1 != cond_builder.and_([     # (alternative call style: 1 iterable of subconditions)
    ...     simple3,
    ...     cond_builder['fqdn'].is_null(),
    ... ])
    True
    >>> and1 != AndCond._make([         # (alternative call style: 1 iterable of subconditions)
    ...     LessOrEqualCond._make('asn', 123456789),
    ...     IsNullCond._make('url'),
    ... ])
    True
    >>> and1 != some_visitor.make_cond(
    ...     AndCond, [                  # (alternative call style: 1 iterable of subconditions)
    ...         some_visitor.make_cond(LessOrEqualCond, 'count', 42),
    ...         some_visitor.make_cond(IsNullCond, 'url'),
    ...     ],
    ... )
    True

    It is worth noting that, when compound conditoons are constructed,
    duplicate subconditions are *automatically omitted*:

    >>> and1_ = cond_builder.and_(simple3, simple1, cond_builder['asn'] <= 42.0, simple3, simple1)
    >>> and1_
    <AndCond: <LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>>
    >>> and1_.subconditions
    OPSet([<LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>])
    >>> and1_.init_args
    (OPSet([<LessOrEqualCond: 'asn', 42>, <IsNullCond: 'url'>]),)
    >>> and1_ == and1 and not (and1_ != and1)
    True

    >>> or1_ = cond_builder.or_(simple2, simple3, simple3, cond_builder['asn'] <= 42.0, simple2)
    >>> or1_
    <OrCond: <EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>>
    >>> or1_.subconditions
    OPSet([<EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>])
    >>> or1_.init_args
    (OPSet([<EqualCond: 'ip', '1.2.3.4'>, <LessOrEqualCond: 'asn', 42>]),)
    >>> or1_ == or1 and not (or1_ != or1)
    True

    Also, note that the order of subconditions is *preserved* but, at
    the same time, is *irrelevant* for equality of compound condition
    objects. Therefore we have, for example:

    >>> and1 == cond_builder.and_(simple1, simple3) and or1 == cond_builder.or_(simple3, simple2)
    True
    >>> cond_builder.and_(simple1, simple3) == and1 and cond_builder.or_(simple3, simple2) == or1
    True
    >>> and1 != cond_builder.and_(simple1, simple3) or or1 != cond_builder.or_(simple3, simple2)
    False
    >>> cond_builder.and_(simple1, simple3) != and1 or cond_builder.or_(simple3, simple2) != or1
    False

    Obviously, as always, *lack of logical equivalence* implies *lack
    of equality* (but not the other way round):

    >>> and1 == cond_builder.and_(simple3, simple1, simple2)
    False
    >>> cond_builder.and_(simple3, simple1, simple2) == and1
    False
    >>> and1 != cond_builder.and_(simple3, simple1, simple2)
    True
    >>> cond_builder.and_(simple3, simple1, simple2) != and1
    True
    >>> or1 == cond_builder.or_(simple1, simple2, simple3)
    False
    >>> cond_builder.or_(simple1, simple2, simple3) == or1
    False
    >>> or1 != cond_builder.or_(simple1, simple2, simple3)
    True
    >>> cond_builder.or_(simple1, simple2, simple3) != or1
    True

    >>> not1 == and1 or and1 == not1 or not1 == or1 or or1 == not1
    False
    >>> not1 != and1 and and1 != not1 and not1 != or1 and or1 != not1
    True
    >>> and1 == or1 or or1 == and1
    False
    >>> and1 != or1 and or1 != and1
    True
    >>> and1 == cond_builder.or_(simple3, simple1) or or1 == cond_builder.and_(simple2, simple3)
    False
    >>> and1 != cond_builder.or_(simple3, simple1) and or1 != cond_builder.and_(simple2, simple3)
    True
    >>> not1 == simple1 or simple1 == not1
    False
    >>> not1 != simple1 and simple1 != not1
    True
    >>> and1 == simple2 or simple2 == and1 or and1 == simple3 or simple3 == and1
    False
    >>> and1 != simple2 and simple2 != and1 and and1 != simple3 and simple3 != and1
    True
    >>> or1 == simple2 or simple2 == or1 or or1 == simple3 or simple3 == or1
    False
    >>> or1 != simple2 and simple2 != or1 and or1 != simple3 and simple3 != or1
    True

    Let's check a few more complex cases...

    >>> or2 = cond_builder.or_(and1, not1, simple2)
    >>> and2 = cond_builder.and_(or1, or2)
    >>> not2 = cond_builder.not_(and2)
    >>> not2 == NotCond._make(
    ...     AndCond._make(
    ...         or1,
    ...         OrCond._make(
    ...             and1,
    ...             not1,
    ...             simple2,
    ...         ),
    ...     ),
    ... ) == NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... ) == NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(                         # (different order of subconditions
    ...                 IsNullCond._make('url'),           # is irrelevant for equality)
    ...                 LessOrEqualCond._make('asn', 42),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... ) == NotCond._make(
    ...     AndCond._make(           # (different order of subconditions
    ...         OrCond._make(        # is irrelevant for equality)
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...     ),
    ... )
    True
    >>> not2 != NotCond._make(
    ...     AndCond._make(
    ...         or1,
    ...         OrCond._make(
    ...             and1,
    ...             not1,
    ...             simple2,
    ...         ),
    ...     )
    ... ) or not2 != NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    False
    >>> or2.init_args == (OPSet([and1, not1, simple2]),)
    True
    >>> or2.subconditions == or2.init_args[0] == OPSet([and1, not1, simple2])
    True
    >>> and2.init_args == (OPSet([or1, or2]),)
    True
    >>> and2.subconditions == and2.init_args[0] == OPSet([or1, or2])
    True
    >>> not2.init_args == (OPSet([and2]),)
    True
    >>> not2.subconditions == not2.init_args[0] == OPSet([and2])
    True
    >>> not2.subcond == and2
    True

    Note that even a small difference (that is, when any operand, even
    only one, is not equal to the corresponding one) causes that whole
    compound conditions are not equal:

    >>> not3 = NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 43),        # 43 instead of 42
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    >>> not4 = NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('urls'),     # 'urls' instead of 'url'
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    >>> not5 = NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessCond._make('asn', 42),    # `LessCond` instead of `LessOrEqualCond`
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    >>> not6 = NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),                                       # missing condition (`NotCond...`)
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    >>> not7 = NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...                 GreaterCond._make('asn', 0),         # added condition (`GreaterCond...`)
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    >>> not2 == not3 or not2 == not4 or not2 == not5 or not2 == not6 or not2 == not7
    False
    >>> not3 == not2 or not3 == not4 or not3 == not5 or not3 == not6 or not3 == not7
    False
    >>> not4 == not2 or not4 == not3 or not4 == not5 or not4 == not6 or not4 == not7
    False
    >>> not5 == not2 or not5 == not3 or not5 == not4 or not5 == not6 or not5 == not7
    False
    >>> not6 == not2 or not6 == not3 or not6 == not4 or not6 == not5 or not6 == not7
    False
    >>> not7 == not2 or not7 == not3 or not7 == not4 or not7 == not5 or not7 == not6
    False
    >>> not2 != not3 and not2 != not4 and not2 != not5 and not2 != not6 and not2 != not7
    True
    >>> not3 != not2 and not3 != not4 and not3 != not5 and not3 != not6 and not3 != not7
    True
    >>> not4 != not2 and not4 != not3 and not4 != not5 and not4 != not6 and not4 != not7
    True
    >>> not5 != not2 and not5 != not3 and not5 != not4 and not5 != not6 and not5 != not7
    True
    >>> not6 != not2 and not6 != not3 and not6 != not4 and not6 != not5 and not6 != not7
    True
    >>> not7 != not2 and not7 != not3 and not7 != not4 and not7 != not5 and not7 != not6
    True

    >>> a_set = {
    ...     cond_builder.or_(and1, not1, simple2),
    ...     cond_builder.true(),
    ... }
    >>> or2 in a_set
    True
    >>> alwaystrue1 in a_set
    True
    >>> alwaysfalse in a_set
    False
    >>> between1 in a_set
    False
    >>> or1 in a_set
    False

    >>> another_set = {
    ...     not2, not3, not4,
    ...     cond_builder['count'].between(1, 100),
    ... }
    >>> not2 in another_set and not3 in another_set and not4 in another_set
    True
    >>> between1 in another_set
    True
    >>> or1 in another_set or or2 in another_set
    False
    >>> alwaystrue1 in another_set or alwaysfalse in another_set
    False
    >>> not5 in another_set or not6 in another_set or not7 in another_set
    False

    >>> a_set & another_set == set()
    True
    >>> yet_another_set = {
    ...     not3,
    ...     cond_builder.true(),
    ... }
    >>> a_set & yet_another_set == {
    ...     cond_builder.true(),
    ... }
    True
    >>> yet_another_set & another_set == {
    ...     not3,
    ... }
    True
    >>> a_set - yet_another_set == {
    ...     cond_builder.or_(and1, not1, simple2),
    ... }
    True
    >>> another_set - yet_another_set == {
    ...     not2, not4,
    ...     cond_builder['count'].between(1, 100),
    ... }
    True
    >>> a_set ^ another_set == a_set | another_set == a_set | another_set | yet_another_set == {
    ...     cond_builder.or_(and1, not1, simple2),
    ...     cond_builder.true(),
    ...     not2, not3, not4,
    ...     cond_builder['count'].between(1, 100),
    ... }
    True

    >>> import copy
    >>> copy.copy(or2) is or2
    True
    >>> copy.copy(and2) is and2
    True
    >>> copy.copy(not2) is not2
    True
    >>> copy.deepcopy(or2) is or2
    True
    >>> copy.deepcopy(and2) is and2
    True
    >>> copy.deepcopy(not2) is not2
    True

    >>> import pickle
    >>> not1pi = pickle.loads(pickle.dumps(not1, pickle.DEFAULT_PROTOCOL))
    >>> not2pi = pickle.loads(pickle.dumps(not2, pickle.DEFAULT_PROTOCOL))
    >>> not1 == not1pi == not1 and not (not1 != not1pi or not1pi != not1) and not1 is not not1pi
    True
    >>> not2 == not2pi == not2 and not (not2 != not2pi or not2pi != not2) and not2 is not not2pi
    True
    >>> not2pi == NotCond._make(
    ...     AndCond._make(           # (different order of subconditions
    ...         OrCond._make(        # is irrelevant for equality)
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             NotCond._make(
    ...                 IsNullCond._make('url'),
    ...             ),
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...     ),
    ... )
    True
    >>> not1 != not2pi != not1 and not (not1 == not2pi or not2pi == not1) and not1 is not not2pi
    True
    >>> not2 != not1pi != not2 and not (not2 == not1pi or not1pi == not2) and not2 is not not1pi
    True
    >>> not2pi != NotCond._make(
    ...     AndCond._make(
    ...         OrCond._make(
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...             LessOrEqualCond._make('asn', 42),
    ...         ),
    ...         OrCond._make(
    ...             AndCond._make(
    ...                 LessOrEqualCond._make('asn', 42),
    ...                 IsNullCond._make('url'),
    ...             ),                                       # missing condition (`NotCond...`)
    ...             EqualCond._make('ip', '1.2.3.4'),
    ...         ),
    ...     ),
    ... )
    True
    >>> (not2pi.subconditions == not2.subconditions
    ...  and not2pi.subconditions is not not2.subconditions)
    True
    >>> (not2pi.subcond == not2.subcond and not2pi.subcond == and2
    ...  and not2pi.subcond is not not2.subcond
    ...  and not2pi.subcond is not and2)
    True


    Specific features of constructors
    =================================

    Generally, no matter in which way instances of concrete `Cond`
    subclasses are created --

    * constructors of some `Cond` subclasses normalize the arguments
      passed to them (so that the corresponding instance attributes are
      always of certain types) -- for example:

      >>> c = cond_builder['asn'].in_([1, 42, 123])  # some iterable (here: list) -> `OPSet` object
      >>> c.op_param
      OPSet([1, 42, 123])
      >>> c.init_args[1]
      OPSet([1, 42, 123])
      >>> c
      <InCond: 'asn', {1, 42, 123}>

    * for certain combinations of `Cond` subclasses and constructor
      arguments you may get an instance of a *different* class than you
      might expect -- because of *condition logic reductions* (resulting
      in producing a condition that is logically equivalent to the
      specified one but simpler) or similar *adjustments*; a few
      selected examples:

      >>> cond_builder.or_(cond_builder['asn'] < 123)   # OR with 1 argument -> just that argument
      <LessCond: 'asn', 123>

      >>> cond_builder.and_(cond_builder['asn'] < 123)  # AND with 1 argument -> just that argument
      <LessCond: 'asn', 123>

      >>> cond_builder.or_()     # OR without arguments -> fixed FALSE
      <FixedCond: False>

      >>> cond_builder.and_()    # AND without arguments -> fixed TRUE
      <FixedCond: True>

      >>> cond_builder.or_(cond_builder['asn'] > 5,         # OR with arguments
      ...                  cond_builder.true(),             # including fixed TRUE
      ...                  cond_builder['url'].is_null())   # -> reduce to fixed TRUE
      <FixedCond: True>

      >>> cond_builder.and_(cond_builder['asn'] > 5,        # AND with arguments
      ...                   cond_builder.false(),           # including fixed FALSE
      ...                   cond_builder['url'].is_null())  # -> reduce to fixed FALSE
      <FixedCond: False>

      >>> cond_builder.or_(cond_builder['asn'] > 5,         # OR directly within OR -> flatten
      ...                  cond_builder.or_(cond_builder['url'].is_null(),
      ...                                   cond_builder['fqdn'] == 'x'))
      <OrCond: <GreaterCond: 'asn', 5>, <IsNullCond: 'url'>, <EqualCond: 'fqdn', 'x'>>

      >>> cond_builder.and_(cond_builder.and_(cond_builder['asn'] > 5,
      ...                                     cond_builder['url'].is_null()),
      ...                   cond_builder['fqdn'] == 'x')    # AND directly within AND -> flatten
      <AndCond: <GreaterCond: 'asn', 5>, <IsNullCond: 'url'>, <EqualCond: 'fqdn', 'x'>>

      >>> cond_builder.not_(cond_builder.not_(cond_builder['asn'] < 123))    # `NOT (NOT x) -> x`
      <LessCond: 'asn', 123>

      >>> cond_builder['asn'].in_(())    # IN with empty operation parameter -> fixed FALSE
      <FixedCond: False>

      >>> c = cond_builder.or_(
      ...     cond_builder.and_(
      ...         cond_builder['who'] == 'Robin',
      ...         cond_builder['asn'].in_([]), # -> fixed FALSE (reducing enclosing AND to FALSE)
      ...     ), # -> fixed FALSE (insignificant for enclosing OR)
      ...     cond_builder['who'] == 'Lancelot',
      ...     cond_builder.not_(
      ...         cond_builder.not_(
      ...             cond_builder.or_(
      ...                 cond_builder['who'] == 'Galahad',
      ...                 cond_builder['who'] == 'Galahad', # (to be skipped as duplicate)
      ...                 cond_builder.and_(
      ...                     cond_builder['who'] == 'Bedivere',
      ...                     cond_builder.not_(
      ...                         cond_builder.not_(
      ...                             cond_builder.and_(
      ...                                 cond_builder['asn'].between(1, 65535),
      ...                                 cond_builder.or_(
      ...                                     cond_builder['ip'] == '1.2.3.4',
      ...                                     cond_builder['count'].in_([2, 3, 5, 7, 11, 13, 17]),
      ...                                     cond_builder.not_(
      ...                                         cond_builder.and_(
      ...                                             cond_builder.or_(), # -> fixed FALSE
      ...                                         ), # -> fixed FALSE
      ...                                     ), # -> fixed TRUE (reducing enclosing OR to TRUE)
      ...                                 ), # -> fixed TRUE (insignificant for enclosing AND)
      ...                                 cond_builder.or_(
      ...                                     cond_builder['url'].contains_substring('://'),
      ...                                     cond_builder.and_(
      ...                                         cond_builder.true(), # (insignif. for encl. AND)
      ...                                         cond_builder['url'].contains_substring('://'),
      ...                                         cond_builder['url'].contains_substring('://'),
      ...                                         cond_builder['url'].contains_substring('://'),
      ...                                     ), # -> `url contains...` (duplicates skipped)
      ...                                     cond_builder['url'].contains_substring('://'),
      ...                                     cond_builder['url'].contains_substring('://'),
      ...                                 ), # -> `url contains...` (duplicates skipped)
      ...                             ), # -> `asn between...` AND `url contains...`
      ...                         ), # -> NOT (`asn between...` AND `url contains...`)
      ...                     ), # -> `asn between...` AND `url contains...`
      ...                 ), # -> `who="Bedivere"` AND `asn between...` AND `url contains...`
      ...                 cond_builder['who'] == 'Galahad', # (to be skipped as duplicate)
      ...                 cond_builder.and_(
      ...                     cond_builder.or_(
      ...                         cond_builder.and_(), # -> fixed TRUE (reducing encl. OR to TRUE)
      ...                         cond_builder['name'] == 'Arthur "Two Sheds" Jackson',
      ...                     ), # -> fixed TRUE (insignificant for enclosing AND)
      ...                     cond_builder['who'] == 'Arthur',
      ...                 ), # -> `who="Arthur"`
      ...                 cond_builder['who'] == 'Galahad', # (to be skipped as duplicate)
      ...                 cond_builder.and_(
      ...                     cond_builder.not_(
      ...                         cond_builder.and_(
      ...                             cond_builder.false(), # (reducing enclosing AND to FALSE)
      ...                             cond_builder['name'] == 'Arthur "Two Sheds" Jackson',
      ...                         ), # -> fixed FALSE
      ...                     ), # -> fixed TRUE (insignificant for enclosing AND)
      ...                     cond_builder.or_(
      ...                         cond_builder.not_(               # <------------,
      ...                             cond_builder['foo'] > 100,                  # (these two
      ...                         ),                                              # complement
      ...                         cond_builder['spam'] <= 1234,                   # each other
      ...                         cond_builder['foo'] > 100,       # <------------`
      ...                     ), # -> fixed TRUE (insignificant for enclosing AND)
      ...                     cond_builder.not_(
      ...                         cond_builder.and_(
      ...                             cond_builder['bar'] >= 0,
      ...                             cond_builder['bar'] < 123,   # <------------, (these two
      ...                             cond_builder['bar'] < 256,                  # complement
      ...                             cond_builder.not_(           # <------------` each other)
      ...                                 cond_builder['bar'] < 123,
      ...                             ),
      ...                         ), # -> fixed FALSE
      ...                     ), # -> fixed TRUE (insignificant for enclosing AND)
      ...                     cond_builder['who'] == 'Arthur',
      ...                     cond_builder.or_(
      ...                         cond_builder['who'] == 'Arthur',
      ...                         cond_builder.and_(
      ...                             cond_builder['who'] == 'Arthur',
      ...                             cond_builder.not_(
      ...                                 cond_builder.not_(
      ...                                     cond_builder['who'] == 'Arthur',
      ...                                 ), # -> NOT (`who="Arthur"`)
      ...                             ), # `who="Arthur"`
      ...                         ), # `who="Arthur"` (duplicates skipped)
      ...                     ),  # `who="Arthur"` (duplicates skipped)
      ...                 ), # -> `who="Arthur"` (duplicates skipped; to be skipped as duplicate)
      ...                 cond_builder.and_(
      ...                     cond_builder['who'] == 'Bedivere',
      ...                     cond_builder['asn'].between(1, 65535),
      ...                     cond_builder['url'].contains_substring('://'),
      ...                 ), # (to be skipped as duplicate)
      ...                 cond_builder['who'] == 'Galahad', # (to be skipped as duplicate)
      ...             ), # -> `who="Galahad"` OR (`who="Bedivere"` AND...) OR `who="Arthur"`
      ...         ), # -> NOT (`who="Galahad"` OR (`who="Bedivere"` AND...) OR `who="Arthur"`)
      ...     ), # -> `who="Galahad"` OR (`who="Bedivere"` AND...) OR `who="Arthur"`
      ... ) # -> `who="Lancelot"` OR `who="Galahad"` OR (`who="Bedivere"` AND...) OR `who="Arthur"`
      >>> repr(c) == (
      ...     "<OrCond: "
      ...         "<EqualCond: 'who', 'Lancelot'>, "
      ...         "<EqualCond: 'who', 'Galahad'>, "
      ...         "<AndCond: "
      ...             "<EqualCond: 'who', 'Bedivere'>, "
      ...             "<BetweenCond: 'asn', (1, 65535)>, "
      ...             "<ContainsSubstringCond: 'url', '://'>>, "
      ...         "<EqualCond: 'who', 'Arthur'>>")
      True

    For more information about those features -- see the "Construction"
    sections of the docs of concrete `Cond` subclasses.


    Pure Boolean (two-valued) logic
    ===============================

    It should be emphasized that all tools provided by this module -- in
    particular all concrete subclasses of `Cond` -- are intended to be
    used in the context of the ordinary Boolean (two-valued) logic, that
    is, the logic based on the two values: *TRUE* and *FALSE*.

    So, if there is a need to process `Cond` instances in a context of
    another logic -- in particular, the three-valued logic used in the
    SQL language, based on the *TRUE*, *FALSE* and *NULL* values -- then
    a very careful translation must be applied to avoid any confusion
    and possible bugs (hint: in the context of SQL's `WHERE` clauses,
    the crux of the challenge lies in appropriate treatment of *logical
    negation*, i.e., in appropriate translation of `NotCond` conditions,
    together with their, direct and indirect, `RecItemCond`-derived
    subconditions...).


    Keys missing from data records
    ==============================

    Coming back to the ordinary Boolean (two-valued) logic we use here...

    While within it there is *no* notion of a *NULL* (or *unknown*, or
    *missing*) *logical value*, we *do* provide the notion of a possible
    fact that a certain key (*record key*) is *missing* from some *data
    record* (or some kind of *NULL* value is assigned to that key);
    selection of any data records to which such a fact applies is
    represented by an `IsNullCond` condition object (note that such a
    condition still represents a logical sentence whose only possible
    values are *TRUE* and *FALSE*).

    An important consequence is that -- for a data record from which a
    certain *record key* is missing (*NULL*) -- the logical values of any
    relevant `RecItemCond`-derived conditions *except* `IsNullCond` are
    *FALSE*. (So, for example, for any *data record* `rec` from which
    the *record key* `key` is missing, for any *operation parameter*
    `val`, the logical values of the `rec[key] < val` condition *and*
    the `rec[key] >= val` conditon are **both** *FALSE*!)

    It means that, in the *general case*, a `RecItemParamCond`-derived
    condition representing a comparison operator, e.g. (for any valid
    `key` and `val`):

        `LessCond._make(key, val)`   # that is: `rec[key] < val`

    -- is *not logically equivalent* to a condition based on *negation*
    of the "opposite" operator, e.g. (for the same `key` and `val`):

        `NotCond._make(              # that is: `NOT (rec[key] >= val)`
            GreaterOrEqualCond._make(key, val))

    ...or to any other *negation*-based equivalent of the latter, e.g.
    (for the same `key` and `val`):

        `NotCond._make(              # that is: `NOT ((rec[key] > val) OR (rec[key] == val))`
            `OrCond._make(
                GreaterCond._make(key, val),
                EqualCond._make(key, val))

    (Note: the second and third conditions are logically equivalent
    to each other, but -- in the *general case* -- *none* of them is
    equivalent to the first one!)


    TODO: add info about the possibiliy of multi-value items in data
    records and about the consequences of that:
         * why e.g.
           * `x == 1 AND x == 3 AND x < 1 AND x > 3` may be *TRUE*
           * `NOT (x == 1) OR NOT (x == 3)` may be *FALSE*
         * why e.g. `x BETWEEN 1 AND 3`, in the *general case*, is
           *not* logically equivalent to `x >= 1 AND x <= 3`

    """


    #
    # Instance construction basics

    def __new__(cls, *args, **kwargs):
        raise TypeError(ascii_str(
            f'cannot create {cls.__qualname__} instances directly '
            f'(use {CondBuilder.__qualname__} instead)'))

    # A non-public constructor:
    # * to be called *only* by internals of this module.
    @classmethod
    @attr_required('_adapt_init_args')
    def _make(cls, *given_init_args):
        init_args = cls._adapt_init_args(*given_init_args)
        instance = cls._get_initialized_instance(*init_args)
        hash(instance)  # (raises `TypeError` if any item of `init_args` is not hashable)
        assert isinstance(instance, Cond)  # (<- not necessarily an instance of `cls`)
        return instance

    # A non-public constructor helper:
    # * to be called *only* from within the `_make()` constructor;
    # * can be *extended* in subclasses (e.g., to create an
    #   instance of another `Cond` subclass than `cls`...).
    @classmethod
    @attr_required('__init__')
    def _get_initialized_instance(cls, *init_args):
        instance = call_new_of_super(super(), cls, *init_args)
        instance.init_args = init_args
        instance.__init__(*init_args)
        return instance


    #
    # Abstract methods (concrete subclasses *must* have them implemented)

    _adapt_init_args: Callable[..., tuple[Hashable, ...]]

    __init__: Callable[..., None]


    #
    # Public interface of instances

    init_args: tuple[Hashable, ...]

    def __repr__(self):
        return f'<{self.__class__.__qualname__}: {self._format_content_for_repr()}>'

    def __eq__(self, other):
        if isinstance(other, Cond):
            return (self._eq_test_components == other._eq_test_components)
        return NotImplemented

    def __hash__(self):
        return self._hash_value

    # * support for `copy.copy()`/`copy.deepcopy()`:

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    # * support for pickling and unpickling:

    def __reduce__(self):
        return (
            object.__new__,
            (self.__class__,),
            self.__dict__,
        )


    #
    # Non-public helpers

    @functools.cached_property
    def _hash_value(self):
        return hash(self._eq_test_components)

    @functools.cached_property
    def _eq_test_components(self):
        return self.__class__, self.init_args

    # (may be overridden in subclasses if necessary)
    def _format_content_for_repr(self):
        return ', '.join(map(repr, self.init_args))


class CompoundCond(Cond):

    """
    The base class for *compound* data selection conditions.

    Provides the following *public instance attribute* (aside from
    `init_args`):

    * `subconditions` -- an `OPSet` of objects (being instances of
      concrete `Cond` subclasses) that represent the underlying
      subconditions.

    The `_make()` non-public constructor provided by concrete subclasses
    accepts positional arguments (either *exactly one* or *any number*
    of them, depending on a subclass) that must be instances of some
    concrete subclasses of `Cond` -- these instances become the contents
    of the `subconditions` collection described above (their order is
    preserved, though it is irrelevant when it comes to equality of
    condition objects). Alternatively, those `Cond` instances can be
    given in the form of exactly one argument being an iterable that
    yields (contains) them.

    >>> cond_builder = CondBuilder()
    >>> my_conjunction = cond_builder.and_(
    ...     cond_builder['ip'] == '123.124.125.126',
    ...     cond_builder['asn'] >= 42,
    ...     cond_builder['count'].between(1, 1000),
    ... )
    >>> my_disjunction = cond_builder.or_(
    ...     cond_builder['url'].contains_substring('tp://exampl\u0119.'),
    ...     cond_builder.not_(
    ...         cond_builder['cc'].is_null(),
    ...     ),
    ... )
    >>> my_negation = cond_builder.not_(
    ...     cond_builder.and_(
    ...         my_disjunction,
    ...         cond_builder['asn'].in_([1, 42, 12345]),
    ...     ),
    ... )
    >>> bigger_piece = cond_builder.or_(my_conjunction, my_negation)
    >>> bigger_piece == OrCond._make(
    ...     AndCond._make(
    ...         # (different order of subconditions is irrelevant for equality)
    ...         BetweenCond._make('count', (1, 1000)),
    ...         EqualCond._make('ip', '123.124.125.126'),
    ...         GreaterOrEqualCond._make('asn', 42),
    ...     ),
    ...     NotCond._make(
    ...         # (below -- alternative call style: 1 iterable of subconditions)
    ...         AndCond._make([
    ...             OrCond._make(OPSet([
    ...                 # (different order of subconditions is irrelevant for equality)
    ...                 NotCond._make({
    ...                     IsNullCond._make('cc'),
    ...                 }),
    ...                 ContainsSubstringCond._make('url', 'tp://exampl\u0119.'),
    ...             ])),
    ...             InCond._make('asn', (1, 42, 12345)),
    ...         ]),
    ...     ),
    ... )
    True
    >>> repr(bigger_piece) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'ip', '123.124.125.126'>, "
    ...             "<GreaterOrEqualCond: 'asn', 42>, "
    ...             "<BetweenCond: 'count', (1, 1000)>>, "
    ...         "<NotCond: "
    ...             "<AndCond: "
    ...                 "<OrCond: "
    ...                     "<ContainsSubstringCond: 'url', 'tp://exampl\u0119.'>, "
    ...                     "<NotCond: "
    ...                         "<IsNullCond: 'cc'>>>, "
    ...                 "<InCond: 'asn', {1, 42, 12345}>>>>")
    True

    ***

    >>> issubclass(CompoundCond, Cond)
    True

    >>> issubclass(NotCond, CompoundCond)
    True
    >>> issubclass(AndCond, CompoundCond)
    True
    >>> issubclass(OrCond, CompoundCond)
    True

    ***

    For more information and examples -- see:

    * the "Compound conditions" section of the docs of the `Cond` base
      class;

    * the docs of `CompoundMultiCond` which is a (more specialized but
      still abstract) subclass of this class;

    * the docs of the concrete subclasses.
    """

    @classmethod
    def _adapt_init_args(cls, *given_init_args):
        subconditions = cls._extract_subconditions(given_init_args)
        assert isinstance(subconditions, OPSet)
        if not all(isinstance(subcond, Cond) for subcond in subconditions):
            raise cls._make_init_args_error(given_init_args)
        return (subconditions,)

    @classmethod
    def _extract_subconditions(cls, given_init_args):
        assert isinstance(given_init_args, tuple)
        if len(given_init_args) == 1 and not isinstance(given_init_args[0], Cond):
            subconditions = given_init_args[0]
            if isinstance(subconditions, OPSet):
                return subconditions
        else:
            subconditions = given_init_args
        try:
            return OPSet(subconditions)
        except TypeError as exc:
            # Here the problem with `subconditions` is that either it is
            # a non-iterable object or contains some non-hashable item(s).
            raise cls._make_init_args_error(given_init_args) from exc

    @classmethod
    def _make_init_args_error(cls, given_init_args):
        arg_listing = ', '.join(map(repr, given_init_args))
        return TypeError(ascii_str(
            f"{cls.__qualname__}'s constructor requires that "
            f"all its arguments, or all items of exactly one "
            f"iterable argument, are instances of subclasses "
            f"of {Cond.__qualname__} (got: {arg_listing})"))

    def __init__(self, subconditions: OPSet[Cond]):
        self.subconditions = subconditions

    def _format_content_for_repr(self):
        return ', '.join(map(repr, self.subconditions))

    #
    # Public interface extension

    subconditions: OPSet[Cond]


class CompoundMultiCond(CompoundCond):

    """
    An abstract subclass of `CompoundCond` being the base class of those
    condition classes whose instances represent *multi-operand* compound
    data selection conditions.

    See the docs of `CompoundCond`, except that the `_make()` non-public
    constructor provided by concrete subclasses is supposed to always
    accept *any number* of subcondition objects (`Cond` instances).

    ***

    >>> issubclass(CompoundMultiCond, CompoundCond)
    True

    >>> issubclass(AndCond, CompoundMultiCond)
    True
    >>> issubclass(OrCond, CompoundMultiCond)
    True

    >>> not issubclass(NotCond, CompoundMultiCond)
    True
    """

    #
    # Non-public abstract attributes (concrete subclasses *must* provide them)

    _neutral_truthness: ClassVar[bool]
    _absorbing_truthness: ClassVar[bool]


    #
    # Non-public `CompoundMultiCond`-specific instance construction stuff

    @classmethod
    def _adapt_init_args(cls, *given_init_args):
        (subconditions,) = super()._adapt_init_args(*given_init_args)
        assert (isinstance(subconditions, OPSet)
                and all(isinstance(subcond, Cond) for subcond in subconditions))

        # A few obvious reductions (see the docs of `AndCond` and
        # `OrCond`):

        # * skipping the *neutral* element, e.g.:
        #   * `TRUE AND x` -> `x`
        #   * `FALSE OR x` -> `x`
        subconditions -= {FixedCond._make(cls._neutral_truthness)}

        # * *flattening*, e.g.:
        #   * `a AND (b AND c) AND d` -> `a AND b AND c AND d`
        #   * `a OR (b OR c) OR d` -> `a OR b OR c OR d`
        subconditions = OPSet(
            subc
            for subcond in subconditions
                for subc in (
                    subcond.subconditions if isinstance(subcond, cls)
                    else (subcond,)))

        # (note: *deduplication* of subconditions is guaranteed thanks
        # to using `OPSet`)
        return (subconditions,)

    @classmethod
    def _get_initialized_instance(cls, subconditions):
        assert (isinstance(subconditions, OPSet)
                and all(isinstance(subcond, Cond) for subcond in subconditions))

        # A few other obvious reductions (see the docs of `AndCond` and
        # `OrCond`):

        # * unwrapping the subcondition, if there is only one
        if len(subconditions) == 1:
            (subcond,) = subconditions
            return subcond

        # * getting the *neutral* element, if there are no subconditions:
        #   * `ALL of <nothing>` -> `TRUE`
        #   * `ANY of <nothing>` -> `FALSE`
        if not subconditions:
            return FixedCond._make(cls._neutral_truthness)

        # * reducing to the *absorbing* element, if it is present:
        #   * `FALSE AND <whatever>` -> `FALSE`
        #   * `TRUE OR <whatever>` -> `TRUE`
        if FixedCond._make(cls._absorbing_truthness) in subconditions:
            return FixedCond._make(cls._absorbing_truthness)

        # * making use of the *complement* law, if applicable:
        #   * `x AND (NOT x) [AND <whatever>]` -> `FALSE`
        #   * `x OR (NOT x) [OR <whatever>]` -> `TRUE`
        negated_subconditions = OPSet(map(NotCond._make, subconditions))
        if not subconditions.isdisjoint(negated_subconditions):
            return FixedCond._make(cls._absorbing_truthness)

        return super()._get_initialized_instance(subconditions)


class RecItemCond(Cond):

    """
    The base class for any *record-item-concerned* data selection
    conditions (i.e., conditions regarding items of data records
    being selected).

    Provides the following *public instance attribute* (aside from
    `init_args`):

    * `rec_key` (ASCII-only `str`) -- the concerned data *record key*
      (e.g.: `'asn'`, or `'fqdn'`, or `'url'`, or `'category'`...).

    The `_make()` non-public constructor provided by concrete subclasses
    accepts one or more (depending on a particular subclass) positional
    arguments.

    The first of the arguments is always the *record key* -- it must be
    an ASCII-only `str` (such as `'asn'`, `'fqdn'`, `'url'`, etc.); it
    becomes the value of the `rec_key` attribute described above.

    ***

    >>> issubclass(RecItemCond, Cond)
    True

    >>> issubclass(EqualCond, RecItemCond)
    True
    >>> issubclass(GreaterCond, RecItemCond)
    True
    >>> issubclass(GreaterOrEqualCond, RecItemCond)
    True
    >>> issubclass(LessCond, RecItemCond)
    True
    >>> issubclass(LessOrEqualCond, RecItemCond)
    True
    >>> issubclass(InCond, RecItemCond)
    True
    >>> issubclass(BetweenCond, RecItemCond)
    True
    >>> issubclass(ContainsSubstringCond, RecItemCond)
    True
    >>> issubclass(IsTrueCond, RecItemCond)
    True
    >>> issubclass(IsNullCond, RecItemCond)
    True

    >>> not issubclass(FixedCond, RecItemCond)
    True

    ***

    For more information and examples -- see:

    * the docs of `RecItemParamCond` which is a (more specialized but
      still abstract) subclass of this class;

    * the docs of the concrete subclasses and the portions of the docs
      of the `Cond` base class relevant to those subclasses.
    """

    @classmethod
    def _adapt_init_args(cls, rec_key):
        return (cls._adapt_rec_key(rec_key),)

    @classmethod
    def _adapt_rec_key(cls, rec_key):
        if not isinstance(rec_key, str):
            raise TypeError(ascii_str(
                f"{cls.__qualname__}'s constructor requires `rec_key` "
                f"being a str (got: {rec_key!r} which is an instance "
                f"of {rec_key.__class__.__qualname__})"))
        if not rec_key.isascii():
            raise ValueError(ascii_str(
                f"{cls.__qualname__}'s constructor requires `rec_key` "
                f"being an ASCII-only str (got: {rec_key!r})"))
        return rec_key

    def __init__(self, rec_key: str):
        self.rec_key = rec_key

    #
    # Public interface extension

    rec_key: str


class RecItemParamCond(RecItemCond):

    """
    The base class for *record-item-value-concerned* data selection
    conditions (i.e., to select data records by *values* a certain
    *record key* maps to).

    Inherits or provides the following *public instance attributes*
    (aside from `init_args`):

    * `rec_key` (ASCII-only `str`) -- the concerned data *record key*
      (e.g.: `'asn'`, or `'fqdn'`, or `'url'`, or `'category'`...).

    * `op_param` -- the *operation parameter*, that is, the value of
      the parameter for the selection operation (the actual operation is
      defined by a concrete subclass).

    The `_make()` non-public constructor provided by concrete subclasses
    accepts one or two positional arguments.

    The first of the arguments is always the *record key* -- it must be
    an ASCII-only `str` (such as `'asn'`, `'fqdn'`, `'url'`, etc.); it
    becomes the value of the `rec_key` attribute described above.

    The second of the arguments, if provided, becomes (maybe after some
    subclass-specific coercion) the value of the `op_param` attribute
    described above -- which can be, for example: some `asn` value
    (such as `42`), or a collection of desired `fqdn` values (such as
    `('foo.pl', 'bar.jp', 'baz.us')`), or some substring of desired
    `url` values (such as `'tp://example.'`)...

    >>> EqualCond._make('asn', 42)
    <EqualCond: 'asn', 42>

    >>> InCond._make('fqdn', ['foo.pl', 'bar.jp', 'baz.us'])
    <InCond: 'fqdn', {'foo.pl', 'bar.jp', 'baz.us'}>

    >>> ContainsSubstringCond._make('url', 'tp://example.')
    <ContainsSubstringCond: 'url', 'tp://example.'>

    If the second argument is not provided, i.e., we have zero *operation
    parameters* given, then `_make()` of a `RecItemParamCond` subclass
    returns a condition representing *logical falsehood* (that is, a
    `FixedCond` instance whose `truthness` attribute is set to `False`).
    At first glance, the existence of this feature may seem odd, but --
    occasionally -- you may find it convenient when implementing
    *condition visitors* (considering that `make_cond()` of visitors
    is a thin wrapper of `_make()` of condition classes; see:
    `CondVisitor.make_cond()`...). (On the other hand, `CondBuilder`
    does *not* provide any way to make use of this feature.)

    >>> EqualCond._make('asn')
    <FixedCond: False>

    >>> InCond._make('fqdn')
    <FixedCond: False>

    >>> ContainsSubstringCond._make('url')
    <FixedCond: False>

    A related extra feature is that for certain concrete subclasses of
    `RecItemParamCond` -- namely, those which have the class attribute
    `accepting_many_op_params` set to true -- multiple *operation
    parameters* can be given (as the second and consecutive arguments to
    `_make()`). In such cases a condition representing an appropriate
    *inclusive disjunction* (an `OrCond`) is obtained:

    >>> EqualCond._make('asn', 42, 43, 12345)
    <OrCond: <EqualCond: 'asn', 42>, <EqualCond: 'asn', 43>, <EqualCond: 'asn', 12345>>

    >>> ContainsSubstringCond._make('url', 'tp://', 'tps://')
    <OrCond: <ContainsSubstringCond: 'url', 'tp://'>, <ContainsSubstringCond: 'url', 'tps://'>>

    On the other hand, for those `RecItemParamCond` subclasses which
    have the `accepting_many_op_params` class attribute set to false
    passing multiple *operation parameters* causes `TypeError`:

    >>> GreaterOrEqualCond._make('asn', 42, 43, 12345)                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...

    >>> InCond._make('fqdn', ['foo.pl', 'bar.jp', 'baz.us'], ['too.much'])     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...

    ***

    >>> issubclass(RecItemParamCond, RecItemCond)
    True

    >>> issubclass(EqualCond, RecItemParamCond)
    True
    >>> issubclass(GreaterCond, RecItemParamCond)
    True
    >>> issubclass(GreaterOrEqualCond, RecItemParamCond)
    True
    >>> issubclass(LessCond, RecItemParamCond)
    True
    >>> issubclass(LessOrEqualCond, RecItemParamCond)
    True
    >>> issubclass(InCond, RecItemParamCond)
    True
    >>> issubclass(BetweenCond, RecItemParamCond)
    True
    >>> issubclass(ContainsSubstringCond, RecItemParamCond)
    True

    >>> not issubclass(IsTrueCond, RecItemParamCond)
    True
    >>> not issubclass(IsNullCond, RecItemParamCond)
    True
    >>> not issubclass(FixedCond, RecItemParamCond)
    True

    ***

    For more information and examples -- see the docs of the concrete
    subclasses and the portions of the docs of the `Cond` base class
    relevant to those subclasses.
    """

    @classmethod
    def _adapt_init_args(cls, rec_key, *op_parameters):
        (rec_key,) = super()._adapt_init_args(rec_key)
        if len(op_parameters) > 1 and not cls.accepting_many_op_params:
            op_param_listing = ', '.join(map(repr, op_parameters))
            raise TypeError(ascii_str(
                f"{cls.__qualname__}'s constructor does not "
                f"accept multiple operation parameters (got: "
                f"{op_param_listing})"))
        return (rec_key,) + tuple(cls._iter_adapted_op_parameters(op_parameters))

    @classmethod
    def _iter_adapted_op_parameters(cls, op_parameters):
        for op_param in op_parameters:
            try:
                yield cls._adapt_op_param(op_param)
            except TypeError as exc:
                raise TypeError(ascii_str(
                    f"{cls.__qualname__}'s constructor got illegal "
                    f"operation parameter: {op_param!r} ({exc})")) from exc

    @classmethod
    def _adapt_op_param(cls, op_param):
        if op_param is None:
            # The main reason we do not support parameters being `None`
            # is that the behavior of Python operations involving `None`
            # is fundamentally different from the *NULL*-propagating
            # (*three-valued logic*-based) behavior of corresponding SQL
            # operations. By forbidding use of `None` as a parameter, we
            # avoid a lot of confusion related to those differences.
            # (Note that there is a parameterless condition class --
            # derived directly from `RecItemCond` -- representing the
            # *is missing from data record* condition: `IsNullCond`.)
            # See also: the "Pure Boolean (two-valued) logic" and "Keys
            # missing from data records" sections of the docs of the
            # `Cond` class.
            raise TypeError('parameters being None are not supported')
        return op_param

    @classmethod
    def _get_initialized_instance(cls, rec_key, *op_parameters):
        if len(op_parameters) != 1:
            # For interface flexibility, a number of operation
            # parameters different than 1 may be accepted -- then:
            # * for multiple parameters -- multiple instances are
            #   created and combined using `OrCond._make()`;
            # * for no parameters -- `OrCond._make()` with no arguments
            #   delegates construction to `FixedCond._make(False)` (see
            #   `OrCond`...).
            return OrCond._make(*(
                cls._make(rec_key, op_param)
                for op_param in op_parameters))
        return super()._get_initialized_instance(rec_key, *op_parameters)

    def __init__(self, rec_key: str, op_param: Hashable):
        super().__init__(rec_key)
        self.op_param = op_param

    #
    # Public interface extension

    accepting_many_op_params: ClassVar[bool]  # (<- expected to exist in concrete subclasses)

    op_param: Hashable


#
# Concrete condition classes

class NotCond(CompoundCond):

    """
    The `NOT` Boolean condition class: negation of exactly one condition
    (hereinafter referred to as *subcondition*).

    (For a certain important reminder -- and hint -- related to possible
    translation of conditions involving `NotCond` instances to their SQL
    counterparts, see: the "Pure Boolean (two-valued) logic" section of
    the docs of the `Cond` class.)


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `subconditions` -- a 1-element `OPSet` containing the object (an
      instance of a concrete subclass of `Cond`) that represents the
      underlying subcondition.

    * `subcond` -- a convenience attribute: its value is just the only
      element of `subconditions` (that is, the object that represents
      the underlying subcondition).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * *Exactly one* positional argument is accepted; it must be an
      instance of a `Cond` subclass, or an iterable object whose
      only item is such an instance (or `TypeError` will be raised).
      The given `Cond` instance becomes the only element of the
      `subconditions` collection, a well as the value of `subcond`
      (see above: "Specific public instance attributes"):

      >>> c = NotCond._make(LessCond._make('asn', 42))
      >>> c
      <NotCond: <LessCond: 'asn', 42>>
      >>> c.init_args
      (OPSet([<LessCond: 'asn', 42>]),)
      >>> c.subcond == LessCond._make('asn', 42)
      True
      >>> c.subconditions == c.init_args[0] == OPSet([LessCond._make('asn', 42)])
      True

      >>> c2 = NotCond._make([LessCond._make('asn', 42)])
      >>> c2
      <NotCond: <LessCond: 'asn', 42>>
      >>> c2.init_args
      (OPSet([<LessCond: 'asn', 42>]),)
      >>> c2.subcond == LessCond._make('asn', 42)
      True
      >>> c2.subconditions == c2.init_args[0] == OPSet([LessCond._make('asn', 42)])
      True
      >>> c2 == c
      True

      >>> NotCond._make('foo')                          # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: 'foo')

      >>> NotCond._make(['foo'])                        # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: ['foo'])

      >>> NotCond._make()
      Traceback (most recent call last):
        ...
      TypeError: NotCond's constructor accepts exactly 1 subcondition (0 given)

      >>> NotCond._make([])
      Traceback (most recent call last):
        ...
      TypeError: NotCond's constructor accepts exactly 1 subcondition (0 given)

      >>> NotCond._make(LessCond._make('asn', 42), IsNullCond._make('url'))
      Traceback (most recent call last):
        ...
      TypeError: NotCond's constructor accepts exactly 1 subcondition (2 given)

      >>> NotCond._make([LessCond._make('asn', 42), IsNullCond._make('url')])
      Traceback (most recent call last):
        ...
      TypeError: NotCond's constructor accepts exactly 1 subcondition (2 given)


    Condition logic reductions/adjustments
    --------------------------------------

    * If the given subcondition is a `FixedCond` instance, a `FixedCond`
      instance representing negation of the given one is obtained:

      >>> NotCond._make(FixedCond._make(True))
      <FixedCond: False>
      >>> NotCond._make([FixedCond._make(True)])
      <FixedCond: False>

      >>> NotCond._make(FixedCond._make(False))
      <FixedCond: True>
      >>> NotCond._make([FixedCond._make(False)])
      <FixedCond: True>

      The (obvious) rationale is that -- logically -- `NOT TRUE` is just
      `FALSE`, and `NOT FALSE` is just `TRUE`.

    * If the given subcondition is a `NotCond` instance, its subcondition
      (*not* wrapped in a `NotCond`) replaces the whole condition:

      >>> NotCond._make(NotCond._make(LessCond._make('asn', 42)))
      <LessCond: 'asn', 42>
      >>> NotCond._make([NotCond._make(LessCond._make('asn', 42))])
      <LessCond: 'asn', 42>
      >>> NotCond._make(NotCond._make([LessCond._make('asn', 42)]))
      <LessCond: 'asn', 42>
      >>> NotCond._make([NotCond._make([LessCond._make('asn', 42)])])
      <LessCond: 'asn', 42>

      >>> NotCond._make(NotCond._make(NotCond._make(LessCond._make('asn', 42))))
      <NotCond: <LessCond: 'asn', 42>>

      >>> NotCond._make(NotCond._make(NotCond._make(NotCond._make(LessCond._make('asn', 42)))))
      <LessCond: 'asn', 42>

      The (obvious) rationale is that -- logically -- `NOT (NOT <something>)`
      is just that `<something>` (i.e., a *double negation* is being
      cancelled out).
    """

    @classmethod
    def _adapt_init_args(cls, *given_init_args):
        (subconditions,) = super()._adapt_init_args(*given_init_args)
        assert (isinstance(subconditions, OPSet)
                and all(isinstance(subcond, Cond) for subcond in subconditions))
        if len(subconditions) != 1:
            raise TypeError(ascii_str(
                f"{cls.__qualname__}'s constructor accepts exactly 1 "
                f"subcondition ({len(subconditions)} given)"))
        return (subconditions,)

    @classmethod
    def _get_initialized_instance(cls, subconditions):
        assert (isinstance(subconditions, OPSet)
                and len(subconditions) == 1)
        (subcond,) = subconditions
        assert isinstance(subcond, Cond)

        # A few obvious reductions:

        if isinstance(subcond, FixedCond):
            # * `NOT TRUE` -> `FALSE`
            # * `NOT FALSE` -> `TRUE`
            return FixedCond._make(not subcond.truthness)

        if isinstance(subcond, NotCond):
            # * `NOT (NOT x)` -> `x`
            return subcond.subcond

        return super()._get_initialized_instance(subconditions)

    #
    # Public interface extension

    @functools.cached_property
    def subcond(self) -> Cond:
        assert len(self.subconditions) == 1
        (subcond,) = self.subconditions
        assert isinstance(subcond, Cond)
        return subcond


class AndCond(CompoundMultiCond):

    """
    The `AND` Boolean condition class: conjunction of, possibly many,
    conditions (hereinafter referred to as *subconditions*).


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `subconditions` -- an `OPSet` containing objects (instances of
      concrete subclasses of `Cond`) that represent the underlying
      subconditions (note that their order is preserved, though it
      is irrelevant when it comes to equality of condition objects).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * Multiple positional arguments are accepted; all of them must be
      instances of `Cond` subclasses (or `TypeError` will be raised).
      Alternatively, exactly one iterable object should be passed in
      -- then it must contain only instances of `Cond` subclasses (or
      `TypeError` will be raised). Those `Cond` instances become the
      elements of the `subconditions` collection (see above: "Public
      instance attributes...").

      >>> c = AndCond._make(LessCond._make('asn', 42), IsNullCond._make('ip'))
      >>> c
      <AndCond: <LessCond: 'asn', 42>, <IsNullCond: 'ip'>>
      >>> c.init_args
      (OPSet([<LessCond: 'asn', 42>, <IsNullCond: 'ip'>]),)
      >>> c.subconditions == c.init_args[0] == OPSet([
      ...     LessCond._make('asn', 42),
      ...     IsNullCond._make('ip'),
      ... ])
      True

      >>> c2 = AndCond._make([LessCond._make('asn', 42), IsNullCond._make('ip')])
      >>> c2
      <AndCond: <LessCond: 'asn', 42>, <IsNullCond: 'ip'>>
      >>> c2.init_args
      (OPSet([<LessCond: 'asn', 42>, <IsNullCond: 'ip'>]),)
      >>> c2.subconditions == c2.init_args[0] == OPSet([
      ...     LessCond._make('asn', 42),
      ...     IsNullCond._make('ip'),
      ... ])
      True
      >>> c2 == c
      True

      >>> AndCond._make('asn', 42)                     # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: 'asn', 42)

      >>> AndCond._make(['asn', 42])                   # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: ['asn', 42])


    Condition logic reductions/adjustments
    --------------------------------------

    * If the given subconditions include some `FixedCond` instances
      representing *logical truth*, those instances are skipped:

      >>> AndCond._make(EqualCond._make('asn', 1),
      ...               FixedCond._make(True),       # <- fixed TRUE
      ...               IsNullCond._make('url'))
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> AndCond._make([EqualCond._make('asn', 1),
      ...                FixedCond._make(True),      # <- fixed TRUE
      ...                IsNullCond._make('url')])
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      The rationale is that -- logically -- `TRUE AND ...something...`
      is just that `...something...` (in theoretical terms: `TRUE` is
      the *neutral element* [aka *identity*] of `AND`, so adding `TRUE`
      to the set of operands never changes the result).

    * If the given subconditions include some `AndCond` instances, each
      of them is replaced with its subconditions (so we can say that
      `AndCond` conditions are being *flattened*):

      >>> c = AndCond._make(
      ...     AndCond._make(
      ...         EqualCond._make('asn', 1),
      ...         IsNullCond._make('url'),
      ...     ),
      ...     AndCond._make(
      ...         EqualCond._make('fqdn', 'x.y'),
      ...         AndCond._make([
      ...             InCond._make('count', (44, 55, 66)),
      ...             InCond._make('cc', ('PL', 'JP')),
      ...         ]),
      ...         AndCond._make([
      ...             AndCond._make(
      ...                 EqualCond._make('source', 'aa.bb'),
      ...                 NotCond._make(
      ...                     AndCond._make(
      ...                         EqualCond._make('category', 'bots'),
      ...                         AndCond._make(
      ...                             NotCond._make(
      ...                                 EqualCond._make('name', 'foo'),
      ...                             ),
      ...                             InCond._make('count', (11, 22, 33, 44, 55)),
      ...                         ),
      ...                     ),
      ...                 ),
      ...             ),
      ...             BetweenCond._make('count', (55, 99)),
      ...         ]),
      ...     ),
      ... )
      >>> repr(c) == (
      ...     "<AndCond: "
      ...         "<EqualCond: 'asn', 1>, "
      ...         "<IsNullCond: 'url'>, "
      ...         "<EqualCond: 'fqdn', 'x.y'>, "
      ...         "<InCond: 'count', {44, 55, 66}>, "
      ...         "<InCond: 'cc', {'PL', 'JP'}>, "
      ...         "<EqualCond: 'source', 'aa.bb'>, "
      ...         "<NotCond: "
      ...             "<AndCond: "
      ...                 "<EqualCond: 'category', 'bots'>, "
      ...                 "<NotCond: "
      ...                     "<EqualCond: 'name', 'foo'>>, "
      ...                 "<InCond: 'count', {11, 22, 33, 44, 55}>>>, "
      ...         "<BetweenCond: 'count', (55, 99)>>")
      True

      The rationale is that -- logically -- `a AND b AND c`, `a AND (b
      AND c)` and `(a AND b) AND c` are all (obviously) equivalent to
      each other (in theoretical terms: thanks to the *associative
      property* of `AND`).

    * If the given subconditions include some duplicates, that is, any
      conditions (instances of any concrete subclasses of `Cond`) being
      equal to a condition already encountered in the subcondition list,
      those superfluous instances are skipped:

      >>> AndCond._make(EqualCond._make('asn', 1),
      ...               IsNullCond._make('url'),
      ...               IsNullCond._make('url'),        # <- duplicate
      ...               EqualCond._make('asn', 1.0),    # <- duplicate
      ...               IsNullCond._make('url'))        # <- duplicate
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> AndCond._make([EqualCond._make('asn', 1),
      ...                IsNullCond._make('url'),
      ...                IsNullCond._make('url'),       # <- duplicate
      ...                EqualCond._make('asn', 1.0),   # <- duplicate
      ...                IsNullCond._make('url')])      # <- duplicate
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      The (rather obvious) rationale is that -- logically -- `x AND x`
      is just `x` (in theoretical terms: `AND` is *idempotent*),
      combined with the fact that the order and parenthesization of
      operands could be freely changed keeping the meaning of the whole
      condition (in theoretical terms: `AND` is *commutative* and
      *associative*); so, for example, `x AND y AND x` is equivalent
      to `(x AND x) AND y`, and -- therefore -- to `x AND y`.

      Thanks to the type of the `subconditions` attribute, `OPSet`,
      this rule is applied automatically, also *after* applying the
      "flattening" rule (described above) -- so we have, for example:

      >>> AndCond._make(AndCond._make(EqualCond._make('asn', 1),
      ...                             IsNullCond._make('url')),
      ...               IsNullCond._make('url'),                      # <- duplicate
      ...               AndCond._make([EqualCond._make('asn', 1.0),   # <- duplicate
      ...                              IsNullCond._make('url')]))     # <- duplicate
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> AndCond._make([AndCond._make([EqualCond._make('asn', 1),
      ...                               IsNullCond._make('url')]),
      ...                IsNullCond._make('url'),                     # <- duplicate
      ...                AndCond._make(EqualCond._make('asn', 1.0),   # <- duplicate
      ...                              IsNullCond._make('url'))])     # <- duplicate
      <AndCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

    * If the number of subconditions is 1, just the object representing
      the subcondition is obtained:

      >>> AndCond._make(LessCond._make('asn', 42))
      <LessCond: 'asn', 42>

      >>> AndCond._make([LessCond._make('asn', 42)])
      <LessCond: 'asn', 42>

      This rule is applied *after* the "all fixed TRUE conditions are
      skipped" and "all duplicates are skipped" rules (both described
      above) -- for example:

      >>> AndCond._make(EqualCond._make('asn', 1),
      ...               EqualCond._make('asn', 1),   # <- duplicate
      ...               FixedCond._make(True))       # <- fixed TRUE
      <EqualCond: 'asn', 1>

      >>> AndCond._make([EqualCond._make('asn', 1),
      ...                EqualCond._make('asn', 1),  # <- duplicate
      ...                FixedCond._make(True)])     # <- fixed TRUE
      <EqualCond: 'asn', 1>

    * If the number of subconditions is 0, a `FixedCond` instance
      representing *logical truth* is obtained:

      >>> AndCond._make()
      <FixedCond: True>

      >>> AndCond._make([])
      <FixedCond: True>

      The rationale is that -- logically -- `ALL of nothing` is `TRUE`
      (in theoretical terms: `TRUE` is the *neutral element* of `AND`,
      so adding `TRUE` to the set of operands should never change the
      result -- *also if that set was initially empty*). Note that, e.g.
      also in Python, the result of `all([])` is `True`.

      This rule is applied *after* applying the "all fixed TRUE
      conditions are skipped" rule (described above) -- so:

      >>> AndCond._make(FixedCond._make(True))
      <FixedCond: True>

      >>> AndCond._make([FixedCond._make(True)])
      <FixedCond: True>

      Note the consistency of these results with the rule concerning
      the 1-subcondition case (described above).

    * If the given subconditions include a `FixedCond` instance
      representing *logical falsehood*, a `FixedCond` instance
      representing *logical falsehood* is obtained:

      >>> AndCond._make(EqualCond._make('asn', 1),
      ...               FixedCond._make(False),      # <- fixed FALSE
      ...               IsNullCond._make('url'))
      <FixedCond: False>

      >>> AndCond._make([EqualCond._make('asn', 1),
      ...                FixedCond._make(False),     # <- fixed FALSE
      ...                IsNullCond._make('url')])
      <FixedCond: False>

      The rationale is that -- logically -- `FALSE AND ...whatever...`
      is always `FALSE` (in theoretical terms: `FALSE` is the *absorbing
      element* [aka *annihilating element*] of `AND`).

    * If the given subconditions include a condition object whose
      negation (made by wrapping it in a `NotCond`) is equal to another
      subcondition (so the former is logically equivalent to the latter
      when negated), a `FixedCond` instance representing *logical
      falsehood* is obtained:

      >>> AndCond._make(EqualCond._make('asn', 1),
      ...               EqualCond._make('count', 42),                  # <------- they complement
      ...               NotCond._make(EqualCond._make('count', 42)),   # <---------'   each other
      ...               IsNullCond._make('url'))
      <FixedCond: False>

      >>> AndCond._make([EqualCond._make('asn', 1),
      ...                EqualCond._make('count', 42),                 # <------- they complement
      ...                NotCond._make(EqualCond._make('count', 42)),  # <---------'   each other
      ...                IsNullCond._make('url')])
      <FixedCond: False>

      The rationale is that -- logically -- `x AND (NOT x)` is `FALSE`
      (in theoretical terms: because of the *complement* law), and then
      -- see the previous bullet point.
    """

    _neutral_truthness: ClassVar[bool] = True
    _absorbing_truthness: ClassVar[bool] = False


class OrCond(CompoundMultiCond):

    """
    The `OR` Boolean condition class: inclusive disjunction of, possibly
    many, conditions (hereinafter referred to as *subconditions*).


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `subconditions` -- an `OPSet` containing objects (instances of
      concrete subclasses of `Cond`) that represent the underlying
      subconditions (note that their order is preserved, though it
      is irrelevant when it comes to equality of condition objects).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * Multiple positional arguments are accepted; all of them must be
      instances of `Cond` subclasses (or `TypeError` will be raised).
      Alternatively, exactly one iterable object should be passed in
      -- then it must contain only instances of `Cond` subclasses (or
      `TypeError` will be raised). Those `Cond` instances become the
      elements of the `subconditions` collection (see above: "Public
      instance attributes...").

      >>> c = OrCond._make(LessCond._make('asn', 42), IsNullCond._make('ip'))
      >>> c
      <OrCond: <LessCond: 'asn', 42>, <IsNullCond: 'ip'>>
      >>> c.init_args
      (OPSet([<LessCond: 'asn', 42>, <IsNullCond: 'ip'>]),)
      >>> c.subconditions == c.init_args[0] == OPSet([
      ...     LessCond._make('asn', 42),
      ...     IsNullCond._make('ip'),
      ... ])
      True

      >>> c2 = OrCond._make([LessCond._make('asn', 42), IsNullCond._make('ip')])
      >>> c2
      <OrCond: <LessCond: 'asn', 42>, <IsNullCond: 'ip'>>
      >>> c2.init_args
      (OPSet([<LessCond: 'asn', 42>, <IsNullCond: 'ip'>]),)
      >>> c2.subconditions == c2.init_args[0] == OPSet([
      ...     LessCond._make('asn', 42),
      ...     IsNullCond._make('ip'),
      ... ])
      True
      >>> c2 == c
      True

      >>> OrCond._make('asn', 42)                      # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: 'asn', 42)

      >>> OrCond._make(['asn', 42])                    # doctest: +ELLIPSIS
      Traceback (most recent call last):
        ...
      TypeError: ...instances of subclasses of Cond (got: ['asn', 42])


    Condition logic reductions/adjustments
    --------------------------------------

    * If the given subconditions include some `FixedCond` instances
      representing *logical falsehood*, those instances are skipped:

      >>> OrCond._make(EqualCond._make('asn', 1),
      ...              FixedCond._make(False),       # <- fixed FALSE
      ...              IsNullCond._make('url'))
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> OrCond._make([EqualCond._make('asn', 1),
      ...               FixedCond._make(False),      # <- fixed FALSE
      ...               IsNullCond._make('url')])
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      The rationale is that -- logically -- `FALSE OR ...something...`
      is just that `...something...` (in theoretical terms: `FALSE` is
      the *neutral element* [aka *identity*] of `OR`, so adding `FALSE`
      to the set of operands never changes the result).

    * If the given subconditions include some `OrCond` instances, each
      of them is replaced with its subconditions (so we can say that
      `OrCond` conditions are being *flattened*):

      >>> c = OrCond._make(
      ...     OrCond._make([
      ...         EqualCond._make('asn', 1),
      ...         IsNullCond._make('url'),
      ...     ]),
      ...     OrCond._make(
      ...         EqualCond._make('fqdn', 'x.y'),
      ...         OrCond._make([
      ...             InCond._make('asn', (4, 5, 6)),
      ...             InCond._make('cc', ('PL', 'JP')),
      ...         ]),
      ...         OrCond._make(
      ...             OrCond._make([
      ...                 EqualCond._make('source', 'aa.bb'),
      ...                 NotCond._make(
      ...                     OrCond._make([
      ...                         EqualCond._make('source', 'c.d'),
      ...                         OrCond._make([
      ...                             NotCond._make(
      ...                                 EqualCond._make('source', 'e.f'),
      ...                             ),
      ...                             InCond._make('count', (1, 2, 3)),
      ...                         ]),
      ...                     ]),
      ...                 ),
      ...             ]),
      ...             BetweenCond._make('asn', (7, 8)),
      ...         ),
      ...     ),
      ... )
      >>> repr(c) == (
      ...     "<OrCond: "
      ...         "<EqualCond: 'asn', 1>, "
      ...         "<IsNullCond: 'url'>, "
      ...         "<EqualCond: 'fqdn', 'x.y'>, "
      ...         "<InCond: 'asn', {4, 5, 6}>, "
      ...         "<InCond: 'cc', {'PL', 'JP'}>, "
      ...         "<EqualCond: 'source', 'aa.bb'>, "
      ...         "<NotCond: "
      ...             "<OrCond: "
      ...                 "<EqualCond: 'source', 'c.d'>, "
      ...                 "<NotCond: "
      ...                     "<EqualCond: 'source', 'e.f'>>, "
      ...                 "<InCond: 'count', {1, 2, 3}>>>, "
      ...         "<BetweenCond: 'asn', (7, 8)>>")
      True

      The rationale is that -- logically -- `a OR b OR c`, `a OR (b
      OR c)` and `(a OR b) OR c` are all (obviously) equivalent to
      each other (in theoretical terms: thanks to the *associative
      property* of `OR`).

    * If the given subconditions include some duplicates, that is, any
      conditions (instances of any concrete subclasses of `Cond`) being
      equal to a condition already encountered in the subcondition list,
      those superfluous instances are skipped:

      >>> OrCond._make(EqualCond._make('asn', 1),
      ...              IsNullCond._make('url'),
      ...              IsNullCond._make('url'),        # <- duplicate
      ...              EqualCond._make('asn', 1.0),    # <- duplicate
      ...              IsNullCond._make('url'))        # <- duplicate
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> OrCond._make([EqualCond._make('asn', 1),
      ...               IsNullCond._make('url'),
      ...               IsNullCond._make('url'),       # <- duplicate
      ...               EqualCond._make('asn', 1.0),   # <- duplicate
      ...               IsNullCond._make('url')])      # <- duplicate
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      The (rather obvious) rationale is that -- logically -- `x OR x` is
      just `x` (in theoretical terms: `OR` is *idempotent*), combined
      with the fact that the order and parenthesization of operands
      could be freely changed keeping the meaning of the whole condition
      (in theoretical terms: `OR` is *commutative* and *associative*);
      so, for example, `x OR y OR x` is equivalent to `(x OR x) OR y`,
      and -- therefore -- to `x OR y`.

      Thanks to the type of the `subconditions` attribute, `OPSet`,
      this rule is applied automatically, also *after* applying the
      "flattening" rule (described above) -- so we have, for example:

      >>> OrCond._make(OrCond._make(EqualCond._make('asn', 1),
      ...                           IsNullCond._make('url')),
      ...              IsNullCond._make('url'),                     # <- duplicate
      ...              OrCond._make([EqualCond._make('asn', 1.0),   # <- duplicate
      ...                            IsNullCond._make('url')]))     # <- duplicate
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

      >>> OrCond._make([OrCond._make([EqualCond._make('asn', 1),
      ...                             IsNullCond._make('url')]),
      ...               IsNullCond._make('url'),                    # <- duplicate
      ...               OrCond._make(EqualCond._make('asn', 1.0),   # <- duplicate
      ...                            IsNullCond._make('url'))])     # <- duplicate
      <OrCond: <EqualCond: 'asn', 1>, <IsNullCond: 'url'>>

    * If the number of subconditions is 1, just the object representing
      the subcondition is obtained:

      >>> OrCond._make(LessCond._make('asn', 42))
      <LessCond: 'asn', 42>

      >>> OrCond._make([LessCond._make('asn', 42)])
      <LessCond: 'asn', 42>

      This rule is applied *after* the "all fixed FALSE conditions are
      skipped" and "all duplicates are skipped" rules (both described
      above) -- for example:

      >>> OrCond._make(EqualCond._make('asn', 1),
      ...              EqualCond._make('asn', 1),    # <- duplicate
      ...              FixedCond._make(False))       # <- fixed FALSE
      <EqualCond: 'asn', 1>

      >>> OrCond._make([EqualCond._make('asn', 1),
      ...               EqualCond._make('asn', 1),   # <- duplicate
      ...               FixedCond._make(False)])     # <- fixed FALSE
      <EqualCond: 'asn', 1>

    * If the number of subconditions is 0, a `FixedCond` instance
      representing *logical falsehood* is obtained:

      >>> OrCond._make()
      <FixedCond: False>

      >>> OrCond._make([])
      <FixedCond: False>

      The rationale is that -- logically -- `ANY of nothing` is `FALSE`
      (in theoretical terms: `FALSE` is the *neutral element* of `OR`,
      so adding `FALSE` to the set of operands should never change the
      result -- *also if that set was initially empty*). Note that, e.g.
      also in Python, the result of `any([])` is `False`.

      This rule is applied *after* applying the "all fixed FALSE
      conditions are skipped" rule (described above) -- so:

      >>> OrCond._make(FixedCond._make(False))
      <FixedCond: False>

      >>> OrCond._make([FixedCond._make(False)])
      <FixedCond: False>

      Note the consistency of these results with the rule concerning
      the 1-subcondition case (described above).

    * If the given subconditions include a `FixedCond` instance
      representing *logical truth*, a `FixedCond` instance representing
      *logical truth* is obtained:

      >>> OrCond._make(EqualCond._make('asn', 1),
      ...              FixedCond._make(True),        # <- fixed TRUE
      ...              IsNullCond._make('url'))
      <FixedCond: True>

      >>> OrCond._make([EqualCond._make('asn', 1),
      ...               FixedCond._make(True),       # <- fixed TRUE
      ...               IsNullCond._make('url')])
      <FixedCond: True>

      The rationale is that -- logically -- `TRUE OR ...whatever...`
      is always `TRUE` (in theoretical terms: `TRUE` is the *absorbing
      element* [aka *annihilating element*] of `OR`).

    * If the given subconditions include a condition object whose
      negation (made by wrapping it in a `NotCond`) is equal to another
      subcondition (so the former is logically equivalent to the latter
      when negated), a `FixedCond` instance representing *logical truth*
      is obtained:

      >>> OrCond._make(EqualCond._make('asn', 1),
      ...              NotCond._make(EqualCond._make('count', 42)),   # <--,
      ...              IsNullCond._make('url'),        #                 they complement each other
      ...              EqualCond._make('count', 42))   # <-----------------'
      <FixedCond: True>

      >>> OrCond._make([EqualCond._make('asn', 1),
      ...               NotCond._make(EqualCond._make('count', 42)),  # <--,
      ...               IsNullCond._make('url'),        #                they complement each other
      ...               EqualCond._make('count', 42)])  # <----------------'
      <FixedCond: True>

      The rationale is that -- logically -- `x OR (NOT x)` is `TRUE` (in
      theoretical terms: because of the *complement* law), and then --
      see the previous bullet point.
    """

    _neutral_truthness: ClassVar[bool] = False
    _absorbing_truthness: ClassVar[bool] = True


class EqualCond(RecItemParamCond):

    """
    The "is the specified data item equal to ...?" condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `rec_key` (ASCII-only `str`) -- the concerned data *record key*
      (e.g.: `'asn'`, or `'fqdn'`, or `'url'`, or `'category'`...).

    * `op_param` -- the *operation parameter* which, for this class,
      is supposed to be the actual value of the `==` comparisons'
      right-hand operand.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The 1st argument must be a `str` (otherwise `TypeError` is raised)
      and it must be ASCII-only (or `ValueError` is raised); the argument
      becomes the value of the `rec_key` attribute.

    * Any other arguments are *operation parameters* (for the multiple
      parameters case -- see the "Condition logic reductions/adjustments"
      subsection below). An *operation parameter* cannot be `None` (or
      `TypeError` is raised).

    >>> c1 = EqualCond._make('asn', 42)
    >>> c1
    <EqualCond: 'asn', 42>
    >>> c1.rec_key
    'asn'
    >>> c1.op_param
    42
    >>> c1.init_args
    ('asn', 42)

    >>> c2 = EqualCond._make('fqdn', 'foo.bar')
    >>> c2
    <EqualCond: 'fqdn', 'foo.bar'>
    >>> c2.rec_key
    'fqdn'
    >>> c2.op_param
    'foo.bar'
    >>> c2.init_args
    ('fqdn', 'foo.bar')

    >>> EqualCond._make('asn', None)                 # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> EqualCond._make(42, 'asn')                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: 42 which is an instance of int)

    >>> EqualCond._make('władca_żlebów'.encode('utf-8'), 42)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: ... which is an instance of bytes)

    >>> EqualCond._make('władca_żlebów', 42)         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> EqualCond._make()                            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'


    Condition logic reductions/adjustments
    --------------------------------------

    * If the number of the given *operation parameters* is *not* equal
      to 1, an `EqualCond` instance is created for each of them, and
      then `OrCond` is used to combine those `EqualCond` instances.
      For example:

      >>> EqualCond._make('asn', 1, 42, 500)
      <OrCond: <EqualCond: 'asn', 1>, <EqualCond: 'asn', 42>, <EqualCond: 'asn', 500>>

      Note, however, that if the number of the given *operation
      parameters* is 0, the object that is eventually obtained is
      a `FixedCond` instance whose `truthness` is `False` (in fact,
      as a result of the relevant `OrCond`-specific condition logic
      reduction):

      >>> EqualCond._make('asn')
      <FixedCond: False>
    """

    #
    # Public interface refinement

    accepting_many_op_params: ClassVar[bool] = True


class GreaterCond(RecItemParamCond):

    """
    The "is the specified data item greater than ...?" condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `EqualCond` docs -- with the obvious
    proviso that here we consider the `>` comparison (not `==`).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    See: the relevant parts of the `EqualCond` docs -- with the proviso
    that `GreaterCond.accepting_many_op_params` is `False`, so
    *multiple operation parameters are disallowed* (they cause
    `TypeError`).

    >>> c = GreaterCond._make('asn', 42)
    >>> c
    <GreaterCond: 'asn', 42>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    42
    >>> c.init_args
    ('asn', 42)

    >>> GreaterCond._make('asn', None)               # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> GreaterCond._make(42, 'asn')                 # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: 42 which is an instance of int)

    >>> GreaterCond._make('władca_żlebów', 42)       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> GreaterCond._make('władca_żlebów', 42)       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> GreaterCond._make()                          # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'

    >>> GreaterCond._make('asn', 1, 42, 500)         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...


    Condition logic reductions/adjustments
    --------------------------------------

    * If the operation parameter is not given, a `FixedCond` instance
      whose `truthness` is `False` is obtained:

      >>> GreaterCond._make('asn')
      <FixedCond: False>
    """

    #
    # Public interface refinement

    accepting_many_op_params: ClassVar[bool] = False


class GreaterOrEqualCond(RecItemParamCond):

    """
    The "is the specified data item greater than or equal to ...?"
    condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `GreaterCond` docs -- with the
    obvious proviso that here we consider the `>=` comparison.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    See: the relevant parts of the `GreaterCond` docs.

    >>> c = GreaterOrEqualCond._make('asn', 42)
    >>> c
    <GreaterOrEqualCond: 'asn', 42>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    42
    >>> c.init_args
    ('asn', 42)

    >>> GreaterOrEqualCond._make('asn', 1, 42, 500)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...


    Condition logic reductions/adjustments
    --------------------------------------

    * If the operation parameter is not given, a `FixedCond` instance
      whose `truthness` is `False` is obtained:

      >>> GreaterOrEqualCond._make('asn')
      <FixedCond: False>
    """

    #
    # Public interface refinement

    accepting_many_op_params: ClassVar[bool] = False


class LessCond(RecItemParamCond):

    """
    The "is the specified data item less than ...?" condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `GreaterCond` docs -- with the
    obvious proviso that here we consider the `<` comparison.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    See: the relevant parts of the `GreaterCond` docs.

    >>> c = LessCond._make('asn', 42)
    >>> c
    <LessCond: 'asn', 42>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    42
    >>> c.init_args
    ('asn', 42)

    >>> LessCond._make('asn', 1, 42, 500)            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...


    Condition logic reductions/adjustments
    --------------------------------------

    * If the operation parameter is not given, a `FixedCond` instance
      whose `truthness` is `False` is obtained:

      >>> LessCond._make('asn')
      <FixedCond: False>
    """

    #
    # Public interface refinement

    accepting_many_op_params: ClassVar[bool] = False


class LessOrEqualCond(RecItemParamCond):

    """
    The "is the specified data item less than or equal to ...?"
    condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `GreaterCond` docs -- with the
    obvious proviso that here we consider the `<=` comparison.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    See: the relevant parts of the `GreaterCond` docs.

    >>> c = LessOrEqualCond._make('asn', 42)
    >>> c
    <LessOrEqualCond: 'asn', 42>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    42
    >>> c.init_args
    ('asn', 42)

    >>> LessOrEqualCond._make('asn', 1, 42, 500)     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...


    Condition logic reductions/adjustments
    --------------------------------------

    * If the operation parameter is not given, a `FixedCond` instance
      whose `truthness` is `False` is obtained:

      >>> LessOrEqualCond._make('asn')
      <FixedCond: False>
    """

    #
    # Public interface refinement

    accepting_many_op_params: ClassVar[bool] = False


class InCond(RecItemParamCond):

    """
    The "does ... contain the specified data item?" condition class.

    Every `InCond` condition should be considered as logically
    equivalent to an `OrCond` whose subconditions are appropriate
    `EqualCond`s (remind, however, that *logical equivalence* does
    not imply *equality* of condition objects).


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `EqualCond` docs -- with the
    proviso that here `op_param` (the *operation parameter*) is an
    `OPSet` specifying the concerned set of values (note that the order
    of those values is preserved, though it is irrelevant when it comes
    to equality of condition objects).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The 1st argument must be a `str` (otherwise `TypeError` is raised)
      and it must be ASCII-only (or `ValueError` is raised); the argument
      becomes the value of the `rec_key` attribute.

    * The 2nd argument, if given, is the *operation parameter*; it must
      be an iterable object (*not* being a `str`, `bytes` or `bytearray`,
      and *not* containing/yielding `None`; otherwise `TypeError` is
      raised) specifying the concerned set of values; the argument is
      automatically converted to an `OPSet` (unless it already is an
      `OPSet`) -- which becomes the value of the `op_param` attribute.

    Note that `InCond.accepting_many_op_params` is `False`, so
    *multiple operation parameters are disallowed* (they cause
    `TypeError`).

    >>> c = InCond._make('asn', OPSet([1, 42, 12345, 765432]))
    >>> c
    <InCond: 'asn', {1, 42, 12345, 765432}>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    OPSet([1, 42, 12345, 765432])
    >>> c.init_args
    ('asn', OPSet([1, 42, 12345, 765432]))

    >>> c2 = InCond._make('asn', [42, 765432, 1, 12345])   # (some iterable => convert to `OPSet`)
    >>> c2
    <InCond: 'asn', {42, 765432, 1, 12345}>
    >>> c2.rec_key
    'asn'
    >>> c2.op_param
    OPSet([42, 765432, 1, 12345])
    >>> c2.init_args
    ('asn', OPSet([42, 765432, 1, 12345]))
    >>> c2 == c    # (note: equal, even though the order of values is different)
    True

    >>> InCond._make('asn', [1, None, 42])                              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should not contain None)

    >>> InCond._make('asn', 42)      # (non-iterable given)             # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be an OPSet or another iterable ... yielding hashable...)

    >>> InCond._make('asn', 'xy')    # (str given)                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be an OPSet or another iterable ... yielding hashable...)

    >>> InCond._make('asn', b'xy')   # (bytes given)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be an OPSet or another iterable ... yielding hashable...)

    >>> InCond._make('asn', bytearray(b'xy'))   # (bytearray given)     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be an OPSet or another iterable ... yielding hashable...)

    >>> InCond._make('asn', [42, [765432]])   # (has unhashable item)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be an OPSet or another iterable ... yielding hashable...)

    >>> InCond._make('asn', None)                                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> InCond._make([42, 12345], 'asn')                                # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: [42, 12345] which is an instance of list)

    >>> InCond._make('władca_żlebów', (42, 12345))                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> InCond._make()                                                  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'

    >>> InCond._make('asn', [1, 42, 12345], [765432])                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... does not accept multiple operation parameters ...


    Condition logic reductions/adjustments
    --------------------------------------

    * If the operation parameter is not given, a `FixedCond` instance
      whose `truthness` is `False` is obtained:

      >>> InCond._make('asn')
      <FixedCond: False>

    * If the operation parameter is an empty iterable, also a
      `FixedCond` instance whose `truthness` is `False` is obtained:

      >>> InCond._make('asn', [])
      <FixedCond: False>

    * If the operation parameter is a 1-item iterable, an equivalent
      `EqualCond` instance is obtained:

      >>> InCond._make('asn', [42])
      <EqualCond: 'asn', 42>
    """

    @classmethod
    def _adapt_op_param(cls, op_param):
        op_param = super()._adapt_op_param(op_param)
        if not isinstance(op_param, OPSet):
            try:
                if isinstance(op_param, (str, bytes, bytearray)):
                    raise TypeError(f'a str/bytes/bytearray given ({op_param!a})')
                op_param = OPSet(op_param)
            except TypeError as exc:
                raise TypeError(
                    'should be an OPSet or another iterable (but not a '
                    'str/bytes/bytearray) yielding hashable items') from exc
        if any(item is None for item in op_param):
            raise TypeError('should not contain None')
        return op_param

    @classmethod
    def _get_initialized_instance(cls, rec_key, *op_parameters):
        if len(op_parameters) == 1:
            op_param = op_parameters[0]
            assert isinstance(op_param, OPSet)
            if len(op_param) == 1:
                # equivalence: `x IN (a,)` -> `x == a`
                (equal_cond_op_param,) = op_param
                return EqualCond._make(rec_key, equal_cond_op_param)     # noqa
            elif not op_param:
                # obvious reduction:
                # <whatever> IN <empty container> -> FALSE
                return FixedCond._make(False)                            # noqa
        else:
            assert not op_parameters
        return super()._get_initialized_instance(rec_key, *op_parameters)

    def _format_content_for_repr(self):
        value_listing = ', '.join(map(repr, self.op_param))
        return f'{self.rec_key!r}, {{{value_listing}}}'

    #
    # Public interface refinements

    accepting_many_op_params: ClassVar[bool] = False

    op_param: OPSet


class BetweenCond(RecItemParamCond):

    """
    The "is the specified data item between ... and ...?" condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `EqualCond` docs -- with the proviso
    that `op_param` (the *operation parameter*) is a pair (2-tuple)
    specifying the endpoints -- the minimum value and the maximum value
    -- of the concerned interval.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The 1st argument must be a `str` (otherwise `TypeError` is raised)
      and it must be ASCII-only (or `ValueError` is raised); the argument
      becomes the value of the `rec_key` attribute.

    * Any other arguments are *operation parameters* (for the multiple
      parameters case -- see the "Condition logic reductions/adjustments"
      subsection below). An *operation parameter* must be a 2-element
      iterable convertible to a tuple (or `TypeError` is raised);
      no element of that iterable can be `None` (or `TypeError` is
      raised).

    >>> c = BetweenCond._make('asn', (42, 1234))
    >>> c
    <BetweenCond: 'asn', (42, 1234)>
    >>> c.rec_key
    'asn'
    >>> c.op_param
    (42, 1234)
    >>> c.init_args
    ('asn', (42, 1234))

    >>> c2 = BetweenCond._make('asn', [42, 1234])  # (non-tuple iterable given => convert to tuple)
    >>> c2
    <BetweenCond: 'asn', (42, 1234)>
    >>> c2.rec_key
    'asn'
    >>> c2.op_param
    (42, 1234)
    >>> c2.init_args
    ('asn', (42, 1234))
    >>> c2 == c
    True

    >>> valid_but_not_useful = BetweenCond._make('asn', (1234, 42))  # not (1st < 2nd): empty range
    >>> valid_but_not_useful
    <BetweenCond: 'asn', (1234, 42)>
    >>> valid_but_not_useful == c     # (note: *not* equal to `c`; here order matters!)
    False

    >>> BetweenCond._make('asn', (42, None))                        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (interval endpoint value must not be None)

    >>> BetweenCond._make('asn', (None, 1234))                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (interval endpoint value must not be None)

    >>> BetweenCond._make('asn', (None, None))                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (interval endpoint value must not be None)

    >>> BetweenCond._make('asn', (42,))                             # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be a 2-element iterable...)

    >>> BetweenCond._make('asn', (42, 123, 1234))                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be a 2-element iterable...)

    >>> BetweenCond._make('asn', 42)                                # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be a 2-element iterable...)

    >>> BetweenCond._make('asn', None)                              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> BetweenCond._make((42, 1234), 'asn')                        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: (42, 1234) which is an instance of tuple)

    >>> BetweenCond._make('władca_żlebów', (42, 1234))              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> BetweenCond._make()                                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'


    Condition logic reductions/adjustments
    --------------------------------------

    * If the number of the given *operation parameters* is *not* equal
      to 1, a `BetweenCond` instance is created for each of them, and
      then `OrCond` is used to combine these `BetweenCond` instances.
      For example:

      >>> c = BetweenCond._make('asn', (42, 1234), (1, 33), (76543, 76544))
      >>> repr(c) == (
      ...     "<OrCond: "
      ...         "<BetweenCond: 'asn', (42, 1234)>, "
      ...         "<BetweenCond: 'asn', (1, 33)>, "
      ...         "<BetweenCond: 'asn', (76543, 76544)>>")
      True

      Note, however, that if the number of the given *operation
      parameters* is 0, the object that is eventually obtained is
      a `FixedCond` instance whose `truthness` is `False` (in fact,
      as a result of the relevant `OrCond`-specific condition logic
      reduction):

      >>> BetweenCond._make('asn')
      <FixedCond: False>
    """

    @classmethod
    def _adapt_op_param(cls, op_param):
        op_param = super()._adapt_op_param(op_param)
        try:
            min_value, max_value = op_param
        except (TypeError, ValueError) as exc:
            raise TypeError(
                'should be a 2-element iterable that '
                'specifies the interval endpoints') from exc
        if min_value is None or max_value is None:
            raise TypeError(
                'interval endpoint value must not be None')
        return min_value, max_value

    #
    # Public interface refinements

    accepting_many_op_params: ClassVar[bool] = True

    op_param: tuple[Hashable, Hashable]


class ContainsSubstringCond(RecItemParamCond):

    r"""
    The "does the specified data item contain the ... substring?"
    condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    See: the relevant parts of the `EqualCond` docs -- with the proviso
    that `op_param` (the *operation parameter*) is a `str` being the
    concerned substring.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The 1st argument must be a `str` (otherwise `TypeError` is raised)
      and it must be ASCII-only (or `ValueError` is raised); the argument
      becomes the value of the `rec_key` attribute.

    * Any other arguments are *operation parameters* (for the multiple
      parameters case -- see the "Condition logic reductions/adjustments"
      subsection below). An *operation parameter* must be a `str`
      (or `TypeError` is raised).

    >>> c = ContainsSubstringCond._make(
    ...     'url', 'w\u0142adca \u017cleb\xf3w')
    >>> c
    <ContainsSubstringCond: 'url', 'w\u0142adca \u017cleb\xf3w'>
    >>> c.rec_key
    'url'
    >>> c.op_param
    'w\u0142adca \u017cleb\xf3w'
    >>> c.init_args
    ('url', 'w\u0142adca \u017cleb\xf3w')

    >>> ContainsSubstringCond._make('url', b'tp://sp')   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be a str)

    >>> ContainsSubstringCond._make('url', 42)           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (should be a str)

    >>> ContainsSubstringCond._make('url', None)         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... illegal ... (parameters being None are not supported)

    >>> ContainsSubstringCond._make((42, 12345), 'url')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: (42, 12345) which is an instance of tuple)

    >>> ContainsSubstringCond._make('żleb', 'x')         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> ContainsSubstringCond._make()                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'


    Condition logic reductions/adjustments
    --------------------------------------

    * If the number of the given *operation parameters* is *not* equal
      to 1, a `ContainsSubstringCond` instance is created for each of
      them; then `OrCond` is used to combine these `ContainsSubstringCond`
      instances. For example:

      >>> c = ContainsSubstringCond._make('url', 'ab', 'cd', 'ef')
      >>> repr(c) == (
      ...     "<OrCond: "
      ...         "<ContainsSubstringCond: 'url', 'ab'>, "
      ...         "<ContainsSubstringCond: 'url', 'cd'>, "
      ...         "<ContainsSubstringCond: 'url', 'ef'>>")
      True

      Note, however, that if the number of the given *operation
      parameters* is 0, the object that is eventually obtained is
      a `FixedCond` instance whose `truthness` is `False` (in fact,
      as a result of the relevant `OrCond`-specific condition logic
      reduction):

      >>> ContainsSubstringCond._make('url')
      <FixedCond: False>
    """

    @classmethod
    def _adapt_op_param(cls, op_param):
        op_param = super()._adapt_op_param(op_param)
        if not isinstance(op_param, str):
            raise TypeError('should be a str')
        return op_param

    #
    # Public interface refinements

    accepting_many_op_params: ClassVar[bool] = True

    op_param: str


class IsTrueCond(RecItemCond):

    """
    The "is the specified data item, being a Boolean flag, set to TRUE?"
    condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `rec_key` (ASCII-only `str`) -- the concerned data *record key*
      (e.g.: `'ignored'`...).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The *only* argument must be a `str` (otherwise `TypeError` is
      raised) and it must be ASCII-only (or `ValueError` is raised);
      the argument becomes the value of the `rec_key` attribute.

    >>> c = IsTrueCond._make('ignored')
    >>> c
    <IsTrueCond: 'ignored'>
    >>> c.rec_key
    'ignored'
    >>> c.init_args
    ('ignored',)

    >>> IsTrueCond._make(42)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: 42 which is an instance of int)

    >>> IsTrueCond._make(bytearray('władca_żlebów'.encode('utf-8')))    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: ... which is an instance of bytearray)

    >>> IsTrueCond._make('władca_żlebów')       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> IsTrueCond._make()                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'

    >>> IsTrueCond._make('ignored', 1)          # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... arguments ...
    """


class IsNullCond(RecItemCond):

    """
    The "is the specified data item missing/NULL?" condition class.


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `rec_key` (ASCII-only `str`) -- the concerned data *record key*
      (e.g.: `'asn'`, or `'fqdn'`, or `'url'`, or `'category'`...).


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The *only* argument must be a `str` (otherwise `TypeError` is
      raised) and it must be ASCII-only (or `ValueError` is raised);
      the argument becomes the value of the `rec_key` attribute.

    >>> c = IsNullCond._make('asn')
    >>> c
    <IsNullCond: 'asn'>
    >>> c.rec_key
    'asn'
    >>> c.init_args
    ('asn',)

    >>> IsNullCond._make(42)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: 42 which is an instance of int)

    >>> IsNullCond._make(bytearray('władca_żlebów'.encode('utf-8')))    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... a str (got: ... which is an instance of bytearray)

    >>> IsNullCond._make('władca_żlebów')       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ... requires `rec_key` being an ASCII-only str ...

    >>> IsNullCond._make()                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'rec_key'

    >>> IsNullCond._make('asn', 1)              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... arguments ...
    """


class FixedCond(Cond):

    """
    The fixed Boolean condition class: either "always TRUE" or "always FALSE".


    Public instance attributes (aside from `init_args`)
    ===================================================

    * `truthness` (bool) -- the logical value of the represented condition.


    Construction
    ============

    Arguments accepted by the `_make()` non-public constructor
    ----------------------------------------------------------

    * The *only* argument must be `True` or `False` (otherwise
      `TypeError` is raised); the argument becomes the value of
      the `truthness` attribute.

    >>> c1 = FixedCond._make(True)
    >>> c1
    <FixedCond: True>
    >>> c1.truthness
    True
    >>> c1.init_args
    (True,)

    >>> c2 = FixedCond._make(False)
    >>> c2
    <FixedCond: False>
    >>> c2.truthness
    False
    >>> c2.init_args
    (False,)

    >>> FixedCond._make(1)                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `truthness` being an instance of bool ...

    >>> FixedCond._make(None)                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `truthness` being an instance of bool ...

    >>> FixedCond._make()                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... missing 1 required positional argument: 'truthness'

    >>> FixedCond._make(True, True)             # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... arguments ...
    """

    @classmethod
    def _adapt_init_args(cls, truthness):
        if not isinstance(truthness, bool):
            raise TypeError(ascii_str(
                f"{cls.__qualname__}'s constructor requires `truthness` "
                f"being an instance of bool (got: {truthness!r} which is "
                f"an instance of {truthness.__class__.__qualname__})"))
        return (truthness,)

    def __init__(self, truthness: bool):
        self.truthness = truthness

    #
    # Public interface extension

    truthness: bool


#
# The base classes for condition visitors
#

_VisitorOutput = TypeVar('_VisitorOutput', covariant=True)

class CondVisitor(Generic[_VisitorOutput], Callable[..., _VisitorOutput]):

    r"""
    The base class for visitors that process given conditions (instances
    of `Cond` subclasses) -- typically, in a recursive manner.

    What we have here is an application of the *Visitor* design pattern
    -- see: https://en.wikipedia.org/wiki/Visitor_pattern (with an
    instance of a concrete subclass of `CondVisitor` as the *visitor*
    object, and condition objects, i.e., instances of concrete
    subclasses of `Cond`, as *element* objects). Note, however, that
    the original pattern has been somewhat modified here; especially,
    the client code *calls the visitor object* directly, passing the
    top-level *element as the argument* (as if the visitor instance
    were a function) -- instead of calling the element's `accept()`
    or the visitor's bare `visit()` (these two methods do not exist).

    Concrete subclasses of this class can provide various kinds of
    processing of instances of `Cond` subclasses (e.g., creation of
    predicate functions or generation of SQL queries...) -- by
    implementing *visiting methods* specific to *concrete* and/or
    *abstract* subclasses of `Cond`. Each such *visiting method*:

    * shall be named according to the pattern: `visit_<name of concrete
      or abstract Cond subclass>` (where *name* is just `__qualname__`
      of that `Cond` subclass) -- for example: `visit_EqualCond`, or
      `visit_NotCond`, or `visit_CompoundCond`, or `visit_RecItemCond`,
      or even (catch-all) `visit_Cond`;

    * shall take at least one positional argument (*not* counting `self`);
      that 1st argument is supposed to be an instance of a matching
      subclass of `Cond`;

    * will be called when the visitor instance is called with an instance
      of a matching `Cond` subclass as the 1st argument -- thanks to the
      `CondVisitor`'s dispatch mechanism, based on name matching (trying
      to match the method name with the names of the superclasses of the
      given condition, including its class itself; note: if multiple
      *visiting methods* match the condition then the *most specific*
      method is chosen; on the other hand, if no method matches the
      condition then `NotImplementedError` is raised);

    * can perform any (visitor-specific) actions (supposedly, making
      use of the given condition's public interface, and possibly --
      if the condition is a *compound* one -- recursively calling the
      visitor, passing to it the condition's subconditions);

    * can return values of any (visitor-specific) types.

    The `CondVisitor` class provides the following interface (typically,
    the methods it consists of should *not* be extended or overridden):

    * direct call interface; note: a visitor instance is intended to be
      called by the client code with a condition object (an instance of
      a `Cond` subclass) as the first argument + any visitor-specific
      positional and/or keyword arguments; all that arguments will be
      passed to the `visit_...()` method appropriate for the class of
      the given condition object (therefore, typically, all visiting
      methods provided by a particular visitor class should take the
      same set of parameters), and the result of the method call will
      become the result of calling the visitor instance;

    * the `make_cond()` helper method -- intended to be used in the code
      of `visit_...()` methods whenever a need to construct an instance
      of a `Cond` subclass arises (for the details, see the docs of the
      `make_cond()` method).

    Note: the aforementioned (visitor-specific) actions that involve the
    given condition object are, typically, some kind of extraction and
    processing (and then, often, returning) of some information from the
    condition object (maybe even creating and returning a new, somewhat
    different, condition object; or maybe, for example, just passing the
    existing condition object intact). Anyway, visitors should *never*
    modify any condition objects in place! (As already emphasized in the
    docs of `Cond`, instances of `Cond` subclasses shall *always* be
    treated as *immutable* objects.)

    Let the examples speak:

    >>> class KeyAdjustingCondTransformer(CondVisitor):
    ...
    ...     '''
    ...     A visitor that produces (recursively) new condition objects
    ...     with a specified prefix added to `rec_key` (if applicable),
    ...     except that any conditions whose `rec_key` is `'count'` are
    ...     omitted (i.e., *not* included at all).
    ...     '''
    ...
    ...     # "catch-all" *visiting method*, i.e., for any subclasses of `Cond`
    ...     # not covered by a more specific `visit_...()`
    ...     def visit_Cond(self, cond, prefix):
    ...         return cond
    ...
    ...     # *visiting method* for subclasses of the abstract class `RecItemCond`
    ...     def visit_RecItemCond(self, cond, prefix):
    ...         if cond.rec_key == 'count':
    ...             return None   # <- omit (do *not* include) this condition
    ...         new_init_args = (prefix + cond.rec_key,) + cond.init_args[1:]
    ...         return self.make_cond(cond.__class__, *new_init_args)
    ...
    ...     # *visiting method* for subclasses of the abstract class `CompoundCond`
    ...     def visit_CompoundCond(self, cond, prefix):
    ...         subresults = (
    ...             self(subcond, prefix)                  # <- note the recursion
    ...             for subcond in cond.subconditions)
    ...         new_subconditions = [                      # <- skipping `None` values (which
    ...             subres                                 #    denote subconditions being omitted)
    ...             for subres in subresults
    ...             if subres is not None]
    ...         if isinstance(cond, NotCond) and not new_subconditions:
    ...             # A `NotCond` cannot have 0 subconditions; therefore,
    ...             # if its subcondition is to be omitted, the `NotCond`
    ...             # must be omitted as well.
    ...             return None                    # <- omit (do *not* include) the whole condition
    ...         return self.make_cond(cond.__class__, *new_subconditions)
    ...
    >>> key_adjusting_transformer = KeyAdjustingCondTransformer()
    >>> cond_builder = CondBuilder()
    >>> c1 = cond_builder['ip'] == '123.124.125.126'
    >>> c1
    <EqualCond: 'ip', '123.124.125.126'>
    >>> c2 = cond_builder['url'].contains_substring('tp://spa')
    >>> c2
    <ContainsSubstringCond: 'url', 'tp://spa'>
    >>> c3 = cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1,                               # <- to be replaced with adjusted version
    ...             cond_builder['asn'] >= 42,        # <- to be replaced with adjusted version
    ...             cond_builder['count'] < 1000,     # <- to be omitted
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['fqdn'].is_null(),   # <- to be replaced with adjusted version
    ...         ),
    ...         cond_builder.not_(                    # <- to be omitted
    ...             cond_builder['count'] <= -3),
    ...         cond_builder['asn'] > 12345,          # <- to be replaced with adjusted version
    ...     ),
    ... )
    >>> c3  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'fqdn'>>, ...'count', -3>>, <GreaterCond: 'asn', 12345>>>

    >>> c1_adjusted = key_adjusting_transformer(c1, 'event.')
    >>> c1_adjusted
    <EqualCond: 'event.ip', '123.124.125.126'>
    >>> c2_adjusted = key_adjusting_transformer(c2, 'event.')
    >>> c2_adjusted
    <ContainsSubstringCond: 'event.url', 'tp://spa'>
    >>> c3_adjusted = key_adjusting_transformer(c3, 'event.')
    >>> c3_adjusted == cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1_adjusted,
    ...             cond_builder['event.asn'] >= 42,
    ...             # *omitted* `cond_builder['event.count'] < 1000`
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['event.fqdn'].is_null(),
    ...         ),
    ...         # *omitted* `cond_builder.not_(cond_builder['count'] <= -3)`
    ...         cond_builder['event.asn'] > 12345,
    ...     ),
    ... )
    True
    >>> c3_adjusted  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'event.fqdn'>>, <GreaterCond: 'event.asn', 12345>>>

    Note: extending *visiting methods* in a subclass (using `super()`)
    is possible and can be quite useful:

    >>> class KeyAdjustingLoggingCondTransformer(KeyAdjustingCondTransformer):
    ...
    ...     '''
    ...     A subclass of `KeyAdjustingCondTransformer` that additionally
    ...     provides logging (using `print()`) of all condition replacements
    ...     and omissions.
    ...     '''
    ...
    ...     def visit_RecItemCond(self, cond, prefix):
    ...         visit_result = super().visit_RecItemCond(cond, prefix)
    ...         if visit_result is None:
    ...             print(f'* omitting: {cond!r}')
    ...         else:
    ...             print(f'* replacing: {cond!r} -> {visit_result}')
    ...         return visit_result
    ...
    ...     def visit_NotCond(self, cond, prefix):
    ...         # Note: here we call `super().visit_CompoundCond(...)`,
    ...         # *not* `super().visit_NotCond(...)` (a bit weird but
    ...         # necessary -- because `KeyAdjustingCondTransformer`
    ...         # does not provide `visit_NotCond()` but only, more
    ...         # generic, `visit_CompoundCond()`).
    ...         visit_result = super().visit_CompoundCond(cond, prefix)
    ...         if visit_result is None:
    ...             print('  * so omitting also a NotCond which wraps it')
    ...         return visit_result
    ...
    >>> key_adjusting_logging_transformer = KeyAdjustingLoggingCondTransformer()
    >>> c3_adjusted_again = key_adjusting_logging_transformer(c3, 'event.')
    * replacing: <EqualCond: 'ip', '123.124.125.126'> -> <EqualCond: 'event.ip', '123.124.125.126'>
    * replacing: <GreaterOrEqualCond: 'asn', 42> -> <GreaterOrEqualCond: 'event.asn', 42>
    * omitting: <LessCond: 'count', 1000>
    * replacing: <IsNullCond: 'fqdn'> -> <IsNullCond: 'event.fqdn'>
    * omitting: <LessOrEqualCond: 'count', -3>
      * so omitting also a NotCond which wraps it
    * replacing: <GreaterCond: 'asn', 12345> -> <GreaterCond: 'event.asn', 12345>
    >>> c3_adjusted_again == c3_adjusted
    True

    ***

    Note: if you need to implement a *transformer* (i.e., a visitor that
    produces condition objects, such as `KeyAdjustingCondTransformer`
    or `KeyAdjustingLoggingCondTransformer` presented above), it is
    recommended to inherit from `CondTransformer` rather than directly
    from `CondVisitor` as above...

    (See the docs of the `CondTransformer` class...)

    ***

    Another example:

    >>> class CondFormatter(CondVisitor):
    ...
    ...     '''
    ...     A visitor that generates (recursively) pretty-formatted string
    ...     representations of condition objects.
    ...     '''
    ...
    ...     INDENT_CHARS = '  '
    ...
    ...     # *visiting method* for subclasses of the abstract class `CompoundCond`
    ...     def visit_CompoundCond(self, cond, indent=''):
    ...         op_symbol = cond.__class__.__name__.removesuffix('Cond').upper()
    ...         subconditions = ',\n'.join(
    ...             self(subcond, indent + self.INDENT_CHARS)    # <- note the recursion
    ...             for subcond in cond.subconditions)
    ...         return f'{indent}{op_symbol} (\n{subconditions})'
    ...
    ...     # *visiting methods* for specific concrete subclasses of `Cond`:
    ...
    ...     def visit_EqualCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} = {cond.op_param!r}'
    ...
    ...     def visit_GreaterCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} > {cond.op_param!r}'
    ...
    ...     def visit_GreaterOrEqualCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} >= {cond.op_param!r}'
    ...
    ...     def visit_LessCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} < {cond.op_param!r}'
    ...
    ...     def visit_LessOrEqualCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} <= {cond.op_param!r}'
    ...
    ...     def visit_IsNullCond(self, cond, indent=''):
    ...         return f'{indent}{cond.rec_key} IS NULL'
    ...
    >>> cond_formatter = CondFormatter()

    >>> print(cond_formatter(c1))
    ip = '123.124.125.126'

    >>> print(cond_formatter(c2))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    NotImplementedError: ...no visit_...() method to handle ... ContainsSubstringCond

    >>> print(cond_formatter(c3))
    NOT (
      OR (
        AND (
          ip = '123.124.125.126',
          asn >= 42,
          count < 1000),
        NOT (
          fqdn IS NULL),
        NOT (
          count <= -3),
        asn > 12345))

    >>> print(cond_formatter(c1_adjusted))
    event.ip = '123.124.125.126'

    >>> print(cond_formatter(c2_adjusted))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    NotImplementedError: ...no visit_...() method to handle ... ContainsSubstringCond

    >>> print(cond_formatter(c3_adjusted))
    NOT (
      OR (
        AND (
          event.ip = '123.124.125.126',
          event.asn >= 42),
        NOT (
          event.fqdn IS NULL),
        event.asn > 12345))

    As emphasized earlier, visitors shall *never* modify the original
    condition objects:

    >>> c1
    <EqualCond: 'ip', '123.124.125.126'>
    >>> c2
    <ContainsSubstringCond: 'url', 'tp://spa'>
    >>> c3 == cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1,
    ...             cond_builder['asn'] >= 42,
    ...             cond_builder['count'] < 1000,
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['fqdn'].is_null(),
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['count'] <= -3),
    ...         cond_builder['asn'] > 12345,
    ...     ),
    ... ) != c3_adjusted
    True
    >>> c3  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'fqdn'>>, ...'count', -3>>, <GreaterCond: 'asn', 12345>>>
    """

    def __call__(self, cond: Cond, *args, **kwargs) -> _VisitorOutput:
        for cond_superclass in cond.__class__.__mro__:
            visit_method_name = 'visit_' + cond_superclass.__qualname__
            visit_method = getattr(self, visit_method_name, None)
            visit_method: Optional[Callable[..., _VisitorOutput]]
            if visit_method is not None:
                return visit_method(cond, *args, **kwargs)
        raise NotImplementedError(ascii_str(
            f'{self.__class__.__qualname__} has no visit_...() method '
            f'to handle an instance of {cond.__class__.__qualname__}'))

    def make_cond(self, cond_cls: type[Cond], *args) -> Cond:
        """
        Construct an instance of a concrete subclass of `Cond`.

        Args (positional-only):
            `cond_cls`:
                The class (a concrete subclass of `Cond`) whose
                non-public constructor `_make()` shall be called
                to construct the desired instance.
            *any other positional arguments*:
                To be passed directly to `cond_cls._make()`.

        Returns:
            An instance of a concrete subclass of `Cond`. Note that --
            due to `Cond`-subclass-specific condition logic reductions/
            /adjustments -- it may be an instance of another concrete
            subclass of `Cond` (i.e., not necessarily an instance of
            `cond_cls`).

        Raises:
            * `TypeError` -- if the `cond_cls` argument is not
              a subclass of `Cond`.
            * Any exception* that can be raised by `cond_cls._make()`.

        *See also:* the "Construction" sections of the docs of the
        concrete subclasses of `Cond`; each of those classes can be
        passed in as the `cond_cls` argument.

        This method is intended to be used in the code of `visit_...()`
        methods whenever there is a need to construct a condition
        object. For example:

        >>> class SillyCondTransformer(CondVisitor):
        ...
        ...     def visit_Cond(self, cond):
        ...         # negate `cond` by wrapping it with a `NotCond`
        ...         return self.make_cond(NotCond, cond)
        ...
        ...     def visit_RecItemParamCond(self, cond):
        ...         # get similar condition with `rec_key` upper-cased
        ...         return self.make_cond(
        ...             cond.__class__,
        ...             cond.rec_key.upper(),
        ...             cond.op_param)
        ...
        ...     def visit_CompoundCond(self, cond):
        ...         # ensure that the transformations defined above are applied
        ...         # to subconditions of compound conditions (recursively)
        ...         return self.make_cond(cond.__class__, map(self, cond.subconditions))
        ...
        >>> silly_cond_transformer = SillyCondTransformer()
        >>> cond_builder = CondBuilder()
        >>> c1 = cond_builder.or_(
        ...     cond_builder['ip'].is_null(),
        ...     cond_builder['asn'] == 1,
        ...     cond_builder['fqdn'].contains_substring('x'))
        >>> c2 = silly_cond_transformer(c1)
        >>> c2 == cond_builder.or_(
        ...     cond_builder.not_(
        ...         cond_builder['ip'].is_null()),
        ...     cond_builder['ASN'] == 1,
        ...     cond_builder['FQDN'].contains_substring('x'))
        True

        >>> silly_cond_transformer.make_cond(str, 'count', [2, 3, 5, 7, 11])
        Traceback (most recent call last):
          ...
        TypeError: a subclass of Cond expected (got: <class 'str'>)

        >>> silly_cond_transformer.make_cond('still not a subclass of Cond')
        Traceback (most recent call last):
          ...
        TypeError: a subclass of Cond expected (got: 'still not a subclass of Cond')

        >>> silly_cond_transformer.make_cond(InCond, 'count', 2, 3, 5, 7, 11)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: InCond's constructor does not accept multiple operation parameters...

        >>> silly_cond_transformer.make_cond(InCond, 'count', [2, 3, 5, 7, 11])
        <InCond: 'count', {2, 3, 5, 7, 11}>

        ***

        Note: if you need to implement a *transformer* (i.e., a visitor
        that produces condition objects, such as `SillyCondTransformer`
        above), it is recommended to inherit from `CondTransformer`
        rather than directly from `CondVisitor` as above...

        (See the docs of the `CondTransformer` class...)
        """
        if not (isinstance(cond_cls, type)
                and issubclass(cond_cls, Cond)):
            raise TypeError(ascii_str(
                f'a subclass of {Cond.__qualname__} '
                f'expected (got: {cond_cls!r})'))
        return cond_cls._make(*args)                                     # noqa


_TransformerOutput = TypeVar('_TransformerOutput', covariant=True, bound=Optional[Cond])

class CondTransformer(CondVisitor[_TransformerOutput]):

    """
    The base class for *transformers*, i.e., visitors that *produce
    conditions* (possibly different than given input conditions).

    For each input condition, the condition returned by the respective
    *visiting method* becomes the corresponding condition in the output.
    However, the condition is omitted from the output if the respective
    *visiting method* returns `None`; moreover, if the parent of any
    omitted condition is a `NotCond`, it is also omitted (since there
    cannot exist a `NotCond` without a subcondition). If the top-level
    condition -- i.e., the one passed in directly to the transformer --
    is omitted, the transformer just returns `None`.

    This class provides one *visiting method* -- `visit_Cond()` --
    and one utility method -- `subvisit()`. The latter applies the
    visitor to all subconditions of the given compound condition;
    if given a leaf (non-compound) condition, it returns it intact.
    The former (`visit_Cond()`) is a "catch-all" visiting method; it
    just applies `subvisit()` to the given condition object (together
    with any other positional and keyword arguments that were given,
    if any) and returns the result.

    **Important:** whenever a visiting method provided by your subclass
    deals with a compound condition (i.e., an instance of any concrete
    subclass of `CompoundCond`), the `subvisit()` method needs to be
    applied to that condition, together with any other positional and
    keyword arguments passed in to the visiting method (alternatively,
    the condition's subconditions can be visited manually, by applying
    the transformer to each of them...) -- to ensure that all conditions
    which appear in your transformer's output have always been visited
    appropriately. Note that if `subvisit()` happens to be applied to
    a non-compound condition, it is harmless (as said above, it returns
    such a condition intact).

    ***

    Making use of `CondTransformer` as the base class can save you some
    work.

    E.g., a functionally equivalent (but more inheritance-friendly, see
    below...) version of the `KeyAdjustingCondTransformer` example class
    from the `CondVisitor`'s docs could be implemented as a subclass of
    `CondTransformer` in the following way:

    >>> class KeyAdjustingCondTransformer(CondTransformer):
    ...
    ...     '''
    ...     A visitor that produces (recursively) new condition objects
    ...     with a specified prefix added to `rec_key` (if applicable),
    ...     except that any conditions whose `rec_key` is `'count'` are
    ...     omitted (i.e., *not* included at all).
    ...     '''
    ...
    ...     # *visiting method* for subclasses of the abstract class `RecItemCond`
    ...     def visit_RecItemCond(self, cond, prefix):
    ...         if cond.rec_key == 'count':
    ...             return None   # <- omit (do *not* include) this condition
    ...         new_init_args = (prefix + cond.rec_key,) + cond.init_args[1:]
    ...         return self.make_cond(cond.__class__, *new_init_args)

    As you see, this version is much shorter -- though, when instantiated,
    it behaves the same as the version from the `CondVisitor`'s docs:

    >>> key_adjusting_transformer = KeyAdjustingCondTransformer()
    >>> cond_builder = CondBuilder()
    >>> c1 = cond_builder['ip'] == '123.124.125.126'
    >>> c1
    <EqualCond: 'ip', '123.124.125.126'>
    >>> c2 = cond_builder['url'].contains_substring('tp://spa')
    >>> c2
    <ContainsSubstringCond: 'url', 'tp://spa'>
    >>> c3 = cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1,                               # <- to be replaced with adjusted version
    ...             cond_builder['asn'] >= 42,        # <- to be replaced with adjusted version
    ...             cond_builder['count'] < 1000,     # <- to be omitted
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['fqdn'].is_null(),   # <- to be replaced with adjusted version
    ...         ),
    ...         cond_builder.not_(                    # <- to be omitted
    ...             cond_builder['count'] <= -3),
    ...         cond_builder['asn'] > 12345,          # <- to be replaced with adjusted version
    ...     ),
    ... )
    >>> c3  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'fqdn'>>, ...'count', -3>>, <GreaterCond: 'asn', 12345>>>

    >>> c1_adjusted = key_adjusting_transformer(c1, 'event.')
    >>> c1_adjusted
    <EqualCond: 'event.ip', '123.124.125.126'>
    >>> c2_adjusted = key_adjusting_transformer(c2, 'event.')
    >>> c2_adjusted
    <ContainsSubstringCond: 'event.url', 'tp://spa'>
    >>> c3_adjusted = key_adjusting_transformer(c3, 'event.')
    >>> c3_adjusted == cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1_adjusted,
    ...             cond_builder['event.asn'] >= 42,
    ...             # *omitted* `cond_builder['event.count'] < 1000`
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['event.fqdn'].is_null(),
    ...         ),
    ...         # *omitted* `cond_builder.not_(cond_builder['count'] <= -3)`
    ...         cond_builder['event.asn'] > 12345,
    ...     ),
    ... )
    True
    >>> c3_adjusted  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'event.fqdn'>>, <GreaterCond: 'event.asn', 12345>>>

    Obviously, further inheritance is also possible, and is even more
    straightforward than from `KeyAdjustingCondTransformer` in the
    version from the `CondVisitor`'s docs (compare the implementations
    of the `visit_NotCond()` method...):

    >>> class KeyAdjustingLoggingCondTransformer(KeyAdjustingCondTransformer):
    ...
    ...     '''
    ...     A subclass of `KeyAdjustingCondTransformer` that additionally
    ...     provides logging (using `print()`) of all condition replacements
    ...     and omissions.
    ...     '''
    ...
    ...     def visit_RecItemCond(self, cond, prefix):
    ...         visit_result = super().visit_RecItemCond(cond, prefix)
    ...         if visit_result is None:
    ...             print(f'* omitting: {cond!r}')
    ...         else:
    ...             print(f'* replacing: {cond!r} -> {visit_result}')
    ...         return visit_result
    ...
    ...     def visit_NotCond(self, cond, prefix):
    ...         # Note: the given condition is a `NotCond` -- a *compound*
    ...         # condition -- so, as said earlier, we need to process
    ...         # it with the `subvisit()` method. Note that *no* use of
    ...         # `super()` is needed here (`CondTransformer` does *not*
    ...         # provide any visiting methods except the `visit_Cond()`
    ...         # catch-all one).
    ...         visit_result = self.subvisit(cond, prefix)
    ...         if visit_result is None:
    ...             print('  * so omitting also a NotCond which wraps it')
    ...         return visit_result
    ...
    >>> key_adjusting_logging_transformer = KeyAdjustingLoggingCondTransformer()
    >>> c3_adjusted_again = key_adjusting_logging_transformer(c3, 'event.')
    * replacing: <EqualCond: 'ip', '123.124.125.126'> -> <EqualCond: 'event.ip', '123.124.125.126'>
    * replacing: <GreaterOrEqualCond: 'asn', 42> -> <GreaterOrEqualCond: 'event.asn', 42>
    * omitting: <LessCond: 'count', 1000>
    * replacing: <IsNullCond: 'fqdn'> -> <IsNullCond: 'event.fqdn'>
    * omitting: <LessOrEqualCond: 'count', -3>
      * so omitting also a NotCond which wraps it
    * replacing: <GreaterCond: 'asn', 12345> -> <GreaterCond: 'event.asn', 12345>
    >>> c3_adjusted_again == c3_adjusted
    True

    Again, the original condition objects -- obviously -- have *not*
    been modified:

    >>> c1
    <EqualCond: 'ip', '123.124.125.126'>
    >>> c2
    <ContainsSubstringCond: 'url', 'tp://spa'>
    >>> c3 == cond_builder.not_(
    ...     cond_builder.or_(
    ...         cond_builder.and_(
    ...             c1,
    ...             cond_builder['asn'] >= 42,
    ...             cond_builder['count'] < 1000,
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['fqdn'].is_null(),
    ...         ),
    ...         cond_builder.not_(
    ...             cond_builder['count'] <= -3),
    ...         cond_builder['asn'] > 12345,
    ...     ),
    ... ) != c3_adjusted
    True
    >>> c3  # doctest: +ELLIPSIS
    <NotCond: <OrCond: <AndCond: ...'fqdn'>>, ...'count', -3>>, <GreaterCond: 'asn', 12345>>>

    As said earlier, if the top-level condition is to be *omitted* then
    just `None` is returned by the called transformer:

    >>> c4 = cond_builder['count'].between(-1000, 1000)
    >>> c4
    <BetweenCond: 'count', (-1000, 1000)>
    >>> c4_adjusted = key_adjusting_transformer(c4, 'event.')
    >>> c4_adjusted is None
    True

    Note that an instance of the `CondTransformer` class itself (thanks
    to the provided implementation of `visit_Cond()`) behaves like a
    *no-op transformer* (i.e., a transformer whose output is equal to
    its input):

    >>> no_op_transformer = CondTransformer()
    >>> c1 == no_op_transformer(c1)
    True
    >>> c2 == no_op_transformer(c2)
    True
    >>> c3 == no_op_transformer(c3)
    True
    >>> c4 == no_op_transformer(c4)
    True
    """

    def visit_Cond(self, cond: Cond, /, *args, **kwargs) -> _TransformerOutput:
        """
        This is the "catch-all" visiting method -- i.e., it handles
        instances of any `Cond` subclasses not covered by more specific
        visiting methods.

        This `CondTransformer`-specific implementation of it applies
        the `subvisit()` method to the given condition object (with
        all additional positional and keyword arguments, if any).

        If, in your subclass, you need to provide your own version of
        this method, you should *extend* it (using `super()`), *not*
        override it completely.
        """
        return self.subvisit(cond, *args, **kwargs)

    def subvisit(self, cond: Cond, /, *args, **kwargs) -> _TransformerOutput:
        """
        If the given condition is a compound one (i.e., is an instance
        of a concrete subclass of `CompoundCond`), make a new compound
        condition (of the same type) -- whose subconditions are the
        results of visiting each of the subconditions of the given
        condition, except that results being `None` are omitted. If the
        given compound condition is a `NotCond` instance and the result
        of visiting its subcondition is `None`, then return `None` (to
        cause the whole `NotCond` condition to be *omitted*).

        If the given condition is *not* a compound one, return it intact.

        This is a utility method, *not* intended to be overridden in
        subclasses.
        """
        if isinstance(cond, CompoundCond):
            assert (len(cond.subconditions) == 1 if isinstance(cond, NotCond)
                    else cond.subconditions)
            new_subconditions = self.__get_new_subconditions(cond, args, kwargs)
            if isinstance(cond, NotCond) and not new_subconditions:
                return None
            return self.make_cond(cond.__class__, new_subconditions)
        return cond

    def __get_new_subconditions(self,
                                cond: CompoundCond,
                                args: tuple,
                                kwargs: dict[str, Any]) -> list[Cond]:
        subresults = (
            self(subcond, *args, **kwargs)
            for subcond in cond.subconditions)
        new_subconditions = [
            subres
            for subres in subresults
            if subres is not None]
        assert len(new_subconditions) <= len(cond.subconditions)
        return new_subconditions


#
# Tools related to predicate-based data selection
#

_Predicate = Callable[['RecordWrapperForPredicates'], bool]

class CondPredicateMaker(CondVisitor[_Predicate]):

    """
    A visitor class to produce data selection predicates from given
    conditions.

    One way to make use of a condition object is to generate a
    *predicate*, that is, a function that takes a data record and
    returns `True` or `False` -- answering the question: "Does the given
    data record satisfies the defined condition?". The purpose of
    `CondPredicateMaker` is to generate such *predicates* from condition
    objects (where a *condition object* is an instance of any concrete
    subclass of `Cond` -- including compound ones, i.e., `NotCond`,
    `AndCond` and `OrCond`).

    An instance of this class shall be called with exactly one argument:
    the *condition object* to be processed.

    The returned object is the desired *predicate*, that is, a 1-argument
    function which:

    * takes an instance of `RecordWrapperForPredicates` (instantiated
      with a dict or a `RecordDict` as the sole construction argument
      -- see the `RecordWrapperForPredicates` docs);

    * returns `True` or `False` (answering the aforementioned question).

    Let the following examples speak.


    >>> make_predicate = CondPredicateMaker()
    >>> cond_builder = CondBuilder()
    >>> rec = {
    ...     'source': 'foo.bar',
    ...     'category': 'bots',
    ...     'ignored': True,
    ...     'name': 'Foo Bąr',
    ...     'address': [
    ...         {
    ...             'ip': '10.20.30.41',
    ...             'asn': 12345,
    ...             'cc': 'PL',
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...             'asn': 65538,
    ...         },
    ...         {
    ...             'ip': '10.20.30.43',
    ...             'cc': 'JP',
    ...         },
    ...         {
    ...             'ip': '10.20.30.44',
    ...         },
    ...     ],
    ...     'not_used': None,
    ... }
    >>> r = RecordWrapperForPredicates(rec)
    >>> def check(cond, r=r):
    ...     predicate = make_predicate(cond)
    ...     return predicate(r)


    First, let's check some simple conditions:

    >>> check(cond_builder['source'] == 'foo.bar')
    True
    >>> check(cond_builder['asn'] == 12345)
    True
    >>> check(cond_builder['asn'] == 65538)
    True
    >>> check(cond_builder['ip'] == 169090601)  # note: IP addresses as integer numbers
    True
    >>> check(cond_builder['ip'] == 169090604)
    True
    >>> check(cond_builder['source'] == 'Foo.Bar')
    False
    >>> check(cond_builder['asn'] == 12344)
    False
    >>> check(cond_builder['asn'] == 65537)
    False
    >>> check(cond_builder['asn'] == 65539)
    False
    >>> check(cond_builder['ip'] == 169090605)
    False
    >>> check(cond_builder['ip'] == '10.20.30.44')
    False
    >>> check(cond_builder['restriction'] == 'foo')
    False

    >>> check(cond_builder['source'] > 'foo.ba')
    True
    >>> check(cond_builder['asn'] > 12344)
    True
    >>> check(cond_builder['asn'] > 12345)
    True
    >>> check(cond_builder['asn'] > 12346)
    True
    >>> check(cond_builder['asn'] > 65537)
    True
    >>> check(cond_builder['asn'] > 65538)
    False
    >>> check(cond_builder['source'] > 'foo.bar')
    False
    >>> check(cond_builder['restriction'] > 'foo')
    False

    >>> check(cond_builder['source'] >= 'foo.bar')
    True
    >>> check(cond_builder['asn'] >= 0)
    True
    >>> check(cond_builder['asn'] >= 12344)
    True
    >>> check(cond_builder['asn'] >= 65538)
    True
    >>> check(cond_builder['source'] >= 'foo.bara')
    False
    >>> check(cond_builder['asn'] >= 65539)
    False
    >>> check(cond_builder['restriction'] >= 'foo')
    False

    >>> check(cond_builder['source'] < 'foo.bara')
    True
    >>> check(cond_builder['asn'] < 12346)
    True
    >>> check(cond_builder['source'] < 'foo.bar')
    False
    >>> check(cond_builder['asn'] < 12345)
    False
    >>> check(cond_builder['asn'] < 12344)
    False
    >>> check(cond_builder['asn'] < 0)
    False
    >>> check(cond_builder['restriction'] < 'foo')
    False

    >>> check(cond_builder['source'] <= 'foo.bar')
    True
    >>> check(cond_builder['asn'] <= 12346)
    True
    >>> check(cond_builder['asn'] <= 12345)
    True
    >>> check(cond_builder['source'] <= 'foo.ba')
    False
    >>> check(cond_builder['asn'] <= 12344)
    False
    >>> check(cond_builder['restriction'] <= 'foo')
    False

    >>> check(cond_builder['source'].in_(['foo.bar']))
    True
    >>> check(cond_builder['name'].in_(['Foo Bąr']))
    True
    >>> check(cond_builder['asn'].in_([12344, 12345, 12346]))
    True
    >>> check(cond_builder['asn'].in_([65538, 0]))
    True
    >>> check(cond_builder['source'].in_(['oo.ba']))
    False
    >>> check(cond_builder['name'].in_([' Foo Bąr ']))
    False
    >>> check(cond_builder['asn'].in_([12344, 12346]))
    False
    >>> check(cond_builder['asn'].in_([65539, 0]))
    False
    >>> check(cond_builder['restriction'].in_(['foo.bar', 'Foo.Bąr']))
    False

    >>> check(cond_builder['source'].between('foo.ba', 'foo.bara'))
    True
    >>> check(cond_builder['asn'].between([12344, 12346]))
    True
    >>> check(cond_builder['asn'].between(12345, 12346))
    True
    >>> check(cond_builder['asn'].between([65537, 65538]))
    True
    >>> check(cond_builder['asn'].between(65538, 65538))
    True
    >>> check(cond_builder['source'].between('foo.ba', 'foo.baq'))
    False
    >>> check(cond_builder['source'].between(['foo.bara', 'foo.barz']))
    False
    >>> check(cond_builder['source'].between('foo.bara', 'foo.ba'))
    False
    >>> check(cond_builder['asn'].between([12346, 12344]))
    False
    >>> check(cond_builder['asn'].between(12342, 12344))
    False
    >>> check(cond_builder['asn'].between([12346, 50000]))
    False
    >>> check(cond_builder['asn'].between(65539, 10000000))
    False
    >>> check(cond_builder['restriction'].between(['bar', 'foo']))
    False

    >>> check(cond_builder['category'].contains_substring('bot'))
    True
    >>> check(cond_builder['category'].contains_substring('ots'))
    True
    >>> check(cond_builder['category'].contains_substring('ot'))
    True
    >>> check(cond_builder['name'].contains_substring('Bą'))
    True
    >>> check(cond_builder['name'].contains_substring(''))
    True
    >>> check(cond_builder['cc'].contains_substring('J'))
    True
    >>> check(cond_builder['cc'].contains_substring('PL'))
    True
    >>> check(cond_builder['cc'].contains_substring(''))
    True
    >>> check(cond_builder['category'].contains_substring(' bots'))
    False
    >>> check(cond_builder['category'].contains_substring('OT'))
    False
    >>> check(cond_builder['name'].contains_substring('bą'))
    False
    >>> check(cond_builder['cc'].contains_substring('j'))
    False
    >>> check(cond_builder['restriction'].contains_substring('foo'))
    False
    >>> check(cond_builder['restriction'].contains_substring(''))
    False

    >>> check(cond_builder['ignored'].is_true())
    True
    >>> check(cond_builder['ignored'].is_true(), r=RecordWrapperForPredicates({'ignored': False}))
    False
    >>> check(cond_builder['ignored'].is_true(), r=RecordWrapperForPredicates({}))
    False

    >>> check(cond_builder['restriction'].is_null())
    True
    >>> check(cond_builder['name'].is_null(), r=RecordWrapperForPredicates({}))
    True
    >>> check(cond_builder['ip'].is_null(), r=RecordWrapperForPredicates({}))
    True
    >>> check(cond_builder['asn'].is_null(), r=RecordWrapperForPredicates({
    ...     'address': [
    ...         {
    ...             'ip': '10.20.30.41',
    ...             'cc': 'PL',
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...         },
    ...     ],
    ... }))
    True
    >>> check(cond_builder['source'].is_null())
    False
    >>> check(cond_builder['category'].is_null())
    False
    >>> check(cond_builder['name'].is_null())
    False
    >>> check(cond_builder['ip'].is_null())
    False
    >>> check(cond_builder['asn'].is_null())
    False
    >>> check(cond_builder['cc'].is_null())
    False

    >>> check(cond_builder.true())
    True

    >>> check(cond_builder.false())
    False

    Note: the type of a value in a data record may be incompatible with
    certain record-item-concerned conditions. In such cases, expect an
    error, e.g.:

    >>> check(cond_builder['asn'].contains_substring(''))
    Traceback (most recent call last):
      ...
    TypeError: only a str can contain a substring (got: 12345 which is an instance of int)

    >>> check(cond_builder['category'].is_true())  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: only a bool can be used as a TRUE/FALSE flag (got: 'bots' ... an instance of str)


    Now, let's check various compound conditions...

    First, negations of some of the simple conditions checked above:

    >>> check(cond_builder.not_(cond_builder['ip'] == 169090604))
    False
    >>> check(cond_builder.not_(cond_builder['ip'] == 169090605))
    True
    >>> check(cond_builder.not_(cond_builder['asn'] > 65537))
    False
    >>> check(cond_builder.not_(cond_builder['asn'] > 65538))
    True
    >>> check(cond_builder.not_(cond_builder['asn'] >= 0))
    False
    >>> check(cond_builder.not_(cond_builder['asn'] >= 65539))
    True
    >>> check(cond_builder.not_(cond_builder['asn'] < 12346))
    False
    >>> check(cond_builder.not_(cond_builder['asn'] < 12345))
    True
    >>> check(cond_builder.not_(cond_builder['asn'] <= 12345))
    False
    >>> check(cond_builder.not_(cond_builder['asn'] <= 12344))
    True
    >>> check(cond_builder.not_(cond_builder['source'].in_(['foo.bar'])))
    False
    >>> check(cond_builder.not_(cond_builder['source'].in_(['oo.ba'])))
    True
    >>> check(cond_builder.not_(cond_builder['asn'].between([12344, 12346])))
    False
    >>> check(cond_builder.not_(cond_builder['asn'].between(12342, 12344)))
    True
    >>> check(cond_builder.not_(cond_builder['category'].contains_substring('bot')))
    False
    >>> check(cond_builder.not_(cond_builder['name'].contains_substring('bą')))
    True
    >>> check(cond_builder.not_(cond_builder['ignored'].is_true()))
    False
    >>> check(cond_builder.not_(cond_builder['ignored'].is_true()),
    ...                         r=RecordWrapperForPredicates({}))
    True
    >>> check(cond_builder.not_(cond_builder['restriction'].is_null()))
    False
    >>> check(cond_builder.not_(cond_builder['name'].is_null()), r=RecordWrapperForPredicates({}))
    False
    >>> check(cond_builder.not_(cond_builder['ip'].is_null()), r=RecordWrapperForPredicates({}))
    False
    >>> check(cond_builder.not_(cond_builder['asn'].is_null()), r=RecordWrapperForPredicates({
    ...     'address': [
    ...         {
    ...             'ip': '10.20.30.41',
    ...             'cc': 'PL',
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...         },
    ...     ],
    ... }))
    False
    >>> check(cond_builder.not_(cond_builder['source'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder['category'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder['name'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder['ip'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder['asn'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder['cc'].is_null()))
    True
    >>> check(cond_builder.not_(cond_builder.true()))
    False
    >>> check(cond_builder.not_(cond_builder.false()))
    True

    Then, a bunch of checks focused on more complex conditions:

    >>> b = cond_builder

    >>> t1 = b.and_(b['ip'] <= 169090601, b['ip'] > 169090601, b.not_(b['ip'].in_([1, 2, 3])))
    >>> t2 = b.or_(b['ip'] == 65538, b['asn'] == 169090604, b['ip'].in_([169090601, 12345]))
    >>> t3 = b['ip'].between(169090604, 169090607)
    >>> t4 = b['name'].in_(['Foo Bąr', 'foo-bar'])
    >>> t5 = b.and_(t1, t2, t3, t4, b.not_(b['ip'] == 4))
    >>> t6 = b.and_(t1, t2, t3, b.not_(b.and_(t4, b.not_(b.and_(t1, t2, t3)))), t5)

    >>> F1 = b.and_(b['ip'] == 169090601, b['ip'] > 169090604)
    >>> F2 = b.or_(b['ip'] < 169090601, b['ip'] >= 169090605)
    >>> F3 = b['ip'].between(169090605, 169090607)
    >>> F4 = b.not_(b['asn'].in_([65538, 1, 2, 3]))
    >>> F5 = b.and_(F1, t6)
    >>> F6 = b.or_(b.not_(b['category'] == 'bots'),
    ...            b.not_(b.and_(b['category'].contains_substring('bot'), b['ip'] == 169090603)),
    ...            b.not_(b['restriction'].is_null()),
    ...            b.not_(b['ignored'].is_true()))

    >>> t7 = b.and_(t1, t2, t3, b.or_(t3, b.and_(F3, t1), b.and_(F3, t2), b.and_(F3, t5)),
    ...             t3, t4, t4, b.or_(t5, F5, F5),
    ...             b.or_(t3, F4),
    ...             t6,
    ...             b.or_(F5, t3, F6),
    ...             b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...             b.or_(b.and_(F4, t5), t1))
    >>> F7 = b.or_(b.not_(t7), F2, F1, b.not_(t1), b.and_(F5, t4, t5, t6), F3)

    >>> F8 = b.and_(t1, t2, t3, b.or_(t3, F3),
    ...             t3, t4, t4, b.or_(t5, F5, F5),
    ...             t6,
    ...             b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...             b.or_(b.and_(F4, t5), F1))
    >>> F9 = b.and_(t1, t2, t3, b.or_(t3, F3),
    ...             t3, t4, t4, b.or_(t5, F5, F5),
    ...             t6,
    ...             b.or_(F1, F2, b.and_(t1, b.or_(F6, t6))),
    ...             b.not_(b.or_(b.and_(F4, t5), t1)))
    >>> F10 = b.and_(t1, t2, t3, b.or_(t3, F3),
    ...              t3, t4, t4, b.or_(t5, F5, F5),
    ...              t6,
    ...              b.or_(F1, F2, b.not_(b.and_(t1, b.or_(F6, t6)))),
    ...              b.or_(b.and_(F4, t5), t1))
    >>> F11 = b.and_(t1, t2, t3, b.or_(t3, F3),
    ...              t3, t4, t4, b.or_(t5, F5, F5),
    ...              t6,
    ...              b.or_(F1, F2, b.and_(F7, b.or_(F6, t6))),
    ...              b.or_(b.and_(F4, t5), t1))

    >>> check(t1)
    True
    >>> check(t2)
    True
    >>> check(t3)
    True
    >>> check(t4)
    True
    >>> check(t5)
    True
    >>> check(t6)
    True
    >>> check(t7)
    True

    >>> check(b.not_(t1))
    False
    >>> check(b.not_(t2))
    False
    >>> check(b.not_(t3))
    False
    >>> check(b.not_(t4))
    False
    >>> check(b.not_(t5))
    False
    >>> check(b.not_(t6))
    False
    >>> check(b.not_(t7))
    False

    >>> check(F1)
    False
    >>> check(F2)
    False
    >>> check(F3)
    False
    >>> check(F4)
    False
    >>> check(F5)
    False
    >>> check(F6)
    False
    >>> check(F7)
    False
    >>> check(F8)
    False
    >>> check(F9)
    False
    >>> check(F10)
    False
    >>> check(F11)
    False

    >>> check(b.not_(F1))
    True
    >>> check(b.not_(F2))
    True
    >>> check(b.not_(F3))
    True
    >>> check(b.not_(F4))
    True
    >>> check(b.not_(F5))
    True
    >>> check(b.not_(F6))
    True
    >>> check(b.not_(F7))
    True
    >>> check(b.not_(F8))
    True
    >>> check(b.not_(F9))
    True
    >>> check(b.not_(F10))
    True
    >>> check(b.not_(F11))
    True

    >>> check(b.and_(t1, t2))
    True
    >>> check(b.and_(t3, t4, t5, t6, t7))
    True
    >>> check(b.and_(t1, t2, t3, t4, t5, t6, t7))
    True
    >>> check(b.and_(t3, t4, t5, t6, F7))
    False
    >>> check(b.and_(t1, t2, t3, F11, t4, t5, t6))
    False
    >>> check(b.and_(t2, F3))
    False
    >>> check(b.and_(F2, t3))
    False
    >>> check(b.and_(F2, F3))
    False
    >>> check(b.and_(t3, F4, t5, t6))
    False
    >>> check(b.and_(F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11))
    False
    >>> check(b.and_(F1, F2, F3, F4, F5, F6, t7, F7, F8, F9, F10, F11))
    False

    >>> check(b.or_(t1, t2))
    True
    >>> check(b.or_(t3, t4, t5, t6, t7))
    True
    >>> check(b.or_(t1, t2, t3, t4, t5, t6, F7))
    True
    >>> check(b.or_(t3, t4, t5, t6, t7))
    True
    >>> check(b.or_(t1, t2, t3, F11, t4, t5, t6))
    True
    >>> check(b.or_(t2, F3))
    True
    >>> check(b.or_(F2, t3))
    True
    >>> check(b.or_(F2, F3))
    False
    >>> check(b.or_(t3, F4, t5, t6))
    True
    >>> check(b.or_(F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11))
    False
    >>> check(b.or_(F1, F2, F3, F4, F5, F6, t7, F7, F8, F9, F10, F11))
    True


    Note that the data record has *not* been modified at all:

    >>> rec == {
    ...     'source': 'foo.bar',
    ...     'category': 'bots',
    ...     'ignored': True,
    ...     'name': 'Foo Bąr',
    ...     'address': [
    ...         {
    ...             'ip': '10.20.30.41',
    ...             'asn': 12345,
    ...             'cc': 'PL',
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...             'asn': 65538,
    ...         },
    ...         {
    ...             'ip': '10.20.30.43',
    ...             'cc': 'JP',
    ...         },
    ...         {
    ...             'ip': '10.20.30.44',
    ...         },
    ...     ],
    ...     'not_used': None,
    ... }
    True


    Remember that a data record must always be wrapped in
    a `RecordWrapperForPredicates`:

    >>> check(cond_builder['source'] == 'foo.bar', r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['source'] > 'foo.bar', r=rec)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['source'] >= 'foo.bar', r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['source'] < 'foo.bar', r=rec)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['source'] <= 'foo.bar', r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['name'].in_(['Foo Bąr']), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['restriction'].between(['bar', 'foo']), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['name'].contains_substring('Bą'), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['ignored'].is_true(), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder['restriction'].is_null(), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...

    >>> check(cond_builder.not_(
    ...     cond_builder['restriction'].is_null()), r=rec)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... requires `record` being a RecordWrapperForPredicates ...


    Also, note that the data record must *not* contain `None` values:

    >>> wrong = RecordWrapperForPredicates({
    ...     'source': None,
    ...     'ignored': None,
    ...     'name': None,
    ...     'restriction': None,
    ...     'address': [
    ...         {
    ...             'ip': None,
    ...             'asn': 12345,
    ...             'cc': None,
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...             'asn': None,
    ...         },
    ...     ],
    ... })
    >>> check(cond_builder['source'] == 'foo.bar', r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['source'] > 'foo.bar', r=wrong)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['source'] >= 'foo.bar', r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['source'] < 'foo.bar', r=wrong)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['source'] <= 'foo.bar', r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['name'].in_(['Foo Bąr', 'xyz']), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['restriction'].between(['bar', 'foo']), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['name'].contains_substring('Bą'), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['ignored'].is_true(), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['restriction'].is_null(), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder.not_(
    ...     cond_builder['restriction'].is_null()), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['ip'] == 169090602, r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['ip'] > 169090602, r=wrong)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['ip'] >= 169090602, r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['ip'] < 169090602, r=wrong)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['asn'] <= 42, r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['asn'].in_([1, 2, 3]), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['asn'].between([12345, 12347]), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['cc'].contains_substring('PL'), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['asn'].is_true(), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder['asn'].is_null(), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    >>> check(cond_builder.not_(
    ...     cond_builder['cc'].is_null()), r=wrong)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... values being None are not supported ...

    ***

    If you ever implement a new condition class and you want to
    make `CondPredicateMaker` support it, you will need to adjust
    `CondPredicateMaker` by adding and/or enhancing (appropriately)
    some visiting method(s).

    If you do not do that, you may observe an incorrect behaviour (!)
    or get an error, e.g.:

    >>> class XYCond(Cond):
    ...     def _adapt_init_args(*_): return ()
    ...     def __init__(self): pass
    ...
    >>> check(XYCond._make())  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    NotImplementedError: CondPredicateMaker has no ... to handle an instance of XYCond

    ***

    Note that `CondPredicateMaker` may appear very useful when testing
    `CondTransformer` subclasses -- especially those in case of which
    output conditions are supposed to be *logically equivalent* to input
    conditions.

    As an example, let's test three transformer classes defined in this
    module: `CondFactoringTransformer`, `CondEqualityMergingTransformer`
    and `CondDeMorganTransformer`...

    >>> import copy
    >>> from pprint import pformat
    >>> from n6lib.common_helpers import iter_deduplicated
    >>> def cond_transformers_test_helper(label_to_transformer, label_to_test_cond, test_records):
    ...     _initial_label_to_test_cond_repr = repr(label_to_test_cond)
    ...     _initial_test_record_copies = copy.deepcopy(test_records)
    ...
    ...     make_predicate = CondPredicateMaker()
    ...     record_wrappers = list(map(RecordWrapperForPredicates, test_records))
    ...
    ...     _clabel_and_predicate_pairs = (
    ...         (clabel, make_predicate(cond))
    ...         for clabel, cond in label_to_test_cond.items())
    ...     clabel_and_rec_id_to_expected_result = {
    ...         (clabel, id(rec)): predicate(rec)
    ...         for clabel, predicate in _clabel_and_predicate_pairs
    ...             for rec in record_wrappers}
    ...
    ...     seen_conditions = set(label_to_test_cond.values())
    ...
    ...     def prepare_transformer_sequences():
    ...         yield from itertools.permutations(label_to_transformer)
    ...         for tlabel in label_to_transformer:
    ...             yield (tlabel, tlabel)
    ...
    ...     def obtain_transformed_conditions_for(transformer_label_seq):
    ...         tr_making_unseen = collections.Counter()
    ...         tr_making_difference = collections.Counter()
    ...         for clabel, cond in label_to_test_cond.items():
    ...             assert cond in seen_conditions
    ...             for i, tlabel in enumerate(transformer_label_seq):
    ...                 transformer = label_to_transformer[tlabel]
    ...                 output_cond = transformer(cond)
    ...                 if output_cond != cond:
    ...                     tr_making_difference[i] += 1
    ...                     if output_cond not in seen_conditions:
    ...                         seen_conditions.add(output_cond)
    ...                         tr_making_unseen[i] += 1
    ...                 else:
    ...                     assert output_cond in seen_conditions
    ...                 yield clabel, output_cond
    ...                 cond = output_cond
    ...         assert tr_making_unseen.keys() <= tr_making_difference.keys()
    ...
    ...         # Additional logging (mainly to evaluate the quality of test data):
    ...         cond_total = len(label_to_test_cond)
    ...         print(' => '.join(
    ...             # To each transformer label we add a comment that
    ...             # includes two numbers:
    ...             # * the number of output conditions unequal to their
    ...             #   corresponding input conditions;
    ...             # * the number of completely new output conditions
    ...             #   (those unequal to any condition seen before).
    ...             f'{tlabel} *{tr_making_difference[i]}({tr_making_unseen[i]})'
    ...             for i, tlabel in enumerate(transformer_label_seq)))
    ...
    ...     def verify_logical_value_of_cond(clabel, cond):
    ...         nonlocal check_count
    ...         predicate = make_predicate(cond)
    ...         for rec in record_wrappers:
    ...             expected_result = clabel_and_rec_id_to_expected_result[clabel, id(rec)]
    ...             actual_result = predicate(rec)
    ...             if actual_result != expected_result:
    ...                 raise AssertionError(
    ...                     f'expected {expected_result!r} but got {actual_result!r} '
    ...                     f'from predicate made for condition {clabel!a}, applied '
    ...                     f'to:\\n{pformat(rec)}')
    ...             check_count += 1
    ...
    ...     print('----------------')
    ...     print(f'Given:')
    ...     print(f'- {len(label_to_transformer)} condition transformers')
    ...     print(f'- {len(label_to_test_cond)} test conditions')
    ...     print(f'- {len(test_records)} test data records')
    ...     print('----------------')
    ...
    ...     check_count = 0
    ...     for transformer_label_seq in prepare_transformer_sequences():
    ...         for clabel, cond in obtain_transformed_conditions_for(transformer_label_seq):
    ...             verify_logical_value_of_cond(clabel, cond)
    ...
    ...     print('----------------')
    ...     print(f'{check_count} checks made')
    ...     print('----------------')
    ...
    ...     if repr(label_to_test_cond) != _initial_label_to_test_cond_repr:
    ...         raise AssertionError('modified condition(s)?!')
    ...     if test_records != _initial_test_record_copies:
    ...         raise AssertionError('modified record(s)?!')
    ...
    >>> cond_transformers_test_helper(
    ...     label_to_transformer=dict(
    ...         Factoring=CondFactoringTransformer(),
    ...         EqualityMerging=CondEqualityMergingTransformer(),
    ...         DeMorgan=CondDeMorganTransformer(),
    ...     ),
    ...
    ...     label_to_test_cond=dict(
    ...         fixed_true=cond_builder.true(),
    ...         fixed_false=cond_builder.false(),
    ...         t1=t1,
    ...         t2=t2,
    ...         t3=t3,
    ...         t4=t4,
    ...         t5=t5,
    ...         t6=t6,
    ...         t7=t7,
    ...         F1=F1,
    ...         F2=F2,
    ...         F3=F3,
    ...         F4=F4,
    ...         F5=F5,
    ...         F6=F6,
    ...         F7=F7,
    ...         F8=F8,
    ...         F9=F9,
    ...         F10=F10,
    ...         F11=F11,
    ...         factoring_dedicated=cond_builder.or_(
    ...             b.and_(
    ...                 b['restriction'] == 'need-to-know',
    ...                 b['source'] == 'abc.abc',
    ...                 b['asn'] == 42,
    ...             ),
    ...             b.and_(
    ...                 b['restriction'] == 'public',
    ...                 b['source'] == 'abc.abc',
    ...                 b['asn'] == 42.0,
    ...             ),
    ...             b.and_(
    ...                 b['restriction'] == 'internal',
    ...                 b['source'] == 'abc.abc',
    ...             ),
    ...             b.and_(
    ...                 b['restriction'] == 'public',
    ...                 b['source'] == 'def.def',
    ...                 b['asn'] == 1,
    ...             ),
    ...             b.and_(
    ...                 b['restriction'] == 'need-to-know',
    ...                 b['source'] == 'abc.abc',
    ...                 b['asn'] == 12345,
    ...             ),
    ...             b.and_(
    ...                 b['restriction'] == 'public',
    ...                 b['source'] == 'ghi.ghi',
    ...                 b['asn'] == 1.0,
    ...             ),
    ...             b['source'] == 'abc.abc',
    ...             b.and_(
    ...                 b['restriction'] == 'public',
    ...                 b['source'] == 'jkl.jkl',
    ...                 b['asn'] == 42,
    ...             ),
    ...         ),
    ...         equality_merging_dedicated = b.or_(
    ...             b['asn'] == 1,
    ...             b.not_(
    ...                 b.and_(
    ...                     b.not_(
    ...                         b['asn'].in_([7, 5, 3]),
    ...                     ),
    ...                     b.not_(
    ...                         b['asn'] == 5.0,
    ...                     ),
    ...                 ),
    ...             ),
    ...             b['asn'] == 2,
    ...             b['asn'].in_([2, 13, 11]),
    ...         ),
    ...         de_morgan_dedicated = b.not_(
    ...             b.or_(
    ...                 b.not_(
    ...                     b['asn'] == 12345,
    ...                 ),
    ...                 b.not_(
    ...                     b.and_(
    ...                         b['cc'].in_(['PL', 'FR', 'EN']),
    ...                         b['asn'] == 12345,
    ...                     ),
    ...                 ),
    ...                 b['name'].is_null(),
    ...                 b['ignored'].is_true(),
    ...                 b.and_(
    ...                     b['category'] == 'bots',
    ...                     b['ip'].between(123, 123455),
    ...                 ),
    ...                 b.not_(
    ...                     b.or_(
    ...                         b['name'] == 'foo',
    ...                         b['ip'].between(123, 123255),
    ...                     ),
    ...                 ),
    ...             ),
    ...         ),
    ...     ),
    ...
    ...     test_records=[
    ...         rec,
    ...         {},
    ...         {'name': 'foo'},
    ...         {'address': [{'ip': '10.20.30.40', 'asn': 42}, {'ip': '10.20.30.45', 'cc': 'PL'}]},
    ...     ])
    ----------------
    Given:
    - 3 condition transformers
    - 23 test conditions
    - 4 test data records
    ----------------
    Factoring *7(7) => EqualityMerging *12(12) => DeMorgan *10(10)
    Factoring *7(0) => DeMorgan *11(9) => EqualityMerging *12(2)
    EqualityMerging *11(6) => Factoring *7(5) => DeMorgan *10(5)
    EqualityMerging *11(0) => DeMorgan *10(6) => Factoring *7(3)
    DeMorgan *11(6) => Factoring *7(3) => EqualityMerging *12(2)
    DeMorgan *11(0) => EqualityMerging *11(2) => Factoring *7(2)
    Factoring *7(0) => Factoring *0(0)
    EqualityMerging *11(0) => EqualityMerging *0(0)
    DeMorgan *11(0) => DeMorgan *0(0)
    ----------------
    2208 checks made
    ----------------
    """

    def visit_CompoundMultiCond(self, cond: CompoundMultiCond) -> _Predicate:
        op_func = self._get_op_func_for(cond)
        subcondition_predicates = [
            self(subcond)
            for subcond in cond.subconditions]

        def predicate(record):
            return op_func(
                pred(record)
                for pred in subcondition_predicates)

        return predicate


    def visit_NotCond(self, cond: NotCond) -> _Predicate:
        subcond_predicate = self(cond.subcond)

        def predicate(record):
            return not subcond_predicate(record)

        return predicate


    def visit_RecItemCond(self, cond: RecItemCond) -> _Predicate:
        return self._make_predicate_from_RecItemCond(
            cond,
            result_for_missing_item=False)


    def visit_IsNullCond(self, cond: IsNullCond) -> _Predicate:
        return self._make_predicate_from_RecItemCond(
            cond,
            result_for_missing_item=True)


    def visit_FixedCond(self, cond: FixedCond) -> _Predicate:
        truthness = cond.truthness

        def predicate(record):                                           # noqa
            return truthness

        return predicate


    def _make_predicate_from_RecItemCond(self,
                                         cond: RecItemCond,
                                         result_for_missing_item: bool) -> _Predicate:
        MISSING = object()
        NOT_USED = object()

        rec_key = cond.rec_key
        op_func = self._get_op_func_for(cond)
        op_param = getattr(cond, 'op_param', NOT_USED)

        assert op_param is not None
        if __debug__ and isinstance(cond, (InCond, BetweenCond)):
            assert isinstance(op_param, (OPSet, tuple))
            assert not any(item is None for item in op_param)

        def predicate(record: RecordWrapperForPredicates) -> bool:
            if not isinstance(record, RecordWrapperForPredicates):
                raise TypeError(ascii_str(
                    f'predicate function requires `record` being '
                    f'a {RecordWrapperForPredicates.__qualname__} '
                    f'instance (got: {record!r})'))
            value = record.get(rec_key, MISSING)
            if value is MISSING:
                return result_for_missing_item
            if value is None:
                raise TypeError(ascii_str(
                    f'record item values being None are not supported '
                    f'(None found as the value of `{rec_key}` in the '
                    f'record {record!r})'))
            return bool(op_func(value, op_param))

        return predicate


    def _get_op_func_for(self, cond: Cond) -> Callable:
        op_func_name = '_op_func_for_' + cond.__class__.__qualname__
        return getattr(self, op_func_name)

    _op_func_for_AndCond = staticmethod(all)
    _op_func_for_OrCond = staticmethod(any)

    _op_func_for_EqualCond = staticmethod(eq)
    _op_func_for_GreaterCond = staticmethod(gt)
    _op_func_for_GreaterOrEqualCond = staticmethod(ge)
    _op_func_for_LessCond = staticmethod(lt)
    _op_func_for_LessOrEqualCond = staticmethod(le)

    @staticmethod
    def _op_func_for_InCond(value, op_param: OPSet) -> bool:
        # Note: we do not use `in`, because it would engage use of `is`
        # (apart from `==`) on compared items (which would make the
        # `InCond`'s way of value comparison subtly different from the
        # `EqualCond`'s way; and we need them to be perfectly equivalent).
        return any(value == item for item in op_param)

    @staticmethod
    def _op_func_for_BetweenCond(value, op_param: tuple[Any, Any]) -> bool:
        apply_is_between = getattr(value, 'apply_is_between', None)
        if apply_is_between is not None:
            # (`value` is probably an instance of `_ComparableMultiValue`)
            return apply_is_between(op_param)
        else:
            return _is_between(value, op_param)

    @staticmethod
    def _op_func_for_ContainsSubstringCond(value, op_param: str) -> bool:
        apply_contains_substring = getattr(value, 'apply_contains_substring', None)
        if apply_contains_substring is not None:
            # (`value` is probably an instance of `_ComparableMultiValue`)
            return apply_contains_substring(op_param)
        else:
            return _contains_substring(value, op_param)

    @staticmethod
    def _op_func_for_IsTrueCond(value, _op_param) -> bool:
        apply_is_true = getattr(value, 'apply_is_true', None)
        if apply_is_true is not None:
            # (`value` is probably an instance of `_ComparableMultiValue`)
            return apply_is_true()
        else:
            return _is_true(value)

    @staticmethod
    def _op_func_for_IsNullCond(_value, _op_param) -> bool:
        # Note that the `result_for_missing_item` argument passed to
        # `_make_predicate_from_RecItemCond()` is `True` -- and the
        # following result is only for the *non-missing* case.
        return False


class RecordWrapperForPredicates:

    r"""
    A wrapper that adapts a mapping (such as a `dict` or `RecordDict`)
    for predicate functions generated with `CondPredicateMaker`.

    Constructor args/kwargs:
        `underlying_mapping`:
            A mapping (typically, a dict or an instance of
            `n6lib.record_dict.RecordDict`).

    This class provides only one mapping method, `get()`, which pretends
    to behave like a normal `dict.get()`; note that the method can raise
    `NotImplementedError` if a given key does not belong to the limited
    set of supported keys (see the `_get_*_value()` private methods).

    >>> rec = {
    ...     'source': 'foo.bar',
    ...     'category': 'bots',
    ...     'ignored': False,
    ...     'name': 'Foo Bąr',
    ...     'address': [
    ...         {
    ...             'ip': '10.20.30.41',
    ...             'asn': 12345,
    ...             'cc': 'PL',
    ...         },
    ...         {
    ...             'ip': '10.20.30.42',
    ...             'asn': 65538,
    ...         },
    ...         {
    ...             'ip': '10.20.30.43',
    ...             'cc': 'JP',
    ...         },
    ...         {
    ...             'ip': '10.20.30.44',
    ...         },
    ...     ],
    ...     'not_used': None,
    ... }
    >>> r = RecordWrapperForPredicates(rec)
    >>> between_op_func = CondPredicateMaker._op_func_for_BetweenCond
    >>> contains_substring_func = CondPredicateMaker._op_func_for_ContainsSubstringCond
    >>> sentinel = object()

    >>> _repr = repr(r)
    >>> _repr.startswith('RecordWrapperForPredicates({')
    True
    >>> _repr.endswith('})')
    True
    >>> repr(rec) in _repr
    True

    >>> r.get('source') == 'foo.bar' and r.get('source') == 'foo.bar'
    True
    >>> r.get('source') > 'foo.baqq' and r.get('source') <= 'foo.bar'
    True
    >>> r.get('source') >= 'foo.bar' and r.get('source') < 'foo.barr'
    True
    >>> between_op_func(r.get('source'), ('a', 'z'))
    True
    >>> between_op_func(r.get('source'), ('a', 'foo.bar'))
    True
    >>> between_op_func(r.get('source'), ('foo.bar', 'z'))
    True
    >>> r.get('category') == 'bots' and r.get('category') == 'bots'
    True
    >>> r.get('ignored') == False and r.get('ignored') == 0
    True
    >>> r.get('name') == 'Foo Bąr'
    True
    >>> contains_substring_func(r.get('name'), 'Foo Bąr')
    True
    >>> contains_substring_func(r.get('name'), 'Foo')
    True
    >>> contains_substring_func(r.get('name'), ' Bąr')
    True
    >>> contains_substring_func(r.get('name'), 'oo B')
    True
    >>> contains_substring_func(r.get('name'), ' ')
    True
    >>> contains_substring_func(r.get('name'), '')
    True
    >>> r.get('restriction') is None
    True
    >>> r.get('restriction', sentinel) is sentinel
    True
    >>> r.get('source', sentinel) == 'foo.bar'
    True
    >>> r.get('ip', sentinel) == 169090601
    True
    >>> r.get('ip') == 169090601
    True
    >>> r.get('ip') == 169090602
    True
    >>> r.get('ip') == 169090603
    True
    >>> r.get('ip') == 169090604
    True
    >>> r.get('ip') <= 169090601 and r.get('ip') >= 169090604
    True
    >>> r.get('ip') <= 169090603 and r.get('ip') >= 169090603
    True
    >>> r.get('ip') <= 4294967295 and r.get('ip') >= 0
    True
    >>> r.get('ip') < 169090602 and r.get('ip') > 169090603
    True
    >>> r.get('ip') < 4294967295 and r.get('ip') > 0
    True
    >>> between_op_func(r.get('ip'), (0, 169090601))
    True
    >>> between_op_func(r.get('ip'), (169090602, 169090603))
    True
    >>> between_op_func(r.get('ip'), (169090604, 4294967295))
    True
    >>> between_op_func(r.get('ip'), (0, 4294967295))
    True
    >>> r.get('asn') == 12345 and r.get('asn') <= 12345 and r.get('asn') >= 12345
    True
    >>> r.get('asn') == 65538 and r.get('asn') <= 65538 and r.get('asn') >= 65538
    True
    >>> r.get('asn') <= 4294967295 and r.get('asn') >= 0
    True
    >>> r.get('asn') <= 65538 and r.get('asn') >= 65538
    True
    >>> r.get('asn') < 12346 and r.get('asn') > 65537 and r.get('asn') > 12344
    True
    >>> r.get('asn') < 65539 and r.get('asn') > 65537
    True
    >>> between_op_func(r.get('asn'), (0, 12345))
    True
    >>> between_op_func(r.get('asn'), (12345, 12346))
    True
    >>> between_op_func(r.get('asn'), (65537, 65538))
    True
    >>> between_op_func(r.get('asn'), (65538, 4294967295))
    True
    >>> r.get('cc') == 'PL' and r.get('cc') == 'JP'
    True
    >>> r.get('cc') <= 'JP' and r.get('cc') > 'PK'
    True
    >>> contains_substring_func(r.get('cc'), 'P')
    True
    >>> contains_substring_func(r.get('cc'), 'PL')
    True
    >>> contains_substring_func(r.get('cc'), 'L')
    True
    >>> contains_substring_func(r.get('cc'), 'J')
    True
    >>> contains_substring_func(r.get('cc'), 'JP')
    True
    >>> contains_substring_func(r.get('cc'), '')
    True

    >>> r.get('source') == 'Foo.Bar'
    False
    >>> r.get('source') > 'foo.bar' or r.get('source') <= 'foo.baqq'
    False
    >>> r.get('source') >= 'foo.barr' or r.get('source') < 'foo.bar'
    False
    >>> between_op_func(r.get('source'), ('a', 'foo.ba'))
    False
    >>> between_op_func(r.get('source'), ('foo.bazz', 'z'))
    False
    >>> r.get('category') == 'BOTS' or r.get('category') == ''
    False
    >>> r.get('ignored') == True or r.get('ignored') == 1
    False
    >>> r.get('name') == 'Foo Bar'
    False
    >>> contains_substring_func(r.get('name'), 'foo')
    False
    >>> contains_substring_func(r.get('name'), ' Foo')
    False
    >>> contains_substring_func(r.get('name'), 'Bąr ')
    False
    >>> contains_substring_func(r.get('name'), 'ooB')
    False
    >>> contains_substring_func(r.get('name'), 'oo  B')
    False
    >>> contains_substring_func(r.get('name'), '  ')
    False
    >>> r.get('source', sentinel) is sentinel
    False
    >>> r.get('ip', sentinel) is sentinel
    False
    >>> r.get('ip') == 169090605 or r.get('ip') == 0 or r.get('ip') == 169090600
    False
    >>> r.get('ip') <= 0 or r.get('ip') >= 4294967295
    False
    >>> r.get('ip') <= 169090600 or r.get('ip') >= 169090605
    False
    >>> r.get('ip') < 169090601 or r.get('ip') > 169090604
    False
    >>> between_op_func(r.get('ip'), (0, 169090600))
    False
    >>> between_op_func(r.get('ip'), (169090605, 4294967295))
    False
    >>> between_op_func(r.get('ip'), (169090603, 169090602))
    False
    >>> between_op_func(r.get('ip'), (-4294967295, 0))
    False
    >>> r.get('asn') == 12346 or r.get('asn') <= 12344 or r.get('asn') >= 65539
    False
    >>> r.get('asn') == 65537 or r.get('asn') <= 0 or r.get('asn') >= 4294967295
    False
    >>> r.get('asn') < 12345 or r.get('asn') > 65538
    False
    >>> r.get('asn') < 9000 or r.get('asn') > 4294901760
    False
    >>> between_op_func(r.get('asn'), (1000000, 4294967295))
    False
    >>> between_op_func(r.get('asn'), (0, 9000))
    False
    >>> between_op_func(r.get('asn'), (12345, 0))
    False
    >>> between_op_func(r.get('asn'), (0, 12344))
    False
    >>> between_op_func(r.get('asn'), (12346, 65537))
    False
    >>> between_op_func(r.get('asn'), (65539, 4294967295))
    False
    >>> r.get('cc') == 'PRL' or r.get('cc') == 'jp'
    False
    >>> r.get('cc') < 'JP' or r.get('cc') >= 'PM'
    False
    >>> contains_substring_func(r.get('cc'), 'R')
    False
    >>> contains_substring_func(r.get('cc'), 'LP')
    False
    >>> contains_substring_func(r.get('cc'), 'p')
    False
    >>> contains_substring_func(r.get('cc'), 'j')
    False
    >>> contains_substring_func(r.get('cc'), 'JP ')
    False
    >>> contains_substring_func(r.get('cc'), ' ')
    False

    >>> contains_substring_func(r.get('ip'), '0')
    Traceback (most recent call last):
      ...
    TypeError: only a str can contain a substring (got: 169090601 which is an instance of int)

    >>> r.get('address') == []
    Traceback (most recent call last):
      ...
    NotImplementedError: RecordWrapperForPredicates._get_address_value() not implemented

    >>> r.get('url') == 'http://foo.bar'
    Traceback (most recent call last):
      ...
    NotImplementedError: RecordWrapperForPredicates._get_url_value() not implemented

    >>> nokeys = RecordWrapperForPredicates({})
    >>> nokeys.get('source') is None
    True
    >>> nokeys.get('source', sentinel) is sentinel
    True
    >>> nokeys.get('source') is None
    True
    >>> nokeys.get('source', sentinel) is sentinel
    True
    >>> nokeys.get('ip') is None
    True
    >>> nokeys.get('ip', sentinel) is sentinel
    True
    >>> nokeys.get('ip') is None
    True
    >>> nokeys.get('ip', sentinel) is sentinel
    True
    """

    def __init__(self, underlying_mapping):
        self._underlying_mapping = underlying_mapping
        self._cache = {}

    def __repr__(self):
        return f'{self.__class__.__qualname__}({self._underlying_mapping!r})'

    # (typically called by a predicate function created
    # with a `CondPredicateMaker`)
    def get(self, key, default=None, *,
            _NOT_CACHED=object(),
            _MISSING=object()):
        value = self._cache.get(key, _NOT_CACHED)
        if value is _NOT_CACHED:
            value_getter_name = f'_get_{key}_value'
            try:
                value_getter = getattr(self, value_getter_name)
            except AttributeError as exc:
                raise NotImplementedError(ascii_str(
                    f'{self.__class__.__qualname__}'
                    f'.{value_getter_name}() not implemented')) from exc
            self._cache[key] = value = value_getter(key, _MISSING)
        if value is _MISSING:
            return default
        return value

    # * Value getters' implementation details:

    def __simple_getter(self, key, default):
        # Note: if `None` is returned, the predicate function
        # being the caller of `.get()` will raise `TypeError`.
        return self._underlying_mapping.get(key, default)

    def __address_item_getter(self, key, default, *, value_adjuster=None):
        values = [
            addr[key]
            for addr in self._underlying_mapping.get('address', ())
            if key in addr]
        if not values:
            return default
        if any(val is None for val in values):
            # Note: because of obtaining `None`, the predicate function
            # being the caller of `.get()` will raise `TypeError`.
            return None
        if value_adjuster is not None:
            values = map(value_adjuster, values)
        return _ComparableMultiValue(values)

    # * Actual value getters (invoked in `.get()`):

    # Note: the set of available keys is consciously limited to those
    # which are really needed -- we do not want to provide a "get any
    # other items just like that" feature because of the risk of
    # introducing silent bugs in the future (different keys may need
    # different ways of lookup, as you can see here...).

    _get_source_value = __simple_getter
    _get_restriction_value = __simple_getter
    _get_category_value = __simple_getter
    _get_ignored_value = __simple_getter
    _get_name_value = __simple_getter

    _get_ip_value = functools.partialmethod(__address_item_getter, value_adjuster=ip_str_to_int)
    _get_asn_value = __address_item_getter
    _get_cc_value = __address_item_getter


class _ComparableMultiValue:

    """
    >>> v = _ComparableMultiValue([0, 42, -1, 333.333])
    >>> v == 0 and v == 42 and v == -1 and v == 333.333
    True
    >>> v >= 0 and v >= 42 and v >= -1 and v >= 333.333
    True
    >>> v >= -0.01 and v >= 41 and v >= -2 and v >= 333.33 and v >= -1000
    True
    >>> v > -0.01 and v > 41 and v > -2 and v > 333.33 and v > -1000
    True
    >>> v <= 0 and v <= 42 and v <= -1 and v <= 333.333
    True
    >>> v <= 0.01 and v <= 43 and v <= 0 and v <= 333.3333 and v <= 1000
    True
    >>> v < 0.01 and v < 43 and v < 0 and v < 333.3333 and v <= 1000
    True
    >>> v >= 43 and v <= 333
    True
    >>> (v.apply_is_between((43, 1000)) and
    ...  v.apply_is_between((333.333, 1000)) and
    ...  v.apply_is_between((42, 42)) and
    ...  v.apply_is_between((41, 43)) and
    ...  v.apply_is_between((-0.5, 41.5)) and
    ...  v.apply_is_between((-1000, -0.5)) and
    ...  v.apply_is_between((-1.5, -0.5)) and
    ...  v.apply_is_between((-1000, 1000)))
    True
    >>> (v == -42 or v == '42' or v == 43 or v == 1 or v == 333.33 or
    ...  v == 1000 or v == '1' or v == '0' or v == [-1] or v == (333.333,))
    False
    >>> v > 1000 or v > 333.333 or v < -1 or v < -1000
    False
    >>> v >= 1000 or v >= 333.3333 or v <= -1.01 or v <= -1000
    False
    >>> (v.apply_is_between((333.3333, 1000)) or
    ...  v.apply_is_between((334, 335)) or
    ...  v.apply_is_between((43, 333)) or
    ...  v.apply_is_between((43, 41)) or
    ...  v.apply_is_between((0.5, 41.5)) and
    ...  v.apply_is_between((-0.7, -0.5)) or
    ...  v.apply_is_between((-1000, -1.5)))
    False
    >>> v.apply_contains_substring('foo')
    Traceback (most recent call last):
      ...
    TypeError: only a str can contain a substring (got: 0 which is an instance of int)
    >>> v != 42
    Traceback (most recent call last):
      ...
    AssertionError: unsupported operation `!=` attempted! (a bug in CondPredicateMaker?)

    >>> v2 = _ComparableMultiValue(['foo', 'bar', 'spam', 'spamming'])
    >>> v2 == 'foo' and v2 == 'bar' and v2 == 'spam' and v2 == 'spamming'
    True
    >>> v2 >= 'foo' and v2 >= 'bar' and v2 >= 'spam' and v2 >= 'spamming'
    True
    >>> v2 >= 'fo' and v2 >= 'ba' and v2 >= 'spa' and v2 >= 'spammi'
    True
    >>> v2 > 'fo' and v2 > 'ba' and v2 > 'spa' and v2 > 'spammi'
    True
    >>> v2 <= 'foo' and v2 <= 'bar' and v2 <= 'spam' and v2 <= 'spamming'
    True
    >>> v2 <= 'fooo' and v2 <= 'barek' and v2 <= 'spamer' and v2 <= 'spammz'
    True
    >>> v2 < 'fooo' and v2 < 'barek' and v2 < 'spamer' and v2 < 'spammz'
    True
    >>> v2 >= 'foooo' and v2 <= 'spa'
    True
    >>> (v2.apply_is_between(('bar', 'foo')) and
    ...  v2.apply_is_between(('a', 'z')) and
    ...  v2.apply_is_between(('foo', 'spam')) and
    ...  v2.apply_is_between(('foo', 'spa')) and
    ...  v2.apply_is_between(('fooo', 'spam')) and
    ...  v2.apply_is_between(('fo', 'spami')) and
    ...  v2.apply_is_between(('a', 'bar')) and
    ...  v2.apply_is_between(('spamming', 'z')))
    True
    >>> (v2.apply_contains_substring('foo') and
    ...  v2.apply_contains_substring('bar') and
    ...  v2.apply_contains_substring('spam') and
    ...  v2.apply_contains_substring('spamming') and
    ...  v2.apply_contains_substring('o') and
    ...  v2.apply_contains_substring('oo') and
    ...  v2.apply_contains_substring('fo') and
    ...  v2.apply_contains_substring('b') and
    ...  v2.apply_contains_substring('a') and
    ...  v2.apply_contains_substring('r') and
    ...  v2.apply_contains_substring('ba') and
    ...  v2.apply_contains_substring('ar') and
    ...  v2.apply_contains_substring('s') and
    ...  v2.apply_contains_substring('sp') and
    ...  v2.apply_contains_substring('pa') and
    ...  v2.apply_contains_substring('am') and
    ...  v2.apply_contains_substring('spa') and
    ...  v2.apply_contains_substring('pam') and
    ...  v2.apply_contains_substring('mm') and
    ...  v2.apply_contains_substring('ming') and
    ...  v2.apply_contains_substring('pammi') and
    ...  v2.apply_contains_substring('ammin') and
    ...  v2.apply_contains_substring('ammi') and
    ...  v2.apply_contains_substring('pammin') and
    ...  v2.apply_contains_substring('spammin') and
    ...  v2.apply_contains_substring('amming'))
    True
    >>> v2 == 'Foo' or v2 == 'BAR' or v2 == 'spaM' or v2 == 'spAmming'
    False
    >>> v2 == 'fo' or v2 == 'fooo' or v2 == 'oo' or v2 == 'spammi'
    False
    >>> v2 < 'bar' or v2 > 'spamming'
    False
    >>> v2 <= 'baq' or v2 >= 'spamminga'
    False
    >>> (v2.apply_is_between(('foooo', 'spa')) or
    ...  v2.apply_is_between(('z', 'a')) or
    ...  v2.apply_is_between(('a', 'baq')) or
    ...  v2.apply_is_between(('spamminga', 'z')))
    False
    >>> (v2.apply_contains_substring('zoo') or
    ...  v2.apply_contains_substring('qbar') or
    ...  v2.apply_contains_substring('span') or
    ...  v2.apply_contains_substring('spamminga') or
    ...  v2.apply_contains_substring('oO') or
    ...  v2.apply_contains_substring('BAR') or
    ...  v2.apply_contains_substring('pAm') or
    ...  v2.apply_contains_substring('Ammi') or
    ...  v2.apply_contains_substring('oof') or
    ...  v2.apply_contains_substring('ooo') or
    ...  v2.apply_contains_substring('br') or
    ...  v2.apply_contains_substring('amr') or
    ...  v2.apply_contains_substring('sa') or
    ...  v2.apply_contains_substring('sm') or
    ...  v2.apply_contains_substring('paam') or
    ...  v2.apply_contains_substring('rr') or
    ...  v2.apply_contains_substring('afoob') or
    ...  v2.apply_contains_substring('samming') or
    ...  v2.apply_contains_substring('ammig'))
    False
    >>> v2 != 'foo'
    Traceback (most recent call last):
      ...
    AssertionError: unsupported operation `!=` attempted! (a bug in CondPredicateMaker?)

    >>> _ComparableMultiValue([True]).apply_is_true()
    True
    >>> _ComparableMultiValue([False]).apply_is_true()
    False
    >>> _ComparableMultiValue([True, False, True]).apply_is_true()
    True
    >>> _ComparableMultiValue([False, True, False]).apply_is_true()
    True
    """

    def __init__(self, iterable: Iterable):
        self._values = tuple(iterable)
        assert all(
            value is not None
            for value in self._values)

    __hash__ = None

    # (related to `EqualCond` and `InCond`)
    def __eq__(self, op_param) -> bool:
        return self._does_any_value_satisfy(eq, op_param)

    # (unsupported; see the rationale in the docs of `CondBuilder`...)
    def __ne__(self, op_param) -> NoReturn:
        raise AssertionError(
            f'unsupported operation `!=` attempted! '
            f'(a bug in {CondPredicateMaker.__qualname__}?)')

    # (related to `GreaterCond`)
    def __gt__(self, op_param) -> bool:
        return self._does_any_value_satisfy(gt, op_param)

    # (related to `GreaterOrEqualCond`)
    def __ge__(self, op_param) -> bool:
        return self._does_any_value_satisfy(ge, op_param)

    # (related to `LessCond`)
    def __lt__(self, op_param) -> bool:
        return self._does_any_value_satisfy(lt, op_param)

    # (related to `LessOrEqualCond`)
    def __le__(self, op_param) -> bool:
        return self._does_any_value_satisfy(le, op_param)

    # (related to `BetweenCond`)
    def apply_is_between(self, op_param: tuple[Any, Any]) -> bool:
        return self._does_any_value_satisfy(_is_between, op_param)

    # (related to `ContainsSubstringCond`)
    def apply_contains_substring(self, op_param: str) -> bool:
        return self._does_any_value_satisfy(_contains_substring, op_param)

    def _does_any_value_satisfy(self, op, op_param) -> bool:
        return any(
            op(value, op_param)
            for value in self._values)

    # (related to `IsTrueCond`)
    def apply_is_true(self) -> bool:
        op = _is_true
        return any(
            op(value)
            for value in self._values)


def _is_between(value, op_param: tuple[Any, Any]) -> bool:
    min_value, max_value = op_param
    return min_value <= value <= max_value


def _contains_substring(value: str, op_param: str) -> bool:
    if not isinstance(value, str):
        raise TypeError(ascii_str(
            f"only a str can contain a substring (got: {value!r} "
            f"which is an instance of {value.__class__.__qualname__})"))
    return op_param in value


def _is_true(value: bool) -> bool:
    if not isinstance(value, bool):
        raise TypeError(ascii_str(
            f"only a bool can be used as a TRUE/FALSE flag (got: {value!r} "
            f"which is an instance of {value.__class__.__qualname__})"))
    return value


#
# Tools related to optimization/adjustment of conditions
#

class CondFactoringTransformer(CondTransformer[Cond]):

    """
    A visitor class to apply to given conditions (recursively)
    a transformation, the essence of which is:

    `(x AND a) OR (x AND b) OR (x AND c) OR e` -> `(x AND (a OR b OR c)) OR e`
    `(x OR a) AND (x OR b) AND (x OR c) AND e` -> `(x OR (a AND b AND c)) AND e`

    TODO: *better description here*.

    `(x AND a AND y AND b) OR (c AND x AND y AND d) OR (e AND x AND f AND y) OR e`
    -> `(x AND y AND ((d AND e) OR (f AND g) OR (h AND i))) OR e`

    `(x AND a) OR (x AND b) or x`
    -> `x`

    XXX

    It is important that the output is always *logically equivalent* to
    the input.

    Let the examples speak...

    >>> factor_out = CondFactoringTransformer()
    >>> b = CondBuilder()
    >>> c1 = b.or_(
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'def.def',
    ...         b['asn'] == 1,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'ghi.ghi',
    ...         b['asn'] == 1.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'jkl.jkl',
    ...         b['asn'] == 42,
    ...     ),
    ... )
    >>> repr(c1) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'def.def'>, "
    ...             "<EqualCond: 'asn', 1>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'ghi.ghi'>, "
    ...             "<EqualCond: 'asn', 1.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'jkl.jkl'>, "
    ...             "<EqualCond: 'asn', 42>>>")
    True
    >>> repr(factor_out(c1)) == (
    ...     "<AndCond: "
    ...         "<EqualCond: 'restriction', 'public'>, "
    ...         "<OrCond: "
    ...             "<AndCond: "
    ...                 "<EqualCond: 'asn', 42.0>, "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'source', 'abc.abc'>, "
    ...                     "<EqualCond: 'source', 'jkl.jkl'>>>, "
    ...             "<AndCond: "
    ...                 "<EqualCond: 'asn', 1>, "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'source', 'def.def'>, "
    ...                     "<EqualCond: 'source', 'ghi.ghi'>>>>>")
    True

    >>> c1extra = b.or_(
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'def.def',
    ...         b['asn'] == 1,
    ...         b.not_(b['ignored'].is_true()),
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'jkl.jkl',
    ...         b['asn'] == 42,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b.not_(b['ignored'].is_true()),
    ...         b['source'] == 'ghi.ghi',
    ...         b['asn'] == 1.0,
    ...     ),
    ... )
    >>> repr(c1extra) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'def.def'>, "
    ...             "<EqualCond: 'asn', 1>, "
    ...             "<NotCond: "
    ...                 "<IsTrueCond: 'ignored'>>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'jkl.jkl'>, "
    ...             "<EqualCond: 'asn', 42>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<NotCond: "
    ...                 "<IsTrueCond: 'ignored'>>, "
    ...             "<EqualCond: 'source', 'ghi.ghi'>, "
    ...             "<EqualCond: 'asn', 1.0>>>")
    True
    >>> repr(factor_out(c1extra)) == (
    ...     "<AndCond: "
    ...         "<EqualCond: 'restriction', 'public'>, "
    ...         "<OrCond: "
    ...             "<AndCond: "
    ...                 "<EqualCond: 'asn', 42.0>, "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'source', 'abc.abc'>, "
    ...                     "<EqualCond: 'source', 'jkl.jkl'>>>, "
    ...             "<AndCond: "
    ...                 "<EqualCond: 'asn', 1>, "
    ...                 "<NotCond: "
    ...                     "<IsTrueCond: 'ignored'>>, "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'source', 'def.def'>, "
    ...                     "<EqualCond: 'source', 'ghi.ghi'>>>>>")
    True

    >>> c2 = b.or_(
    ...     b.and_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'def.def',
    ...         b['asn'] == 1,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 12345,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'ghi.ghi',
    ...         b['asn'] == 1.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'jkl.jkl',
    ...         b['asn'] == 42,
    ...     ),
    ... )
    >>> repr(c2) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'def.def'>, "
    ...             "<EqualCond: 'asn', 1>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 12345>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'ghi.ghi'>, "
    ...             "<EqualCond: 'asn', 1.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'jkl.jkl'>, "
    ...             "<EqualCond: 'asn', 42>>>")
    True
    >>> repr(factor_out(c2)) == (
    ...   "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<OrCond: "
    ...                 "<EqualCond: 'asn', 42>, "
    ...                 "<EqualCond: 'asn', 12345>>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<OrCond: "
    ...                 "<AndCond: "
    ...                     "<EqualCond: 'asn', 42.0>, "
    ...                     "<OrCond: "
    ...                         "<EqualCond: 'source', 'abc.abc'>, "
    ...                         "<EqualCond: 'source', 'jkl.jkl'>>>, "
    ...                 "<AndCond: "
    ...                     "<EqualCond: 'asn', 1>, "
    ...                     "<OrCond: "
    ...                         "<EqualCond: 'source', 'def.def'>, "
    ...                         "<EqualCond: 'source', 'ghi.ghi'>>>>>>")
    True

    >>> c3 = b.or_(
    ...     b.and_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42.0,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'internal',
    ...         b['source'] == 'abc.abc',
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'def.def',
    ...         b['asn'] == 1,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 12345,
    ...     ),
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'ghi.ghi',
    ...         b['asn'] == 1.0,
    ...     ),
    ...     b['source'] == 'abc.abc',
    ...     b.and_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'jkl.jkl',
    ...         b['asn'] == 42,
    ...     ),
    ... )
    >>> repr(c3) == (
    ...     "<OrCond: "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42.0>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'internal'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'def.def'>, "
    ...             "<EqualCond: 'asn', 1>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 12345>>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'ghi.ghi'>, "
    ...             "<EqualCond: 'asn', 1.0>>, "
    ...         "<EqualCond: 'source', 'abc.abc'>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'jkl.jkl'>, "
    ...             "<EqualCond: 'asn', 42>>>")
    True
    >>> repr(factor_out(c3)) == (
    ...     "<OrCond: "
    ...         "<EqualCond: 'source', 'abc.abc'>, "
    ...         "<AndCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<OrCond: "
    ...                 "<AndCond: "
    ...                     "<EqualCond: 'asn', 1>, "
    ...                     "<OrCond: "
    ...                         "<EqualCond: 'source', 'def.def'>, "
    ...                         "<EqualCond: 'source', 'ghi.ghi'>>>, "
    ...                 "<AndCond: "
    ...                     "<EqualCond: 'source', 'jkl.jkl'>, "
    ...                     "<EqualCond: 'asn', 42>>>>>")
    True

    >>> c4 = b.and_(
    ...     b.or_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42,
    ...     ),
    ...     b.or_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 42.0,
    ...     ),
    ...     b.or_(
    ...         b['restriction'] == 'internal',
    ...         b['source'] == 'abc.abc',
    ...     ),
    ...     b.or_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'def.def',
    ...         b['asn'] == 1,
    ...     ),
    ...     b.or_(
    ...         b['restriction'] == 'need-to-know',
    ...         b['source'] == 'abc.abc',
    ...         b['asn'] == 12345,
    ...     ),
    ...     b.or_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'ghi.ghi',
    ...         b['asn'] == 1.0,
    ...     ),
    ...     b['source'] == 'abc.abc',
    ...     b.or_(
    ...         b['restriction'] == 'public',
    ...         b['source'] == 'jkl.jkl',
    ...         b['asn'] == 42,
    ...     ),
    ... )
    >>> repr(c4) == (
    ...     "<AndCond: "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 42.0>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'internal'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'def.def'>, "
    ...             "<EqualCond: 'asn', 1>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'need-to-know'>, "
    ...             "<EqualCond: 'source', 'abc.abc'>, "
    ...             "<EqualCond: 'asn', 12345>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'ghi.ghi'>, "
    ...             "<EqualCond: 'asn', 1.0>>, "
    ...         "<EqualCond: 'source', 'abc.abc'>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<EqualCond: 'source', 'jkl.jkl'>, "
    ...             "<EqualCond: 'asn', 42>>>")
    True
    >>> repr(factor_out(c4)) == (
    ...     "<AndCond: "
    ...         "<EqualCond: 'source', 'abc.abc'>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'restriction', 'public'>, "
    ...             "<AndCond: "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'asn', 1>, "
    ...                     "<AndCond: "
    ...                         "<EqualCond: 'source', 'def.def'>, "
    ...                         "<EqualCond: 'source', 'ghi.ghi'>>>, "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'source', 'jkl.jkl'>, "
    ...                     "<EqualCond: 'asn', 42>>>>>")
    True

    TODO: *maybe more doctest...*
    """

    def visit_AndCond(self, cond: AndCond) -> Cond:                       # noqa
        # The object being visited (`cond`) represents an `AND` condition
        # (we will make use of the fact that `OR` is *distributive* over
        # `AND`), so its `OR` top-level subconditions will be concerned
        # -- to apply a transformation the essence of which is:
        # `(x OR a) AND (x OR b) AND (x OR c)` -> `x OR (a AND b AND c)`
        toplevel_multi_subcond_cls = OrCond
        if new_cond := self._new_cond_with_most_shared_2ndlevel_subconds_factored_out(
                cond,
                toplevel_multi_subcond_cls):

            # (note: within this recursive call, other `new_cond`'s
            # 2nd-level subconditions may be factored out as well...)
            return self(new_cond)

        return self.subvisit(cond)


    def visit_OrCond(self, cond: OrCond) -> Cond:                         # noqa
        # The object being visited (`cond`) represents an `OR` condition
        # (we will make use of the fact that `AND` is *distributive* over
        # `OR`), so its `AND` top-level subconditions will be concerned
        # -- to apply a transformation the essence of which is:
        # `(x AND a) OR (x AND b) OR (x AND c)` -> `x AND (a OR b OR c)`
        toplevel_multi_subcond_cls = AndCond
        if new_cond := self._new_cond_with_most_shared_2ndlevel_subconds_factored_out(
                cond,
                toplevel_multi_subcond_cls):

            # (note: within this recursive call, other `new_cond`'s
            # 2nd-level subconditions may be factored out as well...)
            return self(new_cond)

        return self.subvisit(cond)


    _AndOrCond = Union[AndCond, OrCond]
    _CondList = list[Cond]


    def _new_cond_with_most_shared_2ndlevel_subconds_factored_out(
            self,
            cond: _AndOrCond,
            toplevel_multi_subcond_cls: type[_AndOrCond]) -> Optional[Cond]:

        # (see the relevant comments in `visit_AndCond()` and `visit_OrCond()`)
        assert (isinstance(cond, AndCond) and issubclass(toplevel_multi_subcond_cls, OrCond)
                or isinstance(cond, OrCond) and issubclass(toplevel_multi_subcond_cls, AndCond))

        def make_multi_subcond(*its_subconditions):
            return self.make_cond(toplevel_multi_subcond_cls, its_subconditions)

        def iter_2ndlevel_subconds(parent_):
            if isinstance(parent_, toplevel_multi_subcond_cls):
                yield from parent_.subconditions
            else:
                # Note: `parent_` is not a `toplevel_multi_subcond_cls`,
                # so we yield just `parent_` (see also: the comment in
                # `_gather_subcond_mappings()` and the "If nothing is
                # yielded..." comment below).
                yield parent_

        if extracted := self._extract_most_shared_2ndlevel_subconds_and_their_toplevel_parents(
                cond,
                toplevel_multi_subcond_cls):
            extracted_2ndlevel_subconds, toplevel_subconds_being_replaced = extracted
            factored_out_cond = make_multi_subcond(*extracted_2ndlevel_subconds)
            in_bracket_cond = self.make_cond(cond.__class__, [
                # If nothing is yielded here by `iter_altered(...)`
                # -- this is the case when every condition yielded
                # by `iter_2ndlevel_subconds(...)` is equal to some
                # condition in `extracted_2ndlevel_subconds` -- then we
                # obtain a `FixedCond` which represents the *absorbing
                # element* of `cond.__class__`, that is, a `<FixedCond:
                # False>` if `cond` is an `AndCond`, or a `<FixedCond:
                # True>` if `cond` is an `OrCond`. Note that -- then --
                # `in_bracket_cond` will be set to such a `FixedCond`
                # (because of the *absorbing-element*-focused reduction
                # applied by the `AndCond`'s/`OrCond`'s constructor)
                # -- which will be ignored when the `replacing_subcond`
                # condition will be constructed (because of the
                # *neutral-element*-focused reduction applied by
                # the `AndCond`'s/`OrCond`'s constructor).
                make_multi_subcond(*iter_altered(
                    iter_2ndlevel_subconds(parent),
                    without_items=extracted_2ndlevel_subconds))
                for parent in toplevel_subconds_being_replaced])
            replacing_subcond = make_multi_subcond(factored_out_cond, in_bracket_cond)
            new_subconditions = iter_altered(
                cond.subconditions,
                without_items=toplevel_subconds_being_replaced,
                extra_items=[replacing_subcond])
            return self.make_cond(cond.__class__, new_subconditions)

        return None


    def _extract_most_shared_2ndlevel_subconds_and_their_toplevel_parents(
            self,
            cond: _AndOrCond,
            toplevel_multi_subcond_cls: type[_AndOrCond]) -> Optional[tuple[_CondList, _CondList]]:

        (subc_to_parent_count,
         subc_to_parents) = self._gather_subcond_mappings(cond, toplevel_multi_subcond_cls)

        if shared_2ndlevel_subconds := [
                # (sorted: most shared ones at the beginning)
                subc for subc, count in subc_to_parent_count.most_common()
                if count > 1]:
            grouper = itertools.groupby(shared_2ndlevel_subconds, key=subc_to_parents.__getitem__)
            extracted_2ndlevel_subconds_iterator, their_parents = reversed(next(grouper))  # noqa
            extracted_2ndlevel_subconds = list(extracted_2ndlevel_subconds_iterator)
            assert (extracted_2ndlevel_subconds and their_parents
                    and isinstance(extracted_2ndlevel_subconds, list)
                    and isinstance(their_parents, list)
                    and set(their_parents).issubset(cond.subconditions)
                    and all(isinstance(parent, Cond)
                            for parent in their_parents)
                    and all(their_parents == subc_to_parents[subc]
                            for subc in extracted_2ndlevel_subconds))
            return extracted_2ndlevel_subconds, their_parents

        return None


    def _gather_subcond_mappings(
            self,
            cond: _AndOrCond,
            toplevel_multi_subcond_cls: type[_AndOrCond]) -> tuple[collections.Counter[Cond],
                                                                   collections.defaultdict[
                                                                       Cond, _CondList]]:
        subc_to_parent_count = collections.Counter()
        subc_to_parents = collections.defaultdict(list)

        def store(subc_, parent_):
            subc_to_parent_count[subc_] += 1
            subc_to_parents[subc_].append(parent_)

        for parent in cond.subconditions:
            if isinstance(parent, toplevel_multi_subcond_cls):
                for subc in parent.subconditions:
                    store(subc, parent)
            else:
                # Note: here `parent` is *not* an instance of the class
                # `toplevel_multi_subcond_cls` (which is either `AndCond`
                # or `OrCond`), so we store it *as its own parent* --
                # as if it were *the only subcondition* of an imaginary
                # `toplevel_multi_subcond_cls` instance (note that such
                # an instance cannot be constructed, as the `AndCond`'s
                # and `OrCond`'s constructors, if only one subcondition
                # is given, return -- directly -- that subcondition).
                store(parent, parent)

        return subc_to_parent_count, subc_to_parents


class CondEqualityMergingTransformer(CondTransformer[Cond]):

    """
    A visitor class to apply to given conditions (recursively)
    a transformation, the essence of which is:

    * to gather, from among subconditions of a *disjunction* (i.e.,
      of a condition represented by an `OrCond` object), any *related
      equality tests conditions* (i.e., `... == ...` as well as
      `... IN ...` conditions, represented by `EqualCond`/`InCond`
      objects whose `rec_key`s are equal), and then replace them
      with one logically equivalent `... IN ...` condition (represented
      by an `InCond`)

    as well as

    * to gather, from among subconditions of a *conjunction* (i.e.,
      of a condition represented by an `AndCond` object), any *related
      negated equality tests conditions* (i.e., `NOT (... == ...)` as
      well as `NOT (... IN ...)`, represented by `EqualCond`/`InCond`
      objects whose `rec_key`s are equal, each wrapped in a `NotCond`),
      and then replace them with one logically equivalent `NOT (... IN
      ...)` condition (represented by an `InCond` wrapped in a `NotCond`)

    -- that is, to perform such transformations as, for example:

    * `(x==a) OR (x IN (b,c,d)) OR (x==c)` -> `x IN (a,b,c,d)`
    * `NOT (x==a) AND NOT (x IN (b,c,d)) AND NOT (x==c)` -> `NOT (x IN (a,b,c,d))`

    It is important that the output is always *logically equivalent* to
    the input.

    Let the examples speak...

    >>> with_eq_merged = CondEqualityMergingTransformer()
    >>> b = CondBuilder()
    >>> c1 = b.or_(
    ...     b['asn'] == 1,
    ...     b['asn'].in_([7, 5, 3]),
    ...     b['asn'] == 5,
    ...     b['asn'] == 2,
    ...     b['asn'].in_([2, 13, 11]),
    ... )
    >>> repr(c1) == (
    ...     "<OrCond: "
    ...         "<EqualCond: 'asn', 1>, "
    ...         "<InCond: 'asn', {7, 5, 3}>, "
    ...         "<EqualCond: 'asn', 5>, "
    ...         "<EqualCond: 'asn', 2>, "
    ...         "<InCond: 'asn', {2, 13, 11}>>")
    True
    >>> repr(with_eq_merged(c1)) == (
    ...     "<InCond: 'asn', {1, 7, 5, 3, 2, 13, 11}>")
    True

    As you can see, the order of subconditions is kept as far as
    possible, and the order of their operand values is also kept,
    except that any duplicates are omitted.

    >>> c1_alt = b.or_(
    ...     b['asn'] == 1,
    ...     b.not_(
    ...         b.and_(
    ...             b.not_(
    ...                 b['asn'].in_([7, 5, 3]),
    ...             ),
    ...             b.not_(
    ...                 b['asn'] == 5.0,
    ...             ),
    ...         ),
    ...     ),
    ...     b['asn'] == 2,
    ...     b['asn'].in_([2, 13, 11]),
    ... )
    >>> repr(c1_alt) == (
    ...     "<OrCond: "
    ...         "<EqualCond: 'asn', 1>, "
    ...         "<NotCond: "
    ...             "<AndCond: "
    ...                 "<NotCond: "
    ...                     "<InCond: 'asn', {7, 5, 3}>>, "
    ...                 "<NotCond: "
    ...                     "<EqualCond: 'asn', 5.0>>>>, "
    ...         "<EqualCond: 'asn', 2>, "
    ...         "<InCond: 'asn', {2, 13, 11}>>")
    True
    >>> repr(with_eq_merged(c1_alt)) == (
    ...     "<InCond: 'asn', {1, 7, 5, 3, 2, 13, 11}>")
    True

    Note that duplicate values are detected using `dict`/`set`-like
    containment tests -- so (as in other parts of this module where
    values are compared) *equality* of the values is the deciding
    factor, *not* their types:

    >>> c2 = b.and_(
    ...     b.not_(
    ...         b['asn'].in_([7.0, 5.0, 3.0]),
    ...     ),
    ...     b.not_(
    ...         b['asn'] == 1+0j,
    ...     ),
    ...     b.not_(
    ...         b['asn'] == 5,                  # (`5` does duplicate the earlier `5.0`)
    ...     ),
    ...     b.not_(
    ...         b['asn'].in_([2, 13, 1, 11]),   # (`1` does duplicate the earlier `1+0j`)
    ...     ),
    ...     b.not_(
    ...         b['asn'] == 2.0,                # (`2.0` does duplicate the earlier `2`)
    ...     ),
    ... )
    >>> repr(c2) == (
    ...     "<AndCond: "
    ...         "<NotCond: "
    ...             "<InCond: 'asn', {7.0, 5.0, 3.0}>>, "
    ...         "<NotCond: "
    ...             "<EqualCond: 'asn', (1+0j)>>, "
    ...         "<NotCond: "
    ...             "<EqualCond: 'asn', 5>>, "
    ...         "<NotCond: "
    ...             "<InCond: 'asn', {2, 13, 1, 11}>>, "
    ...         "<NotCond: "
    ...             "<EqualCond: 'asn', 2.0>>>")
    True
    >>> repr(with_eq_merged(c2)) == (
    ...     "<NotCond: "
    ...         "<InCond: 'asn', {7.0, 5.0, 3.0, (1+0j), 2, 13, 11}>>")
    True

    You may be surprised how even deep structures can be flattened (as
    a result of combining the transformation made by this visitor with
    the standard reductions/adjustments specific to compound condition
    classes):

    >>> c3 = b.and_(
    ...     b.not_(
    ...         b['cc'] == 'UK',
    ...     ),
    ...     b.not_(
    ...         b['cc'].in_(['US', 'FR']),
    ...     ),
    ...     b.not_(
    ...         b.or_(
    ...             b['cc'].in_(['PL', 'UA']),
    ...             b.not_(
    ...                 b.and_(
    ...                     b.not_(
    ...                         b['cc'].in_(['JP', 'PL']),
    ...                     ),
    ...                     b.not_(
    ...                         b['cc'] == 'CZ',
    ...                     ),
    ...                     b.not_(
    ...                         b.or_(
    ...                             b.not_(
    ...                                 b.and_(
    ...                                     b.not_(
    ...                                         b['cc'] == 'ST',
    ...                                     ),
    ...                                     b.not_(
    ...                                         b['cc'].in_(['SN', 'SI', 'SG']),
    ...                                     ),
    ...                                     b.not_(
    ...                                         b['cc'] == 'SK',
    ...                                     ),
    ...                                 ),
    ...                             ),
    ...                             b['cc'] == 'SK',
    ...                             b['cc'] == 'SE',
    ...                         ),
    ...                     ),
    ...                 ),
    ...             ),
    ...             b['cc'] == 'DE',
    ...         ),
    ...     ),
    ... )
    >>> repr(c3) == (
    ...     "<AndCond: "
    ...         "<NotCond: "
    ...             "<EqualCond: 'cc', 'UK'>>, "
    ...         "<NotCond: "
    ...             "<InCond: 'cc', {'US', 'FR'}>>, "
    ...         "<NotCond: "
    ...             "<OrCond: "
    ...                 "<InCond: 'cc', {'PL', 'UA'}>, "
    ...                 "<NotCond: "
    ...                     "<AndCond: "
    ...                         "<NotCond: "
    ...                             "<InCond: 'cc', {'JP', 'PL'}>>, "
    ...                         "<NotCond: "
    ...                             "<EqualCond: 'cc', 'CZ'>>, "
    ...                         "<NotCond: "
    ...                             "<OrCond: "
    ...                                 "<NotCond: "
    ...                                     "<AndCond: "
    ...                                         "<NotCond: "
    ...                                             "<EqualCond: 'cc', 'ST'>>, "
    ...                                         "<NotCond: "
    ...                                             "<InCond: 'cc', {'SN', 'SI', 'SG'}>>, "
    ...                                         "<NotCond: "
    ...                                             "<EqualCond: 'cc', 'SK'>>>>, "
    ...                                 "<EqualCond: 'cc', 'SK'>, "
    ...                                 "<EqualCond: 'cc', 'SE'>>>>>, "
    ...                 "<EqualCond: 'cc', 'DE'>>>>")
    True
    >>> repr(with_eq_merged(c3)) == (
    ...     "<NotCond: "
    ...         "<InCond: 'cc', {'UK', 'US', 'FR', 'PL', 'UA', 'JP', 'CZ', "
    ...                         "'ST', 'SN', 'SI', 'SG', 'SK', 'SE', 'DE'}>>")
    True

    Also, note that merging will be performed without any problem even
    if same-`rec_key` mergeable conditions are intermixed with some other
    conditions (maybe of non-mergeable kinds; or maybe of mergeable kinds
    but having other `rec_key` values -- these, obviously, will also be
    merged, separately per each same-`rec_key` set of them...):

    >>> c4 = b.or_(
    ...     b['asn'] == 1.0,
    ...     b['ip'].is_null(),  # (not mergeable at all)
    ...     b['ignored'].is_true(),  # (not mergeable at all)
    ...     b['cc'].in_(['FR', 'UA', 'PL', 'UK']),
    ...     b['asn'].in_([7, 5, 3]),
    ...     b.and_(  # (not mergeable with its parent's subconditions)
    ...         b.not_(
    ...             b['asn'].is_null(),  # (not mergeable at all)
    ...         ),
    ...         b.not_(
    ...             b['cc'] == 'UK',
    ...         ),
    ...         b.not_(
    ...             b.or_(
    ...                 b['cc'].in_(['PL', 'UA']),
    ...                 b['cc'] == 'DE',
    ...             ),
    ...         ),
    ...         b.not_(  # (mergeable but it's the only one with rec_key='count')
    ...             b['count'] == 777777,
    ...         ),
    ...         b.not_(
    ...             b['asn'] == 1.0,
    ...         ),
    ...         b.or_(  # (not mergeable with its parent's subconditions)
    ...             b['asn'].in_([2, 222, 22]),
    ...             b['asn'].in_([222, 2222, 2]),
    ...         ),
    ...         b.not_(
    ...             b['asn'].in_([7, 5, 3]),
    ...         ),
    ...         b['asn'] == 987654321,  # (not mergeable with its parent's subconditions)
    ...         b.not_(  # (not mergeable with its parent's subconditions)
    ...             b.and_(
    ...                 b.not_(
    ...                     b['asn'] == 1,
    ...                 ),
    ...                 b.not_(
    ...                     b['asn'] == 42,
    ...                 ),
    ...             ),
    ...         ),
    ...         b.not_(
    ...             b['asn'] == 5.0,
    ...         ),
    ...         b.not_(
    ...             b['asn'] == 2.0,
    ...         ),
    ...         b.not_(
    ...             b['asn'].in_([2, 13, 11]),
    ...         ),
    ...         b['asn'].in_([17, 18, 19]),  # (not mergeable with its parent's subconditions)
    ...         b.not_(
    ...             b['cc'].in_(['US', 'FR']),
    ...         ),
    ...         b['alamakota'].is_null(),  # (not mergeable at all)
    ...         b.not_(
    ...             b['asn'].in_([-3, -7, -1, 5, 4, 3, 2, 1]),
    ...         ),
    ...         b.not_(
    ...             b['asn'].in_(range(12)),
    ...         ),
    ...     ),
    ...     b['cc'].in_(['US', 'UK', 'UA', 'UG']),
    ...     b['cc'].between('AA', 'CZ'),  # (not mergeable at all)
    ...     b['asn'] == 5+0j,
    ...     b['asn'] == 2+0j,
    ...     b['asn'].is_null(),  # (not mergeable at all)
    ...     b.not_(
    ...         b.and_(
    ...             b.not_(
    ...                 b['asn'] == 1,
    ...             ),
    ...             b.not_(
    ...                 b['asn'] == 42,
    ...             ),
    ...         ),
    ...     ),
    ...     b['asn'].in_(range(3)),
    ...     b['asn'] <= -999999,  # (not mergeable at all)
    ...     b.not_(  # (not mergeable with its parent's subconditions)
    ...         b.or_(
    ...             b['asn'].in_([2, 222, 22]),
    ...             b['asn'].in_([222, 2222, 2]),
    ...         ),
    ...     ),
    ...     b.not_(  # (not mergeable with its parent's subconditions)
    ...         b['asn'].in_(range(12)),
    ...     ),
    ...     b['name'].contains_substring('Dr D., boli cię oko?'),  # (not mergeable at all)
    ...     b['cc'] == 'DE',
    ...     b['asn'].in_([2, 13, 11]),
    ...     b['count'].in_([77, 88, 99]),  # (mergeable but it's the only one with rec_key='count')
    ...     b['cc'] == 'FL',
    ...     b['asn'] >= 999999,  # (not mergeable at all)
    ... )
    >>> repr_c4 = repr(c4)
    >>> repr_c4 == (
    ...     "<OrCond: "
    ...         "<EqualCond: 'asn', 1.0>, "
    ...         "<IsNullCond: 'ip'>, "
    ...         "<IsTrueCond: 'ignored'>, "
    ...         "<InCond: 'cc', {'FR', 'UA', 'PL', 'UK'}>, "
    ...         "<InCond: 'asn', {7, 5, 3}>, "
    ...         "<AndCond: "
    ...             "<NotCond: "
    ...                 "<IsNullCond: 'asn'>>, "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'cc', 'UK'>>, "
    ...             "<NotCond: "
    ...                 "<OrCond: "
    ...                     "<InCond: 'cc', {'PL', 'UA'}>, "
    ...                     "<EqualCond: 'cc', 'DE'>>>, "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'count', 777777>>, "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'asn', 1.0>>, "
    ...             "<OrCond: "
    ...                 "<InCond: 'asn', {2, 222, 22}>, "
    ...                 "<InCond: 'asn', {222, 2222, 2}>>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'asn', {7, 5, 3}>>, "
    ...             "<EqualCond: 'asn', 987654321>, "
    ...             "<NotCond: "
    ...                 "<AndCond: "
    ...                     "<NotCond: "
    ...                         "<EqualCond: 'asn', 1>>, "
    ...                     "<NotCond: "
    ...                         "<EqualCond: 'asn', 42>>>>, "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'asn', 5.0>>, "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'asn', 2.0>>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'asn', {2, 13, 11}>>, "
    ...             "<InCond: 'asn', {17, 18, 19}>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'cc', {'US', 'FR'}>>, "
    ...             "<IsNullCond: 'alamakota'>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'asn', {-3, -7, -1, 5, 4, 3, 2, 1}>>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'asn', {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}>>>, "
    ...         "<InCond: 'cc', {'US', 'UK', 'UA', 'UG'}>, "
    ...         "<BetweenCond: 'cc', ('AA', 'CZ')>, "
    ...         "<EqualCond: 'asn', (5+0j)>, "
    ...         "<EqualCond: 'asn', (2+0j)>, "
    ...         "<IsNullCond: 'asn'>, "
    ...         "<NotCond: "
    ...             "<AndCond: "
    ...                 "<NotCond: "
    ...                     "<EqualCond: 'asn', 1>>, "
    ...                 "<NotCond: "
    ...                     "<EqualCond: 'asn', 42>>>>, "
    ...         "<InCond: 'asn', {0, 1, 2}>, "
    ...         "<LessOrEqualCond: 'asn', -999999>, "
    ...         "<NotCond: "
    ...             "<OrCond: "
    ...                 "<InCond: 'asn', {2, 222, 22}>, "
    ...                 "<InCond: 'asn', {222, 2222, 2}>>>, "
    ...         "<NotCond: "
    ...             "<InCond: 'asn', {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}>>, "
    ...         "<ContainsSubstringCond: 'name', 'Dr D., boli cię oko?'>, "
    ...         "<EqualCond: 'cc', 'DE'>, "
    ...         "<InCond: 'asn', {2, 13, 11}>, "
    ...         "<InCond: 'count', {77, 88, 99}>, "
    ...         "<EqualCond: 'cc', 'FL'>, "
    ...         "<GreaterOrEqualCond: 'asn', 999999>>")
    True
    >>> repr(with_eq_merged(c4)) == (
    ...     "<OrCond: "
    ...         "<InCond: 'asn', {1.0, 7, 5, 3, (2+0j), 42, 0, 13, 11}>, "             # (merged)
    ...         "<IsNullCond: 'ip'>, "
    ...         "<IsTrueCond: 'ignored'>, "
    ...         "<InCond: 'cc', {'FR', 'UA', 'PL', 'UK', 'US', 'UG', 'DE', 'FL'}>, "   # (merged)
    ...         "<AndCond: "
    ...             "<NotCond: "
    ...                 "<IsNullCond: 'asn'>>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'cc', {'UK', 'PL', 'UA', 'DE', 'US', 'FR'}>>, "      # (merged)
    ...             "<NotCond: "
    ...                 "<EqualCond: 'count', 777777>>, "
    ...             "<NotCond: "
    ...                 "<InCond: 'asn', "                                             # (merged)
    ...                           "{1.0, 7, 5, 3, 2.0, 13, 11, -3, -7, -1, 4, 0, 6, 8, 9, 10}>>, "
    ...             "<InCond: 'asn', {2, 222, 22, 2222}>, "      # (merged locally)
    ...             "<EqualCond: 'asn', 987654321>, "
    ...             "<InCond: 'asn', {1, 42}>, "                 # (merged locally)
    ...             "<InCond: 'asn', {17, 18, 19}>, "
    ...             "<IsNullCond: 'alamakota'>>, "
    ...         "<BetweenCond: 'cc', ('AA', 'CZ')>, "
    ...         "<IsNullCond: 'asn'>, "
    ...         "<LessOrEqualCond: 'asn', -999999>, "
    ...         "<NotCond: "
    ...             "<InCond: 'asn', {2, 222, 22, 2222}>>, "     # (merged locally)
    ...         "<NotCond: "
    ...             "<InCond: 'asn', {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}>>, "
    ...         "<ContainsSubstringCond: 'name', 'Dr D., boli cię oko?'>, "
    ...         "<InCond: 'count', {77, 88, 99}>, "
    ...         "<GreaterOrEqualCond: 'asn', 999999>>")
    True

    Obviously, the original condition object is never modified:

    >>> repr(c4) == repr_c4
    True
    """

    def __visit_impl(self, cond: Union[AndCond, OrCond]) -> Cond:
        assert isinstance(cond, (AndCond, OrCond))
        cond = self.subvisit(cond)

        if isinstance(cond, (AndCond, OrCond)):
            subcond_merger = self._SubcondMerger(self, cond)
            if subcond_merger.is_anything_to_merge():
                return self.make_cond(
                    cond.__class__,
                    subcond_merger.generate_subconditions())

        return cond

    visit_AndCond = __visit_impl
    visit_OrCond = __visit_impl


    class _SubcondMerger:

        #
        # Internal static typing aliases and hints

        _Value = Hashable
        _ValueSeq = Sequence[_Value]
        _RecKeyAndValueSeq = tuple[str, _ValueSeq]
        _RecKeyAndValueSeqGetter = Callable[[Cond], Optional[_RecKeyAndValueSeq]]

        _visitor: 'CondEqualityMergingTransformer'
        _cond: Union[AndCond, OrCond]
        _concerned_subconds_are_negated: bool
        _rec_key_and_value_seq_getter: _RecKeyAndValueSeqGetter
        _mergeable_subcond_to_rec_key: Mapping[Cond, str]
        _rec_key_to_value_seqs: Mapping[
            str,
            Sequence[_ValueSeq]]   # (<- sequence of *per-subcondition sequences of values*)

        #
        # Initialization

        def __init__(self,
                     visitor: 'CondEqualityMergingTransformer',
                     cond: Union[AndCond, OrCond]):

            self._visitor = visitor
            self._cond = cond

            (self._concerned_subconds_are_negated,
             self._rec_key_and_value_seq_getter) = self._determine_concerned_subconds_specifics()

            (self._mergeable_subcond_to_rec_key,
             self._rec_key_to_value_seqs) = self._gather_mergeable_subconds_data()

        def _determine_concerned_subconds_specifics(self) -> tuple[bool, _RecKeyAndValueSeqGetter]:
            # The kind of any concerned subconditions (those mergeable
            # and those being direct results of merging) depends on the
            # type of the parent condition -- whether it is `AND` or `OR`:
            assert isinstance(self._cond, (AndCond, OrCond))
            if isinstance(self._cond, AndCond):
                # * *negated* if the parent is `AND` -- for example:
                #   `NOT (x==a) AND NOT (x IN (b,c,d)) AND NOT (x==c)` -> `NOT (x IN (a,b,c,d))`
                concerned_subconds_are_negated = True
                rec_key_and_value_seq_getter = self._get_rec_key_and_value_seq_from_negated
            else:
                # * *plain* (not negated) if the parent is `OR` -- for example:
                #   `(x==a) OR (x IN (b,c,d)) OR (x==c)` -> `x IN (a,b,c,d)`
                concerned_subconds_are_negated = False
                rec_key_and_value_seq_getter = self._get_rec_key_and_value_seq_from_plain
            return concerned_subconds_are_negated, rec_key_and_value_seq_getter

        @classmethod
        def _get_rec_key_and_value_seq_from_negated(cls, c: Cond) -> Optional[_RecKeyAndValueSeq]:
            if isinstance(c, NotCond):
                return cls._get_rec_key_and_value_seq_from_plain(c.subcond)
            return None

        @staticmethod
        def _get_rec_key_and_value_seq_from_plain(c: Cond) -> Optional[_RecKeyAndValueSeq]:
            if isinstance(c, EqualCond):
                return c.rec_key, (c.op_param,)
            if isinstance(c, InCond):
                return c.rec_key, tuple(c.op_param)
            return None

        def _gather_mergeable_subconds_data(self) -> tuple[Mapping[Cond, str],
                                                           Mapping[str, Sequence[_ValueSeq]]]:
            mergeable_subcond_to_rec_key = dict[Cond, str]()
            rec_key_to_value_seqs = collections.defaultdict[str](list)
            for subcond in self._cond.subconditions:
                if got := self._rec_key_and_value_seq_getter(subcond):
                    rec_key, value_seq = got
                    mergeable_subcond_to_rec_key[subcond] = rec_key
                    rec_key_to_value_seqs[rec_key].append(value_seq)
            return mergeable_subcond_to_rec_key, rec_key_to_value_seqs

        #
        # Instance interface

        def is_anything_to_merge(self) -> bool:
            if self._rec_key_to_value_seqs:
                mergeable_subcond_counts = map(len, self._rec_key_to_value_seqs.values())
                return max(mergeable_subcond_counts) > 1
            return False

        def generate_subconditions(self) -> Iterator[Cond]:
            rec_key_to_collected_values: dict[str, OPSet] = {
                rec_key: self._collect_values(value_seqs)
                for rec_key, value_seqs in self._rec_key_to_value_seqs.items()}

            for subcond in self._cond.subconditions:
                rec_key = self._mergeable_subcond_to_rec_key.get(subcond)
                if rec_key is not None:
                    collected_values = rec_key_to_collected_values.pop(rec_key, None)
                    if collected_values is not None:
                        yield self._make_merged_subcond(rec_key, collected_values)
                else:
                    yield subcond

            assert not rec_key_to_collected_values

        def _collect_values(self, value_seqs: Sequence[_ValueSeq]) -> OPSet:
            return OPSet(itertools.chain.from_iterable(value_seqs))

        def _make_merged_subcond(self, rec_key: str, collected_values: OPSet) -> Cond:
            new_subcond = self._visitor.make_cond(InCond, rec_key, collected_values)
            if self._concerned_subconds_are_negated:
                new_subcond = self._visitor.make_cond(NotCond, new_subcond)
            return new_subcond


class CondDeMorganTransformer(CondTransformer[Cond]):

    """
    A visitor class to apply to given conditions (recursively) the
    following transformations based on De Morgan's laws:

    * `NOT (a AND b AND c AND...)` -> (NOT a) OR (NOT b) OR (NOT c) OR...`
    * `NOT (a OR b OR c OR...)` -> (NOT a) AND (NOT b) AND (NOT c) AND...`

    See: https://en.wikipedia.org/wiki/De_Morgan%27s_laws

    It is important that the output is always *logically equivalent* to
    the input.

    Let the examples speak...

    >>> de_morgan = CondDeMorganTransformer()
    >>> b = CondBuilder()
    >>> c1 = b.not_(
    ...     b.and_(
    ...         b['count'] > 0,
    ...         b['count'] <= 42,
    ...     ),
    ... )
    >>> repr(c1) == (
    ...     "<NotCond: "
    ...         "<AndCond: "
    ...             "<GreaterCond: 'count', 0>, "
    ...             "<LessOrEqualCond: 'count', 42>>>")
    True
    >>> repr(de_morgan(c1)) == (
    ...     "<OrCond: "
    ...         "<NotCond: "
    ...             "<GreaterCond: 'count', 0>>, "
    ...         "<NotCond: "
    ...             "<LessOrEqualCond: 'count', 42>>>")
    True
    >>> c2 = b.not_(
    ...     b.or_(
    ...         b['count'] < 128,
    ...         b['count'] >= 256,
    ...     ),
    ... )
    >>> repr(c2) == (
    ...     "<NotCond: "
    ...         "<OrCond: "
    ...             "<LessCond: 'count', 128>, "
    ...             "<GreaterOrEqualCond: 'count', 256>>>")
    True
    >>> repr(de_morgan(c2)) == (
    ...     "<AndCond: "
    ...         "<NotCond: "
    ...             "<LessCond: 'count', 128>>, "
    ...         "<NotCond: "
    ...             "<GreaterOrEqualCond: 'count', 256>>>")
    True

    Note that, in the final result, every `NOT` condition (represented
    by a `NotCond`) is the parent of a *leaf* (non-*compound*) condition
    (i.e., the `NotCond`'s `subcond` is always an instance of a concrete
    subclass of `RecItemCond`, never of `CompoundCond`).

    >>> c3 = b.not_(
    ...     b.or_(
    ...         b.not_(
    ...             b['asn'] == 12345,
    ...         ),
    ...         b.not_(
    ...             b.and_(
    ...                 b['cc'].in_(['PL', 'FR', 'EN']),
    ...                 b['asn'] == 12345,
    ...             ),
    ...         ),
    ...         b['url'].is_null(),
    ...         b['ignored'].is_true(),
    ...         b.and_(
    ...             b['fqdn'] == 'example.org',
    ...             b['ip'].between('1.2.3.0', '1.2.3.255'),
    ...         ),
    ...         b.not_(
    ...             b.or_(
    ...                 b['url'] == 'https://example.org',
    ...                 b['ip'].between('1.2.3.0', '1.2.3.255'),
    ...             ),
    ...         ),
    ...     ),
    ... )
    >>> repr_c3 = repr(c3)
    >>> repr_c3 == (
    ...     "<NotCond: "
    ...         "<OrCond: "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'asn', 12345>>, "
    ...             "<NotCond: "
    ...                 "<AndCond: "
    ...                     "<InCond: 'cc', {'PL', 'FR', 'EN'}>, "
    ...                     "<EqualCond: 'asn', 12345>>>, "
    ...             "<IsNullCond: 'url'>, "
    ...             "<IsTrueCond: 'ignored'>, "
    ...             "<AndCond: "
    ...                 "<EqualCond: 'fqdn', 'example.org'>, "
    ...                 "<BetweenCond: 'ip', ('1.2.3.0', '1.2.3.255')>>, "
    ...             "<NotCond: "
    ...                 "<OrCond: "
    ...                     "<EqualCond: 'url', 'https://example.org'>, "
    ...                     "<BetweenCond: 'ip', ('1.2.3.0', '1.2.3.255')>>>>>")
    True
    >>> repr(de_morgan(c3)) == (
    ...     "<AndCond: "
    ...         "<EqualCond: 'asn', 12345>, "
    ...         "<InCond: 'cc', {'PL', 'FR', 'EN'}>, "
    ...         "<NotCond: "
    ...             "<IsNullCond: 'url'>>, "
    ...         "<NotCond: "
    ...             "<IsTrueCond: 'ignored'>>, "
    ...         "<OrCond: "
    ...             "<NotCond: "
    ...                 "<EqualCond: 'fqdn', 'example.org'>>, "
    ...             "<NotCond: "
    ...                 "<BetweenCond: 'ip', ('1.2.3.0', '1.2.3.255')>>>, "
    ...         "<OrCond: "
    ...             "<EqualCond: 'url', 'https://example.org'>, "
    ...             "<BetweenCond: 'ip', ('1.2.3.0', '1.2.3.255')>>>")
    True

    Obviously, the original condition object is never modified:

    >>> repr(c3) == repr_c3
    True

    ***

    If you ever implement a new compound condition class or any
    non-compound condition class not derived from `RecItemCond`,
    and you want to make `CondDeMorganTransformer` support it,
    you will need to enhance appropriately the implementation
    of `CondDeMorganTransformer.visit_NotCond()`.

    >>> class XYCond(Cond):
    ...     def _adapt_init_args(*_): return ()
    ...     def __init__(self): pass
    ...
    >>> de_morgan(b.not_(XYCond._make()))
    Traceback (most recent call last):
      ...
    NotImplementedError: CondDeMorganTransformer.visit_NotCond() does not support negated XYCond
    """

    def visit_NotCond(self, cond: NotCond) -> Cond:                      # noqa
        subcond = cond.subcond
        assert not isinstance(subcond, NotCond)   # (`NotCond` guarantees that)

        if isinstance(subcond, (AndCond, OrCond)):
            new_cond = self._apply_de_morgan(cond)
            return self(new_cond)

        elif isinstance(subcond, CompoundCond) or not isinstance(subcond, RecItemCond):
            raise NotImplementedError(
                f'{self.__class__.__qualname__}.visit_NotCond() does not '
                f'support negated {subcond.__class__.__qualname__}')

        return self.subvisit(cond)


    def _apply_de_morgan(self, cond: NotCond) -> Cond:
        subcond = cond.subcond
        assert isinstance(subcond, (AndCond, OrCond))

        new_cond_cls = (
            # (the case of: `NOT (a AND b AND c AND...)` -> (NOT a) OR (NOT b) OR (NOT c) OR...`)
            OrCond if isinstance(subcond, AndCond)

            # (the case of: `NOT (a OR b OR c OR...)` -> (NOT a) AND (NOT b) AND (NOT c) AND...`)
            else AndCond)

        return self.make_cond(new_cond_cls, [
            self.make_cond(NotCond, subc)
            for subc in subcond.subconditions])


if __name__ == '__main__':
    from n6lib.unit_test_helpers import run_module_doctests
    run_module_doctests()

# Copyright (c) 2020-2021 NASK. All rights reserved.

"""
This submodule contains static typing stuff (defining several abstract
interfaces) used throughout the `n6lib.structured_data_conversion`
package (and, possibly, also in any modules that make use of the stuff
provided by the package).

Note: generally, the static typing stuff does *not* affect the runtime
semantics, in particular, does *not* provide runtime type checks.

TL;DR:

* read the *TL;DR* fragments of the docs of:

  `Converter`,
  `ConverterMaker`,
  `ConverterExtendedMaker`,
  `Cell`.

* take a look at the code of the definitions of:

  `Converter`,
  `ConverterMaker`,
  `ConverterExtendedMaker`
  `NamespaceItemConverter`,
  `NamespaceItemConverterMaker`,
  `NamespaceItemConverterExtendedMaker,
  and `Name`, `Value`, `NameValuePair`, `NameCellPair`.

***

The purpose of the static typing stuff is twofold:

* to provide a part of the code's (self-)documentation;
* to provide PEP-484/PEP-544-based type hints for external static
  analysis tools (such as [mypy](https://mypy.readthedocs.io) or
  those built into PyCharm...).

***

Here we need a note about the terminology we use in this package's
docs and comments when dealing with abstract interfaces, especially
those defined as duck-typed "protocols" (including `Converter`,
`NamespaceItemConverter`, `ConverterMaker`, `ConverterExtendedMaker`,
`Cell` etc.).

For some object 'x' and some abstract interface `Z`, the following
statements are equivalent to each other:

* "`x` is an (implicit) instance of `Z`",
* "`x` supports `Z`",
* "`x` is a `Z`",
* "`x` is `Z`-compliant",
* "`x` is a `Z`-compliant object",
* "`x` is (an object) compliant with `Z`",
* "the type/class of `x` is an (implicit) subtype/subclass of `Z`",
* "the type/class of `x` implements `Z`",
* "the type/class of `x` is an implementation of `Z`",
* "the type/class of `x` is a `Z`-compliant type/class",
* "the type/class of `x` is a type/class compliant with `Z`".

Note that the class of `x` does *not* have to be an *explicit* subclass
of `Z` (i.e., does *not* have to inherit from `Z`, whether directly or
indirectly).

***

Additional comment: in some definitions of abstract interfaces
(protocols) there are method parameters whose names start with `__`
(double underscore); as PEP-484 states, it means that the particular
parameter is *positional-only* (i.e., its value can be specified by
a caller only as a positional argument, not as a keyword one).
"""

from typing import (
    AbstractSet,        # TODO: use more modern counterpart...
    Any,
    Hashable,           # TODO: use more modern counterpart...
    Iterable,           # TODO: use more modern counterpart...
    Iterator,           # TODO: use more modern counterpart...
    Mapping,            # TODO: use more modern counterpart...
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)

from n6lib.typing_helpers import (
    KwargsDict,
    String,
)


#
# Interfaces/static types related to converted data
#

Value = Any

Name = String
NameOrIndex = Union[Name, int]

NameValuePair = Tuple[Name, Value]
NameCellPair = Tuple[Name, 'Cell']   # (`Cell` is defined below...)

NamespaceMappingOrIterable = Union[
    Mapping[Name, Value],
    Iterable[NameValuePair],
]


#
# Basic interfaces/static types of converters and their factories
#

_InValue_contra = TypeVar('_InValue_contra', contravariant=True)
_OutValue_co = TypeVar('_OutValue_co', covariant=True)

class Converter(Protocol[_InValue_contra, _OutValue_co]):

    """
    TL;DR: defines an abstract interface of an object that meets the
    following requirements:

    * is a callable that takes one argument;
    * returns an iterator that may yield some value(s);
    * is stateless and concurrency-safe (in particular, thread-safe).

    For example, a generator function that accepts one positional
    argument may be treated as a `Converter`-compliant object.

    Also, any *instances* of the classes defined in the `.converters`
    submodule will be `Converter`-compliant objects.

    For a longer description -- see below.

    ***

    An abstract interface (expressed as a duck-typed "protocol") that
    is fundamental to the matter the `n6lib.structured_data_conversion`
    package concerns: it defines a `Converter` as a callable that takes
    exactly one positional argument and returns an iterator that yields
    some number of objects (where "some number" may mean zero or any
    natural number; actual implementations can, at their discretion,
    restrict it to some particular number).

    An additional, **important**, expectation is that a `Converter` is
    a callable that is stateless and concurrency-safe, in the sense
    that it can be called multiple times and each call is independent
    of other calls -- whether of earlier ones, or later ones, or
    concurrent ones...

    Of course, such a broad definition would be hardly useful without
    other stuff defined in the package and, in particular, in this
    module... So, read on.

    ***

    Note: `.converters.BaseConverter` is a base class that provides a
    framework that makes implementing the `Converter` interface more
    convenient. It is, therefore, *possible but not required* that a
    `Converter`-compliant object is an instance of a subclass of
    `.converters.BaseConverter`.

    ***

    There is a specific `Converter` subtype -- whose static type alias
    is defined as `NamespaceItemConverter`. The `NamespaceItemConverter`
    interface restricts the `Converter`'s features in the following way:

    * its call argument must be a `(<a string>, <anything>)` tuple
      (note: there is a static type alias denoting such a tuple,
      defined in this module as `NameValuePair`);

    * its return value is restricted to be an iterator that yields some
      number of `(<a string>, <a `Cell`>)` tuples (note: there is a
      static type alias denoting such a tuple, defined as `NameCellPair`;
      see also the `Cell` abstract interface) -- where: "some number" is
      quite often just *one*, but it can, as well, be zero or any
      natural number.

    `NamespaceItemConverter`-compliant objects are needed as component
    converters (subconverters) owned by converters being instances of
    `.converters.BaseNamespaceConverter` subclasses.

    See also: the description of `NamespaceItemConverterMaker` in the
    docs of the `ConverterMaker` abstract interface.

    ***

    There is also, in the `.converters` module, a class that provides a
    basic framework that makes implementing the `NamespaceItemConverter`
    interface more convenient: the `BaseNameValuePairConverter` class
    (it is, therefore, *possible but not required* that a
    `NamespaceItemConverter`-compliant object is an instance
    of a concrete subclass of `BaseNameValuePairConverter`).

    Moreover, there is, also in the `.converters` module, a simple and
    convenient concrete subclass of `BaseNameValuePairConverter`:
    the `NameValuePairConverter` class.
    """

    def __call__(self, __data):
        # type: (_InValue_contra) -> Iterator[_OutValue_co]
        raise NotImplementedError


_Converter_co = TypeVar('_Converter_co', bound=Converter, covariant=True)

class ConverterMaker(Hashable, Protocol[_Converter_co]):

    """
    TL;DR: defines an abstract interface of an object that meets the
    following requirements:

    * is a callable that takes only (or none of) keyword arguments;
    * returns a `Converter`-compliant object;
    * is stateless and concurrency-safe (in particular, thread-safe);
    * can be used as a dict key.

    For example, a function that accepts certain keyword-only arguments
    (or no arguments at all) and returns a `Converter`-compliant object
    may be treated as a `ConverterMaker`-compliant object.

    Also, the *classes* defined in the `.converters` submodule are
    `ConverterMaker`-compliant objects.

    For a longer description -- see below.

    ***

    An abstract interface (expressed as a duck-typed "protocol") of
    such a callable that:

    * accepts only keyword-only arguments (here unconstrained, however
      classes implementing this protocol may impose some constraints on
      them -- in particular, that only some specific arguments are
      legal, and/or that some arguments are required, and/or that some
      arguments must be instances of some classes or be compliant with
      certain interfaces etc.); and

    * returns a `Converter`; and

    * is hashable and can be used (in itself) as a key in a `dict`.

    An additional, **important**, expectation is that a
    `ConverterMaker` is a stateless and concurrency-safe callable -- in
    the sense that it can be called multiple times and each call is
    independent of other calls -- whether of earlier ones, or later
    ones, or concurrent ones...

    ***

    Note that, in particular, any concrete *class* that is a properly
    implemented subclass of `BaseConverter` (see the `.converters`
    module) supports the `ConverterMaker` interface (i.e., is an
    implicit *instance* [sic!] of this interface).

    However, also note that a class that implements the `Converter`
    interface does *not* have to be a subclass of `BaseConverter` and
    does *not* have to be an (implicit) instance of `ConverterMaker`
    (i.e., does not have to define the `__init__()` method as compliant
    with the signature defined here) -- as **the `Converter` interface
    in itself does *not* say anything about converter constructors**
    (they are the domain of the `ConverterMaker` interface).

    Also, note that, for example, an argumentless lambda that returns
    a `Converter` (which may be, e.g., a generator function that takes
    one positional argument) may also be a `ConverterMaker`-compliant
    object.

    ***

    See also:

    * `ConverterExtendedMaker`.
    * `.converters.BaseConverter.make_subconverter()`.

    ***

    There is a specific case of a `ConverterMaker` subtype whose
    static type alias is defined as `NamespaceItemConverterMaker`.
    Its instances, when called, are expected to return
    `NamespaceItemConverter`-compliant objects.

    `NamespaceItemConverterMaker`-compliant makers are needed when
    specifying certain arguments passed to instance constructors
    provided by subclasses of `.converters.BaseNamespaceConverter`
    -- namely:

    * values in a mapping that is used as the value of the
      `input_name_to_item_converter_maker` argument;

    * an object used as the value of the `free_item_converter_maker`
      argument.

    See the docs of `.converters.BaseNamespaceConverter` and the
    signature of its `__init__()`.

    Also, see the description of `NamespaceItemConverter` in the docs
    of the `Converter` abstract interface.
    """

    def __call__(self, **maker_call_kwargs):
        # type: (...) -> _Converter_co
        raise NotImplementedError

class ConverterExtendedMaker(Hashable, Protocol[_Converter_co]):

    """
    TL;DR: defines an abstract interface of an object that:

    * is `ConverterMaker`-compliant;

    * has certain features (namely: the optional argument
      `subconverter_maker_to_kwargs`, the attribute
      `accept_kwargs_prescribed_for` and the `maker`() method) --
      related to building composite/nested converters.

    The *classes* defined in the `.converters` submodule are
    `ConverterExtendedMaker`-compliant objects.

    For a longer description -- see below.

    ***

    An abstract interface (expressed as a duck-typed "protocol") of
    such a callable that, apart from being a `ConverterMaker`-compliant
    object (as this interface is an implicit subtype of `ConverterMaker`),
    additionally satisfies the following requirements:

    * when called, accepts the `subconverter_maker_to_kwargs` optional
      keyword argument which can be either `None` or such a `Mapping`
      (e.g., a `dict`) that maps `ConverterMaker`-compliant objects
      (possibly, but not necessarily, `ConverterExtendedMaker`-compliant
      ones) to "kwargs-like" `dict`s (i.e., `dict`s whose keys are
      strings); and

    * has an `accept_kwargs_prescribed_for` attribute that is either
      set to `None` or to a `ConverterMaker`-compliant object (possibly,
      but not necessarily, a `ConverterExtendedMaker`-compliant one).

    * has a `maker()` method that:

      * takes some optional keyword-only arguments, below referred to
        as *maker-default-kwargs*, and

      * returns an object that:

        * is a `ConverterExtendedMaker`-compliant object;

        * when invoked, calls this (parent) maker, using each of
          *maker-default-kwargs* as the same-named keyword argument
          unless overridden by the corresponding keyword argument
          passed in to the invocation;

        * has the `accept_kwargs_prescribed_for` attribute set to
          this (parent) maker object

      (for example implementations of the `maker()` method -- see:
      `BaseConverter.maker()` and `BaseConverter._Maker.maker()`).

    ***

    Note that, in particular, any properly implemented concrete subclass
    of `.converters.BaseConverter` supports the `ConverterExtendedMaker`
    interface (i.e., is an implicit *instance* [sic!] of this interface);
    what, in particular, means that its `maker()` class method behaves
    according to the above specification of a `maker()` method.

    See also: `BaseConverter.make_subconverter()`.
    """

    @property
    def accept_kwargs_prescribed_for(self):
        # type: () -> Optional[ConverterMaker]
        raise NotImplementedError

    def __call__(
        self,
        *,
        subconverter_maker_to_kwargs=None,   # type: Optional[Mapping[ConverterMaker, KwargsDict]]
        **rest_maker_call_kwargs
    ):
        # type: (...) -> _Converter_co
        raise NotImplementedError

    def maker(self, **maker_creation_kwargs):
        # type: (...) -> ConverterExtendedMaker[_Converter_co]
        raise NotImplementedError


#
# Namespace-conversion-specific interfaces/static types
#

NamespaceItemConverter = Converter[NameValuePair, NameCellPair]

NamespaceItemConverterMaker = ConverterMaker[NamespaceItemConverter]
NamespaceItemConverterExtendedMaker = ConverterExtendedMaker[NamespaceItemConverter]


class Cell(Protocol):

    """
    TL;DR: A `Cell`-compliant object is a kind of value wrapper; such
    wrappers are used by the machinery of converters that deal with
    dicts or other mapping/namespace-like collections. Typically, you do
    *not* need to bother with the gory details of the `Cell` interface.

    For a longer description -- see below.

    ***

    An abstract interface (expressed as a duck-typed "protocol") of
    a specific kind of value wrapper.

    It is related to conversion of items of namespace-like collections
    (in particular, `dict`s) that is done by using instances of some
    `.converters.BaseNamespaceConverter` subclass (for example, the
    `.converters.NamespaceMappingConverter` class), in conjunction with
    some `NamespaceItemConverter`-compliant objects, in particular
    instances of `.converters.NameValuePairConverter` (or, e.g., of
    some custom subclasses of `.converters.BaseNameValuePairConverter`).

    ***

    Let us emphasize it: you do *not* need to know anything about the
    `Cell`-related details described below -- *as long as:*

    you do *not* create your own classes that implement the
    `NamespaceItemConverter` interface (e.g., your custom
    `BaseNameValuePairConverter` subclasses), and you only make use of
    the standard stuff related to the `input_name_to_item_converter_maker`
    and `free_item_converter_maker` arguments passed to instance
    constructors of `BaseNamespaceConverter` subclasses,

    i.e., you just make use, in a non-sophisticated manner, of the
    following stuff:

    * the `NameValuePairConverter` class (the standard concrete class
      which is an implicit instance of `NamespaceItemConverterMaker`
      and whose instances are `NamespaceItemConverter`-compliant),

    * and/or results of calls of `NameValuePairConverter.maker()` (or
      of calls of `maker()` on such results, possibly recursively...).

    ***

    On the other hand, if you want to make use of some advanced
    features of `NameValuePairConverter` (such as its constructor's
    argument `value_cell_factory`), or to implement your custom
    `NamespaceItemConverter`-compliant classes or `Cell`-compliant
    classes, or to delve into internals of `BaseNamespaceConverter`
    (in particular, into the stuff related to the abstract interface
    `NamespaceConversionStateBookkeeper`), then you should read the
    description below (as well as the pieces of the docs and the code
    it refers to).

    ***

    `Cell` is an interface of such a data wrapper that:

    * (I) keeps (wraps) some actual value object(s),

      cardinality of whom -- i.e., how many values can be kept by such
      a wrapper -- depends on the concrete wrapper type (see the docs
      of the `namespace_conversion_helpers` module...);

      and

    * (II) implements the `+` operator

      -- as an action that can be described as: *merge me with another
      `Cell`-compliant object* (always in a read-only manner, i.e.,
      *not* mutating any existing objects but, if necessary, creating
      new ones); the exact semantics of that action depends on the
      concrete wrapper type (see the docs of the
      `namespace_conversion_helpers` module...);

      and

    * (III) has the `output` attribute

      -- that provides the kept value object(s) in an "unwrapped" form;
      the exact semantics of that "unwrapping" and the type of the
      provided object depends on the concrete wrapper type (see the
      docs of the `namespace_conversion_helpers` module...);

      *important note*: you should *never* try to set a new value of the
      `output` attribute, even if no mechanism prevents you from doing
      that; generally, a `Cell`-compliant object, after it has been
      created, should always be treated as a read-only object;

      also, *mutating* the object provided by the `output` attribute
      *may not* be a good idea if there is a chance that the particular
      `Cell`-compliant object will be re-used later (at least, from the
      point of view of the *defensive programming* approach...).

    `Cell`-compliant objects are produced by the machinery of the
    `BaseNameValuePairConverter`/`NameValuePairConverter` classes, and
    then are consumed by the internals of `BaseNamespaceConverter` or
    of its subclasses. They take part in resolving the *scalar* item
    vs. *collection* item distinction (discussed in the documentation
    of `BaseNameValuePairConverter`).

    ***

    There are standard implementations of the `Cell` interface, defined
    in the `namespace_conversion_helpers` module -- see its docs.

    ***

    See also the docs (if any) and the code of:

    * the `namespace_conversion_helpers` module, in particular the
      `PlainCell`, `MultiCell` and `StemCell` classes defined in that
      module,
    * the `NamespaceItemConverter` interface (documented in the docs
      of the `Converter` interface, as its subtype),
    * the `.converters.BaseNameValuePairConverter` base class
      (which provides a basic framework that makes implementing
      `NamespaceItemConverter` more convenient),
    * the `.converters.NameValuePairConverter` class (which is a simple
      concrete subclass of `BaseNameValuePairConverter`),
    * the `.converters.BaseNamespaceConverter` base class (and its
      concrete subclasses...),
    * the `NamespaceConversionStateBookkeeper` abstract interface
      defined here and the `StandardNamespaceConversionStateBookkeeper`
      concrete class defined in the `namespace_conversion_helpers`
      module.
    """

    @property
    def output(self):
        # type: () -> Value
        raise NotImplementedError

    def __add__(self, __other):
        # type: (Cell) -> Cell
        raise NotImplementedError

    def __radd__(self, __other):
        # type: (Cell) -> Cell
        raise NotImplementedError


class NamespaceConversionStateBookkeeper(Protocol):

    """
    TL;DR: advanced topic, typically you do *not* need to bother with it
    at all.

    ***

    An abstract interface (expressed as a duck-typed "protocol") of
    a special stateful object -- a *conversion state bookkeeper* --
    that is used within the implementation of the
    `.converters.BaseNamespaceConverter.__call__()` method.

    The main rationale for having *conversion state bookkeeper*
    objects, separate from namespace converters that use them, is that
    thanks to such a stateful object (created separately within each
    call of a namespace converter, and intended to exist not longer
    than the lifetime of the iterator/generator produced by that call)
    the namespace converter is relieved from maintaining any mutable
    state by itself (which would be troublesome, given the stateless
    nature of converters).

    ***

    As noted above, typically you do not need to deal with this
    interface (at least not directly). In supposedly very rare cases
    that you really do, please study the code of this interface, as
    well as the code of other related stuff (especially:
    `.namespace_conversion_helpers.StandardNamespaceConversionStateBookkeeper`
    and `.converters.BaseNamespaceConverter.__call__()`) -- as this
    advanced topic is rather scarcely documented (at least for now).
    """

    def preprocess_input_items(self, input_name_value_pairs):
        # type: (Iterable[NameValuePair]) -> Iterable[NameValuePair]
        raise NotImplementedError

    def collect_converted_item(self, input_name, output_name, converted_value_cell):
        # type: (Name, Name, Cell) -> None
        raise NotImplementedError

    def verify_required_input_items_collected(self, required_input_names):
        # type: (AbstractSet) -> None
        raise NotImplementedError

    def generate_output_items(self):
        # type: () -> Iterator[NameValuePair]
        raise NotImplementedError

    def iter_input_names_for_output_name(self, output_name):
        # type: (String) -> Iterator[String]
        raise NotImplementedError

# Copyright (c) 2020-2021 NASK. All rights reserved.

"""
This submodule contains the standard concrete classes implementing the
following interfaces related to the internals of `BaseNamespaceConverter`
(and/or to some advanced ways of customization of its usage):

* `.interfaces.Cell`,
* `.interfaces.NamespaceConversionStateBookkeeper`.

***

The following three standard implementations of the `Cell` interface
are provided: `PlainCell`, `MultiCell` and `StemCell`.

Their `Cell`-specific features (see the docs of `Cell`) are implemented
as follows:

* (I) when it comes to the cardinality of wrapped values (i.e., how many
  of them can be kept by an instance of the particular implementation of
  `Cell`):

  * a `PlainCell` always keeps exactly one value;

  * a `MultiCell` can keep any number of values;

  * a `StemCell` does never keep any value (typically, it acts as a
    "stem" of the actual cell that is supposed to be created later;
    it is used by some `BaseNamespaceConverter`'s internals...);

* (II) when it comes to the `+` operator's semantics:

  * a `PlainCell` just prevents merging it with any `Cell` -- by
    raising `DataConversionError('data duplication detected')`
    -- unless the type of that other one is `StemCell` (then the
    result is just the `PlainCell` instance intact);

  * a `MultiCell`, when merged with another `MultiCell`, creates
    a new `MultiCell` that keeps all of the values kept by the two
    `MultiCell` instances; when merged with a `Cell`-compliant object
    of some other type, delegates the merge operation to that other
    object -- see: `PlainCell` (above) and `StemCell` (below);

  * a `StemCell`, when merged with another `Cell`-compliant object,
    always gives that other object (intact) as the merge result;

* (III) when it comes to the `output` attribute semantics and type:

  * `output` of a `PlainCell` is just the kept value (intact);

  * `output` of a `MultiCell` is a collection (`list`, by default)
    that contains all kept values; the collection type can be
    customized -- you can do that by creating your custom constructor
    (factory) of `MultiCell` instances, by invoking:
    `MultiCell.with_output_as(<one-argument factory of a collection>)`
    (where `<one-argument factory of a collection>` can be, e.g.,
    `set`, `tuple`, `",".join`, etc.);

  * a `StemCell` has no usable `output` (trying to get it causes a
    `TypeError`).

***

This module also contains a concrete class that provides the standard
implementation of the `NamespaceConversionStateBookkeeper` interface --
namely, the `StandardNamespaceConversionStateBookkeeper` class (see its
docs).

***

See also the docs (if any) and the code of:

* the following stuff defined in the `.interfaces` module: `Cell` and
  `NamespaceConversionStateBookkeeper` (see their docs), as well as
  `NamespaceItemConverter` (that one documented in the docs of the
  `.Converter` interface, as its subtype),
* the `.converters.BaseNameValuePairConverter` base class
  (which provides a basic framework that makes implementing
  `NamespaceItemConverter` more convenient),
* the `.converters.NameValuePairConverter` class (which is a simple
  concrete subclass of `BaseNameValuePairConverter`),
* the `.converters.BaseNamespaceConverter` base class (and its concrete
  subclasses...).
"""

from builtins import map                                                         #3--
import collections
import functools
from typing import (
    AbstractSet,
    Any,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    Union,
)

from pyramid.decorator import reify

from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import ascii_str
from n6lib.structured_data_conversion.exceptions import DataConversionError
from n6lib.structured_data_conversion.interfaces import (
    Cell,
    Name,
    NameValuePair,
    Value,
)
from n6lib.typing_helpers import String


#
# Public concrete classes that implement the `Cell` interface
#

class PlainCell(object):

    def __init__(self, value):
        # type: (Value) -> None
        self._output = value

    __repr__ = attr_repr('output')

    @property
    def output(self):
        # type: () -> Value
        return self._output

    def __add__(self, other):
        # type: (Cell) -> Cell
        if isinstance(other, StemCell):
            return self
        raise DataConversionError('data duplication detected')

    __radd__ = __add__


class MultiCell(object):

    def __init__(                                                                #3: remove this method definition *and* uncomment the definition below
        self,
        *values,   # type: Value
        # (in Python 2.7, at the function signature level, we cannot
        # specify keyword-only arguments in a more precise way...)
        **kw       # type: Union[Kw__component_cells, Kw__output_as]
    ):
        self._own_values = values                                     # type: Tuple[Value, ...]
        self._component_cells = tuple(kw.pop('component_cells', ()))  # type: Tuple[MultiCell, ...]
        self._output_as = kw.pop('output_as', list)                   # type: Kw__output_as
        if kw:
            raise TypeError(
                '{}.__init__() got unexpected keyword arguments: {}'.format(
                    self.__class__.__name__,
                    ', '.join(map(repr, sorted(kw)))))

    # def __init__(
    #     self,
    #     *values,              # type: Value
    #     component_cells=(),   # type: Iterable[MultiCell]
    #     output_as=list,       # type: Callable[[Iterator[Value]], Any]
    # ):
    #     self._own_values = values                        # type: Tuple[Value, ...]
    #     self._component_cells = tuple(component_cells)   # type: Tuple[MultiCell, ...]
    #     self._output_as = output_as                      # type: Callable[[Iterator[Value]], Any]

    __repr__ = attr_repr('_own_values', '_component_cells', '_output_as')

    @classmethod
    def with_output_as(cls, output_as):
        # type: (Callable[[Iterator[Value]], Any]) -> Callable[[Value], Cell]
        return functools.partial(cls, output_as=output_as)

    @reify
    def output(self):
        # type: () -> Any
        return self._output_as(self._iter_all_values())

    def __add__(self, other):
        # type: (Cell) -> Cell
        if isinstance(other, MultiCell):
            return self._merge(self, other)
        return NotImplemented

    def __radd__(self, other):
        # type: (Cell) -> Cell
        if isinstance(other, MultiCell):
            return self._merge(other, self)
        return NotImplemented

    #
    # Private helpers

    def _iter_all_values(self):
        # type: () -> Iterator[Value]

        # Note: a recursive implementation would be more concise and elegant
        # but it would be prone to "maximum recursion depth exceeded" errors.

        _partial = functools.partial

        class StackItem(object):
            def __init__(self, cell):
                # type: (MultiCell) -> None
                self.cell = cell                     # type: MultiCell  # (<- only for assertions)
                self.get_unvisited_component_cell = _partial(
                    next,
                    iter(cell._component_cells),
                    None)                               # type: Callable[[], Optional[MultiCell]]
                self.own_values = cell._own_values      # type: Tuple[Value, ...]

        stack = []
        si = StackItem(self)
        while True:
            component_cell = si.get_unvisited_component_cell()
            if component_cell is not None:
                stack.append(si)
                si = StackItem(component_cell)
            else:
                for value in si.own_values:
                    yield value
                if not stack:
                    break
                si = stack.pop()
        assert si.cell is self
        assert not stack

    @classmethod
    def _merge(cls, *component_cells):
        # type: (*MultiCell) -> MultiCell
        # Note: here, actually, we do not concatenate the value
        # collections kept by the cells being merged but only store,
        # within the newly created cell, references to these cells;
        # the actual concatenation is deferred until the first
        # retrieval of the `output` attribute is performed (see:
        # the `output` and `_iter_all_values()` definitions).
        # We shaped it this way because we want to keep both of the
        # following premises:
        # * (1) `Cell`-compliant objects (in particular `MultiCell`
        #       instances) behave as immutable objects (so that, in
        #       particular, when merging two `MultiCell` instances
        #       using the `+` operator, the `_own_values` of any of
        #       them is *not* modified but a new `MultiCell` is
        #       created);
        # * (2) merging many consecutive `MultiCell` instances is
        #       still efficient; in particular, the complexity does
        #       *not* grow to `O(n**2)`.
        try:
            first_component_cell = component_cells[0]  # type: MultiCell
        except IndexError:
            raise ValueError('at least one cell must be given')
        return cls(component_cells=component_cells,
                   output_as=first_component_cell._output_as)
                                                                                 #3--
# (auxiliary MultiCell-related static typing stuff)                              #3--
Kw__component_cells = Iterable[MultiCell]                                        #3--
Kw__output_as = Callable[[Iterator[Value]], Any]                                 #3--


class StemCell(object):

    @property
    def output(self):
        # type: () -> Value
        raise TypeError('{!r}.output should never be retrieved'.format(self))

    def __add__(self, other):
        # type: (Cell) -> Cell
        return other

    __radd__ = __add__


#
# A semi-public concrete class that implements the
# `NamespaceConversionStateBookkeeper` interface

class StandardNamespaceConversionStateBookkeeper(object):

    """
    This is the standard implementation of the
    `.interfaces.NamespaceConversionStateBookkeeper` abstract
    interface.

    TL;DR: Typically, you do *not* need to bother with it at all. :-)

    It is treated by `.converters.BaseNamespaceConverter`'s machinery
    as the default implementation of a *conversion state bookkeeper*
    (i.e., is used by concrete subclasses of `BaseNamespaceConverter`
    unless they override the `state_bookkeeper_context()` method so that
    it provides some other implementation of
    `NamespaceConversionStateBookkeeper`).

    Note: though in nearly all cases this standard implementation
    should be sufficient, by defining and using your custom
    `NamespaceConversionStateBookkeeper` implementation you can
    customize certain details of conversion of namespace-like
    collections; note, however, that this is an advanced issue -- so
    do not try to do it without understanding the code related to the
    matter (unfortunately, rather scarcely documented, at least for
    now).

    ***

    See also:

    * `.interfaces.NamespaceConversionStateBookkeeper`,
    * `.converters.BaseNamespaceConverter`.
    """

    def __init__(self):
        self._output_name_to_converted_value_cell = collections.defaultdict(StemCell)
        self._output_name_to_input_names = collections.defaultdict(list)
        self._collected_input_names = set()

    def preprocess_input_items(self, input_name_value_pairs):
        # type: (Iterable[NameValuePair]) -> Iterable[NameValuePair]
        return input_name_value_pairs

    def collect_converted_item(self, input_name, output_name, converted_value_cell):
        # type: (Name, Name, Cell) -> None
        self._output_name_to_converted_value_cell[output_name] += converted_value_cell
        self._output_name_to_input_names[output_name].append(input_name)
        self._collected_input_names.add(input_name)

    def verify_required_input_items_collected(self, required_input_names):
        # type: (AbstractSet) -> None
        uncollected = required_input_names - self._collected_input_names
        if uncollected:
            raise DataConversionError(
                'the following required items are missing or have '
                'been skipped as effectively NULL-like (i.e., not '
                'carrying any meaningful data): {}'.format(
                    ', '.join(sorted(
                        repr(ascii_str(input_name))
                        for input_name in uncollected))))

    def generate_output_items(self):
        # type: () -> Iterator[NameValuePair]
        for (output_name,
             converted_value_cell) in self._output_name_to_converted_value_cell.items():
            possible_input_names = self.iter_input_names_for_output_name(output_name)
            with DataConversionError.sublocation(possible_input_names):
                yield output_name, converted_value_cell.output

    def iter_input_names_for_output_name(self, output_name):
        # type: (String) -> Iterator[String]
        return iter(self._output_name_to_input_names.get(output_name, ()))

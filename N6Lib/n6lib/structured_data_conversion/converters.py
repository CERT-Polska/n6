# Copyright (c) 2020-2022 NASK. All rights reserved.

import contextlib
import itertools
from typing import (
    Any,
    Callable,
    ClassVar,
    Container,
    ContextManager,
    Dict,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Sized,
    Tuple,
    Union,
    cast,
)

from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    as_unicode,
    ascii_str,
)
from n6lib.structured_data_conversion.exceptions import DataConversionError
from n6lib.structured_data_conversion.interfaces import (
    Cell,
    Converter,
    ConverterMaker,
    ConverterExtendedMaker,
    Name,
    NameCellPair,
    NameValuePair,
    NamespaceConversionStateBookkeeper,
    NamespaceItemConverterMaker,
    NamespaceItemConverterExtendedMaker,
    NamespaceMappingOrIterable,
    Value,
)
from n6lib.structured_data_conversion.namespace_conversion_helpers import (
    MultiCell,
    PlainCell,
    StandardNamespaceConversionStateBookkeeper,
)
from n6lib.typing_helpers import (
    BaseExcFactory,
    KwargsDict,
    String,
    TypeSpec,
)



#
# Public abstract classes
#

class BaseConverter(object):

    """
    An abstract class that makes it easier to define classes of
    converters, i.e., of objects that support the `Converter`
    interface.

    Note that it is not required that a converter is an instance
    of a `BaseConverter` subclass. `BaseConverter` just provides
    a convenient framework to implement converters.

    ***

    Moreover, each concrete subclass of `BaseConverter` is, in itself,
    an implicit *instance* [sic!] of the `ConverterExtendedMaker`
    interface (see its docs, as well as the docs of its supertype,
    `ConverterMaker`).

    ***

    One of the `BaseConverter`-specific facilities is the
    `make_subconverter()` instance method; it makes use of the `dict`
    being the `subconverter_maker_to_kwargs` instance attribute whose
    content originates from the (`ConverterExtendedMaker`-specific)
    `subconverter_maker_to_kwargs` argument accepted by
    `BaseConverter.__init__()`.

    The `make_subconverter()` accepts any `ConverterMaker` compliant
    (possibly `ConverterExtendedMaker`-compliant) object, in particular
    a concrete subclass of `BaseConverter`, or the result of calling
    the `maker()` class method of such a subclass.

    See: the docs of the `make_subconverter()` method.

    **Note** that, when composing converter instances -- building even
    deeply nested containment hierarchies (in particular, by using
    instances of such classes as `IterableCollectionConverter` or
    `NamespaceMappingConverter`, or other concrete subclasses of
    `BaseSequenceLikeCollectionConverter`, `BaseNamespaceConverter`
    etc.) -- that method makes it possible to ensure that the
    `subconverter_maker_to_kwargs` stuff, once specified just for
    the top-level converter, is *automatically propagated* to all
    subconverters (recursively). However, a necessary condition is that
    `make_subconverter()` is used consistently throughout the hierarchy
    (whenever a subconverter is to be created using a maker compliant
    with `ConverterExtendedMaker`).

    The `dict` being the `subconverter_maker_to_kwargs` attribute of a
    given instance can be modified in `__init__()`, **provided that**
    from the moment when the instance initialization is completed or
    before the first invocation of the `make_subconverter()` method on
    that instance (whichever is earlier) that `dict` should be treated
    as a read-only* attribute and a *read-only* collection (that is, it
    should *neither* be replaced *nor* mutated in place).

    ***

    Important: a properly implemented subclass of `BaseConverter`
    should not override the `__init__()` method in any other manner
    than in such a cooperative way that ensures that any arguments
    *not* handled by the particular class are passed up the
    inheritance hierarchy with a `super(...).__init__(**kwargs)`-like
    call.
    """

    #
    # Public class-level interface
    # (implementation of `ConverterExtendedMaker`)

    # (this class attribute is intended to be overridden is subclasses, if needed)
    accept_kwargs_prescribed_for = None  # type: ClassVar[Optional[ConverterMaker]]

    def __init__(
        self,
        *,
        subconverter_maker_to_kwargs=None,  # type: Optional[Mapping[ConverterMaker, KwargsDict]]
        **kwargs
    ):
        super(BaseConverter, self).__init__(**kwargs)
        self.subconverter_maker_to_kwargs = dict(subconverter_maker_to_kwargs or {})

    @classmethod
    def maker(cls, **junior_maker_creation_kwargs):
        # type: (...) -> ConverterExtendedMaker
        """
        TODO: doc...
        """
        return cls._Maker(senior_maker=cls,
                          maker_creation_kwargs=junior_maker_creation_kwargs)

    #
    # Internals related to the above public class-level interface

    class _Maker(object):

        def __init__(self, senior_maker, maker_creation_kwargs):
            # type: (ConverterExtendedMaker, KwargsDict) -> None
            self._senior_maker = senior_maker
            self._maker_creation_kwargs = maker_creation_kwargs

        __repr__ = attr_repr('_senior_maker', '_maker_creation_kwargs')

        # `ConverterMaker`-specific stuff:
        def __call__(self, **maker_call_kwargs):
            # type: (...) -> Converter
            actual_kwargs = dict(self._maker_creation_kwargs)
            actual_kwargs.update(maker_call_kwargs)
            return self._senior_maker(**actual_kwargs)

        # `ConverterExtendedMaker`-specific stuff:
        @property
        def accept_kwargs_prescribed_for(self):
            # type: () -> ConverterExtendedMaker
            return self._senior_maker

        def maker(self, **junior_maker_creation_kwargs):
            # type: (...) -> ConverterExtendedMaker
            return self.__class__(senior_maker=self,
                                  maker_creation_kwargs=junior_maker_creation_kwargs)

        # `BaseConverter.maker()`-result-specific stuff:
        @property
        def provided_kwargs(self):
            # type: () -> KwargsDict
            provided_kwargs_from_senior = getattr(self._senior_maker, 'provided_kwargs', {})
            return dict(provided_kwargs_from_senior,
                        **self._maker_creation_kwargs)

    #
    # Public instance-level interface
    # (implementation of `Converter`)

    def __call__(self, data):
        # type: (Value) -> Iterator
        """
        An abstract method: the main activity of the converter.

        The sole positional argument:
            The data to be converted, provided as an object of
            an unconstrained type (subclasses can restrict what
            types/values they accept).

        Returns:
            An iterator that yields some number of objects being the
            results of the conversion (subclasses, at their discretion,
            can restrict themselves to yield, e.g., always exactly one
            object or no object at all, or always yield not more than
            one object, or a certain number of objects etc., as well as
            to yield, for example, only objects of certain type(s)...).

        Raises:
            * `DataConversionError` -- to signal that client-provided
              *data* are wrong (see the docs of `DataConversionError`);
            * some other exception -- to signal a programming error
              (either internal one or such one for which the client
              code or library code is responsible).

        Let us emphasize what we have already stated in the description
        of the `Converter` abstract interface: each call should be
        concurrency-safe and independent of other calls (whether of
        earlier, or later, or concurrent ones) of the converter object.
        That typically means (in particular) that a converter instance
        should *not* keep, using its attributes, any mutable state.
        """
        raise NotImplementedError

    #
    # Non-public, subclass-accessible helpers

    @staticmethod
    def verify_isinstance(value, type_spec, error_message=None):
        # type: (Value, TypeSpec, Optional[String]) -> None
        """
        A helper that can to be used in subclasses: verify that
        `isinstance(value, type_spec)` is true. If not, raise
        `DataConversionError(error_message)` or -- if `error_message`
        is unspecified or specified as `None` -- a `DataConversionError`
        with an automatically generated `"unexpected type of..."`-like
        message.
        """
        if not isinstance(value, type_spec):
            if error_message is None:
                if isinstance(type_spec, tuple):
                    error_message = 'unexpected type of {!a}'.format(value)
                else:
                    safe_class_name = ascii_str(type_spec.__qualname__)
                    error_message = 'unexpected type of {!a} (should be a {})'.format(
                        value,
                        safe_class_name)
            raise DataConversionError(error_message)

    @staticmethod
    def verify_in(value, container, error_message=None):
        # type: (Value, Container, Optional[String]) -> None
        """
        A helper that can to be used in subclasses: verify
        that `value in container` is true. If not, raise
        `DataConversionError(error_message)` or -- if
        `error_message` is unspecified or specified as
        `None` -- a `DataConversionError` with an automatically
        generated `"... is not in ..."` message.

        """
        if value not in container:
            if error_message is None:
                error_message = '{!a} is not in {!a}'.format(value, container)
            raise DataConversionError(error_message)

    @classmethod
    def verify_is_regular_iterable_collection(cls, value):
        # type: (Value) -> None
        """
        A helper that can to be used in subclasses: verify that for the
        given `value` --

        * `isinstance(value, typing.Iterable)` is true, **but**
        * `isinstance(value, typing.Mapping)` is *not* true, and
        * `isinstance(value, str)` is *not* true, and
        * `isinstance(value, (bytes, bytearray, memoryview))` is *not* true.

        If the result of the above verification is negative, a
        `DataConversionError` with an appropriate message is raised.
        """
        cls.verify_isinstance(value, Iterable, 'expected a collection')
        if isinstance(value, Mapping):
            raise DataConversionError('expected a collection but *not* a mapping')
        if isinstance(value, str):
            raise DataConversionError('expected a collection, *not* a string')
        if isinstance(value, (bytes, bytearray, memoryview)):
            raise DataConversionError('expected a collection, *not* a binary data object')

    # * Instance-level-only stuff:

    subconverter_maker_to_kwargs = None  # type: Dict[ConverterMaker, KwargsDict]

    def make_subconverter(self, subconverter_maker, **custom_kwargs):
        # type: (ConverterMaker, **Any) -> Converter
        """
        A helper that can to be used in subclasses: call the given
        `subconverter_maker` (a `ConverterMaker`-compliant object),
        with appropriate keyword arguments, to create a new converter.

        What is most important -- given the mapping being the
        `subconverter_maker_to_kwargs` attribute (provided by
        `BaseConverter.__init__()`) -- is that:

        * if `subconverter_maker` matches a key in the aforementioned
          `subconverter_maker_to_kwargs` mapping then the items of the
          `dict` being the value pointed by that key are passed to the
          `subconverter_maker(...)` call as keyword arguments
          (possibly, after being selectively overridden by arguments
          passed to this method call);

        * the content of the aforementioned `subconverter_maker_to_kwargs`
          mapping is, if possible, automatically propagated to the newly
          created converter.

        For more details -- see the description below.

        ***

        Required args/kwargs:
            `subconverter_maker`:
                A callable being a `ConverterMaker`-compliant object
                (possibly also a `ConverterExtendedMaker`-compliant
                one) -- to be called to create a new converter.

                Note: typically (though not necessarily) this argument
                is either a callable object returned by the `maker()`
                method of some concrete subclass of `BaseConverter`, or
                just such a subclass itself.

        Any other kwargs:
            To be passed directly to the `subconverter_maker(...)`
            call, possibly overriding arguments from the mapping being
            the `subconverter_maker_to_kwargs` instance attribute.

        Returns:
            A new converter (i.e., a `Converter`-compliant object).

        Raises:
            Any error that `subconverter_maker(...)` can raise; in
            particular, `TypeError` -- if some unsupported arguments
            are passed to the `subconverter_maker(...)` call.

        ***

        When this method is called on some object, hereinafter referred
        to as *the instance*, using the `subconverter_maker` argument
        and, possibly, other arguments (keyword-only ones), then the
        `subconverter_maker` object is invoked in the following way:

        * if `subconverter_maker` matches a key⁽¹⁾ in the mapping being
          *the instance's* `subconverter_maker_to_kwargs` attribute
          then the items of the `dict` -- hereinafter referred to as
          the *prescribed kwargs dict* -- that is stored under that key
          are passed to the `subconverter_maker(...)` call (with the
          proviso that they can be selectively overridden by keyword
          arguments passed to this method call);

        * additionally, if `subconverter_maker` has such attributes
          that we can imply that it is an object compliant with the
          `ConverterExtendedMaker` interface, a copy of the mapping
          being *the instance's* `subconverter_maker_to_kwargs`
          attribute is passed to the `subconverter_maker(...)` call as
          the `subconverter_maker_to_kwargs` argument -- so that its
          items will be automatically propagated to the mapping being
          the `subconverter_maker_to_kwargs` attribute of the newly
          created converter (so that, if the `make_subconverter()`
          method is called on that converter, those items will be
          further propagated...);

          note, however, that it is possible to override that mapping,
          i.e., completely replace it (here that's **not** a per-item
          update!):

          * with the `dict` placed in the *prescribed kwargs dict* as
            the `"subconverter_maker_to_kwargs"` item (if any;
            not recommended but possible);

          * with the `dict` passed to this method call as the
            `subconverter_maker_to_kwargs` argument (if given);

          the latter has the highest priority;

        ⁽¹⁾ By saying that `subconverter_maker` matches a key in the
        mapping being *the instance's* `subconverter_maker_to_kwargs`
        attribute (so that the `dict` stored under that key becomes the
        *prescribed kwargs dict*) we mean that that key is:

        * either the object passed in as `subconverter_maker` itself,

        * or the `accept_kwargs_prescribed_for` attribute (if any) of
          that object, or the `accept_kwargs_prescribed_for` attribute
          (if any) of that attribute -- and so on (recursively).

        However, if there is no match then the *prescribed kwargs dict*
        is assumed to be just an empty `dict`.
        """
        actual_kwargs = {}
        if self._does_look_like_converter_extended_maker(subconverter_maker):
            actual_kwargs['subconverter_maker_to_kwargs'] = dict(self.subconverter_maker_to_kwargs)
        actual_kwargs.update(self._get_kwargs_prescribed_for(subconverter_maker))
        actual_kwargs.update(custom_kwargs)
        return subconverter_maker(**actual_kwargs)

    #
    # Internal helpers

    def _does_look_like_converter_extended_maker(self, subconverter_maker):
        # type: (ConverterMaker) -> bool
        # XXX: We don't use `@typing.runtime_checkable` as, for some reason,
        # it didn't wanted to recognize `BaseConverter` subclasses as
        # ConverterExtendedMaker instances, at least with the Python 2.x
        # version of `typing`...
        return (hasattr(subconverter_maker, 'accept_kwargs_prescribed_for') and
                callable(subconverter_maker) and
                callable(getattr(subconverter_maker, 'maker', None)))

    def _get_kwargs_prescribed_for(self, converter_maker):
        # type: (ConverterMaker) -> KwargsDict
        while True:
            prescribed_kwargs = self.subconverter_maker_to_kwargs.get(converter_maker)
            if prescribed_kwargs is not None:
                break
            converter_maker = getattr(converter_maker, 'accept_kwargs_prescribed_for', None)
            if converter_maker is None:
                prescribed_kwargs = {}
                break
        assert prescribed_kwargs is not None
        return prescribed_kwargs


class BaseSequenceLikeCollectionConverter(BaseConverter):

    """
    TODO doc...
    """

    def __init__(self,
                 element_converter_maker,           # type: ConverterMaker
                 assembling_converter_maker=None,   # type: Optional[ConverterMaker]
                 **kwargs):
        super(BaseSequenceLikeCollectionConverter, self).__init__(**kwargs)
        if assembling_converter_maker is None:
            assembling_converter_maker = self.get_default_assembling_converter_maker()
        self._element_converter = self.make_subconverter(element_converter_maker)
        self._assembling_converter = self.make_subconverter(assembling_converter_maker)

    def __call__(self, data):
        # type: (Value) -> Iterator
        input_elements = self.generate_elements(data)
        output_elements = self.generate_output_elements(input_elements)
        for assembled_data in self._assembling_converter(output_elements):
            yield assembled_data

    #
    # Non-public, subclass-overridable/extendable hooks

    def generate_elements(self, data):
        # type: (Value) -> Iterator[Value]
        """An abstract method: TODO doc..."""
        raise NotImplementedError

    def generate_output_elements(self, input_elements):
        # type: (Iterator[Value]) -> Iterator[Value]
        for index, value in enumerate(input_elements):
            with DataConversionError.sublocation(index):
                for converted_value in self._element_converter(value):
                    yield converted_value

    def get_default_assembling_converter_maker(self):
        # type: () -> ConverterMaker
        return SingleArgCallingConverter.maker(output_factory=list)


_NameToItemConverterMaker = Mapping[Name, NamespaceItemConverterMaker]

class BaseNamespaceConverter(BaseConverter):

    """
    TODO doc...
    """

    def __init__(
            self,
            *,
            input_name_to_item_converter_maker=None,  # type: Optional[_NameToItemConverterMaker]
            required_input_names=(),                  # type: Iterable[Name]
            free_item_converter_maker=None,           # type: Optional[NamespaceItemConverterMaker]
            assembling_converter_maker=None,          # type: Optional[ConverterMaker]
            **kwargs):
        super(BaseNamespaceConverter, self).__init__(**kwargs)
        if input_name_to_item_converter_maker is None:
            input_name_to_item_converter_maker = {}
        if free_item_converter_maker is None:
            free_item_converter_maker = self.get_default_free_item_converter_maker()
        if assembling_converter_maker is None:
            assembling_converter_maker = self.get_default_assembling_converter_maker()
        self._input_name_to_converter = {
            input_name: self.make_subconverter(converter_maker)
            for input_name, converter_maker in input_name_to_item_converter_maker.items()}
        self._required_input_names = frozenset(required_input_names)
        self._free_item_converter = self.make_subconverter(free_item_converter_maker)
        self._assembling_converter = self.make_subconverter(assembling_converter_maker)

    #
    # Implementation of base-class-declared abstract method

    def __call__(self, data):
        # type: (Value) -> Iterator
        with self.state_bookkeeper_context() as bookkeeper:
            input_name_value_pairs = self.generate_input_name_value_pairs(data)
            input_name_value_pairs = self.validate_input_names(input_name_value_pairs)
            input_name_value_pairs = bookkeeper.preprocess_input_items(input_name_value_pairs)
            for input_name, input_value in input_name_value_pairs:
                with DataConversionError.sublocation(input_name):
                    item_conv = self._input_name_to_converter.get(
                        input_name,
                        self._free_item_converter)
                    for output_name, converted_value_cell in item_conv((input_name, input_value)):
                        bookkeeper.collect_converted_item(
                            input_name,
                            output_name,
                            converted_value_cell)
            bookkeeper.verify_required_input_items_collected(self._required_input_names)
            output_name_value_pairs = bookkeeper.generate_output_items()
            for assembled_data in self._assembling_converter(output_name_value_pairs):
                yield assembled_data

    #
    # Non-public, subclass-overridable/extendable hooks

    def generate_input_name_value_pairs(self, data):
        # type: (Value) -> Iterator[NameValuePair]
        """An abstract method: TODO doc..."""
        raise NotImplementedError

    def get_default_free_item_converter_maker(self):
        # type: () -> NamespaceItemConverterMaker
        def illegal_item_error_factory(_data):
            return DataConversionError('illegal item name')
        return cast(
            NamespaceItemConverterMaker,
            ErrorRaisingConverter.maker(error_factory=illegal_item_error_factory))

    def get_default_assembling_converter_maker(self):
        # type: () -> ConverterMaker
        return SingleArgCallingConverter.maker(output_factory=dict)

    @contextlib.contextmanager
    def state_bookkeeper_context(self):
        # type: () -> Generator[NamespaceConversionStateBookkeeper, None, None]
        yield StandardNamespaceConversionStateBookkeeper()

    def validate_input_names(self, data):
        # type: (Iterator) -> (Sequence[NameValuePair])
        """
        Note: this method works in an eager (not lazy) manner (in
        particular, is not a generator and does not return an iterator,
        but a sequence) -- because we want to emphasize that we do
        *not* want to defer the validation, but to have it performed
        immediately.
        """
        validated = []
        for input_name, input_value in data:
            if not isinstance(input_name, str):
                raise DataConversionError(
                    'unexpected non-string key ({!a}) in '
                    'the mapping'.format(input_name))
            validated.append((input_name, input_value))
        return validated


class BaseNameValuePairConverter(BaseConverter):

    """
    An abstract class that makes it easier to define classes
    of converters whose makers are needed when specifying the
    `input_name_to_item_converter_maker` and `free_item_converter_maker`
    arguments for `BaseNamespaceConverter` instance constructors (see
    `BaseNamespaceConverter.__init__()`). Such a maker needs to be
    `NamespaceItemConverterMaker`-compliant (that is, to be such a
    `ConverterMaker`-compliant object whose return values will be
    `NamespaceItemConverter`-compliant) -- therefore a concrete
    subclass of this class (or the result of calling `.maker()`
    on such a subclass) is a natural candidate for such a maker.

    Note that there is a simple and convenient concrete subclass of
    this class: `NameValuePairConverter`.

    ***

    Constructor kwargs:

        'value_converter_maker':

            A `ConverterMaker`-compliant object (possibly, also
            `ConverterExtendedMaker`-compliant), to be called by this
            class's `__init__()` (using the `make_subconverter()`
            method called with that object as the sole argument) to
            create the *value converter*, i.e., the converter that will
            be used to convert the *value* part of each *name-value*
            pair (as yielded by the `generate_actual_name_value_pairs()`
            method).

            Note: as any `Converter`, such a converter can produce any
            number of converted values, not necessarily one (and then
            the same number of `NameCellPair`-compliant tuples will be
            produced by the `__call__()` method defined here).

        `collection` (`None`, `False`, `True` or a callable; default: `None`):

            Defines whether the concerned item should be considered a
            *collection* or *scalar*; and, for the former option, what
            kind of collection it is supposed to be.

            To be more precise about these two options:

            * *scalar*, specified by `None` (or `False`) -- means that
              when the machinery of the namespace collector (i.e., the
              instance of `BaseNamespaceConverter` that employs, among
              others, *this* instance of `BaseNameValuePairConverter`)
              detects that, for a particular output item name, multiple
              (more than one) converted values appear (produced by one
              or more `NamespaceItemConverter`-compliant object(s),
              *not* necessarily only *this* one) then an exception
              `DataConversionError('data duplication detected')` will
              be raised;

            * *collection*, specified by a callable (or `True`) --
              means that, for a particular output item name, no matter
              how many converted values appear for that name (produced
              by one or more `NamespaceItemConverter`-compliant
              object(s), *not* necessarily only *this* one), provided
              that some value(s) appear at all, these values will be
              collected by passing to the given callable an iterator
              that yields all these values;

              the given callable --

              * must take exactly one positional argument being an
                iterator, and
              * is, typically, supposed to be some kind of collection
                factory (such as `list`, `tuple`, `set`, `frozenset`,
                `",".join` etc.);

              if `True` is given (instead of a callable) then the
              built-in `list` factory will be used.

        `value_cell_factory` (`None` or a callable; default: `None`):

            Typically, you do not need to specify this argument. It can
            be used for advanced customization of the *scalar* vs.
            *collection* matter described above (and even more, if some
            custom `Cell`-compliant classes are involved...).

            If given as a non-`None` object:

            * it must be a callable that takes exactly one positional
              argument (being a just converted value) and returns a
              `Cell`-compliant object (that is supposed to wrap that
              value);

            * then the `collection` argument (described above) must
              *not* be given as a non-`None` object (or `TypeError`
              will be raised); `collection` given as `None` is ignored.

            Additional notes:

            * giving `value_cell_factory` as the `PlainCell` class is
              the same as giving `collection` as `False` (or `None`);

            * giving `value_cell_factory` as the `MultiCell` class is
              the same as giving `collection` as `True` (or the `list`
              factory).

            * giving `value_cell_factory` as an object being the result
              of a `MultiCell.with_output_as(<my callable>)` call
              is the same as giving `collection` as `<my callable>`.

    ***

    It should be obvious (provided that the particular subclass is
    implemented properly) that:

    * any concrete *subclass* of this class (as well as the result of
      any `.maker()` invocation on such a subclass) is compliant with
      the `NamespaceItemConverterMaker` interface, and even with the
      `NamespaceItemConverterExtendedMaker` one; and

    * an *instance* of any concrete subclass of this class is compliant
      with the `NamespaceItemConverter` interface.

    However, note that this relationship is not reciprocal, i.e.:

    * it is *not* required that a `NamespaceItemConverterMaker`-compliant
      maker or `NamespaceItemConverterExtendedMaker`-compliant maker is
      a subclass of `BaseNameValuePairConverter`; and

    * it is *not* required that a `NamespaceItemConverter`-compliant
      converter is an instance of a `BaseNameValuePairConverter`
      subclass.

    This class provides just a convenient framework to implement such
    converters and their makers.
    """

    @classmethod
    def maker(cls, **junior_maker_creation_kwargs):
        # type: (...) -> NamespaceItemConverterExtendedMaker
        return cast(
            NamespaceItemConverterExtendedMaker,
            super(BaseNameValuePairConverter, cls).maker(**junior_maker_creation_kwargs))

    def __init__(
            self,
            *,
            value_converter_maker,     # type: ConverterMaker
            collection=None,           # type: Union[None, bool, Callable[[Iterator[Value]], Any]]
            value_cell_factory=None,   # type: Optional[Callable[[Value], Cell]]
            **kwargs):
        super(BaseNameValuePairConverter, self).__init__(**kwargs)
        self._value_converter = self.make_subconverter(value_converter_maker)
        self._value_cell_factory = self.__get_value_cell_factory(collection, value_cell_factory)

    def __get_value_cell_factory(self, collection, value_cell_factory):
        # type: (...) -> Callable[[Value], Cell]
        if collection is not None:
            if value_cell_factory is not None:
                raise TypeError(
                    "either of the 'collection' and 'value_cell_factory' "
                    "keyword arguments can be specified, but not both "
                    "(got: collection={!a}; value_cell_factory={!a}".format(
                        collection, value_cell_factory))
            if isinstance(collection, bool):
                value_cell_factory = (MultiCell if collection else PlainCell)
            else:
                value_cell_factory = MultiCell.with_output_as(collection)
        elif value_cell_factory is None:
            value_cell_factory = PlainCell
        assert value_cell_factory is not None
        return value_cell_factory

    def __call__(self, input_name_value_pair):
        # type: (NameValuePair) -> Iterator[NameCellPair]
        for (actual_name,
             actual_value) in self.generate_actual_name_value_pairs(input_name_value_pair):
            for converted_value in self._value_converter(actual_value):
                converted_value_cell = self._value_cell_factory(converted_value)
                yield actual_name, converted_value_cell

    #
    # Non-public, subclass-overridable/extendable hooks

    def generate_actual_name_value_pairs(self, input_name_value_pair):
        # type: (NameValuePair) -> Iterator[NameValuePair]
        """
        An abstract method: prepare the input *name-value* pair (before
        the main part of conversion).

        This is a hook that takes the *name-value* pair that has been
        passed to the `__call__()` method and yields some number
        (typically just one, but it is not a strict requirement) of
        -- possibly adjusted -- *name-value* pairs, each of whom will
        be the subject of the actual conversion.

        A simple implementation of this method can just yield the given
        *name-value* pair intact.

        Another implementation, for example, can replace the *name*
        part of the given pair with some other name (such name
        substitutions are quite typical for namespace conversions...)
        -- in particular, see the implementation provided by the
        `NameValuePairConverter` class.
        """
        raise NotImplementedError


class BaseCallingConverter(BaseConverter):

    """
    TODO doc...
    """

    def __init__(self,
                 *,
                 output_factory,                       # type: Callable[[Value], Value]
                 output_factory_default_kwargs=None,   # type: Optional[Mapping[Name, Value]]
                 **kwargs):
        super(BaseCallingConverter, self).__init__(**kwargs)
        self.output_factory = output_factory
        if output_factory_default_kwargs is None:
            output_factory_default_kwargs = {}
        self.output_factory_default_kwargs = output_factory_default_kwargs

    def __call__(self, data):
        # type: (Value) -> Iterator
        args, kwargs = self.make_output_factory_args_kwargs(data)
        yield self.output_factory(*args, **kwargs)

    #
    # Non-public, subclass-overridable/extendable hooks

    def make_output_factory_args_kwargs(self, data):
        # type: (Value) -> Tuple[Iterable, Mapping[Name, Value]]
        """An abstract method: TODO doc..."""
        raise NotImplementedError


class BaseConditionalConverter(BaseConverter):

    """
    TODO: doc...
    """

    def __init__(self,
                 *,
                 predicate,      # type: Callable[[Value], bool]
                 negated=False,  # type: bool
                 **kwargs):
        super(BaseConditionalConverter, self).__init__(**kwargs)
        self.predicate = predicate
        self.negated = negated

    #
    # Non-public, subclass-accessible helpers

    def is_condition_satisfied(self, data):
        satisfied = self.predicate(data)
        if self.negated:
            satisfied = not satisfied
        return satisfied



#
# Public concrete classes (that implement the `Converter` interface)
#

class IterableCollectionConverter(BaseSequenceLikeCollectionConverter):

    def generate_elements(self, iterable_obj):
        # type: (Value) -> Iterator[Value]
        self.verify_is_regular_iterable_collection(iterable_obj)
        for value in iterable_obj:
            yield value


class NamespaceMappingConverter(BaseNamespaceConverter):

    def generate_input_name_value_pairs(self, mapping):
        # type: (Value) -> Iterator[NameValuePair]
        self.verify_isinstance(mapping, Mapping)
        for input_name, input_value in mapping.items():
            yield input_name, input_value


class NameValuePairConverter(BaseNameValuePairConverter):

    def __init__(self,
                 *,
                 output_name=None,           # type: Optional[Name]
                 name_converter_maker=None,  # type: Optional[ConverterMaker]
                 **kwargs):
        super(NameValuePairConverter, self).__init__(**kwargs)
        if output_name is not None and not isinstance(output_name, str):
            raise TypeError('{!a} is not a string'.format(output_name))
        if name_converter_maker is None:
            name_converter_maker = PassingThruConverter
        self._output_name = output_name
        self._name_converter = self.make_subconverter(name_converter_maker)

    def generate_actual_name_value_pairs(self, input_name_value_pair):
        # type: (NameValuePair) -> Iterator[NameValuePair]
        input_name, actual_value = input_name_value_pair
        output_name = (self._output_name if self._output_name is not None
                       else input_name)
        for actual_name in self._name_converter(output_name):
            self.verify_isinstance(actual_name, str)
            yield actual_name, actual_value


class SingleArgCallingConverter(BaseCallingConverter):

    def make_output_factory_args_kwargs(self, data):
        # type: (Value) -> Tuple[Iterable, Mapping[Name, Value]]
        return (data,), self.output_factory_default_kwargs


class ArgsCallingConverter(BaseCallingConverter):

    def make_output_factory_args_kwargs(self, iterable_obj):
        # type: (Iterable) -> Tuple[Iterable, Mapping[Name, Value]]
        self.verify_is_regular_iterable_collection(iterable_obj)
        return iterable_obj, self.output_factory_default_kwargs


class KwargsCallingConverter(BaseCallingConverter):

    def make_output_factory_args_kwargs(self, mapping_items):
        # type: (NamespaceMappingOrIterable) -> Tuple[Iterable, Mapping[Name, Value]]
        try:
            if isinstance(mapping_items, (str, bytes, bytearray)):
                raise DataConversionError('got a `str`/`bytes`/`bytearray`')
            self.verify_isinstance(mapping_items, (Mapping, Iterable))
            mapping = dict(**dict(mapping_items))
        except (TypeError, DataConversionError):
            raise DataConversionError(
                'expected a name-to-value mapping or an equivalent '
                'collection of name-value pairs')
        kwargs = dict(self.output_factory_default_kwargs)
        kwargs.update(mapping)
        return (), kwargs


class NoOutputConverter(BaseConverter):

    def __call__(self, data):
        # type: (Value) -> Iterator
        return iter([])


class ConstantOutputConverter(BaseConverter):

    def __init__(self,
                 *,
                 constant_value,  # type: Any
                 **kwargs):
        super(ConstantOutputConverter, self).__init__(**kwargs)
        self.constant_value = constant_value

    def __call__(self, data):
        # type: (Value) -> Iterator
        yield self.constant_value


class PassingThruConverter(BaseConverter):

    def __call__(self, value):
        # type: (Value) -> Iterator
        yield value


class IterConverter(BaseConverter):

    def __call__(self, iterable_obj):
        # type: (Value) -> Iterator
        self.verify_is_regular_iterable_collection(iterable_obj)
        for value in iterable_obj:
            yield value


class ConcatenatingIterConverter(BaseConverter):

    def __call__(self, iterable_obj):
        # type: (Value) -> Iterator
        self.verify_is_regular_iterable_collection(iterable_obj)
        for subiterable_obj in iterable_obj:
            self.verify_is_regular_iterable_collection(subiterable_obj)
            for value in subiterable_obj:
                yield value


class SimpleConditionalConverter(BaseConditionalConverter):

    def __call__(self, data):
        # type: (Value) -> Iterator
        if self.is_condition_satisfied(data):
            yield data


class NonVoidInputConverter(SimpleConditionalConverter):

    def __init__(
          self,
          *,
          string_strips_before_test_if_void=None,  # type: Optional[Sequence[Union[None, String]]]
          **kwargs):
        super(NonVoidInputConverter, self).__init__(
            predicate=self.is_input_void,
            negated=True,
            **kwargs)
        self._string_strips_before_test_if_void = (
            string_strips_before_test_if_void if string_strips_before_test_if_void is not None
            else self.get_default_string_strips_before_test_if_void())

    #
    # Non-public, subclass-overridable/extendable hooks

    def get_default_string_strips_before_test_if_void(self):
        return [None]

    def is_input_void(self, data):
        # type: (Value) -> bool
        if data is None or (isinstance(data, Sized) and
                            len(data) == 0):
            return True
        if isinstance(data, str):
            for strip_arg in self._string_strips_before_test_if_void:
                data = data.strip(strip_arg)
            return not data
        return False


class IfElseConverter(BaseConditionalConverter):

    def __init__(self,
                 *,
                 then_converter_maker,        # type: ConverterMaker
                 else_converter_maker=None,   # type: Optional[ConverterMaker]
                 **kwargs):
        super(IfElseConverter, self).__init__(**kwargs)
        if else_converter_maker is None:
            else_converter_maker = NoOutputConverter
        self._then_converter = self.make_subconverter(then_converter_maker)
        self._else_converter = self.make_subconverter(else_converter_maker)

    def __call__(self, data):
        # type: (Value) -> Iterator
        converter = (self._then_converter if self.is_condition_satisfied(data)
                     else self._else_converter)
        for value in converter(data):
            yield value


class PipelineConverter(BaseConverter):

    def __init__(self,
                 *,
                 component_converter_makers=(),   # type: Iterable[ConverterMaker]
                 **kwargs):
        super(PipelineConverter, self).__init__(**kwargs)
        self.component_converters = [
            self.make_subconverter(converter_maker)
            for converter_maker in itertools.chain(
                # class-specified component converters:
                self.generate_constant_component_converter_makers(),
                # per-instance-specified component converters:
                component_converter_makers)]

    def __call__(self, data):
        # type: (Value) -> Iterator
        proc_values = [data]
        for converter in self.component_converters:
            proc_values = self._apply_converter(converter, proc_values)
        for output_value in proc_values:
            yield output_value

    def _apply_converter(self, converter, input_values):
        for value in input_values:
            for converted_value in converter(value):
                yield converted_value

    #
    # Non-public, subclass-overridable/extendable hooks

    def generate_constant_component_converter_makers(self):
        # type: () -> Iterator[ConverterMaker]
        return iter(())


class StringValueConverter(BaseConverter):

    # (public attribute -- to be set in
    # `__init__()` to instance-specific value)
    max_length = None               # type: Optional[int]

    def __init__(self,
                 *,
                 max_length=None,   # type: Optional[int]
                 **kwargs):
        super(StringValueConverter, self).__init__(**kwargs)
        self.max_length = max_length

    def __call__(self, value):
        # type: (Value) -> Iterator[String]
        self.verify_isinstance(
            value, str,
            error_message='{!a} is not a string'.format(value))
        output_value = as_unicode(value)
        self._verify_length(output_value)
        yield output_value

    def _verify_length(self, value):
        value_length = len(value)
        if self.max_length is not None and value_length > self.max_length:
            raise DataConversionError(
                'too long string (its length: {} characters; '
                'maximum valid length: {} characters)'.format(
                    value_length,
                    self.max_length))


class NonVoidStringValueConverter(PipelineConverter):

    # (public attribute -- to be set in
    # `__init__()` to instance-specific value)
    max_length = None               # type: Optional[int]

    def __init__(self,
                 *,
                 max_length=None,   # type: Optional[int]
                 **kwargs):
        super(NonVoidStringValueConverter, self).__init__(**kwargs)
        self.max_length = max_length

    def generate_constant_component_converter_makers(self):
        # type: () -> Iterator[ConverterMaker]
        yield NonVoidInputConverter
        yield StringValueConverter.maker(max_length=self.max_length)


class EnumStringValueConverter(StringValueConverter):

    def __init__(self,
                 *,
                 enum_values,  # type: Iterable[String]
                 **kwargs):
        super(EnumStringValueConverter, self).__init__(**kwargs)
        self._enum_values = list(enum_values)

    def __call__(self, value):
        # type: (Value) -> Iterator[String]
        for output_value in super(EnumStringValueConverter, self).__call__(value):
            self.verify_in(output_value, self._enum_values)
            yield output_value


class FlagValueConverter(BaseConverter):

    def __init__(self,
                 *,
                 true_flag_strings=('true', 'yes'),   # type: Union[String, Iterable[String]]
                 false_flag_strings=('false', 'no'),  # type: Union[String, Iterable[String]]
                 **kwargs):
        super(FlagValueConverter, self).__init__(**kwargs)
        self._true_flag_strings = self._get_flag_strings_set(true_flag_strings, kind='true')
        self._false_flag_strings = self._get_flag_strings_set(false_flag_strings, kind='false')

    def _get_flag_strings_set(self, raw_arg, kind):
        assert kind in {'true', 'false'}
        if isinstance(raw_arg, str):
            flags = [raw_arg]
        else:
            flags = list(raw_arg)
            non_str_values = [
                f for f in flags
                if not isinstance(f, str)]
            if non_str_values:
                raise TypeError(
                    'non-`str` value(s) found: {non_str_values} (got from '
                    'the argument: {kind}_flag_strings={raw_arg!a})'.format(
                        non_str_values=', '.join(map(ascii, non_str_values)),
                        kind=kind,
                        raw_arg=raw_arg))
        return frozenset(flags)

    def __call__(self, value):
        # type: (Value) -> Iterator[bool]
        self.verify_isinstance(
            value, (str, bool),
            error_message='{!a} is neither a string nor a Boolean value'.format(value))
        if isinstance(value, str):
            value = self._convert_flag_string(value)
        assert isinstance(value, bool)
        yield value

    def _convert_flag_string(self, value):
        word = value.lower()
        if not self._true_flag_strings and not self._false_flag_strings:
            raise DataConversionError(
                '{!a} is an illegal value (for this item, strings '
                'cannot be converted to Boolean values)'.format(word))
        if word in self._true_flag_strings:
            word = True
        elif word in self._false_flag_strings:
            word = False
        else:
            raise DataConversionError(
                '{!a} is an illegal value (for this item these are the only '
                'strings that can be converted to Boolean values: {})'.format(
                    word,
                    ', '.join(
                        sorted(map(ascii, self._true_flag_strings)) +
                        sorted(map(ascii, self._false_flag_strings)))))
        return word


class ErrorRaisingConverter(BaseConverter):

    def __init__(self,
                 *,
                 error_factory=None,  # type: Optional[BaseExcFactory]
                 **kwargs):
        super(ErrorRaisingConverter, self).__init__(**kwargs)
        self._error_factory = (error_factory if error_factory is not None
                               else self.default_error_factory)

    @staticmethod
    def default_error_factory(_data):
        # type: (Value) -> BaseException
        return DataConversionError('unspecified error')

    def __call__(self, data):
        # type: (Value) -> Iterator
        raise self._error_factory(data)
        # noinspection PyUnreachableCode
        yield  # (making this method a generator)


class WithContextManagerConverter(BaseConverter):

    def __init__(self,
                 *,
                 cm_factory,                 # type: Callable[[Value], ContextManager]
                 enclosed_converter_maker,   # type: ConverterMaker
                 input_data_preparer=None,   # type: Optional[Callable[[Value, Value], Value]]
                 **kwargs):
        super(WithContextManagerConverter, self).__init__(**kwargs)
        self._cm_factory = cm_factory
        self._enclosed_converter = self.make_subconverter(enclosed_converter_maker)
        self._input_data_preparer = (self.default_input_data_preparer
                                     if input_data_preparer is None
                                     else input_data_preparer)

    @staticmethod
    def default_input_data_preparer(data, _as_target):
        return data

    def __call__(self, data):
        # type: (Value) -> Iterator
        # Note: this empty list is needed if the actual assignment to
        # `values` (within the `with` block) does not occur because of
        # an exception being suppressed by the context manager.
        # noinspection PyUnusedLocal
        values = []
        context_manager = self._cm_factory(data)
        with context_manager as as_target:
            prepared_data = self._input_data_preparer(data, as_target)
            # Note: here all input values are first produced and only
            # then yielded -- because we want to make this converter
            # behave in the "all or nothing" manner (i.e., in the case
            # of an exception, *no* output values are generated, even
            # if some values have been successfully obtained before the
            # exception actually occurred).
            values = list(self._enclosed_converter(prepared_data))
        for val in values:
            yield val

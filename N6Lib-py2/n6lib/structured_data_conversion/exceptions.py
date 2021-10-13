# Copyright (c) 2020-2021 NASK. All rights reserved.

"""
The `structured_data_conversion` package's public exception classes.
"""

from builtins import map                                                         #3--
import collections
import contextlib
from typing import (
    Generator,
    Iterable,
    List,
    Optional,
    Union,
    Mapping,
)

from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import ascii_str
from n6lib.structured_data_conversion.interfaces import NameOrIndex


class DataConversionError(ValueError):

    """
    An exception that is supposed to be raised by converters when
    input data are wrong/invalid. It is expected (though not strictly
    required) that a user-friendly error message will be passed
    as the sole argument passed to the constructor.

    An additional feature: the `sublocation()` class method that
    returns a (single-use) context manager, which should be used by
    converters when entering conversion of some nested stuff whose
    *relative location* (within its parent structure) is a key/name
    (`str`) or an index (`int`). The method should be called with that
    *relative location* (`str` or `int`) as the sole argument; or with
    an iterable collection of such relative locations (`str`/`int`
    objects) if there is an ambiguity which one is the offending
    one (warning: such a collection must *not* be a mapping or a
    `bytes`/`bytearray`);

    thanks to that the `str()` representation of any `DataConversionError`
    raised within one or more `with` blocks of such context managers
    will be automatically prepended with a *location path* pointing to
    the problematic data item in the whole converted structure.

    For example:

    >>> class MyIntegerNumbersListConverter(object):
    ...
    ...     def __call__(self, input_list):
    ...         for index, value in enumerate(input_list):
    ...             with DataConversionError.sublocation(index):
    ...                 yield self._to_integer(value)
    ...
    ...     def _to_integer(self, value):
    ...         try:
    ...             return int(value)
    ...         except ValueError:
    ...             raise DataConversionError(
    ...                '{!r} is not a value that can be converted to '
    ...                'an integer number'.format(value))
    ...
    >>> from n6lib.structured_data_conversion.converters import BaseConverter
    >>> class MyDictOfListsFlatteningConverter(BaseConverter):
    ...
    ...     def __init__(self, sublist_converter_maker, **kwargs):
    ...         # type: (ConverterMaker) -> None
    ...         super(MyDictOfListsFlatteningConverter, self).__init__(**kwargs)
    ...         self._sublist_converter = self.make_subconverter(sublist_converter_maker)
    ...
    ...     def __call__(self, some_input_dict):
    ...         # type: (dict) -> Iterator[int]
    ...         for name, sublist in sorted(some_input_dict.items()):
    ...             with DataConversionError.sublocation(name):
    ...                 self.verify_isinstance(sublist, list)
    ...                 for value in self._sublist_converter(sublist):
    ...                     yield value
    ...
    >>> my_converter = MyDictOfListsFlatteningConverter(
    ...     sublist_converter_maker=MyIntegerNumbersListConverter)
    >>> d1 = {'bar': ['0', '1', '2', '3', '4'], 'foo': ['15', '101']}
    >>> d2 = {'bar': ['0', '1', '2', 'spam', '4'], 'foo': ['15', '101']}
    >>> d3 = {'bar': ['0', '1', '2', '3', '4'], 'foo': ['spam', '101']}
    >>> d4 = {'bar': ['0', '1', '2', '3', '4'], 'foo': {'spam': '101'}}

    >>> list(my_converter(d1))
    [0, 1, 2, 3, 4, 15, 101]

    >>> list(my_converter(d2))   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    DataConversionError: [bar.3] 'spam' is not a value that can be converted to an integer number

    >>> list(my_converter(d3))   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    DataConversionError: [foo.0] 'spam' is not a value that can be converted to an integer number

    >>> list(my_converter(d4))   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    DataConversionError: [foo] unexpected type of {'spam': '101'} (should be a list)

    An example with an iterable collection of name/index alternatives:

    >>> with DataConversionError.sublocation(['spam', 0, 'foo']):
    ...     with DataConversionError.sublocation([]):  # <- empty collection will be skipped
    ...         with DataConversionError.sublocation(['ham']):  # <- single element like scalar
    ...             raise DataConversionError('Aha!')
    ...
    Traceback (most recent call last):
      ...
    DataConversionError: [{spam,0,foo}.ham] Aha!
    """

    def __init__(self, *args):
        super(DataConversionError, self).__init__(*args)
        self._location_path = collections.deque()

    @classmethod
    @contextlib.contextmanager
    def sublocation(cls, name_or_index_or_alternatives_iter):                    #3: `cls,` -> `cls, /,`
        # type: (Union[NameOrIndex, Iterable[NameOrIndex]]) -> Generator[None, None, None]
        path_item = cls._get_ready_path_item(name_or_index_or_alternatives_iter)
        try:
            yield
        except DataConversionError as exc:
            if path_item is not None:
                exc._location_path.appendleft(path_item)
            raise

    @classmethod
    def _get_ready_path_item(cls, name_or_index_or_alternatives_iter):
        # type: (...) -> Optional[Union[NameOrIndex, List[NameOrIndex]]]
        int = type(1), long                                                      #3--
        str = basestring                                                         #3--
        if isinstance(name_or_index_or_alternatives_iter, (str, int)):
            path_item = name_or_index_or_alternatives_iter
            cls._verify_is_name_or_index(path_item)
        else:
            if isinstance(name_or_index_or_alternatives_iter, (Mapping, bytes, bytearray)):
                # (A `Mapping` or `bytes`/`bytearray`? Let's raise an error!)
                cls._verify_is_name_or_index(name_or_index_or_alternatives_iter)
            path_item = list(name_or_index_or_alternatives_iter)
            for name_or_index in path_item:
                cls._verify_is_name_or_index(name_or_index)
            if len(path_item) == 1:
                path_item = path_item[0]
            elif not path_item:
                path_item = None
        return path_item

    @staticmethod
    def _verify_is_name_or_index(name_or_index):
        # type: (NameOrIndex) -> None
        int = type(1), long                                                      #3--
        str = basestring                                                         #3--
        if not isinstance(name_or_index, (str, int)):
            raise TypeError('{!r} is neither a name (`str`) nor an '
                            'index (`int`)'.format(name_or_index))

    __repr__ = attr_repr('args', '_location_path')

    def __str__(self):
        return self._get_location_prefix() + super(DataConversionError, self).__str__()

    def _get_location_prefix(self):
        if self._location_path:
            path_as_ascii_str = '.'.join(map(self._format_path_item, self._location_path))
            return '[{}] '.format(path_as_ascii_str)
        return ''

    def _format_path_item(self, path_item):
        # type: (Union[NameOrIndex, List[NameOrIndex]]) -> str
        int = type(1), long                                                      #3--
        str = basestring                                                         #3--
        if isinstance(path_item, (str, int)):
            return ascii_str(path_item)
        # This is a list of multiple name/index alternatives, so
        # let's present them in the `{foo,bar,spam}`-like form.
        assert (isinstance(path_item, list)
                and all(isinstance(alt, (str, int)) for alt in path_item)
                and len(path_item) > 1), 'bug in implementation of DataConversionError?!'
        return '{' + ','.join(map(ascii_str, path_item)) + '}'

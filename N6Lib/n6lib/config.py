# Copyright (c) 2013-2023 NASK. All rights reserved.

import ast
import collections
import configparser
import contextlib
import functools
import json
import os
import os.path as osp
import pathlib
import re
import sys
import threading
from collections.abc import (
    Iterator,
    Mapping,
    Sequence,
)
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Final,
    Optional,
    Protocol,
    Union,
    overload,
    runtime_checkable,
)

from n6lib.argument_parser import N6ArgumentParser
from n6lib.class_helpers import (
    CombinedWithSuper,
    UnsupportedClassAttributesMixin,
    get_class_name,
)
from n6lib.common_helpers import (
    DictWithSomeHooks,
    as_bytes,
    as_unicode,
    ascii_str,
    import_by_dotted_name,
    make_exc_ascii_str,
    memoized,
    reduce_indent,
    splitlines_asc,
    str_to_bool,
)
from n6lib.const import ETC_DIR, USER_DIR
from n6lib.datetime_helpers import (
    parse_iso_date,
    parse_iso_datetime_to_utc,
)
from n6lib.log_helpers import get_logger



LOGGER = get_logger(__name__)



###
# 0. Monkey-patching helpers
###

# maybe TODO later: deprecate + later remove these legacy behaviors...
def monkey_patch_configparser_to_provide_some_legacy_defaults():
    """
    Monkey-patch `__init__()` of `configparser.RawConfigParser` (and of
    its subclasses) to:

    * make `;`-prefixed inline comments allowed by default, so that all
      our configurations, no matter whether processed by our stuff or
      by third-party modules, will still accept such comments (unless
      explicitly disallowed by setting the `[Raw]ConfigParser`
      constructor's argument `inline_comment_prefixes` to `None).

    * make duplicate section and option names still allowed by default
      (unless explicitly disallowed by setting the `[Raw]ConfigParser`
      constructor's argument `strict` to `True`).
    """

    FLAG_ATTR = '__n6_monkey_patched_to_apply_some_legacy_defaults'

    orig_init = configparser.RawConfigParser.__init__  # noqa
    if getattr(orig_init, FLAG_ATTR, False):
        return

    @functools.wraps(orig_init)
    def patched_init(*args, **kwargs):
        kwargs.setdefault('inline_comment_prefixes', (';',))
        kwargs.setdefault('strict', False)
        orig_init(*args, **kwargs)

    setattr(patched_init, FLAG_ATTR, True)
    configparser.RawConfigParser.__init__ = patched_init



###
# 1. Standard stuff (significant parts are `configparser`-based)
###

OptConverter = Callable[[str], Any]



@runtime_checkable
class ConfigSpecEgg(Protocol):

    r"""
    A [protocol](https://peps.python.org/pep-0544/) of an alternate
    form of a *configuration specification* (aka *config spec*; see
    the docs of the `Config` class to learn what *config specs* are
    in general...).

    An object compliant with the `ConfigSpecEgg` protocol can be used,
    interchangeably with a `str` (with an appropriately formatted
    content), as an object representing a *configuration specification*
    (or formattable *configuration specification pattern* if applicable)
    when making use of the following tools provided by this module: the
    `Config` and `ConfigMixin` classes, as well as the functions:
    `as_config_spec_string()`, `parse_config_spec()`,
    `join_config_specs()` and `combined_config_spec()`.

    The central element of this protocol is the `hatch_out()` method
    (see its signature and docs for more information).

    Note that this protocol is a
    [runtime-checkable](https://docs.python.org/3/library/typing.html#typing.runtime_checkable)
    one.

    ***

    >>> class ExampleConfigSpecEgg:
    ...
    ...     __my_example_spec = '[spam]\nham = {default_ham} :: int'
    ...
    ...     def hatch_out(self, format_data_mapping=None):
    ...         if format_data_mapping is None:
    ...             return self.__my_example_spec
    ...         return self.__my_example_spec.format_map(format_data_mapping)
    ...
    >>> egg = ExampleConfigSpecEgg()
    >>> isinstance(egg, ConfigSpecEgg)  # (works because the protocol is runtime-checkable)
    True
    >>> egg.hatch_out()
    '[spam]\nham = {default_ham} :: int'
    >>> egg.hatch_out({'default_ham': 42})
    '[spam]\nham = 42 :: int'
    >>> egg.hatch_out(format_data_mapping={'default_ham': 42})
    '[spam]\nham = 42 :: int'
    """

    def hatch_out(self,
                  format_data_mapping: Optional[Mapping[str, Any]] = None) -> str:
        """
        Obtain a *configuration specification* string (or *configuration
        specification pattern* string) that is "virtually" represented
        by a `ConfigSpecEgg`-compliant object on which this method is
        invoked.

        ***

        Any `ConfigSpecEgg`-compliant object is supposed to represent a
        certain *configuration specification* string or *configuration
        specification pattern* string, even though the string itself
        does not need to be stored -- as "materialization" of it (or
        "hatching out") can be deferred until this method is invoked.
        That is, execution of this method is the last moment when the
        underlying data (whatever form it takes) needs to be processed
        to produce a plain string.

        In other words, before a call to this method a *configuration
        specification* (or *configuration specification pattern*)
        represented by the object may be "virtual", but such a call
        extracts from it its "concrete" form (a `str`).

        In still other words: a *config spec* string (or *config spec
        pattern* string) "hatches" from the *config spec egg*.

        ***

        Args/kwargs:
            `format_data_mapping` (a mapping or `None`; default: `None`):
                If the argument is given and not `None` then the
                resultant string should be a *configuration
                specification* that "hatched" involving a
                `str.format_map()`-like operation equivalent
                to `<the underlying "virtual" config spec
                pattern>.format_map(format_data_mapping)`.

                If the argument is `None` (or not given) then
                the resultant string should be the underlying
                *configuration specification* (or *configuration
                specification pattern*) that "hatched" *without*
                any such `str.format_map()`-like operation.

        Returns:
            The "hatched" *configuration specification* (or
            *configuration specification pattern*), being a
            plain `str`.

        Raises:
            The exact type is implementation-dependant; preferably:
            `ConfigSpecEggError` or a subclass of it (unless there is
            a good reason to raise some other exception).

        ***

        *Important:*

        * It should be assumed that this method may be invoked multiple
          times on the same `ConfigSpecEgg`-compliant object, to obtain
          results based on the same underlying object's data (possibly
          with different values of the `format_data_mapping` argument,
          if given); so implementations should treat the `self` object
          as immutable, or at least ensure that a call to this method
          never changes the object's state in a way that could affect
          results of any further calls.

        * Unless there is a specific reason to do otherwise, the
          `format_data_mapping` object *itself*, if not None, should be
          used to perform all `str.format_map()`-like operations on (any
          underlying) *config spec pattern(s)* -- to let any features
          and side effects provided by the type of that mapping object
          (which does not need to be a plain `dict`!) be used/take place
          *regarding that particular mapping object*, during all that
          operations.

        ***

        *Additional note:*

        When, in your client code, you need to obtain a *config spec*
        (or a formattable *config spec pattern*) as a string -- from a
        *config spec* (or, respectively, *config spec pattern*) which
        may be either an egg (`ConfigSpecEgg`-compliant object) or a
        string -- then it is recommended to use the utility function
        `as_config_spec_string()`; by using that function you are able
        to treat the input value uniformly regardless of whether it is
        an egg or a string (the function takes care of doing the right
        thing, in particular, by invoking the `hatch_out()` method if
        the argument is an egg). This advice regards also obtaining a
        formatted *config spec* from a formattable *config spec pattern*
        (regardless whether an egg or a string is given): in such a case
        just pass your *format data mapping* as the second argument to
        the `as_config_spec_string()` function (see also its docs).
        """
        raise NotImplementedError



class ConfigSpecEggError(Exception):
    """
    The preferred class of exceptions raised by concrete implementations
    of the `ConfigSpecEgg.hatch_out()` method (see its docs).
    """



class ConfigError(Exception):

    """
    A generic, `Config`-related, exception class.

    >>> print(ConfigError('Some Message'))
    [configuration-related error] Some Message

    >>> from decimal import Decimal as D
    >>> print(ConfigError('Some arg', D(42), 'Yet another arg'))
    [configuration-related error] ('Some arg', Decimal('42'), 'Yet another arg')
    """

    def __str__(self):
        return '[configuration-related error] ' + super().__str__()



_KeyError_str = getattr(KeyError.__str__, '__func__', KeyError.__str__)

class _KeyErrorSubclassMixin(KeyError):  # a non-public helper

    def __str__(self):
        # Rationale: we want to *avoid* use of the `KeyError`'s
        # implementation of `__str__()` because that implementation
        # -- contrary to what `Exception.__str__()` does -- applies
        # `repr()` (instead of `str()`) to the value of the exception
        # Constructor's argument also when it is the only argument.
        # So here we *skip* that implementation in the MRO of the
        # exception class.
        method = super().__str__
        if getattr(method, '__objclass__', None) is KeyError or (
              # (Let's perform also a *pure-Python* version of this check
              # -- for compatibility with non-CPython, e.g., PyPy, just
              # in case it is ever used by us...)
              _KeyError_str is not None and
              _KeyError_str is getattr(method, '__func__', None)):
            # Note: here the first argument passed to `super()` is
            # `KeyError`, *not* the current class (!).
            method = super(KeyError, self).__str__
        return method()



class NoConfigSectionError(_KeyErrorSubclassMixin, ConfigError):

    """
    Raised by `Config.__getitem__()` when the specified section is missing.

    >>> exc = NoConfigSectionError('some_sect')
    >>> isinstance(exc, ConfigError) and isinstance(exc, KeyError)
    True
    >>> print(exc)
    [configuration-related error] no config section `some_sect`
    >>> exc.sect_name
    'some_sect'

    >>> exc2 = NoConfigSectionError()
    >>> print(exc2)
    [configuration-related error] no config section <unspecified>
    >>> exc2.sect_name is None
    True

    >>> from decimal import Decimal as D
    >>> exc3 = NoConfigSectionError('some_sect', 'arg', D(42))
    >>> print(exc3)
    [configuration-related error] ('no config section `some_sect`', 'arg', Decimal('42'))
    >>> exc3.sect_name
    'some_sect'
    """

    sect_name: Optional[str]

    def __init__(self, sect_name=None, *args):
        sect_ref = f'`{sect_name}`' if sect_name is not None else '<unspecified>'
        msg = f'no config section {sect_ref}'
        super().__init__(msg, *args)
        self.sect_name = sect_name



class NoConfigOptionError(_KeyErrorSubclassMixin, ConfigError):

    """
    Raised by `ConfigSection.__getitem__()` when the specified option is missing.

    >>> exc = NoConfigOptionError('mysect', 'myopt')
    >>> isinstance(exc, ConfigError) and isinstance(exc, KeyError)
    True
    >>> print(exc)
    [configuration-related error] no config option `myopt` in section `mysect`
    >>> exc.sect_name
    'mysect'
    >>> exc.opt_name
    'myopt'

    >>> exc2 = NoConfigOptionError()
    >>> print(exc2)
    [configuration-related error] no config option <unspecified> in section <unspecified>
    >>> exc2.sect_name is None and exc2.opt_name is None
    True

    >>> from decimal import Decimal as D
    >>> exc3 = NoConfigOptionError('S', 'o', D(42))
    >>> print(exc3)
    [configuration-related error] ('no config option `o` in section `S`', Decimal('42'))
    >>> exc3.sect_name
    'S'
    >>> exc3.opt_name
    'o'
    """

    sect_name: Optional[str]
    opt_name: Optional[str]

    def __init__(self, sect_name=None, opt_name=None, *args):
        sect_ref = f'`{sect_name}`' if sect_name is not None else '<unspecified>'
        opt_ref = f'`{opt_name}`' if opt_name is not None else '<unspecified>'
        msg = f'no config option {opt_ref} in section {sect_ref}'
        super().__init__(msg, *args)
        self.sect_name = sect_name
        self.opt_name = opt_name



class Config(DictWithSomeHooks):

    r"""
    Parse the configuration and provide a `dict`-like access to it.

    `Config` is a subclass of `dict`.  Generally, `Config` instances
    behave like a `dict`; lookup-by-key failures are signalled with
    `NoConfigSectionError` which is a subclass of both `KeyError`
    and `ConfigError`.  A `Config` instance maps configuration
    section names (`str`) to `ConfigSection` instances.

    There are two main ways of `Config` instantiation:

    * the modern (recommended) way -- with so called *configuration
      specification* as the obligatory argument (`config_spec`) and
      a few optional keyword arguments (see the "Modern way of
      instantiation" section below).

    * the legacy (obsolete) way -- with exactly one argument
      (`required`) whose value is a `dict` that maps required
      section names to sequences of required option names (see
      the "Legacy way of instantiation" section below).


    Modern way of instantiation (recommended)
    -----------------------------------------

    Args (positional-only):
        `config_spec` (a `str` or `ConfigSpecEgg`-compliant object):
            The *configuration specification* (aka *config spec*) in a
            format which is somewhat similar to the `configparser`-like
            `*.ini`-format.  Such a specification defines: what config
            sections are to be included, what config options are legal,
            what config options are required, how values of particular
            config options shall be converted (e.g., coerced to `int` or
            `bool`...).  See the "Configuration specification format"
            section below.

            *Note*: unlike some other tools provided by this module, the
            `Config` class by itself supports only ready *configuration
            specifications*, not formattable *configuration specification
            patterns* (but, obviously, an already formatted configuration
            specification based on such a pattern is perfectly OK).

    Kwargs (all optional):
        `settings` (a mapping or `None`; default: `None`):
            Depending on the value of the argument:

            * if it is `None` (the default value), the configuration will
              be loaded from all files that:

              * reside in the "/etc/n6" or "~/.n6" directories, or any
                subdirectories of them (recursively...), *and*

              * have a name matching the regular expression specified
                by the `config_filename_regex` argument (by default:
                a string starting with two ASCII digits followed by
                '_', and ending with '.conf') and -- at the same
                time -- *not* matching the regex specified by the
                `config_filename_excluding_regex` argument (by default:
                a string starting with 'logging.' or 'logging-');

              this is so called "N6DataPipeline way" of obtaining the
              configuration;

              NOTE that all normal `configparser` processing is done
              (in its modern-Python 3.x-specific flavor, except that
              `;`-prefixed inline comments are still enabled and
              duplicate section or option names are still allowed);
              especially option names (but *not* section names) are
              normalized to lowercase;

            * if not `None`, it must be a Pyramid-like settings mapping
              (e.g., `dict`) -- that maps '<section name>.<option name>'
              strings to raw option value strings; the configuration
              will be taken from the mapping, *not* from any files;

              this is so-called "Pyramid way" of obtaining the
              configuration; then `settings` is typically a `dict` whose
              content is the result of parsing the `[app:main]` part of
              a Pyramid "*.ini" file in which each option is specified
              in the `<section name>.<option name> = <option value>`
              format;

              NOTE: option names taken from `settings` (contrary
              to option names from configuration files residing in
              "/etc/n6" or "~/.n6", or their subdirectories...) are
              *not* normalized to lowercase; on the other hand, any
              non-`str` option values (if any) -- before being converted
              (see below: the description of the `custom_converters`
              argument) -- are coerced to `str` (especially, `bytes`
              and `bytearray` values are decoded to `str` using the
              UTF-8 encoding).

        `custom_converters` (a mapping or `None`; default: `None`):
            If not `None` it must be a mapping (e.g., `dict`) that maps
            custom converter names (of type `str`) to actual converter
            callables. Such a callable (e.g., a function) must take one
            argument being a `str` instance and return a value of some
            type.  By default, only converters defined in the
            `Config.BASIC_CONVERTERS` mapping (that maps standard
            converter names to their callables) can be used to convert
            values of raw options (options are marked in `config_spec`
            with a particular converter name, aka *converter spec*) to
            actual values; if a `custom_converters` mapping is specified,
            the converters it contains can also be used (they can even
            override converters defined in `Config.BASIC_CONVERTERS`,
            though such a practice is *not* recommended).  See also the
            "Configuration specification format" and "Standard converter
            specs" sections below.

        `config_filename_regex` (a `str` or `re.Pattern`, or `None`; default: `None`):
            Configuration may be loaded *only* from those files whose
            names match this regular expression. `None` is equivalent
            to the value of `Config.DEFAULT_CONFIG_FILENAME_REGEX`. The
            argument is relevant only when the "N6DataPipeline way" of
            obtaining the configuration is in use (i.e., if `settings`
            is `None`), otherwise it is ignored.

        `config_filename_excluding_regex` (a `str` or `re.Pattern`, or `None`; default: `None`):
            Configuration will *never* be loaded from any files whose
            names match this regular expression. `None` is equivalent to
            the value of `Config.DEFAULT_CONFIG_FILENAME_EXCLUDING_REGEX`.
            The argument is relevant only when the "N6DataPipeline way"
            of obtaining the configuration is in use (i.e., if `settings`
            is `None`), otherwise it is ignored.

    Raises:
        Any exception from `parse_config_spec(config_spec)`:
            see the docs of the `parse_config_spec()` function.

        `ConfigError`:
            for any configuration-related error (with an error message
            describing what is the problem).


    NOTE:

    * The resultant Config instance contains only sections that are
      contained by `config_spec`.

    * Option values are converted (see: the description of the
      `custom_converters` argument above) according to the specified
      `config_spec`, using `Config.BASIC_CONVERTERS` (optionally, also
      `custom_converters` -- described above).

    (Compare the above notes with those in the "Legacy way of
    instantiation" section below.)


    Examples:

        config_spec = '''
            [first]
            foo = bar          ; no converter spec, default value: 'bar'
            spam = 42 :: int   ; converter spec: int, default value: 42

            [second]
            spam :: float      ; converter spec: float, no default value (required)
            boo = yes :: bool  ; converter spec: bool, default value: True
        '''

        # from config files:
        my_config = Config(config_spec)

        # from a Pyramid-like `settings` mapping:
        my_config = Config(config_spec, settings={
            'first.foo': 'two bars',
            'first.spam': '43',       # note: this is a raw value (str)
            'second.spam': '44.2',    # note: this is a raw value (str)
        })

    Then you can easily get the needed information:

        first_section = my_config['first']
        foo = first_section['foo']
        # or just:
        foo = my_config['first']['foo']


    See also: the `ConfigMixin` class which makes `Config` instantiation
    (the modern variant) as convenient as possible.


    Convenience class method: `Config.section()`
    --------------------------------------------

    There is also a convenience solution for (frequent) cases when there
    is only one section in the *config spec* -- so you are interested
    directly in the `ConfigSection` object (the only one) rather than in
    its "parent" `Config` object: the `Config.section()` class method.

    Example:

        simple_config_spec = '''
            [the]
            foo = bar
            spam = 42 :: int
        '''
        the_section = Config.section(simple_config_spec,
                                     settings={'the.foo': 'Xyz'})
        assert the_section['foo'] == 'Xyz'
        assert the_section['spam'] == 42

    See also: the `ConfigMixin` class which makes creating a
    `ConfigSection` based on a *config spec* even more convenient.


    Configuration specification format
    ----------------------------------

    The syntax of *configuration specification* (aka *config spec*)
    strings is similar to the standard `*.ini`-format config syntax --
    with the proviso that:

    * the value of an option specifies its default value;

    * it can be followed by `:: <converter_spec>` where `<converter_spec>`
      is a name of a value converter (such as `int`, `float`, `bool`
      etc.; in particular, see the "Standard converter specs" section
      below);

    * if the default value is not specified (i.e., the *no-value* option
      syntax is used) the `:: <config_spec>` part can follow just the
      option name;

    * a `...` marker can be used instead of an option name; if it is
      present in a particular section then that section is allowed to
      contain "free" (aka "arbitrary") options, i.e., some options that
      are not declared in the section specification; otherwise *only*
      explicitly specified options are legal;

    * a `...` marker can be followed by `:: <converter_spec>` -- then
      the specified value converter will be applied to all "free"
      ("arbitrary") options in a particular section;

    * the whole string must not contain any *reserved characters*, i.e.,
      any of `Config.CONFIG_SPEC_RESERVED_CHARS` (which are `\x00` and
      `\x01`, that is, the characters whose ASCII codes are, respectively,
      0 and 1);

    * the crux of the configuration specification *parsing algorithm* is
      implemented in a (non-public) subclass of the `ConfigString` class
      (which is *not* based on the standard `configparser` stuff; see
      the docs of `ConfigString` for information on some, non-major,
      syntactic differences);

    * the whole operation of parsing a *config spec* (normally, run by
      the machinery of `Config`) is exposed as the `parse_config_spec()`
      utility function (see also its docs, in particular, the examples
      included there...).

    Example:

        config_spec = '''
            [some_section]
            some_opt = default val :: bool   ; default value + converter spec
            another_opt = its default val    ; default value, no converter spec
            required_without_default :: int  ; converter spec, no default value
            another_required_opt             ; no converter spec, no default value
            ...           ; `...` means that other (arbitrary) options are allowed in this section

            [another_section]
            some_required_opt :: bool
            yet_another_option : yes :: date
            # below: `...` with a converter spec -- means that other
            # (arbitrary) options are allowed is this section *and* that
            # the specified converter shall be applied to their values
            ... :: bool

            [yet_another_section]
            some_required_opt
            a_few_numbers = 1, 2, 3, 44 :: list_of_int
            # note: lack of `...` means that only the `some_required_opt` and
            # `a_few_numbers` options are allowed in this section
        '''


    Standard converter specs
    ------------------------

    There is a set of converters that are accessible out-of-the-box
    (they are defined in the `Config.BASIC_CONVERTERS` constant).

    Below -- the standard converter specs with conversion examples:

    `str`:
        `"abc ś"` -> `"abc ś"`
        (practically, it is a "do nothing" conversion)

    `bytes`:
        `"abc ś"` -> `b"abc \xc5\x9b"`
        (implementation: `n6lib.common_helpers.as_bytes()`)

    `bool`:
        `"true"` or `"t"` or `"yes"` or `"y"` or `"on"` or `"1"` -> `True`
        `"false"` or `"f"` or `"no"` or `"n"` or `"off"` or `"0"` -> `False`
        (case-insensitive, so uppercase letters are also OK;
        implementation: `n6lib.common_helpers.str_to_bool()`)

    `int`:
        `"42"` -> `42`
        `"-42"` -> `-42`

    `float`:
        `"42"` -> `42.0`
        `"-42.2"` -> `-42.2`

    `date`:
        `"2010-07-19"` -> `datetime.date(2010, 7, 19)`
        (implementation: `n6lib.datetime_helpers.parse_iso_date()`)

    `datetime`:
        `"2010-07-19 12:39:45+02:00"`
        -> `datetime.datetime(2010, 7, 19, 10, 39, 45)`
        (note: normalizing timezone to UTC; implementation:
        `n6lib.datetime_helpers.parse_iso_datetime_to_utc()`)

    `path`:
        `"/spam"` -> `pathlib.Path("/spam")`
        `"/spam/"` -> `pathlib.Path("/spam")`
        `"/spam/pram"` -> `pathlib.Path("/spam/pram")`
        `"~/foo/bar" -> `pathlib.Path("/home/currentuser/foo/bar")`
        `"~someuser/foo/bar" -> `pathlib.Path("/home/someuser/foo/bar")`
        (implementation uses `pathlib.Path` + its method `expanduser()`)

    `list_of_str`:
        `"a, b, c, d, e,"`  -> `["a", "b", "c", "d", "e"]`
        `"a,b,c,d,e"`       -> `["a", "b", "c", "d", "e"]`
        `" a, b,c,d , e, "` -> `["a", "b", "c", "d", "e"]`

    `list_of_bytes`:
        `" a, b,c,d , e, "` -> `[`b"a", b"b", b"c", b"d", b"e"]`

    `list_of_bool`:
        `"yes,No , True ,OFF"` -> `[True, False, True, False]`

    `list_of_int`:
        `"42,43,44,"` -> `[42, 43, 44]`

    `list_of_float`:
        `" 0.2 , 0.4 "` -> `[0.2, 0.4]`

    `list_of_date`:
        `"2010-07-19, 2011-08-20"`
        -> `[datetime.date(2010, 7, 19), datetime.date(2010, 7, 20)]`

    `list_of_datetime`:
        `"2010-07-19 12:39:45+02:00,2011-08-20T23:23,"`
        -> `[datetime.datetime(2010, 7, 19, 10, 39, 45),
             datetime.datetime(2010, 7, 20, 23, 23)]`

    `list_of_path`:
        `"/spam, /pram/,/spam/pram,~/foo/bar , "~someuser/foo/bar"`
        -> `[pathlib.Path("/spam"),
             pathlib.Path("/pram"),
             pathlib.Path("/spam/pram"),
             pathlib.Path("/home/currentuser/foo/bar"),
             pathlib.Path("/home/someuser/foo/bar")]`

    `importable_dotted_name`:
        `"sqlalchemy.orm.properties.ColumnProperty"`
        -> <the `ColumnProperty` class from the `sqlalchemy.orm.properties` module>
        (implementation: `n6lib.common_helpers.import_by_dotted_name()`)

    `py`:
        `"[('a',), {42: None}]"` -> `[("a",), {42: None}]`
        (accepts any Python literal; implementation makes use of
        `ast.literal_eval()`)

    `py_namespaces_dict`:
        `"{'spam': [42, 43, 44], 'ham': {'a': 45.6789}"`
        -> `{'spam': [42, 43, 44], 'ham': {'a': 45.6789}`
        (same as `py` but accepts only a literal of a `dict`
        whose all keys are `str` instances; values can be of
        any literal-representable types, except that those being
        `dict`s must obey the same restrictions, recursively...)

    `json`:
        `'[["a"], {"b": null}]'` -> `[['a'], {'b': None}]`
        (implementation uses `json.loads()`)

    All `list_of_...` converters are implemented using the
    `Config.make_list_converter()` static method; you can
    use it to implement your own custom *list-of* converters.


    Legacy way of instantiation (obsolete)
    --------------------------------------

    Args/kwargs:
        `required` (a `dict`):
            A dictionary that maps required section names (`str`) to
            sequences (such as tuples or lists) of required option
            names (`str`), e.g.: `{'section1': ('opt1', 'opt2'),
            'section2': ['another_opt']}`.  Note that any other
            section/option names are legal and the resultant
            `Config` will contain them as well.

    Raises:
        `SystemExit` (!):
            if any required section/option is missing.
        `configparser.Error` (or any of its subclasses):
            if a config file cannot be properly parsed.

    NOTE:

    * The resultant `Config` instance contains all sections and options --
      from all read files.

    * All resultant option values are just strings (*no* conversion is
      performed).

    (Compare the above notes with those in the "Modern way of
    instantiation" section above.)


    Override config values for particular script run
    ------------------------------------------------

    If a script uses the "N6DataPipeline way" of obtaining the
    configuration (i.e., reads it from files in "/etc/n6/", "~/.n6/",
    etc.) -- no matter whether the *modern* or the *legacy* variant of
    instantiation is employed -- it is possible to override selected
    config options *for a particular script run* using the command-line
    argument `--n6config-override`.

    Check `n6lib.argument_parser.N6ArgumentParser` for more information.

    **Important proviso**: the *logging configuration* options are read
    and parsed by a machinery which is completely *separate* from the
    `n6lib.config.Config`-related stuff -- therefore you **cannot** use
    the `--n6config-override` command line argument to override logging
    configuration options.
    """


    #
    # Option-value-conversion-related internal helpers
    #

    # internal sentinel object
    __NOT_CONVERTED = object()

    # noinspection PyMethodParameters
    def __path_with_expanded_user_converter(s):
        assert isinstance(s, str)
        if not s.strip():
            raise ValueError('path is not allowed to be empty or whitespace-only')
        p = pathlib.Path(s)
        p = p.expanduser()
        if not os.fspath(p).strip():  # (should not happen, but just in case...)
            raise ValueError('path is not allowed to be empty or whitespace-only')
        if not p.is_absolute():
            raise ValueError('path is required to be absolute (not relative)')
        return p

    # noinspection PyMethodParameters
    def __make_list_converter(item_converter, name=None, delimiter=','):

        def converter(s):
            s = s.strip()
            if s.endswith(delimiter):
                # remove trailing delimiter
                s = s[:-len(delimiter)].rstrip()
            if s:
                # noinspection PyCallingNonCallable
                return [item_converter(item.strip())
                        for item in s.split(delimiter)]
            else:
                return []

        if name is None:
            base_name = getattr(item_converter, '__name__', get_class_name(item_converter))
            name = '__{0}__list__converter'.format(base_name)
        converter.__name__ = name
        converter.item_converter = item_converter
        converter.delimiter = delimiter
        return converter

    # noinspection PyMethodParameters
    def __py_literal_converters():

        def py(s):
            return _literal_eval(as_unicode(s).strip())

        def py_namespaces_dict(s):
            val = py(s)
            if not isinstance(val, dict):
                raise TypeError('not a dict')
            _verify_namespaces_recursively(val)
            return val

        _literal_eval = ast.literal_eval

        def _verify_namespaces_recursively(di, ref_word='dict'):
            assert isinstance(di, dict)
            items = sorted(di.items())
            non_str_keys = [key for key, _ in items if not isinstance(key, str)]
            if non_str_keys:
                raise _NonStrKey(
                    'this {} should contain only string keys '
                    '(but contains some non-string ones: {})'.format(
                        ref_word,
                        ', '.join(map(ascii, non_str_keys))))
            for key, val in items:
                if isinstance(val, dict):
                    try:
                        _verify_namespaces_recursively(val, ref_word='subdict')
                    except _NonStrKey as exc:
                        raise _NonStrKey('for key {!a} -> {}'.format(key, exc)) from None

        class _NonStrKey(TypeError):
            pass

        return {
            'py': py,
            'py_namespaces_dict': py_namespaces_dict,
        }


    #
    # Public interface
    #

    #
    # Public constants (should never be modified in-place or replaced!)

    # (characters not allowed in *config specs*, as they
    # are reserved for this module's internal purposes)
    CONFIG_SPEC_RESERVED_CHAR_00: Final[str] = '\x00'
    CONFIG_SPEC_RESERVED_CHAR_01: Final[str] = '\x01'
    CONFIG_SPEC_RESERVED_CHARS: Final[frozenset[str]] = frozenset({
        CONFIG_SPEC_RESERVED_CHAR_00,
        CONFIG_SPEC_RESERVED_CHAR_01,
    })

    DEFAULT_CONVERTER_SPEC: Final[str] = 'str'
    BASIC_CONVERTERS: Final[Mapping[str, OptConverter]] = dict({
        'str': str,
        'bytes': as_bytes,
        'bool': str_to_bool,
        'int': int,
        'float': float,
        'date': parse_iso_date,
        'datetime': parse_iso_datetime_to_utc,
        'path': __path_with_expanded_user_converter,
        'list_of_str': __make_list_converter(str, 'list_of_str'),
        'list_of_bytes': __make_list_converter(as_bytes, 'list_of_bytes'),
        'list_of_bool': __make_list_converter(str_to_bool, 'list_of_bool'),
        'list_of_int': __make_list_converter(int, 'list_of_int'),
        'list_of_float': __make_list_converter(float, 'list_of_float'),
        'list_of_date': __make_list_converter(parse_iso_date, 'list_of_date'),
        'list_of_datetime': __make_list_converter(parse_iso_datetime_to_utc, 'list_of_datetime'),
        'list_of_path': __make_list_converter(__path_with_expanded_user_converter, 'list_of_path'),
        'importable_dotted_name': import_by_dotted_name,
        'json': json.loads,
    }, **__py_literal_converters())
    assert DEFAULT_CONVERTER_SPEC in BASIC_CONVERTERS

    DEFAULT_CONFIG_FILENAME_REGEX: Final[str] = r'\A[0-9][0-9]_.*\.conf\Z'
    DEFAULT_CONFIG_FILENAME_EXCLUDING_REGEX: Final[str] = r'\Alogging[-.]'


    #
    # Public static method

    make_list_converter = staticmethod(__make_list_converter)


    #
    # Construction-and-initialization-related public stuff

    @overload
    def __init__(self,
                 config_spec: Union[str, ConfigSpecEgg],
                 /,
                 *,
                 settings: Optional[Mapping] = None,
                 custom_converters: Optional[Mapping[str, OptConverter]] = None,
                 config_filename_regex: Optional[Union[str, re.Pattern[str]]] = None,
                 config_filename_excluding_regex: Optional[Union[str, re.Pattern[str]]] = None):
        """
        The *modern* way of instantiation of `Config` (see its main docs).
        """

    @overload
    def __init__(self, required: dict[str, Sequence[str]]):
        """
        The *legacy* way of instantiation of `Config` (see its main docs).
        """

    def __init__(self, /, *args, **kwargs):                             # noqa
        self._common_preinit()
        if self._are_init_arguments_for_legacy_init(args, kwargs):
            self._legacy_init(*args, **kwargs)
        else:
            self._modern_init(*args, **kwargs)                          # noqa


    @classmethod
    def section(cls, /, *args, **kwargs):
        """
        A class method that creates a `Config` and picks its sole section.

        This method exists just for convenience.  It requires that the
        *config spec* contains exactly one config section.

        Args/kwargs:
            Like for the `Config` constructor when the *modern way of
            instantiation* is aimed (see the main docs of `Config`).

        Returns:
            A ConfigSection instance.

        Raises:
            `ConfigError` -- also if there is no config section or more
            than one config section.

        A few minor examples:

            >>> config_spec = '''
            ... [foo]
            ... abc = 42 :: int'''
            >>> s = {'foo.abc': '123'}
            >>> Config.section(config_spec, settings=s)
            ConfigSection('foo', {'abc': 123})

            >>> config_spec = ''
            >>> Config.section(config_spec, settings=s)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
              ...
            n6lib.config.ConfigError: ...but no sections found

            >>> config_spec = '''
            ... [foo]
            ... abc = 42 :: int
            ... [bar]'''
            >>> Config.section(config_spec, settings=s)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
              ...
            n6lib.config.ConfigError: ...but the following sections found: 'bar', 'foo'

        See also: `ConfigMixin.get_config_section()`.
        """
        new = cls.__new__(cls)
        new._common_preinit()
        new._modern_init(*args, **kwargs)                               # noqa
        try:
            [section] = new.values()
        except ValueError:
            all_sections = sorted(new)
            sections_descr = (
                'the following sections found: {0}'.format(
                    ', '.join(map(repr, map(ascii_str, all_sections))))
                if all_sections else 'no sections found')
            raise ConfigError(
                'expected config spec that defines '
                'exactly one section but ' + sections_descr) from None
        return section


    @classmethod
    def make(cls, /, *args, **kwargs):
        """
        An alternative (`dict`-like) constructor.

        (Useful mainly in unit tests.)

        Args/kwargs:
            Like for `dict()` or `dict.update()` -- except that keys (of
            the resultant mapping) are required to be `str` instances
            and values are required to be *either* mappings whose keys
            are `str` instances, *or* iterables of `(<key being a `str`
            instance>, <value (being anything)>)` pairs (here "pair"
            means: a 2-tuple or any other 2-element iterable).

        Returns:
            A new `Config` instance (whose values are new `ConfigSection`
            instances).

        Raises:
            `TypeError`:
                if any non-`str` key is detected in the resultant
                mapping or in any of the mappings being its values
                (see the relevant examples below).
            `TypeError` or `ValueError` (adequately):
                if the given args are not *appropriate for a dict of
                dicts* (see the relevant examples below).

        >>> Config.make()
        Config(<{}>)

        >>> Config.make({'abc': {'k': 'v'}})
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> Config.make({'abc': [('k', 'v')]})
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> Config.make([('abc', {'k': 'v'})])
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> Config.make(iter([('abc', [('k', 'v')])]))
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> Config.make(abc={'k': 'v'})
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> Config.make(abc=iter([iter('kv')]))
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)

        >>> sect = ConfigSection('abc', {'k': 'v'})
        >>> c1 = Config.make({'abc': sect})
        >>> c1
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> c1['abc'] == sect and c1['abc'] is not sect
        True
        >>> c2 = Config.make([('abc', sect)])
        >>> c2
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> c2['abc'] == sect and c2['abc'] is not sect
        True
        >>> c3 = Config.make(abc=sect)
        >>> c3
        Config(<{'abc': ConfigSection('abc', {'k': 'v'})}>)
        >>> c3['abc'] == sect and c3['abc'] is not sect
        True

        >>> Config.make({'abc': {}})
        Config(<{'abc': ConfigSection('abc', {})}>)
        >>> Config.make({'abc': []})
        Config(<{'abc': ConfigSection('abc', {})}>)
        >>> Config.make([('abc', {})])
        Config(<{'abc': ConfigSection('abc', {})}>)
        >>> Config.make([('abc', [])])
        Config(<{'abc': ConfigSection('abc', {})}>)
        >>> Config.make(abc={})
        Config(<{'abc': ConfigSection('abc', {})}>)
        >>> Config.make(abc=[])
        Config(<{'abc': ConfigSection('abc', {})}>)

        >>> from decimal import Decimal as D
        >>> Config.make({'abc': {'k': 'v'}}, abc={'kk': D(42)})
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make({'abc': {'k': 'v'}}, abc=[('kk', D(42))])
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make({'abc': [('k', 'v')]}, abc={'kk': D(42)})
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make({'abc': [('k', 'v')]}, abc=[('kk', D(42))])
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make([('abc', {'k': 'v'})], abc={'kk': D(42)})
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make([('abc', {'k': 'v'})], abc=[('kk', D(42))])
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make([('abc', [('k', 'v')])], abc={'kk': D(42)})
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)
        >>> Config.make([('abc', [('k', 'v')])], abc=[('kk', D(42))])
        Config(<{'abc': ConfigSection('abc', {'kk': Decimal('42')})}>)

        >>> Config.make({D(42): {'k': 'v'}})
        Traceback (most recent call last):
          ...
        TypeError: key Decimal('42') is not a `str`
        >>> Config.make({'abc': {D(42): 'v'}})
        Traceback (most recent call last):
          ...
        TypeError: key Decimal('42') is not a `str`
        >>> Config.make(D(42))                           # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...
        >>> Config.make({'abc': D(42)})                  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...
        >>> Config.make({'abc': [D(42)]})                # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...

        >>> Config.make([('k', 'v', 'extra')])           # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ValueError: ...
        >>> Config.make({'abc': [('k', 'v', 'extra')]})  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ValueError: ...
        """
        new = cls.__new__(cls)
        new._common_preinit(
            super_init_args=args,
            super_init_kwargs=kwargs)
        for sect_name, opt_name_to_value in new.items():
            sect = ConfigSection(sect_name, opt_name_to_value)
            keys = [sect_name]
            keys.extend(sect.keys())
            for key in keys:
                if not isinstance(key, str):
                    raise TypeError('key {0!a} is not a `str`'.format(key))
            new[sect_name] = sect
        return new


    @classmethod
    @contextlib.contextmanager
    def overriden_init_defaults(cls, **new_defaults):
        r"""
        A class method which returns a context manager that makes it
        possible to temporarily override (globally, for all threads!)
        the default values of `Config`'s/`Config.section()`'s optional
        arguments (regarding *only* the *modern way of instantiation*).

        Kwargs (each optional):
            Same as those you can pass to the `Config` constructor
            (regarding the *modern way of instantiation*).

        The resultant context manager's `__enter__()` method returns
        a dictionary those content reflects the current overrides of
        `Config`'s/`Config.section()`'s optional arguments (see the
        examples below...). The dictionary is intended to be used for
        informational purposes only; mutating it will have no effect on
        the state of the overrides; mutating the objects it contains may
        have such an effect, but is discouraged.

        ***

        A few examples:

            >>> config_spec = '''
            ... [foo]
            ... abc = 42 :: int
            ... spam = BAR :: bytes
            ... '''
            >>> with Config.overriden_init_defaults(
            ...        settings={'foo.abc': '123'}) as override_info:
            ...     # (here we can place any operations that may make
            ...     # `Config()`/`Config.section()` be invoked, possibly
            ...     # indirectly, including `ConfigMixin`-derived stuff)
            ...     config_full = Config(config_spec)
            ...     config_section = Config.section(config_spec)
            ...
            >>> config_full
            Config(<{'foo': ConfigSection('foo', {'abc': 123, 'spam': b'BAR'})}>)
            >>> config_section
            ConfigSection('foo', {'abc': 123, 'spam': b'BAR'})
            >>> override_info
            {'settings': {'foo.abc': '123'}}

            >>> class _ContrivedConverter:
            ...     def __call__(self, s): return f'contrived {s}'.encode('utf-8')
            ...     def __repr__(self): return f'{type(self).__qualname__}()'
            ...
            >>> with Config.overriden_init_defaults(
            ...        settings={'foo.abc': '123'},
            ...        custom_converters={'bytes': _ContrivedConverter()}) as override_info_1, \
            ...      Config.overriden_init_defaults(    # Note: here we have a few nested contexts.
            ...        settings={'foo.abc': '-1'}) as override_info_2:
            ...     config_full = Config(config_spec)
            ...     config_section = Config.section(config_spec)
            ...
            >>> config_full
            Config(<{'foo': ConfigSection('foo', {'abc': -1, 'spam': b'contrived BAR'})}>)
            >>> config_section
            ConfigSection('foo', {'abc': -1, 'spam': b'contrived BAR'})
            >>> override_info_1
            {'settings': {'foo.abc': '123'}, 'custom_converters': {'bytes': _ContrivedConverter()}}
            >>> override_info_2
            {'settings': {'foo.abc': '-1'}, 'custom_converters': {'bytes': _ContrivedConverter()}}

            >>> with Config.overriden_init_defaults(
            ...        settings={'foo.abc': '123'},
            ...        custom_converters={'bytes': _ContrivedConverter()}) as override_info_1, \
            ...      Config.overriden_init_defaults(    # Note: here we have a few nested contexts.
            ...        custom_converters=None) as override_info_2:
            ...     config_full = Config(config_spec)
            ...     config_section = Config.section(config_spec)
            ...
            >>> config_full
            Config(<{'foo': ConfigSection('foo', {'abc': 123, 'spam': b'BAR'})}>)
            >>> config_section
            ConfigSection('foo', {'abc': 123, 'spam': b'BAR'})
            >>> override_info_1
            {'settings': {'foo.abc': '123'}, 'custom_converters': {'bytes': _ContrivedConverter()}}
            >>> override_info_2
            {'settings': {'foo.abc': '123'}, 'custom_converters': None}

            >>> with Config.overriden_init_defaults() as override_info:
            ...     pass
            ...
            >>> override_info
            {}

        The only supported argument names are the names of
        `Config`-*modern-instantiation*-specific optional
        arguments. Any others cause a `TypeError`:

            >>> with Config.overriden_init_defaults(                    # doctest: +ELLIPSIS
            ...        settings={'foo.abc': '123'},
            ...        unknown_arg='BAZ',
            ...        custom_converters={'bytes': _ContrivedConverter()},
            ...        ilegal_arg='spam'):
            ...     pass
            ...
            Traceback (most recent call last):
              ...
            TypeError: Config.overriden_init_defaults() got ... 'ilegal_arg', 'unknown_arg'
        """
        illegal_argument_names = new_defaults.keys() - cls._MODERN_INIT_OPTIONAL_ARGUMENT_NAMES
        if illegal_argument_names:
            listing = ', '.join(map(ascii, sorted(illegal_argument_names)))
            raise TypeError(
                f'{cls.overriden_init_defaults.__qualname__}() '
                f'got unexpected keyword arguments: {listing}')

        rlock = cls._overrides_of_init_defaults_rlock
        overrides = cls._overrides_of_init_defaults
        with rlock:
            new_overrides = cls._overrides_of_init_defaults = overrides.new_child(new_defaults)
        try:
            yield dict(new_overrides)
        finally:
            with rlock:
                cls._overrides_of_init_defaults = cls._overrides_of_init_defaults.parents


    #
    # Non-public implementation details
    #

    #
    # Pre-initialization helpers

    def _common_preinit(self, *, super_init_args=(), super_init_kwargs=None):
        super().__init__(*super_init_args, **(super_init_kwargs or {}))
        self._config_overridden_dict = N6ArgumentParser().get_config_overridden_dict()

    def _are_init_arguments_for_legacy_init(self, args, kwargs):
        return (
            (len(args) == 1 and not kwargs and isinstance(args[0], dict)) or
            (len(kwargs) == 1 and not args and isinstance(kwargs.get('required'), dict)))

    #
    # DictWithSomeHooks-specific customizations

    def _constructor_args_repr(self):
        content_repr = super()._constructor_args_repr()
        return f'<{content_repr}>'

    def _custom_key_error(self, key_error, method_name):
        exc = super()._custom_key_error(key_error, method_name)
        return NoConfigSectionError(*exc.args)

    #
    # Implementation of the modern way of initialization

    def _modern_init(self, config_spec, /,
                     *,
                     settings=None,
                     custom_converters=None,
                     config_filename_regex=None,
                     config_filename_excluding_regex=None):

        opt_arguments = self._get_eventual_init_optional_arguments(
            settings=settings,
            custom_converters=custom_converters,
            config_filename_regex=config_filename_regex,
            config_filename_excluding_regex=config_filename_excluding_regex)
        settings = opt_arguments['settings']
        custom_converters = opt_arguments['custom_converters']
        config_filename_regex = opt_arguments['config_filename_regex']
        config_filename_excluding_regex = opt_arguments['config_filename_excluding_regex']

        conf_spec_data = parse_config_spec(config_spec)
        converters = {
            **self.BASIC_CONVERTERS,
            **(custom_converters or {}),
        }
        try:
            try:
                if settings is None:
                    sect_name_to_opt_dict = self._load_n6_config_files(
                        config_filename_regex,
                        config_filename_excluding_regex)
                    self._override_config_values_by_cmdlines_arguments(sect_name_to_opt_dict)
                else:
                    sect_name_to_opt_dict = self._convert_settings_mapping(settings)
                self.update(
                    (config_sect.sect_name, config_sect)
                    for config_sect in self._make_config_sections(
                        sect_name_to_opt_dict,
                        conf_spec_data,
                        converters))
            except ConfigError as exc:
                LOGGER.error('%s', ascii_str(exc))
                raise
            except Exception as exc:
                e = ConfigError('{0}: {1}'.format(get_class_name(exc), ascii_str(exc)))
                LOGGER.error('%s', e, exc_info=True)
                raise e from exc
            finally:
                e = None  # noqa   # To break a traceback-related reference cycle (if any).
        except ConfigError as err:
            if settings is None:
                print(_N6DATAPIPELINE_CONFIG_ERROR_MSG_PATTERN.format(ascii_str(err)),
                      file=sys.stderr)
            raise

    _MODERN_INIT_OPTIONAL_ARGUMENT_NAMES = frozenset({
        'settings',
        'custom_converters',
        'config_filename_regex',
        'config_filename_excluding_regex',
    })

    _overrides_of_init_defaults_rlock = threading.RLock()
    _overrides_of_init_defaults = collections.ChainMap()

    def _get_eventual_init_optional_arguments(self, **init_optional_arguments):
        assert init_optional_arguments.keys() == self._MODERN_INIT_OPTIONAL_ARGUMENT_NAMES
        with self._overrides_of_init_defaults_rlock:
            for arg_name, arg_value in self._overrides_of_init_defaults.items():
                if arg_value is None or init_optional_arguments.get(arg_name) is not None:
                    continue
                init_optional_arguments[arg_name] = arg_value
        return init_optional_arguments

    def _convert_settings_mapping(self, settings):
        sect_name_to_opt_dict = {}
        for key, value in settings.items():
            if not isinstance(key, str):
                LOGGER.warning('Ignoring non-`str` settings key %a', key)
                continue
            if not isinstance(value, str):
                if not self._is_standard_pyramid_key_of_non_str(key):  # <- to reduce log noise
                    LOGGER.warning(
                        'Coercing non-`str` value %a (of setting %s) '
                        'to `str` (before further conversion)',
                        value, ascii_str(key))
                value = as_unicode(value)
            first, dotted, second = key.partition('.')
            if dotted:
                sect_name = first
                opt_name = second
            else:
                sect_name = ''
                opt_name = first
            opt_name_to_value = sect_name_to_opt_dict.setdefault(sect_name, {})
            opt_name_to_value[opt_name] = value
        return sect_name_to_opt_dict

    def _is_standard_pyramid_key_of_non_str(self, key):
        return key.startswith(('pyramid.', 'debugtoolbar.')) or key in (
            'csrf_trusted_origins',
            'debug_all',
            'debug_authorization',
            'debug_notfound',
            'debug_routematch',
            'debug_templates',
            'prevent_cachebust',
            'prevent_http_cache',
            'reload_all',
            'reload_assets',
            'reload_resources',
            'reload_templates',
        )

    def _make_config_sections(self,
                              sect_name_to_opt_dict,
                              conf_spec_data,
                              converters):
        resultant_config_sections = []
        conversion_errors = []
        missing_sect_names = []
        absent_nonrequired_sect_names = []
        opt_typo_vulnerable_sect_names = []
        missing_opt_locations = []
        illegal_opt_locations = []

        all_sect_specs = conf_spec_data.get_all_sect_specs()
        for sect_spec in all_sect_specs:
            some_declared_opts_are_absent = False
            input_opt_dict = sect_name_to_opt_dict.get(sect_spec.name)
            if input_opt_dict is None:
                if sect_spec.required:
                    missing_sect_names.append(sect_spec.name)
                    continue
                absent_nonrequired_sect_names.append(sect_spec.name)
                input_opt_dict = {}

            resultant_config_sect = ConfigSection(sect_spec.name)
            for opt_spec in sect_spec.opt_specs:
                opt_location = '{0}.{1}'.format(sect_spec.name, opt_spec.name)
                opt_descr = 'option {0}'.format(ascii_str(opt_location))
                opt_value = input_opt_dict.get(opt_spec.name)
                if opt_value is None:
                    if opt_spec.default is None:
                        missing_opt_locations.append(opt_location)
                        continue
                    # the first condition for the section to
                    # be suspected of containing misspelled
                    # options is met
                    some_declared_opts_are_absent = True
                    opt_value = opt_spec.default
                assert isinstance(opt_value, str)
                converter = self._get_converter(
                    opt_descr,
                    opt_spec.converter_spec,
                    converters,
                    conversion_errors)
                if converter is None:
                    continue
                opt_value = self._apply_value_converter(
                    opt_descr,
                    opt_value,
                    converter,
                    conversion_errors)
                if opt_value is self.__NOT_CONVERTED:
                    continue
                resultant_config_sect[opt_spec.name] = opt_value

            free_opt_names = sorted(
                input_opt_dict.keys() - {opt_spec.name for opt_spec in sect_spec.opt_specs})
            if free_opt_names:
                if sect_spec.free_opts_allowed:
                    if some_declared_opts_are_absent:
                        # all conditions for the section
                        # to be suspected of containing
                        # misspelled options are met
                        opt_typo_vulnerable_sect_names.append(sect_spec.name)
                    free_opts_converter = self._get_converter(
                        'free options in section {0}'.format(sect_spec.name),
                        sect_spec.free_opts_converter_spec,
                        converters,
                        conversion_errors)
                    if free_opts_converter is None:
                        # (an `unknown converter` error recorded
                        # so we can skip to the next section)
                        continue
                    for opt_name in free_opt_names:
                        opt_value = self._apply_value_converter(
                            '{0}.{1}'.format(sect_spec.name, opt_name),
                            input_opt_dict[opt_name],
                            free_opts_converter,
                            conversion_errors)
                        if opt_value is self.__NOT_CONVERTED:
                            continue
                        resultant_config_sect[opt_name] = opt_value
                else:
                    illegal_opt_locations.extend(
                        '{0}.{1}'.format(sect_spec.name, opt_name)
                        for opt_name in free_opt_names)

            resultant_config_sections.append(resultant_config_sect)

        if absent_nonrequired_sect_names:
            LOGGER.error("Absent *non-required* config sections: %s.  Default config values "
                         "have been used.  If it is your actual intention, then, for each "
                         "of these section names, create an empty section inside "
                         "your configuration, to make the situation clear.",
                         ', '.join(absent_nonrequired_sect_names))
        if opt_typo_vulnerable_sect_names:
            LOGGER.warning("For the following config sections: %s some free "
                           "(undeclared but allowed) options are present and, at the same "
                           "time, some declared (though non-required) options are absent. "
                           "Therefore, configuration within these sections should be "
                           "double checked.  To get rid of this warning, specify "
                           "(in your configuration) values for all options that "
                           "are explicitly declared (in the config spec) for "
                           "the mentioned sections.", ', '.join(opt_typo_vulnerable_sect_names))
        if (conversion_errors or
              missing_sect_names or
              missing_opt_locations or
              illegal_opt_locations):
            error_msg = '; '.join(filter(None, [
                    ("missing required config sections: {0}".format(
                        ", ".join(map(ascii_str, missing_sect_names)))
                     if missing_sect_names else None),
                    ("missing required config options: {0}".format(
                        ", ".join(map(ascii_str, missing_opt_locations)))
                     if missing_opt_locations else None),
                    ("illegal config options: {0}".format(
                        ", ".join(map(ascii_str, illegal_opt_locations)))
                     if illegal_opt_locations else None)
                ] + conversion_errors))
            raise ConfigError(error_msg)

        return resultant_config_sections

    def _get_converter(self, opt_descr, converter_spec, converters, conversion_errors):
        try:
            return converters[converter_spec]
        except KeyError:
            conversion_errors.append(
                'unknown config value converter '
                '`{0}` (for {1})'.format(converter_spec, opt_descr))
            return None

    def _apply_value_converter(self, opt_descr, opt_value, converter, conversion_errors):
        try:
            return converter(opt_value)
        except Exception as exc:
            conversion_errors.append(
                'error when applying config value converter {0!a} '
                'to {1}={2!a} ({3}: {4})'.format(
                    converter,
                    opt_descr,
                    opt_value,
                    get_class_name(exc),
                    ascii_str(exc)))
            # We use this special sentinel object because `None` is a valid value.
            return self.__NOT_CONVERTED

    #
    # Implementation of the legacy way of initialization

    def _legacy_init(self, required):
        assert isinstance(required, dict)
        sect_name_to_opt_dict = self._load_n6_config_files()
        self._override_config_values_by_cmdlines_arguments(sect_name_to_opt_dict)
        missing_msg = self._get_error_msg_if_missing(sect_name_to_opt_dict, required)
        if missing_msg:
            LOGGER.error('%s', missing_msg)
            sys.exit(_N6DATAPIPELINE_CONFIG_ERROR_MSG_PATTERN.format(missing_msg))
        self.update(
            (sect_name, ConfigSection(
                sect_name,
                opt_name_to_value))
            for sect_name, opt_name_to_value in sect_name_to_opt_dict.items())

    @staticmethod
    def _get_error_msg_if_missing(sect_name_to_opt_dict, required):
        missing_sect_names = []
        missing_opt_locations = []
        for sect_name, options in required.items():
            if sect_name not in sect_name_to_opt_dict:
                missing_sect_names.append(sect_name)
            else:
                for opt_name in options:
                    if opt_name not in sect_name_to_opt_dict[sect_name]:
                        missing_opt_locations.append("{0}.{1}".format(
                            sect_name,
                            opt_name))
        if missing_sect_names or missing_opt_locations:
            missing_msg = '; '.join(filter(None, [
                ("missing required config sections: {0}".format(
                    ", ".join(sorted(map(ascii_str, missing_sect_names))))
                 if missing_sect_names else None),
                ("missing required config options: {0}".format(
                    ", ".join(sorted(map(ascii_str, missing_opt_locations))))
                 if missing_opt_locations else None)]))
            return missing_msg
        return None

    #
    # Generic helpers

    @classmethod
    @memoized(expires_after=60)
    def _load_n6_config_files(cls, *filename_regexes):
        sect_name_to_opt_dict = {}
        config_parser = configparser.ConfigParser()
        config_files = []
        config_files.extend(cls._get_config_file_paths(ETC_DIR, *filename_regexes))
        config_files.extend(cls._get_config_file_paths(USER_DIR, *filename_regexes))
        if not config_files:
            LOGGER.warning('No config files to read')
            return sect_name_to_opt_dict

        ok_config_files = config_parser.read(config_files, encoding='utf-8')
        err_config_files = set(config_files).difference(ok_config_files)
        if err_config_files:
            LOGGER.warning(
                'Config files that could not be read '
                '(check their permission modes?): %s', ', '.join(
                    '"{0}"'.format(ascii_str(name))
                    for name in sorted(
                        err_config_files,
                        key=config_files.index)))
        if ok_config_files:
            LOGGER.info('Config files read properly: %s', ', '.join(
                '"{0}"'.format(ascii_str(name))
                for name in ok_config_files))
        else:
            LOGGER.warning('No config files read properly')

        for sect_name in config_parser.sections():
            opt_name_to_value = dict(config_parser.items(sect_name))
            assert (
                isinstance(sect_name, str) and
                all(isinstance(opt_name, str) and isinstance(opt_value, str)
                    for opt_name, opt_value in opt_name_to_value.items()))
            opt_name_to_value = {
                opt_name: ('' if opt_value == '""' else opt_value)      # <- TODO: deprecate and later remove this legacy behavior
                for opt_name, opt_value in opt_name_to_value.items()}
            sect_name_to_opt_dict[sect_name] = opt_name_to_value
        return sect_name_to_opt_dict

    @staticmethod
    def _get_config_file_paths(path,
                               config_filename_regex=None,
                               config_filename_excluding_regex=None):
        """
        Get the paths of configuration files from a given dir.

        (All files whose names match `config_filename_regex` except
        those whose names match `config_filename_excluding_regex`.)

        Args/kwargs:
            `path` (a `str`):
                The path of the directory to search for configuration
                files in.
            `config_filename_regex` (a `str` or `re.Pattern`, or `None`; default `None`):
                Configuration may be loaded *only* from those files whose
                names match this regular expression. `None` is equivalent
                to the value of `Config.DEFAULT_CONFIG_FILENAME_REGEX`.
            `config_filename_excluding_regex` (a `str` or `re.Pattern`, or `None`; default `None`):
                Configuration will *never* be loaded from any files whose
                names match this regular expression. `None` is equivalent to
                the value of `Config.DEFAULT_CONFIG_FILENAME_EXCLUDING_REGEX`.

        Returns:
            A sorted list of paths of configuration files.
        """
        if config_filename_regex is None:
            config_filename_regex = Config.DEFAULT_CONFIG_FILENAME_REGEX
        if isinstance(config_filename_regex, str):
            config_filename_regex = re.compile(config_filename_regex)
        if config_filename_excluding_regex is None:
            config_filename_excluding_regex = Config.DEFAULT_CONFIG_FILENAME_EXCLUDING_REGEX
        if isinstance(config_filename_excluding_regex, str):
            config_filename_excluding_regex = re.compile(config_filename_excluding_regex)
        config_files = []
        for directory, _, fnames in os.walk(path):
            for fname in fnames:
                if (config_filename_regex.search(fname)
                      and not config_filename_excluding_regex.search(fname)):
                    config_files.append(osp.join(directory, fname))
        return sorted(config_files)

    def _override_config_values_by_cmdlines_arguments(self, config_dir):
        for key, value in self._config_overridden_dict.items():
            if key in config_dir:
                config_dir[key].update(value)



class ConfigSection(DictWithSomeHooks):

    """
    A subclass of `dict`; its instances are values of `Config` mappings.

    Generally, `ConfigSection` instances behave like a `dict`;
    lookup-by-key failures are signalled with `NoConfigOptionError`
    which is a subclass of both `KeyError` and `ConfigError`.

    A `ConfigSection` instance represents a configuration section; it
    maps configuration option names (`str`) to option values (possibly
    of any types).  It keeps also the name of the configuration section
    it represents.

    >>> s = ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> from collections.abc import Mapping, MutableMapping
    >>> (isinstance(s, ConfigSection) and
    ...  isinstance(s, DictWithSomeHooks) and
    ...  isinstance(s, dict) and
    ...  isinstance(s, MutableMapping) and
    ...  isinstance(s, Mapping))
    True

    >>> s
    ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> s.sect_name
    'some_sect'
    >>> len(s)
    1
    >>> s.items()
    dict_items([('some_opt', 'FOO_bar,spam')])
    >>> s['some_opt']
    'FOO_bar,spam'
    >>> s == {'some_opt': 'FOO_bar,spam'}
    True
    >>> s != {'some_opt': 'FOO_bar,spam'}
    False
    >>> s == {}
    False
    >>> s != {}
    True

    A lookup-by-key failure:

    >>> s['another_opt']     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib.config.NoConfigOptionError: [conf... `another_opt` in section `some_sect`

    A few more examples:

    >>> another_s = ConfigSection('some_sect')
    >>> another_s
    ConfigSection('some_sect', {})
    >>> another_s.sect_name
    'some_sect'
    >>> len(another_s)
    0
    >>> another_s.items()
    dict_items([])
    >>> another_s == {}
    True
    >>> another_s == ConfigSection('some_sect')
    True
    >>> another_s == {'some_opt': 'FOO_bar,spam'}
    False
    >>> another_s == s
    False

    >>> another_s['some_opt'] = 'FOO_bar,spam'
    >>> another_s['some_opt']
    'FOO_bar,spam'
    >>> len(another_s)
    1
    >>> another_s.keys()
    dict_keys(['some_opt'])
    >>> another_s.values()
    dict_values(['FOO_bar,spam'])
    >>> another_s
    ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> another_s == {}
    False
    >>> another_s == ConfigSection('some_sect')
    False
    >>> another_s == {'some_opt': 'FOO_bar,spam'}
    True
    >>> another_s == s
    True

    Note that when an instance of ConfigSection is compared to another
    instance of the class -- also the values of the `sect_name`
    attribute are considered (not only the contents of the mappings):

    >>> another_s.sect_name = 'something_different'
    >>> another_s == {'some_opt': 'FOO_bar,spam'}  # still equal to such a dict
    True
    >>> another_s == s       # ...but not to instance `s` (`sect_name` differs)
    False
    """

    def __init__(self, sect_name, opt_name_to_value=None):
        self.sect_name = sect_name
        if opt_name_to_value is None:
            opt_name_to_value = {}
        super().__init__(opt_name_to_value)

    def __eq__(self, other):
        if isinstance(other, ConfigSection) and other.sect_name != self.sect_name:
            return False
        return super().__eq__(other)

    #
    # DictWithSomeHooks-specific customizations

    def _constructor_args_repr(self):
        content_repr = super()._constructor_args_repr()
        return f'{self.sect_name!r}, {content_repr}'

    def _custom_key_error(self, key_error, method_name):
        exc = super()._custom_key_error(key_error, method_name)
        return NoConfigOptionError(self.sect_name, *exc.args)



class ConfigMixin(UnsupportedClassAttributesMixin):

    r"""
    A convenience mixin for classes that make use of `Config` stuff.

    The most important public methods it provides are:

    * `get_config_full()` -- returns a ready-to-use `Config` instance.
    * `get_config_section()` -- returns a ready-to-use `ConfigSection`
      instance

    -- you can use them *instead* of calling `Config` stuff directly.

    The `get_config_section()` method is probably more handy than
    `get_config_full()` because in most cases you are interested in a
    particular (only one) config section.

    Both of them make use of the following attributes (which, typically,
    will be class attributes -- but they are got through an instance, so
    it is possible to customize them on a per-instance basis if needed):

    * `config_spec` (providing a ready *configuration specification*)
       or -- alternatively -- `config_spec_pattern` (providing a
       formattable *configuration specification pattern*);
    * `custom_converters` -- optional;
    * `config_filename_regex` -- optional (relevant only to the
      "N6DataPipeline way" of obtaining the configuration; see the
      docs of `Config`);
    * `config_filename_excluding_regex` -- optional (relevant only to
      the "N6DataPipeline way" of obtaining the configuration; see the
      docs of `Config`).

    When any of the two aforementioned methods is called, the value of
    the `config_spec` attribute (if present and not `None`) is passed to
    the `Config` constructor as the *config spec* argument. If, instead
    of it, a `config_spec_pattern` attribute is present (and not `None`),
    its value is transformed by calling the `as_config_spec_string()`
    function (see its docs...) with that value as the first positional
    argument (`config_spec`) and a `dict`, gathering all *format kwargs*
    taken by `get_config_full()`/`get_config_section()`, as the second
    argument (named `format_data_mapping`). Then the result of that
    transformation is passed to the `Config` constructor as the *config
    spec* argument.

    Values of the rest of the above-mentioned attributes are passed to
    the `Config` constructor as the respective keyword arguments (see:
    the docs of `Config`).

    Additionally, there are two public helper methods:

    * `is_config_spec_declared()` -- which informs whether at least one
      of the following attributes is present and set to some non-`None`
      value: `config_spec` or `config_spec_pattern`.
    * `make_list_converter()` -- a static method being an alias of
      `Config.make_list_converter()` (just for convenience).

    Let the examples speak...


    First, let us consider a case when a simple `config_spec` is
    defined; it contains just one config section -- so we can use the
    `get_config_section()` method:

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> # (for these doctests we need to patch the config I/O operations)
        ... example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> from unittest.mock import patch
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'foo'
        >>> sorted(m.config.keys())
        ['bar', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True

    Below is the same -- but with config contents taken from a Pyramid
    `settings` mapping (*not* loaded from files in "/etc/n6", "~/.n6",
    etc.):

        >>> example_settings = {'foo.spam': '[null]', 'other.ham': 'Abc'}
        >>> m = MyClass(example_settings)
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'foo'
        >>> sorted(m.config.keys())
        ['bar', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True


    Again, `config_spec` and one config section in use -- but
    additionally with `custom_converters`... Also, in this example
    `config_spec` is a `ConfigSpecEgg`-compliant object, rather than
    `str`:

        >>> from decimal import Decimal
        >>> class SimpleConfigSpecEgg:
        ...     def __init__(self, s):
        ...         self._s = s
        ...     def hatch_out(self, format_data_mapping=None):
        ...         if format_data_mapping is None:
        ...             return self._s
        ...         return self._s.format_map(format_data_mapping)
        ...
        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = SimpleConfigSpecEgg('''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: list_of_decimal
        ...     ''')
        ...     custom_converters = {
        ...         'list_of_decimal': Config.make_list_converter(Decimal),
        ...     }
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': ' 0 , 123,12345,'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'foo'
        >>> sorted(m.config.keys())
        ['bar', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['spam']
        [Decimal('0'), Decimal('123'), Decimal('12345')]
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'foo.spam': '0,123,12345', 'other.ham': 'Abc'}
        >>> m = MyClass(example_settings)
        >>> sorted(m.config.keys())
        ['bar', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['spam']
        [Decimal('0'), Decimal('123'), Decimal('12345')]
        >>> m.is_config_spec_declared()
        True


    Now, there is more than one config section specified (so the
    `get_config_full()` method needs to be used instead of
    `get_config_section()`):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...
        ...         [other]
        ...         ham :: py
        ...     '''
        ...
        ...     def __init__(self, settings=None):
        ...         self.config_full = self.get_config_full(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': '{42: "abc"}'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> isinstance(m.config_full, Config)
        True
        >>> sorted(m.config_full.keys())
        ['foo', 'other']
        >>> (isinstance(m.config_full['foo'], ConfigSection) and
        ...  isinstance(m.config_full['other'], ConfigSection))
        True
        >>> m.config_full['foo'].sect_name
        'foo'
        >>> sorted(m.config_full['foo'].keys())
        ['bar', 'spam']
        >>> m.config_full['foo']['bar']
        42
        >>> m.config_full['foo']['spam']
        [None]
        >>> m.config_full['other']
        ConfigSection('other', {'ham': {42: 'abc'}})
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'foo.spam': '[null]',
        ...                     'other.ham': '{42: "abc"}'}
        >>> m = MyClass(example_settings)
        >>> isinstance(m.config_full, Config)
        True
        >>> sorted(m.config_full.keys())
        ['foo', 'other']
        >>> (isinstance(m.config_full['foo'], ConfigSection) and
        ...  isinstance(m.config_full['other'], ConfigSection))
        True
        >>> sorted(m.config_full['foo'].keys())
        ['bar', 'spam']
        >>> m.config_full['foo']['bar']
        42
        >>> m.config_full['foo']['spam']
        [None]
        >>> m.config_full['other']
        ConfigSection('other', {'ham': {42: 'abc'}})
        >>> m.is_config_spec_declared()
        True


    The next example, even though somewhat similar to the previous one,
    differs from it in a few ways: `config_spec` is an object compliant
    with `ConfigSpecEgg` (rather than a `str`), and the contents of it
    -- and the actual configuration data -- are slightly different than
    above...

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = SimpleConfigSpecEgg('''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...
        ...         [other]
        ...         bar = 43 :: bytes
        ...     ''')
        ...
        ...     def __init__(self, settings=None):
        ...         self.config_full = self.get_config_full(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': '[null]'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> isinstance(m.config_full, Config)
        True
        >>> sorted(m.config_full.keys())
        ['foo', 'other']
        >>> (isinstance(m.config_full['foo'], ConfigSection) and
        ...  isinstance(m.config_full['other'], ConfigSection))
        True
        >>> m.config_full['foo'].sect_name
        'foo'
        >>> sorted(m.config_full['foo'].keys())
        ['bar', 'spam']
        >>> m.config_full['foo']['bar']
        42
        >>> m.config_full['foo']['spam']
        [None]
        >>> m.config_full['other']
        ConfigSection('other', {'bar': b'43'})
        >>> m.config_full['other']['bar']
        b'43'
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'foo.spam': '[null]'}
        >>> m = MyClass(example_settings)
        >>> isinstance(m.config_full, Config)
        True
        >>> sorted(m.config_full.keys())
        ['foo', 'other']
        >>> (isinstance(m.config_full['foo'], ConfigSection) and
        ...  isinstance(m.config_full['other'], ConfigSection))
        True
        >>> sorted(m.config_full['foo'].keys())
        ['bar', 'spam']
        >>> m.config_full['foo']['bar']
        42
        >>> m.config_full['foo']['spam']
        [None]
        >>> m.config_full['other']
        ConfigSection('other', {'bar': b'43'})
        >>> m.config_full['other']['bar']
        b'43'
        >>> m.is_config_spec_declared()
        True


    Another example: with `config_spec_pattern` (`str.format()`-able
    pattern) present instead of `config_spec`, as well as with
    `config_filename_regex` and `config_filename_excluding_regex`
    (plus, by the way, uncovering some details of invocation of
    the non-public method `Config._load_n6_config_files`...):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec_pattern = '''
        ...         [{section_name}]
        ...         {opt_name} = 42 :: {opt_converter_spec}
        ...         spam :: json
        ...     '''
        ...     config_filename_regex = r'^[0-9][0-9]_'
        ...     config_filename_excluding_regex = r'.backup\Z'
        ...
        ...     def __init__(self, settings=None, **format_kwargs):
        ...         self.config = self.get_config_section(settings, **format_kwargs)
        ...
        >>> example_conf_from_files = {'tralala': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files) as loading_method:
        ...
        ...     # keyword arguments to format actual config_spec:
        ...     m = MyClass(section_name='tralala',
        ...                 opt_name='hop-hop',
        ...                 opt_converter_spec='float')
        ...
        >>> from unittest.mock import call
        >>> loading_method.mock_calls == [
        ...     call(r'^[0-9][0-9]_', r'.backup\Z'),
        ... ]
        True
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'tralala'
        >>> sorted(m.config.keys())
        ['hop-hop', 'spam']
        >>> m.config['hop-hop']
        42.0
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'tralala.spam': '[null]'}
        >>> m = MyClass(example_settings,
        ...             # keyword arguments to format actual config_spec:
        ...             section_name='tralala',
        ...             opt_name='hop-hop',
        ...             opt_converter_spec='float')
        >>> m.config['hop-hop']
        42.0
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True


    And almost a twin example, but with `config_spec_pattern` being a
    `ConfigSpecEgg`-compliant object (rather than a `str` instance), and
    with `config_filename_regex` and `config_filename_excluding_regex`
    being `re.Pattern` instances (rather than `str` instances):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec_pattern = SimpleConfigSpecEgg('''
        ...         [{section_name}]
        ...         {opt_name} = 42 :: {opt_converter_spec}
        ...         spam :: json
        ...     ''')
        ...     config_filename_regex = re.compile(r'^[0-9][0-9]_')
        ...     config_filename_excluding_regex = re.compile(r'.backup\Z')
        ...
        ...     def __init__(self, settings=None, **format_kwargs):
        ...         self.config = self.get_config_section(settings, **format_kwargs)
        ...
        >>> example_conf_from_files = {'tralala': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files) as loading_method:
        ...
        ...     # keyword arguments to format actual config_spec:
        ...     m = MyClass(section_name='tralala',
        ...                 opt_name='hop-hop',
        ...                 opt_converter_spec='float')
        ...
        >>> loading_method.mock_calls == [
        ...     call(re.compile(r'^[0-9][0-9]_'), re.compile(r'.backup\Z')),
        ... ]
        True
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'tralala'
        >>> sorted(m.config.keys())
        ['hop-hop', 'spam']
        >>> m.config['hop-hop']
        42.0
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'tralala.spam': '[null]'}
        >>> m = MyClass(example_settings,
        ...             # keyword arguments to format actual config_spec:
        ...             section_name='tralala',
        ...             opt_name='hop-hop',
        ...             opt_converter_spec='float')
        >>> m.config['hop-hop']
        42.0
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_declared()
        True


    It is also possibe to use `combined_config_spec()` in conjunction
    with `ConfigMixin` (indeed, in such cases both those tools really
    shine!):

        >>> class MyBaseClass(ConfigMixin):
        ...
        ...     config_spec_pattern = combined_config_spec('''
        ...         [{section_name}]
        ...         {opt_name} = 42 :: {opt_converter_spec}
        ...         spam :: json
        ...         refrigerator = true :: bool
        ...     ''')
        ...
        ...     def __init__(self, settings=None, **format_kwargs):
        ...         self.config = self.get_config_section(settings, **format_kwargs)
        ...
        >>> class MySubClass(MyBaseClass):
        ...
        ...     config_spec_pattern = combined_config_spec('''
        ...         [{section_name}]
        ...         {opt_name} = 123456789 :: {opt_converter_spec}
        ...         fruit = Lemon!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        ...         vegetables :: list_of_str
        ...     ''')
        ...
        >>> example_conf_from_files = {'tralala': {'spam': '[null]',
        ...                                        'vegetables': 'Tomato, Celery'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...
        ...     # keyword arguments to format actual config_spec:
        ...     m = MySubClass(section_name='tralala',
        ...                    opt_name='hop-hop',
        ...                    opt_converter_spec='float')
        ...
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'tralala'
        >>> sorted(m.config.keys())
        ['fruit', 'hop-hop', 'refrigerator', 'spam', 'vegetables']
        >>> m.config['fruit']
        'Lemon!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        >>> m.config['hop-hop']
        123456789.0
        >>> m.config['refrigerator']
        True
        >>> m.config['spam']
        [None]
        >>> m.config['vegetables']
        ['Tomato', 'Celery']
        >>> m.is_config_spec_declared()
        True

    The same with config contents taken from a Pyramid `settings` mapping
    (*not* loaded from files in "/etc/n6" or "~/.n6", etc.):

        >>> example_settings = {'tralala.spam': '[null]',
        ...                     'tralala.vegetables': 'Tomato, Celery'}
        >>> m = MySubClass(example_settings,
        ...                # keyword arguments to format actual config_spec:
        ...                section_name='tralala',
        ...                opt_name='hop-hop',
        ...                opt_converter_spec='float')
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'tralala'
        >>> sorted(m.config.keys())
        ['fruit', 'hop-hop', 'refrigerator', 'spam', 'vegetables']
        >>> m.config['fruit']
        'Lemon!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        >>> m.config['hop-hop']
        123456789.0
        >>> m.config['refrigerator']
        True
        >>> m.config['spam']
        [None]
        >>> m.config['vegetables']
        ['Tomato', 'Celery']
        >>> m.is_config_spec_declared()
        True


    There are some basic conditions which must be satisfied or an
    exception will be raised...

    `TypeError` is raised if the value of the `config_spec` attribute is
    neither a `str` nor a `ConfigSpecEgg`-compliant object; also, if the
    object has the (`ConfigSpecEgg`-specific) method `hatch_out()` but
    that method returns a non-`str` object:

        >>> class MyClass(ConfigMixin):
        ...     config_spec = b'not a str!!!'
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytes`

        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytes`

        >>> m.is_config_spec_declared()
        True

        >>> class MyClass2(ConfigMixin):
        ...     config_spec = SimpleConfigSpecEgg(b'not a str!!!')
        ...
        >>> m = MyClass2()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytes`

        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytes`

        >>> m.is_config_spec_declared()
        True

    The same appies to `config_spec_pattern`:

        >>> class MyClass(ConfigMixin):
        ...     config_spec_pattern = bytearray(b'not a str!!!')
        ...
        >>> m = MyClass()
        >>> m.get_config_full(foo='bar')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytearray`

        >>> m.get_config_section(foo='bar')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytearray`

        >>> m.is_config_spec_declared()
        True

    Apart from that, `TypeError` is also raised if an attempt is made to
    pass `settings` among format keyword arguments:

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec_pattern = '''
        ...         [{section_name}]
        ...         foo
        ...     '''
        ...
        >>> example_settings = {'hophop.foo': 'bar'}
        >>> m = MyClass()
        >>> m.get_config_full(settings=example_settings,
        ...                   section_name='hophop')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: the `settings` format kwarg is forbidden ...

        >>> m.get_config_section(settings=example_settings,
        ...                      section_name='hophop')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: the `settings` format kwarg is forbidden ...

    Obviously, the fix is to pass the settings as the positional argument:

        >>> m.get_config_full(example_settings,
        ...                   section_name='hophop')
        Config(<{'hophop': ConfigSection('hophop', {'foo': 'bar'})}>)

        >>> m.get_config_section(example_settings,
        ...                      section_name='hophop')
        ConfigSection('hophop', {'foo': 'bar'})

    Another error-related remark: if the `hatch_out()` method of
    `config_spec` or `config_spec_pattern` raises an exception then
    that exception bubbles up:

        >>> class ConfigSpecRottenEgg:
        ...     def hatch_out(self, format_data_mapping=None):
        ...         1 / 0
        ...
        >>> class MyClass(ConfigMixin):
        ...     config_spec = ConfigSpecRottenEgg()
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ZeroDivisionError: ...
        >>> m.get_config_section()  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ZeroDivisionError: ...

        >>> class MyClass(ConfigMixin):
        ...     config_spec_pattern = ConfigSpecRottenEgg()
        ...
        >>> m = MyClass()
        >>> m.get_config_full(foo='bar')  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ZeroDivisionError: ...
        >>> m.get_config_section(foo='bar')  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ZeroDivisionError: ...

    `ValueError` is raised if `config_spec` (rather than
    `config_spec_pattern`) is present when `get_config_section()`
    or `get_config_full()` is being called *with* format keyword
    arguments (aka *format kwargs*):

        >>> class MyClass(ConfigMixin):
        ...     config_spec = 'foo'
        ...
        >>> m = MyClass()
        >>> m.get_config_full(a='b')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec_pattern` attribute is expected ...

        >>> m.get_config_section(a='b')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec_pattern` attribute is expected ...

        >>> m.is_config_spec_declared()
        True

        >>> class MyClass2(ConfigMixin):
        ...     config_spec = SimpleConfigSpecEgg('foo')
        ...
        >>> m = MyClass2()
        >>> m.get_config_full(a='b')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec_pattern` attribute is expected ...

        >>> m.get_config_section(a='b')  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec_pattern` attribute is expected ...

        >>> m.is_config_spec_declared()
        True

    `ValueError` is also raised if `config_spec_pattern` (rather
    than `config_spec`) is present when `get_config_section()`
    or `get_config_full()` is called *without* format keyword
    arguments:

        >>> class MyClass(ConfigMixin):
        ...     config_spec_pattern = 'foo'
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec` attribute is expected ...

        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec` attribute is expected ...

        >>> m.is_config_spec_declared()
        True

        >>> class MyClass2(ConfigMixin):
        ...     config_spec_pattern = SimpleConfigSpecEgg('foo')
        ...
        >>> m = MyClass2()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec` attribute is expected ...

        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ValueError: ... `config_spec` attribute is expected ...

        >>> m.is_config_spec_declared()
        True

    Note that if neither `config_spec` nor `config_spec_pattern` is
    specified then:

    * `get_config_section()` must fail because there is no possibility
      to infer the section name;

    * `get_config_full()` succeeds but the obtained `Config` is empty.

        >>> class MyClass(ConfigMixin):
        ...     pass
        ...
        >>> example_conf_from_files = {'foo': {'spam': '123'},
        ...                            'other': {'ham': 'Abc'}}
        >>> example_settings = {'foo.spam': '123',
        ...                     'other.ham': 'Abc'}
        >>> m = MyClass()
        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.config.ConfigError: ...but no sections found
        >>> m.get_config_section(example_settings)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.config.ConfigError: ...but no sections found
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     config_full = m.get_config_full()
        ...
        >>> config_full
        Config(<{}>)
        >>> m.get_config_full(example_settings)
        Config(<{}>)
        >>> m.is_config_spec_declared()  # note the result here
        False

    Of course, `ConfigError` -- as well as other exceptions (e.g.,
    `TypeError`, `ValueError`...) -- will occur always when the `Config`
    stuff raises them (see the docs of the `Config` class for details).
    """

    unsupported_class_attributes = CombinedWithSuper(frozenset({
        # (previously supported stuff, now explicitly prohibited)
        'config_required',
        'config_group',
        'default_converter',
    }))


    def get_config_full(self, settings=None, /, **format_kwargs):
        """
        Get a `Config` containing stuff from files or from `settings`.

        Args (positional-only, optional):
            `settings` (a mapping or `None`; default: `None`):
                If not `None` it should be a mapping containing
                Pyramid-like settings (see the description of the
                `settings` argument if tne docs of `Config`).

        Any kwargs (unrestricted, except that `settings` is forbidden):
            If given, they will be engaged as *format kwargs* to make
            the *config spec* by formatting it using the value of the
            `config_spec_pattern` attribute (which then must be present
            and not `None`) as the formattable *config spec pattern*.

            If not even one is given then no such attempt will be made;
            instead of that, the value of the `config_spec` attribute
            (which then must be present and not `None`) will be used as
            the *config spec*.

        Raises:
            `ConfigError`, `TypeError`, `ValueError` and possibly
            others... (see the main docs of this class).

        The method makes use of the following attributes:

        * `config_spec` (empty by default) or `config_spec_pattern`;
        * optional: `custom_converters`, and possibly (if the `settings`
          argument is `None`) also: `config_filename_regex` and
          `config_filename_excluding_regex`.

        (See the main docs of this class for details.)
        """
        if 'settings' in format_kwargs:
            raise TypeError(
                'the `settings` format kwarg is forbidden (if you '
                'meant to provide a Pyramid-like settings mapping, '
                'please pass it as the positional argument)')
        args, kwargs = self.__get_args_kwargs(settings, **format_kwargs)
        return Config(*args, **kwargs)


    def get_config_section(self, settings=None, /, **format_kwargs):
        """
        Get a `ConfigSection` containing stuff from files or from `settings`.

        Args (positional-only, optional):
            `settings` (a mapping or `None`; default: `None`):
                If not `None` it should be a mapping containing
                Pyramid-like settings (see the description of the
                `settings` argument if tne docs of `Config`).

        Any kwargs (unrestricted, except that `settings` is forbidden):
            If given, they will be engaged as *format kwargs* to make
            the *config spec* by formatting it using the value of the
            `config_spec_pattern` attribute (which then must be present
            and not `None`) as the formattable *config spec pattern*.

            If not even one is given then no such attempt will be made;
            instead of that, the value of the `config_spec` attribute
            (which then must be present and not `None`) will be used as
            the *config spec*.

        Raises:
            `ConfigError`, `TypeError`, `ValueError` and possibly
            others... (see the main docs of this class).

        The method makes use of the following attributes:

        * `config_spec` (empty by default) or `config_spec_pattern`;
        * optional: `custom_converters`, and possibly (if the `settings`
          argument is `None`) also: `config_filename_regex` and
          `config_filename_excluding_regex`.

        (See the main docs of this class for details.)

        NOTE: this method (unlike `get_config_full()`) is *only* allowed
        to be called if it is clear which is *the* section, i.e., if
        `config_spec` contains exactly one section.

        Typically, you are interested in one section only -- so in
        most cases this method will probably be more handy than
        `get_config_full()`.
        """
        if 'settings' in format_kwargs:
            raise TypeError(
                'the `settings` format kwarg is forbidden (if you '
                'meant to provide a Pyramid-like settings mapping, '
                'please pass it as the positional argument)')
        args, kwargs = self.__get_args_kwargs(settings, **format_kwargs)
        return Config.section(*args, **kwargs)


    def is_config_spec_declared(self):
        """
        Check whether a minimum configuration-related stuff is declared
        explicitly.

        Returns:
            `True` -- if *any* of the following attributes is present
            and set to some non-`None` value:

            * `config_spec`,
            * `config_spec_pattern`;

            `False` -- otherwise.  Note that in such a case a call to
            the `get_config_section()` method must always fail (raising
            an exception) but a call to `get_config_full()` would
            succeed (though returning an empty `Config` instance).
        """
        return (getattr(self, 'config_spec', None) is not None or
                getattr(self, 'config_spec_pattern', None) is not None)


    make_list_converter = staticmethod(Config.make_list_converter)


    def __get_args_kwargs(self, settings, /, **format_kwargs):
        config_spec = self.__get_config_spec(**format_kwargs)
        return (config_spec,), dict(
            settings=settings,
            custom_converters=getattr(self, 'custom_converters', None),
            config_filename_regex=getattr(self, 'config_filename_regex', None),
            config_filename_excluding_regex=getattr(self, 'config_filename_excluding_regex', None))


    def __get_config_spec(self, /, **format_kwargs):
        if format_kwargs:
            if getattr(self, 'config_spec', None) is not None:
                raise ValueError(
                    'when config spec format kwargs are specified '
                    'the `config_spec_pattern` attribute is expected '
                    '(to be non-None) rather than `config_spec`')
            config_spec_pattern = getattr(self, 'config_spec_pattern', '') or ''
            config_spec = as_config_spec_string(config_spec_pattern, format_kwargs)
        else:
            if getattr(self, 'config_spec_pattern', None) is not None:
                raise ValueError(
                    'when *no* config spec format kwargs are specified '
                    'the `config_spec` attribute is expected '
                    '(to be non-None) rather than `config_spec_pattern`')
            config_spec = getattr(self, 'config_spec', '') or ''
        return config_spec



def as_config_spec_string(config_spec, /, format_data_mapping=None):
    """
    Obtain a `str` from the given object that represents a *config spec*.

    Args (positional-only):
        `config_spec` (a `str` or `ConfigSpecEgg`-compliant object):
            The input object that represents a *config spec* (or a
            formattable *config spec pattern*).

            If `config_spec` is an *egg object*, i.e., an object compliant
            with the `ConfigSpecEgg` protocol, then its `hatch_out()`
            method will be called, with `format_data_mapping` (see below)
            as the sole argument (no matter whether it is a mapping or
            `None`), to obtain the result.

            If `config_spec` is a `str` and `format_data_mapping` *is*
            `None` then `config_spec` will be treated as the actual
            *config spec*.

            If `config_spec` is a `str` and `format_data_mapping` is *not*
            `None` then a `config_spec.format_map(format_data_mapping)`
            call will be made to obtain the actual *config spec*.

            Finally, in any case, the resultant string will be processed
            using the `n6lib.common_helpers.reduce_indent()` function.

    Args/kwargs:
        `format_data_mapping` (a mapping or `None`; default: `None`):
            If given and not `None` it should be a mapping ready to
            be passed to `str.format_map()`/`<egg object>.hatch_out()`
            (see the above description of the `config_spec` argument).

    Returns:
        A *config spec* (or *config spec pattern*), appropriately
        prepared and coerced to `str` (see the above description
        of the `config_spec` argument).

    Raises:
        `TypeError`:
            if the `config_spec` argument is neither a string (note: an
            instance of some subclass of `str` is also acceptable) nor
            an object compliant with `ConfigSpecEgg`; also, if the given
            object has the (`ConfigSpecEgg`-specific) `hatch_out()`
            method but that method returns a non-string object.

        Any exception from `config_spec.format_map(format_data_mapping)`:
            if the `config_spec` argument is a string *and* an exception
            -- in particular, a `KeyError` -- is obtained from the
            `config_spec.format_map(format_data_mapping)` call (note:
            that call is made only if `format_data_mapping` is *not*
            `None`).

        Any exception from `config_spec.hatch_out(...)`:
            if the `config_spec` argument is an object compliant with
            `ConfigSpecEgg` *and* an exception -- in particular, a
            `ConfigSpecEggError` (or a subclass of it) -- is obtained
            from the `config_spec.hatch_out(...)` call (note: that call
            is made *regardless* of whether `format_data_mapping` is
            `None`).

    Note that this function, unlike `parse_config_spec()`, does *not*
    parse or validate the content of the processed *config spec* (unless
    some parsing/validation is performed by the internal machinery of
    the given *egg object* if any).

    >>> class SpecEgg:  # (compliant with `ConfigSpecEgg`)
    ...     def __init__(self, s):
    ...         self._s = s
    ...     def hatch_out(self, format_data_mapping=None):
    ...         if format_data_mapping is None:
    ...             return self._s
    ...         return self._s.format_map(format_data_mapping)
    ...
    >>> class CustomStr(str):
    ...     pass
    ...
    >>> class CustomDict(dict):
    ...     def __missing__(self, key):
    ...         return ('brave' if key == 'lancelot_trait'
    ...                 else super().__missing__(key))
    ...
    >>> pattern = '''
    ...     [knights]
    ...     Galahad = {galahad_trait}
    ...     Lancelot = {lancelot_trait} :: bytes
    ...
    ...     [shrubbery]
    ...     price :: int
    ... '''
    >>> expected_pattern = '''
    ... [knights]
    ... Galahad = {galahad_trait}
    ... Lancelot = {lancelot_trait} :: bytes
    ...
    ... [shrubbery]
    ... price :: int
    ... '''
    >>> assert expected_pattern == reduce_indent(pattern)
    >>> str_pattern = as_config_spec_string(pattern)
    >>> str_pattern == expected_pattern and type(str_pattern) is str
    True
    >>> conv_str_pattern = as_config_spec_string(SpecEgg(pattern))
    >>> conv_str_pattern == expected_pattern and type(conv_str_pattern) is str
    True
    >>> cust_pattern = as_config_spec_string(CustomStr(pattern))
    >>> cust_pattern == expected_pattern and type(cust_pattern) is str
    True
    >>> conv_cust_pattern = as_config_spec_string(SpecEgg(CustomStr(pattern)))
    >>> conv_cust_pattern == expected_pattern and type(conv_cust_pattern) is str
    True
    >>> format_data_mapping = CustomDict(
    ...     galahad_trait='pure',
    ... )
    >>> expected_formatted = '''
    ... [knights]
    ... Galahad = pure
    ... Lancelot = brave :: bytes
    ...
    ... [shrubbery]
    ... price :: int
    ... '''
    >>> assert expected_formatted == expected_pattern.format_map(format_data_mapping)
    >>> str_formatted = as_config_spec_string(pattern, format_data_mapping)
    >>> str_formatted == expected_formatted and type(str_formatted) is str
    True
    >>> conv_str_formatted = as_config_spec_string(SpecEgg(pattern), format_data_mapping)
    >>> conv_str_formatted == expected_formatted and type(conv_str_formatted) is str
    True
    >>> cust_formatted = as_config_spec_string(CustomStr(pattern), format_data_mapping)
    >>> cust_formatted == expected_formatted and type(cust_formatted) is str
    True
    >>> conv_cust_formatted = as_config_spec_string(SpecEgg(CustomStr(pattern)),
    ...                                             format_data_mapping=format_data_mapping)
    >>> conv_cust_formatted == expected_formatted and type(conv_cust_formatted) is str
    True

    >>> as_config_spec_string(42)                            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `int`

    >>> as_config_spec_string(b'abc', format_data_mapping)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: `config_spec` is expected to be a `str` or ..., not an instance of `bytes`

    >>> as_config_spec_string(pattern, format_data_mapping={})
    Traceback (most recent call last):
      ...
    KeyError: 'galahad_trait'

    >>> class RottenEgg:
    ...     def hatch_out(self, format_data_mapping=None):
    ...         raise ValueError(format_data_mapping)
    ...
    >>> as_config_spec_string(RottenEgg())
    Traceback (most recent call last):
      ...
    ValueError: None

    >>> as_config_spec_string(RottenEgg(), format_data_mapping)
    Traceback (most recent call last):
      ...
    ValueError: {'galahad_trait': 'pure'}
    """
    if isinstance(config_spec, ConfigSpecEgg):
        config_spec = config_spec.hatch_out(format_data_mapping)
    elif isinstance(config_spec, str) and format_data_mapping is not None:
        config_spec = config_spec.format_map(format_data_mapping)
    if not isinstance(config_spec, str):
        raise TypeError(ascii_str(
            f'`config_spec` is expected to be a `str` or a '
            f'`{ConfigSpecEgg.__qualname__}`-compliant object, '
            f'not an instance of `{type(config_spec).__qualname__}`'))
    return reduce_indent(config_spec)



def parse_config_spec(config_spec, /):
    r"""
    Translate a *config spec* string to an object that is easier to
    manipulate. (Note that, first, the `as_config_spec_string()`
    function is always applied to the argument.)

    Args (positional-only):
        `config_spec` (a `str` or `ConfigSpecEgg`-compliant object):
            The *config spec* to be parsed (see the "Configuration
            specification format" section of the docs of the `Config`
            class).

            It can also be a formattable *config spec pattern*, provided
            that the "replacement fields" it contains do not make it
            unparseable as a valid *config spec*.

    Returns:
        An object that provides an interface similar to the interface
        provided by the `ConfigString` class -- but fitted to manipulate
        a *config spec*; especially, a few additional methods are provided
        (see the examples below). Its type is a subclass of `str`, so the
        object can be used in most contexts where a string is needed.

    Raises:
        Any exception from `as_config_spec_string(config_spec)`:
            see the docs of the `as_config_spec_string()` function.

        `ValueError`:
            if `config_spec` cannot be parsed because its content is not
            a valid *config spec*, including also cases when it contains
            any of `Config.CONFIG_SPEC_RESERVED_CHARS` (which are `\x00`
            and `\x01`, that is, the characters whose ASCII codes are,
            respectively, 0 and 1).


    >>> parsed = parse_config_spec('''
    ...     [first]
    ...     foo = 42 :: int  ; comment
    ...     bar = 43         ; comment
    ...     ham::bytes
    ...     spam
    ...     glam ;comment
    ...     # the `...` below means that free (arbitrary, i.e.,
    ...     # not specified here) options will be allowed in
    ...     # this section
    ...     ...
    ...
    ...     [second]
    ...     bAR :: url
    ... ''')

    >>> parsed.get_opt_value('first.foo')
    '42'
    >>> parsed.get_opt_value('first.FOO')  # option names are *case-insensitive*
    '42'
    >>> parsed.get_opt_value('first.bar')
    '43'
    >>> parsed.get_opt_value('second.bar') is None
    True

    >>> parsed.get_opt_value('second.foo')
    Traceback (most recent call last):
      ...
    KeyError: 'foo'
    >>> parsed.get_opt_value('third.foo')
    Traceback (most recent call last):
      ...
    KeyError: 'third'
    >>> parsed.get_opt_value('FIRST.foo')  # section names are *case-sensitive*
    Traceback (most recent call last):
      ...
    KeyError: 'FIRST'

    >>> opt_spec_foo = parsed.get_opt_spec('first.foo')
    >>> opt_spec_foo.name
    'foo'
    >>> opt_spec_foo.default
    '42'
    >>> opt_spec_foo.converter_spec
    'int'
    >>> opt_spec_foo == _OptSpec('foo', '42', 'int')
    True

    >>> parsed.get_opt_spec('second.foo')
    Traceback (most recent call last):
      ...
    KeyError: 'foo'
    >>> parsed.get_opt_spec('third.foo')
    Traceback (most recent call last):
      ...
    KeyError: 'third'

    >>> opt_spec_bar1 = parsed.get_opt_spec('first.bar')
    >>> opt_spec_bar1.name
    'bar'
    >>> opt_spec_bar1.default
    '43'
    >>> opt_spec_bar1.converter_spec
    'str'
    >>> opt_spec_bar1 == _OptSpec('bar', '43', 'str')
    True

    >>> opt_spec_bar2 = parsed.get_opt_spec('second.bar')
    >>> opt_spec_bar2.name
    'bar'
    >>> opt_spec_bar2.default is None
    True
    >>> opt_spec_bar2.converter_spec
    'url'
    >>> opt_spec_bar2 == _OptSpec('bar', None, 'url')
    True

    >>> sect_spec_first = parsed.get_sect_spec('first')
    >>> sect_spec_first.name
    'first'
    >>> sect_spec_first.opt_specs == [
    ...     parsed.get_opt_spec('first.foo'),
    ...     parsed.get_opt_spec('first.bar'),
    ...     parsed.get_opt_spec('first.ham'),
    ...     parsed.get_opt_spec('first.spam'),
    ...     parsed.get_opt_spec('first.glam'),
    ... ] == [
    ...     _OptSpec('foo', '42', 'int'),
    ...     _OptSpec('bar', '43', 'str'),
    ...     _OptSpec('ham', None, 'bytes'),
    ...     _OptSpec('spam', None, 'str'),
    ...     _OptSpec('glam', None, 'str'),
    ... ]
    True
    >>> sect_spec_first.free_opts_allowed   # the `...` marker is present
    True
    >>> sect_spec_first.free_opts_converter_spec
    'str'
    >>> sect_spec_first == _SectSpec(
    ...     'first',
    ...     [
    ...         parsed.get_opt_spec('first.foo'),
    ...         parsed.get_opt_spec('first.bar'),
    ...         parsed.get_opt_spec('first.ham'),
    ...         parsed.get_opt_spec('first.spam'),
    ...         parsed.get_opt_spec('first.glam'),
    ...     ],
    ...     True,
    ...     'str',
    ... )
    True
    >>> sect_spec_first.required  # includes at least 1 opt without default
    True

    >>> parsed.get_sect_spec('third')
    Traceback (most recent call last):
      ...
    KeyError: 'third'

    >>> parsed.get_all_sect_specs() == [
    ...     parsed.get_sect_spec('first'),
    ...     parsed.get_sect_spec('second'),
    ... ]
    True

    Note: `parse_config_spec()` makes use of the `as_config_spec_string()`
    function which (apart from doing other things) automatically *reduces
    indentation* -- that's why the *config spec* in the following example
    is perfectly synonymous to the one defined earlier:

    >>> parsed == parse_config_spec('''
    ... [first]
    ... foo = 42 :: int  ; comment
    ... bar = 43         ; comment
    ... ham::bytes
    ... spam
    ... glam ;comment
    ... # the `...` below means that free (arbitrary, i.e.,
    ... # not specified here) options will be allowed in
    ... # this section
    ... ...
    ...
    ... [second]
    ... bAR :: url
    ... ''')
    True

    >>> another_parsed = parse_config_spec('''
    ...     ab = cd
    ...       ef gh ij
    ...     \t
    ...     [foo]
    ...     bar = \t\f
    ...         spam
    ...     ''')
    >>> str(another_parsed) == ('''
    ... ab = cd
    ...   ef gh ij
    ...
    ... [foo]
    ... bar =       \f
    ...     spam
    ... ''')
    True
    >>> another_parsed.get_opt_value('.ab')
    'cd\nef gh ij'
    >>> another_parsed.get_opt_value('foo.bar')
    '\nspam'

    >>> class SimpleConfigSpecEgg:
    ...     def __init__(self, s):
    ...         self._s = s
    ...     def hatch_out(self, format_data_mapping=None):
    ...         if format_data_mapping is None:
    ...             return self._s
    ...         return self._s.format_map(format_data_mapping)
    ...
    >>> yet_another_parsed = parse_config_spec(SimpleConfigSpecEgg('''x = y
    ...       z
    ...     [foo]
    ... \t
    ...     bar =
    ...         spam
    ...     baz = ham
    ...     \t'''))
    >>> str(yet_another_parsed) == ('''x = y
    ...   z
    ... [foo]
    ...
    ... bar =
    ...     spam
    ... baz = ham
    ... ''')
    True
    >>> yet_another_parsed.get_opt_value('.x')
    'y\nz'
    >>> yet_another_parsed.get_opt_value('foo.bar')
    '\nspam'
    >>> yet_another_parsed.get_opt_value('foo.baz')
    'ham'

    Some typical error conditions related to ill-formed *config specs*
    are presented below:

    >>> parse_config_spec('''
    ...     [first]
    ...     a = AAA
    ...     [second]
    ...     z = ZZZ
    ...     [first]
    ...     b = BBB
    ...     c = CCC
    ... ''')
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> parse_config_spec(SimpleConfigSpecEgg('''
    ...     [first]
    ...     a = AAA
    ...     b = BBB
    ...     a = AAA
    ... '''))
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'

    >>> parse_config_spec('[wrong.sect]')                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong.sect]' is not valid ...

    >>> parse_config_spec('[wrong_opt')                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt' is not valid ...

    >>> parse_config_spec(']wrong_opt = val')               # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt = val' is not valid ...

    >>> parse_config_spec('wrong opt :: some_conv')         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt :: some_conv' is not valid ...

    >>> parse_config_spec('some_opt = val :: wrong conv')   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ...wrong conv' is not valid...

    >>> parse_config_spec('\n   xyz\n  abc\n\n')            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... ' xyz' looks like a continuation line...

    >>> parse_config_spec('some_opt = \0')                  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: found config spec's character(s) reserved for internal purposes: '\x00'

    >>> parse_config_spec(SimpleConfigSpecEgg('some_opt = \0\1'))   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: found config spec's character(s) reserved for internal purposes: '\x00', '\x01'

    As it was said, the methods analogous to those provided by
    `ConfigString` are also provided; the code below includes a
    few examples...

    >>> parsed.contains('first')
    True
    >>> parsed.contains('first.foo')
    True
    >>> parsed.contains('first.bar')
    True
    >>> parsed.contains('second')
    True
    >>> parsed.contains('second.bar')
    True
    >>> parsed.contains('second.BAR')
    True

    >>> parsed.contains('second.foo')
    False
    >>> parsed.contains('SECOND.bar')
    False
    >>> parsed.contains('third')
    False
    >>> parsed.contains('third.foo')
    False
    >>> parsed.contains('third.bar')
    False

    >>> first = parsed.get('first')
    >>> first == parse_config_spec('''[first]
    ...   foo = 42 :: int  ; comment
    ...   bar = 43         ; comment
    ...   ham::bytes
    ...   spam
    ...   glam ;comment
    ...   # the `...` below means that free (arbitrary, i.e.,
    ...   # not specified here) options will be allowed in
    ...   # this section
    ...   ...
    ... ''')
    True
    >>> first.get_opt_value('first.foo')
    '42'
    >>> first.get_opt_spec('first.foo') == opt_spec_foo
    True
    >>> first.get_sect_spec('first') == parsed.get_sect_spec('first')
    True

    >>> first_foo = parsed.get('first.foo')
    >>> first_foo == first.get('first.foo') == parse_config_spec(
    ...     'foo = 42 :: int  ; comment')
    True
    >>> first_foo.get_opt_value('.foo')
    '42'
    >>> first_foo.get_opt_spec('.foo') == opt_spec_foo
    True
    >>> sect_spec = first_foo.get_sect_spec('')
    >>> sect_spec.name
    ''
    >>> sect_spec.opt_specs == [opt_spec_foo]
    True
    >>> sect_spec.free_opts_allowed
    False
    >>> sect_spec.free_opts_converter_spec
    'str'
    >>> sect_spec == _SectSpec(
    ...     '',
    ...     [opt_spec_foo],
    ...     False,
    ...     'str',
    ... )
    True
    >>> sect_spec.required    # all included opts have default values defined
    False

    >>> parsed.get_opt_names('first') == [
    ...     'foo',
    ...     'bar',
    ...     'ham',
    ...     'spam',
    ...     'glam',
    ...     '...',
    ... ]
    True
    >>> parsed.get_opt_names('second') == ['bar']
    True
    >>> parsed.get_opt_names('') == []
    True
    >>> parsed.get_opt_names('nonexistent')
    Traceback (most recent call last):
      ...
    KeyError: 'nonexistent'

    >>> parsed.get_all_sect_names()
    ['first', 'second']

    >>> parsed.get_all_sect_and_opt_names() == [
    ...     ('first', [
    ...         'foo',
    ...         'bar',
    ...         'ham',
    ...         'spam',
    ...         'glam',
    ...         '...',
    ...      ]),
    ...     ('second', ['bar']),
    ... ]
    True

    >>> (parsed.substitute('first.foo', 'foo = 123 :: someconv') ==
    ...  parse_config_spec('''
    ...      [first]
    ...      foo = 123 :: someconv
    ...      bar = 43         ; comment
    ...      ham::bytes
    ...      spam
    ...      glam ;comment
    ...      # the `...` below means that free (arbitrary, i.e.,
    ...      # not specified here) options will be allowed in
    ...      # this section
    ...      ...
    ...
    ...      [second]
    ...      bAR :: url
    ...      '''))
    True
    """
    config_spec_string = as_config_spec_string(config_spec)
    _verify_no_config_spec_reserved_chars(config_spec_string)
    # (For more doctests related to the class of objects returned by
    # this function -- including some peculiar/corner cases -- see the
    # docstring of the `_ConfSpecData` non-public class...)
    return _ConfSpecData(config_spec_string)



def join_config_specs(*config_specs):
    r"""
    Prepare the given *config specs* by applying to them the function
    `as_config_spec_string()`, and then join them (interleaving them
    with additional newline characters); the final result can be passed
    to `parse_config_spec()`.

    Possibly multiple *args (positional-only):
        *Config specs* (or formattable *config spec patterns*) -- each
        should be a string or a `ConfigSpecEgg`-compliant object.

    Returns:
        A new *config spec* (or *config spec pattern*) string derived
        from the arguments.

    Raises:
        Any exception from `as_config_spec_string(<any of the given specs>)`:
            see the docs of the `as_config_spec_string()` function.

    Note: this function performs a simple-minded "concatenation" of
    *config specs* (treated just as strings). For a smarter way of
    merging *config specs* -- see the `combined_config_spec()` tool.

    >>> joined = join_config_specs(
    ...     # Note that different levels of indentation in each of these
    ...     # three config specs is not a problem for this helper.
    ...     '''
    ...     [first]
    ...     foo = 42 :: int  ; comment
    ...
    ...     ham::bytes''',
    ... '''[SPAM_SPAM_SPAM]
    ... glam ;comment
    ... # some free options are possible:
    ... ...
    ...
    ... ''',
    ... '''            [second]
    ...                bAR = milk://Bar :: url
    ...                            ''')
    >>> joined == '''
    ... [first]
    ... foo = 42 :: int  ; comment
    ...
    ... ham::bytes
    ... [SPAM_SPAM_SPAM]
    ... glam ;comment
    ... # some free options are possible:
    ... ...
    ...
    ...
    ... [second]
    ... bAR = milk://Bar :: url
    ... '''
    True
    >>> parsed = parse_config_spec(joined)
    >>> parsed.get_opt_value('first.foo')
    '42'
    >>> parsed.get_opt_value('first.ham') is None
    True
    >>> parsed.get_opt_value('SPAM_SPAM_SPAM.glam') is None
    True
    >>> parsed.get_opt_value('second.bar')
    'milk://Bar'

    A few more examples:

    >>> class SimpleConfigSpecEgg:
    ...     def __init__(self, s):
    ...         self._s = s
    ...     def hatch_out(self, format_data_mapping=None):
    ...         if format_data_mapping is None:
    ...             return self._s
    ...         return self._s.format_map(format_data_mapping)
    ...
    >>> s1 = '''
    ...      1-indented
    ...     zero-indented
    ...                   '''
    >>> s2 = SimpleConfigSpecEgg('''Zero-indented
    ...   ZERO-indented
    ...      3-indented
    ...
    ... ''')
    >>> s3 = '''  zeRO-indented
    ...               2-indented
    ...                                   \t
    ...             ZeRo-indented
    ...  \t
    ...              1-indented'''
    >>> join_config_specs(s1) == '''
    ...  1-indented
    ... zero-indented
    ... '''
    True
    >>> join_config_specs(s1, s2) == '''
    ...  1-indented
    ... zero-indented
    ...
    ... Zero-indented
    ... ZERO-indented
    ...    3-indented
    ...
    ... '''
    True
    >>> join_config_specs(s1, s2, s3) == '''
    ...  1-indented
    ... zero-indented
    ...
    ... Zero-indented
    ... ZERO-indented
    ...    3-indented
    ...
    ...
    ... zeRO-indented
    ...   2-indented
    ...
    ... ZeRo-indented
    ...
    ...  1-indented'''
    True
    >>> join_config_specs(s3, s2, s1) == '''zeRO-indented
    ...   2-indented
    ...
    ... ZeRo-indented
    ...
    ...  1-indented
    ... Zero-indented
    ... ZERO-indented
    ...    3-indented
    ...
    ...
    ...
    ...  1-indented
    ... zero-indented
    ... '''
    True
    >>> join_config_specs()
    ''
    >>> join_config_specs('')
    ''
    >>> join_config_specs('', '')
    '\n'
    >>> join_config_specs(s1, '')
    '\n 1-indented\nzero-indented\n\n'
    >>> join_config_specs(' ', s1)
    '\n\n 1-indented\nzero-indented\n'
    >>> join_config_specs(s1, '   0-indented \t x ')
    '\n 1-indented\nzero-indented\n\n0-indented    x '
    """
    return '\n'.join(map(as_config_spec_string, config_specs))



def combined_config_spec(config_spec, /):
    r"""
    Given a *config spec* (or formattable *config spec pattern*), make a
    [descriptor](https://docs.python.org/3/reference/datamodel.html#implementing-descriptors)
    ready to be assigned to an attribute of a class (hereafter referred
    to as the *owning class*) -- to make it possible to automatically
    combine that *config spec* (or formattable *config spec pattern*)
    with another *config spec* (or, respectively, *config spec pattern*)
    accessible as the same-named attribute of a superclass (and,
    *if* this tool is used consistently, of further superclasses,
    recursively -- along the [method resolution
    order](https://rhettinger.wordpress.com/2011/05/26/super-considered-super/).

    >>> class OwningClass:
    ...     my_config_spec = combined_config_spec('''
    ...         [well_informed_circles]
    ...         how_many :: int
    ...         radius    =    1.234567::float
    ...     ''')
    ...
    >>> class AnotherOwningClass(OwningClass):
    ...     my_config_spec = combined_config_spec('''
    ...         [well_informed_circles]
    ...         how_many = 42 :: int
    ...         filled :: bool
    ...
    ...         [vehicle_horn]
    ...         sound = beep, beep   ; no converter spec so the default one (`str`) is implied
    ...     ''')
    ...
    >>> class YetAnotherOwningClass(AnotherOwningClass):
    ...     my_config_spec = combined_config_spec('''
    ...         [vehicle_horn]
    ...         sound  :: str
    ...     ''')

    >>> lone_egg = OwningClass.my_config_spec
    >>> isinstance(lone_egg, ConfigSpecEgg)  # (see `ConfigSpecEgg` protocol definition)
    True
    >>> lone = as_config_spec_string(lone_egg)
    >>> lone == (
    ... # Here we have the first config spec string intact
    ... # (except that indentation in it has been reduced)
    ... # because there were no specs to combine it with:
    ... '''
    ... [well_informed_circles]
    ... how_many :: int
    ... radius    =    1.234567::float
    ... ''')
    True
    >>> instance = OwningClass()
    >>> lone == as_config_spec_string(instance.my_config_spec)  # (same when got from instance)
    True

    >>> combined_egg = AnotherOwningClass.my_config_spec
    >>> isinstance(combined_egg, ConfigSpecEgg)
    True
    >>> combined = as_config_spec_string(combined_egg)
    >>> combined == (
    ... # Here we have the result of parsing and *combining* two config specs (from
    ... # `OwningClass.my_config_spec` and `AnotherOwningClass.my_config_spec`):
    ... '''
    ... [well_informed_circles]
    ... how_many = 42 :: int
    ... radius = 1.234567 :: float
    ... filled :: bool
    ...
    ... [vehicle_horn]
    ... sound = beep, beep
    ... ''')
    True
    >>> instance = AnotherOwningClass()
    >>> combined == as_config_spec_string(instance.my_config_spec)  # (same when got from instance)
    True

    >>> as_config_spec_string(YetAnotherOwningClass.my_config_spec) == (
    ... # Here we have the result of parsing and *combining*
    ... # all three config specs:
    ... '''
    ... [well_informed_circles]
    ... how_many = 42 :: int
    ... radius = 1.234567 :: float
    ... filled :: bool
    ...
    ... [vehicle_horn]
    ... sound
    ... ''')
    True

    ***

    Args (positional-only):
        `config_spec` (a `str` or `ConfigSpecEgg`-compliant object):
            A *config spec* (or formattable *config spec pattern*) to be
            combined -- by the resultant attribute descriptor -- with a
            *config spec* (or, respectively, a formattable *config spec
            pattern*) assigned to the relevant attribute of a superclass
            (if any) of the owning class.

            Technical details: the value of the `config_spec` argument
            -- after conversion to a `ConfigSpecEgg`-compliant object,
            which includes also applying the `as_config_spec_string()`
            utility function -- becomes the resultant descriptor's
            *local value* (see the docs of the `CombinedWithSuper`
            class defined in `n6lib.class_helpers` for an explanation
            of the term *local value*).

    Returns:
        An attribute descriptor (whose type is a subclass of the
        `n6lib.class_helpers.CombinedWithSuper` class) that wraps the
        given `config_spec`. When an attempt is made to get (from the
        owning class or its instance) the attribute handled by this
        descriptor, the result is as follows.

        * (1) If any superclass of the owning class has the same-named
          attribute:

          * (a) *if* the value of that same-named attribute does not
            contain any of `Config.CONFIG_SPEC_RESERVED_CHARS` *and*
            is acceptable by `as_config_spec_string()`, the result is a
            `ConfigSpecEgg`-compliant object whose method `hatch_out()`,
            when invoked, will produce a `str` instance being a
            **combined** *config spec*;

            the value returned by `hatch_out()` will include all config
            sections and options copied from the *superclass's config
            spec*, updated/overridden with all sections and options from
            `config_spec` -- with such a **consistency rule** that the
            aforementioned updating/overriding must *not* change, add or
            remove the converter spec of any already encountered option
            or free options marker (except that adding or removing `str`,
            which is the default converter spec, is obviously OK, though
            meaningless); if this rule is violated then an exception
            whose type is `ConfigSpecEggError` (or a subclass of it)
            will be raised;

          * (b) *if* the value of the same-named attribute *either*
            contains some of `Config.CONFIG_SPEC_RESERVED_CHARS`, which
            must cause `ValueError`, *or* causes that an underlying
            call to the `as_config_spec_string()` function raises an
            exception -- *then* that exception bubbles up (see the docs
            of `as_config_spec_string()` for a description of error
            cases possible when a single argument is passed to that
            function).

        * (2) Otherwise, i.e., if no superclass of the owning class has
          the same-named attribute (so there is nothing to *combine*):

          the resultant value is a `ConfigSpecEgg`-compliant object
          whose `hatch_out()` method, when invoked, will produce a `str`
          instance being a *config spec* equivalent to (or based only
          on) the given `config_spec` argument value.

        Note: an exception may bubble up from any of the aforementioned
        invocations of `hatch_out()`. In such cases, typically, it will
        be of type `ConfigSpecEggError` (or a subclass of it), either
        coming directly from that object's internal machinery (for
        example, when some necessary keys are missing from the *format
        data mapping*, if passed to `hatch_out()`), or wrapping another
        exception (which, in particular, may be similar to exceptions
        raised by the `parse_config_spec()` function; see its docs).

        ***

        The returned descriptor has its own implementation of the
        [`__set_name__()`](https://docs.python.org/3/reference/datamodel.html#object.__set_name__)
        special method which may raise:

        * `ValueError`:
          -- if the given *config spec* (or *config spec pattern*)
          contains some of `Config.CONFIG_SPEC_RESERVED_CHARS`;

        * any exception from `as_config_spec_string(config_spec)`
          -- see the docs of the `as_config_spec_string()` function.

        Note that when `__set_name__()` is invoked by the Python class
        creation machinery (when the owning class is created) and an
        exception is obtained from that invocation then Python raises
        `RuntimeError` (with that exception as its *context* exception).

        ***

        *Advice:* the preferred way of obtaining a final *config spec*
        string from the `ConfigSpecEgg`-compliant object provided by the
        returned descriptor (possibly wrapping a formattable *config spec
        pattern*) is to make use of the `as_config_spec_string()` utility
        function, instead of invoking the object's method `hatch_out()`
        directly. That makes it possible to handle in a unified way two
        forms of config specs (or config specs patterns): plain strings
        and `ConfigSpecEgg`-compliant objects; `as_config_spec_string()`
        is able to handle each of them. (See also: various examples in
        the docs of this class as well as the *additional note* in the
        docs of the `ConfigSpecEgg.hatch_out()` method's definition.)

    ***

    More examples (including a few complex cases and some corner cases):

    >>> class Root:
    ...
    ...     ni_spec = combined_config_spec('''
    ...         string = Tralala    ; note: the default *converter spec* is `str`
    ...         number :: int
    ...
    ...         [first]
    ...         abra :: int
    ...         kadabra = hop-hop :: str
    ...         ... :: bool
    ...
    ...         [second]
    ...         torba.borba =       ; note: the default *converter spec* is `str`
    ...         ósme.smake = ""     ; note: the default *converter spec* is `str`
    ...     ''')
    ...
    ...     nu_spec_pattern = combined_config_spec('''
    ...         [{owning_class_name}]
    ...     ''')
    ...
    ...     def __init__(self, /, nu_format_data_mapping=None):
    ...         self.ni = as_config_spec_string(self.ni_spec)
    ...         if nu_format_data_mapping is not None:
    ...             nu_format_data_mapping['owning_class_name'] = type(self).__qualname__
    ...         self.nu = as_config_spec_string(
    ...             self.nu_spec_pattern,
    ...             format_data_mapping=nu_format_data_mapping)
    ...
    >>> class A(Root):
    ...
    ...     ni_spec = combined_config_spec('''
    ...         string = Rymcymcym::    str
    ...         number = 2 :: int
    ...
    ...         [first]
    ...         kadabra   =   BUM albo ŁUP   ; note: the default *converter spec* is `str`
    ...         świekra-konstabla :: list_of_int
    ...     ''')
    ...
    ...     nu_spec_pattern = combined_config_spec('''
    ...         [{owning_class_name}]
    ...         {x_name} = {x_default!r} :: {x_conv!s}
    ...     ''')
    ...
    >>> a = A(nu_format_data_mapping={
    ...     'x_name' : 'x            ',
    ...     'x_default' : 42,
    ...     'x_conv' : '      int    ',
    ... })
    >>> a.ni == '''
    ... string = Rymcymcym
    ... number = 2 :: int
    ...
    ... [first]
    ... abra :: int
    ... kadabra = BUM albo ŁUP
    ... świekra-konstabla :: list_of_int
    ... ... :: bool
    ...
    ... [second]
    ... torba.borba = ""
    ... ósme.smake = ""
    ... '''
    True
    >>> a.nu == '''
    ... [A]
    ... x = 42 :: int
    ... '''
    True
    >>> a_no_format = A()
    >>> a_no_format.nu == '''
    ... [{owning_class_name}]
    ... {x_name} = {x_default!r} :: {x_conv!s}
    ... '''
    True

    If formatting is requested (i.e., a *format data mapping* is given)
    then missing keys cause an exception (`ConfigSpecEggError` or its
    subclass) -- but, generally speaking, *only* for those missing keys
    that are necessary to format the fragments that the final *combined*
    result includes.

    >>> A(nu_format_data_mapping={'x_default': 42})                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... `....A.nu_spec_pattern` ...: 'x_name', 'x_conv')
    >>> A(nu_format_data_mapping={})                                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... `....A.nu_spec_pattern` ...: 'x_name', 'x_default', 'x_conv')

    Note: a value wrapped by our descriptor (its *local value*) may also
    be a `ConfigSpecEgg`-compliant object itself.

    >>> class WeirdConfigSpecEgg:
    ...     def __init__(self, s):
    ...         self._s = s
    ...     def hatch_out(self, format_data_mapping=None):
    ...         if format_data_mapping is not None:
    ...             return "excuse: I didn't know you were called Dennis! :: str"
    ...         return self._s
    ...
    >>> class B(Root):
    ...
    ...     ni_spec = combined_config_spec(WeirdConfigSpecEgg('''
    ...         number: 222 :: int
    ...
    ...         [first]
    ...         kadabra   =   BUM, ale na pewno nie ŁUP::str
    ...         hokus-pokus
    ...
    ...         [second]
    ...         torba.borba=Morele Bax
    ...     '''))
    ...
    ...     nu_spec_pattern = combined_config_spec(WeirdConfigSpecEgg('''
    ...         [{x_name}]
    ...         baba : Jaga
    ...         {anything}
    ...     '''))
    ...
    >>> b = B(nu_format_data_mapping={
    ...     'x_name': 'xyz',
    ...     'x_default': '...unused...',
    ...     'anything': ' \t \t \r\n\t \t ',
    ... })
    >>> b.ni == '''
    ... string = Tralala
    ... number = 222 :: int
    ...
    ... [first]
    ... abra :: int
    ... kadabra = BUM, ale na pewno nie ŁUP
    ... hokus-pokus
    ... ... :: bool
    ...
    ... [second]
    ... torba.borba = Morele Bax
    ... ósme.smake = ""
    ... '''
    True
    >>> b.nu == '''
    ... [B]
    ...
    ... [xyz]
    ... baba = Jaga
    ... '''
    True
    >>> b2 = B(nu_format_data_mapping={
    ...     'x_name': 'xyz',
    ...     'x_default': '...unused...',
    ...     'anything': ('oH = No! More Lemmings! :: list_of_bytes\n'
    ...                  'BRAT = Maynard :: bytes'),
    ... })
    >>> b2.nu == '''
    ... [B]
    ...
    ... [xyz]
    ... baba = Jaga
    ... oh = No! More Lemmings! :: list_of_bytes
    ... brat = Maynard :: bytes
    ... '''
    True
    >>> b_no_format = B()       # without formatting
    >>> b_no_format.nu == '''
    ... [{owning_class_name}]
    ...
    ... [{x_name}]
    ... baba = Jaga
    ... {anything}
    ... '''
    True
    >>> B(nu_format_data_mapping={'x_default': 42})                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... `....B.nu_spec_pattern` ...: 'x_name', 'anything')
    >>> B(nu_format_data_mapping={})                                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... `....B.nu_spec_pattern` ...: 'x_name', 'anything')

    Note: multiple inheritance (of "diamond" shapes) is supported as well
    without any trouble... Enjoy:

    >>> class BA(B, A):
    ...
    ...     ni_spec = combined_config_spec('''
    ...         ... :: float
    ...
    ...         [second]
    ...         ene.due = !@#$::%^=&*=()::{}[]::some-<VERY.CUSTOM>-converter
    ...     ''')
    ...
    ...     nu_spec_pattern = combined_config_spec('''
    ...         [{owning_class_name}]
    ...         proto = HTTPS  ::  another-<VERY.CUSTOM>-converter
    ...         {anything}
    ...
    ...         [{x_name}]
    ...         siostra: Małgosia
    ...         brat: Jaś :: bytes
    ...     ''')
    ...
    >>> BA.__mro__ == (BA, B, A, Root, object)
    True
    >>> ba = BA(nu_format_data_mapping={
    ...     'x_name' : 'oh',
    ...     'x_default': "yeah, yeah, yeah, it's goal!",
    ...     'x_conv' : 'list_of_bytes',
    ...     'anything': ('\n'
    ...                  '\nghijk  :42.0::  float'
    ...                  '\n'
    ...                  '\n'
    ...                  '\nklmn:   ; comment '
    ...                  '\n'
    ...                  '\n opq,'
    ...                  '\n\trst,'
    ...                  '\n'
    ...                  '\n# comment'
    ...                  '\n     uvw   '
    ...                  '\n'
    ...                  '\n :: list_of_str  '
    ...                  '\n'
    ...                  '\n'),
    ... })
    >>> ba.ni == '''
    ... string = Rymcymcym
    ... number = 222 :: int
    ... ... :: float
    ...
    ... [first]
    ... abra :: int
    ... kadabra = BUM, ale na pewno nie ŁUP
    ... świekra-konstabla :: list_of_int
    ... hokus-pokus
    ... ... :: bool
    ...
    ... [second]
    ... torba.borba = Morele Bax
    ... ósme.smake = ""
    ... ene.due = !@#$::%^=&*=()::{}[] :: some-<VERY.CUSTOM>-converter
    ... '''
    True
    >>> ba.nu == '''
    ... [BA]
    ... oh = "yeah, yeah, yeah, it's goal!" :: list_of_bytes
    ... proto = HTTPS :: another-<VERY.CUSTOM>-converter
    ... ghijk = 42.0 :: float
    ... klmn = opq,
    ...   rst,
    ...   uvw :: list_of_str
    ...
    ... [oh]
    ... baba = Jaga
    ... ghijk = 42.0 :: float
    ... klmn = opq,
    ...   rst,
    ...   uvw :: list_of_str
    ... siostra = Małgosia
    ... brat = Jaś :: bytes
    ... '''
    True
    >>> di = {
    ...     'x_name' : 'oh',
    ...     # Note: here we do not include 'x_default' because it is
    ...     # not necessary to format a fragment that the combined
    ...     # result will include. The situation of 'x_conf` is similar
    ...     # but we need to include it because it is a converter spec
    ...     # -- if it was ommited here then differing converter specs
    ...     # would be detected (and such a condition is treated as an
    ...     # error).
    ...     'x_conv': 'list_of_bytes',
    ...     'anything': ('oH = No! More Lemmings! :: list_of_bytes\n'
    ...                  'BRAT = Maynard :: bytes'),
    ... }
    >>> ba2 = BA(nu_format_data_mapping=di)
    >>> from n6lib.common_helpers import CIDict
    >>> ba3 = BA(                                #    Here: showing that mapping types
    ...     nu_format_data_mapping=CIDict(di))   # <- other than `dict` are also OK.
    >>> ba2.nu == ba3.nu == (
    ... # Note: component *config spec patterns* are transformed into
    ... # formatted *config specs* first, and only then those formatted
    ... # specs are combined. Here, in particular, note how the results
    ... # of formatting with items from the given *format data mapping*
    ... # affect what is shadowed by what: the `oh` option value from
    ... # the `A` class is shadowed (in the `BA` section) by the `oh`
    ... # option value from the mapping (i.e., '"yeah, yeah, yeah, it's
    ... # goal!"' is shadowed by 'No! More Lemmings!'); and the 'brat'
    ... # option value from the mapping is shadowed (in the `oh`
    ... # section) by the `brat` option value from the `BA` class
    ... # (i.e., 'Maynard' is shadowed by 'Jaś').
    ... '''
    ... [BA]
    ... oh = No! More Lemmings! :: list_of_bytes
    ... proto = HTTPS :: another-<VERY.CUSTOM>-converter
    ... brat = Maynard :: bytes
    ...
    ... [oh]
    ... baba = Jaga
    ... oh = No! More Lemmings! :: list_of_bytes
    ... brat = Jaś :: bytes
    ... siostra = Małgosia
    ... ''')
    True
    >>> ba_no_format = BA()
    >>> ba_no_format.nu == '''
    ... [{owning_class_name}]
    ... {x_name} = {x_default!r} :: {x_conv!s}
    ... proto = HTTPS :: another-<VERY.CUSTOM>-converter
    ... {anything}
    ...
    ... [{x_name}]
    ... baba = Jaga
    ... {anything}
    ... siostra = Małgosia
    ... brat = Jaś :: bytes
    ... '''
    True

    >>> BA({'x_name' : 'oh',                                            # doctest: +ELLIPSIS
    ...     'x_conv': 'list_of_bytes',
    ...     # Here the value corresponding to the 'anything' key does
    ...     # *not* contain the `oh` option -- so the `oh` option value
    ...     # from the `A` class would *not* be shadowed, so a value
    ...     # corresponding to the 'x_default' key remains necessary to
    ...     # format a fragment that the combined result would include.
    ...     # Therefore, here the lack of 'x_default' will cause an error.
    ...     'anything': ('tralalalalalala = No! More Lemmings! :: list_of_bytes\n'
    ...                  'BRAT = Maynard :: bytes'),
    ... })
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... `....BA.nu_spec_pattern` ...: 'x_default')

    ***

    Apart from missing format data keys, several other conditions also
    cause exceptions...

    The consistency rule described earlier is that when an option is
    shadowed its *converter spec* should not change:

    >>> class N:
    ...     config_spec_pattern = combined_config_spec('''
    ...         [grass]
    ...         color = {color} :: str
    ...     ''')
    ...
    >>> class P(N):
    ...     config_spec_pattern = combined_config_spec('''
    ...         [grass]
    ...         color = {color} :: list_of_str
    ...     ''')
    ...
    >>> as_config_spec_string(P.config_spec_pattern)                           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ...differing *converter specs* of the option `color`...
    >>> as_config_spec_string(P.config_spec_pattern, {'color': 'green'})       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ...differing *converter specs* of the option `color`...

    The same applies to *free options converter specs*:

    >>> class Q:
    ...     hakuna_matata = combined_config_spec('''
    ...         [jungle]
    ...         ...          ; (here: no converter spec, so `str` is implied`)
    ...     ''')
    ...
    >>> class R(Q):
    ...     hakuna_matata = combined_config_spec('''
    ...         [jungle]
    ...         ... :: bool
    ...     ''')
    ...
    >>> as_config_spec_string(R.hakuna_matata)                                 # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ...differing *free options converter specs*...
    >>> as_config_spec_string(R.hakuna_matata, di)                             # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ...differing *free options converter specs*...

    Note, however, that a `:: str` converter spec declaration is
    equivalent to the lack of any explicit converter spec declaration,
    because `str` is the default converter spec. So in the following
    cases we do *not* have exceptions:

    >>> class P2(N):
    ...     config_spec_pattern = combined_config_spec('''
    ...         [grass]
    ...         color = {color}
    ...     ''')
    ...
    >>> as_config_spec_string(P2.config_spec_pattern)== '''
    ... [grass]
    ... color = {color}
    ... '''
    True
    >>> as_config_spec_string(P2.config_spec_pattern, {'color': 'green'})== '''
    ... [grass]
    ... color = green
    ... '''
    True
    >>> class R2(Q):
    ...     hakuna_matata = combined_config_spec('''
    ...         [jungle]
    ...         ... :: str
    ...     ''')
    ...
    >>> as_config_spec_string(R2.hakuna_matata) == '''
    ... [jungle]
    ... ...
    ... '''
    True
    >>> as_config_spec_string(R2.hakuna_matata, di) == '''
    ... [jungle]
    ... ...
    ... '''
    True

    Whereas shadowing a converter spec with a different one is forbidden,
    shadowing a default value with a different one is perfectly OK:

    >>> class Owning:
    ...     my_config_spec = combined_config_spec('''
    ...         [vehicle_horn]
    ...         sound = beep, beep
    ...     ''')
    ...
    >>> class OwningSub(Owning):
    ...     my_config_spec = combined_config_spec('''
    ...         [vehicle_horn]
    ...         sound = AWOOGA!
    ...     ''')
    >>> as_config_spec_string(OwningSub.my_config_spec) == (
    ... as_config_spec_string(OwningSub.my_config_spec, di)) == (
    ... '''
    ... [vehicle_horn]
    ... sound = AWOOGA!
    ... ''')
    True

    Also, note that it is perfectly OK to have a *required* option
    (i.e., without a default value) shadowed by a *non-required* one
    (i.e., with a default value), or a *non-required* option shadowed
    by a *required* one:

    >>> class J:
    ...     config_spec = combined_config_spec('''
    ...         [forest]
    ...         leaves = 3 :: int        ; *non-required* (has default value)
    ...     ''')
    ...
    >>> class K(J):
    ...     config_spec = combined_config_spec('''
    ...         [forest]
    ...         leaves :: int            ; *required* (has *no* default value)
    ...     ''')
    ...
    >>> as_config_spec_string(K.config_spec) == as_config_spec_string(K.config_spec, di) == '''
    ... [forest]
    ... leaves :: int
    ... '''
    True
    >>> class L:
    ...     config_spec = combined_config_spec('''
    ...         [forest]
    ...         leaves :: int            ; *required* (has *no* default value)
    ...     ''')
    ...
    >>> class M(L):
    ...     config_spec = combined_config_spec('''
    ...         [forest]
    ...         leaves = 3 :: int        ; *non-required* (has default value)
    ...     ''')
    ...
    >>> as_config_spec_string(M.config_spec) == as_config_spec_string(M.config_spec, di) == '''
    ... [forest]
    ... leaves = 3 :: int
    ... '''
    True

    ***

    Below: various errors related to wrong contents of config specs (in
    different stages of the descriptors' and eggs' lifetimes)...

    >>> class Problematic:                                    # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     x = combined_config_spec('\0\1')  # (<- reserved characters)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> class EggContainingReservedChars:
    ...     def hatch_out(self, format_data_mapping=None):
    ...         return '\0\1'  # (<- reserved characters)
    ...
    >>> class AnotherProblematic:                             # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     x = combined_config_spec(EggContainingReservedChars())
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> class FooBarBaz:
    ...     x = EggContainingReservedChars()
    ...
    >>> class FooBarBazSub(FooBarBaz):
    ...     x = combined_config_spec('spam = {glam}')
    ...
    >>> as_config_spec_string(FooBarBazSub.x, {'glam': 'ram-pam-pam'})  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ...keys missing...(or some reserved characters in the config spec?)

    Obviously, incorrect (unparseable) config specs are also
    unacceptable:

    >>> class SomeWithUnparseable:
    ...     x = combined_config_spec('''
    ...             bad_indent :: int
    ...         spam = {glam}
    ...     ''')
    ...
    >>> class InnocentSubclass(SomeWithUnparseable):
    ...     x = combined_config_spec('jaki_pan = taki_kran')
    ...
    >>> as_config_spec_string(SomeWithUnparseable.x)                    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... - ValueError: ...

    >>> as_config_spec_string(InnocentSubclass.x)                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... - ValueError: ...

    ***

    Below: various errors related to wrong types (in different stages of
    the descriptors' and eggs' lifetimes)...

    >>> class Erroneous:                                      # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     x = combined_config_spec(123)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> class BadEgg:
    ...     def hatch_out(self, format_data_mapping=None):
    ...         return 123
    ...
    >>> class AnotherErroneous:                               # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     x = combined_config_spec(BadEgg())
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> class Some:
    ...     x = 123
    ...
    >>> class SomeErroneous(Some):
    ...     x = combined_config_spec('qwerty = 42 :: int')
    ...
    >>> SomeErroneous.x                                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> class WithBadEgg:
    ...     x = BadEgg()
    ...
    >>> class SubclassWithBadEgg(WithBadEgg):
    ...     x = combined_config_spec('qwerty = 42 :: int')
    ...
    >>> as_config_spec_string(SubclassWithBadEgg.x)                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... - TypeError: ...
    >>> as_config_spec_string(SubclassWithBadEgg.x, {'a': 'b'})         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib...nfigSpecEggError: ... - TypeError: ...

    ***

    It is worth to mention that the `combined_config_spec()` tool is
    especially useful when it is used in conjunction with `ConfigMixin`.
    See the relevant example in the docs of the latter.

    ***

    One more remark: if our class attribute was set to a config spec
    *string* or *egg* (*not* to our special descriptor wrapping it) then
    it *still* can be combined with other values provided by our special
    descriptor but *only* as the "root" attribute, that is, it will
    *always* completely replace any same-named attributes placed above
    it in the inheritance hierarchy of owning classes:

    >>> class ReplacingMixin:
    ...     ni_spec = '''
    ...         [second]
    ...         abcd :: int    ; comment
    ...         nobody-expect = [{(The Spanish Inquisition!)}] :: str
    ...     '''
    ...     nu_spec_pattern = '''
    ...         [-=#=-_*_{owning_class_name}_*_-=#=-]
    ...         efgh :: float    ; comment comment comment
    ...         and-now-for-something-completely-different = {{It's}} Man!
    ...     '''
    ...
    >>> class ReplacingBA(ReplacingMixin, BA):
    ...     ni_spec = combined_config_spec('''
    ...         [second]
    ...         abcd = 12345678987654321 :: int
    ...         aaa = hm... :: str
    ...     ''')
    ...     nu_spec_pattern = combined_config_spec('''
    ...         [-=#=-_*_{owning_class_name}_*_-=#=-]
    ...         and-now-for-something-completely-different = {{It's}} {It's}!!!!!!!!!!!!
    ...     ''')
    ...
    >>> ReplacingBA.__mro__ == (ReplacingBA, ReplacingMixin, BA, B, A, Root, object)
    True
    >>> repl_ba = ReplacingBA(nu_format_data_mapping={"It's": 'swimming'})
    >>> repl_ba.ni == '''
    ... [second]
    ... abcd = 12345678987654321 :: int
    ... nobody-expect = [{(The Spanish Inquisition!)}]
    ... aaa = hm...
    ... '''
    True
    >>> repl_ba.nu == '''
    ... [-=#=-_*_ReplacingBA_*_-=#=-]
    ... efgh :: float
    ... and-now-for-something-completely-different = {It's} swimming!!!!!!!!!!!!
    ... '''
    True
    >>> repl_ba_no_format = ReplacingBA()
    >>> repl_ba_no_format.nu == '''
    ... [-=#=-_*_{owning_class_name}_*_-=#=-]
    ... efgh :: float
    ... and-now-for-something-completely-different = {{It's}} {It's}!!!!!!!!!!!!
    ... '''
    True
    >>> class WeirdReplacingMixin:
    ...     ni_spec = WeirdConfigSpecEgg(ReplacingMixin.ni_spec)
    ...     nu_spec_pattern = WeirdConfigSpecEgg(ReplacingMixin.nu_spec_pattern)
    ...
    >>> class WeirdReplacingBA(WeirdReplacingMixin, BA):
    ...     ni_spec = combined_config_spec('''
    ...         [second]
    ...         abcd = 12345678987654321 :: int
    ...         aaa = hm... :: str
    ...     ''')
    ...     nu_spec_pattern = combined_config_spec('''
    ...         [-=#=-_*_{owning_class_name}_*_-=#=-]
    ...         and-now-for-something-completely-different = {{It's}} {It's}!!!!!!!!!!!!
    ...     ''')
    ...
    >>> WeirdReplacingBA.__mro__ == (WeirdReplacingBA, WeirdReplacingMixin, BA, B, A, Root, object)
    True
    >>> weird_repl_ba = WeirdReplacingBA(nu_format_data_mapping={"It's": 'swimming'})
    >>> weird_repl_ba.ni == '''
    ... [second]
    ... abcd = 12345678987654321 :: int
    ... nobody-expect = [{(The Spanish Inquisition!)}]
    ... aaa = hm...
    ... '''
    True
    >>> weird_repl_ba.nu == (
    ... # Note this (see also the definition of `WeirdConfigSpecEgg.hatch_out()`):
    ... '''
    ... excuse = I didn't know you were called Dennis!
    ...
    ... [-=#=-_*_WeirdReplacingBA_*_-=#=-]
    ... and-now-for-something-completely-different = {It's} swimming!!!!!!!!!!!!
    ... ''')
    True
    >>> weird_repl_ba_no_format = WeirdReplacingBA()
    >>> weird_repl_ba_no_format.nu == '''
    ... [-=#=-_*_{owning_class_name}_*_-=#=-]
    ... efgh :: float
    ... and-now-for-something-completely-different = {{It's}} {It's}!!!!!!!!!!!!
    ... '''
    True
    """
    return _CombinedConfigSpecDescriptor(config_spec)



###
# 2. Other/alternative solutions
###

class ConfigString(str):

    r"""
    A `str` subclass providing handy ways of raw-string config manipulation.

    Constructor args (positional-only):
        `s` (`str`; empty by default):
            The input string.

    `ConfigString` is a subclass of `str` that provides several
    additional methods to operate on `*.ini`-like-formatted
    configurations -- including getting, adding, removing and
    substitution of configuration sections and options (preserving
    formatting and comments related to sections/options that are
    not touched).

    Note #1: This class uses the *universal newlines* approach for
    splitting lines originating from an input string, i.e., the
    following three different newline styles are recognized: `\n`,
    `\r` and `\r\n`; on the other hand, all resultant contents
    contain `\n`-only (Unix-style) newlines.

    Note #2: Duplicate section names and duplicate option names (in a
    section) are *not* accepted.

    Note #3: Due to some specific requirements, but also for certain
    historical reasons, there are syntactic differences -- rather
    marginal from practical point of view -- from the standard
    `configparser` stuff (which is used by `Config` et consortes
    to parse actual configuration files), especially from its
    modern-Python-3.x-specific flavor. Most important of those
    differences are as follows:

    * ASCII whitespace characters between a section name and the
      enclosing square brackets are ignored (as in the case of, for
      example, the OpenSSL configuration format);

    * section names cannot contain `.` or any ASCII whitespace
      characters (obviously, `]` is also excluded);

    * option names cannot contain any ASCII whitespace characters
      (obviously, `:` and `=` are also excluded), and they cannot
      start with `[` or `]`;

    * options can be placed also in the area above any explicit section
      header -- then they belong to an implicitly created section whose
      name is an empty string;

    * options *without values* are supported (the behavior is similar
      to that when the `configparser`'s `allow_no_value` flag is set;
      related parsing details are close to the behavior of old Py-2.7's
      `ConfigParser`);

    * modern-`configparser`-style indentations are not supported (note,
      however, that traditional indented continuation lines are OK;
      related parsing details are close to the behavior of old Py-2.7's
      `ConfigParser`);

    * the `configparser`-style interpolation mechanisms are *not*
      implemented.

    >>> cs = ConfigString('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... [second]
    ...
    ... bAR = http://\t
    ...   example.com/''')  # (note the multiline option `bAR`)

    >>> cs.contains('first')
    True

    >>> cs.contains('first.foo')
    True

    >>> cs.contains('first.Foo')  # option names are *case-insensitive*
    True

    >>> cs.contains('First.foo')  # section names are *case-sensitive*
    False

    >>> cs.contains('third')
    False

    >>> cs.contains('first.bAR')
    False

    >>> cs.get('first')
    ConfigString('[ first ]\nfoo = 42 ; comment\n\n\nham:spam')

    >>> cs.get('first.foo')  # (note that one trailing '\n' is stripped out)
    ConfigString('foo = 42 ; comment\n\n')

    >>> cs.get('first.Ham')
    ConfigString('ham:spam')

    >>> cs.get('second.bar')
    ConfigString('bAR = http://\t\n  example.com/')

    >>> cs.insert_above('second', 'x = y\na = b') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... x = y
    ... a = b
    ... [second]
    ...
    ... bAR = http://\t
    ...   example.com/''')
    True

    >>> cs.insert_below('second.bar', 'x = y\na = b') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... [second]
    ...
    ... bAR = http://\t
    ...   example.com/
    ... x = y
    ... a = b''')
    True

    >>> cs.substitute('second', 'x = y\na = b') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... x = y
    ... a = b''')
    True

    >>> cs.substitute('second.BAR', 'x = y\na = b') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... [second]
    ...
    ... x = y
    ... a = b''')
    True

    >>> cs.remove('second') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam''')
    True

    >>> cs.remove('second.bAR') == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... [second]
    ... ''')
    True

    >>> cs.remove('second.Bar').substitute('first.foo', 'baz = 43'
    ... ) == ('''
    ... [ first ]
    ... baz = 43
    ... ham:spam
    ... [second]
    ... ''')
    True

    >>> cs.remove('second.Bar').substitute('first.foo', 'baz = 43\n'
    ... ) == (
    ... # (note that one trailing '\n', if any,
    ... # is stripped out from the given value)
    ... '''
    ... [ first ]
    ... baz = 43
    ... ham:spam
    ... [second]
    ... ''')
    True

    >>> cs.remove('second.Bar').substitute('first.foo', 'baz = 43\n\n'
    ... ) == ('''
    ... [ first ]
    ... baz = 43
    ...
    ... ham:spam
    ... [second]
    ... ''')
    True

    >>> cs.remove('second.Bar').substitute('first.foo', '\n\nbaz = 43\n\n'
    ... ) == ('''
    ... [ first ]
    ...
    ...
    ... baz = 43
    ...
    ... ham:spam
    ... [second]
    ... ''')
    True

    >>> (cs.remove('second.Bar').substitute('first.foo', 'baz = 43')
    ... ).get('first.baz')
    ConfigString('baz = 43')

    >>> (cs.remove('second.Bar').substitute('first.foo', 'baz = 43\n')
    ... ).get('first.baz')
    ConfigString('baz = 43')

    >>> (cs.remove('second.Bar').substitute('first.foo', 'baz = 43\n\n')
    ... ).get('first.baz')
    ConfigString('baz = 43\n')

    >>> (cs.remove('second.Bar').substitute('first.foo', '\n\nbaz = 43\n\n')
    ... ).get('first.baz')
    ConfigString('baz = 43\n')

    >>> cs.remove('second.baR').get('second')
    ConfigString('[second]\n')

    >>> cs.get_opt_value('first.foo')
    '42'
    >>> cs.get_opt_value('first.FOO')
    '42'
    >>> cs.get_opt_value('first.ham')
    'spam'
    >>> cs.get_opt_value('second.Bar')
    'http://\nexample.com/'

    >>> cs.get_opt_names('first') == ['foo', 'ham']
    True
    >>> cs.get_opt_names('second') == ['bar']
    True
    >>> cs.get_opt_names('') == []
    True
    >>> cs.get_opt_names('nonexistent')
    Traceback (most recent call last):
      ...
    KeyError: 'nonexistent'

    >>> cs.get_all_sect_names()
    ['first', 'second']

    >>> cs.get_all_sect_and_opt_names() == [
    ...     ('first', ['foo', 'ham']),
    ...     ('second', ['bar']),
    ... ]
    True

    >>> cs == ('''
    ... [ first ]
    ... foo = 42 ; comment
    ...
    ...
    ... ham:spam
    ... [second]
    ...
    ... bAR = http://\t
    ...   example.com/''')
    True

    >>> cs.get('somesect')
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get('somesect.someopt')
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get('first.someopt')
    Traceback (most recent call last):
      ...
    KeyError: 'someopt'

    >>> cs.insert_above('somesect', 'x = y\na = b')
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get_opt_value('somesect.someopt')
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.remove('first.someopt')
    Traceback (most recent call last):
      ...
    KeyError: 'someopt'

    >>> cs.get_opt_value('first')                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ...requires that the location argument specifies an option...


    A few more peculiar cases, some corner cases etc.:

    >>> cs2 = ConfigString('''bar:baz ; inline comment
    ... empty :
    ... empty2 = \t\t\t ; inline comment
    ...
    ... [second]
    ... bar = http://\t ; inline comment ; yeah it is
    ...
    ... # comment
    ...
    ... ; comment ; comment ; comment \t
    ...   ; not a comment  ;  REALLY!
    ...
    ... # comment
    ...
    ...   example.com/; not-a-comment\t
    ...
    ... [fifth]
    ... Some.Option   :   A Value   ;   A Comment
    ... no.value.option \t
    ...   for no-value options
    ...   comments are forbidden
    ...   and continuation lines are ignored \t
    ...
    ... Foo   =   aaa \t ; comment \t
    ...  bbbccc \t ; not-a-comment \t
    ...   zzz \t''')

    >>> cs2.get_opt_value('.BaR')
    'baz'
    >>> cs2.get_opt_value('.empty')
    ''
    >>> cs2.get_opt_value('.empty2')
    ''

    >>> cs2.get_opt_value('second.BaR')
    'http://\n; not a comment  ;  REALLY!\nexample.com/; not-a-comment'

    >>> cs2.get_opt_value('fifth.foo')
    'aaa\nbbbccc \t ; not-a-comment\nzzz'

    >>> cs2.get_opt_value('fifth.some.option')
    'A Value'

    >>> cs2.get_opt_value('fifth.no.value.option') is None
    True
    >>> cs2.get('fifth.no.value.option') == ConfigString(
    ...     'no.value.option \t\n'
    ...     '  for no-value options\n'
    ...     '  comments are forbidden\n'
    ...     '  and continuation lines are ignored \t\n')
    True

    >>> cs2.get_opt_names('') == ['bar', 'empty', 'empty2']
    True
    >>> cs2.get_opt_names('second') == ['bar']
    True
    >>> cs2.get_opt_names('fifth') == [
    ...     'some.option',
    ...     'no.value.option',
    ...     'foo',
    ... ]
    True
    >>> cs2.get_opt_names('nonexistent')
    Traceback (most recent call last):
      ...
    KeyError: 'nonexistent'

    >>> cs2.get_all_sect_names()
    ['', 'second', 'fifth']

    >>> cs2.get_all_sect_and_opt_names() == [
    ...     ('', ['bar', 'empty', 'empty2']),
    ...     ('second', ['bar']),
    ...     ('fifth', [
    ...         'some.option',
    ...         'no.value.option',
    ...         'foo',
    ...     ]),
    ... ]
    True


    >>> ConfigString()
    ConfigString()

    >>> ConfigString('')
    ConfigString()

    >>> ConfigString().get_opt_names('')
    []
    >>> ConfigString().get_opt_names('nonexistent')
    Traceback (most recent call last):
      ...
    KeyError: 'nonexistent'

    >>> ConfigString().get_all_sect_names()
    []

    >>> ConfigString().get_all_sect_and_opt_names()
    []


    >>> ConfigString(' ')
    ConfigString(' ')

    >>> ConfigString('\n')
    ConfigString('\n')

    >>> ConfigString('\r')
    ConfigString('\n')

    >>> ConfigString('\r\n')
    ConfigString('\n')

    >>> ConfigString('\n\n')
    ConfigString('\n\n')

    >>> ConfigString('\r\r')
    ConfigString('\n\n')

    >>> ConfigString('\n\r\n\r\n\r')
    ConfigString('\n\n\n\n')

    >>> ConfigString(' \n \n \n \n ').get_all_sect_names()
    []

    >>> ConfigString(' \n \n \n \n ').get_all_sect_and_opt_names()
    []


    >>> ConfigString('xyz\nabc')
    ConfigString('xyz\nabc')

    >>> ConfigString('xyz\nabc\n')
    ConfigString('xyz\nabc\n')

    >>> ConfigString('xyz\nabc\n\n')
    ConfigString('xyz\nabc\n\n')

    >>> ConfigString('xyz\nabc\r\n\r')
    ConfigString('xyz\nabc\n\n')

    >>> ConfigString('xyz\nabc\n\n').get_opt_names('')
    ['xyz', 'abc']

    >>> ConfigString('xyz\nabc\n\n').get_all_sect_names()
    ['']

    >>> ConfigString('xyz\nabc\n\n').get_all_sect_and_opt_names()
    [('', ['xyz', 'abc'])]


    The constructor can raise `ValueError` when the given string cannot
    be parsed, e.g.:

    >>> ConfigString('xyz\na b c\n\n')           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'a b c' is not valid ...

    >>> ConfigString('''
    ... no_value_opt ; comment illegal for a no-value option
    ... ''')                                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'no_value_opt ; comment ...' is not valid ...

    >>> ConfigString('[wrong.sect]')             # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong.sect]' is not valid ...

    >>> ConfigString('[wrong_opt')               # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt' is not valid ...

    >>> ConfigString('[wrong_opt = val')         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt = val' is not valid ...

    >>> ConfigString(']wrong_opt')               # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt' is not valid ...

    >>> ConfigString(']wrong_opt = val')         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt = val' is not valid ...

    >>> ConfigString('wrong opt')                # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt' is not valid ...

    >>> ConfigString('wrong opt = val')          # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt = val' is not valid ...

    >>> ConfigString('  \n  xyz\n  abc\n\n')     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... '  xyz' looks like a continuation line...

    >>> ConfigString('  [xyz]\n  abc=3')         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... '  [xyz]' looks like a continuation line...

    >>> ConfigString('''
    ... [first]
    ... a = AAA
    ... [second]
    ... z = ZZZ
    ... [first]
    ... b = BBB
    ... c = CCC
    ... ''')
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> ConfigString('''
    ... [first]
    ... a = AAA
    ... b = BBB
    ... a = AAA
    ... ''')
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'

    Also, note that `TypeError` is raised if the argument is not a `str`...

    >>> ConfigString(b'foo = 3')
    Traceback (most recent call last):
      ...
    TypeError: expected a `str` (got an instance of `bytes`)

    ...or when more than one argument is given:

    >>> ConfigString(b'foo = 3', encoding='utf-8')      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    TypeError: ... got an unexpected ...
    """

    def __new__(cls, s='', /):
        if not isinstance(s, str):
            raise TypeError(
                f'expected a `str` (got an instance of '
                f'`{ascii_str(type(s).__qualname__)}`)')
        s = str(s)
        lines = cls._get_lines(s)
        sect_name_to_index_data = cls._get_sect_name_to_index_data(lines)
        new = super().__new__(cls, '\n'.join(lines))
        new._lines = lines
        new._sect_name_to_index_data = sect_name_to_index_data
        return new


    #
    # Public interface extensions
    #

    def __repr__(self):
        content_repr = super().__repr__() if self else ''
        return f'{self.__class__.__qualname__}({content_repr})'


    def contains(self, location):
        """
        Check whether the specified section or option exists.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            `True` if the specified `location` points to an existing
            section or option; otherwise `False`.
        """
        try:
            self._location_to_span(location)
        except KeyError:
            return False
        return True


    def get(self, location):
        """
        Get the contents of the specified `location`.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            A new instance of this class, containing:
            * the text of the section -- if `location` specifies a section.
            * the text of the option -- if `location` specifies an option.

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._from_lines(self._lines[beg:end])


    def insert_above(self, location, text):
        """
        Get the whole contents with `text` inserted above `location`.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (a `str`):
                The text to be inserted.

        Returns:
            A new instance of this class (with additional contents
            inserted as described above).

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.
        """
        beg, _ = self._location_to_span(location)
        return self._get_new_combined(beg, text, beg)


    def insert_below(self, location, text):
        """
        Get the whole contents with `text` inserted below `location`.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (a `str`):
                The text to be inserted.

        Returns:
            A new instance of this class (with additional contents
            inserted as described above).

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.
        """
        _, end = self._location_to_span(location)
        return self._get_new_combined(end, text, end)


    def substitute(self, location, text):
        """
        Get the whole contents with the `location`-specified fragment
        replaced with `text`.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (a `str`):
                The text to be inserted in place of the fragment
                specified with `location`.

        Returns:
            A new instance of this class (with some contents replaced
            as described above).

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._get_new_combined(beg, text, end)


    def remove(self, location):
        """
        Get the whole contents with the `location`-specified fragment
        removed.

        Args/kwargs:
            `location` (a `str`):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            A new instance of this class (with some contents removed
            as described above).

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._get_new_combined(beg, '', end)


    def get_opt_value(self, location_with_opt_name):
        """
        Get the value of the option specified with `location`.

        Args/kwargs:
            `location_with_opt_name` (a `str`):
                It must be a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            An ordinary `str` being the value of the specified option
            or `None` (the latter if the option is a non-value one).

        Raises:
            `KeyError`:
                instantiated with:
                * the section name as the sole argument
                  -- if the specified section does not exist;
                * the option name as the sole argument
                  -- if the specified option does not exist
                  in the specified (and existing) section.

            `ValueError`:
                if the specified location does not include an option
                name.
        """
        opt_value, _ = self._get_opt_value_and_match(location_with_opt_name)
        return opt_value


    def get_opt_names(self, sect_name):
        """
        Get a `list` of options names in the specified section.

        Raises:
            `KeyError`:
                instantiated with the section name as the sole argument,
                if the specified section does not exist; that does *not*
                apply to the '' (empty) section name -- referring to the
                area of the config above any section header; if that
                area does not contain any options then an empty list is
                returned.
        """
        return self._sect_name_to_index_data[sect_name].get_all_opt_names()


    def get_all_sect_names(self):
        """
        Get a `list` of all section names.

        Important: the '' (empty) section name -- referring to the area
        of the config above any section header -- is included only if
        that area contains any options.

        The order of section names is the order of appearance in the
        config.
        """
        return [
            sname
            for sname in sorted(self._sect_name_to_index_data, key=(
                lambda sname: self._sect_name_to_index_data[sname].get_span()))
            if not (sname == '' and
                    not self._sect_name_to_index_data[sname].get_all_opt_names())]


    def get_all_sect_and_opt_names(self):
        """
        Get a `list` of `(<section name>, <list of option names>)` pairs.

        Important: the '' (empty) section name -- referring to the area
        of the config above any section header -- is included only if
        that area contains any options.

        The order of section names and of option names (within each
        `list`) is the order of appearance in the config.
        """
        return [
            (sname, self._sect_name_to_index_data[sname].get_all_opt_names())
            for sname in self.get_all_sect_names()]


    #
    # Non-public constants and helpers
    #

    _COMMENTED_OR_BLANK_LINE_REGEX = re.compile(r'''
        \A
        (?:
            [;\#]
        |
            \s*
            \Z
        )
    ''', re.ASCII | re.VERBOSE)

    _SECT_BEG_REGEX = re.compile(r'''
        \A
        \[
        \s*
        (?P<sect_name>
            [^\s\].]+
        )
        \s*
        \]
    ''', re.ASCII | re.VERBOSE)

    _OPT_BEG_REGEX = re.compile(r'''
        \A
        (?P<opt_name>
            [^:=\s\[\]]
            [^:=\s]*
        )
        \s*
        (?:
            [:=]
            (?P<opt_value>  # may consume surronding whitespaces
                .*?         # but they will be stripped out later...
            )
            (?P<inline_comment>
                \s
                ;
                .*
            )?
        )?
        \Z
    ''', re.ASCII | re.VERBOSE)


    class _SectIndexData(object):

        # building stuff:

        def __init__(self, beg):
            self._beg = beg
            self._end = None
            self._opt_name_to_span = {}
            self._latest_opt_name = None

        def init_opt(self, opt_name, beg):
            self._complete_latest_opt(end=beg)
            self._opt_name_to_span[opt_name] = beg, None
            self._latest_opt_name = opt_name

        def complete(self, end):
            self._complete_latest_opt(end=end)
            self._end = end

        def _complete_latest_opt(self, end):
            opt_name = self._latest_opt_name
            if opt_name is not None:
                beg, _ = self._opt_name_to_span[opt_name]
                self._opt_name_to_span[opt_name] = beg, end
                self._latest_opt_name = None

        # read-only stuff:

        def get_span(self):
            if not self._is_end_completed():
                raise RuntimeError("{0!a} not completed".format(self))
            return self._beg, self._end

        def get_opt_span(self, opt_name):
            if not self._is_opt_completed(opt_name):
                raise RuntimeError("{0!a}.{1!a} not completed".format(self, opt_name))
            return self._opt_name_to_span[opt_name]

        def get_all_opt_names(self):
            return sorted(self._opt_name_to_span, key=(
                lambda opt_name: self._opt_name_to_span[opt_name]))

        def contains_opt_name(self, opt_name):
            return opt_name in self._opt_name_to_span

        def is_completed(self):
            return (self._is_end_completed() and
                    all(self._is_opt_completed(opt_name)
                        for opt_name in self._opt_name_to_span))

        def _is_end_completed(self):
            return self._end is not None

        def _is_opt_completed(self, opt_name):
            _, end = self._opt_name_to_span[opt_name]
            return end is not None


    @staticmethod
    def _get_lines(s):
        lines = splitlines_asc(s)
        if s.endswith(('\n', '\r')):
            lines.append('')
        return lines


    @classmethod
    def _get_sect_name_to_index_data(cls, lines):
        cur_sect_name = ''  # '' refers to the area above any explicit section
        sect_name_to_index_data = {cur_sect_name: cls._SectIndexData(beg=0)}
        non_blank_or_comment_encountered = False
        for i, li in enumerate(lines):
            if cls._COMMENTED_OR_BLANK_LINE_REGEX.search(li):
                continue
            assert li
            if li[0].isspace():  # is a continuation line?
                if not non_blank_or_comment_encountered:
                    raise ValueError(
                        f'first non-blank config line {li!a} '
                        f'looks like a continuation line '
                        f'(that is, starts with whitespace '
                        f'characters)')
                continue
            non_blank_or_comment_encountered = True

            sect_match = cls._SECT_BEG_REGEX.search(li)
            if sect_match:
                # this line is a new section header
                sect_name_to_index_data[cur_sect_name].complete(end=i)
                cur_sect_name = sect_match.group('sect_name')
                if cur_sect_name in sect_name_to_index_data:
                    raise ValueError(f'duplicate section name {cur_sect_name!a}')
                sect_name_to_index_data[cur_sect_name] = cls._SectIndexData(beg=i)

            else:
                opt_match = cls._OPT_BEG_REGEX.search(li)
                if opt_match:
                    # this line is an option spec (e.g., `name=value`...)
                    opt_name = opt_match.group('opt_name')
                    opt_name = opt_name.lower()  # <- to mimic `configparser` stuff
                    sect_idata = sect_name_to_index_data[cur_sect_name]
                    if sect_idata.contains_opt_name(opt_name):
                        raise ValueError(
                            f'duplicate option name {opt_name!a} '
                            f'in section {cur_sect_name!a}')
                    sect_idata.init_opt(opt_name, beg=i)

                else:
                    raise ValueError(
                        f'config line {li!a} is not valid (note that '
                        f'section/option names that are empty or '
                        f'contain certain restricted characters, in '
                        f'particular whitespace, are not supported)')

        sect_name_to_index_data[cur_sect_name].complete(end=len(lines))

        assert all(
            sect_idata.is_completed()
            for sect_idata in sect_name_to_index_data.values())
        return sect_name_to_index_data


    @classmethod
    def _from_lines(cls, lines):
        return cls('\n'.join(lines))


    def _location_to_span(self, location, opt_required=False):
        sect_name, dotted, opt_name = location.partition('.')
        sect_idata = self._sect_name_to_index_data[sect_name]
        if dotted:
            opt_name = opt_name.lower()  # <- to mimic `configparser` stuff
            span = sect_idata.get_opt_span(opt_name)
        elif opt_required:
            raise ValueError(
                f'the called method requires that the location argument '
                f'specifies an option name (got: {location!a})')
        else:
            span = sect_idata.get_span()
        return span


    def _get_new_combined(self, preserve_to, insert_this, preserve_from):
        lines_to_insert = splitlines_asc(insert_this)
        new_lines = (
            self._lines[:preserve_to] +
            lines_to_insert +
            self._lines[preserve_from:])
        return self._from_lines(new_lines)


    def _get_opt_value_and_match(self, location_with_opt_name):
        beg, end = self._location_to_span(location_with_opt_name, opt_required=True)
        first_line = self._lines[beg]
        opt_match = self._OPT_BEG_REGEX.search(first_line)

        assert opt_match
        assert (opt_match.group('opt_name').lower() ==
                location_with_opt_name.partition('.')[2].lower())

        opt_value_first_line = opt_match.group('opt_value')
        if opt_value_first_line is None:
            # Apparently, it is a *no-value option*; if it has some
            # continuation lines after it, they will be just ignored
            # (for historical reasons: when implementing `ConfigString`
            # we attempted to be close to the behavior of old Py-2.7's
            # `ConfigParser`, but in this case it raised `AttributeError`
            # which was obviously a bug; that version of `ConfigParser`
            # had also another bug: `no-value` options had their inline
            # comments appended to their names -- that's why here
            # *no-value options* with inline comments are just
            # forbidden, causing `ValueError`).
            return None, opt_match

        # When `ConfigString` was implemented, we attempted to be
        # close to the (somewhat buggy) behaviour of the old Py-2.7's
        # `ConfigParser` (that's why here, for example, we strip the
        # first line and only then append continuation lines...).
        opt_value_first_line = self._strip_opt_value(opt_value_first_line)

        continuation_lines = [
            li for li in self._lines[(beg + 1):end]
            if not self._COMMENTED_OR_BLANK_LINE_REGEX.search(li)]
        assert all(
            li and li[0].isspace()
            for li in continuation_lines)

        opt_lines = [opt_value_first_line] + list(map(str.strip, continuation_lines))
        opt_value = '\n'.join(opt_lines)

        return opt_value, opt_match


    def _strip_opt_value(self, value):
        value = value.strip()
        if value == '""':
            value = ''
        return value



###
# *Non-public* auxiliary constants and classes
###

_N6DATAPIPELINE_CONFIG_ERROR_MSG_PATTERN = """

{0}.

Make sure that config files for *n6* are present in '/etc/n6/' or
'~/.n6/' (or their directory subtrees) and that they are valid
(especially, that they contain all needed entries).

Note: you may want to copy config file prototypes (templates) from
'etc/n6/' in the *n6* source code repository to your local '~/.n6/',
and then adjust them (in that local '~/.n6/') to your needs.

"""


# (*Beware:* it must be cohered with the content of
# the `_ConfDataSpec._OPT_BEG_REGEX`'s capturing group
# `no_val_converter_spec`.)
_CONVERTER_SPEC_REGEX = re.compile(r'\A\S+\Z', re.ASCII)


@dataclass
class _SectSpec:

    r"""
    >>> s = _SectSpec('',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '\nfoo\nbar = x :: y\n'
    >>> s.free_opts_converter_spec  # (`free_opts_allowed` is false => 'str' here)
    'str'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n'
    >>> s.free_opts_converter_spec  # (`free_opts_allowed` is false => 'str' here)
    'str'
    >>> s.required
    True

    >>> s = _SectSpec(name='some',                           # (equivalent to the previous one)
    ...               opt_specs=[_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec='TO_BE_IGNORED_BECAUSE_FREE_OPTS_DISALLOWED')
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n'
    >>> s.free_opts_converter_spec  # (`free_opts_allowed` is false => 'str' here)
    'str'
    >>> s.required
    True

    >>> s = _SectSpec('some',                                # (equivalent to the previous one)
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               False,
    ...               'TO_BE_IGNORED_BECAUSE_FREE_OPTS_DISALLOWED')
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n'
    >>> s.free_opts_converter_spec  # (`free_opts_allowed` is false => 'str' here)
    'str'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '\n[some]\n'
    >>> s.free_opts_converter_spec  # (`free_opts_allowed` is false => 'str' here)
    'str'
    >>> s.required
    False

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n...\n'
    >>> s.free_opts_converter_spec   # (`free_opts_allowed` is true + `None` given => 'str' here)
    'str'
    >>> s.required
    True

    >>> s = _SectSpec('some',                                # (equivalent to the previous one)
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec='str')
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n...\n'
    >>> s.free_opts_converter_spec
    'str'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=True,         # <- `True` here, and
    ...               free_opts_converter_spec='XY')  # <- SOMETHING here => include ':: SOMETHING'
    >>> str(s)
    '\n[some]\nfoo\nbar = x :: y\n... :: XY\n'
    >>> s.free_opts_converter_spec   # (`free_opts_allowed` is true + SOMETHING given => SOMETHING)
    'XY'
    >>> s.required
    True

    >>> s = _SectSpec(name='some',
    ...               opt_specs=[_OptSpec('foo', 'A', None), _OptSpec('b', 'x\ny', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec='XY')
    >>> str(s)
    '\n[some]\nfoo = A\nb = x\n  y :: y\n... :: XY\n'
    >>> s.free_opts_converter_spec
    'XY'
    >>> s.required
    False

    >>> s = _SectSpec('some',                                # (equivalent to the previous one)
    ...               [_OptSpec('foo', 'A', None), _OptSpec('b', 'x\ny', 'y')],
    ...               True,
    ...               'XY')
    >>> str(s)
    '\n[some]\nfoo = A\nb = x\n  y :: y\n... :: XY\n'
    >>> s.free_opts_converter_spec
    'XY'
    >>> s.required
    False

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', 'A', None), _OptSpec('b', 'x\ny', 'y')],
    ...               free_opts_allowed=True,                 # <- `True` here, and
    ...               free_opts_converter_spec='wrong spec')  # <- invalid converter spec => ERROR!
    Traceback (most recent call last):
      ...
    ValueError: the free options converter spec 'wrong spec' is not valid

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', 'A', None), _OptSpec('b', 'x\ny', 'y')],
    ...               free_opts_allowed=False,                # <- `False` here, so
    ...               free_opts_converter_spec='wrong spec')  # <- ignore invalid converter spec
    >>> str(s)
    '\n[some]\nfoo = A\nb = x\n  y :: y\n'
    >>> s.free_opts_converter_spec   # (`free_opts_allowed` is false => 'str' here)
    'str'
    """

    name: str                       # section name
    opt_specs: list['_OptSpec']     # option specifications
    free_opts_allowed: bool         # whether free (not declared in config spec) opts are allowed
    free_opts_converter_spec: str   # value converter name (aka *converter spec*) for free opts

    def __post_init__(self):
        if self.free_opts_converter_spec is None or not self.free_opts_allowed:
            self.free_opts_converter_spec = Config.DEFAULT_CONVERTER_SPEC
        if not _CONVERTER_SPEC_REGEX.search(self.free_opts_converter_spec):
            raise ValueError(
                f'the free options converter spec '
                f'{self.free_opts_converter_spec!a} '
                f'is not valid')

    @property
    def required(self) -> bool:
        """Whether the section is obligatory."""
        return any(opt.default is None for opt in self.opt_specs)

    def __str__(self) -> str:
        s = '\n'
        if self.name:
            s += f'[{self.name}]\n'
        if self.opt_specs:
            s += '\n'.join(map(str, self.opt_specs))
            s += '\n'
        if self.free_opts_allowed:
            s += '...'
            if self.free_opts_converter_spec != Config.DEFAULT_CONVERTER_SPEC:
                s += f' :: {self.free_opts_converter_spec}'
            s += '\n'
        return s


@dataclass
class _OptSpec:

    r"""
    >>> str(_OptSpec('foo', None, None))
    'foo'

    >>> str(_OptSpec('foo', None, converter_spec=None))
    'foo'

    >>> str(_OptSpec('foo', default=None, converter_spec=None))
    'foo'

    >>> str(_OptSpec(name='foo', default=None, converter_spec=None))
    'foo'

    >>> str(_OptSpec('foo', '', None))
    'foo = ""'

    >>> str(_OptSpec('foo', 'bar', None))
    'foo = bar'

    >>> str(_OptSpec('foo', None, 'spam'))
    'foo :: spam'

    >>> str(_OptSpec('foo', 'bar', 'spam'))
    'foo = bar :: spam'

    >>> str(_OptSpec('foo', 'bar\nspam\r\nham', None))
    'foo = bar\n  spam\n  ham'

    >>> str(_OptSpec('foo', ' \n \n \n \t \n \r\n \r \n', None))
    'foo = ""'

    >>> str(_OptSpec('foo', ' \n \n \n \t \n XYZ \r\n \r \n', None))
    'foo = XYZ'

    >>> str(_OptSpec('foo', '\tbar\t\n\t spam\n ham \t\n\t', 'spam'))
    'foo = bar\n  spam\n  ham :: spam'

    >>> str(_OptSpec(name='foo', default='\tbar\t\n\t spam\n ham \t\n\t', converter_spec='spam'))
    'foo = bar\n  spam\n  ham :: spam'

    >>> str(_OptSpec('foo', None, 'wrong spec'))
    Traceback (most recent call last):
      ...
    ValueError: the `foo` option's converter spec 'wrong spec' is not valid
    """

    name: str                # option name
    default: Optional[str]   # default value
    converter_spec: str      # value converter name (aka *converter spec*)

    def __post_init__(self):
        if self.converter_spec is None:
            self.converter_spec = Config.DEFAULT_CONVERTER_SPEC
        if not _CONVERTER_SPEC_REGEX.search(self.converter_spec):
            raise ValueError(
                f"the `{self.name}` option\'s converter spec "
                f"{self.converter_spec!a} is not valid")

    def __str__(self):
        s = self.name
        if self.default is not None:
            default = '\n  '.join(filter(None, map(str.strip, splitlines_asc(self.default))))
            s += ' = {0}'.format(default or '""')
        if self.converter_spec != Config.DEFAULT_CONVERTER_SPEC:
            s += ' :: {0}'.format(self.converter_spec)
        return s


class _ConfSpecData(ConfigString):

    r"""
    A helper class to deal with *config specs* (parsing them and
    providing an interface to manipulate their data).

    This class should not be instantiated directly beyond this
    module -- the `parse_config_spec()` public helper function
    (which has additional features, e.g., automatically reduces
    indentation...) should be used instead.

    Note that this class is a subclass of `ConfigString` (with
    some methods adjusted and additional methods provided).

    >>> cs = _ConfSpecData('''
    ... [ first ]
    ... foo = 42 :: int ; comment
    ... bar = 43 ; comment
    ... baz = 44 :: int
    ... spam = 45
    ...
    ... ham::bytes
    ... slam
    ... glam ;comment
    ...
    ... # the `...` below means that free (arbitrary, i.e. not specified
    ... # here) options will be allowed in this section
    ... ...
    ...
    ...
    ... [second]
    ...
    ... bAR = http:://\t
    ...   example.com/ :: url''')  # (note the multiline option `bAR`)

    >>> cs.get('first') == _ConfSpecData(
    ...   '[ first ]\nfoo = 42 :: int ; comment\nbar = 43 ; comment\n'
    ...   'baz = 44 :: int\nspam = 45\n\nham::bytes\nslam\nglam ;comment\n\n'
    ...   '# the `...` below means that free (arbitrary, i.e. not specified\n'
    ...   '# here) options will be allowed in this section\n...\n\n')
    True

    >>> cs.contains('second')
    True
    >>> cs.contains('first.SPAM')
    True
    >>> cs.contains('third')
    False
    >>> cs.contains('second.foo')
    False

    >>> cs.get('first.foo')
    _ConfSpecData('foo = 42 :: int ; comment')
    >>> cs.get_opt_value('first.foo')
    '42'
    >>> cs.get_opt_spec('first.foo')
    _OptSpec(name='foo', default='42', converter_spec='int')

    >>> cs.get('first.bar')
    _ConfSpecData('bar = 43 ; comment')
    >>> cs.get_opt_value('first.bar')
    '43'
    >>> cs.get_opt_spec('first.bar')
    _OptSpec(name='bar', default='43', converter_spec='str')

    >>> cs.get('first.bAz')
    _ConfSpecData('baz = 44 :: int')
    >>> cs.get_opt_value('first.BaZ')
    '44'
    >>> cs.get_opt_spec('first.BAZ')
    _OptSpec(name='baz', default='44', converter_spec='int')

    >>> cs.get('first.spam')
    _ConfSpecData('spam = 45\n')
    >>> cs.get_opt_value('first.spam')
    '45'
    >>> cs.get_opt_spec('first.spam')
    _OptSpec(name='spam', default='45', converter_spec='str')

    >>> cs.get('first.Ham')
    _ConfSpecData('ham::bytes')
    >>> cs.get_opt_value('first.HAM') is None
    True
    >>> cs.get_opt_spec('first.HAM')
    _OptSpec(name='ham', default=None, converter_spec='bytes')

    >>> cs.get('first.SLAM')
    _ConfSpecData('slam')
    >>> cs.get_opt_value('first.Slam') is None
    True
    >>> cs.get_opt_spec('first.Slam')
    _OptSpec(name='slam', default=None, converter_spec='str')

    >>> cs.get('first.glam')                   # doctest: +ELLIPSIS
    _ConfSpecData('glam ;comment\n\n# the `...
    >>> cs.get_opt_value('first.glam') is None
    True
    >>> cs.get_opt_spec('first.glam')
    _OptSpec(name='glam', default=None, converter_spec='str')

    >>> cs.get('first....')
    _ConfSpecData('...\n\n')
    >>> cs.get_opt_value('first....') is None
    True
    >>> cs.get_opt_spec('first....')
    _OptSpec(name='...', default=None, converter_spec='str')

    >>> cs.get('second.bar')
    _ConfSpecData('bAR = http:://\t\n  example.com/ :: url')
    >>> cs.get_opt_value('second.bar')
    'http:://\nexample.com/'
    >>> cs.get_opt_spec('second.bar')
    _OptSpec(name='bar', default='http:://\nexample.com/', converter_spec='url')

    >>> cs.get_all_sect_names()
    ['first', 'second']

    >>> cs.get_all_sect_and_opt_names() == [
    ...     ('first', [
    ...         'foo',
    ...         'bar',
    ...         'baz',
    ...         'spam',
    ...         'ham',
    ...         'slam',
    ...         'glam',
    ...         '...',
    ...      ]),
    ...     ('second', ['bar']),
    ... ]
    True
    >>> cs.get_sect_spec('first') == _SectSpec(
    ...     name='first',
    ...     opt_specs=[
    ...         _OptSpec(name='foo', default='42', converter_spec='int'),
    ...         _OptSpec(name='bar', default='43', converter_spec='str'),
    ...         _OptSpec(name='baz', default='44', converter_spec='int'),
    ...         _OptSpec(name='spam', default='45', converter_spec='str'),
    ...         _OptSpec(name='ham', default=None, converter_spec='bytes'),
    ...         _OptSpec(name='slam', default=None, converter_spec='str'),
    ...         _OptSpec(name='glam', default=None, converter_spec='str'),
    ...     ],
    ...     free_opts_allowed=True,     # because the `...` marker is present
    ...     free_opts_converter_spec='str',
    ... )
    True
    >>> cs.get_sect_spec('first').required
    True
    >>> cs.get_sect_spec('second') == _SectSpec(
    ...     name='second',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='bar',
    ...             default='http:://\nexample.com/',
    ...             converter_spec='url',
    ...         ),
    ...     ],
    ...     free_opts_allowed=False,    # because no `...` marker
    ...     free_opts_converter_spec='str',
    ... )
    True
    >>> cs.get_sect_spec('second').required
    False
    >>> cs.get_all_sect_specs() == [
    ...   _SectSpec(
    ...     name='first',
    ...     opt_specs=[
    ...         _OptSpec(name='foo', default='42', converter_spec='int'),
    ...         _OptSpec(name='bar', default='43', converter_spec='str'),
    ...         _OptSpec(name='baz', default='44', converter_spec='int'),
    ...         _OptSpec(name='spam', default='45', converter_spec='str'),
    ...         _OptSpec(name='ham', default=None, converter_spec='bytes'),
    ...         _OptSpec(name='slam', default=None, converter_spec='str'),
    ...         _OptSpec(name='glam', default=None, converter_spec='str'),
    ...     ],
    ...     free_opts_allowed=True,     # because the `...` marker is present
    ...     free_opts_converter_spec='str',
    ...   ),
    ...   _SectSpec(
    ...     name='second',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='bar',
    ...             default='http:://\nexample.com/',
    ...             converter_spec='url',
    ...         ),
    ...     ],
    ...     free_opts_allowed=False,    # because no `...` marker
    ...     free_opts_converter_spec='str',
    ...   ),
    ... ]
    True


    A few more peculiar cases, some corner cases etc.:

    >>> cs2 = _ConfSpecData('''[second]
    ... x:y::conv1 ;inline-comment
    ... Y=ZZ::XX::conv2\t\t\t;inline-comment\t\t\t;yeah
    ... z :: conv3
    ... empty1:""
    ... empty2: ""
    ... empty3:"" ;inline-comment
    ... empty4: "" ;inline-comment
    ... empty5:"" ; inline-comment
    ... empty6: "" ; inline-comment
    ... empty7:  "" ; inline-comment
    ... empty8: ""  ; inline-comment
    ... empty9:  ""  ; inline-comment
    ... empty10 :""
    ... empty11 : ""
    ... empty12 :"" ;inline-comment
    ... empty13 : "" ;inline-comment
    ... empty14 :"" ; inline-comment
    ... empty15 : "" ; inline-comment
    ... empty16 :  "" ; inline-comment
    ... empty17  :  ""  ; inline-comment
    ... empty18:
    ... empty19 :
    ... empty20  :
    ... empty21 : ;inline-comment
    ... empty22 : ; inline-comment
    ... empty23 :  ; inline-comment
    ... empty24  :  ; inline-comment
    ... empty25=""
    ... empty26= ""
    ... empty27 =""
    ... empty28="" ;inline-comment
    ... empty29= "" ;inline-comment
    ... empty30 ="" ;inline-comment
    ... empty31 = "" ;inline-comment
    ... empty32="" ; inline-comment
    ... empty33= "" ; inline-comment
    ... empty34 ="" ; inline-comment
    ... empty35 = "" ; inline-comment
    ... empty36 =  ""  ; inline-comment
    ... empty37 = ""  ; inline-comment
    ... empty38 =  ""  ; inline-comment
    ... empty39=
    ... empty40 =
    ... empty41  =
    ... empty42= ;inline-comment
    ... empty43 = ;inline-comment
    ... empty44= ; inline-comment
    ... empty45 = ; inline-comment
    ... empty46= ;inline-comment
    ... empty47=  ;inline-comment
    ... empty48 = ;inline-comment
    ... empty49 =  ;inline-comment
    ... empty50= ; inline-comment
    ... empty51=  ; inline-comment
    ... empty52 = ; inline-comment
    ... empty53 =  ; inline-comment
    ... empty54  =  ; inline-comment
    ... empty1_i:""::int
    ... empty2_i: ""::int
    ... empty3_i:"" ::int
    ... empty4_i: "" ::int
    ... empty5_i:"":: int
    ... empty6_i: "":: int
    ... empty7_i:"" :: int
    ... empty8_i: "" :: int
    ... empty9_i: ""  :: int
    ... empty10_i: ""  ::  int
    ... empty11_i:  ""  ::  int
    ... empty12_i:""::int ;inline-comment
    ... empty13_i: ""::int ;inline-comment
    ... empty14_i:"" ::int ;inline-comment
    ... empty15_i: "" ::int ;inline-comment
    ... empty16_i:"":: int ;inline-comment
    ... empty17_i: "":: int ;inline-comment
    ... empty18_i:"" :: int ;inline-comment
    ... empty19_i: "" :: int ;inline-comment
    ... empty20_i: "" ::  int ;inline-comment
    ... empty21_i: "" ::  int  ;inline-comment
    ... empty22_i:""::int ; inline-comment
    ... empty23_i: ""::int ; inline-comment
    ... empty24_i:"" ::int ; inline-comment
    ... empty25_i: "" ::int ; inline-comment
    ... empty26_i:"":: int ; inline-comment
    ... empty27_i: "":: int ; inline-comment
    ... empty28_i:"" :: int ; inline-comment
    ... empty29_i: "" :: int ; inline-comment
    ... empty30_i: ""  ::  int ; inline-comment
    ... empty31_i: "" ::  int ; inline-comment
    ... empty32_i: "" ::  int  ; inline-comment
    ... empty33_i:  ""  ::  int  ; inline-comment
    ... empty34_i :""::int
    ... empty35_i : ""::int
    ... empty36_i :"" ::int
    ... empty37_i : "" ::int
    ... empty38_i :"":: int
    ... empty39_i : "":: int
    ... empty40_i :"" :: int
    ... empty41_i : "" :: int
    ... empty42_i :""  :: int
    ... empty43_i : ""  :: int
    ... empty44_i :  ""  :: int
    ... empty45_i :  ""  ::  int
    ... empty46_i  :  ""  ::  int
    ... empty47_i :""::int ;inline-comment
    ... empty48_i : ""::int ;inline-comment
    ... empty49_i :"" ::int ;inline-comment
    ... empty50_i : "" ::int ;inline-comment
    ... empty51_i :"":: int ;inline-comment
    ... empty52_i : "":: int ;inline-comment
    ... empty53_i :"" :: int ;inline-comment
    ... empty54_i : "" :: int ;inline-comment
    ... empty55_i :""::int ; inline-comment
    ... empty56_i : ""::int ; inline-comment
    ... empty57_i :"" ::int ; inline-comment
    ... empty58_i : "" ::int ; inline-comment
    ... empty59_i :"":: int ; inline-comment
    ... empty60_i : "":: int ; inline-comment
    ... empty61_i :"" :: int ; inline-comment
    ... empty62_i : "" :: int ; inline-comment
    ... empty63_i  :  ""  ::  int  ; inline-comment
    ... empty64_i: ::int
    ... empty65_i : ::int
    ... empty66_i: :: int
    ... empty67_i : :: int
    ... empty68_i: ::int ;inline-comment
    ... empty69_i : ::int ;inline-comment
    ... empty70_i: :: int ;inline-comment
    ... empty71_i : :: int ;inline-comment
    ... empty72_i: ::int ; inline-comment
    ... empty73_i : ::int ; inline-comment
    ... empty74_i: :: int ; inline-comment
    ... empty75_i : :: int ; inline-comment
    ... empty76_i  :  ::  int  ; inline-comment
    ... empty77_i=""::int
    ... empty78_i= ""::int
    ... empty79_i =""::int
    ... empty80_i=""::int ;inline-comment
    ... empty81_i= ""::int ;inline-comment
    ... empty82_i =""::int ;inline-comment
    ... empty83_i = ""::int ;inline-comment
    ... empty84_i=""::int ; inline-comment
    ... empty85_i= ""::int ; inline-comment
    ... empty86_i =""::int ; inline-comment
    ... empty87_i = ""::int ; inline-comment
    ... empty88_i="" ::int
    ... empty89_i= "" ::int
    ... empty90_i ="" ::int
    ... empty91_i="" ::int ;inline-comment
    ... empty92_i= "" ::int ;inline-comment
    ... empty93_i ="" ::int ;inline-comment
    ... empty94_i = "" ::int ;inline-comment
    ... empty95_i="" ::int ; inline-comment
    ... empty96_i= "" ::int ; inline-comment
    ... empty97_i ="" ::int ; inline-comment
    ... empty98_i = "" ::int ; inline-comment
    ... empty99_i="":: int
    ... empty100_i= "":: int
    ... empty101_i ="":: int
    ... empty102_i="":: int ;inline-comment
    ... empty103_i= "":: int ;inline-comment
    ... empty104_i ="":: int ;inline-comment
    ... empty105_i = "":: int ;inline-comment
    ... empty106_i="":: int ; inline-comment
    ... empty107_i= "":: int ; inline-comment
    ... empty108_i ="":: int ; inline-comment
    ... empty109_i = "":: int ; inline-comment
    ... empty110_i="" :: int
    ... empty111_i= "" :: int
    ... empty112_i ="" :: int
    ... empty113_i="" :: int ;inline-comment
    ... empty114_i= "" :: int ;inline-comment
    ... empty115_i ="" :: int ;inline-comment
    ... empty116_i = "" :: int ;inline-comment
    ... empty117_i="" :: int ; inline-comment
    ... empty118_i= "" :: int ; inline-comment
    ... empty119_i ="" :: int ; inline-comment
    ... empty120_i = "" :: int ; inline-comment
    ... empty121_i  =  ""  ::  int  ; inline-comment
    ... empty122_i=::int
    ... empty123_i =::int
    ... empty124_i= ::int
    ... empty125_i = ::int
    ... empty126_i=:: int
    ... empty127_i =:: int
    ... empty128_i= :: int
    ... empty129_i = :: int
    ... empty130_i=::int ;inline-comment
    ... empty131_i =::int ;inline-comment
    ... empty132_i= ::int ;inline-comment
    ... empty133_i = ::int ;inline-comment
    ... empty134_i=:: int ;inline-comment
    ... empty135_i =:: int ;inline-comment
    ... empty136_i= :: int ;inline-comment
    ... empty137_i = :: int ;inline-comment
    ... empty138_i=::int ; inline-comment
    ... empty139_i =::int ; inline-comment
    ... empty140_i= ::int ; inline-comment
    ... empty141_i = ::int ; inline-comment
    ... empty142_i=:: int ; inline-comment
    ... empty143_i =:: int ; inline-comment
    ... empty144_i= :: int ; inline-comment
    ... empty145_i = :: int ; inline-comment
    ... empty146_i  =  ::  int  ; inline-comment
    ... bar = http:// :: x \t ; inline comment ; yeah it is
    ...
    ... # comment
    ...
    ... ; comment ; comment ; comment \t
    ...   ; not a comment  ;  ! :: foo :: xx
    ...
    ... # comment
    ...     zz
    ...   example.com/; not-a-comment\t :: int
    ...
    ... [another]
    ... # free options allowed:
    ... ...
    ...
    ... [fifth]
    ... Some.Option   :   A Value   ::   bytes   ;   A Comment
    ... ... :: bytes ; free options allowed + converter for them specified
    ... no.value.option :: int \t; inline comment \t; here allowed! \t
    ...   for no-value options
    ...   continuation lines are ignored \t
    ... Foo   =   aaa \t ; comment \t
    ...  bbbccc \t ; not-a-comment \t :: some_conv \t''')

    >>> cs2.get_opt_value('second.x')
    'y'
    >>> cs2.get_opt_spec('second.x')
    _OptSpec(name='x', default='y', converter_spec='conv1')

    >>> cs2.get_opt_value('second.y')
    'ZZ::XX'
    >>> cs2.get_opt_spec('second.y')
    _OptSpec(name='y', default='ZZ::XX', converter_spec='conv2')

    >>> cs2.get_opt_value('second.z') is None
    True
    >>> cs2.get_opt_spec('second.z')
    _OptSpec(name='z', default=None, converter_spec='conv3')

    >>> empty_options = ['empty{}'.format(i) for i in range(1, 55)]
    >>> all(cs2.get_opt_value('second.' + o) == ''
    ...     for o in empty_options)
    True
    >>> all(cs2.get_opt_spec('second.' + o) == _OptSpec(o, '', 'str')
    ...     for o in empty_options)
    True

    >>> empty_int_options = ['empty{}_i'.format(i) for i in range(1, 147)]
    >>> all(cs2.get_opt_value('second.' + o) == ''
    ...     for o in empty_int_options)
    True
    >>> all(cs2.get_opt_spec('second.' + o) == _OptSpec(o, '', 'int')
    ...     for o in empty_int_options)
    True

    >>> cs2.get_opt_value('second.BaR')
    'http:// :: x\n; not a comment  ;  ! :: foo :: xx\nzz\nexample.com/; not-a-comment'
    >>> cs2.get_opt_spec('second.bAr') == _OptSpec(
    ...   name='bar',
    ...   default=(
    ...       'http:// :: x\n; not a comment  ;  ! :: foo :: '
    ...       'xx\nzz\nexample.com/; not-a-comment'),
    ...   converter_spec='int')
    True

    >>> cs2.get_opt_value('another....') is None
    True

    >>> cs2.get_opt_value('fifth.foo')
    'aaa\nbbbccc \t ; not-a-comment'

    >>> cs2.get_opt_value('fifth.some.option')
    'A Value'

    >>> cs2.get_opt_value('fifth.no.value.option') is None
    True
    >>> cs2.get('fifth.no.value.option') == (
    ...     'no.value.option :: int \t; inline comment \t; here allowed! \t\n'
    ...     '  for no-value options\n'
    ...     '  continuation lines are ignored \t')
    True

    >>> cs2.get_all_sect_names()
    ['second', 'another', 'fifth']

    >>> cs2.get_all_sect_and_opt_names() == [
    ...     ('second', [
    ...         'x',
    ...         'y',
    ...         'z',
    ...       ] + empty_options + empty_int_options + [
    ...         'bar',
    ...      ]),
    ...     ('another', [
    ...         '...',
    ...      ]),
    ...     ('fifth', [
    ...         'some.option',
    ...         '...',
    ...         'no.value.option',
    ...         'foo',
    ...      ]),
    ... ]
    True
    >>> cs2.get_sect_spec('second') == _SectSpec(
    ...     name='second',
    ...     opt_specs=[
    ...         _OptSpec(name='x', default='y', converter_spec='conv1'),
    ...         _OptSpec(name='y', default='ZZ::XX', converter_spec='conv2'),
    ...         _OptSpec(name='z', default=None, converter_spec='conv3'),
    ...       ]
    ...       + list(_OptSpec(name=o, default='', converter_spec='str')
    ...              for o in empty_options)
    ...       + list(_OptSpec(name=o, default='', converter_spec='int')
    ...              for o in empty_int_options)
    ...       + [
    ...         _OptSpec(
    ...             name='bar',
    ...             default=('http:// :: x\n; not a comment  ;  ! :: foo :: '
    ...                      'xx\nzz\nexample.com/; not-a-comment'),
    ...             converter_spec='int',
    ...         ),
    ...     ],
    ...     free_opts_allowed=False,
    ...     free_opts_converter_spec='str',
    ... )
    True
    >>> cs2.get_sect_spec('second').required
    True
    >>> cs2.get_sect_spec('another') == _SectSpec(
    ...     name='another',
    ...     opt_specs=[],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec='str',
    ... )
    True
    >>> cs2.get_sect_spec('another').required
    False
    >>> cs2.get_sect_spec('fifth') == _SectSpec(
    ...     name='fifth',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='some.option',
    ...             default='A Value',
    ...             converter_spec='bytes',
    ...         ),
    ...         _OptSpec(
    ...             name='no.value.option',
    ...             default=None,
    ...             converter_spec='int',
    ...         ),
    ...         _OptSpec(
    ...             name='foo',
    ...             default='aaa\nbbbccc \t ; not-a-comment',
    ...             converter_spec='some_conv',
    ...         ),
    ...     ],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec='bytes',
    ... )
    True
    >>> cs2.get_sect_spec('fifth').required
    True
    >>> cs2.get_all_sect_specs() == [
    ...   _SectSpec(
    ...     name='second',
    ...     opt_specs=[
    ...         _OptSpec(name='x', default='y', converter_spec='conv1'),
    ...         _OptSpec(name='y', default='ZZ::XX', converter_spec='conv2'),
    ...         _OptSpec(name='z', default=None, converter_spec='conv3'),
    ...       ]
    ...       + list(_OptSpec(name=o, default='', converter_spec='str')
    ...              for o in empty_options)
    ...       + list(_OptSpec(name=o, default='', converter_spec='int')
    ...              for o in empty_int_options)
    ...       + [
    ...         _OptSpec(
    ...             name='bar',
    ...             default=('http:// :: x\n; not a comment  ;  ! :: foo :: '
    ...                      'xx\nzz\nexample.com/; not-a-comment'),
    ...             converter_spec='int'),
    ...     ],
    ...     free_opts_allowed=False,
    ...     free_opts_converter_spec='str',
    ...   ),
    ...   _SectSpec(
    ...     name='another',
    ...     opt_specs=[],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec='str',
    ...   ),
    ...   _SectSpec(
    ...     name='fifth',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='some.option',
    ...             default='A Value',
    ...             converter_spec='bytes',
    ...         ),
    ...         _OptSpec(
    ...             name='no.value.option',
    ...             default=None,
    ...             converter_spec='int',
    ...         ),
    ...         _OptSpec(
    ...             name='foo',
    ...             default='aaa\nbbbccc \t ; not-a-comment',
    ...             converter_spec='some_conv',
    ...         ),
    ...     ],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec='bytes',
    ...   ),
    ... ]
    True

    >>> _ConfSpecData('[wrong.sect]')                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong.sect]' is not valid ...

    >>> _ConfSpecData('[wrong_opt')                        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt' is not valid ...

    >>> _ConfSpecData('[wrong_opt = val')                  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt = val' is not valid ...

    >>> _ConfSpecData('[wrong_opt :: some_conv')           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt :: some_conv' is not valid ...

    >>> _ConfSpecData('[wrong_opt = val :: some_conv')     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line '[wrong_opt = val :: some_conv' is not valid ...

    >>> _ConfSpecData(']wrong_opt')                        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt' is not valid ...

    >>> _ConfSpecData(']wrong_opt = val')                  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt = val' is not valid ...

    >>> _ConfSpecData(']wrong_opt :: some_conv')           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt :: some_conv' is not valid ...

    >>> _ConfSpecData(']wrong_opt = val :: some_conv')     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line ']wrong_opt = val :: some_conv' is not valid ...

    >>> _ConfSpecData('wrong opt')                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt' is not valid ...

    >>> _ConfSpecData('wrong opt = val')                   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt = val' is not valid ...

    >>> _ConfSpecData('wrong opt :: some_conv')            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt :: some_conv' is not valid ...

    >>> _ConfSpecData('wrong opt = val :: some_conv')      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt = val :: some_conv' is not valid ...

    >>> _ConfSpecData('some_opt :: wrong conv')            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ...wrong conv' is not valid...

    >>> _ConfSpecData('some_opt = val :: wrong conv')      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: ...wrong conv' is not valid...

    >>> _ConfSpecData('  \n  xyz\n  abc\n\n')              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... '  xyz' looks like a continuation line...

    >>> _ConfSpecData('  [xyz]\n  abc=3')                  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... '  [xyz]' looks like a continuation line...

    >>> _ConfSpecData('''
    ... [first]
    ... a = AAA
    ... [second]
    ... z = ZZZ
    ... [first]
    ... b = BBB
    ... c = CCC
    ... ''')
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> _ConfSpecData('''
    ... [first]
    ... a = AAA
    ... b = BBB
    ... a = AAA
    ... ''')
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'

    >>> _ConfSpecData(b'foo = 3')
    Traceback (most recent call last):
      ...
    TypeError: expected a `str` (got an instance of `bytes`)

    >>> _ConfSpecData(['foo = 3'])
    Traceback (most recent call last):
      ...
    TypeError: expected a `str` (got an instance of `list`)
    """


    _OPT_BEG_REGEX = re.compile(r'''
        \A
        (?P<opt_name>
            [^:=\s\[\]]
            [^:=\s]*
        )
        \s*
        (?:
            (?:
                :
                (?!
                    :   # opt delimiter must not be "::"
                )
            |
                =
            )
            (?P<opt_value>
                .*?     # default value + optional converter spec
            )
        |
            ::          # delimiter of converter spec for `no-value option`
            \s*
            (?P<no_val_converter_spec>
                \S+     # converter spec for `no-value option`
            )           # (*beware:* it must be cohered with `_CONVERTER_SPEC_REGEX`)
        )?
        \s*?
        (?P<inline_comment>  # note: here allowed also for `no-value option`
            \s
            ;
            .*
        )?
        \Z
    ''', re.ASCII | re.VERBOSE)


    def __new__(cls, /, *args, **kwargs):
        new = super().__new__(cls, *args, **kwargs)
        assert isinstance(new, cls)
        new.get_all_sect_specs()  # (to trigger certain validations...)
        return new


    def get_opt_value(self, location_with_opt_name):
        value_with_optional_conv = super().get_opt_value(location_with_opt_name)
        if value_with_optional_conv is None:
            opt_value = None
        else:
            opt_value, _ = self._split_value_with_optional_conv(value_with_optional_conv)
        return opt_value


    def get_opt_spec(self, location_with_opt_name):
        (value_with_optional_conv,
         opt_match) = self._get_opt_value_and_match(location_with_opt_name)
        opt_name = opt_match.group('opt_name').lower()
        if value_with_optional_conv is None:
            # no default value specified
            default_value = None
            converter_spec = opt_match.group('no_val_converter_spec')
        else:
            # default value has been specified
            (default_value,
             converter_spec) = self._split_value_with_optional_conv(value_with_optional_conv)
        return _OptSpec(opt_name, default_value, converter_spec)


    # split into: `(<actual option value>, <converter spec or None>)`
    def _split_value_with_optional_conv(self, value_with_optional_conv):
        first, conv_specified, second = value_with_optional_conv.rpartition('::')
        if conv_specified:
            opt_value = self._strip_opt_value(first)
            converter_spec = second.strip()
        else:
            assert not first
            opt_value = second
            converter_spec = None
        return opt_value, converter_spec


    def get_sect_spec(self, sect_name):
        """
        Get a `_SectSpec` instance for the given section name.

        The returned instance includes specifications of all options
        they contain -- except that `...` is not interpreted as an
        option name but as a "free options allowed" marker.
        """
        opt_spec_seq = []
        free_opts_allowed = False
        free_opts_converter_spec = None
        sect_idata = self._sect_name_to_index_data[sect_name]
        for opt_name in sect_idata.get_all_opt_names():
            location_with_opt_name = '{0}.{1}'.format(sect_name, opt_name)
            opt_spec = self.get_opt_spec(location_with_opt_name)
            if opt_name == '...':
                free_opts_allowed = True
                free_opts_converter_spec = opt_spec.converter_spec
            else:
                opt_spec_seq.append(opt_spec)
        return _SectSpec(
            sect_name,
            opt_spec_seq,
            free_opts_allowed,
            free_opts_converter_spec)


    def get_all_sect_specs(self):
        """
        Get a list of `_SectSpec` instances.

        They contain specifications of all sections and options that
        these sections contain -- except that:

        * `...` is not interpreted as an option name but as a "free
          options allowed" marker;

        * the '' section is included only if it contains any options
          and/or a "free options allowed" marker.

        The order of sections and options (within each `_SectSpec`
        instance) is the order of appearance in the config.
        """
        return [
            self.get_sect_spec(sect_name)
            for sect_name in self.get_all_sect_names()]



class _CombinedConfigSpecDescriptor(CombinedWithSuper):

    def __init__(self, config_spec: Union[str, ConfigSpecEgg]) -> None:
        super().__init__(
            value=config_spec,
            value_combiner=self._combine_config_specs)

    def __set_name__(self, *args) -> None:
        super().__set_name__(*args)  # noqa
        self.value = _CombinedConfigSpecEgg(
            foreground=self.value,
            foreground_location=(f'{self.fixed_owner.__module__}'
                                 f'.{self.fixed_owner.__qualname__}'
                                 f'.{self.name}'))

    @staticmethod
    def _combine_config_specs(background: Union[str, ConfigSpecEgg],
                              foreground: '_CombinedConfigSpecEgg') -> '_CombinedConfigSpecEgg':
        return foreground.copy_setting_background(background)



class _CombinedConfigSpecEgg:

    #
    # Auxiliary exception class (non-public)

    class _CombinedConfigSpecEggError(ConfigSpecEggError):
        pass

    #
    # Other auxiliary classes and constants (non-public)

    # When `str.format_map()` is applied to a *config spec pattern* then
    # for each key *missing* from `format_data_mapping` a special object
    # (of type `_MissingFragment`) is created. Markers which represent
    # such objects in the resultant formatted *config spec* are always
    # distinguishable from any surrounding characters -- *even if* a
    # marker is trimmed to its one-character prefix (such a possibility
    # is unlikely when it comes to real-word *config spec patterns*, but
    # theoretically could occur if certain advanced techniques provided
    # by `str.format()`/`str.format_map()` are used).
    #
    # Thanks to that trick, the machinery of `_CombinedConfigSpecEgg`
    # is able to check whether the *final* combined *config spec*
    # suffers from fragment omissions caused by lack of certain items
    # in `format_data_mapping` -- whereas such omissions are ignored in
    # *intermediary* combined *config specs*.

    class _FormatDataDict(DictWithSomeHooks):

        def __missing__(self, key):
            return _CombinedConfigSpecEgg._MissingFragment(key)

    class _MissingFragment:

        def __init__(self, key):
            self._key_repr = repr(key)

        def __format__(self, _format_spec=None):
            # (note: here format spec is purposely ignored)
            return _CombinedConfigSpecEgg._MISSING_FRAGMENT_PATTERN.format(key_repr=self._key_repr)

        __repr__ = __str__ = __format__

    _MISSING_FRAGMENT_BOUNDARY_CHARS = Config.CONFIG_SPEC_RESERVED_CHARS

    __TMPL = Config.CONFIG_SPEC_RESERVED_CHAR_01 + '<%s>' + Config.CONFIG_SPEC_RESERVED_CHAR_00
    assert __TMPL.startswith(tuple(_MISSING_FRAGMENT_BOUNDARY_CHARS))
    assert __TMPL.endswith(tuple(_MISSING_FRAGMENT_BOUNDARY_CHARS))
    assert __TMPL == re.escape(__TMPL)

    _MISSING_FRAGMENT_PATTERN = __TMPL % '{key_repr}'
    _MISSING_FRAGMENT_REGEX = re.compile(__TMPL % '(?P<key_repr>[^\x00-\x1f]*)')


    #
    # Interface intended to be used only in `_CombinedConfigSpecDescriptor`

    def __init__(self,
                 foreground: Union[str, ConfigSpecEgg],
                 foreground_location: Optional[str] = None,
                 background: Optional[Union[str, ConfigSpecEgg]] = None) -> None:
        foreground_raw = as_config_spec_string(foreground)
        _verify_no_config_spec_reserved_chars(foreground_raw)
        # Foreground *config spec string* (derived from `_CombinedConfigSpecDescriptor.value`)
        self._foreground_raw: str = foreground_raw
        # Fixed owner's module and qualname + attr name (if any, for better error messages)
        self._foreground_location: Optional[str] = foreground_location
        # Background (parent) *config spec egg* (if any):
        self._background_egg: Optional[ConfigSpecEgg] = (
            background if isinstance(background, ConfigSpecEgg) or background is None
            else self.__class__(background))

    def copy_setting_background(self,
                                background: Union[str, ConfigSpecEgg]) -> '_CombinedConfigSpecEgg':
        return self.__class__(
            self._foreground_raw,
            self._foreground_location,
            background)


    #
    # Public interface, specific to the `ConfigSpecEgg` protocol

    # (see the docs of `ConfigSpecEgg.hatch_out()`)

    def hatch_out(self, format_data_mapping: Optional[Mapping[str, Any]] = None) -> str:
        if complete_formatting := (format_data_mapping is not None
                                   and not isinstance(format_data_mapping, self._FormatDataDict)):
            # Here we know we are within the foremost (outermost) call
            # in a chain of nested `hatch_out()` calls.
            format_data_mapping = self._FormatDataDict(format_data_mapping)
        rendered_config_spec = self._render(format_data_mapping)
        if complete_formatting:
            self._verify_no_missing_fragments(rendered_config_spec)
        return rendered_config_spec


    #
    # Internal methods

    def _render(self, format_data_mapping: Optional[_FormatDataDict[str, Any]]) -> str:
        with self._unifying_rendering_exceptions():
            fg_prepared = self._prepare_config_spec(self._foreground_raw, format_data_mapping)
            if self._background_egg is None:
                return str(fg_prepared)
            bg_prepared = self._prepare_config_spec(self._background_egg, format_data_mapping)
            return self._merge_config_specs(bg_prepared, fg_prepared)

    @contextlib.contextmanager
    def _unifying_rendering_exceptions(self):
        try:
            yield
        except self._CombinedConfigSpecEggError:
            raise
        except Exception as exc:
            msg = self._get_error_msg_for_wrapped_exc(exc)
            raise self._CombinedConfigSpecEggError(msg) from exc

    def _get_error_msg_for_wrapped_exc(self, exc: Exception) -> str:
        config_spec_descr = self._get_config_spec_descr('the config spec')
        return ascii_str(
            f'{config_spec_descr} could not be rendered because '
            f'of an exception - {make_exc_ascii_str(exc)}')

    def _prepare_config_spec(self,
                             config_spec: Union[str, ConfigSpecEgg],
                             format_data_mapping: Optional[_FormatDataDict[str, Any]],
                             ) -> _ConfSpecData:
        # (Note: if `config_spec` is `self._background_egg` then its
        # `hatch_out()` is invoked here by `as_config_spec_string()`.
        # On the other hand, if `config_spec` is `self._foreground_raw`
        # (a `str`) then its `.format_map()` is invoked here by
        # `as_config_spec_string()` unless `format_data_mapping` is
        # `None`. See the definition of `as_config_spec_string()`...)
        formatted_if_needed = as_config_spec_string(config_spec, format_data_mapping)
        return _ConfSpecData(formatted_if_needed)

    def _merge_config_specs(self,
                            bg_prepared: _ConfSpecData,
                            fg_prepared: _ConfSpecData) -> str:
        ready_sect_specs = self._iter_ready_sect_specs(bg_prepared, fg_prepared)
        return ''.join(map(str, ready_sect_specs))

    def _iter_ready_sect_specs(self,
                               bg_prepared: _ConfSpecData,
                               fg_prepared: _ConfSpecData) -> Iterator[_SectSpec]:
        fg_sect_name_to_spec = {sect_spec.name: sect_spec
                                for sect_spec in fg_prepared.get_all_sect_specs()}
        for bg_sect_spec in bg_prepared.get_all_sect_specs():
            fg_sect_spec = fg_sect_name_to_spec.pop(bg_sect_spec.name, None)
            if fg_sect_spec is not None:
                yield self._merge_sect_specs(bg_sect_spec, fg_sect_spec)
            else:
                yield bg_sect_spec
        fg_only_sect_specs = fg_sect_name_to_spec.values()
        yield from fg_only_sect_specs

    def _merge_sect_specs(self,
                          bg_sect_spec: _SectSpec,
                          fg_sect_spec: _SectSpec) -> _SectSpec:
        assert bg_sect_spec.name == fg_sect_spec.name
        free_opts_in_any = bg_sect_spec.free_opts_allowed or fg_sect_spec.free_opts_allowed
        free_opts_converter_spec = self._get_free_opts_converter_spec(bg_sect_spec, fg_sect_spec)
        ready_opt_specs = list(self._iter_ready_opt_specs(bg_sect_spec, fg_sect_spec))
        return _SectSpec(
            fg_sect_spec.name,
            ready_opt_specs,
            free_opts_in_any,
            free_opts_converter_spec)

    def _get_free_opts_converter_spec(self,
                                      bg_sect_spec: _SectSpec,
                                      fg_sect_spec: _SectSpec) -> Optional[str]:
        bg_has = bg_sect_spec.free_opts_allowed
        fg_has = fg_sect_spec.free_opts_allowed
        bg_converter_spec = bg_sect_spec.free_opts_converter_spec
        fg_converter_spec = fg_sect_spec.free_opts_converter_spec
        if bg_has and fg_has and bg_converter_spec != fg_converter_spec:
            raise ValueError(self._get_error_msg__free_opts_conv_differ(
                bg_converter_spec,
                fg_converter_spec,
                sect_name=fg_sect_spec.name))
        if fg_has:
            return fg_converter_spec
        if bg_has:
            return bg_converter_spec
        return None

    def _get_error_msg__free_opts_conv_differ(self,
                                              bg_converter_spec: str,
                                              fg_converter_spec: str,
                                              *,
                                              sect_name: str) -> str:
        config_spec_descr = self._get_config_spec_descr() or '...'
        bg_conv_repr = self._get_conv_repr_for_error_msg(bg_converter_spec)
        fg_conv_repr = self._get_conv_repr_for_error_msg(fg_converter_spec)
        return ascii_str(
            f'[{config_spec_descr}] cannot get the section '
            f'`{sect_name}` merged because of differing '
            f'*free options converter specs* '
            f'({bg_conv_repr} vs. {fg_conv_repr})')

    def _iter_ready_opt_specs(self,
                              bg_sect_spec: _SectSpec,
                              fg_sect_spec: _SectSpec) -> Iterator[_OptSpec]:
        fg_opt_name_to_spec = {opt_spec.name: opt_spec
                               for opt_spec in fg_sect_spec.opt_specs}
        for bg_opt_spec in bg_sect_spec.opt_specs:
            fg_opt_spec = fg_opt_name_to_spec.pop(bg_opt_spec.name, None)
            if fg_opt_spec is not None:
                yield self._merge_opt_specs(bg_opt_spec, fg_opt_spec, sect_name=fg_sect_spec.name)
            else:
                yield bg_opt_spec
        fg_only_opt_specs = fg_opt_name_to_spec.values()
        yield from fg_only_opt_specs

    def _merge_opt_specs(self,
                         bg_opt_spec: _OptSpec,
                         fg_opt_spec: _OptSpec,
                         *,
                         sect_name: str) -> _OptSpec:
        assert bg_opt_spec.name == fg_opt_spec.name
        if bg_opt_spec.converter_spec != fg_opt_spec.converter_spec:
            raise ValueError(self._get_error_msg__opt_conv_differ(
                bg_opt_spec.converter_spec,
                fg_opt_spec.converter_spec,
                sect_name=sect_name,
                opt_name=fg_opt_spec.name))
        return _OptSpec(
            fg_opt_spec.name,
            fg_opt_spec.default,
            fg_opt_spec.converter_spec)

    def _get_error_msg__opt_conv_differ(self,
                                        bg_converter_spec: str,
                                        fg_converter_spec: str,
                                        *,
                                        sect_name: str,
                                        opt_name: str) -> str:
        config_spec_descr = self._get_config_spec_descr() or '...'
        bg_conv_repr = self._get_conv_repr_for_error_msg(bg_converter_spec)
        fg_conv_repr = self._get_conv_repr_for_error_msg(fg_converter_spec)
        return ascii_str(
            f'[{config_spec_descr}] cannot get the section '
            f'`{sect_name}` merged because of differing '
            f'*converter specs* of the option `{opt_name}` '
            f'({bg_conv_repr} vs. {fg_conv_repr})')

    def _get_conv_repr_for_error_msg(self, converter_spec: str) -> str:
        return ('a fragment containing unformatted stuff'
                if self._MISSING_FRAGMENT_BOUNDARY_CHARS.intersection(converter_spec)
                else repr(converter_spec))

    def _verify_no_missing_fragments(self, rendered_config_spec: str) -> None:
        if self._MISSING_FRAGMENT_BOUNDARY_CHARS.intersection(rendered_config_spec):
            msg = self._get_error_msg__missing_fragments(rendered_config_spec)
            raise self._CombinedConfigSpecEggError(msg)

    def _get_error_msg__missing_fragments(self, rendered_config_spec: str) -> str:
        config_spec_descr = self._get_config_spec_descr('the rendered config spec')
        msg = (f'{config_spec_descr} is incorrect because of certain '
               f'keys missing from the format data mapping')
        if key_reprs := [match['key_repr']
                         for match in self._MISSING_FRAGMENT_REGEX.finditer(rendered_config_spec)]:
            # ("most probably" -- because, in theory, collection of
            # these missing keys is not 100%-reliable; in practice,
            # for real-word config specs, it should always be OK;
            # anyway, it is done only for better error messages)
            msg += f' (most probably: {", ".join(key_reprs)})'
        else:
            # (a very rare condition, should not occur in real-word cases)
            msg += (f' (or some reserved characters in the config spec?)')
        return ascii_str(msg)

    def _get_config_spec_descr(self, stem: str = '') -> str:
        descr = stem
        if self._foreground_location:
            descr += f' `{self._foreground_location}`'
        return descr.strip()



def _verify_no_config_spec_reserved_chars(config_spec_string: str) -> None:
    found_reserved = Config.CONFIG_SPEC_RESERVED_CHARS.intersection(config_spec_string)
    if found_reserved:
        raise ValueError(ascii_str(
            f'found config spec\'s character(s) reserved for internal '
            f'purposes: {", ".join(map(repr, sorted(found_reserved)))}'))



if __name__ == "__main__":
    import doctest
    doctest.testmod()

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import ast
import collections
import ConfigParser
import json
import os
import os.path as osp
import re
import sys

from n6lib.argument_parser import N6ArgumentParser
from n6lib.class_helpers import get_class_name
from n6lib.common_helpers import (
    DictWithSomeHooks,
    as_unicode,
    ascii_str,
    memoized,
    reduce_indent,
    string_to_bool,
)
from n6lib.const import ETC_DIR, USER_DIR
from n6lib.datetime_helpers import (
    parse_iso_date,
    parse_iso_datetime_to_utc,
)
from n6lib.log_helpers import get_logger



LOGGER = get_logger(__name__)



#
# 1. Standard stuff (mainly ConfigParser-based)
#


class ConfigError(Exception):

    """
    A generic, Config-related, exception class.

    >>> print ConfigError('Some Message')
    [configuration-related error] Some Message

    >>> print ConfigError('Some arg', 42L, 'Yet another arg')
    [configuration-related error] ('Some arg', 42L, 'Yet another arg')
    """

    def __str__(self):
        return '[configuration-related error] ' + super(ConfigError, self).__str__()



_KeyError_str_func = getattr(KeyError.__str__, '__func__', None)

class _KeyErrorSubclassMixin(KeyError):  # a non-public helper

    def __str__(self):
        # we want to *avoid* using KeyError.__str__() (which -- contrary
        # to what Exception.__str__() does -- applies repr() to a sole
        # string argument) so we *skip* it in the MRO
        method = super(_KeyErrorSubclassMixin, self).__str__
        if getattr(method, '__objclass__', None) is KeyError or (
              # for compatibility with non-CPython (e.g. PyPy):
              _KeyError_str_func is not None and
              _KeyError_str_func is getattr(method, '__func__', None)):
            method = super(KeyError, self).__str__
        return method()



class NoConfigSectionError(_KeyErrorSubclassMixin, ConfigError):

    """
    Raised by Config.__getitem__() when the specified section is missing.

    >>> exc = NoConfigSectionError('some_sect')
    >>> isinstance(exc, ConfigError) and isinstance(exc, KeyError)
    True
    >>> print exc
    [configuration-related error] no config section `some_sect`
    >>> exc.sect_name
    'some_sect'

    >>> exc2 = NoConfigSectionError('some_sect', 'arg', 42L)
    >>> print exc2
    [configuration-related error] ('no config section `some_sect`', 'arg', 42L)
    >>> exc2.sect_name
    'some_sect'
    """

    def __init__(self, sect_name, *args):
        msg = "no config section `{0}`".format(sect_name)
        super(NoConfigSectionError, self).__init__(msg, *args)
        self.sect_name = sect_name



class NoConfigOptionError(_KeyErrorSubclassMixin, ConfigError):

    """
    Raised by ConfigSection.__getitem__() when the specified option is missing.

    >>> exc = NoConfigOptionError('mysect', 'myopt')
    >>> isinstance(exc, ConfigError) and isinstance(exc, KeyError)
    True
    >>> print exc
    [configuration-related error] no config option `myopt` in section `mysect`
    >>> exc.sect_name
    'mysect'
    >>> exc.opt_name
    'myopt'

    >>> exc2 = NoConfigOptionError('S', 'o', 42L)
    >>> print exc2
    [configuration-related error] ('no config option `o` in section `S`', 42L)
    >>> exc2.sect_name
    'S'
    >>> exc2.opt_name
    'o'
    """

    def __init__(self, sect_name, opt_name, *args):
        msg = "no config option `{0}` in section `{1}`".format(opt_name, sect_name)
        super(NoConfigOptionError, self).__init__(msg, *args)
        self.sect_name = sect_name
        self.opt_name = opt_name



class Config(DictWithSomeHooks):

    """
    Parse the configuration and provide a dict-like access to it.

    Config is a dict subclass.  Generally, its instances behave like a
    dict; lookup-by-key failures are signalled with NoConfigSectionError
    which is a subclass of both KeyError and ConfigError.  A Config
    instance maps configuration section names (str) to ConfigSection
    instances.

    There are two main ways of Config instantiation:

    * the modern (recommended) way -- with so called *configuration
      specification* as the obligatory argument (`config_spec`) and
      a few optional keyword arguments (see the "Modern way of
      instantiation" docstring section below).

    * the legacy (obsolete) way -- with the `required` dict (that maps
      required section names to sequences of required option names) as
      the sole (but still *optional*) argument (see the "Legacy way of
      instantiation" docstring section below).


    Modern way of instantiation (recommended)
    -----------------------------------------

    Args (obligatory):
        `config_spec` (str):
            The configuration specification in a ConfigParser-like
            format.  It defines: what config sections are to be
            included, what config options are legal, what config options
            are required, how values of particular config options shall
            be converted (e.g., coerced to int or bool...).  See the
            "Configuration specification format" docstring section
            below.

    Kwargs (optional):
        `settings` (dict or None; default: None):
            Depending on the value of the argument:

            * if it is None (the default value), the configuration will
              be read from /etc/n6/*.conf and ~/.n6/*.conf files
              (excluding logging.* and logging-*) [so called "N6Core
              way"];

              NOTE that all normal ConfigParser processing is done,
              especially option names (but *not* section names) are
              normalized to lowercase -- before applying converters
              (see below: the description of the `custom_converters`
              argument);

            * if it is not None, it must be a Pyramid-like settings
              dictionary -- mapping '<section name>.<option name>'
              strings to raw option value strings; the configuration
              will be taken from the dictionary, *not* from any files
              [so called "Pyramid way"; typically the content of the
              `settings` dictionary is the result of parsing the
              `[app:main]` part of a Pyramid *.ini file in which each
              option is specified in the `<section name>.<option name> =
              <option value>` format];

              NOTE: option names taken from a `settings` dict (contrary
              to option names from configuration files parsed with
              ConfigParser) are *not* normalized to lowercase; on the
              other hand, any unicode option names are encoded to str
              using UTF-8 (and non-string keys are just omitted); also,
              non-str option values (if any) -- before being converted
              (see below: the description of the `custom_converters`
              argument) -- are coerced to str (especially, unicode
              values are encoded to str using UTF-8).

        `custom_converters` (dict or None; default: None):
            If not None it must be a dictionary that maps custom
            converter names (being strings) to actual converter callables.
            Such a callable (e.g., a function) must take one argument being
            a str instance and return a value of some type.  By default,
            only converters defined in the Config.BASIC_CONVERTERS
            dictionary (mapping standard converter names to their
            callables) are used to convert values of raw options (which
            are marked in `config_spec` with a particular converter
            name, aka converter spec) to actual values; if a
            `custom_converters` dictionary is specified the converters
            it contains are also applied (they can even override
            converters defined in Config.BASIC_CONVERTERS).  See also
            the "Configuration specification format" and "Standard
            converter specs" docstring sections below.

        `default_converter` (str or callable; default: str()):
            This argument specifies the converter callable (see the
            description of `custom_converters` above) to be used to
            convert values of options that are *not* marked in
            `config_spec` with any converter name.  If a string (and
            not a callable) it must be a key in at least one of the
            mappings: Config.BASIC_CONVERTERS or `custom_converters`.

    Raises:
        * ConfigError -- for any configuration-related error,
          with an error message describing what was the problem.

        * TypeError -- if `config_spec` is not an instance of str.

        * KeyError -- if `default_converter` specified as a str
          is not a key in in at least one of the mappings:
          Config.BASIC_CONVERTERS and `custom_converters`.


    NOTE:

    * The resultant Config instance contains only sections that are
      contained by `config_spec`.

    * Option values are converted (see: the description of the
      `custom_converters` argument above) according to the specified
      `config_spec`, using Config.BASIC_CONVERTERS (optionally, also
      `custom_converters` and/or `default_converter` -- described
      above).

    (Compare the above notes with those in the "Legacy way of
    instantiation" docstring section below.)


    Examples:

        MY_CONFIG_SPEC = '''
        [first]
        foo = bar          ; no converter spec, default value: 'bar'
        spam = 42 :: int   ; converter spec: int, default value: 42

        [second]
        spam :: float      ; converter spec: float, no default value (required)
        boo = yes :: bool  ; converter spec: bool, default value: True
        '''

        # from config files:
        my_config = Config(MY_CONFIG_SPEC)

        # from a Pyramid-like `settings` dict:
        my_config = Config(MY_CONFIG_SPEC, settings={
            'first.foo': 'two bars',
            'first.spam': '43',       # note: this is a raw value (str)
            'second.spam': '44.2',    # note: this is a raw value (str)
        })

        # from config files + with custom default converter
        # (which here will be applied to the value of the
        # `foo` option in the `first` section because that
        # option does not have its own converter spec)
        my_config = Config(MY_CONFIG_SPEC, default_converter=str.upper)

    Then you can easily get the needed information:

        first_section = my_config['first']
        foo = first_section['foo']
        # or just:
        foo = my_config['first']['foo']


    See also: the ConfigMixin class which makes Config instantiation
    (the modern variant) as convenient as possible.


    Convenience class method: Config.section()
    ------------------------------------------

    There is also a convenience solution for (frequent) cases when there
    is only one section in the config spec -- so you are interested
    directly in the ConfigSection object (the only one) rather than in
    its "parent" Config object: the Config.section() class method.
    Example:

        SIMPLE_CONFIG_SPEC = '''
            [the]
            foo = bar
            spam = 42 :: int
        '''
        the_section = Config.section(SIMPLE_CONFIG_SPEC,
                                     settings={'the.foo': 'Xyz'})
        assert the_section['foo'] == 'Xyz'
        assert the_section['spam'] == 42

    See also: the ConfigMixin class which makes creating a ConfigSection
    from config spec even more convenient.


    Configuration specification format
    ----------------------------------

    The syntax of `config_spec` strings is similar to the standard
    INI-format config syntax -- with the proviso that:

    * the value of an option specifies its default value;

    * it can be followed by: `:: <converter_spec>` where
      <converter_spec> is a name of a value converter (such as
      'int', 'float', 'bool' etc.);

    * if the default value is not specified (i.e., `no-value option`
      syntax is used) the `:: <convig_spec>` part can follow just the
      option name;

    * a `...` marker can be used instead of an option name; if it is
      present in a particular section then that section is allowed to
      contain "free" (aka "arbitrary") options, i.e., some options that
      are not declared in the section specification; otherwise *only*
      explicitly specified options are legal;

    * a `...` marker can be followed by `:: <converter_spec>` -- then
      the specified value converter will be applied to all "free"
      ("arbitrary") options in a particular section.

    Example:

        SOME_CONFIG_SPEC = '''
        [some_section]
        some_opt = default val :: unicode  ; default value + converter spec
        another_opt = its default val    ; default value, no converter spec
        required_without_default :: int  ; converter spec, no default value
        another_required_opt             ; no converter spec, no default value
        ...           ; `...` means that other (arbitrary) options are allowed

        [another_section]
        some_required_opt :: unicode
        yet_another_option : yes :: bool
        # below: `...` with a converter spec -- means that other (arbitrary)
        # options are allowed and that the specified converter shall be applied
        # to their values
        ... :: unicode

        [yet_another_section]
        some_required_opt
        a_few_numbers = 1, 2, 3, 44 :: list_of_int
        # note: lack of `...` means that only the `some_required_opt` and
        # `a_few_numbers` options are allowed in this section
        '''


    Standard converter specs
    ------------------------

    There is a set of converters that are accessible out-of-the-box
    (they are defined in the Config.BASIC_CONVERTERS constant).

    Below -- standard converter specs with example conversions:

    * str: 'abc' -> 'abc' (a "do nothing" conversion)

    * unicode: 'abc' -> u'abc'
               'ś' -> u'ś' (note: using UTF-8)

    * bool: 'true' or 't' or 'yes' or 'y' or 'on' or '1' -> True
            'false' or 'f' or 'no' or 'n' or 'off' or '0' -> False
            (case-insensitive so uppercase letters are also OK;
            implementation: n6lib.common_helpers.string_to_bool())

    * int: '42' -> 42
           '-42' -> -42

    * float: '42' -> 42.0
             '-42.2' -> -42.2

    * date: '2010-07-19' -> datetime.date(2010, 7, 19)
            (implementation: n6lib.datetime_helpers.parse_iso_date()

    * datetime: '2010-07-19 12:39:45+02:00'
                -> datetime.datetime(2010, 7, 19, 10, 39, 45)
                (note: normalizing timezone to UTC; implementation:
                n6lib.datetime_helpers.parse_iso_datetime_to_utc))

    * list_of_str: 'a, b, c, d, e,'  -> ['a', 'b', 'c', 'd', 'e']
                   'a,b,c,d,e'       -> ['a', 'b', 'c', 'd', 'e']
                   ' a, b,c,d , e, ' -> ['a', 'b', 'c', 'd', 'e']

    * list_of_unicode: ' a, b,c,d , e, ' -> [u'a', u'b', u'c', u'd', u'e']

    * list_of_bool: 'yes,No , True ,OFF' -> [True, False, True, False]

    * list_of_int: '42,43,44,' -> [42, 43, 44]

    * list_of_float: ' 0.2 , 0.4 ' -> [0.2, 0.4]

    * list_of_date: '2010-07-19, 2011-08-20'
                    -> [datetime.date(2010, 7, 19),
                        datetime.date(2010, 7, 20)]

    * list_of_datetime: '2010-07-19 12:39:45+02:00,2011-08-20T23:23,'
                        -> [datetime.datetime(2010, 7, 19, 10, 39, 45),
                            datetime.datetime(2010, 7, 20, 23, 23)]

    * py: "[('a',), {42: None}]" -> [('a',), {42: None}]
          (implementation uses ast.literal_eval())

    * json: '[["a"], {"b": null}]' -> [[u'a'], {u'b': None}]
            (implementation uses json.loads())

    All `list_of_...` converters are implemented using the
    Config.make_list_converter() static method; you can use it to
    implement your own custom list converters.


    Legacy way of instantiation (obsolete)
    --------------------------------------

    Args/kwargs (optional):
        `required` (dict):
            A dictionary that maps required section names (strings) to
            sequences (such as tuples or lists) of required option
            names, e.g.: `{'section1': ('opt1', 'opt2'), 'section2':
            ['another_opt']}`.  Note that any other section/option names
            are legal and the resultant Config will contain them as
            well.

    Raises:
        * SystemExit (!) -- if any required section/option is missing.
        * ConfigParser.Error (or any of its subclasses) -- if a config
          file cannot be properly parsed.

    NOTE:

    * The resultant Config instance contains all sections and options --
      from all read files.

    * All resultant option values are just strings (*no* conversion is
      performed).

    (Compare the above notes with those in the "Modern way of
    instantiation" docstring section above.)


    Override config values for particular script run
    ------------------------------------------------

    If a script uses the "N6Core way" of obtaining the configuration
    data (i.e., reads them from `.conf` files) -- no matter whether the
    *modern* or the *legacy* variant of instantiation is employed -- it
    is possible to override selected config options *for a particular
    script run* using the `--n6config-override` command line argument.

    Check `n6lib.argument_parser.N6ArgumentParser` for more information.
    """

    # internal sentinel object
    __NOT_CONVERTED = object()

    # internal helper
    def __make_list_converter(item_converter, name=None, delimiter=','):
        def converter(s):
            s = s.strip()
            if s.endswith(delimiter):
                # remove trailing delimiter
                s = s[:-len(delimiter)].rstrip()
            if s:
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

    # internal helper
    def __strip_utf8_literal_eval(s):
        return ast.literal_eval(s.decode('utf-8').strip())


    # public constant (should never be modified in-place!)
    BASIC_CONVERTERS = {
        'str': str,
        'unicode': as_unicode,
        'bool': string_to_bool,
        'int': int,
        'float': float,
        'date': parse_iso_date,
        'datetime': parse_iso_datetime_to_utc,
        'list_of_str': __make_list_converter(str, 'list_of_str'),
        'list_of_unicode': __make_list_converter(as_unicode, 'list_of_unicode'),
        'list_of_bool': __make_list_converter(string_to_bool, 'list_of_bool'),
        'list_of_int': __make_list_converter(int, 'list_of_int'),
        'list_of_float': __make_list_converter(float, 'list_of_float'),
        'list_of_date': __make_list_converter(parse_iso_date, 'list_of_date'),
        'list_of_datetime': __make_list_converter(parse_iso_datetime_to_utc, 'list_of_datetime'),
        'py': __strip_utf8_literal_eval,
        'json': json.loads,
    }


    # public static method
    make_list_converter = staticmethod(__make_list_converter)


    def __init__(self, *args, **kwargs):
        super(Config, self).__init__()
        self._config_overridden_dict = N6ArgumentParser().get_config_overridden_dict()
        if (not args and not kwargs or  # no arguments...
              # ...or only the `required` argument given:
              not kwargs and len(args) == 1 and isinstance(args[0], dict) or
              not args and len(kwargs) == 1 and isinstance(kwargs.get('required'), dict)):
            self._legacy_init(*args, **kwargs)
        else:
            self._modern_init(*args, **kwargs)


    @classmethod
    def section(cls, *args, **kwargs):
        """
        A class method that creates a Config and picks its sole section.

        This method exists just for convenience.  It requires that the
        config spec contains exactly one config section.

        Args/kwargs:
            Like for the Config constructor.

        Returns:
            A ConfigSection instance.

        Raises:
            ConfigError -- also if there is no config section or more
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
            ConfigError: ...but no sections found

            >>> config_spec = '''
            ... [foo]
            ... abc = 42 :: int
            ... [bar]'''
            >>> Config.section(config_spec, settings=s)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
              ...
            ConfigError: ...but the following sections found: 'bar', 'foo'

        See also: ConfigMixin.get_config_section().
        """
        self = cls(*args, **kwargs)
        try:
            [section] = self.itervalues()
        except ValueError:
            all_sections = sorted(self)
            sections_descr = (
                'the following sections found: {0}'.format(
                    ', '.join(map(repr, map(ascii_str, all_sections))))
                if all_sections else 'no sections found')
            raise ConfigError(
                'expected config spec that defines '
                'exactly one section but ' + sections_descr)
        return section


    @classmethod
    def make(*args, **kwargs):
        """
        An alternative (dict-like) constructor.

        (Useful especially in unit tests.)

        Args/kwargs:
            Like for dict() or dict.update() -- except that keys (of
            the resultant mapping) are required to be str instances
            and values are required to be either: mappings whose keys
            are str instances, or iterables of (<key being str
            instance>, <value (being anything)>) pairs (where "pair"
            means: a 2-tuple or any other 2-element iterable).

        Returns:
            A new Config instance (whose values are new ConfigSection
            instances).

        Raises:
            * TypeError -- if any non-str key is detected in the
              resultant mapping or in any of the mappings being its
              values (see below).
            * TypeError or ValueError (adequeately) -- if the given args
              are not "appropriate for a dict of dicts" (see below).

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

        >>> Config.make({'abc': {'k': 'v'}}, abc={'kk': 42L})
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make({'abc': {'k': 'v'}}, abc=[('kk', 42L)])
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make({'abc': [('k', 'v')]}, abc={'kk': 42L})
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make({'abc': [('k', 'v')]}, abc=[('kk', 42L)])
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make([('abc', {'k': 'v'})], abc={'kk': 42L})
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make([('abc', {'k': 'v'})], abc=[('kk', 42L)])
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make([('abc', [('k', 'v')])], abc={'kk': 42L})
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)
        >>> Config.make([('abc', [('k', 'v')])], abc=[('kk', 42L)])
        Config(<{'abc': ConfigSection('abc', {'kk': 42L})}>)

        >>> Config.make({42L: {'k': 'v'}})
        Traceback (most recent call last):
          ...
        TypeError: key 42L is not a str instance
        >>> Config.make({'abc': {42L: 'v'}})
        Traceback (most recent call last):
          ...
        TypeError: key 42L is not a str instance
        >>> Config.make(42L)                             # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...
        >>> Config.make({'abc': 42L})                    # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...
        >>> Config.make({'abc': [42L]})                  # doctest: +IGNORE_EXCEPTION_DETAIL
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
        cls = args[0]
        self = cls.__new__(cls)
        super(Config, self).__init__(*args[1:], **kwargs)
        for sect_name, opt_name_to_value in self.iteritems():
            sect = ConfigSection(sect_name, opt_name_to_value)
            keys = [sect_name]
            keys.extend(sect.iterkeys())
            for key in keys:
                if not isinstance(key, str):
                    raise TypeError('key {0!r} is not a str instance'.format(key))
            self[sect_name] = sect
        return self

    #
    # DictWithSomeHooks-specific customizations

    def _constructor_args_repr(self):
        content_repr = super(Config, self)._constructor_args_repr()
        return '<{0}>'.format(content_repr)

    def _custom_key_error(self, key_error, method_name):
        exc = super(Config, self)._custom_key_error(key_error, method_name)
        return NoConfigSectionError(*exc.args)

    #
    # Implementation of the modern way of initialization

    def _modern_init(self, config_spec,
                     settings=None,
                     custom_converters=None,
                     default_converter=str):
        if not isinstance(config_spec, str):
            raise TypeError('config_spec must be str, not {0}'.format(
                get_class_name(config_spec)))
        converters = dict(self.BASIC_CONVERTERS)
        if custom_converters is not None:
            converters.update(custom_converters)
        if not callable(default_converter):
            default_converter = converters[default_converter]
        converters[None] = default_converter
        try:
            try:
                conf_spec_data = parse_config_spec(config_spec)
                if settings is None:
                    sect_name_to_opt_dict = self._load_n6_config_files()
                    self._override_config_values_by_cmdlines_arguments(sect_name_to_opt_dict)
                else:
                    sect_name_to_opt_dict = self._convert_settings_dict(settings)
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
                raise e
        except ConfigError as err:
            if settings is None:
                print >>sys.stderr, _N6CORE_CONFIG_ERROR_MSG_PATTERN.format(ascii_str(err))
            raise

    def _convert_settings_dict(self, settings):
        sect_name_to_opt_dict = {}
        for key, value in settings.iteritems():
            if isinstance(key, unicode):
                key = key.encode('utf-8')
            elif not isinstance(key, str):
                LOGGER.warning('Ignoring non-string settings key %r', key)
                continue
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            elif not isinstance(value, str):
                if not self._is_standard_pyramid_key_of_nonstring(key):  # <- to reduce log noise
                    LOGGER.warning(
                        'Coercing non-string value %r (of setting %s) '
                        'to str (before further conversion)',
                        value, ascii_str(key))
                value = str(value)
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

    def _is_standard_pyramid_key_of_nonstring(self, key):
        return key.startswith('pyramid.') or key in (
            'debug_authorization',
            'debug_notfound',
            'debug_routematch',
            'debug_templates',
            'prevent_http_cache',
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
                input_opt_dict.viewkeys() -
                set(opt_spec.name for opt_spec in sect_spec.opt_specs))
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
                'error when applying config value converter {0!r} '
                'to {1}={2!r} ({3}: {4})'.format(
                    converter,
                    opt_descr,
                    opt_value,
                    get_class_name(exc),
                    ascii_str(exc)))
            # we use this special sentinel object because None is a valid value
            return self.__NOT_CONVERTED

    #
    # Implementation of the legacy way of initialization

    def _legacy_init(self, required=None):
        sect_name_to_opt_dict = self._load_n6_config_files()
        self._override_config_values_by_cmdlines_arguments(sect_name_to_opt_dict)
        if required is not None:
            missing_msg = self._get_error_msg_if_missing(sect_name_to_opt_dict, required)
            if missing_msg:
                LOGGER.error('%s', missing_msg)
                sys.exit(_N6CORE_CONFIG_ERROR_MSG_PATTERN.format(missing_msg))
        self.update(
            (sect_name, ConfigSection(
                sect_name,
                opt_name_to_value))
            for sect_name, opt_name_to_value in sect_name_to_opt_dict.iteritems())

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
    def _load_n6_config_files(cls):
        sect_name_to_opt_dict = {}
        config_parser = ConfigParser.SafeConfigParser()
        config_files = []
        config_files.extend(cls._get_config_file_paths(ETC_DIR))
        config_files.extend(cls._get_config_file_paths(USER_DIR))
        if not config_files:
            LOGGER.warning('No config files to read')
            return sect_name_to_opt_dict

        ok_config_files = config_parser.read(config_files)
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
            sect_name_to_opt_dict[sect_name] = opt_name_to_value
            assert (
                isinstance(sect_name, str) and
                all(isinstance(opt_name, str) for opt_name in opt_name_to_value))
        return sect_name_to_opt_dict

    @staticmethod
    def _get_config_file_paths(path):
        """
        Get the paths of configuration files from a given dir.

        (All *.conf files except those whose names start with 'logging.'
        or 'logging-'.)

        Args:
            `path`: path of the directory to search for *.conf files in.

        Returns:
            A sorted list of paths of configuration files.
        """
        config_files = []
        for directory, _, fnames in os.walk(path):
            for fname in fnames:
                if (fname.endswith(".conf") and
                      not fname.startswith(("logging.", "logging-"))):
                    config_files.append(osp.join(directory, fname))
        return sorted(config_files)

    def _override_config_values_by_cmdlines_arguments(self, config_dir):
        for key, value in self._config_overridden_dict.iteritems():
            if key in config_dir:
                config_dir[key].update(value)


class ConfigSection(DictWithSomeHooks):

    """
    A dict subclass; its instances are values of a Config mapping.

    Generally, ConfigSection instances behave like a dict; lookup-by-key
    failures are signalled with NoConfigOptionError which is a subclass
    of both KeyError and ConfigError.  A ConfigSection instance
    represents a configuration section; it maps configuration option
    names (str) to option values (possibly of any types).  It keeps also
    the name of the configuration section it represents.

    >>> s = ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> s
    ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> s.sect_name
    'some_sect'

    >>> len(s)
    1
    >>> s.items()
    [('some_opt', 'FOO_bar,spam')]

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
    NoConfigOptionError: [conf... `another_opt` in section `some_sect`

    A few more examples:

    >>> another_s = ConfigSection('some_sect')
    >>> another_s
    ConfigSection('some_sect', {})
    >>> another_s.sect_name
    'some_sect'
    >>> len(another_s)
    0
    >>> another_s.items()
    []
    >>> another_s == {}
    True
    >>> another_s == {'some_opt': 'FOO_bar,spam'}
    False

    >>> another_s['some_opt'] = 'FOO_bar,spam'
    >>> another_s['some_opt']
    'FOO_bar,spam'
    >>> len(another_s)
    1
    >>> another_s.keys()
    ['some_opt']
    >>> another_s.values()
    ['FOO_bar,spam']
    >>> another_s
    ConfigSection('some_sect', {'some_opt': 'FOO_bar,spam'})
    >>> another_s == {}
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
        super(ConfigSection, self).__init__(opt_name_to_value)

    def __eq__(self, other):
        if isinstance(other, ConfigSection) and other.sect_name != self.sect_name:
            return False
        return super(ConfigSection, self).__eq__(other)

    #
    # DictWithSomeHooks-specific customizations

    def _constructor_args_repr(self):
        content_repr = super(ConfigSection, self)._constructor_args_repr()
        return '{0!r}, {1}'.format(self.sect_name, content_repr)

    def _custom_key_error(self, key_error, method_name):
        exc = super(ConfigSection, self)._custom_key_error(key_error, method_name)
        return NoConfigOptionError(self.sect_name, *exc.args)



class ConfigMixin(object):

    """
    A convenience mixin for classes that make use of Config stuff.

    The most important public methods it provides are:

    * get_config_full(...) -- returns a ready-to-use Config instance.
    * get_config_section(...) -- returns a ready-to-use ConfigSection
      instance

    -- you can use them *instead* of calling Config stuff directly.

    Both of them make use of the following attributes (which, typically,
    will be class attributes -- but they are got through an instance so
    it is possible to customize them per-instance if needed):

    * `config_spec` or -- alternatively -- `config_spec_pattern`;
    * `custom_converters` -- optional;
    * `default_converter` -- optional;
    * `config_required` (for compatibility with legacy stuff)
      -- optional;
    * `config_group` (for compatibility with legacy stuff)
      -- optional.

    The get_config_section() method is probably more handy because in
    most cases you are interested in a particular (only one) config
    section.

    Additionally, there are two public helper methods

    * is_config_spec_or_group_declared() -- which informs whether
      at least one of the following attributes is present and set
      to some non-None value: `config_spec`, `config_spec_pattern`,
      `config_group`.
    * make_list_converter() -- a static method being an alias of
      Config.make_list_converter() (just for convenience).

    Let the examples speak...


    First, let us consider a case when a simple `config_spec` is
    defined; it contains just one config section -- so we can use the
    get_config_section() method:

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
        >>> from mock import patch
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
        >>> m.is_config_spec_or_group_declared()
        True

    Below is the same -- but with config contents taken from a Pyramid
    `settings` dict (and *not* loaded from *.conf files):

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
        >>> m.is_config_spec_or_group_declared()
        True


    Again, `config_spec` and one config section in use -- but
    additionally with `custom_converters`:

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: list_of_long
        ...     '''
        ...     custom_converters = {
        ...         'list_of_long': Config.make_list_converter(long),
        ...     }
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': ' 0 , 123,12345,'},
        ...                            'other': {'ham': 'Abc'}}
        >>> from mock import patch
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
        [0L, 123L, 12345L]
        >>> m.is_config_spec_or_group_declared()
        True

    The same with config contents taken from a Pyramid `settings` dict
    (*not* loaded from *.conf files):

        >>> example_settings = {'foo.spam': '0,123,12345', 'other.ham': 'Abc'}
        >>> m = MyClass(example_settings)
        >>> sorted(m.config.keys())
        ['bar', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['spam']
        [0L, 123L, 12345L]
        >>> m.is_config_spec_or_group_declared()
        True


    Now, with `default_converter`; plus also, this time, there is more
    than one config section specified (so the get_config_full() method
    is used instead of get_config_section()):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...
        ...         [other]
        ...         ham
        ...     '''
        ...     default_converter = 'py'
        ...
        ...     def __init__(self, settings=None):
        ...         self.config_full = self.get_config_full(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': '{42: u"abc"}'}}
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
        ConfigSection('other', {'ham': {42: u'abc'}})
        >>> m.is_config_spec_or_group_declared()
        True

    The same with config contents taken from a Pyramid `settings` dict
    (*not* loaded from *.conf files):

        >>> example_settings = {'foo.spam': '[null]',
        ...                     'other.ham': '{42: u"abc"}'}
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
        ConfigSection('other', {'ham': {42: u'abc'}})
        >>> m.is_config_spec_or_group_declared()
        True


    Another example: with `config_spec_pattern` (str.format()-able
    pattern) defined instead of `config_spec`:

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_spec_pattern = '''
        ...         [{section_name}]
        ...         {opt_name} = 42 :: {opt_converter_spec}
        ...         spam :: json
        ...     '''
        ...
        ...     def __init__(self, settings=None, **fmt_args):
        ...         self.config = self.get_config_section(settings, **fmt_args)
        ...
        >>> example_conf_from_files = {'tralala': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...
        ...     # keyword arguments to format actual config_spec:
        ...     m = MyClass(section_name='tralala',
        ...                 opt_name='hop-hop',
        ...                 opt_converter_spec='float')
        ...
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
        >>> m.is_config_spec_or_group_declared()
        True

    The same with config contents taken from a Pyramid `settings` dict
    (*not* loaded from *.conf files):

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
        >>> m.is_config_spec_or_group_declared()
        True


    The following examples involve the legacy attributes: 'config_group`
    and/or 'config_required` (many n6 collectors have them).


    First, just 'config_group` + `config_required` (note that
    `config_spec` -- being omitted here -- defaults to an empty string;
    but also that -- because the section defined as `config_group` is
    not present in the initial `config_spec` -- the section in the
    resultant config spec contains the `...` marker):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_group = 'foo'
        ...     config_required = ('bar', 'ham')
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> example_conf_from_files = {'foo': {'bar': '123', 'ham': '1'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> # note the resultant config spec
        ... m._ConfigMixin__get_config_spec() == '''
        ... [foo]
        ... bar
        ... ham
        ... ...
        ...
        ... '''
        True
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'foo'
        >>> sorted(m.config.keys())
        ['bar', 'ham']
        >>> m.config['bar']
        '123'
        >>> m.config['ham']
        '1'
        >>> m.is_config_spec_or_group_declared()
        True

    Another example -- `config_required` + `config_spec` [sic]
    (`config_required` addes the option `ham` to the config spec):

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_required = ('bar', 'ham')
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': '[null]', 'ham': '1'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> # note the resultant config spec
        >>> m._ConfigMixin__get_config_spec() == '''
        ... [foo]
        ... bar = 42 :: int
        ... spam :: json
        ... ham
        ... '''
        True
        >>> isinstance(m.config, ConfigSection)
        True
        >>> m.config.sect_name
        'foo'
        >>> sorted(m.config.keys())
        ['bar', 'ham', 'spam']
        >>> m.config['bar']
        42
        >>> m.config['ham']
        '1'
        >>> m.config['spam']
        [None]
        >>> m.is_config_spec_or_group_declared()
        True

    And a similar example -- here `config_required` is legal but
    completely redundant because it does not add any information to what
    `config_spec` specifies:

        >>> class MyClass(ConfigMixin):
        ...
        ...     config_required = ('bar', 'spam')
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        ...
        ...     def __init__(self, settings=None):
        ...         self.config = self.get_config_section(settings)
        ...
        >>> example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     m = MyClass()
        ...
        >>> m._ConfigMixin__get_config_spec() == '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        True
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
        >>> m.is_config_spec_or_group_declared()
        True

    And two other examples -- a bit different -- with `config_group` +
    `config_required` + `config_spec`:

        >>> class MyClass(ConfigMixin):
        ...     config_group = 'other'
        ...     config_required = ('bar', 'ham')
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...
        ...         [other]
        ...         bar = 43 :: float
        ...     '''
        ...
        >>> m = MyClass()
        >>> m._ConfigMixin__get_config_spec() == '''
        ... [foo]
        ... bar = 42 :: int
        ... spam :: json
        ...
        ... [other]
        ... bar = 43 :: float
        ... ham
        ... '''
        True
        >>> example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...
        ...     config_full = m.get_config_full()
        ...
        ...     # although there is more than one section it is still
        ...     # clear which one we want -- because of `config_group`:
        ...     config_section = m.get_config_section()
        ...
        >>> isinstance(config_full, Config)
        True
        >>> isinstance(config_section, ConfigSection)
        True
        >>> config_section == config_full['other']
        True
        >>> sorted(config_full.keys())
        ['foo', 'other']
        >>> (isinstance(config_full['foo'], ConfigSection) and
        ...  isinstance(config_full['other'], ConfigSection))
        True
        >>> config_full['foo'].sect_name
        'foo'
        >>> sorted(config_full['foo'].keys())
        ['bar', 'spam']
        >>> config_full['foo']['bar']
        42
        >>> config_full['foo']['spam']
        [None]
        >>> config_full['other'].sect_name
        'other'
        >>> sorted(config_full['other'].keys())
        ['bar', 'ham']
        >>> config_full['other']['bar']
        43.0
        >>> config_full['other']['ham']
        'Abc'
        >>> m.is_config_spec_or_group_declared()
        True

        >>> class MyClass2(ConfigMixin):
        ...     config_group = 'other'
        ...     config_required = ('bar', 'ham')
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        ...     # NOTE: here we specify `default_converter` as a callable
        ...     # so we decorate it with staticmethod() to avoid treating
        ...     # it as MyClass2 method
        ...     default_converter = staticmethod(str.upper)
        ...
        >>> m = MyClass2()
        >>> m._ConfigMixin__get_config_spec() == '''
        ... [foo]
        ... bar = 42 :: int
        ... spam :: json
        ...
        ... [other]
        ... bar
        ... ham
        ... ...
        ...
        ... '''
        True
        >>> example_conf_from_files = {'foo': {'spam': '[null]'},
        ...                            'other': {'ham': 'Abc', 'bar': 'bbb'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...
        ...     config_full = m.get_config_full()
        ...
        ...     # although there is more than one section it is still
        ...     # clear which one we want -- because of `config_group`:
        ...     config_section = m.get_config_section()
        ...
        >>> isinstance(config_full, Config)
        True
        >>> isinstance(config_section, ConfigSection)
        True
        >>> config_section == config_full['other']
        True
        >>> sorted(config_full.keys())
        ['foo', 'other']
        >>> (isinstance(config_full['foo'], ConfigSection) and
        ...  isinstance(config_full['other'], ConfigSection))
        True
        >>> config_full['foo'].sect_name
        'foo'
        >>> sorted(config_full['foo'].keys())
        ['bar', 'spam']
        >>> config_full['foo']['bar']
        42
        >>> config_full['foo']['spam']
        [None]
        >>> config_full['other'].sect_name
        'other'
        >>> sorted(config_full['other'].keys())
        ['bar', 'ham']
        >>> config_full['other']['bar']  # (note: the str.upper() applied)
        'BBB'
        >>> config_full['other']['ham']  # (note: the str.upper() applied)
        'ABC'
        >>> m.is_config_spec_or_group_declared()
        True

    Yet two other examples -- with `config_group` + `config_spec` (but,
    this time, without `config_required`):

        >>> class MyClass(ConfigMixin):
        ...     config_group = 'foo'
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        >>> m = MyClass()
        >>> m._ConfigMixin__get_config_spec() == '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        True
        >>> example_conf_from_files = {'foo': {'spam': '[null]'}}
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     config_full = m.get_config_full()
        ...     config_section = m.get_config_section()
        ...
        >>> isinstance(config_full, Config)
        True
        >>> isinstance(config_section, ConfigSection)
        True
        >>> config_full.keys()
        ['foo']
        >>> config_section == config_full['foo']
        True
        >>> sorted(config_section.keys())
        ['bar', 'spam']
        >>> config_section['bar']
        42
        >>> config_section['spam']
        [None]
        >>> m.is_config_spec_or_group_declared()
        True

        >>> class MyClass2(ConfigMixin):
        ...     config_group = 'other'
        ...     config_spec = '''
        ...         [foo]
        ...         bar = 42 :: int
        ...         spam :: json
        ...     '''
        >>> m = MyClass2()
        >>> m._ConfigMixin__get_config_spec() == '''
        ... [foo]
        ... bar = 42 :: int
        ... spam :: json
        ...
        ... [other]
        ... ...
        ...
        ... '''
        True
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     config_full = m.get_config_full()
        ...     config_section = m.get_config_section()
        ...
        >>> isinstance(config_full, Config)
        True
        >>> isinstance(config_section, ConfigSection)
        True
        >>> config_full.keys()
        ['foo', 'other']
        >>> config_full['foo']['bar']
        42
        >>> config_full['foo']['spam']
        [None]
        >>> config_section == config_full['other']
        True
        >>> config_section.keys()
        []
        >>> m.is_config_spec_or_group_declared()
        True


    There are also some basic conditions which must be satisfied or an
    exception will be raised...

    TypeError if `config_spec` is not a str instance:

        >>> class MyClass(ConfigMixin):
        ...     config_spec = u'not an str!!!'
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: config_spec must be str, not unicode
        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        TypeError: config_spec must be str, not unicode
        >>> m.is_config_spec_or_group_declared()
        True

    ValueError if `config_spec` is present when get_config_section() or
    get_config_full() is called with *additional format keyword
    arguments*:

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
        >>> m.is_config_spec_or_group_declared()
        True

    ValueError if `config_spec_pattern` is present when
    get_config_section() or get_config_full() is called *without*
    additional format keyword arguments:

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
        >>> m.is_config_spec_or_group_declared()
        True

    ConfigError if `config_required` is specified and `config_group` is
    not and it cannot be inferred automagically from `config_spec`
    (because there is no section or there is more than one section):

        >>> class MyClass(ConfigMixin):
        ...     config_required = ('a', 'b')
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ConfigError: ... `config_group` ... cannot be inferred ...
        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ConfigError: ... `config_group` ... cannot be inferred ...
        >>> m.is_config_spec_or_group_declared()  # note the result here!
        False

        >>> class MyClass(ConfigMixin):
        ...     config_required = ('a', 'b')
        ...     config_spec = '''; note that there are two sections
        ...         [foo]
        ...         a = XYZ
        ...         b = 43 :: int
        ...         [bar]
        ...         j = null :: json
        ...     '''
        ...
        >>> m = MyClass()
        >>> m.get_config_full()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ConfigError: ... `config_group` ... cannot be inferred ...
        >>> m.get_config_section()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ConfigError: ... `config_group` ... cannot be inferred ...
        >>> m.is_config_spec_or_group_declared()
        True

    Note that if neither `config_spec` nor `config_spec_pattern`, nor
    `config_group`, nor `config_required` is specified -- normal rules
    apply, that is:

    * get_config_section() must fail because there is no possibility to
      infer the section name;

    * get_config_full() succeeds but the obtained Config is empty.

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
        ConfigError: ...but no sections found
        >>> m.get_config_section(example_settings)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ConfigError: ...but no sections found
        >>> with patch.object(Config, '_load_n6_config_files',
        ...                   return_value=example_conf_from_files):
        ...     config_full = m.get_config_full()
        ...
        >>> config_full
        Config(<{}>)
        >>> m.get_config_full(example_settings)
        Config(<{}>)
        >>> m.is_config_spec_or_group_declared()  # note the result here
        False

    Of course, ConfigError -- as well as TypeError or KeyError -- will
    occur in all cases when the Config stuff raises them (see the
    Config docstring for details).
    """


    def get_config_full(self, settings=None, **format_kwargs):
        """
        Get a Config containing stuff from files or from `settings`.

        Args/kwargs:
            `settings` (optional; default: None):
                If not None it should be a dict containing Pyramid-like
                settings.

        Arbitrary optional kwargs:
            Keyword arguments to be used to format config spec from the
            `config_spec_pattern` attribute.  If they are not given
            `config_spec` attribute will be used instead.

        Raises:
            ConfigError, TypeError, ValueError, KeyError (see the
            docstring of this class).

        The method makes use of the following attributes:

        * `config_spec` (empty by default) or `config_spec_pattern`;
        * optional (modern): `custom_converters`, `default_converter`;
        * optional (legacy): `config_group`, `config_required`.

        (See the docstring of this class for details.)

        """
        args, kwargs = self.__get_args_kwargs(settings, **format_kwargs)
        return Config(*args, **kwargs)


    def get_config_section(self, settings=None, **format_kwargs):
        """
        Get a ConfigSection containing stuff from files or from `settings`.

        Args/kwargs:
            `settings` (optional; default: None):
                If not None it should be a dict containing Pyramid-like
                settings.

        Arbitrary optional kwargs:
            Keyword arguments to be used to format config spec from the
            `config_spec_pattern` attribute.  If they are not given
            `config_spec` attribute will be used instead.

        Raises:
            ConfigError, TypeError, ValueError, KeyError (see the
            docstring of this class).

        The method makes use of the following attributes:

        * `config_spec` (empty by default) or `config_spec_pattern`;
        * optional (modern): `custom_converters`, `default_converter`;
        * optional (legacy): `config_group`, `config_required`.

        (See the docstring of this class for details.)

        NOTE: this method (unlike get_config_full()) can be called
        *only* if it is clear which is *the* section, i.e., if
        `config_spec` contains exactly one section, or if `config_group`
        is specified.

        Typically you are interested in one section only -- so in most
        cases this method will probably be more handy than
        get_config_full().
        """
        args, kwargs = self.__get_args_kwargs(settings, **format_kwargs)
        config_group = self.__get_config_group()
        if config_group is None:
            config_section = Config.section(*args, **kwargs)
        else:
            full_config = Config(*args, **kwargs)
            config_section = full_config[config_group]
        return config_section


    def is_config_spec_or_group_declared(self):
        """
        Check whether a minimum configuration-related stuff is declared
        explicitly.

        Returns:
            True -- if *any* of the following attributes is present and
            set to some non-None value:

            * `config_spec`,
            * `config_spec_pattern`,
            * `config_group`;

            False -- otherwise.  Note that in such a case a call to the
            get_config_section() method must always fail (raising an
            exception) but a call to get_config_full() may succeed
            (though returning an empty Config instance).
        """
        return (getattr(self, 'config_spec', None) is not None or
                getattr(self, 'config_spec_pattern', None) is not None or
                self.__get_config_group() is not None)


    make_list_converter = staticmethod(Config.make_list_converter)


    def __get_args_kwargs(self, settings, **format_kwargs):
        config_spec = self.__get_config_spec(**format_kwargs)
        return (config_spec,), dict(
            settings=settings,
            custom_converters=self.__get_custom_converters(),
            default_converter=self.__get_default_converter())


    def __get_config_spec(self, **format_kwargs):
        if format_kwargs:
            if getattr(self, 'config_spec', None) is not None:
                raise ValueError(
                    'when config spec format kwargs are specified '
                    'the `config_spec_pattern` attribute is expected '
                    '(to be non-None) rather than `config_spec`')
            config_spec_pattern = getattr(self, 'config_spec_pattern', '') or ''
            config_spec = config_spec_pattern.format(**format_kwargs)
        else:
            if getattr(self, 'config_spec_pattern', None) is not None:
                raise ValueError(
                    'when *no* config spec format kwargs are specified '
                    'the `config_spec` attribute is expected '
                    '(to be non-None) rather than `config_spec_pattern`')
            config_spec = getattr(self, 'config_spec', '') or ''
        if not isinstance(config_spec, str):
            raise TypeError('config_spec must be str, not {0}'.format(
                get_class_name(config_spec)))
        config_spec = self.__enrich_config_spec_with_legacy_stuff(config_spec)
        return config_spec


    def __get_custom_converters(self):
        return getattr(self, 'custom_converters', None)


    def __get_default_converter(self):
        return getattr(self, 'default_converter', str)


    def __enrich_config_spec_with_legacy_stuff(self, config_spec):
        config_group = self.__get_config_group()
        config_required = self.__get_config_required()
        assert all(isinstance(opt_name, str) for opt_name in config_required)
        if config_group is not None or config_required:
            conf_spec_data = parse_config_spec(config_spec)
            sect_name_to_spec = self.__get_sect_name_to_spec(conf_spec_data)
            if config_group is None:
                assert config_required
                try:
                    [(config_group, sect_spec)] = sect_name_to_spec.iteritems()
                except ValueError:
                    all_sections = sorted(sect_name_to_spec)
                    sections_descr = (
                        'the following sections found: {0}'.format(
                            ', '.join(map(repr, map(ascii_str, all_sections))))
                        if all_sections else 'no sections found')
                    raise ConfigError(
                        'attribute `config_required` is specified but '
                        '`config_group` is not and it cannot be inferred '
                        'from `config_spec` because it does not contain '
                        'exactly one section ({0})'.format(sections_descr))
            else:
                sect_spec = sect_name_to_spec.get(config_group)
            assert isinstance(config_group, str)
            if sect_spec is None:
                sect_spec = _SectSpec(
                    name=config_group,
                    opt_specs=[
                        _OptSpec(name=str(opt_name),
                                 default=None,
                                 converter_spec=None)
                        for opt_name in config_required],
                    free_opts_allowed=True,
                    free_opts_converter_spec=None)
                config_spec = '{0}\n{1}'.format(
                    reduce_indent(config_spec),
                    sect_spec)
            else:
                assert conf_spec_data.contains(config_group)
                assert isinstance(sect_spec, _SectSpec)
                additional_required_opts = sorted(
                    set(config_required).difference(
                            opt.name
                            for opt in sect_spec.opt_specs),
                    key=config_required.index)
                if additional_required_opts:
                    sect_spec = sect_spec._replace(
                        opt_specs=sect_spec.opt_specs + [
                            _OptSpec(name=str(opt_name),
                                     default=None,
                                     converter_spec=None)
                            for opt_name in additional_required_opts])
                    config_spec = str(conf_spec_data.substitute(
                        config_group,
                        str(sect_spec)))
            assert type(config_spec) is str
            assert isinstance(sect_spec, _SectSpec)
            assert all(isinstance(opt.name, str) for opt in sect_spec.opt_specs)
            assert sect_spec.name == config_group
            assert config_group in (
                self.__get_sect_name_to_spec(parse_config_spec(config_spec)))
            assert set(config_required).issubset(opt.name for opt in sect_spec.opt_specs)
        return config_spec


    def __get_config_group(self):
        config_group = getattr(self, 'config_group', None)
        if config_group is not None:
            config_group = str(config_group)
        return config_group


    def __get_config_required(self):
        config_required = getattr(self, 'config_required', ()) or ()
        if isinstance(config_required, basestring):
            config_required = (str(config_required),)
        return tuple(map(str, config_required))


    @staticmethod
    def __get_sect_name_to_spec(conf_spec_data):
        all_sect_specs = conf_spec_data.get_all_sect_specs()
        return dict((spec.name, spec) for spec in all_sect_specs)



def parse_config_spec(config_spec):
    r"""
    Translate a config spec string to an object that is easier to manipulate.

    Args:
        `config_spec` (str): the config spec string.

    Returns:
        An object that provides an interface similar to the interface
        provided by the ConfigString class -- but fitted to manipulate
        a config spec; especially a few additional methods have been
        added (see the examples below).

    >>> parsed = parse_config_spec('''
    ...     [first]
    ...     foo = 42 :: int  ; comment
    ...     bar = 43         ; comment
    ...     ham::unicode
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
    >>> opt_spec_foo == ('foo', '42', 'int')
    True
    >>> isinstance(opt_spec_foo, tuple) and type(opt_spec_foo) is not tuple
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
    >>> opt_spec_bar1.converter_spec is None
    True
    >>> opt_spec_bar1 == ('bar', '43', None)
    True

    >>> opt_spec_bar2 = parsed.get_opt_spec('second.bar')
    >>> opt_spec_bar2.name
    'bar'
    >>> opt_spec_bar2.default is None
    True
    >>> opt_spec_bar2.converter_spec
    'url'
    >>> opt_spec_bar2 == ('bar', None, 'url')
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
    ...     ('foo', '42', 'int'),
    ...     ('bar', '43', None),
    ...     ('ham', None, 'unicode'),
    ...     ('spam', None, None),
    ...     ('glam', None, None),
    ... ]
    True
    >>> sect_spec_first.free_opts_allowed   # the `...` marker is present
    True
    >>> sect_spec_first.free_opts_converter_spec is None
    True
    >>> sect_spec_first == (
    ...     'first',
    ...     [
    ...         parsed.get_opt_spec('first.foo'),
    ...         parsed.get_opt_spec('first.bar'),
    ...         parsed.get_opt_spec('first.ham'),
    ...         parsed.get_opt_spec('first.spam'),
    ...         parsed.get_opt_spec('first.glam'),
    ...     ],
    ...     True,
    ...     None,
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

    The parse_config_spec() function automatically *reduces
    indentation* (note the difference against the ConfigString constructor!)
    -- that's why the config spec in the following example is
    perfectly synonymous to the one defined earlier:

    >>> parsed == parse_config_spec('''
    ... [first]
    ... foo = 42 :: int  ; comment
    ... bar = 43         ; comment
    ... ham::unicode
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

    >>> yet_another_parsed = parse_config_spec('''x = y
    ...       z
    ...     [foo]
    ... \t
    ...     bar =
    ...         spam
    ...     baz = ham
    ...     \t''')
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

    Some typical error conditions related to ill-formed config specs
    are presented below:

    >>> parse_config_spec('''
    ...     [first]
    ...     a = AAA
    ...     [second]
    ...     z = ZZZ
    ...     [first]
    ...     b = BBB
    ...     c = CCC
    ... ''')                                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> parse_config_spec('''
    ...     [first]
    ...     a = AAA
    ...     b = BBB
    ...     a = AAA
    ... ''')                                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'

    >>> parse_config_spec('wrong opt :: some_conv')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt :: some_conv' is not valid ...

    >>> parse_config_spec('some_opt :: wrong-conv')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'some_opt :: wrong-conv' is not valid ...

    >>> parse_config_spec('\n   xyz\n  abc\n\n')     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... ' xyz' looks like a continuation line...

    As it was said, the methods analogous to those provided by
    ConfigString are also provided; the code below includes a few
    examples...

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
    ...   ham::unicode
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
    >>> sect_spec.free_opts_converter_spec is None
    True
    >>> sect_spec == (
    ...     '',
    ...     [opt_spec_foo],
    ...     False,
    ...     None,
    ... )
    True
    >>> sect_spec.required    # all included opts have default values defined
    False

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
    ...      ham::unicode
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
    # for more doctests related to the class of objects returned by
    # this function -- including some peculiar/corner cases -- see the
    # docstring of the _ConfSpecData class
    return _ConfSpecData(reduce_indent(config_spec))



#
# 2. Other/alternative solutions
#

class ConfigString(str):

    r"""
    A `str` subclass providing handy ways of raw-string config manipulation.

    A subclass of `str` that provides several additional methods to
    operate on .ini-formatted configurations -- including getting,
    adding, removing and substitution of configuration sections and
    options (preserving formatting and comments related to
    sections/options that are not touched).

    Note #1: This class uses the *universal newlines* approach to
    splitting lines originating from an input string; on the other hand,
    all resultant contents contain '\n'-only (Unix-style) newlines.

    Note #2: In contrast to other (ConfigParser-related) classes in
    this module, this class does not accept duplicate section names or
    duplicate option names (in a particular section).

    Note #3: In contrast to other (ConfigParser-related) classes in
    this module, this class (as it is in the case of, e.g., the OpenSSL
    configuration format) ignores whitespace characters between a
    section name and the enclosing square brackets.

    Compatibility note: For the sake of the syntax change described
    above in the note #3, as well as for simplicity of the
    implementation, whitespace characters (accepted, in some cases, by
    stdlib's ConfigParser) are *never* recognized as a part of a section
    name or an option name.  Some other marginal incompatibilities with
    ConfigParser stuff are also possible.

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

    >>> cs.get('somesect')                              # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get('somesect.someopt')                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get('first.someopt')                         # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'someopt'

    >>> cs.insert_above('somesect', 'x = y\na = b')     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.get_opt_value('somesect.someopt')            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'somesect'

    >>> cs.remove('first.someopt')                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    KeyError: 'someopt'

    >>> cs.get_opt_value('first')                       # doctest: +ELLIPSIS
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
    ... REM comment
    ...
    ...   example.com/; not-a-comment\t
    ...
    ... [fifth]
    ... SomeOption   :   A Value   ;   A Comment
    ... no_value_option \t
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

    >>> cs2.get_opt_value('fifth.someoption')
    'A Value'

    >>> cs2.get_opt_value('fifth.no_value_option') is None
    True
    >>> cs2.get('fifth.no_value_option') == ConfigString(
    ...     'no_value_option \t\n'
    ...     '  for no-value options\n'
    ...     '  comments are forbidden\n'
    ...     '  and continuation lines are ignored \t\n')
    True

    >>> cs2.get_all_sect_names()
    ['', 'second', 'fifth']

    >>> cs2.get_all_sect_and_opt_names() == [
    ...     ('', ['bar', 'empty', 'empty2']),
    ...     ('second', ['bar']),
    ...     ('fifth', [
    ...         'someoption',
    ...         'no_value_option',
    ...         'foo',
    ...     ]),
    ... ]
    True


    >>> ConfigString()
    ConfigString()

    >>> ConfigString('')
    ConfigString()

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

    >>> ConfigString('xyz\nabc\n\n').get_all_sect_names()
    ['']

    >>> ConfigString('xyz\nabc\n\n').get_all_sect_and_opt_names()
    [('', ['xyz', 'abc'])]


    The constructor can raise ValueError when the given string cannot be
    parsed, e.g.:

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
    ... ''')                                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> ConfigString('''
    ... [first]
    ... a = AAA
    ... b = BBB
    ... a = AAA
    ... ''')                                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'
    """


    def __new__(cls, *args, **kwargs):
        s = str(*args, **kwargs)
        lines = cls._get_lines(s)
        sect_name_to_index_data = cls._get_sect_name_to_index_data(lines)
        self = super(ConfigString, cls).__new__(cls, '\n'.join(lines))
        self._lines = lines
        self._sect_name_to_index_data = sect_name_to_index_data
        return self


    #
    # Public interface extensions

    def __repr__(self):
        return '{0}({1})'.format(
            self.__class__.__name__,
            (super(ConfigString, self).__repr__() if self else ''))


    def contains(self, location):
        """
        Check whether the specified section or option exists.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            True if the specified `location` points to an existing
            section or option; otherwise False.
        """
        try:
            self._location_to_span(location)
        except KeyError:
            return False
        return True


    def get(self, location):
        """
        Get the contents of the specified `location`.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            A new instance of this class -- containing:
            * if `location` specifies a section: the text of the section.
            * if `location` specifies an option: the text of the option.

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._from_lines(self._lines[beg:end])


    def insert_above(self, location, text):
        """
        Get the whole contents with `text` inserted above `location`.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (str):
                The text to be inserted.

        Returns:
            A new instance of this class (with additional contents
            inserted as described above).

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.
        """
        beg, _ = self._location_to_span(location)
        return self._get_new_combined(beg, text, beg)


    def insert_below(self, location, text):
        """
        Get the whole contents with `text` inserted below `location`.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (str):
                The text to be inserted.

        Returns:
            A new instance of this class (with additional contents
            inserted as described above).

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.
        """
        _, end = self._location_to_span(location)
        return self._get_new_combined(end, text, end)


    def substitute(self, location, text):
        """
        Get the whole contents with the `location`-specified fragment
        replaced with `text`.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).
            `text` (str):
                The text to be inserted in place of the fragment
                specified with `location`.

        Returns:
            A new instance of this class (with some contents replaced
            as described above).

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._get_new_combined(beg, text, end)


    def remove(self, location):
        """
        Get the whole contents with the `location`-specified fragment
        removed.

        Args:
            `location` (str):
                Either a section name (specifying a particular
                section) or a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            A new instance of this class (with some contents removed
            as described above).

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.
        """
        beg, end = self._location_to_span(location)
        return self._get_new_combined(beg, '', end)


    def get_opt_value(self, location_with_opt_name):
        """
        Get the value of the option specified with `location`.

        Args:
            `location_with_opt_name` (str):
                It must be a string in the format: "section.option"
                (specifying a particular option in a particular
                section).

        Returns:
            An ordinary str being the value of the specified option or
            None (the latter if the option is a non-value one).

        Raises:
            KeyError --
            * instantiated with the section name as the sole argument --
              if the specified section does not exist;
            * instantiated with the option name as the sole argument --
              if the specified option does not exist in the specified
              (and existing) section.

            ValueError -- if the specified location does not include an
            option name.
        """
        opt_value, _ = self._get_opt_value_and_match(location_with_opt_name)
        return opt_value


    def get_all_sect_names(self):
        """
        Get a list of all section names.

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
        Get a list of (<section name>, <list of option names>) pairs.

        Important: the '' (empty) section name -- referring to the area
        of the config above any section header -- is included only if
        that area contains any options.

        The order of section names and of option names (within each
        list) is the order of appearance in the config.
        """
        return [
            (sname, self._sect_name_to_index_data[sname].get_all_opt_names())
            for sname in self.get_all_sect_names()]


    #
    # Non-public constants and helpers

    _COMMENTED_OR_BLANK_LINE_REGEX = re.compile(r'''
        \A
        (?:
            [;\#]
        |
            [rR]
            [eE]
            [mM]
            (?:
                \s
            |
                \Z
            )
        |
            \s*
            \Z
        )
    ''', re.VERBOSE)

    _SECT_BEG_REGEX = re.compile(r'''
        \A
        \[
        \s*
        (?P<sect_name>
            [^\]\s]+
        )
        \s*
        \]
    ''', re.VERBOSE)

    _OPT_BEG_REGEX = re.compile(r'''
        \A
        (?P<opt_name>
            [^:=\s\]]
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
    ''', re.VERBOSE)


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
                raise RuntimeError("{0!r} not completed".format(self))
            return self._beg, self._end

        def get_opt_span(self, opt_name):
            if not self._is_opt_completed(opt_name):
                raise RuntimeError("{0!r}.{1!r} not completed".format(self, opt_name))
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
        lines = s.splitlines()
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
                        'first non-blank config line {0!r} '
                        'looks like a continuation line '
                        '(that is, starts with whitespace '
                        'characters)'.format(li))
                continue
            non_blank_or_comment_encountered = True

            sect_match = cls._SECT_BEG_REGEX.search(li)
            if sect_match:
                # this line is a new section header
                sect_name_to_index_data[cur_sect_name].complete(end=i)
                cur_sect_name = sect_match.group('sect_name')
                if cur_sect_name in sect_name_to_index_data:
                    raise ValueError(
                        'duplicate section name {0!r}'.format(cur_sect_name))
                sect_name_to_index_data[cur_sect_name] = cls._SectIndexData(beg=i)

            else:
                opt_match = cls._OPT_BEG_REGEX.search(li)
                if opt_match:
                    # this line is an option spec (e.g., `name=value`...)
                    opt_name = opt_match.group('opt_name')
                    opt_name = opt_name.lower()  # <- to mimic ConfigParser stuff
                    sect_idata = sect_name_to_index_data[cur_sect_name]
                    if sect_idata.contains_opt_name(opt_name):
                        raise ValueError(
                            'duplicate option name {0!r} in section {1!r}'
                            .format(opt_name, cur_sect_name))
                    sect_idata.init_opt(opt_name, beg=i)

                else:
                    raise ValueError(
                        'config line {0!r} is not valid (note that '
                        'section/option names that are empty or '
                        'contain whitespace characters are '
                        'not supported)'.format(li))

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
            opt_name = opt_name.lower()  # <- to mimic ConfigParser stuff
            span = sect_idata.get_opt_span(opt_name)
        elif opt_required:
            raise ValueError(
                'the called method requires that the location argument '
                'specifies an option name (got: {0!r})'.format(location))
        else:
            span = sect_idata.get_span()
        return span


    def _get_new_combined(self, preserve_to, insert_this, preserve_from):
        lines_to_insert = insert_this.splitlines()
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
            # Apparently, it's a `no-value option`.  If it has some
            # continuation lines after it they will be just ignored here
            # (for ConfigString) -- because ConfigParser classes raise
            # AttributeError in such a case (it's obviously a bug in
            # ConfigParser).
            #
            # ConfigParser classes have also another bug: `no-value`
            # options have their inline comments appended to their
            # names.  That's why, for ConfigString, `no-value options`
            # with inline comments are just forbidden (cannot be parsed
            # so they get the ConfigString constructor to raise
            # ValueError).
            return None, opt_match

        # Note that we try to mimic the (somewhat buggy) behaviour of
        # ConfigParser classes (that's why here, for example, we strip
        # the first line and only then append continuation lines...).
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



#
# Auxiliary constants and classes
#

_N6CORE_CONFIG_ERROR_MSG_PATTERN = """

{0}.

Make sure that config files for n6 are present in '/etc/n6' or '~/.n6'
and that they are valid (especially, that they contain all needed
entries).

Note: you may want to execute the `n6config` script to install default
configuration files.

"""


class _SectSpec(collections.namedtuple(
        '_SectSpec', [
            'name',               # the section name (str)
            'opt_specs',          # a list of _OptSpec instances
            'free_opts_allowed',  # whether free (not specified) opts are allowed (bool)
            'free_opts_converter_spec',  # the name of the value converter
        ])):                             # for any free opts (str) or None

    r"""
    >>> s = _SectSpec('',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    'foo\nbar = x :: y\n\n'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '[some]\nfoo\nbar = x :: y\n\n'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, 'bb'), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '[some]\nfoo :: bb\nbar = x :: y\n\n'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [],
    ...               free_opts_allowed=False,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '[some]\n\n'
    >>> s.required
    False

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec=None)
    >>> str(s)
    '[some]\nfoo\nbar = x :: y\n...\n\n'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', None, None), _OptSpec('bar', 'x', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec='z')
    >>> str(s)
    '[some]\nfoo\nbar = x :: y\n... :: z\n\n'
    >>> s.required
    True

    >>> s = _SectSpec('some',
    ...               [_OptSpec('foo', 'A', None), _OptSpec('b', 'x\ny', 'y')],
    ...               free_opts_allowed=True,
    ...               free_opts_converter_spec='z')
    >>> str(s)
    '[some]\nfoo = A\nb = x\n  y :: y\n... :: z\n\n'
    >>> s.required
    False
    """

    @property
    def required(self):
        "Whether the section is obligatory (True or False)."
        return any(opt.default is None for opt in self.opt_specs)

    def __str__(self):
        s = ('[{0}]\n'.format(self.name) if self.name else '')
        if self.opt_specs:
            s += '\n'.join(map(str, self.opt_specs))
            s += '\n'
        if self.free_opts_allowed:
            s += '...'
            if self.free_opts_converter_spec is not None:
                s += ' :: {0}'.format(self.free_opts_converter_spec)
            s += '\n'
        s += '\n'
        return s


class _OptSpec(collections.namedtuple(
        '_OptSpec', [
            'name',               # the option name (str)
            'default',            # the default value (str) or None
            'converter_spec',     # the name of the value converter (str) or None
        ])):

    r"""
    >>> str(_OptSpec('foo', None, None))
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
    """

    def __str__(self):
        s = self.name
        if self.default is not None:
            default = '\n  '.join(filter(None, map(str.strip, self.default.splitlines())))
            s += ' = {0}'.format(default or '""')
        if self.converter_spec is not None:
            s += ' :: {0}'.format(self.converter_spec)
        return s


class _ConfSpecData(ConfigString):

    r"""
    A helper class to deal with config specs (parsing them and
    providing an interface to manipulate their data).

    This class should not be instantiated directly beyond this
    module -- the parse_config_spec() public helper function (which,
    additionally, automatically reduces indentation...) should be
    used instead.

    Note that this class is a subclass of ConfigString (with some
    methods adjusted and additional methods provided).

    >>> cs = _ConfSpecData('''
    ... [ first ]
    ... foo = 42 :: int ; comment
    ... bar = 43 ; comment
    ... baz = 44 :: int
    ... spam = 45
    ...
    ... ham::unicode
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
    ...   'baz = 44 :: int\nspam = 45\n\nham::unicode\nslam\nglam ;comment\n\n'
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
    _OptSpec(name='bar', default='43', converter_spec=None)

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
    _OptSpec(name='spam', default='45', converter_spec=None)

    >>> cs.get('first.Ham')
    _ConfSpecData('ham::unicode')
    >>> cs.get_opt_value('first.HAM') is None
    True
    >>> cs.get_opt_spec('first.HAM')
    _OptSpec(name='ham', default=None, converter_spec='unicode')

    >>> cs.get('first.SLAM')
    _ConfSpecData('slam')
    >>> cs.get_opt_value('first.Slam') is None
    True
    >>> cs.get_opt_spec('first.Slam')
    _OptSpec(name='slam', default=None, converter_spec=None)

    >>> cs.get('first.glam')                   # doctest: +ELLIPSIS
    _ConfSpecData('glam ;comment\n\n# the `...
    >>> cs.get_opt_value('first.glam') is None
    True
    >>> cs.get_opt_spec('first.glam')
    _OptSpec(name='glam', default=None, converter_spec=None)

    >>> cs.get('first....')
    _ConfSpecData('...\n\n')
    >>> cs.get_opt_value('first....') is None
    True
    >>> cs.get_opt_spec('first....')
    _OptSpec(name='...', default=None, converter_spec=None)

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
    ...         _OptSpec(name='bar', default='43', converter_spec=None),
    ...         _OptSpec(name='baz', default='44', converter_spec='int'),
    ...         _OptSpec(name='spam', default='45', converter_spec=None),
    ...         _OptSpec(name='ham', default=None, converter_spec='unicode'),
    ...         _OptSpec(name='slam', default=None, converter_spec=None),
    ...         _OptSpec(name='glam', default=None, converter_spec=None),
    ...     ],
    ...     free_opts_allowed=True,     # because the `...` marker is present
    ...     free_opts_converter_spec=None,
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
    ...     free_opts_converter_spec=None,
    ... )
    True
    >>> cs.get_sect_spec('second').required
    False
    >>> cs.get_all_sect_specs() == [
    ...   _SectSpec(
    ...     name='first',
    ...     opt_specs=[
    ...         _OptSpec(name='foo', default='42', converter_spec='int'),
    ...         _OptSpec(name='bar', default='43', converter_spec=None),
    ...         _OptSpec(name='baz', default='44', converter_spec='int'),
    ...         _OptSpec(name='spam', default='45', converter_spec=None),
    ...         _OptSpec(name='ham', default=None, converter_spec='unicode'),
    ...         _OptSpec(name='slam', default=None, converter_spec=None),
    ...         _OptSpec(name='glam', default=None, converter_spec=None),
    ...     ],
    ...     free_opts_allowed=True,     # because the `...` marker is present
    ...     free_opts_converter_spec=None,
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
    ...     free_opts_converter_spec=None,
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
    ... REM comment
    ...     zz
    ...   example.com/; not-a-comment\t :: int
    ...
    ... [another]
    ... # free options allowed:
    ... ...
    ...
    ... [fifth]
    ... SomeOption   :   A Value   ::   unicode   ;   A Comment
    ... ... :: unicode ; free options allowed + converter for them specified
    ... no_value_option :: int \t; inline comment \t; here allowed! \t
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

    >>> empty_options = ['empty{}'.format(i) for i in xrange(1, 55)]
    >>> all(cs2.get_opt_value('second.' + o) == ''
    ...     for o in empty_options)
    True
    >>> all(cs2.get_opt_spec('second.' + o) == _OptSpec(o, '', None)
    ...     for o in empty_options)
    True

    >>> empty_int_options = ['empty{}_i'.format(i) for i in xrange(1, 147)]
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

    >>> cs2.get_opt_value('fifth.someoption')
    'A Value'

    >>> cs2.get_opt_value('fifth.no_value_option') is None
    True
    >>> cs2.get('fifth.no_value_option') == (
    ...     'no_value_option :: int \t; inline comment \t; here allowed! \t\n'
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
    ...         'someoption',
    ...         '...',
    ...         'no_value_option',
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
    ...       + list(_OptSpec(name=o, default='', converter_spec=None)
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
    ...     free_opts_converter_spec=None,
    ... )
    True
    >>> cs2.get_sect_spec('second').required
    True
    >>> cs2.get_sect_spec('another') == _SectSpec(
    ...     name='another',
    ...     opt_specs=[],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec=None,
    ... )
    True
    >>> cs2.get_sect_spec('another').required
    False
    >>> cs2.get_sect_spec('fifth') == _SectSpec(
    ...     name='fifth',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='someoption',
    ...             default='A Value',
    ...             converter_spec='unicode',
    ...         ),
    ...         _OptSpec(
    ...             name='no_value_option',
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
    ...     free_opts_converter_spec='unicode',
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
    ...       + list(_OptSpec(name=o, default='', converter_spec=None)
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
    ...     free_opts_converter_spec=None,
    ...   ),
    ...   _SectSpec(
    ...     name='another',
    ...     opt_specs=[],
    ...     free_opts_allowed=True,
    ...     free_opts_converter_spec=None,
    ...   ),
    ...   _SectSpec(
    ...     name='fifth',
    ...     opt_specs=[
    ...         _OptSpec(
    ...             name='someoption',
    ...             default='A Value',
    ...             converter_spec='unicode',
    ...         ),
    ...         _OptSpec(
    ...             name='no_value_option',
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
    ...     free_opts_converter_spec='unicode',
    ...   ),
    ... ]
    True

    >>> _ConfSpecData('wrong opt :: some_conv')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'wrong opt :: some_conv' is not valid ...

    >>> _ConfSpecData('some_opt :: wrong-conv')  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: config line 'some_opt :: wrong-conv' is not valid ...

    >>> _ConfSpecData('  \n  xyz\n  abc\n\n')    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: first non-blank ... '  xyz' looks like a continuation line...

    >>> _ConfSpecData('  [xyz]\n  abc=3')        # doctest: +ELLIPSIS
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
    ... ''')                                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate section name 'first'

    >>> _ConfSpecData('''
    ... [first]
    ... a = AAA
    ... b = BBB
    ... a = AAA
    ... ''')                                     # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: duplicate option name 'a' in section 'first'
    """


    _OPT_BEG_REGEX = re.compile(r'''
        \A
        (?P<opt_name>
            [^:=\s\]]
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
                \w+     # converter spec for `no-value option`
            )
        )?
        \s*?
        (?P<inline_comment>  # note: here allowed also for `no-value option`
            \s
            ;
            .*
        )?
        \Z
    ''', re.VERBOSE)


    def get_opt_value(self, location_with_opt_name):
        value_with_optional_conv = super(_ConfSpecData, self).get_opt_value(location_with_opt_name)
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


    # split into: (<the actual opt value>, <the converter spec>)
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
        Get a _SectSpec instance for the given section name.

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
        Get a list of _SectSpec instances.

        They contain specifications of all sections and options that
        these sections contain -- except that:

        * `...` is not interpreted as an option name but as a "free
          options allowed" marker;

        * the '' section is included only if it contains any options
          and/or a "free options allowed" marker.

        The order of sections and options (within each _SectSpec
        instance) is the order of appearance in the config.
        """
        return [
            self.get_sect_spec(sect_name)
            for sect_name in self.get_all_sect_names()]



if __name__ == "__main__":
    import doctest
    doctest.testmod()

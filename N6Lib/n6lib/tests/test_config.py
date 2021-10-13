# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections
import configparser
import datetime
import io
import sys
import unittest
from unittest.mock import (
    DEFAULT,
    call,
    patch,
    sentinel as sen,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.common_helpers import (
    DictWithSomeHooks,
    reduce_indent,
    str_to_bool,
)
from n6lib.config import (
    ConfigError,
    NoConfigSectionError,
    ConfigSection,
    Config,
)
from n6lib.const import ETC_DIR
from n6lib.unit_test_helpers import TestCaseMixin



# NOTE: most important stuff of: ConfigError, NoConfigSectionError,
# NoConfigOptionError, ConfigSection and ConfigString, as well as
# Config.make() -- are already covered by their doctests



class _ConfigExampleDataAndMocksMixin(object):

    #
    # Various test data...

    # example config file paths and their contents
    CONFIG_FILE_PATH_TO_DEFAULT_CONTENT = collections.OrderedDict([
        # (in the order of reading and parsing)
        ('a/b/00_global.conf', reduce_indent('''
                [first]
                a = xyz
                bCD = 1 , 2 , 3
                efg : 42     ; some comment

                [THIRD]
                xx = Zażółć Gęślą Jaźń
                zz = {1: 2}
                QQ = ""
            ''')),
        ('a/b/xYZ.conf', reduce_indent('''
                [first]
                b = 1
                Bcd : 4 , 5 , 6
                # another comment
                [third]
                xx = note that section names are always case-sensitive
                [second\u015b]
                a = 3.2
                B = 4.2
                c = 5.2 ; yet another comment
            '''.strip())),
        ('/x/y/abc.conf', reduce_indent('''
                [first]
                hij = 43
                      44 \u015b \t
                      45

                klm.RST =
                    yes,
                   off,
                  False,\t
                   true,
                    0,\t

                [irrelevant]
                a = 123
                bb = cc

                [second\u015b]
                b : 44.2
                c : 45.2
                d : 46.2
            ''')),
    ])

    # example `settings` arg for modern variant of __init__() call
    # (Pyramid-like `settings` dict)
    DEFAULT_SETTINGS = {
                                           # below -- notes about particular example values:
        'aaa': 'qwerty',
        'first.a': 'xyz',
        'first.b': ' 1 ',
        'first.bcd': b'4 , 5 , 6',         # to be, at first, auto-coerced to str (+warning logged)
        'first.efg': 42.0,                 # to be, at first, auto-coerced to str (+warning logged)
        'first.hij': '43\n44 \u015b\n45',
        'first.klm.rst': ' 1,false, NO ,oN , FALSE',
        'second\u015b.a': '     3.2',
        'second\u015b.b': '    44.20',
        'second\u015b.c': '    45.200 ',
        'second\u015b.d': '000046.2000',
        'THIRD.xx': 'Zażółć Gęślą Jaźń'.encode('utf-8'),  # to be, at first, auto... (as above)
        'THIRD.zz': '{ 1 : 2 } ',
        'THIRD.qq': '',
        'third.xx': 'irrelevant because...',
        'third.yy': '...section names are always case-sensitive',
        'irrelevant opt': 'irrelevant value',
        'irrelevant.a': 123,               # to be, at first, auto-coerced to str (+warning logged)
        'irrelevant.bb': 'cc',
        42: 'to-be-skipped',   # non-str key -- to be just skipped (+warning logged)
    }

    # example `config_spec` arg for modern variant of __init__() call
    # (raw config specification -- just a str)
    DEFAULT_CONFIG_SPEC = '''
        [first]
        a
        b :: int
        bcd = 0 , 0 , 0 ; comment
        efg = 0 :: float
        hij :: str
        klm.rst :: list_of_bool
        N = 2016-02-25 23:24:25.1234 , 1410-07-15T12:01+02:00::list_of_datetime

        [second\u015b]
        ... :: float

        [THIRD]
        XX :: unicode
        YY = {"a": 42} :: json  ; another comment
        zz :: py
        ...

        [fourth]
        Zzz = ZZZ
        ... :: int

        [fifth]
        f = 42 :: int

        [sixth]
    '''

    # example `required` arg for legacy variant of __init__() call
    DEFAULT_LEGACY_REQUIRED = {
        'first': [
            'a',
            'b',
            'hij',
            'klm.rst',
        ],
        'THIRD': [
            'xx',
            'zz',
        ],
    }

    # Below: example expected contents of Config instances
    # (here as ordinary dicts -- for brevity), matching the
    # example input data defined above

    # example outcome of modern variant of __init__() call
    EXPECTED_CONFIG_BASE = {
        'first': {
            'a': 'xyz',
            'b': 1,
            'bcd': '4 , 5 , 6',
            'efg': 42.0,
            'hij': '43\n44 \u015b\n45',
            'klm.rst': [True, False, False, True, False],
            'n': [
                datetime.datetime(2016, 2, 25, 23, 24, 25, 123400),
                datetime.datetime(1410, 7, 15, 10, 1),
            ],
        },
        'second\u015b': {
            'a': 3.2,
            'b': 44.2,
            'c': 45.2,
            'd': 46.2,
        },
        'THIRD': {
            'xx': 'Zażółć Gęślą Jaźń',
            'yy': {'a': 42},
            'zz': {1: 2},
            'qq': '',
        },
        'fourth': {
            'zzz': 'ZZZ',
        },
        'fifth': {
            'f': 42,
        },
        'sixth': {},
    }

    # example outcome of legacy variant of __init__() call
    EXPECTED_LEGACY_INIT_CONFIG_BASE = {
        'first': {
            'a': 'xyz',
            'b': '1',
            'bcd': '4 , 5 , 6',
            'efg': '42',
            'hij': '43\n44 \u015b\n45',
            'klm.rst': '\nyes,\noff,\nFalse,\ntrue,\n0,',
        },
        'second\u015b': {
            'a': '3.2',
            'b': '44.2',
            'c': '45.2',
            'd': '46.2',
        },
        'THIRD': {
            'xx': 'Zażółć Gęślą Jaźń',
            'zz': '{1: 2}',
            'qq': '',
        },
        'third': {
            'xx': 'note that section names are always case-sensitive',
        },
        'irrelevant': {
            'a': '123',
            'bb': 'cc',
        },
    }

    # a pattern for the log message, that indicates absence
    # of a non-required section in the configuration
    PATTERN_FOR_ABSENT_NONREQUIRED_CONFIG_SECT_MESSAGE = (r'^Absent \*non-required\* '
                                                          r'config sections\b')
    # a pattern for the log message, that indicates the possibility
    # of a typo in a config option's name
    PATTERN_FOR_OPT_TYPO_VULNERABLE_SECT_NAMES = (r'\bsome free \(undeclared but '
                                                  r'allowed\) options are present\b')
    TESTED_LOGGER_LEVELS = frozenset(['warning', 'error', 'critical'])
    # a namedtuple to be used in tests as a container for
    # information about expected logged messages' components
    ExpectedLogInvocation = collections.namedtuple('ExpectedLogInvocation',
                                                   ['level', 'msg_regex', 'section_names'])

    #
    # Several test helpers

    def adjust_expected_open_calls(self, expected_open_calls):
        if expected_open_calls is DEFAULT:
            expected_open_calls = [
                call(path, encoding='utf-8')
                for path in self.CONFIG_FILE_PATH_TO_DEFAULT_CONTENT]
        return expected_open_calls

    def patch_file_ops(self, config_files_content):
        self._unmemoize__Config__load_n6_config_files()
        self._patch__os_walk()
        self._patch__configparser_open(config_files_content)
        self._patch__sys_stderr()

    #
    # Private helpers

    def _unmemoize__Config__load_n6_config_files(self):
        unmemoized = classmethod(Config._load_n6_config_files.__func__.func)
        patcher = patch.object(Config, '_load_n6_config_files', unmemoized)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch__os_walk(self):
        def side_effect(top, *args, **kwargs):
            # (see: CONFIG_FILE_PATH_TO_DEFAULT_CONTENT above)
            if top == ETC_DIR:
                yield 'a/b', sen.irrelevant, [
                    'xYZ.conf',          # to be *kept* (as 2nd) in Config._get_config_file_paths()
                    'foo_bar_baz.spam',  # to be skipped in Config._get_config_file_paths()
                    'logging.conf',      # to be skipped in Config._get_config_file_paths()
                ]
                yield 'a/b/', sen.irrelevant, [
                    'logging-01.conf',   # to be skipped in Config._get_config_file_paths()
                    '00_global.conf',    # to be *kept* (as 1st) in Config._get_config_file_paths()
                ]
            else:                                           # to be *kept* in
                yield '/x/y', sen.irrelevant, ['abc.conf']  # Config._get_config_file_paths()
        patcher = patch('os.walk', side_effect=side_effect)
        self.os_walk_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _patch__configparser_open(self, config_files_content):
        def side_effect(path, *args, **kwargs):
            assert path in self.CONFIG_FILE_PATH_TO_DEFAULT_CONTENT, 'bug in test'
            if config_files_content is DEFAULT:
                content = self.CONFIG_FILE_PATH_TO_DEFAULT_CONTENT[path]
            else:
                content = config_files_content
            return io.StringIO(content)
        patcher = patch('configparser.open', create=True, side_effect=side_effect)
        self.configparser_open_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _patch__sys_stderr(self):
        patcher = patch('sys.stderr')
        self.sys_stderr_mock = patcher.start()
        self.addCleanup(patcher.stop)



@expand
class TestConfig(_ConfigExampleDataAndMocksMixin,
                 TestCaseMixin,
                 unittest.TestCase):


    def test_basic_class_features(self):
        self.assertTrue(issubclass(Config, DictWithSomeHooks))
        self.assertTrue(issubclass(Config, dict))


    @foreach(
        param(
            item_converter=int,
            optional_kwargs={},
            expected_name='__int__list__converter',
            expected_delimiter=',',
            example_arg=' 42,  43  ,44\n, \t45,46,47 ',
            expected_result=[42, 43, 44, 45, 46, 47],
        ),
        param(
            item_converter=str_to_bool,
            optional_kwargs=dict(delimiter=';.;'),
            expected_name='__str_to_bool__list__converter',
            expected_delimiter=';.;',
            example_arg=' 0;.;  1  ;.;TRUE\n;.; \tfalse;.;Off;.;no ;.; ',
            expected_result=[False, True, True, False, False, False],
        ),
        param(
            item_converter=float,
            optional_kwargs=dict(name='my_custom_name', delimiter='\n'),
            expected_name='my_custom_name',
            expected_delimiter='\n',
            example_arg=' 42 \n 43  \n44\n \t45.2\n',
            expected_result=[42.0, 43.0, 44.0, 45.2],
        ),
        param(
            item_converter=bytearray,
            optional_kwargs={},
            expected_name='__bytearray__list__converter',
            expected_delimiter=',',
            example_arg=' ',
            expected_result=[],
        ),
    )
    def test__make_list_converter(self, item_converter, optional_kwargs,
                                  expected_name, expected_delimiter,
                                  example_arg, expected_result):
        converter = Config.make_list_converter(item_converter, **optional_kwargs)
        actual_result = converter(example_arg)
        self.assertEqualIncludingTypes(actual_result, expected_result)
        self.assertEqual(converter.__name__, expected_name)
        self.assertEqual(converter.delimiter, expected_delimiter)
        self.assertIs(converter.item_converter, item_converter)



    def test__BASIC_CONVERTERS__general_features(self):
        self.assertIsInstance(Config.BASIC_CONVERTERS, dict)
        self.assertEqualIncludingTypes(set(Config.BASIC_CONVERTERS), {
            'str', 'bytes', 'unicode',
            'bool', 'int', 'float',
            'date', 'datetime',
            'list_of_str', 'list_of_bytes', 'list_of_unicode',
            'list_of_bool', 'list_of_int', 'list_of_float',
            'list_of_date', 'list_of_datetime',
            'importable_dotted_name',
            'py', 'py_namespaces_dict',
            'json',
        })
        self.assertTrue(all(callable(v) for v in Config.BASIC_CONVERTERS.values()))


    @foreach(
        ('str', 'abc', 'abc'),
        ('str', '\u015b', '\u015b'),
        ('unicode', 'abc', 'abc'),
        ('bytes', 'abc', b'abc'),
        ('bytes', '\u015b', b'\xc5\x9b'),
        ('bool', 'Yes', True),
        ('int', '42', 42),
        ('float', '42', 42.0),
        ('date', '1410-07-15', datetime.date(1410, 7, 15)),
        ('datetime', '2016-02-29T23:24:25.1234+02:00',
            datetime.datetime(2016, 2, 29, 21, 24, 25, 123400)),
        ('py', b"{'\xc5\x9b': [False,]}", {'\u015b': [False]}),
        ('py', b"{'\\u015b': [False,]}", {'\u015b': [False]}),
        ('py', "{'\u015b': [False,]}", {'\u015b': [False]}),
        ('py', "{'\\u015b': [False,]}", {'\u015b': [False]}),
        ('json', '{"\\u015b": [false]}', {'\u015b': [False]}),
    )
    def test__BASIC_CONVERTERS__most_of_single_value_converters(self, name, arg, expected_result):
        converter = Config.BASIC_CONVERTERS[name]
        actual_result = converter(arg)
        self.assertEqualIncludingTypes(actual_result, expected_result)


    def test__BASIC_CONVERTERS__importable_dotted_name__of_module(self):
        converter = Config.BASIC_CONVERTERS['importable_dotted_name']
        dotted_name = 'n6lib.tests'
        actual_result = converter(dotted_name)
        import n6lib.tests
        expected_result = n6lib.tests
        self.assertIs(actual_result, expected_result)

    def test__BASIC_CONVERTERS__importable_dotted_name__of_non_module_obj(self):
        converter = Config.BASIC_CONVERTERS['importable_dotted_name']
        dotted_name = 'n6lib.tests._dummy_module_used_by_some_tests.DummyObj'
        actual_result = converter(dotted_name)
        from n6lib.tests._dummy_module_used_by_some_tests import DummyObj as expected_result
        self.assertIs(actual_result, expected_result)


    @foreach(
        ('str', 'abc , def ,ghi,jkl ', ['abc', 'def', 'ghi', 'jkl']),
        ('str', '', []),
        ('unicode', ' abc,def, ghi ,jkl', ['abc', 'def', 'ghi', 'jkl']),
        ('bytes', 'abc , def ,ghi,jkl ', [b'abc', b'def', b'ghi', b'jkl']),
        ('bool', ' Yes,no \t  , OFF', [True, False, False]),
        ('int', '42, 43', [42, 43]),
        ('int', ' \t , \t ', []),
        ('float', '42, 43', [42.0, 43.0]),
        ('date', ' 1410-07-15 , 2007-07-07 ', [
            datetime.date(1410, 7, 15),
            datetime.date(2007, 7, 7),
        ]),
        ('datetime', '2016-02-29T23:24:25.1234+02:00, 1410-07-15 16:15', [
            datetime.datetime(2016, 2, 29, 21, 24, 25, 123400),
            datetime.datetime(1410, 7, 15, 16, 15, 0),
        ]),
    )
    def test__BASIC_CONVERTERS__list_converters(self, base_name, arg, expected_result):
        name = 'list_of_' + base_name
        converter = Config.BASIC_CONVERTERS[name]
        actual_result = converter(arg)
        self.assertEqualIncludingTypes(actual_result, expected_result)
        self.assertEqual(converter.__name__, name)
        self.assertEqual(converter.delimiter, ',')
        self.assertIs(converter.item_converter, Config.BASIC_CONVERTERS[base_name])


    @paramseq
    def modern_init_case_params(cls):
        yield param(
                config_spec='',
                optional_kwargs=dict(),
                config_files_content='',
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(),
            ).label('empty spec, empty config, no kwargs')

        yield param(
                config_spec='',
                optional_kwargs=dict(
                    settings={},
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(),
            ).label('empty spec, empty settings, no other kwargs')

        yield param(
                config_spec='',
                optional_kwargs=dict(
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                    default_converter="| {0!a} |".format,
                ),
                config_files_content='',
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(),
            ).label('empty spec, empty config, some kwargs')

        yield param(
                config_spec='',
                optional_kwargs=dict(
                    settings={},
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                    default_converter="| {0!a} |".format,
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(),
            ).label('empty spec, empty settings, some other kwargs')

        yield param(
                config_spec='',
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(),
            ).label('empty spec, some config, no kwargs')

        yield param(
                config_spec='',
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(),
            ).label('empty spec, some settings, no other kwargs')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(cls.EXPECTED_CONFIG_BASE),
            ).label('config, no kwargs')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(cls.EXPECTED_CONFIG_BASE),
            ).label('settings, no other kwargs')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                ),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        'first': dict(
                            cls.EXPECTED_CONFIG_BASE['first'],
                            efg='-*- 42 -*-',
                        ),
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'],
                            a='-*- 3.2 -*-',
                            b='-*- 44.2 -*-',
                            c='-*- 45.2 -*-',
                            d='-*- 46.2 -*-',
                        ),
                    }
                ),
            ).label('config, kwargs: `custom_converters`')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        'first': dict(
                            cls.EXPECTED_CONFIG_BASE['first'],
                            efg='-*- 42.0 -*-',
                        ),
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'],
                            a='-*-      3.2 -*-',
                            b='-*-     44.20 -*-',
                            c='-*-     45.200  -*-',
                            d='-*- 000046.2000 -*-',
                        ),
                    }
                ),
            ).label('settings, other kwargs: `custom_converters`')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    default_converter="| {0!a} |".format,
                ),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE,
                    first=dict(
                        cls.EXPECTED_CONFIG_BASE['first'],
                        a="| 'xyz' |",
                        bcd="| '4 , 5 , 6' |",
                    ),
                    THIRD=dict(
                        cls.EXPECTED_CONFIG_BASE['THIRD'],
                        qq="| '' |",
                    ),
                    fourth=dict(
                        cls.EXPECTED_CONFIG_BASE['fourth'],
                        zzz="| 'ZZZ' |",
                    ),
                ),
            ).label('config, kwargs: `default_converter` [here: callable]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                    default_converter="list_of_unicode",
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE,
                    first=dict(
                        cls.EXPECTED_CONFIG_BASE['first'],
                        a=['xyz'],
                        bcd=['4', '5', '6'],
                    ),
                    THIRD=dict(
                        cls.EXPECTED_CONFIG_BASE['THIRD'],
                        qq=[],
                    ),
                    fourth=dict(
                        cls.EXPECTED_CONFIG_BASE['fourth'],
                        zzz=['ZZZ'],
                    ),
                ),
            ).label('settings, other kwargs: `default_converter` [here: str]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                    default_converter="| {0!a} |".format,
                ),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        'first': dict(
                            cls.EXPECTED_CONFIG_BASE['first'],
                            a="| 'xyz' |",
                            bcd="| '4 , 5 , 6' |",
                            efg='-*- 42 -*-',
                        ),
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'],
                            a='-*- 3.2 -*-',
                            b='-*- 44.2 -*-',
                            c='-*- 45.2 -*-',
                            d='-*- 46.2 -*-',
                        ),
                        'THIRD': dict(
                            cls.EXPECTED_CONFIG_BASE['THIRD'],
                            qq="| '' |",
                        ),
                        'fourth': dict(
                            cls.EXPECTED_CONFIG_BASE['fourth'],
                            zzz="| 'ZZZ' |",
                        ),
                    }
                ),
            ).label('config; kwargs: `custom_converters`, `default_converter`')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                    custom_converters=dict(weird='-*- {0} -*-'.format),
                    default_converter="| {0!a} |".format,
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        'first': dict(
                            cls.EXPECTED_CONFIG_BASE['first'],
                            a="| 'xyz' |",
                            bcd="| '4 , 5 , 6' |",
                            efg='-*- 42.0 -*-',
                        ),
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'],
                            a='-*-      3.2 -*-',
                            b='-*-     44.20 -*-',
                            c='-*-     45.200  -*-',
                            d='-*- 000046.2000 -*-',
                        ),
                        'THIRD': dict(
                            cls.EXPECTED_CONFIG_BASE['THIRD'],
                            qq="| '' |",
                        ),
                        'fourth': dict(
                            cls.EXPECTED_CONFIG_BASE['fourth'],
                            zzz="| 'ZZZ' |",
                        ),
                    }
                ),
            ).label('settings; other kwargs: `custom_converters`, `default_converter`')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=(
                    '\n'.join(cls.CONFIG_FILE_PATH_TO_DEFAULT_CONTENT.values()) +
                    reduce_indent('''
                        [second\u015b]
                        unknown = 42
                        [THIRD]
                        unknown = 42
                        [fourth]
                        unknown = 42''')),
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'],
                            unknown=42.0,
                        ),
                        'THIRD': dict(
                            cls.EXPECTED_CONFIG_BASE['THIRD'],
                            unknown='42',
                        ),
                        'fourth': dict(
                            cls.EXPECTED_CONFIG_BASE['fourth'],
                            unknown=42,
                        ),
                    }
                ),
            ).label('config, with free options')

        # NOTE that option-name parts of settings dict keys (contrary to
        # option names in config files) *are* case-sensitive (i.e., are
        # *not* normalized to lowercase).  Of course, typically, they
        # should already have been normalized to lowercase (it should be
        # done when Pyramid *.ini file was parsed...).
        strange_settings = dict(cls.DEFAULT_SETTINGS)
        strange_settings.update({
            'unknown': '42',                # no section name -> section name is ''
            '.UnkNown': ' 4321 ',           # uppercase chars in opt name (to be kept as-is)
            '': '43',                       # no section&option name -> both are ''
            'second\u015b.unknown': '42',
            'second\u015b.UNKNOWN': ' 4321 ',     # uppercase-only opt name (to be kept as-is)
            'second\u015b. \t ': '12345',         # whitespace-only opt name (to be kept as-is)
            'second\u015b.': '43',                # empty option name '' (to be kept as-is)
            'THIRD.unknown': '42',
            'THIRD.UnkNown': ' 4321 ',      # uppercase chars in opt name (to be kept as-is)
            'THIRD....\u015b': '12345',     # non-standard chars (to be kept as-is)
            'fourth.unknown': '42',
            'fourth....\u015b': '12345',  # non-standard chars (to be kept as-is)
            123: '997',                     # non-str settings key (to be skipped)
            b'spam': '997',                 # non-str settings key (to be skipped)
        })
        yield param(
                config_spec=(
                    # allowed free options in the '' section
                    '...\n' +
                    cls.DEFAULT_CONFIG_SPEC),
                optional_kwargs=dict(
                    settings=strange_settings,
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE, **{
                        '': {
                            'unknown': '42',
                            'UnkNown': ' 4321 ',
                            '': '43',
                            # items from DEFAULT_SETTINGS:
                            'aaa': 'qwerty',
                            'irrelevant opt': 'irrelevant value',
                        },
                        'second\u015b': dict(
                            cls.EXPECTED_CONFIG_BASE['second\u015b'], **{
                                'unknown': 42.0,
                                'UNKNOWN': 4321.0,
                                ' \t ': 12345.0,
                                '': 43.0,
                            }
                        ),
                        'THIRD': dict(
                            cls.EXPECTED_CONFIG_BASE['THIRD'], **{
                                'unknown': '42',
                                'UnkNown': ' 4321 ',
                                '...\u015b': '12345',
                            }
                        ),
                        'fourth': dict(
                            cls.EXPECTED_CONFIG_BASE['fourth'], **{
                                'unknown': 42,
                                '...\u015b': 12345,
                            }
                        ),
                    }
                ),
            ).label('settings, with free options (including strangely named)')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=(
                    reduce_indent('''
                        [first]
                        a : 42
                        b : 43
                        HIJ : 44
                        klm.rst : True
                        [THIRD]
                        xx = ""
                        zz = None''')),
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make({
                    'first': {
                        'a': '42',
                        'b': 43,
                        'bcd': '0 , 0 , 0',
                        'efg': 0.0,
                        'hij': '44',
                        'klm.rst': [True],
                        'n': [
                            datetime.datetime(2016, 2, 25, 23, 24, 25, 123400),
                            datetime.datetime(1410, 7, 15, 10, 1),
                        ],
                    },
                    'second\u015b': {},
                    'THIRD': {
                        'xx': '',
                        'yy': {'a': 42},
                        'zz': None,
                    },
                    'fourth': {
                        'zzz': 'ZZZ',
                    },
                    'fifth': {
                        'f': 42,
                    },
                    'sixth': {},
                }),
            ).label('config, with required options/sections only')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings={
                        'first.a': '42',
                        'first.b': '43',
                        'first.hij': 44,  # (the non-str value will be coerced to str)
                        'first.klm.rst': '1',
                        'THIRD.xx': b'',  # (the non-str values will be coerced to str)
                        'THIRD.zz': ' None ',
                    },
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=Config.make({
                    'first': {
                        'a': '42',
                        'b': 43,
                        'bcd': '0 , 0 , 0',
                        'efg': 0.0,
                        'hij': '44',
                        'klm.rst': [True],
                        'n': [
                            datetime.datetime(2016, 2, 25, 23, 24, 25, 123400),
                            datetime.datetime(1410, 7, 15, 10, 1),
                        ],
                    },
                    'second\u015b': {},
                    'THIRD': {
                        'xx': '',
                        'yy': {'a': 42},
                        'zz': None,
                    },
                    'fourth': {
                        'zzz': 'ZZZ',
                    },
                    'fifth': {
                        'f': 42,
                    },
                    'sixth': {},
                }),
            ).label('settings, with required options/sections only')

        yield param(
                config_spec='[spam]\na b c = foo',
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=[],
                expected_outcome=(ConfigError, r'ValueError:'),
            ).label('error: wrong spec [using config]')

        yield param(
                config_spec='[spam]\na b c = foo',
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS)
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(ConfigError, r'ValueError:'),
            ).label('error: wrong spec [using settings]')

        yield param(
                config_spec=b'[spam]\na b c = foo',
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=[],
                expected_outcome=(TypeError, r'config_spec must be str'),
            ).label('error: wrong type of spec [using config]')

        yield param(
                config_spec=b'[spam]\na b c = foo',
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS)
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(TypeError, r'config_spec must be str'),
            ).label('error: wrong type of spec [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    default_converter='some_undefined_key',
                ),
                config_files_content=DEFAULT,
                expected_open_calls=[],
                expected_outcome=(KeyError, r"'some_undefined_key'"),
            ).label('error: undefined `default_converter` '
                    'when specified as string [using config]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    default_converter='some_undefined_key',
                    settings=dict(cls.DEFAULT_SETTINGS),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(KeyError, r"'some_undefined_key'"),
            ).label('error: undefined `default_converter` '
                    'when specified as string [using settings]')

        yield param(
                config_spec='',
                optional_kwargs=dict(),
                config_files_content='abc = foo\n',
                expected_open_calls=[call('a/b/00_global.conf', encoding='utf-8')],
                expected_outcome=(ConfigError, r'MissingSectionHeaderError:'),
            ).label('error: wrong config syntax [here: missing section header]')

        class WithTroublesomeStrAndRepr(object):
            def __str__(self):
                return '\u015b'.encode('ascii')  # will raise UnicodeEncodeError...
            def __repr__(self):
                return str(self)
        yield param(
                config_spec='',
                optional_kwargs=dict(
                    settings={
                        'abc': WithTroublesomeStrAndRepr(),
                    },
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(ConfigError, r"UnicodeEncodeError: 'ascii' codec"),
            ).label('error: really broken settings [here: value which cannot be coerced to str]')

        # (NOTE that section names are always case-*sensitive*)
        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=reduce_indent('''
                    [third]
                    xx = ham
                    zz = ["spam"]
                    '''),
                expected_open_calls=DEFAULT,
                expected_outcome=(
                    ConfigError,
                    r'missing required config sections: first, THIRD'),
            ).label('error: missing section(s) [using config]')

        # (NOTE that section names are always case-*sensitive*)
        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings={
                        'third.xx': 'ham',
                        'third.zz': '["spam"]',
                    },
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(
                    ConfigError,
                    r'missing required config sections: first, THIRD'),
            ).label('error: missing section(s) [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=reduce_indent('''
                    [first]
                    klm.rst: true
                    [THIRD]
                    zz=42'''),
                expected_open_calls=DEFAULT,
                expected_outcome=(
                    ConfigError, (
                        r'missing required config options: '
                        r'first\.a, first\.b, first\.hij, THIRD\.xx')),
            ).label('error: missing option(s) [using config]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings={
                        'first.klm.rst': 'true',
                        'THIRD.zz': '42',
                    }
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(
                    ConfigError, (
                        r'missing required config options: '
                        r'first\.a, first\.b, first\.hij, THIRD\.xx')),
            ).label('error: missing option(s) [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=(
                    '\n'.join(cls.CONFIG_FILE_PATH_TO_DEFAULT_CONTENT.values()) +
                    reduce_indent('''
                        [first]
                        unknown = 1
                        [THIRD]
                        unknown = 3  ; NOTE: spec of this section contains `...`
                        [fifth]
                        unknown = 5''')),
                expected_open_calls=DEFAULT,
                expected_outcome=(
                    ConfigError,
                    r'illegal config options: first\.unknown, fifth\.unknown'),
            ).label('error: illegal option(s) [using config]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(
                    settings=dict(
                        cls.DEFAULT_SETTINGS, **{
                            'first.unknown': '1',
                            'THIRD.unknown': '3',  # (NOTE: spec of this section contains `...`)
                            'fifth.unknown': '5',
                        }
                    ),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(
                    ConfigError,
                    r'illegal config options: first\.unknown, fifth\.unknown'),
            ).label('error: illegal option(s) [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=(
                    ConfigError, (
                        r'unknown config value converter `weird` '
                        r'\(for option first\.efg\); '
                        r'unknown config value converter `weird` '
                        r'\(for free options in section second.*')),
            ).label('error: unknown converter [using config]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'weird'),
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(
                    ConfigError, (
                        r'unknown config value converter `weird` '
                        r'\(for option first\.efg\); '
                        r'unknown config value converter `weird` '
                        r'\(for free options in section second.*')),
            ).label('error: unknown converter [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'zero_div_err'),
                optional_kwargs=dict(
                    custom_converters=dict(zero_div_err=lambda s: 1/0),
                ),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=(
                    ConfigError, (
                        r'error when applying config value converter '
                        r'.* \(ZeroDivisionError:')),
            ).label('error when applying converter [using config]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC.replace('float', 'zero_div_err'),
                optional_kwargs=dict(
                    settings=dict(cls.DEFAULT_SETTINGS),
                    custom_converters=dict(zero_div_err=lambda s: 1/0),
                ),
                config_files_content=sen.irrelevant,
                expected_open_calls=[],
                expected_outcome=(
                    ConfigError, (
                        r'error when applying config value converter '
                        r'.* \(ZeroDivisionError:')),
            ).label('error when applying converter [using settings]')

        yield param(
                config_spec=cls.DEFAULT_CONFIG_SPEC,
                optional_kwargs=dict(),
                config_files_content=DEFAULT,
                expected_open_calls=DEFAULT,
                expected_outcome=Config.make(
                    cls.EXPECTED_CONFIG_BASE,
                    first=dict(
                        cls.EXPECTED_CONFIG_BASE['first'],
                        a='abc',
                    ),
                    THIRD=dict(
                        cls.EXPECTED_CONFIG_BASE['THIRD'],
                        yy={'a': 321},
                    ),
                ),
            ).label('config with some options overridden with --n6config-override'
                ).context(patch, 'sys.argv', sys.argv + [
                    '--n6config-override',
                    'first.a=abc',
                    'THIRD.yy={"a": 321}'])

    @foreach(modern_init_case_params)
    def test_modern_init(self,
                         config_spec,
                         optional_kwargs,
                         config_files_content,
                         expected_open_calls,
                         expected_outcome):
        self._test_init(
            [config_spec],
            optional_kwargs,
            config_files_content,
            expected_outcome,
            expected_open_calls)


    @paramseq
    def legacy_init_case_params(cls):
        yield param(
                args=[],
                kwargs=dict(),
                config_files_content='',
                expected_outcome=Config.make(),
            ).label('empty config, no arguments')

        yield param(
                args=[],
                kwargs=dict(),
                config_files_content=DEFAULT,
                expected_outcome=Config.make(cls.EXPECTED_LEGACY_INIT_CONFIG_BASE),
            ).label('config, no arguments')

        yield param(
                args=[cls.DEFAULT_LEGACY_REQUIRED],
                kwargs=dict(),
                config_files_content=DEFAULT,
                expected_outcome=Config.make(cls.EXPECTED_LEGACY_INIT_CONFIG_BASE),
            ).label('config, `required` as positional arg')

        yield param(
                args=[],
                kwargs=dict(required=cls.DEFAULT_LEGACY_REQUIRED),
                config_files_content=DEFAULT,
                expected_outcome=Config.make(cls.EXPECTED_LEGACY_INIT_CONFIG_BASE),
            ).label('config, `required` as kwarg')

        yield param(
                args=[cls.DEFAULT_LEGACY_REQUIRED],
                kwargs=dict(),
                config_files_content=(
                    reduce_indent('''
                    [first]
                    a : 42
                    b : 43
                    HIJ : 44
                    klM.Rst : \tTrue\t
                    [THIRD]
                    xx = ""
                    zz = ({}, [])
                    ''')),

                expected_outcome=Config.make({
                    'first': {
                        'a': '42',
                        'b': '43',
                        'hij': '44',
                        'klm.rst': 'True',
                    },
                    'THIRD': {
                        'xx': '',
                        'zz': '({}, [])',
                    },
                }),
            ).label('config, with required options/sections only')

        yield param(
                args=[cls.DEFAULT_LEGACY_REQUIRED],
                kwargs=dict(),
                config_files_content='abc = foo\n',
                expected_open_calls=[call('a/b/00_global.conf', encoding='utf-8')],
                expected_outcome=(
                    configparser.MissingSectionHeaderError,
                    r'no section headers'),
            ).label('error: wrong config syntax [here: missing section header]')

        # (NOTE that section names are always case-*sensitive*)
        yield param(
                args=[cls.DEFAULT_LEGACY_REQUIRED],
                kwargs=dict(),
                config_files_content=reduce_indent('''
                    [third]
                    xx = ham
                    zz = ["spam"]
                    '''),
                expected_outcome=(
                    SystemExit,
                    r'missing required config sections: THIRD, first'),
            ).label('error: missing section(s)')

        yield param(
                args=[cls.DEFAULT_LEGACY_REQUIRED],
                kwargs=dict(),
                config_files_content=reduce_indent('''
                    [first]
                    klm.rst: true
                    [THIRD]
                    zz=42'''),
                expected_outcome=(
                    SystemExit, (
                        r'missing required config options: '
                        r'THIRD\.xx, first\.a, first\.b, first\.hij')),
            ).label('error: missing option(s)')

        yield param(
            args=[cls.DEFAULT_LEGACY_REQUIRED],
            kwargs=dict(),
            config_files_content=(
                reduce_indent('''
                            [first]
                            a : 42
                            b : 43
                            HIJ : 44
                            klM.Rst : \tTrue\t
                            [THIRD]
                            xx = ""
                            zz = ({}, [])
                            ''')),

            expected_outcome=Config.make({
                'first': {
                    'a': '321',
                    'b': '43',
                    'hij': '44',
                    'klm.rst': 'True',
                },
                'THIRD': {
                    'xx': '',
                    'zz': '({}, [])',
                },
            }),
        ).label('One config value overridden with --ngconfig-override commandline argument'
            ).context(patch, 'sys.argv', sys.argv + [
                '--foo',
                '--n6config-override',
                'first.a=321',
                'fake.option=value'])

        yield param(
            args=[cls.DEFAULT_LEGACY_REQUIRED],
            kwargs=dict(),
            config_files_content=(
                reduce_indent('''
                            [first]
                            a : 42
                            b : 43
                            HIJ : 44
                            klM.Rst : \tTrue\t
                            [THIRD]
                            xx = ""
                            zz = ({}, [])
                            ''')),

            expected_outcome=Config.make({
                'first': {
                    'a': '321',
                    'b': '43',
                    'hij': '44',
                    'klm.rst': 'True',
                },
                'THIRD': {
                    'xx': 'test',
                    'zz': '({}, [])',
                },
            }),
        ).label('Two config values overridden with --ngconfig-override commandline argument'
            ).context(patch, 'sys.argv', sys.argv + [
                '--n6recovery',
                '--n6config-override',
                'first.a=321',
                'THIRD.xx=test',
                '-foo',
                '--bar'])

    @foreach(legacy_init_case_params)
    def test_legacy_init(self,
                         args,
                         kwargs,
                         config_files_content,
                         expected_outcome,
                         expected_open_calls=DEFAULT):
        self._test_init(
            args,
            kwargs,
            config_files_content,
            expected_outcome,
            expected_open_calls)


    @paramseq
    def config_sections_logging_case_params(cls):
        yield param(
                config_spec='''
                    [foo]
                    nonimplemented_opt = 123 :: int
                    [boo]
                    other_nonimplemented = abc
                ''',
                config_files_content=DEFAULT,
                expected_outcome=Config.make(
                    foo=dict(
                        nonimplemented_opt=123,
                    ),
                    boo=dict(
                        other_nonimplemented='abc',
                    ),
                ),
                expected_log_invocations=[
                    cls.ExpectedLogInvocation(
                        level='error',
                        section_names=['boo', 'foo'],
                        msg_regex=cls.PATTERN_FOR_ABSENT_NONREQUIRED_CONFIG_SECT_MESSAGE,
                    ),
                ],
            ).label('Logged error about absent non-required config sections.')

        # the "third" config section is not logged as absent,
        # as the empty section is implemented inside config files
        yield param(
                config_spec='''
                    [first]
                    nonimplemented_opt = default
                    second_nonimplemented_opt = second_default
                    [second]
                    another_nonimplemented = one, two, three :: list_of_str
                    [third]
                    nonimplemented_opt_in_third = yes :: bool
                ''',
                config_files_content=reduce_indent('''
                    [third]
                '''),
                expected_outcome=Config.make(
                    first=dict(
                        nonimplemented_opt='default',
                        second_nonimplemented_opt='second_default',
                    ),
                    second=dict(
                        another_nonimplemented=['one', 'two', 'three'],
                    ),
                    third=dict(
                        nonimplemented_opt_in_third=True,
                    ),
                ),
                expected_log_invocations=[
                    cls.ExpectedLogInvocation(
                        level='error',
                        section_names=['second', 'first'],
                        msg_regex=cls.PATTERN_FOR_ABSENT_NONREQUIRED_CONFIG_SECT_MESSAGE,
                    ),
                ],
            ).label('Logged error about absent non-required config sections.')

        yield param(
                config_spec='''
                    [extendable_section]
                    first_opt :: int
                    second_opt = abc
                    nonimplemented_opt = {"key": "some_val"} :: json
                    ...
                    [nonextendable_section]
                    required_opt
                ''',
                config_files_content=reduce_indent('''
                    [extendable_section]
                    first_opt = 123
                    second_opt = abcd
                    nondeclared_opt = http://example.com/
                    [nonextendable_section]
                    required_opt = required
                '''),
                expected_outcome=Config.make(
                    extendable_section=dict(
                        first_opt=123,
                        second_opt='abcd',
                        nonimplemented_opt={'key': 'some_val'},
                        nondeclared_opt='http://example.com/'
                    ),
                    nonextendable_section=dict(
                        required_opt='required',
                    ),
                ),
                expected_log_invocations=[
                    cls.ExpectedLogInvocation(
                        level='warning',
                        section_names=['extendable_section'],
                        msg_regex=cls.PATTERN_FOR_OPT_TYPO_VULNERABLE_SECT_NAMES,
                    ),
                ],
            ).label('A warning is logged because of the config section being vulnerable'
                    'to typos in option names.')

        # the sections "extendable_section_two" and
        # "extendable_section_three" are not logged as being
        # vulnerable to typos; even though all of the resultant
        # config options are not declared in the `config_spec`,
        # but all of the declared ones are implemented in config
        # files
        yield param(
                config_spec='''
                    [extendable_section_one]
                    first_opt :: float
                    second_opt :: list_of_str
                    nonimplemented_opt = {"key": "some_val"} :: json
                    ...
                    [extendable_section_two]
                    ...
                    [extendable_section_three]
                    some_opt
                    some_second_opt = bytes_opt :: bytes
                    ...
                ''',
                config_files_content=reduce_indent('''
                    [extendable_section_one]
                    first_opt = 123.89
                    second_opt = one, two, three
                    nondeclared_opt = 9989
    
                    [extendable_section_two]
                    nondeclared_opt = does_not_trigger_warning
    
                    [extendable_section_three]
                    some_opt = example
                    some_second_opt = overridden bytes option
                    some_nondeclared_opt = trigger_warning
                '''),
                expected_outcome=Config.make(
                    extendable_section_one=dict(
                        first_opt=123.89,
                        second_opt=['one', 'two', 'three'],
                        nonimplemented_opt={'key': 'some_val'},
                        nondeclared_opt='9989',
                    ),
                    extendable_section_two=dict(
                        nondeclared_opt='does_not_trigger_warning',
                    ),
                    extendable_section_three=dict(
                        some_opt='example',
                        some_second_opt=b'overridden bytes option',
                        some_nondeclared_opt='trigger_warning',
                    )
                ),
                expected_log_invocations=[
                    cls.ExpectedLogInvocation(
                        level='warning',
                        section_names=['extendable_section_one'],
                        msg_regex=cls.PATTERN_FOR_OPT_TYPO_VULNERABLE_SECT_NAMES,
                    ),
                ],
            ).label('A warning is logged because of the config section being vulnerable'
                    ' to typos in option names.')

        # config declaration and its implementation are correct,
        # there should not be any warning or error messages logged
        yield param(
                config_spec='''
                    [extendable_section_one]
                    first_opt :: float
                    second_opt :: list_of_str
                    third_opt = {"key": "some_val"} :: json
                    ...
                    [extendable_section_two]
                    example_opt = some declared option
                    ...
                    [extendable_section_three]
                    some_opt
                    some_second_opt = bytes_opt :: bytes
                    some_third_opt = third option
                    ...
                ''',
                config_files_content=reduce_indent('''
                    [extendable_section_one]
                    first_opt = 123.89
                    second_opt = one, two, three
                    third_opt = {"opt": "example option"}
    
                    [extendable_section_two]
                    example_opt = implemented option
                    nondeclared_opt = still does not trigger warning nor error
    
                    [extendable_section_three]
                    some_opt = example
                    some_second_opt = overridden bytes option
                    some_third_opt = some third option
                '''),
                expected_outcome=Config.make(
                    extendable_section_one=dict(
                        first_opt=123.89,
                        second_opt=['one', 'two', 'three'],
                        third_opt={'opt': 'example option'},
                    ),
                    extendable_section_two=dict(
                        example_opt='implemented option',
                        nondeclared_opt='still does not trigger warning nor error',
                    ),
                    extendable_section_three=dict(
                        some_opt='example',
                        some_second_opt=b'overridden bytes option',
                        some_third_opt='some third option',
                    ),
                ),
                expected_log_invocations=None,
            ).label('No warning nor error is logged, config is correct.')

        yield param(
                config_spec='''
                    [first]
                    first_opt :: int
                    nonimplemented_opt = default
                    [second]
                    another_opt = one, two, three :: list_of_str
                    [third]
                    yet_another_opt :: float
                    nonimplemented_opt_in_third = yes :: bool
                    ...
                ''',
                config_files_content=reduce_indent('''
                    [first]
                    first_opt = 8889
                    [third]
                    yet_another_opt = 999.12
                    opt_with_typo = no
                '''),
                expected_outcome=Config.make(
                    first=dict(
                        first_opt=8889,
                        nonimplemented_opt='default',
                    ),
                    second=dict(
                        another_opt=['one', 'two', 'three'],
                    ),
                    third=dict(
                        yet_another_opt=999.12,
                        nonimplemented_opt_in_third=True,
                        opt_with_typo='no',
                    ),
                ),
                expected_log_invocations=[
                    cls.ExpectedLogInvocation(
                        level='error',
                        section_names=['second'],
                        msg_regex=cls.PATTERN_FOR_ABSENT_NONREQUIRED_CONFIG_SECT_MESSAGE,
                    ),
                    cls.ExpectedLogInvocation(
                        level='warning',
                        section_names=['third'],
                        msg_regex=cls.PATTERN_FOR_OPT_TYPO_VULNERABLE_SECT_NAMES,
                    ),
                ],
            ).label('Warning and error are logged because of the missing nonrequired section '
                    'and a possibility of a typo in option names.')

    @foreach(config_sections_logging_case_params)
    def test_modern_init_logging_uncertainties(self,
                                               config_spec,
                                               config_files_content,
                                               expected_outcome,
                                               expected_log_invocations):
        with patch('n6lib.config.LOGGER') as logger_mock:
            self._test_init(args=[config_spec],
                            kwargs=dict(),
                            config_files_content=config_files_content,
                            expected_outcome=expected_outcome,
                            expected_open_calls=DEFAULT)
            if expected_log_invocations is not None:
                expected_log_levels = {inv.level for inv in expected_log_invocations}
                unexpected_log_levels = self.TESTED_LOGGER_LEVELS - expected_log_levels
                for log_invocation in expected_log_invocations:
                    log_method_mock = getattr(logger_mock, log_invocation.level)
                    self.assertTrue(log_method_mock.called,
                                    "A message with level: %s was "
                                    "not logged." % log_invocation.level)
                    log_args, _ = log_method_mock.call_args
                    logged_msg = log_args[0]
                    logged_sect_names = [x.strip('"') for x in log_args[1].split(', ')]
                    self.assertRegex(logged_msg, log_invocation.msg_regex)
                    self.assertCountEqual(logged_sect_names, log_invocation.section_names,
                                          "Logged section names are not equal to expected ones.")
            else:
                # no messages are expected to be logged, every
                # possible logging level is unexpected
                unexpected_log_levels = self.TESTED_LOGGER_LEVELS

            # make sure there were no messages logged with a level
            # other than expected ones (considering the log levels
            # we are concerned with)
            for unexpected_log_level in unexpected_log_levels:
                self.assertFalse(getattr(logger_mock, unexpected_log_level).called,
                                 "Message with an unexpected level was logged.")


    # a helper used in the above tests of __init__()
    def _test_init(self,
                   args,
                   kwargs,
                   config_files_content,
                   expected_outcome,
                   expected_open_calls):
        self.patch_file_ops(config_files_content)
        expected_open_calls = self.adjust_expected_open_calls(expected_open_calls)
        if isinstance(expected_outcome, Config):
            # expected outcome is a Config instance returned
            result = Config(*args, **kwargs)
            self.assertEqualIncludingTypes(result, expected_outcome)
        else:
            # expected outcome is an exception raised
            expected_exc_class, expected_exc_regex = expected_outcome
            assert issubclass(expected_exc_class, BaseException), 'bug in test'
            with self.assertRaisesRegex(expected_exc_class, expected_exc_regex):
                Config(*args, **kwargs)
        self.assertEqual(self.configparser_open_mock.mock_calls, expected_open_calls)


    @foreach(
        ('first', ConfigSection('first', {
            'aaa': 42,
            'bb': '43',
            'cc': [1, 2, 3],
        })),
        ('second', ConfigSection('second', {
            'foo.bar': 'Spam',
        })),
        ('xyz', NoConfigSectionError),
        ('FIRST', NoConfigSectionError),
        ('Second', NoConfigSectionError),
    )
    def test_some_lookups(self, key, expected_outcome):
        config = Config.make({
            'first': {
                'aaa': 42,
                'bb': '43',
                'cc': [1, 2, 3],
            },
            'second': {
                'foo.bar': 'Spam',
            },
        })
        if isinstance(expected_outcome, ConfigSection):
            # expected outcome is a ConfigSection instance returned
            result = config[key]
            self.assertEqualIncludingTypes(result, expected_outcome)
        else:
            # expected outcome is a NoConfigSectionError exception raised
            assert expected_outcome is NoConfigSectionError, 'bug in test'
            with self.assertRaises(expected_outcome):
                config[key]

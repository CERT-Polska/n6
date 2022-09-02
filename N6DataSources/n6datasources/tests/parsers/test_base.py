# Copyright (c) 2013-2022 NASK. All rights reserved.

import collections.abc
import copy
import csv
import datetime
import hashlib
import io
import json
import traceback
import unittest
from typing import Any
from unittest.mock import (
    ANY,
    Mock,
    MagicMock,
    call,
    patch,
    sentinel,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.class_helpers import get_class_name
from n6lib.common_helpers import (
    FilePagedSequence,
    PlainNamespace,
    ipv4_to_str,
)
from n6lib.config import (
    Config,
    ConfigError,
    ConfigMixin,
    ConfigSection,
    ConfigSpecEgg,
    ConfigSpecEggError,
    NoConfigOptionError,
    NoConfigSectionError,
    as_config_spec_string,
    combined_config_spec,
    parse_config_spec,
)
from n6lib.record_dict import (
    AdjusterError,
    RecordDict,
)
from n6lib.unit_test_helpers import (
    AnyMatchingRegex,
    MethodProxy,
    TestCaseMixin,
)
from n6datapipeline.base import LegacyQueuedBase
from n6datasources.parsers.base import (
    BaseParser,
    AggregatedEventParser,
    BlackListParser,
    SkipParseExceptionsMixin,
)


SAMPLE_ARG_A = sentinel.a
SAMPLE_ARG_B = sentinel.b


@expand
class TestBaseParser(TestCaseMixin, unittest.TestCase):

    #
    # Setup/helpers

    def setUp(self):
        # (We want to make `LegacyQueuedBase.__new__()`'s stuff isolated
        # from real `sys.argv`...)
        self.patch_argparse_stuff()

        # Note: in tests that make use of `self.super_patcher`, usually,
        # some attributes are added to the `self.super_obj_stub` object.
        self.super_obj_stub = PlainNamespace()
        self.super_patcher = patch(
            'n6datasources.parsers.base.super',
            return_value=self.super_obj_stub)

        # Note: in tests that make use of `self.config_patcher`,
        # `self.config_files_mocked_data` needs to be a dict that maps
        # config section names to dicts mapping option names to their
        # values.
        self.config_files_mocked_data = None
        self.config_patcher = patch(
            'n6lib.config.Config._load_n6_config_files',
            side_effect=lambda *_: dict(self.config_files_mocked_data))

        # Note: in tests that make use of `self.mock`+`self.meth`,
        # additional attributes may need to be set on `self.mock`.
        self.mock = Mock(__class__=BaseParser, allow_empty_results=False)
        self.meth = MethodProxy(BaseParser, self.mock)


    def _assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(self, owner):
        parser_class_name = get_class_name(owner)
        config_spec_pattern = owner.config_spec_pattern
        try:
            config_spec = as_config_spec_string(
                config_spec_pattern,
                format_data_mapping=dict(parser_class_name=parser_class_name))
            config_spec_parsed = parse_config_spec(config_spec)
            [main_sect_spec] = [
                sect_spec for sect_spec in config_spec_parsed.get_all_sect_specs()
                if sect_spec.name == parser_class_name]
        except Exception:  # noqa
            self.fail(
                f'could not extract the main parser config section '
                f'from {config_spec_pattern=!a} - the following error '
                f'occurred:\n{traceback.format_exc()}')
        else:
            prefetch_count_opt_spec_seq = [
                opt_spec for opt_spec in main_sect_spec.opt_specs
                if opt_spec.name == 'prefetch_count']

            self.assertIsInstance(config_spec_pattern, (str, ConfigSpecEgg))
            self.assertEqual(len(prefetch_count_opt_spec_seq), 1)
            self.assertEqual(prefetch_count_opt_spec_seq[0].converter_spec, 'int')


    #
    # Actual tests

    def test_superclasses(self):
        self.assertTrue(issubclass(BaseParser, ConfigMixin))
        self.assertTrue(issubclass(BaseParser, LegacyQueuedBase))


    @foreach(
        # Note: these are only selected ones.
        'rabbitmq_config_section',
        'basic_prop_kwargs',
        '__new__',
        'run',
        'stop',
        'on_message',
        'publish_output',
    )
    def test_most_important_stuff_inherited_from_LegacyQueuedBase(self, name):
        here = getattr(BaseParser, name)
        there = getattr(LegacyQueuedBase, name)

        self.assertIs(here, there)


    def test_class_attr_values(self):
        self.assertEqual(BaseParser.input_queue, {'exchange': 'raw', 'exchange_type': 'topic'})
        self.assertEqual(BaseParser.output_queue, {'exchange': 'event', 'exchange_type': 'topic'})
        self.assertIsNone(BaseParser.default_binding_key)
        self.assertIsNone(BaseParser.constant_items)
        self.assertIsInstance(BaseParser.config_spec_pattern, ConfigSpecEgg)
        self.assertRegex(
            as_config_spec_string(BaseParser.config_spec_pattern),
            r'(?mx)^prefetch_count \s* [=:] \s* 1 \s* :: \s* int\b')
        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(BaseParser)
        self.assertIs(BaseParser.record_dict_class, RecordDict)
        self.assertIsNone(BaseParser.record_dict_kwargs, RecordDict)
        self.assertEqual(BaseParser.event_type, 'event')
        self.assertFalse(BaseParser.allow_empty_results)
        self.assertTrue(BaseParser.supports_n6recovery)
        self.assertEqual(BaseParser.unsupported_class_attributes, {
            'default_converter',
            'config_required',
            'config_group',
        })


    def test__CsvRawRows(self):
        raw = (
            b'foo,BAR\r\n'
            b'"spam spam spam ","\xc5\x81 \xdd"\n'
            b'a,"b b b"\r'
            b'"x",y')

        csv_raw_rows = BaseParser.CsvRawRows(raw)

        # (Note: is a multiple-use iterable, not a one-shot iterator.)
        csv_raw_rows_iterator = iter(csv_raw_rows)
        csv_raw_rows_another_iterator = iter(csv_raw_rows)
        csv_raw_rows_list = list(csv_raw_rows)
        csv_raw_rows_another_list = list(csv_raw_rows)

        csv_reader = csv.reader(csv_raw_rows)

        self.assertIsInstance(csv_raw_rows, BaseParser.CsvRawRows)
        self.assertIsInstance(csv_raw_rows_iterator, collections.abc.Iterator)
        self.assertIsInstance(csv_raw_rows_iterator, io.StringIO)
        self.assertIsNot(csv_raw_rows_iterator, csv_raw_rows_another_iterator)
        self.assertEqual(csv_raw_rows_list, csv_raw_rows_another_list)
        self.assertEqual(csv_raw_rows_list, [
            # (`io.StringIO` was made with `newline=''`: *universal newlines*
            # recognition is enabled, but newline characters are left intact;
            # that's how it should be prepared for a CSV reader...)
            'foo,BAR\r\n',
            '"spam spam spam ","Ł \udcdd"\n',  # (<- non-UTF-8 byte decoded to lone surrogate)
            'a,"b b b"\r',
            '"x",y',
        ])
        self.assertEqual(list(csv_reader), [
            ['foo', 'BAR'],
            ['spam spam spam ', 'Ł \udcdd'],
            ['a', 'b b b'],
            ['x', 'y'],
        ])
        # (Note: `==` and `!=` based on the content of the `raw` attribute.)
        self.assertEqual(csv_raw_rows.raw, raw)
        self.assertEqual(csv_raw_rows, BaseParser.CsvRawRows(raw))
        self.assertNotEqual(csv_raw_rows, BaseParser.CsvRawRows(raw + b'x'))


    def test__run_script(self):
        func = self.check_and_extract_func_from_class_method(BaseParser.run_script)
        rec = MagicMock()
        rec.cls.get_script_init_kwargs.return_value = script_init_kwargs = {'a': SAMPLE_ARG_A}
        with patch('n6datasources.parsers.base.logging_configured', rec.logging_configured):

            result = func(rec.cls)

        self.assertIsNone(result)
        self.assertEqual(rec.mock_calls, [
            call.logging_configured(),
            call.logging_configured().__enter__(),
            call.cls.get_script_init_kwargs(),
            call.cls(**script_init_kwargs),
            call.cls().run_handling(),
            call.logging_configured().__exit__(None, None, None),
        ])


    def test__get_script_init_kwargs(self):
        func = self.check_and_extract_func_from_class_method(BaseParser.get_script_init_kwargs)
        rec = MagicMock()

        result = func(rec.cls)

        self.assertEqual(result, {})
        self.assertIsInstance(result, dict)
        self.assertEqual(rec.mock_calls, [])


    @foreach(
        param(binding_key='foo.bar'),
        param(binding_key='foo.bar.202208'),
    )
    @foreach(
        param(use_combined_config_spec=False),
        param(use_combined_config_spec=True),   # (preferred in real code)
    )
    @foreach(
        param(
            config_spec_pattern_custom_content=None,
            config_files_mocked_data={},
            expected_config=ConfigSection('SomeParser', {'prefetch_count': 1}),
            expected_config_full=Config.make({'SomeParser': {'prefetch_count': 1}}),
        ).label('no config spec pattern customization, no data from files'),

        param(
            config_spec_pattern_custom_content=None,
            config_files_mocked_data={
                'SomeParser': {
                    'prefetch_count': '42',
                },
                'unrelated_irrelevant_section': {
                    'another_opt': '123456.456789',
                },
            },
            expected_config=ConfigSection('SomeParser', {'prefetch_count': 42}),
            expected_config_full=Config.make({'SomeParser': {'prefetch_count': 42}}),
        ).label('no config spec pattern customization, some data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 123 :: int
                some_opt = [-3, None] :: py
            ''',
            config_files_mocked_data={},
            expected_config=ConfigSection('SomeParser', {
                'prefetch_count': 123,
                'some_opt': [-3, None],
            }),
            expected_config_full=Config.make({
                'SomeParser': {
                    'prefetch_count': 123,
                    'some_opt': [-3, None],
                },
            }),
        ).label('customized config spec pattern with only main section, no data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count :: int
                some_opt = [-3, None] :: py
            ''',
            config_files_mocked_data={
                'SomeParser': {
                    'prefetch_count': '42',
                },
            },
            expected_config=ConfigSection('SomeParser', {
                'prefetch_count': 42,
                'some_opt': [-3, None],
            }),
            expected_config_full=Config.make({
                'SomeParser': {
                    'prefetch_count': 42,
                    'some_opt': [-3, None],
                },
            }),
        ).label('customized config spec pattern with only main section, some data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 123 :: int
                some_opt = [-3, None] :: py

                [another_section]
                another_opt :: float
                yet_another_opt = Foo Bar Spam Ham
                ...  ; making arbirary option names legal
            ''',
            config_files_mocked_data={
                # (note: no 'SomeParser' key here)
                'another_section': {
                    'another_opt': '123.456',
                    'yet_another_opt': '',
                    'yet_yet_another_opt': 'GHIJKL',
                    'yet_yet_yet_another_opt': '42',
                },
                'unrelated_irrelevant_section': {
                    'another_opt': '123456.456789'
                },
            },
            expected_config=ConfigSection('SomeParser', {
                'prefetch_count': 123,
                'some_opt': [-3, None],
            }),
            expected_config_full=Config.make({
                'SomeParser': {
                    'prefetch_count': 123,
                    'some_opt': [-3, None],
                },
                'another_section': {
                    'another_opt': 123.456,
                    'yet_another_opt': '',
                    'yet_yet_another_opt': 'GHIJKL',
                    'yet_yet_yet_another_opt': '42',
                },
            }),
        ).label('customized config spec pattern with a few sections... (#1)'),

        param(
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 123 :: int
                some_opt = [-3, None] :: py

                [another_section]
                another_opt :: float
                yet_another_opt = Foo Bar Spam Ham

                [yet_another_section]
                some = Ala ma kota! :: str

                [yet_yet_another_section]
                some = A kot ma Alę! :: str
                dt = 2022-08-20 20:33 :: datetime
            ''',
            config_files_mocked_data={
                'SomeParser': {
                    'prefetch_count': '42',
                },
                'another_section': {
                    'another_opt': '123.456',
                },
                'yet_another_section': {},
                # (no 'yet_yet_another_section' key)
            },
            expected_config=ConfigSection('SomeParser', {
                'prefetch_count': 42,
                'some_opt': [-3, None],
            }),
            expected_config_full=Config.make({
                'SomeParser': {
                    'prefetch_count': 42,
                    'some_opt': [-3, None],
                },
                'another_section': {
                    'another_opt': 123.456,
                    'yet_another_opt': 'Foo Bar Spam Ham',
                },
                'yet_another_section': {
                    'some': 'Ala ma kota!',
                },
                'yet_yet_another_section': {
                    'some': 'A kot ma Alę!',
                    'dt': datetime.datetime(2022, 8, 20, 20, 33),
                },
            }),
        ).label('customized config spec pattern with a few sections... (#2)'),
    )
    def test_instantiation(self,
                           binding_key,
                           use_combined_config_spec,
                           config_spec_pattern_custom_content,
                           config_files_mocked_data,
                           expected_config,
                           expected_config_full):

        if config_spec_pattern_custom_content is None:
            class SomeParser(BaseParser):  # noqa
                default_binding_key = binding_key
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec('')
        else:
            class SomeParser(BaseParser):  # noqa
                default_binding_key = binding_key
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec(config_spec_pattern_custom_content)
                else:
                    config_spec_pattern = config_spec_pattern_custom_content

        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(SomeParser)

        self.super_obj_stub.__init__ = super_init_mock = Mock()
        self.config_files_mocked_data = config_files_mocked_data
        with patch('n6lib.config.LOGGER'), \
             self.super_patcher as super_mock, \
             self.config_patcher:

            instance = SomeParser(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        self.assertIsInstance(instance, SomeParser)
        super_mock.assert_called_once_with()
        super_init_mock.assert_called_once_with(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)
        self.assertEqual(instance.config, expected_config)
        self.assertIsInstance(instance.config, ConfigSection)
        self.assertEqual(instance.config_full, expected_config_full)
        self.assertIsInstance(instance.config_full, Config)
        self.assertEqual(instance.prefetch_count, expected_config['prefetch_count'])

        self.assertEqual(instance.input_queue, {
            'exchange': 'raw',            # (note: `BaseParser.preinit_hook()` ensures this
            'exchange_type': 'topic',     # is true, if `default_binding_key` is provided)
            'queue_name': binding_key,
            # (note: because of mocked `super()`, in this test the
            # `configure_pipeline()` method has not been called --
            # that's why here we do not have the 'binding_keys' key;
            # see some other tests where that method *is* called, as
            # in the non-test reality...)
        })
        self.assertEqual(SomeParser.input_queue, {
            'exchange': 'raw',            # (the class attribute has been left intact)
            'exchange_type': 'topic',
        })

        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(instance)


    def test_instantiation_with_missing_default_binding_key_causes_error(self):
        class SomeParser(BaseParser):  # noqa
            pass  # no `default_binding_key` defined => it's an abstract class
        expected_error_regex = "attribute 'default_binding_key' is required"

        with self.assertRaisesRegex(NotImplementedError, expected_error_regex):
            SomeParser()


    @foreach(
        param(binding_key='foo.bar'),
        param(binding_key='foo.bar.202208'),
    )
    @foreach(
        # Note: in the first seven `param()` objects we need to set the
        # test parameter `use_combined_config_spec` to these particular
        # values (in particular, in the first two `param()` objects we
        # need to set that parameter to *false*, because here we want to
        # test the cases when the config spec pattern does *not* include
        # the default elements -- whereas using `combined_config_spec()`
        # would make them be automatically inherited from the config
        # spec pattern of the base parser class). For the rest of the
        # following `param()` objects there are no such needs, so we
        # just set `use_combined_config_spec` to `True` and `False`
        # alternately.
        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [some_other_section]
                required :: int
            ''',
            config_files_mocked_data={
                'some_other_section': {'required': '42'}
            },
            expected_exc=NoConfigSectionError,
        ).label('wrong config spec pattern: undeclared main section'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                some_opt = 7 :: int
            ''',
            config_files_mocked_data={
                'SomeParser': {'some_opt': '42'}
            },
            expected_exc=NoConfigOptionError,
        ).label('wrong config spec pattern: undeclared option `prefetch_count` in main section`'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [another_section]
                {unknown_replacement field} = 3 :: int
            ''',
            config_files_mocked_data={},
            expected_exc=ConfigSpecEggError,
        ).label(
            'wrong config spec pattern (made with `combined_config_spec()`): custom replacement '
            'field and no appropriate extension of `get_config_spec_format_kwargs()`'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
                {unknown_replacement field} = 3 :: int
            ''',
            config_files_mocked_data={},
            expected_exc=KeyError,
        ).label(
            'wrong config spec pattern (made as plain string): custom replacement '
            'field and no appropriate extension of `get_config_spec_format_kwargs()`'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: float
            ''',
            config_files_mocked_data={},
            expected_exc=ConfigSpecEggError,
        ).label(
            'wrong config spec pattern made with `combined_config_spec()`: converter '
            'spec of overridden option does not match one defined in base class'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content=None,
            config_files_mocked_data={
                'SomeParser': {'illegal_opt': 'whatever'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: illegal option name in main section '
                '(when there is no customization of config spec pattern)'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content=None,
            config_files_mocked_data={
                'SomeParser': {'illegal_opt': 'whatever'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: illegal option name in main section '
                '(when there is no customization of config spec pattern '
                'because of setting `combined_config_spec("")`)'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
                some_text = spam spam spam :: str
            ''',
            config_files_mocked_data={
                'SomeParser': {'illegal_opt': 'whatever'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: illegal option name in main section '
                '(when the is some customization of config spec pattern'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
            ''',
            config_files_mocked_data={
                'SomeParser': {'prefetch_count': 'not-a-number'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: invalid option values in main section'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
                required :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={
                'SomeParser': {
                    # (no 'required' key, which is a required option name)
                    'another': 'no',
                },
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: missing option required in main section'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
                required :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={},
            expected_exc=ConfigError,
        ).label('wrong config files data: missing option required in main section + no section'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{parser_class_name}]
                prefetch_count = 1 :: int
                required :: int
                another = yes :: bool

                [another_section]
                foo :: list_of_float
                from = 2010-07-19 12:39:45+02:00 :: datetime
                until = 2022-07-23 :: date
            ''',
            config_files_mocked_data={
                'SomeParser': {
                    'prefetch_count': '123456789',
                    'required': '42',
                    'another': 'OFF',
                },
                'another_section': {
                    # (no 'foo' key, which a required option name)
                    'until': '2022-08-04',
                    'another': 'GHIJKL',    # ('another' is an undeclared option name)
                    'yet_another': '42',    # ('yet_another' is an undeclared option name)
                },
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: illegal and missing option names in another section'),
    )
    def test_instantiation_with_wrong_config_stuff_causes_error(self,
                                                                binding_key,
                                                                use_combined_config_spec,
                                                                config_spec_pattern_custom_content,
                                                                config_files_mocked_data,
                                                                expected_exc):

        if config_spec_pattern_custom_content is None:
            class SomeParser(BaseParser):  # noqa
                default_binding_key = binding_key
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec('')
        else:
            class SomeParser(BaseParser):  # noqa
                default_binding_key = binding_key
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec(config_spec_pattern_custom_content)
                else:
                    config_spec_pattern = config_spec_pattern_custom_content

        self.config_files_mocked_data = config_files_mocked_data
        with patch('n6lib.config.LOGGER'), \
             patch('sys.stderr'), \
             self.super_patcher, \
             self.config_patcher:

            with self.assertRaises(expected_exc) as exc_context:
                SomeParser(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        if expected_exc is ConfigError:
            # (expecting not just any subclass of `ConfigError`
            # but exactly this type of exception)
            self.assertIs(type(exc_context.exception), expected_exc)


    @foreach(
        param(binding_key='foo.bar'),
        param(binding_key='foo.bar.202208'),
    )
    def test_automatic_input_queue_adjustments_during_instantiation(self, binding_key):
        class SomeParser(BaseParser):  # noqa
            default_binding_key = binding_key

        self.config_files_mocked_data = {}
        with self.config_patcher, \
             patch('n6datapipeline.base.LOGGER') as n6datapipeline_base_logger_mock:

            instance = SomeParser.__new__(SomeParser)

            self.assertEqual(instance.input_queue, {
                'exchange': 'raw',
                'exchange_type': 'topic',     # (note: `BaseParser.preinit_hook()` ensures this
                'queue_name': binding_key,    # is true, if `default_binding_key` is provided)
            })

            instance.configure_pipeline()

        self.assertEqual(n6datapipeline_base_logger_mock.warning.mock_calls, [])
        self.assertEqual(instance.input_queue, {
            'exchange': 'raw',
            'exchange_type': 'topic',
            'queue_name': binding_key,
            'binding_keys': [binding_key],    # (<- `configure_pipeline()` added this)
        })
        self.assertEqual(SomeParser.input_queue, {
            'exchange': 'raw',                # (the class attribute has been left intact)
            'exchange_type': 'topic',
        })


    # TODO: full process of the pipeline configuration should
    #       be tested... See: #8523.
    # (note that the following pipeline-related tests as somewhat "dry"...)


    def test__configure_pipeline(self):
        self.mock.default_binding_key = sentinel.default_binding_key
        self.mock.input_queue = {}
        self.super_obj_stub.configure_pipeline = super_configure_pipeline_mock = Mock()
        with self.super_patcher as super_mock:

            self.meth.configure_pipeline()

        self.assertEqual(self.mock.input_queue['binding_keys'], [sentinel.default_binding_key])
        self.assertEqual(self.mock.mock_calls, [])
        super_mock.assert_called_once_with()
        super_configure_pipeline_mock.assert_called_once_with()


    def test__get_component_group_and_id(self):
        component_group, component_id = self.meth.get_component_group_and_id()

        self.assertEqual(component_group, 'parsers')
        self.assertEqual(component_id, 'baseparser')
        self.assertEqual(self.mock.mock_calls, [])


    def test__make_binding_keys(self):
        self.mock.input_queue = {}

        self.meth.make_binding_keys([sentinel.some_binding_key], SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        self.assertEqual(self.mock.input_queue['binding_keys'], [sentinel.some_binding_key])
        self.assertEqual(self.mock.mock_calls, [])


    def test__get_connection_params_dict(self):
        func = self.check_and_extract_func_from_class_method(BaseParser.get_connection_params_dict)
        rec = MagicMock()
        self.super_obj_stub.get_connection_params_dict = rec.super_obj.get_connection_params_dict
        self.super_obj_stub.get_connection_params_dict.return_value = connection_params_dict = {
            'unrelated_param': sentinel.someval,
        }
        rec.cls._aux_rabbitmq_config_spec_pattern = BaseParser._aux_rabbitmq_config_spec_pattern
        rec.cls.rabbitmq_config_section = 'rabbitmq'
        heartbeat_interval_parsers_in_config_file = '321'
        heartbeat_interval_expected = 321
        self.config_files_mocked_data = {
            rec.cls.rabbitmq_config_section: {
                'heartbeat_interval_parsers': heartbeat_interval_parsers_in_config_file,
            },
        }
        with patch('n6lib.config.LOGGER'), \
             self.super_patcher as super_mock, \
             self.config_patcher:

            result = func(rec.cls)

        self.assertEqual(result, {
            'heartbeat_interval': heartbeat_interval_expected,
            'unrelated_param': sentinel.someval,
        })
        self.assertIs(result, connection_params_dict)
        super_mock.assert_called_once_with()
        self.assertEqual(rec.mock_calls, [
            call.super_obj.get_connection_params_dict(),
        ])


    @foreach(
        param(
            config_files_mocked_data={},
            expected_config_error_regex=r'missing required',
        ).label('missing option `heartbeat_interval_parsers`'),

        param(
            config_files_mocked_data={'rabbitmq': {'heartbeat_interval_parsers': 'xyz'}},
            expected_config_error_regex=r'value.*invalid',
        ).label('invalid value of option `heartbeat_interval_parsers`'),
    )
    def test__get_connection_params_dict__with_wrong_config_raises_error(
            self,
            config_files_mocked_data,
            expected_config_error_regex):

        func = self.check_and_extract_func_from_class_method(BaseParser.get_connection_params_dict)
        parser_class_stub = PlainNamespace(
            _aux_rabbitmq_config_spec_pattern=BaseParser._aux_rabbitmq_config_spec_pattern,
            rabbitmq_config_section='rabbitmq')
        self.super_obj_stub.get_connection_params_dict = lambda: sentinel.irrelevant
        self.config_files_mocked_data = config_files_mocked_data
        with patch('n6lib.config.LOGGER'), \
             self.super_patcher, \
             self.config_patcher:

            with self.assertRaisesRegex(ConfigError, expected_config_error_regex):
                func(parser_class_stub)


    def test__run_handling(self):
        self.meth.run_handling()

        self.assertEqual(self.mock.mock_calls, [
            call.run(),
        ])


    @foreach(
        param(
            exc_from_stop=None,
            expected_exc_class=KeyboardInterrupt,
        ),
        param(
            exc_from_stop=ValueError('spam'),
            expected_exc_class=ValueError,
        ),
        param(
            exc_from_stop=SystemExit('Woops!'),
            expected_exc_class=SystemExit,
        ),
    )
    def test__run_handling__with_run_method_raising_keyboard_interrupt(self,
                                                                       exc_from_stop,
                                                                       expected_exc_class):
        self.mock.run.side_effect = KeyboardInterrupt
        self.mock.stop.side_effect = exc_from_stop

        with self.assertRaises(expected_exc_class):
            self.meth.run_handling()

        self.assertEqual(self.mock.mock_calls, [
            call.run(),
            call.stop(),
        ])


    @foreach(
        ValueError('spam'),
        SystemExit('Woops!'),
    )
    def test__run_handling__with_run_method_raising_another_exception(self, exc_from_run):
        self.mock.run.side_effect = exc_from_run

        with self.assertRaises(type(exc_from_run)):
            self.meth.run_handling()

        self.assertEqual(self.mock.mock_calls, [
            call.run(),
        ])


    @patch('n6datasources.parsers.base.FilePagedSequence')
    def test__input_callback(self, FilePagedSequence_mock):
        FilePagedSequence_mock.return_value = MagicMock()
        FilePagedSequence_mock.return_value.__enter__.return_value = sentinel.working_seq
        data = MagicMock(**{'get.return_value': sentinel.rid})
        self.mock.configure_mock(**{
            'prepare_data.return_value': data,
            'setting_error_event_info': MagicMock(),
            'get_output_rk.return_value': sentinel.output_rk,
            'get_output_bodies.return_value': [sentinel.output_body1, sentinel.output_body2],
        })

        self.meth.input_callback(sentinel.routing_key, sentinel.body, sentinel.properties)

        self.assertEqual(self.mock.mock_calls, [
            call.prepare_data(sentinel.routing_key, sentinel.body, sentinel.properties),
            call.prepare_data().get('properties.message_id'),
            call.setting_error_event_info(sentinel.rid),
            call.setting_error_event_info().__enter__(),
            call.get_output_rk(data),
            call.get_output_bodies(data, sentinel.working_seq),
            call.publish_output(
                routing_key=sentinel.output_rk,
                body=sentinel.output_body1),
            call.publish_output(
                routing_key=sentinel.output_rk,
                body=sentinel.output_body2),
            call.setting_error_event_info().__exit__(None, None, None),
        ])
        self.assertEqual(FilePagedSequence_mock.mock_calls, [
            call(page_size=1000),
            call().__enter__(),
            call().__exit__(None, None, None),
        ])


    @foreach(
        param(
            routing_key='provider.channel',
            expected_source='provider.channel',
            expected_raw_format_version_tag=None,
        ),
        param(
            routing_key='provider.channel.202208',
            expected_source='provider.channel',
            expected_raw_format_version_tag='202208',
        ),
    )
    def test__prepare_data(self, routing_key, expected_source, expected_raw_format_version_tag):
        self.mock.CsvRawRows = BaseParser.CsvRawRows

        data = self.meth.prepare_data(
            routing_key=routing_key,
            body=b'<some body>',
            properties=PlainNamespace(foo=sentinel.foo,
                                      bar=sentinel.bar,
                                      timestamp=1389348840,
                                      headers={'a': sentinel.a}))

        self.assertEqual(data, {
            'a': sentinel.a,
            'properties.foo': sentinel.foo,
            'properties.bar': sentinel.bar,
            'properties.timestamp': '2014-01-10 10:14:00',
            'source': expected_source,
            'raw_format_version_tag': expected_raw_format_version_tag,
            'raw': b'<some body>',
            'csv_raw_rows': BaseParser.CsvRawRows(b'<some body>'),
        })


    def test__get_output_rk(self):
        self.mock.event_type = 'foobar'
        data = {'source': 'provider.channel'}

        output_rk = self.meth.get_output_rk(data)

        self.assertEqual(output_rk, 'foobar.parsed.provider.channel')


    def test__get_output_bodies(self):
        parsed = [
            MagicMock(**{
                '__class__': RecordDict,
                'used_as_context_manager': True,
                'get_ready_json.return_value': f'<here {which} json...>',
            })
            for which in ('first', 'second')
        ]
        self.mock.configure_mock(**{
            'parse.return_value': iter(parsed),
            'get_output_message_id.side_effect': [
                sentinel.msg_A,
                sentinel.msg_B,
            ],
            'setting_error_event_info': MagicMock(),
            'postprocess_parsed.side_effect': (
                lambda data, parsed, total, item_no: parsed
            ),
        })
        seq_mock = FilePagedSequence._instance_mock()

        output_bodies = self.meth.get_output_bodies(sentinel.data, seq_mock)

        self.assertIs(output_bodies, seq_mock)
        self.assertEqual(seq_mock._as_list(), [
            b'<here first json...>',
            b'<here second json...>',
        ])
        self.assertEqual(parsed[0].mock_calls, [
            call.__setitem__('id', sentinel.msg_A),
            call.get_ready_json(),
        ])
        self.assertEqual(parsed[1].mock_calls, [
            call.__setitem__('id', sentinel.msg_B),
            call.get_ready_json(),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.parse(sentinel.data),
            call.get_output_message_id(parsed[0]),
            call.delete_too_long_address(parsed[0]),
            call.get_output_message_id(parsed[1]),
            call.delete_too_long_address(parsed[1]),

            call.setting_error_event_info(parsed[0]),
            call.setting_error_event_info().__enter__(),
            call.postprocess_parsed(sentinel.data,
                                    parsed[0],
                                    2,
                                    item_no=1),
            call.setting_error_event_info().__exit__(None, None, None),

            call.setting_error_event_info(parsed[1]),
            call.setting_error_event_info().__enter__(),
            call.postprocess_parsed(sentinel.data,
                                    parsed[1],
                                    2,
                                    item_no=2),
            call.setting_error_event_info().__exit__(None, None, None),
        ])


    def test__get_output_bodies__with_record_dict_not_used_as_context_manager_raises_error(self):
        self.mock.parse.return_value = iter([
            MagicMock(**{
                '__class__': RecordDict,
                'used_as_context_manager': False,
            })
        ])
        seq_mock = FilePagedSequence._instance_mock()

        with self.assertRaises(AssertionError):
            self.meth.get_output_bodies(sentinel.data, seq_mock)

        self.assertEqual(seq_mock._as_list(), [])
        self.assertEqual(self.mock.method_calls, [
            call.parse(sentinel.data),
        ])


    def test__get_output_bodies__with_parse_yielding_no_items_raises_error(self):
        self.mock.parse.return_value = iter([])
        seq_mock = FilePagedSequence._instance_mock()

        with self.assertRaises(ValueError):
            self.meth.get_output_bodies(sentinel.data, seq_mock)

        self.assertEqual(seq_mock._as_list(), [])
        self.assertEqual(self.mock.method_calls, [
            call.parse(sentinel.data),
        ])


    def test__get_output_bodies__with_parse_yielding_no_items_and_with_allow_empty_results(self):
        self.mock.parse.return_value = iter([])
        self.mock.allow_empty_results = True
        seq_mock = FilePagedSequence._instance_mock()

        output_bodies = self.meth.get_output_bodies(sentinel.data, seq_mock)

        self.assertIs(output_bodies, seq_mock)
        self.assertEqual(seq_mock._as_list(), [])  # just empty
        self.assertEqual(self.mock.mock_calls, [
            call.parse(sentinel.data),
        ])


    @foreach(0, 1, 10, 62, 63)
    def test__delete_too_long_address__address_is_ok(self, ip_count):
        parsed_content = {
            'address': [{'ip': ipv4_to_str(i+1)} for i in range(ip_count)],
            'source': 'just-an-example.unrelated-item',
        }
        expected_parsed_content = copy.deepcopy(parsed_content)
        parsed = RecordDict(parsed_content)

        with patch('n6datasources.parsers.base.LOGGER') as logger_mock:
            self.meth.delete_too_long_address(parsed)

        self.assertEqual(parsed, expected_parsed_content)
        self.assertEqual(logger_mock.warning.mock_calls, [])


    @foreach(64, 65, 100, 1000)
    def test__delete_too_long_address__address_is_too_long(self, ip_count):
        event_id = '0123456789abcdef0123456789abcdef'
        parsed = RecordDict({
            'id': event_id,
            'address': [{'ip': ipv4_to_str(i+1)} for i in range(ip_count)],
            'source': 'just-an-example.unrelated-item',
        })
        expected_parsed_content = {
            'id': event_id,
            'source': 'just-an-example.unrelated-item',
        }

        with patch('n6datasources.parsers.base.LOGGER') as logger_mock:
            self.meth.delete_too_long_address(parsed)

        self.assertEqual(parsed, expected_parsed_content)
        self.assertEqual(logger_mock.warning.mock_calls, [
            call(
                AnyMatchingRegex(r'^Too many IPs in `address`: %s \(event id: %a\),'),
                ip_count,
                event_id,
            ),
        ])


    def test__delete_too_long_address__no_address(self):
        parsed_content = {
            'source': 'just-an-example.unrelated-item',
        }
        expected_parsed_content = copy.deepcopy(parsed_content)
        parsed = RecordDict(parsed_content)

        with patch('n6datasources.parsers.base.LOGGER') as logger_mock:
            self.meth.delete_too_long_address(parsed)

        self.assertEqual(parsed, expected_parsed_content)
        self.assertEqual(logger_mock.warning.mock_calls, [])


    def test__parse__which_raises_not_implemented_error(self):
        with self.assertRaises(NotImplementedError):
            self.meth.parse(sentinel.data)


    # def test__new_record_dict(self):
    #     TODO... See: #8527.


    # def test__handle_parse_error(self):
    #     TODO... See: #8527.


    # def test__handle_parse_error__is_picklable(self):
    #     TODO... See: #8527.


    # def test__set_basic_items(self):
    #     TODO... See: #8527.


    @paramseq
    def _parsed_content_and_expected_hash_base_cases_for__get_output_message_id(self):
        return [
            # basics
            (
                {'source': b'foo.bar'},
                b'source,foo.bar'
            ),
            (
                {'source': 'foo.bar'},
                b'source,foo.bar'
            ),
            # proper sorting of multiple values
            (
                {'key1': 2, 'key2': [b'value2', b'value3', b'value1']},
                b'key1,2\nkey2,value1,value2,value3'
            ),
            # ...and of keys + proper encoding of str keys/values
            (
                {'key2': ['value3', 'value1', 'value2'], 'key1': 2},
                b'key1,2\nkey2,value1,value2,value3'
            ),
            # ...as well as proper int representation
            (
                {'key2': [30, 10, 20], 'key1': 9000111222333444555666777888999000},
                b'key1,9000111222333444555666777888999000\nkey2,10,20,30'
            ),
            # non-ascii values (and even lone surrogates)
            (
                {
                    'target': 'zażółć'.encode('utf-8'),
                    'client': ['jaźń', 'gęślą'],
                    'key1': b'\xed\xb3\x9d',
                },
                'client,gęślą,jaźń\n'.encode('utf-8')
                + b'key1,\xed\xb3\x9d\n'
                + 'target,zażółć'.encode('utf-8')
            ),
            (
                {
                    'target': 'zażółć',
                    'client': ['jaźń'.encode('utf-8'), 'gęślą'.encode('utf-8')],
                    'key1': '\udcdd',
                },
                'client,gęślą,jaźń\n'.encode('utf-8')
                + b'key1,\xed\xb3\x9d\n'
                + 'target,zażółć'.encode('utf-8')
            ),
            # subdicts
            (
                {'dip': '3.3.3.3', 'address': [{'ip': '255.255.255.0'}, {'ip': '127.0.0.1'}]},
                b"address,{'ip': '127.0.0.1'},{'ip': '255.255.255.0'}\ndip,3.3.3.3"
            ),
            # non-ascii subdict keys/values
            (
                {
                    'key2': [{b'k\xc4\x852': b'v\xc4\x852'}, {b'k\xc4\x851': b'v\xc4\x851'}],
                    'key1': {b'k\xc4\x85': b'v\xc4\x85'},
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            # proper encoding of str keys/values + proper sorting of whole subdicts
            (
                {
                    'key1': {'ką': 'vą'},
                    'key2': [{'ką2': 'vą2'}, {'ką1': 'vą1'}],
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            (
                {
                    'key1': {'ką': 'vą'},
                    'key2': [{'ką2': b'v\xc4\x852'}, {'ką1': 'vą1'}],
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            (
                {
                    'key1': {'ką': b'v\xc4\x85'},
                    'key2': [{'ką2': b'v\xc4\x852'}, {b'k\xc4\x851': 'vą1'}],
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            (
                {
                    'key1': {b'k\xc4\x85': 'vą'},
                    'key2': [{b'k\xc4\x852': b'v\xc4\x852'}, {'ką1': 'vą1'}],
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            (
                {
                    'key1': {b'k\xc4\x85': b'v\xc4\x85'},
                    'key2': [{b'k\xc4\x852': b'v\xc4\x852'}, {b'k\xc4\x851': 'vą1'}],
                },
                b"key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n"
                b"key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            # ...as well as proper int representation
            (
                {'key1': {'k': 2}, 'key2': [{b'k2': 2}, {'k1': -1}]},
                b"key1,{'k': 2}\nkey2,{'k1': -1},{'k2': 2}"
            ),
            (
                {'key2': [{b'k2': 2}, {b'k1': 1}], 'key1': {b'k': -3}},
                b"key1,{'k': -3}\nkey2,{'k1': 1},{'k2': 2}"
            ),
            (
                {'key2': [{b'k2': 0}, {b'k1': 1}], 'key1': {b'k': 90001112223334445556667778889}},
                b"key1,{'k': 90001112223334445556667778889}\nkey2,{'k1': 1},{'k2': 0}"
            ),
            # proper sorting of multiple items in subdicts
            (
                {
                    'key1': {b'c': 2, 'a': 3, 'b': 1},
                    'key2': [{b'c': 2, 'a': 3, 'b': 1}, {b'd': 3, 'a': 2, 'b': 1}],
                },
                b"key1,{'a': 3, 'b': 1, 'c': 2}\n"
                b"key2,{'a': 2, 'b': 1, 'd': 3},{'a': 3, 'b': 1, 'c': 2}"
            ),
            # ...and proper escaping (and sorting)
            (
                {
                    'key2': [
                        {b'\'"': '\'"', b'\\': '\\', b'"\'': '"\'', b'\x00': '\n', b'"': '"', b'\'': '\''},            # noqa
                        {'\\': b'\\', '"': b'"', '\'': b'\'', '\x00': b'\n', '\'"': b'\'"', '"\'': b'"\''},            # noqa
                        {b'\r': '\x01', b'"\'': '"\'', '"': b'"', b'\'': '\'', '\'"': b'\'"', '\\': b'\\'},            # noqa
                        {b'"': '"', '\r': b'\x01', '\'': b'\'', b'\\': '\\', b'\'"': '\'"', '"\'': b'"\''},            # noqa
                        {'\'': b'\'', b'\'"': '\'"', '"\'': b'"\'', '"': b'"', b'\r': '\x01', '\\': b'\\'},            # noqa
                    ],
                    'key1': {b'"': '"', b'\'': '\'', b'\'"': '\'"', b'"\'': '"\'', b'\\': '\\', b'\x00': '\n'},        # noqa
                },
                b"key1,"
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\x00': '\\n'}\n"    # noqa
                b"key2,"
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\r': '\\x01'},"     # noqa
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\r': '\\x01'},"     # noqa
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\r': '\\x01'},"     # noqa
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\x00': '\\n'},"     # noqa
                b"{\"'\": \"'\", '\"': '\"', '\"\\'': '\"\\'', '\\'\"': '\\'\"', '\\\\': '\\\\', '\\x00': '\\n'}"      # noqa
            ),
        ]

    @foreach(_parsed_content_and_expected_hash_base_cases_for__get_output_message_id)
    def test__get_output_message_id(self, parsed_content, expected_hash_base):
        class _RecordDict(RecordDict):
            adjust_key1 = adjust_key2 = None
            optional_keys = RecordDict.optional_keys | {'key1', 'key2'}
        parser = BaseParser.__new__(BaseParser)
        record_dict = _RecordDict(parsed_content)
        expected_result = hashlib.md5(expected_hash_base, usedforsecurity=False).hexdigest()

        result = parser.get_output_message_id(record_dict)

        self.assertIsInstance(result, str)
        self.assertEqual(result, expected_result)


    @paramseq
    def _parsed_content_and_exc_class_cases_for__get_output_message_id(self):
        return [
            # bad subdict key type
            (
                {'key1': {32: 2}},
                TypeError,
            ),
            (
                {'key1': [{32: 2}]},
                TypeError,
            ),
            # bad subdict value type
            (
                {'key1': {'k': 2.3}},
                TypeError,
            ),
            (
                {'key1': [{'k': 2.3}]},
                TypeError,
            ),
            (
                {'key1': {'k': {'k': 2}}},  # nesting is illegal
                TypeError,
            ),
            (
                {'key1': [{'k': {'k': 2}}]},  # nesting is illegal
                TypeError,
            ),
            # bad value type
            (
                {'key1': 2.3},
                TypeError,
            ),
            (
                {'key1': [2.3]},
                TypeError,
            ),
            (
                {'key1': [[2]]},  # nesting is illegal
                TypeError,
            ),
        ]

    @foreach(_parsed_content_and_exc_class_cases_for__get_output_message_id)
    def test__get_output_message_id__errors(self, parsed_content, exc_class):
        class _RecordDict(RecordDict):
            adjust_key1 = adjust_key2 = None
            optional_keys = RecordDict.optional_keys | {'key1', 'key2'}
        parser = BaseParser.__new__(BaseParser)
        record_dict = _RecordDict(parsed_content)

        with self.assertRaises(exc_class):
            parser.get_output_message_id(record_dict)


    # def test__iter_output_id_base_items(self):
    #     TODO... See: #8527.
    #   (although it's, to some extent, covered by `test__get_output_message_id()`)


    @foreach(
        param(
            data={
                'raw': b'<...just an example unrelated data item...>',
            },
            expected_content_added_to_parsed={},
        ),
        param(
            data={
                'raw': b'<...just an example unrelated data item...>',
                '_do_not_resolve_fqdn_to_ip': False,
            },
            expected_content_added_to_parsed={},
        ),
        param(
            data={
                'raw': b'<...just an example unrelated data item...>',
                '_do_not_resolve_fqdn_to_ip': True,
            },
            expected_content_added_to_parsed={
                '_do_not_resolve_fqdn_to_ip': True,
            },
        ),
    )
    def test__postprocess_parsed(self, data, expected_content_added_to_parsed):
        parsed_content = {'source': 'just-an-example.unrelated-item'}
        expected_parsed_content = parsed_content | expected_content_added_to_parsed
        parsed = RecordDict(parsed_content)

        self.meth.postprocess_parsed(
            data,
            parsed,
            sentinel.unused,
            item_no=sentinel.unused)

        self.assertEqual(parsed, expected_parsed_content)
        self.assertEqual(self.mock.mock_calls, [])


    # def test__set_proto(self):
    #     TODO... See: #8527.


## TODO... See: #8527.
# class TestSkipParseExceptionsMixin
#     (though at least some parts of `SkipParseExceptionsMixin` are covered by
#   ` Test__get_output_bodies__results_for_various_concrete_parsers()`)


## TODO... See: #8527.
# class TestAggregatedEventParser
#     (though at least some parts of `AggregatedEventParser` are covered by
#   ` Test__get_output_bodies__results_for_various_concrete_parsers()`)


## TODO... See: #8527.
# class TestBlackListParser
#     (though at least some parts of `BlackListParser` are covered by
#   ` Test__get_output_bodies__results_for_various_concrete_parsers()`)


class Test__get_output_bodies__results_for_various_concrete_parsers(TestCaseMixin,
                                                                    unittest.TestCase):

    def setUp(self):
        # (We want to make `LegacyQueuedBase.__new__()`'s stuff isolated
        # from real `sys.argv`...)
        self.patch_argparse_stuff()

        class MyError(Exception):
            pass

        class MyParserMixIn(object):
            constant_items = {
                'restriction': 'need-to-know',
                'confidence': 'low',
                'category': 'malurl',
            }
            def parse(self, data):
                assert isinstance(self, BaseParser)
                for dport in data['raw'].decode('utf-8').split(' '):
                    with self.new_record_dict(data) as parsed:
                        if dport == 'NON-ADJUSTER-ERROR':
                            raise MyError('NON-ADJUSTER-ERROR')
                        parsed['dport'] = dport
                        parsed['time'] = '2014-01-10 10:14:00'
                        yield parsed

        self.MyError = MyError
        self.MyParserMixIn = MyParserMixIn

        self.base_data: dict[str, Any] = {
            'properties.message_id': '0123456789abcdef0123456789abcdef',  # like an md5 hash,
            'source': 'foo.bar',
            'properties.timestamp': '2014-01-10 10:14:00',
        }
        self.common_output_items: dict[str, Any] = dict(
            self.MyParserMixIn.constant_items,
            rid='0123456789abcdef0123456789abcdef',
            time='2014-01-10 10:14:00',
            source='foo.bar',
        )


    def _checks_with_dport_80_1024(self, parser_base_cls, raw,
                                   extra_parser_attrs=None,
                                   extra_input_items=None,
                                   extra_output_items1=None,
                                   extra_output_items2=None):
        if extra_input_items is None:
            extra_input_items = {}
        if extra_output_items1 is None:
            extra_output_items1 = {}
        if extra_output_items2 is None:
            extra_output_items2 = {}
        class MyParser(self.MyParserMixIn, parser_base_cls):
            constant_items = dict(self.MyParserMixIn.constant_items,
                                  **extra_input_items)
        if extra_parser_attrs is not None:
            for k, v in extra_parser_attrs.items():
                setattr(MyParser, k, v)
        parser = MyParser.__new__(MyParser)
        data = dict(self.base_data, raw=raw)
        seq_mock = FilePagedSequence._instance_mock()

        output_bodies = parser.get_output_bodies(data, seq_mock)

        self.assertIs(output_bodies, seq_mock)
        self.assertTrue(all(
            isinstance(body, bytes)
            for body in seq_mock._as_list()))
        output_data = [
            json.loads(body)
            for body in seq_mock._as_list()]
        for d in output_data:
            # check that d['id'] looks like an md5 hash...
            self.assertIsInstance(d.get('id'), str)
            self.assertEqual(len(d['id']), 32)
            self.assertTrue(set('0123456789abcdef').issuperset(d['id']))
            # ...then omit d['id'] for simplicity of the test
            del d['id']
        self.assertEqual(output_data, [
            dict(self.common_output_items, dport=80, **extra_output_items1),
            dict(self.common_output_items, dport=1024, **extra_output_items2),
        ])


    def _checks_with_loud_error_expected(self, parser_base_cls, error_cls, raw,
                                         extra_parser_attrs=None,
                                         required_error_attrs=None):
        class MyParser(self.MyParserMixIn, parser_base_cls):
            pass
        if extra_parser_attrs is not None:
            for k, v in extra_parser_attrs.items():
                setattr(MyParser, k, v)
        parser = MyParser.__new__(MyParser)
        data = dict(self.base_data, raw=raw)

        with self.assertRaises(error_cls) as cm:
            parser.get_output_bodies(data, FilePagedSequence._instance_mock())

        if required_error_attrs is not None:
            self.assertTrue(vars(cm.exception).items() >=
                            required_error_attrs.items())


    # BaseParser subclasses

    def test_BaseParser_subclass(self):
        # normal (no error)
        self._checks_with_dport_80_1024(
            BaseParser,
            raw=b'80 1024')

        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        # NOTE: it's *silenced* for non-blacklist events
        self._checks_with_dport_80_1024(
            BaseParser,
            raw=b'80 ADJUSTER-ERROR 1024')


    def test_BaseParser_subclass__not_silenced_error(self):
        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._checks_with_loud_error_expected(
            BaseParser,
            error_cls=self.MyError,
            raw=b'80 NON-ADJUSTER-ERROR 1024')


    def test_SkipParseExceptionsMixin_and_BaseParser_subclass(self):
        class ExceptionSilencingParser(SkipParseExceptionsMixin, BaseParser):
            pass

        # normal (no error)
        self._checks_with_dport_80_1024(
            ExceptionSilencingParser,
            raw=b'80 1024')

        # silenced data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        self._checks_with_dport_80_1024(
            ExceptionSilencingParser,
            raw=b'80 ADJUSTER-ERROR 1024')

        # silenced non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._checks_with_dport_80_1024(
            ExceptionSilencingParser,
            raw=b'80 NON-ADJUSTER-ERROR 1024')


    # AggregatedEventParser subclasses

    def test_AggregatedEventParser_subclass(self):
        # normal (no error)
        self._checks_with_dport_80_1024(
            AggregatedEventParser,
            raw=b'80 1024',
            extra_parser_attrs={
                'group_id_components': ['dport', 'time', 'not-found'],
            },
            extra_output_items1={
                '_group': '80_2014-01-10 10:14:00_None',
            },
            extra_output_items2={
                '_group': '1024_2014-01-10 10:14:00_None',
            })

        self._checks_with_dport_80_1024(
            AggregatedEventParser,
            raw=b'80 1024',
            extra_parser_attrs={
                'group_id_components': 'dport',  # single string is also OK
            },
            extra_output_items1={
                '_group': '80',
            },
            extra_output_items2={
                '_group': '1024',
            })

        self._checks_with_dport_80_1024(
            AggregatedEventParser,
            raw=b'80 1024',
            extra_parser_attrs={
                'group_id_components': ('ip', 'dport'),  # 'ip' means address[0]['ip']
            },
            extra_input_items={
                'address': {'ip': '11.22.33.44'},
            },
            extra_output_items1={
                'address': [{'ip': '11.22.33.44'}],
                '_group': '11.22.33.44_80',
            },
            extra_output_items2={
                'address': [{'ip': '11.22.33.44'}],
                '_group': '11.22.33.44_1024',
            })

        self._checks_with_dport_80_1024(
            AggregatedEventParser,
            raw=b'80 1024',
            extra_parser_attrs={
                'group_id_components': ('ip', 'dport'),
            },
            # ip not given
            extra_output_items1={
                '_group': 'None_80',
            },
            extra_output_items2={
                '_group': 'None_1024',
            })

        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        # NOTE: it's *silenced* for non-blacklist events
        self._checks_with_dport_80_1024(
            AggregatedEventParser,
            raw=b'80 ADJUSTER-ERROR 1024',
            extra_parser_attrs={
                'group_id_components': ['ip', 'dport'],
            },
            extra_output_items1={
                '_group': 'None_80',
            },
            extra_output_items2={
                '_group': 'None_1024',
            })


    def test_AggregatedEventParser_subclass__not_silenced_error(self):
        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._checks_with_loud_error_expected(
            AggregatedEventParser,
            error_cls=self.MyError,
            raw=b'80 NON-ADJUSTER-ERROR 1024')

        # error raised in postprocess_data() due to lack of values
        # the '_group' value could be made of
        self._checks_with_loud_error_expected(
            AggregatedEventParser,
            error_cls=ValueError,
            raw=b'80 1024',
            extra_parser_attrs={
                'group_id_components': ['not-found', 'dip'],
            },
            required_error_attrs={
                '_n6_event_rid': '0123456789abcdef0123456789abcdef',
                '_n6_event_id': ANY,
            })


    # BlackListParser subclasses

    def test_BlackListParser_subclass(self):
        # normal (no error)
        self._checks_with_dport_80_1024(
            BlackListParser,
            raw=b'80 1024',
            extra_input_items={'expires': '2014-02-28 10:00:00'},  # obligatory for blacklists
            extra_output_items1={
                '_bl-series-id': '0123456789abcdef0123456789abcdef',
                '_bl-series-total': 2,
                '_bl-series-no': 1,
                '_bl-time': '2014-01-10 10:14:00',
                '_bl-current-time': self.base_data['properties.timestamp'],
                'expires': '2014-02-28 10:00:00',
            },
            extra_output_items2={
                '_bl-series-id': '0123456789abcdef0123456789abcdef',
                '_bl-series-total': 2,
                '_bl-series-no': 2,
                '_bl-time': '2014-01-10 10:14:00',
                '_bl-current-time': self.base_data['properties.timestamp'],
                'expires': '2014-02-28 10:00:00',
            })


    def test_BlackListParser_subclass__not_silenced_error(self):
        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        self._checks_with_loud_error_expected(
            BlackListParser,
            error_cls=AdjusterError,
            raw=b'80 ADJUSTER-ERROR 1024')

        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._checks_with_loud_error_expected(
            BlackListParser,
            error_cls=self.MyError,
            raw=b'80 NON-ADJUSTER-ERROR 1024')


    # some wrong BaseParser/AggregatedEventParser/BlackListParser subclasses...

    def test_record_dict_context_manager_not_used(self):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    for dport in data['raw'].decode('utf-8').split(' '):
                        # lacking 'with...' statement:
                        parsed = self.new_record_dict(data)
                        parsed['dport'] = dport
                        parsed['time'] = '2014-01-10 11:14:00.248114'
                        yield parsed
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw=b'80 1024')
            with self.assertRaisesRegex(AssertionError, r'record dict yielded in a parser must be '
                                                        r'treated with a "with \.\.\." statement'):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())


    def test_record_dict_context_manager_used_more_than_once(self):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    for dport in data['raw'].decode('utf-8').split(' '):
                        # two 'with...' statements for the same record dict:
                        with self.new_record_dict(data) as parsed:
                            parsed['dport'] = dport
                        with parsed:
                            parsed['time'] = '2014-01-10 11:14:00.248114'
                            yield parsed
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw=b'80 1024')
            with self.assertRaisesRegex(TypeError, r'a record dict instance cannot be used as '
                                                   r'a guarding context manager more than once'):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())


    # some other errors...

    def test__parse__yielded_no_items(self):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    return  # "empty" generator
                    yield  # noqa
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw=b'80 1024')
            with self.assertRaisesRegex(ValueError, r'no output data to publish'):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())


## TODO... See: #8527.
# class Test__add_parser_entry_point_functions

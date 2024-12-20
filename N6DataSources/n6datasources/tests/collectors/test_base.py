# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
import hashlib
import os
import os.path as osp
import pickle
import re
import shutil
import sys
import tempfile
import traceback
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import (
    ANY,
    MagicMock,
    call,
    Mock,
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
from n6lib.common_helpers import PlainNamespace
from n6lib.config import (
    Config,
    ConfigError,
    ConfigMixin,
    ConfigSection,
    ConfigSpecEgg,
    ConfigSpecEggError,
    NoConfigSectionError,
    as_config_spec_string,
    combined_config_spec,
    parse_config_spec,
)
from n6lib.csv_helpers import extract_field_from_csv_row
from n6datapipeline.base import LegacyQueuedBase
from n6datasources.collectors.base import (
    AbstractBaseCollector,
    BaseCollector,
    BaseDownloadingCollector,
    BaseSimpleCollector,
    BaseSimpleEmailCollector,
    BaseTimeOrderedRowsCollector,
    BaseTwoPhaseCollector,
    CollectorConfigMixin,
    StatefulCollectorMixin,
    add_collector_entry_point_functions,
)
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyCallableNamed,
    AnyInstanceOf,
    AnyMatchingRegex,
    TestCaseMixin,
)


SAMPLE_ARG_A = sentinel.a
SAMPLE_ARG_B = sentinel.b
SAMPLE_ARG_C = sentinel.c
SAMPLE_ARG_D = sentinel.d


example_valid_raw_type_and_content_type_cases = [
    # (each value is a `(<collector's *raw_type*>, <collector's *content_type*>)` tuple)
    param(raw_type_and_content_type=('stream', None)),
    param(raw_type_and_content_type=('file', 'application/jwt')),
    param(raw_type_and_content_type=('blacklist', 'text/csv')),
]


@expand
class TestAbstractBaseCollector(TestCaseMixin, unittest.TestCase):

    def test_not_being_a_subclass_of_related_n6_classes(self):
        self.assertFalse(issubclass(AbstractBaseCollector, BaseCollector))
        self.assertFalse(issubclass(AbstractBaseCollector, LegacyQueuedBase))
        self.assertFalse(issubclass(AbstractBaseCollector, CollectorConfigMixin))


    def test_defined_public_method_names(self):
        method_names = {
            name for name, obj in vars(AbstractBaseCollector).items()
            if (isinstance(obj, (Callable, classmethod, staticmethod))
                and not name.startswith('_'))}

        self.assertEqual(method_names, {
            'run_script',
            'get_script_init_kwargs',
            'run_collection',
            'run',
            'stop',
            'after_completed_publishing',
        })


    def test__run_script(self):
        method = AbstractBaseCollector.run_script
        func = self.check_and_extract_func_from_class_method(method)
        rec = MagicMock()
        rec.cls.get_script_init_kwargs.return_value = script_init_kwargs = {'a': SAMPLE_ARG_A}
        with patch('n6datasources.collectors.base.logging_configured', rec.logging_configured):

            result = func(rec.cls)

        self.assertIsNone(result)
        self.assertEqual(rec.mock_calls, [
            call.logging_configured(),
            call.logging_configured().__enter__(),
            call.cls.get_script_init_kwargs(),
            call.cls(**script_init_kwargs),
            call.cls().run_collection(),
            call.logging_configured().__exit__(None, None, None),
        ])


    def test__get_script_init_kwargs(self):
        method = AbstractBaseCollector.get_script_init_kwargs
        func = self.check_and_extract_func_from_class_method(method)
        rec = MagicMock()

        result = func(rec.cls)

        self.assertIsInstance(result, dict)
        self.assertEqual(result, {})
        self.assertEqual(rec.mock_calls, [])


    def test__run_collection(self):
        collector_mock = Mock(__class__=AbstractBaseCollector)

        AbstractBaseCollector.run_collection(collector_mock)

        self.assertEqual(collector_mock.mock_calls, [
            call.run(),
            call.after_completed_publishing(),
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
    def test__run_collection__with_run_method_raising_keyboard_interrupt(self,
                                                                         exc_from_stop,
                                                                         expected_exc_class):
        collector_mock = Mock(
            __class__=AbstractBaseCollector,
            run=Mock(side_effect=KeyboardInterrupt),
            stop=Mock(side_effect=exc_from_stop))

        with self.assertRaises(expected_exc_class):
            AbstractBaseCollector.run_collection(collector_mock)

        self.assertEqual(collector_mock.mock_calls, [
            call.run(),
            call.stop(),
        ])


    @foreach(
        ValueError('spam'),
        SystemExit('Woops!'),
    )
    def test__run_collection__with_run_method_raising_another_exception(self, exc_from_run):
        collector_mock = Mock(
            __class__=AbstractBaseCollector,
            run=Mock(side_effect=exc_from_run))

        with self.assertRaises(type(exc_from_run)):
            AbstractBaseCollector.run_collection(collector_mock)

        self.assertEqual(collector_mock.mock_calls, [
            call.run(),
        ])


    def test__after_completed_publishing(self):
        collector_mock = Mock(__class__=AbstractBaseCollector)

        AbstractBaseCollector.after_completed_publishing(collector_mock)

        self.assertEqual(collector_mock.mock_calls, [])


    @foreach(
        'run',
        'stop'
    )
    def test_abstract_methods_raise_not_implemented_error(self, method_name):
        func = getattr(AbstractBaseCollector, method_name)
        collector_mock = Mock(__class__=AbstractBaseCollector)

        with self.assertRaises(NotImplementedError):
            func(collector_mock)

        self.assertEqual(collector_mock.mock_calls, [])


@expand
class TestBaseCollector(TestCaseMixin, unittest.TestCase):

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
            'n6datasources.collectors.base.super',
            return_value=self.super_obj_stub)

        # Note: in tests that make use of `self.config_patcher`,
        # `self.config_files_mocked_data` needs to be a dict that maps
        # config section names to dicts mapping option names to their
        # values.
        self.config_files_mocked_data = None
        self.config_patcher = patch(
            'n6lib.config.Config._load_n6_config_files',
            side_effect=lambda *_: dict(self.config_files_mocked_data))


    def _assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(self, owner):
        collector_class_name = get_class_name(owner)
        config_spec_pattern = owner.config_spec_pattern
        try:
            config_spec = as_config_spec_string(
                config_spec_pattern,
                format_data_mapping=dict(collector_class_name=collector_class_name))
            config_spec_parsed = parse_config_spec(config_spec)
            [_main_sect_spec] = [
                sect_spec for sect_spec in config_spec_parsed.get_all_sect_specs()
                if sect_spec.name == collector_class_name]
        except Exception:  # noqa
            self.fail(
                f'could not extract the main collector config section '
                f'from {config_spec_pattern=!a} - the following error '
                f'occurred:\n{traceback.format_exc()}')
        else:
            self.assertIsInstance(config_spec_pattern, (str, ConfigSpecEgg))


    #
    # Actual tests

    def test_superclasses(self):
        self.assertTrue(issubclass(BaseCollector, CollectorConfigMixin))
        self.assertTrue(issubclass(BaseCollector, ConfigMixin))
        self.assertTrue(issubclass(BaseCollector, LegacyQueuedBase))
        self.assertTrue(issubclass(BaseCollector, AbstractBaseCollector))


    @foreach(
        # Note: these are only selected ones.
        'rabbitmq_config_section',
        'basic_prop_kwargs',
        '__new__',
        'run',
        'stop',
        'publish_output',
        'start_iterative_publishing',
        'FLUSH_OUT',
        'PubIter',
        'PubIterFlushOut',
    )
    def test_most_important_stuff_inherited_from_LegacyQueuedBase(self, name):
        here = getattr(BaseCollector, name)
        there = getattr(LegacyQueuedBase, name)

        self.assertIs(here, there)


    @foreach(
        'run_script',
        'get_script_init_kwargs',
    )
    def test_class_methods_inherited_from_AbstractBaseCollector(self, method_name):
        method_here = getattr(BaseCollector, method_name)
        method_there = getattr(AbstractBaseCollector, method_name)
        func_here = self.check_and_extract_func_from_class_method(method_here)
        func_there = self.check_and_extract_func_from_class_method(method_there)

        self.assertIs(func_here, func_there)


    @foreach(
        'run_collection',
        'after_completed_publishing',
    )
    def test_other_methods_inherited_from_AbstractBaseCollector(self, method_name):
        func_here = getattr(BaseCollector, method_name)
        func_there = getattr(AbstractBaseCollector, method_name)

        self.assertIs(func_here, func_there)


    def test_class_attr_values(self):
        self.assertIsInstance(BaseCollector.config_spec_pattern, ConfigSpecEgg)
        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(BaseCollector)
        self.assertIsNone(BaseCollector.input_queue)
        self.assertEqual(BaseCollector.output_queue, {'exchange': 'raw', 'exchange_type': 'topic'})
        self.assertIsNone(BaseCollector.raw_format_version_tag)
        self.assertIsNone(BaseCollector.raw_type)
        self.assertIsNone(BaseCollector.content_type)
        self.assertFalse(BaseCollector.supports_n6recovery)
        self.assertEqual(BaseCollector.unsupported_class_attributes, {
            'default_converter',
            'config_required',
            'config_group',
            'config_spec',
            'source_config_section',
            'type',
            'run_handling',
            'get_source_channel',
        })


    def test_subclassing_with_stream_raw_type(self):
        class SomeCollector(BaseCollector):  # noqa
            raw_type = 'stream'

        self.assertIsInstance(SomeCollector.config_spec_pattern, ConfigSpecEgg)
        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(SomeCollector)
        self.assertIsNone(SomeCollector.input_queue)
        self.assertEqual(SomeCollector.output_queue, {'exchange': 'raw', 'exchange_type': 'topic'})
        self.assertIsNone(SomeCollector.raw_format_version_tag)
        self.assertEqual(SomeCollector.raw_type, 'stream')
        self.assertIsNone(SomeCollector.content_type)
        self.assertFalse(SomeCollector.supports_n6recovery)
        self.assertEqual(SomeCollector.unsupported_class_attributes, {
            'default_converter',
            'config_required',
            'config_group',
            'config_spec',
            'source_config_section',
            'type',
            'run_handling',
            'get_source_channel',
        })


    @foreach(
        'file',
        'blacklist',
    )
    def test_subclassing_with_non_stream_raw_type(self, raw_tp):
        content_tp = 'text/csv'

        class SomeCollector(BaseCollector):  # noqa
            raw_type = raw_tp
            content_type = content_tp

        self.assertIsInstance(SomeCollector.config_spec_pattern, ConfigSpecEgg)
        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(SomeCollector)
        self.assertIsNone(SomeCollector.input_queue)
        self.assertEqual(SomeCollector.output_queue, {'exchange': 'raw', 'exchange_type': 'topic'})
        self.assertIsNone(SomeCollector.raw_format_version_tag)
        self.assertEqual(SomeCollector.raw_type, raw_tp)
        self.assertEqual(SomeCollector.content_type, content_tp)
        self.assertFalse(SomeCollector.supports_n6recovery)
        self.assertEqual(SomeCollector.unsupported_class_attributes, {
            'default_converter',
            'config_required',
            'config_group',
            'config_spec',
            'source_config_section',
            'type',
            'run_handling',
            'get_source_channel',
        })


    def test_subclassing_with_no_raw_type_causes_error(self):
        expected_error_regex = r'attribute `raw_type` is not set'

        with self.assertRaisesRegex(NotImplementedError, expected_error_regex):
            class SomeCollector(BaseCollector):  # noqa
                pass


    def test_subclassing_with_illegal_raw_type_causes_error(self):
        expected_error_regex = (
            r"attribute `raw_type` should be one of: "
            r"'stream', 'file', 'blacklist'")

        with self.assertRaisesRegex(ValueError, expected_error_regex):
            class SomeCollector(BaseCollector):  # noqa
                raw_type = 'illegal-raw-type'


    @foreach(
        'file',
        'blacklist',
    )
    def test_subclassing_with_non_stream_raw_type_and_no_content_type_causes_error(self, raw_tp):
        expected_error_regex = (
            r'attribute `raw_type` is .* '
            r'so `content_type` should be .* non-None value')

        with self.assertRaisesRegex(NotImplementedError, expected_error_regex):
            class SomeCollector(BaseCollector):  # noqa
                raw_type = raw_tp


    @foreach(
        'stream',
        'file',
        'blacklist',
    )
    @foreach(
        param(use_combined_config_spec=False),
        param(use_combined_config_spec=True),
    )
    def test_subclassing_with_more_cls_attr_customization(self, raw_tp, use_combined_config_spec):
        content_tp = 'text/csv'
        output_qu = {'exchange': 'awantury-i-wybryki', 'exchange_type': 'direct'}
        raw_format_vt = '202207'
        config_spec_pattern_custom_content = '''
            [{collector_class_name}]
            foo = False :: bool
            bar :: int
        '''

        class SomeCollector(BaseCollector):  # noqa
            config_spec_pattern = (
                combined_config_spec(config_spec_pattern_custom_content)
                if use_combined_config_spec else config_spec_pattern_custom_content)
            output_queue = output_qu
            raw_format_version_tag = raw_format_vt
            raw_type = raw_tp
            content_type = content_tp  # (for raw_type='stream' it's *not* forbidden, just ignored)

        self.assertIsInstance(SomeCollector.config_spec_pattern, (
                ConfigSpecEgg if use_combined_config_spec else str))
        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(SomeCollector)
        self.assertIsNone(SomeCollector.input_queue)
        self.assertEqual(SomeCollector.output_queue, output_qu)
        self.assertEqual(SomeCollector.raw_format_version_tag, raw_format_vt)
        self.assertEqual(SomeCollector.raw_type, raw_tp)
        self.assertEqual(SomeCollector.content_type, content_tp)


    @foreach(
        'stream',
        'file',
        'blacklist',
    )
    @foreach(
        param(attr_names=[
            'default_converter',
        ]),
        param(attr_names=[
            'config_required',
        ]),
        param(attr_names=[
            'config_group',
        ]),
        param(attr_names=[
            'config_spec',
        ]),
        param(attr_names=[
            'source_config_section',
        ]),
        param(attr_names=[
            'get_source_channel',
        ]),
        param(attr_names=[
            'run_handling',
        ]),
        param(attr_names=[
            'type',
        ]),
        param(attr_names=[
            'default_converter',
            'config_required',
        ]),
        param(attr_names=[
            'config_required',
            'config_group',
            'config_spec',
        ]),
        param(attr_names=[
            'config_spec',
            'source_config_section',
            'type',
            'run_handling',
            'get_source_channel',
        ]),
        param(attr_names=[
            'default_converter',
            'config_required',
            'config_group',
            'config_spec',
            'source_config_section',
            'type',
            'run_handling',
            'get_source_channel',
        ]),
    )
    def test_subclassing_with_no_longer_supported_cls_attr_causes_error(self, raw_tp, attr_names):
        expected_error_regex = (
            r'unsupported attributes .* set to non-None values: '
            + ', '.join(map(repr, sorted(attr_names))))

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            class SomeCollector(BaseCollector):  # noqa
                config_spec_pattern = '''
                    [{collector_class_name}]
                    foo = False :: bool
                    bar :: int
                '''
                raw_type = raw_tp
                content_type = 'text/csv'
                locals().update(
                    (unsupported_name, sentinel.irrelevant_value)
                    for unsupported_name in attr_names)

        # (test's self-test assertion)
        assert set(attr_names) <= BaseCollector.unsupported_class_attributes


    @foreach(example_valid_raw_type_and_content_type_cases)
    @foreach(
        param(use_combined_config_spec=False),
        param(use_combined_config_spec=True),   # (preferred in real code)
    )
    @foreach(
        param(
            config_spec_pattern_custom_content=None,
            config_files_mocked_data={
                'unrelated_irrelevant_section': {
                    'foo': 'ABCDEF',
                    'another': 'GHIJKL',
                },
            },
            expected_config=ConfigSection('SomeCollector', {}),
            expected_config_full=Config.make({'SomeCollector': {}}),
        ).label('no config spec pattern customization, irrelevant data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
            ''',
            config_files_mocked_data={},
            expected_config=ConfigSection('SomeCollector', {}),
            expected_config_full=Config.make({'SomeCollector': {}}),
        ).label('minimal config spec pattern (effectively no customization), no data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required = 123 :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={},
            expected_config=ConfigSection('SomeCollector', {
                'required': 123,
                'another': True,
            }),
            expected_config_full=Config.make({'SomeCollector': {
                'required': 123,
                'another': True,
            }}),
        ).label('customized config spec pattern with only main section, no data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={
                'SomeCollector': {
                    'required': '42',
                },
                'unrelated_irrelevant_section': {
                    'foo': 'ABCDEF',
                    'another': 'GHIJKL',
                },
            },
            expected_config=ConfigSection('SomeCollector', {
                'required': 42,
                'another': True,
            }),
            expected_config_full=Config.make({'SomeCollector': {
                'required': 42,
                'another': True,
            }}),
        ).label('customized config spec pattern with only main section, some data from files'),

        param(
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required = 123 :: int
                another = yes :: bool

                [another_section]
                foo :: list_of_float
                from = 2010-07-19 12:39:45+02:00 :: datetime
                until = 2022-07-23 :: date
                ...  ; making arbirary option names legal

                [yet_another_section]
                some = Ala ma kota! :: str

                [yet_yet_another_section]
                some = A kot ma Alę! :: str
            ''',
            config_files_mocked_data={
                'SomeCollector': {
                    'required': '42',
                    'another': 'OFF',
                },
                'another_section': {
                    'foo': '42,43,44.12345',
                    'until': '2022-08-04',
                    'another': 'GHIJKL',
                    'yet_another': '42',
                },
                'yet_another_section': {},
                # (no 'yet_yet_another_section' key)
            },
            expected_config=ConfigSection('SomeCollector', {
                'required': 42,
                'another': False,
            }),
            expected_config_full=Config.make({
                'SomeCollector': {
                    'required': 42,
                    'another': False,
                },
                'another_section': {
                    'foo': [42.0, 43.0, 44.12345],
                    'from': datetime.datetime(2010, 7, 19, 10, 39, 45),
                    'until': datetime.date(2022, 8, 4),
                    'another': 'GHIJKL',
                    'yet_another': '42',
                },
                'yet_another_section': {
                    'some': 'Ala ma kota!',
                },
                'yet_yet_another_section': {
                    'some': 'A kot ma Alę!',
                },
            }),
        ).label('customized config spec pattern with a few sections...'),
    )
    def test_instantiation(self,
                           raw_type_and_content_type,
                           use_combined_config_spec,
                           config_spec_pattern_custom_content,
                           config_files_mocked_data,
                           expected_config,
                           expected_config_full):

        if config_spec_pattern_custom_content is None:
            class SomeCollector(BaseCollector):  # noqa
                raw_type, content_type = raw_type_and_content_type
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec('')
        else:
            class SomeCollector(BaseCollector):  # noqa
                raw_type, content_type = raw_type_and_content_type
                if use_combined_config_spec:
                    config_spec_pattern = combined_config_spec(config_spec_pattern_custom_content)
                else:
                    config_spec_pattern = config_spec_pattern_custom_content

        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(SomeCollector)

        self.super_obj_stub.__init__ = super_init_mock = Mock()
        self.config_files_mocked_data = config_files_mocked_data
        with patch('n6lib.config.LOGGER'), \
             self.super_patcher as super_mock, \
             self.config_patcher:

            instance = SomeCollector(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        self.assertIsInstance(instance, SomeCollector)
        super_mock.assert_called_once_with()
        super_init_mock.assert_called_once_with(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)
        self.assertEqual(instance.config, expected_config)
        self.assertIsInstance(instance.config, ConfigSection)
        self.assertEqual(instance.config_full, expected_config_full)
        self.assertIsInstance(instance.config_full, Config)

        self._assert_config_spec_pattern_is_str_or_egg_containing_basic_stuff(instance)


    @foreach(example_valid_raw_type_and_content_type_cases)
    @foreach(
        # Note: in the first three `param()` objects we need to set the
        # test parameter `use_combined_config_spec` to these particular
        # values (in particular, in the first `param()` we need to set
        # that parameter to *false*, because here we want to test the
        # case when the config spec pattern does *not* include the
        # `[{collector_class_name}]` section header -- whereas
        # using `combined_config_spec()` would make the header be
        # automatically inherited from the config spec pattern of
        # the base collector class). For the rest of the following
        # `param()` objects there are no such needs, so we just set
        # `use_combined_config_spec` to `True` and `False` alternately.
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
                [{collector_class_name}]
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
                [{collector_class_name}]
            ''',
            config_files_mocked_data={
                'SomeCollector': {'illegal_opt': 'whatever'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: illegal option name in main section'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                some_number :: float
            ''',
            config_files_mocked_data={
                'SomeCollector': {'some_number': 'not-a-number'}
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: invalid option value in main section'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={
                'SomeCollector': {
                    # (no 'required' key, which is a required option name)
                    'another': 'no',
                },
            },
            expected_exc=ConfigError,
        ).label('wrong config files data: missing option required in main section'),

        param(
            use_combined_config_spec=False,
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required :: int
                another = yes :: bool
            ''',
            config_files_mocked_data={},
            expected_exc=ConfigError,
        ).label('wrong config files data: missing option required in main section + no section'),

        param(
            use_combined_config_spec=True,
            config_spec_pattern_custom_content='''
                [{collector_class_name}]
                required :: int
                another = yes :: bool

                [another_section]
                foo :: list_of_float
                from = 2010-07-19 12:39:45+02:00 :: datetime
                until = 2022-07-23 :: date
            ''',
            config_files_mocked_data={
                'SomeCollector': {
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
                                                                raw_type_and_content_type,
                                                                use_combined_config_spec,
                                                                config_spec_pattern_custom_content,
                                                                config_files_mocked_data,
                                                                expected_exc):
        class SomeCollector(BaseCollector):  # noqa
            raw_type, content_type = raw_type_and_content_type
            config_spec_pattern = (
                combined_config_spec(config_spec_pattern_custom_content)
                if use_combined_config_spec else config_spec_pattern_custom_content)

        self.config_files_mocked_data = config_files_mocked_data
        with patch('n6lib.config.LOGGER'), \
             patch('sys.stderr'), \
             self.super_patcher, \
             self.config_patcher:

            with self.assertRaises(expected_exc) as exc_context:
                SomeCollector(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        if expected_exc is ConfigError:
            # (expecting not just any subclass of `ConfigError`
            # but exactly this type of exception)
            self.assertIs(type(exc_context.exception), expected_exc)


    # TODO: tests of *configurable pipeline*-related stuff... See: #8518.


    @foreach(
        param(
            given_config=ConfigSection('SomeCollector', {}),
            given_params_dict={},
            expected_final_params_dict={},
        ),
        param(
            given_config=ConfigSection('SomeCollector', {'heartbeat_interval': 42}),
            given_params_dict={},
            expected_final_params_dict={'heartbeat_interval': 42},
        ),
        param(
            given_config=ConfigSection('SomeCollector', {}),
            given_params_dict={'existing_unrelated_param': sentinel.some_param_value},
            expected_final_params_dict={'existing_unrelated_param': sentinel.some_param_value},
        ),
        param(
            given_config=ConfigSection('SomeCollector', {'heartbeat_interval': 42}),
            given_params_dict={'existing_unrelated_param': sentinel.some_param_value},
            expected_final_params_dict={
                'existing_unrelated_param': sentinel.some_param_value,
                'heartbeat_interval': 42,
            },
        ),
    )
    @foreach(
        param(given_config_extra_options={}),
        param(given_config_extra_options={'unrelated_option': sentinel.irrelevant}),
    )
    def test__update_connection_params_dict_before_run(self,
                                                       given_config,
                                                       given_config_extra_options,
                                                       given_params_dict,
                                                       expected_final_params_dict):
        collector_stub = PlainNamespace(config=(given_config | given_config_extra_options))
        params_dict = given_params_dict.copy()
        params_passed_to_super_meth = []
        def super_meth_spy(params_dict):  # noqa
            params_passed_to_super_meth.append(params_dict.copy())
        self.super_obj_stub.update_connection_params_dict_before_run = super_meth_spy
        with self.super_patcher as super_mock:

            BaseCollector.update_connection_params_dict_before_run(
                collector_stub,  # noqa
                params_dict)

        super_mock.assert_called_once_with()
        self.assertEqual(params_passed_to_super_meth, [given_params_dict])
        self.assertEqual(params_dict, expected_final_params_dict)


    def test__get_output_components(self):
        source = sentinel.source
        rk = sentinel.rk
        data_body = sentinel.data_body
        prop_kwargs = sentinel.output_prop_kwargs
        collector_mock = Mock(
            __class__=BaseCollector,
            process_input_data=Mock(return_value=dict(
                # Note: in subclasses the method `process_input_data()`
                # may return different data than the received input data
                # -- that's why here we return something different from
                # `dict(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)` -- even though
                # the `BaseCollector`'s version of this method returns
                # exactly the same input data it received (see below:
                # `test__process_input_data()` -- where that default
                # behavior provided by `BaseCollector` is tested).
                ccc=SAMPLE_ARG_C,
                dddd=SAMPLE_ARG_D,
            )),
            get_source=Mock(return_value=source),
            validate_source=Mock(return_value=None),

            get_output_rk=Mock(return_value=rk),
            validate_output_rk=Mock(return_value=None),

            get_output_data_body=Mock(return_value=data_body),
            validate_output_data_body=Mock(return_value=None),

            get_output_prop_kwargs=Mock(return_value=prop_kwargs),
            validate_output_prop_kwargs=Mock(return_value=None),
        )

        output_rk, output_data_body, output_prop_kwargs = BaseCollector.get_output_components(
            collector_mock,
            a=SAMPLE_ARG_A,
            bb=SAMPLE_ARG_B)

        self.assertEqual(collector_mock.mock_calls, [
            call.process_input_data(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B),
            call.get_source(
                ccc=SAMPLE_ARG_C,
                dddd=SAMPLE_ARG_D,
            ),
            call.validate_source(source),
            call.get_output_rk(
                source=source,
                ccc=SAMPLE_ARG_C,
                dddd=SAMPLE_ARG_D,
            ),
            call.validate_output_rk(rk),
            call.get_output_data_body(
                source=source,
                ccc=SAMPLE_ARG_C,
                dddd=SAMPLE_ARG_D,
            ),
            call.validate_output_data_body(data_body),
            call.get_output_prop_kwargs(
                source=source,
                output_data_body=data_body,
                ccc=SAMPLE_ARG_C,
                dddd=SAMPLE_ARG_D,
            ),
            call.validate_output_prop_kwargs(prop_kwargs),
        ])
        self.assertIs(output_rk, rk)
        self.assertIs(output_data_body, data_body)
        self.assertIs(output_prop_kwargs, prop_kwargs)


    def test__process_input_data(self):
        collector_stub = PlainNamespace()
        input_data = dict(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

        processed_data = BaseCollector.process_input_data(collector_stub, **input_data)  # noqa

        self.assertEqual(processed_data, input_data)


    def test__get_source__which_raises_not_implemented_error(self):
        collector_stub = PlainNamespace()

        with self.assertRaises(NotImplementedError):
            BaseCollector.get_source(
                collector_stub,  # noqa
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)


    def test__get_output_rk(self):
        source = 'my-src-provider.my-src-channel'
        collector_stub = PlainNamespace(raw_format_version_tag=None)

        output_rk = BaseCollector.get_output_rk(
            collector_stub,  # noqa
            source=source,
            a=SAMPLE_ARG_A,
            bb=SAMPLE_ARG_B)

        self.assertEqual(output_rk, source)


    def test__get_output_rk__with_raw_format_version_tag_present(self):
        source = 'my-src-provider.my-src-channel'
        collector_stub = PlainNamespace(raw_format_version_tag='202207')  # noqa

        output_rk = BaseCollector.get_output_rk(
            collector_stub,  # noqa
            source=source,
            a=SAMPLE_ARG_A,
            bb=SAMPLE_ARG_B)

        self.assertEqual(output_rk, source + '.202207')


    def test__get_output_data_body__which_raises_not_implemented_error(self):
        collector_stub = PlainNamespace()

        with self.assertRaises(NotImplementedError):
            BaseCollector.get_output_data_body(
                collector_stub,  # noqa
                source=sentinel.source,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)


    @foreach(
        param(content_type=None),
        param(content_type='whatever/ignored-anyway'),
    )
    def test__get_output_prop_kwargs__with_stream_raw_type(self, content_type):
        raw_type = 'stream'
        message_id = sentinel.message_id
        collector_mock = Mock(
            __class__=BaseCollector,
            raw_type=raw_type,
            content_type=content_type,
            get_output_message_id=Mock(return_value=message_id),
            _validate_source_type_related_attributes=Mock(
                wraps=BaseCollector._validate_source_type_related_attributes))
        source = sentinel.source
        output_data_body = sentinel.output_data_body
        with patch('time.time', return_value=1234.987654321) as time_mock:

            output_prop_kwargs = BaseCollector.get_output_prop_kwargs(
                collector_mock,
                source=source,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)

        self.assertEqual(collector_mock.mock_calls, [
            call._validate_source_type_related_attributes(
                AnyInstanceOf(str),
                raw_type=raw_type,
                content_type=content_type,
            ),
            call.get_output_message_id(
                source=source,
                created_timestamp=1234,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B,
            ),
        ])
        time_mock.assert_called_once_with()
        self.assertEqual(output_prop_kwargs, {
            # (note: if the collector's raw type is "stream" then
            # `content_type` is *not* added to these properties)
            'message_id': message_id,
            'type': raw_type,
            'timestamp': 1234,
            'headers': {},
        })


    @foreach(
        param(raw_type='file'),
        param(raw_type='blacklist'),
    )
    def test__get_output_prop_kwargs__with_non_stream_raw_type(self, raw_type):
        content_type = 'text/csv'
        message_id = sentinel.message_id
        collector_mock = Mock(
            __class__=BaseCollector,
            raw_type=raw_type,
            content_type=content_type,
            get_output_message_id=Mock(return_value=message_id),
            _validate_source_type_related_attributes=Mock(
                wraps=BaseCollector._validate_source_type_related_attributes))
        source = sentinel.source
        output_data_body = sentinel.output_data_body
        with patch('time.time', return_value=1234.987654321) as time_mock:

            output_prop_kwargs = BaseCollector.get_output_prop_kwargs(
                collector_mock,
                source=source,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)

        self.assertEqual(collector_mock.mock_calls, [
            call._validate_source_type_related_attributes(
                AnyInstanceOf(str),
                raw_type=raw_type,
                content_type=content_type,
            ),
            call.get_output_message_id(
                source=source,
                created_timestamp=1234,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B,
            ),
        ])
        time_mock.assert_called_once_with()
        self.assertEqual(output_prop_kwargs, {
            'message_id': message_id,
            'type': raw_type,
            'timestamp': 1234,
            'headers': {},
            # (if the collector's raw type is "file" or "blacklist"
            # then `content_type` *is* added to these properties)
            'content_type': content_type,
        })


    @foreach(
        param(
            raw_type=None,
            expected_error_class=NotImplementedError,
            expected_error_regex=r'attribute `raw_type` is not set',
        ),
        param(
            raw_type='illegal-raw-type',
            expected_error_class=ValueError,
            expected_error_regex=(
                r"attribute `raw_type` should be one of: "
                r"'stream', 'file', 'blacklist'"),
        ),
    )
    @foreach(
        param(content_type=None),
        param(content_type='whatever/irrelevant-anyway'),
    )
    def test__get_output_prop_kwargs__with_no_raw_type_or_illegal_raw_type_raises_error(
            self,
            raw_type,
            content_type,
            expected_error_class,
            expected_error_regex):
        collector_mock = Mock(
            __class__=BaseCollector,
            raw_type=raw_type,
            content_type=content_type,
            _validate_source_type_related_attributes=Mock(
                wraps=BaseCollector._validate_source_type_related_attributes))
        source = sentinel.source
        output_data_body = sentinel.output_data_body

        with self.assertRaisesRegex(expected_error_class, expected_error_regex):
            BaseCollector.get_output_prop_kwargs(
                collector_mock,
                source=source,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)

        collector_mock._validate_source_type_related_attributes.assert_called_once_with(
            AnyInstanceOf(str),
            raw_type=raw_type,
            content_type=content_type)


    @foreach(
        param(raw_type='file'),
        param(raw_type='blacklist'),
    )
    def test__get_output_prop_kwargs__with_non_stream_raw_type_and_no_content_type_raises_error(
            self,
            raw_type):

        collector_mock = Mock(
            __class__=BaseCollector,
            raw_type=raw_type,
            content_type=None,
            _validate_source_type_related_attributes=Mock(
                wraps=BaseCollector._validate_source_type_related_attributes))
        source = sentinel.source
        output_data_body = sentinel.output_data_body
        expected_error_regex = (
            r'attribute `raw_type` is .* '
            r'so `content_type` should be .* non-None value')

        with self.assertRaisesRegex(NotImplementedError, expected_error_regex):
            BaseCollector.get_output_prop_kwargs(
                collector_mock,
                source=source,
                output_data_body=output_data_body,
                a=SAMPLE_ARG_A,
                bb=SAMPLE_ARG_B)

        collector_mock._validate_source_type_related_attributes.assert_called_once_with(
            AnyInstanceOf(str),
            raw_type=raw_type,
            content_type=None)


    @foreach(
        param(
            expected_message_id='0ee79178d8d14de9c91b6499598f9135',
        ),
        param(
            source='another-provider.another-channel',
            expected_message_id='078f339794e866e0461c7bfc584968d9',
        ),
        param(
            created_timestamp=1234,
            expected_message_id='039420f5dd63f768a7ebb7d9c0e8d3e4',
        ),
        param(
            output_data_body=b'<another body>',
            expected_message_id='160267f56db259051e66b2e85653b1ed',
        ),
    )
    def test__get_output_message_id(self,
                                    expected_message_id,
                                    source='my-provider.my-channel',
                                    created_timestamp=1660218035,
                                    output_data_body=b'<some body>'):
        collector_stub = PlainNamespace()

        message_id = BaseCollector.get_output_message_id(
            collector_stub,  # noqa
            source=source,
            created_timestamp=created_timestamp,
            output_data_body=output_data_body)

        self.assertEqual(message_id, expected_message_id)
        self.assertEqual(message_id, hashlib.md5(  # (this check's redundancy is intentional)
            f'{source}\0{created_timestamp}\0'.encode('utf-8') + output_data_body,
            usedforsecurity=False).hexdigest())


    @foreach(
        'x.y',
        'my-provider.my-channel',
        'quite-long-but-still-good.source',
        'with-l-e-g-a-l.chars-only',
    )
    def test__validate_source(self, source):
        # (note: `BaseCollector.validate_source()` checks both the type and
        # the value format -- unlike the other `BaseCollector.validate_...()`
        # methods tested below)
        collector_mock = Mock(__class__=BaseCollector)
        collector_mock._source_value_validation_field.clean_result_value = Mock(
            wraps=BaseCollector._source_value_validation_field.clean_result_value)

        BaseCollector.validate_source(collector_mock, source)

        self.assertEqual(collector_mock._source_value_validation_field.mock_calls, [
            call.clean_result_value(source),
        ])


    def test__validate_source__with_non_str_value_raises_error(self):
        collector_mock = Mock(__class__=BaseCollector)
        expected_error_regex = (
            r"source=b'non-str.value' \(an instance of `bytes` "
            r"whereas an instance of `str` was expected\)")

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            BaseCollector.validate_source(collector_mock, b'non-str.value')


    @foreach(
        '',
        'toooooooooooooooooooo-long.source',
        'no-dot',
        'to.many.dots',
        'with-i_l_l_e_g_a_l.chars',
    )
    def test__validate_source__with_invalid_value_raises_error(self, source):
        collector_mock = Mock(__class__=BaseCollector)
        collector_mock._source_value_validation_field.clean_result_value = Mock(
            wraps=BaseCollector._source_value_validation_field.clean_result_value)
        expected_error_regex = rf"source={re.escape(ascii(source))}"

        with self.assertRaisesRegex(ValueError, expected_error_regex):
            BaseCollector.validate_source(collector_mock, source)

        self.assertEqual(collector_mock._source_value_validation_field.mock_calls, [
            call.clean_result_value(source),
        ])


    def test__validate_output_rk(self):
        # (note: `BaseCollector.validate_output_rk()` checks only the type)
        BaseCollector.validate_output_rk(sentinel.collector, 'any str')


    def test__validate_output_rk__with_non_str_value_raises_error(self):
        collector_mock = Mock(__class__=BaseCollector)
        expected_error_regex = (
            r"output_rk=b'non-str value' \(an instance of `bytes` "
            r"whereas an instance of `str` was expected\)")

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            BaseCollector.validate_output_rk(collector_mock, b'non-str value')


    def test__validate_output_data_body(self):
        # (note: `BaseCollector.validate_output_data_body()` checks only the type)
        BaseCollector.validate_output_data_body(sentinel.collector, b'any bytes')


    def test__validate_output_data_body__with_non_bytes_value_raises_error(self):
        collector_mock = Mock(__class__=BaseCollector)
        expected_error_regex = (
            r"output_data_body='non-bytes value' \(an instance of `str` "
            r"whereas an instance of `bytes` was expected\)")

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            BaseCollector.validate_output_data_body(collector_mock, 'non-bytes value')


    def test__validate_output_prop_kwargs(self):
        # (note: `BaseCollector.validate_output_prop_kwargs()` checks only the type)
        BaseCollector.validate_output_prop_kwargs(sentinel.collector, {'any': 42, b'\0': 'dict'})


    def test__validate_output_prop_kwargs__with_non_dict_value_raises_error(self):
        collector_mock = Mock(__class__=BaseCollector)
        expected_error_regex = (
            r"output_prop_kwargs=\['non-dict value'\] \(an instance of `list` "
            r"whereas an instance of `dict` was expected\)")

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            BaseCollector.validate_output_prop_kwargs(collector_mock, ['non-dict value'])


@expand
class TestBaseCollectorByRunningItsRealSubclass(BaseCollectorTestCase):

    # Note: this class also provides tests concerning `BaseCollector`,
    # but here the approach is different from that in `TestBaseCollector`.
    # In particular, these tests cover the most important interactions
    # with and within the *iterative publishing* machinery (including
    # the cases *when our custom `publish_iteratively()` yields `None`
    # or awaits `self.PubIter`* vs. *when it yields `self.FLUSH_OUT`
    # or awaits `self.PubIterFLushOut`*).

    @paramseq
    def cases(cls):
        # Note ad the test parameter `expected_recorded_calls`: in this
        # test class we record invocations of many methods as well as
        # some other callables...

        for raw_type, content_type in [
            ('stream', None),
            ('file', 'application/jwt'),
            ('blacklist', 'text/csv'),
        ]:
            expected_prop_kwargs_base = {
                'type': raw_type,
            }
            if content_type is not None:
                expected_prop_kwargs_base['content_type'] = content_type

            #
            # No output items

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                iterative_publishing_steps=[],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('no output items')

            #
            # 1 output item

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                iterative_publishing_steps=[
                    {},  # not customized `input_data`
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call.get_output_components(),
                    call.process_input_data(),
                    call.get_source(
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b'my_num=0042 (count=1)',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b'my_num=0042 (count=1)',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b'my_num=0042 (count=1)',

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('1 output item')

            #
            # 1 output item, with custom stuff from `get_script_init_kwargs()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                script_init_kwargs=dict(
                    my_num_format_override='08x',
                ),
                iterative_publishing_steps=[
                    {},  # not customized `input_data`
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(
                        my_num_format_override='08x',
                    ),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call.get_output_components(),
                    call.process_input_data(),
                    call.get_source(
                        my_num=b'0000002a',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_num=b'0000002a',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_num=b'0000002a',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b'my_num=0000002a (count=1)',
                        my_num=b'0000002a',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b'my_num=0000002a (count=1)',
                        my_num=b'0000002a',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b'my_num=0000002a (count=1)',

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('1 output item, with custom stuff from `get_script_init_kwargs()`')

            #
            # 1 output item, with alternative config and without any command-line option

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                config_content='''
                    [ExampleCollector]
                    my_num = 123
                ''',
                cmdline_args=[],
                iterative_publishing_steps=[
                    {},  # not customized `input_data`
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 123},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call.get_output_components(),
                    call.process_input_data(),
                    call.get_source(
                        my_num=b'123',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_num=b'123',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_num=b'123',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b'my_num=123 (count=1)',
                        my_num=b'123',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b'my_num=123 (count=1)',
                        my_num=b'123',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b'my_num=123 (count=1)',

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('1 output item, with alternative config and without any command-line option')

            #
            # Several output items, but no yields between publications
            # (note: that practice is *not* recommended in a real code;
            # but see some further cases where such yields are present...)

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                iterative_publishing_steps=[
                    {
                        # output item #1
                        'irrelevant_item': True,
                    },
                    {
                        # output item #2
                        'my_src': 'custom-provider.custom-channel',
                    },
                    {
                        # output item #3
                        'my_tag': '202305',
                    },
                    {
                        # output item #4
                        'my_body_prefix': b"It's... ",
                    },
                    {
                        # output item #5
                        'my_meta_header': 'Whither Canada?',
                    },
                    {
                        # output item #6
                        'irrelevant_item': True,
                        'my_src': 'custom-provider.custom-channel',
                        'my_tag': '202305',
                        'my_body_prefix': b"It's... ",
                        'my_meta_header': 'Whither Canada?',
                    },
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),

                    # * Output item #1 (for `'irrelevant_item': True`):

                    call.get_output_components(
                        irrelevant_item=True,
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=1)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),

                    # * Output item #2 (for `'my_src': 'custom-provider.custom-channel'`):

                    call.get_output_components(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.process_input_data(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.get_source(
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=2,
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel',

                        # body
                        b"my_num=0042 (count=2)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 2,
                            'message_id': '22222222222222222222222222222222',
                            'headers': {},
                        },
                    ),

                    # * Output item #3 (for `'my_tag': '202305'`):

                    call.get_output_components(
                        my_tag='202305',
                    ),
                    call.process_input_data(
                        my_tag='202305',
                    ),
                    call.get_source(
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=3,
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel.202305',

                        # body
                        b"my_num=0042 (count=3)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 3,
                            'message_id': '33333333333333333333333333333333',
                            'headers': {},
                        },
                    ),

                    # * Output item #4 (for `'my_body_prefix': b"It's... "`):

                    call.get_output_components(
                        my_body_prefix=b"It's... ",
                    ),
                    call.process_input_data(
                        my_body_prefix=b"It's... ",
                    ),
                    call.get_source(
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=4,
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"It's... my_num=0042 (count=4)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 4,
                            'message_id': '44444444444444444444444444444444',
                            'headers': {},
                        },
                    ),

                    # * Output item #5 (for `'my_meta_header': 'Whither Canada?'`):

                    call.get_output_components(
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=5,
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=5)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 5,
                            'message_id': '55555555555555555555555555555555',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Output item #6 (for `{
                    #       'irrelevant_item': True,
                    #       'my_src': 'custom-provider.custom-channel',
                    #       'my_tag': '202305',
                    #       'my_body_prefix': b"It's... ",
                    #       'my_meta_header': 'Whither Canada?',
                    #   }`):

                    call.get_output_components(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=6,
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel.202305',

                        # body
                        b"It's... my_num=0042 (count=6)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 6,
                            'message_id': '66666666666666666666666666666666',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Finalization:

                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('Several output items, but no yields between publications')

            #
            # Several output items, publications interspersed by `yield None`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                iterative_publishing_steps=[
                    {
                        # output item #1
                        'irrelevant_item': True,
                    },
                    None,  # yield
                    {
                        # output item #2
                        'my_src': 'custom-provider.custom-channel',
                    },
                    None,  # yield
                    {
                        # output item #3
                        'my_tag': '202305',
                    },
                    None,  # yield
                    {
                        # output item #4
                        'my_body_prefix': b"It's... ",
                    },
                    None,  # yield
                    {
                        # output item #5
                        'my_meta_header': 'Whither Canada?',
                    },
                    None,  # yield
                    {
                        # output item #6
                        'irrelevant_item': True,
                        'my_src': 'custom-provider.custom-channel',
                        'my_tag': '202305',
                        'my_body_prefix': b"It's... ",
                        'my_meta_header': 'Whither Canada?',
                    },
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),

                    # * Output item #1 (for `'irrelevant_item': True`):

                    call.get_output_components(
                        irrelevant_item=True,
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=1)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),

                    # * Output item #2 (for `'my_src': 'custom-provider.custom-channel'`):

                    call.get_output_components(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.process_input_data(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.get_source(
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=2,
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel',

                        # body
                        b"my_num=0042 (count=2)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 2,
                            'message_id': '22222222222222222222222222222222',
                            'headers': {},
                        },
                    ),

                    # * Output item #3 (for `'my_tag': '202305'`):

                    call.get_output_components(
                        my_tag='202305',
                    ),
                    call.process_input_data(
                        my_tag='202305',
                    ),
                    call.get_source(
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=3,
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel.202305',

                        # body
                        b"my_num=0042 (count=3)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 3,
                            'message_id': '33333333333333333333333333333333',
                            'headers': {},
                        },
                    ),

                    # * Output item #4 (for `'my_body_prefix': b"It's... "`):

                    call.get_output_components(
                        my_body_prefix=b"It's... ",
                    ),
                    call.process_input_data(
                        my_body_prefix=b"It's... ",
                    ),
                    call.get_source(
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=4,
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"It's... my_num=0042 (count=4)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 4,
                            'message_id': '44444444444444444444444444444444',
                            'headers': {},
                        },
                    ),

                    # * Output item #5 (for `'my_meta_header': 'Whither Canada?'`):

                    call.get_output_components(
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=5,
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=5)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 5,
                            'message_id': '55555555555555555555555555555555',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Note: `yield_time_interval_threshold` has been reached
                    #   so this is the moment when the `pika` event loop gets the
                    #   control for a short time (more precisely:, it would if it
                    #   was not patched by the `BaseCollectorTestCase`'s machinery):

                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #6 (for `{
                    #       'irrelevant_item': True,
                    #       'my_src': 'custom-provider.custom-channel',
                    #       'my_tag': '202305',
                    #       'my_body_prefix': b"It's... ",
                    #       'my_meta_header': 'Whither Canada?',
                    #   }`):

                    call.get_output_components(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=16,
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel.202305',

                        # body
                        b"It's... my_num=0042 (count=6)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 16,
                            'message_id': '66666666666666666666666666666666',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Finalization:

                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('Several output items, publications interspersed by `yield None`')

            #
            # Several output items, publications interspersed by `yield self.FLUSH_OUT`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                iterative_publishing_steps=[
                    {
                        # output item #1
                        'irrelevant_item': True,
                    },
                    BaseCollector.FLUSH_OUT,  # yield FLUSH_OUT
                    {
                        # output item #2
                        'my_src': 'custom-provider.custom-channel',
                    },
                    BaseCollector.FLUSH_OUT,  # yield FLUSH_OUT
                    {
                        # output item #3
                        'my_tag': '202305',
                    },
                    BaseCollector.FLUSH_OUT,  # yield FLUSH_OUT
                    {
                        # output item #4
                        'my_body_prefix': b"It's... ",
                    },
                    BaseCollector.FLUSH_OUT,  # yield FLUSH_OUT
                    {
                        # output item #5
                        'my_meta_header': 'Whither Canada?',
                    },
                    BaseCollector.FLUSH_OUT,  # yield FLUSH_OUT
                    {
                        # output item #6
                        'irrelevant_item': True,
                        'my_src': 'custom-provider.custom-channel',
                        'my_tag': '202305',
                        'my_body_prefix': b"It's... ",
                        'my_meta_header': 'Whither Canada?',
                    },
                ],
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),

                    # * Output item #1 (for `'irrelevant_item': True`):

                    call.get_output_components(
                        irrelevant_item=True,
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=1,
                        output_data_body=b"my_num=0042 (count=1)",
                        irrelevant_item=True,
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=1)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 1,
                            'message_id': '11111111111111111111111111111111',
                            'headers': {},
                        },
                    ),

                    # * Here the `FLUSH_OUT` marker has been yielded, so then:

                    # (our contrived implementation will advance time by 100s)
                    call._iter_until_buffer_flushed(),
                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #2 (for `'my_src': 'custom-provider.custom-channel'`):

                    call.get_output_components(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.process_input_data(
                        my_src='custom-provider.custom-channel',
                    ),
                    call.get_source(
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=112,
                        output_data_body=b"my_num=0042 (count=2)",
                        my_src='custom-provider.custom-channel',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel',

                        # body
                        b"my_num=0042 (count=2)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 112,
                            'message_id': '22222222222222222222222222222222',
                            'headers': {},
                        },
                    ),

                    # * Here the `FLUSH_OUT` marker has been yielded, so then:

                    # (our contrived implementation will advance time by 100s)
                    call._iter_until_buffer_flushed(),
                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #3 (for `'my_tag': '202305'`):

                    call.get_output_components(
                        my_tag='202305',
                    ),
                    call.process_input_data(
                        my_tag='202305',
                    ),
                    call.get_source(
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=223,
                        output_data_body=b"my_num=0042 (count=3)",
                        my_tag='202305',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel.202305',

                        # body
                        b"my_num=0042 (count=3)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 223,
                            'message_id': '33333333333333333333333333333333',
                            'headers': {},
                        },
                    ),

                    # * Here the `FLUSH_OUT` marker has been yielded, so then:

                    # (our contrived implementation will advance time by 100s)
                    call._iter_until_buffer_flushed(),
                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #4 (for `'my_body_prefix': b"It's... "`):

                    call.get_output_components(
                        my_body_prefix=b"It's... ",
                    ),
                    call.process_input_data(
                        my_body_prefix=b"It's... ",
                    ),
                    call.get_source(
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=334,
                        output_data_body=b"It's... my_num=0042 (count=4)",
                        my_body_prefix=b"It's... ",
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"It's... my_num=0042 (count=4)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 334,
                            'message_id': '44444444444444444444444444444444',
                            'headers': {},
                        },
                    ),

                    # * Here the `FLUSH_OUT` marker has been yielded, so then:

                    # (our contrived implementation will advance time by 100s)
                    call._iter_until_buffer_flushed(),
                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #5 (for `'my_meta_header': 'Whither Canada?'`):

                    call.get_output_components(
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='std-provider.std-channel',
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='std-provider.std-channel',
                        created_timestamp=445,
                        output_data_body=b"my_num=0042 (count=5)",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'std-provider.std-channel',

                        # body
                        b"my_num=0042 (count=5)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 445,
                            'message_id': '55555555555555555555555555555555',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Here the `FLUSH_OUT` marker has been yielded, so then:

                    # (our contrived implementation will advance time by 100s)
                    call._iter_until_buffer_flushed(),
                    # (our contrived implementation will advance time by 10s)
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),

                    # * Output item #6 (for `{
                    #       'irrelevant_item': True,
                    #       'my_src': 'custom-provider.custom-channel',
                    #       'my_tag': '202305',
                    #       'my_body_prefix': b"It's... ",
                    #       'my_meta_header': 'Whither Canada?',
                    #   }`):

                    call.get_output_components(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.process_input_data(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                    ),
                    call.get_source(
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='custom-provider.custom-channel',
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_prop_kwargs(
                        source='custom-provider.custom-channel',
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.get_output_message_id(
                        source='custom-provider.custom-channel',
                        created_timestamp=556,
                        output_data_body=b"It's... my_num=0042 (count=6)",
                        irrelevant_item=True,
                        my_src='custom-provider.custom-channel',
                        my_tag='202305',
                        my_body_prefix=b"It's... ",
                        my_meta_header='Whither Canada?',
                        my_num=b'0042',
                    ),
                    call.publish_output(
                        # routing_key
                        'custom-provider.custom-channel.202305',

                        # body
                        b"It's... my_num=0042 (count=6)",

                        # prop_kwargs
                        expected_prop_kwargs_base | {
                            'timestamp': 556,
                            'message_id': '66666666666666666666666666666666',
                            'headers': {
                                'meta': {
                                    'my_meta_header': 'Whither Canada?',
                                },
                            },
                        },
                    ),

                    # * Finalization:

                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._schedule_next(AnyCallableNamed('inner_stop')),
                    call.inner_stop(),
                    call.after_completed_publishing(),
                    call._external_func__logging_configured().__exit__(None, None, None),
                ],
            ).label('Several output items, publications interspersed by `yield self.FLUSH_OUT`')

            #
            # Error from `get_script_init_kwargs()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    _class_method__get_script_init_kwargs=ZeroDivisionError('arbitrary error'),
                ),
                expected_exc_and_regex=(
                    ZeroDivisionError,
                    r'arbitrary error',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._external_func__logging_configured().__exit__(
                        ZeroDivisionError, ANY, ANY,
                    ),
                ],
            ).label('Error from `get_script_init_kwargs()`')

            #
            # Error from the command-line argument parser

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                cmdline_args=['--n6illegal-option', 'whatever'],
                expected_exc_and_regex=(
                    SystemExit,
                    r'^2$',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._external_func__logging_configured().__exit__(
                        SystemExit, ANY, ANY,
                    ),
                ],
            ).label('Error from the command-line argument parser')

            #
            # Error from `__init__()` (wrong configuration: missing option)

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                config_content='[ExampleCollector]',
                expected_exc_and_regex=(
                    ConfigError,
                    r'missing required config options: ExampleCollector.my_num',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call._external_func__logging_configured().__exit__(
                        ConfigError, ANY, ANY,
                    ),
                ],
            ).label('Error from `__init__()` (wrong configuration: missing option)')

            #
            # Error from `run()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    run=ZeroDivisionError('arbitrary error'),
                ),
                expected_exc_and_regex=(
                    ZeroDivisionError,
                    r'arbitrary error',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call._external_func__logging_configured().__exit__(
                        ZeroDivisionError, ANY, ANY,
                    ),
                ],
            ).label('Error from `run()`')

            #
            # `KeyboardInterrupt` from `run()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    run=KeyboardInterrupt,
                ),
                expected_exc_and_regex=(
                    KeyboardInterrupt,
                    r'',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.stop(),        # <- note this
                    call.inner_stop(),  # <- and this
                    call._external_func__logging_configured().__exit__(
                        KeyboardInterrupt, ANY, ANY,
                    ),
                ],
            ).label('`KeyboardInterrupt` from `run()`')

            #
            # `SystemExit` from `run()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    run=SystemExit('whatever'),
                ),
                expected_exc_and_regex=(
                    SystemExit,
                    r'whatever',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call._external_func__logging_configured().__exit__(
                        SystemExit, ANY, ANY,
                    ),
                ],
            ).label('`SystemExit` from `run()`')

            #
            # Error from `_next_publishing_iteration()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    _next_publishing_iteration=ZeroDivisionError('arbitrary error'),
                ),
                expected_exc_and_regex=(
                    SystemExit,  # <- note this
                    r'ERROR during iterative publishing:.*arbitrary error',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._external_func__logging_configured().__exit__(
                        SystemExit, ANY, ANY,
                    ),
                ],
            ).label('Error from `_next_publishing_iteration()`')

            #
            # `KeyboardInterrupt` from `_next_publishing_iteration()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    _next_publishing_iteration=KeyboardInterrupt,
                ),
                expected_exc_and_regex=(
                    KeyboardInterrupt,
                    r'',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.stop(),        # <- note this
                    call.inner_stop(),  # <- and this
                    call._external_func__logging_configured().__exit__(
                        KeyboardInterrupt, ANY, ANY,
                    ),
                ],
            ).label('`KeyboardInterrupt` from `_next_publishing_iteration()`')

            #
            # Error from `publish_iteratively()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    publish_iteratively=ZeroDivisionError('arbitrary error'),
                ),
                expected_exc_and_regex=(
                    SystemExit,  # <- note this
                    r'ERROR during iterative publishing:.*arbitrary error',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    # note this:
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._external_func__logging_configured().__exit__(
                        SystemExit, ANY, ANY,
                    ),
                ],
            ).label('Error from `publish_iteratively()`')

            #
            # `KeyboardInterrupt` from `publish_iteratively()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    publish_iteratively=KeyboardInterrupt,
                ),
                expected_exc_and_regex=(
                    KeyboardInterrupt,
                    r'',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    # note this:
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.stop(),        # <- also note this
                    call.inner_stop(),  # <- and this
                    call._external_func__logging_configured().__exit__(
                        KeyboardInterrupt, ANY, ANY,
                    ),
                ],
            ).label('`KeyboardInterrupt` from `publish_iteratively()`')

            #
            # Error from `get_output_data_body()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    get_output_data_body=ZeroDivisionError('arbitrary error'),
                ),
                iterative_publishing_steps=[
                    {},  # not customized `input_data`
                ],
                expected_exc_and_regex=(
                    SystemExit,  # <- note this
                    r'ERROR during iterative publishing:.*arbitrary error',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call.get_output_components(),
                    call.process_input_data(),
                    call.get_source(
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    # note this:
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call._external_func__logging_configured().__exit__(
                        SystemExit, ANY, ANY,
                    ),
                ],
            ).label('Error from `get_output_data_body()`')

            #
            # `KeyboardInterrupt` from `get_output_data_body()`

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                name_to_side_effect=dict(
                    get_output_data_body=KeyboardInterrupt,
                ),
                iterative_publishing_steps=[
                    {},  # not customized `input_data`
                ],
                expected_exc_and_regex=(
                    KeyboardInterrupt,
                    r'',
                ),
                expected_recorded_calls=[
                    call._external_func__logging_configured(),
                    call._external_func__logging_configured().__enter__(),
                    call._class_method__get_script_init_kwargs(),
                    call._class_method__get_arg_parser(),
                    call._special_method__init(),
                    call.set_configuration(),
                    call.get_config_spec_format_kwargs(),
                    call.get_config_from_config_full(
                        config_full=Config.make({
                            'ExampleCollector': {'my_num': 42},
                        }),
                        collector_class_name='ExampleCollector',
                    ),
                    call.run_collection(),
                    call.run(),
                    call.start_publishing(),
                    call.start_iterative_publishing(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.publish_iteratively(),
                    call.get_output_components(),
                    call.process_input_data(),
                    call.get_source(
                        my_num=b'0042',
                    ),
                    call.get_output_rk(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    call.get_output_data_body(
                        source='std-provider.std-channel',
                        my_num=b'0042',
                    ),
                    # note this:
                    call._iter_until_buffer_flushed(),
                    call._schedule_next(AnyCallableNamed('_next_publishing_iteration')),
                    call._next_publishing_iteration(),
                    call.stop(),        # <- also note this
                    call.inner_stop(),  # <- and this
                    call._external_func__logging_configured().__exit__(
                        KeyboardInterrupt, ANY, ANY,
                    ),
                ],
            ).label('`KeyboardInterrupt` from `get_output_data_body()`')


    @foreach(cases)
    @foreach(
        param(iterative_publishing_implemented_as_async_def_coroutine=False),
        param(iterative_publishing_implemented_as_async_def_coroutine=True),
    )
    def test(self,
             *,
             iterative_publishing_implemented_as_async_def_coroutine,
             raw_type_and_content_type,
             config_content='''
                 [ExampleCollector]
                 my_num = 42
            ''',
             cmdline_args=(
                 '--n6my-num-format',
                 '04',
             ),
             script_init_kwargs=None,
             name_to_side_effect=None,
             iterative_publishing_steps=None,
             expected_recorded_calls=None,
             expected_exc_and_regex=None):

        if script_init_kwargs is None:
            script_init_kwargs = {}

        if name_to_side_effect is None:
            name_to_side_effect = {}

        if iterative_publishing_steps is None:
            iterative_publishing_steps = []

        if expected_recorded_calls is None:
            expected_recorded_calls = []


        class ExampleCollector(BaseCollector):  # noqa

            raw_type, content_type = raw_type_and_content_type

            config_spec_pattern = combined_config_spec('''
                [{collector_class_name}]
                my_num :: {my_num_converter_spec}
            ''')

            @classmethod
            def get_script_init_kwargs(cls):
                rec._class_method__get_script_init_kwargs()
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `AbstractBaseCollector.get_arg_parser()`...
                return (
                    super().get_script_init_kwargs()
                    | script_init_kwargs)

            @classmethod
            def get_arg_parser(cls):
                rec._class_method__get_arg_parser()
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `LegacyQueuedBase.get_arg_parser()`...
                arg_parser = super().get_arg_parser()
                arg_parser.add_argument('--n6my-num-format', default='')
                return arg_parser

            def __init__(self, *, my_num_format_override=None, **kwargs):
                rec._special_method__init(**(
                    kwargs if my_num_format_override is None
                    else kwargs | dict(my_num_format_override=my_num_format_override)))
                # Here we have an example custom extension of the
                # default implementation of `BaseCollector.__init__()`.
                super().__init__(**kwargs)
                self._pub_count = 0
                self._my_num_format = (
                    my_num_format_override if my_num_format_override is not None
                    else self.cmdline_args.n6my_num_format)
                # (see: `get_config_from_config_full()` below...)
                assert getattr(self.config, 'my_silly_marker_for_this_test_only', None) == 'Ye!'

            def set_configuration(self):
                rec.set_configuration()
                super().set_configuration()

            def get_config_spec_format_kwargs(self):
                rec.get_config_spec_format_kwargs()
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `CollectorConfigMixin.get_config_spec_format_kwargs()`...
                return super().get_config_spec_format_kwargs() | {
                    'my_num_converter_spec': 'int',
                }

            def get_config_from_config_full(self, *, config_full, collector_class_name):
                rec.get_config_from_config_full(
                    config_full=config_full,
                    collector_class_name=collector_class_name,
                )
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `CollectorConfigMixin.get_config_from_config_full()`...
                config = super().get_config_from_config_full(
                    config_full=config_full,
                    collector_class_name=collector_class_name)
                config.my_silly_marker_for_this_test_only = 'Ye!'
                return config

            def run_collection(self):
                rec.run_collection()
                # Note: typically, the default implementation of
                # this method is enough; however, occasionally,
                # the possibility of extending it appears useful...
                # (Here, we do not add anything interesting.)
                super().run_collection()

            # By placing in this class the following eight method
            # definitions we override/extend some internals of
            # `LegacyQueuedBase`, just for these tests (normally
            # you do *not* override or extend these methods!).

            def run(self):
                rec.run()
                super().run()  # (calling just a `BaseCollectorTestCase`-produced fake)

            def stop(self):
                rec.stop()
                super().stop()  # (calling just a `BaseCollectorTestCase`-produced fake)

            def inner_stop(self):
                rec.inner_stop()
                super().inner_stop()  # (calling just a `BaseCollectorTestCase`-produced fake)

            def start_iterative_publishing(self):
                rec.start_iterative_publishing()
                super().start_iterative_publishing()

            def _get_yield_time_interval_threshold(self):
                # (in these tests we need this method to return the
                # following value, but we do not need `rec...` here)
                return 4.0

            def _iter_until_buffer_flushed(self, outbound_buffer):
                rec._iter_until_buffer_flushed()
                nonlocal cur_time
                cur_time += 100
                yield from super()._iter_until_buffer_flushed(outbound_buffer)

            def _next_publishing_iteration(self):
                rec._next_publishing_iteration()
                super()._next_publishing_iteration()

            def _schedule_next(self, callback):
                rec._schedule_next(callback)
                nonlocal cur_time
                if self._pub_count > 0:
                    cur_time += 10
                super()._schedule_next(callback)

            # Extending/overriding some `LegacyQueuedBase`'s public hook
            # methods related to the *iterative publishing* mechanism...

            def start_publishing(self):
                rec.start_publishing()
                # Here we have an example custom extension; see the
                # docstrings of `LegacyQueuedBase.start_publishing()`...
                # and `LegacyQueuedBase.start_iterative_publishing()`...
                super().start_publishing()
                self.start_iterative_publishing()

            # (Note: the following two variants of the `publish_iteratively()`
            # abstract method are supposed to be perfectly equivalent; although,
            # generally, the *coroutine-based* technique is more flexible...)
            if iterative_publishing_implemented_as_async_def_coroutine:

                async def publish_iteratively(self):
                    rec.publish_iteratively()
                    # Here we have an example of a *coroutine-based* custom
                    # implementation of this abstract method; see the docstring
                    # of `LegacyQueuedBase.publish_iteratively()`...
                    for step in iterative_publishing_steps:
                        if isinstance(step, dict):
                            # `step` is an *input data* dict
                            output_components = self.get_output_components(**step)
                            self.publish_output(*output_components)
                        else:
                            # `step` is a marker...
                            assert step in (self.FLUSH_OUT, None)
                            if step == self.FLUSH_OUT:
                                await self.PubIterFlushOut
                            else:
                                await self.PubIter

            else:

                def publish_iteratively(self):
                    rec.publish_iteratively()
                    # Here we have an example of a *generator-based* custom
                    # implementation of this abstract method; see the docstring
                    # of `LegacyQueuedBase.publish_iteratively()`...
                    for step in iterative_publishing_steps:
                        if isinstance(step, dict):
                            # `step` is an *input data* dict
                            output_components = self.get_output_components(**step)
                            self.publish_output(*output_components)
                        else:
                            # `step` is a marker...
                            assert step in (self.FLUSH_OUT, None)
                            yield step

            # Extending/overriding `BaseCollector`'s public hook methods

            def get_output_components(self, **input_data):
                rec.get_output_components(**input_data)
                nonlocal cur_time
                cur_time += 1
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `BaseCollector.get_output_components()`...
                self._pub_count += 1
                return super().get_output_components(**input_data)

            def process_input_data(self, **input_data):
                rec.process_input_data(**input_data)
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `BaseCollector.process_input_data()`...
                processed_data = super().process_input_data(**input_data)
                assert processed_data == input_data
                my_num = self.config['my_num']
                my_num_formatted = format(my_num, self._my_num_format)
                processed_data['my_num'] = my_num_formatted.encode('utf-8')
                return processed_data

            def get_source(self, **processed_data):
                rec.get_source(**processed_data)
                # Here we have an example custom implementation
                # of this abstract method; see the docstring of
                # `BaseCollector.get_source()`...
                return (
                    processed_data['my_src'] if 'my_src' in processed_data
                    else 'std-provider.std-channel')

            def get_output_rk(self, *, source, **processed_data):
                rec.get_output_rk(source=source, **processed_data)
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `BaseCollector.get_output_rk()`...
                self.raw_format_version_tag = processed_data.get('my_tag')
                return super().get_output_rk(source=source, **processed_data)

            def get_output_data_body(self, *, source, **processed_data):
                rec.get_output_data_body(source=source, **processed_data)
                # Here we have an example custom implementation
                # of this abstract method; see the docstring of
                # `BaseCollector.get_output_data_body()`...
                my_body_prefix = processed_data.get('my_body_prefix', b'')
                return b'%bmy_num=%b (count=%d)' % (
                    my_body_prefix,
                    processed_data['my_num'],
                    self._pub_count)

            def get_output_prop_kwargs(self, *, source, output_data_body,
                                       **processed_data):
                rec.get_output_prop_kwargs(
                    source=source,
                    output_data_body=output_data_body,
                    **processed_data)
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `BaseCollector.get_output_prop_kwargs()`...
                prop_kwargs = super().get_output_prop_kwargs(
                    source=source,
                    output_data_body=output_data_body,
                    **processed_data)
                meta_header_val = processed_data.get('my_meta_header')
                if meta_header_val:
                    prop_kwargs['headers'].setdefault('meta', {})
                    prop_kwargs['headers']['meta']['my_meta_header'] = meta_header_val
                return prop_kwargs

            def get_output_message_id(self, *, source, created_timestamp,
                                      output_data_body, **processed_data):
                rec.get_output_message_id(
                    source=source,
                    created_timestamp=created_timestamp,
                    output_data_body=output_data_body,
                    **processed_data)
                assert created_timestamp == int(cur_time)
                # Here we have an example custom extension of the
                # default implementation; see the docstring of
                # `BaseCollector.get_output_message_id()`...
                message_id = super().get_output_message_id(
                    source=source,
                    created_timestamp=created_timestamp,
                    output_data_body=output_data_body,
                    **processed_data)
                # This is a contrived transformation, just for these tests...
                last_pub_count_digit = str(self._pub_count)[-1:]
                final_message_id = last_pub_count_digit * len(message_id)
                return final_message_id

            # Yet another `AbstractBaseCollector`'s public hook

            def after_completed_publishing(self):
                rec.after_completed_publishing()
                # (note: in fact, the `AbstractBaseCollector`'s version
                # of this method does nothing, but it is a good practice
                # to invoke the `super()`'s version anyway -- just to
                # remain *open for extension* by any future mixins etc.)
                super().after_completed_publishing()


        self.do_patching(config_content=config_content, cmdline_args=cmdline_args)
        self.patch('time.time', side_effect=lambda: cur_time)
        cur_time = 0.77  # (<- incremented by certain `ExampleCollector`'s methods...)
        rec = self._prepare_recording_mock(name_to_side_effect)

        if expected_exc_and_regex:
            with self.assertRaisesRegex(*expected_exc_and_regex):
                ExampleCollector.run_script()
        else:
            ExampleCollector.run_script()

        self.assertEqual(rec.mock_calls, expected_recorded_calls)


    def _prepare_recording_mock(self, name_to_side_effect):
        rec = MagicMock()
        rec.publish_output = self.publish_output_mock
        self.patch(
            'n6datasources.collectors.base.logging_configured',
            rec._external_func__logging_configured)
        for name, side_effect in name_to_side_effect.items():
            mock = getattr(rec, name)
            mock.side_effect = side_effect
        return rec


@expand
class TestBaseTwoPhaseCollector(BaseCollectorTestCase):

    @paramseq
    def cases(cls):
        # Note ad the test parameter `expected_recorded_method_calls`:
        # in this test class we record invocations of the following
        # methods: `obtain_input_pile()`, `generate_input_data_dicts()`,
        # `get_output_components()`, `publish_output()` and
        # `after_completed_publishing()` (see the implementation
        # of `test()` below...).

        for raw_type, content_type in [
            ('stream', None),
            ('file', 'application/jwt'),
            ('blacklist', 'text/csv'),
        ]:
            # The expected value of `publish_output()` calls' 3rd
            # argument (`prop_kwargs`). Note: more of this argument's
            # details are covered in some other tests (in particular,
            # see `cases()` of `TestBaseSimpleCollector`).
            expected_prop_kwargs = {
                'timestamp': AnyInstanceOf(int),
                'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                'type': raw_type,
                'headers': {},
            }
            if content_type is not None:
                expected_prop_kwargs['content_type'] = content_type

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                input_pile=sentinel.input_pile_carrying_one,
                expected_recorded_method_calls=[
                    call.obtain_input_pile(),
                    call.generate_input_data_dicts(sentinel.input_pile_carrying_one),
                    call.get_output_components(foo=1),
                    call.publish_output(
                        # routing_key
                        'x.y',

                        # body
                        b"source: 'x.y', foo: 1, bar: '\xc4\x85'",

                        # prop_kwargs
                        expected_prop_kwargs,
                    ),
                    call.after_completed_publishing(),
                ],
            )

            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                input_pile=sentinel.input_pile_carrying_many,
                expected_recorded_method_calls=[
                    call.obtain_input_pile(),
                    call.generate_input_data_dicts(sentinel.input_pile_carrying_many),
                    call.get_output_components(foo=1, bar=42),
                    call.publish_output(
                        # routing_key
                        'example-provider.example-channel',

                        # body
                        b"source: 'example-provider.example-channel', foo: 1, bar: 42",

                        # prop_kwargs
                        expected_prop_kwargs,
                    ),
                    call.get_output_components(foo='2', bar=[443]),
                    call.publish_output(
                        # routing_key
                        'example-provider.example-channel',

                        # body
                        b"source: 'example-provider.example-channel', foo: '2', bar: [443]",

                        # prop_kwargs
                        expected_prop_kwargs,
                    ),
                    call.get_output_components(foo=b'3'),
                    call.publish_output(
                        # routing_key
                        'x.y',

                        # body
                        b"source: 'x.y', foo: b'3', bar: '\xc4\x85'",

                        # prop_kwargs
                        expected_prop_kwargs,
                    ),
                    call.after_completed_publishing(),
                ],
            )

            # Note: `obtain_input_pile()` returning `None` is the
            # clean way (*without* logging any warnings) to signal
            # that there is no data to publish. Also, note that, in
            # such a case, the `after_completed_publishing()` hook
            # is *not* called.
            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                input_pile=None,
                expected_recorded_method_calls=[
                    call.obtain_input_pile(),
                ],
            )

            # Note: `generate_input_data_dicts()` yielding *no data*
            # causes that a warning is logged. Also, note that, in
            # such a case, the `after_completed_publishing()` hook
            # *is* called.
            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                input_pile=sentinel.input_pile_carrying_nothing,
                expected_recorded_method_calls=[
                    call.obtain_input_pile(),
                    call.generate_input_data_dicts(sentinel.input_pile_carrying_nothing),
                    call.after_completed_publishing(),
                ],
                expected_logger_warning_count=1,
            )

    @foreach(cases)
    def test(self,
             raw_type_and_content_type,
             input_pile,
             expected_recorded_method_calls,
             expected_logger_warning_count=0):

        input_pile_to_seq_of_input_data_dicts = {
            sentinel.input_pile_carrying_one: [
                dict(foo=1),
            ],
            sentinel.input_pile_carrying_many: [
                dict(foo=1, bar=42),
                dict(foo='2', bar=[443]),
                dict(foo=b'3'),
            ],
            sentinel.input_pile_carrying_nothing: [],
        }

        class ExampleCollector(BaseTwoPhaseCollector):  # noqa

            raw_type, content_type = raw_type_and_content_type

            def obtain_input_pile(self):
                rec.obtain_input_pile()
                return input_pile

            def generate_input_data_dicts(self, input_pile, /):
                rec.generate_input_data_dicts(input_pile)
                input_data_dicts = input_pile_to_seq_of_input_data_dicts[input_pile]
                for input_data in input_data_dicts:
                    assert isinstance(input_data, dict)
                    yield input_data

            def get_output_components(self, **input_data):
                rec.get_output_components(**input_data)
                return super().get_output_components(**input_data)

            def get_source(self, **processed_data):
                return (
                    'example-provider.example-channel' if 'bar' in processed_data
                    else 'x.y')

            def get_output_data_body(self, *, source, foo, bar='ą'):  # noqa
                return f'source: {source!r}, foo: {foo!r}, bar: {bar!r}'.encode('utf-8')

            def after_completed_publishing(self):
                rec.after_completed_publishing()

        logger_warning_mock = self.patch('n6datasources.collectors.base.LOGGER').warning
        collector = self.prepare_collector(ExampleCollector)
        rec = Mock()
        rec.publish_output = self.publish_output_mock

        collector.run_collection()

        self.assertEqual(rec.mock_calls, expected_recorded_method_calls)
        self.assertEqual(logger_warning_mock.call_count, expected_logger_warning_count)


@expand
class TestBaseSimpleCollector(BaseCollectorTestCase):

    @paramseq
    def data_body_cases(cls):
        # Note ad the test parameter `expected_recorded_method_calls`:
        # in this test class we record only invocations of two methods:
        # `publish_output()` and `after_completed_publishing()` (see the
        # implementation of `test()` below...).

        yield param(
            data_body=None,
            expected_recorded_method_calls=[],
        )
        yield param(
            data_body=b'{"foo": "bar"}',
            expected_recorded_method_calls=[
                call.publish_output(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    b'{"foo": "bar"}',

                    # prop_kwargs (note: this argument's details
                    # are already covered in some other tests)
                    AnyInstanceOf(dict),
                ),
                call.after_completed_publishing(),
            ],
        )

    @foreach(example_valid_raw_type_and_content_type_cases)
    @foreach(data_body_cases)
    def test(self,
             raw_type_and_content_type,
             data_body,
             expected_recorded_method_calls):

        class ExampleSimpleCollector(BaseSimpleCollector):  # noqa

            raw_type, content_type = raw_type_and_content_type

            def obtain_data_body(self):
                return data_body

            def get_source(self, **kwargs):
                return 'example-provider.example-channel'

            def after_completed_publishing(self):
                rec.after_completed_publishing()

        collector = self.prepare_collector(ExampleSimpleCollector)
        rec = Mock()
        rec.publish_output = self.publish_output_mock

        collector.run_collection()

        self.assertEqual(rec.mock_calls, expected_recorded_method_calls)


@expand
class TestBaseSimpleEmailCollector(BaseCollectorTestCase):

    @paramseq
    def cases(cls):
        # Note ad the test parameter `expected_recorded_method_calls`:
        # in this test class we record only invocations of two methods:
        # `publish_output()` and `after_completed_publishing()` (see the
        # implementation of `test()` below...).

        for raw_type, content_type in [
            ('stream', None),
            ('file', 'application/jwt'),
            ('blacklist', 'text/csv'),
        ]:
            yield param(
                raw_type_and_content_type=(raw_type, content_type),
                raw_email_msg=(
                    b'Date: Sun, 28 May 2023 07:08:09 +0200 (CEST)\r\n'
                    b'Subject: New  events! \r\n'
                    b'From: "Sophisticated Source" <our.source@example.org>\r\n'
                    b'To: "CSIRT for Solar System" <solar.system.csirt@example.net>\r\n'
                    b'Content-Type: text/plain; charset=utf-8\r\n'
                    b'Content-Transfer-Encoding: quoted-printable\r\n'
                    b'\r\n'
                    b'Przepraszamy, brak iwent=C3=B3w, bo nie dowie=C5=BAli...\r\n'),
                expected_recorded_method_calls=[],
            )

            for raw_subject in [None, b'Subject: New  events! \r\n']:
                for raw_date in [None,  b'Date: Mon, 29 May 2023 10:11:12 +0200 (CEST)\r\n']:

                    expected_headers = {}
                    if raw_subject or raw_date:
                        expected_headers['meta'] = {}
                        if raw_subject:
                            expected_headers['meta']['mail_subject'] = 'New events!'
                        if raw_date:
                            expected_headers['meta']['mail_time'] = '2023-05-29 08:11:12'  # (UTC)

                    yield param(
                        raw_type_and_content_type=(raw_type, content_type),
                        raw_email_msg=(
                            (raw_date or b'') +
                            (raw_subject or b'') +
                            b'From: "Sophisticated Source" <our.source@example.org>\r\n'
                            b'To: "CSIRT for Solar System" <solar.system.csirt@example.net>\r\n'
                            b'Content-Type: text/plain; charset=utf-8\r\n'
                            b'Content-Transfer-Encoding: quoted-printable\r\n'
                            b'\r\n'
                            b'Dzie=C5=84 dobry!\r\n'
                            b'\r\n'
                            b'Oto nasze =C5=9Bwie=C5=BCutkie iwenty:\r\n'
                            b'\r\n'
                            b'Pierwszy...\r\n'
                            b'Drugi...\r\n'
                            b'Ty=C5=BC i trzeci.\r\n'
                            b'\r\n'
                            b'To wszystko, dzi=C4=99kujemy za uwag=C4=99!\r\n'),
                        expected_recorded_method_calls=[
                            call.publish_output(
                                # routing_key
                                'example-provider.example-channel',

                                # body
                                bytes(
                                    'Dzień dobry!\n'
                                    '\n'
                                    'Oto nasze świeżutkie iwenty:\n'
                                    '\n'
                                    'Pierwszy...\n'
                                    'Drugi...\n'
                                    'Tyż i trzeci.\n'
                                    '\n'
                                    'To wszystko, dziękujemy za uwagę!\n',
                                    encoding='utf-8'),

                                # prop_kwargs
                                {
                                    'timestamp': AnyInstanceOf(int),
                                    'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                                    'headers': expected_headers,
                                    'type': raw_type,
                                } | ({'content_type': content_type} if content_type is not None
                                     else {})
                            ),
                            call.after_completed_publishing(),
                        ],
                    )

    @foreach(cases)
    def test(self,
             raw_type_and_content_type,
             raw_email_msg,
             expected_recorded_method_calls):

        class ExampleSimpleEmailCollector(BaseSimpleEmailCollector):  # noqa

            raw_type, content_type = raw_type_and_content_type

            def obtain_data_body(self):
                content = self.email_msg.find_content(
                    content_type='text/plain',
                    content_regex='^Oto nasze świeżutkie iwenty:$')
                if content is not None:
                    return content.encode('utf-8')
                return None

            def get_source(self, **kwargs):
                return 'example-provider.example-channel'

            def after_completed_publishing(self):
                rec.after_completed_publishing()

        collector = self.prepare_collector(
            ExampleSimpleEmailCollector,
            stdin_data=raw_email_msg)
        rec = Mock()
        rec.publish_output = self.publish_output_mock

        collector.run_collection()

        self.assertEqual(rec.mock_calls, expected_recorded_method_calls)


## TODO:
# @expand
# class TestBaseDownloadingCollector...


## TODO: incorporate the following test into `TestBaseDownloadingCollector`
##       when it is made... (see the comment above)
##       + add proper tests of new config option (`request_timeout`)
##       see tickets: #9101 + #9070.
@expand
class TestBaseDownloadingCollector__get_request_headers(BaseCollectorTestCase):

    @paramseq
    def configured_and_custom_header_cases():
        for no_custom_request_headers in [None, {}]:
            for no_base_request_headers_config_fragment in ['', 'base_request_headers = {}']:
                yield param(
                    config_content=f'''
                        [ExampleDownloadingCollector]
                        {no_base_request_headers_config_fragment}
                    ''',
                    custom_request_headers=no_custom_request_headers,
                    expected_request_headers={},
                )

            yield param(
                config_content='''
                    [ExampleDownloadingCollector]
                    base_request_headers = {'k': '42', 'BeCeDe': 'Ala ma kota!'}
                ''',
                custom_request_headers=no_custom_request_headers,
                expected_request_headers={'k': '42', 'BeCeDe': 'Ala ma kota!'},
            )

        yield param(
            config_content='''
                [ExampleDownloadingCollector]
                base_request_headers = {'k': '42'}
            ''',
            custom_request_headers={'BeCeDe': 'Ala ma kota!'},
            expected_request_headers={'k': '42', 'BeCeDe': 'Ala ma kota!'},
        )

        for base_request_headers_config_fragment in [
            "",
            "base_request_headers = {}",
            "base_request_headers = {'BeCeDe': 'qwertyuiop'}",
            "base_request_headers = {'K': '123456'}",
            "base_request_headers = {'k': '123456', 'becede': 'ALA MA KOTA!'}",
            "base_request_headers = {'\u212a': '123456', 'bEceDE': 'asdfghjkl'}",
        ]:
            yield param(
                # Note: when base headers are being shadowed by custom
                # headers, keys are matched in a *case-insensitive* way.
                config_content=f'''
                    [ExampleDownloadingCollector]
                    {base_request_headers_config_fragment}
                ''',
                custom_request_headers={'k': '42', 'BeCeDe': 'Ala ma kota!'},
                expected_request_headers={'k': '42', 'BeCeDe': 'Ala ma kota!'},
            )

    @foreach(example_valid_raw_type_and_content_type_cases)
    @foreach(configured_and_custom_header_cases)
    def test(self,
             raw_type_and_content_type,
             config_content,
             custom_request_headers,
             expected_request_headers):

        class ExampleDownloadingCollector(BaseDownloadingCollector):
            raw_type, content_type = raw_type_and_content_type

        collector = self.prepare_collector(
            ExampleDownloadingCollector,
            config_content=config_content)

        result = collector._BaseDownloadingCollector__get_request_headers(custom_request_headers)

        assert isinstance(result, dict)
        assert result == expected_request_headers


@expand
class TestBaseTimeOrderedRowsCollector(BaseCollectorTestCase):

    EXAMPLE_CONFIG = '''
        [ExampleTimeOrderedRowsCollector]
        state_dir = /who/cares
        row_count_mismatch_is_fatal = no
    '''

    EXPECTED_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {},
    }


    class ExampleTimeOrderedRowsCollector(BaseTimeOrderedRowsCollector):

        config_spec_pattern = '''
            [{collector_class_name}]
            state_dir :: path
            row_count_mismatch_is_fatal = no :: bool
        '''

        example_orig_data = None  # to be set on instances by test code

        def get_source(self, **kwargs):
            return 'example-provider.example-channel'

        def obtain_orig_data(self):
            return self.example_orig_data

        def pick_raw_row_time(self, row):
            return extract_field_from_csv_row(row, column_index=1)

        def clean_row_time(self, raw_row_time):
            return raw_row_time


    @paramseq
    def cases(cls):
        yield param(
            # Initial state (one row)
            # and expected saved state (one row)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-13"\n'
                b'\t\n'
                b'"spam","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"spam","2019-07-11"\n'
                        b'"ham","2019-07-13"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-13',
                'newest_rows': {'"ham","2019-07-13"'},
                'rows_count': 7,
            }
        )

        yield param(
            # Same as above but this time we check if the results
            # are the same with `row_count_mismatch_is_fatal` flag
            # set to `True` (in `config_content`).
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = yes
            ''',
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-13"\n'
                b'\t\n'
                b'"spam","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"spam","2019-07-11"\n'
                        b'"ham","2019-07-13"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-13',
                'newest_rows': {'"ham","2019-07-13"'},
                'rows_count': 7,
            }
        )

        yield param(
            # Mostly the same as the first test case, but instead
            # of `date/time-based` order we have ids (just to show that
            # it might work in the same way as with `date/time-based`
            # order)
            # ---
            # Initial state (one row)
            # and expected saved state (one row)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '5',
                'newest_rows': {'"zzz","5"'},
                'rows_count': 5,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","7"\n'
                b'\t\n'
                b'"spam","6"\n'
                b'"zzz","5"\n'
                b'"egg","4"\n'
                b'"sss","3"\n'
                b'\n'
                b'"bar","2"\n'
                b'"foo","1"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"spam","6"\n'
                        b'"ham","7"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '7',
                'newest_rows': {'"ham","7"'},
                'rows_count': 7,
            }
        )

        yield param(
            # Initial state (one row) and
            # expected saved state (two rows)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-11"\n'
                b'\t\n'
                b'"spam","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        # Note that the order of output rows is always
                        # processed in the following way: first it is
                        # *reversed* and then the rows are *sorted* by
                        # row time in a *stable* manner (that is, when
                        # a tie occurs, i.e., when two row times being
                        # compared are equal, the initial reversed order
                        # is preserved; here this rule concerns the rows
                        # `"spam"...` and `"ham"...`).
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"\n'
                        b'"spam","2019-07-11"\n'
                        b'"ham","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-11',
                'newest_rows': {
                    '"ham","2019-07-11"',
                    '"spam","2019-07-11"'
                },
                'rows_count': 7,
            }
        )

        yield param(
            # Initial state (one row) but without expected saved state
            # (no new data)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE)

        yield param(
            # Initial state (two rows)
            # and expected saved state (one row)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {
                    '"spam","2019-07-10"',
                    '"zzz","2019-07-10"'
                },
                'rows_count': 6,
            },
            orig_data=(
                b'"ham","2019-07-11"\n'
                b'"spam","2019-07-10"\n'
                b'"zzz","2019-07-10"\n'
                b'\t\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"ham","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-11',
                'newest_rows': {
                    '"ham","2019-07-11"'
                },
                'rows_count': 7,
            }
        )

        yield param(
            # Initial state (two rows) and
            # expected saved state (also two rows)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"sss","2019-07-02"',
                    '"egg","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-11"\n'
                b'"spam","2019-07-11"\n'
                b'\t\n'
                b'"zzz","2019-07-02"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"zzz","2019-07-02"\n'
                        b'"spam","2019-07-11"\n'
                        b'"ham","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-11',
                'newest_rows': {
                    '"ham","2019-07-11"',
                    '"spam","2019-07-11"'
                },
                'rows_count': 7,
            }
        )

        yield param(
            # Initial state (two rows)
            # but without expected saved state
            # (no new data)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"sss","2019-07-02"',
                    '"egg","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Without initial state but with expected saved state
            # (e.g.first run) - one row
            config_content=cls.EXAMPLE_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data=(
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"foo","2019-06-30"\n'
                        b'"bar","2019-07-01"\n'
                        b'"sss","2019-07-02"\n'
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            }
        )

        yield param(
            # Without initial state but with expected saved state
            # (e.g.first run) - two rows
            config_content=cls.EXAMPLE_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data=(
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-10"\n'
                b'"sss","2019-07-02"\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"foo","2019-06-30"\n'
                        b'"bar","2019-07-01"\n'
                        b'"sss","2019-07-02"\n'
                        b'"egg","2019-07-10"\n'
                        b'"zzz","2019-07-10"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {
                    '"zzz","2019-07-10"',
                    '"egg","2019-07-10"'
                },
                'rows_count': 5,
            }
        )

        yield param(
            # Without initial state (e.g. first run) and without
            # expected saved state (no data at all - just empty string)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data=b'',
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Initial state one row, another row with the same date
            # in orig data - we expect to get this row
            # Expected saved state:
            #   - old row (counted in rows_count)
            #   - new row
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"egg","2019-07-02"',
                    '"sss","2019-07-02"'
                },
                'rows_count': 4,
            }
        )

        yield param(
            # Initial state one row, orig data consists of two
            # additional (new) rows with the same date as "state row"
            # - we expect to get only these two new rows
            # Expected saved state - old row + two new rows
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-02"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"ham","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"egg","2019-07-02"',
                    '"sss","2019-07-02"',
                    '"ham","2019-07-02"'
                },
                'rows_count': 5,
            }
        )

        yield param(
            # Initial state two rows, orig data consists of one
            # additional (new) row with the same date as "state row"
            # - we expect to get only this new row
            # Expected saved state - old rows + new row
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"egg","2019-07-02"',
                    '"sss","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"ham","2019-07-02"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"ham","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"egg","2019-07-02"',
                    '"sss","2019-07-02"',
                    '"ham","2019-07-02"'
                },
                'rows_count': 5,
            }
        )

        yield param(
            # Initial state one row, another row with the same date
            # in orig data - we expect to get this row
            # Expected state: new row (different, latest date)
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            }
        )

        yield param(
            # Same as above but now we are testing `initial_state`
            # **without** `rows_count` key (legacy state).
            # We expect that we'll have `rows_count` key
            # in `expected_saved_state`.
            config_content=cls.EXAMPLE_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"zzz","2019-07-10"\n'
                b'"egg","2019-07-02"\n'
                b'"sss","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            }
        )

        yield param(
            # Same as two above but now we are testing `initial_state`
            # **with** `rows_count` key set to incorrect rows count
            # values. We assume here, that this situation might happen
            # when the source does not meet our requirements (see docs)
            # and we have `row_count_mismatch_is_fatal` flag
            # set to `False` (in `config_content`).

            # We expect correct `expected_saved_state` (len() of all rows)
            # and a warning in logs.
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = no
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_logger_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            }
        )

        yield param(
            # Same as above but now we are testing
            # `row_count_mismatch_is_fatal` flag set to True.
            # We expect ValueError (+ an error in logs).
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = yes
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_error=ValueError,
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Similar to the ones above but now we are testing
            # reaction to duplicates in the `fresh_rows` when the
            # `row_count_mismatch_is_fatal` flag is set to True.
            # We expect ValueError (+ an error in logs).
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = yes
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"zzz","2019-07-10"\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_error=ValueError,
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )
        yield param(
            # Same as the one above but now we are testing
            # reaction to duplicates in the `fresh_rows` when the
            # `row_count_mismatch_is_fatal` flag is set to False.
            #
            # We expect correct `expected_saved_state` (len of all rows)
            # and a warning in logs.
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = no
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"www","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_logger_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"\n'
                        b'"zzz","2019-07-10"\n'
                        b'"www","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-11',
                'newest_rows': {'"www","2019-07-11"'},
                'rows_count': 7,
            }
        )

        yield param(
            # Now we are focusing on:
            #  * mismatch in counted rows
            #  * duplicates in fresh_rows
            # while `row_count_mismatch_is_fatal` flag is set to False.
            #
            # We expect correct `expected_saved_state` (len of all rows)
            # and a warning in logs.
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = no
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"www","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_logger_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"egg","2019-07-02"\n'
                        b'"zzz","2019-07-10"\n'
                        b'"zzz","2019-07-10"\n'
                        b'"www","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-11',
                'newest_rows': {'"www","2019-07-11"'},
                'rows_count': 7,
            }
        )

        yield param(
            # Now we are focusing on:
            #  * mismatch in counted rows
            #  * duplicates in fresh_rows
            # while `row_count_mismatch_is_fatal` flag is set to `True`.
            #
            # We expect ValueError.
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
                row_count_mismatch_is_fatal = yes
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"www","2019-07-11"\n'
                b'"zzz","2019-07-10"\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-01"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_error=ValueError,
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Data from source is not sorted,
            # `older` rows are mixed with newer ones.
            config_content='''
                [ExampleTimeOrderedRowsCollector]
                state_dir = /who/cares
            ''',
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5
            },
            orig_data=(
                b'# halo,m\xc3\xb3wi\xc4\x99...\n'
                b'"spam","2019-07-11"\n'
                b'"ham","2019-07-13"\n'
                b'\t\n'
                b'"zzz","2019-07-10"\n'
                b'"sss","2019-07-02"\n'
                b'"egg","2019-07-02"\n'
                b'\n'
                b'"bar","2019-07-01"\n'
                b'"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'example-provider.example-channel',

                    # body
                    (
                        b'"spam","2019-07-11"\n'
                        b'"ham","2019-07-13"'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-07-13',
                'newest_rows': {'"ham","2019-07-13"'},
                'rows_count': 7,
            }
        )


    @foreach(cases)
    def test(self,
             config_content,
             initial_state,
             orig_data,
             expected_publish_output_calls,
             expected_saved_state,
             expected_logger_warning_count=0,
             expected_error=None):

        logger_warning_mock = self.patch('n6datasources.collectors.base.LOGGER').warning
        collector = self.prepare_collector(
            self.ExampleTimeOrderedRowsCollector,
            config_content=config_content,
            initial_state=initial_state)
        collector.example_orig_data = orig_data

        if expected_error is not None:
            with self.assertRaises(expected_error):
                collector.run_collection()
        else:
            collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)
        self.assertEqual(logger_warning_mock.call_count, expected_logger_warning_count)


@expand
class TestStatefulCollectorMixin(BaseCollectorTestCase):

    patch_StatefulCollectorMixin = False


    #
    # Fixture elements and helpers

    class BareSubclass(StatefulCollectorMixin):
        pass

    assert not issubclass(BareSubclass, LegacyQueuedBase)


    DEFAULT_STATE = 'This is default state - test'

    class ExampleStatefulCollector(StatefulCollectorMixin, BaseCollector):  # noqa

        # (required to create a subclass of `BaseCollector`)
        raw_type = 'stream'

        # (just to show that inheriting the `state_dir` option works)
        config_spec_pattern = combined_config_spec('''
            [{collector_class_name}]

            unrelated_option = irrelevant_default_value
        ''')

        def get_source(self, **kwargs):
            return 'example-provider.example-channel'

        def make_default_state(self):
            return TestStatefulCollectorMixin.DEFAULT_STATE


    def _prepare_collector_and_state_dir(self, raw_type, content_type, create_state_dir=True):
        parent_dir = tempfile.mkdtemp(prefix='n6-TestStatefulCollectorMixin')
        self.addCleanup(shutil.rmtree, parent_dir)  # noqa
        state_dir = osp.join(parent_dir, '.n6state')
        if create_state_dir:
            os.makedirs(state_dir, 0o700)
        collector_class = self.ExampleStatefulCollector
        self.patch_object(collector_class, 'raw_type', raw_type)
        self.patch_object(collector_class, 'content_type', content_type)
        collector = self.prepare_collector(
            collector_class,
            config_content=f'''
                [{collector_class.__name__}]
                state_dir = {state_dir}
            ''')
        return collector, state_dir


    #
    # Test parameters

    @paramseq
    def state_cases():  # noqa
        yield param(
            state='1 2 3 abc',
        )
        yield param(
            state=['whatever', 42, True],
        )
        yield param(
            state=None,
        )
        yield param(
            state='żółte kąty',
        )
        yield param(
            state=b'\xc5\xbc\xc3\xb3\xc5\x82te k\xc4\x85ty',
        )
        yield param(
            state=datetime.date(2022, 1, 3),
        )
        yield param(
            state={b'\xdc': datetime.date(2022, 1, 3), (1.3,): {1.3j}},
        )

    @paramseq
    def state_dir_existence_cases():  # noqa
        yield param(
            already_existing_state_dir=True,
        )
        yield param(
            already_existing_state_dir=False,
        )


    #
    # Actual tests

    @foreach(state_cases)
    @foreach(state_dir_existence_cases)
    @foreach(example_valid_raw_type_and_content_type_cases)
    def test_saving_and_loading_state(self,
                                      state,
                                      already_existing_state_dir,
                                      raw_type_and_content_type):
        logger_warning_mock = self.patch('n6datasources.collectors.base.LOGGER').warning
        collector, state_dir = self._prepare_collector_and_state_dir(
            *raw_type_and_content_type,
            create_state_dir=already_existing_state_dir)
        expected_state_file_name = (
            f'{__name__}'
            f'.TestStatefulCollectorMixin'
            f'.ExampleStatefulCollector'
            f'.pickle')
        assert (
            # No state has been saved.
            os.listdir(state_dir) == [] if already_existing_state_dir
            else not osp.exists(state_dir))
        assert logger_warning_mock.call_count == 0

        collector.save_state(state)
        loaded_state = collector.load_state()

        [real_state_file_name] = os.listdir(state_dir)
        self.assertEqual(loaded_state, state)
        self.assertEqual(real_state_file_name, expected_state_file_name)
        self.assertEqual(logger_warning_mock.call_count, 0)


    @foreach(state_dir_existence_cases)
    @foreach(example_valid_raw_type_and_content_type_cases)
    def test_using_default_state(self,
                                 already_existing_state_dir,
                                 raw_type_and_content_type):
        logger_warning_mock = self.patch('n6datasources.collectors.base.LOGGER').warning
        collector, state_dir = self._prepare_collector_and_state_dir(
            *raw_type_and_content_type,
            create_state_dir=already_existing_state_dir)
        def no_state_saved():
            return (
                os.listdir(state_dir) == [] if already_existing_state_dir
                else not osp.exists(state_dir))
        assert no_state_saved()
        assert logger_warning_mock.call_count == 0

        loaded_state = collector.load_state()

        self.assertEqual(loaded_state, self.DEFAULT_STATE)
        self.assertEqual(logger_warning_mock.call_count, 1)
        self.assertTrue(no_state_saved())

        default_state = collector.make_default_state()

        self.assertEqual(default_state, self.DEFAULT_STATE)
        self.assertTrue(no_state_saved())


    def test__get_state_file_name(self):
        obj = self.BareSubclass.__new__(self.BareSubclass)
        expected_state_file_name = (
            f'{__name__}'
            f'.TestStatefulCollectorMixin'
            f'.BareSubclass'
            f'.pickle')

        state_file_name = obj.get_state_file_name()

        self.assertEqual(state_file_name, expected_state_file_name)


    def test__get_state_file_name__raises_error_if_collector_module_name_is_dunder_main(self):
        self.patch_object(self.BareSubclass, '__module__', '__main__')
        obj = self.BareSubclass.__new__(self.BareSubclass)
        expected_error_regex = (
            r"'__main__' is not the proper name of "
            r"the module containing \S+\.BareSubclass")

        with self.assertRaisesRegex(ValueError, expected_error_regex):
            obj.get_state_file_name()


    def test__make_default_state__base_version(self):
        obj = self.BareSubclass.__new__(self.BareSubclass)

        default_state = obj.make_default_state()

        self.assertIsNone(default_state)


    def test__init__setting_default_state_pickle_protocol(self):
        collector = self.prepare_collector(self.ExampleStatefulCollector)
        self.assertEqual(collector._state_pickle_protocol, pickle.HIGHEST_PROTOCOL)


    def test__init__setting_customized_state_pickle_protocol(self):
        collector = self.prepare_collector(
            self.ExampleStatefulCollector,
            additional_init_kwargs=dict(state_pickle_protocol=3))
        self.assertEqual(collector._state_pickle_protocol, 3)
        self.assertNotEqual(collector._state_pickle_protocol, pickle.HIGHEST_PROTOCOL)


    def test_subclassing_when_obsolete_attr_pickle_protocol_is_present_causes_error(self):
        expected_error_regex = (
            r"unsupported attributes .* set to non-None values:.* 'pickle_protocol'")

        with self.assertRaisesRegex(TypeError, expected_error_regex):
            class SomeSubclass(self.BareSubclass):
                pickle_protocol = 3


    @foreach(
        param(
            state_file_content=(
                b'\x80\x05\x953\x00\x00\x00\x00\x00\x00\x00}\x94\x8c\x03now'
                b'\x94\x8c\x08datetime\x94\x8c\x08datetime\x94\x93\x94C\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x94\x85\x94R\x94s.'),
            expected_loaded_state={'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-5: with-datetime pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x04\x953\x00\x00\x00\x00\x00\x00\x00}\x94\x8c\x03now'
                b'\x94\x8c\x08datetime\x94\x8c\x08datetime\x94\x93\x94C\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x94\x85\x94R\x94s.'),
            expected_loaded_state={'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-4: with-datetime pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x04\x95\x0b\x00\x00\x00\x00\x00\x00\x00]\x94'
                b'(K\x01K*K\x10e.'),
            expected_loaded_state=[1, 42, 16],
        ).label('Protocol-4: non-problematic pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x04\x95\x14\x00\x00\x00\x00\x00\x00\x00]\x94'
                b'(K*\x8c\nja\xc5\xba\xc5\x84 \xed\xb3\x9d\x94e.'),
            expected_loaded_state=[42, 'jaźń \udcdd'],
        ).label('Protocol-4: with-UTF-8-with-surrogate-text pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x04\x95\x12\x00\x00\x00\x00\x00\x00\x00]\x94'
                b'(K*C\x08ja\xc5\xba\xc5\x84 \xdd\x94e.'),
            expected_loaded_state=[42, b'ja\xc5\xba\xc5\x84 \xdd'],
        ).label('Protocol-4: with-not-only-UTF-8-bytes pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x03}q\x00X\x03\x00\x00\x00nowq\x01cdatetime\ndatetime\nq'
                b'\x02C\n\x07\xe6\x08\x19\x0f\x08/\x0c\x05bq\x03\x85q\x04Rq\x05s.'),
            expected_loaded_state={'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-3: with-datetime from Py3'),

        param(
            state_file_content=(
                b'\x80\x02}q\x00X\x03\x00\x00\x00nowq\x01cdatetime\ndatetime\nq'
                b'\x02c_codecs\nencode\nq\x03X\x0b\x00\x00\x00\x07\xc3\xa6'
                b'\x08\x19\x0f\x08/\x0c\x05bq\x04X\x06\x00\x00\x00latin1q\x05'
                b'\x86q\x06Rq\x07\x85q\x08Rq\ts.'),
            expected_warning_count=2,
            expected_loaded_state={'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-2: with-datetime pickle from Py3'),

        param(
            state_file_content=(
                b'\x80\x02}q\x01U\x03nowq\x02cdatetime\ndatetime\nq\x03U\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x85Rq\x04s.'),
            expected_warning_count=1,
            expected_exc=SystemExit,
        ).label('Protocol-2: with-datetime pickle from Py2'),

        param(
            state_file_content=(
                b'\x80\x02}q\x01U\x03nowq\x02cdatetime\ndatetime\nq\x03U\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x85Rq\x04s.'),
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='latin1', errors='strict',
            ),
            expected_warning_count=2,
            expected_loaded_state={'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-2: with-datetime pickle from Py2, '
                'encoding="latin1"'),

        param(
            state_file_content=(
                b'\x80\x02}q\x01U\x03nowq\x02cdatetime\ndatetime\nq\x03U\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x85Rq\x04s.'),
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='bytes', errors='strict',
            ),
            expected_warning_count=2,
            expected_loaded_state={b'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)},
        ).label('Protocol-2: with-datetime pickle from Py2, '
                'encoding="bytes"'),

        param(
            state_file_content=(
                b'\x80\x02}q\x01U\x03nowq\x02cdatetime\ndatetime\nq\x03U\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\x85Rq\x04s.'),
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='bytes', errors='strict',
            ),
            adjust_state_from_py2_pickle__own_impl=repr,
            expected_warning_count=2,
            expected_loaded_state="{b'now': datetime.datetime(2022, 8, 25, 15, 8, 47, 787810)}",
        ).label('Protocol-2: with-datetime pickle from Py2, '
                'encoding="latin1", custom `adjust_state_from_py2_pickle()`'),

        param(
            state_file_content=b'\x80\x02]q\x01(K\x01K*K\x10e.',
            expected_warning_count=2,
            expected_loaded_state=[1, 42, 16],
        ).label('Protocol-2: non-problematic pickle from Py2'),

        param(
            state_file_content=b'\x80\x02]q\x01(K\x01K*K\x10e.',
            adjust_state_from_py2_pickle__own_impl=repr,
            expected_warning_count=2,
            expected_loaded_state='[1, 42, 16]',
        ).label('Protocol-2: non-problematic pickle from Py2, '
                'custom `adjust_state_from_py2_pickle()`'),

        param(
            state_file_content=(
                b'\x80\x02]q\x01(K*X\n\x00\x00\x00ja\xc5\xba\xc5\x84 \xed\xb3\x9dq\x02e.'),
            expected_warning_count=2,
            expected_loaded_state=[42, 'jaźń \udcdd'],
        ).label('Protocol-2: with-UTF-8-with-surrogate-text pickle from Py2'),

        param(
            state_file_content=b'\x80\x02]q\x01(K*U\x08ja\xc5\xba\xc5\x84 \xddq\x02e.',
            expected_warning_count=1,
            expected_exc=SystemExit,
        ).label('Protocol-2: with-not-only-UTF-8-bytes pickle from Py2'),

        param(
            state_file_content=b'\x80\x02]q\x01(K*U\x08ja\xc5\xba\xc5\x84 \xddq\x02e.',
            expected_warning_count=1,
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='utf-8',
            ),
            expected_exc=SystemExit,
        ).label('Protocol-2: with-not-only-UTF-8-bytes pickle from Py2, '
                'encoding="utf-8"'),

        param(
            state_file_content=b'\x80\x02]q\x01(K*U\x08ja\xc5\xba\xc5\x84 \xddq\x02e.',
            expected_warning_count=2,
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='utf-8', errors='surrogateescape',
            ),
            expected_loaded_state=[42, 'jaźń \udcdd'],
        ).label('Protocol-2: with-not-only-UTF-8-bytes pickle from Py2, '
                'encoding="utf-8", errors="surrogateescape"'),

        param(
            state_file_content=b'\x80\x02]q\x01(K*U\x08ja\xc5\xba\xc5\x84 \xddq\x02e.',
            expected_warning_count=2,
            get_py2_pickle_load_kwargs__own_impl=lambda: dict(
                encoding='bytes', errors='strict',
            ),
            expected_loaded_state=[42, b'ja\xc5\xba\xc5\x84 \xdd'],
        ).label('Protocol-2: with-not-only-UTF-8-bytes pickle from Py2, encoding="bytes"'),

        param(
            state_file_content=b'',
            expected_exc=EOFError,
        ).label('empty'),

        param(
            state_file_content=b'x',
            expected_exc=pickle.UnpicklingError,
        ).label('1-byte garbage'),

        param(
            state_file_content=b'xy',
            expected_exc=SystemExit,
        ).label('2-bytes garbage'),

        param(
            state_file_content=b'xyz1234567890',
            expected_exc=SystemExit,
        ).label('longer garbage'),

        param(
            state_file_content=(
                b'}q\x00X\x03\x00\x00\x00nowq\x01cdatetime\ndatetime\n'
                b'q\x02(c_codecs\nencode\nq\x03(X\x0b\x00\x00\x00\x07'
                b'\xc3\xa6\x08\x19\x0f\x08/\x0c\x05bq\x04X\x06\x00\x00'
                b'\x00latin1q\x05tq\x06Rq\x07tq\x08Rq\ts.'),
            expected_exc=SystemExit,
        ).label('Protocol-1 from Py3: treated as garbage.'),

        param(
            state_file_content=(
                b'}q\x01U\x03nowq\x02cdatetime\ndatetime\nq\x03(U\n'
                b'\x07\xe6\x08\x19\x0f\x08/\x0c\x05btRq\x04s.'),
            expected_exc=SystemExit,
        ).label('Protocol-1 from Py2: treated as garbage.'),

        param(
            state_file_content=(
                b'(dp0\nVnow\np1\ncdatetime\ndatetime\np2\n(c_codecs\n'
                b'encode\np3\n(V\x07\xe6\x08\x19\x0f\x08/\x0c\x05b\np4'
                b'\nVlatin1\np5\ntp6\nRp7\ntp8\nRp9\ns.'),
            expected_exc=SystemExit,
        ).label('Protocol-0 from Py3: treated as garbage.'),

        param(
            state_file_content=(
                b"(dp1\nS'now'\np2\ncdatetime\ndatetime\np3\n(S'\\x07"
                b"\\xe6\\x08\\x19\\x0f\\x08/\\x0c\\x05b'\ntRp4\ns."),
            expected_exc=SystemExit,
        ).label('Protocol-0 from Py2: treated as garbage.'),

        param(
            state_file_content=b'\x80',
            expected_exc=pickle.UnpicklingError,
        ).label('1-byte like for Pickle Protocol 2, 3 or newer'),

        param(
            state_file_content=b'\x80\x03',
            expected_exc=EOFError,
        ).label('2-bytes like for Pickle Protocol 3 or newer'),

        param(
            state_file_content=b'\x80\x04xyz',
            expected_exc=pickle.UnpicklingError,
        ).label('2-bytes like for Pickle Protocol 3 or newer, then garbage'),

        param(
            state_file_content=b'\x80\x02',
            expected_warning_count=1,
            expected_exc=SystemExit,
        ).label('2-bytes like for Pickle Protocol 2'),

        param(
            state_file_content=b'\x80\x02xyz',
            expected_warning_count=1,
            expected_exc=SystemExit,
        ).label('2-bytes like for Pickle Protocol 2, then garbage'),
    )
    @foreach(example_valid_raw_type_and_content_type_cases)
    def test_loading_state_in_various_pickle_formats(self,
                                                     raw_type_and_content_type,
                                                     state_file_content,
                                                     get_py2_pickle_load_kwargs__own_impl=None,
                                                     adjust_state_from_py2_pickle__own_impl=None,
                                                     expected_warning_count=0,
                                                     expected_loaded_state=None,
                                                     expected_exc=None):
        assert (expected_loaded_state is not None and expected_exc is None
                or expected_loaded_state is None and expected_exc is not None)

        logger_warning_mock = self.patch('n6datasources.collectors.base.LOGGER').warning
        collector, state_dir = self._prepare_collector_and_state_dir(*raw_type_and_content_type)
        if get_py2_pickle_load_kwargs__own_impl is not None:
            collector.get_py2_pickle_load_kwargs = get_py2_pickle_load_kwargs__own_impl
        if adjust_state_from_py2_pickle__own_impl is not None:
            collector.adjust_state_from_py2_pickle = adjust_state_from_py2_pickle__own_impl
        state_file_path = Path(state_dir) / (
            f'{__name__}'
            f'.TestStatefulCollectorMixin'
            f'.ExampleStatefulCollector'
            f'.pickle')
        state_file_path.write_bytes(state_file_content)
        assert logger_warning_mock.call_count == 0
        assert os.listdir(state_dir) == [state_file_path.name]

        if expected_exc is not None:
            with self.assertRaises(expected_exc) as exc_context:
                collector.load_state()
            if isinstance(exc_context.exception, SystemExit):
                self.assertTrue(exc_context.exception.code)
        else:
            loaded_state = collector.load_state()
            self.assertEqual(loaded_state, expected_loaded_state)
        self.assertEqual(logger_warning_mock.call_count, expected_warning_count)


@expand
class Test__add_collector_entry_point_functions(TestCaseMixin, unittest.TestCase):

    @foreach(
        param(module_name='my_specific_test_module'),
        param(module_name='my_specific_test_module.test_collector'),
        param(module_name='_my_specific_test_module'),
        param(module_name='_my_specific_test_module.test_collector'),
    )
    @foreach(
        param(pass_module_obj=True),
        param(pass_module_obj=False),
    )
    def test(self, module_name, pass_module_obj):
        class NonCollectorClass: pass
        class _MyCollectorPriv1(AbstractBaseCollector): pass
        class _MyCollectorPriv2(BaseCollector):
            raw_type = 'stream'
        class _MyCollectorPriv3(BaseTimeOrderedRowsCollector):
            raw_type = 'file'
            content_type = 'text/plain'
        class MyCollector1(AbstractBaseCollector): pass
        class MyCollector2(BaseCollector):
            raw_type = 'stream'
        class MyCollector3(BaseTimeOrderedRowsCollector):
            raw_type = 'file'
            content_type = 'text/plain'
        class MyCollector4(BaseCollector):
            raw_type = 'blacklist'
            content_type = 'text/plain'
            @classmethod
            def run_script(cls): pass
            run_script.__func__.__module__ = module_name                   # noqa
            run_script.__func__.__qualname__ = 'MyCollector4.run_script'   # noqa
        module_obj = ModuleType(module_name)
        self.patch_dict(sys.modules, {module_name: module_obj})
        module_obj.NonCollectorClass = NonCollectorClass
        module_obj.irrelevant_attr = sentinel.irrelevant_attr
        module_obj._MyCollectorPriv1 = _MyCollectorPriv1
        module_obj._MyCollectorPriv2 = _MyCollectorPriv2
        module_obj._MyCollectorPriv3 = _MyCollectorPriv3
        module_obj.MyCollector1 = MyCollector1
        module_obj.MyCollector2 = MyCollector2
        module_obj.MyCollector3 = MyCollector3
        module_obj.MyCollector4 = MyCollector4
        run_script_func_1 = self.check_and_extract_func_from_class_method(MyCollector1.run_script)
        run_script_func_2 = self.check_and_extract_func_from_class_method(MyCollector2.run_script)
        run_script_func_3 = self.check_and_extract_func_from_class_method(MyCollector3.run_script)
        run_script_func_4 = self.check_and_extract_func_from_class_method(MyCollector4.run_script)
        assert run_script_func_1 is run_script_func_2 is run_script_func_3 is not run_script_func_4

        add_collector_entry_point_functions(
            module_obj if pass_module_obj
            else module_name)

        # * No entry points for private collectors and non-collector objects:
        self.assertFalse(hasattr(module_obj, 'NonCollectorClass_main'))
        self.assertFalse(hasattr(module_obj, 'irrelevant_attr_main'))
        self.assertFalse(hasattr(module_obj, '_MyCollectorPriv1_main'))
        self.assertFalse(hasattr(module_obj, '_MyCollectorPriv2_main'))
        self.assertFalse(hasattr(module_obj, '_MyCollectorPriv3_main'))
        # * On the other hand, each public collector deserves its entry point:
        self.assertTrue(hasattr(module_obj, 'MyCollector1_main'))
        self.assertTrue(hasattr(module_obj, 'MyCollector2_main'))
        self.assertTrue(hasattr(module_obj, 'MyCollector3_main'))
        self.assertTrue(hasattr(module_obj, 'MyCollector4_main'))
        entry_func_1 = self.check_and_extract_func_from_class_method(module_obj.MyCollector1_main)
        entry_func_2 = self.check_and_extract_func_from_class_method(module_obj.MyCollector2_main)
        entry_func_3 = self.check_and_extract_func_from_class_method(module_obj.MyCollector3_main)
        entry_func_4 = self.check_and_extract_func_from_class_method(module_obj.MyCollector4_main)
        self.assertIs(entry_func_1, run_script_func_1)
        self.assertIs(entry_func_2, run_script_func_2)
        self.assertIs(entry_func_3, run_script_func_3)
        self.assertIs(entry_func_4, run_script_func_4)

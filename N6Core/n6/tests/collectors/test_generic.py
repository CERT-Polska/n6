# -*- coding: utf-8 -*-

# Copyright (c) 2013-2022 NASK. All rights reserved.

import datetime
import hashlib
import shutil
import tempfile
import unittest

from mock import (                                                               #3: ->unittest.mock...
    ANY,
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

from n6corelib.email_message import ReceivedEmailMessage                         #3-- (at least for now)...
from n6lib.common_helpers import PlainNamespace
from n6lib.config import (
    ConfigError,
    ConfigSection,
)
from n6lib.csv_helpers import extract_field_from_csv_row
from n6lib.unit_test_helpers import patch_always                                 #3--
from n6.base.queue import QueuedBase                                             #3: n6.base.queue->n6datapipeline.base, QueuedBase->LegacyQueuedBase
from n6.collectors.generic import (                                              #3: **everywhere** n6.collectors.generic -> n6datasources.collectors.base
    BaseCollector,
    BaseEmailSourceCollector,                                                    #3-- (at least for now)...
    BaseOneShotCollector,
    BaseTimeOrderedRowsCollector,
    BaseUrlDownloaderCollector,                                                  #3--
    CollectorWithStateMixin,                                                     #3: ->StatefulCollectorMixin...
)
from n6.tests.collectors._collector_test_helpers import _BaseCollectorTestCase


SAMPLE_ARG_A = sentinel.a                                                        #3: check whether all those constants are in use
SAMPLE_ARG_B = sentinel.b
SAMPLE_CONFIG_SECTION = "some_section"
SAMPLE_OTHER_CONFIG_SECTION = "other_section"
SAMPLE_CONFIG_REQUIRED = ('required_opt',)
SAMPLE_REQUIRED_VALUE = "some option which is required"
SAMPLE_OTHER_REQUIRED_VALUE = "123.89"
CONFIG_WITH_NO_SECTION_DECLARED = ConfigSection('<no section declared>')
MOCKED_CONFIG = {
    'some_section': {
        'required_opt': SAMPLE_REQUIRED_VALUE,
        'some_opt': "ABc dd",
    },
    'other_section': {
        'required_opt': SAMPLE_OTHER_REQUIRED_VALUE,
        'some_opt': '[{"a": "bcd"}]',
    },
}
MOCKED_SUPER_CLS = PlainNamespace(__init__=Mock())
SAMPLE_EMAIL_MESSAGE = sentinel.email_msg
SAMPLE_INPUT_DATA = sentinel.input_data
SAMPLE_MESSAGE_ID = sentinel.message_id
SAMPLE_SOURCE = sentinel.source
SAMPLE_SOURCE_CHANNEL = sentinel.source_channel
SAMPLE_TYPE = sentinel.type
SAMPLE_CONTENT_TYPE = 'text/csv'
SAMPLE_OUTPUT_COMPONENTS = sentinel.output_components
SAMPLE_OUTPUT_RK = sentinel.output_rk
SAMPLE_OUTPUT_DATA_BODY = sentinel.output_data_body
SAMPLE_OUTPUT_PROP_KWARGS = sentinel.output_prop_kwargs

CONFIG_PATCHER = patch('n6lib.config.Config._load_n6_config_files', return_value=MOCKED_CONFIG)
SUPER_PATCHER = patch('n6.collectors.generic.super', return_value=MOCKED_SUPER_CLS, create=True)
STDERR_PATCHER = patch('sys.stderr')


@expand
class TestBaseCollector(unittest.TestCase):

    def test_basics(self):
        self.assertTrue(issubclass(BaseCollector, QueuedBase))                   #3: QueuedBase->LegacyQueuedBase
        self.assertTrue(hasattr(BaseCollector, 'output_queue'))                  #3: revise the attributes to check...
        self.assertTrue(hasattr(BaseCollector, 'raw_format_version_tag'))
        self.assertTrue(hasattr(BaseCollector, 'config_required'))
        self.assertTrue(hasattr(BaseCollector, 'config_group'))
        self.assertTrue(hasattr(BaseCollector, 'type'))

    def test_class_attr_values(self):                                             #3: revise the attributes and types to check...
        self.assertEqual(BaseCollector.output_queue,
                         {'exchange': 'raw', 'exchange_type': 'topic'})
        self.assertIsNone(BaseCollector.raw_format_version_tag)
        self.assertEqual(BaseCollector.config_required,
                         ('source',))
        self.assertIsNone(BaseCollector.config_group)
        self.assertIsNone(BaseCollector.type)

    @foreach(                  #3: in all this test class: revise the attributes/methods/args/results/etc. to check (and their features/states/etc.)...
        param(
            custom_config_group=SAMPLE_CONFIG_SECTION,
            expected_config=ConfigSection(SAMPLE_CONFIG_SECTION,
                                          {'required_opt': SAMPLE_REQUIRED_VALUE,
                                           'some_opt': 'ABc dd'}),
        ).label('Attribute `config_group` declared.'),

        # If a `config_group` is not set, the config section
        # gets its name from `config_spec`, but only if it
        # specifies just one section.
        param(
            custom_config_spec='''
                [other_section]
                some_opt :: json
                required_opt :: float
            ''',
            expected_config=ConfigSection(SAMPLE_OTHER_CONFIG_SECTION,
                                          {'required_opt': 123.89,
                                           'some_opt': [{'a': 'bcd'}]}),
        ).label('Attribute `config_spec` declared.'),

        # In a case when both `config_group` and `config_spec`
        # are set, a `config_group` value is used as a section's
        # name. Although, the `config_spec` is still used,
        # so if section specified in `config_spec` is found
        # in a config file, it has to follow a specification,
        # e.g. there cannot be any not specified options,
        # if the specification does not allow them (it does not end
        # with three dots).
        param(
            custom_config_group=SAMPLE_OTHER_CONFIG_SECTION,
            custom_config_spec='''
                [some_section]
                not_required_opt = 'test' :: str
                ...
            ''',
            expected_config=ConfigSection(SAMPLE_OTHER_CONFIG_SECTION,
                                          {'required_opt': '123.89',
                                           'some_opt': '[{"a": "bcd"}]'}),
        ).label('Both `config_group` and `config_spec` set.'),

        # In case of set `config_spec` and `config_required`,
        # options from `config_required` are going to be included
        # in the result config, even though they are not declared
        # in the `config_spec` and additional options are illegal.
        param(
            custom_config_required=('some_opt',),
            custom_config_spec='''
                [some_section]
                required_opt :: unicode                                           ; #3: replace `unicode` with something else...
            ''',
            expected_config=ConfigSection(SAMPLE_CONFIG_SECTION,
                                          {'required_opt': u'some option which is required',
                                           'some_opt': 'ABc dd'}),
        ).label('Attributes `config_spec` and `config_required`.'),

        # A `config_spec` attribute can have more than one section
        # declared, if a `config_group` is set, so a section name
        # can be inferred from the `config_spec`.
        param(
            custom_config_group=SAMPLE_OTHER_CONFIG_SECTION,
            custom_config_spec='''
                [some_section]
                required_opt :: unicode                                           ; #3: replace `unicode` with something else...
                ...
                [other_section]
                some_opt
                required_opt :: float
                another_opt = 124 :: int
            ''',
            expected_config=ConfigSection(SAMPLE_OTHER_CONFIG_SECTION,
                                          {'required_opt': 123.89,
                                           'some_opt': '[{"a": "bcd"}]',
                                           'another_opt': 124}),
        ).label('A few sections in `config_spec` and `config_group` set.'),

        param(
            expected_config=CONFIG_WITH_NO_SECTION_DECLARED,
        ).label('No `config_spec` or `config_group` declared.'),

        # wrong config declarations
        param(
            custom_config_spec='''
                [some_section]
                required_opt :: unicode                                           ; #3: replace `unicode` with something else...
                ...
                [other_section]
                some_opt
                required_opt :: float
                ...
            ''',
            expected_exc=ConfigError,
        ).label('A few sections in the `config_spec` declared and a `config_group` not set.'),

        param(
            custom_config_group=SAMPLE_CONFIG_SECTION,
            custom_config_spec='''
                [other_section]
                wrong_opt = "Option not in config file."
            ''',
            expected_exc=ConfigError,
        ).label("Invalid `config_spec`."),

        param(
            custom_config_group='group_not_found',
            expected_exc=ConfigError,
        ).label("The config section does not exist in config files."),
    )
    @foreach(
        param(source_type='stream'),
        param(source_type='file'),
        param(source_type='blacklist'),
    )
    def test__init(self,
                   source_type,
                   custom_config_required=SAMPLE_CONFIG_REQUIRED,
                   custom_config_group=None,
                   custom_config_spec=None,
                   expected_config=None,
                   expected_exc=None):
        class SomeCollector(BaseCollector):
            config_group = custom_config_group
            config_required = custom_config_required
            config_spec = custom_config_spec
            type = source_type
        MOCKED_SUPER_CLS.__init__.reset_mock()
        with STDERR_PATCHER, SUPER_PATCHER as super_mock, CONFIG_PATCHER:
            # instantiation
            if expected_exc is not None:
                assert expected_config is None, ("A single test case cannot expect both "
                                                 "exception and config.")
                with self.assertRaises(expected_exc):
                    instance = SomeCollector(a=SAMPLE_ARG_A,
                                             bb=SAMPLE_ARG_B)
            else:
                instance = SomeCollector(a=SAMPLE_ARG_A,
                                         bb=SAMPLE_ARG_B)
                # assert that an instance of the proper type has been returned
                self.assertIsInstance(instance, SomeCollector)
                # assert that super used properly
                super_mock.assert_called_once_with(BaseCollector, instance)
                MOCKED_SUPER_CLS.__init__.assert_called_once_with(a=SAMPLE_ARG_A,
                                                                  bb=SAMPLE_ARG_B)
                self.assertEqual(instance.config, expected_config)

    def test__init__type_not_valid(self):
        # generates an exception if type not valid
        class SomeCollector(BaseCollector):
            config_group = SAMPLE_CONFIG_SECTION
            config_required = SAMPLE_CONFIG_REQUIRED
            type = 'olala'
        with SUPER_PATCHER, CONFIG_PATCHER:
            with self.assertRaises(Exception):
                instance = SomeCollector(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

    def test__init__type_not_set(self):
        # generates an exception if type is None
        class SomeCollector(BaseCollector):
            config_group = SAMPLE_CONFIG_SECTION
            config_required = SAMPLE_CONFIG_REQUIRED
        with SUPER_PATCHER, CONFIG_PATCHER:
            with self.assertRaises(NotImplementedError):
                instance = SomeCollector(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)

    def test__get_script_init_kwargs(self):
        self.assertEqual(BaseCollector.get_script_init_kwargs(), {})

    def test__run_handling__interrupted(self):
        mock = Mock(__class__=BaseCollector,
                    run=Mock(side_effect=KeyboardInterrupt))
        BaseCollector.run_handling(mock)
        mock.run.assert_called_once_with()
        mock.stop.assert_called_once_with()

    def test__run_handling__not_interrupted(self):
        mock = Mock(__class__=BaseCollector)
        BaseCollector.run_handling(mock)
        mock.run.assert_called_once_with()
        self.assertEqual(mock.stop.mock_calls, [])

    def test__get_output_components(self):
        mock = Mock(
            __class__=BaseCollector,
            process_input_data=Mock(return_value=dict(ccc=sentinel.ccc,
                                                      dddd=sentinel.dddd)),
            get_source_channel=Mock(return_value=SAMPLE_SOURCE_CHANNEL),
            get_source=Mock(return_value=SAMPLE_SOURCE),
            get_output_rk=Mock(return_value=SAMPLE_OUTPUT_RK),
            get_output_data_body=Mock(return_value=SAMPLE_OUTPUT_DATA_BODY),
            get_output_prop_kwargs=Mock(
                    return_value=SAMPLE_OUTPUT_PROP_KWARGS))
        # the call
        (output_rk,
         output_data_body,
         output_prop_kwargs) = BaseCollector.get_output_components(
            mock, a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)
        # assertions
        self.assertIs(output_rk, SAMPLE_OUTPUT_RK)
        self.assertIs(output_data_body, SAMPLE_OUTPUT_DATA_BODY)
        self.assertIs(output_prop_kwargs, SAMPLE_OUTPUT_PROP_KWARGS)
        self.assertEqual(mock.mock_calls, [
            call.process_input_data(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B),
            call.get_source_channel(ccc=sentinel.ccc, dddd=sentinel.dddd),
            call.get_source(
                    source_channel=SAMPLE_SOURCE_CHANNEL,
                    ccc=sentinel.ccc, dddd=sentinel.dddd),
            call.get_output_rk(
                    source=SAMPLE_SOURCE,
                    ccc=sentinel.ccc, dddd=sentinel.dddd),
            call.get_output_data_body(
                    source=SAMPLE_SOURCE,
                    ccc=sentinel.ccc, dddd=sentinel.dddd),
            call.get_output_prop_kwargs(
                    source=SAMPLE_SOURCE,
                    output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                    ccc=sentinel.ccc, dddd=sentinel.dddd),
        ])

    def test__process_input_data(self):
        mock = Mock(__class__=BaseCollector)
        processed_data = BaseCollector.process_input_data(mock,
                                                          a=SAMPLE_ARG_A,
                                                          bb=SAMPLE_ARG_B)
        self.assertEqual(processed_data, dict(a=SAMPLE_ARG_A,
                                              bb=SAMPLE_ARG_B))

    def test__get_source_channel(self):
        mock = Mock(__class__=BaseCollector)
        with self.assertRaises(NotImplementedError):
            BaseCollector.get_source_channel(mock)

    def test__get_source(self):
        mock = Mock(__class__=BaseCollector,
                    config=dict(source='my_src_label'))
        source = BaseCollector.get_source(mock,
                                          'my_src_channel',
                                          blablabla=sentinel.blablabla)
        self.assertEqual(source, 'my_src_label.my_src_channel')

    def test__get_output_rk(self):
        mock = Mock(__class__=BaseCollector,
                    raw_format_version_tag=None)
        output_rk = BaseCollector.get_output_rk(mock,
                                                'my_src_label.my_src_channel',
                                                blablabla=sentinel.blablabla)
        self.assertEqual(output_rk, 'my_src_label.my_src_channel')

    def test__get_output_rk__with__raw_format_version_tag(self):
        mock = Mock(__class__=BaseCollector,
                    raw_format_version_tag='33333')
        output_rk = BaseCollector.get_output_rk(mock,
                                                'my_src_label.my_src_channel',
                                                blablabla=sentinel.blablabla)
        self.assertEqual(output_rk, 'my_src_label.my_src_channel.33333')

    def test__get_output_data_body(self):
        mock = Mock(__class__=BaseCollector)
        with self.assertRaises(NotImplementedError):
            BaseCollector.get_output_data_body(mock, SAMPLE_SOURCE,
                                               blablabla=sentinel.blablabla)

    @foreach(
        param(source_type='stream'),
        param(source_type='file'),
        param(source_type='blacklist'),
    )
    def test__get_output_prop_kwargs(self, source_type):
        mock = Mock(__class__=BaseCollector,
                    type=source_type,
                    content_type=SAMPLE_CONTENT_TYPE,
                    get_output_message_id=Mock(return_value=SAMPLE_MESSAGE_ID))
        created_timestamp = 1234
        with patch('time.time', return_value=created_timestamp) as time_mock:
            # the call
            output_prop_kwargs = BaseCollector.get_output_prop_kwargs(
                    mock,
                    source=SAMPLE_SOURCE,
                    output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                    arg_a=SAMPLE_ARG_A)
            # assertions
            time_mock.assert_called_once_with()
            mock.get_output_message_id.assert_called_once_with(
                    source=SAMPLE_SOURCE,
                    created_timestamp=created_timestamp,
                    output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                    arg_a=SAMPLE_ARG_A)
            # if the stream is of the type "source" - it does not
            # add `content_type` to the properties
            if source_type == 'stream':
                self.assertEqual(output_prop_kwargs, {
                        'message_id': SAMPLE_MESSAGE_ID,
                        'type': source_type,
                        'timestamp': 1234,
                        'headers': {}})
            else:
                self.assertEqual(output_prop_kwargs, {
                        'message_id': SAMPLE_MESSAGE_ID,
                        'type': source_type,
                        'content_type': SAMPLE_CONTENT_TYPE,
                        'timestamp': 1234,
                        'headers': {}})

    @foreach(
        param(source_type='stream'),
        param(source_type='file'),
        param(source_type='blacklist'),
    )
    def test__get_output_prop_kwargs_content_type_not_set(self, source_type):
        mock = Mock(spec=BaseCollector,
                    type=source_type,
                    get_output_message_id=Mock(return_value=SAMPLE_MESSAGE_ID))
        created_timestamp = 1234
        with patch('time.time', return_value=created_timestamp) as time_mock:
            # collectors handling the sources of "stream" type do not
            # need the `content_type` to be set
            if source_type == 'stream':
                output_prop_kwargs = BaseCollector.get_output_prop_kwargs(
                        mock,
                        source=SAMPLE_SOURCE,
                        output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                        arg_a=SAMPLE_ARG_A)
                # assertions
                time_mock.assert_called_once_with()
                mock.get_output_message_id.assert_called_once_with(
                        source=SAMPLE_SOURCE,
                        created_timestamp=created_timestamp,
                        output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                        arg_a=SAMPLE_ARG_A)
                self.assertEqual(output_prop_kwargs, {
                        'message_id': SAMPLE_MESSAGE_ID,
                        'type': source_type,
                        'timestamp': 1234,
                        'headers': {}})
            else:
                with self.assertRaises(AttributeError):
                    BaseCollector.get_output_prop_kwargs(
                            mock,
                            source=SAMPLE_SOURCE,
                            output_data_body=SAMPLE_OUTPUT_DATA_BODY,
                            arg_a=SAMPLE_ARG_A)

    def test__get_output_message_id(self):
        source = 'my_src_label.my_src_channel'
        created_timestamp = 1234
        created_timestamp_str = '1234'
        output_data_body = '1234'
        mock = Mock(__class__=BaseCollector)
        message_id = BaseCollector.get_output_message_id(mock,
                                                         source,
                                                         created_timestamp,
                                                         output_data_body)

        ### XXX CR: rather hardcode a few specific md5s instead of:
        expected_message_id = hashlib.md5(source + '\0' +                            #3: usedforsecurity=False...??? , adjust ad string types...
                                          created_timestamp_str + '\0' +
                                          output_data_body).hexdigest()
        self.assertEqual(message_id, expected_message_id)


class TestBaseOneShotCollector(unittest.TestCase):

    def test_basics(self):
        self.assertTrue(issubclass(BaseOneShotCollector, BaseCollector))

    def test__init(self):
        super_cls_mock = PlainNamespace(__init__=Mock())
        with patch_always('n6.collectors.generic.super',                            #3: `patch_always`->`patch`...
                          return_value=super_cls_mock) as super_mock:
            # instantiation
            instance = BaseOneShotCollector(input_data=SAMPLE_INPUT_DATA,
                                            a=SAMPLE_ARG_A,
                                            bb=SAMPLE_ARG_B)
            # assertions
            self.assertIsInstance(instance, BaseOneShotCollector)
            super_mock.assert_called_once_with(BaseOneShotCollector, instance)      #3: `BaseOneShotCollector, instance`--
            super_cls_mock.__init__.assert_called_once_with(a=SAMPLE_ARG_A,
                                                            bb=SAMPLE_ARG_B)
            self.assertIs(instance.input_data, SAMPLE_INPUT_DATA)
            # instantiation without the `input_data` argument
            instance_2 = BaseOneShotCollector(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B)
            self.assertEqual(instance_2.input_data, {})

    @patch('n6.collectors.generic.LOGGER')
    def test__run_handling(self, LOGGER_mock):
        mock = Mock(
                __class__=BaseOneShotCollector,
                input_data=dict(a=SAMPLE_ARG_A, bb=SAMPLE_ARG_B),
                _output_components=None,
                get_output_components=Mock(
                    return_value=SAMPLE_OUTPUT_COMPONENTS))
        # the call
        BaseOneShotCollector.run_handling(mock)
        # assertions
        self.assertEqual(mock.mock_calls,
                         [call.get_output_components(a=SAMPLE_ARG_A,
                                                     bb=SAMPLE_ARG_B),
                          call.run()])
        self.assertIs(mock._output_components, SAMPLE_OUTPUT_COMPONENTS)

    @patch('n6.collectors.generic.LOGGER')
    def test__start_publishing(self, LOGGER_mock):
        mock = Mock(
                __class__=BaseOneShotCollector,
                _output_components=[SAMPLE_OUTPUT_COMPONENTS])
        # the call
        BaseOneShotCollector.start_publishing(mock)
        # assertions
        self.assertEqual(mock.mock_calls,
                         [call.publish_output(SAMPLE_OUTPUT_COMPONENTS),
                          call.inner_stop()])
        self.assertIs(mock._output_components, None)


class TestBaseEmailSourceCollector(unittest.TestCase):                           #3-- (at least for now)

    def test_basics(self):
        self.assertTrue(issubclass(BaseEmailSourceCollector,
                                   BaseOneShotCollector))

    @patch('sys.stdin', **{'read.return_value': sentinel.stdin_read_result})
    def test__get_script_init_kwargs(self, stdin_mock):
        script_init_kwargs = BaseEmailSourceCollector.get_script_init_kwargs()
        self.assertEqual(script_init_kwargs,
                         {'input_data':
                          {'raw_email': sentinel.stdin_read_result}})

    @patch.object(ReceivedEmailMessage, 'from_string',
                  return_value=SAMPLE_EMAIL_MESSAGE)
    def test__process_input_data(self, EM_from_string_mock):
        mock = Mock(__class__=BaseEmailSourceCollector)
        processed_data = BaseEmailSourceCollector.process_input_data(
                mock,
                raw_email=sentinel.raw_email)
        EM_from_string_mock.assert_called_once_with(sentinel.raw_email)
        self.assertEqual(processed_data,
                         {'email_msg': SAMPLE_EMAIL_MESSAGE})

    def test__get_output_data_body(self):
        mock = Mock(__class__=BaseEmailSourceCollector)
        with self.assertRaises(NotImplementedError):
            BaseEmailSourceCollector.get_output_data_body(
                    mock,
                    email_msg=SAMPLE_EMAIL_MESSAGE,
                    blablabla=sentinel.blablabla)

    def test__get_output_prop_kwargs(self):
        mock = Mock(__class__=BaseEmailSourceCollector)
        super_cls_mock = Mock()
        super_cls_mock.get_output_prop_kwargs.return_value = {
            'foo': sentinel.foo,
            'headers': {}}
        email_msg_mock = Mock()
        email_msg_mock.get_utc_datetime.return_value = (
            datetime.datetime(2013, 5, 29, 14, 5, 19, 0))
        email_msg_mock.get_subject.return_value = 'Subject z polskimi znaćżkąmi'
        with patch_always('n6.collectors.generic.super',                            #3: `patch_always`->`patch`...
                          return_value=super_cls_mock) as super_mock:
            output_prop_kw = BaseEmailSourceCollector.get_output_prop_kwargs(
                    mock,
                    email_msg=email_msg_mock,
                    blablabla=sentinel.blablabla)
            super_mock.assert_called_once_with(BaseEmailSourceCollector, mock)
        self.assertEqual(output_prop_kw,
                         {'foo': sentinel.foo,
                          'headers': {'meta': {'mail_subject': 'Subject z polskimi znaćżkąmi',
                                      'mail_time': '2013-05-29 14:05:19'}}})


@expand
class TestBaseUrlDownloaderCollector___try_to_set_http_last_modified(unittest.TestCase):             #3--

    def setUp(self):
        self.instance = object.__new__(BaseUrlDownloaderCollector)
        self.instance._http_last_modified = None  # as in BaseUrlDownloaderCollector.__init__()

    # related to the fixed bug #6673
    @foreach(
        param(
            headers={'Last-Modified': 'Sun, 06 Nov 2019 08:49:37 GMT'},
            expected__http_last_modified=datetime.datetime(2019, 11, 6, 8, 49, 37),
        ).label('preferred RFC-7231 format of header Last-Modified'),

        param(
            headers={'Last-Modified': 'Sunday, 06-Nov-19 08:49:37 GMT'},
            expected__http_last_modified=datetime.datetime(2019, 11, 6, 8, 49, 37),
        ).label('old RFC-850 format of header Last-Modified'),

        param(
            headers={'Last-Modified': 'Sun Nov  6 08:49:37 2019'},
            expected__http_last_modified=datetime.datetime(2019, 11, 6, 8, 49, 37),
        ).label('old ANSI C asctime() format of header Last-Modified'),

        param(
            headers={'Last-Modified': 'foo bar'},
            expected__http_last_modified=None,
        ).label('unsupported format of header Last-Modified'),

        param(
            headers={},
            expected__http_last_modified=None,
        ).label('no header Last-Modified'),
    )
    def test(self, headers, expected__http_last_modified):
        self.instance._try_to_set_http_last_modified(headers)
        self.assertEqual(self.instance._http_last_modified,
                         expected__http_last_modified)


@expand
class TestBaseTimeOrderedRowsCollector(_BaseCollectorTestCase):    #3: adjust ad types, especially of string-like stuff...
                                                                   #3: adjust ad interface/internals differences between the Py2 and Py3 variants of the tested class...
    DEFAULT_CONFIG = '''
        [xyz_my_channel]
        source = xyz
        cache_dir = /who/cares
        row_count_mismatch_is_fatal = False
    '''

    DEFAULT_PROP_KWARGS = {
        'timestamp': ANY,
        'message_id': ANY,
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {},
    }


    class ExampleTimeOrderedRowsCollector(BaseTimeOrderedRowsCollector):

        source_config_section = 'xyz_my_channel'
        config_spec_pattern = '''
            [{source_config_section}]
            source :: str
            cache_dir :: str
            row_count_mismatch_is_fatal = False :: bool
        '''

        example_orig_data = None  # to be set on instance by test code

        def obtain_orig_data(self):
            return self.example_orig_data

        def pick_raw_row_time(self, row):
            return extract_field_from_csv_row(row, column_index=1)

        def clean_row_time(self, raw_row_time):
            return raw_row_time

        def get_source_channel(self, **kwargs):
            return 'my-channel'

    @paramseq
    def cases(cls):
        yield param(
            # Initial state (one row)
            # and expected saved state (one row)
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-13"\n'
                '\t\n'
                '"spam","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-13"\n'
                        '"spam","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = True
            ''',
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-13"\n'
                '\t\n'
                '"spam","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-13"\n'
                        '"spam","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '5',
                'newest_rows': {'"zzz","5"'},
                'rows_count': 5,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","7"\n'
                '\t\n'
                '"spam","6"\n'
                '"zzz","5"\n'
                '"egg","4"\n'
                '"sss","3"\n'
                '\n'
                '"bar","2"\n'
                '"foo","1"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","7"\n'
                        '"spam","6"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-11"\n'
                '\t\n'
                '"spam","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-11"\n'
                        '"spam","2019-07-11"\n'
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5,
            },
            orig_data=(
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE)

        yield param(
            # Initial state (two rows)
            # and expected saved state (one row)
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {
                    '"spam","2019-07-10"',
                    '"zzz","2019-07-10"'
                },
                'rows_count': 6,
            },
            orig_data=(
                '"ham","2019-07-11"\n'
                '"spam","2019-07-10"\n'
                '"zzz","2019-07-10"\n'
                '\t\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-11"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"sss","2019-07-02"',
                    '"egg","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-11"\n'
                '"spam","2019-07-11"\n'
                '\t\n'
                '"zzz","2019-07-02"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-11"\n'
                        '"spam","2019-07-11"\n'
                        '"zzz","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"sss","2019-07-02"',
                    '"egg","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Without initial state but with expected saved state
            # (e.g.first run) - one row
            config_content=cls.DEFAULT_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"\n'
                        '"sss","2019-07-02"\n'
                        '"bar","2019-07-01"\n'
                        '"foo","2019-06-30"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-10"\n'
                '"sss","2019-07-02"\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-10"\n'
                        '"sss","2019-07-02"\n'
                        '"bar","2019-07-01"\n'
                        '"foo","2019-06-30"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state=sentinel.NO_STATE,
            orig_data='',
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-02"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-02"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {
                    '"egg","2019-07-02"',
                    '"sss","2019-07-02"'
                },
                'rows_count': 4,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"ham","2019-07-02"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"ham","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
            config_content=cls.DEFAULT_CONFIG,
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
            },
            orig_data=(
                '# halo,mówię...\n'
                '"zzz","2019-07-10"\n'
                '"egg","2019-07-02"\n'
                '"sss","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = False
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = True
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = True
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"zzz","2019-07-10"\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = False
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 3,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"www","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"www","2019-07-11"\n'
                        '"zzz","2019-07-10"\n'
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = False
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"www","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_warning_count=1,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"www","2019-07-11"\n'
                        '"zzz","2019-07-10"\n'
                        '"zzz","2019-07-10"\n'
                        '"egg","2019-07-02"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
                row_count_mismatch_is_fatal = True
            ''',
            initial_state={
                'newest_row_time': '2019-07-02',
                'newest_rows': {'"sss","2019-07-02"'},
                'rows_count': 2,
            },
            orig_data=(
                '# halo,mówię...\n'
                '"www","2019-07-11"\n'
                '"zzz","2019-07-10"\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-01"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_error=ValueError,
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE,
        )

        yield param(
            # Data from source is not sorted,
            # `older` rows are mixed with newer ones.
            config_content='''
                [xyz_my_channel]
                source = xyz
                cache_dir = /who/cares
            ''',
            initial_state={
                'newest_row_time': '2019-07-10',
                'newest_rows': {'"zzz","2019-07-10"'},
                'rows_count': 5
            },
            orig_data=(
                '# halo,mówię...\n'
                '"spam","2019-07-11"\n'
                '"ham","2019-07-13"\n'
                '\t\n'
                '"zzz","2019-07-10"\n'
                '"sss","2019-07-02"\n'
                '"egg","2019-07-02"\n'
                '\n'
                '"bar","2019-07-01"\n'
                '"foo","2019-06-30"\n'
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'xyz.my-channel',

                    # body
                    (
                        '"spam","2019-07-11"\n'
                        '"ham","2019-07-13"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
             expected_warning_count=None,
             expected_error=None):

        LOGGER_warning_mock = self.patch(
            'n6.collectors.generic.LOGGER.warning'
        )
        collector = self.prepare_collector(self.ExampleTimeOrderedRowsCollector,
                                           config_content=config_content,
                                           initial_state=initial_state)
        collector.example_orig_data = orig_data
        if expected_error:
            with self.assertRaises(expected_error):
                collector.run_handling()
        else:
            collector.run_handling()

        if expected_warning_count:
            self.assertEqual(LOGGER_warning_mock.call_count, expected_warning_count)
        self.assertEqual(self.publish_output_mock.mock_calls,
                         expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)


@expand
class TestCollectorWithStateMixin(_BaseCollectorTestCase):    #3: ->StatefulCollectorMixin...
                                                              #3: adjust ad interface/internals differences between the Py2 and Py3 variants of the tested class...
    patch_CollectorWithStateMixin = False

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp(prefix='n6-TestCollectorWithStateMixin')

    class ExampleCollectorWithState(CollectorWithStateMixin,
                                    BaseCollector):

        config_spec = '''
            [stateful_collector_example_config]
            source :: str
            cache_dir :: str
        '''

        def get_source_channel(self, **kwargs):
            return 'test_channel'

        def make_default_state(self):
            return 'This is default state - test'

    @paramseq
    def cases():
        yield param(
            source_opt='source_1',
            source_type='blacklist',
            state='1 2 3 abc',
            expected_cache_file_name='source_1.test_channel.ExampleCollectorWithState.pickle',
        )

        yield param(
            source_opt='source_2',
            source_type='file',
            state='file content',
            expected_cache_file_name='source_2.test_channel.ExampleCollectorWithState.pickle',
        )
        yield param(
            source_opt='source_3',
            source_type='stream',
            state=None,
            expected_cache_file_name='source_3.test_channel.ExampleCollectorWithState.pickle',
        )
        yield param(
            source_opt='source_4',
            source_type='file',
            state='żółte kąty',
            expected_cache_file_name='source_4.test_channel.ExampleCollectorWithState.pickle',
        )
        yield param(
            source_opt='source_5',
            source_type='file',
            state=b'\xc5\xbc\xc3\xb3\xc5\x82te k\xc4\x85ty',
            expected_cache_file_name='source_5.test_channel.ExampleCollectorWithState.pickle',
        )
        yield param(
            source_opt='source_6',
            source_type='file',
            state=datetime.date(2022, 1, 3),
            expected_cache_file_name='source_6.test_channel.ExampleCollectorWithState.pickle',
        )

    @foreach(cases)
    def test(self,
             source_opt,
             source_type,
             state,
             expected_cache_file_name):
        config_content = '''
            [stateful_collector_example_config]
            source = {}
            cache_dir = {}
        '''.format(source_opt, self.cache_dir)
        self.ExampleCollectorWithState.type = source_type
        collector = self.prepare_collector(self.ExampleCollectorWithState,
                                           config_content=config_content)
        state_before_save = collector.load_state()
        collector.save_state(state)
        loaded_state = collector.load_state()
        default_state = collector.make_default_state()
        cache_file_name = collector.get_cache_file_name()
        self.assertEqual(loaded_state, state)
        self.assertEqual(default_state, state_before_save)
        self.assertEqual(cache_file_name, expected_cache_file_name)

    def tearDown(self):
        shutil.rmtree(self.cache_dir)

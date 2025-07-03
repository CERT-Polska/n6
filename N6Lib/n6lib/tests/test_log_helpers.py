# Copyright (c) 2013-2024 NASK. All rights reserved.

import json
import logging
import os
import os.path
import socket
import ssl
import sys
import threading
import time
import types
import unittest
from unittest.mock import ANY, MagicMock, call, patch, sentinel

from unittest_expander import expand, foreach, param

from n6lib.amqp_getters_pushers import DoNotPublish
from n6lib.amqp_helpers import (
    GUEST_PASSWORD,
    GUEST_USERNAME,
)
from n6lib.const import ETC_DIR, USER_DIR
from n6lib.tests.test_amqp_helpers import CONN_PARAM_CLIENT_PROP_INFORMATION
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    TestCaseMixin,
)
from n6lib.log_helpers import (
    _LOGGER,
    AMQPHandler,
    configure_logging,
    get_logger,
)


@expand
class Test_monkeypached_Formatter_formats_utc_time(unittest.TestCase):

    # note: Formatter is monkey-patched when n6lib is being imported
    # [see: the n6lib.log_helpers.early_Formatter_class_monkeypatching()
    # function and its call in n6lib/__init__.py]

    # TODO: cover also possibilities of:
    #   * customized `Formatter.default_time_format`
    #   * customized `Formatter.default_msec_format`

    @foreach(
        param(
            expected='2015-05-14 20:36:58,123 UTC',
        ).label('default'),

        param(
            expected='15-05-14T20:36:58 UTC',
            custom_datefmt='%y-%m-%dT%H:%M:%S',
        ).label('with custom datefmt'),

        param(
            expected='2015-05-14 20:36:58,123 <UNCERTAIN TIMEZONE>',
            custom_converter=(lambda t: time.gmtime(t)),
        ).label('with custom converter'),

        param(
            expected='15-05-14T20:36:58 <UNCERTAIN TIMEZONE>',
            custom_datefmt='%y-%m-%dT%H:%M:%S',
            custom_converter=(lambda t: time.gmtime(t)),
        ).label('with custom datefmt and custom converter'),
    )
    def test(self, expected, custom_datefmt=None, custom_converter=None):
        record = MagicMock()
        record.created = 1431635818
        record.msecs = 123
        formatter = logging.Formatter(datefmt=custom_datefmt)
        if custom_converter is not None:
            formatter.converter = custom_converter
        formatted = formatter.formatTime(record, custom_datefmt)
        self.assertEqual(expected, formatted)


class Test__get_logger(unittest.TestCase):
    def test(self):
        assert get_logger is logging.getLogger


@patch('n6lib.log_helpers._loaded_configuration_paths', new_callable=set)
@patch('n6lib.log_helpers._try_reading')
@patch('n6lib.log_helpers._LOGGER')
@patch('n6lib.log_helpers.logging')
class Test__configure_logging(unittest.TestCase):

    etc_path = os.path.join(ETC_DIR, 'logging.conf')
    user_path = os.path.join(USER_DIR, 'logging.conf')
    etc_path_suffixed = os.path.join(ETC_DIR, 'logging-mysuffix.conf')
    user_path_suffixed = os.path.join(USER_DIR, 'logging-mysuffix.conf')

    def test_no_file(self, mocked__logging,
                     mocked___LOGGER,
                     mocked__try_reading,
                     _loaded_configuration_paths):
        mocked__try_reading.side_effect = OSError
        mocked__fileConfig = mocked__logging.config.fileConfig
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertFalse(_loaded_configuration_paths)
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertFalse(mocked__fileConfig.called),
        # and when repeated...
        mocked__try_reading.reset_mock()
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertFalse(_loaded_configuration_paths)
        self.assertEqual(mocked__try_reading.call_args_list,
                         # both paths tried again:
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertFalse(mocked__fileConfig.called)

    def test_etc_file_only(self, mocked__logging,
                           mocked___LOGGER,
                           mocked__try_reading,
                           _loaded_configuration_paths):
        # ok for etc path, error for user path
        mocked__try_reading.side_effect = [None, OSError]
        mocked__fileConfig = mocked__logging.config.fileConfig
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__fileConfig.reset_mock()
        mocked__try_reading.reset_mock()
        mocked__try_reading.side_effect = OSError
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         # only user path tried again for:
                         [call(self.user_path)])
        self.assertFalse(mocked__fileConfig.called)

    def test_user_file_only(self, mocked__logging,
                            mocked___LOGGER,
                            mocked__try_reading,
                            _loaded_configuration_paths):
        # error for etc path, ok for user path
        mocked__try_reading.side_effect = [OSError, None]
        mocked__fileConfig = mocked__logging.config.fileConfig
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.user_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.user_path,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__fileConfig.reset_mock()
        mocked__try_reading.reset_mock()
        mocked__try_reading.side_effect = OSError
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.user_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         # only etc path tried again:
                         [call(self.etc_path)])
        self.assertFalse(mocked__fileConfig.called)

    def test_both_files_exist(self, mocked__logging,
                              mocked___LOGGER,
                              mocked__try_reading,
                              _loaded_configuration_paths):
        mocked__fileConfig = mocked__logging.config.fileConfig
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path,
                                                       self.user_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False),
                          call(self.user_path,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__fileConfig.reset_mock()
        mocked__try_reading.reset_mock()
        configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path,
                                                       self.user_path})
        self.assertFalse(mocked__try_reading.called)
        self.assertFalse(mocked__fileConfig.called)

    def test_with_suffixes(self, mocked__logging,
                           mocked___LOGGER,
                           mocked__try_reading,
                           _loaded_configuration_paths):
        mocked__fileConfig = mocked__logging.config.fileConfig
        configure_logging('mysuffix')
        self.assertEqual(_loaded_configuration_paths,
                         {self.etc_path_suffixed,
                          self.user_path_suffixed})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path_suffixed),
                          call(self.user_path_suffixed)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path_suffixed,
                               disable_existing_loggers=False),
                          call(self.user_path_suffixed,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__fileConfig.reset_mock()
        mocked__try_reading.reset_mock()
        configure_logging('mysuffix')
        self.assertEqual(_loaded_configuration_paths,
                         {self.etc_path_suffixed,
                          self.user_path_suffixed})
        self.assertFalse(mocked__try_reading.called)
        self.assertFalse(mocked__fileConfig.called)

    def test_first_without_suffixes_then_with(self, mocked__logging,
                                              mocked___LOGGER,
                                              mocked__try_reading,
                                              _loaded_configuration_paths):
        mocked__fileConfig = mocked__logging.config.fileConfig
        # first without suffixes...
        configure_logging()
        self.assertEqual(_loaded_configuration_paths,
                         {self.etc_path,
                          self.user_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False),
                          call(self.user_path,
                               disable_existing_loggers=False)])
        # and then repeated with suffixes...
        mocked__fileConfig.reset_mock()
        mocked__try_reading.reset_mock()
        configure_logging('mysuffix')
        self.assertEqual(_loaded_configuration_paths,
                         {self.etc_path,
                          self.user_path,
                          self.etc_path_suffixed,
                          self.user_path_suffixed})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path_suffixed),
                          call(self.user_path_suffixed)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path_suffixed,
                               disable_existing_loggers=False),
                          call(self.user_path_suffixed,
                               disable_existing_loggers=False)])

    def test_etc_file_broken(self, mocked__logging,
                             mocked___LOGGER,
                             mocked__try_reading,
                             _loaded_configuration_paths):
        # etc file broken, user file ok
        mocked__fileConfig = mocked__logging.config.fileConfig
        mocked__fileConfig.side_effect = [ValueError, None]
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertFalse(_loaded_configuration_paths)
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__try_reading.reset_mock()
        mocked__fileConfig.reset_mock()
        mocked__fileConfig.side_effect = ValueError
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertFalse(_loaded_configuration_paths)
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False)])

    def test_user_file_broken(self, mocked__logging,
                              mocked___LOGGER,
                              mocked__try_reading,
                              _loaded_configuration_paths):
        # etc file ok, user file broken
        mocked__fileConfig = mocked__logging.config.fileConfig
        mocked__fileConfig.side_effect = [None, ValueError]
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.etc_path),
                          call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.etc_path,
                               disable_existing_loggers=False),
                          call(self.user_path,
                               disable_existing_loggers=False)])
        # and when repeated...
        mocked__try_reading.reset_mock()
        mocked__fileConfig.reset_mock()
        mocked__fileConfig.side_effect = ValueError
        with self.assertRaises(RuntimeError):
            configure_logging()
        self.assertEqual(_loaded_configuration_paths, {self.etc_path})
        self.assertEqual(mocked__try_reading.call_args_list,
                         [call(self.user_path)])
        self.assertEqual(mocked__fileConfig.call_args_list,
                         [call(self.user_path,
                               disable_existing_loggers=False)])


class Test___LOGGER(unittest.TestCase):

    def test(self):
        self.assertIs(_LOGGER, logging.getLogger('n6lib.log_helpers'))


@expand
class TestAMQPHandler__init__interactions_with_other_stuff(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.m = MagicMock()

        self.patch('queue.Queue', self.m.Queue_cls)
        self.patch('threading.Thread', self.m.Thread_cls)
        self.patch('pika.credentials.ExternalCredentials', self.m.ExternalCredentials_cls)
        self.patch('pika.credentials.PlainCredentials', self.m.PlainCredentials_cls)
        self.patch('n6lib.log_helpers.AMQPThreadedPusher', self.m.AMQPThreadedPusher_cls)
        self.patch('n6lib.log_helpers.DoNotPublish', sentinel.DoNotPublish)
        self.patch('n6lib.log_helpers.print', self.m.print)
        self.patch_object(AMQPHandler, '_make_record_serializer', self.m._make_record_serializer)

        self.m.Queue_cls.return_value = sentinel.Queue_instance
        self.m.ExternalCredentials_cls.return_value = sentinel.ExternalCredentials_instance
        self.m.PlainCredentials_cls.return_value = sentinel.PlainCredentials_instance
        self.m.AMQPThreadedPusher_cls.return_value = sentinel.AMQPThreadedPusher_instance
        self.m._make_record_serializer.return_value = sentinel.serializer

    @foreach([
        param(
            init_kwargs=dict(
                connection_params_dict={
                    'host': 'example.com',
                    'port': 1234,
                    'ssl': True,
                    'ssl_ca_certs': '/some/ca-certs/file',
                    'ssl_certfile': '/some/cert/file',
                    'ssl_keyfile': '/some/key/file',
                },
            ),
            expected_calls=[
                call.Queue_cls(),
                call.Thread_cls(
                    target=AnyInstanceOf(types.MethodType),
                    kwargs=dict(
                        error_fifo=sentinel.Queue_instance,
                        error_logger=logging.getLogger(AMQPHandler.ERROR_LOGGER),
                    ),
                ),
                call.ExternalCredentials_cls(),
                call._make_record_serializer(),
                call.AMQPThreadedPusher_cls(
                    connection_params_dict={
                        # Note: this dict *has been* prepared with
                        # `get_amqp_connection_params_dict_from_args()`.
                        'host': 'example.com',
                        'port': 1234,
                        'ssl': True,
                        'ssl_options': {
                            'ca_certs': '/some/ca-certs/file',
                            'certfile': '/some/cert/file',
                            'keyfile': '/some/key/file',
                            'cert_reqs': ssl.CERT_REQUIRED,
                        },
                        'credentials': sentinel.ExternalCredentials_instance,
                        'client_properties': {
                            'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                        },
                    },
                    exchange=dict(
                        AMQPHandler.DEFAULT_EXCHANGE_DECLARE_KWARGS,
                        exchange='logging',
                    ),
                    prop_kwargs=AMQPHandler.DEFAULT_PROP_KWARGS,
                    serialize=sentinel.serializer,
                    error_callback=AnyInstanceOf(types.FunctionType),
                ),
                call.Thread_cls().start(),
            ],
            expected_level=logging.NOTSET,
        ).label(
            'quite typical modern `connection_params_dict` with SSL auth, '
            'no other arguments'
        ),

        param(
            init_kwargs=dict(
                connection_params_dict={
                    'host': 'example.com',
                    'port': 1234,
                    'ssl': True,
                    'ssl_ca_certs': '/some/ca-certs/file',
                    'password_auth': True,
                    'username': 'somebody@example.info',
                    'password': 'Example Password',
                },
                exchange='some-custom-exchange',
                exchange_declare_kwargs=dict(
                    some_key='some value',
                    another_key=42,
                ),
                rk_template=sentinel.WHATEVER,
                prop_kwargs=dict(
                    example_key=sentinel.EXAMPLE_VALUE,
                    and_another_one=123.456,
                ),
                other_pusher_kwargs=dict(
                    queues_to_declare=sentinel.SOME_QUEUES,
                    exchanges_to_declare=sentinel.SOME_EXCHANGES,
                ),
                error_logger_name='n6lib.tests.test_log_helpers.my-custom-error-logger',
                msg_count_window=sentinel.WHATEVER,
                msg_count_max=sentinel.WHATEVER,
                level=logging.INFO,
            ),
            expected_calls=[
                call.Queue_cls(),
                call.Thread_cls(
                    target=AnyInstanceOf(types.MethodType),
                    kwargs=dict(
                        error_fifo=sentinel.Queue_instance,
                        error_logger=logging.getLogger(
                            'n6lib.tests.test_log_helpers.my-custom-error-logger',
                        ),
                    ),
                ),
                call.PlainCredentials_cls(
                    'somebody@example.info',
                    'Example Password',
                ),
                call._make_record_serializer(),
                call.AMQPThreadedPusher_cls(
                    connection_params_dict={
                        # Note: this dict *has been* prepared with
                        # `get_amqp_connection_params_dict_from_args()`.
                        'host': 'example.com',
                        'port': 1234,
                        'ssl': True,
                        'ssl_options': {
                            'ca_certs': '/some/ca-certs/file',
                            'cert_reqs': ssl.CERT_REQUIRED,
                        },
                        'credentials': sentinel.PlainCredentials_instance,
                        'client_properties': {
                            'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                        },
                    },
                    exchange=dict(
                        exchange='some-custom-exchange',
                        some_key='some value',
                        another_key=42,
                    ),
                    prop_kwargs=dict(
                        example_key=sentinel.EXAMPLE_VALUE,
                        and_another_one=123.456,
                    ),
                    serialize=sentinel.serializer,
                    error_callback=AnyInstanceOf(types.FunctionType),
                    queues_to_declare=sentinel.SOME_QUEUES,
                    exchanges_to_declare=sentinel.SOME_EXCHANGES,
                ),
                call.Thread_cls().start(),
            ],
            expected_level=logging.INFO,
        ).label(
            'quite typical modern `connection_params_dict` with password auth, '
            'and a bunch of other arguments...'
        ),

        param(
            init_kwargs=dict(
                connection_params_dict={
                    'host': 'example.com',
                    'port': 1234,
                },
            ),
            expected_calls=[
                call.Queue_cls(),
                call.Thread_cls(
                    target=AnyInstanceOf(types.MethodType),
                    kwargs=dict(
                        error_fifo=sentinel.Queue_instance,
                        error_logger=logging.getLogger(AMQPHandler.ERROR_LOGGER),
                    ),
                ),
                call.print(
                    '\n*** WARNING: ***',
                    AnyMatchingRegex(r'communication will \*not\* be TLS-secured'),
                    sep='\n\n',
                    end='\n\n',
                    file=sys.stderr,
                ),
                call.PlainCredentials_cls(
                    GUEST_USERNAME,
                    GUEST_PASSWORD,
                ),
                call.print(
                    '\n*** WARNING: ***',
                    AnyMatchingRegex(r'\*guest\* pseudo-authentication'),
                    sep='\n\n',
                    end='\n\n',
                    file=sys.stderr,
                ),
                call._make_record_serializer(),
                call.AMQPThreadedPusher_cls(
                    connection_params_dict={
                        # Note: this dict *has been* prepared with
                        # `get_amqp_connection_params_dict_from_args()`.
                        'host': 'example.com',
                        'port': 1234,
                        'ssl': False,
                        'credentials': sentinel.PlainCredentials_instance,
                        'client_properties': {
                            'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                        },
                    },
                    exchange=dict(
                        AMQPHandler.DEFAULT_EXCHANGE_DECLARE_KWARGS,
                        exchange='logging',
                    ),
                    prop_kwargs=AMQPHandler.DEFAULT_PROP_KWARGS,
                    serialize=sentinel.serializer,
                    error_callback=AnyInstanceOf(types.FunctionType),
                ),
                call.Thread_cls().start(),
            ],
            expected_level=logging.NOTSET,
        ).label(
            'minimal (unrecommended) modern `connection_params_dict`, '
            'no other arguments'
        ),

        param(
            init_kwargs=dict(
                connection_params_dict={},
            ),
            expected_calls=[
                call.Queue_cls(),
                call.Thread_cls(
                    target=AnyInstanceOf(types.MethodType),
                    kwargs=dict(
                        error_fifo=sentinel.Queue_instance,
                        error_logger=logging.getLogger(AMQPHandler.ERROR_LOGGER),
                    ),
                ),
                call.print(
                    '\n*** WARNING: ***',
                    AnyMatchingRegex(r'^The .* first argument .* in the legacy format'),
                    AnyMatchingRegex(r'^Please, consider making'),
                    AnyMatchingRegex(r'^The support for'),
                    sep='\n\n',
                    end='\n\n',
                    file=sys.stderr,
                ),
                call._make_record_serializer(),
                call.AMQPThreadedPusher_cls(
                    connection_params_dict={
                        # Note: this dict has *not* been prepared with
                        # `get_amqp_connection_params_dict_from_args()`.
                    },
                    exchange=dict(
                        AMQPHandler.DEFAULT_EXCHANGE_DECLARE_KWARGS,
                        exchange='logging',
                    ),
                    prop_kwargs=AMQPHandler.DEFAULT_PROP_KWARGS,
                    serialize=sentinel.serializer,
                    error_callback=AnyInstanceOf(types.FunctionType),
                ),
                call.Thread_cls().start(),
            ],
            expected_level=logging.NOTSET,
        ).label(
            'empty (unrecommended, legacy) `connection_params_dict`, '
            'no other arguments'
        ),

        param(
            init_kwargs=dict(
                connection_params_dict={
                    'host': 'example.com',
                    'port': 1234,
                    'ssl': True,
                    'ssl_options': {
                        'ca_certs': '/some/ca-certs/file',
                        'certfile': '/some/cert/file',
                        'keyfile': '/some/key/file',
                    },
                    'credentials': sentinel.WHATEVER,
                },
            ),
            expected_calls=[
                call.Queue_cls(),
                call.Thread_cls(
                    target=AnyInstanceOf(types.MethodType),
                    kwargs=dict(
                        error_fifo=sentinel.Queue_instance,
                        error_logger=logging.getLogger(AMQPHandler.ERROR_LOGGER),
                    ),
                ),
                call.print(
                    '\n*** WARNING: ***',
                    AnyMatchingRegex(r'^The .* first argument .* in the legacy format'),
                    AnyMatchingRegex(r'^Please, consider making'),
                    AnyMatchingRegex(r'^The support for'),
                    sep='\n\n',
                    end='\n\n',
                    file=sys.stderr,
                ),
                call._make_record_serializer(),
                call.AMQPThreadedPusher_cls(
                    connection_params_dict={
                        # Note: this dict has *not* been prepared with
                        # `get_amqp_connection_params_dict_from_args()`.
                        'host': 'example.com',
                        'port': 1234,
                        'ssl': True,
                        'ssl_options': {
                            'ca_certs': '/some/ca-certs/file',
                            'certfile': '/some/cert/file',
                            'keyfile': '/some/key/file',
                        },
                        'credentials': sentinel.WHATEVER,
                    },
                    exchange=dict(
                        AMQPHandler.DEFAULT_EXCHANGE_DECLARE_KWARGS,
                        exchange='logging',
                    ),
                    prop_kwargs=AMQPHandler.DEFAULT_PROP_KWARGS,
                    serialize=sentinel.serializer,
                    error_callback=AnyInstanceOf(types.FunctionType),
                ),
                call.Thread_cls().start(),
            ],
            expected_level=logging.NOTSET,
        ).label(
            'example non-empty legacy (unrecommended) `connection_params_dict`, '
            'no other arguments'
        ),
    ])
    def test(self, init_kwargs, expected_level, expected_calls):
        handler = AMQPHandler(**init_kwargs)

        self.assertEqual(handler.level, expected_level)
        self.assertEqual(self.m.mock_calls, expected_calls)


class _AMQPHandlerTestCaseMixin(TestCaseMixin):

    @staticmethod
    def make_serializer(msg_count_window=10, msg_count_max=3):
        class AMQPHandler_(AMQPHandler):
            _msg_count_window = msg_count_window
            _msg_count_max = msg_count_max
        return AMQPHandler_.__new__(AMQPHandler_)._make_record_serializer()

    @classmethod
    def get_constant_log_record_items(cls, custom_items):
        items = {
            u'name': ANY,
            u'pathname': ANY,
            u'filename': ANY,
            u'module': ANY,
            u'lineno': ANY,
            u'funcName': ANY,
            u'created': ANY,
            u'msecs': ANY,
            u'asctime': ANY,
            u'relativeCreated': ANY,
            u'thread': threading.current_thread().ident,
            u'threadName': str(threading.current_thread().name),
            u'processName': ANY,
            u'process': os.getpid(),
            u'py_ver': u'.'.join(map(str, sys.version_info)),
            u'py_64bits': (sys.maxsize > 2 ** 32),
            u'py_platform': str(sys.platform),
            u'hostname': str(cls.get_hostname()),
            u'script_basename': str(cls.get_script_basename()),
        }
        items.update(custom_items)
        return items

    @staticmethod
    def get_hostname():
        return socket.gethostname().split('.', 1)[0]

    @staticmethod
    def get_script_basename():
        return os.path.basename(sys.argv[0]).split('.', 1)[0]


class TestAMQPHandler_cooperation_with_real_logger(_AMQPHandlerTestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.pika_mock = self.patch('n6lib.amqp_getters_pushers.pika')
        self.pika_mock.BasicProperties.side_effect = lambda **kwargs: kwargs
        conn_mock = self.pika_mock.BlockingConnection.return_value = MagicMock()
        self.channel_mock = conn_mock.channel.return_value = MagicMock()

        self.error_logger = logging.getLogger('TestAMQPHandler_logger.errors')
        self.error_logger._log = MagicMock(side_effect=self.error_logger._log)

        self.handler = AMQPHandler(connection_params_dict={},
                                   error_logger_name='TestAMQPHandler_logger.errors')
        self.addCleanup(self.handler.close)

        self.logger = logging.getLogger('TestAMQPHandler_logger')
        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)

        self.rk_template = '{hostname}.{script_basename}.{{levelname}}.{loggername}'.format(
            hostname=self.get_hostname(),
            script_basename=self.get_script_basename(),
            loggername='TestAMQPHandler_logger')

        self.constant_log_record_items = self.get_constant_log_record_items(dict(
                name='TestAMQPHandler_logger',
                filename='test_log_helpers.py',
                funcName='test',
                module='test_log_helpers',
            ))

        class UnRepr(object):
            def __repr__(self):
                raise RuntimeError('boom!')

        self.unserializable = UnRepr()


    def test(self):
        self.logger.warning('Spam %s', 12345)
        self.error_logger.warning('%s', 67890)              # to be skipped
        self.logger.warning('Foo %s', self.unserializable)  # to trigger error logger
        try:
            raise ValueError('hahaha ć')
        except ValueError:
            self.logger.error('Oh! Error:', exc_info=True)
        self.logger.info('Oh! Stack info provided:', stack_info=True)

        time.sleep(0.2)

        self.assertEqual(self.channel_mock.basic_publish.mock_calls, [
            call(
                exchange='logging',
                routing_key=self.rk_template.format(levelname='WARNING'),
                body=ANY,
                properties=ANY,
                mandatory=False,
            ),
            call(
                exchange='logging',
                routing_key=self.rk_template.format(levelname='ERROR'),
                body=ANY,
                properties=ANY,
                mandatory=False,
            ),
            call(
                exchange='logging',
                routing_key=self.rk_template.format(levelname='INFO'),
                body=ANY,
                properties=ANY,
                mandatory=False,
            ),
        ])
        ((_, _, kwargs1),
         (_, _, kwargs2),
         (_, _, kwargs3)) = self.channel_mock.basic_publish.mock_calls

        self.assertJsonEqual(kwargs1['body'], dict(
            self.constant_log_record_items,
            message='Spam 12345',
            msg='Spam %s',
            args=[12345],  # (list as it was JSON-ed)
            levelname='WARNING',
            levelno=logging.WARNING,
            exc_text=None,
        ))
        self.assertEqual(kwargs1['properties'], dict(
            content_type='application/json',
            delivery_mode=1,
        ))

        self.assertJsonEqual(kwargs2['body'], dict(
            self.constant_log_record_items,
            message='Oh! Error:',
            msg='Oh! Error:',
            args=[],  # (list as it was JSON-ed)
            levelname='ERROR',
            levelno=logging.ERROR,
            exc_type_repr=repr(ValueError),
            exc_ascii_str='hahaha \\u0107',
            exc_text=ANY,
            formatted_call_stack=ANY,  # <- by default, only for errors
        ))
        kwargs2_body = json.loads(kwargs2['body'])
        self.assertRegex(
            kwargs2_body['exc_text'],
            r'^Traceback \(most recent call last\):\n  File',
        )
        self.assertRegex(
            kwargs2_body['formatted_call_stack'],
            r'^Stack \(most recent call last\):\n  File',
        )
        self.assertEqual(
            kwargs2_body['formatted_call_stack'].splitlines()[-1],
            r"    self.logger.error('Oh! Error:', exc_info=True)",
        )
        self.assertEqual(kwargs2['properties'], dict(
            content_type='application/json',
            delivery_mode=1,
        ))

        self.assertJsonEqual(kwargs3['body'], dict(
            self.constant_log_record_items,
            message='Oh! Stack info provided:',
            msg='Oh! Stack info provided:',
            args=[],  # (list as it was JSON-ed)
            levelname='INFO',
            levelno=logging.INFO,
            exc_text=None,
            formatted_call_stack=ANY,  # <- explicitly requested by passing `stack_info=True`
        ))
        kwargs3_body = json.loads(kwargs3['body'])
        self.assertRegex(
            kwargs3_body['formatted_call_stack'],
            r'^Stack \(most recent call last\):\n  File',
        )
        self.assertEqual(
            kwargs3_body['formatted_call_stack'].splitlines()[-1],
            r"    self.logger.info('Oh! Stack info provided:', stack_info=True)",
        )
        self.assertEqual(kwargs3['properties'], dict(
            content_type='application/json',
            delivery_mode=1,
        ))

        self.assertEqual(self.error_logger._log.mock_calls, [
            call(
                logging.WARNING,
                '%s',
                (67890,),
            ),
            call(
                logging.ERROR,
                '%s',
                (ANY,),
            )
        ])
        self.assertIn(
            'RuntimeError: boom!',
            self.error_logger._log.mock_calls[1][1][2][0])


class TestAMQPHandler_serializer_adjusts_record_keys(_AMQPHandlerTestCaseMixin, unittest.TestCase):

    def test(self):
        KEY_MAX_LENGTH = AMQPHandler.LOGRECORD_KEY_MAX_LENGTH
        example_big_length = 4 * KEY_MAX_LENGTH
        assert example_big_length > KEY_MAX_LENGTH

        serializer = self.make_serializer()
        rec = logging.makeLogRecord({
            'msg': 'foo %d',
            'args': (42,),

            # * non-ascii
            u'ą': u'ę',

            # * non-str
            ('foo',): ('bar',),

            # * too long
            'x_' * example_big_length: 'x_' * example_big_length,

            # * non-str and too long
            10 ** example_big_length: 43,
        })
        expected_deserialized_rec = self.get_constant_log_record_items({
            u'exc_text': ANY,
            u'levelname': ANY,
            u'levelno': ANY,

            u'msg': u'foo %d',
            u'args': [42],
            u'message': u'foo 42',

            # * non-ascii escaped
            u'\\u0105': u'ę',

            # * non-str coerced to str
            u"('foo',)": [u'bar'],

            # * too long trimmed
            #   (note: here `(KEY_MAX_LENGTH - 6) // 2` is used because
            #          len(u'x[...]') == 6 and len(u'x_') == 2)
            u'{}x[...]'.format(u'x_' * ((KEY_MAX_LENGTH - 6) // 2)): u'x_' * example_big_length,

            # * non-str coerced to str + too long trimmed
            #   (note: here `KEY_MAX_LENGTH - 6` is used because
            #          len(u'1') + len(u'[...]') == 6)
            u'1{}[...]'.format(u'0' * (KEY_MAX_LENGTH - 6)): 43,
        })

        serialized_rec = serializer(rec)

        deserialized_rec = json.loads(serialized_rec)
        self.assertEqualIncludingTypes(deserialized_rec, expected_deserialized_rec)


class TestAMQPHandler_serializer_skips_records(_AMQPHandlerTestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.serializer = self.make_serializer(msg_count_window=10, msg_count_max=3)

    def _rec(self, msg, *args, **kwargs):
        assert 'msg' not in kwargs
        assert 'args' not in kwargs
        kwargs.update(msg=msg, args=args)
        return logging.makeLogRecord(kwargs)

    def test(self):
        records = [
            self._rec(
                'tralala %d', 1,
                created=0.0),
            self._rec(
                'tralala %d', 2,
                created=1.1),
            self._rec(
                'hohoho %d %s', 3, 'a',
                created=2.2),
            self._rec(
                'not exceeding',
                created=2.5),
            self._rec(
                'not exceeding',
                created=3.0),
            self._rec(
                'tralala %d', 4,
                created=3.3),
            self._rec(
                'hohoho %d %s', 5, 'b',
                created=4.4),
            self._rec(
                'tralala %d', 6,
                created=5.5),
            self._rec(
                'hohoho %d %s', 7, 'c',
                created=6.6),
            self._rec(
                'tralala %d', 8,
                created=7.7),
            self._rec(
                'tralala %d', 9,
                created=8.12345),
            self._rec(
                'hohoho %d %s', 10, 'd',
                created=8.8),
            self._rec(
                'tralala %d', 11,
                created=9.9),
            self._rec(
                'hohoho %d %s', 12, 'e',
                created=10.0),
            self._rec(
                'tralala %d', 13,
                created=12345.6),
            self._rec(
                'tralala %d', 14,
                created=12355.5),
            self._rec(
                'tralala %d', 15,
                created=12365.4),
            self._rec(
                'tralala %d', 16,
                created=12375.3),
            self._rec(
                'tralala %d', 17,
                created=99999),
            self._rec(
                'hohoho %d %s', 1234567, 'z',
                created=99999.1),
            self._rec(
                'tralala %d', 18,
                created=99999.2),
            self._rec(
                'not exceeding',
                created=99999.2),
            self._rec(
                'not exceeding',
                created=99999.9),
            self._rec(
                'not exceeding',
                created=99999.9),
            self._rec(
                'tralala %d', 19,
                created=99999.9),
            self._rec(
                'tralala %d', 20,
                created=99999.9),
            self._rec(
                'tralala %d', 21,
                created=99999.999),
            self._rec(
                'tralala %d', 22,
                created=100000.0),
        ]
        res = []
        for rec in records:
            serialized = self.serializer(rec)
            if serialized is DoNotPublish:
                extracted = serialized
            else:
                deserialized = json.loads(serialized)
                extracted = dict(message=deserialized['message'])
                if 'msg_reached_count_max' in deserialized:
                    extracted['msg_reached_count_max'] = deserialized['msg_reached_count_max']
                if 'msg_skipped_to_count' in deserialized:
                    extracted['msg_skipped_to_count'] = deserialized['msg_skipped_to_count']
            res.append(extracted)
        self.assertEqual(res, [
            {
                'message': u'tralala 1',
            },
            {
                'message': u'tralala 2',
            },
            {
                'message': u'hohoho 3 a',
            },
            {
                'message': u'not exceeding',
            },
            {
                'message': u'not exceeding',
            },
            {
                'message': u'tralala 4',
                'msg_reached_count_max': 3,
            },
            {
                'message': u'hohoho 5 b',
            },
            DoNotPublish,  # skipped 'tralala 6'
            {
                'message': u'hohoho 7 c',
                'msg_reached_count_max': 3,
            },
            DoNotPublish,  # skipped 'tralala 8'
            DoNotPublish,  # skipped 'tralala 9'
            DoNotPublish,  # skipped 'hohoho 10 d'
            DoNotPublish,  # skipped 'tralala 11'
            {
                'message': u'hohoho 12 e',
                'msg_skipped_to_count': {
                    u'hohoho %d %s': 1,
                    u'tralala %d': 4,
                }
            },
            {
                'message': u'tralala 13',
            },
            {
                'message': u'tralala 14',
            },
            {
                'message': u'tralala 15',
            },
            {
                'message': u'tralala 16',
            },
            {
                'message': u'tralala 17',
            },
            {
                'message': u'hohoho 1234567 z',
            },
            {
                'message': u'tralala 18',
            },
            {
                'message': u'not exceeding',
            },
            {
                'message': u'not exceeding',
            },
            {
                'message': u'not exceeding',
                'msg_reached_count_max': 3,
            },
            {
                'message': u'tralala 19',
                'msg_reached_count_max': 3,
            },
            DoNotPublish,  # skipped 'tralala 20'
            DoNotPublish,  # skipped 'tralala 21'
            {
                'message': u'tralala 22',
                'msg_skipped_to_count': {
                    u'tralala %d': 2,
                }
            },
        ])


# MAYBE TODO: AMQPHandler unit tests (apart from the above ones)
#class TestAMQPHandler

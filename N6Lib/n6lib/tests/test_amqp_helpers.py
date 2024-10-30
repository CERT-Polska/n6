# Copyright (c) 2013-2024 NASK. All rights reserved.

import re
import ssl
import unittest
from unittest.mock import (
    MagicMock,
    call,
    sentinel as sen,
)

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.amqp_helpers import (
    SimpleAMQPExchangeTool,
    get_amqp_connection_params_dict,
)
from n6lib.config import ConfigSection
from n6lib.unit_test_helpers import (
    AnyMatchingRegex,
    TestCaseMixin,
)


RABBITMQ_CONFIG_SPEC_PATTERN = '''
    [{rabbitmq_config_section}]
    host
    port :: int
    heartbeat_interval :: int
    ssl :: bool
    ssl_ca_certs = <to be specified if the `ssl` option is true>
    ssl_certfile = <to be specified if the `ssl` option is true>
    ssl_keyfile = <to be specified if the `ssl` option is true>
    ...
'''

CONN_PARAM_CLIENT_PROP_INFORMATION = AnyMatchingRegex(re.compile(
    r'\A'
    r'Host: [^,]+, '
    r'PID: [0-9]+, '
    r'script: [^,]+, '
    r'args: \[.*\], '
    r'modified: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}Z'
    r'\Z',
    re.ASCII))


@expand
class TestSimpleAMQPExchangeTool(unittest.TestCase, TestCaseMixin):

    @foreach(
        param(
            init_kwargs=dict(),
            expected_call_to_get_amqp_connection_params_dict=call(
                rabbitmq_config_section="rabbitmq",
            ),
        ),
        param(
            init_kwargs=dict(
                rabbitmq_config_section="some_custom",
            ),
            expected_call_to_get_amqp_connection_params_dict=call(
                rabbitmq_config_section="some_custom",
            ),
        ),
    )
    def test__init(self, init_kwargs, expected_call_to_get_amqp_connection_params_dict):
        get_amqp_conn_pd = self.patch('n6lib.amqp_helpers.get_amqp_connection_params_dict')
        get_amqp_conn_pd.return_value = sen.connection_params_dict

        instance = SimpleAMQPExchangeTool(**init_kwargs)

        self.assertIs(instance._connection_params_dict, sen.connection_params_dict)
        self.assertIs(instance._connection, None)
        self.assertIs(instance._channel, None)
        self.assertEqual(get_amqp_conn_pd.mock_calls, [
            expected_call_to_get_amqp_connection_params_dict,
        ])

    def test__enter(self):
        pika_connparams = self.patch('pika.ConnectionParameters')
        pika_blockingconn = self.patch('pika.BlockingConnection')
        block_conn_mock = MagicMock()
        block_conn_mock.channel.return_value = sen.channel_obj
        pika_blockingconn.return_value = block_conn_mock
        pika_connparams.return_value = sen.conn_params
        instance = SimpleAMQPExchangeTool.__new__(SimpleAMQPExchangeTool)
        instance._connection = None
        instance._channel = None
        instance._connection_params_dict = {'some_kwargs': sen.some_value}

        enter_result = instance.__enter__()

        self.assertEqual(pika_connparams.mock_calls, [
            call(some_kwargs=sen.some_value)
        ])
        self.assertEqual(pika_blockingconn.mock_calls, [
            call(sen.conn_params),
            call().channel(),
        ])
        self.assertIs(enter_result, instance)
        self.assertIs(instance._connection, block_conn_mock)
        self.assertIs(instance._channel, sen.channel_obj)

    @foreach(
        param(None, None, None),
        param(ValueError, ValueError('foo'), sen.traceback),
    )
    def test__exit(self, exc_type, exc_val, exc_tb):
        instance = SimpleAMQPExchangeTool.__new__(SimpleAMQPExchangeTool)
        block_conn_mock = instance._connection = MagicMock()
        instance._channel = sen.channel_obj

        exit_result = instance.__exit__(exc_type, exc_val, exc_tb)

        self.assertEqual(block_conn_mock.mock_calls, [call.close()])
        self.assertIs(instance._connection, None)
        self.assertIs(instance._channel, None)
        self.assertFalse(exit_result)

    def test_declare_exchange(self):
        instance = SimpleAMQPExchangeTool.__new__(SimpleAMQPExchangeTool)
        instance._channel = MagicMock()

        instance.declare_exchange(exchange='o1',
                                  exchange_type='topic',
                                  whatever_kwargs=sen.whatever_kwargs)

        self.assertEqual(instance._channel.mock_calls, [
            call.exchange_declare(exchange='o1',
                                  exchange_type='topic',
                                  whatever_kwargs=sen.whatever_kwargs),
        ])

    def test_bind_exchange_to_exchange(self):
        instance = SimpleAMQPExchangeTool.__new__(SimpleAMQPExchangeTool)
        instance._channel = MagicMock()

        instance.bind_exchange_to_exchange(exchange='o1',
                                           source_exchange='clients',
                                           whatever_kwargs=sen.whatever_kwargs)

        self.assertEqual(instance._channel.mock_calls, [
            call.exchange_bind(destination='o1',
                               source='clients',
                               whatever_kwargs=sen.whatever_kwargs),
        ])

    def test_delete_exchange(self):
        instance = SimpleAMQPExchangeTool.__new__(SimpleAMQPExchangeTool)
        instance._channel = MagicMock()

        instance.delete_exchange('o1', whatever_kwargs=sen.whatever_kwargs)

        self.assertEqual(instance._channel.mock_calls, [
            call.exchange_delete(exchange='o1',
                                 whatever_kwargs=sen.whatever_kwargs),
        ])


@expand
class Test_get_amqp_connection_params_dict(unittest.TestCase, TestCaseMixin):

    def setUp(self):
        self.ConfigMock = self.patch('n6lib.config.Config')
        self.patch('n6lib.amqp_helpers.pika.credentials.ExternalCredentials',
                   return_value=sen.ExternalCredentials)

    @foreach([
        param(
            given_args=[],
            expected_rabbitmq_config_section='rabbitmq',
        ),
        param(
            given_args=['particular_section'],
            expected_rabbitmq_config_section='particular_section',
        ),
    ])
    @foreach([
        param(
            conf_section_content={
                'host': 'debian',
                'port': 5672,
                'ssl': 0,
                'heartbeat_interval': 30,
            },
            expected_result={
                'host': 'debian',
                'port': 5672,
                'ssl': 0,
                'ssl_options': {},
                'heartbeat_interval': 30,
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ),
        param(
            conf_section_content={
                'host': 'debian',
                'port': 5672,
                'ssl': 1,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'ssl_certfile': '/cert/client/cert.pem',
                'ssl_keyfile': '/cert/client/key.pem',
                'heartbeat_interval': 30,
            },
            expected_result={
                'host': 'debian',
                'port': 5672,
                'ssl': 1,
                'ssl_options': {
                    'ca_certs': '/cert/testca/cacert.pem',
                    'certfile': '/cert/client/cert.pem',
                    'keyfile': '/cert/client/key.pem',
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
                'heartbeat_interval': 30,
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ),
    ])
    def test(self,
             given_args,
             conf_section_content,
             expected_rabbitmq_config_section,
             expected_result):

        self.ConfigMock.section.return_value = ConfigSection(
            '<irrelevant for these tests>',
            conf_section_content)
        expected_rabbitmq_config_spec = RABBITMQ_CONFIG_SPEC_PATTERN.format(
            rabbitmq_config_section=expected_rabbitmq_config_section)

        result = get_amqp_connection_params_dict(*given_args)

        self.assertEqual(self.ConfigMock.mock_calls, [
            call.section(expected_rabbitmq_config_spec),
        ])
        self.assertEqual(result, expected_result)

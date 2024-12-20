# Copyright (c) 2013-2024 NASK. All rights reserved.

import contextlib
import copy
import os
import pathlib
import random
import re
import ssl
import unittest
from unittest.mock import (
    MagicMock,
    call,
    patch,
    sentinel as sen,
)

from pika.credentials import PlainCredentials
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.amqp_helpers import (
    GUEST_PASSWORD,
    GUEST_USERNAME,
    RABBITMQ_CONFIG_SPEC_PATTERN,
    AMQPConnectionParamsError,
    SimpleAMQPExchangeTool,
    get_amqp_connection_params_dict,
    get_amqp_connection_params_dict_from_args,
)
from n6lib.config import (
    ConfigError,
    ConfigSection,
)
from n6lib.unit_test_helpers import (
    AnyMatchingRegex,
    TestCaseMixin,
)


CONF_SECTION_DEFAULTS = dict(
    # (see: `n6lib.amqp_helpers.RABBITMQ_CONFIG_SPEC_PATTERN`)
    ssl_ca_certs='',
    ssl_certfile='',
    ssl_keyfile='',
    password_auth=False,
    username=GUEST_USERNAME,
    password=GUEST_PASSWORD,
)

CONN_PARAM_CLIENT_PROP_INFORMATION = AnyMatchingRegex(re.compile(
    r'(?a)'
    r'\A'
    r'Host: [^,]+, '
    r'PID: [0-9]+, '
    r'script: [^,]+, '
    r'args: \[.*\], '
    r'modified: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}Z'
    r'\Z',
))


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
        self.patch(
            'pika.credentials.ExternalCredentials',
            return_value=sen.ExternalCredentials,
        )
        self.patch(
            'n6lib.amqp_helpers.LOGGER',
        )

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
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 10,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'ssl_certfile': '/cert/client/cert.pem',
                'ssl_keyfile': '/cert/client/key.pem',
            },
            expected_result={
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 10,
                'ssl': True,
                'ssl_options': {
                    'ca_certs': '/cert/testca/cacert.pem',
                    'certfile': '/cert/client/cert.pem',
                    'keyfile': '/cert/client/key.pem',
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ).label('client-certificate-based authentication (aka SSL auth)'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 20,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
            },
            expected_result={
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 20,
                'ssl': True,
                'ssl_options': {
                    'ca_certs': '/cert/testca/cacert.pem',
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ).label('username-and-password-based authentication (aka password auth)'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5672,
                'heartbeat_interval': 30,
                'ssl': False,
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
            },
            expected_result={
                'host': 'debian',
                'port': 5672,
                'heartbeat_interval': 30,
                'ssl': False,
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ).label('username-and-password-based authentication, insecure connection (no SSL)'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 40,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
            },
            expected_result={
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 40,
                'ssl': True,
                'ssl_options': {
                    'ca_certs': '/cert/testca/cacert.pem',
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': PlainCredentials(
                    GUEST_USERNAME,
                    GUEST_PASSWORD,
                ),
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ).label('no real authentication'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5672,
                'heartbeat_interval': 50,
                'ssl': False,
            },
            expected_result={
                'host': 'debian',
                'port': 5672,
                'heartbeat_interval': 50,
                'ssl': False,
                'credentials': PlainCredentials(
                    GUEST_USERNAME,
                    GUEST_PASSWORD,
                ),
                'client_properties': {
                    'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
                },
            },
        ).label('no real authentication, insecure connection (no SSL)'),
    ])
    def test_success(self,
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
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 30,
                'ssl': True,
            },
        ).label('`ssl` set to True, but `ssl_ca_certs` unspecified'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 30,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'ssl_certfile': '/cert/client/cert.pem',
            },
        ).label('`ssl` set to True and `ssl_certfile` specified, but `ssl_keyfile` unspecified'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 30,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'ssl_keyfile': '/cert/client/key.pem',
            },
        ).label('`ssl` set to True and `ssl_keyfile` specified, but `ssl_certfile` unspecified'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 30,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 15 * 'x',
            },
        ).label('too short password'),

        param(
            conf_section_content=CONF_SECTION_DEFAULTS | {
                'host': 'debian',
                'port': 5671,
                'heartbeat_interval': 30,
                'ssl': True,
                'ssl_ca_certs': '/cert/testca/cacert.pem',
                'password_auth': True,
                'username': 'my-user@example.com',
            },
        ).label('missing password'),
    ])
    def test_config_error(self,
                          given_args,
                          conf_section_content,
                          expected_rabbitmq_config_section):

        self.ConfigMock.section.return_value = ConfigSection(
            '<irrelevant for these tests>',
            conf_section_content)
        expected_rabbitmq_config_spec = RABBITMQ_CONFIG_SPEC_PATTERN.format(
            rabbitmq_config_section=expected_rabbitmq_config_section)
        with self.assertRaises(ConfigError):

            get_amqp_connection_params_dict(*given_args)

        self.assertEqual(self.ConfigMock.mock_calls, [
            call.section(expected_rabbitmq_config_spec),
        ])


@expand
class Test_get_amqp_connection_params_dict_from_args(unittest.TestCase, TestCaseMixin):

    @classmethod
    def setUpClass(cls):
        cls.prng = random.Random('** arbitrary but deterministic seed **')

    def setUp(self):
        self.patch(
            'pika.credentials.ExternalCredentials',
            return_value=sen.ExternalCredentials,
        )


    GIVEN_CA_CERTS_PATH = '/given/ca/certs'
    GIVEN_CERTFILE_PATH = '/given/certfile'
    GIVEN_KEYFILE_PATH = '/given/keyfile'

    EXPANDED_CA_CERTS_PATH = '/example/expanded/ca/certs'
    EXPANDED_CERTFILE_PATH = '/example/expanded/certfile'
    EXPANDED_KEYFILE_PATH = '/example/expanded/keyfile'

    @paramseq
    def success_cases(cls):  # noqa
        KWARGS_BASE = {  # noqa
            'host': 'example.com',
            'port': 5671,
        }
        EXPECTED_RESULT_BASE = KWARGS_BASE | {  # noqa
            'ssl': False,
            'client_properties': {
                'information': CONN_PARAM_CLIENT_PROP_INFORMATION,
            },
            'credentials': PlainCredentials(
                GUEST_USERNAME,
                GUEST_PASSWORD,
            ),
        }

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'certfile': cls.GIVEN_CERTFILE_PATH,
                'keyfile': cls.GIVEN_KEYFILE_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
            },
            expected_log_warning_func_calls=[],
        ).label(
            'enabled SSL (giving `ca_certs`), '
            'enabled client-certificate-based authentication (giving `certfile` and `keyfile`)',
        )

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,  # <- Redundant yet allowed
                },
                'certfile': cls.GIVEN_CERTFILE_PATH,
                'keyfile': cls.GIVEN_KEYFILE_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
            },
            expected_log_warning_func_calls=[],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...), '
            'enabled client-certificate-based authentication (giving `certfile` and `keyfile`)',
        )

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'certfile': cls.GIVEN_CERTFILE_PATH,
                    'keyfile': cls.GIVEN_KEYFILE_PATH,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'heartbeat_interval': 42,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'credentials': sen.ExternalCredentials,
                'heartbeat_interval': 42,
            },
            expected_log_warning_func_calls=[],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...), '
            'enabled client-certificate-based authentication (via `ssl_options`...)',
        )

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'cert_reqs': ssl.CERT_REQUIRED,  # <- Redundant yet allowed
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
                'heartbeat_interval': 12345,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
                'heartbeat_interval': 12345,
            },
            expected_log_warning_func_calls=[],
        ).label(
            'enabled SSL (giving `ca_certs` + also `ssl_options` containing only extra stuff...), '
            'enabled username-and-password-based authentication',
        )

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                },
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
            },
            expected_log_warning_func_calls=[],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...), '
            'enabled username-and-password-based authentication',
        )

        # WARNING to be logged about insecure SSL option cert_reqs=ssl.CERT_NONE:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'certfile': cls.GIVEN_CERTFILE_PATH,
                    'keyfile': cls.GIVEN_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_NONE,      # <- Note this unrecommended but legal option!
                    'arbitrary-extra-key': sen.WHATEVER,
                },
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_NONE,      # <- Note this unrecommended but legal option!
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'credentials': sen.ExternalCredentials,
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"AMQP server's certificate will \*not\* be verified"
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...) '
            'with cert_reqs=ssl.CERT_NONE in `ssl_options`, '
            'enabled client-certificate-based authentication (via `ssl_options`...)',
        )

        # WARNING to be logged about insecure SSL option cert_reqs=ssl.CERT_OPTIONAL:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'cert_reqs': ssl.CERT_OPTIONAL,  # <- Note this unrecommended but legal option!
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_OPTIONAL,  # <- Note this unrecommended but legal option!
                },
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"AMQP server's certificate may \*not\* be verified"
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`) '
            'with cert_reqs=ssl.CERT_OPTIONAL in `ssl_options`, '
            'enabled username-and-password-based authentication',
        )

        # WARNING to be logged about ignoring `certfile` and `keyfile`
        # when username-and-password-based authentication is enabled:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'keyfile': cls.GIVEN_KEYFILE_PATH,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'certfile': cls.GIVEN_CERTFILE_PATH,
                'password_auth': True,
                'username': 'my-user@example.com',
                'password': 'Passwd&Passwd:-)',
                'heartbeat_interval': 42,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    # Note: no 'certfile' and no 'keyfile'!
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'credentials': PlainCredentials(
                    'my-user@example.com',
                    'Passwd&Passwd:-)',
                ),
                'heartbeat_interval': 42,
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'client certificate .* will be ignored'
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`... + `ssl_options` containing e.g. "keyfile"...), '
            'enabled username-and-password-based authentication',
        )

        # WARNING to be logged about missing username
        # => *guest* pseudo-authentication:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                },
                'password_auth': True,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"password_auth=True but username="
                    r"None, so .*\*no\* real AMQP "
                    r"authentication will be performed"
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...), '
            'requested username-and-password-based authentication '
            'but with unspecified `username` (and `password`) => no real authentication',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'password_auth': True,
                'password': '...whatever...',  # <- Doesn't really matter here
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"password_auth=True but username="
                    r"None, so .*\*no\* real AMQP "
                    r"authentication will be performed"
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`), '
            'requested username-and-password-based authentication '
            'but with unspecified `username` => no real authentication',
        )

        # WARNING to be logged about username='guest
        # => *guest* pseudo-authentication:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                },
                'password_auth': True,
                'username': GUEST_USERNAME,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    rf"password_auth=True but username="
                    rf"'{GUEST_USERNAME}', so .*\*no\* real "
                    rf"AMQP authentication will be performed"
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options` containing "ca_certs"...), '
            'requested username-and-password-based authentication '
            'but with *guest* `username` (and unspecified `password`) => no real authentication',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'password_auth': True,
                'username': GUEST_USERNAME,
                'password': '...whatever...',  # <- Doesn't really matter here
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    rf"password_auth=True but username="
                    rf"'{GUEST_USERNAME}', so .*\*no\* real "
                    rf"AMQP authentication will be performed"
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`), '
            'requested username-and-password-based authentication '
            'but with *guest* `username` => no real authentication',
        )

        # WARNING to be logged about the lack of any authentication-related
        # arguments/options => *guest* pseudo-authentication:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=True, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`), '
            'no real authentication',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=True, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs` + also `ssl_options` containing only extra stuff...), '
            'no real authentication',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,  # <- Redundant yet allowed
                },
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=True, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options`...), '
            'no real authentication',
        )

        # Also, WARNING to be logged about unsecured communication (no SSL):
        yield param(
            given_kwargs=KWARGS_BASE,
            expected_result=EXPECTED_RESULT_BASE,
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'AMQP communication will \*not\* be TLS-secured'
                )),
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=False, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'no SSL, '
            'no real authentication',
        )

        # Also, WARNING to be logged about ignoring each of the SSL-related
        # arguments when `ssl` is false or not given:
        for key in [
            'ca_certs',
            'certfile',
            'keyfile',
        ]:
            yield param(
                given_kwargs=KWARGS_BASE | {
                    key: '/some/file/path',
                },
                expected_result=EXPECTED_RESULT_BASE,
                expected_log_warning_func_calls=[
                    call(AnyMatchingRegex(
                        rf'these argument\(s\) will be ignored: '
                        rf'{key}=[^=]+(?:, ssl_options=[^=]+)?\.$'
                    )),
                    call(AnyMatchingRegex(
                        r'AMQP communication will \*not\* be TLS-secured'
                    )),
                    call(AnyMatchingRegex(
                        r'password_auth=False, ssl=False, .*'
                        r'\*no\* real AMQP authentication '
                        r'will be performed'
                    )),
                ],
            ).label(
                f'no SSL (with `{key}` given but ignored), '
                f'no real authentication',
            )
            yield param(
                given_kwargs=KWARGS_BASE | {
                    'ssl_options': {key: '/some/file/path'},
                },
                expected_result=EXPECTED_RESULT_BASE,
                expected_log_warning_func_calls=[
                    call(AnyMatchingRegex(
                        rf'these argument\(s\) will be ignored: '
                        rf'ssl_options=[^=]+\b{key}\b[^=]+\.$'
                    )),
                    call(AnyMatchingRegex(
                        r'AMQP communication will \*not\* be TLS-secured'
                    )),
                    call(AnyMatchingRegex(
                        r'password_auth=False, ssl=False, .*'
                        r'\*no\* real AMQP authentication '
                        r'will be performed'
                    )),
                ],
            ).label(
                f'no SSL (with `ssl_options` containing "{key}" given but ignored), '
                f'no real authentication',
            )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl_options': {
                    'certfile': cls.GIVEN_CERTFILE_PATH,
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'keyfile': cls.GIVEN_KEYFILE_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE,
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r'these argument\(s\) will be ignored: '
                    r'ca_certs=[^=]+, keyfile=[^=]+, '
                    r'ssl_options=[^=]+certfile[^=]+\.$'
                )),
                call(AnyMatchingRegex(
                    r'AMQP communication will \*not\* be TLS-secured'
                )),
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=False, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            f'no SSL (with various SSL-related arguments/options given but ignored), '
            f'no real authentication',
        )

        # Also, WARNING to be logged about ignoring `username` and/or `password`
        # when they are given, but `password_auth` is false (or not given)...:
        yield param(
            given_kwargs=KWARGS_BASE | {
                'username': 'my-user@example.com',
            },
            expected_result=EXPECTED_RESULT_BASE,
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"^password_auth=False, so these "
                    r"argument\(s\) will be ignored: "
                    r"username='my-user@example.com'\.$"
                )),
                call(AnyMatchingRegex(
                    r'AMQP communication will \*not\* be TLS-secured'
                )),
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=False, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'no SSL, '
            'no real authentication, '
            'with `username` given but ignored',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'cert_reqs': ssl.CERT_NONE,
                },
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'username': 'my-user@example.com',
                'password': '...whatever...',
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_NONE,
                }
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"^password_auth=False, so these "
                    r"argument\(s\) will be ignored: "
                    r"username='my-user@example.com', "
                    r"password=<...hidden...>\.$"
                )),
                call(AnyMatchingRegex(
                    r"AMQP server's certificate will \*not\* be verified"
                )),
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=True, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`...) '
            'with cert_reqs=ssl.CERT_NONE in `ssl_options`, '
            'no real authentication, '
            'with `username` and `password` given but ignored',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'password': '...whatever...',
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                }
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"^password_auth=False, so these "
                    r"argument\(s\) will be ignored: "
                    r"password=<...hidden...>\.$"
                )),
                call(AnyMatchingRegex(
                    r'password_auth=False, ssl=True, .*'
                    r'\*no\* real AMQP authentication '
                    r'will be performed'
                )),
            ],
        ).label(
            'enabled SSL (giving `ca_certs`...) '
            'no real authentication, '
            'with `password` given but ignored',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'certfile': cls.GIVEN_CERTFILE_PATH,
                },
                'keyfile': cls.GIVEN_KEYFILE_PATH,
                'username': 'my-user@example.com',
                'password': '...whatever...',
                'heartbeat_interval': 12345,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
                'heartbeat_interval': 12345,
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    r"^password_auth=False, so these "
                    r"argument\(s\) will be ignored: "
                    r"username='my-user@example.com', "
                    r"password=<...hidden...>\.$"
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options`...), '
            'enabled client-certificate-based authentication (via `ssl_options`...), '
            'with `username` and `password` given but ignored',
        )
        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                    'certfile': cls.GIVEN_CERTFILE_PATH,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'keyfile': cls.GIVEN_KEYFILE_PATH,
                'username': GUEST_USERNAME,  # <- Here it doesn't really matter it's GUEST_USERNAME
                'password': GUEST_PASSWORD,  # <- Here it doesn't really matter it's GUEST_PASSWORD
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                    'arbitrary-extra-key': sen.WHATEVER,
                },
                'credentials': sen.ExternalCredentials,
            },
            expected_log_warning_func_calls=[
                call(AnyMatchingRegex(
                    rf"^password_auth=False, so these "
                    rf"argument\(s\) will be ignored: "
                    rf"username='{GUEST_USERNAME}', "
                    rf"password=<...hidden...>\.$"
                )),
            ],
        ).label(
            'enabled SSL (giving `ssl_options`...), '
            'enabled client-certificate-based authentication (via `ssl_options`...), '
            'with *guest* `username` and `password` given but ignored',
        )

        # WARNING to be logged about unavailable *mtime* of the script:
        yield param(
            with_script_modification_time_unavailable=True,
            given_kwargs=KWARGS_BASE | {
                'ssl': True,
                'ca_certs': cls.GIVEN_CA_CERTS_PATH,
                'certfile': cls.GIVEN_CERTFILE_PATH,
                'keyfile': cls.GIVEN_KEYFILE_PATH,
            },
            expected_result=EXPECTED_RESULT_BASE | {
                'client_properties': {
                    'information': AnyMatchingRegex(
                        r'(?a)'
                        r'\A'
                        r'Host: [^,]+, '
                        r'PID: [0-9]+, '
                        r'script: [^,]+, '
                        r'args: \[.*\], '
                        r'modified: UNKNOWN'  # (<- also note this)
                        r'\Z'
                    ),
                },
                'ssl': True,
                'ssl_options': {
                    'ca_certs': cls.EXPANDED_CA_CERTS_PATH,
                    'certfile': cls.EXPANDED_CERTFILE_PATH,
                    'keyfile': cls.EXPANDED_KEYFILE_PATH,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
                'credentials': sen.ExternalCredentials,
            },
            expected_log_warning_func_calls=[
                call('Could not determine script mtime!'),
            ],
        ).label(
            'with unavailable *mtime* of the script',
        )

    @foreach([
        param(giving_all_defaults=False),
        param(giving_all_defaults=True),
    ])
    @foreach([
        param(using_set_log_warning_func=False),
        param(using_set_log_warning_func=True),
    ])
    @foreach(success_cases)
    def test_success(self,
                     given_kwargs,
                     giving_all_defaults,
                     using_set_log_warning_func,
                     expected_result,
                     expected_log_warning_func_calls,
                     with_script_modification_time_unavailable=False):

        self.patch(
            'os.path.expanduser',
            side_effect={
                pathlib.Path(self.GIVEN_CA_CERTS_PATH): self.EXPANDED_CA_CERTS_PATH,
                pathlib.Path(self.GIVEN_CERTFILE_PATH): self.EXPANDED_CERTFILE_PATH,
                pathlib.Path(self.GIVEN_KEYFILE_PATH): self.EXPANDED_KEYFILE_PATH,
            }.__getitem__,
        )
        if with_script_modification_time_unavailable:
            self.patch(
                'n6lib.const.SCRIPT_FILENAME',
                '/. SOME ./. NON-EXISTENT ./. FILE ./. PATH ./.  :-D',
            )
        given_kwargs = self._prepare_actual_given_kwargs(
            given_kwargs,
            giving_all_defaults,
            freely_adding_ssl_or_auth_related_void_values=True,
        )
        with self.assertStateUnchanged(given_kwargs), \
             self._log_warning_func_ctx_manager(using_set_log_warning_func) as log_warning_func:

            result = get_amqp_connection_params_dict_from_args(**given_kwargs)

        self.assertEqual(result, expected_result)
        self.assertEqual(log_warning_func.mock_calls, expected_log_warning_func_calls)


    @paramseq
    def error_cases():  # noqa
        KWARGS_BASE = {  # noqa
            'host': 'example.com',
            'port': 5671,
        }

        for missing in [
            ['host', 'port'],
            ['host'],
            ['port']
        ]:
            missing_arg_listing = ' and '.join(f'`{k}`' for k in missing)
            yield param(
                given_kwargs={
                    k: v for k, v in KWARGS_BASE.items()
                    if k not in missing},
                expected_exc_type=TypeError,
                expected_exc_regex=r'argument'
            ).label(
                f'missing arguments: {missing_arg_listing}',
            )

        for key in ['username', 'password']:
            yield param(
                given_kwargs=KWARGS_BASE | {
                    key: b'not-a-string',
                },
                expected_exc_type=TypeError,
                expected_exc_regex=rf'{key} must be a str or None',
            ).label(
                f'wrong argument type: `{key}` is not a str or None',
            )

        yield param(
            given_kwargs=KWARGS_BASE | {
                'ssl_options': ['neither-a-dict-nor-None'],
            },
            expected_exc_type=TypeError,
            expected_exc_regex=r'must be a dict or None',
        ).label(
            'wrong argument type: `ssl_options` is neither a dict nor None',
        )

        for key in ['ca_certs', 'certfile', 'keyfile']:
            yield param(
                given_kwargs=KWARGS_BASE | {
                    key: '/some/file/path',
                    f'ssl_{key}': '/some/file/path',
                },
                expected_exc_type=TypeError,
                expected_exc_regex=(
                    rf"\bssl_{key}=[^=]+ and {key}=[^=]+ "
                    rf"\(only one of them should be specified\)"
                ),
            ).label(
                f'duplicate stuff: arguments `ssl_{key}` '
                f'and `{key}` both specified',
            )

            for prefix in ['', 'ssl_']:
                prefixed = prefix + key
                yield param(
                    given_kwargs=KWARGS_BASE | {
                        'ssl_options': {
                            key: '/some/file/path',
                        },
                        prefixed: '/some/file/path',
                    },
                    expected_exc_type=TypeError,
                    expected_exc_regex=(
                        rf"\b{key}=[^=]+ and ssl_options\['{key}'\]=[^=]+ "
                        rf"\(only one of them should be specified\)"
                    ),
                ).label(
                    f'duplicate stuff: argument `{prefixed}` '
                    f'and ssl_options["{key}"] both specified',
                )

        for ca_certs_descr, kwargs_upd in {
            'argument `ca_certs` is not present': {},
            'argument `ca_certs` is None': {
                'ca_certs': None,
            },
            'argument `ca_certs` is empty str': {
                'ca_certs': '',
            },
            'ssl_options["ca_certs"] is not present, `ssl_options` is empty dict': {
                'ssl_options': {},
            },
            'ssl_options["ca_certs"] is None': {
                'ssl_options': {'ca_certs': None},
            },
            'ssl_options["ca_certs"] is empty str': {
                'ssl_options': {'ca_certs': ''},
            },
        }.items():
            yield param(
                given_kwargs=KWARGS_BASE | {'ssl': True} | kwargs_upd,
                expected_exc_type=AMQPConnectionParamsError,
                expected_exc_regex=r'ssl=True but ca_certs=',
            ).label(
                f'`ssl` set to True, but `ca_certs` '
                f'unspecified ({ca_certs_descr})',
            )

        for spec, unspec in [
            ('certfile', 'keyfile'),
            ('keyfile', 'certfile'),
        ]:
            def _prepare_ad_spec(kwargs):
                if spec_in_ssl_options:
                    descr = f'ssl_options["{spec}"] is present'
                    upd_target = kwargs.setdefault('ssl_options', {})
                else:
                    descr = f'argument `{spec}` is present'
                    upd_target = kwargs
                upd_target.update({
                    spec: '/some/file...',
                    'ca_certs': '/some/file...',
                })
                return descr

            def _prepare_ad_unspec(kwargs):
                if unspec_in_ssl_options:
                    descr = f'ssl_options["{unspec}"] {unspec_how}'
                    upd_target = kwargs.setdefault('ssl_options', {})
                    if not unspec_upd:
                        # (see the `continue` statement below...)
                        assert not upd_target, "test's internal premise"
                        descr += ', `ssl_options` is empty dict'
                else:
                    descr = f'argument `{unspec}` {unspec_how}'
                    upd_target = kwargs
                upd_target.update(unspec_upd)
                return descr

            for spec_in_ssl_options in [False, True]:
                for unspec_in_ssl_options in [False, True]:
                    for unspec_how, unspec_upd in {
                        'is not present': {},
                        'is None': {unspec: None},
                        'is empty str': {unspec: ''},
                    }.items():
                        if spec_in_ssl_options and unspec_in_ssl_options and not unspec_upd:
                            # It would be a duplicate of the sibling case with
                            # `unspec_in_ssl_options=False`, so let's skip it.
                            continue

                        given_kwargs: dict = KWARGS_BASE | {
                            'ssl': True,
                        }
                        spec_descr = _prepare_ad_spec(given_kwargs)
                        unspec_descr = _prepare_ad_unspec(given_kwargs)
                        yield param(
                            given_kwargs=given_kwargs,
                            expected_exc_type=AMQPConnectionParamsError,
                            expected_exc_regex=r'certfile=[^=]+ but keyfile=',
                        ).label(
                            f'`ssl` set to True and '
                            f'`{spec}` specified ({spec_descr}) but '
                            f'`{unspec}` unspecified ({unspec_descr})'
                        )

        for password_descr, kwargs_upd in {
            'password is not present': {},
            'password is None': {'password': None},
            'password is empty str': {'password': ''},
            'password is too short': {'password': 15 * 'x'},
        }.items():
            yield param(
                given_kwargs=KWARGS_BASE | kwargs_upd | {
                    'password_auth': True,
                    'username': 'my-user@example.com',
                },
                expected_exc_type=AMQPConnectionParamsError,
                expected_exc_regex=r'password is missing or too short',
            ).label(
                password_descr,
            )

    @foreach([
        param(giving_all_defaults=False),
        param(giving_all_defaults=True),
    ])
    @foreach(error_cases)
    def test_error(self,
                   given_kwargs,
                   giving_all_defaults,
                   expected_exc_type,
                   expected_exc_regex):

        self.patch(
            'n6lib.amqp_helpers.LOGGER.warning',
            (lambda *_: None),
        )
        given_kwargs = self._prepare_actual_given_kwargs(
            given_kwargs,
            giving_all_defaults,
        )
        with self.assertStateUnchanged(given_kwargs), \
             self.assertRaisesRegex(expected_exc_type, expected_exc_regex):

            get_amqp_connection_params_dict_from_args(**given_kwargs)


    def _prepare_actual_given_kwargs(self,
                                     given_kwargs,
                                     giving_all_defaults,
                                     freely_adding_ssl_or_auth_related_void_values=False):
        #
        # Local helpers

        base_ssl_path_arg_names = ('ca_certs', 'certfile', 'keyfile')

        class ExamplePathLike:
            def __init__(self, raw):
                self._raw = raw
            def __fspath__(self):
                return self._raw
            def __eq__(self, other):
                return type(self) is type(other) and self._raw == other._raw

        def maybe_convert_str_to_other_path_type(value):
            assert isinstance(value, str), "test's internal premise"
            if once_per_n_times(2):
                value = os.fsencode(value)
                assert isinstance(value, bytes)
            if once_per_n_times(2) and value:
                value = ExamplePathLike(value)
                assert (type(value) is ExamplePathLike
                        and isinstance(value, os.PathLike))
            assert isinstance(value, (str, bytes, os.PathLike)), "test's internal premise"
            return value

        def once_per_n_times(n):
            return self.prng.randrange(n) == 0

        def empty_dictionary_or_None():  # noqa
            return self.prng.choice([{}, None])

        def empty_str_or_None():  # noqa
            return self.prng.choice(['', None])

        def liberal_flag_value(flag):  # noqa
            if flag:
                value = self.prng.choice([True, 1, 42, 'ye!', b'ye!', [None]])
                assert value
            else:
                value = self.prng.choice([False, 0, '', b'', None, []])
                assert not value
            return value

        #
        # Implementation

        actual = copy.deepcopy(given_kwargs)

        # * Let our tests cover uses of the `ssl_*` "alias" arguments...

        if once_per_n_times(2):
            for arg_name in base_ssl_path_arg_names:
                if (once_per_n_times(2)
                      and arg_name in actual
                      and f'ssl_{arg_name}' not in actual):
                    actual[f'ssl_{arg_name}'] = actual.pop(arg_name)

        # * Improve our tests by making flag arguments more diverse...

        if once_per_n_times(10):
            actual['ssl'] = liberal_flag_value(actual.get('ssl'))
        if once_per_n_times(10):
            actual['password_auth'] = liberal_flag_value(actual.get('password_auth'))

        # * Improve our tests by making SSL-related arguments more diverse...

        # `ssl_options` being an empty dict is expected to be equivalent
        # to being None or *not given*; let our tests cover that...
        if once_per_n_times(10) and freely_adding_ssl_or_auth_related_void_values:
            actual.setdefault('ssl_options', empty_dictionary_or_None())
        ssl_options = actual.get('ssl_options')

        for key in base_ssl_path_arg_names:
            for prefix in ('', 'ssl_'):
                prefixed = prefix + key

                # `ca_certs`, `certfile` or `keyfile` (or its corresponding
                # "alias") being an empty string is expected to be equivalent
                # to being None or *not given**; let our tests cover that...
                if once_per_n_times(10) and freely_adding_ssl_or_auth_related_void_values:
                    actual.setdefault(prefixed, empty_str_or_None())

                # `ca_certs`, `certfile` or `keyfile` (or its corresponding
                # "alias") does not need to be a str; an instance of bytes
                # or any path-like type can be given as well.
                if once_per_n_times(2) and (val := actual.get(prefixed)) is not None:
                    actual[prefixed] = maybe_convert_str_to_other_path_type(val)

            if isinstance(ssl_options, dict):
                # ...and the same for 'ca_certs'/'certfile'/'keyfile' items
                # of `ssl_options`, if possible.
                if once_per_n_times(10) and freely_adding_ssl_or_auth_related_void_values:
                    ssl_options.setdefault(key, empty_str_or_None())
                if once_per_n_times(2) and (val := ssl_options.get(key)) is not None:
                    ssl_options[key] = maybe_convert_str_to_other_path_type(val)

        # * Improve our tests by making `username`/`password` more diverse...

        # `username` or `password` being an empty string is expected to be
        # equivalent to being None or *not given**; let our tests cover that:
        if once_per_n_times(10) and freely_adding_ssl_or_auth_related_void_values:
            actual.setdefault('username', empty_str_or_None())
        if once_per_n_times(10) and freely_adding_ssl_or_auth_related_void_values:
            actual.setdefault('password', empty_str_or_None())

        # * Test also that redundant default values do not break anything...

        if giving_all_defaults:
            # It is expected that passing argument set to its default
            # value or an equivalent of that default value, if that
            # argument was not to be passed, will *not* change the
            # behavior of the function under test.
            actual = dict(
                heartbeat_interval=None,
                ssl=liberal_flag_value(False),
                ca_certs=empty_str_or_None(),
                certfile=empty_str_or_None(),
                keyfile=empty_str_or_None(),
                password_auth=liberal_flag_value(False),
                username=empty_str_or_None(),
                password=empty_str_or_None(),
                ssl_options=empty_dictionary_or_None(),
                ssl_ca_certs=empty_str_or_None(),
                ssl_certfile=empty_str_or_None(),
                ssl_keyfile=empty_str_or_None(),
            ) | actual

        return actual


    @contextlib.contextmanager
    def _log_warning_func_ctx_manager(self,
                                      using_set_log_warning_func):

        log_warning_func = MagicMock()

        if using_set_log_warning_func:
            cm = get_amqp_connection_params_dict_from_args.set_log_warning_func(log_warning_func)
        else:
            cm = patch('n6lib.amqp_helpers.LOGGER.warning', log_warning_func)

        with cm:
            yield log_warning_func

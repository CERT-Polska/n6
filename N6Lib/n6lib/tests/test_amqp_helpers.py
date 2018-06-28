# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import ssl
import unittest

from mock import (
    call,
    sentinel as sen,
)

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.config import ConfigSection
from n6lib.unit_test_helpers import TestCaseMixin

from n6lib.amqp_helpers import get_amqp_connection_params_dict


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


@expand
class Test__get_amqp_connection_params_dict(unittest.TestCase, TestCaseMixin):

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

# Copyright (c) 2017-2024 NASK. All rights reserved.

import unittest
from unittest.mock import (
    MagicMock,
    call,
    sentinel as sen,
)

from n6datapipeline.aux.exchange_updater import ExchangeUpdater
from n6lib.unit_test_helpers import TestCaseMixin


class TestExchangeUpdater(unittest.TestCase, TestCaseMixin):

    def test__init(self):
        auth_api = self.patch('n6datapipeline.aux.exchange_updater.AuthAPI')
        amqp_tool = self.patch('n6datapipeline.aux.exchange_updater.SimpleAMQPExchangeTool')
        auth_api.return_value = sen.auth_api
        amqp_tool.return_value = sen.amqp_tool

        instance = ExchangeUpdater()

        self.assertEqual(auth_api.mock_calls, [call()])
        self.assertEqual(amqp_tool.mock_calls, [call()])
        self.assertIs(instance._auth_api, sen.auth_api)
        self.assertIs(instance._amqp_tool, sen.amqp_tool)

    def test_run(self):
        auth_api = MagicMock()
        amqp_tool = MagicMock()
        auth_api.get_stream_api_enabled_org_ids.return_value = frozenset(('o1', 'o2'))
        auth_api.get_stream_api_disabled_org_ids.return_value = frozenset(('o3', 'o4'))
        instance = ExchangeUpdater.__new__(ExchangeUpdater)
        instance._auth_api = auth_api
        instance._amqp_tool = amqp_tool

        instance.run()

        self.assertEqual(auth_api.mock_calls, [
            call.__enter__(),
            call.get_stream_api_enabled_org_ids(),
            call.get_stream_api_disabled_org_ids(),
            call.__exit__(None, None, None),
        ])
        self.assertEqual(amqp_tool.mock_calls, [
            call.__enter__(),
            call.declare_exchange(exchange='o1', exchange_type='topic', durable=True),
            call.declare_exchange(exchange='o2', exchange_type='topic', durable=True),
            call.bind_exchange_to_exchange(exchange='o1',
                                           source_exchange='clients',
                                           arguments={'n6-client-id': 'o1'}),
            call.bind_exchange_to_exchange(exchange='o2',
                                           source_exchange='clients',
                                           arguments={'n6-client-id': 'o2'}),
            call.delete_exchange(exchange='o3'),
            call.delete_exchange(exchange='o4'),
            call.__exit__(None, None, None)
        ])


if __name__ == '__main__':
    unittest.main()

# Copyright (c) 2013-2021 NASK. All rights reserved.

import unittest
import json

from unittest.mock import (
    MagicMock,
    call,
    sentinel as sen,
)

from n6datapipeline.comparator import (
    Comparator,
    ComparatorData,
    ComparatorDataWrapper,
    ComparatorState,
)
from n6lib.unit_test_helpers import TestCaseMixin


class TestComparator__message_flow(TestCaseMixin, unittest.TestCase):

    def setUp(self):

        self.comparator = Comparator.__new__(Comparator)
        self.comparator.comparator_config = MagicMock()
        self.comparator._connection = MagicMock()

        self.comparator.state = ComparatorState(sen.irrelevant)

        self.patch_object(ComparatorDataWrapper, 'store_state')
        self.comparator.db = ComparatorDataWrapper.__new__(ComparatorDataWrapper)
        self.comparator.db.comp_data = ComparatorData()

        self.comparator.publish_output = MagicMock()

    def test_message_flow_basic(self):

        routing_key = 'bl-new.compared.source_test1.channel_test1'

        input_data_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 1,
            '_bl-series-no': 1,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        }

        expected_event_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            'type': 'bl-new',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        }

        expected_calls_list = [
            call(body=expected_event_1_1, routing_key=routing_key)
        ]
        self.comparator._process_input(input_data_1_1)

        publish_output_call_args_list = self._get_deserialized_calls(self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    def test_message_flow_new_update_change_delist(self):

        # name pattern: data_type_runNo_srcNo_eventNo
        # first run,
        routing_key_1_1_1 = 'bl-new.compared.source_test1.channel_test1'
        routing_key_1_1_2 = 'bl-new.compared.source_test1.channel_test1'

        input_data_1_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 1,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
        }

        expected_event_1_1_1 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-19 12:07:32',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
            'source': 'source_test1.channel_test1',
        }

        input_data_1_1_2 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'url': 'http://www.tests.pl',
            'address': [{
                'cc': 'XX',
                'ip': '2.2.2.2',
                'asn': 3215
            }],
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        }

        expected_event_1_1_2 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-19 12:07:32',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'url': 'http://www.tests.pl',
            'address': [{
                'cc': 'XX',
                'ip': '2.2.2.2',
                'asn': 3215
            }],
            'id': '1c9a2638b51f334da3d2311e01817884',
            'source': 'source_test1.channel_test1',
        }

        #  Second run,
        #  2. 1. msg bl-update, 2. bl-change
        routing_key_2_1_1 = 'bl-update.compared.source_test1.channel_test1'
        routing_key_2_1_2 = 'bl-change.compared.source_test1.channel_test1'

        input_data_2_1_1 = {
            '_bl-time': '2017-01-19 12:13:36',
            '_bl-series-total': 2,
            '_bl-series-no': 1,
            '_bl-series-id': '22222222222222222222222222222222',
            'expires': '2017-01-21 15:15:15',
            'time': '2017-01-19 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '4273a190e57da23c1dee67a7689e115a',
        }

        expected_event_2_1_1 = {
            'type': 'bl-update',
            '_bl-time': '2017-01-19 12:07:32',
            'expires': '2017-01-21 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
            'source': 'source_test1.channel_test1',
        }
        input_data_2_1_2 = {
            '_bl-time': '2017-01-19 14:14:14',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '22222222222222222222222222222222',
            'expires': '2017-01-21 18:18:18',
            'time': '2017-01-19 19:19:19',
            'url': 'http://www.tests.pl',
            'address': [
                {
                    'cc': 'XX',
                    'ip': '2.2.2.2',
                    'asn': 3215
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 3215
                }
            ],
            'source': 'source_test1.channel_test1',
            'id': '929c840e0dec26e26410aeeac418067d',
        }

        expected_event_2_1_2 = {
            'type': 'bl-change',
            '_bl-time': '2017-01-19 14:14:14',
            'expires': '2017-01-21 18:18:18',
            'time': '2017-01-19 19:19:19',
            'url': 'http://www.tests.pl',
            'address': [
                {
                    'cc': 'XX',
                    'ip': '2.2.2.2',
                    'asn': 3215
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 3215
                }
            ],
            'id': '929c840e0dec26e26410aeeac418067d',
            'source': 'source_test1.channel_test1',
            'replaces': '1c9a2638b51f334da3d2311e01817884',
        }

        # third run,
        # one (3.) bl-new and 1., 2. bl-delist (old events)
        routing_key_3_1_1 = 'bl-delist.compared.source_test1.channel_test1'
        routing_key_3_1_2 = 'bl-delist.compared.source_test1.channel_test1'
        routing_key_3_1_3 = 'bl-new.compared.source_test1.channel_test1'

        input_data_3_1_3 = {
            '_bl-time': '2017-01-20 10:10:10',
            '_bl-series-no': 1,
            '_bl-series-total': 1,
            '_bl-series-id': '33333333333333333333333333333333',
            'expires': '2017-01-22 10:10:10',
            'time': '2017-01-20 10:10:10',
            'address': [{
                'cc': 'XX',
                'ip': '3.3.3.3'
            }],
            'id': 'ed928c2322422b2a8e419b00426fbcb0',
            'source': 'source_test1.channel_test1',
        }

        expected_event_3_1_1 = {
            'type': 'bl-delist',
            '_bl-time': '2017-01-19 12:07:32',
            'time': '2017-01-18 15:15:15',
            'expires': '2017-01-21 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
            'source': 'source_test1.channel_test1',
        }

        expected_event_3_1_2 = {
            'type': 'bl-delist',
            'expires': '2017-01-21 18:18:18',
            'address': [
                {
                    'cc': 'XX',
                    'ip': '2.2.2.2',
                    'asn': 3215,
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 3215,
                }
            ],
            'id': '929c840e0dec26e26410aeeac418067d',
            '_bl-time': '2017-01-19 14:14:14',
            'replaces': '1c9a2638b51f334da3d2311e01817884',
            'url': 'http://www.tests.pl',
            'source': 'source_test1.channel_test1',
            'time': '2017-01-19 19:19:19',
        }

        expected_event_3_1_3 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-20 10:10:10',
            'expires': '2017-01-22 10:10:10',
            'time': '2017-01-20 10:10:10',
            'address': [{
                'cc': 'XX',
                'ip': '3.3.3.3'
            }],
            'id': 'ed928c2322422b2a8e419b00426fbcb0',
            'source': 'source_test1.channel_test1',
        }

        self.comparator._process_input(input_data_1_1_1)
        self.comparator._process_input(input_data_1_1_2)
        self.comparator._process_input(input_data_2_1_1)
        self.comparator._process_input(input_data_2_1_2)
        self.comparator._process_input(input_data_3_1_3)

        expected_calls_list = [
            call(body=expected_event_1_1_1, routing_key=routing_key_1_1_1),
            call(body=expected_event_1_1_2, routing_key=routing_key_1_1_2),
            call(body=expected_event_2_1_1, routing_key=routing_key_2_1_1),
            call(body=expected_event_2_1_2, routing_key=routing_key_2_1_2),
            call(body=expected_event_3_1_3, routing_key=routing_key_3_1_3),
            call(body=expected_event_3_1_1, routing_key=routing_key_3_1_1),
            call(body=expected_event_3_1_2, routing_key=routing_key_3_1_2),
        ]

        publish_output_call_args_list = self._get_deserialized_calls(self.comparator.publish_output.call_args_list)
        self.assertListEqual(publish_output_call_args_list, expected_calls_list)

    def test_message_flow_new_but_expired_msg(self):

        # _bl-time > expires -> bl-new, and bl-expires
        routing_key_1 = 'bl-new.compared.source_test1.channel_test1'
        routing_key_2 = 'bl-expire.compared.source_test1.channel_test1'

        input_data_1_1 = {
            '_bl-time': '2017-01-24 10:10:10',
            '_bl-series-no': 1,
            '_bl-series-total': 1,
            '_bl-series-id': '44444444444444444444444444444444',
            'expires': '2017-01-22 10:10:10',
            'time': '2017-01-20 10:10:10',
            'address': [{
                'cc': 'XX',
                'ip': '4.4.4.4'
            }],
            'id': 'ed928c2322422b2a8e419b00426fbcb0',
            'source': 'source_test1.channel_test1',
        }

        expected_event_1_1 = {
            'type': 'bl-new',
            'expires': '2017-01-22 10:10:10',
            'address': [{
                'cc': 'XX',
                'ip': '4.4.4.4'
            }],
            'id': 'ed928c2322422b2a8e419b00426fbcb0',
            '_bl-time': '2017-01-24 10:10:10',
            'source': 'source_test1.channel_test1',
            'time': '2017-01-20 10:10:10',
        }

        expected_event_1_2 = {
            'type': 'bl-expire',
            'expires': '2017-01-22 10:10:10',
            'address': [{
                'cc': 'XX',
                'ip': '4.4.4.4'
            }],
            'id': 'ed928c2322422b2a8e419b00426fbcb0',
            '_bl-time': '2017-01-24 10:10:10',
            'source': 'source_test1.channel_test1',
            'time': '2017-01-20 10:10:10',
        }

        expected_calls_list = [
            call(body=expected_event_1_1, routing_key=routing_key_1),
            call(body=expected_event_1_2, routing_key=routing_key_2),
        ]

        self.comparator._process_input(input_data_1_1)
        publish_output_call_args_list = self._get_deserialized_calls(self.comparator.publish_output.call_args_list)
        self.assertListEqual(publish_output_call_args_list, expected_calls_list)

    def test_message_flow_two_msgs_with_the_same_ip(self):

        routing_key = 'bl-new.compared.source_test1.channel_test1'

        input_data_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 1,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        }

        input_data_1_2 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '2222222d2339d9ab98f08761e7168ebd',
        }

        expected_event_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            'type': 'bl-new',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '111111111119d9ab98f08761e7168ebd',
            'source': 'source_test1.channel_test1',
        }

        expected_calls_list = [
            call(body=expected_event_1_1, routing_key=routing_key)
        ]

        self.comparator._process_input(input_data_1_1)
        self.comparator._process_input(input_data_1_2)

        publish_output_call_args_list = self._get_deserialized_calls(self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    def test_message_flow_msg_from_different_sources_with_the_same_ip(self):

        routing_key_1 = 'bl-new.compared.source_test1.channel_test1'
        routing_key_2 = 'bl-new.compared.source_test2.channel_test2'

        input_data_1_1 = {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 1,
            '_bl-series-no': 1,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
        }

        expected_event_1_1 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-19 12:07:32',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '9104c0ad2339d9ab98f08761e7168ebd',
            'source': 'source_test1.channel_test1',
        }

        input_data_2_1 = {
            '_bl-time': '2017-01-19 10:10:10',
            '_bl-series-total': 1,
            '_bl-series-no': 1,
            '_bl-series-id': '22222222222222222222222222222222',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test2.channel_test2',
            'id': '23f3b0f7fc3db9ab98f08761e7168ebd',
        }

        expected_event_2_1 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-19 10:10:10',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'id': '23f3b0f7fc3db9ab98f08761e7168ebd',
            'source': 'source_test2.channel_test2',
        }

        expected_calls_list = [
            call(body=expected_event_1_1, routing_key=routing_key_1),
            call(body=expected_event_2_1, routing_key=routing_key_2)
        ]

        self.comparator._process_input(input_data_1_1)
        self.comparator._process_input(input_data_2_1)

        publish_output_call_args_list = self._get_deserialized_calls(self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    def _get_deserialized_calls(self, calls_list):
        deserialized_call_list = []
        for call_ in calls_list:
            _, call_kwargs = call_
            new_body = json.loads(call_kwargs['body'])
            deserialized_call_list.append(call(body=new_body, routing_key=call_kwargs['routing_key']))
        return deserialized_call_list

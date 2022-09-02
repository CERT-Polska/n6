# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import json
import os
import tempfile
import unittest

from mock import (
    MagicMock,
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

from n6.utils.comparator import (
    BlackListData,
    Comparator,
    ComparatorData,
    ComparatorDataWrapper,
    ComparatorState,
    SourceData,
)
from n6lib.config import ConfigSection
from n6lib.unit_test_helpers import TestCaseMixin
from n6.base.queue import n6QueueProcessingException


@paramseq
def _is_message_valid_to_compare(cls):
    # Value of the '_bl-series-total' attribute of the second message does not match
    # the value of the 'total' attribute of the open series with the same ID
    yield param(
        input_data_1_1={
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
        },
        input_data_1_2={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 99,
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
        },
        expected_data=n6QueueProcessingException,
    )
    # Value of the '_bl-series-total' attribute of the second message does not match
    # the value of the 'total' attribute of the open series with the same ID.
    yield param(
        input_data_1_1={
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
        },
        input_data_1_2={
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
            'id': '2222222d2339d9ab98f08761e7168ebd',
        },
        expected_data=n6QueueProcessingException,
    )
    # Value of the 'total' attribute of the open series is 0, but there are two events
    yield param(
        input_data_1_1={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 0,
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
        },
        input_data_1_2={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 0,
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
        },
        expected_data=n6QueueProcessingException,
    )
    # The second incoming message has the '_bl-series-no' attribute's value
    # same as a message already registered in the series with the same ID
    yield param(
        input_data_1_1={
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
        },
        input_data_1_2={
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
            'id': '2222222d2339d9ab98f08761e7168ebd',
        },
        expected_data=n6QueueProcessingException,
    )


@paramseq
def _invalid_messages(cls):
    # '_bl-series-id' missing
    yield param(
        input_data={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 1,
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        },
        expected_output=n6QueueProcessingException,
    )
    # '_bl-series-total' missing
    yield param(
        input_data={
            '_bl-time': '2017-01-19 12:07:32',
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
        },
        expected_output=n6QueueProcessingException,
    )
    # '_bl-series-no' missing
    yield param(
        input_data={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 15:15:15',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        },
        expected_output=n6QueueProcessingException,
    )
    # '_bl-time' missing
    yield param(
        input_data={
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
        },
        expected_output=n6QueueProcessingException,
    )
    # 'expires' missing
    yield param(
        input_data={
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 1,
            '_bl-series-id': '11111111111111111111111111111111',
            'time': '2017-01-18 15:15:15',
            'address': [{
                'cc': 'XX',
                'ip': '1.1.1.1'
            }],
            'source': 'source_test1.channel_test1',
            'id': '111111111119d9ab98f08761e7168ebd',
        },
        expected_output=n6QueueProcessingException,
    )


@expand
class TestComparator(TestCaseMixin, unittest.TestCase):

    sample_dbpath = "/tmp/sample_dbfile"
    sample_series_timeout = 300
    sample_cleanup_time = 600
    mocked_config = {
        "comparator": {
            "dbpath": sample_dbpath,
            "series_timeout": str(sample_series_timeout),
            "cleanup_time": str(sample_cleanup_time),
        }
    }
    sample_routing_key = 'bl.enriched.malwaredomainlist.malurl'
    input_callback_proper_msg = {
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

    def setUp(self):
        self.comparator = Comparator.__new__(Comparator)
        self.comparator.comparator_config = MagicMock()
        self.comparator._connection = MagicMock()
        self.comparator.state = ComparatorState(sen.irrelevant)
        self.patch_object(ComparatorDataWrapper, 'store_state')
        self.comparator.db = ComparatorDataWrapper.__new__(ComparatorDataWrapper)
        self.comparator.db.comp_data = ComparatorData()
        self.comparator.publish_output = MagicMock()

    @patch('n6.base.queue.QueuedBase.__init__', return_value=None)
    @patch("n6lib.config.Config._load_n6_config_files", return_value=mocked_config)
    def test_init(self, mocked_config, mocked_queue_dbase_init):

        # config is created, store dir exist, store file exist
        with tempfile.NamedTemporaryFile(prefix='comparator_') as fp:
            mocked_config.return_value["comparator"]["dbpath"] = fp.name
            self.comparator.__init__()
            self.assertIsInstance(self.comparator.comparator_config, ConfigSection)
            self.assertEqual(self.comparator.comparator_config.sect_name, 'comparator')
            self.assertEqual(self.comparator.comparator_config['cleanup_time'], '600')
            self.assertEqual(self.comparator.comparator_config['series_timeout'], '300')
            self.assertRegexpMatches(
                self.comparator.comparator_config['dbpath'], '/tmp/comparator_.*')
            self.assertTrue(os.path.isdir(
                os.path.dirname(self.comparator.comparator_config['dbpath'])))
            self.assertTrue(os.path.isfile(self.comparator.comparator_config['dbpath']))

        # store dir does not exist
        with tempfile.NamedTemporaryFile() as fp, \
                self.assertRaisesRegexp(Exception, r"store dir does not exist, stop comparator"):
            mocked_config.return_value["comparator"]["dbpath"] = os.path.join(
                fp.name, "nonexistent_file")
            self.comparator.__init__()

        # store directory exists, but it has no rights to write
        with tempfile.NamedTemporaryFile() as fp, \
                patch("os.access", return_value=None), \
                self.assertRaisesRegexp(Exception,
                                        r"stop comparator, remember to set the rights for user, "
                                        r"which runs comparator"):
            mocked_config.return_value["comparator"]["dbpath"] = fp.name
            self.comparator.__init__()

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

        publish_output_call_args_list = self._get_deserialized_calls(
            self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    def test_out_of_order_message_flow_basic(self):
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

        input_data_1_2 = {
            '_bl-time': '2016-01-19 12:07:32',
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

        with self.assertRaisesRegexp(n6QueueProcessingException, r'Event belongs to blacklist'):
            self.comparator._process_input(input_data_1_1)
            self.comparator._process_input(input_data_1_2)

    def test_message_flow_basic__on_series_timeout(self):
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
            '_bl-time': '2017-01-19 12:07:33',
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
        self.comparator._process_input(input_data_1_1)
        self.comparator.on_series_timeout(
            input_data_1_1['source'], input_data_1_1['_bl-series-id'])
        # assert that the flag has been cleaned up
        self.assertFalse(self.comparator.state.open_series.keys())
        # assert that the series has been closed
        self.assertIsNone(self.comparator.db.comp_data.sources['source_test1.channel_test1']
                          .blacklist[('1.1.1.1',)].flag)
        self.comparator._process_input(input_data_1_2)
        self.comparator.db.store_state.assert_called_once_with()
        self.assertIn(input_data_1_1['_bl-series-id'] and input_data_1_2['_bl-series-id'],
                      self.comparator.state.open_series.keys())
        self.assertEqual(
            self.comparator.state.open_series['11111111111111111111111111111111']['total'], 2)
        self.assertEqual(self.comparator.db.comp_data.sources[
                            'source_test1.channel_test1'].blacklist[('1.1.1.1',)].flag,
                         input_data_1_1['_bl-series-id'])


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
            'url': 'http://www.example.info',
            'address': [{
                'cc': 'XX',
                'ip': '2.2.2.2',
                'asn': 1234,
            }],
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        }

        expected_event_1_1_2 = {
            'type': 'bl-new',
            '_bl-time': '2017-01-19 12:07:32',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'url': 'http://www.example.info',
            'address': [{
                'cc': 'XX',
                'ip': '2.2.2.2',
                'asn': 1234,
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
            'url': 'http://www.example.info',
            'address': [
                {
                    'cc': 'XX',
                    'ip': '2.2.2.2',
                    'asn': 1234,
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 1234,
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
            'url': 'http://www.example.info',
            'address': [
                {
                    'cc': 'XX',
                    'ip': '2.2.2.2',
                    'asn': 1234,
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 1234,
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
                    'asn': 1234,
                },
                {
                    'cc': 'XX',
                    'ip': '22.22.22.22',
                    'asn': 1234,
                }
            ],
            'id': '929c840e0dec26e26410aeeac418067d',
            '_bl-time': '2017-01-19 14:14:14',
            'replaces': '1c9a2638b51f334da3d2311e01817884',
            'url': 'http://www.example.info',
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

        publish_output_call_args_list = self._get_deserialized_calls(
            self.comparator.publish_output.call_args_list)
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
        publish_output_call_args_list = self._get_deserialized_calls(
            self.comparator.publish_output.call_args_list)
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

        publish_output_call_args_list = self._get_deserialized_calls(
            self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    @foreach(_is_message_valid_to_compare)
    def test_is_message_valid(self, input_data_1_1, input_data_1_2, expected_data):
        with self.assertRaisesRegexp(expected_data, r'Invalid message for a series'):
            self.comparator._process_input(input_data_1_1)
            self.comparator._process_input(input_data_1_2)

    @foreach(_invalid_messages)
    def test_validate_bl_headers(self, input_data, expected_output):
        with self.assertRaisesRegexp(expected_output, r'Invalid message for a black list'):
            self.comparator._process_input(input_data)

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

        publish_output_call_args_list = self._get_deserialized_calls(
            self.comparator.publish_output.call_args_list)
        self.assertEqual(publish_output_call_args_list, expected_calls_list)

    def test_input_callback(self):
        with patch.object(Comparator, '_process_input') as process_input_mock:
            self.comparator.input_callback(self.sample_routing_key,
                                           json.dumps(self.input_callback_proper_msg),
                                           properties=None)
            process_input_mock.assert_called_with(self.input_callback_proper_msg)

    def _get_deserialized_calls(self, calls_list):
        deserialized_call_list = []
        for call_ in calls_list:
            _, call_kwargs = call_
            new_body = json.loads(call_kwargs['body'])
            deserialized_call_list.append(
                call(body=new_body, routing_key=call_kwargs['routing_key']))
        return deserialized_call_list


@paramseq
def _event_valid_key_to_check(cls):
    # The 'url' key is the same as expected in `expected_data`
    yield param(
        input_data=
        {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'url': 'http://www.example.info',
            'address': [{
                'cc': ' XX',
                'ip': '2.2.2.2',
                'asn': 1234,
            }],
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        },
        expected_data='http://www.example.info',
        test_key='url',
    )
    # The 'fqdn' key is the same as expected in `expected_data`
    yield param(
        input_data=
        {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'fqdn': 'another.example.biz',
            'address': [{
                'cc': ' XX',
                'ip': '2.2.2.2',
                'asn': 1234,
            }],
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        },
        expected_data='another.example.biz',
        test_key='fqdn',
    )
    # The 'address' key is the same as expected in `expected_data`
    yield param(
        input_data=
        {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'address': [{
                'cc': ' XX',
                'ip': '2.2.2.1',
                'asn': 1234,
            }, {
                'cc': ' XX',
                'ip': '2.2.2.2',
                'asn': 1234,
            }, {
                'cc': ' XX',
                'ip': '2.2.2.3',
                'asn': 1234,
            }],
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        },
        expected_data=('2.2.2.1', '2.2.2.2', '2.2.2.3'),
        test_key='address',
    )


@paramseq
def _event_invalid_key_to_check(cls):
    # Unable to determine event key for all 'url', 'fqdn', 'address' required data
    yield param(
        input_data=
        {
            '_bl-time': '2017-01-19 12:07:32',
            '_bl-series-total': 2,
            '_bl-series-no': 2,
            '_bl-series-id': '11111111111111111111111111111111',
            'expires': '2017-01-20 19:19:19',
            'time': '2017-01-18 19:19:19',
            'url': None,
            'fqdn': None,
            'address': None,
            'source': 'source_test1.channel_test1',
            'id': '1c9a2638b51f334da3d2311e01817884',
        },
        expected_data=n6QueueProcessingException,
    )


@paramseq
def _ips_to_compare(cls):
    # Compare lists the same
    yield param(
        input_data_ips_old=None,
        expected_data_ips_new=None,
        expected_data=False,
    )
    # Compare lists the same
    yield param(
        input_data_ips_old=['2.2.2.2'],
        expected_data_ips_new=['2.2.2.2'],
        expected_data=False,
    )
    # Compare lists different
    yield param(
        input_data_ips_old=['1.1.1.1'],
        expected_data_ips_new=['2.2.2.2'],
        expected_data=True,
    )
    # Compare lists the same
    yield param(
        input_data_ips_old=['2.2.2.2', '1.1.1.1'],
        expected_data_ips_new=['1.1.1.1', '2.2.2.2'],
        expected_data=False,
    )
    # Compare lists different
    yield param(
        input_data_ips_old=None,
        expected_data_ips_new=['1.1.1.1', '2.2.2.2'],
        expected_data=True,
    )


@expand
class TestSourceData(unittest.TestCase):

    def setUp(self):
        self.source_data = SourceData()

    @foreach(_event_valid_key_to_check)
    def test_get_event_key(self, input_data, expected_data, test_key):
        process_data = self.source_data.get_event_key(input_data)
        self.assertEqual(process_data, expected_data)

    @foreach(_event_invalid_key_to_check)
    def test_get_event_negative_key(self, input_data, expected_data):
        with self.assertRaises(expected_data):
            self.source_data.get_event_key(input_data)

    @foreach(_ips_to_compare)
    def test_are_ips_different(self, input_data_ips_old, expected_data_ips_new, expected_data):
        process_data = self.source_data._are_ips_different(input_data_ips_old,
                                                           expected_data_ips_new)
        self.assertEqual(process_data, expected_data)


class TestComparatorDataWrapper(TestCaseMixin, unittest.TestCase):

    sample_db_path = '/tmp/example.pickle'
    message = {
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
    expected_stored_message = {
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

    def setUp(self):
        self._comparator_data_wrapper = ComparatorDataWrapper.__new__(ComparatorDataWrapper)
        self._comparator_data_wrapper.dbpath = self.sample_db_path
        self._comparator_data_wrapper.comp_data = ComparatorData()

    def test_store_restore_state(self):
        """
        Check validity of data stored in Pickle object and saved as temporary files
        comparing its restored state.
        """

        self._comparator_data_wrapper.process_new_message(self.message)
        self.stored_message = self._comparator_data_wrapper.comp_data
        with tempfile.NamedTemporaryFile() as fp:
            self._comparator_data_wrapper.dbpath = fp.name
            # store the state
            self._comparator_data_wrapper.store_state()
            # delete attribute with stored sources
            del self._comparator_data_wrapper.comp_data
            # check restored state from existing file
            self._comparator_data_wrapper.restore_state()
            self.assertDictEqual(
                self._comparator_data_wrapper.comp_data.sources[
                    'source_test1.channel_test1'].blacklist.get(('1.1.1.1',)).payload,
                self.expected_stored_message)
            # assert given path exist
            self.assertTrue(self._comparator_data_wrapper.dbpath)

        self.restored_message = self._comparator_data_wrapper.comp_data

        def compare_blacklist_objs(first, second, msg=None):
            self.assertEqual(first.__dict__, second.__dict__, msg)

        def compare_source_data_objs(first, second, msg=None):
            self.assertEqual(first.last_event, second.last_event, msg)
            self.assertEqual(first.time, second.time, msg)
            if len(first.blacklist) != len(second.blacklist):
                raise self.failureException(msg or '`blacklist` dicts of compared SourceData '
                                                   'objects have different number of items')
            for blacklist_name, blacklist_data in first.blacklist.items():
                self.assertEqual(blacklist_data, second.blacklist.get(blacklist_name), msg)

        def compare_comparator_data_objs(first, second, msg=None):
            if len(first.sources) != len(second.sources):
                raise self.failureException(msg or '`sources` dicts of compared ComparatorData '
                                                   'objects have different number of items')
            for source_name, source_data in first.sources.items():
                second_source_data = second.sources.get(source_name)
                self.assertEqual(source_data, second_source_data, msg)

        self.addTypeEqualityFunc(BlackListData, compare_blacklist_objs)
        self.addTypeEqualityFunc(SourceData, compare_source_data_objs)
        self.addTypeEqualityFunc(ComparatorData, compare_comparator_data_objs)

        self.assertEqual(self.stored_message, self.restored_message)

        # assert the exception is being raised when trying to store
        # the state, but there is no access to the given path; first,
        # make sure there actually is no access to the given path
        tmp_db_path = "/root/example.pickle"
        assert not os.access(tmp_db_path, os.W_OK), ('The test case relies on the assumption that '
                                                     'the user running the tests does not '
                                                     'have permission to write '
                                                     'to: {!r}'.format(tmp_db_path))
        self._comparator_data_wrapper.dbpath = tmp_db_path
        with patch('n6.utils.comparator.LOGGER') as patched_logger:
            self._comparator_data_wrapper.store_state()
            patched_logger.error.assert_called_once()
        # assert the exception is being raised when trying to restore
        # the state from nonexistent file; first, safely create
        # a temporary file, then close and remove it, so the path
        # most likely does not exist
        with tempfile.NamedTemporaryFile() as fp:
            tmp_db_path = fp.name
        assert not os.path.exists(tmp_db_path), ('The randomly generated temporary directory: '
                                                 '{!r} still exists, so the test cannot '
                                                 'be correctly performed'.format(tmp_db_path))
        with patch.object(self._comparator_data_wrapper, "dbpath", tmp_db_path), \
                self.assertRaisesRegexp(IOError, r"No such file or directory"):
            self._comparator_data_wrapper.restore_state()

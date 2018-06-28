# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import collections
import contextlib
import Queue
import time
import unittest

import pika.credentials
from mock import (
    ANY,
    Mock,
    call,
    sentinel as sen,
)

from n6lib.unit_test_helpers import (
    MethodProxy,
    RLockedMagicMock,
    rlocked_patch,
)
from n6lib.amqp_getters_pushers import AMQPThreadedPusher, DoNotPublish


class TestAMQPThreadedPusher__init__repr(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=AMQPThreadedPusher)
        self.mock.DEFAULT_PROP_KWARGS = AMQPThreadedPusher.DEFAULT_PROP_KWARGS
        self.meth = MethodProxy(AMQPThreadedPusher, self.mock)

    def test__init__using_defaults__no_ssl(self):
        connection_params_dict_mock = RLockedMagicMock()
        connection_params_dict_mock.get.return_value = False
        self.meth.__init__(connection_params_dict=connection_params_dict_mock,
                           exchange='my-exchange')
        # attrs
        self.assertIs(self.mock._connection_params_dict, connection_params_dict_mock)
        self.assertEqual(self.mock._exchange, {'exchange': 'my-exchange'})
        self.assertEqual(self.mock._exchange_name, 'my-exchange')
        self.assertEqual(self.mock._queues_to_declare, [])
        self.assertIsNone(self.mock._serialize)
        self.assertEqual(self.mock._prop_kwargs, AMQPThreadedPusher.DEFAULT_PROP_KWARGS)
        self.assertEqual(self.mock._mandatory, False)
        self.assertIs(self.mock._output_fifo.__class__, Queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, 20000)
        self.assertIsNone(self.mock._error_callback)
        # calls
        self.assertEqual(self.mock.mock_calls, [
            call._setup_communication(),
            call._start_publishing(),
        ])
        self.assertEqual(connection_params_dict_mock.mock_calls, [
            call.get('ssl'),
        ])

    def test__init__specifying_all__with_ssl(self):
        connection_params_dict_mock = RLockedMagicMock()
        connection_params_dict_mock.get.return_value = True
        self.meth.__init__(connection_params_dict=connection_params_dict_mock,
                           exchange={'exchange': sen.exchange, 'foo': sen.foo},
                           queues_to_declare=sen.queues_to_declare,
                           serialize=sen.serialize,
                           prop_kwargs=sen.prop_kwargs,
                           mandatory=sen.mandatory,
                           output_fifo_max_size=12345,
                           error_callback=sen.error_callback)
        # attrs
        self.assertIs(self.mock._connection_params_dict, connection_params_dict_mock)
        self.assertEqual(self.mock._exchange, {'exchange': sen.exchange, 'foo': sen.foo})
        self.assertEqual(self.mock._exchange_name, sen.exchange)
        self.assertEqual(self.mock._queues_to_declare, [
            {'queue': sen.queues_to_declare, 'callback': ANY},
        ])
        self.assertEqual(self.mock._serialize, sen.serialize)
        self.assertEqual(self.mock._prop_kwargs, sen.prop_kwargs)
        self.assertEqual(self.mock._mandatory, sen.mandatory)
        self.assertIs(self.mock._output_fifo.__class__, Queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, 12345)
        self.assertEqual(self.mock._error_callback, sen.error_callback)
        # calls
        self.assertEqual(self.mock.mock_calls, [
            call._setup_communication(),
            call._start_publishing(),
        ])
        self.assertEqual(connection_params_dict_mock.mock_calls, [
            call.get('ssl'),
            call.setdefault('credentials', ANY),
        ])
        self.assertIsInstance(
            connection_params_dict_mock.setdefault.mock_calls[0][-2][1],  # 2nd arg for setdefault
            pika.credentials.ExternalCredentials)

    def test__init__specifying_all_and_obtaining_global_conn_params__with_ssl(self):
        connection_params_dict_mock = RLockedMagicMock()
        connection_params_dict_mock.get.return_value = True
        with rlocked_patch('n6lib.amqp_getters_pushers.get_amqp_connection_params_dict', **{
                'return_value': connection_params_dict_mock}
        ) as get_amqp_conn_params_mock:
            self.meth.__init__(connection_params_dict=None,
                               exchange={'exchange': sen.exchange, 'bar': sen.bar},
                               queues_to_declare=[
                                   sen.queue1,
                                   {'blabla': sen.blabla},
                                   {'blabla': sen.blabla, 'callback': sen.callback},
                               ],
                               serialize=sen.serialize,
                               prop_kwargs=sen.prop_kwargs,
                               mandatory=sen.mandatory,
                               output_fifo_max_size=54321,
                               error_callback=sen.error_callback)
        # attrs
        self.assertIs(self.mock._connection_params_dict, connection_params_dict_mock)
        self.assertEqual(self.mock._exchange, {'exchange': sen.exchange, 'bar': sen.bar})
        self.assertEqual(self.mock._exchange_name, sen.exchange)
        self.assertEqual(self.mock._queues_to_declare, [
            {'queue': sen.queue1, 'callback': ANY},
            {'blabla': sen.blabla, 'callback': ANY},
            {'blabla': sen.blabla, 'callback': sen.callback},
        ])
        self.assertEqual(self.mock._serialize, sen.serialize)
        self.assertEqual(self.mock._prop_kwargs, sen.prop_kwargs)
        self.assertEqual(self.mock._mandatory, sen.mandatory)
        self.assertIs(self.mock._output_fifo.__class__, Queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, 54321)
        self.assertEqual(self.mock._error_callback, sen.error_callback)
        # calls
        self.assertEqual(self.mock.mock_calls, [
            call._setup_communication(),
            call._start_publishing(),
        ])
        self.assertEqual(get_amqp_conn_params_mock.mock_calls, [
            call(),
        ])
        self.assertEqual(connection_params_dict_mock.mock_calls, [
            call.get('ssl'),
            call.setdefault('credentials', ANY),
        ])
        self.assertIsInstance(
            connection_params_dict_mock.setdefault.mock_calls[0][-2][1],  # 2nd arg for setdefault
            pika.credentials.ExternalCredentials)

    def test__repr(self):
        string_repr = self.meth.__repr__()
        self.assertIs(type(string_repr), str)
        self.assertRegexpMatches(string_repr,
                                 r'<AMQPThreadedPusher object at 0x[0-9a-f]+ with .*>')


class TestAMQPThreadedPusher_as_context_manager(unittest.TestCase):

    def test(self):
        obj = AMQPThreadedPusher.__new__(AMQPThreadedPusher)
        with rlocked_patch.object(AMQPThreadedPusher, 'shutdown') as shutdown_mock:
            with obj:
                self.assertEqual(shutdown_mock.mock_calls, [])
            self.assertEqual(shutdown_mock.mock_calls, [call()])


class TestAMQPThreadedPusher_internal_cooperation(unittest.TestCase):

    def setUp(self):
        # patching some global objects and preparing mockups of them
        self._stderr_patcher = rlocked_patch('sys.stderr')
        self.stderr_mock = self._stderr_patcher.start()
        self.addCleanup(self._stderr_patcher.stop)

        # patching some imported modules and preparing mockups of them
        self._time_patcher = rlocked_patch('n6lib.amqp_getters_pushers.time')
        self.time_mock = self._time_patcher.start()
        self.addCleanup(self._time_patcher.stop)

        self._traceback_patcher = rlocked_patch('n6lib.amqp_getters_pushers.traceback')
        self.traceback_mock = self._traceback_patcher.start()
        self.addCleanup(self._traceback_patcher.stop)

        self._pika_patcher = rlocked_patch('n6lib.amqp_getters_pushers.pika')
        self.pika_mock = self._pika_patcher.start()
        self.addCleanup(self._pika_patcher.stop)

        # preparing sentinel exceptions
        class AMQPConnectionError_sentinel_exc(Exception): pass
        class ConnectionClosed_sentinel_exc(Exception): pass
        class generic_sentinel_exc(Exception): pass

        self.AMQPConnectionError_sentinel_exc = AMQPConnectionError_sentinel_exc
        self.ConnectionClosed_sentinel_exc = ConnectionClosed_sentinel_exc
        self.generic_sentinel_exc = generic_sentinel_exc

        # preparing mockups of different objects
        self.conn_mock = RLockedMagicMock()
        self.channel_mock = RLockedMagicMock()
        self.optional_setup_communication_mock = RLockedMagicMock()
        self.serialize = RLockedMagicMock()
        self.error_callback = RLockedMagicMock()

        # configuring the mockups
        self.pika_mock.exceptions.AMQPConnectionError = AMQPConnectionError_sentinel_exc
        self.pika_mock.exceptions.ConnectionClosed = ConnectionClosed_sentinel_exc
        self.pika_mock.ConnectionParameters.return_value = sen.conn_parameters
        self.pika_mock.BlockingConnection.side_effect = [
            AMQPConnectionError_sentinel_exc,
            self.conn_mock,
        ]
        self.pika_mock.BasicProperties.return_value = sen.props
        self.conn_mock.channel.return_value = self.channel_mock
        self.serialize.side_effect = (lambda data: data)

    #
    # Fixture helpers and reusable assertions

    def _reset_mocks(self):
        self.pika_mock.reset_mock()
        self.time_mock.reset_mock()
        self.traceback_mock.reset_mock()
        self.stderr_mock.reset_mock()
        self.conn_mock.reset_mock()
        self.channel_mock.reset_mock()
        self.optional_setup_communication_mock.reset_mock()
        if self.serialize is not None:
            self.serialize.reset_mock()
        if self.error_callback is not None:
            self.error_callback.reset_mock()


    def _make_obj(self, **kw):
        # create and initialize a usable AMQPThreadedPusher instance
        self.obj = AMQPThreadedPusher(connection_params_dict={'conn_param': sen.param_value},
                                      exchange={'exchange': sen.exchange},
                                      queues_to_declare=[
                                          sen.queue1,
                                          {'blabla': sen.blabla},
                                          {'blabla': sen.blabla, 'callback': sen.callback},
                                      ],
                                      serialize=self.serialize,
                                      prop_kwargs={'prop_kwarg': sen.prop_value},
                                      mandatory=sen.mandatory,
                                      output_fifo_max_size=3,
                                      error_callback=self.error_callback,
                                      **kw)


    def _side_effect_for_publish(self, exception_seq):
        orig_publish = AMQPThreadedPusher._publish
        exceptions = iter(exception_seq)

        def _side_effect(data, routing_key, custom_prop_kwargs):
            exc = next(exceptions)
            if exc is None:
                return orig_publish(self.obj, data, routing_key, custom_prop_kwargs)
            else:
                raise exc

        return _side_effect


    def _mock_setup_communication(self):
        self.obj._setup_communication = self.optional_setup_communication_mock


    def _assert_setup_done(self):
        self.assertEqual(self.pika_mock.mock_calls, [
            call.ConnectionParameters(conn_param=sen.param_value),
            call.BlockingConnection(sen.conn_parameters),
            # repeated after pika.exceptions.AMQPConnectionError:
            call.ConnectionParameters(conn_param=sen.param_value),
            call.BlockingConnection(sen.conn_parameters),
        ])
        self.assertEqual(self.time_mock.sleep.mock_calls, [
            # after pika.exceptions.AMQPConnectionError
            call(0.5),  # 0.5 == CONNECTION_RETRY_DELAY
        ])
        self.assertIs(self.obj._connection, self.conn_mock)
        self.assertIs(self.obj._channel, self.channel_mock)
        self.assertEqual(self.channel_mock.mock_calls, [
            call.exchange_declare(exchange=sen.exchange),
            call.queue_declare(queue=sen.queue1, callback=ANY),
            call.queue_declare(blabla=sen.blabla, callback=ANY),
            call.queue_declare(blabla=sen.blabla, callback=sen.callback),
        ])
        # some additional marginal asserts:
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)
        self.assertFalse(self.obj._connection_closed)


    def _assert_publishing_started(self):
        self.assertTrue(self.obj._publishing)
        self.assertTrue(self.obj._publishing_thread.is_alive())


    def _assert_shut_down(self):
        self.assertEqual(self.conn_mock.close.mock_calls, [call()])
        self.assertFalse(self.obj._publishing_thread.is_alive())
        self.assertFalse(self.obj._publishing)
        self.assertTrue(self.obj._connection_closed)


    def _assert_no_remaining_data(self):
        self.assertIn(self.obj._output_fifo.queue, [
            collections.deque(),
            collections.deque([None]),
        ])


    @contextlib.contextmanager
    def _testing_normal_push(self, error_callback_call_count=0):
        self._make_obj()
        try:
            self._assert_setup_done()
            self._assert_publishing_started()

            yield self.obj

            while self.channel_mock.basic_publish.call_count < 2:
                time.sleep(0.01)
        finally:
            self.obj.shutdown()

        # properties of both published messages have been created properly
        # (using also custom prop kwargs if given)
        self.assertEqual(self.pika_mock.BasicProperties.mock_calls, [
            call(prop_kwarg=sen.prop_value),
            call(prop_kwarg=sen.prop_value, custom=sen.custom_value),
        ])

        # both messages have been published properly
        self.assertEqual(self.channel_mock.basic_publish.mock_calls, [
            call(
                exchange=sen.exchange,
                routing_key=sen.rk1,
                body=sen.data1,
                properties=sen.props,
                mandatory=sen.mandatory,
            ),
            call(
                exchange=sen.exchange,
                routing_key=sen.rk2,
                body=sen.data2,
                properties=sen.props,
                mandatory=sen.mandatory,
            ),
        ])

        self.assertEqual(self.error_callback.call_count,
                         error_callback_call_count)
        self._assert_shut_down()
        self._assert_no_remaining_data()

        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)

        # cannot push (as the pusher has been shut down)
        with self.assertRaises(ValueError):
            self.obj.push(sen.data3, sen.rk3)


    def _error_test_commons(self, subcall_mock, expected_subcall_count):
        self._make_obj()
        try:
            self._assert_setup_done()
            self._assert_publishing_started()

            self._reset_mocks()
            self._mock_setup_communication()

            self.obj.push(sen.data, sen.rk)

            # we must delay shutdown() to let the pub. thread operate
            while subcall_mock.call_count < expected_subcall_count:
                time.sleep(0.01)
        finally:
            self.obj.shutdown()

        self.assertEqual(self.serialize.mock_calls, [call(sen.data)])

        self._assert_shut_down()
        self._assert_no_remaining_data()

    #
    # Actual tests

    def test_normal_operation_without_serialize(self):
        self.serialize = None
        with self._testing_normal_push() as obj:
            obj.push(sen.data1, sen.rk1)
            obj.push(sen.data2, sen.rk2, {'custom': sen.custom_value})


    def test_normal_operation_with_serialize(self):
        self.serialize.side_effect = [
            sen.data1,
            DoNotPublish,
            sen.data2,
        ]
        with self._testing_normal_push() as obj:
            # published normally
            obj.push(sen.raw1, sen.rk1)

            # serialize() returns DoNotPublish for this one (see above)
            # so the data will not be published
            obj.push(sen.no_pub_data, sen.no_pub_rk)

            # published normally
            obj.push(sen.raw2, sen.rk2, {'custom': sen.custom_value})

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.raw1),
            call(sen.no_pub_data),
            call(sen.raw2),
        ])


    def test_publishing_flag_is_False(self):
        # do not try to reconnect on pika.exceptions.ConnectionClosed
        # but continue publishing until the output fifo is empty
        def basic_publish_side_effect(*args, **kwargs):
            time.sleep(0.02)

        self.channel_mock.basic_publish.side_effect = basic_publish_side_effect
        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
            side_effect=self._side_effect_for_publish(exception_seq=[
                None,
                self.ConnectionClosed_sentinel_exc,
                None,
            ]),
        ) as _publish_mock:
            with self._testing_normal_push(error_callback_call_count=1) as obj:
                obj._publishing = False
                obj._output_fifo.put_nowait((sen.data1, sen.rk1, None))
                obj._output_fifo.put_nowait((sen.data_err, sen.rk_err, None))
                obj._output_fifo.put_nowait((sen.data2, sen.rk2, {'custom': sen.custom_value}))

        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data1, sen.rk1, None),
            call(sen.data_err, sen.rk_err, None),
            call(sen.data2, sen.rk2, {'custom': sen.custom_value}),
        ])

        # no reconnections
        self.assertFalse(self.optional_setup_communication_mock.mock_calls)

        # one error callback call
        self.assertEqual(self.error_callback.mock_calls, [call(ANY)])


    def test_permanent_AMQPConnectionError(self):
        self.pika_mock.BlockingConnection.side_effect = self.AMQPConnectionError_sentinel_exc

        with self.assertRaises(self.AMQPConnectionError_sentinel_exc):
            self._make_obj()

        self.assertEqual(
            self.pika_mock.mock_calls,
            # 10 calls because CONNECTION_ATTEMPTS == 10)
            10 * [
                call.ConnectionParameters(conn_param=sen.param_value),
                call.BlockingConnection(sen.conn_parameters),
            ]
        )
        self.assertEqual(
            self.time_mock.sleep.mock_calls,
            # (call(0.5) because CONNECTION_RETRY_DELAY == 0.5;
            # 10 calls because CONNECTION_ATTEMPTS == 10)
            10 * [call(0.5)],
        )
        self.assertEqual(self.channel_mock.basic_publish.call_count, 0)
        self.assertEqual(self.error_callback.call_count, 0)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)


    def test_publishing_with_one_ConnectionClosed(self):
        exceptions_from_publish = [
            self.ConnectionClosed_sentinel_exc,
            None,
        ]
        expected_publish_call_count = 2

        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
            side_effect=self._side_effect_for_publish(exceptions_from_publish)
        ) as _publish_mock:
            self._error_test_commons(_publish_mock, expected_publish_call_count)

        self.assertEqual(self.optional_setup_communication_mock.mock_calls, [call()])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
            call(sen.data, sen.rk, None),
        ])
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)

        # properties of the published message have been created properly...
        self.assertEqual(self.pika_mock.BasicProperties.mock_calls, [
            call(prop_kwarg=sen.prop_value),
        ])
        # ...and the message has been published properly
        self.assertEqual(self.channel_mock.basic_publish.mock_calls, [
            call(
                exchange=sen.exchange,
                routing_key=sen.rk,
                body=sen.data,
                properties=sen.props,
                mandatory=sen.mandatory,
            ),
        ])


    def test_publishing_with_exceptions_and_error_callback(self):
        exceptions_from_publish = [
            self.ConnectionClosed_sentinel_exc,
            TypeError,
        ]
        expected_publish_call_count = 2

        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
            side_effect=self._side_effect_for_publish(exceptions_from_publish)
        ) as _publish_mock:
            self._error_test_commons(_publish_mock, expected_publish_call_count)

        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
            call(sen.data, sen.rk, None),
        ])
        self.assertEqual(self.optional_setup_communication_mock.mock_calls, [call()])
        self.assertEqual(self.error_callback.mock_calls, [call(ANY)])
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)

        # the message has not been published
        self.assertFalse(self.pika_mock.BasicProperties.mock_calls)
        self.assertFalse(self.channel_mock.basic_publish.mock_calls)


    def test_publishing_with_exceptions_and_no_error_callback(self):
        self.error_callback = None

        exceptions_from_publish = [
            self.ConnectionClosed_sentinel_exc,
            TypeError,
        ]
        expected_publish_call_count = 2

        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
            side_effect=self._side_effect_for_publish(exceptions_from_publish)
        ) as _publish_mock:
            self._error_test_commons(_publish_mock, expected_publish_call_count)

        assert self.error_callback is None, "bug in test case"

        self.assertIsNone(self.obj._error_callback)
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
            call(sen.data, sen.rk, None),
        ])
        self.assertEqual(self.optional_setup_communication_mock.mock_calls, [call()])
        self.assertEqual(self.traceback_mock.print_exc.mock_calls, [call()])

        # the message has not been published
        self.assertFalse(self.pika_mock.BasicProperties.mock_calls)
        self.assertFalse(self.channel_mock.basic_publish.mock_calls)


    def test_publishing_with_error_callback_raising_exception(self):
        self.error_callback.side_effect = TypeError

        exceptions_from_publish = [
            self.ConnectionClosed_sentinel_exc,
            TypeError,
        ]
        expected_publish_call_count = 2

        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
            side_effect=self._side_effect_for_publish(exceptions_from_publish)
        ) as _publish_mock:
            self._error_test_commons(_publish_mock, expected_publish_call_count)

        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
            call(sen.data, sen.rk, None),
        ])
        self.assertEqual(self.optional_setup_communication_mock.mock_calls, [call()])
        self.assertEqual(self.error_callback.mock_calls, [call(ANY)])
        self.assertEqual(self.traceback_mock.print_exc.mock_calls, [call()])
        self.assertTrue(self.stderr_mock.mock_calls)  # print >>sys.stderr used...

        # the message has not been published
        self.assertFalse(self.pika_mock.BasicProperties.mock_calls)
        self.assertFalse(self.channel_mock.basic_publish.mock_calls)


    def test_serialization_error(self):
        self.serialize.side_effect = TypeError
        expected_serialize_call_count = 1
        with rlocked_patch(
            'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish'
        ) as _publish_mock:
            self._error_test_commons(self.serialize, expected_serialize_call_count)

        self.assertEqual(self.serialize.mock_calls, [call(sen.data)])
        self.assertEqual(self.error_callback.mock_calls, [call(ANY)])
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.stderr_mock.mock_calls)
        self.assertFalse(self.optional_setup_communication_mock.mock_calls)

        # the message has not been published
        self.assertFalse(_publish_mock.mock_calls)
        self.assertFalse(self.pika_mock.BasicProperties.mock_calls)
        self.assertFalse(self.channel_mock.basic_publish.mock_calls)


    def test_publishing_with_fatal_error(self):
        with rlocked_patch(
                'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
                # not an Exception subclass:
                side_effect=BaseException,
        ) as _publish_mock:
            self._make_obj()
            try:
                self.obj.push(sen.data, sen.rk)

                # we must wait to let the pub. thread operate and crash
                while _publish_mock.call_count < 1:
                    time.sleep(0.01)
                self.obj._publishing_thread.join(15.0)

                self.assertFalse(self.obj._publishing_thread.is_alive())
                self.assertFalse(self.obj._publishing)

                self.assertTrue(self.stderr_mock.mock_calls)
            finally:
                self.obj._publishing_thread.join(15.0)
                if self.obj._publishing_thread.is_alive():
                    raise RuntimeError('unexpected problem: the publishing '
                                       'thread did not terminate :-/')

        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)


    def test_publishing_with_fatal_error_and_remaining_data_in_fifo(self):
        def serialize_side_effect(data):
            self.obj._output_fifo.put(sen.item)
            return data
        self.serialize.side_effect = serialize_side_effect

        self.test_publishing_with_fatal_error()

        assert (hasattr(self.obj._output_fifo, 'queue') and
                isinstance(self.obj._output_fifo.queue,
                           collections.deque)), "test case's assumption is invalid"
        underlying_deque = self.obj._output_fifo.queue
        self.assertEqual(underlying_deque, collections.deque([sen.item]))
        with self.assertRaisesRegexp(
                ValueError,
                'pending messages'):
            self.obj.shutdown()
        self.assertEqual(underlying_deque, collections.deque([sen.item]))


    def test_shutting_down_with_timeouted_join_to_publishing_thread(self):
        self._make_obj(publishing_thread_join_timeout=0.2)
        try:
            self._assert_setup_done()
            self._assert_publishing_started()

            output_fifo_put_nowait_orig = self.obj._output_fifo.put_nowait
            output_fifo_put_nowait_mock = Mock()

            # we must wait to let the pub. thread set the heartbeat flag
            # to True (and then that thread will hang on the fifo)
            while not self.obj._publishing_thread_heartbeat_flag:
                time.sleep(0.01)
        except:
            # (to make the pub. thread terminate on any error)
            self.obj.shutdown()
            raise

        try:
            # monkey-patching output_fifo.put_nowait() so that
            # shutdown() will *not* wake-up the pub. thread
            self.obj._output_fifo.put_nowait = output_fifo_put_nowait_mock

            with self.assertRaisesRegexp(
                    RuntimeError,
                    'pushing thread seems to be still alive'):
                self.obj.shutdown()

            # shutdown() returned because the join timeout expired and
            # heartbeat flag was not re-set to True by the pub. thread
            self.assertFalse(self.obj._publishing_thread_heartbeat_flag)

            # the pusher is shut down...
            self.assertEqual(self.conn_mock.close.mock_calls, [call()])
            self.assertFalse(self.obj._publishing)
            self.assertTrue(self.obj._connection_closed)

            # ...but the pub. thread is still alive
            self.assertTrue(self.obj._publishing_thread.is_alive())
        finally:
            # (to always make the pub. thread terminate finally)
            self.obj._publishing = False
            output_fifo_put_nowait_orig(None)

            # now the pub. thread should terminate shortly or be already terminated
            self.obj._publishing_thread.join(15.0)
            if self.obj._publishing_thread.is_alive():
                raise RuntimeError('unexpected problem: the publishing '
                                   'thread did not terminate :-/')

        self.assertEqual(output_fifo_put_nowait_mock.mock_calls, [call(None)])

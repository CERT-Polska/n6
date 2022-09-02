# Copyright (c) 2013-2022 NASK. All rights reserved.

import collections
import contextlib
import re
import queue
import threading
import time
import unittest
from collections.abc import Iterable
from unittest.mock import (
    ANY,
    Mock,
    call,
    patch as nonlocked_patch,
    seal,
    sentinel as sen,
)

import pika.credentials
import pytest
from unittest_expander import (
    expand,
    foreach,
)

from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    MethodProxy,
    RLockedMagicMock,
    rlocked_patch,
)
from n6lib.amqp_getters_pushers import (
    AMQPThreadedPusher,
    BaseAMQPTool,
    DoNotPublish,
)


CONNECTION_ATTEMPTS = 10
CONNECTION_RETRY_DELAY = 0.5

assert CONNECTION_ATTEMPTS \
       == BaseAMQPTool.CONNECTION_ATTEMPTS \
       == AMQPThreadedPusher.CONNECTION_ATTEMPTS

assert CONNECTION_RETRY_DELAY \
       == BaseAMQPTool.CONNECTION_RETRY_DELAY \
       == AMQPThreadedPusher.CONNECTION_RETRY_DELAY


OUTPUT_FIFO_MAX_SIZE = 20000
PUBLISHING_THREAD_START_TIMEOUT = 5
PUBLISHING_THREAD_JOIN_TIMEOUT = 15

assert OUTPUT_FIFO_MAX_SIZE == AMQPThreadedPusher._OUTPUT_FIFO_MAX_SIZE
assert PUBLISHING_THREAD_START_TIMEOUT == AMQPThreadedPusher._PUBLISHING_THREAD_START_TIMEOUT
assert PUBLISHING_THREAD_JOIN_TIMEOUT == AMQPThreadedPusher._PUBLISHING_THREAD_JOIN_TIMEOUT


class TestAMQPThreadedPusher_init(unittest.TestCase):

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
        self.assertIs(self.mock._output_fifo.__class__, queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, OUTPUT_FIFO_MAX_SIZE)
        self.assertIsNone(self.mock._error_callback)
        self.assertEqual(self.mock._publishing_thread_join_timeout, PUBLISHING_THREAD_JOIN_TIMEOUT)
        # calls
        self.assertEqual(self.mock.mock_calls, [
            call._setup_communication(),
            call._start_publishing(),
        ])
        self.assertEqual(connection_params_dict_mock.mock_calls, [
            call.get('ssl'),
            ('__contains__', ('client_properties',), {}),  # because cannot use `call.__contains__`
            call.__setitem__('client_properties', ANY),
        ])
        self.assertIsInstance(
            # 2nd argument passed to __setitem__()
            connection_params_dict_mock.__setitem__.mock_calls[0][-2][1],
            dict)

    def test__init__specifying_all__with_ssl(self):
        connection_params_dict_mock = RLockedMagicMock()
        connection_params_dict_mock.get.return_value = True
        connection_params_dict_mock.__contains__.return_value = True
        self.meth.__init__(connection_params_dict=connection_params_dict_mock,
                           exchange={'exchange': sen.exchange, 'foo': sen.foo},
                           queues_to_declare=sen.queues_to_declare,
                           serialize=sen.serialize,
                           prop_kwargs=sen.prop_kwargs,
                           mandatory=sen.mandatory,
                           output_fifo_max_size=12345,
                           error_callback=sen.error_callback,
                           publishing_thread_join_timeout=42)
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
        self.assertIs(self.mock._output_fifo.__class__, queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, 12345)
        self.assertEqual(self.mock._error_callback, sen.error_callback)
        self.assertEqual(self.mock._publishing_thread_join_timeout, 42)
        # calls
        self.assertEqual(self.mock.mock_calls, [
            call._setup_communication(),
            call._start_publishing(),
        ])
        self.assertEqual(connection_params_dict_mock.mock_calls, [
            call.get('ssl'),
            call.setdefault('credentials', AnyInstanceOf(pika.credentials.ExternalCredentials)),
            ('__contains__', ('client_properties',), {}),  # because cannot use `call.__contains__`
        ])
        self.assertIsInstance(
            # 2nd argument passed to setdefault()
            connection_params_dict_mock.setdefault.mock_calls[0][-2][1],
            pika.credentials.ExternalCredentials)

    def test__init__specifying_all_and_obtaining_global_conn_params__with_ssl(self):
        connection_params_dict_mock = RLockedMagicMock(name='connection_params_dict')
        connection_params_dict_mock.get.return_value = True
        connection_params_dict_mock.__contains__.return_value = True
        with rlocked_patch(
                'n6lib.amqp_getters_pushers.get_amqp_connection_params_dict',
                return_value=connection_params_dict_mock) as get_amqp_conn_params_mock:
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
                               error_callback=sen.error_callback,
                               publishing_thread_join_timeout=23)
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
        self.assertIs(self.mock._output_fifo.__class__, queue.Queue)
        self.assertEqual(self.mock._output_fifo.maxsize, 54321)
        self.assertEqual(self.mock._error_callback, sen.error_callback)
        self.assertEqual(self.mock._publishing_thread_join_timeout, 23)
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
            call.setdefault('credentials', AnyInstanceOf(pika.credentials.ExternalCredentials)),
            ('__contains__', ('client_properties',), {}),  # because cannot use `call.__contains__`
        ])
        self.assertIsInstance(
            connection_params_dict_mock.setdefault.mock_calls[0][-2][1],  # 2nd arg for setdefault
            pika.credentials.ExternalCredentials)


@expand
class TestAMQPThreadedPusher_str_repr_format(unittest.TestCase):

    class _InsecureCredentials:
        _BADLY_PROTECTED_SECRET = 'Super Secret Data'
        __repr__ = __str__ = lambda self: self._BADLY_PROTECTED_SECRET

    @foreach(
        str,
        repr,
        format,
    )
    def test(self, string_repr_func):
        obj = AMQPThreadedPusher.__new__(AMQPThreadedPusher)
        obj._connection_params_dict = {
            'param1': 42,
            'credentials': self._InsecureCredentials(),
            b'not-a-str': 42,
            'param2': b'123',
        }

        string_repr = string_repr_func(obj)

        self.assertIs(type(string_repr), str)
        self.assertNotIn(self._InsecureCredentials._BADLY_PROTECTED_SECRET, string_repr)
        self.assertRegex(string_repr, (
            r"<"
            r"AMQPThreadedPusher object at 0x[0-9a-f]+ "
            r"with "
            # for an ordinary param, use its real repr:
            r"param1=42, "
            # for the 'credentials' param, reveal only `__qualname__` of its type:
            r"credentials=<TestAMQPThreadedPusher_[a-z_]+\._InsecureCredentials object\.\.\.>, "
            # for a non-str-key param (unexpected), replace the whole item with `<...>`:
            r"<...>, "
            # for an ordinary param, use its real repr:
            r"param2=b'123'"
            r">"))


class TestAMQPThreadedPusher_as_context_manager(unittest.TestCase):

    def test(self):
        obj = AMQPThreadedPusher.__new__(AMQPThreadedPusher)
        with rlocked_patch.object(AMQPThreadedPusher, 'shutdown') as shutdown_mock:
            with obj:
                self.assertEqual(shutdown_mock.mock_calls, [])
            self.assertEqual(shutdown_mock.mock_calls, [call()])


@expand
class TestAMQPThreadedPusher_internal_cooperation(unittest.TestCase):

    _CONN_PARAM_CLIENT_PROP_INFORMATION = AnyMatchingRegex(re.compile(
        r'\A'
        r'Host: [^,]+, '
        r'PID: [0-9]+, '
        r'script: [^,]+, '
        r'args: \[.*\], '
        r'modified: (?:'
            r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}Z'
            r'|'
            r'UNKNOWN'
        r')'
        r'\Z',
        re.ASCII))

    # to be used for testing-specific wait operations that normally are
    # supposed to end (almost) immediately; the goal is to prevent
    # endless waiting if something goes wrong
    _SAFE_WAIT_TIMEOUT = 12

    # a sentinel used with the _patched_publish() test helper method
    _INVOKE_ORIGINAL_PUBLISH = object()

    # sentinel exceptions
    class AMQPConnectionError_sentinel_exc(Exception): pass
    class ConnectionClosed_sentinel_exc(Exception): pass
    class generic_sentinel_exc(Exception): pass
    class another_generic_sentinel_exc(Exception): pass


    def setUp(self):
        # patching imported modules/objects with mocks (being instances of RLockedMagicMock)
        self.pika_mock = self._rlocked_patch('n6lib.amqp_getters_pushers.pika')
        self.time_mock = self._rlocked_patch('n6lib.amqp_getters_pushers.time')
        self.traceback_mock = self._rlocked_patch('n6lib.amqp_getters_pushers.traceback')
        self.dump_condensed_debug_msg_mock = self._rlocked_patch(
            'n6lib.amqp_getters_pushers.dump_condensed_debug_msg')

        # patching pusher methods with transparent wrappers (being instances of RLockedMagicMock)
        self.setup_communication_meth_wrapping_mock = \
                self._rlocked_patch_wrapping_pusher_method('_setup_communication')
        self.start_publishing_meth_wrapping_mock = \
                self._rlocked_patch_wrapping_pusher_method('_start_publishing')

        # preparing other mocks
        self.pika_BasicProperties_mock = RLockedMagicMock(name='pika.BasicProperties')
        self.connection_mock = RLockedMagicMock(name='obj._connection')
        self.channel_mock = RLockedMagicMock(name='obj._channel')
        self.serialize = RLockedMagicMock()
        self.error_callback = RLockedMagicMock()

        # configuring the mocks
        self.pika_mock.exceptions.AMQPConnectionError = self.AMQPConnectionError_sentinel_exc
        self.pika_mock.exceptions.ConnectionClosed = self.ConnectionClosed_sentinel_exc
        self.pika_mock.ConnectionParameters.return_value = sen.conn_parameters
        self.pika_mock.BlockingConnection.return_value = self.connection_mock  # (mock is detached)
        self.pika_mock.BasicProperties = self.pika_BasicProperties_mock        # (mock is detached)
        self.pika_BasicProperties_mock.return_value = sen.props
        self.connection_mock.channel.return_value = self.channel_mock          # (mock is detached)
        self.serialize.side_effect = (lambda data: data)
        assert self._are_return_values_of_connection_related_mocks_in_their_initial_state()

    def _rlocked_patch(self, target):
        patcher = rlocked_patch(target)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _rlocked_patch_wrapping_pusher_method(self, pusher_method_name):
        orig_method = getattr(AMQPThreadedPusher, pusher_method_name)
        wrapping_mock = RLockedMagicMock(wraps=orig_method)
        patcher = nonlocked_patch.object(
            AMQPThreadedPusher, pusher_method_name,
            # here we use lambda just to make use of the attribute
            # descriptor behavior of functions (providing a bound
            # method when being accessed via instance):
            new=(lambda obj: wrapping_mock(obj)))
        patcher.start()
        self.addCleanup(patcher.stop)
        return wrapping_mock

    def _are_return_values_of_connection_related_mocks_in_their_initial_state(self):
        return (self.pika_mock.ConnectionParameters.return_value is sen.conn_parameters
                and self.pika_mock.ConnectionParameters.side_effect is None

                and self.pika_mock.BlockingConnection.return_value is self.connection_mock
                and self.pika_mock.BlockingConnection.side_effect is None

                and self.pika_mock.BasicProperties.return_value is sen.props
                and self.pika_mock.BasicProperties.side_effect is None

                and self.connection_mock.channel.return_value is self.channel_mock
                and self.connection_mock.channel.side_effect is None)


    def tearDown(self):
        obj = getattr(self, 'obj', None)
        if obj is not None:
            assert isinstance(obj, AMQPThreadedPusher)
            obj._publishing_thread.join(self._SAFE_WAIT_TIMEOUT + 1)
            if obj._publishing_thread.is_alive():
                raise AssertionError(
                    'test course problem: the publishing '
                    'thread did not terminate :-/')


    #
    # Test/fixture helpers and reusable assertions

    @contextlib.contextmanager
    def _testing_pusher_obj_normal_lifetime(self, failed_connection_attempts_on_init=0):
        self._make_pusher_obj(failed_connection_attempts_on_init)
        try:
            self.assertIs(self.obj._connection, self.connection_mock)
            self.assertIs(self.obj._channel, self.channel_mock)
            self._assert_setup_communication_succeeded(failed_connection_attempts_on_init)
            self._assert_publishing_started_normally()
            self._reset_mocks()

            yield self.obj

        finally:
            self.obj.shutdown()

        self._assert_shut_down_normally()
        self._assert_no_remaining_data()

        # additional marginal assertions
        self.assertIs(self.obj._connection, self.connection_mock)
        self.assertIs(self.obj._channel, self.channel_mock)
        self.assertFalse(self.start_publishing_meth_wrapping_mock.mock_calls)


    def _make_pusher_obj(self, failed_connection_attempts_on_init=0, **kw):
        self.pika_mock.BlockingConnection.side_effect = (
            failed_connection_attempts_on_init * [self.AMQPConnectionError_sentinel_exc] +
            [self.connection_mock])  # noqa (silencing overzealous type checker)

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


    def _reset_mocks(self):
        self.pika_mock.ConnectionParameters.side_effect = None
        self.pika_mock.BlockingConnection.side_effect = None

        self.pika_mock.reset_mock()
        self.time_mock.reset_mock()
        self.traceback_mock.reset_mock()
        self.dump_condensed_debug_msg_mock.reset_mock()
        self.setup_communication_meth_wrapping_mock.reset_mock()
        self.start_publishing_meth_wrapping_mock.reset_mock()
        self.pika_BasicProperties_mock.reset_mock()
        self.connection_mock.reset_mock()
        self.channel_mock.reset_mock()
        if self.serialize is not None:
            self.serialize.reset_mock()
        if self.error_callback is not None:
            self.error_callback.reset_mock()

        assert self.pika_mock.BasicProperties is self.pika_BasicProperties_mock
        assert self._are_return_values_of_connection_related_mocks_in_their_initial_state()


    def _wait_until(self, condition_func):
        time_limit = self._SAFE_WAIT_TIMEOUT
        deadline = time.monotonic() + time_limit
        while time.monotonic() <= deadline:
            if condition_func():
                return
            time.sleep(0.01)
        self.fail(f'the time limit ({time_limit}s) exceeded '
                  f'without satisfying the specified condition')


    @contextlib.contextmanager
    def _patched_publish(self, side_effect=None):
        if isinstance(side_effect, Iterable):
            orig_publish_marker = self._INVOKE_ORIGINAL_PUBLISH
            orig_publish = AMQPThreadedPusher._publish
            item_iterator = iter(side_effect)

            def side_effect(data, routing_key, custom_prop_kwargs):
                item = next(item_iterator)
                if item is orig_publish_marker:
                    return orig_publish(self.obj, data, routing_key, custom_prop_kwargs)
                if isinstance(item, BaseException) or (isinstance(item, type)
                                                       and issubclass(item, BaseException)):
                    raise item
                return item

        with rlocked_patch(
                'n6lib.amqp_getters_pushers.AMQPThreadedPusher._publish',
                side_effect=side_effect) as _publish_mock:
            yield _publish_mock


    def _assert_setup_communication_succeeded(self,
                                              expected_failed_connection_attempts=0,
                                              reconnecting=False):
        self.assertEqual(self.setup_communication_meth_wrapping_mock.mock_calls, [
            call(AnyInstanceOf(AMQPThreadedPusher)),  # (here `self._obj` may not be set)
        ])
        self.assertEqual(
            self.pika_mock.mock_calls,
            # failed attempts (causing AMQPConnectionError), if any:
            expected_failed_connection_attempts * [
                call.ConnectionParameters(
                    conn_param=sen.param_value,
                    client_properties={'information': self._CONN_PARAM_CLIENT_PROP_INFORMATION}),
                call.BlockingConnection(sen.conn_parameters),
            ] +
            # final successful attempt:
            [
                call.ConnectionParameters(
                    conn_param=sen.param_value,
                    client_properties={'information': self._CONN_PARAM_CLIENT_PROP_INFORMATION}),
                call.BlockingConnection(sen.conn_parameters),
            ])
        self.assertEqual(
            self.dump_condensed_debug_msg_mock.mock_calls,
            # before reconnection -- only if `reconnecting` is True:
            reconnecting * [
                call(AnyMatchingRegex(r'will try to reconnect')),
            ] +
            # before each retry (after AMQPConnectionError), if any:
            expected_failed_connection_attempts * [
                call(AnyMatchingRegex(
                    r'^Connection problem in .*\._make_connection.*'
                    r'will retry after a short sleep'),
                ),
            ])
        self.assertEqual(
            self.time_mock.sleep.mock_calls,
            # before each retry (after AMQPConnectionError), if any:
            expected_failed_connection_attempts * [
                call(CONNECTION_RETRY_DELAY),
            ])
        self.assertEqual(self.channel_mock.mock_calls[:4], [
            # see the AMQPThreadedPusher(...) call in _make_pusher_obj()
            call.exchange_declare(exchange=sen.exchange),
            call.queue_declare(queue=sen.queue1, callback=ANY),
            call.queue_declare(blabla=sen.blabla, callback=ANY),
            call.queue_declare(blabla=sen.blabla, callback=sen.callback),
        ])


    def _assert_setup_communication_failed(self,
                                           expected_failed_connection_attempts,
                                           reconnecting=False):
        assert expected_failed_connection_attempts > 0
        self.assertEqual(self.setup_communication_meth_wrapping_mock.mock_calls, [
            call(AnyInstanceOf(AMQPThreadedPusher)),  # (here `self._obj` may not be set)
        ])
        self.assertEqual(
            self.pika_mock.mock_calls,
            # failed attempts (causing AMQPConnectionError):
            expected_failed_connection_attempts * [
                call.ConnectionParameters(
                    conn_param=sen.param_value,
                    client_properties={'information': self._CONN_PARAM_CLIENT_PROP_INFORMATION}),
                call.BlockingConnection(sen.conn_parameters),
            ])
        self.assertEqual(
            self.dump_condensed_debug_msg_mock.mock_calls,
            # before reconnection -- only if `reconnecting` is True:
            reconnecting * [
                call(AnyMatchingRegex(r'will try to reconnect')),
            ] +
            # before each retry (after AMQPConnectionError), if any
            # (note: minus 1 because of no debug info dump after the last
            # attempt; that attempt caused propagation of AMQPConnectionError):
            (expected_failed_connection_attempts - 1) * [
                call(AnyMatchingRegex(
                    r'^Connection problem in .*\._make_connection.*'
                    r'will retry after a short sleep'),
                ),
            ])
        self.assertEqual(
            self.time_mock.sleep.mock_calls,
            # before each retry (after AMQPConnectionError), if any
            # (note: minus 1 because of no delay after the last attempt):
            (expected_failed_connection_attempts - 1) * [
                call(CONNECTION_RETRY_DELAY),
            ])
        self.assertFalse(self.channel_mock.mock_calls)


    def _assert_publishing_started_normally(self):
        self.assertEqual(self.start_publishing_meth_wrapping_mock.mock_calls, [
            call(self.obj),
        ])
        self.assertTrue(self.obj._publishing)
        self.assertTrue(self.obj._publishing_thread.is_alive())

        # additional marginal assertions
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.obj._shutdown_initiated)
        self.assertFalse(self.obj._connection_closed)


    def _assert_published_with_pika(self, *pub_items):
        self.assertEqual(len(self.pika_mock.BasicProperties.mock_calls), len(pub_items))
        self.assertEqual(len(self.channel_mock.basic_publish.mock_calls), len(pub_items))

        for i, item in enumerate(pub_items):
            try:
                data, routing_key, custom_prop_kwargs = item
            except ValueError:
                data, routing_key = item
                custom_prop_kwargs = {}

            self.assertEqual(self.pika_mock.BasicProperties.mock_calls[i], call(
                prop_kwarg=sen.prop_value,
                **custom_prop_kwargs,
            ))
            self.assertEqual(self.channel_mock.basic_publish.mock_calls[i], call(
                body=data,
                routing_key=routing_key,
                exchange=sen.exchange,
                properties=sen.props,
                mandatory=sen.mandatory,
            ))


    def _assert_nothing_published_with_pika(self):
        self._assert_published_with_pika()  # (just with 0 items)


    def _assert_shut_down_normally(self):
        self.assertEqual(self.connection_mock.close.mock_calls[-1:], [
            call(),
        ])
        self.assertFalse(self.obj._publishing_thread.is_alive())
        self.assertFalse(self.obj._publishing)
        self.assertTrue(self.obj._shutdown_initiated)
        self.assertTrue(self.obj._connection_closed)


    def _assert_no_remaining_data(self):
        self.assertIn(self.obj._output_fifo.queue, [
            collections.deque(),        # either no items
            collections.deque([None]),  # or one None (as a "wake up!" sentinel)
        ])


    def _check_push_causes_error_as_pusher_is_inactive(self):
        with self.assertRaisesRegex(
                ValueError,
                r'cannot publish .* currently inactive'):
            self.obj.push(sen.data3, sen.rk3)


    #
    # Actual tests

    @foreach(range(CONNECTION_ATTEMPTS))
    def test_normal_operation_without_serialize(self, failed_connection_attempts_on_init):
        assert failed_connection_attempts_on_init < CONNECTION_ATTEMPTS

        self.serialize = None

        with self._testing_pusher_obj_normal_lifetime(failed_connection_attempts_on_init) as obj:
            obj.push(sen.data1, sen.rk1)
            obj.push(sen.data2, sen.rk2, {'custom': sen.custom_value})

            # (let the publishing thread operate)
            self._wait_until(lambda: self.channel_mock.basic_publish.call_count >= 2)

        self._assert_published_with_pika(
            (sen.data1, sen.rk1),
            (sen.data2, sen.rk2, {'custom': sen.custom_value}),
        )
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    @foreach(range(CONNECTION_ATTEMPTS))
    def test_normal_operation_with_serialize(self, failed_connection_attempts_on_init):
        assert failed_connection_attempts_on_init < CONNECTION_ATTEMPTS

        self.serialize.side_effect = {
            sen.raw1: sen.serialized1,
            sen.no_pub_data: DoNotPublish,
            sen.raw2: sen.serialized2,
        }.get

        with self._testing_pusher_obj_normal_lifetime(failed_connection_attempts_on_init) as obj:

            # to be published normally
            obj.push(sen.raw1, sen.rk1)

            # serialize() returns DoNotPublish for this one (see above)
            # so the data will not be published
            obj.push(sen.no_pub_data, sen.irrelevant)

            # to be published normally
            obj.push(sen.raw2, sen.rk2, {'custom': sen.custom_value})

            # (let the publishing thread operate)
            self._wait_until(lambda: self.channel_mock.basic_publish.call_count >= 2)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.raw1),
            call(sen.no_pub_data),
            call(sen.raw2),
        ])
        self._assert_published_with_pika(
            (sen.serialized1, sen.rk1),
            (sen.serialized2, sen.rk2, {'custom': sen.custom_value}),
        )
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_too_many_failed_connection_attempts_on_init(self):
        failed_connection_attempts_on_init = CONNECTION_ATTEMPTS

        with self.assertRaises(self.AMQPConnectionError_sentinel_exc):
            self._make_pusher_obj(failed_connection_attempts_on_init)

        self._assert_setup_communication_failed(failed_connection_attempts_on_init)
        self.assertFalse(self.start_publishing_meth_wrapping_mock.mock_calls)

        self._assert_nothing_published_with_pika()
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.connection_mock.close.mock_calls)


    @foreach(range(CONNECTION_ATTEMPTS))
    def test_publishing_with_disconnect_and_some_reconnection_attempts_finally_successful(
            self,
            failed_reconnection_attempts):

        assert failed_reconnection_attempts < CONNECTION_ATTEMPTS

        side_effect_of_publish = [
            self.ConnectionClosed_sentinel_exc,
            self._INVOKE_ORIGINAL_PUBLISH,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            self.pika_mock.BlockingConnection.side_effect = (
                failed_reconnection_attempts * [self.AMQPConnectionError_sentinel_exc] +
                [self.connection_mock])  # noqa (silencing overzealous type checker)

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 2)

        self._assert_setup_communication_succeeded(failed_reconnection_attempts, reconnecting=True)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
            call(sen.data, sen.rk, None),
        ])
        self._assert_published_with_pika(
            (sen.data, sen.rk),
        )
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- before trying to reconnect
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_disconnect_and_too_many_failed_reconnection_attempts(self):
        failed_reconnection_attempts = CONNECTION_ATTEMPTS

        side_effect_of_publish = [
            self.ConnectionClosed_sentinel_exc,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            self.pika_mock.BlockingConnection.side_effect = (
                failed_reconnection_attempts * [self.AMQPConnectionError_sentinel_exc])

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 1)

        self._assert_setup_communication_failed(failed_reconnection_attempts, reconnecting=True)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
        ])
        self._assert_nothing_published_with_pika()
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.AMQPConnectionError_sentinel_exc)),
        ])
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- before trying to reconnect
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_disconnect_and_then_shutdown_initiated_flag_set_to_true(self):
        # (when trying to reconnect after disconnection,
        # do *not* retry after the first reconnect failure)

        def pika_ConnectionParameters_side_effect(**_):
            # to be done just before the reconnection attempt
            obj._shutdown_initiated = True
            return sen.conn_parameters

        side_effect_of_publish = [
            self.ConnectionClosed_sentinel_exc,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            self.pika_mock.ConnectionParameters.side_effect = pika_ConnectionParameters_side_effect
            self.pika_mock.BlockingConnection.side_effect = self.AMQPConnectionError_sentinel_exc

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 1)

        self._assert_setup_communication_failed(1, reconnecting=True)  # 1 attempt, *no* retries

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
        ])
        self._assert_nothing_published_with_pika()
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.AMQPConnectionError_sentinel_exc)),
        ])
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- before trying to reconnect
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_disconnect_while_shutdown_initiated_flag_is_true(self):
        # (do not try to reconnect after disconnection at all...)

        side_effect_of_publish = [
            self._INVOKE_ORIGINAL_PUBLISH,
            self.ConnectionClosed_sentinel_exc,
            self._INVOKE_ORIGINAL_PUBLISH,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj._shutdown_initiated = True

            obj.push(sen.data1, sen.rk1)
            obj.push(sen.data_err, sen.rk_err)
            obj.push(sen.data2, sen.rk2, {'custom': sen.custom_value})

            # (let the publishing thread operate)
            self._wait_until(lambda: self.channel_mock.basic_publish.call_count >= 2)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data1),
            call(sen.data_err),
            call(sen.data2),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data1, sen.rk1, None),
            call(sen.data_err, sen.rk_err, None),
            call(sen.data2, sen.rk2, {'custom': sen.custom_value}),
        ])
        self._assert_published_with_pika(
            (sen.data1, sen.rk1),
            (sen.data2, sen.rk2, {'custom': sen.custom_value}),
        )
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.ConnectionClosed_sentinel_exc)),
        ])
        # *no* reconnections attempted
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_disconnect_while_publishing_flag_is_false(self):
        # (do not try to reconnect after disconnection at all; report
        # the problem and continue trying to handle incoming data items
        # -- even if that must fail -- until the output fifo is empty;
        # then the publishing thread should terminate)

        data_has_been_pushed = threading.Event()
        safe_wait_timeout = self._SAFE_WAIT_TIMEOUT

        def basic_publish_side_effect(*_, **__):
            if not data_has_been_pushed.wait(safe_wait_timeout):
                raise AssertionError(
                    'test course problem: the main thread did '
                    'not set the `data_has_been_pushed` event')

        self.channel_mock.basic_publish.side_effect = basic_publish_side_effect

        side_effect_of_publish = [
            self._INVOKE_ORIGINAL_PUBLISH,
            self.ConnectionClosed_sentinel_exc,
            self._INVOKE_ORIGINAL_PUBLISH,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj._publishing = False

            # (here, in this test, we put items into the output fifo
            # manually, as calling obj.push() when obj._publishing
            # is false would cause ValueError)
            obj._output_fifo.put_nowait((sen.data1, sen.rk1, None))
            obj._output_fifo.put_nowait((sen.data_err, sen.rk_err, None))
            obj._output_fifo.put_nowait((sen.data2, sen.rk2, {'custom': sen.custom_value}))

            data_has_been_pushed.set()

            # (let the publishing thread operate)
            self._wait_until(lambda: self.channel_mock.basic_publish.call_count >= 2)

            # now the publishing thread should terminate shortly (or be
            # already terminated)
            obj._publishing_thread.join(self._SAFE_WAIT_TIMEOUT)

            # even though the publishing thread terminated after it had
            # pushed all items from the output fifo...
            self.assertFalse(obj._publishing_thread.is_alive())

            # ...the pusher has *not* been shut down yet
            self.assertFalse(obj._shutdown_initiated)
            self.assertFalse(obj._connection_closed)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data1),
            call(sen.data_err),
            call(sen.data2),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data1, sen.rk1, None),
            call(sen.data_err, sen.rk_err, None),
            call(sen.data2, sen.rk2, {'custom': sen.custom_value}),
        ])
        self._assert_published_with_pika(
            (sen.data1, sen.rk1),
            (sen.data2, sen.rk2, {'custom': sen.custom_value}),
        )
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.ConnectionClosed_sentinel_exc)),
        ])
        # *no* reconnections attempted
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_exception_and_error_callback(self):
        side_effect_of_publish = [
            self.generic_sentinel_exc,
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 1)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
        ])
        self._assert_nothing_published_with_pika()
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.generic_sentinel_exc)),
        ])
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_exception_and_no_error_callback(self):
        side_effect_of_publish = [
            self.generic_sentinel_exc,
        ]
        self.error_callback = None
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 1)

        assert self.error_callback is None, "bug in test case"
        self.assertIsNone(obj._error_callback)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
        ])
        self._assert_nothing_published_with_pika()
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertEqual(self.traceback_mock.print_exc.mock_calls, [
            call(),  # (called because there is no error callback)
        ])

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_error_callback_raising_exception(self):
        side_effect_of_publish = [
            self.generic_sentinel_exc,
        ]
        self.error_callback.side_effect = self.another_generic_sentinel_exc
        with self._patched_publish(side_effect_of_publish) as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: _publish_mock.call_count >= 1)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(_publish_mock.mock_calls, [
            call(sen.data, sen.rk, None),
        ])
        self._assert_nothing_published_with_pika()
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.generic_sentinel_exc)),
        ])
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
            call(AnyMatchingRegex(r'^Exception caught when calling .*\._error_callback')),
        ])
        self.assertEqual(self.traceback_mock.print_exc.mock_calls, [
            call(),  # (called to print traceback of exception from error callback)
        ])

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_publishing_with_serialization_error(self):
        self.serialize.side_effect = self.generic_sentinel_exc

        with self._patched_publish() as _publish_mock, \
             self._testing_pusher_obj_normal_lifetime() as obj:

            obj.push(sen.data, sen.rk)

            # (let the publishing thread operate)
            self._wait_until(lambda: self.serialize.call_count >= 1)

        self.assertEqual(self.serialize.mock_calls, [
            call(sen.data),
        ])
        self.assertEqual(self.error_callback.mock_calls, [
            call(AnyInstanceOf(self.generic_sentinel_exc)),
        ])

        # the message has not been published
        self.assertFalse(_publish_mock.mock_calls)
        self._assert_nothing_published_with_pika()

        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])
        self._check_push_causes_error_as_pusher_is_inactive()


    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_publishing_with_fatal_error(self, remaining_data_in_output_fifo=False):
        side_effect_of_publish = [
            BaseException,  # (does not inherit from Exception)
        ]
        with self._patched_publish(side_effect_of_publish) as _publish_mock:

            self._make_pusher_obj()
            try:
                self._assert_publishing_started_normally()
                self._reset_mocks()

                self.obj.push(sen.data, sen.rk)

                # we wait to let the publishing thread operate and crash
                self._wait_until(lambda: _publish_mock.call_count >= 1)
                self.obj._publishing_thread.join(self._SAFE_WAIT_TIMEOUT)

                self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
                    call('PUBLISHING CO-THREAD STOPS WITH EXCEPTION!'),
                ])

                self.assertFalse(self.obj._publishing_thread.is_alive())
                self.assertFalse(self.obj._publishing)

                self.assertEqual(self.serialize.mock_calls, [
                    call(sen.data),
                ])
                self.assertEqual(_publish_mock.mock_calls, [
                    call(sen.data, sen.rk, None),
                ])
                self._assert_nothing_published_with_pika()
            except:
                # (to try to make the publishing thread terminate on an error)
                self.obj.shutdown()
                raise

        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.start_publishing_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertFalse(self.connection_mock.close.mock_calls)
        self.assertFalse(self.obj._shutdown_initiated)
        self.assertFalse(self.obj._connection_closed)

        if not remaining_data_in_output_fifo:
            self._assert_no_remaining_data()

        self._check_push_causes_error_as_pusher_is_inactive()


    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_publishing_with_fatal_error_and_remaining_data_in_output_fifo(self):
        def serialize_side_effect(data):
            self.obj._output_fifo.put(sen.item)
            return data
        self.serialize.side_effect = serialize_side_effect

        self.test_publishing_with_fatal_error(remaining_data_in_output_fifo=True)

        underlying_deque = getattr(self.obj._output_fifo, 'queue', None)
        assert isinstance(underlying_deque, collections.deque), "test case's assumption is invalid"

        self.assertEqual(underlying_deque, collections.deque([sen.item]))
        self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
            call('PUBLISHING CO-THREAD STOPS WITH EXCEPTION!'),
        ])

        with self.assertRaisesRegex(
                ValueError,
                r'is being shut down but .* pending messages'):
            self.obj.shutdown()

        self.assertEqual(underlying_deque, collections.deque([sen.item]))
        self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
            call('PUBLISHING CO-THREAD STOPS WITH EXCEPTION!'),

            # info about ValueError (referred to by assertRaisesRegex()
            # above, propagated from _check_state_after_stop()) was dumped
            call(AnyMatchingRegex(r'^EXCEPTION FROM .*\._before_close')),
        ])


    def test_shutting_down_with_timed_out_join_to_publishing_thread(self):
        self._make_pusher_obj(publishing_thread_join_timeout=0.2)
        try:
            self._assert_publishing_started_normally()
            self._reset_mocks()

            output_fifo_put_nowait_orig = self.obj._output_fifo.put_nowait
            output_fifo_put_nowait_mock = Mock()

            # we wait to let the publishing thread set the liveliness
            # indicator to True (and then hang on the output fifo)
            self._wait_until(lambda: self.obj._publishing_thread_liveliness_indicator)
        except:
            # (to try to make the publishing thread terminate on an error)
            self.obj.shutdown()
            raise

        try:
            # monkey-patching output_fifo.put_nowait() so that
            # shutdown() will *not* wake-up the publishing thread
            self.obj._output_fifo.put_nowait = output_fifo_put_nowait_mock

            with self.assertRaisesRegex(
                    RuntimeError,
                    r'is being shut down but .* pushing thread seems to be still alive'):
                self.obj.shutdown()

            # shutdown() returned because the join timeout expired and
            # the liveliness indicator was not re-set to True by the
            # publishing thread
            self.assertFalse(self.obj._publishing_thread_liveliness_indicator)

            # the pusher is shut down...
            self.assertEqual(self.connection_mock.close.mock_calls, [
                call(),
            ])
            self.assertFalse(self.obj._publishing)
            self.assertTrue(self.obj._shutdown_initiated)
            self.assertTrue(self.obj._connection_closed)

            # ...but the publishing thread is still alive
            self.assertTrue(self.obj._publishing_thread.is_alive())

            # info about RuntimeError (referred to by assertRaisesRegex()
            # above, propagated from _check_state_after_stop()) was dumped
            self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
                call(AnyMatchingRegex(r'^EXCEPTION FROM .*\._before_close')),
            ])

            self._check_push_causes_error_as_pusher_is_inactive()
        finally:
            # (to ensure the publishing thread will terminate)
            self.obj._publishing = False
            output_fifo_put_nowait_orig(None)

            # now the publishing thread should terminate shortly (or be
            # already terminated)
            self.obj._publishing_thread.join(self._SAFE_WAIT_TIMEOUT)

        self.assertEqual(output_fifo_put_nowait_mock.mock_calls, [
            call(None),
        ])
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.start_publishing_meth_wrapping_mock.mock_calls)

        self._check_push_causes_error_as_pusher_is_inactive()


    def test_shutting_down_with_timed_out_acquisition_of_connection_lock(self):
        self._make_pusher_obj()
        try:
            self._assert_publishing_started_normally()
            self._reset_mocks()

            self.obj.SHUTDOWN_CONNECTION_LOCK_TIMEOUT = 0.01

            with self.obj._connection_lock, \
                 self.assertRaisesRegex(
                     RuntimeError,
                     r'connection cannot be closed gracefully.*'
                     r'timeout .* has been reached'):
                self.obj.shutdown()
        except:
            # (to try to make the publishing thread terminate on an error)
            self.obj.shutdown()
            raise

        # shutdown has been initiated...
        self.assertTrue(self.obj._shutdown_initiated)

        # ...and the publishing thread has terminated (and
        # the related flag has been set to false)...
        self.assertFalse(self.obj._publishing_thread.is_alive())
        self.assertFalse(self.obj._publishing)

        # ...but the AMQP connection has *not* been closed
        # (and the related flag has *not* been set to true)
        self.assertFalse(self.connection_mock.close.mock_calls)
        self.assertFalse(self.obj._connection_closed)
        self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
            call(AnyMatchingRegex(
                r'^CANNOT CLOSE AMQP CONNECTION PROPERLY BECAUSE OF '
                r'EXCEPTION FROM .*\._close_connection_with_lock'),
            ),
        ])

        # non-essential assertions/checks
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.start_publishing_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self._check_push_causes_error_as_pusher_is_inactive()


    def test_shutting_down_while_already_disconnected(self):
        # (not an error, just causes additional debug info dump)

        with self._testing_pusher_obj_normal_lifetime():
            self.connection_mock.close.side_effect = self.ConnectionClosed_sentinel_exc

        self.assertEqual(self.dump_condensed_debug_msg_mock.mock_calls, [
            call(AnyMatchingRegex(r'^AMQP connection seems to be already closed')),
        ])
        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])

        # non-essential assertions/checks
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self._check_push_causes_error_as_pusher_is_inactive()


    @foreach(1, 2, 33)
    def test_shutting_down_more_than_once(self, redundant_shutdowns):
        # (not an error, just no-op)

        with self._testing_pusher_obj_normal_lifetime() as obj:
            pass

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # <- during shutdown
        ])

        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
        self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        for _ in range(redundant_shutdowns):
            obj.shutdown()

            self._assert_shut_down_normally()
            self.assertFalse(self.error_callback.mock_calls)
            self.assertFalse(self.setup_communication_meth_wrapping_mock.mock_calls)
            self.assertFalse(self.dump_condensed_debug_msg_mock.mock_calls)
            self.assertFalse(self.traceback_mock.print_exc.mock_calls)

        self.assertEqual(self.connection_mock.close.mock_calls, [
            call(),  # (still only this one)
        ])

        self._check_push_causes_error_as_pusher_is_inactive()


    def test_timed_out_start_of_publishing_thread(self):
        # (hardly probable but let's cover it for completeness...)

        # to be used as obj._publishing_thread (normally, a threading.Thread)
        publishing_thread_mock = RLockedMagicMock(name='obj._publishing_thread')

        # to be used as obj._publishing_thread_started (normally, a threading.Event)
        publishing_thread_started_mock = RLockedMagicMock(name='obj._publishing_thread_started')
        publishing_thread_started_mock.wait.return_value = False

        with rlocked_patch('n6lib.amqp_getters_pushers.threading') as threading_mock, \
             self.assertRaisesRegex(
                 RuntimeError,
                 r'reached the publishing thread start timeout'):

            threading_mock.Lock = threading.Lock  # (<- a real class)
            threading_mock.Thread.return_value = publishing_thread_mock
            threading_mock.Event.return_value = publishing_thread_started_mock
            seal(threading_mock)

            self._make_pusher_obj()

        assert threading_mock.Thread.call_count <= 1, 'unexpected extra use of threading.Thread'
        assert threading_mock.Event.call_count <= 1, 'unexpected extra use of threading.Event'

        self._assert_setup_communication_succeeded()
        self.assertEqual(self.start_publishing_meth_wrapping_mock.mock_calls, [
            call(AnyInstanceOf(AMQPThreadedPusher)),  # (as here `self._obj` is not set)
        ])

        self.assertEqual(publishing_thread_mock.start.mock_calls, [
            call(),
        ])
        self.assertEqual(publishing_thread_started_mock.wait.mock_calls, [
            call(PUBLISHING_THREAD_START_TIMEOUT),
        ])

        self._assert_nothing_published_with_pika()
        self.assertFalse(self.error_callback.mock_calls)
        self.assertFalse(self.traceback_mock.print_exc.mock_calls)
        self.assertFalse(self.connection_mock.close.mock_calls)

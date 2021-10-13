# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections
import collections as collections_abc          #3: `import collections.abc as collections_abc`
import itertools
import queue as queue_lib
import threading
import time
import traceback
import weakref

import pika
import pika.credentials
import pika.exceptions

from n6lib.amqp_helpers import (
    get_amqp_connection_params_dict,
    get_n6_default_client_properties_for_amqp_connection,
)
from n6lib.class_helpers import is_seq
from n6lib.common_helpers import (
    NonBlockingLockWrapper,
    dump_condensed_debug_msg,
)



__all__ = [
    'BaseAMQPTool',
    'AMQPSimpleGetter',
    'AMQPSimplePusher',
    'AMQPThreadedPusher',
]



# data placeholder that can be returned by pushers' `serialize` callbacks
DoNotPublish = object()



class BaseAMQPTool(object):

    CONNECTION_ATTEMPTS = 10
    CONNECTION_RETRY_DELAY = 0.5

    def __init__(self,
                 connection_params_dict,
                 queues_to_declare=(),
                 **kwargs):

        super(BaseAMQPTool, self).__init__(**kwargs)

        # resolve the `connection_params_dict` argument if specified as None
        if connection_params_dict is None:
            connection_params_dict = get_amqp_connection_params_dict()
        if connection_params_dict.get('ssl'):
            connection_params_dict.setdefault(
                  'credentials',
                  pika.credentials.ExternalCredentials())
        if 'client_properties' not in connection_params_dict:
            connection_params_dict['client_properties'] = \
                get_n6_default_client_properties_for_amqp_connection()

        # normalize the `queues_to_declare` argument
        # -- to a list of kwargs for queue_declare()
        if is_seq(queues_to_declare):
            queues_to_declare = list(queues_to_declare)
        else:
            queues_to_declare = [queues_to_declare]
        for i, queue in enumerate(queues_to_declare):
            queue = queues_to_declare[i] = (
                dict(queue) if isinstance(queue, collections_abc.Mapping)
                else {'queue': queue})
            queue.setdefault('callback', (lambda *args, **kwargs: None))

        # set several non-public instance attributes
        self._connection_params_dict = connection_params_dict
        self._queues_to_declare = queues_to_declare

        self._shutdown_lock = threading.Lock()

        self._connection_lock = threading.Lock()
        self._connection_lock_nonblocking = NonBlockingLockWrapper(
            self._connection_lock,
            lock_description='the connection/channel operations lock')
        self._connection_closed = False

        # setup AMQP communication
        self._setup_communication()


    def __repr__(self):
        return '<{0} object at {1:#x} with {2!r}>'.format(
              self.__class__.__name__,                                           #3 `__name__`->`__qualname__`
              id(self),
              self._connection_params_dict)


    #
    # Context manager interface

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.shutdown()


    #
    # Public methods

    def shutdown(self):
        with self._shutdown_lock:
            try:
                self._before_close()
            finally:
                if not self._connection_closed:
                    with self._connection_lock:
                        self._connection.close()
                    self._connection_closed = True


    #
    # Non-public methods

    def _setup_communication(self):
        with self._connection_lock_nonblocking:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = self._make_connection()
            self._channel = self._connection.channel()
            self._declare_exchanges()
            self._declare_queues()
            self._additional_communication_setup()

    def _make_connection(self):
        for attempt in itertools.count(start=1):
            parameters = pika.ConnectionParameters(**self._connection_params_dict)
            try:
                return pika.BlockingConnection(parameters)
            except pika.exceptions.AMQPConnectionError:
                if attempt >= self.CONNECTION_ATTEMPTS:
                    raise
            time.sleep(self.CONNECTION_RETRY_DELAY)
        assert False, 'this code line should never be reached'

    def _declare_exchanges(self):
        raise NotImplementedError

    def _declare_queues(self):
        for queue_kwargs in self._queues_to_declare:
            self._channel.queue_declare(**queue_kwargs)

    def _additional_communication_setup(self):
        pass

    def _before_close(self):
        pass



# TODO: finish implementation of this class! (now it's only a stub!)
# then TODO: tests (at least what is not yet tested for AMQPThreadedPusher)
class AMQPSimpleGetter(BaseAMQPTool):

    def __init__(self,
                 queue_bindings,
                 exchanges_to_declare=(),
                 **kwargs):
        """
        Initialize the instance (opening AMQP connection etc.).

        Obligatory kwargs:
            `connection_params_dict` (dict or None; obligatory):
                A dict to be passed as **kwargs into the
                pika.ConnectionParameters constructor.  It can be
                explicitly specified as None -- then it will be obtained
                automatically using the function
                amqp_helpers.get_amqp_connection_params_dict().

            `queue_bindings` (dict or sequence of dicts; obligatory):
                A dict to be passed as **kwargs into
                pika.channel.Channel.queue_bind(), or a sequence
                of such dicts.  Dict(s) do not need to contain
                the 'callback' item (by default a no-op callable
                is used).

        Optional kwargs:
            `queues_to_declare` (str/dict/sequence...; default: empty tuple):
                The name of a queue to be declared or a dict of **kwargs
                for pika.channel.Channel.queue_declare(), or a sequence
                of such names or dicts.  Dict(s) do not need to contain
                the 'callback' item (by default a no-op callable is used).

            `exchanges_to_declare` (str/dict/seq...; default: empty tuple):
                The name of an exchange to be declared or a dict of **kwargs
                for pika.channel.Channel.exchange_declare(), or a sequence
                of such names or dicts.

        Raises:
            A pika.exceptions.AMQPError subclass:
                If AMQP connection cannot be set up.
        """

        # normalize the `queue_bindings` argument
        # -- to a list of kwargs for queue_bind()
        if is_seq(queue_bindings):
            queue_bindings = list(queue_bindings)
        else:
            queue_bindings = [queue_bindings]
        for i, bind_kwargs in enumerate(queue_bindings):
            bind_kwargs = queue_bindings[i] = dict(bind_kwargs)
            bind_kwargs.setdefault('callback', (lambda *args, **kwargs: None))

        # normalize the `exchanges_to_declare` argument
        # -- to a list of kwargs for exchange_declare()
        if is_seq(exchanges_to_declare):
            exchanges_to_declare = list(exchanges_to_declare)
        else:
            exchanges_to_declare = [exchanges_to_declare]
        for i, exchange in enumerate(exchanges_to_declare):
            exchanges_to_declare[i] = (
                dict(exchange) if isinstance(exchange, collections_abc.Mapping)
                else {'exchange': exchange})

        self._exchanges_to_declare = exchanges_to_declare
        self._queue_bindings = queue_bindings

        super(AMQPSimpleGetter, self).__init__(**kwargs)


    #
    # Non-public methods

    def _declare_exchanges(self):
        for exchange_kwargs in self._exchanges_to_declare:
            self._channel.exchange_declare(**exchange_kwargs)

    def _additional_communication_setup(self):
        "XXX: self._channel.queue_bind(..."
        raise NotImplementedError('TODO!')



# TODO: tests (at least what is not yet tested for AMQPThreadedPusher)
class AMQPSimplePusher(BaseAMQPTool):

    DEFAULT_PROP_KWARGS = dict(
        content_type='application/octet-stream',
        delivery_mode=2,  # persistent  ## FIXME:? what is better as default: 1 or 2?
    )

    def __init__(self,
                 exchange,
                 serialize=None,
                 prop_kwargs=None,
                 mandatory=False,
                 **kwargs):
        """
        Initialize the instance (opening AMQP connection etc.).

        Obligatory kwargs:
            `connection_params_dict` (dict or None):
                A dict to be passed as **kwargs into the
                pika.ConnectionParameters constructor.  It can be
                explicitly specified as None -- then it will be obtained
                automatically using the function
                amqp_helpers.get_amqp_connection_params_dict().

            `exchange` (str or dict):
                The name of the exchange or a dict of **kwargs for
                pika.channel.Channel.exchange_declare().

        Optional kwargs:
            `queues_to_declare` (str/dict/sequence...; default: empty tuple):
                The name of a queue to be declared or a dict of **kwargs
                for pika.channel.Channel.queue_declare(), or a sequence
                of such names or dicts.  Dict(s) do not need to contain
                the 'callback' item (by default a no-op callable is used).
                Note that, as a message producer, typically you do *not*
                need to declare queues.

            `serialize` (a callable object or None; default: None):
                If not None, it should be a callable object that takes
                one argument: data to be serialized before publishing;
                the callable should always return a bytes object or the
                DoNotPublish sentinel (the latter to suppress publishing
                of the given data).

                If None, pushed data items should always be bytes.

                Note: when we refer to bytes objects here, also str
                objects are accepted (and automatically encoded to bytes
                using the UTF-8 encoding), but in the future, most
                probably, we will change the interface so that only
                bytes (and the DoNotPublish sentinel when applicable)
                will be accepted.

            `prop_kwargs` (dict or None; default: None):
                A dict of **kwargs for the pika.BasicProperties constructor.
                If None the value of the `DEFAULT_PROP_KWARGS` class
                attribute will be used.

            `mandatory` (bool; default: False):
                The value of the `mandatory` keyword argument for
                pika.channel.Channel.basic_publish().

        Raises:
            A pika.exceptions.AMQPError subclass:
                If AMQP connection cannot be set up.
        """

        # normalize the `exchange` argument
        if isinstance(exchange, (str, unicode)):                                 #3: unicode--
            exchange = {'exchange': exchange}

        # set the `prop_kwargs` argument to default value if not specified
        if prop_kwargs is None:
            prop_kwargs = self.DEFAULT_PROP_KWARGS

        # set several non-public instance attributes
        self._exchange = exchange
        self._exchange_name = exchange['exchange']
        self._serialize = serialize
        self._prop_kwargs = prop_kwargs
        self._mandatory = mandatory

        self._push_lock = threading.Lock()
        self._publishing = False  # to be set in _start_publishing()

        super(AMQPSimplePusher, self).__init__(**kwargs)

        # start the publishing thread
        self._start_publishing()


    #
    # Public methods

    def push(self, data, routing_key, custom_prop_kwargs=None):
        with self._push_lock:
            if not self._publishing:
                raise ValueError('cannot publish message as '
                                 '{0!r} is currently inactive'
                                 .format(self))
            self._do_push(data, routing_key, custom_prop_kwargs)


    #
    # Non-public methods

    def _declare_exchanges(self):
        self._channel.exchange_declare(**self._exchange)

    def _start_publishing(self):
        self._publishing = True

    def _do_push(self, data, routing_key, custom_prop_kwargs):
        if self._serialize is not None:
            data = self._serialize(data)
        self._publish(data, routing_key, custom_prop_kwargs)

    def _publish(self, data, routing_key, custom_prop_kwargs):
        if data is DoNotPublish:
            return
        prop_kwargs = self._prop_kwargs
        if custom_prop_kwargs:
            prop_kwargs = dict(prop_kwargs, **custom_prop_kwargs)
        properties = pika.BasicProperties(**prop_kwargs)
        with self._connection_lock_nonblocking:
            self._channel.basic_publish(exchange=self._exchange_name,
                                        routing_key=routing_key,
                                        body=data,
                                        properties=properties,
                                        mandatory=self._mandatory)

    def _stop_publishing(self):
        self._publishing = False

    def _before_close(self):
        with self._push_lock:
            self._stop_publishing()
            self._check_state_after_stop()

    def _check_state_after_stop(self):
        pass



### XXX: Shouldn't the communication be always configured in the
### publishing thread?  From pika docs: "Pika does not have any notion
### of threading in the code. If you want to use Pika with threading,
### make sure you have a Pika connection per thread, created in that
### thread.  It is not safe to share one Pika connection across
### threads."  (http://pika.readthedocs.org/en/0.10.0/faq.html)
class AMQPThreadedPusher(AMQPSimplePusher):

    def __init__(self,
                 output_fifo_max_size=20000,
                 error_callback=None,
                 # 15 seems to be conservative enough, even paranoic a bit :-)
                 publishing_thread_join_timeout=15,
                 **kwargs):
        """
        Initialize the instance and start the publishing co-thread.

        Kwargs -- the same as for AMQPSimplePusher plus also:

            `output_fifo_max_size` (int; default: 20000):
                Maximum length of the internal output fifo.

            `error_callback` (None or a callable object; default: None):
                A callback to be used when an exception (being an instance
                of an Exception subclass) is caught in the publishing
                co-thread while trying to publish some data.  The callback
                will be called with the exception object as the sole
                argument, in the publishing co-thread.

                If there is no callback, i.e. `error_callback` is None:
                the exception's traceback will be printed to sys.stderr.

                If the callback throws another exception it will be caught
                and its traceback will be printed to sys.stderr.

            `publishing_thread_join_timeout` (int; default: 15):
                Related to pusher shut down: the timeout value (in seconds)
                for joining the publishing thread before checking the internal
                heartbeat flag; the value should not be smaller than a
                reasonable duration of one iteration of the publishing thread
                loop (which includes getting a message from the inner queue,
                serializing the message and sending it to the AMQP broker,
                handling any exception etc.).

        Raises:
            A pika.exceptions.AMQPError subclass:
                If AMQP connection cannot be set up.
        """

        self._output_fifo = queue_lib.Queue(maxsize=output_fifo_max_size)
        self._error_callback = error_callback
        self._publishing_thread_join_timeout = publishing_thread_join_timeout
        self._publishing_thread = None  # to be set in _start_publishing()
        self._publishing_thread_heartbeat_flag = False

        super(AMQPThreadedPusher, self).__init__(**kwargs)


    #
    # Non-public methods

    def _start_publishing(self):
        self._publishing_thread = threading.Thread(
            target=self._publishing_loop,
            kwargs=dict(proxy=weakref.proxy(self)))
        self._publishing_thread.daemon = True
        self._publishing = True
        self._publishing_thread.start()

    def _do_push(self, data, routing_key, custom_prop_kwargs):
        self._output_fifo.put_nowait((data, routing_key, custom_prop_kwargs))

    def _stop_publishing(self):
        self._publishing = False
        if self._publishing_thread.is_alive():
            try:
                # put None as a "wake-up!" sentinel
                self._output_fifo.put_nowait(None)
            except queue_lib.Full:
                pass
        while True:
            self._publishing_thread_heartbeat_flag = False
            self._publishing_thread.join(self._publishing_thread_join_timeout)
            if (not self._publishing_thread.is_alive() or
                  not self._publishing_thread_heartbeat_flag):
                break

    def _check_state_after_stop(self):
        if self._publishing_thread.is_alive():
            raise RuntimeError('{0!r} is being shut down but the pushing '
                               'thread seems to be still alive (though '
                               'probably malfunctioning); there may be some '
                               'pending messages that have not been '
                               '(and will not be) published!'
                               .format(self))
        underlying_deque = self._output_fifo.queue
        assert isinstance(underlying_deque, collections.deque)
        num_of_pending = sum(1 for item in underlying_deque
                             if item is not None)
        if num_of_pending:
            raise ValueError('{0!r} is being shut down but '
                             '{1} pending messages have not been '
                             '(and will not be) published!'
                             .format(self, num_of_pending))

    @staticmethod
    def _publishing_loop(proxy):
        # proxy is a weakref.proxy(self) (to avoid reference cycles)
        try:
            output_fifo = proxy._output_fifo
            while proxy._publishing or not output_fifo.empty():
                proxy._publishing_thread_heartbeat_flag = True
                item = output_fifo.get()
                if item is not None:  # None is a "wake up!" sentinel
                    data, routing_key, custom_prop_kwargs = item
                    try:
                        proxy._handle_data(data, routing_key, custom_prop_kwargs)
                    except Exception as exc:
                        proxy._handle_error(exc)
        except:
            dump_condensed_debug_msg('PUBLISHING CO-THREAD STOPS WITH EXCEPTION!')
            raise  # traceback should be printed to sys.stderr automatically
        finally:
            proxy._publishing = False

    def _handle_data(self, data, routing_key, custom_prop_kwargs):
        if self._serialize is not None:
            data = self._serialize(data)
        try:
            self._publish(data, routing_key, custom_prop_kwargs)
        except pika.exceptions.ConnectionClosed:
            if self._publishing:
                self._setup_communication()
                self._publish(data, routing_key, custom_prop_kwargs)
            else:
                # the pusher is being shut down
                # => do not try to reconnect
                raise

    def _handle_error(self, exc):
        if self._error_callback is None:
            traceback.print_exc()
        else:
            try:
                self._error_callback(exc)
            except Exception:
                dump_condensed_debug_msg(
                    'Exception caught when calling '
                    '{0!r}._error_callback({1!r}):'
                    .format(self, exc))
                traceback.print_exc()

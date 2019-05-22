# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

# Note, however, that some parts of the QueuedBase class are patterned
# after some examples from the docs of a 3rd-party library: `pika`; and
# some of the docstrings are taken from or contain fragments of the
# docs of the `pika` library.

import collections
import contextlib
import copy
import functools
import pprint
import re
import sys
import types

try:
    import pika
    import pika.credentials
except ImportError:
    print >>sys.stderr, "Warning: pika is required to run AMQP components"

from n6lib.amqp_helpers import get_amqp_connection_params_dict
from n6lib.argument_parser import N6ArgumentParser
from n6lib.auth_api import AuthAPICommunicationError
from n6lib.common_helpers import exiting_on_exception
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class n6QueueProcessingException(Exception):
    pass


class n6AMQPCommunicationError(Exception):
    pass


class QueuedBase(object):

    """
    Base class for n6 components that communicate through AMQP queues.

    Child classes should define the following class attributes:

    * `input_queue` and/or
    * `output_queue`

    -- to get respective queues configured.

    Each of them should either be None or an appropriate collection:

    * input_queue should be a dict:
      {
        "exchange": "<name of exchange to connect to>",
        "exchange_type": "<type of exchange>",
        "queue_name": "<name of queue to connect to>",
        "binding_keys": <list of routing keys to bind to>,
        "queue_exclusive": True|False,  # is queue exclusive (optional)
      }

    * output_queue should be a dict or a list of such dicts -- each like:
      {
        "exchange": "<name of exchange to connect to>",
        "exchange_type": "<type of exchange>",
      }

    These two attributes are automatically deep-copied before being
    transformed into instance-specific attributes (then adjusted
    per-instance, see: __new__() and preinit_hook()...).

    QueuedBase should handle unexpected interactions with RabbitMQ
    such as channel and connection closures.

    Dev note: if child classes are defining __init__(), it should accept
    **kwargs and call super(ChildClass, self).__init__(**kwargs)
    """

    #
    # Basic attributes

    CONNECTION_ATTEMPTS = 600
    CONNECTION_RETRY_DELAY = 10
    SOCKET_TIMEOUT = 3.0

    # the name of the config section the RabbitMQ settings shall be taken from
    rabbitmq_config_section = 'rabbitmq'

    # (see: the __new__() class method below)
    input_queue = None
    output_queue = None

    # if a script should run only in one instance - used to set basic_consume(exclusive=) flag
    single_instance = True

    # in a subclass, it should be set to False if the component should not
    # accept --n6recovery argument option (see: the get_arg_parser() method)
    supports_n6recovery = True

    # it is set on a new instance by __new__() (which is called
    # automatically before __init__()) to an argparse.Namespace instance
    cmdline_args = None

    #  parameter prefetch_count
    #  Specifies a prefetch window in terms of whole messages.
    #  This field may be used in combination with the prefetch-size field
    #  (although the prefetch-size limit is not implemented
    #  yet in RabbitMQ). A message will only be sent in advance
    #  if both prefetch windows (and those at the channel
    #  and connection level) allow it. The prefetch-count is ignored
    #  if the no-ack option is set.
    prefetch_count = 20

    # basic kwargs for pika.BasicProperties (message-publishing-related)
    basic_prop_kwargs = {'delivery_mode': 2}

    # (in seconds)
    reconnect_delay = 5


    #
    # Pre-init methods

    # (for historical reasons we do not want to place these operations
    # in __init__() -- mainly because __init__() is skipped in several
    # unit tests...)

    def __new__(cls, **kwargs):
        """
        Create and pre-configure an instance.

        Normally, this special method should not be overridden in
        subclasses. (If you really need that please *extend* it by
        overridding and calling with super()).

        The method causes that immediately after creating of a
        QueuedBase-derived class instance -- before calling __init__()
        -- the following operations are performed on the instance:

        1) (re)-making the `input_queue` and `output_queue` attributes
           as instance ones -- by deep-copying them (so they are
           exclusively owned by the instance and not by the class or any
           of its superclasses); note: whereas `input_queue` (both as
           the class attribute and the resultant instance attribute)
           should always be a dict (unless None), the `output_queue`
           *instance* attribute must always be a list of dicts (unless
           None) -- i.e.: if the `output_queue` *class* attribute is a
           dict the resultant *instance* attribute will be a one-element
           list (containing a deep copy of that dict);

        2) the get_arg_parser() method is called to obtain the argument
           parser object;

        3) the parse_known_args() method of the obtained argument parser
           is called and the obtained command-line argument container
           (produced by the argument parser as a argparse.Namespace
           instance) is set as the `cmdline_args` attribute.

        4) the preinit_hook() method is called (see its docs...).
        """
        # some unit tests are over-zealous about patching super()
        from __builtin__ import super

        self = super(QueuedBase, cls).__new__(cls, **kwargs)

        if cls.input_queue is not None and not isinstance(self.input_queue, dict):
            raise TypeError('The `input_queue` class attribute must be a dict or None')
        self.input_queue = copy.deepcopy(cls.input_queue)

        if cls.output_queue is not None and not (
                isinstance(self.output_queue, dict) or
                isinstance(self.output_queue, list) and all(
                    isinstance(item, dict) for item in self.output_queue)):
            raise TypeError('The `output_queue` class attribute must be '
                            'a dict or a list of dicts, or None')
        output_queue = copy.deepcopy(cls.output_queue)
        if isinstance(output_queue, dict):
            output_queue = [output_queue]
        self.output_queue = output_queue

        self.cmdline_args = self.parse_cmdline_args()
        self.preinit_hook()
        return self

    def parse_cmdline_args(self):
        """
        Parse commandline arguments (taken from sys.argv[1:]).

        Returns:
            An argparse.Namespace instance containing parsed commandline
            arguments.

        Unrecognized commandline arguments starting with the 'n6' text
        prefixed by one or more '-' (hyphen) characters (such as
        '-n6recovery' or '--n6blahblah'...) cause the SystemExit
        exception with exit code 2; other unrecognized commandline
        arguments are ignored.

        This method is automatically called after instance creation,
        before __init__() is called (see the docs of __new__()).

        This method *should not* be overridden completely; instead, it
        can be *extended* (overridden + called with super()).
        """
        arg_parser = self.get_arg_parser()
        cmdline_args, unknown = arg_parser.parse_known_args()
        illegal_n6_args = [arg for arg in unknown if re.match(r'\-+n6', arg)]
        if illegal_n6_args:
            arg_parser.error('unrecognized n6-specific arguments: {0}'.format(
                ', '.join(illegal_n6_args)))
        return cmdline_args

    def get_arg_parser(self):
        """
        Make and configure argument parser.

        Returns:
            An argparse.ArgumentParser instance.

        This method is automatically called after instance creation,
        before __init__() is called (see the docs of __new__() and
        parse_cmdline_args()).

        This method *should not* be overridden completely; instead, it
        can be *extended* (overridden + called with super()).

        The default implementation of this method adds to the created
        argument parser the possibility to run (from the command line)
        parsers/collectors/other components that inherit from the
        QueuedBase class -- with the "--n6recovery" parameter; it will
        cause that the standard implementation of the preinit_hook()
        method will add the '_recovery' suffix to all AMQP exchange
        and queue names.

        To prevent this method from providing the "--n6recovery"
        parameter, set the `supports_n6recovery` class attribute to
        False.
        """
        arg_parser = N6ArgumentParser()
        if self.supports_n6recovery:  # <- True by default
            arg_parser.add_argument('--n6recovery',
                                    action='store_true',
                                    help=('add the "_recovery" suffix to '
                                          'all AMQP exchange/queue names'))
        return arg_parser

    def preinit_hook(self):
        """
        Adjust some attributes after instance creation, before __init__() call.

        This method is automatically called after instance creation,
        before __init__() is called (see: the docs of __new__()).

        This method *should not* be overridden completely; instead,
        it can be *extended* (overridden + called with super()).

        The default implementation of this method checks whether
        self.cmdline_args.n6recovery is set to true; if it is then the
        '_recovery' suffix is added to AMQP exchange and queue names
        in the `input_queue` and `output_queue` instance attributes
        (it is needed to perform data recovery from MongoDB...).
        """
        if not self.supports_n6recovery or not self.cmdline_args.n6recovery:
            return
        suffix = '_recovery'
        assert ('input_queue' in vars(self) and   # __new__() ensures
                'output_queue' in vars(self))     # that this is true
        queue_conf_dicts = []
        if self.input_queue is not None:
            assert isinstance(self.input_queue, dict)   # it's dict
            queue_conf_dicts.append(self.input_queue)   # so using .append
        if self.output_queue is not None:
            assert isinstance(self.output_queue, list)  # it's list of dicts
            queue_conf_dicts.extend(self.output_queue)  # so using .extend
        for conf_dict in queue_conf_dicts:
            for key in ('exchange', 'queue_name'):
                if key in conf_dict:
                    conf_dict[key] += suffix


    #
    # Actual initialization

    def __init__(self, **kwargs):
        super(QueuedBase, self).__init__(**kwargs)

        LOGGER.debug('input_queue: %r', self.input_queue)
        LOGGER.debug('output_queue: %r', self.output_queue)

        self._connection = None
        self._channel_in = None
        self._channel_out = None
        self._num_queues_bound = 0
        self._declared_output_exchanges = set()
        self.output_ready = False
        self.waiting_for_reconnect = False
        self._closing = False
        self._consumer_tag = None
        self._conn_params_dict = self.get_connection_params_dict()


    #
    # Utility static methods

    @classmethod
    def get_connection_params_dict(cls):
        """
        Get the AMQP connection parameters (as a dict)
        using n6lib.amqp_helpers.get_amqp_connection_params_dict()
        and the `CONNECTION_ATTEMPTS`, `CONNECTION_RETRY_DELAY` and
        `SOCKET_TIMEOUT` class constants.

        Returns:
            A dict that can be used as **kwargs for pika.ConnectionParameters.
        """
        conn_params_dict = get_amqp_connection_params_dict(cls.rabbitmq_config_section)
        conn_params_dict.update(
                connection_attempts=cls.CONNECTION_ATTEMPTS,
                retry_delay=cls.CONNECTION_RETRY_DELAY,
                socket_timeout=cls.SOCKET_TIMEOUT,
        )
        return conn_params_dict


    #
    # Regular instance methods

    # Start/stop-related stuff:

    def run(self):
        """Connecting to RabbitMQ and start the IOLoop (blocking on it)."""
        self.update_connection_params_dict_before_run(self._conn_params_dict)
        try:
            self._connection = self.connect()
            self._connection.ioloop.start()
        finally:
            # note: in case of SIGINT/KeyboardInterrupt it is important
            # that `self._publishing_generator` is closed *before* the
            # pika IO loop is re-started with `stop()` [sic] -- to
            # avoid the risk described in the last-but-one paragraph
            # of `publish_output_and_iter_until_sent()`s docstring
            self._ensure_publishing_generator_closed()

    def update_connection_params_dict_before_run(self, params_dict):
        """
        A hook that can be implemented in subclasses.

        Args/kwargs:
            `params_dict`:
                The AMQP connection params dict. Custom implementations
                of this method are expected to update this dict in-place.
        """

    ### XXX... (TODO: analyze whether it is correct...)
    def stop(self):
        """
        Quote from pika docs:

        '''
        Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then closing the channel and
        connection. The IOLoop is started again because this method is invoked
        when CTRL-C is pressed raising a KeyboardInterrupt exception. This
        exception stops the IOLoop which needs to be running for pika to
        communicate with RabbitMQ. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.
        '''
        """
        LOGGER.debug('Stopping')
        self.inner_stop()
        self._connection.ioloop.start()
        LOGGER.info('Stopped')

    ### XXX... (TODO: analyze whether it is correct...)
    def inner_stop(self):
        self._closing = True
        self.stop_consuming()
        self.close_channels()

    # Connection-related stuff:

    def connect(self):
        """
        From pika docs:

        This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.

        Returns:
            pika.SelectConnection
        """
        LOGGER.info('Connecting to %s', self._conn_params_dict['host'])

        return pika.SelectConnection(
                pika.ConnectionParameters(**self._conn_params_dict),
                self.on_connection_open,
                self.on_connection_error_open,
                stop_ioloop_on_close=False,
        )

    def close_connection(self):
        LOGGER.info('Closing connection...')
        self._connection.close()

    def on_connection_error_open(self, connection):
        LOGGER.critical('Could not connect to RabbitMQ after %d attempts',
                        connection.params.connection_attempts)
        sys.exit(1)

    def on_connection_open(self, connection):
        """
        From pika docs:

        This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object.

        Args:
            `connection`: pika.SelectConnection instance
        """
        LOGGER.info('Connection opened')
        self._connection.add_on_close_callback(self.on_connection_closed)
        self.open_channels()

    # WARNING: probably due to some bug in some libraries, this callback
    # may be called more than once per one connection breakage -- so this
    # callback should be idempotent (that's why the `waiting_for_reconnect`
    # flag has been introduced)
    def on_connection_closed(self, connection, reply_code, reply_text):
        """
        From pika docs:

        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        Args:
            `connection`: The closed connection obj
            `reply_code`: The server-provided reply_code if given
            `reply_text`: The server-provided reply_text if given
        """
        self._channel_in = None
        self._channel_out = None
        self.output_ready = False
        if self._closing:
            self._connection.ioloop.stop()
        else:
            if self.waiting_for_reconnect:
                # it may happen as, probably due to some bug, pika may
                # call the on_connection_closed() callback twice
                # (see: some comments in the ticket #2566)
                LOGGER.warning(
                      'Connection closed (not scheduling reopening as '
                      'it has already been scheduled!): (%s) %s',
                      reply_code, reply_text)
            else:
                LOGGER.warning(
                      'Connection closed (reopening in %s seconds): (%s) %s',
                      self.reconnect_delay, reply_code, reply_text)
                self.waiting_for_reconnect = True
                self._connection.add_timeout(self.reconnect_delay, self.reconnect)

    def reconnect(self):
        """
        From pika docs:

        Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.
        """
        self.waiting_for_reconnect = False
        self._connection.ioloop.stop()
        if not self._closing:
            self._connection = self.connect()
            self._connection.ioloop.start()

    # Channel-related stuff:

    def open_channels(self):
        """
        From pika docs (about <channel>.channel():

        Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command. When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.
        """
        LOGGER.info('Creating new channels')
        if self.input_queue is not None:
            self._connection.channel(on_open_callback=self.on_input_channel_open)
        if self.output_queue is not None:
            self._connection.channel(on_open_callback=self.on_output_channel_open)

    def close_channels(self):
        """
        From pika docs (about <channel>.close()):

        Call to close [...] by issuing the Channel.Close RPC command.
        """
        LOGGER.info('Closing the channels')
        if self._channel_in is not None:
            if self._channel_in.is_open:
                self._channel_in.close()
        if self._channel_out is not None:
            if self._channel_out.is_open:
                self._channel_out.close()

    def close_channel(self, channel_mode):
        """
        Close the channel as specified by channel_mode.

        Args:
            `channel_mode`: type of channel to close - "in" or "out"
        """
        channel = getattr(self, "_channel_%s" % channel_mode)
        if channel.is_open:
            channel.close()

    def on_input_channel_open(self, channel):
        """
        Invoked by pika when the input channel has been opened.

        Args:
            `channel`: The channel object
        """
        LOGGER.debug('Input channel opened')
        self._channel_in = channel
        self._channel_in.add_on_close_callback(self.on_channel_closed)
        self._num_queues_bound = 0
        self.setup_input_exchange()
        self.setup_dead_exchange()

    def on_output_channel_open(self, channel):
        """
        Invoked by pika when the output channel has been opened.

        Args:
            `channel`: The channel object
        """
        LOGGER.debug('Output channel opened')
        self._channel_out = channel
        self._channel_out.add_on_close_callback(self.on_channel_closed)
        self._declared_output_exchanges.clear()
        self.setup_output_exchanges()

    def on_channel_closed(self, channel, reply_code, reply_text):
        """
        From pika docs:

        Invoked by pika when a channel has been closed, e.g. when
        RabbitMQ unexpectedly closes the channel.  Channels can be closed
        e.g. if you attempt to do something that violates the protocol,
        such as re-declare an exchange or queue with different parameters.
        In this case, we'll close the connection to shutdown the object.

        Args:
            `channel`: The closed channel
            `reply_code`: The numeric reason the channel was closed
            `reply_text`: The text reason the channel was closed
        """
        log = (LOGGER.debug if reply_code in (0, 200)
               else LOGGER.warning)
        log('Channel %i has been closed: (%s) %s',
            channel, reply_code, reply_text)
        self._connection.close(
            reply_code=reply_code,
            reply_text='Because channel {0} has been closed: "{1}"'
                       .format(channel, reply_text))

    # Input-exchange/queue-related stuff:

    def setup_dead_exchange(self):
        """Setup exchange for dead letter messages (e.g., rejected messages)."""
        LOGGER.debug('Declaring dead-letter exchange')
        if self._channel_in is not None:
            self._channel_in.exchange_declare(
                self.on_dead_exchange_declared,
                "dead",
                "topic",
                durable=True)
        else:
            LOGGER.error('Dead-letter exchange cannot be declared because input channel is None')
            ## XXX: restart or what?

    def on_dead_exchange_declared(self, frame):
        """
        Called when dead letter exchange is created.

        Creates a queue to gather dead letter messages.
        """
        LOGGER.debug('Declaring dead-letter queue')
        if self._channel_in is not None:
            assert frame.channel_number == self._channel_in.channel_number
            self._channel_in.queue_declare(
                self.on_dead_queue_declared,
                "dead_queue",
                durable=True,
                auto_delete=False)
        else:
            LOGGER.error('Dead-letter queue cannot be declared because input channel is None')
            ## XXX: restart or what?

    def on_dead_queue_declared(self, method_frame):
        """
        Called when dead letter queue is created.

        Binds all keys to the queue to gather dead letter messages.
        """
        LOGGER.debug('Binding dead-letter exchange')
        if self._channel_in is not None:
            self._channel_in.queue_bind(
                self.on_bindok,
                "dead_queue",
                "dead",
                "#")
        else:
            LOGGER.error('Dead-letter queue cannot be bound because input channel is None')
            ## XXX: restart or what?

    def setup_input_exchange(self):
        """
        From pika docs:

        Setup the [input] exchange on RabbitMQ by invoking the
        Exchange.Declare RPC command. When it is complete, the
        on_input_exchange_declared method will be invoked by pika.
        """
        params = self.input_queue
        LOGGER.debug('Declaring exchange %s', params["exchange"])
        self._channel_in.exchange_declare(
            self.on_input_exchange_declared,
            params["exchange"],
            params["exchange_type"],
            durable=True)

    def on_input_exchange_declared(self, frame):
        """
        From pika docs:

        Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        Args:
            `frame`: Exchange.DeclareOk response frame
        """
        LOGGER.debug('The input exchange declared')
        if self._channel_in is not None:
            assert frame.channel_number == self._channel_in.channel_number
            self.setup_queue(self.input_queue["queue_name"])
        else:
            LOGGER.error('Input queue cannot be set up because input channel is None')
            ## XXX: restart or what?

    def setup_queue(self, queue_name):
        """
        From pika docs:

        Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declared method will
        be invoked by pika.

        Args:
            `queue_name`: The name of the queue to declare.
        """
        LOGGER.debug('Declaring queue %s', queue_name)
        self._channel_in.queue_declare(
            self.on_queue_declared,
            queue_name,
            durable=True,
            auto_delete=False,
            arguments={"x-dead-letter-exchange": "dead"})

    def on_queue_declared(self, method_frame):
        """
        From pika docs:

        Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the
        Queue.Bind RPC command. When this command is complete, the
        on_bindok method will be invoked by pika.

        Args:
            method_frame: The Queue.DeclareOk frame
        """
        LOGGER.debug('Binding %r to %r with %r',
                     self.input_queue["exchange"],
                     self.input_queue["queue_name"],
                     self.input_queue["binding_keys"])
        for binding_key in self.input_queue["binding_keys"]:
            self._channel_in.queue_bind(self.on_bindok,
                                        self.input_queue["queue_name"],
                                        self.input_queue["exchange"],
                                        binding_key)

    def on_bindok(self, unused_frame):
        """
        From pika docs:

        Invoked by pika when the Queue.Bind method has completed. At this
        point we will check if all needed bindings were created and
        start consuming after that.

        Args:
            unused_frame: The Queue.BindOk response frame
        """
        LOGGER.debug('Queue bound')
        self._num_queues_bound += 1
        # note: the dead-letter queue is also bound -- that's why we have `+ 1` below:
        if self._num_queues_bound == len(self.input_queue["binding_keys"]) + 1:
            LOGGER.debug('All queues bound (including the dead-letter queue)')
            LOGGER.debug('Setting prefetch count')
            self._channel_in.basic_qos(prefetch_count=self.prefetch_count)
            self.start_consuming()

    def start_consuming(self):
        """
        From pika docs:

        This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if
        RabbitMQ cancels the consumer. It then issues the Basic.Consume
        RPC command which returns the consumer tag that is used to
        uniquely identify the consumer with RabbitMQ. We keep the value
        to use it when we want to cancel consuming. The on_message
        method is passed in as a callback pika will invoke when a
        message is fully received.
        """
        LOGGER.debug('Issuing consumer related RPC commands')
        self._channel_in.add_on_cancel_callback(self.on_consumer_cancelled)
        self._consumer_tag = self._channel_in.basic_consume(
                self.on_message,
                self.input_queue["queue_name"],
                exclusive=self.single_instance)

    def stop_consuming(self):
        """
        From pika docs:

        Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.
        """
        if self._channel_in is not None:
            LOGGER.debug('Sending a Basic.Cancel RPC command to RabbitMQ')
            self._channel_in.basic_cancel(self.on_cancelok, self._consumer_tag)
        else:
            LOGGER.warning(
                'input queue consuming cannot be cancelled properly '
                'because input channel is already None')
            ## XXX: restart or what?

    def on_cancelok(self, unused_frame):
        """
        From pika docs:

        This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer. At this point we will close the
        channel.  This will invoke the on_channel_closed method once the
        channel has been closed, which will in-turn close the
        connection.

        Args:
            `unused_frame`: The Basic.CancelOk frame
        """
        LOGGER.debug('RabbitMQ acknowledged the cancellation of the consumer')
        self.close_channel("in")

    def on_consumer_cancelled(self, method_frame):
        """
        From pika docs:

        Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        Args:
            `method_frame`: The Basic.Cancel frame
        """
        LOGGER.info('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        if self._channel_in is not None:
            self._channel_in.close()
        else:
            LOGGER.warning('input channel cannot be closed because it is already None')
            ## XXX: restart or what?

    def acknowledge_message(self, delivery_tag):
        """
        From pika docs:

        Acknowledge the message delivery from RabbitMQ by sending a Basic.Ack
        RPC method for the delivery tag.

        Args:
            `delivery_tag`: The delivery tag from the Basic.Deliver frame.
        """
        LOGGER.debug('Acknowledging message %r', delivery_tag)
        self._channel_in.basic_ack(delivery_tag)

    def nacknowledge_message(self, delivery_tag, reason, requeue=False):
        """
        Dis-acknowledge the message delivery by sending a Nack
        (RabbitMQ-specific extension of AMQP) for the delivery tag.

        Args:
            `delivery_tag`: The delivery tag from the Basic.Deliver frame.
        """
        ## FIXME?: maybe it should be INFO?
        LOGGER.debug('Not-Acknowledging message whose delivery tag is %r\n'
                     'Reason: %r\nRequeue: %r', delivery_tag, reason, requeue)
        self._channel_in.basic_nack(delivery_tag, multiple=False, requeue=requeue)

    def on_message(self, channel, basic_deliver, properties, body):
        """
        From pika docs:

        Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object
        that is passed in carries the exchange, routing key, delivery
        tag and a redelivered flag for the message. The properties
        passed in is an instance of BasicProperties with the message
        properties and the body is the message that was sent.

        Args:
            `channel`: The channel object.
            `basic_deliver`: A pika.Spec.Basic.Deliver object.
            `properties`: A pika.Spec.BasicProperties object.
            `body`: The message body.
        """
        exc_info = None
        delivery_tag = basic_deliver.delivery_tag
        routing_key = basic_deliver.routing_key
        try:
            LOGGER.debug('Received message #%r routed with key %r)',
                         delivery_tag, routing_key)
            try:
                self.input_callback(routing_key, body, properties)
            except AuthAPICommunicationError as exc:
                sys.exit(exc)
        except Exception as exc:
            # Note: catching Exception is OK here.  We *do* want to
            # catch any exception, except SystemExit, KeyboardInterrupt etc.
            event_info_msg = self._get_error_event_info_msg(exc, properties)
            LOGGER.error('Exception occured while processing message #%r%s '
                         '[%s: %r]. The message will be nack-ed...',
                         delivery_tag,
                         (' ({0})'.format(event_info_msg) if event_info_msg
                          else ''),
                         type(exc).__name__,
                         getattr(exc, 'args', exc),
                         exc_info=True)
            LOGGER.debug('Metadata of message '  ## FIXME?: maybe it should be INFO?
                         '#%r:\nrouting key: %r\nproperties: %r',
                         delivery_tag, routing_key, properties)
            LOGGER.debug('Body of message #%r:\n%r', delivery_tag, body)
            self.nacknowledge_message(delivery_tag, '{0!r} in {1!r}'.format(type(exc), self))
        except:
            # we do want to nack and requeue event on SystemExit, KeyboardInterrupt etc.
            exc_info = sys.exc_info()
            LOGGER.info('%r occured while processing message #%r. '
                        'The message will be requeued...',
                        exc_info[1],
                        delivery_tag)
            self.nacknowledge_message(delivery_tag, '{0!r} in {1!r}'.format(exc_info[1], self),
                                      requeue=True)
            # now we can re-raise the original exception
            raise exc_info[0], exc_info[1], exc_info[2]
        else:
            self.acknowledge_message(delivery_tag)
        finally:
            del exc_info

    def input_callback(self, routing_key, body, properties):
        """
        Placeholder for input_callback defined by child classes.

        Args:
            `routing_key`:
                The routing key to send the message with.
            `body`:
                The body of the message.
            `properties`:
                A pika.BasicProperties instance (which, among others, has
                the `headers` attribute -- being None or a dict of custom
                message headers).
        """
        raise NotImplementedError

    @staticmethod
    @contextlib.contextmanager
    def setting_error_event_info(rid_or_record_dict):
        """
        Set error event info (rid and optionally id) on any raised Exception.

        (For better error inspection when analyzing logs...)

        Args:
            `rid_or_record_dict`:
                Either a message rid (a string) or an event data
                (a RecordDict instance or just a dict).

        To be used in subclasses in input_callback or methods called by it.
        Some simple examples:

            event_rid = <some operations...>
            with self.setting_error_event_info(event_rid):
                <some operations that may raise errors>

            event_record_dict = <some operations...>
            with self.setting_error_event_info(event_record_dict):
                <some operations that may raise errors>
        """
        if isinstance(rid_or_record_dict, (basestring, types.NoneType)):
            event_rid = rid_or_record_dict
            event_id = None
        else:
            event_rid = rid_or_record_dict.get('rid')
            event_id = rid_or_record_dict.get('id')

        try:
            yield
        except Exception as exc:
            # see also: _get_error_event_info_msg() above
            if getattr(exc, '_n6_event_rid', None) is None:
                exc._n6_event_rid = event_rid
            if getattr(exc, '_n6_event_id', None) is None:
                exc._n6_event_id = event_id
            raise

    @staticmethod
    def _get_error_event_info_msg(exc, properties):
        # see also: setting_error_event_info() below
        msg_parts = []
        message_id = getattr(properties, 'message_id', None)
        event_rid = getattr(exc, '_n6_event_rid', None)
        event_id = getattr(exc, '_n6_event_id', None)
        # (note: message_id is often the same as rid)
        if message_id is not None and (event_rid is None or message_id != event_rid):
            msg_parts.append('AMQP message_id: {0}'.format(message_id))
        if event_rid is not None:
            msg_parts.append('event rid: {0}'.format(event_rid))
        if event_id is not None:
            msg_parts.append('event id: {0}'.format(event_id))
        return ', '.join(msg_parts)

    # Output-exchanges-related stuff:

    def setup_output_exchanges(self):
        """
        Setup all output exchanges on RabbitMQ (by invoking Exchange.Declare
        RPC commands for each of them0.  When such a command is
        completed, the on_output_exchange_declared method (with the
        `exchange` argument already bound using functools.partial) will
        be invoked by pika.
        """
        for params in self.output_queue:
            exchange = params["exchange"]
            callback = functools.partial(self.on_output_exchange_declared, exchange)
            LOGGER.debug('Declaring output exchange %r', exchange)
            self._channel_out.exchange_declare(
                callback,
                exchange,
                params["exchange_type"],
                durable=True)

    def on_output_exchange_declared(self, exchange, frame):
        """
        Args:
            `exchange`: Declared exchange name.
            `frame`: Exchange.DeclareOk response frame.
        """
        LOGGER.debug('Output exchange %r declared', exchange)
        self._declared_output_exchanges.add(exchange)
        if self._channel_out is not None:
            assert frame.channel_number == self._channel_out.channel_number
            assert isinstance(self.output_queue, list)
            if len(self._declared_output_exchanges) == len(self.output_queue):
                LOGGER.debug('All output exchanges declared')
                self.output_ready = True
                self.start_publishing()
        else:
            LOGGER.error('Cannot set up publishing because output channel is None')
            ## XXX: restart or what?

    def start_publishing(self):
        """
        Placeholder for the publishing method.

        It gets called after all output exchanges have been declared and
        are ready.  Publishers should override this method.
        """

    def publish_output(self, routing_key, body, prop_kwargs=None, exchange=None):
        """
        Publish to the (default or specified) output exchange.

        Args:
            `routing_key`:
                The routing key to send the message with.
            `body`:
                The body of the message.
            `prop_kwargs` (optional):
                Custom keyword arguments for pika.BasicProperties.
            `exchange` (optional):
                The exchange name.  If omitted, the 'exchange' value of
                the first item of the `output_queue` instance attribute
                will be used.
        """
        if self._closing:
            # CRITICAL because for a long time (since 2013-04-26!) there was a silent return here!
            LOGGER.critical('Trying to publish when the `_closing` flag is true!')
            raise RuntimeError('trying to publish when the `_closing` flag is true!')
        if not self.output_ready:
            # CRITICAL because for a long time (since 2013-04-26!) there was a silent return here!
            LOGGER.critical('Trying to publish when the `output_ready` flag is false!')
            raise RuntimeError('trying to publish when the `output_ready` flag is false!')

        if exchange is None:
            exchange = self.output_queue[0]['exchange']
        if exchange not in self._declared_output_exchanges:
            raise RuntimeError('exchange {0!r} has not been declared'.format(exchange))

        kwargs_for_properties = self.basic_prop_kwargs.copy()
        if prop_kwargs is not None:
            kwargs_for_properties.update(prop_kwargs)
        if 'headers' in kwargs_for_properties and (
              not kwargs_for_properties['headers']):
            # delete empty `headers` dict
            del kwargs_for_properties['headers']
        properties = pika.BasicProperties(**kwargs_for_properties)

        self.basic_publish(exchange=exchange,
                           routing_key=routing_key,
                           body=body,
                           properties=properties)

        # basic_publish() might trigger the on_connection_closed() callback
        if self._closing or not self.output_ready:
            raise n6AMQPCommunicationError(
                'after output channel\'s basic_publish(): _closing={0!r} '
                '(should be False) and output_ready={1!r} (should be True) '
                '-- which means that AMQP communication is no longer possible '
                'and most probably the data have not been sent '
                '(routing key: {2!r}, body length: {3})'.format(
                    self._closing, self.output_ready, routing_key, len(body)))

    def basic_publish(self, exchange, routing_key, body, properties):
        """
        Thin wrapper around pika's basic_publish -- for easier testing/mocking.

        Typically it is *not* used directly but only by calling the
        publish_output() method.
        """
        LOGGER.debug('Publishing message to %r, rk: %r\n'
                     'Properties: %s\nBody: %r',
                     exchange,
                     routing_key,
                     pprint.pformat(properties),
                     body)
        self._channel_out.basic_publish(exchange=exchange,
                                        routing_key=routing_key,
                                        body=body,
                                        properties=properties)

    @exiting_on_exception
    def start_iterative_publishing(self):
        """
        A tool to perform many *publish* actions in such a way that
        after each of them (or each not-too-long sequence of them) we
        give control back to the pika IO loop to let it perform its
        normal activities (especially dispatching the data in the pika
        connection's outbound buffer). When all of these *publish*
        actions are completed the IO loop will be shut down
        automatically.

        To use this method you typically need to:

        * implement the `start_publishing()` method so that it calls
          this method, and

        * implement the `publish_iteratively()` abstract method (as a
          generator) -- see its docstring...

        Therefore, typical usage looks like this:

            def start_publishing(self):
                self.start_iterative_publishing()

            def publish_iteratively(self):
                # here: a custom implementation -- see the
                # docstring of `publish_iteratively()`...

        """
        self._publishing_generator = self.publish_iteratively()
        self._next_publishing_iteration()

    def publish_iteratively(self):
        """
        When the `start_iterative_publishing()` method is used, this
        method should be implemented as a generator that publishes
        consecutive output messages. Each time after a message was (or
        a few messages were) published -- the generator should yield.
        Yielded values does not matter; a yield point itself is
        important because it is a place when we give control back to
        the pika IO loop.

        Any exception other than `StopIteration` propagated outside the
        generator will be transformed automatically into a `SystemExit`
        with a fatal-error-signaling status.

        When implementing this method you may want to use the
        `publish_output_and_iter_until_sent()` method -- so that you
        can have some control on when the data are actually sent.
        Especially, it can help you to: * avoid excessive memory
        consumption when data are being produced faster than the
        outbound buffer is flushed; * reduce the likelihood of
        unnoticed data loss (note, however, that even if we are sure
        that the pika connection's outbound buffer has been fully
        flushed, it does *not* guarantee that the data have really
        arrived at the broker -- for more information see the docstring
        of `publish_output_and_iter_until_sent()`...).

        Example implementation:

            def publish_iteratively(self):
                for rk, body, prop_kwargs in <some sequence or iterator...>:
                    for _ in self.publish_output_and_iter_until_sent(rk, body, prop_kwargs):
                        yield  # <- to give control back to the pika IO loop
        """
        raise NotImplementedError

    def _next_publishing_iteration(self):
        if self._closing:
            LOGGER.warning('%r is being closed so publishing is not continued', self)
            return
        try:
            next(self._publishing_generator)
        except StopIteration:
            self._schedule_after_publishing_iteration(self.inner_stop)
        else:
            self._schedule_after_publishing_iteration(self._next_publishing_iteration)

    def _schedule_after_publishing_iteration(self, callback, delay=0.1):
        if self._closing:
            LOGGER.warning('%r is being closed so %r will *not* be scheduled', self, callback)
            return
        self._connection.add_timeout(delay, exiting_on_exception(callback))

    def _ensure_publishing_generator_closed(self):
        publishing_generator = getattr(self, '_publishing_generator', None)
        if publishing_generator is not None:
            publishing_generator.close()

    def publish_output_and_iter_until_sent(self, *args, **kwargs):
        """
        Call the `publish_output()` method with the given arguments,
        then return an iterator that will continue yielding `None`
        values until the pika connection's outbound buffer is fully
        flushed (so that, when the iterator at last is exhausted we can
        assume that all output data have been sent from the point of
        view of the AMQP connection's output socket). Moreover, once
        the outbound buffer is flushed, the iterator yields one more
        time unconditionally.

        To make it possible that the iterator will finish -- you must
        *after each its step* somehow give control back to the pika IO
        loop (so that it can progressively flush the outbound buffer by
        sending the pending data).

        Usage:

            for _ in self.publish_output_and_iter_until_sent(
                  output_routing_key, output_body, output_prop_kwargs):
                # [...] here we must, somehow, give
                # control back to the pika IO loop
            # here we are sure that the pika connection's
            # outbound buffer has been fully flushed

        Beware that invasive asynchronous events, such as the standard
        SIGINT handler that raises `KeyboardInterrupt`, can break pika
        IO loop's data dispatch, i.e., it is possible that the pika
        connection's outbound buffer is fully flushed but some data
        have not been actually sent via the connection's output socket
        because `KeyboardInterrupt` (or some other asynchronously
        raised exception) interfered... Therefore you should *not*
        rely on this method *if* `KeyboardInterrupt` (or some other
        asynchronously raised exception) has interrupted the IO loop.

        Also, *note* that even the assumption that all data have been
        sent (from the point of view of the output socket) does *not*
        necessarily mean that all data have arrived at the AMQP broker
        or been safely stored/handled there. (To ensure that, RabbitMQ
        delivery confirmations would have to be used...)
        """
        outbound_buffer = self._connection.outbound_buffer
        assert isinstance(outbound_buffer, collections.deque)
        self.publish_output(*args, **kwargs)
        return self._iter_until_buffer_flushed(outbound_buffer)

    @staticmethod
    def _iter_until_buffer_flushed(outbound_buffer):
        while outbound_buffer:
            yield
        # once the buffer is emptied, let's yield one more time unconditionally
        yield

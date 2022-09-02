# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

# Note, however, that some parts of the QueuedBase class are patterned
# after some examples from the docs of a 3rd-party library: `pika`; and
# some of the docstrings are taken from or contain fragments of the
# docs of the `pika` library.

###
### [TODO] this module needs special attention during migration
###        to a new version of `pika`!...
###

from __future__ import print_function
from future.utils import raise_
import collections
import contextlib
import copy
import functools
import pprint
import re
import sys
import time

try:
    import pika
    import pika.credentials
except ImportError:
    print("Warning: pika is required to run AMQP components", file=sys.stderr)

from n6corelib.timeout_callback_manager import TimeoutCallbackManager
from n6lib.amqp_helpers import (
    PIPELINE_OPTIONAL_COMPONENTS,
    PIPELINE_OPTIONAL_GROUPS,
    get_amqp_connection_params_dict,
    get_pipeline_binding_states,
)
from n6lib.argument_parser import N6ArgumentParser
from n6lib.auth_api import AuthAPICommunicationError
from n6lib.common_helpers import (
    ascii_str,
    exiting_on_exception,
    make_exc_ascii_str,
)
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
        "accepted_event_types": <list of event types accepted by the component>,
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

    SOCKET_TIMEOUT = 3.0
    STOP_TIMEOUT = 180
    AMQP_SETUP_TIMEOUT = 60

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
        overriding and calling with super()).

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
        from builtins import super

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

        For more information about the parsing see documentation
        for the `parse_only_n6_args` method.
        """
        arg_parser = self.get_arg_parser()
        return self.parse_only_n6_args(arg_parser)

    @classmethod
    def parse_only_n6_args(cls, arg_parser):
        """
        Parse commandline arguments (taken from sys.argv[1:])
        using provided argument parser.

        Args/kwargs:
            `arg_parser`:
                An `N6ArgumentParser` instance used to parse
                the commandline arguments.

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
        cmdline_args, unknown = arg_parser.parse_known_args()
        illegal_n6_args = [arg for arg in unknown if re.match(r'\-+n6', arg)]
        if illegal_n6_args:
            arg_parser.error('unrecognized n6-specific arguments: {0}'.format(
                ', '.join(illegal_n6_args)))
        return cmdline_args

    @classmethod
    def get_arg_parser(cls):
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
        argument parser:

        * the possibility to run (from the command line)
          parsers/collectors/other components that inherit from the
          QueuedBase class -- with the "--n6input-suffix ..." and/or
          "--n6output-suffix ..." command line options; that will cause
          that the standard implementation of the preinit_hook() method
          will add an appropriate suffix to all input and/or output
          (respectively) AMQP exchange names and queue names;

        * the possibility to run (from the command line)
          parsers/collectors/other components that inherit from the
          QueuedBase class -- with the "--n6recovery" command line
          option; that will cause that the standard implementation of
          the preinit_hook() method will add the '_recovery' suffix to
          *all* (input and output) AMQP exchange names and queue names
          (that is needed to perform data recovery from MongoDB...); to
          prevent this method from providing the "--n6recovery" option,
          set the `supports_n6recovery` class attribute to False.
        """
        arg_parser = N6ArgumentParser()
        arg_parser.add_argument('--n6input-suffix',
                                metavar='SUFFIX',
                                help=('add the specified suffix to all '
                                      'input AMQP exchange/queue names'))
        arg_parser.add_argument('--n6output-suffix',
                                metavar='SUFFIX',
                                help=('add the specified suffix to all '
                                      'output AMQP exchange/queue names'))
        if cls.supports_n6recovery:  # <- True by default
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

        The default implementation of this method modifies, if needed,
        the contents of the `input_queue` and/or `output_queue`
        instance attributes accordingly to the "--n6input-suffix",
        "--n6output-suffix" and "--n6recovery" command line options
        (see: get_arg_parser()).

        Note: if both the "--n6input-suffix ..." and "--n6recovery"
        options or both the "--n6output-suffix ..." and "--n6recovery"
        options are given then the "_recovery" suffix is added as the
        rightmost one.
        """
        def add_suffix_to_queue_conf(queue_conf, suffix):
            if queue_conf is None or suffix is None:
                return
            assert isinstance(queue_conf, (dict, list))
            queue_conf_dicts = ([queue_conf] if isinstance(queue_conf, dict)
                                else queue_conf)
            for conf_dict in queue_conf_dicts:
                for key in ('exchange', 'queue_name'):
                    if key in conf_dict:
                        conf_dict[key] += suffix

        assert ('input_queue' in vars(self) and   # __new__() ensures
                'output_queue' in vars(self))     # that this is true

        add_suffix_to_queue_conf(self.input_queue,
                                 suffix=self.cmdline_args.n6input_suffix)

        add_suffix_to_queue_conf(self.output_queue,
                                 suffix=self.cmdline_args.n6output_suffix)

        if not self.supports_n6recovery or not self.cmdline_args.n6recovery:
            return

        queue_conf_dicts = []
        if self.input_queue is not None:
            assert isinstance(self.input_queue, dict)   # it's dict
            queue_conf_dicts.append(self.input_queue)   # so using .append
        if self.output_queue is not None:
            assert isinstance(self.output_queue, list)  # it's list of dicts
            queue_conf_dicts.extend(self.output_queue)  # so using .extend
        add_suffix_to_queue_conf(queue_conf_dicts, suffix='_recovery')


    #
    # Actual initialization

    def __init__(self, **kwargs):
        super(QueuedBase, self).__init__(**kwargs)

        LOGGER.debug('input_queue: %r', self.input_queue)
        LOGGER.debug('output_queue: %r', self.output_queue)

        self.clear_amqp_communication_state_attributes()
        self.configure_pipeline()
        self._conn_params_dict = self.get_connection_params_dict()
        self._amqp_setup_timeout_callback_manager = \
            self._make_timeout_callback_manager('AMQP_SETUP_TIMEOUT')

    def configure_pipeline(self):
        """
        Place the component inside the pipeline, by creating
        binding keys, which are used to determine which component's
        output messages should be bound to the input queue
        of currently initialized component.

        If the component is configured in the pipeline config,
        special keywords called "states" will be used to create
        unique binding keys, joining one component's output
        to other component's input. If no configuration
        could be found, the method will look for a "hard-coded"
        list of binding keys in the `input_queue` attribute.

        Usually, each binding key is composed of four sections,
        where the first section defines accepted types of
        events, second section is the "state", and the last two
        contain wildcards, matching all events originally routed
        with keys consisting of `source` and `channel` part,
        separated by dot.

        Previously, the `input_queue` dict - a class attribute
        (which has been transformed to an instance attribute) of
        the component contained the `binding_keys` key, a fixed
        list of input queue's binding keys of the component. Now,
        the `binding_keys` list is generated using
        the `accepted_event_types` list and the list of "binding
        states" defined in pipeline configuration.

        A different binding key is created for every "state".
        Sample binding key: *.{state}.*.*, where {state} is
        a "state" defined in the pipeline config. The behaviour
        differs for such components as collectors, parsers
        or DBarchiver - see their docstrings for more details.

        If the `accepted_event_types` item of the `input_queue`
        attribute is defined, it specifies the types of events,
        the component should bind to. Otherwise, the component
        will bind to all event types (the asterisk wildcard).

        The pipeline config should be defined in the `pipeline`
        section by default. Each component is configured through
        the option, that is the component's lowercase class' name;
        its values should be a list of "binding states", separated
        by a comma, that will be used to create component's
        binding keys, e.g. for the Enricher the config will look like:

        [pipeline]
        enricher = somestate, otherstate

        Considering that Enricher has a following list of the
        `accepted_event_types`:

        ['event', 'bl', 'bl-update', 'suppressed']

        Then the list of resulting binding keys for the Enricher
        will be:

        ['event.somestate.*.*', 'bl.somestate.*.*',
        'bl-update.somestate.*.*', 'suppressed.somestate.*.*',
        'event.otherstate.*.*', 'bl.otherstate.*.*',
        'bl-update.*.*', 'suppressed.otherstate.*.*']

        These "binding states" are parts of routing keys of messages
        received by the component, that identify the component
        which sent them. E.g., parsers send their messages with
        routing keys using the format:
        <event type>.parsed.<source label>.<source channel>
        The second part of the routing key - "parsed" is
        characteristic for parsers, being their "binding state".
        If you want other component to receive messages from parsers,
        then "parsed" should be on the list of values bound to
        the option being the component's ID. So, for the Enricher
        to receive this type of messages, it should have configuration
        like:

        [pipeline]
        enricher = parsed

        Each component is also bound to some group of components,
        the `utils` group by default. Collectors are bound
        to the `collectors` group and parsers - to `parsers`.
        The "binding states" can be defined for a whole group.
        The group's config will be used, in case, there is no config
        for a component. Otherwise, a component's specific config
        option has the priority over the group's option.

        SEE: configuration template file with the "pipeline" section
        for more examples.
        """
        if self.input_queue is not None:
            self.set_queue_name()
            pipeline_group, pipeline_name = self.get_component_group_and_id()
            binding_states = get_pipeline_binding_states(pipeline_group, pipeline_name)
            if binding_states:
                assert(isinstance(binding_states, list))
                accepted_event_types = self.input_queue.get('accepted_event_types')
                if (accepted_event_types is not None and
                        not isinstance(accepted_event_types, list)):
                    raise TypeError('The `accepted_event_types` key of the `input_queue` dict, '
                                    'if present and set, should be a list')
                self.make_binding_keys(binding_states, accepted_event_types)
            # if there is no pipeline configuration for the component,
            # check if binding keys have been manually set in
            # the `input_queue` attribute
            elif ('binding_keys' in self.input_queue and
                    self.input_queue['binding_keys'] is not None):
                if not isinstance(self.input_queue['binding_keys'], list):
                    raise TypeError('The `binding_keys` item of the `input_queue` attribute, '
                                    'if manually set, has to be a list')
            elif (pipeline_name not in PIPELINE_OPTIONAL_COMPONENTS and
                  pipeline_group not in PIPELINE_OPTIONAL_GROUPS):
                LOGGER.warning('The component `%s` is not configured in the pipeline '
                               'config and the list of binding keys is not defined '
                               'in the `input_queue` attribute. If the `input_queue` '
                               'attribute is set, the list of binding keys should be '
                               'defined', pipeline_name)
                self.input_queue['binding_keys'] = []

    def set_queue_name(self):
        """
        The hook that should be implemented by subclasses, which does
        not have explicitly defined input queue's name, like
        IntelMQ bots.
        """

    def get_component_group_and_id(self):
        """
        Get component's group name and its ID. These values are used
        for the pipeline configuration mechanism.

        Pipeline configuration-related methods search for these names
        among the options of the `pipeline` config section.

        If the component's ID or its group name is found in
        the section, the list of values will be used as component's
        'binding states'. Then these 'binding states' are used
        to generate binding keys for component's input queue.

        The method should be overridden in subclasses of components
        of different groups, such as collectors or parsers.

        Returns:
            A tuple of component's group name and its ID.
        """
        return 'utils', self.__class__.__name__.lower()

    def make_binding_keys(self, binding_states, accepted_event_types):
        if not accepted_event_types:
            accepted_event_types = ['*']
        self.input_queue['binding_keys'] = []
        for state in binding_states:
            for event_type in accepted_event_types:
                self.input_queue['binding_keys'].append(
                    '{type}.{state}.*.*'.format(type=event_type, state=state))

    def clear_amqp_communication_state_attributes(self):
        self._connection = None
        self._channel_in = None
        self._channel_out = None
        self._num_queues_bound = 0
        self._declared_output_exchanges = set()
        self.output_ready = False
        self._closing = False
        self._consumer_tag = None
        LOGGER.debug('AMQP communication state attributes cleared')


    #
    # Utility static methods

    @classmethod
    def get_connection_params_dict(cls):
        """
        Get the AMQP connection parameters (as a dict)
        using n6lib.amqp_helpers.get_amqp_connection_params_dict()
        and the `SOCKET_TIMEOUT` class constant.

        Returns:
            A dict that can be used as **kwargs for pika.ConnectionParameters.
        """
        conn_params_dict = get_amqp_connection_params_dict(cls.rabbitmq_config_section)
        conn_params_dict.update(
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
            try:
                self._connection = self.connect()
                self._connection.ioloop.start()
            finally:
                self._amqp_setup_timeout_callback_manager.deactivate()
        finally:
            # note: in case of SIGINT/KeyboardInterrupt it is important
            # that `self._publishing_generator` is closed *before* the
            # pika IO loop is re-started by `stop()` [sic] -- to avoid
            # the risk described in the last-but-one paragraph of the
            # `publish_iteratively()`s docstring
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
        with self._make_timeout_callback_manager('STOP_TIMEOUT'):
            self._connection.ioloop.start()
        LOGGER.info('Stopped')

    ### XXX... (TODO: analyze whether it is correct...)
    def inner_stop(self):
        self._closing = True
        self.stop_consuming()
        self.close_channels()

    def _make_timeout_callback_manager(self, timeout_attribute_name):
        timeout = getattr(self, timeout_attribute_name)
        timeout_expiry_msg = '{}.{}={!r} expired!'.format(self.__class__.__name__,  #3: `__name__` -> `__qualname__`
                                                          timeout_attribute_name,
                                                          timeout)
        return TimeoutCallbackManager(timeout, sys.exit, timeout_expiry_msg)

    def _is_input_ready_or_none(self):
        return (self._consumer_tag is not None or
                self.input_queue is None)

    def _is_output_ready_or_none(self):
        return (self.output_ready or
                self.output_queue is None)


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
        LOGGER.info('Connecting to %s', ascii_str(self._conn_params_dict['host']))
        if self.input_queue is not None or self.output_queue is not None:
            self._amqp_setup_timeout_callback_manager.deactivate()
            self._amqp_setup_timeout_callback_manager.activate()
        return pika.SelectConnection(
                pika.ConnectionParameters(**self._conn_params_dict),
                self.on_connection_open,
                self.on_connection_error_open,
                stop_ioloop_on_close=True,
        )

    def close_connection(self):
        LOGGER.info('Closing connection...')
        self._connection.close()

    def on_connection_error_open(self, connection, error_message='<not given>'):
        error_message = ascii_str(error_message)
        # in case logging via AMQP does not work...
        print('Could not connect to RabbitMQ. Reason: {}.'.format(error_message),
              file=sys.stderr)
        LOGGER.critical('Could not connect to RabbitMQ. Reason: %s', error_message)
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

    def on_connection_closed(self, connection, reply_code, reply_text):
        """
        From pika docs:

        This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. [...]

        Args:
            `connection`: The closed connection obj
            `reply_code`: The server-provided reply_code if given
            `reply_text`: The server-provided reply_text if given
        """
        reply_text = ascii_str(reply_text)
        self._closing = True
        self._channel_in = None
        self._channel_out = None
        self._consumer_tag = None
        self.output_ready = False
        if reply_code in (0, 200):
            LOGGER.info('AMQP connection has been closed with code: %s. Reason: %s',
                        reply_code, reply_text)
        else:
            # in case logging via AMQP does not work, let's additionally
            # print this error message to the standard error output
            print('Error: AMQP connection has been closed with code: {}. '
                  'Reason: {}.'.format(reply_code, reply_text),
                  file=sys.stderr)
            LOGGER.error('AMQP connection has been closed with code: %s. Reason: %s',
                         reply_code, reply_text)
            sys.exit(1)


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
        channel_str = ascii_str(channel)
        reply_text = ascii_str(reply_text)
        log = (LOGGER.debug if reply_code in (0, 200)
               else LOGGER.warning)
        log('Channel %s has been closed: (%s) %s',
            channel_str, reply_code, reply_text)
        self._connection.close(
            reply_code=reply_code,
            reply_text='Because channel {0} has been closed: "{1}"'
                       .format(channel_str, reply_text))

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
        LOGGER.debug('Declaring exchange %r', params["exchange"])
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
        LOGGER.debug('Declaring queue %r', queue_name)
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
        if not self.input_queue['binding_keys']:
            LOGGER.warning('The list of binding keys is empty for a queue %r.',
                           self.input_queue['queue_name'])
        else:
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
            self.complete_input_setup()

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

    def complete_input_setup(self):
        if self._is_output_ready_or_none():
            self._amqp_setup_timeout_callback_manager.deactivate()

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
        if not self._is_output_ready_or_none():
            LOGGER.warn('Message received from the input_queue while the'
                        'output queue has not been yet set up. '
                        '[%s:%s] The message will be requeueud.',
                        delivery_tag,
                        routing_key)

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
            raise_(exc_info[0], exc_info[1], exc_info[2])
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
        if rid_or_record_dict is None:
            event_rid = event_id = None
        elif isinstance(rid_or_record_dict, str):
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
                self.complete_output_setup()
                self.start_publishing()
        else:
            LOGGER.error('Cannot set up publishing because output channel is None')
            ## XXX: restart or what?

    def complete_output_setup(self):
        if self._is_input_ready_or_none():
            self._amqp_setup_timeout_callback_manager.deactivate()

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
                     ascii_str(pprint.pformat(properties)),
                     body)
        self._channel_out.basic_publish(exchange=exchange,
                                        routing_key=routing_key,
                                        body=body,
                                        properties=properties)


    #
    # *Iterative publishing* mechanism

    # To learn about this mechanism, first read the docstrings of
    # the `start_iterative_publishing()` and `publish_iteratively()`
    # methods (see below)...

    # A marker to be yielded (instead of `None`) by `publish_iteratively()`
    # to signal that we want to flush unconditionally the pika connection's
    # outbound buffer.
    FLUSH_OUT = 'FLUSH_OUT'

    # When the size (in bytes) of the pika connection's outbound buffer
    # reaches the value of this attribute then a full flush of the
    # buffer is to be performed automatically on the next yield from
    # `publish_iteratively()` (even if `FLUSH_OUT` was not yielded).
    # This attribute can be overridden in subclasses, however the
    # default value (10 000 000 bytes == 10 MB) should be appropriate
    # in most cases.
    iterative_publishing_outbound_buffer_size_threshold = 10 ** 7

    # When a `yield` causes that the control is given to the pika
    # connection's IO loop for a moment -- this value defines the
    # scheduled duration of that "moment"; the default value (one
    # tenth of a second) should be appropriate in most cases.
    iterative_publishing_schedule_next_delay = 0.1

    # These two attributes can be used in subclasses to customize
    # exception handling by the *iterative publishing* machinery
    # -- see:
    # * `publish_iteratively()` (below);
    # * `n6lib.common_helpers.exiting_on_exception()`.
    iterative_publishing_exc_factory = SystemExit
    iterative_publishing_exc_message_pattern = ('ERROR during iterative publishing: '
                                                '{exc_info[0].__name__!r}: {exc_info[1]!r} '
                                                '(DEBUG INFO: {condensed_debug_msg})')

    def start_iterative_publishing(self):
        """
        *Iterative publishing* is a mechanism of performing *publish*
        actions (i.e., `publish_output()` calls) -- possibly many of
        them -- in such a way that after each not-too-long sequence of
        those actions the control can be given to the pika connection's
        IO loop to let it perform its normal activities (in particular,
        dispatching the data remaining in the connection's outbound
        buffer).

        Thanks to the *iterative publishing* mechanism it is possible:

        * to avoid excessive memory consumption when data are produced
          faster than the pika connection's outbound buffer is flushed
          (see the comment above the `QueuedBase`'s attribute
          `iterative_publishing_outbound_buffer_size_threshold`);

        * to avoid "starving" the pika connection's IO loop (and,
          consequently, to avoid exceeding the pika connection's
          `heartbeat_interval` timeout; the value of the actual
          `heartbeat_interval` is automatically taken into
          consideration);

        * if needed -- to manually force flushing out the pika
          connection's outbound buffer; it is important to do it
          *before* "ticking off" some input data as properly handled,
          e.g., *before* saving state that confirms that some data has
          been processed and published successfully (to learn more --
          read the paragraphs of the `publish_iteratively()` docstring
          about yielding `self.FLUSH_OUT` and flushing the outbound
          buffer...).


        Note: the *iterative publishing* mechanism cannot be used with
        `QueuedBase` classes that have `input_queue` set to anything
        but `None` -- therefore it can be used mostly with collectors
        (at least for now; this limitation may be lifted in the future).


        To use the *iterative publishing* mechanism you need to:

        * implement the `start_publishing()` method so that it calls
          this (`start_iterative_publishing()`) method, *and*

        * implement the `publish_iteratively()` abstract method (as a
          generator) -- see its docstring...

        Therefore, typical usage looks like this:

            def start_publishing(self):
                self.start_iterative_publishing()

            def publish_iteratively(self):
                # here: a custom implementation -- see the
                # docstring of `publish_iteratively()`...
        """
        if self.input_queue is not None:
            # (the mechanism implemented by `_iter_until_buffer_flushed()`
            # is, most probably, *not* compatible with async input handling
            # -- because obtaining such a state that the pika connection's
            # outbound buffer is empty may become hard to achieve when
            # input traffic is high...)
            raise NotImplementedError('*iterative publishing* cannot be used '
                                      'when `input_queue` is not None')
        self._publishing_generator = self._do_publish_iteratively()
        self._schedule_next(self._next_publishing_iteration)

    def publish_iteratively(self):
        """
        An abstract method: the generator that implements the concrete
        (subclass-customizable) part of *iterative publishing*.

        If the *iterative publishing* mechanism is used (i.e., if the
        `start_iterative_publishing()` method is called in
        `start_publishing()`), the `publish_iteratively()` method
        should be implemented as a generator that executes a `yield`
        statement after each `publish_output()` call (or after a small
        number of such calls).  The `yield` statement defines the
        moment when the control *may* be given back (by the underlying
        machinery of *iterative publishing*) to the pika connection's
        IO loop.

        The `yield` statement should have one of the following forms:

        * `yield` (or `yield None` which is equivalent),
        * `yield self.FLUSH_OUT` (see below...).

        Any exception propagated beyond the generator's `next()` (other
        than `StopIteration`, `SystemExit` or `KeyboardInterrupt`) will
        be transformed automatically into an exception constructed with
        the callable specified as the `iterative_publishing_exc_factory`
        attribute (whose default value is `SystemExit`), with a message
        whose content is based on the formattable pattern specified as
        the `iterative_publishing_exc_message_pattern` attribute (whose
        default value should be sufficient in nearly all cases).

        Example implementation of `publish_iteratively()`:

            def publish_iteratively(self):
                for foo in self._generate_many_foo():
                    output_components = self.get_output_components(foo=foo)
                    self.publish_output(*output_components)
                    yield

        Note that there is *no* explicit call of `inner_stop()` (under
        the hood, it is called by the *iterative publishing* machinery,
        when needed).

        There is also a possibility to manually force flushing out the
        pika connection's outbound buffer -- by yielding the special
        marker: `self.FLUSH_OUT`; when it is yielded then the machinery
        of *iterative publishing* not only gives the control to the
        connection's IO loop for a moment, but also continues "pinging"
        the IO loop until its outbound buffer is fully flushed; so
        that, when the control is -- at last -- given back to our
        `publish_iteratively()` generator (at the point directly after
        our `yield self.FLUSH_OUT` statement), we can assume that all
        output data have been sent (from the point of view of the AMQP
        connection's output socket), *provided that* the control has
        been given back normally, i.e., *not* by throwing an exception
        (such as `GeneratorExit` -- which is thrown into the generator
        when the `close()` generator method is called from outside;
        that may be caused by connection breakage, receiving a SIGINT
        [ctrl+c], or some other exceptional condition...).

            def publish_iteratively(self):
                for foo in self._generate_many_foo():
                    output_components = self.get_output_components(foo=foo)
                    self.publish_output(*output_components)
                    yield self.FLUSH_OUT
                    # we can assume that *output_components* have been sent
                    self.some_action_to_be_done_after_successful_publish()

        Note that yielding `self.FLUSH_OUT` at the end of the body of
        the `publish_iteratively()` implementation is *not necessary*
        because the connection's outbound buffer is automatically
        flushed after the `publish_iteratively()` generator exits
        (of course, provided there is no connection error or other
        exceptional condition).

        *Beware* that invasive asynchronous events, such as handling a
        SIGINT by the standard handler that raises `KeyboardInterrupt`,
        can break pika IO loop's data dispatch, i.e., it is possible
        that the pika connection's outbound buffer appears to be fully
        flushed but some data have *not* been actually sent via the
        connection's output socket -- because `KeyboardInterrupt` (or
        some other asynchronously raised exception) interfered...
        Therefore, in case of IO loop interruption caused by
        `KeyboardInterrupt` (or by another invasive asynchronous event)
        you should *not* ack or tick off your data as handled properly.

        Also, *note* that even the assumption that all data have been
        sent (from the point of view of the output socket) does *not*
        necessarily mean that all data have arrived at the AMQP broker
        and been safely stored/handled there.  (To ensure that,
        RabbitMQ delivery confirmations would have to be used...
        Maybe we will implement their support in the future, but for
        now we must cope without them).
        """
        raise NotImplementedError


    class __PublishingGeneratorCleanExit(BaseException): pass
    class __PublishingGeneratorDirtyExit(BaseException): pass

    # noinspection PyBroadException
    def _ensure_publishing_generator_closed(self):
        publishing_generator = getattr(self, '_publishing_generator', None)
        if publishing_generator is None:
            return

        CleanExit = self.__PublishingGeneratorCleanExit
        DirtyExit = self.__PublishingGeneratorDirtyExit

        def close_publishing_generator():
            pub_gen_exit_exc_type = (DirtyExit if is_present(to_be_raised_exc_info)
                                     else CleanExit)
            try:
                publishing_generator.throw(pub_gen_exit_exc_type)
            except (StopIteration, pub_gen_exit_exc_type):
                LOGGER.debug('OK, the publishing generator exited.')
            else:
                raise AssertionError(
                    'this should never happen: although {} was thrown into '
                    'the publishing generator, it (even then!) did *not* '
                    'exited!'.format(pub_gen_exit_exc_type.__name__))

        def is_heavier_than_one_to_be_raised(exc_info):
            if is_keyb_interrupt(exc_info) and not is_keyb_interrupt(to_be_raised_exc_info):
                return True
            if is_heavy(exc_info) and not is_heavy(to_be_raised_exc_info):
                return True
            if is_present(exc_info) and not is_present(to_be_raised_exc_info):
                return True
            return False

        def is_keyb_interrupt(exc_info):
            return (is_present(exc_info)
                    and issubclass(exc_info[0], KeyboardInterrupt))

        def is_heavy(exc_info):
            return (is_present(exc_info)
                    and issubclass(exc_info[0], BaseException)
                    and not issubclass(exc_info[0], Exception))

        def is_present(exc_info):
            return exc_info[0] is not None

        def is_to_be_raised(exc_info):
            return (exc_info[0] is to_be_raised_exc_info[0] and
                    exc_info[1] is to_be_raised_exc_info[1])

        def log_inner_exc():
            assert is_present(inner_exc_info)
            if is_present(outer_exc_info):
                if is_to_be_raised(inner_exc_info):
                    LOGGER.error(
                        'This exception occurred when trying to close the '
                        'publishing generator: %s -- it will supersede the '
                        'exception that has already been being handled: %s. '
                        'Traceback of the superseded exception:',
                        make_exc_ascii_str(inner_exc_info),
                        make_exc_ascii_str(outer_exc_info),
                        exc_info=outer_exc_info)
                else:
                    assert is_to_be_raised(outer_exc_info)
                    LOGGER.error(
                        'This exception occurred when trying to close the '
                        'publishing generator: %s -- to be superseded by the '
                        'exception that has already been being handled: %s. '
                        'Traceback of the superseded exception:',
                        make_exc_ascii_str(inner_exc_info),
                        make_exc_ascii_str(outer_exc_info),
                        exc_info=inner_exc_info)
            else:
                assert is_to_be_raised(inner_exc_info)
                LOGGER.error(
                    'This exception occurred when trying to close the '
                    'publishing generator: %s -- to be propagated...',
                    make_exc_ascii_str(inner_exc_info))

        def log_unlikely_exception_from_insisted_close(exc_info):
            assert is_present(disruptive_exc_info)
            LOGGER.critical(
                'Yet another (unexpected) exception occurred, while handling '
                'the previous disruptive exception, when trying to close the '
                'publishing generator: %s -- to be superseded by that '
                'previous disruptive exception: %s. Traceback of the '
                'superseded exception:',
                make_exc_ascii_str(exc_info),
                make_exc_ascii_str(disruptive_exc_info),
                exc_info=exc_info)

        def log_disruptive_exc():
            assert is_present(disruptive_exc_info)
            if is_to_be_raised(disruptive_exc_info):
                LOGGER.error(
                    'This disruptive exception occurred while trying to deal '
                    'with (probably not clean) shutdown of the publishing '
                    'generator: %s -- to be propagated...',
                    make_exc_ascii_str(disruptive_exc_info))
            else:
                assert is_present(to_be_raised_exc_info)
                LOGGER.error(
                    'This disruptive exception occurred while trying to deal '
                    'with (not clean) shutdown of the publishing generator: '
                    '%s -- to be superseded by the exception that has already '
                    'been being handled: %s. Traceback of the superseded '
                    'exception:',
                    make_exc_ascii_str(disruptive_exc_info),
                    make_exc_ascii_str(to_be_raised_exc_info),
                    exc_info=disruptive_exc_info)

        try:
            to_be_raised_exc_info = outer_exc_info = sys.exc_info()
            try:
                try:
                    close_publishing_generator()
                except:
                    inner_exc_info = sys.exc_info()
                    if is_heavier_than_one_to_be_raised(inner_exc_info):
                        to_be_raised_exc_info = inner_exc_info
                    log_inner_exc()
            except:
                # As a result of a bug or some asynchronous event (SIGINT?)
                # an exception has been raised within the above `try` block
                # but *not* within the inner `try` block (most probably, it
                # happened within the inner `except` block).
                disruptive_exc_info = sys.exc_info()
                try:
                    # Let's insistently try to ensure that the publishing
                    # generator is closed!
                    close_publishing_generator()
                except:
                    # This case is very unlikely, but if it happens let's
                    # at least log it.
                    log_unlikely_exception_from_insisted_close(sys.exc_info())
                finally:
                    if is_heavier_than_one_to_be_raised(disruptive_exc_info):
                        to_be_raised_exc_info = disruptive_exc_info
                    log_disruptive_exc()
            finally:
                if is_present(to_be_raised_exc_info):
                    exc_type, exc_value, tb = to_be_raised_exc_info
                    raise_(exc_type, exc_value, tb)
        finally:
            # (breaking traceback-related reference cycles, if any)
            # noinspection PyUnusedLocal
            to_be_raised_exc_info = outer_exc_info = inner_exc_info = \
                disruptive_exc_info = exc_value = tb = None

    def _do_publish_iteratively(self):
        outbound_buffer = self._connection.outbound_buffer
        assert isinstance(outbound_buffer, collections.deque)
        outbound_buffer_size_threshold = self.iterative_publishing_outbound_buffer_size_threshold
        yield_time_interval_threshold = self._get_yield_time_interval_threshold()
        yielding_allowed = True
        concrete_publishing_generator = self.publish_iteratively()
        try:
            try:
                # TODO: analyze whether time.time() should be replaced e.g. with time.monotonic().
                yield_time = time.time()
                for marker in concrete_publishing_generator:
                    if marker not in (self.FLUSH_OUT, None):
                        raise ValueError('marker should be either {!r} or None '
                                         '(got: {!r})'.format(self.FLUSH_OUT, marker))
                    if (marker == self.FLUSH_OUT or
                          len(outbound_buffer) >= outbound_buffer_size_threshold):
                        for _ in self._iter_until_buffer_flushed(outbound_buffer):
                            yield
                        # Once the buffer is empty, let's *yield* one more time
                        # unconditionally -- to make it slightly more probable
                        # that the sent data have actually left the machine.
                        yield
                        yield_time = time.time()
                    elif time.time() - yield_time >= yield_time_interval_threshold:
                        yield
                        yield_time = time.time()
            except (self.__PublishingGeneratorCleanExit,
                    self.__PublishingGeneratorDirtyExit):
                yielding_allowed = False
                raise
            finally:
                try:
                    concrete_publishing_generator.close()
                finally:
                    if yielding_allowed:
                        for _ in self._iter_until_buffer_flushed(outbound_buffer):
                            yield
                        # Once the buffer is empty, let's *yield* one more time
                        # unconditionally -- to make it slightly more probable
                        # that the sent data have actually left the machine.
                        yield
        except self.__PublishingGeneratorCleanExit:
            pass
        if not self._is_buffer_empty(outbound_buffer):
            raise n6AMQPCommunicationError(
                "the publishing generator (the main internal component "
                "of the *iterative publishing* machinery) was just to "
                "be closed cleanly (i.e., while no exception was being "
                "handled) *but* the pika connection's outbound buffer "
                "is still *not* empty (i.e., has not been flushed) -- "
                "that means some data which were to be published have "
                "not been (and, probably, will not be) actually sent!")

    def _get_yield_time_interval_threshold(self):
        """
        When the time elapsed since the latest activity of the pika
        connection's IO loop reaches the value (in seconds) returned by
        this method then the next yield from `publish_iteratively()`
        will make the pika connection's IO loop get the control for a
        moment...
        """
        # * factor of 0.2 (in relation to `heartbeat_interval`)
        #   seems to be reasonably safe
        # * but also, let's better try *not* to continue starving
        #   the IO loop longer than 10 seconds anyway (trying, in
        #   particular, not to be close to typical TCP timeouts
        #   and such stuff...)
        return min(0.2 * self._conn_params_dict['heartbeat_interval'],
                   10.0)

    def _iter_until_buffer_flushed(self, outbound_buffer):
        while True:
            if self._is_buffer_empty(outbound_buffer):
                LOGGER.debug("OK, pika's outbound buffer is empty")
                break
            LOGGER.debug("pika's outbound buffer is not empty yet...")
            yield

    def _is_buffer_empty(self, outbound_buffer):
        if self._connection.outbound_buffer is not outbound_buffer:
            raise n6AMQPCommunicationError(
                "it has just been detected that the current pika "
                "connection's outbound buffer object is *not* the "
                "same as the one that was in use when *iterative "
                "publishing* was being initialized; that means we "
                "are not 100% sure what connection objects were "
                "used to perform some number of *publish* actions "
                "(if any) and -- therefore -- we cannot reliably "
                "check whether their outbound buffers have been "
                "actually flushed; so we must assume that it is "
                "possible that some data that were to be published "
                "have not been (and will not be) actually sent!")
        return not outbound_buffer

    def _next_publishing_iteration(self):
        if self._closing:
            LOGGER.warning('%r is being closed so publishing is not continued', self)
            return
        try:
            next(self._publishing_generator)
        except StopIteration:
            self._schedule_next(self.inner_stop)
        else:
            self._schedule_next(self._next_publishing_iteration)

    def _schedule_next(self, callback):
        if self._closing:
            LOGGER.warning('%r is being closed so %r will *not* be scheduled', self, callback)
            return

        @exiting_on_exception(
            exc_factory=self.iterative_publishing_exc_factory,
            exc_message_pattern=self.iterative_publishing_exc_message_pattern)
        @functools.wraps(callback)
        def callback_with_error_handling():
            callback()

        self._connection.add_timeout(self.iterative_publishing_schedule_next_delay,
                                     callback_with_error_handling)

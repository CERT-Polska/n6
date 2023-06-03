# Copyright (c) 2020-2023 NASK. All rights reserved.

"""
Generic AMQP collector.
"""

import pika

from n6datasources.collectors.base import (
    BaseCollector,
    add_collector_entry_point_functions,
)
from n6lib.amqp_helpers import get_amqp_connection_params_dict_from_args
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class AMQPCollector(BaseCollector):

    raw_type = 'stream'

    # (note: we deliberately do *not* use `combined_config_spec()` here)
    config_spec_pattern = '''
        # Note: when running the `n6collector_amqp` script, you
        # specify the config section name as the sole positional
        # command-line argument.
        #
        # So you can have, in you config file(s), any number of
        # configurations of the `n6collector_amqp` script -- each
        # in a separate config section of a distinct name. Then
        # it will even be possible to run multiple instances of
        # `n6collector_amqp` in parallel -- as they are able to
        # work independently of each other, *provided that* each
        # has a different value of the `input_queue_name` option,
        # and (to avoid duplication of work and output data) uses
        # different *binding keys* (if applicable; see the options
        # and comments below...).

        [{config_section_name_from_cmdline_arg}]

        source_provider :: str
        source_channel :: str

        input_host :: str
        input_port :: int
        input_heartbeat_interval :: int
        input_ssl :: bool
        input_ssl_ca_certs :: str
        input_ssl_certfile :: str
        input_ssl_keyfile :: str

        input_queue_name :: str

        # Note: if you set `input_queue_exchange` to an empty string,
        # then the collector itself will neither declare the input
        # exchange nor do any bindings (in that case, the values of
        # `input_queue_exchange_type` and `input_queue_binding_keys`
        # will be just ignored).
        input_queue_exchange :: str
        input_queue_exchange_type :: str

        # Note: if `input_queue_exchange` (see above) is not empty but
        # the value of following option specifies no binding keys, then
        # the collector will bind the input queue to the input exchange
        # *without* any binding key (that makes sense for certain types
        # of exchanges).
        input_queue_binding_keys :: list_of_str
    '''

    @classmethod
    def get_arg_parser(cls):
        arg_parser = super().get_arg_parser()
        arg_parser.add_argument(
            'n6config_section_name',
            help=(
                'the configuration section name to '
                'be used by the AMQP collector'))
        return arg_parser

    def __init__(self, **kwargs):
        self._config_section_name_from_cmdline_arg = self.cmdline_args.n6config_section_name
        self._input_channel = None
        super().__init__(**kwargs)

    def get_config_spec_format_kwargs(self):
        return super().get_config_spec_format_kwargs() | {
            'config_section_name_from_cmdline_arg': self._config_section_name_from_cmdline_arg,
        }

    def get_config_from_config_full(self, *, config_full, collector_class_name):
        return config_full[self._config_section_name_from_cmdline_arg]

    def run_collection(self):
        input_conn = None
        try:
            input_conn = self._setup_input_connection()
            try:
                self._input_channel = input_conn.channel()
                self._declare_input_exchange_if_needed()
                self._declare_input_queue()
                self._bind_input_queue_if_needed()
                super().run_collection()
            finally:
                if self._input_channel is not None and self._input_channel.is_open:
                    self._input_channel.close()
        finally:
            # closing connection is important so we want to
            # perform it even if closing channel failed somehow
            if input_conn is not None and input_conn.is_open:
                input_conn.close()

    def _setup_input_connection(self):
        conn_kwargs = self._get_input_connection_params_dict()
        return pika.BlockingConnection(
            pika.ConnectionParameters(**conn_kwargs))

    def _get_input_connection_params_dict(self):
        return get_amqp_connection_params_dict_from_args(
            host=self.config['input_host'],
            port=self.config['input_port'],
            heartbeat_interval=self.config['input_heartbeat_interval'],
            ssl=self.config['input_ssl'],
            ca_certs=self.config['input_ssl_ca_certs'],
            certfile=self.config['input_ssl_certfile'],
            keyfile=self.config['input_ssl_keyfile'])

    def _declare_input_exchange_if_needed(self):
        if self.config['input_queue_exchange']:
            self._input_channel.exchange_declare(
                self.config['input_queue_exchange'],
                self.config['input_queue_exchange_type'],
                durable=True)

    def _declare_input_queue(self):
        self._input_channel.queue_declare(
            self.config['input_queue_name'],
            durable=True)

    def _bind_input_queue_if_needed(self):
        if self.config['input_queue_exchange']:
            binding_keys = self.config['input_queue_binding_keys']
            if binding_keys:
                for rk in binding_keys:
                    self._input_channel.queue_bind(
                        self.config['input_queue_name'],
                        self.config['input_queue_exchange'],
                        routing_key=rk)
            else:
                self._input_channel.queue_bind(
                    self.config['input_queue_name'],
                    self.config['input_queue_exchange'])

    def start_publishing(self):
        LOGGER.info('Starting publishing...')
        self.start_iterative_publishing()

    def publish_iteratively(self):
        input_queue_message_timeout = self._get_input_queue_message_timeout()
        LOGGER.info('Consuming messages from the input queue...')
        for method, prop, body in self._input_channel.consume(
                self.config['input_queue_name'],
                inactivity_timeout=input_queue_message_timeout):
            if method is None:
                assert prop is None and body is None
                LOGGER.debug('Got nothing.')
                yield
            else:
                LOGGER.debug('Got a message (%a %a %a).', method, prop, body)
                self.publish_output(*self.get_output_components(body=body))
                yield self.FLUSH_OUT
                self._input_channel.basic_ack(method.delivery_tag)

    def _get_input_queue_message_timeout(self):
        # * The factor of 0.1 (in relation to `heartbeat_interval` and
        #   `input_heartbeat_interval`) seems to be reasonably safe.
        # * But, also, let's better try *not* to starve the output
        #   connection's IO loop longer than ~4 seconds anyway...
        return min([
            0.1 * self._conn_params_dict['heartbeat_interval'],
            0.1 * self.config['input_heartbeat_interval'],
            4.0,
        ])

    def get_source(self, **processed_data):
        return f"{self.config['source_provider']}.{self.config['source_channel']}"

    def get_output_data_body(self, *, body, **_):  # noqa
        return body


add_collector_entry_point_functions(__name__)

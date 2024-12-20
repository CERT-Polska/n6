# Copyright (c) 2023-2024 NASK. All rights reserved.

import dataclasses
import pathlib
from os.path import expanduser as orig_os_path_expanduser
from ssl import CERT_REQUIRED
from unittest.mock import (
    Mock,
    call,
    patch,
    sentinel,
)

import pika
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.amqp import AMQPCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.amqp_helpers import (
    GUEST_PASSWORD,
    GUEST_USERNAME,
)
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


@expand
class TestAMQPCollector(BaseCollectorTestCase):

    #
    # Constants

    HOME_DIR = '/home/whoever'
    CONFIG_CONTENT = '''
        [amqp_collector__not_doing_exchange_declare_and_bind__with_ssl_auth]

        source_provider = example-provider
        source_channel = example-channel

        input_host = rabbit1
        input_port = 5671
        input_heartbeat_interval = 30

        input_ssl = True
        input_ssl_ca_certs = ~/certs/n6-CA/cacert.pem
        input_ssl_certfile = ~/certs/cert.pem
        input_ssl_keyfile = ~/certs/key.pem

        input_queue_name = example-input-amqp-queue-1

        input_queue_exchange =
        input_queue_exchange_type = irrelevant
        input_queue_binding_keys = irrelevant


        [amqp_collector__doing_exchange_declare_and_bind__with_ssl_auth]

        source_provider = example-prov-2
        source_channel = example-chan-2

        input_host = rabbit2
        input_port = 5672
        input_heartbeat_interval = 20

        input_ssl = 1
        input_ssl_ca_certs = ~/certs/n6-CA/cacert2.pem
        input_ssl_certfile = ~/certs/cert2.pem
        input_ssl_keyfile = ~/certs/key2.pem

        # (these 3 could be omitted, as in the previous section)
        input_password_auth = 0
        input_username =
        input_password =

        input_queue_name = example-input-amqp-queue-2

        input_queue_exchange = example-input-amqp-exchange-2
        input_queue_exchange_type = topic
        input_queue_binding_keys = example.binding.key.first, example.binding.key.second


        [amqp_collector__doing_exchange_declare_and_bind__with_password_auth]

        source_provider = example-prov-3
        source_channel = example-chan-3

        input_host = rabbit3
        input_port = 5673
        input_heartbeat_interval = 76543

        input_ssl = true
        input_ssl_ca_certs = ~/certs/n6-CA/cacert3.pem

        input_password_auth = true
        input_username = my-user@example.com
        input_password = password*password

        input_queue_name = example-input-amqp-queue-3

        input_queue_exchange = example-input-amqp-exchange-3
        input_queue_exchange_type = topic
        input_queue_binding_keys = example.binding.key.first, example.binding.key.second


        [amqp_collector__doing_exchange_declare_and_bind__without_any_binding_key__without_ssl__without_any_auth]

        source_provider = example-prov-4
        source_channel = example-chan-4

        input_host = rabbit4
        input_port = 5674
        input_heartbeat_interval = 40

        input_ssl = no

        input_queue_name = example-input-amqp-queue-4

        input_queue_exchange = example-input-amqp-exchange-4
        input_queue_exchange_type = fanout
        input_queue_binding_keys =
    '''


    #
    # Auxiliary stub classes

    class _ConsumeResultStub:
        def __init__(self, *items):
            self._rev_items = list(reversed(items))
        def __iter__(self):
            return self
        def __next__(self):
            try:
                return self._rev_items.pop()
            except IndexError:
                raise KeyboardInterrupt

    @dataclasses.dataclass
    class _AMQPMethodStub:
        delivery_tag: int


    #
    # Test cases and implementation

    @paramseq
    def cases(cls):
        expected_prop_kwargs = {
            'timestamp': AnyInstanceOf(int),
            'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
            'type': 'stream',
            'headers': {},
        }

        yield param(
            cmdline_args=['amqp_collector__not_doing_exchange_declare_and_bind__with_ssl_auth'],
            input_channel_consume_result=cls._ConsumeResultStub(
                (None, None, None),
                # * input message A
                (cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A'),
                (None, None, None),
                (None, None, None),
                # * input message B
                (cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B'),
                # * input message C
                (cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C'),
                (None, None, None),
            ),
            expected_recorded_actions=[
                # * setup
                call.collector_module.pika.ConnectionParameters(
                    host='rabbit1',
                    port=5671,
                    heartbeat_interval=30,
                    ssl=True,
                    ssl_options=dict(
                        ca_certs=f'{cls.HOME_DIR}/certs/n6-CA/cacert.pem',
                        certfile=f'{cls.HOME_DIR}/certs/cert.pem',
                        keyfile=f'{cls.HOME_DIR}/certs/key.pem',
                        cert_reqs=CERT_REQUIRED,
                    ),
                    credentials=AnyInstanceOf(pika.credentials.ExternalCredentials),
                    client_properties={'information': AnyInstanceOf(str)},
                ),
                call.collector_module.pika.BlockingConnection(sentinel.conn_parameters),
                call.input_conn.channel(),
                call.collector._input_channel.queue_declare(
                    'example-input-amqp-queue-1',
                    durable=True,
                ),
                call.collector_module.LOGGER.info('Starting publishing...'),
                call.collector_module.LOGGER.info('Consuming messages from the input queue...'),
                call.collector._input_channel.consume(
                    'example-input-amqp-queue-1',
                    inactivity_timeout=3.0,  # (see collector's `_get_input_queue_message_timeout`)
                ),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * input message A
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A',
                ),
                call.collector.publish_output(
                    'example-provider.example-channel',   # routing_key
                    b'body-A',                            # body
                    expected_prop_kwargs,                 # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_A),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * input message B
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B',
                ),
                call.collector.publish_output(
                    'example-provider.example-channel',   # routing_key
                    b'body-B',                            # body
                    expected_prop_kwargs,                 # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_B),

                # * input message C
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C',
                ),
                call.collector.publish_output(
                    'example-provider.example-channel',   # routing_key
                    b'body-C',                            # body
                    expected_prop_kwargs,                 # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_C),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * finalization
                call.collector._input_channel.close(),
                call.input_conn.close(),
            ],
        )

        yield param(
            cmdline_args=['amqp_collector__doing_exchange_declare_and_bind__with_ssl_auth'],
            input_channel_consume_result=cls._ConsumeResultStub(
                # * input message A
                (cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A'),
                # * input message B
                (cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B'),
                (None, None, None),
                (None, None, None),
                (None, None, None),
                (None, None, None),
                # * input message C
                (cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C'),
            ),
            expected_recorded_actions=[
                # * setup
                call.collector_module.pika.ConnectionParameters(
                    host='rabbit2',
                    port=5672,
                    heartbeat_interval=20,
                    ssl=True,
                    ssl_options=dict(
                        ca_certs=f'{cls.HOME_DIR}/certs/n6-CA/cacert2.pem',
                        certfile=f'{cls.HOME_DIR}/certs/cert2.pem',
                        keyfile=f'{cls.HOME_DIR}/certs/key2.pem',
                        cert_reqs=CERT_REQUIRED,
                    ),
                    credentials=AnyInstanceOf(pika.credentials.ExternalCredentials),
                    client_properties={'information': AnyInstanceOf(str)},
                ),
                call.collector_module.pika.BlockingConnection(sentinel.conn_parameters),
                call.input_conn.channel(),
                call.collector._input_channel.exchange_declare(         # (<- note this)
                    'example-input-amqp-exchange-2',
                    'topic',
                    durable=True,
                ),
                call.collector._input_channel.queue_declare(
                    'example-input-amqp-queue-2',
                    durable=True,
                ),
                call.collector._input_channel.queue_bind(               # (<- note this)
                    'example-input-amqp-queue-2',
                    'example-input-amqp-exchange-2',
                    routing_key='example.binding.key.first',
                ),
                call.collector._input_channel.queue_bind(               # (<- note this)
                    'example-input-amqp-queue-2',
                    'example-input-amqp-exchange-2',
                    routing_key='example.binding.key.second',
                ),
                call.collector_module.LOGGER.info('Starting publishing...'),
                call.collector_module.LOGGER.info('Consuming messages from the input queue...'),
                call.collector._input_channel.consume(
                    'example-input-amqp-queue-2',
                    inactivity_timeout=2.0,  # (see collector's `_get_input_queue_message_timeout`)
                ),

                # * input message A
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A',
                ),
                call.collector.publish_output(
                    'example-prov-2.example-chan-2',   # routing_key
                    b'body-A',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_A),

                # * input message B
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B',
                ),
                call.collector.publish_output(
                    'example-prov-2.example-chan-2',   # routing_key
                    b'body-B',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_B),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * input message C
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C',
                ),
                call.collector.publish_output(
                    'example-prov-2.example-chan-2',   # routing_key
                    b'body-C',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_C),

                # * finalization
                call.collector._input_channel.close(),
                call.input_conn.close(),
            ],
        )

        yield param(
            cmdline_args=['amqp_collector__doing_exchange_declare_and_bind__with_password_auth'],
            input_channel_consume_result=cls._ConsumeResultStub(
                # * input message A
                (cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A'),
                # * input message B
                (cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B'),
                (None, None, None),
                (None, None, None),
                (None, None, None),
                (None, None, None),
                # * input message C
                (cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C'),
            ),
            expected_recorded_actions=[
                # * setup
                call.collector_module.pika.ConnectionParameters(
                    host='rabbit3',
                    port=5673,
                    heartbeat_interval=76543,
                    ssl=True,
                    ssl_options=dict(
                        ca_certs=f'{cls.HOME_DIR}/certs/n6-CA/cacert3.pem',
                        cert_reqs=CERT_REQUIRED,
                    ),
                    credentials=pika.credentials.PlainCredentials(
                        'my-user@example.com',
                        'password*password',
                    ),
                    client_properties={'information': AnyInstanceOf(str)},
                ),
                call.collector_module.pika.BlockingConnection(sentinel.conn_parameters),
                call.input_conn.channel(),
                call.collector._input_channel.exchange_declare(         # (<- note this)
                    'example-input-amqp-exchange-3',
                    'topic',
                    durable=True,
                ),
                call.collector._input_channel.queue_declare(
                    'example-input-amqp-queue-3',
                    durable=True,
                ),
                call.collector._input_channel.queue_bind(               # (<- note this)
                    'example-input-amqp-queue-3',
                    'example-input-amqp-exchange-3',
                    routing_key='example.binding.key.first',
                ),
                call.collector._input_channel.queue_bind(               # (<- note this)
                    'example-input-amqp-queue-3',
                    'example-input-amqp-exchange-3',
                    routing_key='example.binding.key.second',
                ),
                call.collector_module.LOGGER.info('Starting publishing...'),
                call.collector_module.LOGGER.info('Consuming messages from the input queue...'),
                call.collector._input_channel.consume(
                    'example-input-amqp-queue-3',
                    inactivity_timeout=3.0,  # (see collector's `_get_input_queue_message_timeout`)
                ),

                # * input message A
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A',
                ),
                call.collector.publish_output(
                    'example-prov-3.example-chan-3',   # routing_key
                    b'body-A',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_A),

                # * input message B
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_B), sentinel.unused, b'body-B',
                ),
                call.collector.publish_output(
                    'example-prov-3.example-chan-3',   # routing_key
                    b'body-B',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_B),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * no input message
                call.collector_module.LOGGER.debug('Got nothing.'),
                call.pub_iter_yield(None),

                # * input message C
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_C), sentinel.unused, b'body-C',
                ),
                call.collector.publish_output(
                    'example-prov-3.example-chan-3',   # routing_key
                    b'body-C',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_C),

                # * finalization
                call.collector._input_channel.close(),
                call.input_conn.close(),
            ],
        )

        yield param(
            cmdline_args=[
                'amqp_collector__doing_exchange_declare_and'
                '_bind__without_any_binding_key__without_ssl__without_any_auth',

                # (maybe TODO: make it cause error, see #8745...)
                '<ignored extra positional arg>',
            ],
            input_channel_consume_result=cls._ConsumeResultStub(
                # * input message A
                (cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A'),
            ),
            expected_recorded_actions=[
                # * setup
                call.collector_module.pika.ConnectionParameters(
                    host='rabbit4',
                    port=5674,
                    heartbeat_interval=40,
                    ssl=False,
                    credentials=pika.credentials.PlainCredentials(
                        GUEST_USERNAME,
                        GUEST_PASSWORD,
                    ),
                    client_properties={'information': AnyInstanceOf(str)},
                ),
                call.collector_module.pika.BlockingConnection(sentinel.conn_parameters),
                call.input_conn.channel(),
                call.collector._input_channel.exchange_declare(
                    'example-input-amqp-exchange-4',
                    'fanout',
                    durable=True,
                ),
                call.collector._input_channel.queue_declare(
                    'example-input-amqp-queue-4',
                    durable=True,
                ),
                call.collector._input_channel.queue_bind(               # (<- note this)
                    'example-input-amqp-queue-4',
                    'example-input-amqp-exchange-4',
                ),
                call.collector_module.LOGGER.info('Starting publishing...'),
                call.collector_module.LOGGER.info('Consuming messages from the input queue...'),
                call.collector._input_channel.consume(
                    'example-input-amqp-queue-4',
                    inactivity_timeout=3.0,  # (see collector's `_get_input_queue_message_timeout`)
                ),

                # * input message A
                call.collector_module.LOGGER.debug(
                    'Got a message (%a %a %a).',
                    cls._AMQPMethodStub(sentinel.delivery_tag_A), sentinel.unused, b'body-A',
                ),
                call.collector.publish_output(
                    'example-prov-4.example-chan-4',   # routing_key
                    b'body-A',                         # body
                    expected_prop_kwargs,              # prop_kwargs
                ),
                call.pub_iter_yield('FLUSH_OUT'),
                call.collector._input_channel.basic_ack(sentinel.delivery_tag_A),

                # * finalization
                call.collector._input_channel.close(),
                call.input_conn.close(),
            ],
        )

    @foreach(cases)
    def test(self,
             cmdline_args,
             input_channel_consume_result,
             expected_recorded_actions):

        rec = Mock()
        rec.collector.publish_output = self.publish_output_mock
        self.patch('n6datasources.collectors.amqp.LOGGER', rec.collector_module.LOGGER)
        self.patch('n6datasources.collectors.amqp.pika', rec.collector_module.pika)
        rec.collector_module.pika.ConnectionParameters.return_value = sentinel.conn_parameters
        rec.collector_module.pika.BlockingConnection.return_value = rec.input_conn
        rec.input_conn.channel.return_value = rec.collector._input_channel
        rec.collector._input_channel.consume.return_value = input_channel_consume_result
        self._patch_get_input_connection_params_dict()
        self._patch_publish_iteratively(rec)

        collector = self.prepare_collector(
            AMQPCollector,
            config_content=self.CONFIG_CONTENT,
            cmdline_args=cmdline_args)

        assert rec.mock_calls == []
        assert collector._config_section_name_from_cmdline_arg == cmdline_args[0]
        assert collector._input_channel is None
        with self.assertRaises(KeyboardInterrupt):

            collector.run_collection()

        assert rec.mock_calls == expected_recorded_actions
        assert collector._input_channel is rec.collector._input_channel


    @foreach(
        [],
        ['--non-positional-arg'],
    )
    def test_missing_positional_commandline_arg_causes_error(self, cmdline_args):
        with self.assertRaisesRegex(SystemExit, '^2$'):
            self.prepare_collector(AMQPCollector, cmdline_args=cmdline_args)


    #
    # Patching helpers

    def _patch_get_input_connection_params_dict(self):
        orig_get_input_connection_params_dict = AMQPCollector._get_input_connection_params_dict
        home_dir = self.HOME_DIR

        def os_path_expanduser_wrapper(path):
            if isinstance(path, pathlib.Path) and str(path).startswith('~/'):
                path = pathlib.Path(f"{home_dir}/{str(path).removeprefix('~/')}")
            return orig_os_path_expanduser(path)

        def _get_input_connection_params_dict_wrapper(self):
            assert isinstance(self, AMQPCollector)
            with patch('os.path.expanduser', os_path_expanduser_wrapper):
                return orig_get_input_connection_params_dict(self)

        self.patch_object(
            AMQPCollector,
            '_get_input_connection_params_dict',
            _get_input_connection_params_dict_wrapper)


    def _patch_publish_iteratively(self, rec):
        orig_publish_iteratively = AMQPCollector.publish_iteratively

        def publish_iteratively_wrapper(self):
            assert isinstance(self, AMQPCollector)
            pub_iter = orig_publish_iteratively(self)
            while True:
                yielded_by_pub_iter = next(pub_iter)
                rec.pub_iter_yield(yielded_by_pub_iter)
                yield yielded_by_pub_iter

        self.patch_object(
            AMQPCollector,
            'publish_iteratively',
            publish_iteratively_wrapper)

# Copyright (c) 2021 NASK. All rights reserved.

import hashlib
import json
import re
import time
from functools import wraps
from logging import getLogger
from typing import Optional

import pika
from intelmq.lib.bot import CollectorBot
from intelmq.lib.message import MessageFactory

from n6datapipeline.base import LegacyQueuedBase
from n6datapipeline.intelmq import bots_config
from n6datapipeline.intelmq.utils.intelmq_converter import IntelToN6Converter
from n6lib.const import RAW_TYPE_ENUMS
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


LOGGER = getLogger(__name__)


INTELMQ_TARGET_DIR = '/opt'
N6_DATA_FIELD_NAME = IntelToN6Converter.extra_field_name_in
N6_DATA_FIELD_SPEC = {
    'description': 'Field for storing n6-specific data that should be ignored '
                   'by IntelMQ bots',
    'type': 'JSONDict',
}


def get_getattribute(cls, original_class_objects, allowed_objects):
    def getattribute(self, item):
        """
        Raise `NotImplementedError` if a bot tries to access
        an object from IntelMQ class that was not patched
        and is not adapted to work inside n6 pipeline.
        """
        if item in original_class_objects and item not in allowed_objects:
            raise NotImplementedError(ascii(item))
        else:
            return super(cls, self).__getattribute__(item)

    return getattribute


def get__load_harmonization_configuration_method(original_method):
    """
    Get a method extending the original IntelMQ method, which loads
    harmonization configuration, so it adds a definition of the new
    harmonization field - the field which will serve as a container
    for n6-specific serialized data, ignored by IntelMQ bots.
    """
    def new_method(self):
        original_method(self)
        assert isinstance(self.harmonization, dict)
        self.harmonization['event'][N6_DATA_FIELD_NAME] = N6_DATA_FIELD_SPEC.copy()
        self.harmonization['report'][N6_DATA_FIELD_NAME] = N6_DATA_FIELD_SPEC.copy()
    return new_method


def get__message__add_method(original_method):
    def new_method(self, *args, **kwargs):
        self.harmonization_config[N6_DATA_FIELD_NAME] = N6_DATA_FIELD_SPEC.copy()
        return original_method(self, *args, **kwargs)
    return new_method


# TODO: <LEGACY CODE CHECK> probably should be removed
# def get_load_configuration(bot_module_path):
#
#     def get_intelmq_etc_path():
#         module_dirname = os.path.dirname(os.path.abspath(bot_module_path))
#         parent_dirname, _ = os.path.split(module_dirname)
#         return os.path.join(parent_dirname, 'etc')
#
#     def load_config_wrapper(configuration_filepath):
#         config_dirname, config_filename = os.path.split(configuration_filepath)
#         if config_dirname.startswith(INTELMQ_TARGET_DIR):
#             configuration_filepath = os.path.join(get_intelmq_etc_path(), config_filename)
#         return load_configuration(configuration_filepath)
#
#     return load_config_wrapper


def get_parameters(config_instance):
    return config_instance.make_parameter_provider()


def get_iso_datetime_is_valid(original_method):
    def new_iso_datetime_is_valid(value, sanitize=False):
        return original_method(parse_iso_datetime_to_utc(value), sanitize)
    return new_iso_datetime_is_valid


def get_generate_datetime_now(original_method):
    def new_generate_datetime_now(*args):
        return str(parse_iso_datetime_to_utc(original_method()))
    return new_generate_datetime_now


def get_load_runtime_configuration(original_method):
    def new_method(self, *args):
        # self.__bot_id = self.bot_id
        # setattr(self, f'_{self.__class__.__name__}__bot_id', self.bot_id)
        return original_method(self, *args)
    return new_method


class DumpMessageException(Exception):
    """Raised to communicate the message should be NACK-ed."""


class QueuedBaseExtended(LegacyQueuedBase):

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }
    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    bot_id: Optional[str] = None
    # to be set by wrapper, later used as a config
    # n6config: Union[ConfigSection, dict] = {}
    config: dict = {}
    exception_proof: bool = False

    bot_group_name: str = 'intelmq-experts'

    # if None, it will be loaded during message init
    harmonization = None

    collectors_rk_pattern = re.compile(r'^[0-9a-zA-Z-_]+\.[0-9a-zA-Z-_]+$')
    utils_rk_pattern = re.compile(r'([0-9a-zA-Z-_]+\.){3}([0-9a-zA-Z-_]+)')

    def __init__(self, **kwargs):
        # private attribute used by IntelMQ config loader
        self.__bot_id = self.bot_id
        # attributes of the currently received message
        self.current_message = None
        self.current_routing_key = None
        self.current_properties = None
        self.load_runtime_configuration()
        self.load_harmonization_configuration()
        self.exception_proof_mode = self.exception_proof
        self.exception_proof = False
        self.routing_state = self.bot_id
        super(QueuedBaseExtended, self).__init__(**kwargs)
        try:
            self.init()
        except AttributeError:
            pass
        except Exception:
            if not self.exception_proof_mode:
                raise

    def _get_input_messages_type(self):
        if self.collectors_rk_pattern.search(self.current_routing_key):
            return 'Report'
        return 'Event'

    def set_queue_name(self):
        self.input_queue['queue_name'] = self.bot_id

    def get_component_group_and_id(self):
        return self.bot_group_name, self.bot_id

    def make_binding_keys(self, binding_states, accepted_event_types):
        input_message_type = self.config.get('input_messages_type')
        if input_message_type and input_message_type.lower() == 'report':
            # in case the incoming messages are declared to be
            # of the 'Report' type (this type of messages should
            # be sent by collectors), set a simple binding keys,
            # so they match collector's routing key
            self.input_queue['binding_keys'] = binding_states.copy()
        else:
            super(QueuedBaseExtended, self).make_binding_keys(binding_states,
                                                              accepted_event_types)

    def input_callback(self,
                       routing_key: str,
                       body: bytes,
                       properties: pika.BasicProperties) -> None:
        self.current_routing_key = routing_key
        input_msg = body.decode('utf-8')
        self.current_message = input_msg
        self.current_properties = properties
        try:
            self.process()
        except Exception as e:
            print(e)
            if self.exception_proof_mode:
                self.emergency_send(self.current_message)
            else:
                raise

    def receive_message(self):
        # if a message comes from a collector, it qualifies as
        # a `Report`, otherwise - an `Event`
        msg_type = self._get_input_messages_type()
        msg = MessageFactory.unserialize(self.current_message, default_type=msg_type)
        return msg

    def _get_output_prop_kwargs(self, **kwargs):
        return None

    @staticmethod
    def _replace_rk_state(key, state, sep='.'):
        segments = key.split(sep)
        segments[1] = state
        return sep.join(segments)

    def _get_bot_rk(self):
        """
        Create the routing key similar to other n6 'utils'
        components, like:
        <event type>.<bot ID>.<source label>.<source channel>

        Returns:
            The output message's routing key as a string.
        """
        routing_state = self.routing_state
        input_rk = self.current_routing_key
        if self.utils_rk_pattern.search(input_rk):
            return self._replace_rk_state(input_rk, routing_state)
        # if the event type is not defined in message's routing key,
        # assume it is 'event'
        LOGGER.warning(f"Judging by the processed message's routing key ({input_rk}), "
                       f"the message from collector-like component has been received "
                       f"by the component from the 'intelmq-experts' group. It may need "
                       f"to be parsed by the parser-like component first")
        return f'event.{routing_state}.{input_rk}'

    def send_message(self, *events, **kwargs):
        rk = self._get_bot_rk()
        for event in events:
            serialized_event = event.serialize()
            self.publish_output(routing_key=rk,
                                body=serialized_event,
                                prop_kwargs=self._get_output_prop_kwargs(
                                        output_data_body=serialized_event))

    def emergency_send(self, event):
        rk = self._get_bot_rk()
        self.publish_output(routing_key=rk,
                            body=event,
                            prop_kwargs=self._get_output_prop_kwargs(
                                    output_data_body=event.serialize()))

    def acknowledge_message(self, *args):
        """
        Call a proper method based on number of arguments.
        Implementation of the method in `intelmq.lib.bot.Bot`
        takes no arguments, in `n6datapipeline.base.LegacyQueuedBase`
        it takes one positional argument - `delivery_tag`.

        Args:
            `delivery_tag`:
                The delivery tag from the Basic.Deliver frame.

        Raises:
            TypeError if the method is called with more than
            one argument.
        """
        if not args:
            pass
        elif len(args) > 1:
            raise TypeError('acknowledge_message() takes 1 positional argument but {} '
                            'were given.'.format(len(args)))
        else:
            delivery_tag = args[0]
            super(QueuedBaseExtended, self).acknowledge_message(delivery_tag)

    def _dump_message(self, *args, **kwargs):
        raise DumpMessageException


class BaseCollectorExtended(QueuedBaseExtended):

    output_queue = {
        'exchange': 'raw',
        'exchange_type': 'topic',
    }

    DEFAULT_CONTENT_TYPE = 'text/plain'
    DEFAULT_SOURCE_CHANNEL = 'intelmq-collector'

    type = 'stream'
    input_queue = None

    bot_group_name = 'intelmq-collectors'

    __class__ = CollectorBot

    def __init__(self, **kwargs):
        self.__class__.__base__.send_message = QueuedBaseExtended.send_message
        super(BaseCollectorExtended, self).__init__(**kwargs)
        self.source_label = self.config.get('source_label') or self.bot_id
        self.source_channel = self.config.get('source_channel') or self.DEFAULT_SOURCE_CHANNEL
        self._set_type()

    def _set_type(self):
        custom_type = self.config.get('type')
        if custom_type:
            self._validate_type()
            self.type = custom_type
            if self.type == 'file':
                try:
                    self.content_type = self.config['content_type']
                except KeyError:
                    LOGGER.warning("The `content_type` attribute is not set in the 'n6config' "
                                   "section of the runtime config, although the `type` "
                                   "attribute is set to `file`. Setting "
                                   "default value: 'text/plain'.")
                    self.content_type = 'text/plain'

    def _validate_type(self):
        """
        Validate type of message to be archived in MongoDB.
        It should be one of: 'stream', 'file', 'blacklist.
        """
        if self.type not in RAW_TYPE_ENUMS:
            raise Exception(f'Wrong type of data being archived in MongoDB: {self.type}, '
                            f'should be one of: {RAW_TYPE_ENUMS}')

    def _get_output_message_id(self, timestamp, output_data_body):
        return hashlib.md5(('\0'.join((self.source_label,
                            '{0:d}'.format(timestamp),
                             output_data_body))).encode('utf-8')
                           ).hexdigest()

    def _get_output_prop_kwargs(self, **kwargs):
        # save information about source label and source channel
        # as meta headers, so they are ignored by IntelMQ
        # harmonization, but will be available for a parser
        created_timestamp = int(time.time())

        headers = {
            'meta': {
                'collector_info': {
                    'source_label': self.source_label,
                    'source_channel': self.source_channel,
                },
            },
        }
        properties = {
            'message_id': self._get_output_message_id(timestamp=created_timestamp, **kwargs),
            'type': self.type,
            'timestamp': created_timestamp,
            'headers': headers,
        }
        # there are no blacklist IntelMQ collectors, so we
        # are ignoring the "blacklist" type
        if self.type == 'file':
            properties.update({'content_type': self.content_type})
        return properties

    def _get_bot_rk(self):
        return '{}.{}'.format(self.source_label, self.source_channel)

    def start_publishing(self):
        self.process()
        self.inner_stop()


class BaseParserExtended(QueuedBaseExtended):

    input_queue = {
        "exchange": "raw",
        "exchange_type": "topic",
    }
    output_queue = {
        "exchange": "event",
        "exchange_type": "topic",
    }

    CONSTANT_ITEMS_DEFAULTS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'other',
    }

    event_type = 'event'
    parser_routing_state = 'intelmq-parsed'
    extra_intelmq_field = IntelToN6Converter.extra_field_name_in

    bot_group_name = 'intelmq-parsers'

    def __init__(self, **kwargs):
        super(BaseParserExtended, self).__init__(**kwargs)
        self.routing_state = self.config.get('routing_state') or self.parser_routing_state
        self._set_constant_items()

    def init(self):
        pass

    def configure_pipeline(self):
        self.default_binding_key = self.config.get('default_binding_key')
        if not self.default_binding_key:
            raise ValueError(f"A 'default_binding_key' option has to be set in parser's config "
                             f"(bot ID: {self.bot_id})")
        self.input_queue['binding_keys'] = [self.default_binding_key]
        super(BaseParserExtended, self).configure_pipeline()

    def make_binding_keys(self, binding_keys, *args, **kwargs):
        """
        Make binding keys, only if there is a pipeline configuration
        for a parser.
        """
        self.input_queue['binding_keys'] = binding_keys

    def _set_constant_items(self):
        for opt_name, default_value in self.CONSTANT_ITEMS_DEFAULTS.items():
            try:
                value = self.config[opt_name]
            except KeyError:
                value = default_value
                LOGGER.warning("The %a option has not been found in the 'n6config' section of "
                               "the runtime config for the parser bot with ID: %a. Using "
                               "default value: %a", opt_name, self.bot_id, value)
            setattr(self, opt_name, value)

    def _get_bot_rk(self):
        return '{}.{}.{}'.format(self.event_type, self.routing_state, self.default_binding_key)

    @staticmethod
    def _iter_output_id_base_items(event):
        return ((key, value) for key, value in event.items()
                if not key.startswith('__'))

    def _get_output_message_id(self, event):
        serialized_fields = []
        for key, value in sorted(self._iter_output_id_base_items(event)):
            serialized_fields.append("{},{}".format(key, value))
        return hashlib.md5(("\n".join(serialized_fields)).encode('utf-8')).hexdigest()

    def _set_parser_fields(self, event):
        message_id = self.current_properties.message_id
        source = self.current_properties.headers['meta']['collector_info']['source_label']
        channel = self.current_properties.headers['meta']['collector_info']['source_channel']
        source_spec = '{}.{}'.format(source, channel)
        n6parser_fields = {
            'id': self._get_output_message_id(event),
            'rid': message_id,
            'source': source_spec,
            # subsequent fields should have been set
            # in `_set_constant_items()`
            'confidence': self.confidence,
            'category': self.category,
            'restriction': self.restriction,
        }
        # store n6 parser-specific data in the message's extra field,
        # which is ignored by IntelMQ components
        event.add(self.extra_intelmq_field, json.dumps(n6parser_fields))

    def send_message(self, *events):
        rk = self._get_bot_rk()
        for event in events:
            self._set_parser_fields(event)
            serialized_event = event.serialize()
            self.publish_output(routing_key=rk, body=serialized_event)


class n6Cache:

    def _get_decorator(self, ttl):
        def is_time_up(time_of_set):
            current_time = time.time()
            if current_time - time_of_set >= ttl:
                return True

        def decorate(func):
            @wraps(func)
            def wrapper(key):
                retval, time_of_set = func(key)
                if not retval:
                    return retval
                if is_time_up(time_of_set):
                    self.remove(key)
                return retval
            return wrapper
        return decorate

    def __init__(self, _host, _port, _db, ttl=600, password=None):
        if isinstance(ttl, bots_config.DummyParameter):
            ttl = 600
        self._cache_container = {}
        self.decorator = self._get_decorator(ttl)
        self.exists = self.decorator(self.exists)
        self.get = self.decorator(self.get)

    def exists(self, item):
        try:
            _, time_of_set = self._cache_container[item]
        except KeyError:
            return False, None
        return True, time_of_set

    def get(self, key):
        try:
            returned_tuple = self._cache_container[key]
        except KeyError:
            return None, None
        retval, time_of_set = returned_tuple
        if isinstance(retval, bytes):
            return retval.decode('utf-8'), time_of_set
        return returned_tuple

    def set(self, key, value, *args, **kwargs):
        self._cache_container[key] = (value, time.time())

    def remove(self, key):
        try:
            del self._cache_container[key]
        except KeyError:
            pass

    def flush(self):
        del self._cache_container
        self._cache_container = {}

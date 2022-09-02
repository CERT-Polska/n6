# Copyright (c) 2021 NASK. All rights reserved.

import logging
from inspect import isroutine

from n6datapipeline.base import LegacyQueuedBase
from n6datapipeline.intelmq.helpers import (
    n6Cache,
    BaseCollectorExtended,
    BaseParserExtended,
    QueuedBaseExtended,
    get__load_harmonization_configuration_method,
    get__message__add_method,
    get_generate_datetime_now,
    get_getattribute,
    get_iso_datetime_is_valid,
    get_load_runtime_configuration,
    get_parameters,
)

from intelmq.lib import (
    bot,
    cache,
    message,
)


OBJECTS_FROM_QUEUEDBASE = [
    '__new__',
    'get_connection_params_dict',
    'rabbitmq_config_section',
    'single_instance',
    'supports_n6recovery',
    'cmdline_args',
    'prefetch_count',
    'basic_prop_kwargs',
    'run',
    'stop',
    'inner_stop',
    'connect',
    'close_connection',
    'on_connection_error_open',
    'on_connection_open',
    'on_connection_closed',
    'open_channels',
    'close_channels',
    'close_channel',
    'on_input_channel_open',
    'on_output_channel_open',
    'on_channel_closed',
    'setup_dead_exchange',
    'on_dead_exchange_declared',
    'on_dead_queue_declared',
    'setup_input_exchange',
    'on_input_exchange_declared',
    'setup_queue',
    'on_queue_declared',
    'on_bindok',
    'start_consuming',
    'stop_consuming',
    'on_cancelok',
    'on_consumer_cancelled',
    'nacknowledge_message',
    'on_message',
    'setup_output_exchanges',
    'on_output_exchange_declared',
    'start_publishing',
    'publish_output',
    'basic_publish',
]
BOT_ALLOWED_OBJECTS = [
    'init',
    '__init__',
    'input_queue',
    'output_queue',
    'receive_message',
    '_dump_message',
    'new_event',
    'set_request_parameters',
    'stop',
    'run',
    'input_callback',
    'send_message',
    'supports_n6recovery',
    'acknowledge_message',
    'harmonization',
    'parameters',
    'logger',
    'http_user_agent',
    '_Bot__bot_id',
    '_Bot__log_configuration_parameter',
    'source_queue',
]

CACHE_ALLOWED_OBJECTS = [
    '__init__',
    'get',
    'set',
    'exists',
    'flush',
]

BOT_INSTANCE_OBJECTS = [
    'logger',
    '_Bot__error_retries_counter',
    'run_mode',
    '_Bot__log_buffer',
    'source_pipeline_broker',
    'instances_threads',
    'parameters',
    '_Bot__source_pipeline',
    '_Bot__sighup',
    '_Bot__destination_pipeline',
    'harmonization',
    '_Bot__bot_id',
]

OBJECTS_FROM_COLLECTORBOT = [
    'name',
    'accuracy',
    'code',
    'provider',
    'documentation',
    '_CollectorBot__filter_empty_report',
    '_CollectorBot__add_report_fields',
    'send_message',
    'new_report',
]

OBJECTS_FROM_PARSERBOT = [
    'new_event',
    '_csv_params',
    '_ignore_lines_starting',
    '_handle',
    '_current_line',
    'parse_csv',
    'parse_csv_dict',
    'parse_json',
    'parse_json_stream',
    'parse',
    'parse_line',
    'process',
    'recover_line',
    'recover_line_csv',
    'recover_line_csv_dict',
    'recover_line_json',
    'recover_line_json_stream',
]

BOT_CLASS_OBJECTS = list(bot.Bot.__dict__.keys())
ALL_BOT_OBJECTS = BOT_INSTANCE_OBJECTS.copy() + BOT_CLASS_OBJECTS.copy()
LIST_OF_CACHE_OBJECTS = list(cache.Cache.__dict__.copy().keys())

N6_EXTRA_DATA_FIELD_NAME = 'n6_data'
INTELMQ_EXTRA_DATA_FIELD_NAME = 'intelmq'

# keep some methods of the IntelMQ `Bot` class, so they can be set
# as methods of the n6 replacement class
set_request_parameters_method = bot.Bot.set_request_parameters
load_runtime_configuration_method = bot.Bot._Bot__load_runtime_configuration
load_harmonization_configuration_method = get__load_harmonization_configuration_method(
    bot.Bot._Bot__load_harmonization_configuration)
log_configuration_parameter_method = bot.Bot._Bot__log_configuration_parameter

for queuedbase_obj in OBJECTS_FROM_QUEUEDBASE:
    setattr(QueuedBaseExtended, queuedbase_obj, LegacyQueuedBase.__dict__[queuedbase_obj])


bot_class_attrs = {key: val for key, val in vars(bot.Bot).items()
                   if not key.startswith('_') and not isroutine(val)}

bot.Bot = QueuedBaseExtended

# move class attributes of the IntelMQ `Bot` class (they are being
# used as parameters) with their default values to the n6 replacement
# class to prevent raising AttributeErrors
for key, val in bot_class_attrs.items():
    if key not in QueuedBaseExtended.__dict__:
        setattr(bot.Bot, key, val)

QueuedBase = QueuedBaseExtended

bot.Bot.set_request_parameters = set_request_parameters_method
bot.Bot.load_runtime_configuration = load_runtime_configuration_method
bot.Bot.load_harmonization_configuration = load_harmonization_configuration_method
bot.Bot._Bot__log_configuration_parameter = log_configuration_parameter_method
# TODO: improve the `__getattribute__()` patch
# bot.Bot.__getattribute__ = get_getattribute(bot.Bot, ALL_BOT_OBJECTS, BOT_ALLOWED_OBJECTS)
bot.Bot.logger = logging.getLogger(__name__)

cache.Cache = n6Cache
cache.Cache.__getattribute__ = get_getattribute(cache.Cache,
                                                LIST_OF_CACHE_OBJECTS,
                                                CACHE_ALLOWED_OBJECTS)


# TODO: <LEGACY CODE CHECK> check if it is necessary
# def patched_parsed_utc_isoformat(value):
#     return str(parse_iso_datetime_to_utc(value))

# harmonization.DateTime.parse_utc_isoformat = patched_parsed_utc_isoformat
# harmonization.DateTime.generate_datetime_now = get_generate_datetime_now(
#     harmonization.DateTime.generate_datetime_now)

# CollectorBot patching
collectorbot_objects = {obj: getattr(bot.CollectorBot, obj) for obj in OBJECTS_FROM_COLLECTORBOT}
bot.CollectorBot = BaseCollectorExtended
for name, obj in collectorbot_objects.items():
    setattr(bot.CollectorBot, name, obj)

# ParserBot patching
parserbot_objects = {obj: getattr(bot.ParserBot, obj) for obj in OBJECTS_FROM_PARSERBOT}
bot.ParserBot = BaseParserExtended
for name, obj in parserbot_objects.items():
    setattr(bot.ParserBot, name, obj)

# intelmq.lib.message patching
message.Message.add = get__message__add_method(message.Message.add)

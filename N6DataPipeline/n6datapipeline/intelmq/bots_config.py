#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect
import logging
import os
from pathlib import Path

from n6lib.config import (
    Config,
    ConfigMixin,
)


LOGGER = logging.getLogger(__name__)


BOT_CONFIG_CLASS_SUFFIX = 'Config'
INTELMQ_TOOLS_PATH = Path(__file__).absolute().parent


def verify_callers_path(file_path, called_class):
    """
    Check, whether an inspected object's iterator is being accessed
    by an object from IntelMQ library. Log a warning otherwise.

    Args:
        `file_path`:
            path to a file, from which inspected object was accessed.
    """

    if os.path.split(file_path)[1] != 'expert.py' and 'intelmq' not in file_path.split(os.sep):
        LOGGER.warning("Iterator of instance of %s is being accessed outside of "
                       "IntelMQ's library.", called_class)


class DummyParameter:

    # attributes that should not be replaced by a dummy parameter,
    # but raise an exception, so `getattr()` method returns default
    # value
    exceptional_attrs = [
        'http_header',
        'http_verify_cert',
        'ssl_client_certificate',
        'http_timeout_sec',
        'http_timeout_max_tries',
    ]

    def __init__(self, name):
        if name in self.exceptional_attrs:
            raise AttributeError
        LOGGER.warning('The parameter {!r} should not be used!'.format(name))


class BotParameterProvider:

    def __init__(self, config):
        self.config = config

    def __getattribute__(self, item):
        config_dict = super(BotParameterProvider, self).__getattribute__('config')
        try:
            return config_dict[item]
        except KeyError:
            LOGGER.warning('Nonexistent attribute `%s` was tried to be accessed.', item)
            raise AttributeError


class BotsConfigBase(ConfigMixin):

    # attributes of bots' parameters, that are accessed,
    # but have no use inside n6 pipeline
    unused_options = [
        'redis_cache_host',
        'redis_cache_port',
        'redis_cache_db',
        'redis_cache_password',
    ]
    # options that should be set to None if not declared in config,
    # that are directly accessed by IntelMQ, so they have to exist
    default_none_options = [
        'http_proxy',
        'https_proxy',
    ]
    default_user_agent = ('Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36')
    general_config_spec = '''
    [intelmq]
    cache_ttl = 600 :: int
    http_user_agent = {user_agent}
    ...
    '''.format(user_agent=default_user_agent)
    config_ttl_opt_name = 'cache_ttl'
    parameter_ttl_opt_name = 'redis_cache_ttl'

    def __init__(self, **fmt_args):
        self.config = Config.section(self.general_config_spec)
        if self.is_config_spec_or_group_declared():
            self.config.update(self.get_config_section(**fmt_args))
        self.parameters = self.config.copy()
        config_ttl = self.parameters.get(self.config_ttl_opt_name)
        if config_ttl:
            self.parameters[self.parameter_ttl_opt_name] = config_ttl
            del self.parameters[self.config_ttl_opt_name]
        if self.unused_options:
            self.parameters.update({key: None for key in self.unused_options})
        if self.default_none_options:
            self.parameters.update({key: None for key in self.default_none_options
                                    if key not in self.parameters})

    def get_n6_config(self):
        return self.config

    def make_parameter_provider(self):
        return BotParameterProvider(self.parameters)


class GenericBotConfig(BotsConfigBase):

    config_spec_pattern = '''
    [{bot_classname}]
    routing_state = {routing_state}
    input_messages_type = {msg_type}
    ...
    '''


class GenericCollectorConfig(BotsConfigBase):

    config_spec_pattern = '''
    [{bot_classname}]
    routing_state = {routing_state}
    input_messages_type = {msg_type}
    feed = {feed}
    accuracy = {accuracy} :: float
    source_label = {source_label}
    source_channel = {source_channel}
    ...
    '''


class GenericParserConfig(BotsConfigBase):

    config_spec_pattern = '''
    [{bot_classname}]
    routing_state = intelmq-parsed
    input_messages_type = {msg_type}
    default_binding_key = {default_bk}
    category
    ...
    '''


class ASNLookupExpertBotConfig(BotsConfigBase):

    config_spec = '''
    [ASNLookupExpertBot]
    database
    ...
    '''


class CymruExpertBotConfig(BotsConfigBase):

    config_spec = '''
    [CymruExpertBot]
    queue_name = cymru-whois
    input_messages_type = event
    ...
    '''


class FieldReducerExpertBotConfig(BotsConfigBase):

    """
    Config class for the `FieldReducerExpertBot`.

    The bot can work in two modes (`type` config option):
    `whitelist` or `blacklist`.

    In a `blacklist` mode it removes message fields from
    `keys` list, in `whitelist` - accepts only fields from
    `keys` list.

    Configure `type` (work mode) and `keys` (list of fields)
    options.
    """

    config_spec = '''
    [FieldReducerExpertBot]
    queue_name = field-reducer-bot
    input_messages_type = event
    type = blacklist
    keys :: list_of_str
    ...
    '''


class GeoIPExpertBotConfig(BotsConfigBase):

    DBPATH = INTELMQ_TOOLS_PATH / 'data' / 'GeoLite2-City.mmdb'

    config_spec = '''
    [GeoIPExpertBot]
    input_messages_type = event
    database = {}
    ...
    '''.format(DBPATH)


class RIPENCCExpertBotConfig(BotsConfigBase):

    config_spec = '''
    [RIPENCCExpertBot]
    input_messages_type = event :: str
    query_ripe_db_asn = true
    query_ripe_db_ip = true
    query_ripe_stat_asn = true
    query_ripe_stat_ip = true
    ...
    '''
    default_converter = 'bool'


class TorExpertBotConfig(BotsConfigBase):

    DBPATH = INTELMQ_TOOLS_PATH / 'data' / 'latest'

    config_spec = '''
    [TorExpertBot]
    database = {db_path}
    '''.format(db_path=DBPATH)


class ModifyExpertBotConfig(BotsConfigBase):

    DBPATH = INTELMQ_TOOLS_PATH / 'data' / 'modify.conf'

    config_spec = '''
    [ModifyExpertBot]
    configuration_path = {conf_path}
    '''.format(conf_path=DBPATH)

    @staticmethod
    def _new_iter(self):
        verify_callers_path(inspect.stack()[1][1], type(self))
        for i in self['temp_bot_config']:
            yield i

    class FakeClass:
        """
        Instance of this class will be used as a temporary `self`
        for an `init()` method of the `ModifyExpertBot`.
        """
        def __init__(self, parameters):
            self.config = None
            self.parameters = parameters

    def _get_new_init(self, original_meth):
        fake_instance = self.FakeClass(self.make_parameter_provider())
        def inner(inner_self):
            # replace instance of a `QueuedBaseExtended` class
            # with instance of a `FakeClass` as a `self` for bot's
            # `init()` method, in order to avoid overriding this
            # instance's `config` attribute
            original_meth(fake_instance)
            inner_self.config['temp_bot_config'] = fake_instance.config
        return inner

    def patch_subclass(self, bot_class):
        """
        Patch ModifyExpertBot's `init()` method to avoid overriding
        a `config` attribute of a `QueuedBaseExtended` instance
        - there is a name conflict (bot's class instance uses
        identically named attribute - `config`).

        Instead of overriding a `config` attribute - copy its content
        to the original `config` as its key. Then modify `config`'s
        behavior, if it is being accessed as iterator - iterate
        through bot's config, not original content.
        """
        original_meth = bot_class.init
        bot_class.init = self._get_new_init(original_meth)
        self.config.__class__.__iter__ = self._new_iter


# output bots

class FilesOutputBotConfig(BotsConfigBase):

    config_spec = '''
    [FilesOutputBot]
    routing_key = files-output-bot
    input_message_type = event
    tmp = /tmp/intel_tmp
    dir = /tmp/intel_events
    suffix: .json
    hierarchical_output: false :: bool
    single_key: false :: bool
    ...
    '''

# collector bots

class Malc0deCollectorConfig(BotsConfigBase):

    config_spec = '''
    [Malc0deCollector]
    source_label = malc0de
    source_channel = intelmq
    feed = malc0de
    accuracy = 50.00 :: float
    ...
    '''


# parsers bots

class Malc0deParserBotConfig(BotsConfigBase):

    config_spec = '''
    [Malc0deParserBot]
    default_binding_key = malc0de.intelmq
    restriction = need-to-know
    confidence = low
    category = bots
    '''

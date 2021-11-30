# Copyright (c) 2021 NASK. All rights reserved.

import importlib
import logging

from intelmq import RUNTIME_CONF_FILE
from intelmq.lib import bot
from intelmq.lib.utils import load_configuration

from n6datapipeline.intelmq import bots_config
from n6lib.argument_parser import N6ArgumentParser
from n6lib.config import ConfigError
from n6lib.log_helpers import logging_configured


LOGGER = logging.getLogger(__name__)


class IntelMQWrapper:

    INTELMQ_BOTS_PATH = 'intelmq.bots'
    BOT_CATEGORIES = ['expert', 'collector', 'output', 'parser']
    BOT_CATEGORIES_TO_MODULES = {cat + 's': cat for cat in BOT_CATEGORIES}
    BOT_CLASSNAME_CONST = 'BOT'
    RUNTIME_CONF_N6_SECTION_NAME = 'n6config'
    DEFAULT_MESSAGE_TYPE = 'event'
    DEFAULT_CHANNEL = 'intelmq'
    DEFAULT_ACCURACY = 50.0

    DESCRIPTION = ("Run IntelMQ bot by providing bot's ID, which needs to be defined in "
                   "the IntelMQ runtime config (runtime.yaml). Path of the config file depends "
                   "on IntelMQ's configuration. It may be: '/opt/intelmq/etc/runtime.yaml' or "
                   "'/etc/intelmq/runtime.yaml' etc. The bot ID section must provide the "
                   "'module' option - its value must be the path of the bot's module. "
                   "You can, or for some types of bots, like parser bots, you must add the "
                   f"{RUNTIME_CONF_N6_SECTION_NAME!a} option in bot's section. The option "
                   f"is not recognized by IntelMQ, but allows to configure bot's instance "
                   f"running within n6 pipeline.")

    def __init__(self):
        self._arguments = self._get_parsed_args(self.DESCRIPTION)
        self.runtime_conf = load_configuration(RUNTIME_CONF_FILE)
        self.bot_id = self._arguments.BOT_ID
        try:
            self.bot_config = self.runtime_conf[self.bot_id]
        except KeyError:
            raise ConfigError(f'Bot ID: {self.bot_id} could not be found in the '
                              f'IntelMQ runtime config')
        module_path = self._get_bots_module_path()
        self.bot_class = self._import_bot(module_path)
        self._bot_category = None

    def _get_parsed_args(self, description):
        parser = N6ArgumentParser(description=description)
        parser.add_argument('BOT_ID', help="Bot ID defined in the IntelMQ runtime config.")
        parser.add_argument('-e', '--exception-proof',
                            help='Run the bot in the "exception-proof" mode, where it will '
                                 'send forward incoming messages, even if an exception '
                                 'is raised',
                            dest='exproof',
                            action="store_true")
        return parser.parse_args()

    def _get_bots_module_path(self):
        try:
            return self.bot_config['module']
        except KeyError:
            raise ConfigError(f"The runtime config of bot ID: f{self.bot_id} does "
                              f"not provide the 'module' option")

    def _import_bot(self, module_path):
        bot_module = importlib.import_module(module_path)
        # TO CONSIDER: maybe reimplement the option
        # if self._arguments.classname:
        #     return getattr(bot_module, self._arguments.classname)
        return bot_module.BOT

    @staticmethod
    def _join_paths(path_a, path_b):
        return '{a}.{b}'.format(a=path_a, b=path_b)

    @staticmethod
    def _get_classname_or_none(bot_class, do_load_bot_config):
        if do_load_bot_config:
            return bot_class.__name__
        return None

    @staticmethod
    def _create_default_source(bot_classname):
        lower_classname = bot_classname.lower()
        if lower_classname.endswith('bot'):
            lower_classname = lower_classname[:-3]
        if lower_classname.endswith('collector'):
            lower_classname = lower_classname[:-9]
        elif lower_classname.endswith('parser'):
            lower_classname = lower_classname[:-6]
        return lower_classname

    @classmethod
    def _do_patching(cls, bot_class, bot_id, bot_config,
                     exception_proof=False):
        # LEGACY: loading configuration for IntelMQ bots from
        # the n6 config files
        # config_instance = cls.load_config_for_bot(bot_class, bot_type, do_load_bot_config)

        # delete bot's instance method, which shadows the n6
        # pipeline-specific method
        try:
            del bot_class.run
        except AttributeError:
            # the method is not present in all types of bots
            pass
        # LEGACY: Bot's parameters patching
        # bot.Bot.parameters = get_parameters(config_instance)
        bot.Bot.bot_id = bot_id
        # a little hacks to provide the private `__bot_id` attribute
        # to the `__load_runtime_configuration_method`
        setattr(bot_class, f'_{bot_class.__name__}__bot_id', bot_id)
        setattr(bot_class, f'_Bot__bot_id', bot_id)
        bot.Bot.exception_proof = exception_proof
        bot.Bot.config = bot_config.get(cls.RUNTIME_CONF_N6_SECTION_NAME, {})
        # LEGACY
        # bot.Bot.n6config = config_instance.get_n6_config()
        # if hasattr(config_instance, 'patch_subclass'):
        #     config_instance.patch_subclass(bot_class)

    @staticmethod
    def _do_run(bot_class):
        with logging_configured():
            bot_instance = bot_class()
            bot_instance.run()

    @classmethod
    def load_config_for_bot(cls, bot_class, bot_type, do_load_bot_config):
        # LEGACY: confirm it should be removed
        bot_classname = cls._get_classname_or_none(bot_class, do_load_bot_config)
        if bot_classname:
            config_class = getattr(bots_config, bot_classname + 'Config', None)
            if config_class is None:
                if bot_type == 'collector':
                    default_source = cls._create_default_source(bot_classname)
                    return bots_config.GenericCollectorConfig(bot_classname=bot_classname,
                                                              routing_state=bot_classname.lower(),
                                                              msg_type='report',
                                                              feed=bot_classname.lower(),
                                                              accuracy=cls.DEFAULT_ACCURACY,
                                                              source_label=default_source,
                                                              channel_label=cls.DEFAULT_CHANNEL)
                elif bot_type == 'parser':
                    default_source = cls._create_default_source(bot_classname)
                    return bots_config.GenericParserConfig(bot_classname=bot_classname,
                                                           msg_type=cls.DEFAULT_MESSAGE_TYPE,
                                                           default_bk='{}.{}'.format(
                                                                default_source,
                                                                cls.DEFAULT_CHANNEL))
                return bots_config.GenericBotConfig(bot_classname=bot_classname,
                                                    routing_state=bot_classname.lower(),
                                                    msg_type=cls.DEFAULT_MESSAGE_TYPE)
            else:
                return config_class()
        else:
            # `bot_classname` is set to None, if it is chosen
            # not to load bot's config
            return bots_config.BotsConfigBase()

    @classmethod
    def run_external(cls, bot_class, bot_id, exception_proof=False):
        """
        Helper class method allowing to quickly run the wrapped bot
        without having to instantiate the class or to pass command
        line arguments - the arguments are passed as the method's
        arguments.

        Args/kwargs:
            `bot_class` (str):
                Name of the class implementing the bot.
            `bot_type` (str):
                Type of the bot; allowed values: 'default', 'expert',
                    'collector', 'output', 'parser'.
            `exception_proof` (bool; default: False):
                If True, the "exception proof" mechanism will
                be enabled.
            `load_bot_config` (bool; default: False):
                Should the bot-specific configuration be loaded.
        """
        # cls._verify_bot_type(bot_type)
        bot_config = {}
        cls._do_patching(bot_class, bot_config, bot_id, exception_proof)
        cls._do_run(bot_class)

    def run_intelmq_bot(self):
        self._do_patching(self.bot_class,
                          self.bot_id,
                          self.bot_config,
                          exception_proof=self._arguments.exproof)
        self._do_run(self.bot_class)


def main():
    wrapper = IntelMQWrapper()
    wrapper.run_intelmq_bot()


if __name__ == '__main__':
    main()

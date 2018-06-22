# Copyright (c) 2013-2018 NASK. All rights reserved.

from argparse import Action, ArgumentParser


class N6ConfigValuesAction(Action):

    """
    Custom argparser argument's action implementation.

    Splits arguments provided by user into dictionary
    which holds dictionaries with values for various
    options of config sections.
    """

    def __init__(self, option_strings, dest, nargs='*', **kwargs):
        super(N6ConfigValuesAction, self).__init__(option_strings, dest, nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        custom_config_values = {}
        for value in values:
            section_option, section_option_value = value.split('=')
            section, option = section_option.split('.')
            if section in custom_config_values:
                custom_config_values[section][option] = section_option_value
            else:
                custom_config_values[section] = {option: section_option_value}
        setattr(namespace, self.dest, custom_config_values)


class N6ArgumentParser(ArgumentParser):

    """
    Generic argument parser for N6Core scripts.

    This is an implementation of ArgumentParser for N6 project
    which has arguments used by all scripts.

    Command line arguments provided by this class::
        --n6config-override:
            makes it possible to override any N6Core script configuration
            options for the particular script run.
    """

    def __init__(self, *args, **kwargs):
        super(N6ArgumentParser, self).__init__(*args, **kwargs)

        if not self.description:
            self.description = "n6-specific options"
        self.add_argument('--n6config-override',
                          action=N6ConfigValuesAction,
                          default={},
                          help=('override the script\'s config options '
                                'for the particular run. Provide options '
                                'in given format: `<section>.<option>=<value>`. If you '
                                'want to provide more than one option separate '
                                'each of them using space, eg. `<section1>.<option1>=<value> '
                                '<section1>.<option2>=<value>`'))

    def get_config_overridden_dict(self):
        # Here we use (implicitly) global state: sys.argv.  It may feel a bit
        # magic from the caller's point of view (see: n6lib.config...) -- but
        # thanks to that the code is simpler because we do not need to transfer
        # the command-line arguments information explicitly.
        cmdline_args, _ = self.parse_known_args()
        return cmdline_args.n6config_override

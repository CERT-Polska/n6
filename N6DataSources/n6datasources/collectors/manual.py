# Copyright (c) 2013-2023 NASK. All rights reserved.

import argparse
import datetime
import gzip
import os
import sys

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    add_collector_entry_point_functions
)
from n6lib import const as n6const
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


def existing_file(file_path):
    """
    'type' for argparse that checks that the file exists but does not open it.
    """
    if not os.path.exists(file_path):
        raise argparse.ArgumentTypeError("{0} does not exist".format(file_path))
    return file_path


def validate_datetime(datestr):
    if not datestr:
        return None
    try:
        try:
            return parse_iso_datetime_to_utc(datestr)
        except ValueError:
            return datetime.datetime.strptime(datestr, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError("This value must be datetime formatted e.g. '%%Y-%%m-%%dT%%H:%%M', '%%Y-%%m-%%d'")


def validate_singlechar(input_str):
    if len(input_str) != 1:
        raise argparse.ArgumentTypeError("This value must be a single char")
    return input_str


def validate_do_not_resolve_fqdn(_do_not_resolve_fqdn):
    if _do_not_resolve_fqdn in ('True', 'true', True):
        return True
    elif _do_not_resolve_fqdn in (False, "False", 'false', ''):
        return False
    else:
        raise argparse.ArgumentTypeError("This value must be True, False or blank")


class ManualCollector(BaseSimpleCollector):

    raw_type = 'file'
    content_type = 'text/plain'

    config_spec_pattern = None
    config = {}

    MANUAL_SOURCE_CHANNELS = ['unrestricted', 'pl']

    def _ask_interactive_question(self, msg, choices=None, allow_n=True, validate=None):
        print(f'\n{msg}')

        if choices is None:
            while True:
                input_ = input()
                try:
                    if validate is not None:
                        return validate(input_)
                    return input_
                except:
                    sys.stdout.write("Please provide valid input: \n")

        for num, opt in enumerate(choices):
            print("  [{0}] {1}".format(num, opt))
        if allow_n:
            print("  [n] None - value defined in submitted file")

        while True:
            choice = input().lower()
            if allow_n and choice == 'n':
                return None
            else:
                try:
                    pos = int(choice)
                    return_value = choices[pos]
                    return return_value
                except:
                    sys.stdout.write("Please respond with a valid choice: ")

    def get_arg_parser(self):
        arg_parser = super(ManualCollector, self).get_arg_parser()
        arg_parser.add_argument('-i', '--interactive', help="interactive data submission, if set other options are ignored", action='store_true')
        arg_parser.add_argument('-f', '--final_run', help="save data to n6, default: dry_run first to test parsing", action='store_true')
        arg_parser.add_argument('--source_channel', help="source_channel, e.g. manual.unrestricted or manual.pl",
            choices=self.MANUAL_SOURCE_CHANNELS)
        arg_parser.add_argument('--category', help="n6 category", choices=n6const.CATEGORY_ENUMS)
        arg_parser.add_argument('--confidence', help="n6 confidence level", choices=n6const.CONFIDENCE_ENUMS)
        arg_parser.add_argument('--restriction', help="n6 visibility restriction", choices=n6const.RESTRICTION_ENUMS)
        arg_parser.add_argument('--name', help="name of the threat")
        arg_parser.add_argument('--origin', help="n6 origin of data", choices=n6const.ORIGIN_ENUMS)
        arg_parser.add_argument('--dataset', help="describe where the data comes from")
        arg_parser.add_argument('--time', help="UTC event time (if not provided in submitted file)"
                                                " e.g. '%%Y-%%m-%%dT%%H:%%M', '%%Y-%%m-%%d'", type=validate_datetime)
        arg_parser.add_argument('--field_sep', help="Character separating columns (default: ,)", type=validate_singlechar, default=',')
        arg_parser.add_argument('--comment_prefix', help="Character starting comments (default: #)", type=validate_singlechar, default='#')
        arg_parser.add_argument('--column_spec', help="Instructions for n6 parser how to interpret columns", default=None)
        arg_parser.add_argument('--time_format', help="Instructions how to parse date and time in the file, e.g. %%m/%%d/%%Y %%H:%%M"
                                                      "(default: ISO formatted or UNIX timestamp)", default=None)
        arg_parser.add_argument('--skip_fqdn_to_ip', help="Instructions for n6 enricher. Do not resolve fqdn to ip."
                                                          " Default: False, if used: return True",
                                                          default=False, action='store_true',)

        arg_parser.add_argument('input_file', help="file to submit to n6", type=existing_file, metavar="FILE")
        self.arg_parser = arg_parser
        return arg_parser
    
    def set_configuration(self) -> None:
        return None
    
    def get_source(self, **processed_data):
        if self.cmdline_args.interactive:
            sc = self._ask_interactive_question("Select source channel: ", self.MANUAL_SOURCE_CHANNELS, allow_n=False)
        else:
            sc = self.cmdline_args.source_channel
            if sc is None:
                self.arg_parser.error("argument --source_channel is required")
        return 'manual.{0}'.format(sc)

    def obtain_data_body(self, **kwargs):
        input_file = self.cmdline_args.input_file
        is_gzip = False
        with open(input_file, "rb") as f:
            if (f.read(2) == b'\x1f\x8b'):
                is_gzip = True
        if is_gzip:
            with gzip.open(input_file, "rb") as f:
                result = f.read()
        else:
            with open(input_file, "rb") as f:
                result = f.read()
        return result

    def _get_event_base(self, **kwargs):
        """Get base event data from cmdline_args or interactive mode
        """
        event_base = {}
        if self.cmdline_args.interactive:
            print("\n\nPlease provide base information about submitted events.")
            print("If the submitted file contains relevant columns use 'n' option.")
            print("Submission will fail if some mandatory fields are missing.\n")
            event_base['category'] = self._ask_interactive_question("Select category:", n6const.CATEGORY_ENUMS)
            event_base['confidence'] = self._ask_interactive_question("Select confidence level:", n6const.CONFIDENCE_ENUMS)
            event_base['restriction'] = self._ask_interactive_question("Select visibility restriction:", n6const.RESTRICTION_ENUMS)
            event_base['name'] = self._ask_interactive_question("What is name of the threat (optional)")
            event_base['origin'] = self._ask_interactive_question("Select origin of data", n6const.ORIGIN_ENUMS)
            event_base['dataset'] = self._ask_interactive_question("Describe where data comes from:")
            event_base['time'] = self._ask_interactive_question(
                "UTC event time (if not provided in submitted file)"
                " e.g.: '%Y-%m-%dT%H:%M' or '%Y-%m-%d':",
                validate=validate_datetime
            )
        else:
            event_base['category'] = self.cmdline_args.category
            event_base['confidence'] = self.cmdline_args.confidence
            event_base['restriction'] = self.cmdline_args.restriction
            event_base['name'] = self.cmdline_args.name
            event_base['origin'] = self.cmdline_args.origin
            event_base['dataset'] = self.cmdline_args.dataset
            event_base['time'] = self.cmdline_args.time
        return event_base
    
    def _get_parsing_info(self, **kwargs):
        parsing_info = {}
        if self.cmdline_args.interactive:
            print("\n\nPlease provide information how to parse submitted file.")
            print("Parser reads tabular data with defined separator and comment characters")
            print("First line of the file may be a comment and provide information about columns and n6 field names, e.g.:")
            print("#ip,url,-,-,time")
            print("use '-' to skip the column, any other value should be a valid n6 field name.\n")
            parsing_info['field_separator'] = self._ask_interactive_question("Input column separator char: ", validate=validate_singlechar)
            parsing_info['comment_prefix'] = self._ask_interactive_question("Input comment prefix char: ", validate=validate_singlechar)
            parsing_info['column_spec'] = self._ask_interactive_question(
                "Enter parsing instructions for the parser (i.e. column specification), e.g.:\n"
                "time,-,ip,url,-,-\n"
                "Leave blank if submitted file contains parsing info in the first line."
            )
            parsing_info['time_format'] = self._ask_interactive_question(
                "How to parse date and time in the file, e.g. %m/%d/%Y %H:%M\n"
                "Leave blank if time and date in the file are ISO formatted or are UNIX timestamp"
                )
        else:
            parsing_info['field_separator'] = self.cmdline_args.field_sep
            parsing_info['comment_prefix'] = self.cmdline_args.comment_prefix
            parsing_info['column_spec'] = self.cmdline_args.column_spec
            parsing_info['time_format'] = self.cmdline_args.time_format
        return parsing_info

    def get_output_prop_kwargs(self, **kwargs):
        prop_kwargs = super(ManualCollector,
                            self).get_output_prop_kwargs(**kwargs)
        if 'meta' not in prop_kwargs['headers']:
            prop_kwargs['headers']['meta'] = {}
        prop_kwargs['headers']['meta']['event_base'] = self._get_event_base()
        prop_kwargs['headers']['meta']['parsing_info'] = self._get_parsing_info()
        if self.cmdline_args.interactive:
            prop_kwargs['headers']['meta']['dry_run'] = True
            prop_kwargs['headers']['_do_not_resolve_fqdn_to_ip'] = validate_do_not_resolve_fqdn(self._ask_interactive_question(
                                                                        "Do not resolve fqdn to ip (True or False).\n"
                                                                        "Leave blank if False",
                                                                        validate=validate_do_not_resolve_fqdn
                                                                        ))
        else:
            prop_kwargs['headers']['_do_not_resolve_fqdn_to_ip'] = self.cmdline_args.skip_fqdn_to_ip
            if not self.cmdline_args.final_run:
                prop_kwargs['headers']['meta']['dry_run'] = True
        return prop_kwargs

    def run_collection(self):
        input_data = self.obtain_input_pile()
        self._output_components = self.get_output_components(**input_data)
        self.run()
        LOGGER.info('Stopped')
    
    def start_publishing(self):
        if self.cmdline_args.interactive:
            print("Publishing data to n6...")
        self.publish_output(*self._output_components)
        if self.cmdline_args.interactive:
            print("Waiting for response...")
        self._output_components = None
        LOGGER.debug('Stopping')
        self.inner_stop()


add_collector_entry_point_functions(__name__)


if __name__ == "__main__":
    ManualCollector.run_script()

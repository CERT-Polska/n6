# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
from io import StringIO

from n6lib.log_helpers import get_logger
from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6datapipeline.base import n6QueueProcessingException
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


class ManualParser(BaseParser):

    default_binding_key = "manual.*"

    constant_items = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.cmdline_args.n6heartbeat:
            self._conn_params_dict['heartbeat_interval'] = self.cmdline_args.n6heartbeat

    def parse(self, data):
        parsing_info = data['meta']['parsing_info']
        event_base = data['meta']['event_base']

        empty_keys = [key for key in event_base.keys() if not event_base[key]]
        for key in empty_keys:
            del event_base[key]

        data_rows = StringIO(data['raw'].decode('utf-8'))

        if parsing_info['column_spec']:
            columns = parsing_info['column_spec'].split(',')
        else:
            header_row = data_rows.readline()
            if not header_row.startswith(parsing_info['comment_prefix']):
                raise n6QueueProcessingException("Missing header and no column_spec specified")
            columns = header_row[1:].strip().split(',')
            
        for data_line in data_rows:
            if data_line.startswith(parsing_info['comment_prefix']):
                continue
            with self.new_record_dict(data) as parsed:
                data_columns = data_line.strip().split(parsing_info['field_separator'])
                if len(data_columns) != len(columns):
                    raise AdjusterError("Invalid file format: column_spec does not match file content\n"
                                        "column_spec: {0}\n"
                                        "parsed_row: {1}\n".format(columns, data_line)
                                        )
                parsed.update(event_base)
                for position, column_name in enumerate(columns):
                    if column_name == '-':
                        continue
                    if column_name == 'time':
                        if parsing_info['time_format']:
                            try:
                                parsed['time'] = datetime.datetime.strptime(data_columns[position], parsing_info['time_format'])
                            except ValueError as e:
                                raise AdjusterError(str(e))
                        else:
                            try:
                                timestamp = float(data_columns[position])
                                parsed['time'] = datetime.datetime.utcfromtimestamp(timestamp)
                            except ValueError:
                                try:
                                    parsed['time'] = parse_iso_datetime_to_utc(data_columns[position])
                                except ValueError as e:
                                    raise AdjusterError(str(e))
                    elif column_name == 'ip':
                        parsed['address'] = {column_name: data_columns[position]}
                    else:
                        parsed[column_name] = data_columns[position]
                yield parsed

    def get_arg_parser(self):
        arg_parser = super(ManualParser, self).get_arg_parser()
        arg_parser.add_argument('--n6heartbeat', help="Heartbeat value.", default=None, type=int)
        return arg_parser


add_parser_entry_point_functions(__name__)

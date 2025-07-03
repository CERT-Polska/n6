# Copyright (c) 2020-2025 NASK. All rights reserved.

"""
Parsers: `cert-pl.shield`.
"""

import csv

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import (
    ProblematicTimeValueError,
    datetime_with_tz_to_utc,
    parse_iso_datetime_to_utc,
)
from n6lib.log_helpers import get_logger
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


class CertPlShieldParser(BaseParser):

    default_binding_key = 'cert-pl.shield'

    constant_items = {
        "restriction": "public",
        "confidence": "high",
        "category": "phish",
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter='\t', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # <in-register id>,<domain address>,<insertion date+time (time zone Europe/Warsaw)>,...
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['fqdn'] = row[1]
                    parsed['time'] = datetime_with_tz_to_utc(row[2], 'Europe/Warsaw')
                except ProblematicTimeValueError as exc:
                    raise AdjusterError(str(exc))
                yield parsed


class CertPlShield202505Parser(BaseParser):

    default_binding_key = 'cert-pl.shield.202505'

    constant_items = {
        "restriction": "public",
        "confidence": "high",
        "category": "phish",
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter='\t', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # <in-register id>,<domain address>,<insertion date+time (time zone UTC)>,...
            with self.new_record_dict(data) as parsed:
                try:
                    parsed['fqdn'] = row[1]
                    parsed['time'] = parse_iso_datetime_to_utc(row[2])
                except ProblematicTimeValueError as exc:
                    raise AdjusterError(str(exc))
                yield parsed


add_parser_entry_point_functions(__name__)

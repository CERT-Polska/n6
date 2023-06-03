# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Parser: `zoneh.rss`.
"""

import datetime
import json
import re

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class ZonehRssParser(BaseParser):

    default_binding_key = "zoneh.rss"
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'deface',
    }

    fqdn_regex = re.compile(r'''
        \A
        (\w+://)?       # optional protocol part (e.g. http://)
        (?P<fqdn>
        [^:/]+)         # proper FQDN part, everything except ':' and '/'
                        # more precise parsing is done inside RecordDict.adjust_fqdn() method
        (/.*)?          # optional slash and any following character
        \Z
        ''', re.VERBOSE | re.ASCII)

    datetime_regex = re.compile(r'''
        (?P<datetime>
        \w{3},[ ]       # abbreviated name of the day
        \d{2}[ ]        # number of the day
        \w{3}[ ]        # abbreviated name of the month
        \d{4}[ ]        # year
        (\d{2}:?){3})   # time in HH:MM:SS format
        [ ]
        (?P<offset>
        [+-]\d{4})      # UTC offset
        ''', re.VERBOSE | re.ASCII)

    datetime_format = "%a, %d %b %Y %H:%M:%S"
    iso_format = "%Y-%m-%d %H:%M:%S"

    def parse(self, data):
        raw_events = json.loads(data['raw'])
        for event in raw_events:
            with self.new_record_dict(data) as parsed:
                url = event[0]  # 'title' part of the message
                parsed['fqdn'] = self._get_fqdn_from_url(url)
                # if fqdn was not valid (so it was not added to the
                # record dict), it does not make sense to emit the event
                if 'fqdn' not in parsed:
                    continue
                if event[2]:    # 'pubDate' part of the message
                    parsed['time'] = self._normalize_datetime(event[2])
                else:
                    parsed['time'] = data['properties.timestamp']
                yield parsed

    @classmethod
    def _get_fqdn_from_url(cls, url):
        """
        Use regular expressions to extract FQDN from the passed URL.

        Args:
            `url`:
                URL from the RSS stream.

        Returns:
            Fully Qualified Domain Name extracted from the URL, as
            a string
        """
        match = cls.fqdn_regex.search(url)
        if match:
            return match.group('fqdn')
        return None

    @classmethod
    def _normalize_datetime(cls, source_datetime):
        """
        Extract date and time of last update from the source,
        use information about time zone offset, to normalize it to
        the naive :class:datetime.datetime instance.

        Args:
            `source_datetime`:
                String with date and time in custom format.

        Returns:
            *ISO-8601*-formatted datetime as a string.
        """
        # This helper method doesn't use a '%z' directive as a part of
        # the 'format' argument for the datetime.datetime.strptime()
        # method, to match the offset part of a string, because its
        # functioning is platform-dependent, and it doesn't always work.
        match = cls.datetime_regex.search(source_datetime)
        naive_datetime = datetime.datetime.strptime(match.group('datetime'), cls.datetime_format)
        offset = match.group('offset')  # Format: +HHMM or -HHMM
        iso_datetime = datetime.datetime.strftime(naive_datetime, cls.iso_format)
        # Concatenate *ISO-8601*-formatted datetime string and UTC offset.
        iso_datetime += offset
        return iso_datetime


add_parser_entry_point_functions(__name__)

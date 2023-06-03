# Copyright (c) 2014-2023 NASK. All rights reserved.

"""
Parsers: `abuse-ch.feodotracker.202110` (TODO: other `abuse-ch` parsers...).
"""

import csv
import json

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger
from n6sdk.encoding_helpers import ascii_str

LOGGER = get_logger(__name__)


class AbuseChFeodoTracker202110Parser(BaseParser):

    default_binding_key = 'abuse-ch.feodotracker.202110'

    constant_items = {
            'restriction': 'public',
            'confidence': 'medium',
            'category': 'cnc',
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # first_seen_utc,dst_ip,dst_port,c2_status,last_online,malware
            t, ip, dport, _, _, name = row
            with self.new_record_dict(data) as parsed:
                parsed.update({
                    'time': t,
                    'address': {'ip': ip},
                    'dport': dport,
                    'name': name,
                })
                yield parsed


class AbuseChSslBlacklist201902Parser(BaseParser):
    # Note that, contrary to its name, it is an *event-based* source.

    default_binding_key = "abuse-ch.ssl-blacklist.201902"

    constant_items = {
            "restriction": "public",
            "confidence": "low",
            "category": "cnc",
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # Listingdate,SHA1,Listingreason
            t, x509fp_sha1, name = row
            with self.new_record_dict(data) as parsed:
                parsed.update({
                    'time': t,
                    'x509fp_sha1': x509fp_sha1,
                    'name': name,
                })
                yield parsed


class AbuseChUrlhausUrls202001Parser(BaseParser):

    default_binding_key = 'abuse-ch.urlhaus-urls.202001'

    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "malurl",
    }

    def parse(self, data):
        raw_events = json.loads(data['raw'])
        for event in raw_events:
            if event['url_info_from_api'].get('payloads'):
                for payload in event['url_info_from_api']['payloads']:
                    with self.new_record_dict(data) as parsed:
                        parsed['time'] = event['dateadded']
                        parsed['url'] = event['url']
                        parsed['md5'] = payload['response_md5']
                        parsed['sha256'] = payload['response_sha256']
                        if payload.get('signature'):
                            parsed['name'] = payload['signature'].lower()
                        if payload.get('filename'):
                            parsed['filename'] = payload['filename']
                        yield parsed
            else:
                with self.new_record_dict(data) as parsed:
                    parsed['time'] = event['dateadded']
                    parsed['url'] = event['url']
                    if event['url_info_from_api']['query_status'] == "no_results":
                        LOGGER.warning('No results in API response for '
                                       'url: %r, url_id: %r.',
                                       event['url'],
                                       event['url_id'])
                    yield parsed


class AbuseChUrlhausPayloadsUrlsParser(BaseParser):

    default_binding_key = 'abuse-ch.urlhaus-payloads-urls'

    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "malurl",
    }

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # firstseen,url,filetype,md5,sha256,signature
            with self.new_record_dict(data) as parsed:
                parsed['time'] = row[0]
                parsed['url'] = row[1]
                parsed['md5'] = row[3]
                parsed['sha256'] = row[4]
                name = ascii_str(row[5]).strip().lower()
                if name not in ('', 'none', 'null'):
                    parsed['name'] = name
                yield parsed


add_parser_entry_point_functions(__name__)

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

import csv
import datetime
import json
import re
import sys
from cStringIO import StringIO

from n6.parsers.generic import (
    BaseParser,
    BlackListTabDataParser,
    entry_point_factory,
)
from n6lib.common_helpers import ascii_str
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger
from n6lib.record_dict import AdjusterError


LOGGER = get_logger(__name__)


class MissingItemsException(Exception):
    """Raised when key items needed to create an event are missing."""


#
# Mix-in classes providing common stuff for abuse.ch parsers

class _BaseMixIn(object):

    ignored_row_prefixes = '#'
    field_sep = '\t'
    skip_blank_rows = True

    @staticmethod
    def _get_expires(time):
        return (parse_iso_datetime_to_utc(time) +
                datetime.timedelta(days=2))


class _DomsMixIn(_BaseMixIn):

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        '_do_not_resolve_fqdn_to_ip': True,  # parser is only for archived data
    }

    def process_row_fields(self, data, parsed,
                           fqdn, ips=None, _asns=None):
        if ',' in fqdn:
            # we assume that always only one domain is given per row; if not...
            raise AssertionError('Nobody expects the FQDN-ish Pluralition!')
        parsed['fqdn'] = fqdn
        if ips:
            parsed['address'] = [{'ip': ip.strip()}
                                 for ip in ips.split(',')]
        elif 'fqdn' not in parsed:  # <- may not have been stored if invalid
            raise AdjusterError('fqdn {!r} is not a valid domain '
                                'and there are no IPs -- so the '
                                'event is a rubbish'.format(fqdn))
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = self._get_expires(data['properties.timestamp'])
        return parsed


class _DomsMixIn201406(_BaseMixIn):

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def process_row_fields(self, data, parsed,
                           fqdn):
        if ',' in fqdn:
            # we assume that always only one domain is given per row; if not...
            raise AssertionError('Nobody expects the FQDN-ish Pluralition!')
        parsed['fqdn'] = fqdn
        if 'fqdn' not in parsed:  # <- may not have been stored if invalid
            raise AdjusterError('fqdn {!r} is not a valid domain'.format(fqdn))
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = self._get_expires(data['properties.timestamp'])
        return parsed


class _IpsMixIn(_BaseMixIn):

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def process_row_fields(self, data, parsed,
                           ip, *rest):
        parsed['address'] = {'ip': ip}
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = self._get_expires(data['properties.timestamp'])
        return parsed


class _IpsMixIn201406(_BaseMixIn):

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def process_row_fields(self, data, parsed,
                           ip, *rest):
        parsed['address'] = {'ip': ip}
        parsed['time'] = data['properties.timestamp']
        parsed['expires'] = self._get_expires(data['properties.timestamp'])
        return parsed


#
# Actual parser classes


# Spyeye
class AbuseChSpyeyeDoms201406Parser(_DomsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.spyeye-doms.201406'
    constant_items = dict(_DomsMixIn201406.constant_items, name='spyeye')

class AbuseChSpyeyeDomsParser(_DomsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.spyeye-doms'
    constant_items = dict(_DomsMixIn.constant_items, name='spyeye')

class AbuseChSpyeyeIps201406Parser(_IpsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.spyeye-ips.201406'
    constant_items = dict(_IpsMixIn.constant_items, name='spyeye')

class AbuseChSpyeyeIpsParser(_IpsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.spyeye-ips'
    constant_items = dict(_IpsMixIn.constant_items, name='spyeye')


# Zeus
class AbuseChZeusDoms201406Parser(_DomsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.zeus-doms.201406'
    constant_items = dict(_DomsMixIn201406.constant_items, name='zeus')

class AbuseChZeusDomsParser(_DomsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.zeus-doms'
    constant_items = dict(_DomsMixIn.constant_items, name='zeus')

class AbuseChZeusIps201406Parser(_IpsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.zeus-ips.201406'
    constant_items = dict(_IpsMixIn.constant_items, name='zeus')

class AbuseChZeusIpsParser(_IpsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.zeus-ips'
    constant_items = dict(_IpsMixIn.constant_items, name='zeus')

class AbuseChZeusTrackerParser(BaseParser):

    default_binding_key = 'abuse-ch.zeustracker'
    constant_items = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'malurl',
    }

    def parse(self, data):
        md5_pattern = re.compile(ur'[a-fA-F\d]{32}')

        raw_events = json.loads(data['raw'])
        for event in raw_events:
            with self.new_record_dict(data) as parsed:
                parsed["time"] = event[0].split()[1].strip("()") + "T00:00:00Z"
                parsed["url"] = event[1].split(",")[0].split()[1].strip()
                md5 = re.search(md5_pattern, event[1])
                if md5:
                    parsed["md5"] = md5.group(0)
                yield parsed


# Palevo
class AbuseChPalevoDoms201406Parser(_DomsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.palevo-doms.201406'
    constant_items = dict(_DomsMixIn201406.constant_items, name='palevo')

class AbuseChPalevoDomsParser(_DomsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.palevo-doms'
    constant_items = dict(_DomsMixIn.constant_items, name='palevo')

class AbuseChPalevoIps201406Parser(_IpsMixIn201406, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.palevo-ips.201406'
    constant_items = dict(_IpsMixIn.constant_items, name='palevo')

class AbuseChPalevoIpsParser(_IpsMixIn, BlackListTabDataParser):
    default_binding_key = 'abuse-ch.palevo-ips'
    constant_items = dict(_IpsMixIn.constant_items, name='palevo')


class AbuseChFeodoTrackerParser(BaseParser):

    default_binding_key = 'abuse-ch.feodotracker'
    constant_items = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'cnc',
    }

    version_to_name = {
        'A': 'feodo',
        'B': 'feodo',
        'C': 'feodo-emotet',
        'D': 'feodo-dridex',
        'E': 'feodo-heodo',
    }
    datetime_format = '%Y-%m-%d %H:%M:%S %Z'
    # regex patterns used to split raw description and create
    # key: value pairs
    string_to_pairs_pattern = r'[ ]*,[ ]*'
    pairs_to_key_item_pattern = r'[ ]*:[ ]*'

    def parse(self, data):
        raw_events = json.loads(data['raw'])
        for event in raw_events:
            parsed_fields = self._description_to_dict(event)
            with self.new_record_dict(data) as parsed:
                parsed['time'] = datetime.datetime.strptime(parsed_fields['firstseen'],
                                                            self.datetime_format)
                parsed['address'] = {'ip': parsed_fields['host']}
                try:
                    parsed['name'] = self.version_to_name[parsed_fields['version'].upper()]
                except KeyError:
                    LOGGER.warning("Unknown version value '%s' for the event. A record dict's "
                                   "'name' field cannot be filled.", parsed_fields['version'])
                yield parsed

    @classmethod
    def _description_to_dict(cls, desc):
        """
        Get a dict with field names as keys and their values
        as linked items out of not parsed, raw string from
        the RSS item.

        Args:
            `desc` (str):
                One of a not parsed fields from RSS item, describing
                a few elements.

        Returns:
            A dict mapping fields to their values, describing
            the event.
        """
        pairs = re.split(cls.string_to_pairs_pattern, desc)
        keys_values = [re.split(cls.pairs_to_key_item_pattern, x, maxsplit=1) for x in pairs]
        return {x[0].lower(): x[1] for x in keys_values}


class AbuseChFeodoTracker201908Parser(BaseParser):

    default_binding_key = "abuse-ch.feodotracker.201908"

    constant_items = {
            "restriction": "public",
            "confidence": "medium",
            "category": "cnc",
    }

    def parse(self, data):
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # Firstseen,DstIP,DstPort,LastOnline,Malware
            t, ip, dport, _, name = row
            with self.new_record_dict(data) as parsed:
                parsed.update({
                    'time': t,
                    'address': {'ip': ip},
                    'dport': dport,
                    'name': name,
                })
                yield parsed


class AbuseChFeodoTracker202110Parser(BaseParser):

    default_binding_key = "abuse-ch.feodotracker.202110"

    constant_items = {
            "restriction": "public",
            "confidence": "medium",
            "category": "cnc",
    }

    def parse(self, data):
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
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


class AbuseChRansomwareTrackerParser(BaseParser):

    default_binding_key = 'abuse-ch.ransomware'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
    }

    def parse(self, data):
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
        for row in rows:
            if not row:
                continue
            with self.new_record_dict(data) as parsed:
                if row[1] == 'C2':
                    parsed['category'] = 'cnc'
                elif row[1] in ['Distribution Site', 'Payment Site']:
                    parsed['category'] = 'malurl'
                else:
                    continue
                parsed['time'] = parse_iso_datetime_to_utc(row[0])
                parsed['name'] = row[2]
                parsed['fqdn'] = row[3]
                ips = row[7]
                if ips:
                    parsed['address'] = [{'ip': ip} for ip in set(ips.split('|'))]
                if row[4]:
                    parsed['url'] = row[4]
                yield parsed


class _AbuseChSSLBlacklistBaseParser(BaseParser):

    """
    Parser creating one event from one element of a JSON, or more
    events, based on every list of elements of associated binaries.

    Note that, contrary to their names, 'SSL Blacklist'
    and 'SSL Blacklist Dyre' sources are *event-based*.
    """

    LENGTH_OF_BINARIES_LIST = 4

    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }


    def parse(self, data):
        """
        Main parsing method.

        Args:
            `data`: collected data from an AMQP queue.

        Yields:
            A :class:n6lib.record_dict.RecordDict instance.

        Common items for both types of events are parsed once, at the
        beginning of parsing of an element and kept in the temporary
        `parsed_base` dict. Target RecordDict is then updated by
        its content.

        In case none of lists containing information about associated
        binaries is valid, parse only general information.
        """
        raw_events = json.loads(data['raw'])
        for url, items in raw_events.iteritems():
            # A flag used to command to publish an event, based on
            # general details, in case none of the elements from the
            # associated binaries table has been parsed successfully.
            any_binary_parsed = False
            parsed_base = {}
            subject = items.get('subject')
            if subject is not None:
                parsed_base['x509subject'] = subject
            issuer = items.get('issuer')
            if issuer is not None:
                parsed_base['x509issuer'] = issuer
            name = items.get('name')
            if name is not None:
                parsed_base['name'] = name
            binaries = items.get('binaries')
            if binaries:
                fingerprint = items.get('fingerprint')
                if fingerprint is not None:
                    parsed_base['x509fp_sha1'] = fingerprint
                for binary in binaries:
                    with self.new_record_dict(data) as parsed:
                        try:
                            self._create_event_from_binary(parsed, parsed_base, binary)
                        except MissingItemsException:
                            LOGGER.warning(
                                "The list of binary's items is incomplete. Skipping the event.")
                            continue
                        any_binary_parsed = True
                        yield parsed
            if not any_binary_parsed:
                with self.new_record_dict(data) as parsed:
                    try:
                        self._create_general_event(parsed, parsed_base, items)
                    except MissingItemsException:
                        LOGGER.warning(
                            'No timestamp or fingerprint for the event with URL: %s. '
                            'Skipping the event.', url)
                        continue
                    yield parsed

    @classmethod
    def _create_event_from_binary(cls, parsed, parsed_base, binary):
        """
        Fill a new record dict instance with data, accordingly for
        the event based on an associated binary.

        Args:
            `parsed`: a new record dict instance.
            `parsed_base`: pre-filled dict with basic data.
            `binary`: list of items describing a single binary.

        Raises:
            n6.parsers.abuse_ch.MissingItemsException:
                if a list of items is incomplete.
        """
        if len(binary) < cls.LENGTH_OF_BINARIES_LIST:
            raise MissingItemsException
        parsed.update(parsed_base)
        parsed['time'] = binary[0]
        parsed['md5'] = binary[1]
        parsed['address'] = {'ip': binary[2]}
        parsed['dport'] = binary[3]

    @staticmethod
    def _create_general_event(parsed, parsed_base, items):
        """
        Fill a new record dict with data, accordingly for
        the event based only on the general information.

        Args:
            `parsed`: a new record dict instance.
            `parsed_base`: pre-filled dict with basic data.
            `items`: dict with general information about event.

        Raises:
            n6.parsers.abuse_ch.MissingItemsException:
                if one of key elements is missing - timestamp
                or fingerprint.
        """
        try:
            parsed['time'] = items['timestamp']
        except (AdjusterError, KeyError):
            raise MissingItemsException
        try:
            parsed['x509fp_sha1'] = items['fingerprint']
        except (AdjusterError, KeyError):
            raise MissingItemsException
        parsed.update(parsed_base)


class AbuseChSSLBlacklistDyreParser(_AbuseChSSLBlacklistBaseParser):
    # Note that, contrary to its name, it is an *event-based* source.

    default_binding_key = "abuse-ch.ssl-blacklist-dyre"


class AbuseChSSLBlacklistParser(_AbuseChSSLBlacklistBaseParser):
    # Note that, contrary to its name, it is an *event-based* source.

    default_binding_key = "abuse-ch.ssl-blacklist"


class AbuseChSSLBlacklist201902Parser(BaseParser):
    # Note that, contrary to its name, it is an *event-based* source.

    default_binding_key = "abuse-ch.ssl-blacklist.201902"

    constant_items = {
            "restriction": "public",
            "confidence": "low",
            "category": "cnc",
    }

    def parse(self, data):
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
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


class AbuseChUrlhausUrlsParser(BaseParser):

    default_binding_key = 'abuse-ch.urlhaus-urls'

    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "malurl",
    }

    def parse(self, data):
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
        for row in rows:
            # SOURCE FIELDS FORMAT:
            # id,dateadded,url,url_status,threat,tags,urlhaus_link, reporter
            with self.new_record_dict(data) as parsed:
                parsed['time'] = row[1]
                parsed['url'] = row[2]
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
        rows = csv.reader(StringIO(data['raw']), delimiter=',', quotechar='"')
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


entry_point_factory(sys.modules[__name__])

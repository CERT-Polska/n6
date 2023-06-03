# Copyright (c) 2022-2023 NASK. All rights reserved.

"""
Parser: `cesnet-cz.warden`.
"""

import json

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)
from n6lib.log_helpers import get_logger
from n6lib.common_helpers import ipv4_to_int


LOGGER = get_logger(__name__)


class CesnetCzWardenParser(BaseParser):

    default_binding_key = 'cesnet-cz.warden'

    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'low',
    }

    allow_empty_results = True

    LOGIC_REQUIRED = 'LOGIC_REQUIRED'
    NO_MAPPING = 'NO_MAPPING'

    warden_to_n6_category = {
        'Abusive': NO_MAPPING,
        'Abusive.Spam': LOGIC_REQUIRED,
        'Abusive.Harassment': NO_MAPPING,
        'Abusive.Child': NO_MAPPING,
        'Abusive.Sexual': NO_MAPPING,
        'Abusive.Violence': NO_MAPPING,

        'Malware': 'malurl',
        'Malware.Virus': NO_MAPPING,
        'Malware.Worm': NO_MAPPING,
        'Malware.Trojan': NO_MAPPING,
        'Malware.Spyware': NO_MAPPING,
        'Malware.Dialer': NO_MAPPING,
        'Malware.Rootkit': NO_MAPPING,

        'Recon': NO_MAPPING,
        'Recon.Scanning': 'scanning',
        'Recon.Sniffing': NO_MAPPING,
        'Recon.SocialEngineering': NO_MAPPING,
        'Recon.Searching': NO_MAPPING,

        'Attempt': NO_MAPPING,
        'Attempt.Exploit': NO_MAPPING, 
        'Attempt.Login': 'server-exploit', 
        'Attempt.NewSignature': NO_MAPPING,

        'Intrusion': NO_MAPPING,
        'Intrusion.AdminCompromise': NO_MAPPING, 
        'Intrusion.UserCompromise': 'server-exploit',
        'Intrusion.AppCompromise': NO_MAPPING,
        'Intrusion.Botnet': NO_MAPPING,

        'Availability': NO_MAPPING,
        'Availability.DoS': NO_MAPPING, 
        'Availability.DDoS': NO_MAPPING, 
        'Availability.Sabotage': NO_MAPPING, 
        'Availability.Outage': NO_MAPPING,

        'Information': NO_MAPPING,
        'Information.UnauthorizedAccess': NO_MAPPING, 
        'Information.UnauthorizedModification': NO_MAPPING,

        'Fraud': NO_MAPPING,
        'Fraud.UnauthorizedUsage': NO_MAPPING, 
        'Fraud.Copyright': NO_MAPPING, 
        'Fraud.Masquerade': NO_MAPPING, 
        'Fraud.Phishing': NO_MAPPING, 
        'Fraud.Scam': NO_MAPPING,

        'Vulnerable': NO_MAPPING,
        'Vulnerable.Open': NO_MAPPING, 
        'Vulnerable.Config': NO_MAPPING,

        'Anomaly': NO_MAPPING,
        'Anomaly.Traffic': 'flow-anomaly', 
        'Anomaly.Connection': NO_MAPPING, 
        'Anomaly.Protocol': NO_MAPPING, 
        'Anomaly.System': NO_MAPPING, 
        'Anomaly.Application': NO_MAPPING, 
        'Anomaly.Behaviour': NO_MAPPING,

        'Other': NO_MAPPING, 
    }

    # These lists contain Warden Categories which can be excluded from being logged
    none_ip_exclude_logging = ['Availability.DoS', 'Attempt.Login', 'Recon.Scanning']
    none_category_exclude_logging = ['Availability.DoS']

    def parse(self, data):
        raw = json.loads(data['raw'])
        for warden_event in raw:
            for warden_category in warden_event['Category']:
                n6_category = self._parse_category(warden_category, warden_event)
                n6_ip = self._parse_ip(warden_event)
                if n6_ip is None and warden_category not in self.none_ip_exclude_logging:
                    LOGGER.info('IP does not exist: %s', warden_event)
                if n6_category is None and warden_category not in self.none_category_exclude_logging:
                    LOGGER.info('Category does not exist: %s', warden_event)
                if n6_category is not None and n6_ip is not None:
                    with self.new_record_dict(data) as parsed:
                        parsed['time'] = warden_event['DetectTime']
                        parsed['category'] = n6_category
                        parsed['address'] = {'ip': n6_ip}
                        n6_dip = self._parse_dip(warden_event)
                        if n6_dip is not None:
                            parsed['dip'] = n6_dip
                        n6_dport = self._parse_dport(warden_event)
                        if n6_dport is not None:
                            parsed['dport'] = n6_dport
                        n6_sport = self._parse_sport(warden_event)
                        if n6_sport is not None:
                            parsed['sport'] = n6_sport
                        n6_proto = self._parse_proto(warden_event)
                        if n6_proto is not None:
                            parsed['proto'] = n6_proto
                        n6_name = self._parse_name(warden_event)
                        if n6_name is not None:
                            parsed['name'] = n6_name
                        # Extraordinary cases
                        if warden_category == 'Malware':
                            if n6_sport is not None:
                                parsed['dport'] = n6_sport
                            if 'sport' in parsed:
                                del parsed['sport']
                            n6_url = self._parse_url(warden_event)
                            if n6_url is not None:
                                parsed['url'] = n6_url
                        yield parsed

    def _parse_category(self, warden_category, warden_event):
        n6_category = self.warden_to_n6_category.get(warden_category)
        if n6_category:
            if n6_category == self.NO_MAPPING:
                return None
            if n6_category == self.LOGIC_REQUIRED:
                if warden_category == 'Abusive.Spam':
                    src = warden_event.get('Source')
                    if src and (src[0].get('IP4') or src[0].get('IP')):
                        return 'spam'
                return None
            return n6_category
        return None

    def _parse_ip(self, warden_event):
        if warden_event.get('Source'):
            for ip_key in ('IP4', 'IP'):
                ip_addrs = warden_event.get('Source')[0].get(ip_key)
                if ip_addrs:
                    warden_ip = ip_addrs[0]
                    try:
                        ipv4_to_int(warden_ip)
                        return warden_ip
                    except ValueError:
                        pass
        return None

    def _parse_dip(self, warden_event):
        if warden_event.get('Target'):
            for ip_key in ('IP4', 'IP'):
                ip_addrs_target = warden_event.get('Target')[0].get(ip_key)
                if ip_addrs_target and (len(ip_addrs_target) == 1):
                    warden_ip = ip_addrs_target[0]
                    try:
                        ipv4_to_int(warden_ip)
                        return warden_ip
                    except ValueError:
                        pass
        return None

    def _parse_dport(self, warden_event):
        if warden_event.get('Target'):
            ports_target = warden_event.get('Target')[0].get('Port')
            if ports_target and (len(ports_target) == 1):
                return ports_target[0]
        return None

    def _parse_sport(self, warden_event):
        if warden_event.get('Source'):
            ports_source = warden_event.get('Source')[0].get('Port')
            if ports_source and (len(ports_source) == 1):
                return ports_source[0]
        return None

    def _parse_proto(self, warden_event):
        for key in ('Source', 'Target'):
            if warden_event.get(key):
                protos = warden_event.get(key)[0].get('Proto')
                if protos and (protos[0] in ('tcp', 'udp', 'icmp')):
                    return protos[0]
        return None

    def _parse_name(self, warden_event):
        description = warden_event.get('Description')
        note = warden_event.get('Note')
        if description:
            return description
        if note:
            return note
        return None

    def _parse_url(self, warden_event):
        for key in ('Source', 'Target'):
            if warden_event.get(key):
                urls = warden_event.get(key)[0].get('URL')
                if urls and (len(urls) == 1):
                    return urls[0]
        return None


add_parser_entry_point_functions(__name__)

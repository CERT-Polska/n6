# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections
import os
import urllib.parse

import dns.resolver
# TODO: After migration to Pyton 3.x: remove the `iptools` dependency,
#       adjusting our code to use std lib's `ipaddress` (maybe also
#       adding IPv4/v6/both-dedicated config converters?), and/or our
#       own existing IP-address-related helpers...
import iptools                                                                              #3 --remove-replace iptools
import maxminddb.const
from dns.exception import DNSException
from geoip2 import database, errors

from n6.base.queue import QueuedBase
from n6lib.common_helpers import replace_segment, is_ipv4
from n6lib.config import ConfigMixin
from n6lib.log_helpers import get_logger, logging_configured
from n6lib.record_dict import RecordDict


LOGGER = get_logger(__name__)


class Enricher(ConfigMixin, QueuedBase):

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'enrichement',
        'accepted_event_types': [
            'event',
            'bl',
            'bl-update',
            'suppressed',
        ],
    }
    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    config_spec = """
        [enrich]
        dnshost
        dnsport :: int
        geoippath = ""
        asndatabasefilename = ""
        citydatabasefilename = ""
        excluded_ips = "" :: list_of_str
    """

    single_instance = False

    #
    # Initialization

    def __init__(self, **kwargs):
        self.is_geodb_enabled = False
        self.gi_asn = None
        self.gi_cc = None
        self._resolver = None
        self._enrich_config = self.get_config_section()
        self.excluded_ips = self._get_excluded_ips()
        self._setup_geodb()
        self._setup_dnsresolver(self._enrich_config["dnshost"], self._enrich_config["dnsport"])
        super(Enricher, self).__init__(**kwargs)

    def _get_excluded_ips(self):
        if self._enrich_config['excluded_ips']:
            return iptools.IpRangeList(*self._enrich_config['excluded_ips'])                        #3 --replace iptools
        return None

    def _setup_dnsresolver(self, dnshost, dnsport):
        self._resolver = dns.resolver.Resolver(configure=False)
        self._resolver.nameservers = [dnshost]
        self._resolver.port = dnsport

    def _setup_geodb(self):
        geoipdb_path = self._enrich_config["geoippath"]
        if geoipdb_path:
            geoipdb_asn_file = self._enrich_config["asndatabasefilename"]
            geoipdb_city_file = self._enrich_config["citydatabasefilename"]
            if geoipdb_asn_file:
                self.gi_asn = database.Reader(fileish=os.path.join(geoipdb_path, geoipdb_asn_file),
                                              mode=maxminddb.const.MODE_MEMORY)
                self.is_geodb_enabled = True
            if geoipdb_city_file:
                self.gi_cc = database.Reader(fileish=os.path.join(geoipdb_path, geoipdb_city_file),
                                             mode=maxminddb.const.MODE_MEMORY)
                self.is_geodb_enabled = True

    #
    # Main activity

    def input_callback(self, routing_key, body, properties):
        data = RecordDict.from_json(body)
        with self.setting_error_event_info(data):
            enriched = self.enrich(data)
            rk = replace_segment(routing_key, 1, 'enriched')
            body = enriched.get_ready_json()
            self.publish_output(routing_key=rk, body=body)

    def enrich(self, data):
        enriched_keys = []
        ip_to_enriched_address_keys = collections.defaultdict(list)
        ip_from_url, fqdn_from_url = self._extract_ip_or_fqdn(data)
        self._maybe_set_fqdn(fqdn_from_url, data, enriched_keys)
        self._maybe_set_address_ips(ip_from_url, data, ip_to_enriched_address_keys)
        if data.get('address'):
            self._filter_out_excluded_ips(data, ip_to_enriched_address_keys)
            self._maybe_set_other_address_data(data, ip_to_enriched_address_keys)
        # NOTE: the `enriched` item of the record dict is set here to
        # the pair (2-tuple) whose elements are:
        #   0) a list of keys added by Enricher to the record dict
        #      (for now, the only such key is "fqdn"),
        #   1) a dict whose keys are IP addresses (strings) and values
        #      are lists of address item keys added by Enricher for a
        #      particular IP ("asn", "cc", "ip")
        # -- for example:
        #   (["fqdn"], {"127.0.0.1": ["ip"], "1.2.3.4": ["asn", "cc", "ip"]})
        data['enriched'] = (enriched_keys, ip_to_enriched_address_keys)
        self._ensure_address_is_clean(data)
        self._final_sanity_assertions(data)  # <- can be commented out for efficiency
        return data

    def _extract_ip_or_fqdn(self, data):
        ip_from_url = fqdn_from_url = None
        url = data.get('url')
        if url is not None:
            _fqdn_or_ip = self.url_to_fqdn_or_ip(url)
            # ^ note: the returned _fqdn_or_ip *can* be an empty string
            ## but it should not be None; added the following condition for debug
            if _fqdn_or_ip is None:
                LOGGER.error(
                    '_fqdn_or_ip is None, source: %r, url: %r',
                    data['source'],
                    url)
            if is_ipv4(_fqdn_or_ip):
                ip_from_url = _fqdn_or_ip
            elif _fqdn_or_ip:
                fqdn_from_url = _fqdn_or_ip
        return ip_from_url, fqdn_from_url

    def _maybe_set_fqdn(self, fqdn_from_url, data, enriched_keys):
        if data.get('fqdn') is None and fqdn_from_url:
            data['fqdn'] = fqdn_from_url
            enriched_keys.append('fqdn')

    def _maybe_set_address_ips(self, ip_from_url, data, ip_to_enriched_address_keys):
        if not data.get('address'):
            if data.get('fqdn') is None:
                if ip_from_url:
                    data['address'] = [{'ip': ip_from_url}]
                    ip_to_enriched_address_keys[ip_from_url].append('ip')
            elif not data.get('_do_not_resolve_fqdn_to_ip'):
                _address = []
                for ip in self.fqdn_to_ip(data.get('fqdn')):
                    _address.append({'ip': ip})
                    ip_to_enriched_address_keys[ip].append('ip')
                if _address:
                    data['address'] = _address

    def _filter_out_excluded_ips(self, data, ip_to_enriched_address_keys):
        assert 'address' in data
        if self.excluded_ips:
            _address = []
            for addr in data['address']:
                ip = addr['ip']
                if ip in self.excluded_ips:
                    ip_to_enriched_address_keys.pop(ip, None)
                else:
                    _address.append(addr)
            data['address'] = _address

    def _maybe_set_other_address_data(self, data, ip_to_enriched_address_keys):
        if self.is_geodb_enabled:
            assert 'address' in data
            for addr in data['address']:
                # ASN
                self._maybe_set_asn(addr, data, ip_to_enriched_address_keys)
                # CC
                self._maybe_set_cc(addr, data, ip_to_enriched_address_keys)

    def _maybe_set_asn(self, addr, data, ip_to_enriched_address_keys):
        if self.gi_asn is not None:
            ip = addr['ip']
            existing_asn = addr.pop('asn', None)
            if existing_asn is not None:
                LOGGER.warning(
                        'it should not happen: event\'s `address` '
                        'contained an `asn` (%r) *before* enrichment '
                        '-- so the `asn` has been dropped! '
                        '[ip: %s; source: %r; event id: %r; rid: %r]',
                        existing_asn,
                        ip,
                        data['source'],
                        data['id'],
                        data['rid'])
            asn = self.ip_to_asn(ip)
            if asn:
                addr['asn'] = asn
                ip_to_enriched_address_keys[ip].append('asn')

    def _maybe_set_cc(self, addr, data, ip_to_enriched_address_keys):
        if self.gi_cc is not None:
            ip = addr['ip']
            existing_cc = addr.pop('cc', None)
            if existing_cc is not None:
                LOGGER.warning(
                        'it should not happen: event\'s `address` '
                        'contained a `cc` (%r) *before* enrichment '
                        '-- so the `cc` has been dropped! '
                        '[ip: %s; source: %r; event id: %r; rid: %r]',
                        existing_cc,
                        ip,
                        data['source'],
                        data['id'],
                        data['rid'])
            cc = self.ip_to_cc(ip)
            if cc:
                addr['cc'] = cc
                ip_to_enriched_address_keys[ip].append('cc')

    def _ensure_address_is_clean(self, data):
        if data.get('address'):
            # ensure that all content is normalized
            # by RecordDict's `address` adjuster
            data['address'] = data['address']
        else:
            # ensure that no empty address is left
            data.pop('address', None)

    def _final_sanity_assertions(self, data):
        if __debug__:
            enriched_keys, ip_to_enriched_address_keys = data['enriched']
            ip_to_addr = {
                addr['ip']: addr
                for addr in data.get('address', ())}
            assert all(
                name in data
                for name in enriched_keys)
            assert all(
                set(addr_keys).issubset(ip_to_addr[ip])
                for ip, addr_keys in ip_to_enriched_address_keys.items())

    #
    # Resolution helpers

    def url_to_fqdn_or_ip(self, url):
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.netloc.endswith(':'):
            # URL is probably wrong -- something like: "http://http://..."
            return ''
        return parsed_url.hostname

    def fqdn_to_ip(self, fqdn):
        try:
            dns_result = self._resolver.query(fqdn, 'A')
        except DNSException:
            return []
        ip_set = set()
        for i in dns_result:
            ip_set.add(str(i))
        return sorted(ip_set)

    def ip_to_asn(self, ip):
        assert self.gi_asn is not None
        try:
            geoip_asn = self.gi_asn.asn(ip)
        except errors.GeoIP2Error:
            LOGGER.info("%r cannot be resolved by GeoIP (to ASN)", ip)
            return None
        return geoip_asn.autonomous_system_number

    def ip_to_cc(self, ip):
        assert self.gi_cc is not None
        try:
            geoip_city = self.gi_cc.city(ip)
        except errors.GeoIP2Error:
            LOGGER.info("%r cannot be resolved by GeoIP (to CC)", ip)
            return None
        return geoip_city.country.iso_code


def main():
    with logging_configured():
        enricher = Enricher()
        try:
            enricher.run()
        except KeyboardInterrupt:
            enricher.stop()


if __name__ == "__main__":
    main()

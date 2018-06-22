# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import hashlib
import unittest

import iptools
import mock
import pygeoip
from dns.exception import DNSException

from n6.utils.enrich import Enricher
from n6lib.record_dict import RecordDict
from n6lib.unit_test_helpers import TestCaseMixin


class MockConfig(object):

    config = {
        'enrich': {
            'dnshost': '8.8.8.8',
            'dnsport': '53',
            'geoippath': '/usr/share/GeoIP',
        },
        'rabbitmq': {
            'host': 'localhost',
            'port': 5671,
            'ssl': 0,
            'heartbeat_interval': 10,
        },
    }

    def __init__(self, *args, **kwargs):
        pass

    def __getitem__(self, key):
        return self.config[key]


class TestEnricher(TestCaseMixin, unittest.TestCase):

    COMMON_DATA = {
        "category": "other",
        "confidence": "low",
        "restriction": "public",
        "source": "test.test",
        "time": str(datetime.datetime.now()),
        "id": hashlib.md5("test").hexdigest(),
        "rid": hashlib.md5("test").hexdigest(),
    }

    @mock.patch('n6.base.queue.QueuedBase.get_connection_params_dict')
    @mock.patch('n6.utils.enrich.Config', MockConfig)
    def setUp(self, *args):
        Enricher._setup_dnsresolver = mock.MagicMock()
        Enricher._setup_geodb = mock.MagicMock()
        self.enricher = Enricher()
        self.enricher._resolver = mock.MagicMock()
        self.enricher.gi_asn = mock.MagicMock()
        self.enricher.gi_cc = mock.MagicMock()
        self.enricher._resolver.query = mock.MagicMock(return_value=["127.0.0.1"])
        self.enricher.gi_asn.org_by_addr = mock.MagicMock(return_value="AS1234")
        self.enricher.gi_cc.country_code_by_addr = mock.MagicMock(return_value="PL")

    def test__enrich__with_no_data(self):
        data = self.enricher.enrich(RecordDict({}))
        self.assertEqualIncludingTypes(data, RecordDict({'enriched': ([], {})}))

    def test__enrich__with_irrelevant_data(self):
        data = self.enricher.enrich(RecordDict(self.COMMON_DATA))
        self.assertEqualIncludingTypes(data, RecordDict(dict(self.COMMON_DATA, **{
            'enriched': ([], {})})))

    def test__enrich__with_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_fqdn_given__with_nodns_flag(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "_do_not_resolve_fqdn_to_ip": True}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        self.enricher._resolver.query.return_value = [
            '2.2.2.2',
            '127.0.0.1',
            '13.1.2.3',
            '1.1.1.1',
            '127.0.0.1',  # duplicate
            '13.1.2.3',   # duplicate
            '12.11.10.9',
            '13.1.2.3',   # duplicate
            '1.0.1.1',
        ]
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"1.0.1.1": ["asn", "cc", "ip"],
                              "1.1.1.1": ["asn", "cc", "ip"],
                              "12.11.10.9": ["asn", "cc", "ip"],
                              "127.0.0.1": ["asn", "cc", "ip"],
                              "13.1.2.3": ["asn", "cc", "ip"],
                              "2.2.2.2": ["asn", "cc", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '1.0.1.1',  # note: *removed IP duplicates* and
                         "asn": '1234',    #       *ordered* by IP (textually)
                         "cc": 'PL'},
                        {"ip": '1.1.1.1',
                         "asn": '1234',
                         "cc": 'PL'},
                        {"ip": '12.11.10.9',
                         "asn": '1234',
                         "cc": 'PL'},
                        {"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'},
                        {"ip": '13.1.2.3',
                         "asn": '1234',
                         "cc": 'PL'},
                        {"ip": '2.2.2.2',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_url_given(self):
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.asert_called_once_with("www.nask.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_url_given__with_nodns_flag(self):
        data = self.enricher.enrich(RecordDict({
            "url": "http://www.nask.pl/asd",
            "_do_not_resolve_fqdn_to_ip": True}))
        self.enricher._resolver.asert_called_once_with("www.nask.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_wrong_url_given(self):
        data = self.enricher.enrich(RecordDict({"url": "http://http://www.nask.pl/asd"}))
        self.assertEqual(self.enricher._resolver.mock_calls, [])
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "url": "http://http://www.nask.pl/asd"}))

    def test__enrich__with_fqdn_not_resolved(self):
        self.enricher._resolver.query = mock.MagicMock(side_effect=DNSException)
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl"}))

    def test__enrich__with_fqdn_from_url_not_resolved(self):
        self.enricher._resolver.query = mock.MagicMock(side_effect=DNSException)
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl"}))

    def test__enrich__with_ip_url_given(self):
        data = self.enricher.enrich(RecordDict({"url": "http://192.168.0.1/asd"}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"192.168.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        data = self.enricher.enrich(RecordDict({
            "url": "http://192.168.0.1/asd",
            "_do_not_resolve_fqdn_to_ip": True}))
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"192.168.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl",
                                                "url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_fqdn_and_url_given__with_nodns_flag(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "_do_not_resolve_fqdn_to_ip": True}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd"}))
        self.enricher._resolver.asert_called_once_with("cert.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "address": [{"ip": "10.20.30.40"}]}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "address": [{"ip": "10.20.30.40"}],
            "_do_not_resolve_fqdn_to_ip": True}))
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": "10.20.30.40"}]}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"10.20.30.40": ["asn", "cc"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": "10.20.30.40"}]}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": "10.20.30.40"}]}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": "10.20.30.40"}]}))
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__fqdn_to_ip__called(self):
        """Test if fqdn_to_ip is called if data does not contain address"""
        data = RecordDict({"fqdn": "cert.pl"})
        data.update(self.COMMON_DATA)
        self.enricher.fqdn_to_ip = mock.MagicMock()
        self.enricher.enrich(data)
        self.enricher.fqdn_to_ip.assert_called_with("cert.pl")

    def test__url_to_fqdn_or_ip__called(self):
        """Test if url_to_fqdn_or_ip is called if data does not contain address and fqdn"""
        data = RecordDict({"url": "http://www.cert.pl"})
        data.update(self.COMMON_DATA)
        self.enricher.url_to_fqdn_or_ip = mock.MagicMock(return_value="www.cert.pl")
        self.enricher.enrich(data)
        self.enricher.url_to_fqdn_or_ip.assert_called_with("http://www.cert.pl")

    def test__url_to_fqdn_or_ip__called_for_ip_url(self):
        """Test if url_to_fqdn_or_ip is called if data does not contain address and fqdn"""
        data = RecordDict({"url": "http://192.168.0.1"})
        data.update(self.COMMON_DATA)
        self.enricher.url_to_fqdn_or_ip = mock.MagicMock(return_value="192.168.0.1")
        self.enricher.enrich(data)
        self.enricher.url_to_fqdn_or_ip.assert_called_with("http://192.168.0.1")

    def test_adding_asn_cc_if_possible(self):
        """Test if asn/cc are (maybe) added"""
        self.enricher.gi_asn.org_by_addr.side_effect = [
            pygeoip.GeoIPError,
            "AS1234",
            "AS123456"]
        self.enricher.gi_cc.country_code_by_addr.side_effect = [
            "PL",
            "UK",
            pygeoip.GeoIPError]
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        self.enricher.enrich(data)
        self.assertEqual(data["address"], [
            {"ip": "127.0.0.1", "cc": "PL"},
            {"ip": "192.187.0.1", "asn": 1234, "cc": "UK"},
            {"ip": "10.15.1.255", "asn": 123456},
        ])
        self.assertEqual(data["enriched"], ([], {
            "127.0.0.1": ["cc"],
            "192.187.0.1": ["asn", "cc"],
            "10.15.1.255": ["asn"],
        }))

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_asn_cc_always_dropped_and_new_ones_added_if_possible(self, LOGGER_mock):
        """Test if already existing asn/cc are removed and new ones are (maybe) added"""
        self.enricher.gi_asn.org_by_addr.side_effect = [
            pygeoip.GeoIPError,
            pygeoip.GeoIPError,
            "AS12345"]
        self.enricher.gi_cc.country_code_by_addr.side_effect = [
            pygeoip.GeoIPError,
            "PL",
            "UK"]
        data = RecordDict({
            "address": [{"ip": "127.0.0.1", "cc": "JP"},
                        {"ip": "192.187.0.1", "cc": "US", "asn": 424242},
                        {"ip": "10.15.1.255", "asn": 434343}]})
        data.update(self.COMMON_DATA)
        expected_num_of_warnings = 4  # 2 existing `cc` + 2 existing `asn`
        self.enricher.enrich(data)
        self.assertEqual(data["address"], [
            {"ip": "127.0.0.1"},
            {"ip": "192.187.0.1", "cc": "PL"},
            {"ip": "10.15.1.255", "asn": 12345, "cc": "UK"},
        ])
        self.assertEqual(data["enriched"], ([], {
            "192.187.0.1": ["cc"],
            "10.15.1.255": ["asn", "cc"],
        }))
        self.assertEqual(
            len(LOGGER_mock.warning.mock_calls),
            expected_num_of_warnings)

    def test__ip_to_asn__called(self):
        """Test if ip_to_asn was called for all ips"""
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        self.enricher.ip_to_asn = mock.MagicMock(return_value="")
        self.enricher.enrich(data)
        for addr in data["address"]:
            self.enricher.ip_to_asn.assert_any_call(addr["ip"])
        self.assertEqual(len(data["address"]), self.enricher.ip_to_asn.call_count)

    def test__ip_to_cc__called(self):
        """Test if ip_to_cc was called for all ips"""
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        self.enricher.ip_to_cc = mock.MagicMock(return_value="")
        self.enricher.enrich(data)
        for addr in data["address"]:
            self.enricher.ip_to_cc.assert_any_call(addr["ip"])
        self.assertEqual(len(data["address"]), self.enricher.ip_to_cc.call_count)

    def test__fqdn_to_ip__not_called(self):
        """Test if fqdn_to_ip not called if address already present"""
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        self.enricher.fqdn_to_ip = mock.MagicMock(return_value="127.0.0.1")
        self.enricher.enrich(data)
        self.assertFalse(self.enricher.fqdn_to_ip.called)

    def test_routing_key_modified(self):
        """Test if routing key after enrichement is set to "enriched.*"
        when publishing to output queue"""
        self.enricher.publish_output = mock.MagicMock()
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        body = data.get_ready_json()
        initial_routing_key = "event.parsed.test.test-source"
        properties = None
        self.enricher.input_callback(initial_routing_key, body, properties)
        args, kwargs = self.enricher.publish_output.call_args
        self.assertIn("routing_key", kwargs)
        self.assertEqual(kwargs["routing_key"], "event.enriched.test.test-source")

    def test__get_excluded_ips__with_excluded_ips_in_config(self):
        # config file with excluded_ips
        self.enricher._enrich_config = {'dnshost': '8.8.8.8',
                                        'dnsport': '53',
                                        'geoippath': '/usr/share/GeoIP',
                                        'excluded_ips': '1.1.1.1, 2.2.2.2,3.3.3.3'}
        expected = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')
        result = self.enricher._get_excluded_ips()
        self.assertItemsEqual(expected, result)

    def test__get_excluded_ips__without_excluded_ips_in_config(self):
        # config file without excluded_ips
        self.enricher._enrich_config = {'dnshost': '8.8.8.8',
                                        'dnsport': '53',
                                        'geoippath': '/usr/share/GeoIP'}
        expected = None
        result = self.enricher._get_excluded_ips()
        self.assertEqual(expected, result)

    def test__enrich__with_excluded_ips_config__with_some_ip_to_exclude__1(self):
        self.enricher._enrich_config = {'dnshost': '8.8.8.8',
                                        'dnsport': '53',
                                        'geoippath': '/usr/share/GeoIP',
                                        'excluded_ips': '127.0.0.1, 2.2.2.2, 3.3.3.3'}
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd",
                                                "address": [{'ip': "127.0.0.1"}]}))
        self.enricher._resolver.asert_called_once_with("www.nask.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl"}))  # (note: emptied `address` removed)

    def test__enrich__with_excluded_ips_config__with_some_ip_to_exclude__2(self):
        self.enricher._enrich_config = {'dnshost': '8.8.8.8',
                                        'dnsport': '53',
                                        'geoippath': '/usr/share/GeoIP',
                                        'excluded_ips': '127.0.0.1, 2.2.2.2, 3.3.3.3'}
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.asert_called_once_with("www.nask.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl"}))  # (note: emptied `address` removed)

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        self.enricher._enrich_config = {'dnshost': '8.8.8.8',
                                        'dnsport': '53',
                                        'geoippath': '/usr/share/GeoIP',
                                        'excluded_ips': '2.2.2.2, 3.3.3.3'}
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.asert_called_once_with("www.nask.pl")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__filter_out_excluded_ips__with_excluded_ips_being_None(self):
        self.enricher.excluded_ips = None
        data = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': "127.0.0.1"}],
        })
        expected = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': "127.0.0.1"}],
        })
        ip_to_enr_mock = mock.MagicMock()
        ip_to_enr_expected_calls = []
        self.enricher._filter_out_excluded_ips(data, ip_to_enr_mock)
        self.assertEqualIncludingTypes(expected, data)
        self.assertEqual(ip_to_enr_mock.mock_calls, ip_to_enr_expected_calls)

    def test__filter_out_excluded_ips__with_no_ip_in_excluded_ips(self):
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')
        data = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': '1.1.1.5'}, {'ip': '2.1.1.1'}],
        })
        expected = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': '1.1.1.5'}, {'ip': '2.1.1.1'}],
        })
        ip_to_enr_mock = mock.MagicMock()
        ip_to_enr_expected_calls = []
        self.enricher._filter_out_excluded_ips(data, ip_to_enr_mock)
        self.assertEqualIncludingTypes(expected, data)
        self.assertEqual(ip_to_enr_mock.mock_calls, ip_to_enr_expected_calls)

    def test__filter_out_excluded_ips__with_ip_in_excluded_ips__1(self):
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')
        data = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': '1.1.1.1'}, {'ip': '1.1.1.6'}],
        })
        expected = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': '1.1.1.6'}],
        })
        ip_to_enr_mock = mock.MagicMock()
        ip_to_enr_expected_calls = [
            mock.call.pop('1.1.1.1', None),
        ]
        self.enricher._filter_out_excluded_ips(data, ip_to_enr_mock)
        self.assertEqualIncludingTypes(expected, data)
        self.assertEqual(ip_to_enr_mock.mock_calls, ip_to_enr_expected_calls)

    def test__filter_out_excluded_ips__with_ip_in_excluded_ips__2(self):
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')
        data = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{'ip': '1.1.1.1', 'asn': 1234}],
        })
        expected = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [],
        })
        ip_to_enr_mock = mock.MagicMock()
        ip_to_enr_expected_calls = [
            mock.call.pop('1.1.1.1', None),
        ]
        self.enricher._filter_out_excluded_ips(data, ip_to_enr_mock)
        self.assertEqualIncludingTypes(expected, data)
        self.assertEqual(ip_to_enr_mock.mock_calls, ip_to_enr_expected_calls)

    def test__filter_out_excluded_ips__with_range_of_ips(self):
        self.enricher.excluded_ips = iptools.IpRangeList('3.0.0.0/8')
        data = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [
                {
                    'ip': '3.3.3.3',
                    'asn': 1234
                },
                {
                    'ip': '3.255.255.255',
                    'asn': 5632
                },
                {
                    'ip': '3.0.0.0',
                    'asn': 5631
                },
                {
                    'ip': '2.255.255.255',
                    'asn': 5632
                },
            ],
        })
        expected = RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [
                {
                    'ip': '2.255.255.255',
                    'asn': 5632,
                },
            ],
        })
        ip_to_enr_mock = mock.MagicMock()
        ip_to_enr_expected_call_items = [
            mock.call.pop('3.3.3.3', None),
            mock.call.pop('3.255.255.255', None),
            mock.call.pop('3.0.0.0', None),
        ]
        self.enricher._filter_out_excluded_ips(data, ip_to_enr_mock)
        self.assertEqualIncludingTypes(expected, data)
        self.assertItemsEqual(ip_to_enr_mock.mock_calls, ip_to_enr_expected_call_items)

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

import datetime
import hashlib
import os
import unittest

import iptools                                                                              #3 --remove-replace iptools
import mock
from geoip2.errors import GeoIP2Error
from dns.exception import DNSException

from n6.utils.enrich import Enricher
from n6lib.record_dict import RecordDict
from n6lib.unit_test_helpers import TestCaseMixin


DEFAULT_GEO_IP_DB_PATH = '/usr/share/GeoIP'
DEFAULT_ASN_DB_FILENAME = 'GeoLite2-ASN.mmdb'
DEFAULT_CC_DB_FILENAME = 'GeoLite2-City.mmdb'


class MockASNReader(mock.Mock):

    asn = mock.Mock(return_value=mock.MagicMock(autonomous_system_number="1234"))


class MockCCReader(mock.Mock):

    city = mock.Mock(return_value=mock.MagicMock(country=mock.MagicMock(iso_code="PL")))


class MockReader(object):

    def __new__(cls, fileish, *args, **kwargs):
        filename = os.path.basename(fileish)
        if filename == DEFAULT_ASN_DB_FILENAME:
            return MockASNReader()
        elif filename == DEFAULT_CC_DB_FILENAME:
            return MockCCReader()
        raise ValueError('Unrecognized name of GeoIP database file: {!r}. '
                         'Should be one of: {!r}, {!r}'.format(filename,
                                                               DEFAULT_ASN_DB_FILENAME,
                                                               DEFAULT_CC_DB_FILENAME))


class _BaseTestEnricher(TestCaseMixin):

    """
    The class defines methods returning input test data.
    Concrete classes should extend these methods, by taking
    returned data and building assertions against expected
    data.

    These tests should be common for cases testing the Enricher
    with all the GeoIP databases, as well as only ASN, only CC
    or none of them enabled.
    """

    COMMON_DATA = {
        "category": "other",
        "confidence": "low",
        "restriction": "public",
        "source": "test.test",
        "time": str(datetime.datetime.now()),
        "id": hashlib.md5("test").hexdigest(),
        "rid": hashlib.md5("test").hexdigest(),
    }
    MOCK_CONFIG = NotImplemented

    @mock.patch('n6.base.queue.QueuedBase.get_connection_params_dict')
    @mock.patch('n6.utils.enrich.database.Reader', MockReader)
    @mock.patch('n6.utils.enrich.ConfigMixin.get_config_section')
    def setUp(self, config_mock, *args):
        config_mock.return_value = self.MOCK_CONFIG
        Enricher._setup_dnsresolver = mock.MagicMock()
        self.enricher = Enricher()
        self.enricher._resolver = mock.MagicMock()
        self.enricher._resolver.query = mock.MagicMock(return_value=["127.0.0.1"])

    def test__ip_to_asn__called_or_not(self):
        """
        Prepare for a test, whether the `ip_to_asn()` method was
        called for all IP addresses, or not.
        """
        self.enricher.ip_to_asn = mock.MagicMock(return_value="")
        data = self._make_actions_to_call_geoip_method_get_data()
        return data

    def test__ip_to_cc__called_or_not(self):
        """
        Prepare for a test, whether the `ip_to_cc()` method was
        called for all IP addresses, or not.
        """
        self.enricher.ip_to_cc = mock.MagicMock(return_value="")
        data = self._make_actions_to_call_geoip_method_get_data()
        return data

    def test__enrich__with_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        return data

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        self.enricher._resolver.query.return_value = [
            '2.2.2.2',
            '127.0.0.1',
            '13.1.2.3',
            '1.1.1.1',
            '127.0.0.1',  # duplicate
            '13.1.2.3',  # duplicate
            '12.11.10.9',
            '13.1.2.3',  # duplicate
            '1.0.1.1',
        ]
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        return data

    def test__enrich__with_url_given(self):
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.query.assert_called_once_with("www.nask.pl", "A")
        return data

    def test__enrich__with_ip_url_given(self):
        return self.enricher.enrich(RecordDict({"url": "http://192.168.0.1/asd"}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        return self.enricher.enrich(RecordDict({
            "url": "http://192.168.0.1/asd",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl",
                                                "url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        return data

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        return data

    def test__enrich__with_address_and_fqdn_given(self):
        return self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "address": [{"ip": "10.20.30.40"}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        return self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "address": [{"ip": "10.20.30.40"}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        return self.enricher.enrich(RecordDict({
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": "10.20.30.40"}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        return self.enricher.enrich(RecordDict({
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": "10.20.30.40"}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        return self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": "10.20.30.40"}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        return self.enricher.enrich(RecordDict({
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": "10.20.30.40"}]}))

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        self._prepare_config_for_excluded_ips(['2.2.2.2', '3.3.3.3'])
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.query.assert_called_once_with("www.nask.pl", "A")
        return data

    # helper methods
    def _prepare_config_for_excluded_ips(self, list_of_ips):
        self.enricher._enrich_config = {'excluded_ips': list_of_ips}

    @staticmethod
    def _get_actual_data_for_adding_asn_cc_if_possible():
        return RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})

    @staticmethod
    def _get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible():
        return RecordDict({
            "address": [{"ip": "127.0.0.1", "cc": "JP"},
                        {"ip": "192.187.0.1", "cc": "US", "asn": 424242},
                        {"ip": "10.15.1.255", "asn": 434343}]})

    def _enricher_execution_helper(self, data_init, expected_num_of_warnings=None):
        data = data_init
        data.update(self.COMMON_DATA)
        self.enricher.enrich(data)
        self.expected_num_of_warnings = expected_num_of_warnings
        return data

    def _set_asn_db_return_value_if_enabled(self, returned_asn):
        if self.enricher.gi_asn is not None:
            self.assertTrue(self.enricher.is_geodb_enabled)
            self.enricher.gi_asn = mock.Mock()
            self.enricher.gi_asn.asn = mock.Mock(
                return_value=mock.MagicMock(autonomous_system_number=returned_asn))

    def _set_asn_db_side_effect_if_enabled(self, side_effect):
        if self.enricher.gi_asn is not None:
            self.assertTrue(self.enricher.is_geodb_enabled)
            self.enricher.gi_asn = mock.Mock()
            self.enricher.gi_asn.asn = mock.MagicMock(side_effect=side_effect)

    def _set_cc_db_return_value_if_enabled(self, returned_cc):
        if self.enricher.gi_cc is not None:
            self.assertTrue(self.enricher.is_geodb_enabled)
            self.enricher.gi_cc = mock.Mock()
            self.enricher.gi_cc.city = mock.Mock(
                return_value=mock.Mock(country=mock.Mock(iso_code=returned_cc)))

    def _set_cc_db_side_effect_if_enabled(self, side_effect):
        if self.enricher.gi_cc is not None:
            self.assertTrue(self.enricher.is_geodb_enabled)
            self.enricher.gi_cc = mock.Mock()
            self.enricher.gi_cc.city = mock.MagicMock(side_effect=side_effect)

    def _make_actions_to_call_geoip_method_get_data(self):
        data = RecordDict({
            "address": [{"ip": "127.0.0.1"},
                        {"ip": "192.187.0.1"},
                        {"ip": "10.15.1.255"}]})
        data.update(self.COMMON_DATA)
        self.enricher.enrich(data)
        return data

    def _assert_geoip_method_called(self, meth, data):
        for addr in data["address"]:
            meth.assert_any_call(addr["ip"])
        self.assertEqual(len(data["address"]), meth.call_count)

    def _assert_geoip_method_not_called(self, meth):
        self.assertFalse(meth.called)


class TestEnricherWithFullConfig(_BaseTestEnricher, unittest.TestCase):

    MOCK_CONFIG = {
        'dnshost': '8.8.8.8',
        'dnsport': 53,
        'geoippath': DEFAULT_GEO_IP_DB_PATH,
        'asndatabasefilename': DEFAULT_ASN_DB_FILENAME,
        'citydatabasefilename': DEFAULT_CC_DB_FILENAME,
        'excluded_ips': [],
    }

    def test__ip_to_asn__called_or_not(self):
        data = super(TestEnricherWithFullConfig, self).test__ip_to_asn__called_or_not()
        self._assert_geoip_method_called(self.enricher.ip_to_asn, data)

    def test__ip_to_cc__called_or_not(self):
        data = super(TestEnricherWithFullConfig, self).test__ip_to_cc__called_or_not()
        self._assert_geoip_method_called(self.enricher.ip_to_cc, data)

    def test__enrich__with_no_data(self):
        data = self.enricher.enrich(RecordDict({}))
        self.assertEqualIncludingTypes(data, RecordDict({'enriched': ([], {})}))

    def test__enrich__with_irrelevant_data(self):
        data = self.enricher.enrich(RecordDict(self.COMMON_DATA))
        self.assertEqualIncludingTypes(data, RecordDict(dict(self.COMMON_DATA, **{
            'enriched': ([], {})})))

    def test__enrich__with_fqdn_given(self):
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_fqdn_given()
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
        self.assertFalse(self.enricher._resolver.query.called)
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates()
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
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_url_given()
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
        self.assertFalse(self.enricher._resolver.query.called)
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
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"192.168.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_ip_url_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"192.168.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_fqdn_and_url_given()
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
        self.assertFalse(self.enricher._resolver.query.called)
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given(self):
        data = super(TestEnricherWithFullConfig, self).test__enrich__with_address_and_fqdn_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_address_and_fqdn_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_address_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"10.20.30.40": ["asn", "cc"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_address_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_address_and_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn", "cc"]}),
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_address_and_fqdn_and_ip_url_given()
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

    def test_adding_asn_cc_if_asn_not_valid_and_cc_is_valid(self):
        """Test if asn/cc are (maybe) added"""
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_asn_db_side_effect_if_enabled(GeoIP2Error)
        self._set_cc_db_return_value_if_enabled('PL')
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'cc': u'PL', u'ip': u'127.0.0.1'},
                          {u'cc': u'PL', u'ip': u'192.187.0.1'},
                          {u'cc': u'PL', u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'cc'],
                               u'127.0.0.1': [u'cc'],
                               u'192.187.0.1': [u'cc']}),
                         data_expected["enriched"])

    def test_adding_asn_cc_if_asn_and_cc_are_valid(self):
        """Test if asn/cc are (maybe) added"""
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_asn_db_return_value_if_enabled(1234)
        self._set_cc_db_return_value_if_enabled('UK')
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'asn': 1234, u'cc': u'UK', u'ip': u'127.0.0.1'},
                          {u'asn': 1234, u'cc': u'UK', u'ip': u'192.187.0.1'},
                          {u'asn': 1234, u'cc': u'UK', u'ip': u'10.15.1.255'}],
                         data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'asn', u'cc'],
                               u'127.0.0.1': [u'asn', u'cc'],
                               u'192.187.0.1': [u'asn', u'cc']}),
                         data_expected["enriched"])

    def test_adding_asn_cc_if_asn_is_valid_and_cc_is_not(self):
        """Test if asn/cc are (maybe) added"""
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_asn_db_return_value_if_enabled(123456)
        self._set_cc_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'asn': 123456, u'ip': u'127.0.0.1'},
                          {u'asn': 123456, u'ip': u'192.187.0.1'},
                          {u'asn': 123456, u'ip': u'10.15.1.255'}],
                         data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'asn'],
                               u'127.0.0.1': [u'asn'],
                               u'192.187.0.1': [u'asn']}),
                         data_expected["enriched"])

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_asn_cc_always_dropped_and_new_ones_added_if_asn_and_are_not_valid(self, LOGGER_mock):
        """Test if already existing asn/cc are removed and new ones are (maybe) added"""
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        self._set_asn_db_side_effect_if_enabled(GeoIP2Error)
        self._set_cc_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=4)
        self.assertEqual([{u'ip': u'127.0.0.1'},
                          {u'ip': u'192.187.0.1'},
                          {u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])
        self.assertEqual(len(LOGGER_mock.warning.mock_calls), self.expected_num_of_warnings)

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_asn_cc_always_dropped_and_new_ones_added_if_asn_is_not_valid(self, LOGGER_mock):
        """Test if already existing asn/cc are removed and new ones are (maybe) added"""
        self._set_asn_db_side_effect_if_enabled(GeoIP2Error)
        self._set_cc_db_return_value_if_enabled('PL')
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=4)
        self.assertEqual([{u'cc': u'PL', u'ip': u'127.0.0.1'},
                          {u'cc': u'PL', u'ip': u'192.187.0.1'},
                          {u'cc': u'PL', u'ip': u'10.15.1.255'}],
                         data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'cc'],
                               u'127.0.0.1': [u'cc'],
                               u'192.187.0.1': [u'cc']}),
                         data_expected["enriched"])
        self.assertEqual(
            len(LOGGER_mock.warning.mock_calls),
            self.expected_num_of_warnings)

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_asn_cc_always_dropped_and_new_ones_added_if_asn_and_cc_are_valid(self, LOGGER_mock):
        """Test if already existing asn/cc are removed and new ones are (maybe) added"""
        self._set_asn_db_return_value_if_enabled(12345)
        self._set_cc_db_return_value_if_enabled('UK')
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=4)
        self.assertEqual([{u'asn': 12345, u'cc': u'UK', u'ip': u'127.0.0.1'},
                          {u'asn': 12345, u'cc': u'UK', u'ip': u'192.187.0.1'},
                          {u'asn': 12345, u'cc': u'UK', u'ip': u'10.15.1.255'}],
                         data_expected["address"])
        self.assertEqual(([],
                          {u'10.15.1.255': [u'asn', u'cc'],
                           u'127.0.0.1': [u'asn', u'cc'],
                           u'192.187.0.1': [u'asn', u'cc']}), data_expected["enriched"])
        self.assertEqual(
            len(LOGGER_mock.warning.mock_calls),
            self.expected_num_of_warnings)

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
        self._prepare_config_for_excluded_ips(['1.1.1.1', '2.2.2.2', '3.3.3.3'])
        expected = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')                             #3 --replace iptools
        result = self.enricher._get_excluded_ips()
        self.assertItemsEqual(expected, result)

    def test__get_excluded_ips__without_excluded_ips_in_config(self):
        self._prepare_config_for_excluded_ips([])
        expected = None
        result = self.enricher._get_excluded_ips()
        self.assertEqual(expected, result)

    def test__enrich__with_excluded_ips_config__with_some_ip_to_exclude__1(self):
        self._prepare_config_for_excluded_ips(['127.0.0.1', '2.2.2.2', '3.3.3.3'])
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd",
                                                "address": [{'ip': "127.0.0.1"}]}))
        # the 'data' field is present, so FQDN will not be resolved
        # to IP addresses
        self.assertFalse(self.enricher._resolver.query.called)
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl"}))  # (note: emptied `address` removed)

    def test__enrich__with_excluded_ips_config__with_some_ip_to_exclude__2(self):
        self._prepare_config_for_excluded_ips(['127.0.0.1', '2.2.2.2', '3.3.3.3'])
        self.enricher.excluded_ips = self.enricher._get_excluded_ips()
        data = self.enricher.enrich(RecordDict({"url": "http://www.nask.pl/asd"}))
        self.enricher._resolver.query.assert_called_once_with("www.nask.pl", "A")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl"}))  # (note: emptied `address` removed)

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        data = super(TestEnricherWithFullConfig,
                     self).test__enrich__with_excluded_ips_config__without_any_ip_to_exclude()
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
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')           #3 --replace iptools
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
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')           #3 --replace iptools
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
        self.enricher.excluded_ips = iptools.IpRangeList('1.1.1.1', '2.2.2.2', '3.3.3.3')           #3 --replace iptools
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
        self.enricher.excluded_ips = iptools.IpRangeList('3.0.0.0/8')                               #3 --replace iptools
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


class TestEnricherNoASNDatabase(_BaseTestEnricher, unittest.TestCase):

    MOCK_CONFIG = {
        'dnshost': '8.8.8.8',
        'dnsport': 53,
        'geoippath': DEFAULT_GEO_IP_DB_PATH,
        'asndatabasefilename': '',
        'citydatabasefilename': DEFAULT_CC_DB_FILENAME,
        'excluded_ips': [],
    }

    def test__ip_to_asn__called_or_not(self):
        super(TestEnricherNoASNDatabase, self).test__ip_to_asn__called_or_not()
        self._assert_geoip_method_not_called(self.enricher.ip_to_asn)

    def test__ip_to_cc__called_or_not(self):
        data = super(TestEnricherNoASNDatabase, self).test__ip_to_cc__called_or_not()
        self._assert_geoip_method_called(self.enricher.ip_to_cc, data)

    def test__enrich__with_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["cc", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "cc": 'PL'}]}))

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"1.0.1.1": ["cc", "ip"],
                              "1.1.1.1": ["cc", "ip"],
                              "12.11.10.9": ["cc", "ip"],
                              "127.0.0.1": ["cc", "ip"],
                              "13.1.2.3": ["cc", "ip"],
                              "2.2.2.2": ["cc", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '1.0.1.1',  # note: *removed IP duplicates* and
                         "cc": 'PL'},      # *ordered* by IP (textually)
                        {"ip": '1.1.1.1',
                         "cc": 'PL'},
                        {"ip": '12.11.10.9',
                         "cc": 'PL'},
                        {"ip": '127.0.0.1',
                         "cc": 'PL'},
                        {"ip": '13.1.2.3',
                         "cc": 'PL'},
                        {"ip": '2.2.2.2',
                         "cc": 'PL'}]}))

    def test__enrich__with_url_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "cc": 'PL'}]}))

    def test__enrich__with_ip_url_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"192.168.0.1": ["cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "cc": 'PL'}]}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_ip_url_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"192.168.0.1": ["cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "cc": 'PL'}]}))

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["cc", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_address_and_fqdn_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_address_and_fqdn_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"10.20.30.40": ["cc"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        data = super(TestEnricherNoASNDatabase, self).test__enrich__with_address_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"10.20.30.40": ["cc"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_address_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["cc"]}),
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_address_and_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["cc"]}),
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_address_and_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["cc"]}),
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '10.20.30.40',
                         "cc": 'PL'}]}))

    def test_adding_geoip_data_if_cc_is_valid(self):
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_cc_db_return_value_if_enabled('US')
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'cc': u'US', u'ip': u'127.0.0.1'},
                          {u'cc': u'US', u'ip': u'192.187.0.1'},
                          {u'cc': u'US', u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'cc'],
                               u'127.0.0.1': [u'cc'],
                               u'192.187.0.1': [u'cc']}),
                         data_expected["enriched"])

    def test_adding_geoip_data_if_cc_is_not_valid(self):
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_cc_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'ip': u'127.0.0.1'},
                          {u'ip': u'192.187.0.1'},
                          {u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_geoip_data__drop_and_add_cc__if_cc_is_valid(self, LOGGER_mock):
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        self._set_cc_db_return_value_if_enabled('FR')
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=2)
        self.assertEqual([{u'ip': u'127.0.0.1', u'cc': u'FR'},
                          {u'ip': u'192.187.0.1', u'cc': u'FR', u'asn': 424242},
                          {u'ip': u'10.15.1.255', u'cc': u'FR', u'asn': 434343}],
                         data_expected["address"])
        self.assertEqual(([], {u'127.0.0.1': [u'cc'],
                               u'192.187.0.1': [u'cc'],
                               u'10.15.1.255': [u'cc']}),
                         data_expected["enriched"])
        self.assertEqual(len(LOGGER_mock.warning.mock_calls), self.expected_num_of_warnings)

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_geoip_data__drop_cc__if_cc_is_invalid(self, LOGGER_mock):
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        self._set_cc_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=2)
        self.assertEqual([{u'ip': u'127.0.0.1'},
                          {u'ip': u'192.187.0.1', u'asn': 424242},
                          {u'ip': u'10.15.1.255', u'asn': 434343}],
                         data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])
        self.assertEqual(len(LOGGER_mock.warning.mock_calls), self.expected_num_of_warnings)

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        data = super(TestEnricherNoASNDatabase,
                     self).test__enrich__with_excluded_ips_config__without_any_ip_to_exclude()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["cc", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "cc": 'PL'}]}))


class TestEnricherNoCCDatabase(_BaseTestEnricher, unittest.TestCase):

    MOCK_CONFIG = {
        'dnshost': '8.8.8.8',
        'dnsport': 53,
        'geoippath': DEFAULT_GEO_IP_DB_PATH,
        'asndatabasefilename': DEFAULT_ASN_DB_FILENAME,
        'citydatabasefilename': '',
        'excluded_ips': [],
    }

    def test__ip_to_asn__called_or_not(self):
        data = super(TestEnricherNoCCDatabase, self).test__ip_to_asn__called_or_not()
        self._assert_geoip_method_called(self.enricher.ip_to_asn, data)

    def test__ip_to_cc__called_or_not(self):
        super(TestEnricherNoCCDatabase, self).test__ip_to_cc__called_or_not()
        self._assert_geoip_method_not_called(self.enricher.ip_to_cc)

    def test__enrich__with_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234'}]}))

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"1.0.1.1": ["asn", "ip"],
                              "1.1.1.1": ["asn", "ip"],
                              "12.11.10.9": ["asn", "ip"],
                              "127.0.0.1": ["asn", "ip"],
                              "13.1.2.3": ["asn", "ip"],
                              "2.2.2.2": ["asn", "ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '1.0.1.1',  # note: *removed IP duplicates* and
                         "asn": '1234'},   #       *ordered* by IP (textually)
                        {"ip": '1.1.1.1',
                         "asn": '1234'},
                        {"ip": '12.11.10.9',
                         "asn": '1234'},
                        {"ip": '127.0.0.1',
                         "asn": '1234'},
                        {"ip": '13.1.2.3',
                         "asn": '1234'},
                        {"ip": '2.2.2.2',
                         "asn": '1234'}]}))

    def test__enrich__with_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["asn", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234'}]}))

    def test__enrich__with_ip_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"192.168.0.1": ["asn", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234'}]}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_ip_url_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"192.168.0.1": ["asn", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1',
                         "asn": '1234'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234'}]}))

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["asn", "ip"]}),
            "url": "http://192.168.0.1/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234'}]}))

    def test__enrich__with_address_and_fqdn_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_address_and_fqdn_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_address_and_fqdn_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"10.20.30.40": ["asn"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_address_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"10.20.30.40": ["asn"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        data = super(TestEnricherNoCCDatabase, self).test__enrich__with_address_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn"]}),
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_address_and_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn"]}),
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_address_and_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"10.20.30.40": ["asn"]}),
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '10.20.30.40',
                         "asn": '1234'}]}))

    def test_adding_geoip_data_if_asn_is_valid(self):
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_asn_db_return_value_if_enabled(45678)
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'asn': 45678, u'ip': u'127.0.0.1'},
                          {u'asn': 45678, u'ip': u'192.187.0.1'},
                          {u'asn': 45678, u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {u'10.15.1.255': [u'asn'],
                               u'127.0.0.1': [u'asn'],
                               u'192.187.0.1': [u'asn']}),
                         data_expected["enriched"])

    def test_adding_geoip_data_if_asn_is_not_valid(self):
        data_init = self._get_actual_data_for_adding_asn_cc_if_possible()
        self._set_asn_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'ip': u'127.0.0.1'},
                          {u'ip': u'192.187.0.1'},
                          {u'ip': u'10.15.1.255'}], data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_geoip_data__drop_and_add_asn__if_asn_is_valid(self, LOGGER_mock):
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        self._set_asn_db_return_value_if_enabled(456789)
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=2)
        self.assertEqual([{u'ip': u'127.0.0.1', u'cc': u'JP', u'asn': 456789},
                          {u'ip': u'192.187.0.1', u'cc': u'US', u'asn': 456789},
                          {u'ip': u'10.15.1.255', u'asn': 456789}],
                         data_expected["address"])
        self.assertEqual(([], {u'127.0.0.1': [u'asn'],
                               u'192.187.0.1': [u'asn'],
                               u'10.15.1.255': [u'asn']}),
                         data_expected["enriched"])
        self.assertEqual(len(LOGGER_mock.warning.mock_calls), self.expected_num_of_warnings)

    @mock.patch('n6.utils.enrich.LOGGER')
    def test_existing_geoip_data__drop_asn__if_asn_is_invalid(self, LOGGER_mock):
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        self._set_asn_db_side_effect_if_enabled(GeoIP2Error)
        data_expected = self._enricher_execution_helper(data_init, expected_num_of_warnings=2)
        self.assertEqual([{u'ip': u'127.0.0.1', u'cc': 'JP'},
                          {u'ip': u'192.187.0.1', u'cc': 'US'},
                          {u'ip': u'10.15.1.255'}],
                         data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])
        self.assertEqual(len(LOGGER_mock.warning.mock_calls), self.expected_num_of_warnings)

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        data = super(TestEnricherNoCCDatabase,
                     self).test__enrich__with_excluded_ips_config__without_any_ip_to_exclude()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["asn", "ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1',
                         "asn": '1234'}]}))


class TestEnricherNoGeoIPDatabase(_BaseTestEnricher, unittest.TestCase):

    MOCK_CONFIG = {
        'dnshost': '8.8.8.8',
        'dnsport': 53,
        'geoippath': '',
        'asndatabasefilename': '',
        'citydatabasefilename': '',
        'excluded_ips': [],
    }

    def test__ip_to_asn__called_or_not(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__ip_to_asn__called_or_not()
        self._assert_geoip_method_not_called(self.enricher.ip_to_asn)

    def test__ip_to_cc__called_or_not(self):
        super(TestEnricherNoGeoIPDatabase, self).test__ip_to_cc__called_or_not()
        self._assert_geoip_method_not_called(self.enricher.ip_to_cc)

    def test__enrich__with_fqdn_given(self):
        data = self.enricher.enrich(RecordDict({"fqdn": "cert.pl"}))
        self.enricher._resolver.query.assert_called_once_with("cert.pl", "A")
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1'}]}))

    def test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_fqdn_given__resolved_to_various_ips_with_duplicates()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"1.0.1.1": ["ip"],
                              "1.1.1.1": ["ip"],
                              "12.11.10.9": ["ip"],
                              "127.0.0.1": ["ip"],
                              "13.1.2.3": ["ip"],
                              "2.2.2.2": ["ip"]}),
            "fqdn": "cert.pl",
            "address": [{"ip": '1.0.1.1'},  # note: *removed IP duplicates* and
                        {"ip": '1.1.1.1'},   # *ordered* by IP (textually)
                        {"ip": '12.11.10.9'},
                        {"ip": '127.0.0.1'},
                        {"ip": '13.1.2.3'},
                        {"ip": '2.2.2.2'}]}))

    def test__enrich__with_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1'}]}))

    def test__enrich__with_ip_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"192.168.0.1": ["ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1'}]}))

    def test__enrich__with_ip_url_given__with_nodns_flag(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_ip_url_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {"192.168.0.1": ["ip"]}),
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '192.168.0.1'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_fqdn_and_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1'}]}))

    def test__enrich__with_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {"127.0.0.1": ["ip"]}),
            "url": "http://192.168.0.1/asd",
            "fqdn": "cert.pl",
            "address": [{"ip": '127.0.0.1'}]}))

    def test__enrich__with_address_and_fqdn_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_address_and_fqdn_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40'}]}))

    def test__enrich__with_address_and_fqdn_given__with_nodns_flag(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_address_and_fqdn_given__with_nodns_flag()
        self.assertEqualIncludingTypes(data, RecordDict({
            # (here the '_do_not_resolve_fqdn_to_ip' flag did *not* change behaviour)
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "address": [{"ip": '10.20.30.40'}],
            "_do_not_resolve_fqdn_to_ip": True}))

    def test__enrich__with_address_and_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_address_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '10.20.30.40'}]}))

    def test__enrich__with_address_and_ip_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase, self).test__enrich__with_address_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "url": "http://192.168.0.3/asd",
            "address": [{"ip": '10.20.30.40'}]}))

    def test__enrich__with_address_and_fqdn_and_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_address_and_fqdn_and_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "url": "http://www.nask.pl/asd",
            "address": [{"ip": '10.20.30.40'}]}))

    def test__enrich__with_address_and_fqdn_and_ip_url_given(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_address_and_fqdn_and_ip_url_given()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": ([], {}),
            "fqdn": "cert.pl",
            "url": "http://192.168.0.1/asd",
            "address": [{"ip": '10.20.30.40'}]}))

    def test_existing_geoip_data__drop_and_add_asn__if_asn_is_valid(self):
        # no additional GeoIP data should be added and existing ASN/CC
        # values should not be dropped
        data_init = self._get_actual_data_for_existing_asn_cc_always_dropped_and_new_ones_added_if_possible()
        data_expected = self._enricher_execution_helper(data_init)
        self.assertEqual([{u'ip': u'127.0.0.1', u'cc': u'JP'},
                          {u'ip': u'192.187.0.1', u'cc': u'US', u'asn': 424242},
                          {u'ip': u'10.15.1.255', u'asn': 434343}],
                         data_expected["address"])
        self.assertEqual(([], {}), data_expected["enriched"])

    def test__enrich__with_excluded_ips_config__without_any_ip_to_exclude(self):
        data = super(TestEnricherNoGeoIPDatabase,
                     self).test__enrich__with_excluded_ips_config__without_any_ip_to_exclude()
        self.assertEqualIncludingTypes(data, RecordDict({
            "enriched": (["fqdn"], {"127.0.0.1": ["ip"]}),
            "url": "http://www.nask.pl/asd",
            "fqdn": "www.nask.pl",
            "address": [{"ip": '127.0.0.1'}]}))

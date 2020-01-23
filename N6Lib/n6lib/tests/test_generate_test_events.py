# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import random
import unittest
from collections import MutableSequence

from mock import patch
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.generate_test_events import RandomEvent

_SIMPLE_CONFIG = {
    "possible_event_attributes": ["name", "source", "restriction", "confidence", "category",
                                  "time", "url", "fqdn", "address", "proto", "sport", "dport",
                                  "dip", "id", "rid", "client", "replaces", "status", "md5",
                                  "origin", "sha1", "sha256", "target", "modified", "expires"],
    "required_attributes": ["id", "rid", "source", "restriction", "confidence", "category",
                            "time"],
    "dip_categories": ["bots", "cnc", "dos-attacker", "scanning", "other"],
    "port_values": ["sport", "dport"],
    "md5_values": ["id", "rid", "replaces", "md5"],
    "possible_cc_codes": ["PL", "US", "DE", "CA", "FR", "UK"],
    "possible_domains": ["www.example.com", "example.net"],
    "possible_url": ["http://example.com/index.html", "http://www.example.com/home.html"],
    "possible_source": ["source.one", "another.source", "yet.another-source"],
    "possible_restriction": ["public", "need-to-know"],
    "possible_target": ["Example Ltd.", "Random Co"],
    "possible_client": ["Test Client 1", "Test Client 2"],
    "seconds_max": 180000,
    "expires_days_max": 8,
    "random_ips_max": 5,
}


standard_config_patch = patch(
    'n6lib.generate_test_events.ConfigMixin.get_config_section', return_value=_SIMPLE_CONFIG)


class TestRandomEventWithConfig(unittest.TestCase):

    @standard_config_patch
    def setUp(self, mocked_config):
        event_instance = RandomEvent()
        self.event = event_instance.event
        config = event_instance.config
        self.required_attrs = config['required_attributes']

    def test_required_attrs(self):
        """
        Check if all required values are included in the random event.
        """
        for attr in self.required_attrs:
            self.assertIn(attr, self.event)


@expand
class TestRandomEventWithParams(unittest.TestCase):

    _DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'
    _STANDARD_PARAMS = {
        'name': ['Testing name', 'Testing name2'],
        'source': ['testevents.testchannel', 'testevents.testchannel2'],
        'restriction': ['public', 'internal'],
        'confidence': ['medium', 'high'],
        'url': ['http://www.testdomain.io/test.html', 'http://www.testdomain.io/test2.html'],
        'fqdn': ['www.testdomain.io', 'www.testdomain2.io'],
        'proto': ['tcp', 'udp'],
        'sport': [8353, 8354],
        'dport': [6362, 6463],
        'id': ['d41d8cd98f00b204e9800998ecf8427e', 'bd155b858cc3e76131e3a580480f66cb'],
        'rid': ['48c3b7df32017d7ba6b00c7ae1d33ee6', '4290b1ed5b6fcceef044a3444e1af155'],
        'client': ['testclient', 'testclient2'],
        'replaces': ['eb81460b901a9358df8dd2897fc862a4', '19e342ca7281b2ae296fb868ad17d8c9'],
        'status': ['active', 'expired'],
        'md5': ['6aef738be9d369031b054ebc5235e735', '30d2a232918bc77e21010998b5501e05'],
        'origin': ['darknet', 'honeypot'],
        'sha1': ['02346807a6013599e62044978131068d893fc36e',
                 '8826c5a01fd04759431004ef30c755c280949e8e'],
        'sha256': ['9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
                   '60303ae22b998861bce3b28f33eec1be758a213c86c93c076dbe9f558c11c752'],
        'target': ['test target1', 'test target2'],
    }
    _SPECIAL_PARAMS = {
        'time.min': ['2016-01-02 8:20:11.111234', '2016-01-02 8:20:11.111234'],
        'time.max': ['2016-06-10 14:15:11.23853', '2016-01-02 8:20:11.111234'],
        'ip': ['127.0.0.1', '127.0.0.2'],
        'cc': ['PL', 'EN'],
        'asn': ['1234', '4321'],
    }

    @paramseq
    def _categories():
        yield param({'category': ['flow', 'scam']}).label('non_dip_categories')
        yield param({'category': ['bots', 'cnc']}).label('dip_categories')

    @paramseq
    def _asn_cc_params():
        yield param({'asn': [3213, 1234, 3333]}).label('asn')
        yield param({'cc': ['DE', 'UK']}).label('cc')
        yield param({'asn': [3213, 1234, 3333], 'cc': ['PL', 'EN']}).label('asn_cc')

    @foreach(_categories)
    def test_params(self, category, label):
        """
        Check if params are included in the event.

        Two cases: 1st - category in 'dip categories', 2nd case
        - category not in 'dip categories'.
        """
        params = {}
        params.update(category)
        params.update(self._STANDARD_PARAMS)
        params.update(self._SPECIAL_PARAMS)
        with standard_config_patch:
            instance = RandomEvent(params=params)
        random_event = instance.event
        for param, values in self._STANDARD_PARAMS.iteritems():
            if ((label == 'non_dip_categories' and param in ['dip', 'proto']) or
                    (label == 'dip_categories' and param in ['url', 'fqdn'])):
                self.assertNotIn(param, random_event)
            else:
                self.assertIn(param, random_event)
                event_attr = random_event.get(param)
                if isinstance(event_attr, MutableSequence):
                    self.assertEqual(values, event_attr)
                else:
                    self.assertIn(param, random_event)
                    event_attr = random_event.get(param)
                    if isinstance(event_attr, MutableSequence):
                        self.assertEqual(values, event_attr)
                    else:
                        self.assertIn(random_event.get(param), values)
            self._check_time_attribute(random_event.get('time'))
            if 'modified' in random_event:
                self._compare_modified_attribute(
                    random_event.get('time'), random_event.get('modified'))

    def _get_test_asn_cc_method(self, opt_primary):
        """
        Test a behavior, when user attaches asn and cc params.

        It is a method returning a proper test method.
        When one of them or both are attached - include both of them in
        attributes (otherwise it is randomly chosen whether to include
        asn and cc in address attribute).
        """
        output_params = {}
        if opt_primary:
            assert_method = self.assertNotIn
            output_params['opt.primary'] = True
        else:
            assert_method = self.assertIn

        def test_method(params):
            output_params.update(params)
            with standard_config_patch:
                random_event = RandomEvent(params=output_params).event
            self.assertIn('address', random_event)
            address_attr = random_event.get('address')
            self.assertIsInstance(address_attr, MutableSequence)
            for address in address_attr:
                assert_method('asn', address)
                assert_method('cc', address)
        return test_method

    @foreach(_asn_cc_params)
    def test_asn_cc(self, params):
        """
        Check for 'asn' and 'cc' address attributes, no opt.primary.
        """
        test_method = self._get_test_asn_cc_method(False)
        test_method(params)

    @foreach(_asn_cc_params)
    def test_opt_primary(self, params):
        """
        Check for 'asn' and 'cc' address attributes, with opt.primary.
        """
        test_method = self._get_test_asn_cc_method(True)
        test_method(params)

    def _check_time_attribute(self, datetime_):
        event_datetime = datetime.datetime.strptime(datetime_, self._DATETIME_FORMAT)
        time_min = datetime.datetime.strptime(self._SPECIAL_PARAMS['time.min'][0],
                                              self._DATETIME_FORMAT)
        time_max = datetime.datetime.strptime(self._SPECIAL_PARAMS['time.max'][0],
                                              self._DATETIME_FORMAT)
        self.assertGreaterEqual(event_datetime, time_min)
        self.assertGreaterEqual(time_max, event_datetime)

    def _compare_modified_attribute(self, time_datetime, modified_datetime):
        self.assertGreaterEqual(
            modified_datetime, datetime.datetime.strptime(time_datetime, self._DATETIME_FORMAT))


class TestOptPrimary(unittest.TestCase):

    # 'ip' is added to params, to ensure that 'address' is included
    _STANDARD_PARAMS = {
        'ip': ['127.1.1.1'],
        'url': ['www.testurl.url', 'www.testurl2.url'],
        'fqdn': ['testdomain.com', 'testdomain2.com'],
        'address': [{'ip': '127.1.1.1', 'asn': 1234, 'cc': 'PL'}],
        'opt.primary': True,
    }
    _OPT_PRIMARY_DEPENDANT_ATTRS = ['url', 'fqdn']
    _OPT_PRIMARY_ADDRESS_DEPENDANT_ELEMENTS = ['asn', 'cc']

    def test_opt_primary(self):
        """
        Check the behavior if opt.primary is True.

        Some attributes, like 'url' and 'fqdn' and elements of
        the 'address' attribute ('asn', 'cc') should not be present
        in case of opt.primary param.
        """
        params = self._STANDARD_PARAMS
        with standard_config_patch:
            random_event = RandomEvent(params=params).event
        for attr in self._OPT_PRIMARY_DEPENDANT_ATTRS:
            self.assertNotIn(attr, random_event)
        address_attr = random_event.get('address')
        for address in address_attr:
            for element in self._OPT_PRIMARY_ADDRESS_DEPENDANT_ELEMENTS:
                self.assertNotIn(element, address)


@expand
class TestAccessZone(unittest.TestCase):

    _CLIENT_ID = 'test_client'

    @paramseq
    def _get_arguments():
        yield param(access_zone='inside')
        yield param(access_zone='threats')
        yield param(access_zone='search')

    def test_inside_zone(self):
        """Access zone: 'inside' - 'client' attribute: client_id."""
        clients = [self._CLIENT_ID, None]
        for client in clients:
            with standard_config_patch:
                random_event = RandomEvent(access_zone='inside', client_id=client).event
            self.assertIn('client', random_event)
            client_attr = random_event.get('client')
            self.assertIsInstance(client_attr, MutableSequence)
            self.assertEqual(len(client_attr), 1)
            self.assertEqual(client_attr[0], client)

    @foreach(_get_arguments)
    def test_client_from_params(self, access_zone):
        """Test different access zones with 'client' in params."""
        params = {'client': ['test_client1', 'test_client2']}
        with standard_config_patch:
            random_event = RandomEvent(
                params=params, access_zone=access_zone, client_id=self._CLIENT_ID).event
        self.assertIn('client', random_event)
        client_attr = random_event.get('client')
        if access_zone == 'inside':
            self.assertEqual(client_attr[0], self._CLIENT_ID)
        else:
            # access zone is other than 'inside' - get 'client' from
            # params
            for client in client_attr:
                self.assertIn(client, params['client'])


@expand
class TestExtraParams(unittest.TestCase):

    _MAX_SUB_LEN = 4

    @paramseq
    def _get_possible_vals():
        with standard_config_patch:
            random_event_config = RandomEvent().config
        config_fqdn_vals = 'possible_domains'
        config_url_vals = 'possible_url'
        possible_fqdns = random_event_config.get(config_fqdn_vals)
        possible_urls = random_event_config.get(config_url_vals)
        for fqdn in possible_fqdns:
            yield param(val=fqdn, possible_vals=possible_fqdns).label('fqdn')
        for url in possible_urls:
            yield param(val=url, possible_vals=possible_urls).label('url')

    @foreach(_get_possible_vals)
    def test_subs(self, val, possible_vals, label):
        """Test fqdn.sub and url.sub params."""
        sub = self._get_sub(val)
        # set category to 'flow', to prevent randomly choosing one of
        # the 'dip' categories
        params = {'category': 'flow', '{}.sub'.format(label): [sub]}
        with standard_config_patch:
            random_event = RandomEvent(params=params).event
        event_attr = random_event.get(label)
        self.assertIn(event_attr, possible_vals)

    @staticmethod
    def _get_sub(val):
        max_len = len(val)
        random_start = random.randint(0, len(val)-2)
        random_end = random.randint(random_start, max_len)
        return val[random_start:random_end]


@expand
class TestGenerateMultipleEventData(unittest.TestCase):

    _NUM_OF_EVENTS = range(1, 20)

    @foreach(_NUM_OF_EVENTS)
    def test_generate_multiple_event_data(self, num):
        """Test RandomEvent.generate_multiple_event_data() method."""
        with standard_config_patch:
            events = list(RandomEvent.generate_multiple_event_data(num))
        self.assertEqual(len(events), num)

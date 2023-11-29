# Copyright (c) 2013-2023 NASK. All rights reserved.

import json
import unittest
from unittest.mock import MagicMock, call

from n6datapipeline.base import LegacyQueuedBase
from n6datapipeline.filter import Filter
from n6lib.auth_api import InsideCriteriaResolver
from n6lib.record_dict import RecordDict, AdjusterError



## maybe TODO later: clean-up/refactor the stuff in this module...

# (note that the main job of *filter* -- i.e., determining which
# organization ids the event's `client` attribute should include
# -- is covered also by comprehensive tests implemented within the
# n6lib.tests.test_auth_api.TestInsideCriteriaResolver_initialization and
# n6lib.tests.test_auth_api.TestInsideCriteriaResolver__get_client_and_urls_matched_org_ids
# classes)



TEST_CRITERIA = (
    [
        {'org_id': 'afbc',
         'cc_seq': ['AL'],
         'asn_seq': [43756],
         'fqdn_seq': [u'mycertbridgeonetalamakotawpmikmoknask.org',
                      u'alamakota.biz',
                      u'mikmokcertmakabimynask.net'],
         'ip_min_max_seq': [(2334252224, 2334252227)]},
        {'org_id': 'fdc',
         'cc_seq': ['SU', 'RU'],
         'asn_seq': [45975, 13799],
         'fqdn_seq': [u'onetbridgemikmokcert.eu', u'mikmokcertalamakota.org', u'mikmoknaskwp.info'],
         'ip_min_max_seq': [(2589577040, 2589577041)]},
        {'org_id': 'edca',
         'cc_seq': ['DD', 'DD'],
         'asn_seq': [8262, 4079],
         'fqdn_seq': [u'virut.eu', u'bridgealamakotawpvirut.eu', u'bridge.biz'],
         'ip_min_max_seq': [(653221832, 653221835)]},
        {'org_id': 'bdc',
         'cc_seq': ['GU', 'GU'],
         'asn_seq': [10546, 63520],
         'fqdn_seq': [u'certmikmokonetnaskvirutmakabiforcewpmybridgealamakota.org',
                      u'forcemyonetvirutbridgemikmokwpnaskmakabi.info',
                      u'virut.net'],
         'ip_min_max_seq': [(494991530, 494991530)]},
        {'org_id': 'befa',
         'cc_seq': ['CX', 'US'],
         'asn_seq': [31110, 26648],
         'fqdn_seq': [u'makabimikmokvirutonet.biz'],
         'ip_min_max_seq': [(3228707569, 3228707578)]},
        {'org_id': 'ebcadf',
         'cc_seq': ['US', 'GU'],
         'asn_seq': [52042],
         'fqdn_seq': [u'alamakotamakabi.pl', u'forcemakabivirutcert.com'],
         'ip_min_max_seq': [(1787298955, 1787298955)]},
        {'org_id': 'cfa',
         'cc_seq': ['DD', 'AI'],
         'asn_seq': [59009, 39165, 43185],
         'fqdn_seq': [u'alamakotabridge.pl',
                      u'makabibridgevirutmycertnaskonetalamakotawpforcemikmok.biz',
                      u'naskmikmok.eu'],
         'ip_min_max_seq': [(1378497104, 1378497107)]},
        {'org_id': 'eabf',
         'cc_seq': ['AL'],
         'asn_seq': [33151, 61490, 57963],
         'fqdn_seq': [u'wpbridgemakabialamakota.pl',
                      u'bridgemakabialamakotamikmokonetforcenaskmywpvirutcert.org',
                      u'onetmikmokwpbridgecert.ru'],
         'ip_min_max_seq': [(1007811092, 1007811093), (1007811094, 1007811095)]},
        {'org_id': 'caebf',
         'cc_seq': ['DD'],
         'asn_seq': [40051, 39020, 61348],
         'fqdn_seq': [u'naskalamakotaonet.info'],
         'ip_min_max_seq': [(2031422565, 2031422565)]},
        {'org_id': 'decfba',
         'cc_seq': ['SU', 'RU'],
         'asn_seq': [21463],
         'fqdn_seq': [u'mikmokalamakota.eu'],
         'ip_min_max_seq': [(1292036523, 1292036525)]},
        {'org_id': 'cli16bit',
         'cc_seq': ['PL'],
         'asn_seq': [21467],
         'fqdn_seq': [u'ala.eu', u'król.pl'],
         'ip_min_max_seq': [(1292042241, 1292107775), (1292036523, 1292042239)]},
    ])


class TestFilter(unittest.TestCase):

    def setUp(self):
        self.filter = Filter.__new__(Filter)
        self.per_test_inside_criteria = None  # to be set in methods that need it
        self.filter.auth_api = self._make_auth_api_mock()
        self.fqdn_only_categories = frozenset(['leak'])

    def _make_auth_api_mock(self):
        m = MagicMock()
        m.get_inside_criteria_resolver.side_effect = (
            lambda: InsideCriteriaResolver(self.per_test_inside_criteria))
        return m

    def tearDown(self):
        assert all(
            c == call.get_inside_criteria_resolver()
            for c in self.filter.auth_api.mock_calls), 'test must be updated?'


    def test_parameters_queue(self):
        """Test parameters queue."""
        self.assertTrue(issubclass(Filter, LegacyQueuedBase))
        self.assertEqual(Filter.input_queue['exchange'],
                         'event')
        self.assertEqual(Filter.input_queue['exchange_type'],
                         'topic')
        self.assertEqual(Filter.input_queue['queue_name'],
                         'filter')
        self.assertEqual(Filter.input_queue['accepted_event_types'],
                         ['event',
                          'bl-new',
                          'bl-update',
                          'bl-change',
                          'bl-delist',
                          'bl-expire',
                          'suppressed'])
        self.assertEqual(Filter.output_queue['exchange'],
                         'event')
        self.assertEqual(Filter.output_queue['exchange_type'],
                         'topic')

    def reset_body(self, d):
        d['address'][0]['cc'] = 'XX'
        d['address'][1]['cc'] = 'XX'
        d['address'][2]['cc'] = 'XX'
        d['address'][0]['asn'] = '1'
        d['address'][1]['asn'] = '1'
        d['address'][2]['asn'] = '1'
        d['address'][0]['ip'] = '0.0.0.1'
        d['address'][1]['ip'] = '0.0.0.2'
        d['address'][2]['ip'] = '1.0.0.0'
        return d

    def test__get_client_and_urls_matched__1(self):
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "139.33.220.192", "asn": "1"},
                                            {"cc": "XX", "ip": "100.71.83.178", "asn": "1"},
                                            {"cc": "XX", "ip": "102.71.83.178", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}

        # tested key:[test_value,[valid value]]
        input_data = {'ip': ['139.33.220.192', ['afbc']],
                      'cc': ['AL', ['afbc', 'eabf']],
                      'asn': ['43756', ['afbc']],
                      'fqdn': ['mycertbridgeonetalamakotawpmikmoknask.org', ['afbc']]}

        self.per_test_inside_criteria = TEST_CRITERIA

        for i in input_data:
            body = self.reset_body(body)
            if i == 'fqdn':
                body['fqdn'] = input_data[i][0]
            else:
                body['address'][0][i] = input_data[i][0]
            json_msg = json.dumps(body)
            record_dict = RecordDict.from_json(json_msg)
            self.assertEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                (input_data[i][1], {}))

    def test__get_client_and_urls_matched__2(self):
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"},
                                            {"cc": "XX", "ip": "100.71.83.178", "asn": "1"},
                                            {"cc": "XX", "ip": "102.71.83.178", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}

        # tested key:[test_value,[valid value]]
        input_data = {'ip': ['154.89.207.81', ['fdc']],
                      'cc': ['SU', ['decfba', 'fdc']],
                      'asn': ['45975', ['fdc']],
                      'fqdn': ['onetbridgemikmokcert.eu', ['fdc']]}

        self.per_test_inside_criteria = TEST_CRITERIA

        for i in input_data:
            body = self.reset_body(body)
            if i == 'fqdn':
                body['fqdn'] = input_data[i][0]
            else:
                body['address'][0][i] = input_data[i][0]
            json_msg = json.dumps(body)
            record_dict = RecordDict.from_json(json_msg)
            self.assertCountEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                (input_data[i][1], {}))

    def test__get_client_and_urls_matched__3(self):
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"},
                                            {"cc": "XX", "ip": "100.71.83.178", "asn": "1"},
                                            {"cc": "XX", "ip": "102.71.83.178", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}

        # tested key:[test_value,[valid value]]
        input_data = {'ip': ['192.114.42.241', ['befa']],
                      'cc': ['CX', ['befa']],
                      'asn': ['31110', ['befa']],
                      'fqdn': ['makabimikmokvirutonet.biz', ['befa']]}

        self.per_test_inside_criteria = TEST_CRITERIA
        for i in input_data:
            body = self.reset_body(body)
            if i == 'fqdn':
                body['fqdn'] = input_data[i][0]
            else:
                body['address'][0][i] = input_data[i][0]
            json_msg = json.dumps(body)
            record_dict = RecordDict.from_json(json_msg)
            self.assertCountEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                (input_data[i][1], {}))

        # tested key:[test_value,[valid value]]
        input_data = {'ip': ['192.114.42.242', ['befa']],
                      'cc': ['CX', ['befa']],
                      'asn': ['31110', ['befa']],
                      'fqdn': ['makabimikmokvirutonet.biz', ['befa']]}
        for i in input_data:
            body = self.reset_body(body)
            if i == 'fqdn':
                body['fqdn'] = input_data[i][0]
            else:
                body['address'][0][i] = input_data[i][0]
            json_msg = json.dumps(body)
            record_dict = RecordDict.from_json(json_msg)
            self.assertCountEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                (input_data[i][1], {}))

    def test__get_client_and_urls_matched__empty_cc(self):
        test_criteria_local = [
            {'org_id': 'befa',
             'cc_seq': ['CX', 'US'],
             'asn_seq': [31110, 26648],
             'fqdn_seq': [u'makabimikmokvirutonet.biz'],
             'ip_min_max_seq': [(3228707569, 3228707578)],
             },
        ]
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"},
                                            {"cc": "XX", "ip": "100.71.83.178", "asn": "1"},
                                            {"cc": "XX", "ip": "102.71.83.178", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}

        # tested key:[test_value,[valid value]]
        input_data = {'ip': ['192.114.42.241', ['befa']],
                      # 'cc':['CX', ['befa']],
                      'asn': ['31110', ['befa']],
                      'fqdn': ['makabimikmokvirutonet.biz', ['befa']]}

        self.per_test_inside_criteria = test_criteria_local
        for i in input_data:
            body = self.reset_body(body)
            if i == 'fqdn':
                body['fqdn'] = input_data[i][0]
            else:
                body['address'][0][i] = input_data[i][0]
            json_msg = json.dumps(body)
            record_dict = RecordDict.from_json(json_msg)
            self.assertCountEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                (input_data[i][1], {}))

    def test__get_client_and_urls_matched__range_ip(self):
        test_criteria_local = [
            {
                'org_id': 'cli16bit',
                'cc_seq': ['PL'],
                'asn_seq': [21467],
                'fqdn_seq': [u'ala.eu'],
                'ip_min_max_seq': TEST_CRITERIA[-1]['ip_min_max_seq'],
            }
        ]
        body = self.prepare_mock(test_criteria_local)

        body['address'][0]['ip'] = '77.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['ip'] = '77.2.233.250'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['ip'] = '77.2.254.250'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['ip'] = '77.3.100.1'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['ip'] = '77.3.255.255'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        # test outside the network
        body['address'][0]['ip'] = '77.2.233.170'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['ip'] = '77.2.233.0'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['ip'] = '77.1.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['ip'] = '77.3.0.0'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['ip'] = '77.4.0.0'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__single_ip(self):
        test_criteria_local = [
            {
                'org_id': 'cli16bit',
                'cc_seq': ['PL'],
                'asn_seq': [21467],
                'fqdn_seq': [u'ala.eu'],
                'ip_min_max_seq': [(1292036523, 1292036523)],  # '77.2.233.171'
            }
        ]
        data = self.prepare_mock(test_criteria_local)
        data['address'][0]['ip'] = '77.2.233.171'
        record_dict = RecordDict(data)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        for other_ip in [
                '77.2.233.170',
                '77.2.233.172',
                '77.2.233.250',
                '77.2.233.0',
                '77.2.254.250',
                '77.3.100.1',
                '77.3.255.255',
                '77.1.233.171',
                '77.3.0.0',
                '77.4.0.0',
                '1.2.3.4',
                '10.20.30.40',
                '0.0.0.1',
                '255.255.255.255',
        ]:
            data['address'][0]['ip'] = other_ip
            record_dict = RecordDict(data)
            self.assertEqual(
                self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
                ([], {}))

    def test__get_client_and_urls_matched__cc(self):
        test_criteria_local = [
            {'org_id': 'cli16bit',
             'cc_seq': ['PL'],
             'asn_seq': [21467],
             'fqdn_seq': [u'ala.eu'],
             'ip_min_max_seq': TEST_CRITERIA[-1]['ip_min_max_seq'], }]
        body = self.prepare_mock(test_criteria_local)

        body['address'][0]['cc'] = 'PL'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['cc'] = 'pl'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['cc'] = 'Pl'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        # test outside the network
        body['address'][0]['cc'] = 'EU'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__asn(self):
        test_criteria_local = [
            {'org_id': 'cli16bit',
             'cc_seq': ['PL'],
             'asn_seq': [21467],
             'fqdn_seq': [u'ala.eu'],
             'ip_min_max_seq': TEST_CRITERIA[-1]['ip_min_max_seq'], }]
        body = self.prepare_mock(test_criteria_local)

        body['address'][0]['asn'] = '21467'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['asn'] = ' 21467'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['asn'] = '21467 '
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['asn'] = '0021467'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['address'][0]['asn'] = 21467
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        # test outside the network
        body['address'][0]['asn'] = '21466'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['asn'] = '21468'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['asn'] = '21468'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body['address'][0]['asn'] = '0'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__fqdn_seq(self):
        test_criteria_local = [
            {'org_id': 'cli16bit',
             'cc_seq': ['PL'],
             'asn_seq': [21467],
             'fqdn_seq': [u'ala.eu', u'xxx.org', u'aaa.aa'],
             'ip_min_max_seq': TEST_CRITERIA[-1]['ip_min_max_seq'], }]
        body = self.prepare_mock(test_criteria_local)

        body['fqdn'] = 'ala.eu'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['fqdn'] = 'xxx.org'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['fqdn'] = 'aaa.aa'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        body['fqdn'] = u'aaa.aa'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['cli16bit'], {}))

        # test outside the network
        body['fqdn'] = 'xxx.eu'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__empty_fileds_asn_ip_cc_fqdn_address(self):
        test_criteria_local = [{'org_id': 'org1',
                                'cc_seq': ["PL", "DE", "US"],
                                'asn_seq': [42, 555, 12312],
                                'fqdn_seq': [u"nask.pl", u"onet.pl"],
                                'ip_min_max_seq': TEST_CRITERIA[-1]['ip_min_max_seq'], },
                               {'org_id': 'org2',
                                'cc_seq': ["RU", "DE", "US"],
                                'asn_seq': [4235],
                                'fqdn_seq': [u"nask.pl", u"cert.pl"],
                                'ip_min_max_seq': [(1, 4194303),
                                                   (4294901760, 4294901792)], }]

        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}

        # test_all_fields
        self.per_test_inside_criteria = test_criteria_local
        body['fqdn'] = 'onet.pl'
        body['address'][0]['cc'] = 'GH'
        body['address'][0]['asn'] = '1234'
        body['address'][0]['ip'] = '73.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_fqdn
        if 'fqdn' in body:
            del body['fqdn']
        body['address'][0]['cc'] = 'GH'
        body['address'][0]['asn'] = '1234'
        body['address'][0]['ip'] = '73.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        # test test_empty_cc
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        body['fqdn'] = 'onet.pl'
        body['address'][0]['asn'] = '4235'
        body['address'][0]['ip'] = '73.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1', 'org2'], {}))

        # test test_empty_asn
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        body['fqdn'] = 'www.onet.pl'
        body['address'][0]['cc'] = 'XX'
        body['address'][0]['ip'] = '73.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_ip
        if 'ip' in body['address'][0]:
            del body['address'][0]['ip']
        body['fqdn'] = 'www.onet.com'
        body['address'][0]['cc'] = 'XX'
        body['address'][0]['asn'] = '1234'
        json_msg = json.dumps(body)
        self.assertRaises(AdjusterError, RecordDict.from_json, json_msg)

        # test test_empty_address
        if 'address' in body:
            del body['address']
        body['fqdn'] = 'www.onet.pl'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_all
        if 'address' in body:
            del body['address']
        if 'fqdn' in body:
            del body['fqdn']
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertCountEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl", "source": "hpfeeds.dionaea",
                "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397",
                "sport": "2147", "dip": "10.28.71.43", "id": "023a00e7c2ef04ee5b0f767ba73ee397"}
        # test test_empty_ip_asn
        if 'ip' in body['address'][0]:
            del body['address'][0]['ip']
        if 'asn' in body['address']:
            del body['address'][0]['asn']
        body['fqdn'] = 'www.onet.pl'
        body['address'][0]['cc'] = 'PL'
        json_msg = json.dumps(body)
        self.assertRaises(AdjusterError, RecordDict.from_json, json_msg)

        # test test_empty_ip_cc
        if 'ip' in body['address'][0]:
            del body['address'][0]['ip']
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        body['fqdn'] = 'www.onet.pl'
        body['address'][0]['asn'] = '1234'
        json_msg = json.dumps(body)
        self.assertRaises(AdjusterError, RecordDict.from_json, json_msg)

        # test test_empty_ip_fqdn
        if 'ip' in body['address'][0]:
            del body['address'][0]['ip']
        if 'fqdn' in body:
            del body['fqdn']
        body['address'][0]['asn'] = '1234'
        body['address'][0]['cc'] = 'PL'
        json_msg = json.dumps(body)
        self.assertRaises(AdjusterError, RecordDict.from_json, json_msg)

        # test test_empty_asn_cc
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        body['fqdn'] = 'www'
        body['address'][0]['ip'] = '77.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_asn_cc
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        if 'fqdn' in body:
            del body['fqdn']
        body['address'][0]['cc'] = 'PL'
        body['address'][0]['ip'] = '77.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_fqdn_cc
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        if 'fqdn' in body:
            del body['fqdn']
        body['address'][0]['asn'] = '42'
        body['address'][0]['ip'] = '7.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_asn_ip_fqdn
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        if 'fqdn' in body:
            del body['fqdn']
        if 'ip' in body['address'][0]:
            del body['address'][0]['ip']
        body['address'][0]['cc'] = 'PL'
        json_msg = json.dumps(body)
        self.assertRaises(AdjusterError, RecordDict.from_json, json_msg)

        # test test_empty_asn_cc_fqdn
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        if 'fqdn' in body:
            del body['fqdn']
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        body['address'][0]['ip'] = '77.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

        # test test_empty_asn_cc_fqdn
        if 'asn' in body['address'][0]:
            del body['address'][0]['asn']
        if 'fqdn' in body:
            del body['fqdn']
        if 'cc' in body['address'][0]:
            del body['address'][0]['cc']
        body['address'][0]['ip'] = '77.2.233.171'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1'], {}))

    def test__get_client_and_urls_matched__no_fqdn_seq(self):
        test_criteria_local = [
            {'org_id': 'org4',
             'asn_seq': [21467],
             'fqdn_seq': [''], }]
        body = self.prepare_mock(test_criteria_local)
        # test outside network
        body['address'][0]['cc'] = 'GU'
        body['address'][0]['asn'] = 21467
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {}))

    def test__get_client_and_urls_matched__url_pattern(self):
        test_criteria_local = [
            {'org_id': 'org4',
             'asn_seq': [],
             'fqdn_seq': [''],
             'url_seq': ['wp.pl', u'wpą.pl'], }]
        body = self.prepare_mock(test_criteria_local)
        # test glob mach
        body[u'url_pattern'] = u'*.*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': ['wp.pl', u'wpą.pl']}))
        # test regexp match
        body[u'url_pattern'] = u'^w.*\\.[pu][ls]'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': ['wp.pl', u'wpą.pl']}))
        # test glob, not match
        body[u'url_pattern'] = u'*/*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # test regexp not mach
        body[u'url_pattern'] = u'^w.*\\.[au][ls]'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # test bad regexp
        body[u'url_pattern'] = u'^w.*\\.[au][ls'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # test bad glob
        body[u'url_pattern'] = u'??!xx%$2ąść„ŋ…'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # test glob with unicode, match
        body[u'url_pattern'] = u'??ą.pl'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': [u'wpą.pl']}))
        # test regexp with unicode, match
        body[u'url_pattern'] = u'..*ą\\.pl'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': [u'wpą.pl']}))
        # test regexp with unicode, match
        body[u'url_pattern'] = r'\w+(?<=ą)\.[p]'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': [u'wpą.pl']}))
        # test regexp with unicode, match
        body[u'url_pattern'] = r'\w+(?<!ą)\.[p]'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': [u'wp.pl']}))

    def test__get_client_and_urls_matched__url_pattern_empty(self):
        test_criteria_local = [
            {'org_id': 'org4',
             'asn_seq': [],
             'fqdn_seq': [''],
             'url_seq': ['wp.pl', u'wpą.pl'], }]
        body = self.prepare_mock(test_criteria_local)
        # test empty url_pattern unicode
        body[u'url_pattern'] = u''
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # test empty url_pattern string
        body[u'url_pattern'] = ''
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # # test empty url_pattern = None
        body[u'url_pattern'] = None
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def prepare_mock(self, test_criteria_local):
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "sha1": "023a00e7c2ef04ee5b0f767ba73ee39734323432", "name": "virut",
                "proto": "tcp", "address": [{"cc": "XX", "ip": "1.1.1.1", "asn": "1"},
                                            {"cc": "XX", "ip": "100.71.83.178", "asn": "1"},
                                            {"cc": "XX", "ip": "102.71.83.178", "asn": "1"}],
                "fqdn": "domain.com", "url": "http://onet.pl",
                "source": "hpfeeds.dionaea", "time": "2013-07-01 20:37:20", "dport": "445",
                "rid": "023a00e7c2ef04ee5b0f767ba73ee397", "sport": "2147", "dip": "10.28.71.43",
                "id": "023a00e7c2ef04ee5b0f767ba73ee397"}
        self.per_test_inside_criteria = test_criteria_local
        body = self.reset_body(body)
        return body

    def test__get_client_and_urls_matched__url_seq_empty(self):
        test_criteria_local = [
            {'org_id': 'org4',
             'asn_seq': [],
             'fqdn_seq': [''],
             'url_seq': [''], }]
        body = self.prepare_mock(test_criteria_local)
        # test glob mach
        body[u'url_pattern'] = u'*.*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__many_url_seq(self):
        test_criteria_local = [
            {'org_id': 'org4',
             'asn_seq': [],
             'fqdn_seq': [''],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], }]
        body = self.prepare_mock(test_criteria_local)
        # test glob mach
        body[u'url_pattern'] = u'*.*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': ['example.com', 'http://aaa.pl/auth.php', u'wąska.pl']}))
        # test regexp mach
        body[u'url_pattern'] = u'.*aaa\\.pl\\/auth.*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': ['http://aaa.pl/auth.php']}))
        # test regexp mach
        body[u'url_pattern'] = u'.*example.*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': ['example.com']}))
        # test regexp mach
        body[u'url_pattern'] = u'wą[a-z][xkl]a\\..*'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org4'], {'org4': [u'wąska.pl']}))

    def test__get_client_and_urls_matched__only_fqdn(self):
        # domain is ok, category 'leak'
        test_criteria_local = [
            {'org_id': 'org77',
             'asn_seq': [],
             'fqdn_seq': [u'spa.pl', u'ham.com', u'egg.pl', u'domain.com'],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], },
            {'org_id': 'org78',
             'asn_seq': [],
             'fqdn_seq': [u'domain.com', u'kotpiesiwiewiorka.pl'],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], }
        ]
        body = self.prepare_mock(test_criteria_local)
        body['category'] = 'leak'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org77', 'org78'], {}))
        # asn is ok, but category is 'leak' and domain is fake
        for test_criteria in test_criteria_local:
            test_criteria['asn_seq'] = [777, 888, 999]
            test_criteria['fqdn_seq'] = [u'domaincert.com', u'kot.pl']
        body = self.prepare_mock(test_criteria_local)
        body['category'] = 'leak'
        for adr in body['address']:
            adr['asn'] = 888
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))
        # in first element test_criteria_local fqdn_seq is fake, asn_seq in all elements is ok.
        test_criteria_local = [
            {'org_id': 'org77',
             'asn_seq': [888],
             'fqdn_seq': [u'spam.pl', u'ham.pl', u'egg.pl'],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], },
            {'org_id': 'org78',
             'asn_seq': [666, 777, 888],
             'fqdn_seq': [u'domain.com', u'kotpiesiwiewiorka.pl'],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], }
        ]
        body = self.prepare_mock(test_criteria_local)
        body['category'] = 'leak'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org78'], {}))
        # test do not use check_pattern if category is 'leak'
        test_criteria_local = [
            {'org_id': 'org22',
             'asn_seq': [],
             'fqdn_seq': [''],
             'url_seq': [u'wąska.pl', 'example.com', 'http://aaa.pl/auth.php'], }]
        body = self.prepare_mock(test_criteria_local)
        body[u'url_pattern'] = u'*.*'
        body['category'] = 'leak'
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            ([], {}))

    def test__get_client_and_urls_matched__with_idna_fqdn(self):
        test_criteria_local = [{
            'org_id': 'org1000',
            'fqdn_seq': [u'xn--krlgr-1tac.pl'],  # `królgór.pl`, IDNA-encoded + coerced to unicode
        }]
        self.per_test_inside_criteria = test_criteria_local
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "name": "virut", "address": [{"cc": "XX", "ip": "1.1.1.1"}],
                "source": "hpfeeds.dionaea", "time": "2013-07-01 20:37:20",
                "fqdn": u'test.królgór.pl'}
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org1000'], {}))

    def test__get_client_and_urls_matched__with_unicode_url_pattern(self):
        test_criteria_local = [{
            'org_id': 'org11',
            'url_seq': [u'władcażlebów.pl'],
        }]
        self.per_test_inside_criteria = test_criteria_local
        body = {"category": "bots", "restriction": "public", "confidence": "medium",
                "name": "virut", "address": [{"cc": "XX", "ip": "1.1.1.1"}],
                "source": "hpfeeds.dionaea", "time": "2013-07-01 20:37:20",
                u'url_pattern': u'*ów.*'}
        json_msg = json.dumps(body)
        record_dict = RecordDict.from_json(json_msg)
        self.assertEqual(
            self.filter.get_client_and_urls_matched(record_dict, self.fqdn_only_categories),
            (['org11'], {'org11': [u'władcażlebów.pl']}))

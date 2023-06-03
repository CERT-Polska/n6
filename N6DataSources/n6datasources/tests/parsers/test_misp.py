# Copyright (c) 2016-2023 NASK. All rights reserved.

import datetime
import fnmatch
import unittest

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.misp import (
    MispParser,
    TLP_RESTRICTION,
)


class MispParserTestMixIn(ParserTestMixin):
    def test_basics(self):
        self.assertIn(self.PARSER_BASE_CLASS, self.PARSER_CLASS.__bases__)
        default_binding_key = '.'.join(self.PARSER_CLASS.default_binding_key.
                                                   split(".")[:2])
        regex_default_binding_key = fnmatch.translate(default_binding_key)
        self.assertRegex(self.PARSER_SOURCE, regex_default_binding_key)
        self.assertEqual(self.PARSER_CLASS.constant_items,
                         self.PARSER_CONSTANT_ITEMS)


@expand
class TestMispParser(MispParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'testsource.misp'
    PARSER_CLASS = MispParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'confidence': 'medium',
    }

    @paramseq
    def _tag_tlp_with_min_tlp_and_expected_restriction():
        yield param('white', 'white', 'public')
        yield param('white', 'green', 'need-to-know')
        yield param('white', 'amber', 'internal')
        yield param('white', 'red', 'internal')
        yield param('green', 'white', 'need-to-know')
        yield param('green', 'green', 'need-to-know')
        yield param('green', 'amber', 'internal')
        yield param('green', 'red', 'internal')
        yield param('amber', 'white', 'internal')
        yield param('amber', 'green', 'internal')
        yield param('amber', 'amber', 'internal')
        yield param('amber', 'red', 'internal')
        yield param('red', 'white', 'internal')
        yield param('red', 'green', 'internal')
        yield param('red', 'amber', 'internal')
        yield param('red', 'red', 'internal')

    @paramseq
    def _min_tlp_and_expected_restriction():
        yield param('white', 'need-to-know')
        yield param('green', 'need-to-know')
        yield param('amber', 'internal')
        yield param('red', 'internal')

    def setUp(self):
        self.parser = MispParser.__new__(MispParser)

    def cases(self):
        yield (
            '[{"Event": {\n'
            '"info": "testname", "orgc_id": "2", "id": "1", "threat_level_id": "3",\n'
            '"uuid": "111111aa-1111-111a-a11a-11111a1aa111",\n'
            '"Attribute": [\n'
            # Network activity, 'hostname'
            '{"category": "Network activity", "type": "hostname", "comment": "SomeComment.", '
            '"event_id": "1", "timestamp": "1456387743", "value": "example1.test1.info", '
            '"id": "1", "uuid" : "555555ee-5555-555e-e55e-55555e5ee555"},\n'
            # Network activity, 'hostname'
            '{"category": "Network activity", "type": "hostname", "comment": "Port 616", '
            '"event_id": "1", "timestamp": "1456387744", "value": "example1.test2.info",  '
            '"id": "1", "uuid": "666666ff-6666-666f-f66f-66666f6ff666"},\n'
            # Network activity, 'hostname', no value, dport in 'comment'
            '{"category": "Network activity", "type": "hostname", "comment": "On port 612", '
            '"event_id": "1", "timestamp": "1456387745", "value": "",  "id": "1",'
            '"uuid": "88888888-8888-8888-8888-888888888888"},\n'
            # Network activity, 'hostname', event skipped
            '{"category": "Network activity", "type": "hostname", "comment": "", '
            '"event_id": "1", "timestamp": "1456387745", "value": "",  "id": "1", '
            '"uuid": "444444dd-4444-444d-d44d-44444d4dd444"},\n'
            # Payload delivery, 'ip-src'
            '{"category": "Payload delivery", "type": "ip-src", "comment": "On port 617", '
            '"event_id": "1", "timestamp": "1456387747", "value": "1.1.1.1",  "id": "1", '
            '"uuid": "99999999-9999-9999-9999-999999999999"},\n'
            # Payload delivery, 'hostname'
            '{"category" : "Payload delivery",\n'
            '"comment" : "This attribute has been automatically imported",\n'
            '"uuid" : "666666ff-6666-666f-f66f-66666f6ff666",\n'
            '"event_id" : "1",\n'
            '"timestamp" : "1482134474",\n'
            '"value" : "www.example-foo-bar.com",\n'
            '"type" : "hostname",\n'
            '"id": "1"\n'
            '},\n'
            # Payload delivery, 'hostname'
            '{\n'
            '"category" : "Payload delivery",\n'
            '"comment" : "This attribute has been automatically imported",\n'
            '"uuid" : "88888888-8888-8888-8888-888888888888",\n'
            '"event_id" : "1",\n'
            '"timestamp" : "1482134475",\n'
            '"value" : "see.example-spam-ham.org",\n'
            '"type" : "hostname",\n'
            '"id": "1"\n'
            '},\n'
            # Network activity, 'ip-dst'
            # + "to_ids": true - category should be 'cnc'
            '{'
            '"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid": "555555ee-5555-555e-e55e-55555e5ee555", '
            '"event_id" : "1", "timestamp" : "1482134476", "to_ids": true, '
            '"value" : "1.1.1.1", "type" : "ip-dst", "id": "1"},\n'
            # Network activity, 'ip-dst'
            # + "to_ids": false - category should be 'other'
            '{'
            '"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid": "555555ee-5555-555e-e55e-55555e5ee555", '
            '"event_id" : "1", "timestamp" : "1482134476", "to_ids": false, '
            '"value" : "1.1.1.1", "type" : "ip-dst", "id": "1"},\n'
            # Network activity, 'ip-dst', with dport from 'comment'
            '{'
            '"category" : "Network activity", "comment" : "port number: 333", "uuid": '
            '"555555ee-5555-555e-e55e-55555e5ee555", "event_id" : "1", "timestamp": '
            '"1482134476", "value" : "2.2.2.2",'
            '"type" : "ip-dst", "id": "1"},\n'
            # Network activity, 'ip-src'
            '{'
            '"category" : "Network activity", "uuid" : '
            '"555555ee-5555-555e-e55e-55555e5ee555", "event_id" : "1", "timestamp" : '
            '"1482134476", "value" : "3.3.3.3",'
            '"type" : "ip-src", "id": "1"},\n'
            # Network activity, 'email-src'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "555555ee-5555-555e-e55e-55555e5ee555",'
            '"event_id" : "1", "timestamp" : "1482134476", "value" : "test@example.com",'
            '"type" : "email-src", "id": "1"},\n'
            # Network activity, 'email-dst'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "555555ee-5555-555e-e55e-55555e5ee555",'
            '"event_id" : "1", "timestamp" : "1482134476", "value" : "destination@example.com",'
            '"type" : "email-dst", "id": "1"},\n'
            # Payload delivery, 'url'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "444444dd-4444-444d-d44d-44444d4dd444", "event_id":'
            ' "1", "timestamp" : "1482134477", "value" : "http://www.example-foo-bar.'
            'com/stay.php", "type" : "url", "id": "1"},\n'
            # Payload delivery, 'ip-dst'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "77777777-7777-7777-7777-777777777777",'
            '"event_id" : "1", "timestamp" : "1482134479", "value" : "1.2.3.4",'
            '"type" : "ip-dst", "id": "1"},\n'
            # Payload delivery, 'domain'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "666666ff-6666-666f-f66f-66666f6ff666",'
            '"event_id" : "1", "timestamp" : "1482134474", "value" : "example.com",'
            '"type" : "domain", "id": "1"},\n'
            # Network activity, 'url'
            # "to_ids": true - category should be 'cnc'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "444444dd-4444-444d-d44d-44444d4dd444", "event_id":'
            ' "1", "timestamp" : "1482134477", "to_ids": true, '
            '"value" : "http://malware.example.com/test", "type" : "url", "id": "1"},\n'
            ## Network activity, 'url'
            # "to_ids": false - category should be 'other'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "444444dd-4444-444d-d44d-44444d4dd444", "event_id":'
            ' "1", "timestamp" : "1482134477", "to_ids": false, '
            '"value" : "http://malware.example.com/test", "type" : "url", "id": "1"},\n'
            # Network activity, 'domain|ip'
            ' {"category": "Network activity", "comment": "Jaff C2", "uuid": "333333cc-3333-333c-'
            'c33c-33333c3cc333", "event_id": "1", "timestamp": "1496390810", "to_ids": true, '
            '"deleted": "False", "value": "exampledomain.net|1.2.3.4", "sharing_group_id": '
            '"0", "ShadowAttribute": [], "disable_correlation": "False",' 
            '"distribution": "5", "type": "domain|ip", "id": "1"},\n'
            # Network activity, 'domain|ip', only FQDN in the "value" field
            '{"category": "Network activity", "comment": "Binary Server hosting ...",'
            ' "uuid": "222222bb-2222-222b-b22b-22222b2bb222", "event_id": "1", "timestamp": '
            '"1496390796", "to_ids": false, "deleted": "False", "value": "anotherexample.com", '
            '"sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation": "False", '
            '"distribution": "5", "type": "domain|ip", "id": "1"}\n'
            ']\n'
            '}\n'
            '}]'.encode('ascii'),
            [
                dict(
                    name='testname',
                    category='other',
                    fqdn='example1.test1.info',
                    time="2016-02-25 08:09:03",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='other',
                    fqdn='example1.test2.info',
                    time="2016-02-25 08:09:04",
                    restriction='need-to-know',
                    dport=616,
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='666666ff-6666-666f-f66f-66666f6ff666',
                ),
                dict(
                    name='testname',
                    category='other',
                    time="2016-02-25 08:09:05",
                    restriction='need-to-know',
                    dport=612,
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='88888888-8888-8888-8888-888888888888',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-02-25 08:09:07",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='99999999-9999-9999-9999-999999999999',
                    address=[{'ip': '1.1.1.1'}]
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:14",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='666666ff-6666-666f-f66f-66666f6ff666',
                    fqdn='www.example-foo-bar.com',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:15",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='88888888-8888-8888-8888-888888888888',
                    fqdn='see.example-spam-ham.org',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    address=[{'ip': '1.1.1.1'}],
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='other',
                    address=[{'ip': '1.1.1.1'}],
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='other',
                    address=[{'ip': '2.2.2.2'}],
                    dport=333,
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='bots',
                    address=[{'ip': '3.3.3.3'}],
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='other',
                    email='test@example.com',
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='other',
                    email='destination@example.com',
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='555555ee-5555-555e-e55e-55555e5ee555',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    url="http://www.example-foo-bar.com/stay.php",
                    time="2016-12-19 08:01:17",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='444444dd-4444-444d-d44d-44444d4dd444',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:19",
                    address=[{'ip': '1.2.3.4'}],
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='77777777-7777-7777-7777-777777777777',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:14",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='666666ff-6666-666f-f66f-66666f6ff666',
                    fqdn='example.com',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    url="http://malware.example.com/test",
                    time="2016-12-19 08:01:17",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='444444dd-4444-444d-d44d-44444d4dd444',
                ),
                dict(
                    name='testname',
                    category='other',
                    url="http://malware.example.com/test",
                    time="2016-12-19 08:01:17",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='444444dd-4444-444d-d44d-44444d4dd444',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    fqdn="exampledomain.net",
                    address=[{'ip': '1.2.3.4'}],
                    time="2017-06-02 08:06:50",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='333333cc-3333-333c-c33c-33333c3cc333',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    fqdn="anotherexample.com",
                    time="2017-06-02 08:06:36",
                    restriction='need-to-know',
                    misp_event_uuid='111111aa-1111-111a-a11a-11111a1aa111',
                    misp_attr_uuid='222222bb-2222-222b-b22b-22222b2bb222',
                ),
            ]
        )

    def test_get_event_with_ok_data(self):
        misp_category = 'Network activity'
        misp_attribute = {
            u'category': u'Network activity',
            u'comment': u'C2',
            u'uuid': u'111111aa-1111-111a-a11a-11111a1aa111',
            u'event_id': u'1',
            u'timestamp': u'1456824276',
            u'to_ids': True,
            u'value': u'1.1.1.1',
            u'sharing_group_id': u'0',
            u'ShadowAttribute': [],
            u'SharingGroup': [],
            u'distribution': u'5',
            u'type': u'ip-dst',
            u'id': u'11'}
        mistp_event_type = 'ip-dst'
        expect = {
            'address': [{'ip': u'1.1.1.1'}],
            'category': 'cnc',
            'time': datetime.datetime(2016, 3, 1, 9, 24, 36)}
        result = self.parser.get_event(misp_attribute, misp_category, mistp_event_type)
        self.assertEqual(expect, result)

    def test_get_event_with_empty_data(self):
        mistp_event_type = 'ip-dst'
        misp_category = 'Network activity'
        misp_attribute = {
            u'category': u'Network activity',
            u'comment': u'C2',
            u'uuid': u'111111aa-1111-111a-a11a-11111a1aa111',
            u'event_id': u'1',
            u'timestamp': u'1456824276',
            u'to_ids': True,
            u'value': u'',
            u'sharing_group_id': u'0',
            u'ShadowAttribute': [],
            u'SharingGroup': [],
            u'distribution': u'5',
            u'type': u'ip-dst',
            u'id': u'11'}
        expect = None
        result = self.parser.get_event(misp_attribute, misp_category, mistp_event_type)
        self.assertEqual(expect, result)

    def test_get_dport_pattern(self):
        commnet = 'C&C IRC server, port 8443'
        expect = {'dport': '8443'}
        result_dict = {}
        self.parser.get_dport(commnet, result_dict)
        self.assertEqual(result_dict, expect)

    def test_get_dport_pattern_with_two_ports_get_first(self):
        commnet = 'port TCP/80 and port TCP/81'
        expect = {'dport': '80'}
        result_dict = {}
        self.parser.get_dport(commnet, result_dict)
        self.assertEqual(result_dict, expect)

    def test_get_dport_pattern_without_port(self):
        commnet = 'On port'
        expect = {}
        result_dict = {}
        self.parser.get_dport(commnet, result_dict)
        self.assertEqual(result_dict, expect)

    def test_get_dport_pattern_without_port_import_version(self):
        commnet = 'On import 555'
        expect = {}
        result_dict = {}
        self.parser.get_dport(commnet, result_dict)
        self.assertEqual(result_dict, expect)

    def test_get_restriction_with_one_dict_in_tag_ok_data(self):
        mist_event = {"Tag": [{u'colour': u'#ffa800', u'exportable': True, u'id': u'2', u'name': u'tlp:amber'}]}
        expect = 'internal'
        result = self.parser.get_restriction(mist_event, None)
        self.assertEqual(expect, result)

    def test_get_restriction_with_two_dicts_in_tag_ok_data(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'},
                {u'colour': u'#ffffff', u'exportable': True, u'id': u'3', u'name': u'tlp:white'}
            ]
        }
        expect = 'public'
        result = self.parser.get_restriction(mist_event, None)
        self.assertEqual(expect, result)

    def test_get_restriction_with_two_dicts_in_tag_ok_data_reverse_version(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#ffffff', u'exportable': True, u'id': u'3', u'name': u'tlp:red'},
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'}
            ]
        }
        expect = 'internal'
        result = self.parser.get_restriction(mist_event, None)
        self.assertEqual(expect, result)

    def test_get_restriction_without_tag(self):
        mist_event = {}
        expect = 'need-to-know'
        result = self.parser.get_restriction(mist_event, None)
        self.assertEqual(expect, result)

    def test_get_restriction_with_tag_without_tlp(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'}
            ]
        }
        expect = 'need-to-know'
        result = self.parser.get_restriction(mist_event, None)
        self.assertEqual(expect, result)

    # test getting of the restriction with minimal TLP value provided
    @foreach(_tag_tlp_with_min_tlp_and_expected_restriction)
    def test_get_restriction_with_tag_and_min_tlp(self, tag_tlp, min_tlp, expected_restriction):
        misp_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'},
                {u'colour': u'#ffffff', u'exportable': True, u'id': u'3',
                 u'name': u'tlp:{}'.format(tag_tlp)}
            ]
        }
        min_restriction = TLP_RESTRICTION[min_tlp]
        result = self.parser.get_restriction(misp_event, min_restriction)
        self.assertEqual(expected_restriction, result)

    @foreach(_min_tlp_and_expected_restriction)
    def test_get_restriction_without_tag_with_min_tlp(self, min_tlp, expected_restriction):
        misp_event = {}
        min_restriction = TLP_RESTRICTION[min_tlp]
        result = self.parser.get_restriction(misp_event, min_restriction)
        self.assertEqual(expected_restriction, result)

    @foreach(_min_tlp_and_expected_restriction)
    def test_get_restriction_with_tag_without_tlp_with_min_tlp(self, min_tlp,
                                                               expected_restriction):
        misp_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'}
            ]
        }
        min_restriction = TLP_RESTRICTION[min_tlp]
        result = self.parser.get_restriction(misp_event, min_restriction)
        self.assertEqual(expected_restriction, result)

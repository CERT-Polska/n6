# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import fnmatch
import unittest

from n6.parsers.generic import (
    BaseParser,
)
from n6.tests.parsers._parser_test_mixin import ParserTestMixIn
from n6.parsers.misp import (
    MispParser,
    TLP_RESTRICTION,
)

from unittest_expander import expand, foreach, param, paramseq


class MispParserTestMixIn(ParserTestMixIn):
    def test_basics(self):
        self.assertIn(self.PARSER_BASE_CLASS, self.PARSER_CLASS.__bases__)
        default_binding_key = '.'.join(self.PARSER_CLASS.default_binding_key.
                                                   split(".")[:2])
        regex_default_binding_key = fnmatch.translate(default_binding_key)
        self.assertRegexpMatches(self.PARSER_SOURCE, regex_default_binding_key)
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
        yield param('green', 'white', 'need-to-know')
        yield param('green', 'green', 'need-to-know')
        yield param('green', 'red', 'internal')
        yield param('amber', 'white', 'internal')
        yield param('amber', 'green', 'internal')
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
            '"info": "testname", "orgc_id": "2", "id": "4368", "threat_level_id": "3",\n'
            '"uuid": "585793ca-6840-484c-b78f-6272a5fe7088",\n'
            '"Attribute": [\n'
            # Network activity, 'hostname'
            '{"category": "Network activity", "type": "hostname", "comment": "Impvia.", '
            '"event_id": "6666", "timestamp": "1456387743", "value": "svra01.test1.info", '
            '"id": "315474", "uuid" : "585793cc-3964-44d5-9d71-6272a5fe7088"},\n'
            # Network activity, 'hostname'
            '{"category": "Network activity", "type": "hostname", "comment": "Port 616", '
            '"event_id": "7777", "timestamp": "1456387744", "value": "svra01.test2.info",  '
            '"id": "315475", "uuid": "585793ca-6960-49b8-af1f-6272a5fe7088"},\n'
            # Network activity, 'hostname', no value, dport in 'comment'
            '{"category": "Network activity", "type": "hostname", "comment": "On port 612", '
            '"event_id": "888", "timestamp": "1456387745", "value": "",  "id": "315476",'
            '"uuid": "585793cb-ec30-4ee3-b4b4-6272a5fe7088"},\n'
            # Network activity, 'hostname', event skipped
            '{"category": "Network activity", "type": "hostname", "comment": "", '
            '"event_id": "888", "timestamp": "1456387745", "value": "",  "id": "315476", '
            '"uuid": "585793cd-4e5c-41d0-b874-6272a5fe7088"},\n'
            # Payload delivery, 'ip-src'
            '{"category": "Payload delivery", "type": "ip-src", "comment": "On port 617", '
            '"event_id": "888", "timestamp": "1456387747", "value": "1.1.1.1",  "id": "315476", '
            '"uuid": "585793ce-db10-4cc1-a912-6272a5fe7088"},\n'
            # Payload delivery, 'hostname'
            '{"category" : "Payload delivery",\n'
            '"comment" : "This attribute has been automatically imported",\n'
            '"uuid" : "585793ca-6960-49b8-af1f-6272a5fe7088",\n'
            '"event_id" : "4948",\n'
            '"timestamp" : "1482134474",\n'
            '"value" : "www.example-foo-bar.com",\n'
            '"type" : "hostname",\n'
            '"id" : "452050"\n'
            '},\n'
            # Payload delivery, 'hostname'
            '{\n'
            '"category" : "Payload delivery",\n'
            '"comment" : "This attribute has been automatically imported",\n'
            '"uuid" : "585793cb-ec30-4ee3-b4b4-6272a5fe7088",\n'
            '"event_id" : "4948",\n'
            '"timestamp" : "1482134475",\n'
            '"value" : "see.example-spam-ham.org",\n'
            '"type" : "hostname",\n'
            '"id" : "452051"\n'
            '},\n'
            # Network activity, 'ip-dst'
            '{'
            '"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid": "585793cc-3964-44d5-9d71-6272a5fe7088", '
            '"event_id" : "4948", "timestamp" : "1482134476", "value" : "192.0.2.232",'
            '"type" : "ip-dst", "id" : "452052"},\n'
            # Network activity, 'ip-dst', with dport from 'comment'
            '{'
            '"category" : "Network activity", "comment" : "port number: 333", "uuid": '
            '"585793cc-3964-44d5-9d71-6272a5fe7088", "event_id" : "4948", "timestamp": '
            '"1482134476", "value" : "192.0.2.233",'
            '"type" : "ip-dst", "id" : "452052"},\n'
            # Network activity, 'ip-src'
            '{'
            '"category" : "Network activity", "uuid" : '
            '"585793cc-3964-44d5-9d71-6272a5fe7088", "event_id" : "4948", "timestamp" : '
            '"1482134476", "value" : "192.0.2.235",'
            '"type" : "ip-src", "id" : "452052"},\n'
            # Network activity, 'email-src'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793cc-3964-44d5-9d71-6272a5fe7088",'
            '"event_id" : "4948", "timestamp" : "1482134476", "value" : "test@example.com",'
            '"type" : "email-src", "id" : "452052"},\n'
            # Network activity, 'email-dst'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793cc-3964-44d5-9d71-6272a5fe7088",'
            '"event_id" : "4948", "timestamp" : "1482134476", "value" : "destination@example.com",'
            '"type" : "email-dst", "id" : "452052"},\n'
            # Payload delivery, 'url'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793cd-4e5c-41d0-b874-6272a5fe7088", "event_id":'
            ' "4948", "timestamp" : "1482134477", "value" : "http://www.example-foo-bar.'
            'com/stay.php", "type" : "url", "id" : "452053"},\n'
            # Payload delivery, 'ip-dst'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793cf-61c4-4d08-8474-6272a5fe7088",'
            '"event_id" : "4948", "timestamp" : "1482134479", "value" : "1.2.3.4",'
            '"type" : "ip-dst", "id" : "452055"},\n'
            # Payload delivery, 'domain'
            '{"category" : "Payload delivery", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793ca-6960-49b8-af1f-6272a5fe7088",'
            '"event_id" : "4948", "timestamp" : "1482134474", "value" : "example.com",'
            '"type" : "domain", "id" : "452050"},\n'
            # Network activity, 'url'
            '{"category" : "Network activity", "comment" : "This attribute has been '
            'automatically imported", "uuid" : "585793cd-4e5c-41d0-b874-6272a5fe7088", "event_id":'
            ' "4948", "timestamp" : "1482134477", "value" : "http://malware.example.com/test",'
            '"type" : "url", "id" : "452053"},\n'
            # Network activity, 'domain|ip'
            ' {"category": "Network activity", "comment": "Jaff C2", "uuid": "59311c9a-2678-4a17-9'
            'b4a-610bc0a8a8de", "event_id": "1788", "timestamp": "1496390810", "to_ids": "True", '
            '"deleted": "False", "value": "exampledomain.net|1.2.3.4", "sharing_group_id": '
            '"0", "ShadowAttribute": [], "disable_correlation": "False",' 
            '"distribution": "5", "type": "domain|ip", "id": "33260"},\n'
            # Network activity, 'domain|ip', only FQDN in the "value" field
            '{"category": "Network activity", "comment": "Binary Server hosting ...",'
            ' "uuid": "59311c8c-ac5c-4215-9483-3643c0a8a8de", "event_id": "1788", "timestamp": '
            '"1496390796", "to_ids": "True", "deleted": "False", "value": "anotherexample.com", '
            '"sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation": "False", '
            '"distribution": "5", "type": "domain|ip", "id": "33259"}\n'
            ']\n'
            '}\n'
            '}]',
            [
                dict(
                    name='testname',
                    category='cnc',
                    fqdn='svra01.test1.info',
                    time="2016-02-25 08:09:03",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    fqdn='svra01.test2.info',
                    time="2016-02-25 08:09:04",
                    restriction='need-to-know',
                    dport=616,
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793ca-6960-49b8-af1f-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    time="2016-02-25 08:09:05",
                    restriction='need-to-know',
                    dport=612,
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cb-ec30-4ee3-b4b4-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-02-25 08:09:07",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793ce-db10-4cc1-a912-6272a5fe7088',
                    address=[{'ip': '1.1.1.1'}]
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:14",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793ca-6960-49b8-af1f-6272a5fe7088',
                    fqdn='www.example-foo-bar.com',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:15",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cb-ec30-4ee3-b4b4-6272a5fe7088',
                    fqdn='see.example-spam-ham.org',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    address=[{'ip': '192.0.2.232'}],
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    address=[{'ip': '192.0.2.233'}],
                    dport=333,
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='bots',
                    address=[{'ip': '192.0.2.235'}],
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    email='test@example.com',
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    email='destination@example.com',
                    time="2016-12-19 08:01:16",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cc-3964-44d5-9d71-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    url="http://www.example-foo-bar.com/stay.php",
                    time="2016-12-19 08:01:17",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cd-4e5c-41d0-b874-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:19",
                    address=[{'ip': '1.2.3.4'}],
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cf-61c4-4d08-8474-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    time="2016-12-19 08:01:14",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793ca-6960-49b8-af1f-6272a5fe7088',
                    fqdn='example.com',
                ),
                dict(
                    name='testname',
                    category='cnc',
                    url="http://malware.example.com/test",
                    time="2016-12-19 08:01:17",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='585793cd-4e5c-41d0-b874-6272a5fe7088',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    fqdn="exampledomain.net",
                    address=[{'ip': '1.2.3.4'}],
                    time="2017-06-02 08:06:50",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='59311c9a-2678-4a17-9b4a-610bc0a8a8de',
                ),
                dict(
                    name='testname',
                    category='malurl',
                    fqdn="anotherexample.com",
                    time="2017-06-02 08:06:36",
                    restriction='need-to-know',
                    misp_event_uuid='585793ca-6840-484c-b78f-6272a5fe7088',
                    misp_attr_uuid='59311c8c-ac5c-4215-9483-3643c0a8a8de',
                ),
            ]
        )

    def test_get_event_with_ok_data(self):
        misp_category = 'Network activity'
        misp_attribute = {
            u'category': u'Network activity',
            u'comment': u'C2',
            u'uuid': u'56d55fd4-0d48-4ea4-9657-0b7f950d210f',
            u'event_id': u'4378',
            u'timestamp': u'1456824276',
            u'to_ids': True,
            u'value': u'46.166.165.254',
            u'sharing_group_id': u'0',
            u'ShadowAttribute': [],
            u'SharingGroup': [],
            u'distribution': u'5',
            u'type': u'ip-dst',
            u'id': u'318747'}
        mistp_event_type = 'ip-dst'
        expect = {
            'address': [{'ip': u'46.166.165.254'}],
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
            u'uuid': u'56d55fd4-0d48-4ea4-9657-0b7f950d210f',
            u'event_id': u'4378',
            u'timestamp': u'1456824276',
            u'to_ids': True,
            u'value': u'',
            u'sharing_group_id': u'0',
            u'ShadowAttribute': [],
            u'SharingGroup': [],
            u'distribution': u'5',
            u'type': u'ip-dst',
            u'id': u'318747'}
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

    def test_get_tlp_with_one_dict_in_tag_ok_data(self):
        mist_event = {"Tag": [{u'colour': u'#ffa800', u'exportable': True, u'id': u'2', u'name': u'tlp:amber'}]}
        expect = 'internal'
        result = self.parser.get_restriction(mist_event)
        self.assertEqual(expect, result)

    def test_get_tlp_with_two_dict_in_tag_ok_data(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'},
                {u'colour': u'#ffffff', u'exportable': True, u'id': u'3', u'name': u'tlp:white'}
            ]
        }
        expect = 'public'
        result = self.parser.get_restriction(mist_event)
        self.assertEqual(expect, result)

    def test_get_tlp_with_two_dict_in_tag_ok_data_reverse_version(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#ffffff', u'exportable': True, u'id': u'3', u'name': u'tlp:red'},
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'}
            ]
        }
        expect = 'internal'
        result = self.parser.get_restriction(mist_event)
        self.assertEqual(expect, result)

    def test_get_tlp_without_tag(self):
        mist_event = {}
        expect = 'need-to-know'
        result = self.parser.get_restriction(mist_event)
        self.assertEqual(expect, result)

    def test_get_tlp_with_tag_without_tlp(self):
        mist_event = {
            "Tag": [
                {u'colour': u'#1eed40', u'exportable': True, u'id': u'1', u'name': u'Type:OSINT'}
            ]
        }
        expect = 'need-to-know'
        result = self.parser.get_restriction(mist_event)
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

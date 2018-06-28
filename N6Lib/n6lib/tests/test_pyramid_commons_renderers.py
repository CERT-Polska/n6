# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import unittest

from mock import sentinel as sen

from n6lib.pyramid_commons.renderers import StreamRenderer_csv


class TestStreamRenderer_csv(unittest.TestCase):

    def test_supports_nonascii_unicode_strings(self):
        def data_generator_factory():
            yield {
                'id': 32 * '0',
                'rid': 32 * '1',
                'source': 'foo.bar',
                'restriction': 'public',
                'confidence': 'low',
                'category': 'cnc',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'ip': '127.0.0.1',
                'name': 'Żółć\nłódź',
                'sport': 22,
                'target': u'KÓŁKO',
            }
            yield {
                'id': 32 * u'2',
                'rid': 32 * u'3',
                'source': u'ham.spam',
                'restriction': u'need-to-know',
                'confidence': u'high',
                'category': u'spam',
                'time': datetime.datetime(2015, 2, 16, 23, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'name': u'łódź\r\nżółć',
                'url': u'http://jaźń.example/',
                'sport': 22222,
            }
        renderer = StreamRenderer_csv(data_generator_factory(), sen.request)
        results = ''.join(renderer.generate_content())
        self.assertIsInstance(results, str)
        self.assertEqual(results, (
            '"time","id","source","category",'
            '"name","md5","ip","url","fqdn","asn","cc","details"'
            '\r\n'
            '"2015-02-15T16:20:34Z","' + 32 * '0' + '","foo.bar","cnc",'
            '"Żółć\\nłódź","","127.0.0.1","","","","","from port 22 target KÓŁKO"'
            '\r\n'
            '"2015-02-16T23:20:34Z","' + 32 * '2' + '","ham.spam","spam",'
            '"łódź\\r\\nżółć","","255.255.255.0","http://jaźń.example/","","","","from port 22222"'
            '\r\n\n'))


### TODO: more tests...

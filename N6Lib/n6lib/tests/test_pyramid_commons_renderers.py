# Copyright (c) 2013-2021 NASK. All rights reserved.

import datetime
import unittest
from unittest.mock import (
    sentinel as sen,
    Mock
)

from n6lib.pyramid_commons.renderers import (
    StreamRenderer_csv,
    SnortDNSRenderer,
    SuricataDNSRenderer,
    SnortHTTPRenderer,
    SuricataHTTPRenderer,
    SnortIPRenderer,
    SuricataIPRenderer,
    SnortIPBlacklistRenderer,
    SuricatatIPBlacklistRenderer
)


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
                'ip': '192.168.1.15',
                'name': 'Żółć\nłódź',
                'sport': 22,
                'target': u'KÓŁKO',
                'proto': 'tcp',
                'dip': '192.168.1.12',
                'dport': 55
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
                'proto': 'tcp',
                'dip': '192.168.1.12',
            }
            yield {
                'id': 32 * '0',
                'rid': 32 * '1',
                'source': 'foo.bar',
                'restriction': 'public',
                'confidence': 'low',
                'category': 'cnc',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'ip': '192.168.1.15',
                'name': 'Żółć\nłódź',
                'sport': 22,
                'target': u'KÓŁKO',
                'proto': 'tcp',
                'dport': 55
            }

        renderer = StreamRenderer_csv(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, (
                u'"time","id","source","category",'
                u'"name","md5","ip","url","fqdn","asn","cc","details"'
                u'\r\n'
                u'"2015-02-15T16:20:34Z","00000000000000000000000000000000","foo.bar","cnc","Żółć\\nłódź","",'
                u'"192.168.1.15","","","","","tcp from port 22 to 192.168.1.12:55 target KÓŁKO"'
                u'\r\n'
                u'"2015-02-16T23:20:34Z","22222222222222222222222222222222","ham.spam","spam","łódź\\r\\nżółć",'
                u'"","255.255.255.0","http://jaźń.example/","","","","tcp from port 22222 to 192.168.1.12"'
                u'\r\n'
                u'"2015-02-15T16:20:34Z","00000000000000000000000000000000","foo.bar","cnc","Żółć\\nłódź","",'
                u'"192.168.1.15","","","","","tcp from port 22 to port 55 target KÓŁKO"'
                u'\r\n\n'.encode('utf-8')))


class TestSnortDNSRenderer(unittest.TestCase):

    def test_snort_dns_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b5',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
            }

        renderer = SnortDNSRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert udp $HOME_NET any -> $DNS_SERVERS 53 (msg:"n6 tor nask www.nask.pl"; '
                         b'content:"|01 00 00 01 00 00 00 00 00 00|"; offset:2; depth:10; '
                         b'content:"|03|www|04|nask|02|pl|00|"; nocase; fast_pattern:only; '
                         b'classtype:bad-unknown; sid:3149742773; gid:6000001; rev:1; '
                         b'metadata:n6id b52c96bea30646abf8170f333bbd42b5;)\n\n')

    def test_snort_dns_renderer_no_fqdn(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
            }

        renderer = SnortDNSRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, b'\n')


class TestSuricataDNSRenderer(unittest.TestCase):

    def test_suricata_dns_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b7',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
            }

        renderer = SuricataDNSRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert dns $HOME_NET any -> $DNS_SERVERS 53 (msg:"n6 tor nask www.nask.pl"; '
                         b'content:"|03|www|04|nask|02|pl|00|"; nocase; fast_pattern:only; '
                         b'classtype:bad-unknown; sid:3149742775; gid:6000001; rev:1; '
                         b'metadata:n6id b52c96bea30646abf8170f333bbd42b7;)\n\n')


class TestSnortHTTPRenderer(unittest.TestCase):

    def test_snort_http_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl:8080/path?search#20'
            }

        renderer = SnortHTTPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert tcp $HOME_NET any -> any $HTTP_PORTS (msg:"n6 tor nask '
                         b'http://www.nask.pl:8080/path?search#20"; flow:to_server,established; '
                         b'content:"/path?search#20"; http_uri; nocase; content:"Host|3A| www.nask.pl"; '
                         b'nocase; fast_pattern:only; http_header; classtype:bad-unknown; sid:3149742777; '
                         b'gid:6000002; rev:1; metadata:n6id b52c96bea30646abf8170f333bbd42b9;)\n\n')

    def test_snort_http_renderer_no_url(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
            }

        renderer = SnortHTTPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, b'\n')


class TestSuricataHTTPRenderer(unittest.TestCase):

    def test_suricata_http_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl:8080/path?search#0'
            }

        renderer = SuricataHTTPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert http $HOME_NET any -> any $HTTP_PORTS '
                         b'(msg:"n6 tor nask http://www.nask.pl:8080/path?search#0"; flow:to_server,established; '
                         b'content:"/path?search#0"; http_uri; nocase; content:"Host|3A| www.nask.pl"; nocase; '
                         b'fast_pattern:only; http_header; classtype:bad-unknown; sid:3149742777; gid:6000002; '
                         b'rev:1; metadata:n6id b52c96bea30646abf8170f333bbd42b9;)\n\n')


class TestSnortIPRenderer(unittest.TestCase):

    def test_snort_ip_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl/path?search#00'
            }

        renderer = SnortIPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert ip $HOME_NET any -> 255.255.255.0 any (msg:"n6 tor nask 255.255.255.0";'
                         b' classtype:bad-unknown; sid:3149742777; gid:6000003; '
                         b'rev:1; metadata:n6id b52c96bea30646abf8170f333bbd42b9;)\n\n')

    def test_snort_ip_renderer_no_address(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'url': 'http://www.nask.pl/path?search#01'
            }

        renderer = SnortIPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, b'\n')


class TestSuricataIPRenderer(unittest.TestCase):

    def test_suricata_ip_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl/path?search#1'
            }

        renderer = SuricataIPRenderer(data_generator_factory(), sen.request)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b'alert ip $HOME_NET any -> 255.255.255.0 any (msg:"n6 tor nask 255.255.255.0"; '
                         b'classtype:bad-unknown; sid:3149742777; gid:6000003; rev:1; '
                         b'metadata:n6id b52c96bea30646abf8170f333bbd42b9;)\n\n')


class TesSnorttIPBlacklistRenderer(unittest.TestCase):

    def test_snort_ip_blacklist_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl/path?search#2'
            }

        mock = Mock(params={'category': ['tor']})
        renderer = SnortIPBlacklistRenderer(data_generator_factory(), mock)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b"# ['tor']\n255.255.255.0/32 #b52c96bea30646abf8170f333bbd42b9 nask\n\n")

    def test_snort_ip_blacklist_renderer_no_category(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl/path?search#3'
            }

        mock = Mock(params={'nocategory': ['tor']})
        renderer = SnortIPBlacklistRenderer(data_generator_factory(), mock)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, b"255.255.255.0/32 #b52c96bea30646abf8170f333bbd42b9 nask\n\n")

    def test_snort_ip_blacklist_renderer_no_address(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b9',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'url': 'http://www.nask.pl/path?search#4'
            }

        mock = Mock(params={'category': ['tor']})
        renderer = SnortIPBlacklistRenderer(data_generator_factory(), mock)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results, b"# ['tor']\n\n")


class TestSuricataIPBlacklistRenderer(unittest.TestCase):

    def test_suricata_ip_blacklist_renderer(self):
        def data_generator_factory():
            yield {
                'id': 'b52c96bea30646abf8170f333bbd42b8',
                'rid': 32 * '1',
                'category': 'tor',
                'name': 'nask',
                'fqdn': 'www.nask.pl',
                'source': 'source',
                'rectriction': 'public',
                'confidence': 'low',
                'time': datetime.datetime(2015, 2, 15, 16, 20, 34),
                'address': [{'ip': '255.255.255.0'}],
                'url': 'http://www.nask.pl/path?search#1'
            }

        mock = Mock(params={'category': ['tor']})
        renderer = SuricatatIPBlacklistRenderer(data_generator_factory(), mock)
        results = b''.join(renderer.generate_content())
        self.assertIsInstance(results, bytes)
        self.assertEqual(results,
                         b"# ['tor']\n"
                         b"255.255.255.0,8,14 #b52c96bea30646abf8170f333bbd42b8 nask\n\n")

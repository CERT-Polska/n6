# -*- coding: utf-8 -*-

# Copyright (c) 2019-2020 NASK. All rights reserved.

import unittest

from bson.json_util import loads
from mock import (
    ANY,
    Mock,
    call,
    patch,
    sentinel,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6.collectors.abuse_ch import (
    AbuseChRansomwareTrackerCollector,
    AbuseChFeodoTrackerCollector,
    AbuseChSSLBlacklistCollector,
    AbuseChUrlhausPayloadsUrlsCollector,
    AbuseChSSLBlacklistDyreCollector,
    NoNewDataException,
)
from n6.tests.collectors.test_generic import _BaseCollectorTestCase



class _TestAbuseChDownloadingTimeOrderedRowsCollectorBase(_BaseCollectorTestCase):

    COLLECTOR_CLASS = None

    def _perform_test(
            self,
            config_content,
            initial_state,
            orig_data,
            expected_publish_output_calls,
            expected_saved_state,
            label,              # arg (added by @foreach) irrelevant here
            context_targets):   # arg (added by @foreach) irrelevant here

        collector = self.prepare_collector(self.COLLECTOR_CLASS,
                                           config_content=config_content,
                                           initial_state=initial_state)

        def prepare_orig_data():
            return "".join(orig_data)

        collector.obtain_orig_data = prepare_orig_data
        collector.run_handling()
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)


@expand
class TestAbuseChRansomwareTrackerCollector(_TestAbuseChDownloadingTimeOrderedRowsCollectorBase):

    COLLECTOR_CLASS = AbuseChRansomwareTrackerCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [abusech_ransomware]
                source=abuse-ch
                cache_dir=~/.n6cache
                url=https://www.example.com
                download_retries=5
            ''',
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.ransomware',

                    # body
                    (
                        '"2018-08-09 03:00:00", "ZZ5", "XX5", "4.4.4.4", '
                            '"http://www.example_5.com", "offline", "", '
                            '"4.4.4.4", "55555", "YY5"\n'
                        '"2018-08-09 03:00:00", "ZZ4", "XX4", "3.3.3.3", '
                            '"http://www.example_4.com", "offline", "", '
                            '"3.3.3.3", "44444", "YY4"\n'
                        '"2018-08-09 02:00:00", "ZZ3", "XX3", "2.2.2.2", '
                            '"http://www.example_3.com", "offline", "", '
                            '"2.2.2.2", "33333", "YY3"'
                    ),

                    # prop_kwargs
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'text/csv',
                        'headers': {}
                    },
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2018-08-09 03:00:00',
                'newest_rows': {
                    '"2018-08-09 03:00:00", "ZZ4", "XX4", "3.3.3.3", '
                        '"http://www.example_4.com", "offline", "", '
                        '"3.3.3.3", "44444", "YY4"',
                    '"2018-08-09 03:00:00", "ZZ5", "XX5", "4.4.4.4", '
                        '"http://www.example_5.com", "offline", "", '
                        '"4.4.4.4", "55555", "YY5"'
                },
            },
        )

    @paramseq
    def initial_state_and_orig_data_variants():
        yield param(
            initial_state={
                'newest_row_time': '2018-08-09 01:00:00',
                'newest_rows': {
                    '"2018-08-09 01:00:00", "ZZ1", "XX1", "0.0.0.0", '
                    '"http://www.example_1.com", "offline", "", '
                    '"0.0.0.0", "11111", "YY1"',
                    '"2018-08-09 01:00:00", "ZZ2", "XX2", "1.1.1.1", '
                    '"http://www.example_2.com", "offline", "", '
                    '"1.1.1.1", "22222", "YY2"'
                },
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '"2018-08-09 03:00:00", "ZZ5", "XX5", "4.4.4.4", '
                '"http://www.example_5.com", "offline", "", '
                '"4.4.4.4", "55555", "YY5"\n'
                '"2018-08-09 03:00:00", "ZZ4", "XX4", "3.3.3.3", '
                '"http://www.example_4.com", "offline", "", '
                '"3.3.3.3", "44444", "YY4"\n'
                '"2018-08-09 02:00:00", "ZZ3", "XX3", "2.2.2.2", '
                '"http://www.example_3.com", "offline", "", '
                '"2.2.2.2", "33333", "YY3"\n'
                '"2018-08-09 01:00:00", "ZZ2", "XX2", "1.1.1.1", '
                '"http://www.example_2.com", "offline", "", '
                '"1.1.1.1", "22222", "YY2"\n'
                '"2018-08-09 01:00:00", "ZZ1", "XX1", "0.0.0.0", '
                '"http://www.example_1.com", "offline", "", '
                '"0.0.0.0", "11111", "YY1"\n',
                '"2018-08-09 00:00:00", "ZZ0", "XX0", "0.0.0.0", '
                '"http://www.example_1.com", "offline", "", '
                '"0.0.0.0", "00000", "YY0"',
            ),
        )

        yield param(
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '# row which should be ignored by collector\n'
                '"2018-08-09 03:00:00", "ZZ5", "XX5", "4.4.4.4", '
                '"http://www.example_5.com", "offline", "", '
                '"4.4.4.4", "55555", "YY5"\n'
                '"2018-08-09 03:00:00", "ZZ4", "XX4", "3.3.3.3", '
                '"http://www.example_4.com", "offline", "", '
                '"3.3.3.3", "44444", "YY4"\n'
                '"2018-08-09 02:00:00", "ZZ3", "XX3", "2.2.2.2", '
                '"http://www.example_3.com", "offline", "", '
                '"2.2.2.2", "33333", "YY3"\n'
            ),
        )

        yield param(
            initial_state={
                # legacy form of state
                'timestamp': '2018-08-09 02:00:00',
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '"2018-08-09 03:00:00", "ZZ5", "XX5", "4.4.4.4", '
                '"http://www.example_5.com", "offline", "", '
                '"4.4.4.4", "55555", "YY5"\n'
                '"2018-08-09 03:00:00", "ZZ4", "XX4", "3.3.3.3", '
                '"http://www.example_4.com", "offline", "", '
                '"3.3.3.3", "44444", "YY4"\n'
                '"2018-08-09 02:00:00", "ZZ3", "XX3", "2.2.2.2", '
                '"http://www.example_3.com", "offline", "", '
                '"2.2.2.2", "33333", "YY3"\n'
                '"2018-08-09 01:00:00", "ZZ2", "XX2", "1.1.1.1", '
                '"http://www.example_2.com", "offline", "", '
                '"1.1.1.1", "22222", "YY2"\n'
                '"2018-08-09 01:00:00", "ZZ1", "XX1", "0.0.0.0", '
                '"http://www.example_1.com", "offline", "", '
                '"0.0.0.0", "11111", "YY1"\n',
                '"2018-08-09 00:00:00", "ZZ0", "XX0", "0.0.0.0", '
                '"http://www.example_1.com", "offline", "", '
                '"0.0.0.0", "00000", "YY0"',
            ),
        )

    @foreach(cases)
    @foreach(initial_state_and_orig_data_variants)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChFeodoTrackerCollector(_TestAbuseChDownloadingTimeOrderedRowsCollectorBase):

    COLLECTOR_CLASS = AbuseChFeodoTrackerCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [abusech_feodotracker]
                source=abuse-ch
                cache_dir=~/.n6cache
                url=https://www.example.com
                download_retries=5
            ''',
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.201908',

                    # body
                    (
                        '2019-08-20 03:00:00,5.5.5.5,447,2019-08-20,ExampleName5\n'
                        '2019-08-20 03:00:00,4.4.4.4,447,2019-08-20,ExampleName4\n'
                        '2019-08-20 02:00:00,3.3.3.3,447,2019-08-20,ExampleName3'
                    ),

                    # prop_kwargs
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'text/csv',
                        'headers': {}
                    },
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,2019-08-20,ExampleName4'
                },
            },
        )

    @paramseq
    def initial_state_and_orig_data_variants():
        yield param(
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '2019-08-20 01:00:00,1.1.1.1,447,2019-08-20,ExampleName1',
                    '2019-08-20 01:00:00,2.2.2.2,447,2019-08-20,ExampleName2'
                },
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '2019-08-20 03:00:00,5.5.5.5,447,2019-08-20,ExampleName5\n'
                '2019-08-20 03:00:00,4.4.4.4,447,2019-08-20,ExampleName4\n'
                '2019-08-20 02:00:00,3.3.3.3,447,2019-08-20,ExampleName3\n'
                '2019-08-20 01:00:00,2.2.2.2,447,2019-08-20,ExampleName2\n'
                '2019-08-20 01:00:00,1.1.1.1,447,2019-08-20,ExampleName1\n'
                '2019-08-20 00:00:00,0.0.0.0,447,2019-08-20,ExampleName0'
            ),
        )

        yield param(
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '# row which should be ignored by collector\n'
                '2019-08-20 03:00:00,5.5.5.5,447,2019-08-20,ExampleName5\n'
                '2019-08-20 03:00:00,4.4.4.4,447,2019-08-20,ExampleName4\n'
                '2019-08-20 02:00:00,3.3.3.3,447,2019-08-20,ExampleName3\n'
            ),
        )

    @foreach(cases)
    @foreach(initial_state_and_orig_data_variants)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChSSLBlacklistCollector(_TestAbuseChDownloadingTimeOrderedRowsCollectorBase):

    COLLECTOR_CLASS = AbuseChSSLBlacklistCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [abusech_ssl_blacklist]
                source=abuse-ch
                cache_dir=~/.n6cache
                url=https://www.example.com
                download_retries=5
            ''',
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.ssl-blacklist.201902',

                    # body
                    (
                        '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5\n'
                        '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                        '2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3'
                    ),

                    # prop_kwargs
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'text/csv',
                        'headers': {}
                    },
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5',
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4'
                },
            },
        )

    @paramseq
    def initial_state_and_orig_data_variants():
        yield param(
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1',
                    '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2'
                },
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                '2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
                '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2\n'
                '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1\n'
                '2019-08-20 00:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName0'
            ),
        )

        yield param(
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '# row which should be ignored by collector\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                '2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
            ),
        )

        yield param(
            initial_state={
                # legacy form of state
                'time': '2019-08-20 02:00:00',
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5\n'
                '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                '2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
                '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2\n'
                '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1\n'
                '2019-08-20 00:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName0'
            ),
        )

    @foreach(cases)
    @foreach(initial_state_and_orig_data_variants)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChUrlhausPayloadsUrlsCollector(_TestAbuseChDownloadingTimeOrderedRowsCollectorBase):

    COLLECTOR_CLASS = AbuseChUrlhausPayloadsUrlsCollector

    DEFAULT_PROP_KWARGS = {
        'timestamp': ANY,
        'message_id': ANY,
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {}
    }



    @paramseq
    def cases():
        yield param(
            config_content='''
                [abusech_urlhaus_payloads_urls]
                source=abuse-ch
                cache_dir=~/.n6cache
                url=https://www.example.com
                download_retries=5
            ''',
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.urlhaus-payloads-urls',

                    # body
                    (
                        '"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                            '"555e5555e555ee5e55e55555ee555555",'
                            '"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                            '"ExampleNick5"\n'
                        '"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                            '"444d4444d444dd4d44d44444dd444444",'
                            '"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                            '"ExampleNick4"\n'
                        '"2019-08-20 02:00:00","http://www.example3.com","XX3",'
                            '"333c3333c333cc3c33c33333cc333333",'
                            '"3c3c33cc33c3c33cc33c3333333cccccccccccccc333333c3c3c3c3c3c3c3c33",'
                            '"ExampleNick3"'
                    ),

                    # prop_kwargs
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'text/csv',
                        'headers': {}
                    },
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                        '"555e5555e555ee5e55e55555ee555555",'
                        '"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                        '"ExampleNick5"',
                    '"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                        '"444d4444d444dd4d44d44444dd444444",'
                        '"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                        '"ExampleNick4"'
                },
            },
        )

    @paramseq
    def initial_state_and_orig_data_variants():
        yield param(
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '"2019-08-20 01:00:00","http://www.example2.com","XX2",'
                        '"222b2222b222bb2b22b22222bb222222",'
                        '"2b2b22bb22b2b22bb22b2222222bbbbbbbbbbbbbb222222b2b2b2b2b2b2b2b22",'
                        '"ExampleNick2"',
                    '"2019-08-20 01:00:00","http://www.example1.com","XX1",'
                        '"111a1111a111aa1a11a11111aa111111",'
                        '"1a1a11aa11a1a11aa11a1111111aaaaaaaaaaaaaa111111a1a1a1a1a1a1a1a11",'
                        '"ExampleNick1"'
                },
            },
            orig_data=(
                '# row which should be ignored by collector\n'
                '"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                    '"555e5555e555ee5e55e55555ee555555",'
                    '"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                    '"ExampleNick5"\n'
                '"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                    '"444d4444d444dd4d44d44444dd444444",'
                    '"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                    '"ExampleNick4"\n'
                '"2019-08-20 02:00:00","http://www.example3.com","XX3",'
                    '"333c3333c333cc3c33c33333cc333333",'
                    '"3c3c33cc33c3c33cc33c3333333cccccccccccccc333333c3c3c3c3c3c3c3c33",'
                    '"ExampleNick3"\n'
                '"2019-08-20 01:00:00","http://www.example2.com","XX2",'
                    '"222b2222b222bb2b22b22222bb222222",'
                    '"2b2b22bb22b2b22bb22b2222222bbbbbbbbbbbbbb222222b2b2b2b2b2b2b2b22",'
                    '"ExampleNick2"\n'
                '"2019-08-20 01:00:00","http://www.example1.com","XX1",'
                    '"111a1111a111aa1a11a11111aa111111",'
                    '"1a1a11aa11a1a11aa11a1111111aaaaaaaaaaaaaa111111a1a1a1a1a1a1a1a11",'
                    '"ExampleNick1"\n'
                '"2019-08-20 00:00:00","http://www.example0.com","XX0",'
                    '"000a0000a000aa0a00a00000aa000000",'
                    '"0a0a00aa00a0a00aa00a0000000aaaaaaaaaaaaaa000000a0a0a0a0a0a0a0a00",'
                    '"ExampleNick0"'
            ),
        )

        yield param(
            initial_state=sentinel.NO_STATE,
            orig_data=(
                '# row which should be ignored by collector\n'
                '"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                    '"555e5555e555ee5e55e55555ee555555",'
                    '"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                    '"ExampleNick5"\n'
                '"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                    '"444d4444d444dd4d44d44444dd444444",'
                    '"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                    '"ExampleNick4"\n'
                '"2019-08-20 02:00:00","http://www.example3.com","XX3",'
                    '"333c3333c333cc3c33c33333cc333333",'
                    '"3c3c33cc33c3c33cc33c3333333cccccccccccccc333333c3c3c3c3c3c3c3c33",'
                    '"ExampleNick3"\n'
            ),
        )

    @foreach(cases)
    @foreach(initial_state_and_orig_data_variants)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChSSLBlacklistDyreCollector__get_output_data_body(unittest.TestCase):

    COLLECTOR_CLASS = AbuseChSSLBlacklistDyreCollector

    regular_rss = [
        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>c55f4ccb1dee96eba345ab280367a2ebb032e6f4 (2016-10-17 12:44:04'
         ')</title>\n<link>https://sslbl.abuse.ch/intel/randoma542b7148f2ddea211'
         '495787733</link>\n<description>SHA1: c55f4ccb1dee96eba345ab280367a2ebb032e6f4'
         'e, Common Name: random-company.com, Issuer: example RSA'
         'Domain Validation Secure Server CA</description>\n<guid>https://sslb'
         'l.abuse.ch/intel/c55f4ccb1dee96eba345ab280367a2ebb032e6f4'
         '</guid>\n</item>\n</channel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>random6a5b83dc3e8c8d649101f7872719fce (2016-10-17 12:44:04'
         ')</title>\n<link>https://sslbl.abuse.ch/intel/random6a5b83dc3e8c8'
         'd649101f7872719fce</link>\n<description>SHA1: random6a5b83dc3e8c8'
         'd649101f7872719fce, Common Name: random-company.com, Issuer: example'
         'Domain Validation Secure Server CA</description>\n<guid>https://sslb'
         'l.abuse.ch/intel/random6a5b83dc3e8c8d649101f7872719fce&amp;id=838'
         '4156e3b53194b118b9fe8c9d26709</guid>\n</item>\n</channel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>erandom_stateb882f1f03f091123511eaa3fc2d6b1 (2016-10-14 11:13:35)<'
         '/title>\n<link>https://sslbl.abuse.ch/intel/erandom_stateb882f1f03f0911235'
         '11eaa3fc2d6b1</link>\n<description>SHA1: erandom_stateb882f1f03f091123511e'
         'aa3fc2d6b1, Common Name: C=GB, ST=Berkshire, L=Newbury, O=My Company L'
         'td, Issuer: C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd</descripti'
         'on>\n<guid>https://sslbl.abuse.ch/intel/erandom_stateb882f1f03f091123511ea'
         'a3fc2d6b1&amp;id=758994d35dd23c61dacd6902c32cab9e</guid>\n</item>\n</cha'
         'nnel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>anony920e3d0cba40be80fba5e23a6b4f9a706dd4 (2016-10-07 04:51:52)<'
         '/title>\n<link>https://sslbl.abuse.ch/intel/anony920e3d0cba40be80fba5e23'
         'a6b4f9a706dd4</link>\n<description>SHA1: anony920e3d0cba40be80fba5e23a6b'
         '4f9a706dd4, Common Name: C=US, ST=Denial, L=Springfield, O=Dis, Issuer'
         ': C=US, ST=Denial, L=Springfield, O=Dis</description>\n<guid>https://ss'
         'lbl.abuse.ch/intel/anony920e3d0cba40be80fba5e23a6b4f9a706dd4&amp;id=aa8'
         '822242d2ed85df15ba6db737add3d</guid>\n</item>\n</channel>\n</rss>\n'),
    ]

    invalid_rss = [
        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>random6a5b83dc3e8c8d649101f7872719fce (2016-10-17 12:44:04)<'
         '/title>\n<description>SHA1: random6a5b83dc3e8c8d649101f7872719fce, C'
         'ommon Name: random-company.com, Issuer: RANDOM_RANDOM Secu'
         're Server CA</description>\n<guid>https://sslbl.abuse.ch/intel/1111af01'
         'd6a5b83dc3e8c8d649101f7872719fce&amp;id=8384156e3b53194b118b9fe8c9d267'
         '09</guid>\n</item>\n'),
    ]

    results = [
        {
            "https://sslbl.abuse.ch/intel/randoma542b7148f2ddea211495787733":
            {
                "subject": "OU=Domain Control Validated, OU=PositiveSSL, CN=random-company.com",
                "issuer": "C=GB, ST=Greater Manchester, L=Salford, O=example CA Limited, "
                          "CN=RANDOM_RANDOM Secure Server CA",
                "fingerprint": "random6a5b83dc3e8c8d649101f7872719fce",
                "name": "Gozi MITM",
                "timestamp": "2016-10-17 12:44:04",
            },
        },
        {
            "https://sslbl.abuse.ch/intel/random6a5b83dc3e8c8d649101f7872719fce":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "randoma542b7148f2ddea211495787733",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    [
                        "2016-10-13 16:27:10",
                        "76b609dac79e76fe7b5a78af35c5a2d6",
                        "1.1.1.1",
                        "443",
                    ],
                    [
                        "2016-10-10 17:29:57",
                        "9096210f20753c836378ca7aa18c3d25",
                        "2.2.2.2",
                        "443",
                    ],
                ],
            },
        },
        {
            "https://sslbl.abuse.ch/intel/erandom_stateb882f1f03f091123511eaa3fc2d6b1":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "erandom_stateb882f1f03f091123511eaa3fc2d6b1",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    [
                        "2016-10-07 19:55:38",
                        "d9e83ed20a652e7629b753e20336f7a4",
                        "3.3.3.3",
                        "443",
                    ],
                ],
            },
        },
    ]

    detail_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>random-company.com</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject'
        ':</th><td>OU=Domain Control Validated, OU=PositiveSSL, CN=random-company.'
        'com</td></tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>'
        'example Domain Validation Secure Server CA</td></tr>\n<tr bgcolor="#D8'
        'D8D8"><th>Issuer:</th><td>C=GB, ST=Greater Manchester, L=Salford, O='
        'example CA Limited, CN=RANDOM_RANDOM Secure Server CA</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Fingerprint (SHA1):</th><td>random6'
        'a5b83dc3e8c8d649101f7872719fce</td></tr>\n<tr bgcolor="red"><th>Status:'
        '</th><td><strong>Blacklisted</strong> (Reason: Gozi MITM, Listing date'
        ': 2016-10-17 12:44:04)</td></tr>\n</table>\n<br /><h2>Associated malware'
        ' binaries</h2>\n<p>This SSL certificate was spotted passively or by usi'
        'ng scanning techniques. Therefore SSLBL is not able to provide any ref'
        'erencing malware binaries.</p>\n<div class="footer">Copyright &copy; 20'
        '16 - sslbl.abuse.ch</div>\n</div>\n</body>\n</html>\n')

    binaries_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>localhost</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject:</th>'
        '<td>C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>localhost<'
        '/td></tr>\n<tr bgcolor="#D8D8D8"><th>Issuer:</th><td>C=GB, ST=Yorks, L='
        'York, O=MyCompany Ltd., OU=IT, CN=localhost</td></tr>\n<tr bgcolor="#ff'
        'ffff"><th>SSL Version:</th><td>TLSv1</td></tr>\n<tr bgcolor="#D8D8D8"><'
        'th>Fingerprint (SHA1):</th><td>randoma542b7148f2ddea21149578773'
        '3</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Blacklisted<'
        '/strong> (Reason: ZeuS C&amp;C, Listing date: 2016-10-17 11:52:40)</td'
        '></tr>\n</table>\n<br /><h2>Associated malware binaries</h2>\n<table clas'
        's="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malware binary (MD5 hash'
        ')</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcolor="#D8D8D8">'
        '<td>2016-10-13 16:27:10</td><td>76b609dac79'
        'e76fe7b5a78af35c5a2d6</td><td>1.1.1.1</td><td>443</td></tr>\n'
        '<tr bgcolor="#ffffff"><td>2016-10-10 17:29:57</td><td>9096210f20753c83637'
        '8ca7aa18c3d25</td><td>2.2.2.2</td><td>443</td></tr>'
        '</table>\n<p># of referencing malware binaries: <strong>4</strong>'
        '</p>\n<div class="footer">Copyright &copy; 2016 - sslbl.ab'
        'use.ch</div>\n</div>\n</body>\n</html>\n')

    updated_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>localhost</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject:</th>'
        '<td>C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>localhost<'
        '/td></tr>\n<tr bgcolor="#D8D8D8"><th>Issuer:</th><td>C=GB, ST=Yorks, L='
        'York, O=MyCompany Ltd., OU=IT, CN=localhost</td></tr>\n<tr bgcolor="#ff'
        'ffff"><th>SSL Version:</th><td>TLSv1</td></tr>\n<tr bgcolor="#D8D8D8"><'
        'th>Fingerprint (SHA1):</th><td>erandom_stateb882f1f03f091123511eaa3fc2d6b1'
        '</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Blacklisted<'
        '/strong> (Reason: ZeuS C&amp;C, Listing date: 2016-10-17 11:52:40)</td'
        '></tr>\n</table>\n<br /><h2>Associated malware binaries</h2>\n<table clas'
        's="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malware binary (MD5 hash'
        ')</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcolor="#D8D8D8"><td>20'
        '16-10-13 16:27:10</td><td>76b609dac79e76fe7b5a78af35c5a2d6</td><td>3.'
        '3.3.3</td><td>443</td></tr>\n<tr bgcolor="#ffffff"><td>2016-10-10 1'
        '7:29:57</td><td>9096210f20753c836378ca7aa18c3d25</td><td>3.3.3.3<'
        '/td><td>443</td></tr>\n<tr bgcolor="#D8D8D8"><td>2016-10-07 19:55:38</t'
        'd><td>d9e83ed20a652e7629b753e20336f7a4</td><td>3.3.3.3</td><td>44'
        '3</td></tr>\n</table>\n<p># of referencing malware binaries: <strong>3</'
        'strong></p>\n<div class="footer">Copyright &copy; 2016 - sslbl.abuse.ch'
        '</div>\n</div>\n</body>\n</html>\n')

    not_updated_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>C=US, ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgcolor'
        '="#D8D8D8"><th>Subject:</th><td>C=US, ST=Denial, L=Springfield, O=Dis<'
        '/td></tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>C=US, '
        'ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgcolor="#D8D8D8"><th>Is'
        'suer:</th><td>C=US, ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgco'
        'lor="#ffffff"><th>SSL Version:</th><td>TLS 1.2</td></tr>\n<tr bgcolor="'
        '#D8D8D8"><th>Fingerprint (SHA1):</th><td>anony920e3d0cba40be80fba5e23a6'
        'b4f9a706dd4</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Bl'
        'acklisted</strong> (Reason: TorrentLocker C&amp;C, Listing date: 2016-'
        '10-07 04:51:52)</td></tr>\n</table>\n<br /><h2>Associated malware binari'
        'es</h2>\n<table class="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malwa'
        're binary (MD5 hash)</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcol'
        'or="#D8D8D8"><td>2016-10-06 15:32:44</td><td>randomc0621a42ca3da0b0a01'
        '2e2ac43</td><td>3.3.3.3</td><td>443</td></tr>\n</table>\n<p># of re'
        'ferencing malware binaries: <strong>4</strong></p>\n<div class="footer"'
        '>Copyright &copy; 2016 - sslbl.abuse.ch</div>\n</div>\n</body>\n</html>'
        '\n')

    states = [
        {
            "https://sslbl.abuse.ch/intel/erandom_stateb882f1f03f091123511eaa3fc2d6b1":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "erandom_stateb882f1f03f091123511eaa3fc2d6b1",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    (
                        "2016-10-13 16:27:10",
                        "76b609dac79e76fe7b5a78af35c5a2d6",
                        "3.3.3.3",
                        "443",
                    ),
                    (
                        "2016-10-10 17:29:57",
                        "9096210f20753c836378ca7aa18c3d25",
                        "3.3.3.3",
                        "443",
                    ),
                ],
            },
        },
        {
            "https://sslbl.abuse.ch/intel/anony920e3d0cba40be80fba5e23a6b4f9a706dd4":
            {
                "subject": "C=US, ST=Denial, L=Springfield, O=Dis",
                "issuer": "C=US, ST=Denial, L=Springfield, O=Dis",
                "fingerprint": "anony920e3d0cba40be80fba5e23a6b4f9a706dd4",
                "name": "TorrentLocker C&C",
                "timestamp": "2016-10-07 04:51:52",
                "binaries": [
                    (
                        "2016-10-06 15:32:44",
                        "randomc0621a42ca3da0b0a012e2ac43",
                        "3.3.3.3",
                        "443",
                    ),
                ],
            },
        },
    ]

    params = [
        # 1st case: detail page does not contain binaries table
        param(
            rss=regular_rss[0],
            page=detail_page,
            state=None,
            result=results[0],
        ).label('no_binaries'),

        # 2nd case: detail page with binaries table
        param(
            rss=regular_rss[1],
            page=binaries_page,
            state=None,
            result=results[1],
        ).label('binaries'),

        # 3rd case: invalid RSS, no URL, no new data
        param(
            rss=invalid_rss[0],
            page=None,
            state=None,
            result=None,
        ).label('no_url'),

        # 4th case: detail page contains one more binary record,
        # comparing to data saved during last collector's "run"
        param(
            rss=regular_rss[2],
            page=updated_page,
            state=states[0],
            result=results[2],
        ).label('updated_page'),

        # 5th case: no new items, do not publish
        param(
            rss=regular_rss[3],
            page=not_updated_page,
            state=states[1],
            result=None,
        ).label('not_updated_page')
    ]

    mocked_config = {
        'url': sentinel.dummy_url,
        'details_download_timeout': 12,
        'details_retry_timeout': 4,
    }


    @foreach(params)
    def test(self, rss, page, state, result, label):
        with patch('n6.collectors.generic.CollectorWithStateMixin.__init__'), \
             patch.object(self.COLLECTOR_CLASS, 'config', self.mocked_config, create=True):
            instance = self.COLLECTOR_CLASS()
            instance._download_retry = Mock(return_value=rss)
            instance._download_retry_external = Mock(return_value=page)
            instance.load_state = Mock(return_value=state)

            if label in ('no_url', 'not_updated_page'):
                with self.assertRaises(NoNewDataException):
                    self.COLLECTOR_CLASS.get_output_data_body(instance)
            else:
                output_data_body = self.COLLECTOR_CLASS.get_output_data_body(instance)
                self.assertDictEqual(loads(output_data_body), result)

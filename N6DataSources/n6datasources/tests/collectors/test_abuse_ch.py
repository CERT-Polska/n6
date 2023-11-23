# Copyright (c) 2019-2023 NASK. All rights reserved.

import json
from unittest.mock import (
    call,
    sentinel,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.abuse_ch import (
    AbuseChFeodoTrackerCollector,
    AbuseChSslBlacklistCollector,
    AbuseChUrlhausUrlsCollector,
    AbuseChUrlhausPayloadsUrlsCollector,
)
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    zip_data_in_memory,
)


class _BaseAbuseChDownloadingTimeOrderedRowsCollectorTestCase(BaseCollectorTestCase):

    COLLECTOR_CLASS = None   # to be set in concrete test classes

    DEFAULT_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {},
    }

    def _perform_test(
            self,
            config_content,
            initial_state,
            orig_data,
            expected_publish_output_calls,
            expected_saved_state,
            perform_request_mocked_responses=None,
            label=None,                     # argument irrelevant here (passed in by `@foreach`)   # noqa
            context_targets=None):          # argument irrelevant here (passed in by `@foreach`)   # noqa

        collector = self.prepare_collector(self.COLLECTOR_CLASS,
                                           config_content=config_content,
                                           initial_state=initial_state)
        if orig_data:
            self.patch(
                "n6datasources.collectors.base.BaseDownloadingCollector.download",
                return_value=orig_data)
        else:
            self.patch(
                "n6datasources.collectors.base.BaseDownloadingCollector.download",
                side_effect=perform_request_mocked_responses)
        collector.run_collection()
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)


@expand
class TestAbuseChFeodoTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollectorTestCase):

    COLLECTOR_CLASS = AbuseChFeodoTrackerCollector

    EXAMPLE_ORIG_DATA = (
        b'# row which should be ignored by collector\n'
        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5\n'
        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3\n'
        b'2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2\n'
        b'2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1\n'
        b'2019-08-20 00:00:00,0.0.0.0,447,online,2019-08-20,ExampleName0'
    )

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1',
                    '2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2',
                },
                'rows_count': 3
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3\n'
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
                        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5'},
                'rows_count': 6
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 00:00:00,0.0.0.0,447,online,2019-08-20,ExampleName0\n'
                        b'2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1\n'
                        b'2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2\n'
                        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3\n'
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
                        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChSslBlacklistCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollectorTestCase):

    COLLECTOR_CLASS = AbuseChSslBlacklistCollector

    EXAMPLE_ORIG_DATA = (
        b'# row which should be ignored by collector\n'
        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5\n'
        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
        b'2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
        b'2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2\n'
        b'2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1\n'
        b'2019-08-20 00:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName0'
    )

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [AbuseChSslBlacklistCollector]
                row_count_mismatch_is_fatal = False
                url=https://www.example.com
                download_retries=5
            ''',
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1',
                    '2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2'
                },
                'rows_count': 3
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.ssl-blacklist.201902',

                    # body
                    (
                        b'2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
                        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5',
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4'
                },
                'rows_count': 6
            },
        )

        yield param(
            config_content='''
                [AbuseChSslBlacklistCollector]
                row_count_mismatch_is_fatal = False
                url=https://www.example.com
                download_retries=5
            ''',
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.ssl-blacklist.201902',

                    # body
                    (
                        b'2019-08-20 00:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName0\n'
                        b'2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName1\n'
                        b'2019-08-20 01:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName2\n'
                        b'2019-08-20 02:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName3\n'
                        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4\n'
                        b'2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName5',
                    '2019-08-20 03:00:00,f0a0k0e0d0s0h0a010000000000a0a0a00000000,ExampleName4'
                },
                'rows_count': 6
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChUrlhausUrlsCollector(BaseCollectorTestCase):

    CONFIG_CONTENT = '''
        [AbuseChUrlhausUrlsCollector]
        api_url=https://www.example2.com
        url=https://www.example1.com
        api_retries=3
        row_count_mismatch_is_fatal = False
        download_retries=10
    '''

    DEFAULT_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'stream',
        'headers': {},
    }

    DEFAULT_ABUSE_ROWS = (
        '# row which should be ignored by collector\n'
        '"111111","2020-01-01 01:00:00","http://example_1.com","XXX1","YYY1","ZZZ1",'
        '"https://urlhaus.abuse.ch/url/111111/","Example_Nick_1"\n'
        '"000000","2020-01-01 00:00:00","http://example_0.com","XXX0","YYY0","ZZZ0",'
        '"https://urlhaus.abuse.ch/url/000000/","Example_Nick_0"\n'
    )

    DEFAULT_INFO_PAGE_1 = json.dumps(
        {
            "urlhaus_reference": "https://urlhaus.abuse.ch/url/000000/",
            "threat": "malware_download",
            "larted": "true",
            "reporter": "ExampleNick_1",
            "url": "https://example_1.com",
            "tags": [
                "elf",
                "Mozi",
            ],
            "blacklists": {
                "surbl": "not listed",
                "gsb": "not listed",
                "spamhaus_dbl": "not listed",
            },
            "id": "111111",
            "host": "1.1.1.1",
            "payloads": [
                {
                    "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/a00a00aa0aa0a0a00aaa0a00a0a00a00a00a000a0a00000a0a0a0a00a0aaa0a0/",
                    "file_type": "elf",
                    "filename": "",
                    "response_md5": "1a111111a1aa11a111111aa11a111aa1",
                    "response_sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1",
                    "response_size": "95268",
                    "signature": "",
                    "firstseen": "2020-01-20",
                    "virustotal": {
                        "link": "https://www.virustotal.com/file/a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1/analysis/111111111111/",
                        "percent": "61.02",
                        "result": "36 / 59",
                    },
                },
            ],
            "url_status": "online",
            "takedown_time_seconds": "",
            "date_added": "2020-01-01 00:00:00 UTC",
            "query_status": "ok",
        },
    )
    DEFAULT_INFO_PAGE_2 = json.dumps(
        {
            "urlhaus_reference": "https://urlhaus.abuse.ch/url/000000/",
            "threat": "malware_download",
            "larted": "true",
            "reporter": "ExampleNick_1",
            "url": "https://example_1.com",
            "tags": [
                "elf",
                "Mozi",
            ],
            "blacklists": {
                "surbl": "not listed",
                "gsb": "not listed",
                "spamhaus_dbl": "not listed",
            },
            "id": "111111",
            "host": "1.1.1.1",
            "payloads": [
                {
                    "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/a00a00aa0aa0a0a00aaa0a00a0a00a00a00a000a0a00000a0a0a0a00a0aaa0a0/",
                    "file_type": "elf",
                    "filename": "",
                    "response_md5": "1a111111a1aa11a111111aa11a111aa1",
                    "response_sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1",
                    "response_size": "95268",
                    "signature": "",
                    "firstseen": "2020-01-20",
                    "virustotal": {
                        "link": "https://www.virustotal.com/file/a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1/analysis/111111111111/",
                        "percent": "61.02",
                        "result": "36 / 59",
                    },
                },
            ],
            "url_status": "online",
            "takedown_time_seconds": "",
            "date_added": "2020-01-01 00:00:00 UTC",
            "query_status": "ok",
        },
    )

    def _perform_test(
            self,
            config_content,
            initial_state,
            perform_request_mocked_responses,
            expected_publish_output_calls,
            expected_saved_state,
            label,              # argument irrelevant here (passed in by `@foreach`)   # noqa
            context_targets):   # argument irrelevant here (passed in by `@foreach`)   # noqa

        collector = self.prepare_collector(AbuseChUrlhausUrlsCollector,
                                           config_content=config_content,
                                           initial_state=initial_state)
        self.patch(
            "n6datasources.collectors.base.BaseDownloadingCollector.download",
            side_effect=perform_request_mocked_responses)
        collector.run_collection()
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)

    @paramseq
    def cases(cls):
        yield param(
            config_content=cls.CONFIG_CONTENT,
            initial_state=sentinel.NO_STATE,
            perform_request_mocked_responses=[
                zip_data_in_memory(filename='csv.txt', data=cls.DEFAULT_ABUSE_ROWS),
                cls.DEFAULT_INFO_PAGE_1,
                cls.DEFAULT_INFO_PAGE_2,
            ],
            expected_publish_output_calls=[
                call('abuse-ch.urlhaus-urls.202001', (
                    b'['
                        b'{'
                            b'"url_id": "000000", '
                            b'"dateadded": "2020-01-01 00:00:00", '
                            b'"url": "http://example_0.com", '
                            b'"url_status": "XXX0", '
                            b'"threat": "YYY0", '
                            b'"tags": "ZZZ0", '
                            b'"urlhaus_link": "https://urlhaus.abuse.ch/url/000000/", '
                            b'"reporter": "Example_Nick_0", '
                            b'"url_info_from_api": '
                                b'{'
                                    b'"urlhaus_reference": "https://urlhaus.abuse.ch/url/000000/", '
                                    b'"threat": "malware_download", '
                                    b'"larted": "true", '
                                    b'"reporter": "ExampleNick_1", '
                                    b'"url": "https://example_1.com", '
                                    b'"tags": ["elf", "Mozi"], '
                                    b'"blacklists": {"surbl": "not listed", "gsb": "not listed", "spamhaus_dbl": "not listed"}, '
                                    b'"id": "111111", '
                                    b'"host": "1.1.1.1", '
                                    b'"payloads": '
                                        b'['
                                            b'{'
                                                b'"urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/a00a00aa0aa0a0a00aaa0a00a0a00a00a00a000a0a00000a0a0a0a00a0aaa0a0/", '
                                                b'"file_type": "elf", '
                                                b'"filename": "", '
                                                b'"response_md5": "1a111111a1aa11a111111aa11a111aa1", '
                                                b'"response_sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1", '
                                                b'"response_size": "95268", '
                                                b'"signature": "", '
                                                b'"firstseen": "2020-01-20", '
                                                b'"virustotal": {"link": "https://www.virustotal.com/file/a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1/analysis/111111111111/", "percent": "61.02", "result": "36 / 59"}'
                                            b'}'
                                        b'], '
                                b'"url_status": "online", '
                                b'"takedown_time_seconds": "", '
                                b'"date_added": "2020-01-01 00:00:00 UTC", '
                                b'"query_status": "ok"'
                            b'}'
                        b'}, '
                        b'{'
                            b'"url_id": "111111", '
                            b'"dateadded": "2020-01-01 01:00:00", '
                            b'"url": "http://example_1.com", '
                            b'"url_status": "XXX1", '
                            b'"threat": "YYY1", '
                            b'"tags": "ZZZ1", '
                            b'"urlhaus_link": "https://urlhaus.abuse.ch/url/111111/", '
                            b'"reporter": "Example_Nick_1", '
                            b'"url_info_from_api": '
                                b'{'
                                    b'"urlhaus_reference": "https://urlhaus.abuse.ch/url/000000/", '
                                    b'"threat": "malware_download", '
                                    b'"larted": "true", "reporter": "ExampleNick_1", '
                                    b'"url": "https://example_1.com", '
                                    b'"tags": ["elf", "Mozi"], '
                                    b'"blacklists": {"surbl": "not listed", "gsb": "not listed", "spamhaus_dbl": "not listed"}, '
                                    b'"id": "111111", '
                                    b'"host": "1.1.1.1", '
                                    b'"payloads": '
                                        b'['
                                            b'{'
                                                b'"urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/a00a00aa0aa0a0a00aaa0a00a0a00a00a00a000a0a00000a0a0a0a00a0aaa0a0/", '
                                                b'"file_type": "elf", '
                                                b'"filename": "", '
                                                b'"response_md5": "1a111111a1aa11a111111aa11a111aa1", '
                                                b'"response_sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1", '
                                                b'"response_size": "95268", '
                                                b'"signature": "", '
                                                b'"firstseen": "2020-01-20", '
                                                b'"virustotal": {"link": "https://www.virustotal.com/file/a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1/analysis/111111111111/", "percent": "61.02", "result": "36 / 59"}'
                                            b'}'
                                        b'], '
                                b'"url_status": "online", '
                                b'"takedown_time_seconds": "", '
                                b'"date_added": "2020-01-01 00:00:00 UTC", '
                                b'"query_status": "ok"'
                            b'}'
                        b'}'
                    b']'
                ),
                     # prop_kwargs
                     cls.DEFAULT_PROP_KWARGS,
                     ),
            ],
            expected_saved_state={
                'newest_row_time': '2020-01-01 01:00:00',
                'newest_rows': {
                    '"111111","2020-01-01 01:00:00","http://example_1.com","XXX1","YYY1","ZZZ1",'
                        '"https://urlhaus.abuse.ch/url/111111/","Example_Nick_1"'
                },
                'rows_count': 2
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestAbuseChUrlhausPayloadsUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollectorTestCase):  # noqa

    COLLECTOR_CLASS = AbuseChUrlhausPayloadsUrlsCollector

    EXAMPLE_ORIG_DATA = (
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
    )

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [AbuseChUrlhausPayloadsUrlsCollector]
                url=https://www.example.com
                download_retries=5
            ''',
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
                'rows_count': 3
            },
            orig_data=zip_data_in_memory(filename='payload.txt', data=cls.EXAMPLE_ORIG_DATA,
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.urlhaus-payloads-urls',

                    # body
                    (
                        b'"2019-08-20 02:00:00","http://www.example3.com","XX3",'
                            b'"333c3333c333cc3c33c33333cc333333",'
                            b'"3c3c33cc33c3c33cc33c3333333cccccccccccccc333333c3c3c3c3c3c3c3c33",'
                            b'"ExampleNick3"\n'
                        b'"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                            b'"444d4444d444dd4d44d44444dd444444",'
                            b'"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                            b'"ExampleNick4"\n'
                        b'"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                            b'"555e5555e555ee5e55e55555ee555555",'
                            b'"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                            b'"ExampleNick5"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS,
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
                        '"ExampleNick4"',
                },
                'rows_count': 6
            },
        )

        yield param(
            config_content='''
                [AbuseChUrlhausPayloadsUrlsCollector]
                url=https://www.example.com
                download_retries=5
            ''',
            initial_state=sentinel.NO_STATE,
            orig_data=zip_data_in_memory(
                filename='payload.txt',
                data=(
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
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.urlhaus-payloads-urls',

                    # body
                    (
                        b'"2019-08-20 02:00:00","http://www.example3.com","XX3",'
                            b'"333c3333c333cc3c33c33333cc333333",'
                            b'"3c3c33cc33c3c33cc33c3333333cccccccccccccc333333c3c3c3c3c3c3c3c33",'
                            b'"ExampleNick3"\n'
                        b'"2019-08-20 03:00:00","http://www.example4.com","XX4",'
                            b'"444d4444d444dd4d44d44444dd444444",'
                            b'"4d4d44dd44d4d44dd44d4444444dddddddddddddd444444d4d4d4d4d4d4d4d44",'
                            b'"ExampleNick4"\n'
                        b'"2019-08-20 03:00:00","http://www.example5.com","XX5",'
                            b'"555e5555e555ee5e55e55555ee555555",'
                            b'"5e5e55ee55e5e55ee55e5555555eeeeeeeeeeeeee555555e5e5e5e5e5e5e5e55",'
                            b'"ExampleNick5"'
                    ),

                    # prop_kwargs
                    cls.DEFAULT_PROP_KWARGS
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
                    '"ExampleNick4"',
                },
                'rows_count': 3
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

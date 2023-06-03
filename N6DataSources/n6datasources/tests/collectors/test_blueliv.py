# Copyright (c) 2023 NASK. All rights reserved.

import json

from unittest.mock import call
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.collectors.blueliv import BluelivMapCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


@expand
class TestBluelivMapCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = BluelivMapCollector

    EXPECTED_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'blacklist',
        'content_type': 'application/json',
        'headers': {},
    }

    def _perform_test(self,
                      config_content,
                      orig_data,
                      expected_download_calls,
                      expected_publish_output_calls,
                      **kwargs):

        download_mock = self.patch_object(
            BaseDownloadingCollector,
            'download',
            return_value=orig_data)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content)

        collector.run_collection()
        self.assertEqual(download_mock.mock_calls, expected_download_calls)
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [BluelivMapCollector]
                base_url = https://example.com/
                token = a1a1a1a1a1a1a1a1a1
                endpoint_name = some-endpoint/name1
                download_retries = 1
            ''',
            orig_data=json.dumps(
                {
                    "name1": [
                        {
                            "url": "http://example-url1.com",
                            "type": "MALWARE",
                            "country": "ES",
                            "status": "ONLINE",
                            "latitude": 1.1,
                            "longitude": -1.1,
                            "ip": "1.1.1.1",
                            "updatedAt": "2023-03-29T12:00:02+0000",
                            "firstSeenAt": "2022-12-30T10:10:10+0000",
                            "lastSeenAt": "2023-03-29T11:55:52+0000",
                        },
                    ],
                }, sort_keys=True).encode('utf-8'),
            expected_download_calls=[
                call(
                    method='GET',
                    url='https://example.com/some-endpoint/name1',
                    custom_request_headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'bearer a1a1a1a1a1a1a1a1a1',
                        'User-Agent': 'SDK v2',
                        'X-API-CLIENT': 'a1a1a1a1a1a1a1a1a1',
                        'Accept-Encoding': 'gzip, deflate',
                    },
                ),
            ],
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'blueliv.map',

                    # body
                    json.dumps([
                        {
                            "url": "http://example-url1.com",
                            "type": "MALWARE",
                            "country": "ES",
                            "status": "ONLINE",
                            "latitude": 1.1,
                            "longitude": -1.1,
                            "ip": "1.1.1.1",
                            "updatedAt": "2023-03-29T12:00:02+0000",
                            "firstSeenAt": "2022-12-30T10:10:10+0000",
                            "lastSeenAt": "2023-03-29T11:55:52+0000",
                        },
                    ], sort_keys=True).encode('utf-8'),

                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
        ).label('ok case')

        yield param(
            config_content='''
                [BluelivMapCollector]
                base_url = https://example.com/
                token = a1a1a1a1a1a1a1a1a1
                endpoint_name = some-endpoint/name1
                download_retries = 1
            ''',
            orig_data=json.dumps(
                {
                    "wrong_endpoint": [
                        {
                            "url": "http://example-url1.com",
                            "type": "MALWARE",
                            "country": "ES",
                            "status": "ONLINE",
                            "latitude": 1.1,
                            "longitude": -1.1,
                            "ip": "1.1.1.1",
                            "updatedAt": "2023-03-29T12:00:02+0000",
                            "firstSeenAt": "2022-12-30T10:10:10+0000",
                            "lastSeenAt": "2023-03-29T11:55:52+0000"
                        },
                    ],
                }, sort_keys=True).encode('utf-8'),
            expected_download_calls=[
                call(
                    method='GET',
                    url='https://example.com/some-endpoint/name1',
                    custom_request_headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'bearer a1a1a1a1a1a1a1a1a1',
                        'User-Agent': 'SDK v2',
                        'X-API-CLIENT': 'a1a1a1a1a1a1a1a1a1',
                        'Accept-Encoding': 'gzip, deflate',
                    },
                ),
            ],
            expected_publish_output_calls=[],
        ).label('No key specified with `endpoint_name` option')

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

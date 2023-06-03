# Copyright (c) 2023 NASK. All rights reserved.

from unittest.mock import call

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.collectors.openphish import OpenphishWebBlCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


@expand
class TestOpenphishWebBlCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = OpenphishWebBlCollector

    def _perform_test(self,
                      config_content,
                      orig_data,
                      expected_output,
                      **kwargs):

        self.patch_object(BaseDownloadingCollector, 'download', return_value=orig_data)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content)

        collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls, expected_output)


    @paramseq
    def cases():
        yield param(
            config_content='''
                [OpenphishWebBlCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b'https: // subdomain1.example1.com/postede/pst/\n'
                b'https: // subdomain1.example1.com/postede/pst/ 2222222222222222222\n'
                b'http: // subdomain1.example1.com/postede/pst/ 333333333333333333/\n'
                b'http: // subdomain1.example1.info/Example/web/viewer.jsp?file=Privacy\n'
            ),
            expected_output=[
                call(
                    'openphish.web-bl',
                    (
                        b'https: // subdomain1.example1.com/postede/pst/\n'
                        b'https: // subdomain1.example1.com/postede/pst/ 2222222222222222222\n'
                        b'http: // subdomain1.example1.com/postede/pst/ 333333333333333333/\n'
                        b'http: // subdomain1.example1.info/Example/web/viewer.jsp?file=Privacy\n'
                    ),
                    {
                        'timestamp': AnyInstanceOf(int),
                        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                        'type': 'blacklist',
                        'content_type': 'text/plain',
                        'headers': {},
                    },
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

# Copyright (c) 2023 NASK. All rights reserved.

from unittest.mock import call

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.collectors.spam404_com import Spam404ComScamListBlCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


@expand
class TestSpam404ComScamListBlCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = Spam404ComScamListBlCollector

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
                [Spam404ComScamListBlCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b'example1.com\n'
                b'example2.com\n'
                b'example3.com\n'
                b'example4.com\n'
                b'example5.com\n'
                b'example6.com'
            ),
            expected_output=[
                call(
                    'spam404-com.scam-list-bl',
                    (
                        b'example1.com\n'
                        b'example2.com\n'
                        b'example3.com\n'
                        b'example4.com\n'
                        b'example5.com\n'
                        b'example6.com'
                    ),
                    {
                        'timestamp': AnyInstanceOf(int),
                        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                        'type': 'blacklist',
                        'content_type': 'text/csv',
                        'headers': {},
                    },
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

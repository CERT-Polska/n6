# Copyright (c) 2023 NASK. All rights reserved.

from unittest.mock import call

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.collectors.stopforum import StopForumSpamCollector
from n6datasources.tests.collectors.test_base import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    zip_data_in_memory,
)


@expand
class TestStopForumCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = StopForumSpamCollector
    EXAMPLE_ORIG_DATA = (
        b'"1.1.1.1", "1", "2023-01-01 13:00:00"\n'
        b'"2.2.2.2", "222", "2023-01-01 14:00:00"\n'
        b'"3.3.3.3", "3333", "2023-01-01 15:00:00"\n'
    )

    EXPECTED_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'file',
        'content_type': 'text/plain',
        'headers': {},
    }

    def _perform_test(self,
                      config_content,
                      orig_data,
                      expected_publish_output_calls,
                      label,                # arg (added by @foreach) irrelevant here
                      context_targets):     # arg (added by @foreach) irrelevant here

        self.patch_object(BaseDownloadingCollector, 'download', return_value=orig_data)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content)

        collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)


    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [StopForumSpamCollector]
                url=https://www.example.com
                download_retries = 1
            ''',
            orig_data=zip_data_in_memory(
                filename='csv.txt',
                data=cls.EXAMPLE_ORIG_DATA
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'stopforum.spam',
                    # body
                    (
                        b'"1.1.1.1", "1", "2023-01-01 13:00:00"\n'
                        b'"2.2.2.2", "222", "2023-01-01 14:00:00"\n'
                        b'"3.3.3.3", "3333", "2023-01-01 15:00:00"\n'
                    ),
                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

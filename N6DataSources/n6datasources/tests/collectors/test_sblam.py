# Copyright (c) 2020-2023 NASK. All rights reserved.

from unittest.mock import (
    ANY,
    call,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.sblam import SblamSpamCollector
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestSblamSpamCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = SblamSpamCollector

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
                [SblamSpamCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b"# HTTP spam sources identified by http://sblam.com.\n"
                b"# Generated 2020-04-23 03:59:01\n"
                b"# This is a list of HTML form (comment) spammers--not for blocking e-mail spam!\n"
                b"1.1.1.1\n"
                b"2.2.2.2\n"
                b"3.3.3.3\n"
                b"4.4.4.4"
            ),
            expected_output=[
                call(
                    'sblam.spam',
                    (
                        b"# HTTP spam sources identified by http://sblam.com.\n"
                        b"# Generated 2020-04-23 03:59:01\n"
                        b"# This is a list of HTML form (comment) spammers--not for blocking e-mail spam!\n"
                        b"1.1.1.1\n"
                        b"2.2.2.2\n"
                        b"3.3.3.3\n"
                        b"4.4.4.4"
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
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

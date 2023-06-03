# Copyright (c) 2023 NASK. All rights reserved.

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

from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.collectors.greensnow_co import GreenSnowCoListTxtCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestGreenSnowCoListTxtParser(BaseCollectorTestCase):

    COLLECTOR_CLASS = GreenSnowCoListTxtCollector

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
                [GreenSnowCoListTxtCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b'1.1.1.1\n'
                b'2.2.2.2\n'
                b'3.3.3.3\n'
                b'4.4.4.4\n'
                b'5.5.5.5\n'
                b'6.6.6.6\n'
                b'7.7.7.7\n'
            ),
            expected_output=[
                call(
                    'greensnow-co.list-txt',
                    (
                        b'1.1.1.1\n'
                        b'2.2.2.2\n'
                        b'3.3.3.3\n'
                        b'4.4.4.4\n'
                        b'5.5.5.5\n'
                        b'6.6.6.6\n'
                        b'7.7.7.7\n'
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
        yield param(
            config_content='''
                [GreenSnowCoListTxtCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=b"",
            expected_output=[
                call(
                    'greensnow-co.list-txt',
                    b"",
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

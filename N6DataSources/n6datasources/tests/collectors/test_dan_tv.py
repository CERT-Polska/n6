# Copyright (c) 2019-2023 NASK. All rights reserved.

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

from n6datasources.collectors.dan_tv import DanTvTorCollector
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestDanTvTorCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = DanTvTorCollector

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
                [DanTvTorCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b"1.1.1.1\n"
                b"2.2.2.2\n"
                b"1111:1a00:0000:0000:a00a:00aa:aaa0:0000\n"
                b"2222:2b22:0000:0000:b00b:00bb:bbb0:0000"
            ),
            status_code=200,
            expected_output=[
                call(
                    'dan-tv.tor',
                    (
                        b"1.1.1.1\n"
                        b"2.2.2.2\n"
                        b"1111:1a00:0000:0000:a00a:00aa:aaa0:0000\n"
                        b"2222:2b22:0000:0000:b00b:00bb:bbb0:0000"
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'blacklist',
                        'content_type': 'text/plain',
                        'headers': {},
                    },
                )
            ],
            expect_raise=False,
        )
        yield param(
            config_content='''
                [DanTvTorCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=b"",
            status_code=200,
            expected_output=[
                call(
                    'dan-tv.tor',
                    b"",
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'blacklist',
                        'content_type': 'text/plain',
                        'headers': {},
                    },
                )
            ],
            expect_raise=False,
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

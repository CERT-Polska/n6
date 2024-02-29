# Copyright (c) 2016-2024 NASK. All rights reserved.

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
from n6datasources.collectors.turris_cz import TurrisCzGreylistCsvCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestTurrisCzGreylistCsvCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = TurrisCzGreylistCsvCollector

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
                [TurrisCzGreylistCsvCollector]
                url = https://example.com
            ''',
            orig_data=(
                b'# For the terms of use see https://example.com/some_license.txt\n'
                b'Address,Tags\n'
                b'0.0.0.1,telnet\n'
                b'0.0.0.2,telnet\n'
                b'0.0.0.3,telnet\n'
                b'0.0.0.4,telnet\n'
                b'0.0.0.5,telnet\n'
                b'0.0.0.0.0.0.0.16,http_scan\n'
                b'0.0.0.0.0.0.0.32,dns\n'
                b'0.0.0.6,\"ftp,http,smtp,telnet\"'
            ),
            status_code=200,
            expected_output=[
                call(
                    'turris-cz.greylist-csv.202401',
                    (
                        b'# For the terms of use see https://example.com/some_license.txt\n'
                        b'Address,Tags\n'
                        b'0.0.0.1,telnet\n'
                        b'0.0.0.2,telnet\n'
                        b'0.0.0.3,telnet\n'
                        b'0.0.0.4,telnet\n'
                        b'0.0.0.5,telnet\n'
                        b'0.0.0.0.0.0.0.16,http_scan\n'
                        b'0.0.0.0.0.0.0.32,dns\n'
                        b'0.0.0.6,\"ftp,http,smtp,telnet\"'
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'blacklist',
                        'content_type': 'text/csv',
                        'headers': {},
                    },
                )
            ],
            expect_raise=False,
        )


    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

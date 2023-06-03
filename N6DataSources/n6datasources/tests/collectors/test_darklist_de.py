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

from n6datasources.collectors.darklist_de import DarklistDeBlCollector
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestDarklistDeBlCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = DarklistDeBlCollector

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
                [DarklistDeBlCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b"# darklist.de - blacklisted raw IPs\n"
                b"# generated on 21.04.2020 08:15\n"
                b"\n"
                b"1.1.1.0/24\n"
                b"2.2.2.0/24\n"
                b"3.3.3.0/24\n"
                b"4.4.4.4\n"
                b"5.5.5.5\n"
                b"6.6.6.6\n"
            ),
            expected_output=[
                call(
                    'darklist-de.bl',
                    (
                        b"# darklist.de - blacklisted raw IPs\n"
                        b"# generated on 21.04.2020 08:15\n"
                        b"\n"
                        b"1.1.1.0/24\n"
                        b"2.2.2.0/24\n"
                        b"3.3.3.0/24\n"
                        b"4.4.4.4\n"
                        b"5.5.5.5\n"
                        b"6.6.6.6\n"
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
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

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

from n6datasources.collectors.spamhaus import (
    SpamhausBotsCollector,
    SpamhausDropCollector,
    SpamhausEdropCollector,
)
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


class _BaseSpamhausCollectorTestCase(BaseCollectorTestCase):

    COLLECTOR_CLASS = None

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


@expand
class TestSpamhausBotsCollector(_BaseSpamhausCollectorTestCase):

    COLLECTOR_CLASS = SpamhausBotsCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [SpamhausBotsCollector]
                url=https://www.example.com
                cert=cert-pl
                api_key=abcdef123456
                download_retries=1
            ''',
            orig_data=(
                b'; Bots filtered by last 24 hours, prepared for EXAMPLE COMPANY on UTC = Mon Mar 20 10:30:19 2023\n'
                b'; Copyright \xc2\xa9 2023 The Spamhaus Project Ltd. All rights reserved.\n'
                b'; No re-distribution or public access allowed without Spamhaus permission.\n'
                b'; Fields description:\n'
                b';\n'
                b'; 1 - Infected IP\n'
                b'; 2 - ASN\n'
                b'; 3 - Country Code\n'
                b'; 4 - Lastseen Timestamp (in UTC)\n'
                b'; 5 - Bot Name\n'
                b';   Command & Control (C&C) information, if available:\n'
                b'; 6 - C&C Domain\n'
                b'; 7 - Remote IP (connecting to)\n'
                b'; 8 - Remote Port (connecting to)\n'
                b'; 9 - Local Port\n'
                b'; 10 - Protocol\n'
                b';   Additional fields may be added in the future without notice\n'
                b';\n'
                b'; ip, asn, country, lastseen, botname, domain, remote_ip, remote_port, local_port, protocol\n'
                b';\n'
                b'1.1.1.1,AS11111,PL,1679301488,example_name_1,,,25,16661,TCP\n'
                b'2.2.2.2,AS22222,PL,1679288166,example_name_2,,,25,40273,TCP\n'
                b'3.3.3.3,AS33333,PL,1679260357,example_name_3,,,25,26068,TCP\n'
                b'4.4.4.4,AS44444,PL,1679219256,example_name_4,,,25,30782,TCP\n'
                b'5.5.5.5,AS55555,PL,1679224062,example_name_5,,,25,19399,TCP\n'
                b'6.6.6.6,AS66666,PL,1679255968,example_name_6,,,25,33190,TCP\n'
            ),
            expected_output=[
                call(
                    'spamhaus.bots',
                    (
                        b'; Bots filtered by last 24 hours, prepared for EXAMPLE COMPANY on UTC = Mon Mar 20 10:30:19 2023\n'
                        b'; Copyright \xc2\xa9 2023 The Spamhaus Project Ltd. All rights reserved.\n'
                        b'; No re-distribution or public access allowed without Spamhaus permission.\n'
                        b'; Fields description:\n'
                        b';\n'
                        b'; 1 - Infected IP\n'
                        b'; 2 - ASN\n'
                        b'; 3 - Country Code\n'
                        b'; 4 - Lastseen Timestamp (in UTC)\n'
                        b'; 5 - Bot Name\n'
                        b';   Command & Control (C&C) information, if available:\n'
                        b'; 6 - C&C Domain\n'
                        b'; 7 - Remote IP (connecting to)\n'
                        b'; 8 - Remote Port (connecting to)\n'
                        b'; 9 - Local Port\n'
                        b'; 10 - Protocol\n'
                        b';   Additional fields may be added in the future without notice\n'
                        b';\n'
                        b'; ip, asn, country, lastseen, botname, domain, remote_ip, remote_port, local_port, protocol\n'
                        b';\n'
                        b'1.1.1.1,AS11111,PL,1679301488,example_name_1,,,25,16661,TCP\n'
                        b'2.2.2.2,AS22222,PL,1679288166,example_name_2,,,25,40273,TCP\n'
                        b'3.3.3.3,AS33333,PL,1679260357,example_name_3,,,25,26068,TCP\n'
                        b'4.4.4.4,AS44444,PL,1679219256,example_name_4,,,25,30782,TCP\n'
                        b'5.5.5.5,AS55555,PL,1679224062,example_name_5,,,25,19399,TCP\n'
                        b'6.6.6.6,AS66666,PL,1679255968,example_name_6,,,25,33190,TCP\n'
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'text/csv',
                        'headers': {},
                    },
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestSpamhausDropCollector(_BaseSpamhausCollectorTestCase):

    COLLECTOR_CLASS = SpamhausDropCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [SpamhausDropCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b'; Spamhaus DROP List 2023/03/20 - (c) 2023 The Spamhaus Project\n'
                b'; https://www.spamhaus.org/drop/drop.txt\n'
                b'; Last-Modified: Mon, 20 Mar 2023 10:06:14 GMT\n'
                b'; Expires: Mon, 20 Mar 2023 11:46:33 GMT\n'
                b'1.1.1.1/20 ; ABC111111\n'
                b'2.2.2.2/16 ; ABC222222\n'
                b'3.3.3.3/18 ; ABC333333\n'
                b'4.4.4.4/22 ; ABC444444\n'
            ),
            expected_output=[
                call(
                    'spamhaus.drop',
                    (
                        b'; Spamhaus DROP List 2023/03/20 - (c) 2023 The Spamhaus Project\n'
                        b'; https://www.spamhaus.org/drop/drop.txt\n'
                        b'; Last-Modified: Mon, 20 Mar 2023 10:06:14 GMT\n'
                        b'; Expires: Mon, 20 Mar 2023 11:46:33 GMT\n'
                        b'1.1.1.1/20 ; ABC111111\n'
                        b'2.2.2.2/16 ; ABC222222\n'
                        b'3.3.3.3/18 ; ABC333333\n'
                        b'4.4.4.4/22 ; ABC444444\n'
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
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


@expand
class TestSpamhausEdropCollector(_BaseSpamhausCollectorTestCase):

    COLLECTOR_CLASS = SpamhausEdropCollector

    @paramseq
    def cases():
        yield param(
            config_content='''
                [SpamhausEdropCollector]
                url=https://www.example.com
                download_retries=1
            ''',
            orig_data=(
                b'; Spamhaus EDROP List 2023/03/20 - (c) 2023 The Spamhaus Project'
                b'; https://www.spamhaus.org/drop/edrop.txt'
                b'; Last-Modified: Sat, 18 Mar 2023 12:49:39 GMT'
                b'; Expires: Tue, 21 Mar 2023 10:01:09 GMT'
                b'1.1.1.1/24 ; ABC111111\n'
                b'2.2.2.2/24 ; ABC222222\n'
                b'3.3.3.3/24 ; ABC333333\n'
                b'4.4.4.4/24 ; ABC444444\n'
            ),
            expected_output=[
                call(
                    'spamhaus.edrop',
                    (
                        b'; Spamhaus EDROP List 2023/03/20 - (c) 2023 The Spamhaus Project'
                        b'; https://www.spamhaus.org/drop/edrop.txt'
                        b'; Last-Modified: Sat, 18 Mar 2023 12:49:39 GMT'
                        b'; Expires: Tue, 21 Mar 2023 10:01:09 GMT'
                        b'1.1.1.1/24 ; ABC111111\n'
                        b'2.2.2.2/24 ; ABC222222\n'
                        b'3.3.3.3/24 ; ABC333333\n'
                        b'4.4.4.4/24 ; ABC444444\n'
                    ),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
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

# Copyright (c) 2021-2023 NASK. All rights reserved.

from unittest.mock import call

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.dataplane import (
    DataplaneDnsrdCollector,
    DataplaneDnsrdanyCollector,
    DataplaneDnsversionCollector,
    DataplaneSipinvitationCollector,
    DataplaneSipqueryCollector,
    DataplaneSipregistrationCollector,
    DataplaneSmtpdataCollector,
    DataplaneSmtpgreetCollector,
    DataplaneSshclientCollector,
    DataplaneSshpwauthCollector,
    DataplaneTelnetloginCollector,
    DataplaneVncrfbCollector,
)
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


class _BaseDataplaneCollectorTestCase(BaseCollectorTestCase):

    EXAMPLE_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'blacklist',
        'content_type': 'text/plain',
        'headers': {},
    }

    def _perform_test(self,
                      collector_class,
                      config_content,
                      orig_data,
                      expected_publish_output_calls,
                      **kwargs):

        self.patch_object(BaseDownloadingCollector, 'download', return_value=orig_data)
        collector = self.prepare_collector(collector_class, config_content=config_content)

        collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)


@expand
class TestDataplaneDnsrdCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneDnsrdCollector,
            config_content='''
                [DataplaneDnsrdCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.  \n"
                b"#\n"
                b"174      |  Example name 1   |  1.1.1.1   |  2021-05-20 20:17:02  |  dnsrd\n"
                b"1901     |  Example name 2   |  2.2.2.2   |  2021-05-18 00:17:22  |  dnsrd   \n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.dnsrd',

                    # body
                    (
                        b"# addresses seen in the current report.  \n"
                        b"#\n"
                        b"174      |  Example name 1   |  1.1.1.1   |  2021-05-20 20:17:02  |  dnsrd\n"
                        b"1901     |  Example name 2   |  2.2.2.2   |  2021-05-18 00:17:22  |  dnsrd   \n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneDnsrdanyCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneDnsrdanyCollector,
            config_content='''
                [DataplaneDnsrdanyCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.  \n"
                b"#\n"
                b"174      |  Example name 1   |  1.1.1.1   |  2021-05-20 20:17:02  |  dnsrdany\n"
                b"1901     |  Example name 2   |  2.2.2.2   |  2021-05-18 00:17:22  |  dnsrdany   \n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.dnsrdany',

                    # body
                    (
                        b"# addresses seen in the current report.  \n"
                        b"#\n"
                        b"174      |  Example name 1   |  1.1.1.1   |  2021-05-20 20:17:02  |  dnsrdany\n"
                        b"1901     |  Example name 2   |  2.2.2.2   |  2021-05-18 00:17:22  |  dnsrdany   \n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneDnsversionCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneDnsversionCollector,
            config_content='''
                [DataplaneDnsversionCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"174      |  Example name 1   |  1.1.1.1    |  2021-05-17 03:02:54  |  dnsversion\n"
                b"174      |  Example name 2   |  2.2.2.2    |  2021-05-17 13:24:57  |  dnsversion\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.dnsversion',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"174      |  Example name 1   |  1.1.1.1    |  2021-05-17 03:02:54  |  dnsversion\n"
                        b"174      |  Example name 2   |  2.2.2.2    |  2021-05-17 13:24:57  |  dnsversion\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSipinvitationCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSipinvitationCollector,
            config_content='''
                [DataplaneSipinvitationCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"8075    |  Example name     |  1.1.1.1   |  2021-05-19 10:39:59  |  sipinvitation\n"
                b"8075    |  Example name     |  2.2.2.2   |  2021-05-21 01:11:24  |  sipinvitation\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.sipinvitation',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"8075    |  Example name     |  1.1.1.1   |  2021-05-19 10:39:59  |  sipinvitation\n"
                        b"8075    |  Example name     |  2.2.2.2   |  2021-05-21 01:11:24  |  sipinvitation\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSipqueryCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSipqueryCollector,
            config_content='''
                [DataplaneSipqueryCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"3       |  Example name 1   |  1.1.1.1   |  2021-05-16 05:56:23  |  sipquery\n"
                b"174     |  Example name 2   |  2.2.2.2   |  2021-05-20 02:57:29  |  sipquery\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.sipquery',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"3       |  Example name 1   |  1.1.1.1   |  2021-05-16 05:56:23  |  sipquery\n"
                        b"174     |  Example name 2   |  2.2.2.2   |  2021-05-20 02:57:29  |  sipquery\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSipregistrationCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSipregistrationCollector,
            config_content='''
                [DataplaneSipregistrationCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"8075    |  Example name     |  1.1.1.1   |  2021-05-20 21:53:29  |  sipregistration\n"
                b"8075    |  Example name     |  2.2.2.2   |  2021-05-21 01:11:22  |  sipregistration\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.sipregistration',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"8075    |  Example name     |  1.1.1.1   |  2021-05-20 21:53:29  |  sipregistration\n"
                        b"8075    |  Example name     |  2.2.2.2   |  2021-05-21 01:11:22  |  sipregistration\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSmtpdataCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSmtpdataCollector,
            config_content='''
                [DataplaneSmtpdataCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"2116    |  Example name 1   |  1.1.1.1   |  2021-05-18 18:48:47  |  smtpdata\n"
                b"3329    |  Example name 2  |  2.2.2.2    |  2021-05-21 04:17:39  |  smtpdata \n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.smtpdata',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"2116    |  Example name 1   |  1.1.1.1   |  2021-05-18 18:48:47  |  smtpdata\n"
                        b"3329    |  Example name 2  |  2.2.2.2    |  2021-05-21 04:17:39  |  smtpdata \n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSmtpgreetCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSmtpgreetCollector,
            config_content='''
                [DataplaneSmtpgreetCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"174    |  Example name    |  1.1.1.1  |  2021-05-21 00:09:34  |  smtpgreet\n"
                b"174    |  Example name    |  2.2.2.2  |  2021-05-20 20:21:30  |  smtpgreet\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.smtpgreet',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"174    |  Example name    |  1.1.1.1  |  2021-05-21 00:09:34  |  smtpgreet\n"
                        b"174    |  Example name    |  2.2.2.2  |  2021-05-20 20:21:30  |  smtpgreet\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

@expand
class TestDataplaneSshclientCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSshclientCollector,
            config_content='''
                [DataplaneSshclientCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"3      |  Example name 1  |  1.1.1.1    |  2021-05-21 12:08:37  |  sshclient  \n"
                b"137    |  Example name 2  |  2.2.2.2    |  2021-05-19 23:51:08  |  sshclient\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.sshclient',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"3      |  Example name 1  |  1.1.1.1    |  2021-05-21 12:08:37  |  sshclient  \n"
                        b"137    |  Example name 2  |  2.2.2.2    |  2021-05-19 23:51:08  |  sshclient\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)


@expand
class TestDataplaneSshpwauthCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneSshpwauthCollector,
            config_content='''
                [DataplaneSshpwauthCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"3     |  Example name 1   |  1.1.1.1    |  2021-05-21 12:08:38  |  sshpwauth\n"
                b"137   |  Example name 2   |  2.2.2.2    |  2021-05-19 23:51:09  |  sshpwauth\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.sshpwauth',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"3     |  Example name 1   |  1.1.1.1    |  2021-05-21 12:08:38  |  sshpwauth\n"
                        b"137   |  Example name 2   |  2.2.2.2    |  2021-05-19 23:51:09  |  sshpwauth\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

@expand
class TestDataplaneTelnetloginCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneTelnetloginCollector,
            config_content='''
                [DataplaneTelnetloginCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"174   |  Example name      |  1.1.1.1   |  2021-05-15 23:41:50  |  telnetlogin\n"
                b"174   |  Example name      |  2.2.2.2   |  2021-05-17 14:20:24  |  telnetlogin\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.telnetlogin',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"174   |  Example name      |  1.1.1.1   |  2021-05-15 23:41:50  |  telnetlogin\n"
                        b"174   |  Example name      |  2.2.2.2   |  2021-05-17 14:20:24  |  telnetlogin\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

@expand
class TestDataplaneVncrfbCollector(_BaseDataplaneCollectorTestCase):

    @paramseq
    def cases(self):
        yield param(
            collector_class=DataplaneVncrfbCollector,
            config_content='''
                [DataplaneVncrfbCollector]
                url = https://www.example.com
            ''',
            orig_data=(
                b"# addresses seen in the current report.\n"
                b"#\n"
                b"3   |  Example name   |  1.1.1.1    |  2021-05-20 08:44:51  |  vncrfb\n"
                b"3   |  Example name   |  2.2.2.2    |  2021-05-21 09:23:27  |  vncrfb\n"
            ),
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'dataplane.vncrfb',

                    # body
                    (
                        b"# addresses seen in the current report.\n"
                        b"#\n"
                        b"3   |  Example name   |  1.1.1.1    |  2021-05-20 08:44:51  |  vncrfb\n"
                        b"3   |  Example name   |  2.2.2.2    |  2021-05-21 09:23:27  |  vncrfb\n"
                    ),

                    # prop_kwargs
                    self.EXAMPLE_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

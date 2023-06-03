# Copyright (c) 2023 NASK. All rights reserved.

from unittest.mock import (
    call,
    sentinel,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.zoneh import ZonehRssCollector
from n6datasources.collectors.base import BaseDownloadingCollector
from n6datasources.tests.collectors.test_base import BaseCollectorTestCase
from n6lib.common_helpers import OPSet
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


@expand
class TestZonehRssCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = ZonehRssCollector
    EXAMPLE_ORIG_DATA = (
        b'<rss version="2.0">'
        b'<channel>'
            b'<title>Zone-H.org Special Defacements</title>'
                b'<description>Latest special defacements published by Zone-H.org</description>'
                b'<link>http://www.zone-h.org</link>'
                b'<lastBuildDate>Thu, 14 Jul 16 07:47:45 +0000</lastBuildDate>'
                b'<generator>Zone-H</generator>'
                b'<item>'
                    b'<title><![CDATA[http://example1.com]]></title>'
                    b'<link><![CDATA[http://www.zone-h.org/mirror/id/...]]></link>'
                    b'<guid><![CDATA[http://www.zone-h.org/mirror/id/...]]></guid>'
                    b'<description><![CDATA[http://example1.com notified by ABCD]]></description>'
                    b'<pubDate>Tue, 10 Jan 2023 12:00:00 +0000</pubDate>'
                b'</item>'
                b'<item>'
                    b'<title><![CDATA[http://example2.com]]></title>'
                    b'<link><![CDATA[http://www.zone-h.org/mirror/id/... ]]></link>'
                    b'<guid><![CDATA[http://www.zone-h.org/mirror/id/... ]]></guid>'
                    b'<description><![CDATA[http://example2.com notified by ABCD]]></description>'
                    b'<pubDate>Tue, 10 Jan 2023 13:00:00 +0000</pubDate>'
                b'</item>'
            b'</channel>'
        b'</rss>'
    )

    EXPECTED_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'stream',
        'headers': {},
    }

    def _perform_test(self,
                      config_content,
                      orig_data,
                      initial_state,
                      expected_publish_output_calls,
                      expected_saved_state,
                      **kwargs):

        self.patch_object(BaseDownloadingCollector, 'download', return_value=orig_data)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content,
            initial_state=initial_state)

        collector.run_collection()

        self.assertEqual(self.saved_state, expected_saved_state)
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)


    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [ZonehRssCollector]
                url = https://www.example.com
                download_retries = 1
            ''',
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'zoneh.rss',

                    # body
                    (
                        b'['
                            b'["http://example1.com", "http://example1.com notified by ABCD", "Tue, 10 Jan 2023 12:00:00 +0000"], '
                            b'["http://example2.com", "http://example2.com notified by ABCD", "Tue, 10 Jan 2023 13:00:00 +0000"]'
                        b']'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state=OPSet(
                [
                    ('http://example1.com', 'http://example1.com notified by ABCD', 'Tue, 10 Jan 2023 12:00:00 +0000'),
                    ('http://example2.com', 'http://example2.com notified by ABCD', 'Tue, 10 Jan 2023 13:00:00 +0000'),
                ]
            ),
        ).label('No initial state')

        yield param(
            config_content='''
                [ZonehRssCollector]
                url = https://www.example.com
                download_retries = 1
            ''',
            initial_state=OPSet(
                [
                    ('http://example1.com', 'http://example1.com notified by ABCD', 'Tue, 10 Jan 2023 12:00:00 +0000')
                ]
            ),
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'zoneh.rss',
                    # body
                    (
                        b'[["http://example2.com", "http://example2.com notified by ABCD", "Tue, 10 Jan 2023 13:00:00 +0000"]]'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state=OPSet(
                [
                    ('http://example1.com', 'http://example1.com notified by ABCD', 'Tue, 10 Jan 2023 12:00:00 +0000'),
                    ('http://example2.com', 'http://example2.com notified by ABCD', 'Tue, 10 Jan 2023 13:00:00 +0000'),
                ],
            )
        ).label('Initial state - just 1 event')

        yield param(
            config_content='''
                [ZonehRssCollector]
                url = https://www.example.com
                download_retries = 1
            ''',
            initial_state=OPSet(
                [
                    ('http://example1.com', 'http://example1.com notified by ABCD', 'Tue, 10 Jan 2023 12:00:00 +0000'),
                    ('http://example2.com', 'http://example2.com notified by ABCD', 'Tue, 10 Jan 2023 13:00:00 +0000'),
                ],
            ),
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[],
            expected_saved_state=sentinel.NO_STATE
        ).label('Initial state with two events, no new data')


    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

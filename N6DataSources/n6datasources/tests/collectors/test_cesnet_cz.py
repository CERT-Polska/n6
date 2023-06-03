# Copyright (c) 2022-2023 NASK. All rights reserved.

import json
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

from n6datasources.collectors.cesnet_cz import (
    CesnetCzWardenCollector,
)
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestCesnetCzWardenCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = CesnetCzWardenCollector

    @paramseq
    def cases():
        # 0 events
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events": []},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    b'[]',
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )
        # 1 event
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events": [{"event": "test"}]},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    b'[{"event": "test"}]',
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )
        # 2 events
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events": [{"event": "test"}, {"event": "test"}]},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    b'[{"event": "test"}, {"event": "test"}]',
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )
        # 999 events
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events": [{"event": "test"}] * 999},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    json.dumps([{"event": "test"}] * 999).encode('utf-8'),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )
	# 1000 events
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events":  [{"event": "test"}] * 1000},
                {"lastid": 1927614083, "events": []},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    json.dumps([{"event": "test"}] * 1000).encode('utf-8'),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )
	# 1001 events
        yield param(
            config_content="""
                [CesnetCzWardenCollector]
                url=https://warden-hub.cesnet.cz/warden3/getEvents?nocat=Test
                key_file_path=/path/to/key.pem
                cert_file_path=/path/to/cert.pem
            """,
            downloaded_jsons=[
                {"lastid": 1927614083, "events": [{"event": "test"}] * 1000},
                {"lastid": 1927614083, "events": [{"event": "test"}]},
            ],
            expected_output=[
                call(
                    'cesnet-cz.warden',
                    json.dumps([{"event": "test"}] * 1001).encode('utf-8'),
                    {
                        'timestamp': ANY,
                        'message_id': ANY,
                        'type': 'file',
                        'content_type': 'application/json',
                        'headers': {},
                    },
                ),
            ]
        )

    @foreach(cases)
    def test(self,
             config_content,
             downloaded_jsons,
             expected_output):
        collector = self._mocked_collector(config_content, downloaded_jsons)
        collector.run_collection()
        self.assertEqual(
            self.publish_output_mock.mock_calls,
            expected_output)

    def _mocked_collector(self, config_content, downloaded_jsons):
        self.patch_object(CesnetCzWardenCollector,
                          '_download_data',
                          side_effect=downloaded_jsons)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content)
        return collector

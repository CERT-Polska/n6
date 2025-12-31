# Copyright (c) 2025 NASK. All rights reserved.

import json
from unittest.mock import (
    call,
    sentinel,
)
from n6datasources.collectors.base import BaseDownloadingCollector
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.tu_dresden_de import TuDresdenDeResolversCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestTuDresdenDeResolversCollector(BaseCollectorTestCase):
    COLLECTOR_CLASS = TuDresdenDeResolversCollector

    EXAMPLE_ORIG_DATA = b"""{
    "metaData": {
        "total": 4
    },
    "dnsEntries": [
        {
        "protocol": "udp",
        "queried_ip": "10.10.10.10",
        "replying_ip": "10.10.10.10",
        "backend_resolver": "10.10.10.10",
        "timestamp_request": "2025-08-02T08:41:29.900268",
        "resolver_type": "Forwarder",
        "queried_ip_country": "POL",
        "replying_ip_country": "POL",
        "queried_ip_asn": 1111,
        "replying_ip_asn": 1111,
        "queried_ip_prefix": "10.10.0.0/16",
        "replying_ip_prefix": "10.10.0.0/16",
        "queried_ip_org": "Example org 1",
        "replying_ip_org": "Example org 1",
        "backend_resolver_country": "POL",
        "backend_resolver_asn": 11111,
        "backend_resolver_prefix": "10.0.0.0/8",
        "backend_resolver_org": "Example org 1",
        "scan_date": "2025-08-02"
        },
        {
        "protocol": "udp",
        "queried_ip": "20.20.20.20",
        "replying_ip": "20.20.20.20",
        "backend_resolver": "20.20.20.20",
        "timestamp_request": "2025-08-02T08:41:28.305947",
        "resolver_type": "Forwarder",
        "queried_ip_country": "POL",
        "replying_ip_country": "POL",
        "queried_ip_asn": 22222,
        "replying_ip_asn": 22222,
        "queried_ip_prefix": "20.20.0.0/16",
        "replying_ip_prefix": "20.20.0.0/16",
        "queried_ip_org": "Example org 2",
        "replying_ip_org": "Example org 2",
        "backend_resolver_country": "POL",
        "backend_resolver_asn": 11111,
        "backend_resolver_prefix": "20.0.0.0/8",
        "backend_resolver_org": "Example Resolver org",
        "scan_date": "2025-08-02"
        },
        {
        "protocol": "udp",
        "queried_ip": "30.30.30.30",
        "replying_ip": "30.30.30.30",
        "backend_resolver": "30.30.30.30",
        "timestamp_request": "2025-08-02T08:41:26.121771",
        "resolver_type": "Forwarder",
        "queried_ip_country": "POL",
        "replying_ip_country": "POL",
        "queried_ip_asn": 33333,
        "replying_ip_asn": 33333,
        "queried_ip_prefix": "30.30.0.0/16",
        "replying_ip_prefix": "30.30.0.0/16",
        "queried_ip_org": "Example org 3",
        "replying_ip_org": "Example org 3",
        "backend_resolver_country": "POL",
        "backend_resolver_asn": 11111,
        "backend_resolver_prefix": "30.0.0.0/8",
        "backend_resolver_org": "Example Resolver org",
        "scan_date": "2025-08-02"
        },
        {
        "protocol": "udp",
        "queried_ip": "40.40.40.40",
        "replying_ip": "40.40.40.40",
        "backend_resolver": "40.40.40.40",
        "timestamp_request": "2025-08-02T08:41:25.7719",
        "resolver_type": "Forwarder",
        "queried_ip_country": "POL",
        "replying_ip_country": "POL",
        "queried_ip_asn": 444444,
        "replying_ip_asn": 444444,
        "queried_ip_prefix": "40.40.0.0/16",
        "replying_ip_prefix": "40.40.0.0/16",
        "queried_ip_org": "Example org 4",
        "replying_ip_org": "Example org 4",
        "backend_resolver_country": "POL",
        "backend_resolver_asn": 11111,
        "backend_resolver_prefix": "40.0.0.0/8",
        "backend_resolver_org": "Example Resolver org",
        "scan_date": "2025-08-02"
        }
    ],
    "statusCode": {
        "message": "Success",
        "code": 0
    }
    }
"""
    RAW_EXAMPLE_OUTPUT_BODY = [
        {
            "protocol": "udp",
            "queried_ip": "10.10.10.10",
            "replying_ip": "10.10.10.10",
            "backend_resolver": "10.10.10.10",
            "timestamp_request": "2025-08-02T08:41:29.900268",
            "resolver_type": "Forwarder",
            "queried_ip_country": "POL",
            "replying_ip_country": "POL",
            "queried_ip_asn": 1111,
            "replying_ip_asn": 1111,
            "queried_ip_prefix": "10.10.0.0/16",
            "replying_ip_prefix": "10.10.0.0/16",
            "queried_ip_org": "Example org 1",
            "replying_ip_org": "Example org 1",
            "backend_resolver_country": "POL",
            "backend_resolver_asn": 11111,
            "backend_resolver_prefix": "10.0.0.0/8",
            "backend_resolver_org": "Example org 1",
            "scan_date": "2025-08-02",
        },
        {
            "protocol": "udp",
            "queried_ip": "20.20.20.20",
            "replying_ip": "20.20.20.20",
            "backend_resolver": "20.20.20.20",
            "timestamp_request": "2025-08-02T08:41:28.305947",
            "resolver_type": "Forwarder",
            "queried_ip_country": "POL",
            "replying_ip_country": "POL",
            "queried_ip_asn": 22222,
            "replying_ip_asn": 22222,
            "queried_ip_prefix": "20.20.0.0/16",
            "replying_ip_prefix": "20.20.0.0/16",
            "queried_ip_org": "Example org 2",
            "replying_ip_org": "Example org 2",
            "backend_resolver_country": "POL",
            "backend_resolver_asn": 11111,
            "backend_resolver_prefix": "20.0.0.0/8",
            "backend_resolver_org": "Example Resolver org",
            "scan_date": "2025-08-02",
        },
        {
            "protocol": "udp",
            "queried_ip": "30.30.30.30",
            "replying_ip": "30.30.30.30",
            "backend_resolver": "30.30.30.30",
            "timestamp_request": "2025-08-02T08:41:26.121771",
            "resolver_type": "Forwarder",
            "queried_ip_country": "POL",
            "replying_ip_country": "POL",
            "queried_ip_asn": 33333,
            "replying_ip_asn": 33333,
            "queried_ip_prefix": "30.30.0.0/16",
            "replying_ip_prefix": "30.30.0.0/16",
            "queried_ip_org": "Example org 3",
            "replying_ip_org": "Example org 3",
            "backend_resolver_country": "POL",
            "backend_resolver_asn": 11111,
            "backend_resolver_prefix": "30.0.0.0/8",
            "backend_resolver_org": "Example Resolver org",
            "scan_date": "2025-08-02",
        },
        {
            "protocol": "udp",
            "queried_ip": "40.40.40.40",
            "replying_ip": "40.40.40.40",
            "backend_resolver": "40.40.40.40",
            "timestamp_request": "2025-08-02T08:41:25.7719",
            "resolver_type": "Forwarder",
            "queried_ip_country": "POL",
            "replying_ip_country": "POL",
            "queried_ip_asn": 444444,
            "replying_ip_asn": 444444,
            "queried_ip_prefix": "40.40.0.0/16",
            "replying_ip_prefix": "40.40.0.0/16",
            "queried_ip_org": "Example org 4",
            "replying_ip_org": "Example org 4",
            "backend_resolver_country": "POL",
            "backend_resolver_asn": 11111,
            "backend_resolver_prefix": "40.0.0.0/8",
            "backend_resolver_org": "Example Resolver org",
            "scan_date": "2025-08-02",
        },
    ]

    EXAMPLE_OUTPUT_BODY = json.dumps(RAW_EXAMPLE_OUTPUT_BODY).encode("utf-8")
    SECOND_EXAMPLE_OUTPUT_BODY = json.dumps(RAW_EXAMPLE_OUTPUT_BODY[:2]).encode("utf-8")


    EXPECTED_PROP_KWARGS = {
        "message_id": AnyMatchingRegex(r"\A[0-9a-f]{32}\Z"),
        "timestamp": AnyInstanceOf(int),
        "type": "file",
        "headers": {},
        "content_type": "application/json",
    }

    def _perform_test(self,
                      config_content,
                      initial_state,
                      orig_data,
                      expected_output,
                      **kwargs):

        self.patch_object(BaseDownloadingCollector, "download", return_value=orig_data)
        collector = self.prepare_collector(
            self.COLLECTOR_CLASS, config_content=config_content, initial_state=initial_state
        )

        collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls, expected_output)

    @paramseq
    def cases(cls):
        # all data in on one page
        yield param(
            config_content="""
                [TuDresdenDeResolversCollector]
                url=https://odns-data.netd.cs.tu-dresden.de/api/v2/ODNSQuery/GetDnsEntries
                api_key=example_key
                entries_per_page=99999
                queried_protocol=UDP
                quired_ip_country=POL
                sort_field=timestamp_request
                download_retries=3
            """,
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_output=[
                call(
                    # routing_key
                    "tu-dresden-de.resolvers",
                    # body
                    (cls.EXAMPLE_OUTPUT_BODY),
                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
        )
        # data on more than one page
        yield param(
            config_content="""
                [TuDresdenDeResolversCollector]
                url=https://odns-data.netd.cs.tu-dresden.de/api/v2/ODNSQuery/GetDnsEntries
                api_key=example_key
                entries_per_page=4
                queried_protocol=UDP
                quired_ip_country=POL
                sort_field=timestamp_request
                download_retries=3
            """,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            initial_state={
                'newest_event_stored_time': '2025-08-02T08:41:26'
            },
            expected_output=[
                call(
                    # routing_key
                    "tu-dresden-de.resolvers",
                    # body
                    (cls.SECOND_EXAMPLE_OUTPUT_BODY),
                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
        )
        yield param(
            config_content="""
                [TuDresdenDeResolversCollector]
                url=https://odns-data.netd.cs.tu-dresden.de/api/v2/ODNSQuery/GetDnsEntries
                api_key=example_key
                entries_per_page=2
                queried_protocol=UDP
                quired_ip_country=POL
                sort_field=timestamp_request
                download_retries=3
            """,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            initial_state=sentinel.NO_STATE,
            expected_output=[
                call(
                    # routing_key
                    "tu-dresden-de.resolvers",
                    # body
                    (cls.EXAMPLE_OUTPUT_BODY),
                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

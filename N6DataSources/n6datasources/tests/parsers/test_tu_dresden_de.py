# Copyright (c) 2025 NASK. All rights reserved.

import json
import unittest
from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.tu_dresden_de import TuDresdenDeResolversParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestTuDresdenDeResolversParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'tu-dresden-de.resolvers'
    PARSER_CLASS = TuDresdenDeResolversParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'low',
        'category': 'amplifier',
        'proto': 'udp',
        'dport': 53,
    }

    raw_events = RAW_EXAMPLE_OUTPUT_BODY = [
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
        },
    ]

    OBTAINED_DATA = json.dumps(RAW_EXAMPLE_OUTPUT_BODY).encode("utf-8")

    def cases(self):
        yield (
            self.OBTAINED_DATA,
            [
                {
                    'time': '2025-08-02 08:41:29',
                    'address': [{"ip": "10.10.10.10"}],
                    'name': 'resolver_type: Forwarder',
                    'additional_data': 'replying_ip: 10.10.10.10'
                },
                {
                    'time': '2025-08-02 08:41:28',
                    'address': [{"ip": "20.20.20.20"}],
                    'name': 'resolver_type: Forwarder',
                    'additional_data': 'replying_ip: 20.20.20.20'
                },
                {
                    'time': '2025-08-02 08:41:26',
                    'address': [{"ip": "30.30.30.30"}],
                    'name': 'resolver_type: Forwarder',
                    'additional_data': 'replying_ip: 30.30.30.30'
                },
                {
                    'time': '2025-08-02 08:41:25',
                    'address': [{"ip": "40.40.40.40"}],
                    'name': 'resolver_type: Forwarder',
                    'additional_data': 'replying_ip: 40.40.40.40'
                },
            ]
        )
        yield (
            b'INVALID_DATA',
            ValueError
        )

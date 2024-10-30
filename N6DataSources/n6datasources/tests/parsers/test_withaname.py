# Copyright (c) 2024 NASK. All rights reserved.

import json
import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.withaname import WithanameDdosiaParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestWithanameDdosiaParser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = "withaname.ddosia"
    PARSER_CLASS = WithanameDdosiaParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "need-to-know",
        "confidence": "low",
        "category": "dos-victim",
    }

    RAW_CSV_FILE = (
        "host,ip,type,method,port,use_ssl,path\r\n"
        "www.example1.com,1.1.1.1,http2,GET,443,True,/example?example-s=1\r\n"
        "www.example2.com,2.2.2.2,http,GET,443,True,/example/page/2/\r\n"
        "www.example3.com,3.3.3.3,http,GET,443,True,example/\r\n"
        "www.example4.com,4.4.4.4,tcp,PING,443,True,\r\n"
    )

    RAW_CSV_FILE_WITH_INVALID_PORT = (
        "host,ip,type,method,port,use_ssl,path\r\n"
        "www.example1.com,1.1.1.1,http2,GET,7586456,True,/example?example-s=1\r\n"
        "www.example2.com,2.2.2.2,http,GET,44456456453,True,/example/page/2/\r\n"
        "www.example3.com,3.3.3.3,http,GET,444564563,True,example/\r\n"
        "www.example4.com,4.4.4.4,tcp,PING,4456443,True,\r\n"
    )

    def cases(self):
        yield (
            json.dumps(
                {
                    'csv_file': self.RAW_CSV_FILE,
                    'datetime': '2024-08-26T09:55:03'
                },
            ).encode(),
            [
                {
                    "address": [{"ip": "1.1.1.1"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example1.com",
                    "dport": 443,
                    "proto": "tcp",
                    "name": "DDoSia victim (http2 GET)",
                },
                {
                    "address": [{"ip": "2.2.2.2"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example2.com",
                    "dport": 443,
                    "proto": "tcp",
                    "name": "DDoSia victim (http GET)",
                },
                {
                    "address": [{"ip": "3.3.3.3"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example3.com",
                    "dport": 443,
                    "proto": "tcp",
                    "name": "DDoSia victim (http GET)",
                },
                {
                    "address": [{"ip": "4.4.4.4"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example4.com",
                    "dport": 443,
                    "proto": "icmp",
                    "name": "DDoSia victim (tcp PING)",
                },
            ]
        )

        yield (
            json.dumps(
                {
                    'csv_file': self.RAW_CSV_FILE_WITH_INVALID_PORT,
                    'datetime': '2024-08-26T09:55:03'
                },
            ).encode(),
            [
                {
                    "address": [{"ip": "1.1.1.1"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example1.com",
                    "proto": "tcp",
                    "name": "DDoSia victim (http2 GET)",
                },
                {
                    "address": [{"ip": "2.2.2.2"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example2.com",
                    "proto": "tcp",
                    "name": "DDoSia victim (http GET)",
                },
                {
                    "address": [{"ip": "3.3.3.3"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example3.com",
                    "proto": "tcp",
                    "name": "DDoSia victim (http GET)",
                },
                {
                    "address": [{"ip": "4.4.4.4"}],
                    "time": "2024-08-26 09:55:03",
                    "fqdn": "www.example4.com",
                    "proto": "icmp",
                    "name": "DDoSia victim (tcp PING)",
                },
            ]
        )

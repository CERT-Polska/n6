# Copyright (c) 2014-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.abuse_ch import (
    AbuseChFeodoTracker202110Parser,
    AbuseChSslBlacklist201902Parser,
    AbuseChUrlhausUrls202001Parser,
    AbuseChUrlhausPayloadsUrlsParser,
)
from n6datasources.parsers.base import BaseParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestAbuseChFeodotracker202110Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.feodotracker'
    PARSER_RAW_FORMAT_VERSION_TAG  = '202110'
    PARSER_CLASS = AbuseChFeodoTracker202110Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'cnc'
    }

    def cases(self):
        yield (
            b'2019-05-27 13:36:27,0.0.0.1,447,online,2019-05-28,TrickBot\n'
            b'this, is, one, very, wrong, line\n'
            b'2019-05-25 01:30:36,0.0.0.1,443,online,2019-05-27,Heodo\n'
            b'2019-05-16 19:43:27,0.0.0.1,8080,online,2019-05-22,Heodo\n',
            [
                {
                    'name': 'trickbot',
                    'address': [{'ip': '0.0.0.1'}],
                    'dport': 447,
                    'time': '2019-05-27 13:36:27',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.1'}],
                    'dport': 443,
                    'time': '2019-05-25 01:30:36',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.1'}],
                    'dport': 8080,
                    'time': '2019-05-16 19:43:27',
                },
            ]
        )

        yield (
            b'INVALID_DATA',
            ValueError
        )


class TestAbuseChSslBlacklists201902Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist'
    PARSER_RAW_FORMAT_VERSION_TAG = '201902'
    PARSER_CLASS = AbuseChSslBlacklist201902Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def cases(self):
        yield (
            b'2019-02-26 15:42:09,1111c502625cec0a0211714f8d5c2972868963d4,Gozi C&C\n'
            b'this_line,should_not,be_here\n'
            b'2019-02-26 06:40:29,2222ad74167f5b27d47a4f629d11aa187710fd41,Malware C&C\n',
        [
            {
                'category': 'cnc',
                'restriction': 'public',
                'confidence': 'low',
                'name': 'gozi c&c',
                'x509fp_sha1': '1111c502625cec0a0211714f8d5c2972868963d4',
                'time': '2019-02-26 15:42:09',
            },
            {
                'category': 'cnc',
                'restriction': 'public',
                'confidence': 'low',
                'name': 'malware c&c',
                'x509fp_sha1': '2222ad74167f5b27d47a4f629d11aa187710fd41',
                'time': '2019-02-26 06:40:29',
            }

        ])

        yield (
            b'asdasd',
            ValueError
        )

class TestAbuseChUrlhausUrls202001Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.urlhaus-urls'
    PARSER_RAW_FORMAT_VERSION_TAG = '202001'
    PARSER_CLASS = AbuseChUrlhausUrls202001Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'malurl',
    }

    def cases(self):
        # Valid JSON without signature, we expect to yield one event.
        yield (b'''
        [{
            "dateadded": "2020-01-01 01:00:00",
            "url_status": "online",
            "tags": "None",
            "url": "https://example-1.com",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/000000/",
            "reporter": "ExampleNick_1",
            "threat": "malware_download",
            "url_info_from_api": {
                "urlhaus_reference": "https://urlhaus.abuse.ch/url/000000/",
                "threat": "malware_download",
                "larted": "true",
                "reporter": "ExampleNick_1",
                "url": "https://example_1.com",
                "tags": [
                    "elf",
                    "Mozi"
                ],
                "blacklists": {
                    "surbl": "not listed",
                    "gsb": "not listed",
                    "spamhaus_dbl": "not listed"
                },
                "id": "111111",
                "host": "1.1.1.1",
                "payloads": [
                    {
                        "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/a00a00aa0aa0a0a00aaa0a00a0a00a00a00a000a0a00000a0a0a0a00a0aaa0a0/",
                        "file_type": "elf",
                        "filename": null,
                        "response_md5": "1a111111a1aa11a111111aa11a111aa1",
                        "response_sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1",
                        "response_size": "95268",
                        "signature": null,
                        "firstseen": "2020-01-20",
                        "virustotal": {
                            "link": "https://www.virustotal.com/file/a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1/analysis/111111111111/",
                            "percent": "61.02",
                            "result": "36 / 59"
                        }
                    }
                ],
                "url_status": "online",
                "takedown_time_seconds": null,
                "date_added": "2020-01-01 00:00:00 UTC",
                "query_status": "ok"
            },
            "url_id": "111111"
        }]''',
               [
                   {
                       "time": "2020-01-01 01:00:00",
                       "url": "https://example-1.com",
                       "md5": "1a111111a1aa11a111111aa11a111aa1",
                       "sha256": "a11a11aa1aa1a1a11aaa1a11a1a11a11a11a111a1a11111a1a1a1a11a1aaa1a1",
                   }
               ])

        # Valid JSON with provided signature, we expect to yield one event.
        yield (b'''
        [{
            "dateadded": "2020-02-02 01:00:00",
            "url_status": "online",
            "tags": "None",
            "url": "https://example-2.com",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/222222/",
            "reporter": "ExampleNick_2",
            "threat": "malware_download",
            "url_info_from_api": {
                "urlhaus_reference": "https://urlhaus.abuse.ch/url/222222/",
                "threat": "malware_download",
                "larted": "true",
                "reporter": "ExampleNick_2",
                "url": "http://example-2.com",
                "tags": [
                    "elf",
                    "Mozi"
                ],
                "blacklists": {
                    "surbl": "not listed",
                    "gsb": "not listed",
                    "spamhaus_dbl": "not listed"
                },
                "id": "222222",
                "host": "2.2.2.2",
                "payloads": [
                    {
                        "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2/",
                        "file_type": "elf",
                        "filename": null,
                        "response_md5": "2b222222b2bb22b222222bb22b222bb2",
                        "response_sha256": "b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2",
                        "response_size": "95268",
                        "signature": "Example_Signature_2",
                        "firstseen": "2020-01-20",
                        "virustotal": {
                            "link": "https://www.virustotal.com/file/b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2/analysis/222222222222/",
                            "percent": "61.02",
                            "result": "36 / 59"
                        }
                    }
                ],
                "url_status": "online",
                "takedown_time_seconds": null,
                "date_added": "2020-01-01 00:00:00 UTC",
                "query_status": "ok"
            },
            "url_id": "222222"
        }]''',
               [
                   {
                       "time": "2020-02-02 01:00:00",
                       "url": "https://example-2.com",
                       "md5": "2b222222b2bb22b222222bb22b222bb2",
                       "sha256": "b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2",
                       "name": "example_signature_2"
                   }
               ])

        # Valid JSON with provided filename, we expect to yield one event.
        yield (b'''
                [{
                    "dateadded": "2020-02-02 01:00:00",
                    "url_status": "online",
                    "tags": "None",
                    "url": "https://example-2.com",
                    "urlhaus_link": "https://urlhaus.abuse.ch/url/222222/",
                    "reporter": "ExampleNick_2",
                    "threat": "malware_download",
                    "url_info_from_api": {
                        "urlhaus_reference": "https://urlhaus.abuse.ch/url/222222/",
                        "threat": "malware_download",
                        "larted": "true",
                        "reporter": "ExampleNick_2",
                        "url": "http://example-2.com",
                        "tags": [
                            "elf",
                            "Mozi"
                        ],
                        "blacklists": {
                            "surbl": "not listed",
                            "gsb": "not listed",
                            "spamhaus_dbl": "not listed"
                        },
                        "id": "222222",
                        "host": "2.2.2.2",
                        "payloads": [
                            {
                                "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2/",
                                "file_type": "elf",
                                "filename": "Example_Filename_2",
                                "response_md5": "2b222222b2bb22b222222bb22b222bb2",
                                "response_sha256": "b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2",
                                "response_size": "95268",
                                "signature": null,
                                "firstseen": "2020-01-20",
                                "virustotal": {
                                    "link": "https://www.virustotal.com/file/b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2/analysis/222222222222/",
                                    "percent": "61.02",
                                    "result": "36 / 59"
                                }
                            }
                        ],
                        "url_status": "online",
                        "takedown_time_seconds": null,
                        "date_added": "2020-01-01 00:00:00 UTC",
                        "query_status": "ok"
                    },
                    "url_id": "222222"
                }]''',
               [
                   {
                       "time": "2020-02-02 01:00:00",
                       "url": "https://example-2.com",
                       "md5": "2b222222b2bb22b222222bb22b222bb2",
                       "sha256": "b22b22bb2bb2b2b22bbb2b22b2b22b22b22b222b2b22222b2b2b2b22b2bbb2b2",
                       "filename": "Example_Filename_2"
                   }
               ])

        # Valid JSON with two elements in `['url_info_from_api']['payloads']` list.
        # We expect to yield two events.
        yield (b'''
        [{
            "dateadded": "2020-03-04 01:00:00",
            "url_status": "online",
            "tags": "None",
            "url": "https://example-3-4.com",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/333444/",
            "reporter": "ExampleNick_3",
            "threat": "malware_download",
            "url_info_from_api": {
                "urlhaus_reference": "https://urlhaus.abuse.ch/url/333444/",
                "threat": "malware_download",
                "larted": "true",
                "reporter": "ExampleNick_3/ExampleNick_4",
                "url": "http://example-3-4.com",
                "tags": [
                    "elf",
                    "Mozi"
                ],
                "blacklists": {
                    "surbl": "not listed",
                    "gsb": "not listed",
                    "spamhaus_dbl": "not listed"
                },
                "id": "333444",
                "host": "3.3.4.4",
                "payloads": [
                    {
                        "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/c33c33cc3cc3c3c33ccc3c33c3c33c33c33c333c3c33333c3c3c3c33c3ccc3c3/",
                        "file_type": "elf",
                        "filename": null,
                        "response_md5": "3c333333c3cc33c333333cc33c333cc3",
                        "response_sha256": "c33c33cc3cc3c3c33ccc3c33c3c33c33c33c333c3c33333c3c3c3c33c3ccc3c3",
                        "response_size": "95268",
                        "signature": "Example_Signature_3",
                        "firstseen": "2020-01-20",
                        "virustotal": {
                            "link": "https://www.virustotal.com/file/c33c33cc3cc3c3c33ccc3c33c3c33c33c33c333c3c33333c3c3c3c33c3ccc3c3/analysis/222222222222/",
                            "percent": "61.02",
                            "result": "36 / 59"
                        }
                    },
                    {
                        "urlhaus_download": "https://urlhaus-api.abuse.ch/v1/download/d44d44dd4dd4d4d44ddd4d44d4d44d44d44d444d4d44444d4d4d4d44d4ddd4d4/",
                        "file_type": "elf",
                        "filename": null,
                        "response_md5": "4d444444d4dd44d444444dd44d444dd4",
                        "response_sha256": "d44d44dd4dd4d4d44ddd4d44d4d44d44d44d444d4d44444d4d4d4d44d4ddd4d4",
                        "response_size": "95268",
                        "signature": "Example_Signature_4",
                        "firstseen": "2020-01-20",
                        "virustotal": {
                            "link": "https://www.virustotal.com/file/d44d44dd4dd4d4d44ddd4d44d4d44d44d44d444d4d44444d4d4d4d44d4ddd4d4/analysis/222222222222/",
                            "percent": "61.02",
                            "result": "36 / 59"
                        }
                    }
                ],
                "url_status": "online",
                "takedown_time_seconds": null,
                "date_added": "2020-01-01 00:00:00 UTC",
                "query_status": "ok"
            },
            "url_id": "333444"
        }]''',
               [
                   {
                       "time": "2020-03-04 01:00:00",
                       "url": "https://example-3-4.com",
                       "md5": "3c333333c3cc33c333333cc33c333cc3",
                       "sha256": "c33c33cc3cc3c3c33ccc3c33c3c33c33c33c333c3c33333c3c3c3c33c3ccc3c3",
                       "name": "example_signature_3"
                   },
                   {
                       "time": "2020-03-04 01:00:00",
                       "url": "https://example-3-4.com",
                       "md5": "4d444444d4dd44d444444dd44d444dd4",
                       "sha256": "d44d44dd4dd4d4d44ddd4d44d4d44d44d44d444d4d44444d4d4d4d44d4ddd4d4",
                       "name": "example_signature_4"
                   }
               ])

        # Valid JSON with empty `['url_info_from_api']['payloads']` list.
        # We expect to yield one event without `payload_info` (just time + url).
        yield (b'''
        [{
            "dateadded": "2020-05-05 01:00:00",
            "url_status": "online",
            "tags": "None",
            "url": "https://example-5.com",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/555555/",
            "reporter": "ExampleNick_5",
            "threat": "malware_download",
            "url_info_from_api": {
                "urlhaus_reference": "https://urlhaus.abuse.ch/url/555555/",
                "threat": "malware_download",
                "larted": "true",
                "reporter": "ExampleNick_5",
                "url": "http://example-5.com",
                "tags": [
                    "elf",
                    "Mozi"
                ],
                "blacklists": {
                    "surbl": "not listed",
                    "gsb": "not listed",
                    "spamhaus_dbl": "not listed"
                },
                "id": "555555",
                "host": "5.5.5.5",
                "payloads": [],
                "url_status": "online",
                "takedown_time_seconds": null,
                "date_added": "2020-01-01 00:00:00 UTC",
                "query_status": "ok"
            },
            "url_id": "555555"
        }]''',
               [

                   {
                       "time": "2020-05-05 01:00:00",
                       "url": "https://example-5.com",
                   }
               ])

        # Valid JSON with empty api response (url id exists in csv
        # but there is no data about that url in api) - we expect
        # to yield one event with only `time` and `url` keys.
        yield (b'''
        [{
            "dateadded": "2020-06-06 01:00:00",
            "url_status": "online",
            "tags": "None",
            "url": "https://example-6.com",
            "urlhaus_link": "https://urlhaus.abuse.ch/url/6666666666666666666666666666666/",
            "reporter": "ExampleNick_5",
            "threat": "malware_download",
            "url_info_from_api": {
                 "query_status": "no_results"
             },
            "url_id": "6666666666666666666666666666666"
        }]''',
               [
                   {
                       "time": "2020-06-06 01:00:00",
                       "url": "https://example-6.com",
                   }
               ])

        yield (
            b'Invalid_JSON',
            ValueError
        )


class TestAbuseChUrlhausPayloadsUrlsParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.urlhaus-payloads-urls'
    PARSER_CLASS = AbuseChUrlhausPayloadsUrlsParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'malurl',
    }

    def cases(self):
        yield (
            b'"2020-01-09 14:00:00","http://www.example1.com","exe","111a1111a111aa1a11a11111aa111111","1a1a11aa11a1a11aa11a1111111aaaaaaaaaaaaaa111111a1a1a1a1a1a1a1a11","None"\n'
            b'"this is", "wrong", "line", "and", "should", "not_be_valid"\n'
            b'"2020-01-09 15:00:00","http://www.example2.com","exe","222b2222b222bb2b22b22222bb222222","2b2b22bb22b2b22bb22b2222222bbbbbbbbbbbbbb222222b2b2b2b2b2b2b2b22","Example_Name_1"',
            [
                {
                    'url': 'http://www.example1.com',
                    'time': '2020-01-09 14:00:00',
                    'md5': '111a1111a111aa1a11a11111aa111111',
                    'sha256': '1a1a11aa11a1a11aa11a1111111aaaaaaaaaaaaaa111111a1a1a1a1a1a1a1a11',
                },
                {
                    'url': 'http://www.example2.com',
                    'time': '2020-01-09 15:00:00',
                    'md5': '222b2222b222bb2b22b22222bb222222',
                    'sha256': '2b2b22bb22b2b22bb22b2222222bbbbbbbbbbbbbb222222b2b2b2b2b2b2b2b22',
                    'name': 'example_name_1',
                },
            ]
        )
        yield (
            b'"this", "is", "invalid", "data", "to", "raise", "Value", "Error"',
            ValueError
        )

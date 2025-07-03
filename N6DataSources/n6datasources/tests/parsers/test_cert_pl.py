# Copyright (c) 2020-2025 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.cert_pl import (
    CertPlShieldParser,
    CertPlShield202505Parser,
)
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestCertPlShieldParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'cert-pl.shield'
    PARSER_CLASS = CertPlShieldParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'high',
        'category': 'phish',
    }

    def cases(self):
        yield (
            # `time` to be converted to UTC from CET
            # ("winter time" in the "Europe/Warsaw" timezone):
            b'8\texample_8.com\t2020-10-25T03:00:00\n'

            # `time` to be converted to UTC from the "CEST-or-CET?" ambiguity hour
            # (ambiguous times -> resolved in favor of the later variant):
            b'7\texample_7.com\t2020-10-25T02:59:59\n'
            b'6\texample_6.com\t2020-10-25T02:00:00\n'

            # `time` to be converted to UTC from CEST
            # ("summer time" in the "Europe/Warsaw" timezone):
            b'5\texample_5.com\t2020-10-25T01:59:59\n'
            b'4\texample_4.com\t2020-06-03T13:00:00\n'
            b'3\texample_3.com\t2020-06-03T12:00:00\n'
            b'2\texample_2.com\t2020-06-02T13:00:00\n'
            b'1\texample_1.com\t2020-06-02T12:00:00\n'

            # `time` *not* to be converted to UTC from values that do
            # not make sense (i.e., do not exist in the CEST and CET
            # timezones) -> so these rows will be **skipped** (!):
            b'0\texample_0b.com\t2020-03-29T02:59:59\n'
            b'0\texample_0a.com\t2020-03-29T02:00:30'
            ,
            [
                # `time` converted to UTC from CET
                # ("winter time" in the "Europe/Warsaw" timezone):
                dict(
                    time="2020-10-25 02:00:00",
                    fqdn="example_8.com",
                ),

                # `time` converted to UTC from the "CEST-or-CET?" ambiguity hour
                # (ambiguous times -> resolved in favor of the later variant):
                dict(
                    time="2020-10-25 01:59:59",
                    fqdn="example_7.com",
                ),
                dict(
                    time="2020-10-25 01:00:00",
                    fqdn="example_6.com",
                ),

                # `time` converted to UTC from CEST
                # ("summer time" in the "Europe/Warsaw" timezone):
                dict(
                    time="2020-10-24 23:59:59",
                    fqdn="example_5.com",
                ),
                dict(
                    time="2020-06-03 11:00:00",
                    fqdn="example_4.com",
                ),
                dict(
                    time="2020-06-03 10:00:00",
                    fqdn="example_3.com",
                ),
                dict(
                    time="2020-06-02 11:00:00",
                    fqdn="example_2.com",
                ),
                dict(
                    time="2020-06-02 10:00:00",
                    fqdn="example_1.com",
                ),
            ]
        )


class TestCertPlShield202505Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'cert-pl.shield'
    PARSER_RAW_FORMAT_VERSION_TAG = '202505'
    PARSER_CLASS = CertPlShield202505Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'high',
        'category': 'phish',
    }

    def cases(self):
        yield (
            b'4\texample_4.com\t2025-05-08T12:28:06+00:00\n'
            b'3\texample_3.com\t2025-05-08T12:27:06+00:00\n'
            b'2\texample_2.com\t2025-05-08T12:26:06+00:00\n'
            b'1\texample_1.com\t2025-05-08T12:25:06+00:00\n'
            ,
            [
                dict(
                    time="2025-05-08 12:28:06",
                    fqdn="example_4.com",
                ),
                dict(
                    time="2025-05-08 12:27:06",
                    fqdn="example_3.com",
                ),
                dict(
                    time="2025-05-08 12:26:06",
                    fqdn="example_2.com",
                ),
                dict(
                    time="2025-05-08 12:25:06",
                    fqdn="example_1.com",
                ),
            ]
        )

        yield (
            b'invalid\trow\t\n'
            ,
            ValueError
        )

# Copyright (c) 2021-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.dataplane import (
    _DataplaneBaseParser,
    DataplaneDnsrdParser,
    DataplaneDnsrdanyParser,
    DataplaneDnsversionParser,
    DataplaneSipinvitationParser,
    DataplaneSipqueryParser,
    DataplaneSipregistrationParser,
    DataplaneSmtpdataParser,
    DataplaneSmtpgreetParser,
    DataplaneSshclientParser,
    DataplaneSshpwauthParser,
    DataplaneTelnetloginParser,
    DataplaneVncrfbParser
)
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.record_dict import BLRecordDict


class _BaseDataplaneParserTestCase(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict
    PARSER_BASE_CLASS = _DataplaneBaseParser
    download_time = "2014-01-10 10:14:00"
    expires_time = "2014-01-12 10:14:00"

    @staticmethod
    def _case_with_name(parser_source):
        """Check if parser_source needs to test `name` param."""
        return parser_source.split(".")[1] in ("sshpwauth", "telnetlogin")

    def cases(self):
        if self._case_with_name(self.PARSER_SOURCE):
            yield (
                b"# addresses seen in the current report. \n"
                b"#\n"
                b"174 | Example name 1 | 1.1.1.1  | 2021-05-20 20:17:02 | sshpwauth\n"
                b"174 | Example name 2 | 2.2.2.2  | 2021-05-17 03:02:55 | telnetlogin \n"
                b"174 | Example name 3 | wrong.ip.address  | 2021-05-17 03:02:55 | telnetlogin \n",
                [
                    dict(
                        self.get_bl_items(1, 2, bl_current_time=self.download_time),
                        address=[{"ip": "1.1.1.1"}],
                        time="2021-05-20 20:17:02",
                        name="auth attempt",
                        expires=self.expires_time,
                    ),
                    dict(
                        self.get_bl_items(2, 2, bl_current_time=self.download_time),
                        address=[{"ip": "2.2.2.2"}],
                        time="2021-05-17 03:02:55",
                        name="auth attempt",
                        expires=self.expires_time,
                    ),
                ]
            )
        else:
            yield (
                b"# addresses seen in the current report. \n"
                b"#\n"
                b"174 | Example name 1 | 1.1.1.1  | 2021-05-20 20:17:02 | category\n"
                b"174 | Example name 2 | 2.2.2.2  | 2021-05-17 03:02:55 | category \n"
                b"174 | Example name 3 | wrong.ip.address  | 2021-05-17 03:02:55 | category \n",
                [
                    dict(
                        self.get_bl_items(1, 2, bl_current_time=self.download_time),
                        address=[{"ip": "1.1.1.1"}],
                        time="2021-05-20 20:17:02",
                        expires=self.expires_time,
                    ),
                    dict(
                        self.get_bl_items(2, 2, bl_current_time=self.download_time),
                        address=[{"ip": "2.2.2.2"}],
                        time="2021-05-17 03:02:55",
                        expires=self.expires_time,
                    ),
                ]
            )


class TestDataplaneDnsrdParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.dnsrd"
    PARSER_CLASS = DataplaneDnsrdParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneDnsrdanyParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.dnsrdany"
    PARSER_CLASS = DataplaneDnsrdanyParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneDnsversionParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.dnsversion"
    PARSER_CLASS = DataplaneDnsversionParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneSipinvitationParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.sipinvitation"
    PARSER_CLASS = DataplaneSipinvitationParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneSipqueryParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.sipquery"
    PARSER_CLASS = DataplaneSipqueryParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneSipregistrationParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.sipregistration"
    PARSER_CLASS = DataplaneSipregistrationParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }


class TestDataplaneSmtpdataParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.smtpdata"
    PARSER_CLASS = DataplaneSmtpdataParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "spam",
    }


class TestDataplaneSmtpgreetParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.smtpgreet"
    PARSER_CLASS = DataplaneSmtpgreetParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneSshclientParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.sshclient"
    PARSER_CLASS = DataplaneSshclientParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class TestDataplaneSshpwauthParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.sshpwauth"
    PARSER_CLASS = DataplaneSshpwauthParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }


class TestDataplaneTelnetLoginParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.telnetlogin"
    PARSER_CLASS = DataplaneTelnetloginParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }


class TestDataplaneVncrfbParser(_BaseDataplaneParserTestCase):

    PARSER_SOURCE = "dataplane.vncrfb"
    PARSER_CLASS = DataplaneVncrfbParser
    PARSER_CONSTANT_ITEMS = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }

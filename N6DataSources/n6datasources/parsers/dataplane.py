# Copyright (c) 2021-2023 NASK. All rights reserved.

"""
Parsers: `dataplane.dnsrd`, `dataplane.dnsrdany`, `dataplane.dnsversion`,
`dataplane.sipinvitation`, `dataplane.sipquery`, `dataplane.sipregistration`,
`dataplane.smtpdata`, `dataplane.smtpgreet`, `dataplane.sshclient`,
`dataplane.sshpwauth`, `dataplane.telnetlogin`, `dataplane.vncrfb`.
"""

import csv
import datetime

from n6datasources.parsers.base import (
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.common_helpers import IPv4_STRICT_DECIMAL_REGEX
from n6lib.csv_helpers import (
    split_csv_row,
    strip_fields
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class _DataplaneBaseParser(BlackListParser):

    EXPIRES_DAYS = 2

    # can be set in concrete classes if needed
    name_item = None

    def parse(self, data):
        rows = csv.reader(data['csv_raw_rows'], delimiter=',', quotechar='"')
        for row in rows:
            row = row[0]
            if row.startswith("#"):
                continue

            # fields: "ASN", "ASname", "ipaddr", "lastseen", "category"
            _, _, ip, lastseen, _ = strip_fields(split_csv_row(row, delimiter="|"))

            # we skip rows with invalid IP address
            if not self._is_ip_valid(ip):
                continue

            with self.new_record_dict(data) as parsed:
                parsed["address"] = {"ip": ip}
                parsed["time"] = lastseen
                parsed["expires"] = (
                    parse_iso_datetime_to_utc(data["properties.timestamp"])
                    + datetime.timedelta(days=self.EXPIRES_DAYS)
                )
                if self.name_item is not None:
                    parsed['name'] = self.name_item
                yield parsed

    def _is_ip_valid(self, ip):
        match = IPv4_STRICT_DECIMAL_REGEX.match(ip)
        if match is None:
            return False
        return True


class DataplaneDnsrdParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.dnsrd"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneDnsrdanyParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.dnsrdany"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneDnsversionParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.dnsversion"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneSipinvitationParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.sipinvitation"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneSipqueryParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.sipquery"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneSipregistrationParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.sipregistration"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }


class DataplaneSmtpdataParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.smtpdata"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "spam",
    }


class DataplaneSmtpgreetParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.smtpgreet"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneSshclientParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.sshclient"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


class DataplaneSshpwauthParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.sshpwauth"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }

    name_item = "auth attempt"



class DataplaneTelnetloginParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.telnetlogin"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "server-exploit",
    }

    name_item = "auth attempt"


class DataplaneVncrfbParser(_DataplaneBaseParser):

    default_binding_key = "dataplane.vncrfb"
    constant_items = {
        "restriction": "public",
        "confidence": "low",
        "category": "scanning",
    }


add_parser_entry_point_functions(__name__)


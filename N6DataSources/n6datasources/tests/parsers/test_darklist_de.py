# Copyright (c) 2020-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.darklist_de import DarklistDeBlParser
from n6datasources.parsers.base import BlackListParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin

from n6lib.record_dict import BLRecordDict


class TestDarklistDeBlParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'darklist-de.bl'
    PARSER_CLASS = DarklistDeBlParser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'scanning',
    }

    ips_time = '2020-04-21 08:15:00'

    # This value should be changed alongside
    # `EXPIRES_DAYS` variable in the parsers module
    expires_time = '2020-04-28 08:15:00'

    def cases(self):
        # Typical cases, we expect to yield 6 events
        # (last one is not a valid IP record)
        yield (
            (
                b"# darklist.de - blacklisted raw IPs\n"
                b"# generated on 21.04.2020 08:15\n"
                b"\n"
                b"1.1.1.0/24\n"
                b"2.2.2.0/24\n"
                b"3.3.3.0/24\n"
                b"4.4.4.4\n"
                b"5.5.5.5\n"
                b"6.6.6.6\n"
                b"1111.1111.1111.1111 not_IP_record\n"
            ),
            [
                dict(
                    self.get_bl_items(1, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "1.1.1.0"}],
                    ip_network='1.1.1.0/24',
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(2, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "2.2.2.0"}],
                    ip_network='2.2.2.0/24',
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(3, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "3.3.3.0"}],
                    ip_network='3.3.3.0/24',
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(4, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "4.4.4.4"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(5, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "5.5.5.5"}],
                    expires=self.expires_time,
                ),
                dict(
                    self.get_bl_items(6, 6, bl_current_time=self.ips_time),
                    time=self.ips_time,
                    address=[{'ip': "6.6.6.6"}],
                    expires=self.expires_time,
                )
            ],
        )

        # Invalid data
        yield (
            b"# darklist.de - blacklisted raw IPs\n"
            b"# generated on 21.04.2020 08:15\n",
            ValueError
        )

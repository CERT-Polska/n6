# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest

from n6.parsers.generic import BaseParser
from n6.parsers.zone_h import ZoneHRSSParser
from n6.tests.parsers._parser_test_mixin import ParserTestMixin


class TestZoneHRSSParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'zoneh.rss'
    PARSER_CLASS = ZoneHRSSParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'deface',
    }

    def cases(self):
        yield (
            # 1st case, valid: UTC offset: 00:00
            '[["http://yz.ytlsga.gov.cn/indonesia.txt", "http://yz.ytlsga.gov.cn/indonesia.txt '
            'notified by Panataran", "Tue, 19 Jul 2016 14:48:17 +0000"],'
            # 2nd case, valid: UTC offset: +10:00
            '["http://wap.ygz.ytlsga.gov.cn/indonesia.txt", "http://wap.ygz.ytlsga.gov.cn/'
            'indonesia.txt notified by Panataran", "Tue, 19 Jul 2016 14:51:14 +1000"],'
            # 3rd case, valid: UTC offset: -12:30
            '["http://www.azembassy.org.tr/?options=content&amp;amp;id=18",'
            '"http://www.azembassy.org.tr/?options=content&amp;amp;id=18 notified by '
            'Monte Melkonian Cyber Army", "Sun, 15 Feb 2015 21:03:51 -1230"],'
            # 4th case, valid: missing field 'pubDate' in RSS stream
            '["http://www.snnprscon.gov.et", "http://www.snnprscon.gov.et notified by '
            'by_dada\u015f",""],'
            # 5th case, invalid: empty 'title' field
            '["", "http://blog.empleosonora.gob.mx notified by '
            'Haxor Beast Prayer", "Mon, 16 Feb 2015 13:01:58 +0000"],'
            # 6th case, invalid: protocol only, no domain name
            '["https:///", "http://register.yokohamatire.ph notified by '
            'BD GREY HAT HACKERS", "Sun, 01 Feb 2015 20:53:19 +0000"],'
            # 7th case, invalid: illegal characters inside domain name
            '["http://invalid@%$#domain.com", "http://voiceraise.wwf.org.my notified by '
            'GantengersCrew", "Thu, 21 Jul 2016 11:22:16 +0000"],'
            # 8th case, valid: no protocol, 'www.' only
            '["www.istitutocomprensivogoddo.gov.it", "www.istitutocomprensivogoddo.gov.it/'
            'istituto/index.html notified by Moh Ooasiic]", "Fri, 13 Feb 2015 18:54:23 -0400"],'
            # 9th case, valid: ftp protocol
            '["ftp://bojonegorokab.go.id/yolo.txt", "ftp://bojonegorokab.go.id/yolo.txt'
            ' notified by SultanHaikal", "Tue, 10 Feb 2015 23:50:59 +0000"],'
            # 10th case, valid: https protocol
            '["https://desarrollo-insumos.ica.gov.co", "https://desarrollo-insumos.ica.gov.co '
            'notified by oroboruo", "Sun, 01 Feb 2015 22:42:01 +0500"],'
            # 11th case, invalid: illegal colon character in domain name
            '["http://pruebas:insumos.ica.gov.co", "http://pruebas-insumos.ica.gov.co '
            'notified by oroboruo", "Sun, 01 Feb 2015 22:40:21 +0000"],'
            # 12th case, valid: no protocol, no 'www.' prefix
            '["tongbai.gov.cn/hkg.php", "tongbai.gov.cn/hkg.php notified by HKGTW", '
            '"Thu, 21 Jul 2016 13:37:51 +0000"],'
            # 13th case, invalid: missing slash sign after 'http:'
            '["http:/shenley-pc.gov.uk", "http:/shenley-pc.gov.uk notified by fallaga team", '
            '"Fri, 22 Jul 2016 08:05:10 +0000"]]',
            [
                dict(
                    fqdn="yz.ytlsga.gov.cn",
                    time="2016-07-19 14:48:17",
                ),
                dict(
                    fqdn="wap.ygz.ytlsga.gov.cn",
                    time="2016-07-19 04:51:14",
                ),
                dict(
                    fqdn="www.azembassy.org.tr",
                    time="2015-02-16 09:33:51",
                ),
                dict(
                    fqdn="www.snnprscon.gov.et",
                    time=self.message_created,
                ),
                dict(
                    fqdn="www.istitutocomprensivogoddo.gov.it",
                    time="2015-02-13 22:54:23",
                ),
                dict(
                    fqdn="bojonegorokab.go.id",
                    time="2015-02-10 23:50:59",
                ),
                dict(
                    fqdn="desarrollo-insumos.ica.gov.co",
                    time="2015-02-01 17:42:01",
                ),
                dict(
                    fqdn="tongbai.gov.cn",
                    time="2016-07-21 13:37:51",
                ),
            ]
        )

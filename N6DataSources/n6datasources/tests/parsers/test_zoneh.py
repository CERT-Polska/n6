# Copyright (c) 2013-2023 NASK. All rights reserved.

import unittest

from n6datasources.parsers.base import BaseParser
from n6datasources.parsers.zoneh import ZonehRssParser
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin


class TestZonehRssParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'zoneh.rss'
    PARSER_CLASS = ZonehRssParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'deface',
    }

    def cases(cls):
        yield (
            # 1st case, valid: UTC offset: 00:00
            b'[["http://example1.com/whatever.txt", "http://example1.com/abc.txt '
            b'notified by AbcdGuy", "Tue, 19 Jul 2016 14:48:17 +0000"],'

            # 2nd case, valid: UTC offset: +10:00
            b'["http://example2.com/abc.txt", "http://example2.com/'
            b'abc.txt notified by AbcdGuy", "Tue, 19 Jul 2016 14:51:14 +1000"],'

            # 3rd case, valid: UTC offset: -12:30
            b'["http://example3.com/?options=content&amp;amp;id=18",'
            b'"http://example3.com/?options=content&amp;amp;id=18 notified by '
            b'Example Imagined Cyber Army", "Sun, 15 Feb 2015 21:03:51 -1230"],'

            # 4th case, valid: missing field 'pubDate' in RSS stream
            b'["http://example4.com", "http://example4.com notified by '
            b'example_guy",""],'

            # 5th case, invalid: empty 'title' field
            b'["", "http://something-wrong1.com notified by '
            b'Another Guy", "Mon, 16 Feb 2015 13:01:58 +0000"],'

            # 6th case, invalid: protocol only, no domain name
            b'["https:///", "http://something-wrong2.com notified by '
            b'AndAnotherExampleGuy", "Sun, 01 Feb 2015 20:53:19 +0000"],'

            # 7th case, invalid: illegal characters inside domain name
            b'["http://invalid@%$#domain.com", "http://another.example.com notified by '
            b'ThatPreviousGuy", "Thu, 21 Jul 2016 11:22:16 +0000"],'

            # 8th case, valid: no protocol, 'www.' only
            b'["example5.com", "example5.com/'
            b'example-example/index.html notified by ExampleGuy]", "Fri, 13 Feb 2015 18:54:23 -0400"],'

            # 9th case, valid: ftp protocol
            b'["ftp://example6.com/example.txt", "ftp://example6.com/example.txt'
            b' notified by SampleExampleGuy", "Tue, 10 Feb 2015 23:50:59 +0000"],'

            # 10th case, valid: https protocol
            b'["https://example7.com", "https://example7.com '
            b'notified by ex-am-pl-eR", "Sun, 01 Feb 2015 22:42:01 +0500"],'

            # 11th case, invalid: illegal colon character in domain name
            b'["http://why:the-colon.example.com", "http://why:the-colon.example.com '
            b'notified by someOne", "Sun, 01 Feb 2015 22:40:21 +0000"],'

            # 12th case, valid: no protocol, no 'www.' prefix
            b'["example8.com/exmpl.php", "example8.com/exmpl.php notified by SoMeONE", '
            b'"Thu, 21 Jul 2016 13:37:51 +0000"],'

            # 13th case, invalid: missing slash sign after 'http:'
            b'["http:/something-wrong2.com", "http:/something-wrong2.com notified by some example team", '
            b'"Fri, 22 Jul 2016 08:05:10 +0000"]]',
            [
                dict(
                    fqdn="example1.com",
                    time="2016-07-19 14:48:17",
                ),
                dict(
                    fqdn="example2.com",
                    time="2016-07-19 04:51:14",
                ),
                dict(
                    fqdn="example3.com",
                    time="2015-02-16 09:33:51",
                ),
                dict(
                    fqdn="example4.com",
                    time=cls.message_created,
                ),
                dict(
                    fqdn="example5.com",
                    time="2015-02-13 22:54:23",
                ),
                dict(
                    fqdn="example6.com",
                    time="2015-02-10 23:50:59",
                ),
                dict(
                    fqdn="example7.com",
                    time="2015-02-01 17:42:01",
                ),
                dict(
                    fqdn="example8.com",
                    time="2016-07-21 13:37:51",
                ),
            ]
        )

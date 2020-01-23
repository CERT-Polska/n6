# -*- coding: utf-8 -*-

# Copyright (c) 2013-2020 NASK. All rights reserved.

import datetime
import unittest

from n6lib.record_dict import (
    AdjusterError,
    BLRecordDict,
)
from n6.parsers.abuse_ch import (
    AbuseChSpyeyeDomsParser,
    AbuseChSpyeyeIpsParser,
    AbuseChZeusDomsParser,
    AbuseChZeusIpsParser,
    AbuseChPalevoDomsParser,
    AbuseChPalevoIpsParser,
    AbuseChSpyeyeDoms201406Parser,
    AbuseChZeusDoms201406Parser,
    AbuseChPalevoDoms201406Parser,
    AbuseChSpyeyeIps201406Parser,
    AbuseChZeusIps201406Parser,
    AbuseChPalevoIps201406Parser,
    AbuseChZeusTrackerParser,
    AbuseChFeodoTrackerParser,
    AbuseChFeodoTracker201908Parser,
    AbuseChRansomwareTrackerParser,
    _AbuseChSSLBlacklistBaseParser,
    AbuseChSSLBlacklistDyreParser,
    AbuseChSSLBlacklistParser,
    AbuseChSSLBlacklist201902Parser,
    AbuseChUrlhausUrlsParser,
    AbuseChUrlhausUrls202001Parser,
    AbuseChUrlhausPayloadsUrlsParser,
)
from n6.parsers.generic import (
    BaseParser,
    BlackListTabDataParser,
)
from n6.tests.parsers._parser_test_mixin import ParserTestMixIn
from n6lib.datetime_helpers import parse_iso_datetime_to_utc


MESSAGE_EXPIRES = str(parse_iso_datetime_to_utc(ParserTestMixIn.message_created) +
                      datetime.timedelta(days=2))


#
# Common cases

def _cases_for_doms201406(self):
    """Cases for tests of AbuseCh...DomsParser classes."""
    yield ('www.example.su\n'
           '# ignore comments and blank lines...\n'
           ' \n'
           '\n'
           'example.RU\n'
           ' site.EXAMPLE.org\n'
           'example.NET \n'
           'example.123.pl.com\n',  # invalid fqdn but there are some IPs
           [
               dict(
                   self.get_bl_items(1, 5),
                   fqdn='www.example.su',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(2, 5),
                   fqdn='example.ru',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(3, 5),
                   fqdn='site.example.org',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(4, 5),
                   fqdn='example.net',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(5, 5),
                   fqdn='example.123.pl.com',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
           ])


def _cases_for_doms(self):
    """Cases for tests of AbuseCh...DomsParser classes."""
    yield ('www.example.su\n'
           '# ignore comments and blank lines...\n'
           ' \n'
           '\n'
           'example.RU\t11.22.33.44,122.123.124.125 ,222.223.224.225, 10.20.30.40\t12345,54321 , 123,01234\n'
           ' site.EXAMPLE.org\n'
           'example.NET \n'
           'example.\xee.com \t 1.1.1.1 \t 1000 ',  # invalid fqdn but there are some IPs
           [
               dict(
                   self.get_bl_items(1, 5),
                   fqdn='www.example.su',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(2, 5),
                   fqdn='example.ru',
                   address=[
                       dict(ip='11.22.33.44'),
                       dict(ip='122.123.124.125'),
                       dict(ip='222.223.224.225'),
                       dict(ip='10.20.30.40'),
                   ],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(3, 5),
                   fqdn='site.example.org',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(4, 5),
                   fqdn='example.net',
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(5, 5),
                   address=[dict(ip='1.1.1.1')],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
           ])
    yield ('example.RU\t11.22.33.44,122.123.124.125 ,222.223.224.225, 10.20.30.40\t12345,54321 , 432,0543 \t 1.2.3.4\n',
           TypeError)       # bad number of columns
    yield ('example.RU\t12345,54321 , 432,0543\t11.22.33.44,122.123.124.125 ,222.223.224.225, 10.20.30.40\n',
           AdjusterError)   # bad order of columns (=> wrong types)
    yield ('example.\xee.com\n',
           AdjusterError)   # invalid fqdn and no IPs


def _cases_for_ips(self):
    """Cases for tests of AbuseCh...IpsParser classes."""
    yield ('11.22.33.44\t1234\n'  # format of row: ip on a first place + any number of ignored extra columns
           '222.223.224.225 \t\t\t\t\t\n'  # (trailing whitespace is stripped out)
           '# ignore comments and blank lines...\n'
           ' \n'
           '\n'
           '10.20.30.40 \t 4567\n'
           ' 1.1.1.1\n',
           [
               dict(
                   self.get_bl_items(1, 4),
                   address=[dict(ip='11.22.33.44')],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(2, 4),
                   address=[dict(ip='222.223.224.225')],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(3, 4),
                   address=[dict(ip='10.20.30.40')],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
               dict(
                   self.get_bl_items(4, 4),
                   address=[dict(ip='1.1.1.1')],
                   time=self.message_created,
                   expires=MESSAGE_EXPIRES,
               ),
           ])
    yield ('4567\t11.22.33.44\n',
           AdjusterError)   # bad order of columns (=> wrong types)
    yield ('\t4567\n',
           AdjusterError)   # empty IP field


def _cases_for_tracker(self):
    '''Cases for test of AbuseChZeusTrackerParser class'''
    yield ('''[["example.com/KINS/panel/bot.exe (2015-06-10)", "URL: http://example.com/KINS/panel/bot.exe, status: offline, MD5 hash: aa11b3bf473c2e18537c925e640820b9"]]''',
            [{
                'time': '2015-06-10 00:00:00',
                'url': 'http://example.com/KINS/panel/bot.exe',
                'md5': 'aa11b3bf473c2e18537c925e640820b9',
            }]
        )
    yield ('''[["example.com/Mit.exe (2015-06-07)", "URL: http://example.com/Mit.exe, status: offline, MD5 hash: "]]''',
            [{
                'time': '2015-06-07 00:00:00',
                'url': 'http://example.com/Mit.exe',
            }]
        )
    yield ('''[["www.example.com/so.exe (2015-06-06)", "URL: http://www.example.com/so.exe, status: offline, MD5 hash: aa119e170c483b2bf0600ec257cd6d32"]]''',
            [{
                'time': '2015-06-06 00:00:00',
                'url': 'http://www.example.com/so.exe',
                'md5': 'aa119e170c483b2bf0600ec257cd6d32',
            }]
        )


#
# Actual test case clases

class TestAbuseChSpyeyeDoms201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.spyeye-doms'
    PARSER_CLASS = AbuseChSpyeyeDoms201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'spyeye',
    }

    cases = _cases_for_doms201406


class TestAbuseChSpyeyeDomsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.spyeye-doms'
    PARSER_CLASS = AbuseChSpyeyeDomsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'spyeye',
        '_do_not_resolve_fqdn_to_ip': True,
    }

    cases = _cases_for_doms


class TestAbuseChSpyeyeIps201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.spyeye-ips'
    PARSER_CLASS = AbuseChSpyeyeIps201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'spyeye',
    }

    cases = _cases_for_ips


class TestAbuseChSpyeyeIpsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.spyeye-ips'
    PARSER_CLASS = AbuseChSpyeyeIpsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'spyeye',
    }

    cases = _cases_for_ips


class TestAbuseChZeusDoms201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.zeus-doms'
    PARSER_CLASS = AbuseChZeusDoms201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'zeus',
    }

    cases = _cases_for_doms201406


class TestAbuseChZeusDomsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.zeus-doms'
    PARSER_CLASS = AbuseChZeusDomsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'zeus',
        '_do_not_resolve_fqdn_to_ip': True,
    }

    cases = _cases_for_doms


class TestAbuseChZeusIps201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.zeus-ips'
    PARSER_CLASS = AbuseChZeusIps201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'zeus',
    }

    cases = _cases_for_ips


class TestAbuseChZeusIpsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.zeus-ips'
    PARSER_CLASS = AbuseChZeusIpsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'zeus',
    }

    cases = _cases_for_ips


class TestAbuseChPalevoDoms201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.palevo-doms'
    PARSER_CLASS = AbuseChPalevoDoms201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'palevo',
    }

    cases = _cases_for_doms201406


class TestAbuseChPalevoDomsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.palevo-doms'
    PARSER_CLASS = AbuseChPalevoDomsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'palevo',
        '_do_not_resolve_fqdn_to_ip': True,
    }

    cases = _cases_for_doms


class TestAbuseChPalevoIps201406Parser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.palevo-ips'
    PARSER_CLASS = AbuseChPalevoIps201406Parser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'palevo',
    }

    cases = _cases_for_ips


class TestAbuseChPalevoIpsParser(ParserTestMixIn, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'abuse-ch.palevo-ips'
    PARSER_CLASS = AbuseChPalevoIpsParser
    PARSER_BASE_CLASS = BlackListTabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
        'name': 'palevo',
    }

    cases = _cases_for_ips


class TestAbuseChZeusTrackerParser(ParserTestMixIn, unittest.TestCase):
    PARSER_SOURCE = 'abuse-ch.zeustracker'
    PARSER_CLASS = AbuseChZeusTrackerParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'malurl',
    }

    cases = _cases_for_tracker


class TestAbuseChFeodoTrackerParser(ParserTestMixIn, unittest.TestCase):
    PARSER_SOURCE = 'abuse-ch.feodotracker'
    PARSER_CLASS = AbuseChFeodoTrackerParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'cnc',
    }
    some_input_data = '''["Host: 1.1.1.1, Version: C, Firstseen: 2015-06-01 13:35:33 UTC",
                        "Host: 2.2.2.2, Version: A, Firstseen: 2015-04-01 13:53:33 UTC",
                        "Host: 3.3.3.3, Version: f, Firstseen: 2015-04-28 08:53:33 UTC",
                        "Host: 4.4.4.4, Version: B, Firstseen: 2000-04-01 13:53:33 UTC"]'''

    def cases(self):
        yield (
            self.some_input_data,
            [
                {
                    'time': '2015-06-01 13:35:33',
                    'address': [{'ip': '1.1.1.1'}],
                    'name': 'feodo-emotet'
                },
                {
                    'time': '2015-04-01 13:53:33',
                    'address': [{'ip': '2.2.2.2'}],
                    'name': 'feodo'
                },
                # unknown 'Version' value, so a 'name' field
                # is skipped
                {
                    'time': '2015-04-28 08:53:33',
                    'address': [{'ip': '3.3.3.3'}],
                },
                {
                    'time': '2000-04-01 13:53:33',
                    'address': [{'ip': '4.4.4.4'}],
                    'name': 'feodo'
                }

            ]
        )


class TestAbuseChFeodotracker201908Parser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.feodotracker'
    PARSER_CLASS = AbuseChFeodoTracker201908Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'cnc'
    }

    def cases(self):
        yield (
            '2019-05-27 13:36:27,0.0.0.0,447,2019-05-28,TrickBot\n'
            'this, is, one, wrong, line\n'
            '2019-05-25 01:30:36,0.0.0.0,443,2019-05-27,Heodo\n'
            '2019-05-16 19:43:27,0.0.0.0,8080,2019-05-22,Heodo\n',
            [
                {
                    'name': 'trickbot',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 447,
                    'time': '2019-05-27 13:36:27',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 443,
                    'time': '2019-05-25 01:30:36',
                },
                {
                    'name': 'heodo',
                    'address': [{'ip': '0.0.0.0'}],
                    'dport': 8080,
                    'time': '2019-05-16 19:43:27',
                },
            ]
        )

        yield (
            "INVALID_DATA",
            ValueError
        )


class TestAbuseChRansomwareTrackerParser(ParserTestMixIn, unittest.TestCase):
    PARSER_SOURCE = 'abuse-ch.ransomware'
    PARSER_CLASS = AbuseChRansomwareTrackerParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
    }
    some_input_data = (
        '"2016-11-08 13:11:44","Distribution Site","EXAMPLE1","example1.com",'
            '"http://example1.com","online","","1.1.1.1","00000","FR"\n'
        '"2016-11-08 13:10:35","Payment Site","EXAMPLE2","example2.com",'
            '"http://example2.com","online","","2.2.2.2|3.3.3.3",'
            '"00000|7922","RU|US"\n'
        '"2016-02-28 13:13:13","Unknown Value","E_X_A_M_P_L_E","unknown1234567.com",'
            '"http://unknown1234567.com/24h","unknown1234567","","","",""\n'
        '"2016-11-08 13:13:46","C2","example3","example3.com",'
            '"http://example3.com","unknown","","","",""\n'
    )

    def cases(self):
        yield (
            self.some_input_data,
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    url='http://example1.com',
                    time='2016-11-08 13:11:44',
                    name='EXAMPLE1',
                    fqdn='example1.com',
                    category='malurl'
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}, {'ip': '3.3.3.3'}],
                    url='http://example2.com',
                    time='2016-11-08 13:10:35',
                    name='EXAMPLE2',
                    fqdn='example2.com',
                    category='malurl'
                ),
                dict(
                    url='http://example3.com',
                    time='2016-11-08 13:13:46',
                    name='example3',
                    fqdn='example3.com',
                    category='cnc'
                )
            ]
        )


class _TestAbuseChSSLBlacklistParserBase(ParserTestMixIn, unittest.TestCase):

    PARSER_BASE_CLASS = _AbuseChSSLBlacklistBaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def cases(self):
        yield (
            # 1st case: details page for the element without
            # an associated binaries table.
            '{"https://sslbl.abuse.ch/example/1111af01d6a5b83dc3e8c8d649101f7872719fce":'
            '{"name": "Gozi MITM", "timestamp": "2016-10-17 12:44:04",'
            '"fingerprint": "1111af01d6a5b83dc3e8c8d649101f7872719fce",'
            '"subject": "OU=Domain Control Validated, OU=PositiveSSL, CN=example1.com",'
            '"issuer": "C=GB, ST=Greater Manchester, L=Salford, O=Random, CN=RANDOM"}}',
            [
                # 1st case: single, general event.
                dict(
                    time="2016-10-17 12:44:04",
                    x509fp_sha1="1111af01d6a5b83dc3e8c8d649101f7872719fce",
                    x509subject="OU=Domain Control Validated, OU=PositiveSSL, CN=example1.com",
                    x509issuer="C=GB, ST=Greater Manchester, L=Salford, O=Random, "
                               "CN=RANDOM",
                    name="gozi mitm"
                ),
            ]
        )
        yield (
            # 2nd case: element with 2 associated binaries.
            '{"https://sslbl.abuse.ch/example/random":'
            '{"name": "ZeuS C&C", "timestamp": "2016-10-17 11:52:40",'
            '"fingerprint": "5fcb5b418f779a542b7148f2ddea211491111111",'
            '"subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",'
            '"issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",'
            '"binaries": [["2016-10-13 16:27:10", "11a609dac79e76fe7b5a78af35c5a2d6", '
            '"1.1.1.1", "443"], ["2016-10-10 17:29:57", "1116210f20753c836378ca7aa18c3d25", '
            '"2.2.2.2", "444"]]}}',
            [
                dict(
                    time="2016-10-13 16:27:10",
                    x509fp_sha1="5fcb5b418f779a542b7148f2ddea211491111111",
                    x509subject="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    x509issuer="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    name="zeus c&c",
                    md5="11a609dac79e76fe7b5a78af35c5a2d6",
                    address=[{'ip': '1.1.1.1'}],
                    dport=443
                ),
                dict(
                    time="2016-10-10 17:29:57",
                    x509fp_sha1="5fcb5b418f779a542b7148f2ddea211491111111",
                    x509subject="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    x509issuer="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    name="zeus c&c",
                    md5="1116210f20753c836378ca7aa18c3d25",
                    address=[{'ip': '2.2.2.2'}],
                    dport=444
                ),
            ]
        )
        yield (
            # 3rd case: 2 associated binaries.
            '{"https://sslbl.abuse.ch/example/e03e111111a111f1f03f091123511eaa3fc2d6b1":'
            '{"name": "Gootkit C&C", "timestamp": "2016-10-14 11:13:35",'
            '"fingerprint": "e03e111111a111f1f03f091123511eaa3fc2d6b1",'
            '"subject": "C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",'
            '"issuer": "C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",'
            '"binaries": [["fb890a2b17cc70e0fde9ec9adc01b6b9", '
            '"3.3.3.3", "80"], ["2016-10-13 15:50:13", "a1a999747a8e94b65b42e8073ddb1b93",'
            ' "3.3.3.3", "80"]]}}',
            [
                # 3rd case: first event is skipped, incomplete list
                # of items of the associated binary.
                dict(
                    time="2016-10-13 15:50:13",
                    x509fp_sha1="e03e111111a111f1f03f091123511eaa3fc2d6b1",
                    x509subject="C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",
                    x509issuer="C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",
                    name="gootkit c&c",
                    md5="a1a999747a8e94b65b42e8073ddb1b93",
                    address=[{'ip': '3.3.3.3'}],
                    dport=80
                ),
            ]
        )
        yield (
            # 4th case: empty binaries list, no timestamp, element skipped.
            '{"https://sslbl.abuse.ch/example/111ffc1d71cb6a4911c14393f1825857793a1869":'
            '{"name": "Gootkit C&C",'
            '"fingerprint": "111ffc1d71cb6a4911c14393f1825857793a1869",'
            '"subject": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost",'
            '"issuer": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost",'
            '"binaries": []}}',
            ValueError
        )
        yield (
            # 5th case: empty 'fingerprint' field, element skipped.
            '{"https://sslbl.abuse.ch/example/2a222d036ffc65bffe0bcf2e82da6b83a61fb577":'
            '{"name": "Gootkit C&C",'
            '"fingerprint": "",'
            '"subject": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost",'
            '"issuer": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost"}}',
            ValueError
        )
        yield (
            # 6th case: one, incomplete binary. Publish the event based
            # on the general details only.
            '{"https://sslbl.abuse.ch/example/3aa13433ad8784cae053fe51a38643a8b5dc2b3e":'
            '{"name": "TorrentLocker C&C", "timestamp": "2016-10-06 05:31:14",'
            '"fingerprint": "3aa13433ad8784cae053fe51a38643a8b5dc2b3e",'
            '"subject": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"issuer": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"binaries": [["aa37a33ebd8d08361eb4c0258bc772ce", '
            '"5.5.5.5"]]}}',
            [
                dict(
                    time="2016-10-06 05:31:14",
                    x509fp_sha1="3aa13433ad8784cae053fe51a38643a8b5dc2b3e",
                    x509subject="C=US, ST=Denial, L=Springfield, O=Dis",
                    x509issuer="C=US, ST=Denial, L=Springfield, O=Dis",
                    name="torrentlocker c&c"
                ),
            ]
        )
        yield (
            # 7th case: invalid binaries, no timestamp in general
            # details, skip the whole event.
            '{"https://sslbl.abuse.ch/example/aa1119406cb50a7c5382ed8c86cb468b06ee6e24":'
            '{"name": "TorrentLocker C&C",'
            '"fingerprint": "aa1119406cb50a7c5382ed8c86cb468b06ee6e24",'
            '"subject": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"issuer": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"binaries": [["11111a1851f2ac1a1ee8c4b5ebee6ec2", '
            '"6.6.6.6"]]}}',
            ValueError
        )


class TestAbuseChSSLBlacklistParser(_TestAbuseChSSLBlacklistParserBase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist'
    PARSER_CLASS = AbuseChSSLBlacklistParser


class TestAbuseChSSLBlacklistDyreParser(_TestAbuseChSSLBlacklistParserBase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist-dyre'
    PARSER_CLASS = AbuseChSSLBlacklistDyreParser


class TestAbuseChSSLBlacklists201902Parser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist'
    PARSER_CLASS = AbuseChSSLBlacklist201902Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def cases(self):
        yield (
            '2019-02-26 15:42:09,1111c502625cec0a0211714f8d5c2972868963d4,Gozi C&C\n'
            'this_line,should_not,be_here\n'
            '2019-02-26 06:40:29,2222ad74167f5b27d47a4f629d11aa187710fd41,Malware C&C\n',
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
            'asdasd',
            ValueError
        )


class TestAbuseChUrlhausUrlsParser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.urlhaus-urls'
    PARSER_CLASS = AbuseChUrlhausUrlsParser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'malurl',
    }

    def cases(self):
        yield (
            '"31629","2018-07-12 16:18:02","http://example1.com","online","malware_download","None","https://urlhaus.abuse.ch/url/XXXXX/", "random_reporter"\n'
            '"this is", "wrong", "line", "and", "should", "not", "be", "valid"\n'
            '"31628","2018-07-12 16:01:19","http://www.example2.com","online","malware_download","doc,emotet","https://urlhaus.abuse.ch/url/XXXXX/", "random_reporter"\n',
            [
                {
                    'url': 'http://example1.com',
                    'time': '2018-07-12 16:18:02',
                },
                {
                    'url': 'http://www.example2.com',
                    'time': '2018-07-12 16:01:19',
                },
            ]
        )
        yield (
            'INVALID_DATA',
            IndexError
        )
        yield (
            '"this", "is", "invalid", "data", "to", "raise", "Value", "Error"',
            ValueError
        )


class TestAbuseChUrlhausUrls202001Parser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.urlhaus-urls'
    PARSER_CLASS = AbuseChUrlhausUrls202001Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'malurl',
    }

    def cases(self):
        # Valid JSON without signature, we expect to yield one event.
        yield ('''
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
        yield ('''
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
        yield ('''
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
        yield ('''
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
        yield ('''
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
        yield ('''
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
            'Invalid_JSON',
            ValueError
        )


class TestAbuseChUrlhausPayloadsUrlsParser(ParserTestMixIn, unittest.TestCase):

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
            '"2020-01-09 14:00:00","http://www.example1.com","exe","111a1111a111aa1a11a11111aa111111","1a1a11aa11a1a11aa11a1111111aaaaaaaaaaaaaa111111a1a1a1a1a1a1a1a11","None"\n'
            '"this is", "wrong", "line", "and", "should", "not_be_valid"\n'
            '"2020-01-09 15:00:00","http://www.example2.com","exe","222b2222b222bb2b22b22222bb222222","2b2b22bb22b2b22bb22b2222222bbbbbbbbbbbbbb222222b2b2b2b2b2b2b2b22","Example_Name_1"',
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
            '"this", "is", "invalid", "data", "to", "raise", "Value", "Error"',
            ValueError
        )

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

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
    AbuseChRansomwareTrackerParser,
    _AbuseChSSLBlacklistBaseParser,
    AbuseChSSLBlacklistDyreParser,
    AbuseChSSLBlacklistParser,
    AbuseChSSLBlacklistParser201902,
    AbuseChUrlhausUrlsParser,
)
from n6.parsers.generic import (
    BaseParser,
    BlackListTabDataParser,
    TabDataParser,
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
           'example.\xee.com \t 168.192.168.192 \t 1000 ',  # invalid fqdn but there are some IPs
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
                   address=[dict(ip='168.192.168.192')],
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
           ' 168.192.168.192\n',
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
                   address=[dict(ip='168.192.168.192')],
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
    yield ('''[["kendra.fr/KINS/panel/bot.exe (2015-06-10)", "URL: http://kendra.fr/KINS/panel/bot.exe, status: offline, MD5 hash: da95b3bf473c2e18537c925e640820b9"]]''',
            [{
                'time': '2015-06-10 00:00:00',
                'url': 'http://kendra.fr/KINS/panel/bot.exe',
                'md5': 'da95b3bf473c2e18537c925e640820b9',
            }]
        )
    yield ('''[["sjcvaleguia.com.br/Mix/valeg/bot.exe (2015-06-07)", "URL: http://sjcvaleguia.com.br/Mix/valeg/bot.exe, status: offline, MD5 hash: "]]''',
            [{
                'time': '2015-06-07 00:00:00',
                'url': 'http://sjcvaleguia.com.br/Mix/valeg/bot.exe',
            }]
        )
    yield ('''[["www.gkmexico.com/sos/css/bor.exe (2015-06-06)", "URL: http://www.gkmexico.com/sos/css/bor.exe, status: offline, MD5 hash: ff3a9e170c483b2bf0600ec257cd6d32"]]''',
            [{
                'time': '2015-06-06 00:00:00',
                'url': 'http://www.gkmexico.com/sos/css/bor.exe',
                'md5': 'ff3a9e170c483b2bf0600ec257cd6d32',
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
    some_input_data = '''["Host: 50.63.128.135, Version: C, Firstseen: 2015-06-01 13:35:33 UTC",
                        "Host: 50.66.128.136, Version: A, Firstseen: 2015-04-01 13:53:33 UTC",
                        "Host: 70.40.128.135, Version: f, Firstseen: 2015-04-28 08:53:33 UTC",
                        "Host: 50.66.128.100, Version: B, Firstseen: 2000-04-01 13:53:33 UTC"]'''

    def cases(self):
        yield (
            self.some_input_data,
            [
                {
                    'time': '2015-06-01 13:35:33',
                    'address': [{'ip': '50.63.128.135'}],
                    'name': 'feodo-emotet'
                },
                {
                    'time': '2015-04-01 13:53:33',
                    'address': [{'ip': '50.66.128.136'}],
                    'name': 'feodo'
                },
                # unknown 'Version' value, so a 'name' field
                # is skipped
                {
                    'time': '2015-04-28 08:53:33',
                    'address': [{'ip': '70.40.128.135'}],
                },
                {
                    'time': '2000-04-01 13:53:33',
                    'address': [{'ip': '50.66.128.100'}],
                    'name': 'feodo'
                }

            ]
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
        '"2016-11-08 13:11:44","Distribution Site","Locky","genelev.net",'
            '"http://genelev.net/slzk0i9","online","","5.135.214.248","16276","FR"\n'
        '"2016-11-08 13:10:35","Payment Site","Cerber","rokematin.com",'
            '"http://rokematin.com/0et8v","online","","2.176.241.230|2.176.241.230|67.171.65.64",'
            '"13055|7922","RU|US"\n'
        '"2016-02-28 13:13:13","Unknown Value","TalesFromTheCrypt","unknown.com",'
            '"http://unknown.com/24h","unknown","","","",""\n'
        '"2016-11-08 13:13:46","C2","TeslaCrypt","waag-azhar.com",'
            '"http://waag-azhar.com/ug4qr8h","unknown","","","",""\n'
    )

    def cases(self):
        yield (
            self.some_input_data,
            [
                dict(
                    address=[{'ip': '5.135.214.248'}],
                    url='http://genelev.net/slzk0i9',
                    time='2016-11-08 13:11:44',
                    name='Locky',
                    fqdn='genelev.net',
                    category='malurl'
                ),
                dict(
                    address=[{'ip': '2.176.241.230'}, {'ip': '67.171.65.64'}],
                    url='http://rokematin.com/0et8v',
                    time='2016-11-08 13:10:35',
                    name='Cerber',
                    fqdn='rokematin.com',
                    category='malurl'
                ),
                dict(
                    url='http://waag-azhar.com/ug4qr8h',
                    time='2016-11-08 13:13:46',
                    name='teslacrypt',
                    fqdn='waag-azhar.com',
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
            '{"https://sslbl.abuse.ch/intel/6800af01d6a5b83dc3e8c8d649101f7872719fce":'
            '{"name": "Gozi MITM", "timestamp": "2016-10-17 12:44:04",'
            '"fingerprint": "6800af01d6a5b83dc3e8c8d649101f7872719fce",'
            '"subject": "OU=Domain Control Validated, OU=PositiveSSL, CN=facenoplays.com",'
            '"issuer": "C=GB, ST=Greater Manchester, L=Salford, O=COMODO CA Limited, CN=COMODO"}}',
            [
                # 1st case: single, general event.
                dict(
                    time="2016-10-17 12:44:04",
                    x509fp_sha1="6800af01d6a5b83dc3e8c8d649101f7872719fce",
                    x509subject="OU=Domain Control Validated, OU=PositiveSSL, CN=facenoplays.com",
                    x509issuer="C=GB, ST=Greater Manchester, L=Salford, O=COMODO CA Limited, "
                               "CN=COMODO",
                    name="gozi mitm"
                ),
            ]
        )
        yield (
            # 2nd case: element with 2 associated binaries.
            '{"https://sslbl.abuse.ch/intel/5fcb5b418f779a542b7148f2ddea211495787733":'
            '{"name": "ZeuS C&C", "timestamp": "2016-10-17 11:52:40",'
            '"fingerprint": "5fcb5b418f779a542b7148f2ddea211495787733",'
            '"subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",'
            '"issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",'
            '"binaries": [["2016-10-13 16:27:10", "76b609dac79e76fe7b5a78af35c5a2d6", '
            '"52.77.110.77", "443"], ["2016-10-10 17:29:57", "9096210f20753c836378ca7aa18c3d25", '
            '"52.77.110.78", "444"]]}}',
            [
                dict(
                    time="2016-10-13 16:27:10",
                    x509fp_sha1="5fcb5b418f779a542b7148f2ddea211495787733",
                    x509subject="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    x509issuer="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    name="zeus c&c",
                    md5="76b609dac79e76fe7b5a78af35c5a2d6",
                    address=[{'ip': '52.77.110.77'}],
                    dport=443
                ),
                dict(
                    time="2016-10-10 17:29:57",
                    x509fp_sha1="5fcb5b418f779a542b7148f2ddea211495787733",
                    x509subject="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    x509issuer="C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                    name="zeus c&c",
                    md5="9096210f20753c836378ca7aa18c3d25",
                    address=[{'ip': '52.77.110.78'}],
                    dport=444
                ),
            ]
        )
        yield (
            # 3rd case: 2 associated binaries.
            '{"https://sslbl.abuse.ch/intel/e03e335629b882f1f03f091123511eaa3fc2d6b1":'
            '{"name": "Gootkit C&C", "timestamp": "2016-10-14 11:13:35",'
            '"fingerprint": "e03e335629b882f1f03f091123511eaa3fc2d6b1",'
            '"subject": "C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",'
            '"issuer": "C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",'
            '"binaries": [["fb890a2b17cc70e0fde9ec9adc01b6b9", '
            '"146.148.124.166", "80"], ["2016-10-13 15:50:13", "e8e999747a8e94b65b42e8073ddb1b93",'
            ' "146.148.124.166", "80"]]}}',
            [
                # 3rd case: first event is skipped, incomplete list
                # of items of the associated binary.
                dict(
                    time="2016-10-13 15:50:13",
                    x509fp_sha1="e03e335629b882f1f03f091123511eaa3fc2d6b1",
                    x509subject="C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",
                    x509issuer="C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd",
                    name="gootkit c&c",
                    md5="e8e999747a8e94b65b42e8073ddb1b93",
                    address=[{'ip': '146.148.124.166'}],
                    dport=80
                ),
            ]
        )
        yield (
            # 4th case: empty binaries list, no timestamp, element skipped.
            '{"https://sslbl.abuse.ch/intel/572efc1d71cb6a4911c14393f1825857793a1869":'
            '{"name": "Gootkit C&C",'
            '"fingerprint": "572efc1d71cb6a4911c14393f1825857793a1869",'
            '"subject": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost",'
            '"issuer": "C=US, ST=CA, L=Los Angeles, O=Domain, OU=INC DOMAIN, '
            'CN=localhost/emailAddress=webmater@localhost",'
            '"binaries": []}}',
            ValueError
        )
        yield (
            # 5th case: empty 'fingerprint' field, element skipped.
            '{"https://sslbl.abuse.ch/intel/0d195d036ffc65bffe0bcf2e82da6b83a61fb577":'
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
            '{"https://sslbl.abuse.ch/intel/4cf13433ad8784cae053fe51a38643a8b5dc2b3e":'
            '{"name": "TorrentLocker C&C", "timestamp": "2016-10-06 05:31:14",'
            '"fingerprint": "4cf13433ad8784cae053fe51a38643a8b5dc2b3e",'
            '"subject": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"issuer": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"binaries": [["fc38b33ebd8d08361eb4c0258bc772ce", '
            '"146.148.124.166"]]}}',
            [
                dict(
                    time="2016-10-06 05:31:14",
                    x509fp_sha1="4cf13433ad8784cae053fe51a38643a8b5dc2b3e",
                    x509subject="C=US, ST=Denial, L=Springfield, O=Dis",
                    x509issuer="C=US, ST=Denial, L=Springfield, O=Dis",
                    name="torrentlocker c&c"
                ),
            ]
        )
        yield (
            # 7th case: invalid binaries, no timestamp in general
            # details, skip the whole event.
            '{"https://sslbl.abuse.ch/intel/de8019406cb50a7c5382ed8c86cb468b06ee6e24":'
            '{"name": "TorrentLocker C&C",'
            '"fingerprint": "de8019406cb50a7c5382ed8c86cb468b06ee6e24",'
            '"subject": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"issuer": "C=US, ST=Denial, L=Springfield, O=Dis",'
            '"binaries": [["47305a1851f2ac1a1ee8c4b5ebee6ec2", '
            '"185.155.96.110"]]}}',
            ValueError
        )


class TestAbuseChSSLBlacklistParser(_TestAbuseChSSLBlacklistParserBase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist'
    PARSER_CLASS = AbuseChSSLBlacklistParser


class TestAbuseChSSLBlacklistDyreParser(_TestAbuseChSSLBlacklistParserBase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist-dyre'
    PARSER_CLASS = AbuseChSSLBlacklistDyreParser


class TestAbuseChSSLBlacklistsParser201902(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.ssl-blacklist'
    PARSER_CLASS = AbuseChSSLBlacklistParser201902
    PARSER_BASE_CLASS = TabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'cnc',
    }

    def cases(self):
        yield (
            '2019-02-26 15:42:09,7112c502625cec0a0211714f8d5c2972868963d4,Gozi C&C\n'
            'this_line,should_not,be_here\n'
            '2019-02-26 06:40:29,8adcad74167f5b27d47a4f629d11aa187710fd41,Malware C&C\n',
        [
            {
                'category': 'cnc',
                'restriction': 'public',
                'confidence': 'low',
                'name': 'gozi c&c',
                'x509fp_sha1': '7112c502625cec0a0211714f8d5c2972868963d4',
                'time': '2019-02-26 15:42:09',
            },
            {
                'category': 'cnc',
                'restriction': 'public',
                'confidence': 'low',
                'name': 'malware c&c',
                'x509fp_sha1': '8adcad74167f5b27d47a4f629d11aa187710fd41',
                'time': '2019-02-26 06:40:29',
            }

        ])

        yield (
            'asdasd',
            IndexError
        )


class TestAbuseChUrlhausUrlsParser(ParserTestMixIn, unittest.TestCase):

    PARSER_SOURCE = 'abuse-ch.urlhaus-urls'
    PARSER_CLASS = AbuseChUrlhausUrlsParser
    PARSER_BASE_CLASS = TabDataParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'malurl',
    }

    def cases(self):
        yield (
            '"31629","2018-07-12 16:18:02","http://10.20.30.40/bins/x86.foobar","online","malware_download","None","https://urlhaus.abuse.ch/url/31629/"\n'
            '"this is", wrong, line\n'
            '"31628","2018-07-12 16:01:19","http://www.example.in/pdf/EN_en/Jul2018/Pay-Invoice/","online","malware_download","doc,emotet","https://urlhaus.abuse.ch/url/31628/"\n',
            [
                {
                    'category': 'malurl',
                    'restriction': 'public',
                    'confidence': 'low',
                    'url': 'http://10.20.30.40/bins/x86.foobar',
                    'source': 'abuse-ch.urlhaus-urls',
                    'time': '2018-07-12 16:18:02',
                },
                {
                    'category': 'malurl',
                    'restriction': 'public',
                    'confidence': 'low',
                    'url': 'http://www.example.in/pdf/EN_en/Jul2018/Pay-Invoice/',
                    'source': 'abuse-ch.urlhaus-urls',
                    'time': '2018-07-12 16:01:19',
                },
            ]
        )
        yield (
            'asdasd',
            IndexError
        )

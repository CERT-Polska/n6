# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
import unittest

from n6lib.record_dict import (
    BLRecordDict,
)
from n6datasources.parsers.base import (
    BaseParser,
    BlackListParser,
)
from n6datasources.parsers.shadowserver import (
    ShadowserverVnc201412Parser,
    _BaseShadowserverParser,
    ShadowserverCompromisedWebsite201412Parser,
    ShadowserverIpmi201412Parser,
    ShadowserverChargen201412Parser,
    ShadowserverNetbios201412Parser,
    ShadowserverNetis201412Parser,
    ShadowserverNtpVersion201412Parser,
    ShadowserverQotd201412Parser,
    ShadowserverRedis201412Parser,
    ShadowserverSmb201412Parser,
    ShadowserverSnmp201412Parser,
    ShadowserverSsdp201412Parser,
    ShadowserverSslPoodle201412Parser,
    ShadowserverMemcached201412Parser,
    ShadowserverMongodb201412Parser,
    ShadowserverMssql201412Parser,
    ShadowserverNatpmp201412Parser,
    ShadowserverDb2201412Parser,
    ShadowserverOpenResolver201412Parser,
    ShadowserverSandboxUrl201412Parser,
    ShadowserverElasticsearch201412Parser,
    ShadowserverSslFreak201412Parser,
    ShadowserverNtpMonitor201412Parser,
    ShadowserverPortmapper201412Parser,
    ShadowserverMdns201412Parser,
    ShadowserverXdmcp201412Parser,
    ShadowserverRdp201412Parser,
    ShadowserverTftp201412Parser,
    ShadowserverIsakmp201412Parser,
    ShadowserverTelnet201412Parser,
    ShadowserverCwmp201412Parser,
    ShadowserverLdap201412Parser,
    ShadowserverSinkholeHttp202203Parser,
    ShadowserverSinkhole202203Parser,
    ShadowserverDarknet202203Parser,
    ShadowserverModbus202203Parser,
    ShadowserverIcs202204Parser,
    ShadowserverCoap202204Parser,
    ShadowserverUbiquiti202204Parser,
    ShadowserverArd202204Parser,
    ShadowserverRdpeudp202204Parser,
    ShadowserverDvrDhcpdiscover202204Parser,
    ShadowserverHttp202204Parser,
    ShadowserverFtp202204Parser,
    ShadowserverMqtt202204Parser,
    ShadowserverLdapTcp202204Parser,
    ShadowserverRsync202204Parser,
    ShadowserverRadmin202204Parser,
    ShadowserverAdb202204Parser,
    ShadowserverAfp202204Parser,
    ShadowserverCiscoSmartInstall202204Parser,
    ShadowserverIpp202204Parser,
    ShadowserverHadoop202204Parser,
    ShadowserverExchange202204Parser,
    ShadowserverSmtp202204Parser,
    ShadowserverAmqp202204Parser,
)
from n6datasources.tests.parsers._parser_test_mixin import ParserTestMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc



class TestShadowserverIpmi201412Parse(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ipmi'
    PARSER_CLASS = ShadowserverIpmi201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ipmi',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","ipmi_version","asn","geo","region","city",'
            b'"none_auth","md2_auth","md5_auth","passkey_auth","oem_auth","defaultkg",'
            b'"permessage_auth","userlevel_auth","usernames","nulluser","anon_login","error",'
            b'"deviceid","devicerev","firmwarerev","version","manufacturerid","manufacturername",'
            b'"productid","productname"\n'
            b'"2014-06-23 01:09:21","1.1.1.1","623","","ipmi","2.0","11111","PL",'
            b'"EXAMPLE_LOCATION","EXAMPLE_LOCATION_2","yes","yes","yes","yes","yes","default",'
            b'"enabled", "enabled","yes","no","no","","","","","","","","",""\n',

            [
                dict(
                    time='2014-06-23 01:09:21',
                    address=[{'ip': '1.1.1.1'}],
                    name='ipmi',
                    dport=623,
                    ipmi_version='2.0',
                ),
            ]
        )


class TestShadowserverCompromisedWebsiteParser(ParserTestMixin, unittest.TestCase):

    RECORD_DICT_CLASS = BLRecordDict

    PARSER_SOURCE = 'shadowserver.compromised-website'
    PARSER_CLASS = ShadowserverCompromisedWebsite201412Parser
    PARSER_BASE_CLASS = BlackListParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'low',
    }

    def cases(self):
        date = str(parse_iso_datetime_to_utc(
                ParserTestMixin.message_created) + datetime.timedelta(
                days=ShadowserverCompromisedWebsite201412Parser.EXPIRES_DAYS))

        yield (
            b'"timestamp","ip","port","hostname","tag","application","asn","geo","region","city",'
            b'"url","http_host","category","system","detected_since","server"\n'

            b'"2014-06-22 00:18:59","1.1.1.1","80","example1.pl",'
            b'"name1","http","11111","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example.com","spam","Linux","2014-05-17 00:20:00",""\n'

            b'"2024-06-22 11:18:59","2.2.2.2","80","example2.com",'
            b'"name2","http","22222","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example2.com","bbbbb","Linux","2014-05-17 00:20:00",""\n'

            b'"2024-06-22 11:18:59","3.3.3.3","80","example3.com",'
            b'"name3","http","33333","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example3.com","cnc","Linux","2014-05-17 00:20:00",""\n'

            b'"2024-06-22 11:18:59","4.4.4.4","80","example4.com",'
            b'"name4","http","444444","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example4.com","ddos","Linux","2014-05-17 00:20:00",""\n'

            b'"2024-06-22 11:18:59","5.5.5.5","80","example5.com",'
            b'"name5","http","55555","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example5.com","malwarehosting","Linux",'

            b'"2014-05-17 00:20:00",""\n'

            b'"2024-06-22 11:18:59","6.6.6.6","80","example6.com",'
            b'"name6","http","66666","PL","ExampleLoc","ExampleLoc",'
            b'"media/system/css/login.php","example6.com","phishing","Linux","2014-05-17 00:20:00",""\n'
            ,
            [
                dict(
                    self.get_bl_items(1, 6),
                    time='2014-06-22 00:18:59',
                    address=[{'ip': '1.1.1.1'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name1',
                    fqdn='example.com',
                    category='spam',
                    detected_since="2014-05-17 00:20:00",
                ),
                dict(
                    self.get_bl_items(2, 6),
                    time='2024-06-22 11:18:59',
                    address=[{'ip': '2.2.2.2'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name2',
                    fqdn='example2.com',
                    category='other',
                    detected_since="2014-05-17 00:20:00",
                ),
                dict(
                    self.get_bl_items(3, 6),
                    time='2024-06-22 11:18:59',
                    address=[{'ip': '3.3.3.3'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name3',
                    fqdn='example3.com',
                    category='cnc',
                    detected_since="2014-05-17 00:20:00",
                ),
                dict(
                    self.get_bl_items(4, 6),
                    time='2024-06-22 11:18:59',
                    address=[{'ip': '4.4.4.4'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name4',
                    fqdn='example4.com',
                    category='dos-attacker',
                    detected_since="2014-05-17 00:20:00",
                ),
                dict(
                    self.get_bl_items(5, 6),
                    time='2024-06-22 11:18:59',
                    address=[{'ip': '5.5.5.5'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name5',
                    fqdn='example5.com',
                    category='malurl',
                    detected_since="2014-05-17 00:20:00",
                ),
                dict(
                    self.get_bl_items(6, 6),
                    time='2024-06-22 11:18:59',
                    address=[{'ip': '6.6.6.6'}],
                    request='media/system/css/login.php',
                    dport=80,
                    expires=date,
                    name='name6',
                    fqdn='example6.com',
                    category='phish',
                    detected_since="2014-05-17 00:20:00",
                ),
            ]
        )


class TestShadowserverChargen201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.chargen'
    PARSER_CLASS = ShadowserverChargen201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'chargen',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","size","asn",'
            b'"geo","region","city"\n'
            b'"2014-03-24 04:16:38","1.1.1.1","udp","19",'
            b'"example.pl","chargen","","11111","PL",'
            b'"EXAMPLE_LOCATION_1","EXAMPLE_LOCATION_2"\n'
            ,
            [
                dict(
                    time='2014-03-24 04:16:38',
                    address=[{'ip': '1.1.1.1'}],
                    dport=19,
                    proto='udp',
                ),

            ]
        )


class TestShadowserverMemcached201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.memcached'
    PARSER_CLASS = ShadowserverMemcached201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'memcached',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","pid","pointer_size","uptime","time","curr_connections",'
            b'"total_connections"\n'
            b'"2015-03-14 00:31:27","1.1.1.1","tcp",11211,"example.pl","memcached",'
            b'"1.1.10",1111,"PL","ExampleLocation1","ExampleLocation2",0,0,3194,64,11111111,'
            b'"2015-03-14 00:31:28",10,148\n',

            [
                dict(
                    time='2015-03-14 00:31:27',
                    address=[{'ip': '1.1.1.1'}],
                    dport=11211,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverMongodbParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.mongodb'
    PARSER_CLASS = ShadowserverMongodb201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'mongodb',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","gitversion","sysinfo","opensslversion","allocator",'
            b'"javascriptengine","bits","maxbsonobjectsize","ok","visible_databases"\n'
            b'"2015-03-14 00:35:50","1.1.1.1","tcp",27017,"example.pl",'
            b'"mongodb","2.0.6",11111,"PL","ExampleLoc1","ExampleLoc2",0,0,"1a1a1a1a1a1a1a1a1a1a1",'
            b'"Linux ip-1.1.1.1 example_exaple #1 SMP Fri Nov '
            b'20 17:48:28 EST 2009 x86_64 BOOST_LIB_VERSION=1234",,,,64,16777216,1,"example_db"\n',
            [
                dict(
                    time='2015-03-14 00:35:50',
                    address=[{'ip': '1.1.1.1'}],
                    dport=27017,
                    proto='tcp',
                    visible_databases="example_db"
                ),
            ]
        )


class TestShadowserverNatpmp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.natpmp'
    PARSER_CLASS = ShadowserverNatpmp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'nat-pmp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","opcode","uptime","external_ip"\n'
            b'"2015-03-17 06:08:42","1.1.1.1","udp",5351,"example.pl",'
            b'"example",0,111111,"PL","ExampleLoc1","ExampleLoc2",0,0,111,111111,"0.0.0.0"\n',
            [
                dict(
                    time='2015-03-17 06:08:42',
                    address=[{'ip': '1.1.1.1'}],
                    dport=5351,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverMssql201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.mssql'
    PARSER_CLASS = ShadowserverMssql201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'mssql',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","server_name","instance_name","tcp_port","named_pipe",'
            b'"response_length","amplification"\n'
            b'"2015-03-14 06:38:42","1.1.1.1","udp",1434,"example.pl",'
            b'"mssql","10.10.2500.10",11111,"PL","ExampleLoc1","ExampleLoc2",111111,222222,'
            b'"WHATEVER","INSERTGT",2283,"\\WHATEVER\\example",310,"6.89"\n',
            [
                dict(
                    time='2015-03-14 06:38:42',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1434,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverNetbios201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.netbios'
    PARSER_CLASS = ShadowserverNetbios201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'netbios',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","mac_address","asn","geo",'
            b'"region","city","workgroup","machine_name","username"\n'
            b'"2014-04-22 00:12:57","1.1.1.1","udp",137,"example.pl","netbios",'
            b'"00-00-00-00-00-00",111111,"PL","ExampleLoc1","ExampleLoc2","WORKGROUP",'
            b'"Example-ABC12345",\n'
            ,
            [
                dict(
                    time='2014-04-22 00:12:57',
                    address=[{'ip': '1.1.1.1'}],
                    dport=137,
                    mac_address='00-00-00-00-00-00',
                    proto='udp',
                ),

            ]
        )


class TestShadowserverNetis201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.netis'
    PARSER_CLASS = ShadowserverNetis201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'netis-router',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","response","asn","geo","region","city",'
            b'"naics","sic"\n'
            b'"2015-01-09 03:49:16","1.1.1.1",53413,"ip-1-1-1-1.example.pl",'
            b'"example_vulnerability","Login:",11111,"PL","ExampleLoc1","ExampleLoc2",0,0',
            [
                dict(
                    time='2015-01-09 03:49:16',
                    address=[{'ip': '1.1.1.1'}],
                    dport=53413,
                ),
            ]
        )


class TestShadowserverNtpVersion201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ntp-version'
    PARSER_CLASS = ShadowserverNtpVersion201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ntp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","asn","geo","region","city","version",'
            b'"clk_wander","clock","error","frequency","jitter","leap","mintc","noise","offset",'
            b'"peer","phase","poll","precision","processor","refid","reftime","rootdelay",'
            b'"rootdispersion","stability","state","stratum","system","tai","tc"\n'
            b'"2014-03-24 02:14:37","1.1.1.1","udp",123,,11111,"PL","ExampleLoc1","ExampleLoc2",'
            b'4,"0.000","0x01234567.89ABCDEF",,"0.000","0.000",0,3,,"0.000",,,,"-10","unknown",'
            b'"2.2.2.2","0xABCDEF01.23456789","0.000","0.000",,,4,"UNIX",,10\n',
            [
                dict(
                    time='2014-03-24 02:14:37',
                    address=[{'ip': '1.1.1.1'}],
                    dport=123,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverQotd201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.qotd'
    PARSER_CLASS = ShadowserverQotd201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'qotd',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","quote","asn","geo","region",'
            b'"city"\n'
            b'"2014-12-01 12:09:00","1.1.1.1","udp",17,"example-host.example.com",'
            b'"qotd","Example_Example" ??",1111,"PL",ExampleLoc","ExampleLoc"\n',
            [
                dict(
                    time='2014-12-01 12:09:00',
                    address=[{'ip': '1.1.1.1'}],
                    dport=17,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverRedis201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.redis'
    PARSER_CLASS = ShadowserverRedis201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'redis',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","git_sha1","git_dirty_flag","build_id","mode","os",'
            b'"architecture","multiplexing_api","gcc_version","process_id","run_id","uptime",'
            b'"connected_clients"\n'
            b'"2015-03-14 00:39:44","1.1.1.1","tcp",6379,"ip-1-1-1-1.example.'
            b'com","redis","1.2.3",11111,"PL",ExampleLoc","ExampleLoc",0,0,00000000,0,"1111111'
            b'111aa11","standalone","Linux 1.2.3-4-amd64 x86_64",,"epoll","5.6.7",1111,"example123'
            b'example123456789abcdef01234",5678901,3\n',
            [
                dict(
                    time='2015-03-14 00:39:44',
                    address=[{'ip': '1.1.1.1'}],
                    dport=6379,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverSmb201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.smb'
    PARSER_CLASS = ShadowserverSmb201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'smb',
        'proto': 'tcp',
    }

    def cases(self):
        yield(
            b'"timestamp","ip","port","hostname","asn","geo","region","city","naics'
            b'","sic","smb_implant","arch","key" \n'

            b'"2017-08-11 05:10:04","1.2.3.4",445,"ex.example.com",1111,"PL",'
            b'ExampleLocE","ExampleLoc",123456,654321,"N",,\n'

            b'"2017-08-11 05:10:11","2.3.4.5",445,"ex1.example.org",12345,"PL",'
            b'"ExampleLoc","ExampleLoc",0,0,"N",,\n'

            b'"2017-08-11 05:10:12","3.4.5.6",445,"ex3.example.net",11111,"PL",'
            b'ExampleLoc","ExampleLoc",0,0,"N",,\n'

            b'"2017-08-11 05:10:17","4.5.6.7",445,,1111,"PL",'
            b'ExampleLoc,ExampleLoc",0,0,"N",,',
            [
                dict(
                    time='2017-08-11 05:10:04',
                    address=[{'ip': '1.2.3.4'}],
                    dport=445,
                ),
                dict(
                    time='2017-08-11 05:10:11',
                    address=[{'ip': '2.3.4.5'}],
                    dport=445,
                ),
                dict(
                    time='2017-08-11 05:10:12',
                    address=[{'ip': '3.4.5.6'}],
                    dport=445,
                ),
                dict(
                    time='2017-08-11 05:10:17',
                    address=[{'ip': '4.5.6.7'}],
                    dport=445,
                ),
            ]
        )


class TestShadowserverSnmp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.snmp'
    PARSER_CLASS = ShadowserverSnmp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'snmp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","sysdesc","sysname","asn","geo",'
            b'"region","city","version"\n'
            b'"2014-03-24 04:13:12","1.1.1.1","udp","10448","1.1.1.1.example.com'
            b'-example","EX-Example1234","","11111","PL",ExampleLoc","ExampleLoc","2"\n',
            [
                dict(
                    time='2014-03-24 04:13:12',
                    address=[{'ip': '1.1.1.1'}],
                    dport=10448,
                    proto='udp',
                    sysdesc='EX-Example1234',
                    version='2',
                ),
            ]
        )


class TestShadowserverSsdpParser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ssdp'
    PARSER_CLASS = ShadowserverSsdp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ssdp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","header","asn","geo","region",'
            b'"city","systime","cache_control","location","server","search_target",'
            b'"unique_service_name","host","nts","nt"\n'
            b'"2014-12-02 09:12:54","1.1.1.1","udp",1900,"example.pl",'
            b'"ssdp","HTTP/1.1 200 OK",1111,"PL","SL","EXAMPLE_CITY",,"max-age=1200","http://1.1.1.1.'
            b'example.com,"qwertyuiopASDFGHJKLzxcvbnm","upnp:rootdevice","'
            b'asdasdasasadevice",,,\n',
            [
                dict(
                    time='2014-12-02 09:12:54',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1900,
                    proto='udp',
                    header='HTTP/1.1 200 OK',
                ),
            ]
        )


class TestShadowserverSslPoodle201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ssl-poodle'
    PARSER_CLASS = ShadowserverSslPoodle201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ssl-poodle',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","handshake","asn","geo","region","city",'
            b'"cipher_suite","ssl_poodle","cert_length","subject_common_name","issuer_common_name"'
            b',"cert_issue_date","cert_expiration_date","sha1_fingerprint","cert_serial_number",'
            b'"ssl_version","signature_algorithm","key_algorithm","subject_organization_name",'
            b'"subject_organization_unit_name","subject_country","subject_state_or_province_name",'
            b'"subject_locality_name","subject_street_address","subject_postal_code",'
            b'"subject_surname","subject_given_name","subject_email_address",'
            b'"subject_business_category","subject_serial_number","issuer_organization_name",'
            b'"issuer_organization_unit_name","issuer_country","issuer_state_or_province_name",'
            b'"issuer_locality_name","issuer_street_address","issuer_postal_code","issuer_surname",'
            b'"issuer_given_name","issuer_email_address","issuer_business_category",'
            b'"issuer_serial_number","naics","sic"\n'
            b'"2015-01-09 01:30:25","1.1.1.1",443,"1.1.1.1.example.net.pl","ssl",'
            b'"TLSv1.0",11111,"PL","ExampleLOc","ExampleLOc","TLS_RSA_WITH_RC4_128_SHA","Y",1024,'
            b'"2.2.2.2","ExampleName CA","Nov  6 19:14:57 2013 GMT","Nov  1 19:14:57 2033 GMT",'
            b'"11:AA:11:1A:AA:11:A1:11:1A:A1:A1:A1:A1:A1:A1:A1:A1:A1:A1:A1","1A11AAA1",2,'
            b'"sha1WithRSAEncryption","rsaEncryption",,,"IL",,,,,,,,,,,,"US",,,,,,,,,,,\n',
            [
                dict(
                    time='2015-01-09 01:30:25',
                    address=[{'ip': '1.1.1.1'}],
                    dport=443,
                    handshake='TLSv1.0',
                    cert_length='1024',
                    subject_common_name='2.2.2.2',
                ),
            ]
        )


class TestShadowserverSandboxUrl201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.sandbox-url'
    PARSER_CLASS = ShadowserverSandboxUrl201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'sandbox-url',
        'origin': 'sandbox',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","asn","geo","md5hash","url","user_agent","host","method"\n'
            b'"2014-11-01 01:08:48","1.1.1.1",11111,"PL","111aa111a11a1aa111a1aaaa111aaaa1"'
            b',"http://example_1.com","Opera/9.50 (Windows NT '
            b'6.0; U; en)","example_1.com","GET"\n'
            b'"2014-11-01 01:47:50","2.2.2.2",11111,"PL","222bb222b22b2bb222b2bbbb222bbbb2"'
            b',"http://example.com/","Mozilla/4.0 (compatible; '
            b'MSIE 6.0; Windows NT 5.1; SV1)","example.com'
            b'","POST"',
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    md5='111aa111a11a1aa111a1aaaa111aaaa1',
                    url='http://example_1.com',
                    fqdn='example_1.com',
                    method='GET',
                    time='2014-11-01 01:08:48',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    md5='222bb222b22b2bb222b2bbbb222bbbb2',
                    url='http://example.com/',
                    fqdn='example.com',
                    method='POST',
                    time='2014-11-01 01:47:50',
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverOpenResolver201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.open-resolver'
    PARSER_CLASS = ShadowserverOpenResolver201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'resolver',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","asn","geo","region","city","port","protocol",'
            b'"hostname","min_amplification","dns_version","p0f_genre","p0f_detail"\n'

            b'"2013-08-22 00:00:00","1.1.1.1",11111,"PL","ExampleLoc","ExampleLoc",53,"udp",'
            b',"1.3810","DNS_VERSION",,\n'

            b'"2013-08-22 00:00:01","2.2.2.2",22222,"PL","ExampleLoc","ExampleLoc",53,"udp",'
            b'"host.example.pl","1.3810",,,\n'
            ,
            [
                dict(
                    address=[{'ip': '1.1.1.1'}],
                    dport=53,
                    proto='udp',
                    min_amplification='1.3810',
                    dns_version='DNS_VERSION',
                    time='2013-08-22 00:00:00',
                ),
                dict(
                    address=[{'ip': '2.2.2.2'}],
                    dport=53,
                    fqdn='host.example.pl',
                    proto='udp',
                    min_amplification='1.3810',
                    time='2013-08-22 00:00:01',
                ),
            ]
        )



class TestShadowserverElasticsearch201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.elasticsearch'
    PARSER_CLASS = ShadowserverElasticsearch201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'elasticsearch',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-02-04 14:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region",'
            b'"city","naics","sic","ok","name","cluster_name","status","build_hash",'
            b'"build_timestamp","build_snapshot","lucene_version","tagline"\n'
            b'"2015-10-03 00:31:48","1.1.1.1","tcp",9200,"1-1-1-1.dynamic.example.pl",'
            b'"elasticsearch","1.2.3",11111,"PL","ExampleLoc","ExampleLoc",0,0,,"node1","Example",'
            b'200,"12312asdadasdasdadasdasdasd13121asd21","2015-02-19T13:05:36Z","false",'
            b'"7.8.9","You Know, for Search"\n'
            ,
            [
                dict(
                    time='2015-10-03 00:31:48',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    dport=9200,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverSslFreak201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ssl-freak'
    PARSER_CLASS = ShadowserverSslFreak201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ssl-freak',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-02-06 12:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","handshake","asn","geo","region","city",'
            b'"cipher_suite","cert_length","subject_common_name","issuer_common_name",'
            b'"cert_issue_date","cert_expiration_date","sha1_fingerprint","cert_serial_number",'
            b'"signature_algorithm","key_algorithm","subject_organization_name",'
            b'"subject_organization_unit_name","subject_country","subject_state_or_province_name",'
            b'"subject_locality_name","subject_street_address","subject_postal_code",'
            b'"subject_surname","subject_given_name","subject_email_address",'
            b'"subject_business_category","subject_serial_number","issuer_organization_name",'
            b'"issuer_organization_unit_name","issuer_country","issuer_state_or_province_name",'
            b'"issuer_locality_name","issuer_street_address","issuer_postal_code","issuer_surname",'
            b'"issuer_given_name","issuer_email_address","issuer_business_category",'
            b'"issuer_serial_number",'
            b'"naics","sic","freak_vulnerable","freak_cipher_suite"\n'

            b'"2015-09-20 00:45:47","1.1.1.1",443,,"ssl-freak","TLSv1.0",11111,"PL",'
            b'"ExampleLoc","ExampleLoc","TLS_RSA_WITH_RC4_128_SHA",1024,"Example AB123cd",'
            b'"Example AB123cd","2005-01-01 00:00:00","2024-12-31 00:00:00",'
            b'"AA:AA:AA:11:11:1A:1A:1A:1A:1A:1A:1A:1A:1A:1A:1A:AA:11:1A:A1","-7654321D",'
            b'"sha1WithRSAEncryption","rsaEncryption","Example","123QWERTY",,,,,,,,,,,'
            b'"Example","123QWERTY",,,,,,,,,,,0,0,"Y","Example"\n'

            b'"2015-09-20 00:45:41","3.3.3.3",443,,"ssl-freak","TLSv1.0",33333,"PL",'
            b'"ExampleLoc","ExampleLoc","Example",1024,"Example AB123cd",'
            b'"Example AB123cd","2005-01-01 00:00:00","2024-12-31 00:00:00",'
            b'"BB:AA:BB:BB:AA:BB:AA:BB:AA:BB:AA:B4:BB:BB:BB:BA:BB:AB:BB:BA","-1234567",'
            b'"sha1WithRSAEncryption","rsaEncryption","Example","1234ASDFG",,,,,,,,,,,'
            b'"Example","1234ASDFG",,,,,,,,,,,111111,222222,"Y",'
            b'"TLS_RSA_EXPORT_WITH_RC4_40_MD5"\n'

            b'"2015-09-20 00:45:47","2.2.2.2",443,,"ssl-freak","TLSv1.0",22222,"PL",'
            b'"ExampleLoc","ExampleLoc","TLS_RSA_WITH_RC4_128_SHA",1024,"Example AB123cd",'
            b'"Example AB123cd","2005-01-01 00:00:00","2024-12-31 00:00:00",'
            b'"CC:CB:BC:CC:CC:CC:CC:CC:CC:CB:CC:CC:CC:CC:CC:BC:CC:BB:CC:CB","-7654321D",'
            b'"sha1WithRSAEncryption","rsaEncryption","Example","123QWERTY",,,,,,,,,,,'
            b'"Example","123QWERTY",,,,,,,,,,,0,0,"Y","Example"\n'
            ,
            [
                dict(
                    time='2015-09-20 00:45:47',
                    address=[{'ip': '1.1.1.1'}, ],
                    proto='tcp',
                    dport=443,
                    handshake='TLSv1.0',
                    cert_length='1024',
                    subject_common_name='Example AB123cd',
                ),
                dict(
                    time='2015-09-20 00:45:41',
                    address=[{'ip': '3.3.3.3'}, ],
                    proto='tcp',
                    dport=443,
                    handshake='TLSv1.0',
                    cert_length='1024',
                    subject_common_name='Example AB123cd',
                ),
                dict(
                    time='2015-09-20 00:45:47',
                    address=[{'ip': '2.2.2.2'}, ],
                    proto='tcp',
                    dport=443,
                    handshake='TLSv1.0',
                    cert_length='1024',
                    subject_common_name='Example AB123cd',
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverNtpMonitor201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ntp-monitor'
    PARSER_CLASS = ShadowserverNtpMonitor201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ntp',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-01-03 11:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","packets","size","asn","geo","region",'
            b'"city","naics","sic"\n'

            b'"2015-09-23 06:09:24","1.1.1.1","udp",123,"example.pl",'
            b'80,11111,1111,"PL","ExampleLoc","ExampleLoc",111111,222222\n'

            b'"2015-09-23 06:09:27","2.2.2.2","udp",123,"2-2-2-2.example.pl",'
            b'1,80,22222,"PL","ExampleLoc","ExampleLoc",0,0\n'

            b'"2015-09-23 06:09:46","3.3.3.3","udp",123,"example.pl",11,'
            b'33333,3333,"PL","ExampleLoc","ExampleLoc",111111,222222\n'
            ,
            [
                dict(
                    time='2015-09-23 06:09:24',
                    address=[{'ip': '1.1.1.1'}, ],
                    proto='udp',
                    dport=123,
                ),
                dict(
                    time='2015-09-23 06:09:27',
                    address=[{'ip': '2.2.2.2'}, ],
                    proto='udp',
                    dport=123,
                ),
                dict(
                    time='2015-09-23 06:09:46',
                    address=[{'ip': '3.3.3.3'}, ],
                    proto='udp',
                    dport=123,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverPortmapper201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.portmapper'
    PARSER_CLASS = ShadowserverPortmapper201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'portmapper',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-02-03 08:21:13'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","programs","mountd_port","exports"\n'

            b'"2015-10-03 04:11:31","1.1.1.1","udp",111,"example.net",'
            b'"portmapper",11111,"PL","ExampleLoc","ExampleLoc",0,0,"100000 2 111/udp; 100000 2 '
            b'111/udp; 100003 2 100003 1 333/udp; 100004 1 333/udp; 100011 1 222/udp; 100011 2 '
            b'333/udp; 100011 1 777/udp; 100011 2 777/udp;",789,"/ 3.3.3.3;"\n'

            b'"2015-10-03 04:11:32","2.2.2.2","udp",111,"example.net",'
            b'"portmapper",44444,"PL","ExampleLoc","ExampleLoc",0,0,"100000 2 111/udp; 100000 2 '
            b'111/udp; 100004 1 54321/udp; 100004 1 56789/udp;",,\n'
            ,
            [
                dict(
                    time='2015-10-03 04:11:31',
                    address=[{'ip': '1.1.1.1'}, ],
                    proto='udp',
                    dport=111,
                ),
                dict(
                    time='2015-10-03 04:11:32',
                    address=[{'ip': '2.2.2.2'}, ],
                    proto='udp',
                    dport=111,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverMdns201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.mdns'
    PARSER_CLASS = ShadowserverMdns201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'mdns',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-02-10 19:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region",'
            b'"city","naics","sic","mdns_name","mdns_ipv4","mdns_ipv6","services",'
            b'"workstation_name","workstation_ipv4","workstation_ipv6","workstation_info",'
            b'"http_name","http_ipv4","http_ipv6","http_ptr","http_info","http_target",'
            b'"http_port"\n'

            b'"2016-03-21 07:38:47","1.1.1.1","udp",5353,"example.com","mdns",11111,'
            b'"PL","Example","Example",0,0,,,,"_workstation._tcp.local.;",,,,,,,,,,,\n'

            b'"2016-03-21 07:38:48","2.2.2.2","udp",5353,,"mdns",22222,"PL","ExampleLoc",'
            b'"Example ExampleA",0,0,,,,"_workstation._tcp.local.; _http._tcp.local.; '
            b'_smb._tcp.local.; _qdiscover._tcp.local.;",,,,,,,,,,,\n'
            ,
            [
                dict(
                    time='2016-03-21 07:38:47',
                    address=[{'ip': '1.1.1.1'}],
                    proto='udp',
                    dport=5353,
                ),
                dict(
                    time='2016-03-21 07:38:48',
                    address=[{'ip': '2.2.2.2'}, ],
                    proto='udp',
                    dport=5353,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverXdmcp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.xdmcp'
    PARSER_CLASS = ShadowserverXdmcp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'xdmcp',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-05-03 11:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","opcode","reported_hostname","status","size"\n'

            b'"2016-07-21 02:10:01","1.1.1.1","udp",177,"example.pl",'
            b'"xdmcp",111111,"PL","example","example",0,0,"example","example4238","0 user, '
            b'load: 0.00, 0.00, 0.00",48\n'

            b'"2016-07-21 02:10:43","1.1.1.1","udp",177,"1-1-1-1.example.net",'
            b'"xdmcp",1111111,"PL","example","example",0,0,"example","linux-example",'
            b'"Linux 1.2.345-6.78-abc",49\n'

            # 3rd case - protocol other than UDP (should be
            # nevertheless acknowledged)
            b'"2016-07-21 02:10:43","1.1.1.1","tcp",177,"1-1-1-1.example.net",'
            b'"xdmcp",111111,"PL","example","example",0,0,"example","linux-example",'
            b'"Linux 1.2.345-6.78-abc",49\n',
            [
                dict(
                    time='2016-07-21 02:10:01',
                    address=[{'ip': '1.1.1.1'}],
                    proto='udp',
                    dport=177,
                ),
                dict(
                    time='2016-07-21 02:10:43',
                    address=[{'ip': '1.1.1.1'}],
                    proto='udp',
                    dport=177,
                ),
                dict(
                    time='2016-07-21 02:10:43',
                    address=[{'ip': '1.1.1.1'}],
                    proto='tcp',
                    dport=177,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverDb2201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.db2'
    PARSER_CLASS = ShadowserverDb2201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'db2',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-01-09 01:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","db2_hostname","servername","size"\n'

            b'"2016-07-21 01:10:01","1.1.1.1","udp",523,"example.com",'
            b'"db2",11111,"PL","ExampleLoc","ExampleLoc",0,0,"EXAMPLE",'
            b'"example.com",298\n'

            b'"2016-07-21 01:28:58","2.2.2.2","udp",523,,"db2",22222,"PL","ExampleLoc",'
            b'"ExampleLoc",0,0,"Example","Example",298\n'
            ,
            [
                dict(
                    time='2016-07-21 01:10:01',
                    address=[{'ip': '1.1.1.1'}],
                    proto='udp',
                    dport=523,
                ),
                dict(
                    time='2016-07-21 01:28:58',
                    address=[{'ip': '2.2.2.2'}],
                    proto='udp',
                    dport=523,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverRdp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.rdp'
    PARSER_CLASS = ShadowserverRdp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'rdp',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-09-01 10:00:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","handshake","asn","geo","region",'
            b'"city","rdp_protocol","cert_length","subject_common_name","issuer_common_name",'
            b'"cert_issue_date","cert_expiration_date","sha1_fingerprint","cert_serial_number",'
            b'"ssl_version","signature_algorithm","key_algorithm","sha256_fingerprint",'
            b'"sha512_fingerprint","md5_fingerprint","naics","sic","sector"\n'

            b'"2016-10-17 00:11:12","1.1.1.1",3389,"example.com.pl","rdp",,11111,"PL",'
            b'"ExampleLoc","ExampleLoc","WhatWho_Example",2048,"example_name","example_name",'
            b'"Jul  7 00:16:58 2016 GMT","Jan  6 00:16:58 2017 GMT",'
            b'"22:22:23:21:22:12:22:21:27:27:32:22:23:22:24:22:22:22:22:22",'
            b'"111111111111111111111",2,"sha1WithRSAEncryption","rsaEncryption",'
            b'"BB:BB:BB:BB:BB:BB:BB:BB:BB:3B:BB:84:BB:1B:BB:BF:BB:BB:BB:BB:BB:48:BB:BB:BB:'
            b'AA:BB:BB:F8:BB:BB:BB",'
            b'"AA:AA:0A:AA:AA:A6:AA:AA:A9:AA:AA:2A:AA:AF:AA:AA:9B:AA:AA:A7:AA:AA:A1:AA:AA:AA:'
            b'BB:BB:BB:BB:BB:BB:BB:B5:BB:BB:B5:BB:BB:BB:BB:07:BB:BB:BB:B9:FB:BB:BB:BB:B0:'
            b'BB:BB:BB:BB:BB:BB:BB:BA:BB:BB:BB:BB","AA:AA:0A:AA:AA:AA:30:AA:AA:AA:A5:AA:AA:AA'
            b':AA:AA",0,0,\n'

            b'"2016-10-17 00:11:12","2.2.2.2",22222,"example.com.pl",'
            b'"rdp",'
            b',222222,"PL","ExampleLoc","ExampleLoc","RDP",2048,"example.com.pl",'
            b'"example-addr-example.com","Aug 18 04:42:15 2016 GMT",'
            b'"Feb 17 04:42:15 2017 GMT",'
            b'"BB:BB:BB:BB:BB:BB:BB:BB:DB:B8:BB:BB:B1:BB:0B:BB:BE:BB:BB:BB",'
            b'"11AAA1A1A1A1A1AA1A1A1A1A11AA1AA1",2,'
            b'"sha1WithRSAEncryption","rsaEncryption","AA:AA:0A:AA:74:AA:AA:AA:'
            b'BB:BB:BB:BB:BB:BB:BB:E7:BB:BB:BB:'
            b'BB:BB:BB:BB:BB:BB:99:6C:BB:BB:BB:BB:BB","AA:AA:AA:AA:AA:CA:AA:AA:AE:AA:AA:8A:AA:AA:'
            b'FF:FF:FF:FF:FF:'
            b'BB:BB:BB:BB:BB:BB:85:BB:BB:BB:BB:BB:BD:BB:3B:BB:BB:BB:BB:BB:9B:BB:BB:BB:BB:BB:BB:BA'
            b':BB:BB:B1:BB:BB:'
            b'BB:BB:BB:BB:BB:BB:B1:BB:9B:BB:B5:BB","11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:'
            b'00",0,0,\n'

            b'"2016-10-17 00:11:12","3.3.3.3",33333,"example.com.pl",'
            b'"rdp",,33333,'
            b'"PL","ExampleLoc","ExampleLoc","RDP",2048,"ExampleName","ExampleName",'
            b'"Jan  7 17:00:02 2016 GMT","Jul  8 17:00:02 2016 GMT","BB:BB:BB:BB:BB:BB:8E:BB:BB:'
            b'BB:BB:BB:BB:BB:BB:'
            b'AA:AA:0A:C8:76","123456789ABCDEF01234567890ABCDEF",2,"sha1WithRSAEncryption",'
            b'"rsaEncryption",'
            b'"BB:BB:BB:BB:BB:BB:BB:1B:BB:BB:AB:B2:BB:BB:BA:BB:BB:BB:BB:B7:BB:BB:BB:BB:BB:7B:BB:'
            b'BB:BB:BB:BB:BB:BB",'
            b'"BB:BB:BB:BB:BB:BB:BB:D8:BB:B1:BB:BB:BB:BB:9B:BB:BB:BB:BB:BB:BC:BB:12:BB:BB:BB:BB:B'
            b'B:B7:BB:BB:BB:'
            b'BB:BB:BB:BB:BB:BB:11:22:33:11:22:33:11:22:33:11:22:33:11:22:33:11:22:33:44:55:66:77:'
            b'88:99:AA:BB",'
            b'"BB:BB:BB:BB:BB:BB:CC:DD:EE:FF:00:11:22:33:44:55",0,0,\n'
            ,
            [
                dict(
                    time='2016-10-17 00:11:12',
                    address=[{'ip': '1.1.1.1'}],
                    dport=3389,
                ),
                dict(
                    time='2016-10-17 00:11:12',
                    address=[{'ip': '2.2.2.2'}],
                    dport=22222,
                ),
                dict(
                    time='2016-10-17 00:11:12',
                    address=[{'ip': '3.3.3.3'}],
                    dport=33333,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverTftp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.tftp'
    PARSER_CLASS = ShadowserverTftp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'tftp',
        'proto': 'udp',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-02-03 11:55:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","opcode","errorcode","error","errormessage","size"\n'

            b'"2016-10-11 00:12:07","1.1.1.1","udp",48682,"example.net",'
            b'"tftp",11111,"PL","ExampleLoc","ExampleLoc",111111,222222,5,0,"Not defined",'
            b'"Get not supported",22\n'

            b'"2016-10-11 00:12:07","2.2.2.2","udp",32769,"example.net",'
            b'"tftp",22222,"PL","ExampleLoc","ExampleLoc",111111,222222,5,0,"Not defined",'
            b'"Get not supported",22\n'
            ,
            [
                dict(
                    time='2016-10-11 00:12:07',
                    address=[{'ip': '1.1.1.1'}],
                    dport=48682,
                ),
                dict(
                    time='2016-10-11 00:12:07',
                    address=[{'ip': '2.2.2.2'}],
                    dport=32769,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverIsakmp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.isakmp'
    PARSER_CLASS = ShadowserverIsakmp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'isakmp',
        'proto': 'udp',
    }
    MESSAGE_EXTRA_HEADERS = {'meta': {'mail_time': '2016-08-07 07:11:03'}}

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname",'
            b'"tag",'
            b'"asn","geo","region","city","naics","sic","initiator_spi",'
            b'"responder_spi","next_payload","exchange_type",'
            b'"flags","message_id","next_payload2","domain_of_interpretation","protocol_id",'
            b'"spi_size","notify_message_type"\n'

            b'"2016-10-17 00:11:13","1.1.1.1","udp",500,"example.com.pl",'
            b'"isakmp-vulnerable",'
            b'1111,"PL","ExampleLoc","ExampleLoc",111111,222222,"aa1a1a1a1a1a1a1a",'
            b'"2221322221322212",11,05,'
            b'00,00000000,00,00,,'
            b'0,14\n'

            b'"2016-10-17 00:11:13","2.2.2.2","udp",500,"example.com.pl",'
            b'"isakmp-vulnerable",'
            b'1111,"PL","ExampleLoc","ExampleLoc",111111,222222,"aa1a1a1a1a1a1a1a",'
            b'"0100111010105011",11,05,'
            b'00,00000000,00,00,,'
            b'0,14\n'

            b'"2016-10-17 00:11:14","3.3.3.3","udp",40002,"3-3-3-3.example.com.pl",'
            b'"isakmp-vulnerable",'
            b'22222,"PL","ExampleLoc","ExampleLoc",0,0,"aa1a1a1a1a1a1a1a",'
            b'"aa1a1a1a1a1a1a1a",11,05,'
            b'00,00000000,00,00,,'
            b'0,14\n'
            ,
            [
                dict(
                    time='2016-10-17 00:11:13',
                    address=[{'ip': '1.1.1.1'}],
                    dport=500,
                ),
                dict(
                    time='2016-10-17 00:11:13',
                    address=[{'ip': '2.2.2.2'}],
                    dport=500,
                ),
                dict(
                    time='2016-10-17 00:11:14',
                    address=[{'ip': '3.3.3.3'}],
                    dport=40002,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverTelnet201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.telnet'
    PARSER_CLASS = ShadowserverTelnet201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'telnet',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","banner"\n'

            b'"2017-01-15 20:16:38","1.1.1.1","tcp",2323,"1-1-1-1.example.pl",'
            b'"telnet-alt",22222,"PL","ExampleLoc","ExampleLoc",0,0,"xDSL Router|Login: "\n'

            b'"2017-01-15 20:16:38","2.2.2.2","tcp",2323,"2-2-2-2.example.pl",'
            b'"telnet-alt",22222,"PL","ExampleLoc","ExampleLoc",0,0,"No more sessions.|"\n'
            ,
            [
                dict(
                    time='2017-01-15 20:16:38',
                    address=[{'ip': '1.1.1.1'}],
                    dport=2323,
                ),
                dict(
                    time='2017-01-15 20:16:38',
                    address=[{'ip': '2.2.2.2'}],
                    dport=2323,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverCwmp201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.cwmp'
    PARSER_CLASS = ShadowserverCwmp201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'cwmp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","http","http_code","http_reason","content_type","connection",'
            b'"www_authenticate","set_cookie","server","content_length","transfer_encoding",'
            b'"date"\n'

            b'"2017-01-13 00:00:00","1.1.1.1","tcp",7547,"example_example.com.pl",'
            b'"cwmp",1111,"PL","ExampleLoc","ExampleLoc",111111,222222,"HTTP/1.1",200,"OK",,,,,,0,,'
            b'\n'

            b'"2017-01-13 00:00:01","2.2.2.2","tcp",7547,"example_example.com.pl",'
            b'"cwmp",1111,"PL","ExampleLoc","ExampleLoc",111111,222222,"HTTP/1.1",404,"Not Found",'
            b'"text/html",,,,"WatWhere/1.23 UPnP/1.0",,"chunked",\n'
            ,
            [
                dict(
                    time='2017-01-13 00:00:00',
                    address=[{'ip': '1.1.1.1'}],
                    dport=7547,
                ),
                dict(
                    time='2017-01-13 00:00:01',
                    address=[{'ip': '2.2.2.2'}],
                    dport=7547,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverLdap201412Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ldap'
    PARSER_CLASS = ShadowserverLdap201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ldap',
    }

    def cases(self):
        yield (
            # header
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","size","configuration_naming_context","current_time",'
            b'"default_naming_context","dns_host_name","domain_controller_functionality",'
            b'"domain_functionality","ds_service_name","forest_functionality",'
            b'"highest_committed_usn","is_global_catalog_ready","is_synchronized",'
            b'"ldap_service_name","naming_contexts","root_domain_naming_context",'
            b'"schema_naming_context","server_name","subschema_subentry","supported_capabilities",'
            b'"supported_control","supported_ldap_policies","supported_ldap_version",'
            b'"supported_sasl_mechanisms"\n'

            # 1
            b'"2017-01-15 07:10:06","1.1.1.1","udp",389,"1-1-1-1.example.com",'
            b'"ldap",22222,"PL","ExampleLoc","ExampleLoc",0,0,2516,"CN=Configuration,DC=indicator,'
            b'DC=local","20170115071156.0Z","DC=indicator,DC=local","exampleabcdef.indicator.local",3,3,'
            b'"CN=Configuration,DC=indicator,DC=local",3,23456789,"TRUE","TRUE",'
            b'"indicator.local:exampleabcdef$@INDICATOR.LOCAL","DC=indicator,DC=local|CN=Configuration,'
            b'DC=indicator,DC=local|CN=Schema,CN=Configuration,DC=indicator,'
            b'DC=local|DC=DomainDnsZones,DC=indicator,DC=local|DC=ForestDnsZones,DC=indicator,'
            b'DC=local","DC=indicator,DC=local","CN=Schema,CN=Configuration,DC=indicator,DC=local",'
            b'"CN=exampleabcdef,CN=Servers,CN=Default-First-Site-Name,CN=Sites,CN=Configuration,'
            b'DC=indicator,DC=local","CN=Aggregate,CN=Schema,CN=Configuration,DC=indicator,'
            b'DC=local","1.2.840.111111.1.4.800|1.2.840.111111.1.4.22222|1.2.840.111111.1.4.1791'
            b'|1.2.333.4444444.5.6.1111","1.2.840.111111.1.4.22222|1.1.840.111111.1.1.22222'
            b'|1.2.333.4444444.5.6.1111|1.1.111.1111111.1.1.22222|1.2.333.4444444.5.6.22222'
            b'|1.2.333.4444444.5.6.1111|1.1.111.1111111.1.1.22222|1.2.333.4444444.5.6.22222'
            b'|1.2.333.4444444.5.6.1111|1.1.111.1111111.1.1.22222|1.2.333.4444444.5.6.22222'
            b'|1.2.333.4444444.5.6.1111|1.1.111.1111111.1.1.22222|1.1.111.1111111.1.1.22222'
            b'|1.2.333.4444444.5.6.1111|1.1.111.1111111.1.1.22222|3.33.333.3.33333.3.4.22222'
            b'|3.33.333.3.33333.3.1.22222|1.1.111.1111111.1.1.22222|1.2.333.4444444.5.6.122222'
            b'|1.1.111.1111111.1.1.22222|1.1.111.1111111.1.1.22222|1.1.840.111111.1.1.22222'
            b'|1.1.111.1111111.1.1.22222|1.1.111.1111111.1.1.22222|1.1.840.111111.1.1.22222",'
            b'"MaxPoolThreads|MaxDatagramRecv|MaxReceiveBuffer|InitRecvTimeout|MaxConnections'
            b'|MaxConnIdleTime|MaxPageSize|MaxQueryDuration|MaxTempTableSize|MaxResultSetSize'
            b'|MaxNotificationPerConn|MaxValRange|ThreadMemoryLimit|SystemMemoryLimitPercent",'
            b'"3|2","GSSAPI|GSS-SPNEGO|EXTERNAL|DIGEST-MD5"\n'

            # 2
            b'"2017-01-15 07:10:08","2.2.2.2","udp",389,"2-2-2-2.example.com",'
            b'"ldap",11111,"PL","ExampleLoc","ExampleLoc",0,0,2829,"CN=Configuration,'
            b'DC=example,DC=local","20170115070916.0Z","DC=example,DC=local",'
            b'"examplesrv.example.local",5,5,"CN=Configuration,DC=example,DC=local",5,1234567,'
            b'"TRUE","TRUE","example.local:examplesrv$@example.LOCAL","DC=example,'
            b'DC=local|CN=Configuration,DC=example,DC=local|CN=Schema,CN=Configuration,DC=example,'
            b'DC=local|DC=DomainDnsZones,DC=example,DC=local|DC=ForestDnsZones,DC=example,'
            b'DC=local","DC=example,DC=local","CN=Schema,CN=Configuration,DC=example,DC=local",'
            b'"CN=exampleSRV,CN=Servers,CN=Default-First-Site-Name,CN=Sites,CN=Configuration,'
            b'DC=example,DC=local","CN=Aggregate,CN=Schema,CN=Configuration,DC=example,DC=local",'
            b'"1.2.333.4444444.5.6.3333|1.1.3333.111111.1.1.2222222|1.1.111.1111111.1.1.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.1.111.1111111.1.1.2222222",'
            b'"1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|3.33.333.3.33333.3.1.2222222|3.33.333.3.33333.3.1.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222|1.2.333.4444444.5.6.2222222'
            b'|1.2.333.4444444.5.6.3333|1.2.333.4444444.5.6.2222222","MaxPoolThreads|MaxDatagramRecv'
            b'|MaxReceiveBuffer|InitRecvTimeout|MaxConnections|MaxConnIdleTime|MaxPageSize'
            b'|MaxBatchReturnMessages|MaxQueryDuration|MaxTempTableSize|MaxResultSetSize'
            b'|MinResultSets|MaxResultSetsPerConn|MaxNotificationPerConn|MaxValRange'
            b'|ThreadMemoryLimit|SystemMemoryLimitPercent","3|2","GSSAPI|GSS-SPNEGO'
            b'|EXTERNAL|DIGEST-MD5"\n',
            [
                dict(
                    time='2017-01-15 07:10:06',
                    address=[{'ip': '1.1.1.1'}],
                    dport=389,
                ),
                dict(
                    time='2017-01-15 07:10:08',
                    address=[{'ip': '2.2.2.2'}],
                    dport=389,
                ),
            ]
        )
        yield (
            b'bad_data\n'
            b'row\n'
            ,
            Exception
        )


class TestShadowserverVnc201412Parser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.vnc'
    PARSER_CLASS = ShadowserverVnc201412Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'proto': 'tcp',
        'name': 'vnc',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","asn","geo","region","city","naics","sic"'
            b',"product","banner"\n'

            b'"2017-08-14 12:42:17","1.1.1.1",5900,"example1.com",1111,"PL",'
            b'"ExampleLoc","ExampleLoc",111111,222222,"Example Protocol 1.1",DEF 123.456\n'

            b'"2017-08-14 12:42:17","2.2.2.2",5900,"example2.com",1111,"PL",'
            b'"ExampleLoc","ExampleLoc",111111,222222,"Example Protocol 1.2","ABC 012.345"'
            ,
            [
                dict(
                    time='2017-08-14 12:42:17',
                    address=[{'ip': '1.1.1.1'}, ],
                    dport=5900,
                    product="Example Protocol 1.1",
                ),
                dict(
                    time='2017-08-14 12:42:17',
                    address=[{'ip': '2.2.2.2'}, ],
                    dport=5900,
                    product="Example Protocol 1.2",
                ),
            ]
        )


class TestShadowserverSinkholeHttp202203Parser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.sinkhole-http'
    PARSER_CLASS = ShadowserverSinkholeHttp202203Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    def cases(self):
        yield (
        b'"timestamp","protocol","src_ip","src_port","src_asn","src_geo","src_region","src_city",'
        b'"src_hostname","src_naics","src_sector","device_vendor","device_type","device_model",'
        b'"dst_ip","dst_port","dst_asn","dst_geo","dst_region","dst_city","dst_hostname","dst_naics",'
        b'"dst_sector","public_source","infection","family","tag","application","version","event_id",'
        b'"http_url","http_host","http_agent","forwarded_by","ssl_cipher","http_referer"\n'
        b'"2021-06-03 00:00:00","tcp","1.1.1.1",2222,11111,"PL","STATE","CITYXXX","example.pl",'
        b'1111111,"Communications, Service Provider, and Hosting Service",,,,"2.2.2.2",1111,22222,"NL",'
        b'"NOORD-HOLLAND","AMSTERDAM","example2.com",111111,"Communications, Service Provider, '
        b'and Hosting Service","Bitsight","avalanche-andromeda",,,,,,"http://example.com/test.php",'
        b'"example.com","Mozilla/4.0",,,'
            ,
            [
                dict(
                    time='2021-06-03 00:00:00',
                    address=[{'ip': '1.1.1.1'}, ],
                    dport=1111,
                    sport=2222,
                    dip='2.2.2.2',
                    proto='tcp',
                    url='http://example.com/test.php',
                    fqdn='example.com',
                    name='avalanche-andromeda',
                ),
            ]
        )


class TestShadowserverSinkholeParser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.sinkhole'
    PARSER_CLASS = ShadowserverSinkhole202203Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    def cases(self):
        yield (
        b'"timestamp","protocol","src_ip","src_port","src_asn","src_geo","src_region","src_city",'
        b'"src_hostname","src_naics","src_sector","device_vendor","device_type","device_model",'
        b'"dst_ip","dst_port","dst_asn","dst_geo","dst_region","dst_city","dst_hostname","dst_naics",'
        b'"dst_sector","public_source","infection","family","tag","application","version","event_id"\n'
        b'"2021-05-18 00:00:00","tcp","1.1.1.1",2222,11111,"PL","STATE","CITY",,11111,"Communications, '
        b'Service Provider, and Hosting Service",,"Linux",,"2.2.2.2",1111,11111,"DE","HESSEN","FRANKFURT AM MAIN",'
        b',111111,"Communications, Service Provider, and Hosting Service",,"test",,,,,1234567890'
            ,
            [
                dict(
                    time='2021-05-18 00:00:00',
                    address=[{'ip': '1.1.1.1'}, ],
                    dport=1111,
                    sport=2222,
                    dip='2.2.2.2',
                    proto='tcp',
                    name='test',
                ),
            ]
        )


class TestShadowserverDarknet202203Parser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.darknet'
    PARSER_CLASS = ShadowserverDarknet202203Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'darknet',
    }

    def cases(self):
        yield (
        b'"timestamp","protocol","src_ip","src_port","src_asn","src_geo","src_region",'
        b'"src_city","src_hostname","src_naics","src_sector","device_vendor","device_type",'
        b'"device_model","dst_ip","dst_port","dst_asn","dst_geo","dst_region","dst_city",'
        b'"dst_hostname","dst_naics","dst_sector","public_source","infection","family","tag",'
        b'"application","version","event_id","count"\n'
        b'"2021-04-27 00:00:00","tcp","1.1.1.1",2222,11111,"PL","EXAMPLE STATE","WALBRZYCH",'
        b'"example.com",111111,"Communications, Service Provider, and Hosting Service",,,,'
        b'"2.2.2.2",1111,,,,,,,,,"mirai",,"mirai",,,,'
            ,
            [
                dict(
                    time='2021-04-27 00:00:00',
                    address=[{'ip': '1.1.1.1'}, ],
                    dport=1111,
                    dip='2.2.2.2',
                    proto='tcp',
                    name='mirai',
                ),
            ]
        )


class TestShadowserverModbus202203Parser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.modbus'
    PARSER_CLASS = ShadowserverModbus202203Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'modbus',
    }

    def cases(self):
        yield (
        b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics",'
        b'"sic","unit_id","vendor","revision","product_code","function_code","conformity_level",'
        b'"object_count","response_length","raw_response","sector"\n'
        b'"2022-02-20 02:30:40","1.1.1.1","tcp",1111,"1.1.1.1.example.com","modbus",11111,"PL",'
        b'"EXAMPLE VOIVODESHIP","EXAMPLE CITY",,,0,"Example Company","v2.2","ABC DEF 1234",43,129,3,50,'
        b'"AaaAa1a1a1aAAa1a1aaaaAAAaaaA11","Communications, Service Provider, and Hosting Service"'
            ,
            [
                dict(
                    time='2022-02-20 02:30:40',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    vendor='Example Company',
                    revision='v2.2',
                    product_code='ABC DEF 1234',
                ),
            ]
        )


class TestShadowserverIcs202204Parser(ParserTestMixin, unittest.TestCase):
    PARSER_SOURCE = 'shadowserver.ics'
    PARSER_CLASS = ShadowserverIcs202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    def cases(self):
        yield (
        b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics",'
        b'"sic","sector","device_vendor","device_type","device_model","device_version","device_id",'
        b'"response_length","raw_response"\n'
        b'"2022-03-15 01:06:47","1.1.1.1","tcp",1111,"1-1-1-1.example.com","fox",11111,"PL",'
        b'"STATE","CITYXXX",111111,,"Communications, Service Provider, and Hosting Service",'
        b'"ExampleDevice","iSM","1.0.1","1.1.111","ExampleDevId",484,"aaAaaAaAaaaAa1aaaBASE64RRAWRESPONSE=="'
            ,
            [
                dict(
                    time='2022-03-15 01:06:47',
                    address=[{'ip': '1.1.1.1'}, ],
                    dport=1111,
                    proto='tcp',
                    name='fox',
                    device_vendor='ExampleDevice',
                    device_type='iSM',
                    device_model='1.0.1',
                    device_version='1.1.111',
                    device_id='ExampleDevId',
                ),
            ]
        )


class TestShadowserverCoap202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.coap'
    PARSER_CLASS = ShadowserverCoap202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'coap',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic","response"\n'
            b'"2021-05-18 01:28:59","1.1.1.1","udp",1111,,"coap",11111,"PL","STATE","CITY",,,"</api>..."'
            ,
            [
                dict(
                    time='2021-05-18 01:28:59',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverUbiquiti202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ubiquiti'
    PARSER_CLASS = ShadowserverUbiquiti202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ubiquiti',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","mac","radioname","essid","modelshort","modelfull","firmware","size"\n'
            b'"2021-05-18 01:19:39","1.1.1.1","udp",1111,,"ubiquiti",11111,"PL","WIELKOPOLSKIE",'
            b'"EXAMPLE",,,"111111111111","test1","test2","ABC",,"AA1.aa111.v1.0.1.1111.111111.1111",123'
            ,
            [
                dict(
                    time='2021-05-18 01:19:39',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverArd202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ard'
    PARSER_CLASS = ShadowserverArd202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ard',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo",'
            b'"region","city","naics","sic","machine_name","response_size"\n'
            b'"2021-05-18 10:20:52","1.1.1.1","udp",1111,"1.1.1.1.example.com",'
            b'"ard",11111,"PL","SOMEWHERE","SOME CITY",111111,,"Serwer",1006'
            ,
            [
                dict(
                    time='2021-05-18 10:20:52',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverRdpeudp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.rdpeudp'
    PARSER_CLASS = ShadowserverRdpeudp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'rdpeudp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic","sessionid"\n'
            b'"2021-05-18 13:18:31","1.1.1.1","udp",1111,"test.example.com","rdpeudp",11111,"PL","STATE","CITY",111111,,"01234567"'
            ,
            [
                dict(
                    time='2021-05-18 13:18:31',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='udp',
                ),
            ]
        )


class TestShadowserverDvrDhcpdiscover202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.dvr-dhcpdiscover'
    PARSER_CLASS = ShadowserverDvrDhcpdiscover202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'dvr-dhcpdiscover',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","sector","device_vendor","device_type","device_model","device_version",'
            b'"device_id","device_serial","machine_name","manufacturer","method","http_port",'
            b'"internal_port","video_input_channels","alarm_input_channels","video_output_channels",'
            b'"alarm_output_channels","remote_video_input_channels","mac_address","ipv4_address",'
            b'"ipv4_gateway","ipv4_subnet_mask","ipv4_dhcp_enable","ipv6_address","ipv6_link_local",'
            b'"ipv6_gateway","ipv6_dhcp_enable"\n'
            b'"2022-04-20 13:29:33","1.1.1.1","udp",1111,"host-1-1-1-1.example.com","dvrdhcpdiscover",'
            b'11111,"PL","STATE","CITY",,,,"Private","ABC","ABC1234-5DE6","1.111.111A001.0",'
            b'"1234","1A111AAAAAA1AA1","ABC","Private","client.notifyDevInfo",80,22222,0,0,0,0,4,'
            b'"00:00:00:00:00:00","1.1.1.1","2.2.2.2","3.3.3.3",0,"/1",'
            b'"0000::0000:0000:0000:0000/64",,'
            ,
            [
                dict(
                    time='2022-04-20 13:29:33',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='udp',
                    device_vendor='Private',
                    device_type='ABC',
                    device_model='ABC1234-5DE6',
                    device_version='1.111.111A001.0',
                    device_id='1234',
                ),
            ]
        )


class TestShadowserverHttp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.http'
    PARSER_CLASS = ShadowserverHttp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city"'
            b',"naics","sic","http","http_code","http_reason","content_type","connection",'
            b'"www_authenticate","set_cookie","server","content_length","transfer_encoding",'
            b'"http_date"\n'
            b'"2021-05-18 00:03:55","1.1.1.1","tcp",1111,"1-1-1-1.example.com","basic-auth,http",'
            b'11111,"PL","STATE","CITY",111111,,"HTTP/1.1",401,"Unauthorized","text/html",,'
            b'"Basic realm=""1.1.1.1""",,"Microsoft-IIS/10.0",3333,,"Tue, 18 May 2021 00:03:55 GMT"'
            ,
            [
                dict(
                    time='2021-05-18 00:03:55',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    name='basic-auth,http',
                ),
            ]
        )


class TestShadowserverFtp202204Parserr(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ftp'
    PARSER_CLASS = ShadowserverFtp202204Parser
    PARSER_BASE_CLASS = BaseParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ftp, clear text pass',
    }

    def cases(self):
        # Only first row (empty "handshake" field) is mapped. Second row ("hanshake" field with some content) is ignored.
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic","banner",'
            b'"handshake","cipher_suite","cert_length","subject_common_name","issuer_common_name","cert_issue_date",'
            b'"cert_expiration_date","sha1_fingerprint","cert_serial_number","ssl_version","signature_algorithm",'
            b'"key_algorithm","subject_organization_name","subject_organization_unit_name","subject_country",'
            b'"subject_state_or_province_name","subject_locality_name","subject_street_address","subject_postal_code",'
            b'"subject_surname","subject_given_name","subject_email_address","subject_business_category",'
            b'"subject_serial_number","issuer_organization_name","issuer_organization_unit_name","issuer_country",'
            b'"issuer_state_or_province_name","issuer_locality_name","issuer_street_address","issuer_postal_code",'
            b'"issuer_surname","issuer_given_name","issuer_email_address","issuer_business_category","issuer_serial_number",'
            b'"sha256_fingerprint","sha512_fingerprint","md5_fingerprint","cert_valid","self_signed","cert_expired",'
            b'"validation_level","auth_tls_response","auth_ssl_response","tlsv13_support","tlsv13_cipher","jarm","device_vendor",'
            b'"device_type","device_model","device_version","device_sector"\n'

            b'"2021-05-18 17:45:19","1.1.1.1","tcp",1111,"example.com","ftp",11111,"PL","STATE","CITY",'
            b'111111,,"12345678 FTP Server 1.2.3 (localhost) [1.1.1.1]|220 Ready|",,"TLS_XXXX_RSA_WITH_AES_XXX_XXX_SHA256",'
            b'2048,"*.example.com","Certyfikat SSL","2020-07-02 08:53:25","2022-07-02 08:53:25","test","test",2,'
            b'"sha256WithRSAEncryption","rsaEncryption",,,,,,,,,,,,,example.com XXX.",,"PL",,,,,,,,,,"test","test","test",'
            b'"Y","N","N","DV","234 AUTH command successful.",,,,,Vendor,Type,Model,Version,\n'

            b'"2021-05-18 17:45:19","1.1.1.1","tcp",1111,"example.com","ftp",11111,"PL","STATE","CITY",'
            b'111111,,"12345678 FTP Server 1.2.3 (localhost) [1.1.1.1]|220 Ready|","TLSv1.2",'
            b'"TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",2048,"*.example.com","Certyfikat SSL","2020-07-02 08:53:25",'
            b'"2022-07-02 08:53:25","test","test",2,"sha256WithRSAEncryption","rsaEncryption",,,,,,,,,,,,,example.com S.A.",'
            b',"PL",,,,,,,,,,"test","test","test","Y","N","N","DV","234 AUTH command successful.",,,,,Vendor,Type,Model,Version,'
            ,
            [
                dict(
                    time='2021-05-18 17:45:19',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    device_vendor='Vendor',
                    device_type='Type',
                    device_model='Model',
                    device_version='Version',
                ),
            ]
        )


class TestShadowserverMqtt202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.mqtt'
    PARSER_CLASS = ShadowserverMqtt202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'mqtt',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region",'
            b'"city","naics","sic","anonymous_access","raw_response","hex_code","code",'
            b'"cipher_suite","cert_length","subject_common_name","issuer_common_name",'
            b'"cert_issue_date","cert_expiration_date","sha1_fingerprint","sha256_fingerprint",'
            b'"sha512_fingerprint","md5_fingerprint","cert_serial_number","ssl_version",'
            b'"signature_algorithm","key_algorithm","subject_organization_name",'
            b'"subject_organization_unit_name","subject_country","subject_state_or_province_name",'
            b'"subject_locality_name","subject_street_address","subject_postal_code",'
            b'"subject_surname","subject_given_name","subject_email_address","subject_business_category",'
            b'"subject_serial_number","issuer_organization_name","issuer_organization_unit_name",'
            b'"issuer_country","issuer_state_or_province_name","issuer_locality_name","issuer_street_address",'
            b'"issuer_postal_code","issuer_surname","issuer_given_name","issuer_email_address",'
            b'"issuer_business_category","issuer_serialNumber"\n'
            b'"2021-05-18 05:56:19","1.1.1.1","tcp",1111,"example.com","mqtt",11111,"PL","STATE",'
            b'"EXMPL CITY",,,"N",20020005,05,"Connection Refused, not authorized"'
            b',,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,'
            ,
            [
                dict(
                    time='2021-05-18 05:56:19',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverShadowserverLdapTcp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ldap-tcp'
    PARSER_CLASS = ShadowserverLdapTcp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ldap',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","size","configuration_naming_context","current_time","default_naming_context",'
            b'"dns_host_name","domain_controller_functionality","domain_functionality","ds_service_name",'
            b'"forest_functionality","highest_committed_usn","is_global_catalog_ready","is_synchronized",'
            b'"ldap_service_name","naming_contexts","root_domain_naming_context","schema_naming_context",'
            b'"server_name","subschema_subentry","supported_capabilities","supported_control",'
            b'"supported_ldap_policies","supported_ldap_version","supported_sasl_mechanisms"\n'
            b'"2021-05-18 12:57:01","1.1.1.1","tcp",1111,"example.com","ldap-tcp",11111,"PL",'
            b'"EXAMPLE STATE","CITY_ABC",,,0,,,,,,,,,,,,,,,,,,,,,,'
            ,
            [
                dict(
                    time='2021-05-18 12:57:01',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverRsync202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.rsync'
    PARSER_CLASS = ShadowserverRsync202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'rsync',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic","module","motd","password"\n'
            b'"2021-05-18 06:14:50","1.1.1.1","tcp",1111,"1-1-1-1.example.com","rsync",11111,"PL","EXAMPLE STATE","EXAMPLEEEEE",,,,,'
            ,
            [
                dict(
                    time='2021-05-18 06:14:50',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverRadmin202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.radmin'
    PARSER_CLASS = ShadowserverRadmin202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'radmin',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","version","asn","geo","region","city","naics","sic"\n'
            b'"2021-05-18 13:27:35","1.1.1.1","tcp",1111,,"radmin","Radmin v3.X Radmin Authentication",11111,"PL","STATE","CITY",111111,'
            ,
            [
                dict(
                    time='2021-05-18 13:27:35',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverAdb202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.adb'
    PARSER_CLASS = ShadowserverAdb202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'adb',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","name","model","device","features","device_vendor","device_type",'
            b'"device_model","device_version","device_sector"\n'
            b'"2021-05-18 09:18:27","1.1.1.1","tcp",1111,"example.com","adb",11111,"PL",'
            b'"STATE","CITY",222222,,,,,,Vendor,Type,Model,Version,'
            ,
            [
                dict(
                    time='2021-05-18 09:18:27',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    device_vendor='Vendor',
                    device_type='Type',
                    device_model='Model',
                    device_version='Version',
                ),
            ]
        )


class TestShadowserverAfp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.afp'
    PARSER_CLASS = ShadowserverAfp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'afp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region",'
            b'"city","naics","sic","machine_type","afp_versions","uams","flags","server_name",'
            b'"signature","directory_service","utf8_servername","network_address"\n'
            b'"2021-05-18 08:41:58","1.1.1.1","tcp",1111,"1-1-1-1.example.com","afp",11111,"PL",'
            b'"STATE","CITY",111111,,"test","AFP2.2,AFPX03,AFP3.1,AFP3.2,AFP3.3,AFP3.4",'
            b'"DHX2,No User Authent,Cleartxt Passwrd","SupportsCopyFile,SupportsServerMessages,'
            b'SupportsServerSignature,SupportsTCP/IP,SupportsSrvrNotifications,SupportsOpenDirectory,'
            b'SupportsUTF8Servername,SupportsUUIDs,SupportsSuperClient","XXXABC","test",,"XXXABC",'
            b'"2.2.2.2 (TCP/IP address),"'
            ,
            [
                dict(
                    time='2021-05-18 08:41:58',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverCiscoSmartInstall202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.cisco-smart-install'
    PARSER_CLASS = ShadowserverCiscoSmartInstall202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'cisco-smart-install',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic"\n'
            b'"2021-05-18 15:55:35","1.1.1.1","tcp",1111,,"cisco-smart-install",11111,"PL","EXAMPLE STATE","EXAMPLE CITY",,'
            ,
            [
                dict(
                    time='2021-05-18 15:55:35',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )


class TestShadowserverIpp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.ipp'
    PARSER_CLASS = ShadowserverIpp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ipp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region",'
            b'"city","naics","sic","ipp_version","cups_version","printer_uris","printer_name",'
            b'"printer_info","printer_more_info","printer_make_and_model","printer_firmware_name",'
            b'"printer_firmware_string_version","printer_firmware_version","printer_organization",'
            b'"printer_organization_unit","printer_uuid","printer_wifi_ssid","device_vendor",'
            b'"device_type","device_model","device_version","device_sector"\n'
            b'"2021-05-18 12:38:28","1.1.1.1","tcp",1111,"example.com","ipp",11111,"PL","EXAMPLE STATE",'
            b'"EXAMPLE CITY",,,,,"http://2.2.2.2:2222","Printer Name","Info","MoreInfo",'
            b'"Samsung XX-XXXX Series",,,,,,,,Vendor,Type,Model,Version,'
            ,
            [
                dict(
                    time='2021-05-18 12:38:28',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    device_vendor='Vendor',
                    device_type='Type',
                    device_model='Model',
                    device_version='Version',
                ),
            ]
        )


class TestShadowserverHadoop202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.hadoop'
    PARSER_CLASS = ShadowserverHadoop202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'hadoop',
        'proto': 'tcp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","version","asn","geo","region",'
            b'"city","naics","sic","server_type","clusterid","total_disk","used_disk",'
            b'"free_disk","livenodes","namenodeaddress","volumeinfo"\n'
            b'"2021-05-18 15:44:33","1.1.1.1",1111,"example.com","1.2.3-abc6.7.8, '
            b'test",11111,"PL","EXAMPLE STATE","CITY_ABC",111111,,"namenode","cluster",'
            b'3333,4444,,"test",,'
            ,
            [
                dict(
                    time='2021-05-18 15:44:33',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                ),
            ]
        )


class TestShadowserverExchange202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.exchange'
    PARSER_CLASS = ShadowserverExchange202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'proto': 'tcp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","port","hostname","tag","asn","geo","region","city","naics","sic","sector","version","servername","url"\n'
            b'"2021-05-18 00:40:54","1.1.1.1",1111,"example.com","exchange;cve-2020-11111",11111,"PL","STATE","CITYXXX",,,,,"test",'
            ,
            [
                dict(
                    time='2021-05-18 00:40:54',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    name='exchange;cve-2020-11111',
                ),
            ]
        )


class TestShadowserverSmtp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.smtp'
    PARSER_CLASS = ShadowserverSmtp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city","naics","sic","banner"\n'
            b'"2021-05-18 16:46:22","1.1.1.1","tcp",1111,"example.com","smtp;XXyyyy",11111,"PL","STATE","CITY",,,"123 example.com XXXX YYY 1.23 Tue, 18 May 2021 18:46:22 +0200|"'
            ,
            [
                dict(
                    time='2021-05-18 16:46:22',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                    name='smtp;XXyyyy',
                ),
            ]
        )


class TestShadowserverAmqp202204Parser(ParserTestMixin, unittest.TestCase):

    PARSER_SOURCE = 'shadowserver.amqp'
    PARSER_CLASS = ShadowserverAmqp202204Parser
    PARSER_BASE_CLASS = _BaseShadowserverParser
    PARSER_CONSTANT_ITEMS = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'amqp',
    }

    def cases(self):
        yield (
            b'"timestamp","ip","protocol","port","hostname","tag","asn","geo","region","city",'
            b'"naics","sic","channel","message_length","class","method","version_major",'
            b'"version_minor","capabilities","cluster_name","platform","product","product_version",'
            b'"mechanisms","locales","sector"\n'
            b'"2022-04-20 13:56:51","1.1.1.1","tcp",1111,"example.com","amqp",11111,"PL",'
            b'"EXAMPLE STATE","CITY_ABC",111111,,0,123,10,10,0,9,"publisher_confirms,'
            b'exchange_exchange_bindings,basic.nack,consumer_cancel_notify,connection.blocked,'
            b'consumer_priorities,authentication_failure_close,per_consumer_qos,direct_reply_to",'
            b'"rabbit@example.com","Erlang/OTP 1.2.3","RabbitMQ","4.5.6","PLAIN AMQPLAIN","en_US",'
            b'"Communications, Service Provider, and Hosting Service"'
            ,
            [
                dict(
                    time='2022-04-20 13:56:51',
                    address=[{'ip': '1.1.1.1'}],
                    dport=1111,
                    proto='tcp',
                ),
            ]
        )

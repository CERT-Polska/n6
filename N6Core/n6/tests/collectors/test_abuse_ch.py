# -*- coding: utf-8 -*-

from bson.json_util import loads
import unittest

import mock
from unittest_expander import expand, foreach, param

from n6.collectors.abuse_ch import (
    AbuseChSSLBlacklistDyreCollector,
    NoNewDataException,
)

@expand
class _TestAbuseChSSLBlacklistBase(unittest.TestCase):

    """
    Base test case class for checking `get_output_data_body()` method
    of AbuseChSSLBlacklistCollector and AbuseChSSLBlacklistDyreCollector.
    """

    regular_rss = [
        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>5fcb5b418f779a542b7148f2ddea211495787733 (2016-10-17 12:44:04'
         ')</title>\n<link>https://sslbl.abuse.ch/intel/5fcb5b418f779a542b7148f2ddea211'
         '495787733</link>\n<description>SHA1: 5fcb5b418f779a542b7148f2ddea211495787733'
         'e, Common Name: facenoplays.com, Issuer: COMODO RSA'
         'Domain Validation Secure Server CA</description>\n<guid>https://sslb'
         'l.abuse.ch/intel/5fcb5b418f779a542b7148f2ddea211495787733&amp;id=838'
         '4156e3b53194b118b9fe8c9d26709</guid>\n</item>\n</channel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>6800af01d6a5b83dc3e8c8d649101f7872719fce (2016-10-17 12:44:04'
         ')</title>\n<link>https://sslbl.abuse.ch/intel/6800af01d6a5b83dc3e8c8'
         'd649101f7872719fce</link>\n<description>SHA1: 6800af01d6a5b83dc3e8c8'
         'd649101f7872719fce, Common Name: facenoplays.com, Issuer: COMODO RSA'
         'Domain Validation Secure Server CA</description>\n<guid>https://sslb'
         'l.abuse.ch/intel/6800af01d6a5b83dc3e8c8d649101f7872719fce&amp;id=838'
         '4156e3b53194b118b9fe8c9d26709</guid>\n</item>\n</channel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>e03e335629b882f1f03f091123511eaa3fc2d6b1 (2016-10-14 11:13:35)<'
         '/title>\n<link>https://sslbl.abuse.ch/intel/e03e335629b882f1f03f0911235'
         '11eaa3fc2d6b1</link>\n<description>SHA1: e03e335629b882f1f03f091123511e'
         'aa3fc2d6b1, Common Name: C=GB, ST=Berkshire, L=Newbury, O=My Company L'
         'td, Issuer: C=GB, ST=Berkshire, L=Newbury, O=My Company Ltd</descripti'
         'on>\n<guid>https://sslbl.abuse.ch/intel/e03e335629b882f1f03f091123511ea'
         'a3fc2d6b1&amp;id=758994d35dd23c61dacd6902c32cab9e</guid>\n</item>\n</cha'
         'nnel>\n</rss>\n'),

        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>dcbe920e3d0cba40be80fba5e23a6b4f9a706dd4 (2016-10-07 04:51:52)<'
         '/title>\n<link>https://sslbl.abuse.ch/intel/dcbe920e3d0cba40be80fba5e23'
         'a6b4f9a706dd4</link>\n<description>SHA1: dcbe920e3d0cba40be80fba5e23a6b'
         '4f9a706dd4, Common Name: C=US, ST=Denial, L=Springfield, O=Dis, Issuer'
         ': C=US, ST=Denial, L=Springfield, O=Dis</description>\n<guid>https://ss'
         'lbl.abuse.ch/intel/dcbe920e3d0cba40be80fba5e23a6b4f9a706dd4&amp;id=aa8'
         '822242d2ed85df15ba6db737add3d</guid>\n</item>\n</channel>\n</rss>\n'),
    ]

    invalid_rss = [
        ('<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
         '<rss version="2.0">\n'
         '<channel>\n'
         '<item>\n'
         '<title>6800af01d6a5b83dc3e8c8d649101f7872719fce (2016-10-17 12:44:04)<'
         '/title>\n<description>SHA1: 6800af01d6a5b83dc3e8c8d649101f7872719fce, C'
         'ommon Name: facenoplays.com, Issuer: COMODO RSA Domain Validation Secu'
         're Server CA</description>\n<guid>https://sslbl.abuse.ch/intel/6800af01'
         'd6a5b83dc3e8c8d649101f7872719fce&amp;id=8384156e3b53194b118b9fe8c9d267'
         '09</guid>\n</item>\n'),
    ]

    results = [
        {
            "https://sslbl.abuse.ch/intel/5fcb5b418f779a542b7148f2ddea211495787733":
            {
                "subject": "OU=Domain Control Validated, OU=PositiveSSL, CN=facenoplays.com",
                "issuer": "C=GB, ST=Greater Manchester, L=Salford, O=COMODO CA Limited, "
                          "CN=COMODO RSA Domain Validation Secure Server CA",
                "fingerprint": "6800af01d6a5b83dc3e8c8d649101f7872719fce",
                "name": "Gozi MITM",
                "timestamp": "2016-10-17 12:44:04",
            },
        },
        {
            "https://sslbl.abuse.ch/intel/6800af01d6a5b83dc3e8c8d649101f7872719fce":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "5fcb5b418f779a542b7148f2ddea211495787733",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    [
                        "2016-10-13 16:27:10",
                        "76b609dac79e76fe7b5a78af35c5a2d6",
                        "52.77.110.77",
                        "443",
                    ],
                    [
                        "2016-10-10 17:29:57",
                        "9096210f20753c836378ca7aa18c3d25",
                        "52.77.110.77",
                        "443",
                    ],
                ],
            },
        },
        {
            "https://sslbl.abuse.ch/intel/e03e335629b882f1f03f091123511eaa3fc2d6b1":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "e03e335629b882f1f03f091123511eaa3fc2d6b1",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    [
                        "2016-10-07 19:55:38",
                        "d9e83ed20a652e7629b753e20336f7a4",
                        "52.77.110.77",
                        "443",
                    ],
                ],
            },
        },
    ]

    detail_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>facenoplays.com</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject'
        ':</th><td>OU=Domain Control Validated, OU=PositiveSSL, CN=facenoplays.'
        'com</td></tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>CO'
        'MODO RSA Domain Validation Secure Server CA</td></tr>\n<tr bgcolor="#D8'
        'D8D8"><th>Issuer:</th><td>C=GB, ST=Greater Manchester, L=Salford, O=CO'
        'MODO CA Limited, CN=COMODO RSA Domain Validation Secure Server CA</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Fingerprint (SHA1):</th><td>6800af01d6'
        'a5b83dc3e8c8d649101f7872719fce</td></tr>\n<tr bgcolor="red"><th>Status:'
        '</th><td><strong>Blacklisted</strong> (Reason: Gozi MITM, Listing date'
        ': 2016-10-17 12:44:04)</td></tr>\n</table>\n<br /><h2>Associated malware'
        ' binaries</h2>\n<p>This SSL certificate was spotted passively or by usi'
        'ng scanning techniques. Therefore SSLBL is not able to provide any ref'
        'erencing malware binaries.</p>\n<div class="footer">Copyright &copy; 20'
        '16 - sslbl.abuse.ch</div>\n</div>\n</body>\n</html>\n')

    binaries_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>localhost</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject:</th>'
        '<td>C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>localhost<'
        '/td></tr>\n<tr bgcolor="#D8D8D8"><th>Issuer:</th><td>C=GB, ST=Yorks, L='
        'York, O=MyCompany Ltd., OU=IT, CN=localhost</td></tr>\n<tr bgcolor="#ff'
        'ffff"><th>SSL Version:</th><td>TLSv1</td></tr>\n<tr bgcolor="#D8D8D8"><'
        'th>Fingerprint (SHA1):</th><td>5fcb5b418f779a542b7148f2ddea21149578773'
        '3</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Blacklisted<'
        '/strong> (Reason: ZeuS C&amp;C, Listing date: 2016-10-17 11:52:40)</td'
        '></tr>\n</table>\n<br /><h2>Associated malware binaries</h2>\n<table clas'
        's="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malware binary (MD5 hash'
        ')</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcolor="#D8D8D8">'
        '<td>2016-10-13 16:27:10</td><td>76b609dac79'
        'e76fe7b5a78af35c5a2d6</td><td>52.77.110.77</td><td>443</td></tr>\n'
        '<tr bgcolor="#ffffff"><td>2016-10-10 17:29:57</td><td>9096210f20753c83637'
        '8ca7aa18c3d25</td><td>52.77.110.77</td><td>443</td></tr>'
        '</table>\n<p># of referencing malware binaries: <strong>4</strong>'
        '</p>\n<div class="footer">Copyright &copy; 2016 - sslbl.ab'
        'use.ch</div>\n</div>\n</body>\n</html>\n')

    updated_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>localhost</td></tr>\n<tr bgcolor="#D8D8D8"><th>Subject:</th>'
        '<td>C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost</td>'
        '</tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>localhost<'
        '/td></tr>\n<tr bgcolor="#D8D8D8"><th>Issuer:</th><td>C=GB, ST=Yorks, L='
        'York, O=MyCompany Ltd., OU=IT, CN=localhost</td></tr>\n<tr bgcolor="#ff'
        'ffff"><th>SSL Version:</th><td>TLSv1</td></tr>\n<tr bgcolor="#D8D8D8"><'
        'th>Fingerprint (SHA1):</th><td>e03e335629b882f1f03f091123511eaa3fc2d6b1'
        '</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Blacklisted<'
        '/strong> (Reason: ZeuS C&amp;C, Listing date: 2016-10-17 11:52:40)</td'
        '></tr>\n</table>\n<br /><h2>Associated malware binaries</h2>\n<table clas'
        's="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malware binary (MD5 hash'
        ')</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcolor="#D8D8D8"><td>20'
        '16-10-13 16:27:10</td><td>76b609dac79e76fe7b5a78af35c5a2d6</td><td>52.'
        '77.110.77</td><td>443</td></tr>\n<tr bgcolor="#ffffff"><td>2016-10-10 1'
        '7:29:57</td><td>9096210f20753c836378ca7aa18c3d25</td><td>52.77.110.77<'
        '/td><td>443</td></tr>\n<tr bgcolor="#D8D8D8"><td>2016-10-07 19:55:38</t'
        'd><td>d9e83ed20a652e7629b753e20336f7a4</td><td>52.77.110.77</td><td>44'
        '3</td></tr>\n</table>\n<p># of referencing malware binaries: <strong>3</'
        'strong></p>\n<div class="footer">Copyright &copy; 2016 - sslbl.abuse.ch'
        '</div>\n</div>\n</body>\n</html>\n')

    not_updated_page = (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http:/'
        '/www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n<html xmlns="http:'
        '//www.w3.org/1999/xhtml">\n<head>\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />'
        '\n<meta name="robots" content="all" />\n'
        '<meta name="description" content="The SSL Blacklist is a collection of'
        ' SHA1 fingerprints of malicious SSL certificates that are being used b'
        'y specific botnet C&amp;C channels to control infected computers" />\n<'
        'meta name="keywords" content="SSL, blacklist, blocklist, database, fin'
        'gerprint, sha1, suricata, ids, ips, intrusion detection, prevention, s'
        'nort" />\n<link href="/css/layout.css" rel="stylesheet" type="text/css"'
        ' />\n<link rel="shortcut icon" type="image/x-icon" href="/favicon.ico" '
        '/>\n<script type="text/javascript" src="/js/sorttable.js"></script>\n<ti'
        'tle>SSL Blacklist :: Blacklist</title></head>\n<body>\n<div class="MainC'
        'ontainer">\n<div class="Header"></div>\n<div class="navigation"><a href='
        '"/" target="_parent" title="SSL Blacklist Home">Home</a> | <a href="/b'
        'lacklist/" target="_parent" title="SSL Blacklist">SSL Blacklist</a> | '
        '<a href="http://www.abuse.ch/?page_id=4727" target="_blank" title="Con'
        'tact abuse.ch">Contact</a></div>\n<h1>SSL Certificate Information</h1>'
        '\n<table class="tlstable">\n<tr bgcolor="#ffffff"><th>Subject Common Nam'
        'e:</th><td>C=US, ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgcolor'
        '="#D8D8D8"><th>Subject:</th><td>C=US, ST=Denial, L=Springfield, O=Dis<'
        '/td></tr>\n<tr bgcolor="#ffffff"><th>Issuer Common Name:</th><td>C=US, '
        'ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgcolor="#D8D8D8"><th>Is'
        'suer:</th><td>C=US, ST=Denial, L=Springfield, O=Dis</td></tr>\n<tr bgco'
        'lor="#ffffff"><th>SSL Version:</th><td>TLS 1.2</td></tr>\n<tr bgcolor="'
        '#D8D8D8"><th>Fingerprint (SHA1):</th><td>dcbe920e3d0cba40be80fba5e23a6'
        'b4f9a706dd4</td></tr>\n<tr bgcolor="red"><th>Status:</th><td><strong>Bl'
        'acklisted</strong> (Reason: TorrentLocker C&amp;C, Listing date: 2016-'
        '10-07 04:51:52)</td></tr>\n</table>\n<br /><h2>Associated malware binari'
        'es</h2>\n<table class="sortable">\n<tr><th>Timestamp (UTC)</th><th>Malwa'
        're binary (MD5 hash)</th><th>DstIP</th><th>DstPort</th></tr>\n<tr bgcol'
        'or="#D8D8D8"><td>2016-10-06 15:32:44</td><td>cedb27c0621a42ca3da0b0a01'
        '2e2ac43</td><td>46.38.52.233</td><td>443</td></tr>\n</table>\n<p># of re'
        'ferencing malware binaries: <strong>4</strong></p>\n<div class="footer"'
        '>Copyright &copy; 2016 - sslbl.abuse.ch</div>\n</div>\n</body>\n</html>'
        '\n')

    states = [
        {
            "https://sslbl.abuse.ch/intel/e03e335629b882f1f03f091123511eaa3fc2d6b1":
            {
                "subject": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "issuer": "C=GB, ST=Yorks, L=York, O=MyCompany Ltd., OU=IT, CN=localhost",
                "fingerprint": "e03e335629b882f1f03f091123511eaa3fc2d6b1",
                "name": "ZeuS C&C",
                "timestamp": "2016-10-17 11:52:40",
                "binaries": [
                    (
                        "2016-10-13 16:27:10",
                        "76b609dac79e76fe7b5a78af35c5a2d6",
                        "52.77.110.77",
                        "443",
                    ),
                    (
                        "2016-10-10 17:29:57",
                        "9096210f20753c836378ca7aa18c3d25",
                        "52.77.110.77",
                        "443",
                    ),
                ],
            },
        },
        {
            "https://sslbl.abuse.ch/intel/dcbe920e3d0cba40be80fba5e23a6b4f9a706dd4":
            {
                "subject": "C=US, ST=Denial, L=Springfield, O=Dis",
                "issuer": "C=US, ST=Denial, L=Springfield, O=Dis",
                "fingerprint": "dcbe920e3d0cba40be80fba5e23a6b4f9a706dd4",
                "name": "TorrentLocker C&C",
                "timestamp": "2016-10-07 04:51:52",
                "binaries": [
                    (
                        "2016-10-06 15:32:44",
                        "cedb27c0621a42ca3da0b0a012e2ac43",
                        "46.38.52.233",
                        "443",
                    ),
                ],
            },
        },
    ]

    params = [
        # 1st case: detail page does not contain binaries table
        param(
            rss=regular_rss[0],
            page=detail_page,
            state=None,
            result=results[0],
        ).label('no_binaries'),

        # 2nd case: detail page with binaries table
        param(
            rss=regular_rss[1],
            page=binaries_page,
            state=None,
            result=results[1],
        ).label('binaries'),

        # 3rd case: invalid RSS, no URL, no new data
        param(
            rss=invalid_rss[0],
            page=None,
            state=None,
            result=None,
        ).label('no_url'),

        # 4th case: detail page contains one more binary record,
        # comparing to data saved during last collector's "run"
        param(
            rss=regular_rss[2],
            page=updated_page,
            state=states[0],
            result=results[2],
        ).label('updated_page'),

        # 5th case: no new items, do not publish
        param(
            rss=regular_rss[3],
            page=not_updated_page,
            state=states[1],
            result=None,
        ).label('not_updated_page')
    ]

    mocked_config = {
        'url': mock.sentinel.dummy_url,
    }


    @foreach(params)
    def test__get_output_data_body(self, rss, page, state, result, label):
        with mock.patch('n6.collectors.generic.CollectorWithStateMixin.__init__'), \
             mock.patch.object(self.COLLECTOR_CLASS, 'config', self.mocked_config, create=True):
            instance = self.COLLECTOR_CLASS()
            instance._download_retry = mock.Mock(return_value=rss)
            instance._download_retry_external = mock.Mock(return_value=page)
            instance.load_state = mock.Mock(return_value=state)

            if label in ('no_url', 'not_updated_page'):
                with self.assertRaises(NoNewDataException):
                    self.COLLECTOR_CLASS.get_output_data_body(instance)
            else:
                output_data_body = self.COLLECTOR_CLASS.get_output_data_body(instance)
                self.assertDictEqual(loads(output_data_body), result)


class TestAbuseChSSLBlacklistDyreCollector(_TestAbuseChSSLBlacklistBase):

    COLLECTOR_CLASS = AbuseChSSLBlacklistDyreCollector

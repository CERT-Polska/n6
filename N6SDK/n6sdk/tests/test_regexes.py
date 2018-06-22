# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.


import unittest

from n6sdk.regexes import (
    CC_SIMPLE_REGEX,
    DOMAIN_ASCII_LOWERCASE_REGEX,
    DOMAIN_ASCII_LOWERCASE_STRICT_REGEX,
    IPv4_STRICT_DECIMAL_REGEX,
    IPv4_CIDR_NETWORK_REGEX,
    IPv4_ANONYMIZED_REGEX,
    SOURCE_REGEX,
    PY_IDENTIFIER_REGEX,
)


class Test_CC_SIMPLE_REGEX(unittest.TestCase):

    regex = CC_SIMPLE_REGEX

    def test_valid(self):
        self.assertRegexpMatches('PL', self.regex)
        self.assertRegexpMatches('FR', self.regex)
        self.assertRegexpMatches('US', self.regex)
        self.assertRegexpMatches('X1', self.regex)
        self.assertRegexpMatches('Y2', self.regex)

    def test_not_valid(self):
        self.assertNotRegexpMatches('Pl', self.regex)
        self.assertNotRegexpMatches('pL', self.regex)
        self.assertNotRegexpMatches('pl', self.regex)
        self.assertNotRegexpMatches(' PL', self.regex)
        self.assertNotRegexpMatches('PL ', self.regex)
        self.assertNotRegexpMatches('USA', self.regex)
        self.assertNotRegexpMatches('Y', self.regex)
        self.assertNotRegexpMatches('12', self.regex)
        self.assertNotRegexpMatches('Y3', self.regex)
        self.assertNotRegexpMatches('', self.regex)


class Test_DOMAIN_ASCII_LOWERCASE_REGEX(unittest.TestCase):

    regex = DOMAIN_ASCII_LOWERCASE_REGEX

    def test_valid(self):
        self.assertRegexpMatches('t', self.regex)
        self.assertRegexpMatches(u't', self.regex)
        self.assertRegexpMatches('tt', self.regex)
        self.assertRegexpMatches(u't-t', self.regex)
        self.assertRegexpMatches('t---t', self.regex)
        self.assertRegexpMatches(u'tt-ttt-tt', self.regex)
        self.assertRegexpMatches('testtesttest', self.regex)
        self.assertRegexpMatches(u'test.com', self.regex)
        self.assertRegexpMatches('www.a-b-c.test.com', self.regex)
        self.assertRegexpMatches(u'www.a-b-c.test.com', self.regex)
        self.assertRegexpMatches('abc.123.www.c3.tr-al-ala.1--es--2.test.com',
                                 self.regex)
        self.assertRegexpMatches('www.{}.test.com'.format(63 * 'x'),
                                 self.regex)
        self.assertRegexpMatches(u'www.{}.test.com'.format(63 * u'x'),
                                 self.regex)
        self.assertRegexpMatches('life_is_more_eventful_than.rfc',
                                 self.regex)
        self.assertRegexpMatches(u'life_is_more_eventful_than.rfc',
                                 self.regex)
        self.assertRegexpMatches('-', self.regex)
        self.assertRegexpMatches(u'___.___', self.regex)
        self.assertRegexpMatches('-', self.regex)
        self.assertRegexpMatches('-t', self.regex)
        self.assertRegexpMatches(u't-', self.regex)
        self.assertRegexpMatches('-t-', self.regex)
        self.assertRegexpMatches(u'-www.test.com', self.regex)
        self.assertRegexpMatches('www-.test.com', self.regex)
        self.assertRegexpMatches(u'www.-test.com', self.regex)
        self.assertRegexpMatches('www.test-.com', self.regex)
        self.assertRegexpMatches(u'www.test.-com', self.regex)
        self.assertRegexpMatches('www.test.com-', self.regex)
        self.assertRegexpMatches('www.test.z55', self.regex)
        self.assertRegexpMatches(u'www.test.z55', self.regex)
        self.assertRegexpMatches('www.15.15.15.15.z55', self.regex)
        self.assertRegexpMatches(u'www.15.15.15.15.z55', self.regex)
        self.assertRegexpMatches('15.15.15.15.z55', self.regex)
        self.assertRegexpMatches(u'15.15.15.15.z55', self.regex)

    def test_not_valid(self):
        self.assertNotRegexpMatches('', self.regex)
        self.assertNotRegexpMatches('.www.test.com', self.regex)
        self.assertNotRegexpMatches('www..test.com', self.regex)
        self.assertNotRegexpMatches('www.test.com.', self.regex)
        self.assertNotRegexpMatches(' www.test.com', self.regex)
        self.assertNotRegexpMatches('www .test.com', self.regex)
        self.assertNotRegexpMatches(u'www. test.com', self.regex)
        self.assertNotRegexpMatches(u'www.test.com ', self.regex)
        self.assertNotRegexpMatches(u'www.tęst.com', self.regex)
        self.assertNotRegexpMatches('www.test.com ', self.regex)
        self.assertNotRegexpMatches('www.t@st.com', self.regex)
        self.assertNotRegexpMatches('www.tęst.com', self.regex)
        self.assertNotRegexpMatches(u'www.tęst.com', self.regex)
        self.assertNotRegexpMatches('www.TEST.com', self.regex)
        self.assertNotRegexpMatches(u'www.TEST.com', self.regex)
        self.assertNotRegexpMatches('http://www.test.com', self.regex)
        self.assertNotRegexpMatches('www.{}.test.com'.format(64 * 'x'),
                                    self.regex)
        self.assertNotRegexpMatches(u'www.{}.test.com'.format(64 * u'x'),
                                    self.regex)
        self.assertNotRegexpMatches('www.test.5', self.regex)
        self.assertNotRegexpMatches(u'www.test.5', self.regex)
        self.assertNotRegexpMatches('15.15.15.15', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15', self.regex)
        self.assertNotRegexpMatches('15.15.15.15.z55:1234', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15.z55:1234', self.regex)
        self.assertNotRegexpMatches('15.15.15.15.z55:z1234', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15.z55:z1234', self.regex)


class Test_DOMAIN_ASCII_LOWERCASE_STRICT_REGEX(unittest.TestCase):

    regex = DOMAIN_ASCII_LOWERCASE_STRICT_REGEX

    def test_valid(self):
        self.assertRegexpMatches('t', self.regex)
        self.assertRegexpMatches(u't', self.regex)
        self.assertRegexpMatches('tt', self.regex)
        self.assertRegexpMatches(u't-t', self.regex)
        self.assertRegexpMatches('t---t', self.regex)
        self.assertRegexpMatches(u'tt-ttt-tt', self.regex)
        self.assertRegexpMatches('testtesttest', self.regex)
        self.assertRegexpMatches(u'test.com', self.regex)
        self.assertRegexpMatches('www.a-b-c.test.com', self.regex)
        self.assertRegexpMatches(u'www.a-b-c.test.com', self.regex)
        self.assertRegexpMatches('abc.123.www.c3.tr-al-ala.1--es--2.test.com',
                                 self.regex)
        self.assertRegexpMatches('www.{}.test.com'.format(63 * 'x'),
                                 self.regex)
        self.assertRegexpMatches(u'www.{}.test.com'.format(63 * u'x'),
                                 self.regex)
        self.assertRegexpMatches('www.test.z55', self.regex)
        self.assertRegexpMatches(u'www.test.z55', self.regex)
        self.assertRegexpMatches('www.15.15.15.15.z55', self.regex)
        self.assertRegexpMatches(u'www.15.15.15.15.z55', self.regex)
        self.assertRegexpMatches('15.15.15.15.z55', self.regex)
        self.assertRegexpMatches(u'15.15.15.15.z55', self.regex)

    def test_not_valid(self):
        self.assertNotRegexpMatches(u'not_compliant_with.rfc', self.regex)
        self.assertNotRegexpMatches(u'___.___', self.regex)
        self.assertNotRegexpMatches('', self.regex)
        self.assertNotRegexpMatches('-', self.regex)
        self.assertNotRegexpMatches('-t', self.regex)
        self.assertNotRegexpMatches('t-', self.regex)
        self.assertNotRegexpMatches('-t-', self.regex)
        self.assertNotRegexpMatches('-www.test.com', self.regex)
        self.assertNotRegexpMatches('www-.test.com', self.regex)
        self.assertNotRegexpMatches(u'www.-test.com', self.regex)
        self.assertNotRegexpMatches(u'www.test-.com', self.regex)
        self.assertNotRegexpMatches(u'www.test.-com', self.regex)
        self.assertNotRegexpMatches('www.test.com-', self.regex)
        self.assertNotRegexpMatches('.www.test.com', self.regex)
        self.assertNotRegexpMatches('www..test.com', self.regex)
        self.assertNotRegexpMatches('www.test.com.', self.regex)
        self.assertNotRegexpMatches(' www.test.com', self.regex)
        self.assertNotRegexpMatches('www .test.com', self.regex)
        self.assertNotRegexpMatches(u'www. test.com', self.regex)
        self.assertNotRegexpMatches(u'www.test.com ', self.regex)
        self.assertNotRegexpMatches(u'www.test .com', self.regex)
        self.assertNotRegexpMatches('www.test.com ', self.regex)
        self.assertNotRegexpMatches('www.t@st.com', self.regex)
        self.assertNotRegexpMatches('www.tęst.com', self.regex)
        self.assertNotRegexpMatches(u'www.tęst.com', self.regex)
        self.assertNotRegexpMatches('www.TEST.com', self.regex)
        self.assertNotRegexpMatches(u'www.TEST.com', self.regex)
        self.assertNotRegexpMatches('http://www.test.com', self.regex)
        self.assertNotRegexpMatches('www.{}.test.com'.format(64 * 'x'),
                                    self.regex)
        self.assertNotRegexpMatches(u'www.{}.test.com'.format(64 * u'x'),
                                    self.regex)
        self.assertNotRegexpMatches('www.test.5', self.regex)
        self.assertNotRegexpMatches(u'www.test.5', self.regex)
        self.assertNotRegexpMatches('15.15.15.15', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15', self.regex)
        self.assertNotRegexpMatches('15.15.15.15.z55:1234', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15.z55:1234', self.regex)
        self.assertNotRegexpMatches('15.15.15.15.z55:z1234', self.regex)
        self.assertNotRegexpMatches(u'15.15.15.15.z55:z1234', self.regex)


class Test_IPv4_STRICT_DECIMAL_REGEX(unittest.TestCase):

    regex = IPv4_STRICT_DECIMAL_REGEX

    def test_valid(self):
        self.assertRegexpMatches('1.2.3.4', self.regex)
        self.assertRegexpMatches('11.22.33.44', self.regex)
        self.assertRegexpMatches('211.222.233.244', self.regex)
        self.assertRegexpMatches('255.1.0.254', self.regex)
        self.assertRegexpMatches('250.251.253.254', self.regex)
        self.assertRegexpMatches('255.255.255.255', self.regex)
        self.assertRegexpMatches('127.0.0.1', self.regex)
        self.assertRegexpMatches('192.168.10.255', self.regex)
        self.assertRegexpMatches('0.0.0.0', self.regex)
        self.assertRegexpMatches('0.1.2.3', self.regex)
        self.assertRegexpMatches('1.2.0.3', self.regex)
        self.assertRegexpMatches('1.2.3.0', self.regex)

    def test_too_big_num(self):
        self.assertNotRegexpMatches('256.22.33.44', self.regex)
        self.assertNotRegexpMatches('22.256.33.44', self.regex)
        self.assertNotRegexpMatches('22.33.256.44', self.regex)
        self.assertNotRegexpMatches('22.33.44.256', self.regex)
        self.assertNotRegexpMatches('1000.1000.1000.1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegexpMatches('11223344', self.regex)
        self.assertNotRegexpMatches('11.22.33', self.regex)
        self.assertNotRegexpMatches('.11.22.33.44', self.regex)
        self.assertNotRegexpMatches('11.22...33.44', self.regex)
        self.assertNotRegexpMatches('11.22.33.44.', self.regex)
        self.assertNotRegexpMatches('11.22.33.44.55', self.regex)
        self.assertNotRegexpMatches('011.22.33.44', self.regex)
        self.assertNotRegexpMatches('00.1.2.3', self.regex)
        self.assertNotRegexpMatches('1.2.00.3', self.regex)
        self.assertNotRegexpMatches('1.2.3.00', self.regex)
        self.assertNotRegexpMatches('11.22.033.44', self.regex)
        self.assertNotRegexpMatches(' 11.22.33.44', self.regex)
        self.assertNotRegexpMatches('11.22.33.44 ', self.regex)
        self.assertNotRegexpMatches('11.22. 33.44', self.regex)
        self.assertNotRegexpMatches('11.22 .33.44', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('11.-22.33.44', self.regex)
        self.assertNotRegexpMatches('example.com', self.regex)
        self.assertNotRegexpMatches('http://1.2.3.4', self.regex)
        self.assertNotRegexpMatches('', self.regex)


class Test_IPv4_CIDR_NETWORK_REGEX(unittest.TestCase):

    regex = IPv4_CIDR_NETWORK_REGEX

    def test_valid(self):
        self.assertRegexpMatches('1.2.3.4/0', self.regex)
        self.assertRegexpMatches('1.2.3.4/27', self.regex)
        self.assertRegexpMatches('1.2.3.4/28', self.regex)
        self.assertRegexpMatches('1.2.3.4/32', self.regex)
        self.assertRegexpMatches('11.22.33.44/10', self.regex)
        self.assertRegexpMatches('211.222.233.244/19', self.regex)
        self.assertRegexpMatches('255.1.0.254/20', self.regex)
        self.assertRegexpMatches('250.251.253.254/28', self.regex)
        self.assertRegexpMatches('255.255.255.255/0', self.regex)
        self.assertRegexpMatches('255.255.255.255/32', self.regex)
        self.assertRegexpMatches('127.0.0.1/28', self.regex)
        self.assertRegexpMatches('192.168.10.255/28', self.regex)
        self.assertRegexpMatches('0.0.0.0/0', self.regex)
        self.assertRegexpMatches('0.0.0.0/32', self.regex)
        self.assertRegexpMatches('0.1.2.3/28', self.regex)
        self.assertRegexpMatches('1.2.0.3/28', self.regex)
        self.assertRegexpMatches('1.2.3.0/28', self.regex)

    def test_too_big_num(self):
        self.assertNotRegexpMatches('256.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('22.256.33.44/28', self.regex)
        self.assertNotRegexpMatches('22.33.256.44/28', self.regex)
        self.assertNotRegexpMatches('22.33.44.256/28', self.regex)
        self.assertNotRegexpMatches('1000.1000.1000.1000/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/33', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegexpMatches('1122334428', self.regex)
        self.assertNotRegexpMatches('11223344/28', self.regex)
        self.assertNotRegexpMatches('11.22.33/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44.55/28', self.regex)
        self.assertNotRegexpMatches('.11.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22...33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44./28', self.regex)
        self.assertNotRegexpMatches('11.22.33.28', self.regex)
        self.assertNotRegexpMatches('11.22.33.28.', self.regex)
        self.assertNotRegexpMatches('.11.22.33.28.', self.regex)
        self.assertNotRegexpMatches('011.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22.033.44/28', self.regex)
        self.assertNotRegexpMatches('00.1.2.3/28', self.regex)
        self.assertNotRegexpMatches('1.2.00.3/28', self.regex)
        self.assertNotRegexpMatches('1.2.3.00/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/028', self.regex)
        self.assertNotRegexpMatches(' 11.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/ 28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44 /28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/28 ', self.regex)
        self.assertNotRegexpMatches('11.22. 33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22 .33.44/28', self.regex)
        self.assertNotRegexpMatches('11.-22.33.44/28', self.regex)
        self.assertNotRegexpMatches('11.22.33.44/-28', self.regex)
        self.assertNotRegexpMatches('1.2.3.4', self.regex)
        self.assertNotRegexpMatches('11.22.33.44', self.regex)
        self.assertNotRegexpMatches('example.com/28', self.regex)
        self.assertNotRegexpMatches('http://1.2.3.4/28', self.regex)
        self.assertNotRegexpMatches('', self.regex)


class Test_IPv4_ANONYMIZED_REGEX(unittest.TestCase):

    regex = IPv4_ANONYMIZED_REGEX

    def test_valid(self):
        self.assertRegexpMatches('x.2.3.4', self.regex)
        self.assertRegexpMatches('x.x.33.44', self.regex)
        self.assertRegexpMatches('x.x.x.244', self.regex)
        self.assertRegexpMatches('x.1.0.254', self.regex)
        self.assertRegexpMatches('x.251.x.254', self.regex)
        self.assertRegexpMatches('x.255.187.x', self.regex)
        self.assertRegexpMatches('x.x.x.x', self.regex)  # silly but valid
        self.assertRegexpMatches('x.0.0.0', self.regex)
        self.assertRegexpMatches('x.1.2.3', self.regex)
        self.assertRegexpMatches('x.2.0.3', self.regex)
        self.assertRegexpMatches('x.2.3.0', self.regex)

    def test_not_anonymized(self):
        self.assertNotRegexpMatches('1.2.3.4', self.regex)
        self.assertNotRegexpMatches('11.22.33.44', self.regex)
        self.assertNotRegexpMatches('211.222.233.244', self.regex)
        self.assertNotRegexpMatches('255.1.0.254', self.regex)
        self.assertNotRegexpMatches('250.251.253.254', self.regex)
        self.assertNotRegexpMatches('255.255.255.255', self.regex)
        self.assertNotRegexpMatches('127.0.0.1', self.regex)
        self.assertNotRegexpMatches('192.168.10.255', self.regex)
        self.assertNotRegexpMatches('0.0.0.0', self.regex)
        self.assertNotRegexpMatches('0.1.2.3', self.regex)
        self.assertNotRegexpMatches('1.2.0.3', self.regex)
        self.assertNotRegexpMatches('1.2.3.0', self.regex)

    def test_too_big_num(self):
        self.assertNotRegexpMatches('x.256.33.44', self.regex)
        self.assertNotRegexpMatches('x.33.256.44', self.regex)
        self.assertNotRegexpMatches('x.33.44.256', self.regex)
        self.assertNotRegexpMatches('x.1000.1000.1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegexpMatches('11.x.22.33', self.regex)
        self.assertNotRegexpMatches('11.22.x.x', self.regex)
        self.assertNotRegexpMatches('xx.11.22.33', self.regex)
        self.assertNotRegexpMatches('xx.11.xx.33', self.regex)
        self.assertNotRegexpMatches('11223344', self.regex)
        self.assertNotRegexpMatches('x223344', self.regex)
        self.assertNotRegexpMatches('11.22.33', self.regex)
        self.assertNotRegexpMatches('x.22.33', self.regex)
        self.assertNotRegexpMatches('.x.22.33.44', self.regex)
        self.assertNotRegexpMatches('x.22...33.44', self.regex)
        self.assertNotRegexpMatches('x.22.33.44.', self.regex)
        self.assertNotRegexpMatches('x.22.33.44.55', self.regex)
        self.assertNotRegexpMatches('x.022.33.44', self.regex)
        self.assertNotRegexpMatches('xx.1.2.3', self.regex)
        self.assertNotRegexpMatches('x.2.00.3', self.regex)
        self.assertNotRegexpMatches('x.2.3.00', self.regex)
        self.assertNotRegexpMatches('x.22.033.44', self.regex)
        self.assertNotRegexpMatches(' x.22.33.44', self.regex)
        self.assertNotRegexpMatches('x.22.33.44 ', self.regex)
        self.assertNotRegexpMatches('x.22. 33.44', self.regex)
        self.assertNotRegexpMatches('x.22 .33.44', self.regex)
        self.assertNotRegexpMatches('x.22.33.44/28', self.regex)
        self.assertNotRegexpMatches('x.-22.33.44', self.regex)
        self.assertNotRegexpMatches('example.com', self.regex)
        self.assertNotRegexpMatches('http://x.2.3.4', self.regex)
        self.assertNotRegexpMatches('', self.regex)


## TODO:
#class Test_EMAIL_SIMPLIFIED_REGEX(unittest.TestCase):


## TODO:
#class Test_IBAN_REGEX(unittest.TestCase):


class Test_SOURCE_REGEX(unittest.TestCase):

    regex = SOURCE_REGEX

    def test_valid(self):
        self.assertRegexpMatches('foo.bar', self.regex)
        self.assertRegexpMatches('foo-foo.bar', self.regex)
        self.assertRegexpMatches('-spam.ha--m--', self.regex)
        self.assertRegexpMatches('a.b', self.regex)
        self.assertRegexpMatches('-.-', self.regex)  # weird but legal

    def test_not_valid(self):
        self.assertNotRegexpMatches('', self.regex)
        self.assertNotRegexpMatches('.', self.regex)
        self.assertNotRegexpMatches('foo.', self.regex)
        self.assertNotRegexpMatches('.bar', self.regex)
        self.assertNotRegexpMatches('foo-foo', self.regex)
        self.assertNotRegexpMatches('foo-foo.bar.spam', self.regex)
        self.assertNotRegexpMatches('Foo-Foo.bar', self.regex)
        self.assertNotRegexpMatches('foo_foo.bar', self.regex)


class Test_PY_IDENTIFIER_REGEX(unittest.TestCase):

    regex = PY_IDENTIFIER_REGEX

    def test_valid(self):
        self.assertRegexpMatches('_', self.regex)
        self.assertRegexpMatches('a', self.regex)
        self.assertRegexpMatches('spam', self.regex)
        self.assertRegexpMatches('SPAM', self.regex)
        self.assertRegexpMatches('spam_123', self.regex)
        self.assertRegexpMatches('Spam123', self.regex)
        self.assertRegexpMatches('_spaM_', self.regex)
        self.assertRegexpMatches('_123', self.regex)
        self.assertRegexpMatches('s123pam', self.regex)

    def test_not_valid(self):
        self.assertNotRegexpMatches('', self.regex)
        self.assertNotRegexpMatches('-', self.regex)
        self.assertNotRegexpMatches('1', self.regex)
        self.assertNotRegexpMatches('123', self.regex)
        self.assertNotRegexpMatches('123spam', self.regex)
        self.assertNotRegexpMatches('123SPAM', self.regex)
        self.assertNotRegexpMatches('123_', self.regex)
        self.assertNotRegexpMatches('spam-123', self.regex)
        self.assertNotRegexpMatches('spam!', self.regex)


### TODO -- test the regexes:
#    ISO_DATE_REGEX
#    ISO_TIME_REGEX
#    ISO_DATETIME_REGEX
# (now they are covered only indirectly by some
# doctests in n6sdk.datetime_helpers)

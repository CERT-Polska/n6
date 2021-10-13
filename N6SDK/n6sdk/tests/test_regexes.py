# Copyright (c) 2013-2021 NASK. All rights reserved.


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
        self.assertRegex('PL', self.regex)
        self.assertRegex('FR', self.regex)
        self.assertRegex('US', self.regex)
        self.assertRegex('X1', self.regex)
        self.assertRegex('Y2', self.regex)

    def test_not_valid(self):
        self.assertNotRegex('Pl', self.regex)
        self.assertNotRegex('pL', self.regex)
        self.assertNotRegex('pl', self.regex)
        self.assertNotRegex(' PL', self.regex)
        self.assertNotRegex('PL ', self.regex)
        self.assertNotRegex('USA', self.regex)
        self.assertNotRegex('Y', self.regex)
        self.assertNotRegex('12', self.regex)
        self.assertNotRegex('Y3', self.regex)
        self.assertNotRegex('', self.regex)


class Test_DOMAIN_ASCII_LOWERCASE_REGEX(unittest.TestCase):

    regex = DOMAIN_ASCII_LOWERCASE_REGEX

    def test_valid(self):
        self.assertRegex('t', self.regex)
        self.assertRegex('tt', self.regex)
        self.assertRegex('t-t', self.regex)
        self.assertRegex('t---t', self.regex)
        self.assertRegex('tt-ttt-tt', self.regex)
        self.assertRegex('testtesttest', self.regex)
        self.assertRegex('test.com', self.regex)
        self.assertRegex('www.a-b-c.test.com', self.regex)
        self.assertRegex('abc.123.www.c3.tr-al-ala.1--es--2.test.com',
                                 self.regex)
        self.assertRegex('www.{}.test.com'.format(63 * 'x'),
                                 self.regex)
        self.assertRegex('life_is_more_eventful_than.rfc',
                                 self.regex)
        self.assertRegex('-', self.regex)
        self.assertRegex('___.___', self.regex)
        self.assertRegex('-t', self.regex)
        self.assertRegex('t-', self.regex)
        self.assertRegex('-t-', self.regex)
        self.assertRegex('-www.test.com', self.regex)
        self.assertRegex('www-.test.com', self.regex)
        self.assertRegex('www.-test.com', self.regex)
        self.assertRegex('www.test-.com', self.regex)
        self.assertRegex('www.test.-com', self.regex)
        self.assertRegex('www.test.com-', self.regex)
        self.assertRegex('www.test.z55', self.regex)
        self.assertRegex('www.15.15.15.15.z55', self.regex)
        self.assertRegex('15.15.15.15.z55', self.regex)

    def test_not_valid(self):
        self.assertNotRegex('', self.regex)
        self.assertNotRegex('.www.test.com', self.regex)
        self.assertNotRegex('www..test.com', self.regex)
        self.assertNotRegex('www.test.com.', self.regex)
        self.assertNotRegex(' www.test.com', self.regex)
        self.assertNotRegex('www .test.com', self.regex)
        self.assertNotRegex('www. test.com', self.regex)
        self.assertNotRegex('www.test.com ', self.regex)
        self.assertNotRegex('www.tęst.com', self.regex)
        self.assertNotRegex('www.test.com ', self.regex)
        self.assertNotRegex('www.t@st.com', self.regex)
        self.assertNotRegex('www.TEST.com', self.regex)
        self.assertNotRegex('http://www.test.com', self.regex)
        self.assertNotRegex('www.{}.test.com'.format(64 * 'x'),
                                    self.regex)
        self.assertNotRegex('www.test.5', self.regex)
        self.assertNotRegex('15.15.15.15', self.regex)
        self.assertNotRegex('15.15.15.15.z55:1234', self.regex)
        self.assertNotRegex('15.15.15.15.z55:z1234', self.regex)


class Test_DOMAIN_ASCII_LOWERCASE_STRICT_REGEX(unittest.TestCase):

    regex = DOMAIN_ASCII_LOWERCASE_STRICT_REGEX

    def test_valid(self):
        self.assertRegex('t', self.regex)
        self.assertRegex('tt', self.regex)
        self.assertRegex('t-t', self.regex)
        self.assertRegex('t---t', self.regex)
        self.assertRegex('tt-ttt-tt', self.regex)
        self.assertRegex('testtesttest', self.regex)
        self.assertRegex('test.com', self.regex)
        self.assertRegex('www.a-b-c.test.com', self.regex)
        self.assertRegex('abc.123.www.c3.tr-al-ala.1--es--2.test.com',
                                 self.regex)
        self.assertRegex('www.{}.test.com'.format(63 * 'x'),
                                 self.regex)
        self.assertRegex('www.test.z55', self.regex)
        self.assertRegex('www.15.15.15.15.z55', self.regex)
        self.assertRegex('15.15.15.15.z55', self.regex)

    def test_not_valid(self):
        self.assertNotRegex('not_compliant_with.rfc', self.regex)
        self.assertNotRegex('___.___', self.regex)
        self.assertNotRegex('', self.regex)
        self.assertNotRegex('-', self.regex)
        self.assertNotRegex('-t', self.regex)
        self.assertNotRegex('t-', self.regex)
        self.assertNotRegex('-t-', self.regex)
        self.assertNotRegex('-www.test.com', self.regex)
        self.assertNotRegex('www-.test.com', self.regex)
        self.assertNotRegex('www.-test.com', self.regex)
        self.assertNotRegex('www.test-.com', self.regex)
        self.assertNotRegex('www.test.-com', self.regex)
        self.assertNotRegex('www.test.com-', self.regex)
        self.assertNotRegex('.www.test.com', self.regex)
        self.assertNotRegex('www..test.com', self.regex)
        self.assertNotRegex('www.test.com.', self.regex)
        self.assertNotRegex(' www.test.com', self.regex)
        self.assertNotRegex('www .test.com', self.regex)
        self.assertNotRegex('www. test.com', self.regex)
        self.assertNotRegex('www.test.com ', self.regex)
        self.assertNotRegex('www.test .com', self.regex)
        self.assertNotRegex('www.test.com ', self.regex)
        self.assertNotRegex('www.t@st.com', self.regex)
        self.assertNotRegex('www.tęst.com', self.regex)
        self.assertNotRegex('www.TEST.com', self.regex)
        self.assertNotRegex('http://www.test.com', self.regex)
        self.assertNotRegex('www.{}.test.com'.format(64 * 'x'),
                                    self.regex)
        self.assertNotRegex('www.test.5', self.regex)
        self.assertNotRegex('15.15.15.15', self.regex)
        self.assertNotRegex('15.15.15.15.z55:1234', self.regex)
        self.assertNotRegex('15.15.15.15.z55:z1234', self.regex)


class Test_IPv4_STRICT_DECIMAL_REGEX(unittest.TestCase):

    regex = IPv4_STRICT_DECIMAL_REGEX

    def test_valid(self):
        self.assertRegex('1.2.3.4', self.regex)
        self.assertRegex('11.22.33.44', self.regex)
        self.assertRegex('211.222.233.244', self.regex)
        self.assertRegex('255.1.0.254', self.regex)
        self.assertRegex('250.251.253.254', self.regex)
        self.assertRegex('255.255.255.255', self.regex)
        self.assertRegex('127.0.0.1', self.regex)
        self.assertRegex('192.168.10.255', self.regex)
        self.assertRegex('0.0.0.0', self.regex)
        self.assertRegex('0.1.2.3', self.regex)
        self.assertRegex('1.2.0.3', self.regex)
        self.assertRegex('1.2.3.0', self.regex)

    def test_too_big_num(self):
        self.assertNotRegex('256.22.33.44', self.regex)
        self.assertNotRegex('22.256.33.44', self.regex)
        self.assertNotRegex('22.33.256.44', self.regex)
        self.assertNotRegex('22.33.44.256', self.regex)
        self.assertNotRegex('1000.1000.1000.1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegex('11223344', self.regex)
        self.assertNotRegex('11.22.33', self.regex)
        self.assertNotRegex('.11.22.33.44', self.regex)
        self.assertNotRegex('11.22...33.44', self.regex)
        self.assertNotRegex('11.22.33.44.', self.regex)
        self.assertNotRegex('11.22.33.44.55', self.regex)
        self.assertNotRegex('011.22.33.44', self.regex)
        self.assertNotRegex('00.1.2.3', self.regex)
        self.assertNotRegex('1.2.00.3', self.regex)
        self.assertNotRegex('1.2.3.00', self.regex)
        self.assertNotRegex('11.22.033.44', self.regex)
        self.assertNotRegex(' 11.22.33.44', self.regex)
        self.assertNotRegex('11.22.33.44 ', self.regex)
        self.assertNotRegex('11.22. 33.44', self.regex)
        self.assertNotRegex('11.22 .33.44', self.regex)
        self.assertNotRegex('11.22.33.44/28', self.regex)
        self.assertNotRegex('11.-22.33.44', self.regex)
        self.assertNotRegex('example.com', self.regex)
        self.assertNotRegex('http://1.2.3.4', self.regex)
        self.assertNotRegex('', self.regex)


class Test_IPv4_CIDR_NETWORK_REGEX(unittest.TestCase):

    regex = IPv4_CIDR_NETWORK_REGEX

    def test_valid(self):
        self.assertRegex('1.2.3.4/0', self.regex)
        self.assertRegex('1.2.3.4/27', self.regex)
        self.assertRegex('1.2.3.4/28', self.regex)
        self.assertRegex('1.2.3.4/32', self.regex)
        self.assertRegex('11.22.33.44/10', self.regex)
        self.assertRegex('211.222.233.244/19', self.regex)
        self.assertRegex('255.1.0.254/20', self.regex)
        self.assertRegex('250.251.253.254/28', self.regex)
        self.assertRegex('255.255.255.255/0', self.regex)
        self.assertRegex('255.255.255.255/32', self.regex)
        self.assertRegex('127.0.0.1/28', self.regex)
        self.assertRegex('192.168.10.255/28', self.regex)
        self.assertRegex('0.0.0.0/0', self.regex)
        self.assertRegex('0.0.0.0/32', self.regex)
        self.assertRegex('0.1.2.3/28', self.regex)
        self.assertRegex('1.2.0.3/28', self.regex)
        self.assertRegex('1.2.3.0/28', self.regex)

    def test_too_big_num(self):
        self.assertNotRegex('256.22.33.44/28', self.regex)
        self.assertNotRegex('22.256.33.44/28', self.regex)
        self.assertNotRegex('22.33.256.44/28', self.regex)
        self.assertNotRegex('22.33.44.256/28', self.regex)
        self.assertNotRegex('1000.1000.1000.1000/28', self.regex)
        self.assertNotRegex('11.22.33.44/33', self.regex)
        self.assertNotRegex('11.22.33.44/1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegex('1122334428', self.regex)
        self.assertNotRegex('11223344/28', self.regex)
        self.assertNotRegex('11.22.33/28', self.regex)
        self.assertNotRegex('11.22.33.44.55/28', self.regex)
        self.assertNotRegex('.11.22.33.44/28', self.regex)
        self.assertNotRegex('11.22...33.44/28', self.regex)
        self.assertNotRegex('11.22.33.44./28', self.regex)
        self.assertNotRegex('11.22.33.28', self.regex)
        self.assertNotRegex('11.22.33.28.', self.regex)
        self.assertNotRegex('.11.22.33.28.', self.regex)
        self.assertNotRegex('011.22.33.44/28', self.regex)
        self.assertNotRegex('11.22.033.44/28', self.regex)
        self.assertNotRegex('00.1.2.3/28', self.regex)
        self.assertNotRegex('1.2.00.3/28', self.regex)
        self.assertNotRegex('1.2.3.00/28', self.regex)
        self.assertNotRegex('11.22.33.44/028', self.regex)
        self.assertNotRegex(' 11.22.33.44/28', self.regex)
        self.assertNotRegex('11.22.33.44/ 28', self.regex)
        self.assertNotRegex('11.22.33.44 /28', self.regex)
        self.assertNotRegex('11.22.33.44/28 ', self.regex)
        self.assertNotRegex('11.22. 33.44/28', self.regex)
        self.assertNotRegex('11.22 .33.44/28', self.regex)
        self.assertNotRegex('11.-22.33.44/28', self.regex)
        self.assertNotRegex('11.22.33.44/-28', self.regex)
        self.assertNotRegex('1.2.3.4', self.regex)
        self.assertNotRegex('11.22.33.44', self.regex)
        self.assertNotRegex('example.com/28', self.regex)
        self.assertNotRegex('http://1.2.3.4/28', self.regex)
        self.assertNotRegex('', self.regex)


class Test_IPv4_ANONYMIZED_REGEX(unittest.TestCase):

    regex = IPv4_ANONYMIZED_REGEX

    def test_valid(self):
        self.assertRegex('x.2.3.4', self.regex)
        self.assertRegex('x.x.33.44', self.regex)
        self.assertRegex('x.x.x.244', self.regex)
        self.assertRegex('x.1.0.254', self.regex)
        self.assertRegex('x.251.x.254', self.regex)
        self.assertRegex('x.255.187.x', self.regex)
        self.assertRegex('x.x.x.x', self.regex)  # silly but valid
        self.assertRegex('x.0.0.0', self.regex)
        self.assertRegex('x.1.2.3', self.regex)
        self.assertRegex('x.2.0.3', self.regex)
        self.assertRegex('x.2.3.0', self.regex)

    def test_not_anonymized(self):
        self.assertNotRegex('1.2.3.4', self.regex)
        self.assertNotRegex('11.22.33.44', self.regex)
        self.assertNotRegex('211.222.233.244', self.regex)
        self.assertNotRegex('255.1.0.254', self.regex)
        self.assertNotRegex('250.251.253.254', self.regex)
        self.assertNotRegex('255.255.255.255', self.regex)
        self.assertNotRegex('127.0.0.1', self.regex)
        self.assertNotRegex('192.168.10.255', self.regex)
        self.assertNotRegex('0.0.0.0', self.regex)
        self.assertNotRegex('0.1.2.3', self.regex)
        self.assertNotRegex('1.2.0.3', self.regex)
        self.assertNotRegex('1.2.3.0', self.regex)

    def test_too_big_num(self):
        self.assertNotRegex('x.256.33.44', self.regex)
        self.assertNotRegex('x.33.256.44', self.regex)
        self.assertNotRegex('x.33.44.256', self.regex)
        self.assertNotRegex('x.1000.1000.1000', self.regex)

    def test_various_defects(self):
        self.assertNotRegex('11.x.22.33', self.regex)
        self.assertNotRegex('11.22.x.x', self.regex)
        self.assertNotRegex('xx.11.22.33', self.regex)
        self.assertNotRegex('xx.11.xx.33', self.regex)
        self.assertNotRegex('11223344', self.regex)
        self.assertNotRegex('x223344', self.regex)
        self.assertNotRegex('11.22.33', self.regex)
        self.assertNotRegex('x.22.33', self.regex)
        self.assertNotRegex('.x.22.33.44', self.regex)
        self.assertNotRegex('x.22...33.44', self.regex)
        self.assertNotRegex('x.22.33.44.', self.regex)
        self.assertNotRegex('x.22.33.44.55', self.regex)
        self.assertNotRegex('x.022.33.44', self.regex)
        self.assertNotRegex('xx.1.2.3', self.regex)
        self.assertNotRegex('x.2.00.3', self.regex)
        self.assertNotRegex('x.2.3.00', self.regex)
        self.assertNotRegex('x.22.033.44', self.regex)
        self.assertNotRegex(' x.22.33.44', self.regex)
        self.assertNotRegex('x.22.33.44 ', self.regex)
        self.assertNotRegex('x.22. 33.44', self.regex)
        self.assertNotRegex('x.22 .33.44', self.regex)
        self.assertNotRegex('x.22.33.44/28', self.regex)
        self.assertNotRegex('x.-22.33.44', self.regex)
        self.assertNotRegex('example.com', self.regex)
        self.assertNotRegex('http://x.2.3.4', self.regex)
        self.assertNotRegex('', self.regex)


## TODO:
#class Test_EMAIL_SIMPLIFIED_REGEX(unittest.TestCase):


## TODO:
#class Test_IBAN_REGEX(unittest.TestCase):


class Test_SOURCE_REGEX(unittest.TestCase):

    regex = SOURCE_REGEX

    def test_valid(self):
        self.assertRegex('foo.bar', self.regex)
        self.assertRegex('foo-foo.bar', self.regex)
        self.assertRegex('-spam.ha--m--', self.regex)
        self.assertRegex('a.b', self.regex)
        self.assertRegex('-.-', self.regex)  # weird but legal

    def test_not_valid(self):
        self.assertNotRegex('', self.regex)
        self.assertNotRegex('.', self.regex)
        self.assertNotRegex('foo.', self.regex)
        self.assertNotRegex('.bar', self.regex)
        self.assertNotRegex('foo-foo', self.regex)
        self.assertNotRegex('foo-foo.bar.spam', self.regex)
        self.assertNotRegex('Foo-Foo.bar', self.regex)
        self.assertNotRegex('foo_foo.bar', self.regex)


class Test_PY_IDENTIFIER_REGEX(unittest.TestCase):

    regex = PY_IDENTIFIER_REGEX

    def test_valid(self):
        self.assertRegex('_', self.regex)
        self.assertRegex('a', self.regex)
        self.assertRegex('spam', self.regex)
        self.assertRegex('SPAM', self.regex)
        self.assertRegex('spam_123', self.regex)
        self.assertRegex('Spam123', self.regex)
        self.assertRegex('_spaM_', self.regex)
        self.assertRegex('_123', self.regex)
        self.assertRegex('s123pam', self.regex)

    def test_not_valid(self):
        self.assertNotRegex('', self.regex)
        self.assertNotRegex('-', self.regex)
        self.assertNotRegex('1', self.regex)
        self.assertNotRegex('123', self.regex)
        self.assertNotRegex('123spam', self.regex)
        self.assertNotRegex('123SPAM', self.regex)
        self.assertNotRegex('123_', self.regex)
        self.assertNotRegex('spam-123', self.regex)
        self.assertNotRegex('spam!', self.regex)


### TODO -- test the regexes:
#    ISO_DATE_REGEX
#    ISO_TIME_REGEX
#    ISO_DATETIME_REGEX
# (now they are covered only indirectly by some
# doctests in n6sdk.datetime_helpers)

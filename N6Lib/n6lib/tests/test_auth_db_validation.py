# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import datetime
import sys
import unittest

from unittest_expander import (
    expand,
    foreach,
)

from n6lib.auth_db.models import (
    CACert,
    Cert,
    CriteriaASN,
    CriteriaCategory,
    CriteriaCC,
    CriteriaContainer,
    CriteriaIPNetwork,
    CriteriaName,
    Component,
    EMailNotificationAddress,
    EMailNotificationTime,
    InsideFilterASN,
    InsideFilterCC,
    InsideFilterFQDN,
    InsideFilterIPNetwork,
    InsideFilterURL,
    Org,
    OrgGroup,
    Source,
    Subsource,
    SubsourceGroup,
    SystemGroup,
    User,
)
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.data_spec import (
    FieldValueError,
    FieldValueTooLongError,
)


@expand
class TestValidators(unittest.TestCase):

    value_too_long_pattern = r'\A(Length of .+ is greater than )(\d{1,3})\Z'
    decode_error_pattern = r'\AValue .+ caused UnicodeDecodeError.+'
    encode_error_pattern = r'\AValue .+ caused UnicodeEncodeError.+'
    ldap_not_safe_char_pattern = r'\AValue: .+ contains illegal character: .+\Z'

    @foreach([
        'example.com',
        'example',
        '  ex-ampl_e.co1m',
        'EXAMPLE.COM',
        u'example.com',
        # max length of a single label (segment of a domain name)
        '{}'.format('a' * 63),
        u'{}'.format(u'b' * 63),
        # max length of a domain name
        '{}'.format('example.'*31 + 'foo.com'),
        u'{}'.format(u'example.'*31 + u'foo.com'),
        'łódź.example.com',   # will be IDNA-encoded...
        u'łódź.example.com',  # will be IDNA-encoded...
    ])
    def test_fqdn(self, val):
        self._test_proper_values(InsideFilterFQDN, {'fqdn': val})

    @foreach(
        'example.com',
        'example',
        'ex-ampl_e.co1m',
        '    EXAMPLE.COM             ',
        u'example.com',
        '{}'.format('a' * CLIENT_ORGANIZATION_MAX_LENGTH),
        u'{}'.format(u'b' * CLIENT_ORGANIZATION_MAX_LENGTH),
    )
    def test_org_id(self, val):
        self._test_proper_values(Org, {'org_id': val})

    @foreach(
        'www.example.123',
        'http://www.example.com',
        '123',
    )
    def test_invalid_regex_domain(self, val):
        msg_pattern = r'.+ is not a valid domain name\Z'
        self._test_illegal_values(InsideFilterFQDN, {'fqdn': val}, FieldValueError, msg_pattern)
        self._test_illegal_values(Org, {'org_id': val}, FieldValueError, msg_pattern)

    def test_too_long_fqdn(self):
        too_long_fqdn = 'example.'*31 + 'fooo.com'
        self._test_illegal_values(InsideFilterFQDN,
                                  {'fqdn': too_long_fqdn},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)
        self._test_illegal_values(InsideFilterFQDN,
                                  {'fqdn': unicode(too_long_fqdn)},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)

    def test_too_long_org_id(self):
        length = 1 + CLIENT_ORGANIZATION_MAX_LENGTH
        self._test_illegal_values(Org,
                                  {'org_id': 'a'*length},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)
        self._test_illegal_values(Org,
                                  {'org_id': u'B'*length},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)

    @foreach(
        123,
        '123',
        u'   123      ',
        4294967295,
        '123.123',
        '65535.65535',
    )
    def test_asn(self, val):
        self._test_proper_values(InsideFilterASN, {'asn': val})
        self._test_proper_values(CriteriaASN, {'asn': val})

    @foreach(
        4294967296,
        '65536.65535',
        u'65535.65536',
        '65536.65536',
        'abc',
        u'ąężź',
    )
    def test_illegal_asn(self, val):
        msg_pattern = r'.+ is not a valid Autonomous System Number\Z'
        self._test_illegal_values(InsideFilterASN, {'asn': val}, FieldValueError, msg_pattern)
        self._test_illegal_values(CriteriaASN, {'asn': val}, FieldValueError, msg_pattern)

    @foreach(
        'pl',
        'PL',
        '   En     ',
        'eN',
        'p1',
        'P2',
    )
    def test_cc(self, val):
        self._test_proper_values(InsideFilterCC, {'cc': val})
        self._test_proper_values(CriteriaCC, {'cc': val})
        self._test_proper_values(Org,
                                 {'org_id': 'example.com',
                                  'email_notifications_language': val})

    @foreach(
        '1P',
        u'a_',
        'ąę',
        u'żę',
        'PLL',
    )
    def test_illegal_cc(self, val):
        message_regex = r'.+ is not a valid 2-character country code\Z'
        self._test_illegal_values(InsideFilterCC, {'cc': val}, FieldValueError, message_regex)
        self._test_illegal_values(CriteriaCC, {'cc': val}, FieldValueError, message_regex)
        self._test_illegal_values(Org,
                                  {'org_id': 'example.com',
                                   'email_notifications_language': val},
                                  FieldValueError, message_regex)

    @foreach(
        'info@example.com',
        u'ex123@example.com',
        'Some@email',
        '      valid_Val@exAmple.com   ',
        'another-val@example.com',
        '123@321',
    )
    def test_email(self, val):
        self._test_proper_values(EMailNotificationAddress, {'email': val})

    @foreach(
        'invalid',
        u'some@some@example.com',
    )
    def test_illegal_email(self, val):
        self._test_illegal_values(EMailNotificationAddress, {'email': val}, FieldValueError,
                                  r'.+ is not a valid e-mail address\Z')

    @foreach(
        'żółw@example.com',
        u'żółw@ęxąplę.com',
        u'other\udcddval@example.com',
    )
    def test_email_ascii_only(self, val):
        self._test_non_ascii_values(EMailNotificationAddress, val, {'email': val})

    @foreach(
        '12:01',
        '1:1',
        '23:30',
        u'1:12',
        10,
        21,
        datetime.time(13, 14),
        datetime.time(15),
    )
    def test_notification_time(self, val):
        self._test_proper_values(EMailNotificationTime, {'notification_time': val})

    @foreach(
        '12',
        '12:',
        u':11',
        '12:03:001',
        'abc',
    )
    def test_illegal_notification_time(self, val):
        expected_msg_pattern = r'\AValue .+ caused ValueError:.+'
        self._test_illegal_values(EMailNotificationTime, {'notification_time': val},
                                  FieldValueError, expected_msg_pattern)

    @foreach(
        11,
        14,
        0,
        23,
    )
    def test_int_cleaning_method_notification_time(self, val):
        expected_val = datetime.time(val)
        self._test_proper_values(EMailNotificationTime, {'notification_time': expected_val})

    def test_illegal_type_notification_time(self):
        expected_msg_pattern = r"\AValue .* is of a wrong type.*"
        new_time = datetime.datetime(2018, 3, 14, 15, 11)
        self._test_illegal_values(EMailNotificationTime, {'notification_time': new_time},
                                  FieldValueError, expected_msg_pattern)

    @foreach(
        '1.2.3.4/0',
        '    11.22.33.44/10      ',
        u'127.0.0.1/28',
        '0.0.0.0/0',
    )
    def test_ip_network(self, val):
        self._test_proper_values(InsideFilterIPNetwork, {'ip_network': val})
        self._test_proper_values(CriteriaIPNetwork, {'ip_network': val})

    @foreach(
        '1122334428',
        '11.22.33.28.',
        '256.22.33.44/28',
        u'1000.1000.1000.1000/28',
        '00.1.2.3/28',
        'example.com/28',
        'http://1.2.3.4/28',
        '',
        u'abcdef',
    )
    def test_illegal_ip_network(self, val):
        expected_msg_pattern = (r'.+ is not a valid CIDR IPv4 network specification\Z')
        self._test_illegal_values(InsideFilterIPNetwork, {'ip_network': val}, FieldValueError,
                                  expected_msg_pattern)
        self._test_illegal_values(CriteriaIPNetwork, {'ip_network': val}, FieldValueError,
                                  expected_msg_pattern)

    def test_wrong_type_ip_network(self):
        tested_value = ('127.0.0.1', '28')
        expected_msg_pattern = r'\AIllegal type of value for a string-type field.\Z'
        self._test_illegal_values(InsideFilterIPNetwork, {'ip_network': tested_value},
                                  FieldValueError, expected_msg_pattern)
        self._test_illegal_values(CriteriaIPNetwork, {'ip_network': tested_value},
                                  FieldValueError, expected_msg_pattern)

    @foreach(
        'http://www.example.com/index.html',
        'any string      ',
        u'   abcd     1234    '
        '------- 22222222 +++++',
        'a' * 2048,
    )
    def test_url(self, val):
        self._test_proper_values(InsideFilterURL, {'url': val})

    def test_decode_error_url(self):
        tested_value = '\xc2 \xd3'
        self._test_illegal_values(InsideFilterURL, {'url': tested_value}, FieldValueError,
                                  self.decode_error_pattern)

    def test_too_long_url(self):
        tested_value = 'a' * 2049
        with self.assertRaises(FieldValueTooLongError):
            InsideFilterURL(url=tested_value)

    @foreach(
        'info@example.com',
        u'ex123@example.com',
        u'Some@email',
        '    vaLid_val@example.com   ',
        'another-val@example.com',
        'so}me@example',
        'so{me@example',
        'so$&?!me@example',
    )
    def test_user_login(self, val):
        self._test_proper_values(User, {'login': val})

    @foreach(
        '.login@example.com',
        'login..login@example.com',
        'login....login@example.com',
        'login.@example.com',
        'lo:gin@example.com',
        'lo   gin@example.com',
        '@example.com',
    )
    def test_illegal_user_login(self, val):
        expected_msg_pattern = (r'.+ is not a valid user login - '
                                r'an e-mail address is expected\.\Z')
        self._test_illegal_values(User, {'login': val}, FieldValueError, expected_msg_pattern)

    def test_user_login_ldap_safe(self):
        tested_val = 'lo<gin@example.com'
        self._test_ldap_not_safe_chars(User, {'login': tested_val})

    def test_non_ascii_user_login(self):
        tested_val = 'ąęź@example.com'
        self._test_non_ascii_values(User, tested_val, {'login': tested_val})

    @foreach(
        'abc.def',
        u'   a-b-c-1.2-d-e-f   ',
        '123.321',
    )
    def test_source(self, val):
        self._test_proper_values(Source, {'source_id': val, 'anonymized_source_id': val})

    @foreach(
        'abcdef',
        '1234',
        'abc.  ',
        'abc.',
        '.cde',
        '    .cde',
        'abc..def',
    )
    def test_illegal_source(self, val):
        expected_msg_pattern = r'.+ is not a valid source specification\Z'
        sample_valid_source = 'abc.def'
        self._test_illegal_values(Source, {'source_id': val}, FieldValueError,
                                  expected_msg_pattern)
        self._test_illegal_values(Source,
                                  {'source_id': sample_valid_source, 'anonymized_source_id': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        '06f30a5903f4cf0642b5',
        'abcdef0123456789ffff',
        u'5cc863bfbf1b669e5f05',
        'B4162A543BE9E50ACE42',
    )
    def test_hex_number(self, val):
        self._test_proper_values(Cert, {'serial_hex': val})

    @foreach(
        'e479-09b_23572199b66',
        '19f16e,29fd.8b56294c',
        '6ę515be3556ą8267826c',
        '   9aadc6e968ee4a4d5601   ',
        'b215',
    )
    def test_illegal_hex_number(self, val):
        expected_msg_pattern = r'.+ is not a valid certificate serial number\Z'
        self._test_illegal_values(Cert, {'serial_hex': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        'n6-service-ca',
        'n6-client-ca',
        'abcc#cert',
        'cert@ca.com',
    )
    def test_ca_label_lowercase(self, val):
        self._test_proper_values(CACert, {'ca_label': val})

    @foreach(
        'n6-service-CA',
        'N6Ca',
        'abcc#Cert',
        'cert@cA.com',
        'certcA',
    )
    def test_non_lowercase_ca_label(self, val):
        expected_msg_pattern = r'\ACA label .+ has to be lowercase\.\Z'
        self._test_illegal_values(CACert, {'ca_label': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        (Org, 'org_id'),
        (CriteriaName, 'name'),
        (CriteriaCategory, 'category'),
        (OrgGroup, 'org_group_id'),
        (Component, 'login'),
        (CriteriaContainer, 'label'),
        (Subsource, 'label'),
        (SubsourceGroup, 'label'),
        (SystemGroup, 'name'),
        (CACert, 'ca_label'),
    )
    def test_ascii_only_fields_with_illegal_chars(self, model, tested_arg):
        tested_val = 'ąęźćżłów'
        self._test_non_ascii_values(model, tested_val, {tested_arg: tested_val})

    @foreach(
        (Org, 'org_id'),
        (OrgGroup, 'org_group_id'),
        (Component, 'login'),
        (CriteriaContainer, 'label'),
        (Subsource, 'label'),
        (SubsourceGroup, 'label'),
        (SystemGroup, 'name'),
        (CACert, 'ca_label'),
    )
    def test_setting_ldap_not_safe_chars(self, model, tested_arg):
        tested_val = 'exa=mple'
        self._test_ldap_not_safe_chars(model, {tested_arg: tested_val})

    def _test_proper_values(self, model, kwargs):
        self.assertTrue(model(**kwargs))

    def _test_illegal_values(self, model, kwargs, expected_exc, expected_msg_pattern):
        with self.assertRaises(expected_exc):
            model(**kwargs)
        self.assertRegexpMatches(sys.exc_info()[1].public_message, expected_msg_pattern)

    def _test_non_ascii_values(self, model, val, kwargs):
        assert isinstance(val, basestring)
        if isinstance(val, str):
            expected_msg_pattern = self.decode_error_pattern
        else:
            expected_msg_pattern = self.encode_error_pattern
        with self.assertRaises(FieldValueError):
            model(**kwargs)
        self.assertRegexpMatches(sys.exc_info()[1].public_message, expected_msg_pattern)

    def _test_ldap_not_safe_chars(self, model, kwargs):
        with self.assertRaises(FieldValueError):
            model(**kwargs)
        self.assertRegexpMatches(sys.exc_info()[1].public_message, self.ldap_not_safe_char_pattern)

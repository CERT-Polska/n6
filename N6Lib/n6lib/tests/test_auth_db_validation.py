# Copyright (c) 2018-2024 NASK. All rights reserved.

import datetime
import unittest
from unittest.mock import (
    call,
    patch,
)
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.auth_db.fields import CategoryCustomizedField
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
    RecentWriteOpCommit,
    DependantEntity,
    EMailNotificationAddress,
    EMailNotificationTime,
    Entity,
    EntityContactPoint,
    EntityContactPointPhone,
    EntityExtraId,
    EntityExtraIdType,
    EntityIPNetwork,
    EntitySector,
    IgnoreList,
    IgnoredIPNetwork,
    InsideFilterASN,
    InsideFilterCC,
    InsideFilterFQDN,
    InsideFilterIPNetwork,
    InsideFilterURL,
    Org,
    OrgConfigUpdateRequest,
    OrgConfigUpdateRequestASN,
    OrgConfigUpdateRequestEMailNotificationAddress,
    OrgConfigUpdateRequestEMailNotificationTime,
    OrgConfigUpdateRequestFQDN,
    OrgConfigUpdateRequestIPNetwork,
    OrgGroup,
    RegistrationRequest,
    RegistrationRequestEMailNotificationAddress,
    RegistrationRequestFQDN,
    RegistrationRequestASN,
    RegistrationRequestIPNetwork,
    Source,
    Subsource,
    SubsourceGroup,
    SystemGroup,
    User,
    UserProvisionalMFAConfig,
    UserSpentMFACode,
    WebToken,
)
from n6lib.const import (
    CATEGORY_ENUMS,
    CLIENT_ORGANIZATION_MAX_LENGTH,
)
from n6lib.data_spec import (
    FieldValueError,
    FieldValueTooLongError,
)


@expand
class TestValidators(unittest.TestCase):

    value_too_long_pattern = r'\b[Ll]ength of .+ is greater than\b'

    @foreach(
        'example.com',
        'example',
        '  ex-ampl_e.co1m',
        'EXAMPLE.COM',
        # max length of a single label (segment of a domain name)
        '{}'.format('a' * 63),
        # max length of a domain name
        '{}'.format('example.'*31 + 'foo.com'),
        # to be be IDNA-encoded...
        'łódź.example.com',
    )
    @foreach(
        InsideFilterFQDN,
        OrgConfigUpdateRequestFQDN,
        RegistrationRequestFQDN,
    )
    def test_fqdn(self, model, val):
        self._test_proper_values(model, {'fqdn': val}, expecting_stripped_string=True)

    @foreach(
        'example.com',
        'example',
        'ex-ampl_e.co1m',
        '    EXAMPLE.COM             ',
        '{}'.format('a' * CLIENT_ORGANIZATION_MAX_LENGTH),
    )
    @foreach(
        Org,
        RegistrationRequest,
    )
    def test_org_id(self, model, val):
        self._test_proper_values(model, {'org_id': val}, expecting_stripped_string=True)

    @foreach(
        param(val='www.example.123'),
        param(val='http://www.example.com'),
        param(val='123'),
    )
    @foreach(
        param(model=InsideFilterFQDN, tested_arg='fqdn'),
        param(model=OrgConfigUpdateRequestFQDN, tested_arg='fqdn'),
        param(model=RegistrationRequestFQDN, tested_arg='fqdn'),
        param(model=Org, tested_arg='org_id'),
        param(model=RegistrationRequest, tested_arg='org_id'),
    )
    def test_invalid_regex_domain(self, model, tested_arg, val):
        expected_msg_pattern = r'\bdomain name\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        InsideFilterFQDN,
        OrgConfigUpdateRequestFQDN,
        RegistrationRequestFQDN,
    )
    def test_too_long_fqdn(self, model):
        too_long_fqdn = 'example.'*31 + 'fooo.com'
        self._test_illegal_values(model,
                                  {'fqdn': too_long_fqdn},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)

    @foreach(
        Org,
        RegistrationRequest,
    )
    def test_too_long_org_id(self, model):
        length = 1 + CLIENT_ORGANIZATION_MAX_LENGTH
        self._test_illegal_values(model,
                                  {'org_id': 'a'*length},
                                  FieldValueTooLongError,
                                  self.value_too_long_pattern)

    @foreach(
        '1',
        'abc',
        'Abc',  # (to be automatically `.lower()`-ed)
        '0123456789abcdef0123456789abcdef0123',   # (36 hex digits)
    )
    @foreach(
        OrgConfigUpdateRequest,
        RegistrationRequest,
    )
    def test_id_hex(self, model, val):
        self._test_proper_values(model, {'id': val})

    @foreach(
        '',
        '-1',
        'gbc',
        '0123456789abcdef0123456789abcdef01234',   # (37 hex digits)
    )
    @foreach(
        OrgConfigUpdateRequest,
        RegistrationRequest,
    )
    def test_illegal_id_hex(self, model, val):
        self._test_illegal_values(model, {'id': val}, FieldValueError)

    @foreach(
        123,
        '123',
        '   123      ',
        4294967295,
        '123.123',
        '65535.65535',
    )
    @foreach(
        InsideFilterASN,
        OrgConfigUpdateRequestASN,
        RegistrationRequestASN,
        InsideFilterASN,
    )
    def test_asn(self, model, val):
        self._test_proper_values(model, {'asn': val})

    @foreach(
        4294967296,
        '65536.65535',
        '65535.65536',
        '65536.65536',
        'abc',
        'ąężź',
    )
    @foreach(
        InsideFilterASN,
        OrgConfigUpdateRequestASN,
        RegistrationRequestASN,
        InsideFilterASN,
    )
    def test_illegal_asn(self, model, val):
        expected_msg_pattern = r'\bnot a valid Autonomous System Number\b'
        self._test_illegal_values(model, {'asn': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(val='pl'),
        param(val='PL'),
        param(val='   En     '),
        param(val='eN'),
        param(val='p1'),
        param(val='P2'),
    )
    @foreach(
        param(model=InsideFilterCC, tested_arg='cc'),
        param(model=CriteriaCC, tested_arg='cc'),
        param(model=Org, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='terms_lang'),
    )
    def test_cc(self, model, tested_arg, val):
        self._test_proper_values(model, {tested_arg: val}, expecting_stripped_string=True)

    @foreach(
        param(val='1P'),
        param(val='a_'),
        param(val='ąę'),
        param(val='żę'),
        param(val='PLL'),
    )
    @foreach(
        param(model=InsideFilterCC, tested_arg='cc'),
        param(model=CriteriaCC, tested_arg='cc'),
        param(model=Org, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='terms_lang'),
    )
    def test_illegal_cc(self, model, tested_arg, val):
        expected_msg_pattern = r'\bnot a valid 2-character country code\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(val='info@example.com'),
        param(val='ex123@example.com'),
        param(val='uPPercase@example.com'),
        param(val='      valiD.V_a-l@s-p-a-m.example.com   '),
        param(val='another-val@email'),
        param(val='123@321.org'),
        param(val='so}me@example'),
        param(val='so{me@example'),
        param(val='so$&?!me@example'),
    )
    @foreach(
        EMailNotificationAddress,
        Entity,
        EntityContactPoint,
        OrgConfigUpdateRequestEMailNotificationAddress,
    )
    def test_email(self, model, val):
        self._test_proper_values(model, {'email': val}, expecting_stripped_string=True)

    @foreach(
        param(val='no-at-sign'),
        param(val='.some@example.com'),
        param(val='some..some@example.com'),
        param(val='some....some@example.com'),
        param(val='some.@example.com'),
        param(val='lo:gin@example.com'),
        param(val='lo   gin@example.com'),
        param(val='@example.com'),
        param(val='some@some@example.com'),
        param(val='some@s_p_a_m.example.com'),
        param(val='123@321.123'),
        param(val='some@domain-with-UPPERcase.example.com'),
    )
    @foreach(
        EMailNotificationAddress,
        Entity,
        EntityContactPoint,
        OrgConfigUpdateRequestEMailNotificationAddress,
    )
    def test_illegal_email(self, model, val):
        expected_msg_pattern = (r'\bnot a valid e-mail address\b')
        self._test_illegal_values(model, {'email': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        '12:01',
        '1:1',
        '23:30',
        '1:12',
        10,
        21,
        datetime.time(13, 14),
        datetime.time(15),
    )
    @foreach(
        EMailNotificationTime,
        OrgConfigUpdateRequestEMailNotificationTime,
    )
    def test_notification_time(self, model, val):
        self._test_proper_values(model, {'notification_time': val})

    @foreach(
        '12',
        '12:',
        ':11',
        '12:03:001',
        'abc',
    )
    @foreach(
        EMailNotificationTime,
        OrgConfigUpdateRequestEMailNotificationTime,
    )
    def test_illegal_notification_time(self, model, val):
        self._test_illegal_values(model, {'notification_time': val}, FieldValueError)

    @foreach(
        11,
        14,
        0,
        23,
    )
    @foreach(
        EMailNotificationTime,
        OrgConfigUpdateRequestEMailNotificationTime,
    )
    def test_int_cleaning_method_notification_time(self, model, val):
        expected_val = datetime.time(val)
        self._test_proper_values(model, {'notification_time': expected_val})

    def test_illegal_type_notification_time(self):
        expected_msg_pattern = r'\bwrong type\b'
        new_time = datetime.datetime(2018, 3, 14, 15, 11)
        self._test_illegal_values(EMailNotificationTime,
                                  {'notification_time': new_time},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        param(
            val='1.2.3.4/0',
            expected_adjusted_val='1.2.3.4/0',
        ),
        param(
            val='    11.22.33.44/10      ',
            expected_adjusted_val='11.22.33.44/10',
        ),
        param(
            val='127.0.0.1/28',
            expected_adjusted_val='127.0.0.1/28',
        ),
        param(
            val='0.0.0.0/0',
            expected_adjusted_val='0.0.0.0/0',
        ),
        param(
            val='11.22.33.44/32',
            expected_adjusted_val='11.22.33.44/32',
        ),
        param(
            val='11.22.33.44',
            expected_adjusted_val='11.22.33.44/32',  # [sic]
        ),
    )
    @foreach(
        InsideFilterIPNetwork,
        OrgConfigUpdateRequestIPNetwork,
        RegistrationRequestIPNetwork,
        CriteriaIPNetwork,
        IgnoredIPNetwork,
        EntityIPNetwork,
    )
    def test_ip_network(self, model, val, expected_adjusted_val):
        obj = model(ip_network=val)
        adjusted_val = obj.ip_network
        self.assertEqual(adjusted_val, expected_adjusted_val)

    @foreach(
        '1122334428',
        '11.22.33.28.',
        '256.22.33.44/28',
        '1000.1000.1000.1000/28',
        '00.1.2.3/28',
        'example.com/28',
        'http://1.2.3.4/28',
        '',
        'abcdef',
    )
    @foreach(
        InsideFilterIPNetwork,
        OrgConfigUpdateRequestIPNetwork,
        RegistrationRequestIPNetwork,
        CriteriaIPNetwork,
        IgnoredIPNetwork,
        EntityIPNetwork,
    )
    def test_illegal_ip_network(self, model, val):
        expected_msg_pattern = r'\bneither a .* CIDR IPv4 network .* nor a single IPv4 address\b'
        self._test_illegal_values(model,
                                  {'ip_network': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        InsideFilterIPNetwork,
        OrgConfigUpdateRequestIPNetwork,
        RegistrationRequestIPNetwork,
        CriteriaIPNetwork,
        IgnoredIPNetwork,
        EntityIPNetwork,
    )
    def test_wrong_type_ip_network(self, model):
        val = ('127.0.0.1', '28')
        expected_msg_pattern = r'\btype of value for a string-type field\b'
        self._test_illegal_values(model,
                                  {'ip_network': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        'http://www.example.com/index.html',
        'any string      ',
        '   abcd     1234    '
        '------- 22222222 +++++',
        'a' * 2048,
    )
    def test_url(self, val):
        self._test_proper_values(InsideFilterURL, {'url': val}, expecting_stripped_string=True)

    # TODO: cover not only "url", but many various fields of many models...
    #       and not only `bytes` but a few more non-`str` types...
    #       (probably related to all fields whose validators make use of
    #       any of the following:
    #       * _adjust_to_unicode_stripped
    #       * _adjust_ascii_only_to_unicode
    #       * _adjust_ascii_only_ldap_safe_to_unicode_stripped
    #       * _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none
    #       * _adjust_to_none_if_empty_or_whitespace
    #       * _adjust_ascii_only_to_unicode_stripped_or_none
    #       * _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none).
    def test_wrong_type_for_string_based_field(self):
        tested_value = b'something'
        expected_msg_pattern = r'\btype of value for a string-type field\b'
        self._test_illegal_values(InsideFilterURL,
                                  {'url': tested_value},
                                  FieldValueError,
                                  expected_msg_pattern)

    def test_too_long_url(self):
        tested_value = 'a' * 2049
        with self.assertRaises(FieldValueTooLongError):
            InsideFilterURL(url=tested_value)

    @foreach(list(CATEGORY_ENUMS) + list(map('  {}  '.format, CATEGORY_ENUMS)))
    def test_category(self, val):
        with patch('n6lib.auth_db.fields.LOGGER') as LOGGER_mock:
            self._test_proper_values(CriteriaCategory,
                                     {'category': val},
                                     expecting_stripped_string=True)
        self.assertEqual(LOGGER_mock.mock_calls, [])

    @foreach(
        'a',
        '-',
        'a-b',
        'obcazki',
        '  a-b  ',
        '  obcazki  ',
    )
    def test_unknown_but_tolerated_category(self, val):
        with patch('n6lib.auth_db.fields.LOGGER') as LOGGER_mock:
            self._test_proper_values(CriteriaCategory,
                                     {'category': val},
                                     expecting_stripped_string=True)
        self.assertEqual(LOGGER_mock.mock_calls, [
            call.warning(CategoryCustomizedField.warning_msg_template, val.strip()),
        ])

    @foreach(
        '',
        ' ',
        'a_b',
        'obcążki',
    )
    def test_illegal_category(self, val):
        self._test_illegal_values(CriteriaCategory,
                                  {'category': val},
                                  FieldValueError,
                                  r'\bnot a valid event category\b')

    @foreach(
        'info@example.com',
        'ex123@example.com',
        '  valid.v_a-l@s-p-a-m.example.com  ',
        'another-val@email',
        '123@321.org',
        'so}me@example',
        'so{me@example',
        'so$&?!me@example',
    )
    def test_user_login(self, val):
        self._test_proper_values(User,
                                 {'login': val},
                                 expecting_stripped_string=True)

    @foreach(
        'info@example.com',
        'ex123@example.com',
        '  valid.v_a-l@s-p-a-m.example.com  ',
        'another-val@email',
        '123@321.org',
    )
    def test_registration_req_email(self, val):
        self._test_proper_values(RegistrationRequest,
                                 {'email': val},
                                 expecting_stripped_string=True)

    @foreach(
        'uPPercase@example.com',
        'info@example.com',
        'ex123@example.com',
        '      valiD.V_a-l@s-p-a-m.example.com   ',
        'another-val@email',
        '123@321.org',
    )
    def test_registration_req_notification_email(self, val):
        self._test_proper_values(RegistrationRequestEMailNotificationAddress,
                                 {'email': val},
                                 expecting_stripped_string=True)

    @foreach(
        'uPPercase@example.com',
        'no-at-sign',
        '.some@example.com',
        'some..some@example.com',
        'some....some@example.com',
        'some.@example.com',
        'lo:gin@example.com',
        'lo   gin@example.com',
        '@example.com',
        'some@some@example.com',
        'some@s_p_a_m.example.com',
        '123@321.123',
        'some@domain-with-UPPERcase.example.com',
    )
    def test_illegal_user_login(self, val):
        expected_msg_pattern = (r'\bnot a valid user login\b|\billegal character')
        self._test_illegal_values(User,
                                  {'login': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        'uPPercase@example.com',
        'so}me@example',
        'so{me@example',
        'so$&?!me@example',
        'no-at-sign',
        '.some@example.com',
        'some..some@example.com',
        'some....some@example.com',
        'some.@example.com',
        'lo:gin@example.com',
        'lo   gin@example.com',
        '@example.com',
        'some@some@example.com',
        'some@s_p_a_m.example.com',
        '123@321.123',
        'some@domain-with-UPPERcase.example.com',
    )
    def test_illegal_registration_req_email(self, val):
        expected_msg_pattern = (r'\bnot a valid user login\b|\billegal character')
        self._test_illegal_values(RegistrationRequest,
                                  {'email': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        'so}me@example',
        'so{me@example',
        'so$&?!me@example',
        'no-at-sign',
        '.some@example.com',
        'some..some@example.com',
        'some....some@example.com',
        'some.@example.com',
        'lo:gin@example.com',
        'lo   gin@example.com',
        '@example.com',
        'some@some@example.com',
        'some@s_p_a_m.example.com',
        '123@321.123',
        'some@domain-with-UPPERcase.example.com',
    )
    def test_illegal_registration_req_notification_email(self, val):
        expected_msg_pattern = (r'\bnot a valid e-mail address\b|\billegal character')
        self._test_illegal_values(RegistrationRequestEMailNotificationAddress,
                                  {'email': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        'abc.def',
        '   a-b-c-1.2-d-e-f   ',
        '123.321',
    )
    def test_source(self, val):
        self._test_proper_values(Source,
                                 {'source_id': val, 'anonymized_source_id': val},
                                 expecting_stripped_string=True)

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
        expected_msg_pattern = r'\bnot a valid source specification\b'
        sample_valid_source = 'abc.def'
        self._test_illegal_values(Source,
                                  {'source_id': val},
                                  FieldValueError,
                                  expected_msg_pattern)
        self._test_illegal_values(Source,
                                  {'source_id': sample_valid_source, 'anonymized_source_id': val},
                                  FieldValueError,
                                  expected_msg_pattern)

    @foreach(
        param(model=Cert, tested_arg='serial_hex'),
        param(model=OrgConfigUpdateRequest, tested_arg='id'),
    )
    @foreach(
        param(val='06f30a5903f4cf0642b5'),
        param(val='abcdef0123456789ffff'),
        param(val='5cc863bfbf1b669e5f05'),
        param(val='B4162A543BE9E50ACE42'),
        param(val='   9aadc6e968ee4a4d5601   '),
    )
    def test_hex_number(self, model, tested_arg, val):
        self._test_proper_values(model, {tested_arg: val}, expecting_stripped_string=True)

    @foreach(
        'e479-09b_23572199b66',
        '19f16e,29fd.8b56294c',
        '6ę515be3556ą8267826c',
        'b215',
    )
    def test_illegal_hex_number(self, val):
        expected_msg_pattern = r'\bnot a valid certificate serial number\b'
        self._test_illegal_values(Cert, {'serial_hex': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(model=User, tested_arg='api_key_id'),
        param(model=WebToken, tested_arg='token_id'),
    )
    @foreach(
        param(val='eb08d960-f5c3-4c1e-af0c-86b8f9229fec'),
        param(val='eb08d960-F5C3-4C1E-AF0C-86B8F9229FEC'),
        param(val='EB08D960-F5C3-4C1E-af0c-86b8f9229fec'),
        param(val='EB08D960-F5C3-4C1E-AF0C-86B8F9229FEC'),
        param(val='   eb08d960-f5c3-4c1e-af0c-86b8f9229fec   '),
    )
    def test_uuid4(self, model, tested_arg, val):
        self._test_proper_values(model, {tested_arg: val}, expecting_stripped_string=True)

    @foreach(
        param(model=User, tested_arg='api_key_id'),
        param(model=WebToken, tested_arg='token_id'),
    )
    @foreach(
        param(val='zb08d960-f5c3-4c1e-af0c-86b8f9229fec'),
        param(val='eb08d960-FF5C3-4C1E-AF0C-86B8F9229FEC'),
        param(val='EB08D960-F5C3-5C1E-af0c-86b8f9229fec'),
        param(val='   eb08d960-f5c3-4c1e-af0c-6b8f9229fec   '),
        param(val='06f30a5903f4cf0642b5'),
        param(val='5cc863bfbf1b669e5f05'),
        param(val='B4162A543BE9E50ACE42'),
        param(val='e479-09b_23572199b66'),
        param(val='b215'),
    )
    def test_illegal_uuid4(self, model, tested_arg, val):
        expected_msg_pattern = r'\bnot a valid UUID4\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(model=User, tested_arg='mfa_key_base'),
        param(model=UserProvisionalMFAConfig, tested_arg='mfa_key_base'),
    )
    @foreach(
        param(val='ąśżź456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'),
        param(val='ąśżź456789ABCDEF0123456789ABCDEF0123456789abcdef0123456789abcdef'),
        param(val='   ąśżź456789abcdef0123456789abcdef0123456789ABCDEF0123456789ABCDEF00000000000   '),
        param(val='   ąśżź456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef00000000000   '),
        param(val='Ż' * 64),
        param(val='ż' * 64),
    )
    def test_no_whitespace_secret(self, model, tested_arg, val):
        self._test_proper_values(model, {tested_arg: val}, expecting_stripped_string=True)

    @foreach(
        param(model=User, tested_arg='mfa_key_base'),
        param(model=UserProvisionalMFAConfig, tested_arg='mfa_key_base'),
    )
    @foreach(
        param(val='   0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde   '),
        param(val='   0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDE   '),
        param(val='Ż' * 63),
        param(val='ż' * 63),
        param(val='EB08D960-F5C3-4C1E-af0c-86b8f9229fec'),
        param(val='   eb08d960-f5c3-4c1e-af0c-86b8f9229fec   '),
        param(val='0123456789ab  cdef0123456789abcdef0123456789abcdef0123456789abcdef'),
        param(val='0123456789AB  CDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF'),
        param(val='b215'),
    )
    def test_illegal_no_whitespace_secret(self, model, tested_arg, val):
        expected_msg_pattern = r'\bnot a valid secret\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(model=Cert, tested_arg='created_on'),
        param(model=Cert, tested_arg='valid_from'),
        param(model=Cert, tested_arg='expires_on'),
        param(model=Cert, tested_arg='revoked_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='modified_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='modified_on'),
        param(model=User, tested_arg='api_key_id_modified_on'),
        param(model=User, tested_arg='mfa_key_base_modified_on'),
        param(model=WebToken, tested_arg='created_on'),
        param(model=UserSpentMFACode, tested_arg='spent_on'),
    )
    @foreach(
        param(
            val=datetime.datetime(1970, 1, 1, 0, 0, 0),
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 0, 0),
        ),
        param(
            val=datetime.datetime(1970, 1, 1, 0, 0, 0, 999999),
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 0, 0),
        ),
        param(
            val='1970-01-01T01:59:59.999999+01:00',
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 59, 59),
        ),
        param(
            val=datetime.datetime(2019, 6, 7, 8, 9, 10, 123456),
            expected_adjusted_val=datetime.datetime(2019, 6, 7, 8, 9, 10),
        ),
        param(
            val='2019-06-07 10:09:10.123456+02:00',
            expected_adjusted_val=datetime.datetime(2019, 6, 7, 8, 9, 10),
        ),
    )
    def test_datetimes(self, model, tested_arg, val, expected_adjusted_val):
        obj = model(**{tested_arg: val})
        adjusted_val = getattr(obj, tested_arg)
        self.assertEqual(adjusted_val, expected_adjusted_val)

    @foreach([
        param(model=RecentWriteOpCommit, tested_arg='made_at'),
    ])
    @foreach(
        param(
            val=datetime.datetime(1970, 1, 1, 0, 0, 0),
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 0, 0),
        ),
        param(
            val=datetime.datetime(1970, 1, 1, 0, 0, 0, 999999),
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 0, 0, 999999),
        ),
        param(
            val='1970-01-01T01:59:59.999999+01:00',
            expected_adjusted_val=datetime.datetime(1970, 1, 1, 0, 59, 59, 999999),
        ),
        param(
            val=datetime.datetime(2019, 6, 7, 8, 9, 10, 123456),
            expected_adjusted_val=datetime.datetime(2019, 6, 7, 8, 9, 10, 123456),
        ),
        param(
            val='2019-06-07 10:09:10.123456+02:00',
            expected_adjusted_val=datetime.datetime(2019, 6, 7, 8, 9, 10, 123456),
        ),
    )
    def test_datetimes_keeping_sec_fractions(self, model, tested_arg, val, expected_adjusted_val):
        obj = model(**{tested_arg: val})
        adjusted_val = getattr(obj, tested_arg)
        self.assertEqual(adjusted_val, expected_adjusted_val)

    @foreach(
        param(model=Cert, tested_arg='created_on'),
        param(model=Cert, tested_arg='valid_from'),
        param(model=Cert, tested_arg='expires_on'),
        param(model=Cert, tested_arg='revoked_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='modified_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='modified_on'),
        param(model=User, tested_arg='api_key_id_modified_on'),
        param(model=User, tested_arg='mfa_key_base_modified_on'),
        param(model=WebToken, tested_arg='created_on'),
        param(model=UserSpentMFACode, tested_arg='spent_on'),
        param(model=RecentWriteOpCommit, tested_arg='made_at'),
    )
    @foreach(
        param(val=datetime.datetime(1810, 1, 1, 0, 0, 0)),
        param(val=datetime.datetime(1969, 12, 31, 23, 59, 59)),
        param(val=datetime.datetime(1969, 12, 31, 23, 59, 59, 999999)),
        param(val='1970-01-01T01:59:59.999999+02:00'),
    )
    def test_datetimes_too_old(self, model, tested_arg, val):
        expected_msg_pattern = r'\bdate\+time\b.*\bolder than the required minimum\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(model=Cert, tested_arg='created_on'),
        param(model=Cert, tested_arg='valid_from'),
        param(model=Cert, tested_arg='expires_on'),
        param(model=Cert, tested_arg='revoked_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='modified_on'),
        param(model=OrgConfigUpdateRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='submitted_on'),
        param(model=RegistrationRequest, tested_arg='modified_on'),
        param(model=User, tested_arg='api_key_id_modified_on'),
        param(model=User, tested_arg='mfa_key_base_modified_on'),
        param(model=WebToken, tested_arg='created_on'),
        param(model=UserSpentMFACode, tested_arg='spent_on'),
        param(model=RecentWriteOpCommit, tested_arg='made_at'),
    )
    @foreach(
        param(val='1970-01-01TT01:59:59.999999+01:00'),
        param(val='1970-01-01'),
        param(val='01:59:59.999999+01:00'),
        param(val='spam'),
        param(val=''),
    )
    def test_wrongly_formatted_datetimes(self, model, tested_arg, val):
        expected_msg_pattern = r'\bis not a valid date \+ time\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        'n6-service-ca',
        'n6-client-ca',
        'abcc#cert',
        'cert@ca.com',
        '  abcc#cert  ',
        '  cert@ca.com  ',
    )
    def test_ca_label_lowercase(self, val):
        self._test_proper_values(CACert, {'ca_label': val}, expecting_stripped_string=True)

    @foreach(
        'n6-service-CA',
        'N6Ca',
        'abcc#Cert',
        'cert@cA.com',
        'certcA',
    )
    def test_non_lowercase_ca_label(self, val):
        expected_msg_pattern = r'\bcontains illegal upper-case characters\b'
        self._test_illegal_values(CACert, {'ca_label': val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(val='ąęźćżłów').label('uni'),
        param(val='other\udcddval').label('uni-surro'),
    )
    @foreach(
        param(model=Org, tested_arg='org_id'),
        param(model=CriteriaName, tested_arg='name'),
        param(model=OrgGroup, tested_arg='org_group_id'),
        param(model=User, tested_arg='login'),
        param(model=Component, tested_arg='login'),
        param(model=Entity, tested_arg='email'),
        param(model=EntityContactPoint, tested_arg='email'),
        param(model=EMailNotificationAddress, tested_arg='email'),
        param(model=OrgConfigUpdateRequestEMailNotificationAddress, tested_arg='email'),
        param(model=RegistrationRequest, tested_arg='email'),
        param(model=RegistrationRequestEMailNotificationAddress, tested_arg='email'),
        param(model=CriteriaContainer, tested_arg='label'),
        param(model=Subsource, tested_arg='label'),
        param(model=SubsourceGroup, tested_arg='label'),
        param(model=IgnoreList, tested_arg='label'),
        param(model=SystemGroup, tested_arg='name'),
        param(model=CACert, tested_arg='ca_label'),
    )
    def test_ascii_only_fields_with_illegal_chars(self, model, tested_arg, val):
        expected_msg_pattern = r'\bcontains non-ASCII characters\b'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        (Org, 'org_id'),
        (RegistrationRequest, 'org_id'),
        (OrgGroup, 'org_group_id'),
        (Component, 'login'),
        (User, 'login'),
        (RegistrationRequest, 'email'),
        (CriteriaContainer, 'label'),
        (Subsource, 'label'),
        (SubsourceGroup, 'label'),
        (SystemGroup, 'name'),
        (CACert, 'ca_label'),
    )
    def test_setting_ldap_not_safe_chars(self, model, tested_arg):
        val = 'exa+mple'
        expected_msg_pattern = r'\billegal character'
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError, expected_msg_pattern)

    @foreach(
        param(model=CriteriaName, tested_arg='name'),
        param(model=Subsource, tested_arg='label'),
        param(model=SubsourceGroup, tested_arg='label'),
        param(model=CriteriaContainer, tested_arg='label'),
        param(model=IgnoreList, tested_arg='label'),
        param(model=SystemGroup, tested_arg='name'),
        param(model=Cert, tested_arg='creator_details'),
        param(model=Cert, tested_arg='revocation_comment'),
        param(model=CACert, tested_arg='ca_label'),
        param(model=OrgGroup, tested_arg='org_group_id'),
    )
    @foreach(
        param(val=''),
        param(val=' '),
        param(val='  \t  \n\n  \r\n  \t  \n  '),
    )
    def test_string_based_fields_empty_or_whitespace_only_to_null(
            self, model, tested_arg, val):
        # (note that some of these fields are NOT NULLABLE so "in the
        # real life" their NULL values will **not** be accepted on the
        # database level)
        obj = model(**{tested_arg: val})
        self.assertIsNone(getattr(obj, tested_arg))

    @foreach(
        param(model=Cert, tested_arg='certificate'),
        param(model=Cert, tested_arg='csr'),
        param(model=CACert, tested_arg='certificate'),
        param(model=CACert, tested_arg='ssl_config'),
        param(model=RegistrationRequest, tested_arg='csr'),
    )
    def test_string_based_fields_empty_to_null(
            self, model, tested_arg):
        # (note that same of these fields are NOT NULLABLE so "in the
        # real life" their NULL values will **not** be accepted on the
        # database level)
        obj = model(**{tested_arg: ''})
        self.assertIsNone(getattr(obj, tested_arg))

    @foreach(
        param(model=User, tested_arg='login'),
        param(model=Component, tested_arg='login'),
        param(model=Cert, tested_arg='serial_hex'),
        param(model=User, tested_arg='api_key_id'),
        param(model=User, tested_arg='mfa_key_base'),
        param(model=UserProvisionalMFAConfig, tested_arg='mfa_key_base'),
        param(model=WebToken, tested_arg='token_id'),
        param(model=Org, tested_arg='org_id'),
        param(model=RegistrationRequest, tested_arg='org_id'),
        param(model=Org, tested_arg='email_notification_language'),
        param(model=OrgConfigUpdateRequest, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='email_notification_language'),
        param(model=RegistrationRequest, tested_arg='terms_lang'),
        param(model=EMailNotificationAddress, tested_arg='email'),
        param(model=OrgConfigUpdateRequestEMailNotificationAddress, tested_arg='email'),
        param(model=RegistrationRequest, tested_arg='email'),
        param(model=RegistrationRequestEMailNotificationAddress, tested_arg='email'),
        param(model=Entity, tested_arg='email'),
        param(model=EntityContactPoint, tested_arg='email'),
        param(model=EntityContactPointPhone, tested_arg='phone_number'),
        param(model=DependantEntity, tested_arg='name'),
        param(model=Entity, tested_arg='full_name'),
        param(model=EntityContactPoint, tested_arg='external_entity_name'),
        param(model=EntitySector, tested_arg='label'),
        param(model=EntityExtraIdType, tested_arg='label'),
        param(model=EntityExtraId, tested_arg='value'),
        param(model=InsideFilterASN, tested_arg='asn'),
        param(model=OrgConfigUpdateRequestASN, tested_arg='asn'),
        param(model=RegistrationRequestASN, tested_arg='asn'),
        param(model=CriteriaASN, tested_arg='asn'),
        param(model=InsideFilterCC, tested_arg='cc'),
        param(model=CriteriaCC, tested_arg='cc'),
        param(model=InsideFilterFQDN, tested_arg='fqdn'),
        param(model=OrgConfigUpdateRequestFQDN, tested_arg='fqdn'),
        param(model=RegistrationRequestFQDN, tested_arg='fqdn'),
        param(model=InsideFilterIPNetwork, tested_arg='ip_network'),
        param(model=OrgConfigUpdateRequestIPNetwork, tested_arg='ip_network'),
        param(model=RegistrationRequestIPNetwork, tested_arg='ip_network'),
        param(model=CriteriaIPNetwork, tested_arg='ip_network'),
        param(model=IgnoredIPNetwork, tested_arg='ip_network'),
        param(model=EntityIPNetwork, tested_arg='ip_network'),
        param(model=InsideFilterURL, tested_arg='url'),
        param(model=Source, tested_arg='source_id'),
        param(model=Source, tested_arg='anonymized_source_id'),
    )
    @foreach(
        param(val=''),
        param(val=' '),
        param(val='  \t  \n\n  \r\n  \t  \n  '),
    )
    def test_string_based_fields_empty_or_whitespace_only_disallowed_by_validator(
            self, model, tested_arg, val):
        self._test_illegal_values(model, {tested_arg: val}, FieldValueError)

    def _test_proper_values(self, model, kwargs, expecting_stripped_string=False):
        obj = model(**kwargs)
        self.assertTrue(obj)
        if expecting_stripped_string:
            for name in kwargs:
                actual_val = getattr(obj, name)
                self.assertIsInstance(actual_val, str)
                self.assertEqual(actual_val, actual_val.strip())

    def _test_illegal_values(self, model, kwargs, expected_exc, expected_msg_pattern=None):
        with self.assertRaises(expected_exc) as context:
            model(**kwargs)
        if expected_msg_pattern is not None:
            self.assertRegex(context.exception.public_message, expected_msg_pattern)

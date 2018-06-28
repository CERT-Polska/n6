# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime

from n6lib.auth_db.fields import (
    HexField,
    OrgIdField,
    URLSimpleField,
    UserLoginField,
)
from n6lib.data_spec import (
    N6DataSpec,
    FieldValueError,
)
from n6lib.record_dict import (
    chained,
    make_adjuster_applying_callable,
    make_adjuster_using_data_spec,
)


invalid_field_template_msg = 'Value: {value!r} raised {exc.__class__.__name__}: {exc}.'
illegal_characters_for_ldap = ['\\', ',', '+', '"', '<', '>', ';', '=', '\x00']


def _check_for_illegal_chars(chars_list, value):
    for char in chars_list:
        if char in value:
            return char
    return False


def to_lowercase(val):
    return val.lower()


def ascii_only_to_unicode_stripped(val):
    if isinstance(val, unicode):
        try:
            val.encode('ascii', 'strict')  # just to check against encoding errors
        except UnicodeEncodeError as exc:
            raise FieldValueError(
                public_message=invalid_field_template_msg.format(value=val, exc=exc))
    else:
        assert isinstance(val, str)
        try:
            val = val.decode('ascii', 'strict')
        except UnicodeDecodeError as exc:
            raise FieldValueError(
                public_message=invalid_field_template_msg.format(value=val, exc=exc))
    assert isinstance(val, unicode)
    return val.strip()


def to_stripped(val):
    if not isinstance(val, basestring):
        raise FieldValueError(public_message='Illegal type of value for a string-type field.')
    if isinstance(val, str):
        try:
            val = val.decode('utf-8', 'strict')
        except UnicodeDecodeError as exc:
            raise FieldValueError(
                public_message=invalid_field_template_msg.format(value=val, exc=exc))
    assert isinstance(val, unicode)
    return val.strip()


def make_val_ldap_safe(val):
    val = val.strip()
    if val.startswith('#'):
        raise FieldValueError(
            public_message='Value: {value!r} cannot start with "#" symbol.'.format(value=val))
    illegal_char = _check_for_illegal_chars(illegal_characters_for_ldap, val)
    if illegal_char is not False:
        raise FieldValueError(
            public_message='Value: {value!r} contains illegal character: {char!r}.'.format(
                value=val, char=illegal_char))
    return val


def validate_time_hour_minute_only(val):
    hour_minute_format = '%H:%M'
    try:
        datetime.datetime.strptime(val, hour_minute_format)
    except (TypeError, ValueError) as exc:
        raise FieldValueError(public_message=invalid_field_template_msg.format(value=val, exc=exc))
    return val


class AuthDBDataSpec(N6DataSpec):

    org_id = OrgIdField()
    url_regexed = URLSimpleField()
    user_login = UserLoginField()
    hex_number = HexField()


class AuthDBValidator(object):

    adjuster_prefix = 'adjust_'
    data_spec = AuthDBDataSpec()

    # base adjuster methods
    adjust_to_lowercase = make_adjuster_applying_callable(to_lowercase)
    adjust_ascii_only_to_unicode_stripped = make_adjuster_applying_callable(
        ascii_only_to_unicode_stripped)
    adjust_stripped = make_adjuster_applying_callable(to_stripped)
    adjust_ldap_safe = make_adjuster_applying_callable(make_val_ldap_safe)

    # adjuster methods used for specific columns
    adjust_org_id = chained(
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe,
        make_adjuster_using_data_spec('org_id'))
    adjust_asn = make_adjuster_using_data_spec('asn')
    adjust_cc = chained(
        adjust_stripped,
        make_adjuster_using_data_spec('cc'))
    adjust_email_notifications_language = chained(
        adjust_stripped,
        make_adjuster_using_data_spec('cc'))
    adjust_email = chained(
        adjust_ascii_only_to_unicode_stripped,
        make_adjuster_using_data_spec('email'))
    adjust_notification_time = make_adjuster_applying_callable(validate_time_hour_minute_only)
    adjust_fqdn = chained(
        adjust_stripped,
        make_adjuster_using_data_spec('fqdn'))
    adjust_ip_network = chained(
        adjust_stripped,
        make_adjuster_using_data_spec('ip_network'))
    adjust_url = chained(
        adjust_stripped,
        make_adjuster_using_data_spec('url_regexed'))
    adjust_criteria_name_name = adjust_ascii_only_to_unicode_stripped
    adjust_criteria_category_category = adjust_ascii_only_to_unicode_stripped
    adjust_org_group_id = chained(
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe)
    adjust_user_login = chained(
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe,
        make_adjuster_using_data_spec('user_login'))
    adjust_component_login = chained(
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe)
    adjust_source_id = chained(
        adjust_ldap_safe,
        make_adjuster_using_data_spec('source'))
    adjust_anonymized_source_id = adjust_source_id
    adjust_label = chained(
        adjust_ldap_safe,
        adjust_ascii_only_to_unicode_stripped,
    )
    adjust_system_group_name = chained(
        adjust_ldap_safe,
        adjust_ascii_only_to_unicode_stripped,
    )
    adjust_serial_hex = make_adjuster_using_data_spec('hex_number')
    adjust_revocation_comment = adjust_stripped
    adjust_request_case_id = adjust_serial_hex
    adjust_status = adjust_stripped
    adjust_ca_label = chained(
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe,
    )

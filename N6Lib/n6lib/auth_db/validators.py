# Copyright (c) 2013-2019 NASK. All rights reserved.

import json
import string

from n6lib.auth_db import (
    ILLEGAL_CHARACTERS_FOR_LDAP,
    INVALID_FIELD_TEMPLATE_MSG,
)
from n6lib.auth_db.fields import (
    ExtraIDField,
    OrgIdField,
    TimeHourMinuteField,
    URLSimpleField,
    UserLoginField,
)
from n6lib.const import CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM
from n6lib.data_spec import (
    N6DataSpec,
    FieldValueError,
)
from n6lib.record_dict import (
    chained,
    make_adjuster_applying_callable,
    make_adjuster_using_data_spec,
)


def _check_for_illegal_chars(chars_list, value):
    for char in chars_list:
        if char in value:
            return char
    return False


def to_lowercase(val):
    return val.lower()


def check_if_lowercase(val):
    if not val.islower():
        raise FieldValueError(public_message="CA label {!r} has to be lowercase.".format(val))
    return val


def ascii_only_to_unicode_stripped(val):
    if isinstance(val, unicode):
        try:
            val.encode('ascii', 'strict')  # just to check against encoding errors
        except UnicodeEncodeError as exc:
            raise FieldValueError(
                public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=val, exc=exc))
    else:
        assert isinstance(val, str)
        try:
            val = val.decode('ascii', 'strict')
        except UnicodeDecodeError as exc:
            raise FieldValueError(
                public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=val, exc=exc))
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
                public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=val, exc=exc))
    assert isinstance(val, unicode)
    return val.strip()


def make_val_ldap_safe(val):
    val = val.strip()
    if val.startswith('#'):
        raise FieldValueError(
            public_message='Value: {value!r} cannot start with "#" symbol.'.format(value=val))
    illegal_char = _check_for_illegal_chars(ILLEGAL_CHARACTERS_FOR_LDAP, val)
    if illegal_char is not False:
        raise FieldValueError(
            public_message='Value: {value!r} contains illegal character: {char!r}.'.format(
                value=val, char=illegal_char))
    return val


def make_json_serializable(val):
    if isinstance(val, basestring):
        try:
            json.loads(val)
        except ValueError:
            raise FieldValueError(public_message="Cannot decode value: {!r} "
                                                 "as JSON object.".format(val))
        else:
            return val
    else:
        try:
            return json.dumps(val)
        except (TypeError, ValueError):
            raise FieldValueError(public_message="Cannot encode value: {!r} "
                                                 "as JSON object.".format(val))


# the function may be used in the future, after it is fixed
# def make_json_key_to_bool(val):
#     def is_json_boolean(v):
#         if v.lower() in ('true', 'false'):
#             return True
#         return False
#     if not val:
#         return val
#     decoded = json.loads(val)
#     try:
#         for key, val in decoded.iteritems():
#             if not is_json_boolean(val):
#                 raise FieldValueError(public_message="Values of JSON object's ({!r} keys "
#                                                      "should be of boolean only.".format(val))
#     except AttributeError:
#         raise FieldValueError(public_message="A JSON encoded value: {!r} has to "
#                                              "decode to a simple, not nested dict.".format(val))
#     return val


_HEXDIGITS_LOWERCASE = set(string.hexdigits.lower())


def is_cert_serial_number_valid(serial_number):
    return (_HEXDIGITS_LOWERCASE.issuperset(serial_number) and
            len(serial_number) == CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM)


def validate_cert_serial_number(val):
    if not is_cert_serial_number_valid(val):
        raise FieldValueError(public_message="Value {!r} is not a valid "
                                             "certificate serial number".format(val))
    return val


class AuthDBDataSpec(N6DataSpec):

    extra_id = ExtraIDField()
    org_id = OrgIdField()
    time_simple = TimeHourMinuteField()
    url_regexed = URLSimpleField()
    user_login = UserLoginField()


class AuthDBValidator(object):

    adjuster_prefix = 'adjust_'
    data_spec = AuthDBDataSpec()

    # base adjuster methods
    adjust_to_lowercase = make_adjuster_applying_callable(to_lowercase)
    adjust_lowercase_only = make_adjuster_applying_callable(check_if_lowercase)
    adjust_ascii_only_to_unicode_stripped = make_adjuster_applying_callable(
        ascii_only_to_unicode_stripped)
    adjust_stripped = make_adjuster_applying_callable(to_stripped)
    adjust_ldap_safe = make_adjuster_applying_callable(make_val_ldap_safe)
    adjust_json_serializable = make_adjuster_applying_callable(make_json_serializable)
    # adjust_json_bool_vals = make_adjuster_applying_callable(make_json_key_to_bool)
    adjust_valid_cert_serial_number = make_adjuster_applying_callable(validate_cert_serial_number)

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
    adjust_request_parameters = chained(
        adjust_json_serializable,
        adjust_ascii_only_to_unicode_stripped,
        # adjust_json_bool_vals,
    )
    adjust_inside_request_parameters = adjust_request_parameters
    adjust_search_request_parameters = adjust_request_parameters
    adjust_threats_request_parameters = adjust_request_parameters
    adjust_email = chained(
        adjust_ascii_only_to_unicode_stripped,
        make_adjuster_using_data_spec('email'))
    adjust_notification_time = make_adjuster_using_data_spec('time_simple')
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
    adjust_extra_id_value = make_adjuster_using_data_spec('extra_id')
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
    adjust_serial_hex = chained(
        adjust_to_lowercase,
        adjust_valid_cert_serial_number,
    )
    adjust_creator_details = adjust_json_serializable
    adjust_revocation_comment = adjust_stripped
    adjust_ca_label = chained(
        adjust_lowercase_only,
        adjust_ascii_only_to_unicode_stripped,
        adjust_ldap_safe,
    )

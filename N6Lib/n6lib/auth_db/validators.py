# Copyright (c) 2018-2025 NASK. All rights reserved.

import json
import string

from n6lib.auth_db import MAX_LEN_OF_CERT_SERIAL_HEX
from n6lib.auth_db.fields import (
    CategoryCustomizedField,
    ComponentLoginField,
    DateTimeCustomizedField,
    DomainNameCustomizedField,
    EmailCustomizedField,
    EntityNameField,
    IdHexField,
    OfficialOrContactTokenField,
    OrgIdField,
    RegistrationRequestAnyEmailField,
    RegistrationRequestEmailBeingCandidateLoginField,
    NoWhitespaceSecretField,
    TimeHourMinuteField,
    URLSimpleField,
    HTTPAbsoluteURLField,
    UserLoginField,
    UUID4SecretField,
    UUID4SimpleField,
)
from n6lib.common_helpers import ascii_str
from n6lib.data_spec import FieldValueError
from n6lib.data_spec.fields import (
    ASNField,
    IPv4NetField,
    CCField,
    SourceField,
)
from n6lib.record_dict import (
    applied_for_nonfalse,
    chained,
    make_adjuster_applying_callable,
    make_adjuster_using_data_spec,
)
from n6sdk.data_spec import BaseDataSpec



#
# Private stuff
#

_HEXDIGITS_LOWERCASE = frozenset(string.hexdigits.lower())


def _verified_as_str(val):
    if not isinstance(val, str):
        raise FieldValueError(public_message='Illegal type of value for a string-type field.')
    return val


def _verified_as_ascii_only_str(val):
    val = _verified_as_str(val)
    try:
        # ensure it contains only pure-ASCII characters
        val.encode('ascii', 'strict')
    except UnicodeEncodeError:
        raise FieldValueError(
            public_message='Value {value!a} contains non-ASCII characters.'.format(value=val))
    return val


def _ascii_only_ldap_safe_str_strip(val):
    # XXX: forbidding "LDAP-unsafe" chars is needed only temporarily (until LDAP stuff is dropped)
    val = _verified_as_ascii_only_str(val)
    val = val.strip()
    if val.startswith('#'):
        raise FieldValueError(
            public_message='Value {value!a} starts with illegal "#" prefix.'.format(value=val))
    illegal_characters = LDAP_UNSAFE_CHARACTERS.intersection(val)
    if illegal_characters:
        raise FieldValueError(
            public_message='Value {value!a} contains illegal character(s): {chars}.'.format(
                value=val,
                chars=', '.join(sorted("'{}'".format(ascii_str(ch))
                                       for ch in illegal_characters))))
    return val


def _to_none_if_empty_or_whitespace(val):
    val = _verified_as_str(val)
    if not val.strip():
        return None
    return val


def _to_json_or_none(val):
    if val is None:
        return None
    elif isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            json.loads(val)
        except ValueError:
            raise FieldValueError(public_message="Cannot decode value: {!a} "
                                                 "as JSON object.".format(val))
        else:
            return val
    else:
        try:
            return json.dumps(val)
        except (TypeError, ValueError):
            raise FieldValueError(public_message="Cannot encode value {!a} "
                                                 "as JSON object.".format(val))


def _verified_as_valid_cert_serial_number(val):
    if not is_cert_serial_number_valid(val):
        raise FieldValueError(public_message="Value {!a} is not a valid "
                                             "certificate serial number".format(val))
    return val


def _verified_as_ca_label_containing_no_uppercase(ca_label):
    if ca_label != ca_label.lower():
        raise FieldValueError(public_message="CA label {!a} contains illegal "
                                             "upper-case characters.".format(ca_label))
    return ca_label


_adjust_to_none_if_empty_or_whitespace = (
    make_adjuster_applying_callable(_to_none_if_empty_or_whitespace))


_adjust_to_unicode_stripped = chained(
    make_adjuster_applying_callable(_verified_as_str),
    make_adjuster_applying_callable(str.strip))


_adjust_ascii_only_to_unicode = (
    make_adjuster_applying_callable(_verified_as_ascii_only_str))


_adjust_ascii_only_to_unicode_stripped_or_none = chained(
    _adjust_ascii_only_to_unicode,
    make_adjuster_applying_callable(str.strip),
    _adjust_to_none_if_empty_or_whitespace)


_adjust_ascii_only_ldap_safe_to_unicode_stripped = (
    make_adjuster_applying_callable(_ascii_only_ldap_safe_str_strip))


_adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none = chained(
    make_adjuster_applying_callable(_ascii_only_ldap_safe_str_strip),
    _adjust_to_none_if_empty_or_whitespace)


_adjust_to_json_or_none = (
    make_adjuster_applying_callable(_to_json_or_none))


_adjust_country_code = chained(
    _adjust_to_unicode_stripped,
    make_adjuster_using_data_spec('cc'))


_adjust_hexadecimal_id = chained(
    _adjust_to_unicode_stripped,
    make_adjuster_applying_callable(str.lower),
    make_adjuster_using_data_spec('id_hex'))


_adjust_source_id = chained(
    _adjust_ascii_only_ldap_safe_to_unicode_stripped,
    make_adjuster_using_data_spec('source'))


_adjust_time = (
    make_adjuster_using_data_spec('time'))

_adjust_time_keeping_microseconds = (
    make_adjuster_using_data_spec('time_keeping_microseconds'))


class _AuthDBValidatorsDataSpec(BaseDataSpec):

    org_id = OrgIdField()
    org_uuid = UUID4SimpleField()

    user_login = UserLoginField()
    component_login = ComponentLoginField()

    uuid4 = UUID4SecretField()
    mfa_key_base = NoWhitespaceSecretField()

    asn = ASNField()
    cc = CCField()
    category = CategoryCustomizedField()
    email = EmailCustomizedField()
    fqdn = DomainNameCustomizedField()
    id_hex = IdHexField()
    ip_network = IPv4NetField(accept_bare_ip=True)  # XXX: add arg `trim_host_bits=True` when implemented? (but first see #8949...)
    phone_number = OfficialOrContactTokenField(
        error_msg_template='"{}" is not a valid phone number')
    source = SourceField()
    time = DateTimeCustomizedField()
    time_keeping_microseconds = DateTimeCustomizedField(keep_sec_fraction=True)
    time_hour_minute = TimeHourMinuteField()
    url = URLSimpleField()
    http_absolute_url = HTTPAbsoluteURLField()

    registration_request_email_being_candidate_login = (
        RegistrationRequestEmailBeingCandidateLoginField())
    registration_request_notification_email = RegistrationRequestAnyEmailField()

    entity_name = EntityNameField()

    entity_sector_label = OfficialOrContactTokenField(
        error_msg_template='"{}" is not a valid entity sector label')
    entity_extra_id_type_label = OfficialOrContactTokenField(
        error_msg_template='"{}" is not a valid extra ID type label')
    entity_extra_id = OfficialOrContactTokenField(
        error_msg_template='"{}" is not a valid extra ID')


#
# Public stuff
#

LDAP_UNSAFE_CHARACTERS = frozenset('\\,+"<>;=\x00')


def is_cert_serial_number_valid(serial_number: str) -> bool:
    return (_HEXDIGITS_LOWERCASE.issuperset(serial_number) and
            len(serial_number) == MAX_LEN_OF_CERT_SERIAL_HEX)


class AuthDBValidators(object):

    VALIDATOR_METHOD_PREFIX = 'validator_for__'

    data_spec = _AuthDBValidatorsDataSpec()

    # The following methods are used to validate values for specific
    # Auth DB columns, identified by names that are based on one of the
    # following two patterns:
    #
    # (1) *qualified*: `validator_for__<table name>__<column name>`.
    # (2) *unqualified* (aka *generic*): `validator_for__<column name>`,
    #
    # To find the validator appropriate for a particular column in a
    # particular table, the machinery of AuthDBCustomDeclarativeMeta
    # first tries to find the validator method by the *qualified* name,
    # and then, if nothing was found, by the *unqualified* name.

    # (1) *qualified* validator methods:

    validator_for__email_notification_time__notification_time = (
        make_adjuster_using_data_spec('time_hour_minute'))
    validator_for__org_config_update_request_email_notification_time__notification_time = (
        make_adjuster_using_data_spec('time_hour_minute'))

    validator_for__criteria_name__name = _adjust_ascii_only_to_unicode_stripped_or_none
    validator_for__criteria_category__category = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('category'))

    validator_for__registration_request__id = _adjust_hexadecimal_id
    validator_for__registration_request__submitted_on = _adjust_time
    validator_for__registration_request__modified_on = _adjust_time
    validator_for__registration_request__email = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('registration_request_email_being_candidate_login'))
    validator_for__registration_request__terms_lang = _adjust_country_code

    validator_for__registration_request_email_notification_address__email = chained(
        _adjust_ascii_only_to_unicode,
        make_adjuster_applying_callable(str.strip),
        make_adjuster_using_data_spec('registration_request_notification_email'))

    validator_for__org_config_update_request__id = _adjust_hexadecimal_id
    validator_for__org_config_update_request__submitted_on = _adjust_time
    validator_for__org_config_update_request__modified_on = _adjust_time

    validator_for__user__login = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('user_login'))
    validator_for__component__login = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('component_login'))

    validator_for__org_config_update_request_user_addition_or_activation_request__user_login = chained(  # noqa
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('user_login'))
    validator_for__org_config_update_request_user_deactivation_request__user_login = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('user_login'))

    validator_for__user__api_key_id = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('uuid4'))
    validator_for__user__api_key_id_modified_on = _adjust_time

    validator_for__web_token__token_id = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('uuid4'))
    validator_for__web_token__created_on = _adjust_time

    validator_for__user_spent_mfa_code__spent_on = _adjust_time

    validator_for__subsource__label = (
        _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none)
    validator_for__subsource_group__label = (
        _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none)
    validator_for__criteria_container__label = (
        _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none)
    validator_for__system_group__name = (
        _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none)

    validator_for__cert__serial_hex = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_applying_callable(str.lower),
        make_adjuster_applying_callable(_verified_as_valid_cert_serial_number))
    validator_for__cert__creator_details = _adjust_to_json_or_none
    validator_for__cert__created_on = _adjust_time
    validator_for__cert__valid_from = _adjust_time
    validator_for__cert__expires_on = _adjust_time
    validator_for__cert__revoked_on = _adjust_time
    validator_for__cert__revocation_comment = chained(
        _adjust_to_unicode_stripped,
        _adjust_to_none_if_empty_or_whitespace)

    validator_for__ca_cert__ca_label = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_applying_callable(_verified_as_ca_label_containing_no_uppercase),
        _adjust_to_none_if_empty_or_whitespace)

    validator_for__ignore_list__label = (
        _adjust_ascii_only_to_unicode_stripped_or_none)

    validator_for__entity__full_name = (
        make_adjuster_using_data_spec('entity_name'))
    validator_for__entity__alert_email = chained(
        _adjust_ascii_only_to_unicode,
        make_adjuster_applying_callable(str.strip),
        make_adjuster_using_data_spec('email'))

    validator_for__entity_contact_point__external_entity_name = (
        make_adjuster_using_data_spec('entity_name'))
    validator_for__dependant_entity__name = (
        make_adjuster_using_data_spec('entity_name'))

    validator_for__entity_sector__label = (
        make_adjuster_using_data_spec('entity_sector_label'))
    validator_for__entity_extra_id_type__label = (
        make_adjuster_using_data_spec('entity_extra_id_type_label'))
    validator_for__entity_extra_id__value = (
        make_adjuster_using_data_spec('entity_extra_id'))
    
    validator_for__agreement__label = _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none
    validator_for__agreement__en = chained(
        _adjust_to_unicode_stripped,
        _adjust_to_none_if_empty_or_whitespace)
    validator_for__agreement__pl = chained(
        _adjust_to_unicode_stripped,
        _adjust_to_none_if_empty_or_whitespace)
    validator_for__agreement__url_en = chained(
        _adjust_to_unicode_stripped,
        applied_for_nonfalse(
            make_adjuster_using_data_spec('http_absolute_url')),
        _adjust_to_none_if_empty_or_whitespace)

    validator_for__agreement__url_pl = chained(
        _adjust_to_unicode_stripped,
        applied_for_nonfalse(
            make_adjuster_using_data_spec('http_absolute_url')),
        _adjust_to_none_if_empty_or_whitespace)


    validator_for__recent_write_op_commit__made_at = _adjust_time_keeping_microseconds

    # (2) *unqualified* (*generic*) validator methods:

    validator_for__org_id = chained(
        _adjust_ascii_only_ldap_safe_to_unicode_stripped,
        make_adjuster_using_data_spec('org_id'))
    validator_for__org_group_id = _adjust_ascii_only_ldap_safe_to_unicode_stripped_or_none

    validator_for__org_uuid = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('org_uuid'))

    validator_for__mfa_key_base = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('mfa_key_base'))
    validator_for__mfa_key_base_modified_on = _adjust_time

    validator_for__email_notification_language = _adjust_country_code
    validator_for__email = chained(
        _adjust_ascii_only_to_unicode,
        make_adjuster_applying_callable(str.strip),
        make_adjuster_using_data_spec('email'))
    validator_for__phone_number = (
        make_adjuster_using_data_spec('phone_number'))

    validator_for__asn = chained(
        make_adjuster_applying_callable(ascii_str),
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('asn'))
    validator_for__cc = _adjust_country_code
    validator_for__fqdn = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('fqdn'))
    validator_for__ip_network = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('ip_network'))
    validator_for__url = chained(
        _adjust_to_unicode_stripped,
        make_adjuster_using_data_spec('url'))

    validator_for__source_id = _adjust_source_id
    validator_for__anonymized_source_id = _adjust_source_id

    validator_for__certificate = chained(
        _adjust_ascii_only_to_unicode,
        _adjust_to_none_if_empty_or_whitespace)
    validator_for__csr = chained(
        _adjust_ascii_only_to_unicode,
        _adjust_to_none_if_empty_or_whitespace)
    validator_for__ssl_config = chained(
        _adjust_ascii_only_to_unicode,
        _adjust_to_none_if_empty_or_whitespace)

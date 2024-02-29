# Copyright (c) 2018-2022 NASK. All rights reserved.

import datetime
import re
import string

from n6lib.auth_db import (
    INVALID_FIELD_TEMPLATE_MSG,
    MAX_LEN_OF_DOMAIN_NAME,
    MAX_LEN_OF_EMAIL,
    MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
    MAX_LEN_OF_ID_HEX,
    MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN,
    MAX_LEN_OF_ORG_ID,
    MAX_LEN_OF_URL,
    MAX_LEN_OF_UUID4,
)
from n6lib.common_helpers import (
    EMAIL_OVERRESTRICTED_SIMPLE_REGEX,
    ascii_str,
)
from n6lib.const import CATEGORY_ENUMS
from n6lib.data_spec import FieldValueError
from n6lib.data_spec.fields import (
    DateTimeField,
    DomainNameField,
    EmailSimplifiedField,
    Field,
    IPv4NetField,
    UnicodeLimitedField,
    UnicodeRegexField,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class CategoryCustomizedField(UnicodeLimitedField, UnicodeRegexField):

    max_length = MAX_LEN_OF_GENERIC_ONE_LINE_STRING
    regex = r'\A[\-0-9a-z]+\Z'
    error_msg_template = '"{}" is not a valid event category'

    warning_msg_template = ('category value %a is not amongst the elements '
                            'of n6lib.const.CATEGORY_ENUMS!')

    def clean_result_value(self, value):
        value = super().clean_result_value(value)
        if value not in CATEGORY_ENUMS:
            # we do not raise an error here -- to make future
            # transitions/migrations more convenient...
            LOGGER.warning(self.warning_msg_template, value)
        return value


class DomainNameCustomizedField(DomainNameField):

    max_length = MAX_LEN_OF_DOMAIN_NAME


class ComponentLoginField(DomainNameCustomizedField):

    error_msg_template = '"{}" is not a valid component login - a domain name is expected'


class OrgIdField(DomainNameCustomizedField):

    max_length = MAX_LEN_OF_ORG_ID
    error_msg_template = '"{}" is not a valid organization ID - a domain name is expected'


class EmailCustomizedField(EmailSimplifiedField):

    max_length = MAX_LEN_OF_EMAIL
    regex = EMAIL_OVERRESTRICTED_SIMPLE_REGEX
    error_msg_template = '"{}" is not a valid e-mail address'

    def _validate_value(self, value):
        forbidden_characters = self._get_additionally_forbidden_characters()
        illegal_characters = forbidden_characters.intersection(value)
        if illegal_characters:
            illegal_characters_listing = ', '.join(
                f"'{ch}'" for ch in sorted(illegal_characters))
            raise FieldValueError(public_message=ascii_str(
                f'"{value}" contains illegal character(s): '
                f'{illegal_characters_listing}.'))
        super()._validate_value(value)

    def _get_additionally_forbidden_characters(self):
        return frozenset()


class UserLoginField(EmailCustomizedField):

    _CHARACTERS_ADDITIONALLY_FORBIDDEN_IN_LOGINS = frozenset(string.ascii_uppercase)

    error_msg_template = '"{}" is not a valid user login - an e-mail address is expected'

    def _get_additionally_forbidden_characters(self):
        return (self._CHARACTERS_ADDITIONALLY_FORBIDDEN_IN_LOGINS |
                super()._get_additionally_forbidden_characters())


class IdHexField(UnicodeLimitedField, UnicodeRegexField):

    disallow_empty = True
    max_length = MAX_LEN_OF_ID_HEX
    regex = r'\A[0-9a-f]+\Z'

    error_msg_template = '"{}" is not a valid hex-digits-only identifier'


class NoWhitespaceSecretField(UnicodeLimitedField, UnicodeRegexField):

    sensitive = True
    default_error_msg_if_sensitive = 'not a valid secret - too short or contains whitespace?'

    disallow_empty = True
    max_length = MAX_LEN_OF_GENERIC_ONE_LINE_STRING
    regex = re.compile(r'\A\S{64,}\Z',  # Non-whitespace characters only, not less than 64 of them.
                       re.UNICODE)


class UUID4SecretField(UnicodeLimitedField, UnicodeRegexField):

    sensitive = True
    default_error_msg_if_sensitive = 'not a valid UUID4'

    disallow_empty = True
    regex = r'\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z'
    max_length = MAX_LEN_OF_UUID4

    def _fix_value(self, value):
        value = super()._fix_value(value)
        return value.lower()


class RegistrationRequestAnyEmailField(EmailCustomizedField):

    # Note: the characters specified by this constant are formally
    # valid e-mail characters but we prefer to forbid them in email
    # addresses originating from the registration request web form
    # which is supposed to be publicly accessible without authentication
    # (it is not a "hard" counteraction against some particular type of
    # attack -- but rather a "soft"/"just-in-case"/"let's reduce the
    # likelihood of some types of attacks" kind of safety measure).
    _CHARACTERS_ADDITIONALLY_FORBIDDEN_IN_REGISTRATION_REQ_EMAILS = frozenset('#$%&\'*/=?^`{|}~')

    def _get_additionally_forbidden_characters(self):
        return (self._CHARACTERS_ADDITIONALLY_FORBIDDEN_IN_REGISTRATION_REQ_EMAILS |
                super()._get_additionally_forbidden_characters())


class RegistrationRequestEmailBeingCandidateLoginField(UserLoginField,
                                                       RegistrationRequestAnyEmailField):

    def _validate_value(self, value):
        # XXX: this method extension is to be removed when
        #      we finally get rid of the LDAP stuff remains.
        from n6lib.auth_db.validators import _ascii_only_ldap_safe_str_strip
        super()._validate_value(value)
        assert value.strip() == _ascii_only_ldap_safe_str_strip(value)

    def _get_additionally_forbidden_characters(self):
        # XXX: this method extension is to be removed when
        #      we finally get rid of the LDAP stuff remains.
        from n6lib.auth_db.validators import LDAP_UNSAFE_CHARACTERS
        return (LDAP_UNSAFE_CHARACTERS |
                super()._get_additionally_forbidden_characters())


class IPv4NetAlwaysAsStringField(IPv4NetField):

    def convert_param_cleaned_string_value(self, value):
        assert isinstance(value, str)
        return value


class URLSimpleField(UnicodeLimitedField):

    max_length = MAX_LEN_OF_URL
    disallow_empty = True
    decode_error_handling = 'strict'


class DateTimeCustomizedField(DateTimeField):

    min_datetime = datetime.datetime.utcfromtimestamp(0)  # 1970-01-01T00:00:00Z
    keep_sec_fraction = False

    def clean_result_value(self, value):
        value = super().clean_result_value(value)
        # do not accept times that are *not* representable as UNIX timestamps
        if value < self.min_datetime:
            raise FieldValueError(public_message=(
                'The given date+time {} is older '
                'than the required minimum {}'.format(
                    value.isoformat(),
                    self.min_datetime.isoformat())))
        return value


class TimeHourMinuteField(Field):

    """
    A field class, specifying valid data types and values
    for fields adapted to store hour+minute time information.

    This field type can accept `datetime.time` objects, strings
    and integers. Returns a `datetime.time` object.
    """

    time_format = '%H:%M'

    def clean_param_value(self, value):
        value = super().clean_param_value(value)
        return self._time_object_from_string(value)

    def clean_result_value(self, value):
        value = super().clean_result_value(value)
        if isinstance(value, datetime.time):
            return self._validate_time_object(value)
        elif isinstance(value, str):
            return self._time_object_from_string(value)
        elif isinstance(value, int):
            return self._time_object_from_integer(value)
        else:
            raise FieldValueError(public_message='Value {value!a} is of a wrong type:'
                                                 ' {val_type!a} to be validated as a proper '
                                                 'database `Time` column record.'
                                                 .format(value=value, val_type=type(value)))

    @staticmethod
    def _validate_time_object(value):
        if value.second or value.microsecond:
            raise FieldValueError(public_message='Validated datetime.time object: {!a} has to '
                                                 'contain hour only or hour with minutes, without '
                                                 'seconds and microseconds.'.format(value))
        if value.tzinfo is not None:
            raise FieldValueError(public_message='Validated datetime.time object: {!a} has to '
                                                 'be "naive" (must not include '
                                                 'timezone information).'.format(value))
        return value

    @classmethod
    def _time_object_from_string(cls, value):
        try:
            return datetime.datetime.strptime(value, cls.time_format).time()
        except (TypeError, ValueError):
            raise FieldValueError(
                public_message='"{}" is not a valid *hour:minute* time '
                               'specification'.format(ascii_str(value)))

    @staticmethod
    def _time_object_from_integer(value):
        """
        Validate, whether passed value is an integer in range
        0 to 23, so it can be set as an hour part in `datetime.time`
        object.

        Although the `Time` type of column represents datetime.time
        in Python, MySQL backend interprets passed integers
        differently than datetime.time. E.g. it converts a single-
        and double-digit numbers to seconds (not to hours, like
        datetime.time). Next places to the left reflect successively
        minutes and hours.

        In order to simplify this behavior, the method takes a number
        between 0 and 23 and converts it to a `datetime.time` object,
        that represents an hour only.

        Args:
            `value`:
                validated hour as integer.

        Returns:
            a `datetime.time` object.

        Raises:
            A `FieldValueError` if the validated number is out
            of the expected range.
        """
        try:
            return datetime.time(value)
        except ValueError as exc:
            raise FieldValueError(public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=value,
                                                                                   exc=exc))


class _BaseNameOrTokenField(UnicodeLimitedField, UnicodeRegexField):

    # Note: there is no `\A` (or `^`) and no `\Z` (or `$`) in the
    # following regex -- as we only demand that values contain *some*
    # non-whitespace character(s) (*not* that they contain *only* such
    # characters).
    regex = re.compile(r'\S+', re.UNICODE)
    auto_strip = True
    disallow_empty = True

    def clean_result_value(self, value):
        if value is None:
            # Note that it is relevant only to *non-nullable* columns,
            # because for nullable ones our Base's metaclass ensures
            # that for `None` values validators are not used.
            raise FieldValueError(public_message='The value is missing')
        return super().clean_result_value(value)


class OfficialOrContactTokenField(_BaseNameOrTokenField):

    max_length = MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN


class EntityNameField(_BaseNameOrTokenField):

    max_length = MAX_LEN_OF_GENERIC_ONE_LINE_STRING
    error_msg_template = '"{}" is not a valid entity name.'

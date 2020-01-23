# Copyright (c) 2013-2019 NASK. All rights reserved.

import datetime

from n6lib.auth_db import (
    INVALID_FIELD_TEMPLATE_MSG,
    MAX_LEN_OF_DOMAIN_NAME,
    MAX_LEN_OF_EMAIL,
    MAX_LEN_OF_GENERIC_SHORT_STRING,
    MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL,
    MAX_LEN_OF_ORG_ID,
    MAX_LEN_OF_URL,
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

    max_length = MAX_LEN_OF_GENERIC_SHORT_STRING
    regex = r'\A[\-0-9a-z]+\Z'
    error_msg_template = u'"{}" is not a valid event category'

    warning_msg_template = ('category value %r is not amongst the elements '
                            'of n6lib.const.CATEGORY_ENUMS!')

    def clean_result_value(self, value):
        value = super(CategoryCustomizedField, self).clean_result_value(value)
        if value not in CATEGORY_ENUMS:
            # we do not raise an error here -- to make future
            # transitions/migrations more convenient...
            LOGGER.warning(self.warning_msg_template, value)
        return value


class DomainNameCustomizedField(DomainNameField):

    max_length = MAX_LEN_OF_DOMAIN_NAME


class ComponentLoginField(DomainNameCustomizedField):

    error_msg_template = u'"{}" is not a valid component login - a domain name is expected'


class OrgIdField(DomainNameCustomizedField):

    max_length = MAX_LEN_OF_ORG_ID
    error_msg_template = u'"{}" is not a valid organization ID - a domain name is expected'


class EmailCustomizedField(EmailSimplifiedField):

    max_length = MAX_LEN_OF_EMAIL
    regex = EMAIL_OVERRESTRICTED_SIMPLE_REGEX
    error_msg_template = u'"{}" is not a valid e-mail address'

    def _validate_value(self, value):
        forbidden_characters = self._get_additionally_forbidden_characters()
        illegal_characters = forbidden_characters.intersection(value)
        if illegal_characters:
            raise FieldValueError(
                public_message='"{value}" contains illegal character(s): {chars}.'.format(
                    value=ascii_str(value),
                    chars=', '.join(sorted("'{}'".format(ascii_str(ch))
                                           for ch in illegal_characters))))
        super(EmailCustomizedField, self)._validate_value(value)

    def _get_additionally_forbidden_characters(self):
        return frozenset()


class UserLoginField(EmailCustomizedField):

    error_msg_template = u'"{}" is not a valid user login - an e-mail address is expected'


class RegistrationRequestEmailField(EmailCustomizedField):

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
                super(RegistrationRequestEmailField,
                      self)._get_additionally_forbidden_characters())


# XXX: this class is to be removed when we finally get rid of the LDAP stuff remains
class RegistrationRequestEmailLDAPSafeField(RegistrationRequestEmailField):

    def _validate_value(self, value):
        from n6lib.auth_db.validators import _ascii_only_ldap_safe_to_unicode_stripped
        super(RegistrationRequestEmailLDAPSafeField, self)._validate_value(value)
        assert value.strip() == _ascii_only_ldap_safe_to_unicode_stripped(value)

    def _get_additionally_forbidden_characters(self):
        from n6lib.auth_db.validators import LDAP_UNSAFE_CHARACTERS
        return (LDAP_UNSAFE_CHARACTERS |
                super(RegistrationRequestEmailLDAPSafeField,
                      self)._get_additionally_forbidden_characters())


class IPv4NetAlwaysAsStringField(IPv4NetField):

    def convert_param_cleaned_string_value(self, value):
        assert isinstance(value, unicode)
        return value


class URLSimpleField(UnicodeLimitedField):

    max_length = MAX_LEN_OF_URL
    disallow_empty = True
    decode_error_handling = 'strict'


class DateTimeCustomizedField(DateTimeField):

    min_datetime = datetime.datetime.utcfromtimestamp(0)  # 1970-01-01T00:00:00Z

    def clean_result_value(self, value):
        value = super(DateTimeCustomizedField, self).clean_result_value(value)
        # get rid of the fractional part of seconds
        value = value.replace(microsecond=0)
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
    for fields adapted to store time in hour:minute format.

    This field type can accept datetime.time objects, strings
    and integers. Returns a datetime.time object.
    """

    hour_minute_format = '%H:%M'

    def clean_param_value(self, value):
        """
        It is a result-only field, so the method always raises
        an exception.
        """
        raise TypeError("it is a result-only field")

    def clean_result_value(self, value):
        value = super(TimeHourMinuteField, self).clean_result_value(value)
        if isinstance(value, datetime.time):
            return self._clean_time_object(value)
        elif isinstance(value, basestring):
            return self._clean_string(value)
        elif isinstance(value, int):
            return self._clean_integer(value)
        else:
            raise FieldValueError(public_message='Value {value!r} is of a wrong type:'
                                                 ' {val_type!r} to be validated as a proper '
                                                 'database `Time` column record.'
                                                 .format(value=value, val_type=type(value)))

    @staticmethod
    def _clean_time_object(value):
        if value.second or value.microsecond:
            raise FieldValueError(public_message='Validated datetime.time object: {!r} has to '
                                                 'contain hour only or hour with minutes, without '
                                                 'seconds and microseconds.'.format(value))
        if value.tzinfo is not None or value.utcoffset() is not None:
            raise FieldValueError(public_message='Validated datetime.time object: {!r} has to '
                                                 'be "naive" (must not include '
                                                 'timezone information).'.format(value))
        return value

    @classmethod
    def _clean_string(cls, value):
        try:
            return datetime.datetime.strptime(value, cls.hour_minute_format).time()
        except (TypeError, ValueError) as exc:
            raise FieldValueError(
                public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=value, exc=exc))

    @staticmethod
    def _clean_integer(value):
        """
        Validate, whether passed value is an integer in range
        0 to 23, so it can be set as an hour part in datetime.time
        object.

        Although the `Time` type of column represents datetime.time
        in Python, MySQL backend interprets passed integers
        differently than datetime.time. E.g. it converts a single-
        and double-digit numbers to seconds (not to hours, like
        datetime.time). Next places to the left reflect successively
        minutes and hours.

        In order to simplify this behavior, the method takes a number
        between 0 and 23 and converts it to a datetime.time object,
        that represents an hour only.

        Args:
            `value`:
                validated hour as integer.

        Returns:
            a datetime.time object.

        Raises:
            A FieldValueError if the validated number is out
            of expected range.
        """
        try:
            return datetime.time(value)
        except ValueError as exc:
            raise FieldValueError(public_message=INVALID_FIELD_TEMPLATE_MSG.format(value=value,
                                                                                   exc=exc))


class _BaseOfficialIdOrTypeLabelField(UnicodeLimitedField, UnicodeRegexField):

    max_length = MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL
    disallow_empty = True

    def clean_result_value(self, value):
        return super(_BaseOfficialIdOrTypeLabelField, self).clean_result_value(value.strip())


class TypeLabelField(_BaseOfficialIdOrTypeLabelField):

    regex = r'\w+'
    error_msg_template = u'"{}" is not a valid type label'


class ExtraIdField(_BaseOfficialIdOrTypeLabelField):

    regex = r'\A[0-9\-]+\Z'
    error_msg_template = u'"{}" is not a valid extra ID'

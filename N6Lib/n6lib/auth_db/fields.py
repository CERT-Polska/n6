# Copyright (c) 2013-2019 NASK. All rights reserved.

import datetime

from n6lib.auth_db import INVALID_FIELD_TEMPLATE_MSG
from n6lib.common_helpers import EMAIL_OVERRESTRICTED_SIMPLE_REGEX
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.data_spec import FieldValueError
from n6lib.data_spec.fields import (
    DomainNameField,
    FieldForN6,
    UnicodeLimitedField,
    UnicodeRegexField,
)


class OrgIdField(DomainNameField):

    disallow_empty = True
    max_length = CLIENT_ORGANIZATION_MAX_LENGTH


class URLSimpleField(UnicodeLimitedField):

    max_length = 2048
    decode_error_handling = 'strict'


class EmailRestrictedField(UnicodeLimitedField, UnicodeRegexField):

    max_length = 255
    regex = EMAIL_OVERRESTRICTED_SIMPLE_REGEX
    error_msg_template = u'"{}" is not a valid e-mail address.'


class UserLoginField(EmailRestrictedField):

    error_msg_template = '"{}" is not a valid user login - an e-mail address is expected.'


class TimeHourMinuteField(FieldForN6):

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


class ExtraIDField(UnicodeRegexField):

    regex = r'\A[0-9\-]+\Z'
    error_msg_template = '"{}" is not a valid extra ID value.'

    def clean_result_value(self, value):
        return super(ExtraIDField, self).clean_result_value(value.strip())

# Copyright (c) 2013-2018 NASK. All rights reserved.

from n6lib.common_helpers import EMAIL_OVERRESTRICTED_SIMPLE_REGEX
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.data_spec.fields import (
    DomainNameField,
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


class HexField(UnicodeRegexField):

    regex = r'\A[0-9a-f]*\Z'
    error_msg_template = '"{}" is not a valid hexadecimal number.'

    def clean_result_value(self, value):
        return super(HexField, self).clean_result_value(value.strip().lower())

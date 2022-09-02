# Copyright (c) 2022 NASK. All rights reserved.

import re
from enum import Enum
from typing import Optional

from flask import g
from flask_admin.model import InlineFormAdmin
from jinja2 import Markup
from wtforms import (
    StringField,
    IntegerField,
)
from wtforms.widgets import TextInput


FQDN_INSIDE_EMAIL_REGEX = re.compile(r'''
    (?<=@)  # do not capture the '@' character
    [^@\s]+
    \Z
''', re.VERBOSE)


class RecordTypes(Enum):

    ASN = 'ASN_RECORD'
    IP_NETWORK = 'IP_NETWORK_RECORD'
    FQDN = 'FQDN_RECORD'
    FQDN_EMAIL = 'FQDN_FROM_EMAIL_RECORD'


class ApiLookupWidget(TextInput):

    is_lookup_client_active: bool = True
    __FQDN_FROM_EMAIL_VAL_ATTR_NAME = 'data_fqdn_value'

    def __call__(self, field, **kwargs):
        data = self.__get_data_or_none(kwargs, field)
        record_type = kwargs.get('record_type')
        if record_type is None:
            raise ValueError(f'The `record_type` keyword argument of '
                             f'the {self.__class__.__name__!a} is missing')
        if record_type == RecordTypes.FQDN_EMAIL.value and data:
            # The kwarg will be converted to input element's attribute.
            # In custom attribute names, prefixed with 'data',
            # underscore characters will be replaced with hyphens.
            kwargs[self.__FQDN_FROM_EMAIL_VAL_ATTR_NAME] = data
        input_html = super().__call__(field, **kwargs)
        if data is not None and self.is_lookup_client_active:
            btn_html = Markup('<button '
                              'type="button" '
                              'class="el-over-input api-lookup-btn btn btn-default" '
                              f'onclick="makeApiRequest(event, {record_type})">'
                              '</button>')
            joined_html = Markup()
            return joined_html.join((input_html, btn_html))
        return input_html

    @classmethod
    def __get_data_or_none(cls, kw, field):
        data = kw.get('data') or field._value()
        if data is None or (isinstance(data, str) and not data):
            return None
        # a special case when the value being looked up against
        # an API should be extracted from an e-mail address
        if kw.get('record_type') == RecordTypes.FQDN_EMAIL.value:
            return cls.__extract_fqdn_from_email(data)
        return data

    @classmethod
    def __extract_fqdn_from_email(cls, email_value: str) -> Optional[str]:
        match = FQDN_INSIDE_EMAIL_REGEX.search(email_value.strip())
        if match is None:
            return None
        return match.group()


class BaddomainsApiLookupWidget(ApiLookupWidget):

    def __call__(self, field, **kwargs):
        self.is_lookup_client_active = g.is_baddomains_client_active
        return super().__call__(field, **kwargs)


class ASNInlineFormAdmin(InlineFormAdmin):

    record_type = RecordTypes.ASN

    form_extra_fields = {
        'asn': IntegerField(widget=ApiLookupWidget(),
                            render_kw={'record_type': record_type.value}),
    }


class IPNetworkInlineFormAdmin(InlineFormAdmin):

    record_type = RecordTypes.IP_NETWORK

    form_extra_fields = {
        'ip_network': StringField(widget=ApiLookupWidget(),
                                  render_kw={'record_type': record_type.value}),
    }


class FQDNInlineFormAdmin(InlineFormAdmin):

    record_type = RecordTypes.FQDN

    form_extra_fields = {
        'fqdn': StringField(widget=BaddomainsApiLookupWidget(),
                            render_kw={'record_type': record_type.value}),
    }


class EmailInlineFormAdmin(InlineFormAdmin):

    record_type = RecordTypes.FQDN_EMAIL

    form_extra_fields = {
        'email': StringField(widget=BaddomainsApiLookupWidget(),
                             render_kw={'record_type': record_type.value})
    }


# Dict of arguments of a single column type. To be used as a value
# of column name key in the `form_args` instance attribute of
# a subclass of `ModelView`.
FQDN_FIELD_ARGS = {
    'widget': BaddomainsApiLookupWidget(),
    'render_kw': {'record_type': RecordTypes.FQDN.value},
}

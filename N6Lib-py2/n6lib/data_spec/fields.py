# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.


# Terminology: some definitions and synonyms
# ==========================================
# -> see the comment at the top of the
#    `n6lib/data_spec/_data_spec.py` file.


from builtins import map                                                         #3--
import base64
import string
import urllib.parse

from n6lib.common_helpers import ascii_str
from n6lib.common_helpers import (                                               #3--
    as_bytes,                                                                    #3--
    as_unicode,                                                                  #3--
)                                                                                #3--
from n6lib.class_helpers import is_seq_or_set
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6sdk.data_spec.fields import (
    Field,
    AddressField,
    AnonymizedIPv4Field,
    ASNField,
    CCField,
    DateTimeField,
    DictResultField,
    DomainNameField,
    DomainNameSubstringField,
    EmailSimplifiedField,
    FlagField,
    HexDigestField,
    IBANSimplifiedField,
    IntegerField,
    IPv4Field,
    IPv4NetField,
    ListOfDictsField,
    MD5Field,
    PortField,
    ResultListFieldMixin,
    SHA1Field,
    SHA256Field,
    SourceField,
    UnicodeField,
    UnicodeEnumField,
    UnicodeLimitedField,
    UnicodeRegexField,
    URLField,
    URLSubstringField,
)
from n6sdk.exceptions import FieldValueError



#
# FieldForN6-related Constants
#

VALID_MAIN_QUALIFIERS = frozenset({'required', 'optional'})
VALID_ACCESS_QUALIFIERS = frozenset({'unrestricted', 'anonymized'})



#
# Actual field classes
#

# NOTE: all field classes defined in this module should be subclasses of
# the following class (to have features provided by it) and should have
# names ending with 'FieldForN6' (for consistency and easier testing...)

class FieldForN6(Field):

    # extended Field.handle_in_arg()
    def handle_in_arg(self, arg_name, arg_value):
        try:
            (main_qualifier,
             additional_info) = self._get_main_qualifier_and_additional_info(arg_value)
            ai_validator_meth_name = '_validate_{}_additional_info_items'.format(arg_name)
            ai_validator_meth = getattr(self, ai_validator_meth_name)
            ai_validator_meth(additional_info)
        except ValueError as exc:
            raise ValueError(
                '{}.__init__() got {}={!r}; {}'.format(
                    self.__class__.__name__,                                     #3: `__name__`->`__qualname__`
                    arg_name,
                    arg_value,
                    exc))
        additional_info_attr_name = arg_name + '_additional_info'
        setattr(self, additional_info_attr_name, additional_info)
        super(FieldForN6, self).handle_in_arg(arg_name, main_qualifier)

    def _get_main_qualifier_and_additional_info(self, arg_value):
        if is_seq_or_set(arg_value):
            # the `in_params`/`in_result` field constructor argument is a
            # set or a sequence (but not a str/bytes/bytearray) -- so we expect
            # that it contains the main qualifier (one of VALID_MAIN_QUALIFIERS)
            # and possibly also other items (which we will isolate and place
            # in the `additional_info` frozenset)
            (main_qualifier,
             additional_info) = self._extract_components(arg_value)
        else:
            # otherwise we expect it to be just the main qualifier or None
            # (as in n6sdk)
            if arg_value is not None and arg_value not in VALID_MAIN_QUALIFIERS:
                raise ValueError(
                    "if not None it should be a valid main qualifier "
                    "(one of: {}) or a set/sequence containing it".format(
                        ', '.join(sorted(map(repr, VALID_MAIN_QUALIFIERS)))))
            main_qualifier = arg_value
            additional_info = frozenset()
        assert main_qualifier is None and not additional_info or (
            main_qualifier in VALID_MAIN_QUALIFIERS and
            not (additional_info & VALID_MAIN_QUALIFIERS))
        return main_qualifier, additional_info

    def _extract_components(self, arg_value):
        found_main_qual = VALID_MAIN_QUALIFIERS.intersection(arg_value)
        try:
            # exactly one (being an item of VALID_MAIN_QUALIFIERS) is expected
            [main_qualifier] = found_main_qual
        except ValueError:
            if found_main_qual:
                raise ValueError(
                    "multiple main qualifiers: {} (expected only one)".format(
                        ', '.join(sorted(map(repr, found_main_qual)))))
            else:
                raise ValueError(
                    "no main qualifier (expected one of: {})".format(
                        ', '.join(sorted(map(repr, VALID_MAIN_QUALIFIERS)))))
        additional_info = frozenset(arg_value) - found_main_qual
        return main_qualifier, additional_info

    def _validate_in_params_additional_info_items(self, additional_info):
        self._ensure_no_multiple_access_qualifiers(additional_info)
        ### XXX: probably some other possibilities will be added here...
        self._ensure_only_access_qualifiers(additional_info)

    def _validate_in_result_additional_info_items(self, additional_info):
        self._ensure_no_multiple_access_qualifiers(additional_info)
        self._ensure_only_access_qualifiers(additional_info)

    def _ensure_only_access_qualifiers(self, a_set):
        illegal_items = a_set - VALID_ACCESS_QUALIFIERS
        if illegal_items:
            raise ValueError('illegal item(s): {}'.format(
                ', '.join(sorted(map(repr, illegal_items)))))

    def _ensure_no_multiple_access_qualifiers(self, a_set):
        found_access_qual = a_set & VALID_ACCESS_QUALIFIERS
        if len(found_access_qual) > 1:
            raise ValueError(
                "multiple access qualifiers: {} (expected only one)".format(
                    ', '.join(sorted(map(repr, found_access_qual)))))


# n6lib versions of field classes defined in SDK:

class AddressFieldForN6(AddressField, FieldForN6):
    pass

class AnonymizedIPv4FieldForN6(AnonymizedIPv4Field, FieldForN6):
    pass

class ASNFieldForN6(ASNField, FieldForN6):
    pass

class CCFieldForN6(CCField, FieldForN6):
    pass

class DateTimeFieldForN6(DateTimeField, FieldForN6):
    pass

class DictResultFieldForN6(DictResultField, FieldForN6):
    pass

class DomainNameFieldForN6(DomainNameField, FieldForN6):
    pass

class DomainNameSubstringFieldForN6(DomainNameSubstringField, FieldForN6):
    pass

class EmailSimplifiedFieldForN6(EmailSimplifiedField, FieldForN6):
    pass

class FlagFieldForN6(FlagField, FieldForN6):
    pass

class HexDigestFieldForN6(HexDigestField, FieldForN6):
    pass

class IBANSimplifiedFieldForN6(IBANSimplifiedField, FieldForN6):
    pass

class IntegerFieldForN6(IntegerField, FieldForN6):
    pass

class IPv4FieldForN6(IPv4Field, FieldForN6):
    pass

class IPv4NetFieldForN6(IPv4NetField, FieldForN6):
    pass

class ListOfDictsFieldForN6(ListOfDictsField, FieldForN6):
    pass

class MD5FieldForN6(MD5Field, FieldForN6):
    pass

class PortFieldForN6(PortField, FieldForN6):
    pass

class SHA1FieldForN6(SHA1Field, FieldForN6):
    pass

class SHA256FieldForN6(SHA256Field, FieldForN6):
    pass

class SourceFieldForN6(SourceField, FieldForN6):
    pass

class URLFieldForN6(URLField, FieldForN6):
    pass

class URLSubstringFieldForN6(URLSubstringField, FieldForN6):
    pass

class UnicodeFieldForN6(UnicodeField, FieldForN6):
    pass

class UnicodeEnumFieldForN6(UnicodeEnumField, FieldForN6):
    pass

class UnicodeLimitedFieldForN6(UnicodeLimitedField, FieldForN6):
    pass

class UnicodeRegexFieldForN6(UnicodeRegexField, FieldForN6):
    pass


# n6lib-specific field classes:

class _ClientOrgIdFieldForN6(UnicodeLimitedFieldForN6):
    ###encoding = 'ascii'     ### XXX: to be uncommented...
    ###disallow_empty = True  ### XXX: to be uncommented???...
    max_length = CLIENT_ORGANIZATION_MAX_LENGTH

class _InsideCritURLFieldForN6(UnicodeFieldForN6):
    # consciously *not* related to URLFieldForN6
    encoding = 'utf-8'
    decode_error_handling = 'utf8_surrogatepass_and_surrogateescape'

class _ListOfInsideCritURLsFieldForN6(ResultListFieldMixin, _InsideCritURLFieldForN6):
    sort_result_list = True


class ClientFieldForN6(ResultListFieldMixin, _ClientOrgIdFieldForN6):
    sort_result_list = True


class URLBase64FieldForN6(UnicodeField, FieldForN6):

    # *EXPERIMENTAL* (likely to be changed or removed in the future
    # without any warning/deprecation/etc.)

    # consciously *not* directly related to URLFieldForN6 (as we don't
    # want the length limit; probably, in the future, the limit will
    # be removed also from URLFieldForN6)

    encoding = 'utf-8'
    decode_error_handling = 'utf8_surrogatepass_and_surrogateescape'

    _URLSAFE_B64_VALID_CHARACTERS = frozenset(string.ascii_letters + '0123456789' + '-_=')
    assert len(_URLSAFE_B64_VALID_CHARACTERS) == 65  # 64 encoding chars and padding char '='

    def _fix_value(self, value):
        value = self._stubbornly_unquote(value)
        value = self._urlsafe_b64decode(value)
        value = super(URLBase64FieldForN6, self)._fix_value(value)
        return value

    def _stubbornly_unquote(self, value):
        # Note: we can assume that the value has been unquoted (from
        # %-encoding) by the Pyramid stuff, but the following stubborn
        # unquoting is added for cases when data have been quoted by
        # the client "too many times"; we try to be "liberal in what we
        # accept" because, indeed, it is quite easy to get lost in all
        # this encoding stuff :-).  But, on the other hand, we would
        # not like to allow for any ambiguities, so we accept *only*
        # URL-safe-Base64-encoding, not standard-Base64-encoding (as
        # the latter involves '+' whose meaning would not be clear:
        # it could be interpreted as a plus sign or as a space which,
        # then, could be interpreted just as an "ignorable filler"...).
        # Note, therefore, that it becomes *not* crucial whether we use
        # `urllib.unquote()` or `urllib.unquote_plus()` here -- because
        # URL-safe-Base64-encoding does *not* allow plus signs (and we
        # also *forbid* spaces, even as "ignorable fillers").
        value = as_unicode(value)                                                         #3--
        for _ in range(10):
            # ^ limited number of steps because we do not like allowing
            #   API clients to make us go into an infinite loop... :-]
            value = urllib.parse.unquote_plus(value)
            if u'%' not in value and u'+' not in value:                                   #3: u-- u--
                break
        value = as_unicode(value)                                                         #3--
        return value

    def _urlsafe_b64decode(self, value):
        value = value.rstrip('\r\n')  # some encoders like to append a newline...
        try:
            # `base64.urlsafe_b64decode()` just ignores illegal
            # characters *but* we want to be *more strict*
            if not self._URLSAFE_B64_VALID_CHARACTERS.issuperset(value):
                raise ValueError
            # `base64.urlsafe_b64decode()` (contrary to `base64.standard_b64decode()`)    #3--
            # does *not* accept unicode strings (even not pure-ASCII ones) :-/            #3--
            value = as_bytes(value)                                                       #3--
            value = base64.urlsafe_b64decode(value)
        except (ValueError, TypeError):  # (TypeError is raised on incorrect Base64 padding)  # <- TODO: check if it is still true in Py3
            raise FieldValueError(public_message=(
                '"{}" is not a valid URL-safe-Base64-encoded string '
                '[see: RFC 4648, section 5]'.format(ascii_str(value))))
        return value


class URLsMatchedFieldForN6(DictResultFieldForN6):

    key_to_subfield_factory = {None: _ListOfInsideCritURLsFieldForN6}

    def __init__(self, **kwargs):
        self._client_org_id_field = _ClientOrgIdFieldForN6()
        super(URLsMatchedFieldForN6, self).__init__(**kwargs)

    def clean_result_value(self, value):
        value = super(URLsMatchedFieldForN6, self).clean_result_value(value)
        assert isinstance(value, dict)
        if not value:
            raise ValueError('the dictionary is empty')
        return value

    def _adjust_key(self, key):
        return self._client_org_id_field.clean_result_value(key)


class SomeUnicodeFieldForN6(UnicodeLimitedFieldForN6):

    encoding = 'utf-8'
    decode_error_handling = 'utf8_surrogatepass_and_surrogateescape'
    max_length = 3000

    def clean_param_value(self, value):
        raise TypeError("it's not a param field")


class SomeUnicodeListFieldForN6(ResultListFieldMixin, SomeUnicodeFieldForN6):
    pass


class SomeFieldForN6(SomeUnicodeFieldForN6):

    def clean_result_value(self, value):
        str = unicode                                                            #3--
        if isinstance(value, (str, bytes, bytearray)):
            value = super(SomeFieldForN6, self).clean_result_value(value)
        return value


# for RecordDict['enriched']
# (see the comment in the code of n6.utils.enrich.Enricher.enrich())
class EnrichedFieldForN6(FieldForN6):

    enrich_toplevel_keys = ('fqdn',)

    def __init__(self, **kwargs):
        super(EnrichedFieldForN6, self).__init__(**kwargs)
        self._toplevel_key_field = UnicodeEnumFieldForN6(enum_values=self.enrich_toplevel_keys)
        self._address_key_field = UnicodeEnumFieldForN6(enum_values=sorted(
            AddressFieldForN6.key_to_subfield_factory))
        self._ipv4_field = IPv4FieldForN6()

    def clean_param_value(self, value):
        raise TypeError("it's not a param field")

    def clean_result_value(self, value):
        enriched_keys_raw, ip_to_enriched_address_keys_raw = value
        enriched_keys = sorted(set(
            self._toplevel_key_field.clean_result_value(name)
            for name in enriched_keys_raw))
        ip_to_enriched_address_keys = {
            self._ipv4_field.clean_result_value(ip): sorted(set(
                self._address_key_field.clean_result_value(name)
                for name in addr_keys))
            for ip, addr_keys in ip_to_enriched_address_keys_raw.items()}
        return (enriched_keys, ip_to_enriched_address_keys)

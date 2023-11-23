# Copyright (c) 2013-2023 NASK. All rights reserved.


# Terminology: some definitions and synonyms
# ==========================================
# -> see the comment at the top of the
#    `N6Lib/n6lib/data_spec/_data_spec.py` file.


import base64
import string
import urllib.parse

from n6lib.common_helpers import ascii_str
from n6lib.class_helpers import is_seq_or_set
from n6lib.const import (
    CLIENT_ORGANIZATION_MAX_LENGTH,
    LACK_OF_IPv4_PLACEHOLDER_AS_STR,
)
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
                '{}.__init__() got {}={!a}; {}'.format(
                    self.__class__.__qualname__,
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
                        ', '.join(sorted(map(ascii, VALID_MAIN_QUALIFIERS)))))
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
                        ', '.join(sorted(map(ascii, found_main_qual)))))
            else:
                raise ValueError(
                    "no main qualifier (expected one of: {})".format(
                        ', '.join(sorted(map(ascii, VALID_MAIN_QUALIFIERS)))))
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
                ', '.join(sorted(map(ascii, illegal_items)))))

    def _ensure_no_multiple_access_qualifiers(self, a_set):
        found_access_qual = a_set & VALID_ACCESS_QUALIFIERS
        if len(found_access_qual) > 1:
            raise ValueError(
                "multiple access qualifiers: {} (expected only one)".format(
                    ', '.join(sorted(map(ascii, found_access_qual)))))


# internal helper field class
# (TODO later: to be merged to `IPv4Field` when SDK is merged to `n6lib`
#       -- then its tests and tests of `AddressField` should should also
#       include the behavior provided here, regarding `0.0.0.0`...)

class _IPv4FieldExcludingLackOfPlaceholder(IPv4Field):
    def _validate_value(self, value):
        if value == LACK_OF_IPv4_PLACEHOLDER_AS_STR:
            raise FieldValueError(public_message=(
                f'IPv4 address "{LACK_OF_IPv4_PLACEHOLDER_AS_STR}" is disallowed'))
        super()._validate_value(value)


# n6lib versions of field classes defined in SDK:

class AddressFieldForN6(AddressField, FieldForN6):
    key_to_subfield_factory = {
        u'ip': _IPv4FieldExcludingLackOfPlaceholder,
        u'cc': CCField,
        u'asn': ASNField,
    }

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

class IPv4FieldForN6(_IPv4FieldExcludingLackOfPlaceholder, FieldForN6):
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

    encoding = 'ascii'
    disallow_empty = True

    _URLSAFE_B64_VALID_CHARACTERS = frozenset(string.ascii_letters + '0123456789' + '-_=')
    assert len(_URLSAFE_B64_VALID_CHARACTERS) == 65  # 64 encoding chars and padding char '='

    def clean_param_value(self, value):
        # (the input is URL-safe-Base64-encoded + possibly also %-encoded...)
        value = super().clean_param_value(value)
        assert isinstance(value, str)
        value = self._stubbornly_unquote(value)
        value = value.rstrip('\r\n')  # some Base64 encoders like to append a newline...
        value = self._urlsafe_b64decode(value)
        assert isinstance(value, bytes)
        # (the output is raw/binary)
        return value

    def clean_result_value(self, value):
        raise TypeError("it's a param-only field")
        ### TODO later?
        # # (the input is either raw/binary or already URL-safe-Base64-encoded)
        # if not isinstance(value, str):
        #     value = base64.urlsafe_b64encode(value)
        # value = super().clean_result_value(value)
        # assert isinstance(value, str)
        # self._urlsafe_b64decode(value)  # just validate, ignore decoding result
        # # (the output is always URL-safe-Base64-encoded)
        # return value

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
        for _ in range(10):
            # ^ limited number of steps because we do not like allowing
            #   API clients to make us go into an infinite loop... :-]
            value = urllib.parse.unquote_plus(value)
            if '%' not in value and '+' not in value:
                break
        return value

    def _urlsafe_b64decode(self, value):
        try:
            # `base64.urlsafe_b64decode()` just ignores illegal
            # characters *but* we want to be *more strict*
            if not self._URLSAFE_B64_VALID_CHARACTERS.issuperset(value):
                raise ValueError
            value = base64.urlsafe_b64decode(value)
        except ValueError as exc:
            # (^ also `binascii.Error` may be raised, but
            # it is a subclass of `ValueError` anyway)
            raise FieldValueError(public_message=(
                f'"{ascii_str(value)}" is not a valid URL-safe-Base64'
                f'-encoded string [see: RFC 4648, section 5]')) from exc
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
        key = super()._adjust_key(key)
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
        if isinstance(value, (str, bytes, bytearray)):
            value = super(SomeFieldForN6, self).clean_result_value(value)
        return value


# for RecordDict['enriched']
# (see the comment in the code of n6datapipeline.enrich.Enricher.enrich())
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

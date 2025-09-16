# Copyright (c) 2013-2025 NASK. All rights reserved.

"""
.. note::

   For basic information how to use the classes defined in this module
   please consult the :ref:`data_spec_class` chapter of the tutorial.
"""


import collections.abc as collections_abc
import datetime
import ipaddress
import re
from binascii import unhexlify

from n6sdk.addr_helpers import (
    ip_network_as_tuple,
)
from n6sdk.class_helpers import is_seq
from n6sdk.datetime_helpers import (
    datetime_utc_normalize,
    parse_iso_datetime_to_utc,
)
from n6sdk.encoding_helpers import (
    ascii_str,
    as_unicode,
    compute_str_index_from_utf8_bytes_index,
    replace_surrogate_pairs_with_proper_codepoints,
    str_to_bool,
    verified_as_ascii_str,
)
from n6sdk.exceptions import (
    FieldValueError,
    FieldValueTooLongError,
)
from n6sdk.regexes import (
    CC_SIMPLE_REGEX,
    DOMAIN_ASCII_LOWERCASE_REGEX,
    EMAIL_SIMPLIFIED_REGEX,
    IBAN_REGEX,
    IPv4_STRICT_DECIMAL_REGEX,
    IPv4_CIDR_NETWORK_REGEX,
    IPv4_ANONYMIZED_REGEX,
    SOURCE_REGEX,
)



#
# The base field specification class

class Field(object):

    """
    The base class for all data field specification classes.

    It has two (overridable/extendable) instance methods:
    :meth:`clean_param_value` and :meth:`clean_result_value`
    (see below).

    Constructors of all field classes accept the following keyword-only
    arguments:

    * `in_params` (default: :obj:`None`:
          One of: ``'required'``, ``'optional'``, :obj:`None`.
    * `in_result` (default: :obj:`None`):
          One of: ``'required'``, ``'optional'``, :obj:`None`.
    * `single_param` (default: :obj:`False`):
          If false: multiple query parameter values are allowed.
    * `extra_params` (default: :obj:`None`):
          A dictionary that maps parameter *subnames* (second parts of
          *dotted names*) to instances of :class:`Field` or of its
          subclass.
    * `custom_info` (default: an empty dictionary):
          A dictionary containing arbitrary data (accessible as the
          :attr:`custom_info` instance attribute).
    * **any** keyword arguments whose names are the names of class-level
      attributes (see the second point in the paragraph below).

    Note that fields can be customized in two ways:

    1) by subclassing (and overridding/extending some of class-level
       attributes and/or methods);

    2) by specifying custom *per-instance* values with keyword
       arguments passed to the constructor -- then corresponding
       class-level attributes (typically defined in the body of the
       particular class or of any superclass of it) are overridden.
    """

    def __init__(self, **kwargs):
        self._init_kwargs = kwargs
        self._set_public_attrs(**kwargs)

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__qualname__,
            ', '.join(
                '{}={!r}'.format(key, value)
                for key, value in sorted(self._init_kwargs.items())))


    #
    # overridable methods/attributes

    # `BaseDataSpec.clean_{param,result}_dict()` methods (as well as the
    # `n6lib.record_dict.make_adjuster_using_data_spec()` function) take
    # into consideration the values of the following attributes when
    # handling cleaning errors...
    sensitive = False
    default_error_msg_if_sensitive = u'not a valid value'

    def clean_param_value(self, value):
        """
        The method called by *data specification*'s parameter cleaning methods.

        Args:
            `value`:
                A single parameter value (being *always* a :class:`str`
                instance).

        Returns:
            The value after necessary cleaning (adjustment/coercion/etc.
            and validation).

        Raises:
            Any instance/subclass of :exc:`~exceptions.Exception`
            (especially a :exc:`n6sdk.exceptions.FieldValueError`).

        The default implementation just passes the value unchanged.
        This method can be extended (using :func:`super`) in subclasses.

        The method should always return a new object,
        **never** modifying the given value in-place.

        .. note::

           Although any subclass of :exc:`~exceptions.Exception` can be
           used to signalize a cleaning/validation error, if you want to
           specify a *public message*, use
           :exc:`n6sdk.exceptions.FieldValueError` with the
           `public_message` constructor keyword argument specified.

        .. seealso::

           For more information -- see :ref:`field_cleaning_methods` in
           the tutorial.
        """
        assert isinstance(value, str)
        return value

    def clean_result_value(self, value):
        """
        The method called by *data specification*'s result cleaning methods.

        Args:
            `value`:
                A result item value (*not* necessarily a :class:`str`;
                valid types depend on a particular implementation of
                the method).

        Returns:
            The value after necessary cleaning (adjustment/coercion/etc.
            and validation).

        Raises:
            Any instance/subclass of :exc:`~exceptions.Exception`.

        The default implementation just passes the value unchanged.
        This method can be extended (using :func:`super`) in subclasses.

        The method should always return a new object,
        **never** modifying the given value in-place.

        .. seealso::

           For more information -- see :ref:`field_cleaning_methods` in
           the tutorial.
        """
        return value

    def handle_in_arg(self, arg_name, arg_value):
        """
        The method called on instance initialization for the `in_params`
        and `in_result` constructor arguments (separately for each of
        them).

        Args:
            `arg_name`:
                Always either ``'in_params'`` or ``'in_result'``.
            `arg_value`:
                The value of the particular (specified with `arg_name`)
                constructor argument.  The standard set of valid values
                includes only: :obj:`None`, ``'required'``, ``'optional'``
                -- but you may want to extend it in a subclass by
                overriding/extending the method.

        Raises:
            :exc:`~exceptions.ValueError` if `arg_value` is not valid
            (see above).

        The default implementation checks if `arg_value` is valid (see
        above); if it is, the attribute whose name is `arg_name` is set
        to `arg_value`.
        """
        assert arg_name in ('in_params', 'in_result')
        if arg_value not in (None, 'required', 'optional'):
            raise ValueError(
                "{!a} is not one of: None, 'required', 'optional'"
                .format(arg_value))
        setattr(self, arg_name, arg_value)


    #
    # non-public internals

    def _set_public_attrs(self,
                          in_params=None,
                          in_result=None,
                          single_param=False,
                          extra_params=None,
                          custom_info=None,
                          **per_instance_attrs):
        self.handle_in_arg('in_params', in_params)
        self.handle_in_arg('in_result', in_result)
        self.single_param = single_param
        self.extra_params = (
            extra_params if extra_params is not None
            else {})
        self.custom_info = (
            custom_info if custom_info is not None
            else {})
        self._set_per_instance_attrs(per_instance_attrs)

    def _set_per_instance_attrs(self, per_instance_attrs):
        # per-instance customizations of class-level attributes
        cls = self.__class__
        for attr_name, obj in per_instance_attrs.items():
            if not hasattr(cls, attr_name):
                raise TypeError(
                    '{}.__init__() got an unexpected keyword argument {!a}'
                    .format(cls.__qualname__, attr_name))
            setattr(self, attr_name, obj)



#
# Concrete field specification classes

class DateTimeField(Field):

    """
    For date-and-time (timestamp) values, automatically normalized to UTC.
    """

    keep_sec_fraction = True

    def clean_param_value(self, value):
        """
        The input `value` should be an *ISO-8601*-formatted :class:`str`.

        Returns: a :class:`datetime.datetime` object (a *naive* one,
        i.e. not aware of any timezone).
        """
        value = super(DateTimeField, self).clean_param_value(value)
        value = self._parse_datetime_string(value)
        if not self.keep_sec_fraction:
            value = value.replace(microsecond=0)
        return value

    def clean_result_value(self, value):
        """
        The input `value` should be a :class:`str` (*ISO-8601*-formatted)
        or a :class:`bytes`/:class:`bytearray` (*ISO-8601*-formatted), or
        a :class:`datetime.datetime` object (timezone-aware or *naive*).

        Returns: a :class:`datetime.datetime` object (a *naive* one,
        i.e. not aware of any timezone).
        """
        value = super(DateTimeField, self).clean_result_value(value)
        value = self._as_naive_utc_datetime(value)
        if not self.keep_sec_fraction:
            value = value.replace(microsecond=0)
        return value

    def _as_naive_utc_datetime(self, value):
        if isinstance(value, datetime.datetime):
            return datetime_utc_normalize(value)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode('utf-8', 'replace')
        if isinstance(value, str):
            return self._parse_datetime_string(value)
        raise TypeError(
            '{!a} is neither a str/bytes/bytearray nor a '
            'datetime.datetime object'.format(value))

    @staticmethod
    def _parse_datetime_string(value):
        try:
            return parse_iso_datetime_to_utc(value)
        except Exception:
            raise FieldValueError(public_message=(
                u'"{}" is not a valid date + '
                u'time specification'.format(ascii_str(value))))


class FlagField(Field):

    """
    For *YES/NO* flags, automatically normalized to :class:`bool`.
    """

    enable_empty_param_as_true = True

    def clean_param_value(self, value):
        """
        The input `value` should be such a :class:`str` that
        ``value.lower()`` is equal to one of:

        * ``""`` (this one only if `enable_empty_param_as_true`), or
          ``"yes"``, or ``"y"``, or ``"true"``, or ``"t"``, or ``"1"``,
          or ``"on"`` -- then the resultant cleaned value will be
          :obj:`True`;

        * ``"no"`` or ``"n"``, or ``"false"``, or ``"f"``, or ``"0"``,
          or ``"off"`` -- then the resultant cleaned value will be
          :obj:`False`;

        Note that when an empty string is given *and* the
        `enable_empty_param_as_true` option is true (it is :obj:`True`
        by default) then the resultant cleaned value will be :obj:`True`
        (!); thanks to that, a flag can be set by specifying the
        appropriate URL query parameter with no value (i.e., by using
        just its name).

        Returns: a :class:`bool` object (:obj:`True` or :obj:`False`).
        """
        value = super(FlagField, self).clean_param_value(value)
        if self.enable_empty_param_as_true and not value:
            return True
        value = value.lower()
        try:
            value = str_to_bool(value)
        except ValueError:
            raise FieldValueError(public_message=(
                str_to_bool.PUBLIC_MESSAGE_PATTERN.format(ascii_str(value))))
        return value


    def clean_result_value(self, value):
        """
        The input `value` should be such an object that
        ``str(value).lower()`` (or ``str(value.decode().lower())`` if
        `value` is a :class:`bytes`/:class:`bytearray`) is equal to one
        of:

        * ``"yes"`` or ``"y"``, or ``"true"``, or ``"t"``, or ``"1"``,
          or ``"on"`` -- then the resultant cleaned value will be
          :obj:`True`;

        * ``"no"`` or ``"n"``, or ``"false"``, or ``"f"``, or ``"0"``,
          or ``"off"`` -- then the resultant cleaned value will be
          :obj:`False`.

        It means that, among others, the boolean objects (:obj:`True`
        and :obj:`False`), the integers ``1`` and ``0``, as well as
        various *YES/NO-like* string variants (such as: ``"yes"``,
        ``"YES"``, ``"yEs"``, ``"y"``, ``"N"``, ``"True"``, ``"false"``,
        ``"1"``, ``"0"``...) -- are all perfectly OK as input values.

        Returns: a :class:`bool` object (:obj:`True` or :obj:`False`).
        """
        value = super(FlagField, self).clean_result_value(value)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode('utf-8')
        value = str(value).lower()
        value = str_to_bool(value)
        return value


class UnicodeField(Field):

    """
    For arbitrary text data.
    """

    encoding = 'utf-8'
    decode_error_handling = 'strict'
    replace_surrogates = False
    disallow_empty = False

    #: **Experimental attribute**
    #: (can be removed in future versions,
    #: so do not rely on it, please).
    auto_strip = False

    def clean_param_value(self, value):
        value = super(UnicodeField, self).clean_param_value(value)
        value = self._fix_value(value)
        self._validate_value(value)
        return value

    def clean_result_value(self, value):
        value = super(UnicodeField, self).clean_result_value(value)
        if not isinstance(value, (str, bytes, bytearray)):
            raise TypeError('{!a} is not a str/bytes/bytearray instance'.format(value))
        value = self._fix_value(value)
        self._validate_value(value)
        return value

    def _fix_value(self, value):
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode(self.encoding, self.decode_error_handling)
            except UnicodeError:
                raise FieldValueError(public_message=(
                    u'"{}" cannot be decoded with encoding "{}"'.format(
                        ascii_str(value),
                        self.encoding)))
        assert isinstance(value, str)
        if self.replace_surrogates:
            value = replace_surrogate_pairs_with_proper_codepoints(
                value,
                replace_unpaired_surrogates_with_fffd=True)
        if self.auto_strip:
            value = value.strip()
        return value

    def _validate_value(self, value):
        if self.disallow_empty and not value:
            raise FieldValueError(public_message=u'The value is empty')


class HexDigestField(UnicodeField):

    """
    For hexadecimal digests (hashes), such as *MD5*, *SHA256* or any other.

    Uppercase letters (``A``-``F``) that values may contain are normalized
    to lowercase.

    The constructor-arguments-or-subclass-attributes:
    :attr:`num_of_characters` (the exact number of characters each hex
    digest consist of) and :attr:`hash_algo_descr` (the digest algorithm
    label, such as ``"MD5"`` or ``"SHA256"``) are obligatory.
    """

    num_of_characters = None
    hash_algo_descr = None

    def __init__(self, **kwargs):
        super(HexDigestField, self).__init__(**kwargs)
        if self.num_of_characters is None:
            raise TypeError("'num_of_characters' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        if self.hash_algo_descr is None:
            raise TypeError("'hash_algo_descr' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        if getattr(self, 'max_length', None) is None:
            self.max_length = self.num_of_characters

    def _fix_value(self, value):
        value = super(HexDigestField, self)._fix_value(value)
        return value.lower()

    def _validate_value(self, value):
        super(HexDigestField, self)._validate_value(value)
        try:
            unhexlify(value)  # Note: only checking (no assignment).
            if len(value) != self.num_of_characters:
                raise ValueError('expected length: {!a} (got: {!a})'.format(
                    self.num_of_characters,
                    len(value)))
        except (TypeError, ValueError):
            raise FieldValueError(public_message=(
                u'"{}" is not a valid {} hash'.format(
                    ascii_str(value),
                    self.hash_algo_descr)))


class MD5Field(HexDigestField):

    """
    For hexadecimal MD5 digests (hashes).
    """

    num_of_characters = 32
    hash_algo_descr = 'MD5'


class SHA1Field(HexDigestField):

    """
    For hexadecimal SHA-1 digests (hashes).
    """

    num_of_characters = 40
    hash_algo_descr = 'SHA1'


class SHA256Field(HexDigestField):

    """
    For hexadecimal SHA-256 digests (hashes).
    """

    num_of_characters = 64
    hash_algo_descr = 'SHA256'


class UnicodeEnumField(UnicodeField):

    """
    For text data limited to a finite set of possible values.

    The constructor-argument-or-subclass-attribute :attr:`enum_values`
    (a sequence or set of strings) is obligatory.
    """

    enum_values = None

    def __init__(self, **kwargs):
        super(UnicodeEnumField, self).__init__(**kwargs)
        if self.enum_values is None:
            raise TypeError("'enum_values' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        self.enum_values = tuple(as_unicode(v) for v in self.enum_values)

    def _validate_value(self, value):
        super(UnicodeEnumField, self)._validate_value(value)
        if value not in self.enum_values:
            raise FieldValueError(public_message=(
                u'"{}" is not one of: {}'.format(
                    ascii_str(value),
                    u', '.join(u'"{}"'.format(v) for v in self.enum_values))))


class UnicodeLimitedField(UnicodeField):

    """
    For text data with limited length.

    The constructor-argument-or-subclass-attribute :attr:`max_length`
    (an integer number greater or equal to 1) is obligatory.
    """

    max_length = None

    def __init__(self, **kwargs):
        super(UnicodeLimitedField, self).__init__(**kwargs)
        if self.max_length is None:
            raise TypeError("'max_length' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        if self.max_length < 1:
            raise ValueError("'max_length' specified for {} should "
                             "not be lesser than 1 ({} given)"
                             .format(self.__class__.__qualname__,
                                     ascii_str(self.max_length)))

    def _validate_value(self, value):
        super(UnicodeLimitedField, self)._validate_value(value)
        if len(value) > self.max_length:
            raise FieldValueTooLongError(
                field=self,
                checked_value=value,
                max_length=self.max_length,
                public_message=(
                    u'Length of "{}" is greater than {}'.format(
                        ascii_str(value),
                        self.max_length)))


class UnicodeLimitedByHypotheticalUTF8BytesLengthField(UnicodeField):

    """
    For text data with limited *hypothetical UTF-8 bytes representation's
    length* (i.e., the length of the possible `bytes` representation, as
    if the ready value was encoded to UTF-8). Note that the value itself
    is still a Unicode string (`str`), *not* `bytes`.

    The constructor-argument-or-subclass-attribute :attr:`max_utf8_bytes`
    (an integer number greater or equal to 1) is obligatory.
    """

    max_utf8_bytes = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.max_utf8_bytes is None:
            raise TypeError(f"'max_utf8_bytes' not specified for "
                            f"{self.__class__.__qualname__} "
                            f"(neither as a class attribute "
                            f"nor as a constructor argument)")
        if self.max_utf8_bytes < 1:
            raise ValueError(f"'max_utf8_bytes' specified for "
                             f"{self.__class__.__qualname__} "
                             f"should not be lesser than 1 "
                             f"({self.max_utf8_bytes!a} given)")

    def _validate_value(self, value):
        super()._validate_value(value)

        max_length = compute_str_index_from_utf8_bytes_index(value, self.max_utf8_bytes)
        if max_length is not None:
            error_msg = (
                f'"{ascii_str(value)}" would take up more than '
                f'{self.max_utf8_bytes} bytes if encoded to UTF-8')

            if self.disallow_empty and max_length <= 0:
                assert max_length == 0
                raise FieldValueError(public_message=(
                    f'{error_msg}; but, at the same time, the '
                    f'value would be empty after trimming'))

            raise FieldValueTooLongError(
                field=self,
                checked_value=value,
                max_length=max_length,
                public_message=error_msg)


class UnicodeRegexField(UnicodeField):

    """
    For text data limited by the specified regular expression.

    The constructor-argument-or-subclass-attribute :attr:`regex`
    (a regular expression specified as a :class:`str` or a
    :class:`str`-pattern-based compiled regular expression
    object) is obligatory.
    """

    regex = None
    error_msg_template = u'"{}" is not a valid value'

    def __init__(self, **kwargs):
        super(UnicodeRegexField, self).__init__(**kwargs)
        if self.regex is None:
            raise TypeError("'regex' not specified for {} "
                            "(neither as a class attribute "
                            "nor as a constructor argument)"
                            .format(self.__class__.__qualname__))
        if isinstance(self.regex, str):
            self.regex = re.compile(self.regex, flags=re.ASCII)
        elif (isinstance(self.regex, bytes)
              or not isinstance(getattr(self.regex, 'pattern', None), str)):
            raise TypeError("for {}, only str-based (*not* "
                            "bytes-based) regular expressions "
                            "are allowed as 'regex' (got: {!a})"
                            .format(self.__class__.__qualname__,
                                    self.regex))

    def _validate_value(self, value):
        super(UnicodeRegexField, self)._validate_value(value)
        if self.regex.search(value) is None:
            raise FieldValueError(public_message=(
                self.error_msg_template.format(ascii_str(value))))


class SourceField(UnicodeLimitedField, UnicodeRegexField):

    """
    For dot-separated source specifications, such as ``my-org.type``.
    """

    regex = SOURCE_REGEX
    error_msg_template = '"{}" is not a valid source specification'
    max_length = 32


class IPv4Field(UnicodeLimitedField, UnicodeRegexField):

    """
    For IPv4 addresses, such as ``127.234.5.17``.

    (Using decimal dotted-quad notation.)
    """

    regex = IPv4_STRICT_DECIMAL_REGEX
    error_msg_template = '"{}" is not a valid IPv4 address'
    max_length = 15  # <- formally redundant but may improve introspection

    # TODO: analyze whether we should change the behavior -- to
    #       accept and maybe also produce `ipaddress.*` objects


class IPv6Field(UnicodeField):

    """
    For IPv6 addresses, such as ``2001:0db8:85a3:0000:0000:8a2e:0370:7334``.

    Note that:

    * when cleaning a parameter value -- the address is normalized to an
      "exploded" form, such as
      ``u'2001:0db8:85a3:0000:0000:8a2e:0370:7334'``;

    * when cleaning a result value -- the address is normalized to a
      "compressed" form, such as ``u'2001:db8:85a3::8a2e:370:7334'``.
    """

    error_msg_template = '"{}" is not a valid IPv6 address'
    max_length = 39  # <- not used at all but may improve introspection

    # TODO later: analyze whether we should change the behavior -- to
    #             accept and maybe also produce `ipaddress.*` objects

    def clean_param_value(self, value):
        ipv6_obj = super(IPv6Field, self).clean_param_value(value)
        return ipv6_obj.exploded

    def clean_result_value(self, value):
        ipv6_obj = super(IPv6Field, self).clean_result_value(value)
        return ipv6_obj.compressed

    def _fix_value(self, value):
        value = super(IPv6Field, self)._fix_value(value)
        try:
            _, _, last_segment = value.rpartition(':')
            if '.' in last_segment and not IPv4_STRICT_DECIMAL_REGEX.search(last_segment):
                raise ValueError('{!a} is not a valid IPv4-like suffix'.format(last_segment))
            ipv6_obj = ipaddress.IPv6Address(value)
        except Exception:
            raise FieldValueError(public_message=(
                self.error_msg_template.format(ascii_str(value))))
        return ipv6_obj


class AnonymizedIPv4Field(UnicodeLimitedField, UnicodeRegexField):

    """
    For anonymized IPv4 addresses, such as ``x.x.5.17``.

    (Using decimal dotted-quad notation, with the leftmost octet -- and
    possibly any other octets -- replaced with "x".)
    """

    regex = IPv4_ANONYMIZED_REGEX
    error_msg_template = '"{}" is not a valid anonymized IPv4 address'
    max_length = 13  # <- formally redundant but may improve introspection

    def _fix_value(self, value):
        value = super(AnonymizedIPv4Field, self)._fix_value(value)
        return value.lower()


class IPv4NetField(UnicodeLimitedField, UnicodeRegexField):

    """
    For IPv4 network specifications (CIDR), such as ``127.234.5.0/24``.

    Note that:

    * when cleaning a parameter value -- an ``(<address part as str>,
      <prefix length part as int>)`` tuple is returned (e.g.,
      ``('127.234.5.0', 24)``); this behavior is provided by the default
      implementation of the :meth:`convert_param_cleaned_string_value`
      method and can be changed by shadowing that method with a subclass
      attribute or a constructor argument;

    * when cleaning a result value -- a :class:`str` is returned
      (e.g., ``'127.234.5.0/24'``).
    """

    regex = IPv4_CIDR_NETWORK_REGEX
    error_msg_template = ('"{}" is not a valid CIDR '
                          'IPv4 network specification')
    max_length = 18  # <- formally redundant but may improve introspection

    accept_bare_ip = False

    # maybe TODO: add + implement support for: trim_host_bits = <False|True> (but first see #8949)

    # TODO: analyze whether we should change the behavior -- to
    #       accept and maybe also produce `ipaddress.*` objects

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.accept_bare_ip:
            self.error_msg_template = self.error_msg_template.replace(
                'is not a valid CIDR IPv4 network specification',
                'is neither a valid CIDR IPv4 network specification '
                'nor a single IPv4 address')

    def clean_param_value(self, value):
        value = super(IPv4NetField, self).clean_param_value(value)
        return self.convert_param_cleaned_string_value(value)

    def convert_param_cleaned_string_value(self, value):
        ip, prefixlen = ip_network_as_tuple(value)
        assert isinstance(ip, str) and IPv4_STRICT_DECIMAL_REGEX.search(ip)
        assert isinstance(prefixlen, int) and 0 <= prefixlen <= 32
        # returning a tuple: `ip` is a str, `prefixlen` is an int
        return ip, prefixlen

    def clean_result_value(self, value):
        if not isinstance(value, (str, bytes, bytearray)):
            try:
                ip, net = value
                value = '{}/{}'.format(as_unicode(ip), as_unicode(net))
            except (ValueError, TypeError):
                raise FieldValueError(public_message=(
                    self.error_msg_template.format(ascii_str(value))))
        # returning a str
        return super(IPv4NetField, self).clean_result_value(value)

    def _fix_value(self, value):
        value = super()._fix_value(value)
        if self.accept_bare_ip and IPv4_STRICT_DECIMAL_REGEX.search(value):
            value = f'{value}/32'
        return value


class IPv6NetField(UnicodeField):

    """
    For IPv6 network specifications (CIDR), such as
    ``2001:0db8:85a3:0000:0000:8a2e:0370:7334/48``.

    Note that:

    * when cleaning a parameter value --

      * a (<address part as str>, <prefix length part as int>) tuple is
        returned (e.g., ``('2001:0db8:85a3:0000:0000:8a2e:0370', 48)``);

      * the address part is normalized to the "exploded" form, such as
        ``2001:0db8:85a3:0000:0000:8a2e:0370:7334``;

      this behavior is provided by the default implementation of the
      :meth:`convert_param_prepared_value` method and can be changed by
      shadowing that method with a subclass attribute or a constructor
      argument;

    * when cleaning a result value --

      * a :class:`str` is returned (e.g.,
        ``'2001:db8:85a3::8a2e:370:7334/48'``);

      * the address part is normalized to the "compressed" form, such as
        ``2001:db8:85a3::8a2e:370:7334``.
    """

    error_msg_template = ('"{}" is not a valid CIDR '
                          'IPv6 network specification')
    max_length = 43  # <- not used at all but may improve introspection

    # TODO later: add + implement support for: accept_bare_ip = <False|True>
    # maybe TODO later: add + implement support for: trim_host_bits = <False|True> (see #8949...)

    # TODO later: analyze whether we should change the behavior -- to
    #             accept and maybe also produce `ipaddress.*` objects

    def clean_param_value(self, value):
        ipv6_obj, prefixlen = super(IPv6NetField, self).clean_param_value(value)
        return self.convert_param_prepared_value(ipv6_obj, prefixlen)

    def convert_param_prepared_value(self, ipv6_obj, prefixlen):
        assert isinstance(ipv6_obj, ipaddress.IPv6Address)
        ipv6 = ipv6_obj.exploded
        assert isinstance(ipv6, str)
        assert isinstance(prefixlen, int) and 0 <= prefixlen <= 128, prefixlen
        # returning a tuple: `ipv6` is a str, `prefixlen` is an int
        return ipv6, prefixlen

    def clean_result_value(self, value):
        if not isinstance(value, (str, bytes, bytearray)):
            try:
                ipv6_raw, prefixlen_raw = value
                value = '{}/{}'.format(as_unicode(ipv6_raw), as_unicode(prefixlen_raw))
            except (ValueError, TypeError):
                raise FieldValueError(public_message=(
                    self.error_msg_template.format(ascii_str(value))))
        ipv6_obj, prefixlen = super(IPv6NetField, self).clean_result_value(value)
        assert isinstance(ipv6_obj, ipaddress.IPv6Address)
        ipv6 = ipv6_obj.compressed
        assert isinstance(ipv6, str)
        assert isinstance(prefixlen, int) and 0 <= prefixlen <= 128, prefixlen
        # returning a str
        return '{}/{}'.format(ipv6, prefixlen)

    def _fix_value(self, value):
        value = super(IPv6NetField, self)._fix_value(value)
        try:
            ipv6_str, prefixlen_str = value.split('/')
            _, _, last_segment = ipv6_str.rpartition(':')
            if '.' in last_segment and not IPv4_STRICT_DECIMAL_REGEX.search(last_segment):
                raise ValueError('{!a} is not a valid IPv4-like suffix '
                                 'of the address part'.format(last_segment))
            ipv6_obj = ipaddress.IPv6Address(ipv6_str)
            prefixlen = int(prefixlen_str)
            if str(prefixlen) != prefixlen_str:
                raise ValueError('{!a} != {!a}'.format(str(prefixlen), prefixlen_str))
            if not 0 <= prefixlen <= 128:
                raise ValueError('{!a} not in range 0..128'.format(prefixlen))
        except Exception:
            raise FieldValueError(public_message=(
                self.error_msg_template.format(ascii_str(value))))
        return ipv6_obj, prefixlen


class CCField(UnicodeLimitedField, UnicodeRegexField):

    """
    For 2-letter country codes, such as ``FR`` or ``UA``.
    """

    regex = CC_SIMPLE_REGEX
    error_msg_template = '"{}" is not a valid 2-character country code'
    max_length = 2   # <- formally redundant but may improve introspection

    def _fix_value(self, value):
        value = super(CCField, self)._fix_value(value)
        return value.upper()


class URLSubstringField(UnicodeLimitedField):

    """
    For substrings of URLs (such as ``xample.com/path?que``).
    """

    max_length = 2048
    decode_error_handling = 'utf8_surrogatepass_and_surrogateescape'


class URLField(URLSubstringField):

    """
    For URLs (such as ``http://xyz.example.com/path?query=foo#fr``).
    """


class DomainNameSubstringField(UnicodeLimitedField):

    """
    For substrings of domain names, automatically IDNA-encoded and lower-cased.
    """

    max_length = 255

    def _fix_value(self, value):
        value = super(DomainNameSubstringField, self)._fix_value(value)
        try:
            value = value.encode('idna')
        except ValueError:
            raise FieldValueError(public_message=(
                u'"{}" could not be encoded using the '
                u'IDNA encoding'.format(ascii_str(value))))
        value = ascii_str(value)
        return value.lower()


class DomainNameField(DomainNameSubstringField, UnicodeRegexField):

    """
    For domain names, automatically IDNA-encoded and lower-cased.
    """

    regex = DOMAIN_ASCII_LOWERCASE_REGEX
    error_msg_template = '"{}" is not a valid domain name'


class EmailSimplifiedField(UnicodeLimitedField, UnicodeRegexField):

    """
    For e-mail addresses.

    (Note: values are *not* normalized in any way, especially the domain
    part is *not* IDNA-encoded or lower-cased.)
    """

    max_length = 254
    regex = EMAIL_SIMPLIFIED_REGEX
    error_msg_template = '"{}" is not a valid e-mail address'


class IBANSimplifiedField(UnicodeLimitedField, UnicodeRegexField):

    """
    For International Bank Account Numbers.
    """

    regex = IBAN_REGEX
    error_msg_template = '"{}" is not a valid IBAN'
    max_length = 34   # <- formally redundant but may improve introspection

    def _fix_value(self, value):
        value = super(IBANSimplifiedField, self)._fix_value(value)
        return value.upper()


class IntegerField(Field):

    """
    For integer numbers (optionally with min./max. limits defined).
    """

    min_value = None
    max_value = None
    error_msg_template = None

    def clean_param_value(self, value):
        value = super(IntegerField, self).clean_param_value(value)
        return self._clean_value(value)

    def clean_result_value(self, value):
        value = super(IntegerField, self).clean_result_value(value)
        return self._clean_value(value)

    def _clean_value(self, value):
        try:
            value = self._coerce_value(value)
            self._check_range(value)
        except FieldValueError:
            if self.error_msg_template is None:
                raise
            raise FieldValueError(public_message=(
                self.error_msg_template.format(ascii_str(value))))
        return value

    def _coerce_value(self, value):
        try:
            coerced_value = self._do_coerce(value)
            # e.g. float is OK *only* if it is an integer number (such as 42.0)
            if not isinstance(value, (str, bytes, bytearray)) and coerced_value != value:
                raise ValueError
        except (TypeError, ValueError):
            raise FieldValueError(public_message=(
                u'"{}" cannot be interpreted as an '
                u'integer number'.format(ascii_str(value))))
        assert isinstance(coerced_value, int)
        return coerced_value

    def _do_coerce(self, value):
        return int(value)

    def _check_range(self, value):
        assert isinstance(value, int)
        if self.min_value is not None and value < self.min_value:
            raise FieldValueError(public_message=(
                u'{} is lesser than {}'.format(value, self.min_value)))
        if self.max_value is not None and value > self.max_value:
            raise FieldValueError(public_message=(
                u'{} is greater than {}'.format(value, self.max_value)))


class ASNField(IntegerField):

    """
    For AS numbers, such as ``12345``, ``123456789`` or ``12345.65432``.
    """

    min_value = 0
    max_value = 2 ** 32 - 1
    error_msg_template = '"{}" is not a valid Autonomous System Number'

    def _do_coerce(self, value):
        if isinstance(value, (str, bytes, bytearray)):
            if isinstance(value, (bytes, bytearray)):
                value = value.decode('utf-8')
            # numbers prefixed with 'AS<optional blank characters>'
            # or 'ASN<optional blank characters>' (checked in a
            # case-insensitive manner) are also accepted
            value_lower = value.lower()
            if value_lower.startswith(('as', 'asn')):
                prefix_len = (3 if value_lower.startswith('asn')
                              else 2)
                value = value[prefix_len:].lstrip()
            # supporting also the '<16-bit number>.<16-bitnumber>' ASN notation;
            if '.' in value:
                high, low = map(int, value.split('.'))
                if not (0 <= low <= 65535):  # (high is checked later)
                    raise ValueError
                return (high << 16) + low
            else:
                return int(value)
        elif isinstance(value, int):
            return int(value)
        else:
            # not accepting e.g. floats, to avoid the '42.0'/42.0-confusion
            # ('42.0' gives 42 * 2**16 but 42.0 would give 42 if were accepted)
            raise TypeError


class PortField(IntegerField):

    """
    For TCP/UDP port numbers, such as ``12345``.
    """

    min_value = 0
    max_value = 2 ** 16 - 1
    error_msg_template = '"{}" is not a valid port number'


class ResultListFieldMixin(Field):

    """
    A mix-in class for fields whose result values are supposed to be
    a *sequence of values* and not single values.

    Its :meth:`clean_result_value` checks that its argument is a
    *non-string sequence* (:class:`list` or :class:`tuple`, or any other
    :class:`collections.abc.Sequence`, but *not* a :class:`str` or
    :class:`bytes`/:class:`bytearray`) and performs result cleaning (as
    defined in a superclass) for *each item* of it.  The resultant value
    is always an ordinary :class:`list`.

    The class provides two optional
    constructor-arguments-or-subclass-attributes:

    * :attr:`allow_empty` (default value: :obj:`False` which means that
      an empty sequence causes a cleaning error; specify as :obj:`True`
      to resign from applying this constraint);

    * :attr:`sort_result_list` (default value: :obj:`False`; if
      specified as :obj:`True` the :meth:`~list.sort` method will
      automatically be called on a resultant list; a
      :class:`collections.abc.Mapping` instance can also be specified --
      then it will specify the keyword arguments to be used for each
      such :meth:`~list.sort` call).

    See also the subclasses of this class: :class:`ListOfDictsField`,
    :class:`AddressField` and :class:`ExtendedAddressField`.
    """

    allow_empty = False
    sort_result_list = False

    def clean_result_value(self, value):
        if not is_seq(value):
            raise TypeError('{!a} is not a *non*-str/bytes/bytearray '
                            'sequence'.format(value))
        if not self.allow_empty and not value:
            raise ValueError('empty sequence given')
        do_clean = super(ResultListFieldMixin, self).clean_result_value
        return self._clean_result_list(value, do_clean)

    def _clean_result_list(self, value, do_clean):
        checked_value_list = []
        too_long = False
        for v in value:
            try:
                v = do_clean(v)
            except FieldValueTooLongError as exc:
                if exc.field is not self:
                    raise
                too_long = True
                assert hasattr(self, 'max_length')
                assert exc.max_length == self.max_length
                v = exc.checked_value
            checked_value_list.append(v)
        if too_long:
            raise FieldValueTooLongError(
                field=self,
                checked_value=checked_value_list,
                max_length=self.max_length,
                public_message=(
                    u'Length of at least one item of '
                    u'list {} is greater than {}'.format(
                        ascii_str(value),
                        self.max_length)))
        if isinstance(self.sort_result_list, collections_abc.Mapping):
            checked_value_list.sort(**self.sort_result_list)
        elif self.sort_result_list:
            checked_value_list.sort()
        return checked_value_list


class DictResultField(Field):

    """
    A base class for fields whose result values are supposed to be
    dictionaries.

    The constructor-argument-or-subclass-attribute
    :attr:`key_to_subfield_factory` can be:

    * specified as a dictionary that maps *subfield keys* (being
      ASCII-only :class:`str` or :obj:`None`) to *field factories*
      (typically, just :class:`Field` subclasses) -- then processed data
      dictionaries are constrained and cleaned in the following way:

      * each *key* in a processed data dictionary **must** be one of
        *subfield keys* -- **unless** *subfield keys* include the
        :obj:`None` key,

      * each *key* in a processed data dictionary **must** be an
        ASCII-only :class:`str`,

      * each *value* from a processed data dictionary **is cleaned**
        with :meth:`clean_result_value` of a field object produced by
        the *field factory* specified under the corresponding *key* or
        -- if *subfield keys* do not include that *key* but do include
        :obj:`None` -- the *factory* specified under the :obj:`None` key
        (in other words, the :obj:`None` key -- if *subfield keys*
        include it -- plays the role of the *default field factory*
        key);

    * left as :obj:`None` -- then there are no constraints about
      structure and content of processed data dictionaries, except that
      their keys **must** be ASCII-only :class:`str` strings.

    Note: in the above description, whenever we say about a *processed
    data dictionary* we mean a dictionary being a value cleaned with
    this field's :meth:`clean_result_value` (we do *not* mean a whole
    *result dictionary* which is cleaned with *data specification's*
    :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict`).
    """

    key_to_subfield_factory = None

    def __init__(self, **kwargs):
        super(DictResultField, self).__init__(**kwargs)
        if self.key_to_subfield_factory is None:
            self.key_to_subfield = None
            self.default_subfield = None
        else:
            self.key_to_subfield = {
                self._adjust_key(key): factory()
                for key, factory in self.key_to_subfield_factory.items()
                if key is not None}
            default_subfield_factory = self.key_to_subfield_factory.get(None)
            self.default_subfield = (
                default_subfield_factory()
                if default_subfield_factory is not None
                else None)

    def clean_param_value(self, value):
        """Always raises :exc:`~exceptions.TypeError`."""
        raise TypeError("it's a result-only field")

    def clean_result_value(self, value):
        value = super(DictResultField, self).clean_result_value(value)
        if not isinstance(value, collections_abc.Mapping):
            raise TypeError('{!a} is not a mapping'.format(value))
        keys = frozenset(value)
        illegal_keys_msg_seq = list(map(ascii_str, self._generate_illegal_keys_msg(keys)))
        if illegal_keys_msg_seq:
            raise ValueError(
                  '{!a} contains illegal keys ({})'.format(
                      value,
                      ', '.join(illegal_keys_msg_seq)))
        missing_keys_msg_seq = list(map(ascii_str, self._generate_missing_keys_msg(keys)))
        if missing_keys_msg_seq:
            raise ValueError(
                  '{!a} does not contain required keys ({})'.format(
                      value,
                      ', '.join(missing_keys_msg_seq)))
        if self.key_to_subfield is None:
            value = {
                self._adjust_key(k): v
                for k, v in value.items()}
        elif self.default_subfield is None:
            value = {
                self._adjust_key(k): self.key_to_subfield[k].clean_result_value(v)
                for k, v in value.items()}
        else:
            value = {
                self._adjust_key(k):
                    self.key_to_subfield.get(k, self.default_subfield).clean_result_value(v)
                for k, v in value.items()}
        return value

    def _adjust_key(self, key):
        return verified_as_ascii_str(key)

    def _generate_illegal_keys_msg(self, keys):
        if self.key_to_subfield is not None and self.default_subfield is None:
            illegal_keys = keys - self.key_to_subfield.keys()
            yield from sorted(map(repr, illegal_keys))

    def _generate_missing_keys_msg(self, keys):
        yield from ()


class ListOfDictsField(ResultListFieldMixin, DictResultField):

    """
    For lists of dictionaries containing arbitrary items.

    The constructor-argument-or-subclass-attribute :attr:`must_be_unique`
    should be an iterable container (by default it is en empty tuple),
    but *not* a :class:`str` or :class:`bytes`/:class:`bytearray`. If
    the container is not empty it should consist of one or more
    dictionary keys whose corresponding values will have to be unique
    within a particular list of dictionaries (or
    :class:`~exceptions.ValueError` will be raised).
    """

    must_be_unique = ()

    def __init__(self, **kwargs):
        super(ListOfDictsField, self).__init__(**kwargs)
        if isinstance(self.must_be_unique, (str, bytes, bytearray)):
            raise TypeError("{}'s 'must_be_unique' is expected to "
                            "be an iterable container, but not a "
                            "str/bytes/bytearray (got: {!a})".format(
                                self.__class__.__qualname__,
                                self.must_be_unique))

    def clean_result_value(self, value):
        value = super(ListOfDictsField, self).clean_result_value(value)
        nonunique = set(self._iter_keys_of_nonunique(value))
        if nonunique:
            raise ValueError(
                'non-unique items within dictionaries (keys: {})'.format(
                    ', '.join(sorted(map(ascii, nonunique)))))
        return value

    def _iter_keys_of_nonunique(self, value):
        for key in self.must_be_unique:
            items = [di[key] for di in value
                     if key in di]
            if len(set(items)) != len(items):
                yield key


class AddressField(ListOfDictsField):

    """
    For lists of dictionaries -- each containing ``"ip"`` and optionally
    ``"cc"`` and/or ``"asn"``.
    """

    key_to_subfield_factory = {
        u'ip': IPv4Field,
        u'cc': CCField,
        u'asn': ASNField,
    }
    must_be_unique = ('ip',)

    def _generate_missing_keys_msg(self, keys):
        yield from super()._generate_missing_keys_msg(keys)
        if 'ip' not in keys:
            yield "'ip'"


class DirField(UnicodeEnumField):

    """
    For ``dir`` values in items cleaned by of
    :class:`ExtendedAddressField` instances (``dir`` marks role of the
    address in terms of the direction of the network flow in layers 3 or
    4).
    """

    enum_values = ('src', 'dst')


class ExtendedAddressField(ListOfDictsField):

    """
    For lists of dictionaries -- each containing either ``"ip"`` or
    ``"ipv6"`` (but not both), and optionally all or some of: ``"cc"``,
    ``"asn"``, ``"dir"``, ``"rdns"``.
    """

    key_to_subfield_factory = {
        u'ip': IPv4Field,
        u'ipv6': IPv6Field,
        u'cc': CCField,
        u'asn': ASNField,
        u'dir': DirField,
        u'rdns': DomainNameField,
    }
    must_be_unique = ('ip', 'ipv6')

    def _generate_illegal_keys_msg(self, keys):
        yield from super()._generate_illegal_keys_msg(keys)
        if 'ip' in keys and 'ipv6' in keys:
            yield "'ip' or 'ipv6' [only one of these two should be specified]"

    def _generate_missing_keys_msg(self, keys):
        yield from super()._generate_missing_keys_msg(keys)
        if 'ip' not in keys and 'ipv6' not in keys:
            yield "'ip' or 'ipv6' [one of these two should be specified]"

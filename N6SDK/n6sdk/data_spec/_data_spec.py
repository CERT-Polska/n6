# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 NASK. All rights reserved.


import collections

from pyramid.decorator import reify

from n6sdk.data_spec.fields import (
    Field,
    AnonymizedIPv4Field,
    ASNField,
    CCField,
    DateTimeField,
    DomainNameField,
    DomainNameSubstringField,
    EmailSimplifiedField,
    ExtendedAddressField,
    IBANSimplifiedField,
    IntegerField,
    IPv4Field,
    IPv4NetField,
    IPv6Field,
    IPv6NetField,
    ListOfDictsField,
    MD5Field,
    PortField,
    SHA1Field,
    SourceField,
    UnicodeEnumField,
    UnicodeLimitedField,
    URLField,
    URLSubstringField,
)
from n6sdk.exceptions import (
    FieldValueError,
    ParamKeyCleaningError,
    ParamValueCleaningError,
    ResultKeyCleaningError,
    ResultValueCleaningError,
    _KeyCleaningErrorMixin,
)



#
# Constants

RESTRICTION_ENUMS = (
    'public', 'need-to-know', 'internal',
)

CONFIDENCE_ENUMS = (
    'low', 'medium', 'high',
)

CATEGORY_ENUMS = (
    'amplifier',
    'bots',
    'backdoor',
    'cnc',
    'deface',
    'dns-query',
    'dos-attacker',
    'dos-victim',
    'flow',
    'flow-anomaly',
    'fraud',
    'leak',
    'malurl',
    'malware-action',
    'other',
    'phish',
    'proxy',
    'sandbox-url',
    'scam',
    'scanning',
    'server-exploit',
    'spam',
    'spam-url',
    'tor',
    'vulnerable',
    'webinject',
)

PROTO_ENUMS = (
    'tcp', 'udp', 'icmp',
)

ORIGIN_ENUMS = (
    'c2',
    'dropzone',
    'proxy',
    'p2p-crawler',
    'p2p-drone',
    'sinkhole',
    'sandbox',
    'honeypot',
    'darknet',
    'av',
    'ids',
    'waf',
)

STATUS_ENUMS = (
    'active', 'delisted', 'expired', 'replaced',
)



#
# Auxiliary classes

class Ext(dict):

    """
    An auxiliary class of a :class:`dict`-like container -- to be used
    to extend field specifications in :class:`DataSpec` subclasses (for
    usage examples, see the descriptions of :class:`DataSpec` and
    :class:`AllSearchableDataSpec`).
    """

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               super(Ext, self).__repr__())

    def copy(self):
        return self.__class__(self)

    def make_extended_field(self, field):
        merged_init_kwargs = self.copy()
        merged_init_kwargs.nondestructive_update(field._init_kwargs)
        return field.__class__(**merged_init_kwargs)

    def nondestructive_update(self, other):
        if isinstance(other, collections.Mapping):
            other = other.iteritems()
        for key, value in other:
            stored_value = self.setdefault(key, value)
            if (stored_value is not value) and isinstance(stored_value, Ext):
                if isinstance(value, Field):
                    self[key] = stored_value.make_extended_field(value)
                elif isinstance(value, collections.Mapping):
                    merged_value = stored_value.copy()
                    merged_value.nondestructive_update(value)
                    self[key] = merged_value



#
# The abstract base class for any data specification classes

class BaseDataSpec(object):

    """
    The base class for data specification classes.

    Typically, you will not instantiate or subclass this class directly
    -- instead, you may want to use :class:`DataSpec` or, more likely, a
    subclass of it.
    """

    def __init__(self, **kwargs):
        self._all_param_fields = {}
        self._required_param_fields = {}
        self._single_param_fields = {}
        self._all_result_fields = {}
        self._required_result_fields = {}

        self._set_fields()

        super(BaseDataSpec, self).__init__(**kwargs)


    #
    # public properties

    @reify
    def all_keys(self):
        """
        Instance property: a :class:`frozenset` of all keys.

        (Includes all legal parameter names and result keys.)
        """
        return self.all_param_keys | self.all_result_keys

    @reify
    def all_param_keys(self):
        """
        Instance property: a :class:`frozenset` of all legal parameter names.
        """
        return frozenset(self._all_param_fields)

    @reify
    def all_result_keys(self):
        """
        Instance property: a :class:`frozenset` of all legal result keys.
        """
        return frozenset(self._all_result_fields)


    #
    # public methods (possibly extendable)

    def clean_param_dict(self, params,
                         # optional keyword arguments:
                         ignored_keys=(),
                         forbidden_keys=(),
                         extra_required_keys=(),
                         discarded_keys=()):
        """
        Clean client query parameters.

        Args:
            `params` (:class:`dict`):
                A dictionary that maps strings being query parameter
                keys (param field names) to lists of *raw (uncleaned)*
                values of these parameters.

        Kwargs (each being an iterable container, empty by default):
            `ignored_keys`: to be treated as they did not exist at all;
            `forbidden_keys`: presence of any triggers an error;
            `extra_required_keys`: lack of any triggers an error;
            `discarded_keys`: to be omitted (after validation of keys).

        Returns:
            A new dictionary that maps query parameter keys (param field
            names) to lists of *cleaned* values of these parameters.

        Raises:
            An instance of a subclass of
            :exc:`~n6sdk.exceptions.ParamCleaningError`:
            :exc:`~n6sdk.exceptions.ParamKeyCleaningError` or
            :exc:`~n6sdk.exceptions.ParamValueCleaningError`.

        .. seealso::

           For more information -- see :ref:`data_spec_cleaning_methods`
           in the tutorial.

        .. warning::

           The method should **never** modify the given dictionary (or
           any of its values).  It should always return a new
           dictionary.
        """
        keys = self._clean_keys(
            params.viewkeys() - frozenset(ignored_keys),
            self._all_param_fields.viewkeys() - frozenset(forbidden_keys),
            self._required_param_fields.viewkeys() | frozenset(extra_required_keys),
            frozenset(discarded_keys),
            exc_class=ParamKeyCleaningError)
        return dict(self._iter_clean_param_items(params, keys))

    def clean_result_dict(self, result,
                          # optional keyword arguments:
                          ignored_keys=(),
                          forbidden_keys=(),
                          extra_required_keys=(),
                          discarded_keys=()):
        """
        Clean a single result record.

        Args:
            `result` (:class:`dict`):
                A dictionary that maps strings being result keys (result
                field names) to corresponding *raw (uncleaned)* values.

        Kwargs (each being an iterable container, empty by default):
            `ignored_keys`: to be treated as they did not exist at all;
            `forbidden_keys`: presence of any triggers an error;
            `extra_required_keys`: lack of any triggers an error;
            `discarded_keys`: to be omitted (after validation of keys).

        Returns:
            Either a new dictionary that maps result keys (result field
            names) to corresponding *cleaned* values, or :obj:`None`.
            Returning :obj:`None` means that this particular network
            incident shall be skipped, i.e., the generated response will
            *not* include it (note, however, that the default
            implementation of this method never returns :obj:`None`).

        Raises:
            An instance of a subclass of
            :exc:`~n6sdk.exceptions.ResultCleaningError`:
            :exc:`~n6sdk.exceptions.ResultKeyCleaningError` or
            :exc:`~n6sdk.exceptions.ResultValueCleaningError`.

        .. seealso::

           For more information -- see :ref:`data_spec_cleaning_methods`
           in the tutorial.

        .. warning::

           The method should **never** modify the given dictionary (or
           any of its values).  It should always return a new dictionary
           or :obj:`None`.
        """
        keys = self._clean_keys(
            result.viewkeys() - frozenset(ignored_keys),
            self._all_result_fields.viewkeys() - frozenset(forbidden_keys),
            self._required_result_fields.viewkeys() | frozenset(extra_required_keys),
            frozenset(discarded_keys),
            exc_class=ResultKeyCleaningError)
        return dict(self._iter_clean_result_items(result, keys))

    def param_field_specs(self, which='all', multi=True, single=True, **kwargs):
        """
        Get selected *param field* specifications.

        Args/kwargs:
            `which` (optional; default: ``'all'``):
                The token the fields are to be selected by.  To be
                passed directly into :meth:`filter_by_which`.
            `multi` (optional; default: :obj:`True`):
                If *false* the fields initialized **without**
                ``single_param=True`` will be excluded.
            `single` (optional; default: :obj:`True`):
                If *false* the fields initialized **with**
                ``single_param=True`` will be excluded.

        Other kwargs:
            Any extra keyword arguments will be passed directly into
            :meth:`filter_by_which`.

        Returns:
            A new ``{<field key>: <Field instance>, ...}`` :class:`dict`
            including the selected *param fields*.

        Raises:
            The default implementation of this method just propagates
            any exceptions thrown by :meth:`filter_by_which`.
        """
        field_items = self.filter_by_which(
            which,
            self._all_param_fields,
            self._required_param_fields,
            **kwargs)
        if not multi:
            field_items &= self._single_param_fields.viewitems()
        if not single:
            field_items -= self._single_param_fields.viewitems()
        return dict(field_items)

    def result_field_specs(self, which='all', **kwargs):
        """
        Get selected *result field* specifications.

        Args/kwargs:
            `which` (optional; default: ``'all'``):
                The token the fields are to be selected by.  To be
                passed directly into :meth:`filter_by_which`.

        Other kwargs:
            Any extra keyword arguments will be passed directly into
            :meth:`filter_by_which`.

        Returns:
            A new ``{<field key>: <Field instance>, ...}`` :class:`dict`
            including the selected *result fields*.

        Raises:
            The default implementation of this method just propagates
            any exceptions thrown by :meth:`filter_by_which`.
        """
        return dict(self.filter_by_which(
            which,
            self._all_result_fields,
            self._required_result_fields,
            **kwargs))


    #
    # overridable/extendable methods

    @classmethod
    def filter_by_which(cls, which, all_fields_dict, required_fields_dict):
        """
        Select fields that match the `which` argument (called by the
        :meth:`param_field_specs` and :meth:`result_field_specs`
        methods).

        Args:
            `which`:
                The token the fields are to be selected by.  The default
                implementation of this method supports only the values:
                ``'all'``, ``'required'``, ``'optional'``.
            `all_fields_dict`:
                A ``{<field key>: <Field instance>, ...}`` :class:`dict`
                that includes **all** data specification's *param
                fields* **or** *result fields* (apropriately --
                depending on whether this method is being called by
                :meth:`param_field_specs` or :meth:`result_field_specs`).
            `required_fields_dict`:
                A :class:`dict` similar to `all_fields_dict` but
                including all **required** *param fields* **or** *result
                fields* (apropriately...).

        Kwargs:
            The default implementation of this method does *not* accept
            any additional keyword arguments but in subclasses the
            method can be extended to accept some (note that
            :meth:`param_field_specs` and :meth:`result_field_specs`
            always pass any extra keyword arguments into this method).

        Returns:
            A container of ``(<field key>, <Field instance>)`` tuples.
            It includes the field selected by `which`.

            The returned container must be an object that is a *dict
            items view* or a *set-like* object, i.e., an object that:

            * either is a result of a ``<dict instance>.viewitems()``
              call

            * or satisfies the ``isinstance(<the set-like object>,
              collections.Set)`` condition.

        Raises:
            :exc:`~exceptions.ValueError` if the `which` argument is not
            valid.
        """
        all_fields = all_fields_dict.viewitems()
        required_fields = required_fields_dict.viewitems()
        assert required_fields <= all_fields
        if which == 'all':
            return all_fields
        elif which == 'required':
            return required_fields
        elif which == 'optional':
            return all_fields - required_fields
        raise ValueError(
            "{!r} is not one of: 'all', 'required', 'optional'"
            .format(which))


    def get_adjusted_field(self, key, field, ext=None):
        if ext is not None:
            field = ext.make_extended_field(field)
        return field


    #
    # non-public internals

    def _set_fields(self):
        key_to_field = {}
        for key, field in self._iter_all_field_specs():
            key = key.decode('ascii')
            key_to_field[key] = field
            if field.in_params is not None:
                self._all_param_fields[key] = field
                if field.in_params == 'required':
                    self._required_param_fields[key] = field
                else:
                    assert field.in_params == 'optional'
                if field.single_param:
                    self._single_param_fields[key] = field
            if field.in_result is not None:
                self._all_result_fields[key] = field
                if field.in_result == 'required':
                    self._required_result_fields[key] = field
                else:
                    assert field.in_result == 'optional'
        # making all fields (including those Ext-updated)
        # accessible also as instance attributes
        vars(self).update(key_to_field)

    def _iter_all_field_specs(self):
        key_to_ext = collections.defaultdict(Ext)
        seen_keys = set()
        attr_containers = (self,) + self.__class__.__mro__
        for ac in attr_containers:
            for key, obj in vars(ac).iteritems():
                if isinstance(obj, Ext):
                    key_to_ext[key].nondestructive_update(obj)
                    continue
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if isinstance(obj, Field):
                    field_ext = key_to_ext.get(key)
                    field = self.get_adjusted_field(key, obj, field_ext)
                    yield key, field
                    for extra in self._iter_extra_param_specs(key, field):
                        yield extra

    def _iter_extra_param_specs(self, key, parent_field):
        for key_suffix, xfield in parent_field.extra_params.iteritems():
            if xfield is None:
                # field was masked ("removed") using Ext, e.g. in a subclass
                continue
            if not isinstance(xfield, Field):
                raise TypeError('{!r} is not a {!r} instance'
                                .format(xfield, Field))
            xkey = '{}.{}'.format(key, key_suffix)
            xfield = self.get_adjusted_field(xkey, xfield)
            yield xkey, xfield
            # recursive yielding:
            for extra in self._iter_extra_param_specs(xkey, xfield):
                yield extra

    @staticmethod
    def _clean_keys(keys, legal_keys, required_keys, discarded_keys,
                    exc_class):
        illegal_keys = keys - legal_keys
        missing_keys = required_keys - keys
        if illegal_keys or missing_keys:
            assert issubclass(exc_class, _KeyCleaningErrorMixin)
            raise exc_class(illegal_keys, missing_keys)
        return {key.decode('ascii') for key in (keys - discarded_keys)}

    def _iter_clean_param_items(self, params, keys):
        error_info_seq = []
        for key in keys:
            assert key in self._all_param_fields
            assert key in params
            field = self._all_param_fields[key]
            param_values = params[key]
            assert param_values and type(param_values) is list
            assert hasattr(field, 'single_param')
            if field.single_param and len(param_values) > 1:
                error_info_seq.append((
                    key,
                    param_values,
                    FieldValueError(public_message=(
                        u'Multiple values for a single-value-only field.'))
                ))
            else:
                cleaned_values = []
                for value in param_values:
                    try:
                        cleaned_val = field.clean_param_value(value)
                    except Exception as exc:
                        error_info_seq.append((key, value, exc))
                    else:
                        cleaned_values.append(cleaned_val)
                if cleaned_values:
                    yield key, cleaned_values
        if error_info_seq:
            raise ParamValueCleaningError(error_info_seq)

    def _iter_clean_result_items(self, result, keys):
        error_info_seq = []
        for key in keys:
            assert key in self._all_result_fields
            assert key in result
            field = self._all_result_fields[key]
            value = result[key]
            try:
                yield key, field.clean_result_value(value)
            except Exception as exc:
                error_info_seq.append((key, value, exc))
        if error_info_seq:
            raise ResultValueCleaningError(error_info_seq)



#
# Concrete data specification base classes

class DataSpec(BaseDataSpec):

    """
    The basic, ready-to-use, data specification class.

    Typically, you will want to create a subclass of it (note that, by
    default, all fields are *disabled as query parameters*, so you may
    want to *enable* some of them).  For example::

        class MyDataSpec(DataSpec):

            # enable `source` as a query parameter
            source = Ext(in_params='optional')

            # enable the `time.min` and `time.until` query parameters
            # (leaving `time.max` still disabled)
            time = Ext(
                extra_params=Ext(
                    min=Ext(in_params='optional'),
                    until=Ext(in_params='optional'),
                ),
            )

            # enable `fqdn` and `fqdn.sub` as query parameters
            # and add a new query parameter: `fqdn.prefix`
            fqdn = Ext(
                in_params='optional',
                extra_params=Ext(
                    sub=Ext(in_params='optional'),
                    prefix=DomainNameSubstringField(in_params='optional'),
                ),
            )

            # completely disable the `modified` field
            modified = None

            # add a new field
            weekday = UnicodeEnumField(
                in_params='optional',
                in_result='optional',
                enum_values=(
                    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday'),
                ),
            )

    .. seealso::

        Compare this class with :class:`AllSearchableDataSpec`.
    """

    #
    # Fields that are always *required in results*

    id = UnicodeLimitedField(
        in_result='required',
        max_length=64,
    )

    source = SourceField(
        in_result='required',
    )

    restriction = UnicodeEnumField(
        in_result='required',
        enum_values=RESTRICTION_ENUMS,
    )

    confidence = UnicodeEnumField(
        in_result='required',
        enum_values=CONFIDENCE_ENUMS,
    )

    category = UnicodeEnumField(
        in_result='required',
        enum_values=CATEGORY_ENUMS,
    )

    time = DateTimeField(
        in_params=None,  # <- should be None even in subclasses
        in_result='required',

        extra_params=dict(
            min=DateTimeField(          # `time.min`
                single_param=True,
            ),
            max=DateTimeField(          # `time.max`
                single_param=True,
            ),
            until=DateTimeField(        # `time.until`
                single_param=True,
            ),
        ),
    )

    #
    # Fields related to `address`

    # an `address` is a list of dicts -- each containing either
    # `ip` or `ipv6` (but not both) and optionally some or all of:
    # `asn`, `cc`, `dir`, `rdns`
    address = ExtendedAddressField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',
    )

    # query params related to the components of `address` items

    ip = IPv4Field(
        in_result=None,  # <- should be None even in subclasses
        extra_params=dict(
            net=IPv4NetField(),         # `ip.net`
        ),
    )

    ipv6 = IPv6Field(
        in_result=None,  # <- should be None even in subclasses
        extra_params=dict(
            net=IPv6NetField(),         # `ipv6.net`
        ),
    )

    asn = ASNField(
        in_result=None,  # <- should be None even in subclasses
    )

    cc = CCField(
        in_result=None,  # <- should be None even in subclasses
    )

    #
    # Fields related only to black list events

    active = Field(
        in_params=None,  # <- should be None even in subclasses
        in_result=None,  # <- typically will be None even in subclasses

        extra_params=dict(
            min=DateTimeField(          # `active.min`
                single_param=True,
            ),
            max=DateTimeField(          # `active.max`
                single_param=True,
            ),
            until=DateTimeField(        # `active.until`
                single_param=True,
            ),
        ),
    )

    expires = DateTimeField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',
    )

    replaces = UnicodeLimitedField(
        in_result='optional',
        max_length=64,
    )

    status = UnicodeEnumField(
        in_result='optional',
        enum_values=STATUS_ENUMS,
    )

    #
    # Fields related only to aggregated (high frequency) events

    count = IntegerField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',
        min_value=0,
        max_value=(2 ** 15 - 1),
    )

    until = DateTimeField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',
    )

    #
    # Other fields

    action = UnicodeLimitedField(
        in_result='optional',
        max_length=32,
    )

    adip = AnonymizedIPv4Field(
        in_result='optional',
    )

    dip = IPv4Field(
        in_result='optional',
    )

    dport = PortField(
        in_result='optional',
    )

    email = EmailSimplifiedField(
        in_result='optional',
    )

    fqdn = DomainNameField(
        in_result='optional',

        extra_params=dict(
            sub=DomainNameSubstringField(),  # `fqdn.sub`
        ),
    )

    iban = IBANSimplifiedField(
        in_result='optional',
    )

    injects = ListOfDictsField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',
    )

    md5 = MD5Field(
        in_result='optional',
    )

    modified = DateTimeField(
        in_params=None,  # <- should be None even in subclasses
        in_result='optional',

        extra_params=dict(
            min=DateTimeField(          # `modified.min`
                single_param=True,
            ),
            max=DateTimeField(          # `modified.max`
                single_param=True,
            ),
            until=DateTimeField(        # `modified.until`
                single_param=True,
            ),
        ),
    )

    name = UnicodeLimitedField(
        in_result='optional',
        max_length=255,
    )

    origin = UnicodeEnumField(
        in_result='optional',
        enum_values=ORIGIN_ENUMS,
    )

    phone = UnicodeLimitedField(
        in_result='optional',
        max_length=20,
    )

    proto = UnicodeEnumField(
        in_result='optional',
        enum_values=PROTO_ENUMS,
    )

    registrar = UnicodeLimitedField(
        in_result='optional',
        max_length=100,
    )

    sha1 = SHA1Field(
        in_result='optional',
    )

    sport = PortField(
        in_result='optional',
    )

    target = UnicodeLimitedField(
        in_result='optional',
        max_length=100,
    )

    url = URLField(
        in_result='optional',
        extra_params=dict(
            sub=URLSubstringField(),    # `url.sub`
        ),
    )

    url_pattern = UnicodeLimitedField(
        in_result='optional',
        max_length=255,
        disallow_empty=True,
    )

    username = UnicodeLimitedField(
        in_result='optional',
        max_length=64,
    )

    x509fp_sha1 = SHA1Field(
        in_result='optional',
    )



class AllSearchableDataSpec(DataSpec):

    """
    A :class:`DataSpec` subclass with most of its fields marked as searchable.

    You may want to use this class instead of :class:`DataSpec` if your
    data backend makes it easy to search by various event attributes
    (all relevant ones or most of them).

    Typically, you will want to create your own subclass of
    :class:`AllSearchableDataSpec` (especially to *disable* some
    searchable parameters).  For example::

        class MyDataSpec(AllSearchableDataSpec):

            # disable `source` as a query parameter
            source = Ext(in_params=None)

            # disable the `time.max` query parameter
            # (leaving `time.min` and `time.until` still enabled)
            time = Ext(
                extra_params=Ext(
                    max=Ext(in_params=None),
                ),
            )

            # disable the `fqdn.sub` query parameter and, at the
            # same time, add a new query parameter: `fqdn.prefix`
            fqdn = Ext(
                extra_params=Ext(
                    sub=Ext(in_params=None),
                    prefix=DomainNameSubstringField(in_params='optional'),
                ),
            )

            # completely disable the `modified` field (together with the
            # related "extra params": `modified.min` etc.)
            modified = None

            # add a new field
            weekday = UnicodeEnumField(
                in_params='optional',
                in_result='optional',
                enum_values=(
                    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday'),
                ),
            )

    .. seealso::

        Compare this class with :class:`DataSpec`.
    """

    #
    # Fields that are always *required in results*

    id = Ext(in_params='optional')

    source = Ext(in_params='optional')

    restriction = Ext(in_params='optional')

    confidence = Ext(in_params='optional')

    category = Ext(in_params='optional')

    time = Ext(
        extra_params=Ext(
            min=Ext(in_params='optional'),
            max=Ext(in_params='optional'),
            until=Ext(in_params='optional'),
        ),
    )

    #
    # Fields related to `address`

    # (the `address` field from the superclass remains unchanged)

    ip = Ext(
        in_params='optional',
        extra_params=Ext(
            net=Ext(in_params='optional'),
        ),
    )

    ipv6 = Ext(
        in_params='optional',
        extra_params=Ext(
            net=Ext(in_params='optional'),
        ),
    )

    asn = Ext(in_params='optional')

    cc = Ext(in_params='optional')

    #
    # Fields related only to black list events

    active = Ext(
        extra_params=Ext(
            min=Ext(in_params='optional'),
            max=Ext(in_params='optional'),
            until=Ext(in_params='optional'),
        ),
    )

    # (the `expires` field from the superclass remains unchanged)

    replaces = Ext(in_params='optional')

    status = Ext(in_params='optional')

    #
    # Fields related only to aggregated (high frequency) events

    # (the `count` field from the superclass remains unchanged)
    # (the `until` field from the superclass remains unchanged)

    #
    # Other fields

    action = Ext(in_params='optional')

    # (the `adip` field from the superclass remains unchanged)

    dip = Ext(in_params='optional')

    dport = Ext(in_params='optional')

    email = Ext(in_params='optional')

    fqdn = Ext(
        in_params='optional',
        extra_params=Ext(
            sub=Ext(in_params='optional'),
        ),
    )

    iban = Ext(in_params='optional')

    # (the `injects` field from the superclass remains unchanged)

    md5 = Ext(in_params='optional')

    modified = Ext(
        extra_params=Ext(
            min=Ext(in_params='optional'),
            max=Ext(in_params='optional'),
            until=Ext(in_params='optional'),
        ),
    )

    name = Ext(in_params='optional')

    origin = Ext(in_params='optional')

    phone = Ext(in_params='optional')

    proto = Ext(in_params='optional')

    registrar = Ext(in_params='optional')

    sha1 = Ext(in_params='optional')

    sport = Ext(in_params='optional')

    target = Ext(in_params='optional')

    url = Ext(
        in_params='optional',
        extra_params=Ext(
            sub=Ext(in_params='optional'),
        ),
    )

    url_pattern = Ext(in_params='optional')

    username = Ext(in_params='optional')

    x509fp_sha1 = Ext(in_params='optional')

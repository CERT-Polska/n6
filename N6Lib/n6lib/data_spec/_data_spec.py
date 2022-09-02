# Copyright (c) 2013-2022 NASK. All rights reserved.


# Terminology: some definitions and synonyms
# ==========================================
#
# Data specification and its fields
# ---------------------------------
#
# * `data spec class` (or `data specification class`)
#   -- n6sdk.data_spec.BaseDataSpec or (more probably) some subclass of
#      it (especially n6lib.data_spec.N6DataSpec or N6InsideDataSpec)
#   [can also be informally referred to as `data spec[ification]` but
#    the proper meaning of `data spec[ification]` is different -- see
#    below]
#
# * `data spec` (or `data specification`)
#   -- an *instance* of some *data spec class*
#      (note that, typically, you need only one *data spec*)
#
# * `field class` or `field spec class` (or `field specification class`)
#   -- n6sdk.data_spec.fields.Field or (more probably) some subclass of
#      it (especially a *subclass* of n6lib.data_spec.fields.FieldForN6)
#   [can also be informally referred to as `field` but the proper
#    meaning of `field`/`field spec[ification]` is different -- see
#    below]
#
# * `field` or `field spec[ification]` or `field instance`
#   -- some *instance* of a certain *field class*
#      (note that, typically, a particular *field* is the value of some
#      attribute of *data spec*; the name of such attribute is referred
#      to as *field key* or *field name* -- see below)
#
#   [NOTE, however, that the word `field` may have also completely
#    different meaning: referring just to an *event attribute* (see:
#    http://redmine.cert.pl/projects/data-repository/wiki/API_REST_en#Event-attributes)
#    -- taken as an abstract entity or when referring to some concrete
#    data, especially to an item of a *raw/cleaned param/result dict*
#    (see below), or to an item of a RecordDict, or to an item of a
#    certain database record...]
#
# * `field key` or `field name`
#   -- a `str` being the name of a *data spec*'s attribute whose value
#      is a *field*
#
#   [there are also some closely related terms, not necessarily formal:
#    * used in the context of REST API queries and related machinery --
#      such as: `query param[eter] name`, `param[eter] name`,
#      `param[eter] key`, `param[eter] field key`...
#    * used in the context of REST API results and related machinery --
#      such as: `event attribute name`, `result dict key`, `result key`,
#      `result field key`...
#    * used in the context of N6Core components and related machinery --
#      such as: `event attribute name`, `record dict key`...]
#
#
# REST-API-queries-related stuff
# ------------------------------
#
# * `param field` or `param field spec[ification]`
#   -- some *field* that was instantiated with the `in_params` argument
#      *not* being None
#
# * `raw param value` or `uncleaned param value`
#   -- a `str` being a single value of some REST API query parameter
#      (specified by a REST API client) -- ready to be passed into the
#      clean_param_value() method of the apropriate *param field*
#   [may also be, less formally, referred to as
#    `[raw/uncleaned] [query] param[eter] value`
#    (parts in square brackets may be omitted)]
#
# * `cleaned param value`
#   -- an object (*not* necessarily a `str`) being the result of
#      applying the clean_param_value() method of the apropriate
#      *param field* to some *raw param value*
#   [may also be, less formally, referred to as
#    `[cleaned] [query] param[eter] value`
#    (parts in square brackets may be omitted)]
#
# * `raw param dict` or `uncleaned param dict`
#   -- a dict that maps *field keys* (each related to some *param
#      field*) to *lists* of *raw param values* -- ready to be passed
#      into the clean_param_dict() method of *data spec*
#   [may also be, less formally, referred to as
#    `[raw/uncleaned] [query] param[eter][s] dict[ionary]`
#    (parts in square brackets may be omitted)]
#
# * `cleaned param dict`
#   -- a dict that maps *field keys* (each related to some *param
#      field*) to *lists* of *cleaned param values*; generally, such
#      a dict is created by applying the clean_param_dict() method of
#      *data spec* to some *raw param dict*
#   [may also be, less formally, referred to as
#    `[cleaned] [query] param[eter][s] dict[ionary]`
#    (parts in square brackets may be omitted)]
#
#
# REST-API-results-related stuff
# ------------------------------
#
# * `result field` or `result field spec[ification]`
#   -- some *field* that was instantiated with the `in_result` argument
#      *not* being None
#
# * `raw result value` or `uncleaned result value`
#   -- an object (*not* necessarily a `str`) being a value of a
#      particular event attribute -- ready to be passed into the
#      clean_result_value() method of the apropriate *result field*
#   [may also be, less formally, referred to as
#    `[raw/uncleaned] result [item] value`
#    (parts in square brackets may be omitted)]
#
# * `cleaned result value`
#   -- an object (*not* necessarily a `str`) being the result of
#      applying the clean_result_value() method of the apropriate
#      *result field* to some *raw result value*
#   [may also be, less formally, referred to as
#    `[cleaned] result [item] value`
#    (parts in square brackets may be omitted)]
#
# * `raw result dict` or `uncleaned result dict`
#   -- a dict, typically coming from the data backend API, containing
#      uncleaned data of a particular event; such a dict maps *field
#      keys* (each related to some *result field*) to *raw result
#      values*
#
# * `cleaned result dict`
#   -- a dict containing cleaned data of a particular event; such as
#      dict maps *field keys* (each related to some *result field*) to
#      *cleaned result values*; generally, such a dict is created by
#      applying the clean_result_dict() method of *data spec* to some
#      *raw result dict*
#
#
# See also
# --------
#
# N6SDK/docs/source/tutorial.rst + docstrings of related n6sdk classes,
# or just http://n6sdk.readthedocs.io/en/latest/tutorial.html (although
# the latter may be out of date).


from pyramid.decorator import reify

from n6lib.const import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    RESTRICTION_ENUMS,
    STATUS_ENUMS,
    EVENT_TYPE_ENUMS,
)
from n6lib.data_spec.fields import (
    FieldForN6,
    AddressFieldForN6,
    AnonymizedIPv4FieldForN6,
    ASNFieldForN6,
    CCFieldForN6,
    ClientFieldForN6,
    DateTimeFieldForN6,
    DomainNameFieldForN6,
    DomainNameSubstringFieldForN6,
    EmailSimplifiedFieldForN6,
    EnrichedFieldForN6,
    FlagFieldForN6,
    IBANSimplifiedFieldForN6,
    IntegerFieldForN6,
    IPv4FieldForN6,
    IPv4NetFieldForN6,
    ListOfDictsFieldForN6,
    MD5FieldForN6,
    PortFieldForN6,
    SHA1FieldForN6,
    SHA256FieldForN6,
    SomeFieldForN6,
    SomeUnicodeFieldForN6,
    SomeUnicodeListFieldForN6,
    SourceFieldForN6,
    UnicodeEnumFieldForN6,
    UnicodeLimitedFieldForN6,
    URLBase64FieldForN6,
    URLFieldForN6,
    URLSubstringFieldForN6,
    URLsMatchedFieldForN6,
)
from n6lib.log_helpers import get_logger
from n6sdk.data_spec import (
    DataSpec,
    Ext,
)
from n6sdk.data_spec.fields import (
    AddressField,
    DateTimeField,
    IntegerField,
    IPv4Field,
    MD5Field,
    SHA1Field,
    SHA256Field,
    UnicodeField,
    UnicodeEnumField,
)
from n6sdk.regexes import PY_IDENTIFIER_REGEX



LOGGER = get_logger(__name__)



class N6DataSpec(DataSpec):

    #
    # Replaced/masked fields

    # * fields that are always required in results:

    # (note: in n6 we require that `id` values are MD5 hashes)
    id = MD5FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('required', 'unrestricted'),
    )

    source = SourceFieldForN6(
        in_params=('optional', 'anonymized'),
        in_result=('required', 'anonymized'),
    )

    restriction = UnicodeEnumFieldForN6(
        in_params='optional',
        in_result='required',
        enum_values=RESTRICTION_ENUMS,
    )

    confidence = UnicodeEnumFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('required', 'unrestricted'),
        enum_values=CONFIDENCE_ENUMS,
    )

    category = UnicodeEnumFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('required', 'unrestricted'),
        enum_values=CATEGORY_ENUMS,
    )

    modified = DateTimeFieldForN6(
        in_params=None,
        in_result='optional',
        ###in_result='required',

        ### XXX: to be required in result and optional in params
        ### XXX: to be unrestricted both in params and in result...

        extra_params=dict(
            min=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='modified_query',
                ),
            ),
            max=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='modified_query',
                ),
            ),
            until=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='modified_query',
                ),
            ),
        ),
    )

    time = DateTimeFieldForN6(
        in_params=None,
        in_result=('required', 'unrestricted'),

        extra_params=dict(
            min=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
            ),
            max=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
            ),
            until=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
            ),
        ),
    )


    # * fields related to `address`:

    # (using an AddressField subclass [without `ipv6`, `dir`, `rdns`]
    # instead of an ExtendedAddressField subclass -- at least for now...)
    address = AddressFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    ip = IPv4FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=None,

        extra_params=dict(
            net=IPv4NetFieldForN6(
                in_params=('optional', 'unrestricted'),
                custom_info=dict(
                    func='ip_net_query',
                ),
            ),
        ),
    )

    ipv6 = None  # (present in SDK, *masked* here -- at least for now...)

    asn = ASNFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=None,
    )

    cc = CCFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=None,
    )


    # * fields related to black list events:

    active = FieldForN6(
        in_params=None,
        in_result=None,

        extra_params=dict(
            min=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='active_bl_query',
                ),
            ),
            max=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='active_bl_query',
                ),
            ),
            until=DateTimeFieldForN6(
                in_params=('optional', 'unrestricted'),
                single_param=True,
                custom_info=dict(
                    func='active_bl_query',
                ),
            ),
        ),
    )

    expires = DateTimeFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    # (note: in n6 we require that `replaces` values are MD5 hashes)
    replaces = MD5FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    status = UnicodeEnumFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
        enum_values=STATUS_ENUMS,
    )


    # * fields related to aggregated (high frequency) events:

    count = IntegerFieldForN6(
        in_params=None,
        in_result='optional',
        min_value=0,
        max_value=(2 ** 15 - 1),  ### to be extended to 2**16-1?
    )                             ### OR rather more (see: ticket #6324)

    # see: ticket #6324
    count_actual = IntegerFieldForN6(
        in_params=None,
        in_result='optional',
        min_value=0,
        max_value=(2 ** 53 - 1),  # big enough + seems to be JSON-safe...
    )

    until = DateTimeFieldForN6(
        in_params=None,
        in_result='optional',
    )


    # * other fields:

    action = UnicodeLimitedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
        max_length=32,
    )

    adip = AnonymizedIPv4FieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    dip = IPv4FieldForN6(
        # note: `dip` is *restricted* as a param but *anonymized* as a result item
        in_params='optional',
        in_result=('optional', 'anonymized'),
    )

    dport = PortFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    email = EmailSimplifiedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    fqdn = DomainNameFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),

        extra_params=dict(
            sub=DomainNameSubstringFieldForN6(
                in_params=('optional', 'unrestricted'),
                custom_info=dict(
                    func='like_query',
                ),
            ),
        ),
    )

    iban = IBANSimplifiedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    injects = ListOfDictsFieldForN6(  ## XXX: shouldn't it be more specialized field?
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )

    md5 = MD5FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    name = UnicodeLimitedFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
        max_length=255,  ### XXX: to be reduced to 100
    )

    origin = UnicodeEnumFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
        enum_values=ORIGIN_ENUMS,
    )

    phone = UnicodeLimitedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
        max_length=20,
    )

    proto = UnicodeEnumFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
        enum_values=PROTO_ENUMS,
    )

    registrar = UnicodeLimitedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
        max_length=100,
    )

    sha1 = SHA1FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    sha256 = SHA256FieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    sport = PortFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
    )

    target = UnicodeLimitedFieldForN6(
        in_params=('optional', 'unrestricted'),
        in_result=('optional', 'unrestricted'),
        max_length=100,
    )

    url = URLFieldForN6(
        in_params=('optional', 'unrestricted'),  ### XXX: to be None, and later searched by fqdn?
        in_result=('optional', 'unrestricted'),

        extra_params=dict(
            sub=URLSubstringFieldForN6(
                in_params=('optional', 'unrestricted'),
                custom_info=dict(
                    func='like_query',
                ),
            ),
            # *EXPERIMENTAL*
            # (likely to be changed or removed in the future
            # without any warning/deprecation/etc.)
            b64=URLBase64FieldForN6(
                in_params=('optional', 'unrestricted'),
                custom_info=dict(
                    func='url_b64_experimental_query',
                ),
            )
        ),
    )

    url_pattern = UnicodeLimitedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
        max_length=255,
        disallow_empty=True,
    )

    urls_matched = URLsMatchedFieldForN6(
        in_params=None,
        in_result='optional',
    )

    username = UnicodeLimitedFieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
        max_length=64,
    )

    x509fp_sha1 = SHA1FieldForN6(
        in_params=None,
        in_result=('optional', 'unrestricted'),
    )


    #
    # Added fields

    rid = MD5FieldForN6(
        in_result='required',
        in_params='optional',
    )

    client = ClientFieldForN6(
        in_result='optional',
        in_params='optional',
    )

    opt = FieldForN6(                   # the `opt` "param container field"
        in_result=None,                 # for, e.g., query/rendering options
        in_params=None,

        extra_params=dict(
            primary=FlagFieldForN6(     # the `opt.primary` flag
                in_params=('optional', 'unrestricted'),
                single_param=True,
            ),
            limit=IntegerFieldForN6(    # the `opt.limit` param
                in_params=('optional', 'unrestricted'),
                single_param=True,
                min_value=1,
                max_value=(2**64 - 1),  # the highest possible MySQL limit
            ),
        ),
    )

    # special field -- final cleaned results do *not* include it
    enriched = EnrichedFieldForN6()

    # fields related to some particular parsers

    # * of various specialized field types:
    alternative_fqdns = SomeUnicodeListFieldForN6(in_result='optional')
    block = FlagFieldForN6(in_result=('optional', 'unrestricted'))
    ip_network = IPv4NetFieldForN6(in_result='optional')
    tags = SomeUnicodeListFieldForN6(in_result='optional')

    # * of the SomeUnicodeFieldForN6 type:
    description = SomeUnicodeFieldForN6(in_result='optional')
    filename = SomeUnicodeFieldForN6(in_result='optional')
    min_amplification = SomeUnicodeFieldForN6(in_result='optional')
    rt = SomeUnicodeFieldForN6(in_result='optional')
    x509issuer = SomeUnicodeFieldForN6(in_result=('optional', 'unrestricted'))
    x509subject = SomeUnicodeFieldForN6(in_result=('optional', 'unrestricted'))

    # * of the SomeFieldForN6 type:
    additional_data = SomeFieldForN6(in_result='optional')
    botid = SomeFieldForN6(in_result='optional')
    cert_length = SomeFieldForN6(in_result='optional')
    channel = SomeFieldForN6(in_result='optional')
    dataset = SomeFieldForN6(in_result='optional')
    detected_since = SomeFieldForN6(in_result='optional')
    device_id = SomeFieldForN6(in_result='optional')
    device_model = SomeFieldForN6(in_result='optional')
    device_type = SomeFieldForN6(in_result='optional')
    device_vendor = SomeFieldForN6(in_result='optional')
    device_version = SomeFieldForN6(in_result='optional')
    dns_version = SomeFieldForN6(in_result='optional')
    facebook_id = SomeFieldForN6(in_result='optional')
    first_seen = SomeFieldForN6(in_result='optional')
    gca_specific = SomeFieldForN6(in_result='optional')
    handshake = SomeFieldForN6(in_result='optional')
    header = SomeFieldForN6(in_result='optional')
    intelmq = SomeFieldForN6(in_result='optional')
    internal_ip = SomeFieldForN6(in_result='optional')
    ipmi_version = SomeFieldForN6(in_result='optional')
    mac_address = SomeFieldForN6(in_result='optional')
    method = SomeFieldForN6(in_result='optional')
    misp_eventdid = SomeFieldForN6(in_result='optional')    # use of the field deprecated
    misp_attr_uuid = SomeFieldForN6(in_result='optional')
    misp_event_uuid = SomeFieldForN6(in_result='optional')
    product = SomeFieldForN6(in_result=('optional', 'unrestricted'))
    product_code = SomeFieldForN6(in_result='optional')
    proxy_type = SomeFieldForN6(in_result='optional')
    # note: yes it's "referer" (single 'r', not a mistake!) - see: https://tools.ietf.org/html/rfc7231#section-5.5.2
    referer = SomeFieldForN6(in_result='optional')
    request = SomeFieldForN6(in_result='optional')
    revision = SomeFieldForN6(in_result='optional')
    sender = SomeFieldForN6(in_result='optional')
    subject_common_name = SomeFieldForN6(in_result='optional')
    sysdesc = SomeFieldForN6(in_result='optional')
    user_agent = SomeFieldForN6(in_result='optional')
    vendor = SomeFieldForN6(in_result='optional')
    version = SomeFieldForN6(in_result='optional')
    visible_databases = SomeFieldForN6(in_result='optional')

    # dummy fields (only for RecordDict's adjusters specification)

    _type = UnicodeEnumFieldForN6(enum_values=EVENT_TYPE_ENUMS)
    _first_time = DateTimeFieldForN6()
    _blseriesno = IntegerFieldForN6()
    _blseriestotal = IntegerFieldForN6()
    _blseriesid = MD5FieldForN6()
    _bltime = DateTimeFieldForN6()
    _blcurrenttime = DateTimeFieldForN6()


    #
    # Additional field metadata

    ### will become obsolete after switching to the new DB schema
    custom_field_keys = {
        'action',
        'additional_data',
        'adip',
        'alternative_fqdns',
        'block',
        'botid',
        'cert_length',
        'channel',
        'count_actual',
        'dataset',
        'description',
        'detected_since',
        'device_id',
        'device_model',
        'device_type',
        'device_vendor',
        'device_version',
        'dns_version',
        'email',
        'enriched',
        'facebook_id',
        'filename',
        'first_seen',
        'gca_specific',
        'handshake',
        'header',
        'iban',
        'injects',
        'intelmq',
        'internal_ip',
        'ip_network',
        'ipmi_version',
        'mac_address',
        'method',
        'min_amplification',
        'misp_eventdid',    # use deprecated, field substituted with `misp_event_uuid`
        'misp_attr_uuid',
        'misp_event_uuid',
        'phone',
        'product',
        'product_code',
        'proxy_type',
        'referer',
        'registrar',
        'request',
        'revision',
        'rt',
        'sender',
        'subject_common_name',
        'sysdesc',
        'tags',
        'url_pattern',
        'urls_matched',
        'user_agent',
        'username',
        'vendor',
        'version',
        'visible_databases',
        'x509fp_sha1',
        'x509issuer',
        'x509subject',
    }

    ### will become obsolete after switching to the new DB schema
    sql_relationship_field_keys = {
        'client',
    }


    @reify
    def unrestricted_param_keys(self):
        return frozenset(self.param_field_specs('unrestricted').keys())

    @reify
    def anonymized_param_keys(self):
        return frozenset(self.param_field_specs('anonymized').keys())

    @reify
    def restricted_param_keys(self):
        return self.all_param_keys - (self.unrestricted_param_keys |
                                      self.anonymized_param_keys)


    @reify
    def unrestricted_result_keys(self):
        return frozenset(self.result_field_specs('unrestricted').keys())

    @reify
    def anonymized_result_keys(self):
        return frozenset(self.result_field_specs('anonymized').keys())

    @reify
    def restricted_result_keys(self):
        return self.all_result_keys - (self.unrestricted_result_keys |
                                       self.anonymized_result_keys)


    #
    # New public methods

    ### will become obsolete after switching to the new DB schema
    def generate_sqlalchemy_columns(self, **col_kwargs_updates):
        """
        Example usage:

            from sqlalchemy.ext.declarative import declarative_base

            Base = declarative_base()
            n6spec = N6DataSpec()

            class n6NormalizedData(Base):

                __tablename__ = 'event'

                locals().update(n6spec.generate_sqlalchemy_columns(
                    id=dict(primary_key=True),
                    time=dict(primary_key=True),
                    ip=dict(primary_key=True, autoincrement=False))
        """
        from sqlalchemy import Column
        from n6lib.db_events import JSONText

        seen_col_names = set()

        if self.custom_field_keys:
            name = 'custom'
            seen_col_names.add(name)
            yield name, Column(JSONText(), nullable=True,
                               **col_kwargs_updates.get(name, {}))

        for key, field in self.result_field_specs().items():
            for name, column in self._generate_cols_from_field_spec(
                    key,
                    field,
                    col_kwargs_updates):
                if name in seen_col_names:
                    raise ValueError('column name {!a} duplicated'
                                     .format(name))
                seen_col_names.add(name)
                yield name, column


    #
    # Extended superclass methods

    def clean_param_dict(self, params, auth_api, full_access, res_limits,
                         **kwargs):
        self._update_clean_param_dict_kwargs(kwargs, full_access, res_limits)
        params = super(N6DataSpec, self).clean_param_dict(params, **kwargs)
        if not full_access:
            params = self._params_deanonymized(params, auth_api)
        return params


    def clean_result_dict(self, result, auth_api, full_access, opt_primary,
                          **kwargs):
        result = self._result_with_unpacked_custom(result)
        enriched = result.pop('enriched', None)
        if enriched is None and opt_primary:
            return None  # for `opt.primary`: record without 'enriched' skipped
        self._preclean_address_related_items(result)
        self._update_clean_result_dict_kwargs(kwargs, full_access)
        if not full_access:
            result = self._result_anonymized(result, auth_api)
        result = super(N6DataSpec, self).clean_result_dict(result, **kwargs)
        if opt_primary:
            self._strip_down_to_primary_data(result, enriched)
        return result


    def param_field_specs(self, which='all', multi=True, single=True, **kwargs):
        return super(N6DataSpec, self).param_field_specs(
            which,
            field_additional_info_attr='in_params_additional_info',
            **kwargs)

    def result_field_specs(self, which='all', **kwargs):
        return super(N6DataSpec, self).result_field_specs(
            which,
            field_additional_info_attr='in_result_additional_info',
            **kwargs)

    @classmethod
    def filter_by_which(cls, which, all_fields_dict, required_fields_dict,
                        field_additional_info_attr, **kwargs):
        try:
            return super(N6DataSpec, cls).filter_by_which(
                which,
                all_fields_dict,
                required_fields_dict,
                **kwargs)
        except ValueError:
            return {
                (k, field)
                for k, field in all_fields_dict.items()
                if which in getattr(field, field_additional_info_attr)}


    #
    # Param value deanonymizers (called in _params_deanonymized() -- see below)

    # each deanonymizer should be a method that:
    # * has name `deanonymize_<field key>'
    # * takes two arguments:
    #   * anonymized value (already cleaned)
    #   * AuthAPI instance
    # * returns deanonymized value or None
    # (returning None means that for a particular case, instead of applying
    # deanonymization, the given value shall be omitted)

    def deanonymize_source(self, value, auth_api):
        mapping = auth_api.get_anonymized_source_mapping()['reverse_mapping']
        return mapping.get(value)  # (note: the result can be None)


    #
    # Result value anonymizers (called in _result_anonymized() -- see below)

    # each anonymizer should be a method that:
    # * has name `anonymize_<field key>'
    # * takes two arguments:
    #   * result dict (a dict containing data of a particular event;
    #     values it contains are *not* cleaned yet)
    #   * AuthAPI instance
    # * returns either None or a tuple whose items are:
    #   * field key (the same or different than that used in the method name)
    #   * anonymized value
    # (returning None means that for a particular case anonymization means
    # just omitting the given value)

    def anonymize_source(self, result, auth_api):
        source = result['source']
        mapping = auth_api.get_anonymized_source_mapping()['forward_mapping']
        anonymized_source = mapping.get(source, 'hidden.unknown')
        return 'source', anonymized_source

    def anonymize_dip(self, result, auth_api):
        dip = result['dip']
        source = result['source']

        if source in auth_api.get_dip_anonymization_disabled_source_ids():
            # anonymization of `dip` is *disabled* for this source
            return 'dip', dip

        # anonymization of `dip` is *enabled* for this source
        if 'adip' in result:
            # `adip` already in the result (no need to add it)
            return None
        # `adip` not in the result -- so it needs to be made from `dip`
        adip = '.'.join(['x', 'x'] + dip.split('.')[2:])
        return 'adip', adip


    #
    # Non-public internals

    ### will become obsolete after switching to the new DB schema
    def _generate_cols_from_field_spec(self, key, field, col_kwargs_updates):
        from sqlalchemy import (
            Column,
            DateTime,
            Enum,
            String,
            Text,
        )
        from sqlalchemy.dialects.mysql import (
            SMALLINT,
            INTEGER,
        )
        from n6lib.db_events import (
            IPAddress,
            MD5,
            SHA1,
            SHA256,
            JSONText,
        )

        if (key in self.sql_relationship_field_keys or
              key in self.custom_field_keys):
            return

        if PY_IDENTIFIER_REGEX.search(key) is None:
            raise ValueError('{!a} is not a valid Python identifier'
                             .format(key))

        col_kwargs = {'nullable': (field.in_result != 'required' and
                                   key != 'ip')}
        col_kwargs.update(col_kwargs_updates.get(key, {}))

        if isinstance(field, AddressField):
            for subkey, subfield in field.key_to_subfield.items():
                for name, column in self._generate_cols_from_field_spec(
                        subkey,
                        subfield,
                        col_kwargs_updates):
                    yield name, column
            yield key, Column(JSONText(), **col_kwargs)
        else:
            if isinstance(field, DateTimeField):
                col_args = [DateTime]
            elif isinstance(field, MD5Field):
                col_args = [MD5]
            elif isinstance(field, SHA1Field):
                col_args = [SHA1]
            elif isinstance(field, SHA256Field):
                col_args = [SHA256]
            elif isinstance(field, IPv4Field):
                col_args = [IPAddress]
            elif isinstance(field, UnicodeEnumField):
                col_args = [Enum(*field.enum_values, name=(key + '_type'))]
            elif isinstance(field, UnicodeField):
                max_length = getattr(field, 'max_length', None)
                if max_length is not None:
                    col_args = [String(max_length)]
                else:
                    col_args = [Text]
            elif isinstance(field, IntegerField):
                if field.min_value is None:
                    raise NotImplementedError(
                        "'min_value' being None not supported")
                elif field.max_value is None:
                    raise NotImplementedError(
                        "'max_value' being None not supported")
                elif (field.min_value >= -(2 ** 15) and
                      field.max_value < 2 ** 15):
                    col_args = [SMALLINT]
                elif (field.min_value >= 0 and
                      field.max_value < 2 ** 16 and
                      # dport and sport are INTEGER, not SMALLINT in db
                      # (at least for now; for historical reasons)
                      key not in ('dport', 'sport')):
                    col_args = [SMALLINT(unsigned=True)]
                elif (field.min_value >= -(2 ** 31) and
                      field.max_value < 2 ** 31):
                    col_args = [INTEGER]
                elif (field.min_value >= 0 and
                      field.max_value < 2 ** 32):
                    col_args = [INTEGER(unsigned=True)]
                else:
                    raise NotImplementedError(
                        'integer range {!a}..{!a} not supported'
                        .format(field.min_value, field.max_value))
            else:
                raise NotImplementedError('{!a} not supported'.format(field))
            yield key, Column(*col_args, **col_kwargs)


    def _update_clean_param_dict_kwargs(self, kwargs, full_access, res_limits):
        forbidden_keys = frozenset(kwargs.get('forbidden_keys', ()))
        extra_required_keys = frozenset(kwargs.get('extra_required_keys', ()))
        enabled_to_required = res_limits['request_parameters']
        if not full_access:
            forbidden_keys |= self.restricted_param_keys
        if enabled_to_required is not None:
            forbidden_keys |= self.all_param_keys.difference(enabled_to_required)
            extra_required_keys |= {
                key for key, required in enabled_to_required.items()
                if required}
        kwargs['forbidden_keys'] = forbidden_keys
        kwargs['extra_required_keys'] = extra_required_keys

    def _params_deanonymized(self, params, auth_api):
        assert 'dip' not in params, (
            '[sanity check failed] clean_param_dict() has '
            'accepted "dip" in params for non-full-access???')
        deanonymized_params = {}
        anon = self.anonymized_param_keys
        for key, value_list in params.items():
            if key in anon:
                deanonymizer = getattr(self, 'deanonymize_' + key)
                deanonymized_value_list = [
                    deanonymizer(value, auth_api) for value in value_list]
                ## FIXME?: what to do with a `source` value being None???
                ## for now we just omit such a value
                ## => the resultant value list can be empty
                ##    so that the resultat query contains "1 != 1"
                ##    (which must make the result empty; so,
                ##    maybe, some short-circuit procedure -- to return
                ##    an empty result early -- is desired?)
                deanonymized_params[key] = [
                    value for value in deanonymized_value_list
                    if value is not None]
            else:
                deanonymized_params[key] = value_list
        return deanonymized_params


    ### probably must be adjusted when switching to the new DB schema
    def _result_with_unpacked_custom(self, result):
        upd_result = result.copy()
        custom_items = upd_result.pop('custom', {})
        upd_result.update(custom_items)
        return upd_result

    ### probably must be adjusted when switching to the new DB schema
    def _preclean_address_related_items(self, result):
        event_tag = self._get_event_tag_for_logging(result)
        address = result.pop('address', None)
        address_item = {
            key: value for key, value in [
                ('ip', result.pop('ip', None)),
                ('asn', result.pop('asn', None)),
                ('cc', result.pop('cc', None))]
            if value is not None}
        if address is not None:
            if address:
              # DEBUGGING #3141
              try:
                new_address = [
                    {key: value for key, value in addr.items()
                     if value is not None}
                    for addr in address]
                if new_address != address:
                    LOGGER.warning(
                        'values being None in the address: %a\n%s',
                        address, event_tag)
                address = new_address
              except AttributeError as exc:
                exc_str = str(exc)
                if "no attribute 'items'" in exc_str:
                    raise AttributeError('{0} [`address`: {1!a}]'.format(exc_str, address))
                else:
                    raise
            else:
                LOGGER.warning('empty address: %a\n%s', address, event_tag)
                address = None
        if address_item:
            if address is None:
                LOGGER.warning(
                    'address does not exist but it should and it should '
                    'contain at least the item %a\n->address containing '
                    'it will be used...\n%s', address_item, event_tag)
                address = [address_item]
            elif address_item not in address:
                # intentionally ERROR and not WARNING
                LOGGER.error(
                    'data inconsistency detected: item %a is not in the '
                    'address %a\n%s', address_item, address, event_tag)
        if address is not None:
            result['address'] = address

    def _update_clean_result_dict_kwargs(self, kwargs, full_access):
        if not full_access:
            discarded_keys = frozenset(kwargs.get('discarded_keys', ()))
            kwargs['discarded_keys'] = discarded_keys | self.restricted_result_keys

    def _result_anonymized(self, result, auth_api):
        anonymized_result = {}
        anon = self.anonymized_result_keys
        for key, value in result.items():
            if key in anon:
                anonymizer = getattr(self, 'anonymize_' + key)
                anon_item = anonymizer(result, auth_api)
                if anon_item is not None:
                    anon_key, anon_value = anon_item
                    anonymized_result[anon_key] = anon_value
            else:
                anonymized_result[key] = value
        return anonymized_result

    def _strip_down_to_primary_data(self, result, enriched):
        assert enriched is not None
        event_tag = self._get_event_tag_for_logging(result)
        enriched_keys, ip_to_enriched_address_keys = enriched
        for key in enriched_keys:
            try:
                del result[key]
            except KeyError:
                LOGGER.warning(
                    'cannot delete key %a from result dict '
                    'because it does not contain the key\n%s',
                    key, event_tag)
        orig_address = result.pop('address', None)
        address = list(self._generate_stripped_address_items(
            orig_address,
            ip_to_enriched_address_keys,
            event_tag))
        if address:
            result['address'] = address

    def _generate_stripped_address_items(self,
                                         address,
                                         ip_to_enriched_address_keys,
                                         event_tag):
        if address is None:
            return  # (the generator yields 0 items)
        for orig_addr in address:
            addr = orig_addr.copy()
            enriched_addr_keys = ip_to_enriched_address_keys.get(addr['ip'])
            if not enriched_addr_keys:
                yield addr
                continue
            for key in enriched_addr_keys:
                try:
                    del addr[key]
                except KeyError:
                    LOGGER.warning(
                        'cannot delete key %a from address item %a '
                        'because it does not contain the key\n%s',
                        key, orig_addr, event_tag)
            if addr:
                yield addr

    def _get_event_tag_for_logging(self, result):
        try:
            return (
                '(@event whose id is {}, time is {}, modified is {})'.format(
                    result.get('id', 'not set'),
                    result.get('time', 'not set'),
                    result.get('modified', 'not set')))
        except (AttributeError, ValueError, TypeError):  # a bit of paranoia :)
            return '(@unknown event)'



class N6InsideDataSpec(N6DataSpec):

    """N6DataSpec subclass for the '/report/inside' REST API resource."""

    client = Ext(
        in_params=None,  # client is taken automatically from auth data
    )

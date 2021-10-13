# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

#
# TODO: more comments + docs
#

from __future__ import print_function                                            #3--
import base64
import collections as collections_abc                #3: -> `import collections.abc as collections_abc`
import copy
import functools
import json
import re
import sys

try:
    from bson.json_util import dumps
except ImportError:
    print('Warning: bson is required to run parsers', file=sys.stderr)

from n6lib.class_helpers import (
    AsciiMixIn,
    attr_repr,
    is_seq,
)
from n6lib.common_helpers import (
    LimitedDict,
    ascii_str,
    as_bytes,
    ipv4_to_str,
    make_exc_ascii_str,
    try_to_normalize_surrogate_pairs_to_proper_codepoints,
)
from n6lib.const import (
    CATEGORY_TO_NORMALIZED_NAME,
    NAME_NORMALIZATION,
)
from n6lib.data_spec import (
    N6DataSpec,
    FieldValueError,
    FieldValueTooLongError,
)
from n6lib.log_helpers import get_logger
from n6lib.url_helpers import (
    URL_SCHEME_AND_REST_LEGACY_REGEX,
    make_provisional_url_search_key,
)


LOGGER = get_logger(__name__)
NONSTANDARD_NAMES_LOGGER = get_logger('NONSTANDARD_NAMES')


#
# Auxiliary constants

COMMON_URL_SCHEME_DEOBFUSCATIONS = {
    'hxxp': 'http',
    'hxxps': 'https',
    'fxp': 'ftp',
}


#
# Exceptions

class AdjusterError(AsciiMixIn, Exception):
    """Raised by a record dict when an exception was raised by an adjuster."""


#
# Adjuster-related decorators and helpers

def chained(*adjusters):
    """
    Combine several adjusters.
    """
    if len(adjusters) == 1:
        return adjusters[0]
    else:
        def _compound_adjuster(self, value):
            for adj in adjusters:
                value = adj(self, value)
            return value
        _compound_adjuster._factory_names = frozenset().union(
            *(getattr(adj, '_factory_names', frozenset())
              for adj in adjusters))
        return _compound_adjuster


def applied_for_nonfalse(adjuster):
    """
    Wrap an adjuster so it will pass thru any false values without adjustment.
    """
    def _applied_for_nonfalse_adjuster(self, value):
        if value:
            value = adjuster(self, value)
        return value
    _applied_for_nonfalse_adjuster._factory_names = getattr(
          adjuster, '_factory_names', frozenset())
    return _applied_for_nonfalse_adjuster


def preceded_by(*adjusters):
    """
    Decorate a method: specified adjusters will be called before it.
    """
    compound_adjuster = chained(*adjusters)
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, value, *args, **kwargs):
            value = compound_adjuster(self, value)
            return func(self, value, *args, **kwargs)
        wrapper._factory_names = (
            getattr(func, '_factory_names', frozenset()) |
            getattr(compound_adjuster, '_factory_names', frozenset()))
        return wrapper
    return decorator


def adjuster_factory(adjuster_template_func):
    """
    Decorator for making adjuster factories.
    """
    name = adjuster_template_func.__name__
    def actual_factory(*args, **kwargs):
        def adjuster(self, value):
            return adjuster_template_func(self, value, *args, **kwargs)
        adjuster.__name__ = name + '__adjuster'
        # additional attrs for introspection:
        adjuster._factory_names = frozenset({name})
        return adjuster
    actual_factory.__name__ = name
    return actual_factory


#
# Some adjuster factories

@adjuster_factory
def ensure_in(self, value, valid_values):
    if value not in valid_values:
        raise ValueError('{!r} does not contain value {!r}'
                         .format(valid_values, value))
    return value


@adjuster_factory
def ensure_in_range(self, value, start, stop):
    if not start <= value < stop:
        raise ValueError('condition {!r} <= {!r} < {!r} is not met'
                         .format(start, value, stop))
    return value


@adjuster_factory
def ensure_isinstance(self, value, *type_or_types):
    if not isinstance(value, type_or_types):
        raise TypeError('{!r} (type: {!r}) is not an instance of {!r}'
                        .format(value, type(value), type_or_types))
    return value


@adjuster_factory
def ensure_validates_by_regexp(self, value, regexp):
    str = unicode                                                                #3--
    if not isinstance(value, (str, bytes, bytearray)):
        raise TypeError('{!r} is not a string'.format(value))
    if isinstance(regexp, (str, bytes)):
        regexp = re.compile(regexp, re.ASCII)
    # note: here we use regexp.search, *not* regexp.match
    if regexp.search(value) is None:
        raise ValueError('value {0!r} does not match regexp '
                         '{1.pattern!r} (flags: {1.flags!r})'
                         .format(value, regexp))
    return value


# TODO: tests
@adjuster_factory
def ensure_not_longer_than(self, value, max_length):
    try:
        length = len(value)
    except (TypeError, AttributeError):
        raise TypeError('{!r} (type: {!r}) does not support `len()`'
                        .format(value, type(value)))
    if length > max_length:
        raise ValueError('value length ({}) is greater than the maximum ({})'
                         .format(length, max_length))
    return value


@adjuster_factory
def make_adjuster_using_data_spec(self, value, spec_field_name,
                                  on_too_long=None):
    spec_field = getattr(self.data_spec, spec_field_name)
    if spec_field.sensitive and on_too_long is not None:
        raise RuntimeError('{!r}.sensitive is true so the `on_too_long` '
                           'argument should be None (got: on_too_long={!r})'
                           .format(spec_field, on_too_long))
    try:
        return spec_field.clean_result_value(value)
    except FieldValueTooLongError as exc:
        # If value might be sensitive we want an exception without any details
        # (see: `raise FieldValueError...` at the end of this function...).
        if (not spec_field.sensitive) or getattr(exc, 'safe_for_sensitive', False):
            if on_too_long is None:
                raise
            LOGGER.warning(
                'calling %r as the on-too-long callback, because: %s',
                on_too_long, exc)
            try:
                assert hasattr(exc, 'checked_value')
                assert hasattr(exc, 'max_length')
                assert isinstance(exc.max_length, (int, long)) and exc.max_length > 0     #3: `long`--
                processed_value = on_too_long(exc.checked_value, exc.max_length)
            except Exception as e:
                if not hasattr(e, 'propagate_it_anyway'):
                    e.propagate_it_anyway = True
                raise
            return spec_field.clean_result_value(processed_value)
    except Exception as exc:
        # If value might be sensitive we want an exception without any details
        # (see: `raise FieldValueError...` at the end of this function...).
        if (not spec_field.sensitive) or getattr(exc, 'safe_for_sensitive', False):
            raise
    assert spec_field.sensitive
    raise FieldValueError(public_message=spec_field.default_error_msg_if_sensitive)


@adjuster_factory
def make_adjuster_applying_value_method(self, value, value_method_name,
                                        *args, **kwargs):
    return getattr(value, value_method_name)(*args, **kwargs)


@adjuster_factory
def make_adjuster_applying_callable(self, value, func, *args, **kwargs):
    return func(value, *args, **kwargs)


@adjuster_factory
def make_multiadjuster(self, value, singular_adjuster=None):
    if not is_seq(value):
        value = (value,)
    if singular_adjuster is None:
        return list(value)
    return [singular_adjuster(self, el) for el in value]


@adjuster_factory
def make_dict_adjuster(self, value, **keys_to_adjusters):
    if isinstance(value, collections_abc.Mapping):
        return {k: (keys_to_adjusters[k](self, v)
                    if k in keys_to_adjusters
                    else v)
                for k, v in sorted(value.items())}
    raise TypeError('{!r} is not a mapping'.format(value))


#
# Reusable generic adjusters and auxiliary co-adjusters

def rd_adjuster(self, value):
    if not isinstance(value, RecordDict):
        raise TypeError('{!r} (type: {!r}) is not an instance of {!r}'
                        .format(value, type(value), RecordDict))
    return value


@preceded_by(ensure_isinstance(unicode, bytes, bytearray))                       #3: `unicode`->`str`
def unicode_adjuster(self, value):
    str = unicode                                                                #3--
    if isinstance(value, str):
        return value
    assert isinstance(value, (bytes, bytearray))
    try:
        return value.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError("could not decode text from binary data {!r} using "
                         "utf-8 encoding ({}); please note that it is parser's "
                         "responsibility to ensure that input objects passed "
                         "into unicode adjusters are either *unicode strings* "
                         "(`str`) or *utf-8-encoded data* (as objects of type "
                         "`bytes` or `bytearray`)".format(value, ascii_str(exc)))


@preceded_by(ensure_isinstance(unicode, bytes, bytearray))                       #3: `unicode`->`str`
def unicode_surrogate_pass_and_esc_adjuster(self, value):
    str = unicode                                                                #3--
    if isinstance(value, str):
        return value
    assert isinstance(value, (bytes, bytearray))
    return value.decode('utf-8', 'utf8_surrogatepass_and_surrogateescape')


ipv4_preadjuster = chained(
    ensure_isinstance(int, long, unicode, str),                                  #3: `long`-- `unicode`--
    make_adjuster_applying_callable(ipv4_to_str))


@preceded_by(unicode_surrogate_pass_and_esc_adjuster)
def url_preadjuster(self, value):
    match = URL_SCHEME_AND_REST_LEGACY_REGEX.match(value)
    if match is None:
        raise ValueError('{!r} does not seem to be a valid URL'
                         .format(value))
    scheme = match.group('scheme').lower()
    scheme = COMMON_URL_SCHEME_DEOBFUSCATIONS.get(scheme, scheme)
    return scheme + match.group('rest')


#
# `on_too_long` callbacks for make_adjuster_using_data_spec()

def trim(value, max_length):
    """
    >>> trim('ef.ghi', 1)
    'e'
    >>> trim('ef.ghi', 2)
    'ef'
    >>> trim('ef.ghi', 3)
    'ef.'
    >>> trim('ef.ghi', 4)
    'ef.g'
    >>> trim('ef.ghi', 5)
    'ef.gh'
    >>> trim('ef.ghi', 6)
    'ef.ghi'
    >>> trim('ef.ghi', 7)
    'ef.ghi'
    >>> trim('ef.ghi', 1000)
    'ef.ghi'
    """
    return value[:max_length]

def trim_domain(value, max_length):
    """
    >>> trim_domain('ef.ghi', 1)
    'i'
    >>> trim_domain('ef.ghi', 2)
    'hi'
    >>> trim_domain('ef.ghi', 3)
    'ghi'
    >>> trim_domain('ef.ghi', 4)  # note this!
    'ghi'
    >>> trim_domain('ef.ghi', 5)
    'f.ghi'
    >>> trim_domain('ef.ghi', 6)
    'ef.ghi'
    >>> trim_domain('ef.ghi', 7)
    'ef.ghi'
    >>> trim_domain('ef.ghi', 1000)
    'ef.ghi'
    """
    value = value[-max_length:]
    if value.startswith('.'):
        return value[1:]
    return value

def trim_seq(value, max_length):
    return [trim(v, max_length) for v in value]

def trim_domain_seq(value, max_length):
    return [trim_domain(v, max_length) for v in value]


#
# The actual record dict classes

### CR: TODO: docstrings for public methods
### (especially get_ready_dict et consortes...)

class RecordDict(collections_abc.MutableMapping):

    """
    Record dict class for non-blacklist events.
    """

    _ADJUSTER_PREFIX = 'adjust_'
    _APPENDER_PREFIX = 'append_'

    data_spec = N6DataSpec()

    required_keys = frozenset(data_spec.result_field_specs('required'))
    optional_keys = frozenset(data_spec.result_field_specs('optional')) | {
        # note: the 'type' item is somewhat related to
        # <parser class>.event_type but *not* to <collector class>.type (!)
        'type',  ## <- FIXME???: shouldn't it be required? (not optional?)

        'enriched',  # (its values are added by enricher)

        # internal keys
        # (items whose keys start with '_' are neither recorded
        #  into database nor used for id computation)

        '_do_not_resolve_fqdn_to_ip',  # flag for enricher
        '_parsed_old',

        # *EXPERIMENTAL* (likely to be changed or removed in the future
        # without any warning/deprecation/etc.)
        '_url_data',
        '_url_data_ready',

        # internal keys of aggregated items
        '_group',
        '_first_time',

        # internal keys of blacklist items
        ## FIXME?: shouldn't they be required
        ## (not optional) for BLRecordDict???
        '_bl-series-no',
        '_bl-series-total',
        '_bl-series-id',
        '_bl-time',
        '_bl-current-time',
    }

    # *EXPERIMENTAL* (likely to be changed or removed in the future
    # without any warning/deprecation/etc.)
    setitem_key_to_target_key = {
        # (trick for non-idempotent adjusters...)
        '_url_data': '_url_data_ready',
    }

    # for the following keys, if the given value is invalid,
    # AdjusterError is not propagated; instead the value is just
    # not stored (and a warning is logged)
    without_adjuster_error = frozenset({
        'fqdn',
        'name',
        'url',
        'url_pattern',
    })

    #
    # Instantiation-related methods

    @classmethod
    def from_json(cls, json_string, **kwargs):
        return cls(json.loads(json_string), **kwargs)

    def __init__(self, iterable_or_mapping=(),
                 log_nonstandard_names=False,
                 context_manager_error_callback=None):
        self._dict = {}
        self._settable_keys = (self.required_keys |
                               self.optional_keys)

        # to catch some kinds of bugs early...
        duplicated = self.required_keys & self.optional_keys
        if duplicated:
            raise ValueError('{} has keys declared both '
                             'as required and optional: {}'
                             .format(self.__class__.__name__,                    #3: `__name__`->`__qualname__`
                                     ', '.join(sorted(duplicated))))

        missing_adjusters = [key for key in self._settable_keys
                             if not hasattr(self, self._adjuster_name(key))]
        if missing_adjusters:
            raise TypeError('{!r} has no adjusters for keys: {}'
                             .format(self,
                                     ', '.join(sorted(missing_adjusters))))

        self.log_nonstandard_names = log_nonstandard_names

        # context-manager (__enter__/__exit__) -related stuff
        self.context_manager_error_callback = context_manager_error_callback
        self.used_as_context_manager = False

        self.update(iterable_or_mapping)

    @classmethod
    def _adjuster_name(cls, key):
        return cls._ADJUSTER_PREFIX + key.replace('-', '')

    #
    # Output-related methods

    def get_ready_dict(self):
        current_keys = set(self._dict)
        assert self._settable_keys >= current_keys
        missing_keys = self.required_keys - current_keys
        if missing_keys:
            raise ValueError('missing keys: ' +
                             ', '.join(sorted(missing_keys)))
        ready_dict = copy.deepcopy(self._dict)
        ######## provide the legacy item
        ######## (needed by old version of RecordDict, in not-yet-updated components)
        used_custom_keys = self.data_spec.custom_field_keys.intersection(ready_dict)
        if used_custom_keys:
            ready_dict['__preserved_custom_keys__'] = sorted(used_custom_keys)
        ######## ^^^ (to be removed later)
        return ready_dict

    def get_ready_json(self):
        # changed from json.dumps on bson.dumps
        ### XXX: why? bson.json_utils.dumps() pre-converts some values, but is it necessary???
        ###      See #3243 (in particular, #note-7)
        return dumps(self.get_ready_dict())

    def iter_db_items(self):
        # to be cloned later (see below)
        item_prototype = {key: value
                          for key, value in self.get_ready_dict().items()
                          if not key.startswith('_')}  # no internal keys

        # pop actual custom items and place them in the "custom" field
        all_custom_keys = self.data_spec.custom_field_keys
        custom_items = {key: item_prototype.pop(key)
                        for key in all_custom_keys
                        if key in item_prototype}
        self._prepare_url_data_items(item_prototype, custom_items)
        if custom_items:
            item_prototype['custom'] = custom_items

        # depending on "address" provide one or more database items (dicts)
        address_list = item_prototype.pop('address', None)  # NOTE: deleting `address`
        if address_list:
            # the `address` list was present and not empty
            # -> db item for each list item (each db item containing
            # `ip`[/`cc`/`asn`] of the list item + the whole `address`)
            item_prototype['address'] = address_list  # restore
            all_addr_keys_are_legal = {'ip', 'cc', 'asn'}.issuperset
            for addr in address_list:
                assert 'ip' in addr and all_addr_keys_are_legal(addr)
                # cloning the prototype dict...
                db_item = item_prototype.copy()
                # ...and updating the copy with particular address data
                db_item.update(addr)
                yield db_item
        else:
            # the `address` list was *empty* or *not* present
            # -> only one db item *without* `address`, `ip` etc.
            yield item_prototype

    # *EXPERIMENTAL* (likely to be changed or removed in the future
    # without any warning/deprecation/etc.)
    def _prepare_url_data_items(self, item_prototype, custom_items):
        url_data = self.get('_url_data_ready')
        if url_data is not None:
            assert 'url_data' not in custom_items
            str = basestring                                                             #3--
            assert isinstance(url_data.get('url_orig'), str)
            url_orig = base64.urlsafe_b64decode(as_bytes(url_data['url_orig']))          #3: `as_bytes(`-- `)--
            item_prototype['url'] = make_provisional_url_search_key(url_orig)  # [sic]
            custom_items['url_data'] = url_data

    __repr__ = attr_repr('_dict')

    #
    # MutableMapping interface implementation

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, key):
        return self._dict[key]

    def __delitem__(self, key):
        del self._dict[key]

    def __setitem__(self, key, value):
        ######## silently ignore the legacy item
        if key == '__preserved_custom_keys__': return
        ######## ^^^ (to be removed later)
        target_key = self.setitem_key_to_target_key.get(key, key)
        try:
            self._dict[target_key] = self._get_adjusted_value(key, value)
        except AdjusterError as exc:
            if key in self.without_adjuster_error:
                LOGGER.warning('Invalid value not stored (%s)', exc)
            else:
                raise

    def _get_adjusted_value(self, key, value):
        if key not in self._settable_keys:
            raise RuntimeError('for {!r}, key {!r} is illegal'
                               .format(self, key))

        adjuster_method_name = self._adjuster_name(key)
        try:
            adjuster = getattr(self, adjuster_method_name)
        except AttributeError:
            raise RuntimeError('{!r} has no adjuster for key {!r}'
                               .format(self, key))
        if adjuster is None:
            # adjuster explicitly set to None -> passing value unchanged
            return value

        try:
            return adjuster(value)
        except Exception as exc:
            if getattr(exc, 'propagate_it_anyway', False):
                raise
            adjuster_error_msg = ('{!r}.{}({value!r}) raised {exc_str}'
                                  .format(self,
                                          adjuster_method_name,
                                          value=value,
                                          exc_str=make_exc_ascii_str(exc)))
            raise AdjusterError(adjuster_error_msg)

    # reimplementation only for speed
    def __contains__(self, key):
        return key in self._dict

    # reimplementation with slightly different interface
    # and some additional guarantees
    def update(self, iterable_or_mapping=()):
        # updating in a deterministic order: sorted by key (thanks to
        # that, in particular, 'category' is set *before* 'name' --
        # see: adjust_name())
        sorted_items = sorted(iterable_or_mapping.items()
                              if isinstance(iterable_or_mapping, collections_abc.Mapping)
                              else iterable_or_mapping)
        setitem = self.__setitem__
        for key, value in sorted_items:
            setitem(key, value)

    # record dicts are always deep-copied (to avoid hard-to-find bugs)
    def copy(self):
        return copy.deepcopy(self)

    __copy__ = copy

    #
    # Context manager interface

    def __enter__(self):
        self.used_as_context_manager = True
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            error_callback = self.context_manager_error_callback
        except AttributeError:
            raise TypeError('a record dict instance cannot be used '
                            'as a guarding context manager more than once')
        try:
            if exc_type is not None and error_callback is not None:
                if exc is None:
                    exc = exc_type()
                return error_callback(exc)
        finally:
            del self.context_manager_error_callback

    #
    # Adjusters

    adjust_id = make_adjuster_using_data_spec('id')
    adjust_rid = make_adjuster_using_data_spec('rid')
    adjust_source = make_adjuster_using_data_spec('source')
    adjust_origin = make_adjuster_using_data_spec('origin')
    adjust_restriction = make_adjuster_using_data_spec('restriction')
    adjust_confidence = make_adjuster_using_data_spec('confidence')
    adjust_category = make_adjuster_using_data_spec('category')
    adjust_md5 = make_adjuster_using_data_spec('md5')
    adjust_sha1 = make_adjuster_using_data_spec('sha1')
    adjust_sha256 = make_adjuster_using_data_spec('sha256')
    adjust_proto = make_adjuster_using_data_spec('proto')
    adjust_sport = make_adjuster_using_data_spec('sport')
    adjust_dport = make_adjuster_using_data_spec('dport')
    adjust_count = make_adjuster_using_data_spec('count')
    adjust_count_actual = make_adjuster_using_data_spec('count_actual')

    adjust_time = chained(
        make_adjuster_using_data_spec('time'),  # will return datetime
        make_adjuster_applying_callable(str))   # will transform it to str

    adjust_modified = chained(
        make_adjuster_using_data_spec('modified'),  # will return datetime
        make_adjuster_applying_callable(str))   # will transform it to str

    adjust_address = chained(
        make_multiadjuster(
            make_dict_adjuster(
                ip=ipv4_preadjuster)),
        applied_for_nonfalse(
            make_adjuster_using_data_spec('address')))

    adjust_dip = chained(
        ipv4_preadjuster,
        make_adjuster_using_data_spec('dip'))

    adjust_url = chained(
        url_preadjuster,
        make_adjuster_using_data_spec(
            'url', on_too_long=trim))

    adjust_fqdn = make_adjuster_using_data_spec(
        'fqdn', on_too_long=trim_domain)

    adjust_client = chained(
        make_multiadjuster(),
        applied_for_nonfalse(
            make_adjuster_using_data_spec('client')))

    adjust_until = chained(
        make_adjuster_using_data_spec('until'),    # will return datetime
        make_adjuster_applying_callable(str))      # will transform it to str

    adjust_expires = chained(
        make_adjuster_using_data_spec('expires'),  # will return datetime
        make_adjuster_applying_callable(str))      # will transform it to str

    adjust_target = make_adjuster_using_data_spec(
        'target', on_too_long=trim)

    adjust_type = make_adjuster_using_data_spec('_type')

    # generic internal field adjusters
    adjust__do_not_resolve_fqdn_to_ip = ensure_isinstance(bool)
    adjust__parsed_old = rd_adjuster

    # *EXPERIMENTAL* internal field adjusters
    # (likely to be changed or removed in the future
    # without any warning/deprecation/etc.)
    adjust__url_data = make_dict_adjuster(
        url_orig=chained(
            unicode_surrogate_pass_and_esc_adjuster,
            make_adjuster_applying_callable(try_to_normalize_surrogate_pairs_to_proper_codepoints),
            make_adjuster_applying_callable(as_bytes),
            make_adjuster_applying_callable(base64.urlsafe_b64encode),
            unicode_adjuster,
            ensure_validates_by_regexp(r'\A[0-9a-zA-Z\-_=]+\Z'),
            ensure_not_longer_than(2 ** 17)),
        url_norm_opts=make_dict_adjuster())
    adjust__url_data_ready = make_dict_adjuster(
        url_orig=chained(
            ensure_isinstance(str, unicode),                                     #3: `unicode`--
            unicode_adjuster,                                                    #3--
            ensure_validates_by_regexp(r'\A[0-9a-zA-Z\-_=]+\Z'),
            ensure_not_longer_than(2 ** 17)),
        url_norm_opts=make_dict_adjuster())

    # hi-freq-only internal field adjusters
    adjust__group = unicode_adjuster
    adjust__first_time = chained(
        make_adjuster_using_data_spec('_first_time'),  # will return datetime
        make_adjuster_applying_callable(str))          # will transform it to str

    # bl-only non-internal field adjusters
    adjust_status = make_adjuster_using_data_spec('status')
    adjust_replaces = make_adjuster_using_data_spec('replaces')

    # bl-only internal field adjusters
    adjust__blseriesno = make_adjuster_using_data_spec('_blseriesno')
    adjust__blseriestotal = make_adjuster_using_data_spec('_blseriestotal')
    adjust__blseriesid = make_adjuster_using_data_spec('_blseriesid')
    adjust__bltime = chained(
        make_adjuster_using_data_spec('_bltime'),  # will return datetime
        make_adjuster_applying_callable(str))      # will transform it to str
    adjust__blcurrenttime = chained(
        make_adjuster_using_data_spec('_blcurrenttime'),
        make_adjuster_applying_callable(str))

    # special custom field adjuster
    # (see the comment in the code of n6.utils.enrich.Enricher.enrich())
    adjust_enriched = make_adjuster_using_data_spec('enriched')

    # custom field adjusters
    adjust_adip = make_adjuster_using_data_spec('adip')

    adjust_additional_data = make_adjuster_using_data_spec(
        'additional_data', on_too_long=trim)

    adjust_alternative_fqdns = chained(
        make_multiadjuster(),
        make_adjuster_using_data_spec(
            'alternative_fqdns',
            on_too_long=trim_domain_seq))

    adjust_block = make_adjuster_using_data_spec('block')
    adjust_description = make_adjuster_using_data_spec(
        'description', on_too_long=trim)

    adjust_ip_network = make_adjuster_using_data_spec('ip_network')

    adjust_min_amplification = make_adjuster_using_data_spec(
        'min_amplification', on_too_long=trim)

    adjust_request = make_adjuster_using_data_spec(
        'request', on_too_long=trim)

    adjust_user_agent = make_adjuster_using_data_spec(
        'user_agent', on_too_long=trim)

    adjust_sender = make_adjuster_using_data_spec(
        'sender', on_too_long=trim)

    adjust_botid = make_adjuster_using_data_spec(
        'botid', on_too_long=trim)

    adjust_method = make_adjuster_using_data_spec(
        'method', on_too_long=trim)

    adjust_channel = make_adjuster_using_data_spec(
        'channel', on_too_long=trim)

    adjust_first_seen = make_adjuster_using_data_spec(
        'first_seen', on_too_long=trim)

    adjust_referer = make_adjuster_using_data_spec(
        'referer', on_too_long=trim)

    adjust_rt = make_adjuster_using_data_spec(
        'rt', on_too_long=trim)

    adjust_proxy_type = make_adjuster_using_data_spec(
        'proxy_type', on_too_long=trim)

    adjust_dns_version = make_adjuster_using_data_spec(
        'dns_version', on_too_long=trim)

    adjust_internal_ip = make_adjuster_using_data_spec(
        'internal_ip', on_too_long=trim)

    adjust_ipmi_version = make_adjuster_using_data_spec(
        'ipmi_version', on_too_long=trim)

    adjust_mac_address = make_adjuster_using_data_spec(
        'mac_address', on_too_long=trim)

    adjust_sysdesc = make_adjuster_using_data_spec(
        'sysdesc', on_too_long=trim)

    adjust_version = make_adjuster_using_data_spec(
        'version', on_too_long=trim)

    adjust_dataset = make_adjuster_using_data_spec(
        'dataset', on_too_long=trim)

    adjust_header = make_adjuster_using_data_spec(
        'header', on_too_long=trim)

    adjust_detected_since = make_adjuster_using_data_spec(
        'detected_since', on_too_long=trim)

    adjust_handshake = make_adjuster_using_data_spec(
        'handshake', on_too_long=trim)

    adjust_cert_length = make_adjuster_using_data_spec(
        'cert_length', on_too_long=trim)

    adjust_subject_common_name = make_adjuster_using_data_spec(
        'subject_common_name', on_too_long=trim)

    adjust_visible_databases = make_adjuster_using_data_spec(
        'visible_databases', on_too_long=trim)

    adjust_url_pattern = make_adjuster_using_data_spec('url_pattern')

    adjust_urls_matched = make_adjuster_using_data_spec('urls_matched')

    adjust_username = make_adjuster_using_data_spec('username')

    adjust_email = make_adjuster_using_data_spec('email')

    adjust_facebook_id = make_adjuster_using_data_spec('facebook_id')

    adjust_iban = make_adjuster_using_data_spec('iban')

    adjust_injects = make_adjuster_using_data_spec('injects')

    adjust_phone = make_adjuster_using_data_spec('phone')

    adjust_registrar = make_adjuster_using_data_spec(
        'registrar', on_too_long=trim)

    adjust_x509fp_sha1 = make_adjuster_using_data_spec('x509fp_sha1')

    adjust_x509issuer = make_adjuster_using_data_spec('x509issuer')

    adjust_x509subject = make_adjuster_using_data_spec('x509subject')

    adjust_action = make_adjuster_using_data_spec('action')

    # The attribute and related methods are left for the backward
    # compatibility with older data from the MISP sources.
    adjust_misp_eventdid = make_adjuster_using_data_spec('misp_eventdid')

    adjust_misp_attr_uuid = make_adjuster_using_data_spec('misp_attr_uuid')

    adjust_misp_event_uuid = make_adjuster_using_data_spec('misp_event_uuid')

    adjust_product = make_adjuster_using_data_spec('product')

    # custom field used for cooperation with IntelMQ
    adjust_intelmq = make_adjuster_using_data_spec('intelmq')

    adjust_tags = chained(
        make_multiadjuster(),
        make_adjuster_using_data_spec(
            'tags',
            on_too_long=trim_seq))

    adjust_filename = make_adjuster_using_data_spec(
        'filename', on_too_long=trim)

    # the `name` adjuster is a bit more complex...
    @preceded_by(unicode_adjuster)
    def adjust_name(self, value):
        category = self.get('category')
        if category is None:
            exc = RuntimeError('cannot set "name" when "category" is not set')
            exc.propagate_it_anyway = True  # let the programmer know it!
            raise exc
        if not value:
            raise ValueError('empty value')
        if category in CATEGORY_TO_NORMALIZED_NAME:
            value = self._get_normalized_name(value, category)
            value = self._adjust_name_according_to_data_spec(value)
            self._check_and_handle_nonstandard_name(value, category)
        else:
            value = self._adjust_name_according_to_data_spec(value)
        return value

    _adjust_name_according_to_data_spec = make_adjuster_using_data_spec(
        'name', on_too_long=trim)

    def _get_normalized_name(self, value, category):
        value = value.lower()
        first_char = value[0]
        normalization = NAME_NORMALIZATION.get(first_char,
                                               NAME_NORMALIZATION['ELSE'])
        for regex, normalized_value in normalization:
            if regex.search(value):
                value = normalized_value
                break
        return value

    def _check_and_handle_nonstandard_name(self, value, category):
        if self.log_nonstandard_names:
            category_std_names = self._get_category_std_names(category)
            if value not in category_std_names:
                self._log_nonstandard_name(value, category)

    def _get_category_std_names(self, category_key):
        while True:
            category_std_names = CATEGORY_TO_NORMALIZED_NAME[category_key]
            str = basestring                                                     #3--
            if not isinstance(category_std_names, str):
                return category_std_names
            category_key = category_std_names

    # private class attribute: a cache of already logged non-standard names
    # -- used in _log_nonstandard_name() to avoid cluttering the logs
    _already_logged_nonstandard_names = LimitedDict(maxlen=10000)

    def _log_nonstandard_name(self, value, category,
                              _already_logged=_already_logged_nonstandard_names):
        if (category, value) not in _already_logged:
            category_sublogger = NONSTANDARD_NAMES_LOGGER.getChild(category)
            category_sublogger.warning(ascii_str(value))
            _already_logged[(category, value)] = None

    #
    # Appenders for multiple-adjusted attributes

    # Providing methods: append_<key> -- for example:
    # * append_address(<singular value>)
    def __getattr__(self, name):
        if name.startswith(self._APPENDER_PREFIX):
            key = name[len(self._APPENDER_PREFIX):]
            adjuster_method_name = self._adjuster_name(key)
            adjuster = getattr(self, adjuster_method_name, None)
            if self._is_multiadjuster(adjuster):
                def appender(singular_value):
                    value_seq = list(self.get(key, []))
                    value_seq.append(singular_value)
                    self[key] = value_seq
                return appender
        raise AttributeError('{.__class__.__name__!r} object has '               #3: `__name__`->`__qualname__`
                             'no attribute {!r}'.format(self, name))

    @staticmethod
    def _is_multiadjuster(adjuster):
        factory_names = getattr(adjuster, '_factory_names', frozenset())
        return ('make_multiadjuster' in factory_names)


class BLRecordDict(RecordDict):

    """
    Record dict class for blacklist events (slightly harder restricted).
    """

    required_keys = RecordDict.required_keys | {'expires'}
    optional_keys = RecordDict.optional_keys - {'expires'}



_data_spec = RecordDict.data_spec
assert _data_spec is BLRecordDict.data_spec

_all_keys = RecordDict.required_keys | RecordDict.optional_keys
assert _all_keys == BLRecordDict.required_keys | BLRecordDict.optional_keys

assert _data_spec.result_field_specs('required').viewkeys() == RecordDict.required_keys
assert _data_spec.all_result_keys == {
    key for key in _all_keys
    if key not in ('type', 'enriched') and not key.startswith('_')}

# Copyright (c) 2013-2024 NASK. All rights reserved.

import collections
import bisect
import contextlib
import copy
import datetime
import fcntl
import fnmatch
import functools
import ipaddress
import json
import math
import os
import pathlib
import pickle
import re
import time
import traceback
import threading
from collections.abc import (
    Iterable,
    Mapping,
)
from typing import (
    TypedDict,
    Union,
)

from sqlalchemy import (
    null,
    text as sqla_text,
)
from sqlalchemy.exc import SQLAlchemyError

from n6lib.api_key_auth_helper import (
    APIKeyAuthError,
    APIKeyAuthHelper,
)
from n6lib.class_helpers import (
    LackOf,
    attr_repr,
)
from n6lib.common_helpers import (
    ascii_str,
    ip_network_as_tuple,
    ip_network_tuple_to_min_max_ip,
    ipv4_to_int,
    make_exc_ascii_str,
    memoized,
    deep_copying_result,
)
from n6lib.config import (
    Config,
    ConfigError,
    ConfigMixin,
    combined_config_spec,
)
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.context_helpers import ThreadLocalContextDeposit
from n6lib.data_selection_tools import (
    Cond,
    CondBuilder,
    CondVisitor,
    CondTransformer,
    CondDeMorganTransformer,
    CondEqualityMergingTransformer,
    CondFactoringTransformer,
    ## XXX: uncomment when predicates stuff in `_DataPreparer` supports new `Cond` et consortes.
    #CondPredicateMaker,
    EqualCond,
    InCond,
    IsNullCond,
    IsTrueCond,
    OrCond,
    RecItemCond,
)
from n6lib.db_events import n6NormalizedData
from n6lib.db_filtering_abstractions import (
    BaseCond as LegacyBaseCond,
    PredicateConditionBuilder as LegacyPredicateConditionBuilder,
    SQLAlchemyConditionBuilder as LegacySQLAlchemyConditionBuilder,
)
from n6lib.file_helpers import SignedStampedFileAccessor
from n6lib.jwt_helpers import (
    JWT_ALGO_RSA_SHA256,
    JWTDecodeError,
    jwt_decode,
)
from n6lib.log_helpers import get_logger
from n6lib.ldap_api_replacement import (
    LdapAPI,
    LdapAPIReplacementWrongOrgUserAPIKeyIdError,
    get_attr_value,
    get_attr_value_list,
    get_dn_segment_value,
    get_node,
)
from n6lib.threaded_async import LoopedTask
from n6lib.typing_helpers import (
    AccessZone,
    EventDataResourceId,
)
from n6sdk.addr_helpers import IPv4Container



__all__ = (
    'DEFAULT_MAX_DAYS_OLD',
    'DEFAULT_RESOURCE_LIMIT_WINDOW',
    'RESOURCE_ID_TO_ACCESS_ZONE',
    'EVENT_DATA_RESOURCE_IDS',
    'ACCESS_ZONE_TO_RESOURCE_ID',
    'ACCESS_ZONES',

    'AuthAPIError',
    'AuthAPIUnauthenticatedError',
    'AuthAPICommunicationError',

    'AuthAPI',
    'AuthAPIWithPrefetching',
    'InsideCriteriaResolver',
)



LOGGER = get_logger(__name__)



DEFAULT_MAX_DAYS_OLD = 100
DEFAULT_RESOURCE_LIMIT_WINDOW = 3600

# As you can see here, there is a direct 1-to-1 relation between the
# three REST API *event data resources* (aka "data stream" resources)
# and the three *access zones*.
RESOURCE_ID_TO_ACCESS_ZONE = {
    '/report/inside': 'inside',
    '/report/threats': 'threats',
    '/search/events': 'search',
}
EVENT_DATA_RESOURCE_IDS = frozenset(RESOURCE_ID_TO_ACCESS_ZONE)
ACCESS_ZONE_TO_RESOURCE_ID = dict(
    (az, res_id)
    for res_id, az in RESOURCE_ID_TO_ACCESS_ZONE.items())
ACCESS_ZONES = frozenset(ACCESS_ZONE_TO_RESOURCE_ID)

assert set(AccessZone.__args__) == ACCESS_ZONES
assert set(EventDataResourceId.__args__) == EVENT_DATA_RESOURCE_IDS

_BOOL_TO_FLAG = {True: 'TRUE', False: 'FALSE'}
_FLAG_TO_BOOL = {f: b for b, f in _BOOL_TO_FLAG.items()}



class AuthAPIError(Exception):
    """Base class for AuthAPI-specific errors."""


class AuthAPIUnauthenticatedError(AuthAPIError):
    """Raised when authentication failed."""


class AuthAPICommunicationError(AuthAPIError):

    """Raised when low-level communication is broken."""

    def __init__(self, exc_info_msg, low_level_exc=None):
        super().__init__(self, exc_info_msg, low_level_exc)
        self.exc_info_msg = exc_info_msg
        self.low_level_exc = low_level_exc

    def __str__(self):
        return self.exc_info_msg



# This is a decorator for those `AuthAPI` methods which use `AuthAPI`'s
# `get_ldap_root_node()`. Those *methods must be argumentless*. Their
# return values are always memoized per *root node* object (that is, as
# long as `AuthAPI`'s `_get_root_node()` returns the same object).
def cached_basing_on_ldap_root_node(func):
    NO_RESULT = object()
    mutex = threading.RLock()
    method_name = func.__name__

    @functools.wraps(func)
    def func_wrapper(self):
        with self:
            root_node = self.get_ldap_root_node()
            cache = root_node['_method_name_to_result_']

            with mutex:
                result = cache.get(method_name, NO_RESULT)
                if result is NO_RESULT:
                    result = cache[method_name] = func(self)

            return result

    func_wrapper.func = func  # making the original function still available

    _names_of_methods_cached_basing_on_ldap_root_node.add(method_name)
    return func_wrapper

_names_of_methods_cached_basing_on_ldap_root_node = set()


class AuthAPI(ConfigMixin):

    """
    An API that provides common set of authentication/authorization methods.

    The constructor takes one optional argument: `settings` (to be used
    by n6lib.ldap_api_replacement.LdapAPI constructor; see also the docs
    of the n6lib.config.Config class).

    Use the (reentrant) context manager interface to ensure that a series
    of method calls will be consistent in terms of LDAP data state (i.e.
    all the calls will use the same set of data, produced with the same
    LDAP query).  Example:

        with auth_api:
            inside_crit_resolver = auth_api.get_inside_criteria_resolver()
            org_id_to_acc_inf = auth_api.get_org_ids_to_access_infos()

    **Note:** N6ConfigHelper (defined in n6lib.pyramid_commons) installs
    a tween which makes the whole view-level handling of each Pyramid
    request (including the entire process of generating the chunks of a
    stream response) be automatically wrapped in the Auth API's context
    manager (see: n6lib.pyramid_commons.auth_api_context_tween_factory).
    """

    config_spec = combined_config_spec('''
        [api_key_based_auth]
        server_secret = :: str
    ''')

    def __init__(self, settings=None):
        self.__last_root_node = None
        self._root_node_deposit = ThreadLocalContextDeposit(repr_token=self.__class__.__qualname__)
        self._config_full = self.get_config_full(settings)
        self._ldap_api = LdapAPI(settings)
        self._data_preparer = _DataPreparer()
        self._api_key_auth_helper = APIKeyAuthHelper(
            self._config_full['api_key_based_auth']['server_secret'],
            self._authenticate_with_user_id_and_api_key_id)


    #
    # Context manager interface

    def __enter__(self):
        self._root_node_deposit.on_enter(outermost_context_factory=self._get_root_node)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._root_node_deposit.on_exit(exc_type, exc, tb)


    #
    # Public methods + their private helpers

    # WARNING: when you call this function you should *never* modify its results!
    def get_ldap_root_node(self):
        root_node = self._root_node_deposit.outermost_context
        if root_node is None:
            root_node = self._get_root_node()
        return root_node

    def is_api_key_authentication_enabled(self):
        return self._api_key_auth_helper.is_api_key_authentication_enabled()

    def get_api_key_as_jwt_or_none(self, user_id, api_key_id):
        return self._api_key_auth_helper.get_api_key_as_jwt_or_none(user_id, api_key_id)

    def authenticate_with_api_key(self, api_key):
        try:
            auth_data = self._api_key_auth_helper.authenticate_with_api_key(api_key)
        except APIKeyAuthError as exc:
            raise AuthAPIUnauthenticatedError from exc
        return auth_data

    # noinspection PyMethodMayBeStatic
    def authenticate_with_oidc_access_token(self,
                                            access_token,
                                            json_web_key,
                                            required_claims,
                                            decoding_options=None,
                                            audience=None):
        try:
            return jwt_decode(access_token,
                              json_web_key,
                              accepted_algorithms=(JWT_ALGO_RSA_SHA256,),
                              required_claims=required_claims,
                              options=decoding_options,
                              required_audience=audience)
        except JWTDecodeError as exc:
            LOGGER.warning(exc)
            raise AuthAPIUnauthenticatedError

    # (see `self._api_key_auth_helper` initialized in `__init__()`)
    def _authenticate_with_user_id_and_api_key_id(self, user_id, api_key_id):
        auth_data = self._get_auth_data_for_user_id(user_id)
        org_id = auth_data['org_id']
        assert auth_data == {'user_id': user_id, 'org_id': org_id}
        try:
            self._ldap_api.authenticate_with_api_key_id(org_id, user_id, api_key_id)
        except LdapAPIReplacementWrongOrgUserAPIKeyIdError as exc:
            raise AuthAPIUnauthenticatedError from exc
        return auth_data

    def _get_auth_data_for_user_id(self, user_id):
        """
        Verify that the given `user_id` is the login of an existing and
        non-blocked user, then return an appropriate *auth data* dict.

        Args:
            `user_id`: user id (login) as a str.

        Returns:
            {'org_id': <organization id (str)>,
             'user_id': <user id *aka* login> (str)}

        Raises:
            AuthAPIUnauthenticatedError if:
            * the given `user_id` is empty, or
            * the user does not exist, or
            * the user is blocked.
        """
        if not user_id:
            raise AuthAPIUnauthenticatedError
        user_ids_to_org_ids = self.get_user_ids_to_org_ids()
        try:
            org_id = user_ids_to_org_ids[user_id]
        except KeyError:
            raise AuthAPIUnauthenticatedError
        assert user_id is not None
        assert org_id is not None
        return {'user_id': user_id, 'org_id': org_id}

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_user_ids_to_org_ids(self):
        """
        Returns the user-id-to-org-id mapping (as a dict).

        (*Only* non-blocked users are included.)
        """
        return self._data_preparer.get_user_ids_to_org_ids(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_org_ids(self):
        """
        Returns a frozenset of all organization ids (typically, already cached).
        """
        return self._data_preparer.get_org_ids(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as InsideCriteriaResolver's
    # public interface does not include any mutating methods or properties
    @cached_basing_on_ldap_root_node
    def get_inside_criteria_resolver(self):
        """
        Returns an InsideCriteriaResolver instance (typically already cached).
        """
        return self._data_preparer.get_inside_criteria_resolver(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as the public interface
    # of the returned object does not include any mutating methods or properties
    @cached_basing_on_ldap_root_node
    def get_ignore_lists_criteria_resolver(self):
        """
        Returns a callable object (typically already cached) which,
        when applied to a `RecordDict`, returns `True` if the event
        represented by it should be makred as *ignored*, and `False`
        otherwise.
        """
        return self._data_preparer.get_ignore_lists_criteria_resolver(
            self.get_ldap_root_node())

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_anonymized_source_mapping(self):
        """
        Returns a dict (typically already cached):

        {
            'forward_mapping': {
                 <source id (str)>: <anonymized source id (str)>,
                 ...
            },
            'reverse_mapping': {
                 <anonymized source id (str)>: <source id (str)>,
                 ...
            },
        }
        """
        return self._data_preparer.get_anonymized_source_mapping(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_dip_anonymization_disabled_source_ids(self):
        """
        Returns a frozenset of source ids (typically already cached) for
        which anonymization of `dip` is *not enabled*.
        """
        return self._data_preparer.get_dip_anonymization_disabled_source_ids(
            self.get_ldap_root_node())

    #@deep_copying_result <- we cannot use it here as part of defensive programming
    #                        because there are problems with copying ColumnElement objects
    #                        (instead, you need to be careful: to *never* modify resulting dicts)
    def get_access_info(self, auth_data):
        """
        Get the REST API access information for the specified organization.

        Args:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id (str)>, 'user_id': <user id *aka* login (str)>}.

        Returns:
            None or a dictionary (for a single organization), provided by
            executing the following procedure:

            * (1) invoke `<AuthAPI obj>.get_org_ids_to_access_infos().get(<org id>)`,
            * (2) then:
              * (a) if the result is None or the legacy mode is active, return
                that result intact;
              * (b) otherwise, make a deep copy of that result and then convert
                all `n6lib.data_selection_tools.Cond` instances in the contents
                of the `access_zone_conditions` items of that copy (in place)
                to instances of `sqlalchemy.sql.expression.ColumnElement` (that
                represent SQL conditions).

        Note: even if the organization exists, this method may still
        return None (this is the case when the organization has no
        access to any subsource for any access zone).
        """
        org_id = auth_data['org_id']
        all_access_infos = self.get_org_ids_to_access_infos()
        access_info = all_access_infos.get(org_id)
        if (access_info is not None
              and not self._data_preparer._using_legacy_version_of_access_filtering_conditions):
            access_info = self._data_preparer.obtain_ready_access_info(access_info)
        assert (access_info is None
                or (isinstance(access_info, dict)
                    and access_info.keys() == {
                        'access_zone_conditions',
                        'rest_api_resource_limits',
                        'rest_api_full_access',
                    }
                    and (isinstance(access_info['access_zone_conditions'], dict)
                         and access_info['access_zone_conditions'].keys()
                             <= ACCESS_ZONES)
                    and (isinstance(access_info['rest_api_resource_limits'], dict)
                         and access_info['rest_api_resource_limits'].keys()
                             <= EVENT_DATA_RESOURCE_IDS)
                    and isinstance(access_info['rest_api_full_access'], bool)))
        return access_info

    #@deep_copying_result <- we cannot use it here as part of defensive programming
    #                        because there are problems with copying ColumnElement objects
    #                        (instead, you need to be careful: to *never* modify resulting dicts)
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_access_infos(self):
        """
        Get a dict that maps organization ids to REST API access information.

        Returns a dict (typically already cached):

        {
            <organization id (str)>: {
                'access_zone_conditions': {
                    <access zone: 'inside' or 'threats' or 'search'>: [
                        <an instance of `n6lib.data_selection_tools.Cond` (or of
                         `sqlalchemy.sql.expression.ColumnElement` in the legacy mode),
                         representing subsources criteria + `full_access` flag etc.>,
                        ...
                    ],
                    ...
                },
                'rest_api_resource_limits': {
                    <resource id (one of EVENT_DATA_RESOURCE_IDS)>: {
                        'window': <int>,
                        'queries_limit': <int>,
                        'results_limit': <int>,
                        'max_days_old': <int>,
                        'request_parameters': <None or {
                            <user query parameter name>: <is required?
                                                          -- True or False>
                            ...
                        }>,
                    },
                    ...
                'rest_api_full_access': <True or False>,
                },
            },
            ...
        }

        Note that:

        * Organizations for whom some (or even all) REST API "data
          stream" resources are *disabled* (i.e., whose `access_to_...`
          flags are False) *are still included* -- but **with the
          reservation of the next point** (below).

        * NOTE, however, that organizations that do *not* have access to
          any subsource for any access zone *are excluded*.

        * The `access_zone_conditions` information includes only access
          zones for whom the given organization does have access to any
          subsource.

        * Only the event data resources of REST API (those identified
          by the resource ids: '/report/inside', '/report/threats',
          '/search/events') are covered by the `rest_api_resource_limits`
          information -- and *only provided that* the given resource is
          enabled for the given organization, i.e., the organization's
          LDAP entry *does* have the appropriate `cn=res-...'  child
          entry.

        Also, note that the behaviour described above is -- in some
        important aspects -- different than the behaviour of the
        get_source_ids_to_subs_to_stream_api_access_infos() and
        get_source_ids_to_notification_access_info_mappings() methods.

        Important: access conditions already include the `restriction !=
        'internal'` condition for organizations for whom
        `rest_api_full_access` is False.
        """
        result = self._data_preparer.get_org_ids_to_access_infos(
            self.get_ldap_root_node())
        return result

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    def get_org_actual_name(self, auth_data):
        """
        Get the *actual name* (aka `name`) of the specified organization
        (if the organization exists *and* has its *actual name*;
        otherwise `None` is got).

        Args:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id (str)>, 'user_id': <user id *aka* login (str)>}.

        Returns:
            None or a str (for a single organization), provided by
            getting: <AuthAPI instance>.get_org_ids_to_actual_names().get(<org id>)
        """
        org_id = auth_data['org_id']
        all_actual_names = self.get_org_ids_to_actual_names()
        return all_actual_names.get(org_id)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_actual_names(self):
        """
        Get a dict that maps str objects being organization identifiers
        to str objects being the organizations' *actual names*.

        The dict includes only organizations that have *actual names* set.
        """
        return self._data_preparer.get_org_ids_to_actual_names(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as the
    # `get_org_ids_to_combined_configs()` method (which is called
    # from this method) is already wrapped using that decorator
    def get_combined_config(self, auth_data):
        """
        Get the combined config (related to e-mail notifications and the
        "inside" criteria used by n6filter) for the specified organization.

        Args:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id (str)>, 'user_id': <user id *aka* login (str)>}.

        Returns:
            None or a dictionary (for a single organization), provided by
            getting: <AuthAPI instance>.get_org_ids_to_combined_configs().get(<org id>)
        """
        org_id = auth_data['org_id']
        all_combined_configs = self.get_org_ids_to_combined_configs()
        return all_combined_configs.get(org_id)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_combined_configs(self):
        """
        Get a dict that maps organization ids to their combined configs
        related to e-mail notifications and to "inside" criteria used by
        n6filter.

        Returns a dict (typically already cached):

        {
            <org id>: {
                'email_notifications': {                                 # optional
                    'email_notification_addresses': [<str>, ...],                  # sorted
                    'email_notification_times': [<datetime.time>, ...],            # sorted
                    'email_notification_language': <str>,                          # optional
                    'email_notification_business_days_only': <bool>,
                },
                'inside_criteria': {                                     # optional
                    'fqdn_seq': [<fqdn (str)>, ...],                               # sorted
                    'asn_seq': [<asn (int)>, ...],                                 # sorted
                    'cc_seq': [<cc (str)>, ...],                                   # sorted
                    'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],   # sorted
                    'url_seq': [<url (str)>, ...],                                 # sorted
                },
            },
            ...
        }

        The key of each item of the resultant dict is the identifier
        of an organization.

        The value of each item of the resultant dict is also a dict;
        it contains up to two items, which are the following:

        * the `email_notifications` item (if present) is
          a dict containing the same data as returned by
          `get_org_ids_to_notification_configs()`, but:

            * omitting the `name` and `n6stream-api-enabled` items;

            * having rest of the keys adjusted in such a way that
              all `n6email-notifications` prefixes are replaced
              with `email_notification` ones, and with all `-`
              characters replaced with `_` (in other words,
              adjusted to be consistent with the names of the
              corresponding attributes of `n6lib.auth_db.models.Org`,
              rather than the legacy LDAP attributes).

        * the `inside_criteria` item (if present) is a
          dict containing the same data as a non-empty
          dict that is an item of the list returned by
          `_get_inside_criteria()`, but:

          * omitting the `org_id` item;

          * with all lists (which are the dict's values)
            being sorted.
        """
        return self._data_preparer.get_org_ids_to_combined_configs(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_stream_api_enabled_org_ids(self):
        """
        Returns a frozenset of ids (typically, already cached) of the
        organizations for whom the `n6stream-api-enabled` flag is set
        to "TRUE".
        """
        return self._data_preparer.get_stream_api_enabled_org_ids(
            self.get_ldap_root_node())

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_stream_api_disabled_org_ids(self):
        """
        Returns a frozenset of ids (typically, already cached) of the
        organizations for whom the `n6stream-api-enabled` flag is set
        to "FALSE", or to some illegal content (e.g., multiple values).
        """
        return self._data_preparer.get_stream_api_disabled_org_ids(
            self.get_ldap_root_node())

    #@deep_copying_result <- we do not want it here -- per analogiam to
    #                        `get_source_ids_to_notification_access_info_mappings()` [see below]
    #                        (instead, you need to be careful: to *never* modify resulting objects)
    @cached_basing_on_ldap_root_node
    def get_source_ids_to_subs_to_stream_api_access_infos(self):
        """
        Get a dict that maps source ids to per-subsource Stream (STOMP) API
        access information.

        Returns a dict (typically already cached):

        {
            <source id>: {
                <subsource DN (str)>: (
                    <filtering predicate: a callable that takes an instance of
                     n6lib.db_filtering_abstractions.RecordFacadeForPredicates
                     as the sole argument and returns True or False>,
                    {
                        'inside': <set of organization ids (str)>,
                        'threats': <set of organization ids (str)>,
                        'search': <set of organization ids (str)>,
                    }
                ),
                ...
            },
            ...
        }

        -- *excluding* organizations for whom:

        * stream API is not enabled (the `n6stream-api-enabled` flag
          is not set to sole "TRUE"), or

        * the REST API (sic!) resource that corresponds to the given
          access zone is disabled (the child LDAP entry `cn=res-...` is
          missing).

        Note that the three access zone keys ('inside', 'threats',
        'search') are always present (even when a given set of
        organization ids is empty).

        However, subsources (and sources) for whom there are no
        organizations (*non-excluded* ones) for any access zone
        -- are omitted entirely.

        Important: *all* predicates already include the `restriction !=
        'internal'` condition (because, for Stream API, all
        organizations are treated as they had *no full access*).
        """
        return self._data_preparer.get_source_ids_to_subs_to_stream_api_access_infos(
            self.get_ldap_root_node())

    #@deep_copying_result <- we do not want it here -- because profiling of *n6counter* revealed
    #                        an unacceptable performance penalty
    #                        (instead, you need to be careful: to *never* modify resulting objects)
    @cached_basing_on_ldap_root_node
    def get_source_ids_to_notification_access_info_mappings(self):
        """
        Get a dict that maps source ids to per-subsource access information
        related to e-mail notifications.

        Returns a dict (typically already cached):

        {
            <source id>: {
                (<subsource DN (str)>, <for full access orgs? (bool)>): (
                    <filtering predicate: a callable that takes an instance of
                      n6lib.db_filtering_abstractions.RecordFacadeForPredicates
                      as the sole argument and returns True or False>,
                    <set of organization ids (str)>,
                ),
                ...
            },
            ...
        }

        -- *excluding* organizations for whom:

        * email notifications are not enabled (the
          `n6email-notifications-enabled` flag is not set to sole
          "TRUE"), or

        * the REST API (sic!) resource that corresponds to the 'inside'
          access zone is disabled (the child LDAP entry `cn=res-inside`
          is missing).

        Note than this method is related to the 'inside' access zone
        only.

        Also, note that subsources (and sources) for whom there are no
        organizations (*non-excluded* ones) for the 'inside' access zone
        -- are just omitted.

        Important: predicates *for non-full-access organizations*
        already include the `restriction != 'internal'` condition.
        """
        return self._data_preparer.get_source_ids_to_notification_access_info_mappings(
            self.get_ldap_root_node())

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_notification_configs(self):
        """
        Get a dict that maps organization ids to e-mail notification configs.

        Returns a dict (typically already cached):

        {
            <org id>: {
                'name': <a str or False (bool)>,
                'n6stream-api-enabled': <bool>,
                'n6email-notifications-address': [<str>, ...],            # sorted
                'n6email-notifications-times': [<datetime.time>, ...],    # sorted
                'n6email-notifications-language': <str>,                  # optional
                'n6email-notifications-business-days-only': <bool>,
            },
            ...
        }

        Organizations for whom e-mail notifications are not enabled (the
        `n6email-notifications-enabled` flag is not set to sole "TRUE")
        are *not* included.

        A value for 'n6email-notifications-address'
        or 'n6email-notifications-times' is always
        a sorted list; it can be an empty list.
        """
        return self._data_preparer.get_org_ids_to_notification_configs(
            self.get_ldap_root_node())

    #
    # Non-public (but overridable) methods

    @memoized(expires_after=600, max_size=3)
    def _get_root_node(self):
        if not self._is_up_to_date(self.__last_root_node):
            self.__last_root_node = None  # (root nodes may take huge amounts of memory)
            self.__last_root_node = self._fetch_fresh_root_node(self._ldap_api)
        return self.__last_root_node

    def _is_up_to_date(self, root_node):
        if root_node is not None:
            ver, timestamp = self._peek_database_ver_and_timestamp(self._ldap_api)
            extra = root_node['_extra_']
            return bool(ver == extra['ver']
                        and timestamp == extra['timestamp'])
        return False

    @staticmethod
    def _peek_database_ver_and_timestamp(ldap_api_cm):
        try:
            with ldap_api_cm as ldap_api:
                return ldap_api.peek_database_ver_and_timestamp()
        except SQLAlchemyError as exc:
            raise AuthAPICommunicationError(traceback.format_exc(), exc)

    @staticmethod
    def _fetch_fresh_root_node(ldap_api_cm):
        try:
            with ldap_api_cm as ldap_api:
                root_node = ldap_api.search_structured()
        except SQLAlchemyError as exc:
            raise AuthAPICommunicationError(traceback.format_exc(), exc)
        else:
            root_node['_method_name_to_result_'] = {}
            return root_node



class AuthAPIWithPrefetching(AuthAPI):

    """
    A variant of the Auth API that spawns an internal *prefetch task*
    that refreshes the data cache in the background. Thanks to that we
    can eliminate the nasty delays the base variant of Auth API suffers
    from when there is a need to load fresh data.
    """

    # Note: we want the *prefetch task* to repeatedly obtain the
    # following data in the background (as obtaining them in the
    # foreground would be too much time-consuming, at least in
    # the case of the REST API and Portal):
    #
    # * the *root node*, i.e., the result of calling the
    #   `LdapAPI`'s method `search_structured()` (which
    #   involves a lot of Auth DB queries as well as much
    #   of Python-level data processing);
    #
    # * the results of certain Auth API's public methods
    #   -- such ones that use the *root node* as their input,
    #   and involve much of additional time-consuming data
    #   processing.
    #
    # At the same time, we *do* want to keep the guarantee that Auth
    # API's public methods provide consistent results when used within
    # the same `with <Auth API instance>:` block.  That's why the task's
    # future object provides the most recently fetched *root node* as
    # its result -- after populating its '_method_name_to_result_' item
    # (being the `@cached_basing_on_ldap_root_node`'s machinery cache
    # dict) with results of most time-consuming public methods of Auth
    # API.


    #
    # Configuration-related stuff

    config_spec = combined_config_spec('''
        [auth_api_prefetching]

        max_sleep_between_runs = 12 :: int
        tolerance_for_outdated = 300 :: int
        tolerance_for_outdated_on_error = 1200 :: int

        pickle_cache_dir = :: path_or_none
        pickle_cache_signature_secret = :: secret_or_none
    ''')

    @property
    def custom_converters(self):
        SECRET_MIN_LENGTH = 64

        conv_path = Config.BASIC_CONVERTERS['path']
        conv_bytes = Config.BASIC_CONVERTERS['bytes']

        def conv_path_or_none(val):
            if not val.strip():
                return None
            return conv_path(val)

        def conv_secret_or_none(val):
            if not val.strip():
                return None
            if len(val) < SECRET_MIN_LENGTH:
                raise ValueError(f'not allowed to be shorter than {SECRET_MIN_LENGTH} characters')
            return conv_bytes(val)

        return {
            'path_or_none': conv_path_or_none,
            'secret_or_none': conv_secret_or_none,
        }

    def get_config_full(self, /, *args, **kwargs):
        SECT = 'auth_api_prefetching'
        OPT_TO_MINIMUM_VALUE = {
            'max_sleep_between_runs': 5,
            'tolerance_for_outdated': 60,
            'tolerance_for_outdated_on_error': 0,
        }
        DIR_OPT = 'pickle_cache_dir'
        SECRET_OPT = 'pickle_cache_signature_secret'
        config_full = super().get_config_full(*args, **kwargs)
        config = config_full[SECT]
        for opt, min_value in OPT_TO_MINIMUM_VALUE.items():
            if config[opt] < min_value:
                raise ConfigError(f'{SECT}.{opt} is too small (should be >= {min_value!a})')
        if config[DIR_OPT] is not None and config[SECRET_OPT] is None:
            raise ConfigError(f'`{SECT}.{DIR_OPT}` is set, whereas `{SECT}.{SECRET_OPT}` is not')
        if config[SECRET_OPT] is not None and config[DIR_OPT] is None:
            raise ConfigError(f'`{SECT}.{SECRET_OPT}` is set, whereas `{SECT}.{DIR_OPT}` is not')
        assert (config[DIR_OPT] and config[SECRET_OPT]
                or (config[DIR_OPT] is None and config[SECRET_OPT] is None))
        return config_full


    #
    # Initialization

    def __init__(self, settings=None):
        super().__init__(settings=settings)

        self._prefetch_task_data_preparer = _DataPreparer()

        (task_target_func,
         loop_iteration_hook) = self._get_prefetch_task_functions()

        prefetch_task_initial_trigger_event = threading.Event()

        self._prefetch_task = LoopedTask(
            target=task_target_func,
            loop_iteration_hook=loop_iteration_hook,
            cancel_and_join_at_python_exit=True,

            # This initial suspension is added to make sure that the
            # *tick-callback*-related stuff (see below...) is set up
            # before the start of the actual task's operation.
            initial_trigger_event=prefetch_task_initial_trigger_event)

        self._future = self._prefetch_task.async_start()

        backends_tick_callback = self._get_backends_tick_callback_checking_for_cancel(self._future)
        # Note: the `backends_tick_callback` callable does *not* need to
        # be thread-safe because all relevant uses of `self._ldap_api`
        # and `self._prefetch_task_data_preparer` are local to the
        # prefetching task thread.
        self._ldap_api.tick_callback = backends_tick_callback
        self._prefetch_task_data_preparer.tick_callback = backends_tick_callback

        prefetch_task_initial_trigger_event.set()


    #
    # Overridden `AuthAPI` methods

    def _get_root_node(self):
        return self._future.result()


    #
    # Internal helpers

    _NAMES_OF_METHODS_WITH_RESULT_PREFETCHING = (
        'get_org_ids_to_access_infos',
        'get_org_ids_to_combined_configs',
    )

    def _get_prefetch_task_functions(self):

        # Dedicated `_DataPreparer` instance

        preparer = self._prefetch_task_data_preparer  # (see above: `__init__()`)


        # Local constants

        assert all(
            (method_name in _names_of_methods_cached_basing_on_ldap_root_node
             and hasattr(self, method_name)
             and hasattr(preparer, method_name))
            for method_name in self._NAMES_OF_METHODS_WITH_RESULT_PREFETCHING)

        METHOD_NAME_TO_OBJ = {
            method_name: getattr(preparer, method_name)
            for method_name in self._NAMES_OF_METHODS_WITH_RESULT_PREFETCHING}

        SAFE_RESERVE_MULTIPLIER = 1.5

        (MAX_SLEEP_BETWEEN_RUNS,
         TOLERANCE_FOR_OUTDATED,
         TOLERANCE_FOR_OUTDATED_ON_ERROR,
         PICKLE_FILE_PATH,
         PICKLE_SIGNATURE_SECRET) = self._get_configured_values()

        assert isinstance(MAX_SLEEP_BETWEEN_RUNS, int)
        assert isinstance(TOLERANCE_FOR_OUTDATED, int)
        assert isinstance(TOLERANCE_FOR_OUTDATED_ON_ERROR, int)
        assert (isinstance(PICKLE_FILE_PATH, pathlib.Path) and PICKLE_FILE_PATH.is_absolute() and
                isinstance(PICKLE_SIGNATURE_SECRET, bytes) and PICKLE_SIGNATURE_SECRET
                or (PICKLE_FILE_PATH is None and
                    PICKLE_SIGNATURE_SECRET is None))

        PICKLE_CACHE_ENABLED = (PICKLE_FILE_PATH is not None)


        # Helper stuff (implemented outside this method)

        peek_database_ver_and_timestamp = functools.partial(
            self._peek_database_ver_and_timestamp,
            self._ldap_api)

        fetch_fresh_root_node = functools.partial(
            self._fetch_fresh_root_node,
            self._ldap_api)

        if PICKLE_CACHE_ENABLED:
            pickle_storage = _PrefetchingPickleStorage(
                PICKLE_FILE_PATH,
                pickle_signature_secret=PICKLE_SIGNATURE_SECRET)
            synchronizer = _InterprocessPrefetchingSynchronizer(
                PICKLE_FILE_PATH,
                min_safe_job_duration=(MAX_SLEEP_BETWEEN_RUNS * SAFE_RESERVE_MULTIPLIER))
        else:
            pickle_storage = None
            synchronizer = contextlib.ExitStack()  # <- (dummy synchronizer)


        # State variables

        sleep = MAX_SLEEP_BETWEEN_RUNS
        last_root_node = LackOf


        # Actual implementation

        def task_target_func():
            LOGGER.info('Prefetching task *starts*...')

            while True:
                try:
                    root_node = _try_to_prefetch()
                except Exception as exc:
                    fallback_root_node = _handle_prefetching_error(exc)
                    assert fallback_root_node
                    return fallback_root_node

                if root_node is not None:
                    break

            _log_prefetching_success(root_node)
            assert root_node
            return root_node


        def loop_iteration_hook(future):
            nonlocal last_root_node
            last_root_node = future.peek_result(default=LackOf)

            future.sleep_until_cancelled(sleep)


        def _try_to_prefetch():
            with synchronizer:
                database_ver, database_ts = peek_database_ver_and_timestamp()
                pickle_ver, pickle_ts, recent_job_duration = _maybe_get_pickle_meta_values()
                last_ver, last_ts = _maybe_get_last_root_node_ver_and_timestamp()

                (pickle_ver, pickle_ts, recent_job_duration,
                 last_ver, last_ts,
                 ) = _initial_checks_and_adjustments(database_ver, database_ts,
                                                     pickle_ver, pickle_ts, recent_job_duration,
                                                     last_ver, last_ts)

                assert pickle_ver <= database_ver or not pickle_ver
                assert last_ver <= database_ver or not last_ver
                assert last_ver <= pickle_ver or not last_ver or not pickle_ver

                _set_sleep(MAX_SLEEP_BETWEEN_RUNS)

                if last_ver == database_ver:
                    LOGGER.info("The last returned root node is still "
                                "the fresh one => let's use it again.")
                    return last_root_node
                if last_ver and (last_ver == pickle_ver or not pickle_ver):
                    assert last_ver < database_ver
                    sleep_val = _compute_sleep_if_timestamp_ok(last_ts, recent_job_duration)
                    if sleep_val is not None:
                        LOGGER.info("The last returned root node is "
                                    "sufficiently new => let's use it again.")
                        _set_sleep(sleep_val)
                        return last_root_node

                if not PICKLE_CACHE_ENABLED:
                    LOGGER.info("OK, it's time to obtain a fresh root node.")
                    return _load_fresh_root_node()

                with _catching_and_logging_unpickling_error():
                    if pickle_ver == database_ver:
                        LOGGER.info("The pickled root node is the "
                                    "fresh one => let's unpickle it.")
                        return _unpickle_root_node(pickle_ver, pickle_ts)
                    if pickle_ver:
                        assert pickle_ver < database_ver
                        sleep_val = _compute_sleep_if_timestamp_ok(pickle_ts, recent_job_duration)
                        if sleep_val is not None:
                            LOGGER.info("The pickled root node is sufficiently "
                                        "new => let's unpickle it.")
                            unpickled_root_node = _unpickle_root_node(pickle_ver, pickle_ts)
                            _set_sleep(sleep_val)
                            return unpickled_root_node

                LOGGER.info("OK, it's time to obtain a fresh root node.")
                assert isinstance(synchronizer, _InterprocessPrefetchingSynchronizer)
                if synchronizer.designate_loading_and_pickling_job():
                    # OK, it is *us* (the current process) who has been
                    # designated to do the job of loading and pickling
                    # fresh data... So let us do it!
                    job_start_monotime = time.monotonic()
                    root_node = _load_fresh_root_node()
                    job_duration = _pickle_root_node(root_node, job_start_monotime)
                    assert _is_nonnegative_finite(job_duration)

                    # And then, let us allow other processes (if any)
                    # to unpickle what we just loaded and pickled...
                    synchronizer.wait_giving_others_chance_to_unpickle(job_duration)

                    # We have served others, let us also serve ourselves. :-)
                    return root_node

                # OK, some other process is doing the job of loading and
                # pickling fresh data... Let us make this function be
                # invoked again immediately, so that we will be able to
                # unpickle that fresh data (*root node*) as soon as it
                # is ready.
                return None

        def _maybe_get_pickle_meta_values():
            if PICKLE_CACHE_ENABLED:
                assert isinstance(pickle_storage, _PrefetchingPickleStorage)
                metadata = pickle_storage.retrieve_metadata_or_none()
                if metadata is not None:
                    metadata: _PrefetchingPickleStorage.PickleMetadata
                    return (
                        metadata['ver'],
                        metadata['timestamp'],
                        metadata['job_duration'],
                    )
            return LackOf, LackOf, LackOf

        def _maybe_get_last_root_node_ver_and_timestamp():
            if last_root_node:
                extra = last_root_node['_extra_']
                return (
                    extra['ver'],
                    extra['timestamp'],
                )
            assert last_root_node is LackOf
            return LackOf, LackOf

        def _initial_checks_and_adjustments(database_ver, database_ts,
                                            pickle_ver, pickle_ts, recent_job_duration,
                                            last_ver, last_ts):
            # *Note:* generally, data version numbers (here: `..._ver` params,
            # which correspond to Auth DB's `recent_write_op_commit.id`) are
            # *unique*; but their timestamps (here: `..._ts` params, which
            # correspond to Auth DB's `recent_write_op_commit.made_at`) are
            # *not* necessarily unique.

            def warn_unexpected(msg):
                # The `ERROR` level is used intentionally (to make the warning "loud").
                LOGGER.error('[LOUD WARNING] Continuing despite unexpected condition: '
                             '%s (more info: %s).', ascii_str(msg), format_all_values())
            def format_all_values():
                return ascii_str(f'{database_ver=}, {database_ts=}, '
                                 f'{pickle_ver=}, {pickle_ts=}, {recent_job_duration=}, '
                                 f'{last_ver=}, {last_ts=}')

            if not (_is_positive_int(database_ver) and _is_positive_finite(database_ts)):
                raise AssertionError(f'incorrect `database_ver` and/or `database_ts` '
                                     f'(more info: {format_all_values()})')
            if not (_is_positive_int(pickle_ver) and _is_positive_finite(pickle_ts)
                    or (pickle_ver is pickle_ts is LackOf)):
                raise AssertionError(f'incorrect `pickle_ver` and/or `pickle_ts` '
                                     f'(more info: {format_all_values()})')
            if not (_is_positive_int(last_ver) and _is_positive_finite(last_ts)
                    or (last_ver is last_ts is LackOf)):
                raise AssertionError(f'incorrect `last_ver` and/or `last_ts` '
                                     f'(more info: {format_all_values()})')
            if not (_is_nonnegative_finite(recent_job_duration)
                    or recent_job_duration is LackOf):
                raise AssertionError(f'incorrect `recent_job_duration` '
                                     f'(more info: {format_all_values()})')

            if pickle_ver > database_ver or pickle_ts > database_ts:
                warn_unexpected(f'`pickle_ver` > `database_ver` and/or '
                                f'`pickle_ts` > `database_ts` (auth '
                                f'database was rebuilt or what?) => '
                                f'ignoring pickled stuff...')
                pickle_ver = pickle_ts = recent_job_duration = LackOf
            elif pickle_ver == database_ver and pickle_ts != database_ts:
                warn_unexpected(f'`pickle_ver` == `database_ver` but '
                                f'`pickle_ts` != `database_ts` (auth '
                                f'database was rebuilt or what?) => '
                                f'ignoring pickled stuff...')
                pickle_ver = pickle_ts = recent_job_duration = LackOf

            if last_ver > database_ver or last_ts > database_ts:
                warn_unexpected(f'`last_ver` > `database_ver` and/or '
                                f'`last_ts` > `database_ts` (auth '
                                f'database was rebuilt or what?) => '
                                f'ignoring last returned stuff...')
                last_ver = last_ts = LackOf
            elif last_ver == database_ver and last_ts != database_ts:
                warn_unexpected(f'`last_ver` == `database_ver` but '
                                f'`last_ts` != `database_ts` (auth '
                                f'database was rebuilt or what?) => '
                                f'ignoring last returned stuff...')
                last_ver = last_ts = LackOf

            if last_ver > pickle_ver or last_ts > pickle_ts:
                warn_unexpected(f'`last_ver` > `pickle_ver` and/or '
                                f'`last_ts` > `pickle_ts` (!) => '
                                f'ignoring both pickled stuff '
                                f'and last returned stuff...')
                pickle_ver = pickle_ts = recent_job_duration = LackOf
                last_ver = last_ts = LackOf
            elif last_ver == pickle_ver and last_ts != pickle_ts:
                warn_unexpected(f'`last_ver` == `pickle_ver` but '
                                f'`last_ts` != `pickle_ts` (!) => '
                                f'ignoring both pickled stuff '
                                f'and last returned stuff...')
                pickle_ver = pickle_ts = recent_job_duration = LackOf
                last_ver = last_ts = LackOf

            # *Note:* the following assertions confirm only a part of
            # many conditions whose truthness, at this point, is already
            # guaranteed...
            assert database_ver and database_ts
            assert (pickle_ver and pickle_ts and PICKLE_CACHE_ENABLED
                    or (pickle_ver is pickle_ts is LackOf))
            assert (last_ver and last_ts and last_root_node
                    or (last_ver is last_ts is LackOf))
            # Note that:
            # * if `not pickle_ver` then `pickle_ver is LackOf` (and vice versa)
            # * if `not pickle_ts` then `pickle_ts is LackOf` (and vice versa)
            # * if `not last_ver` then `last_ver is LackOf` (and vice versa)
            # * if `not last_ts` then `last_ts is LackOf` (and vice versa)
            # * if `not last_root_node` then `last_root_node is LackOf` (and vice versa)
            # Also, note that:
            # * if `pickle_ver` then also `pickle_ts` and `PICKLE_CACHE_ENABLED` must be non-false
            # * if `pickle_ts` then also `pickle_ver` and `PICKLE_CACHE_ENABLED` must be non-false
            # * if `last_ver` then also `last_ts` and `last_root_node` must be non-false
            # * if `last_ts` then also `last_ver` and `last_root_node` must be non-false
            # However, note that:
            # * `PICKLE_CACHE_ENABLED` being non-false
            #   does *not* imply that `pickle_ver`/`pickle_ts` must be non-false
            # * `last_root_node` being non-false
            #   does *not* imply that `last_ver`/`last_ts` must be non-false

            return (
                pickle_ver, pickle_ts, recent_job_duration,
                last_ver, last_ts,
            )

        def _is_positive_int(val):
            return isinstance(val, int) and val > 0

        def _is_positive_finite(val):
            return isinstance(val, (float, int)) and val > 0 and math.isfinite(val)

        def _is_nonnegative_finite(val):
            return isinstance(val, (float, int)) and val >= 0 and math.isfinite(val)

        def _set_sleep(sleep_val):
            nonlocal sleep
            sleep = sleep_val

        def _compute_sleep_if_timestamp_ok(timestamp, recent_job_duration):
            seconds_outdated = time.time() - timestamp
            seconds_until_unacceptable = TOLERANCE_FOR_OUTDATED - seconds_outdated
            if recent_job_duration:
                seconds_discount = min(recent_job_duration * SAFE_RESERVE_MULTIPLIER, 1800)
                seconds_until_unacceptable += seconds_discount
            if seconds_until_unacceptable > 0:
                sleep_val = min(seconds_until_unacceptable, MAX_SLEEP_BETWEEN_RUNS)
                return sleep_val
            return None

        def _load_fresh_root_node():
            LOGGER.info('Root node loading *starts*...')
            LOGGER.info('Fetching root node from database...')
            root_node = fetch_fresh_root_node()
            LOGGER.info('Root node fetched from database.')
            LOGGER.info('Executing time consuming methods to populate cache...')
            method_name_to_result = root_node['_method_name_to_result_']
            method_name_to_result.update(_call_methods(root_node))
            LOGGER.info('Time consuming methods executed, cache populated.')
            LOGGER.info('Root node loading *finishes*.')
            return root_node

        def _call_methods(root_node):
            for method_name, method_obj in METHOD_NAME_TO_OBJ.items():
                LOGGER.info('Executing method %a...', method_name)
                result = method_obj(root_node)
                LOGGER.info('Method %a executed.', method_name)
                yield method_name, result

        @contextlib.contextmanager
        def _catching_and_logging_unpickling_error():
            assert PICKLE_CACHE_ENABLED and pickle_storage is not None
            try:
                yield
            except pickle_storage.Error as exc:
                LOGGER.error('Could not unpickle root node - %s. '
                             'Will try to cope without using it...',
                             ascii_str(exc), exc_info=True)

        def _unpickle_root_node(pickle_ver, pickle_ts):
            assert PICKLE_CACHE_ENABLED and pickle_storage is not None
            LOGGER.info('Unpickling root node...')
            root_node = pickle_storage.retrieve_root_node(
                expected_ver=pickle_ver,
                expected_timestamp=pickle_ts)
            LOGGER.info('Root node unpickled.')
            return root_node

        def _pickle_root_node(root_node, job_start_monotime):
            assert PICKLE_CACHE_ENABLED and pickle_storage is not None
            LOGGER.info('Pickling root node...')
            job_duration = pickle_storage.store_everything(root_node, job_start_monotime)
            LOGGER.info('Root node pickled.')
            return job_duration

        def _handle_prefetching_error(exc):
            # (returns `last_root_node` or raises `SystemExit`)
            LOGGER.error('Prefetching task *error*! %s', make_exc_ascii_str(exc))
            min_acceptable_timestamp = time.time() - TOLERANCE_FOR_OUTDATED_ON_ERROR
            last_ver, last_ts = _maybe_get_last_root_node_ver_and_timestamp()
            if last_ts >= min_acceptable_timestamp:
                assert (last_ver == last_root_node['_extra_']['ver'] and
                        last_ts == last_root_node['_extra_']['timestamp'])
                utc_iso = _format_timestamp_as_utc_iso(last_ts)
                LOGGER.error('Because of the prefetching error (see the '
                             'previous log message), the last returned '
                             'data will be used. Note: it can be used '
                             'because it is not older than %d seconds '
                             '(data version: %a, timestamp: %a == %sZ).',
                             TOLERANCE_FOR_OUTDATED_ON_ERROR,
                             last_ver, last_ts, utc_iso)
                return last_root_node
            msg = ('Unable to recover from an Auth API prefetching '
                   'error! (see the relevant ERROR log message)')
            LOGGER.critical(msg)
            raise SystemExit(msg) from exc

        def _log_prefetching_success(root_node):
            comment = ('no new data obtained' if root_node is last_root_node
                       else 'data obtained')
            extra = root_node['_extra_']
            utc_iso = _format_timestamp_as_utc_iso(extra['timestamp'])
            LOGGER.info(f'Prefetching task *finishes*, {comment} '
                        f'(data version: %a, timestamp: %a == %s).',
                        extra['ver'], extra['timestamp'], utc_iso)

        def _format_timestamp_as_utc_iso(timestamp):
            return datetime.datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'

        return task_target_func, loop_iteration_hook


    _PICKLE_FILE_BASENAME = 'AuthAPIWithPrefetchingPickleCache'

    def _get_configured_values(self):
        config = self._config_full['auth_api_prefetching']

        max_sleep_between_runs = config['max_sleep_between_runs']
        tolerance_for_outdated = config['tolerance_for_outdated']
        tolerance_for_outdated_on_error = config['tolerance_for_outdated_on_error']
        pickle_file_path = None
        pickle_signature_secret = None

        pickle_dir = config['pickle_cache_dir']
        if pickle_dir is not None:
            preparer = self._prefetch_task_data_preparer
            if preparer._using_legacy_version_of_access_filtering_conditions:
                LOGGER.warning(
                    'Disabling the *pickle cache* feature because the legacy '
                    'variant of access filtering conditions is in use.')
            elif preparer._skipping_optimization_of_access_filtering_conditions:
                LOGGER.warning(
                    'Disabling the *pickle cache* feature because the unoptimized '
                    'variant of access filtering conditions is in use.')
            else:
                pickle_file_path = pickle_dir / self._PICKLE_FILE_BASENAME
                pickle_signature_secret = config['pickle_cache_signature_secret']
        return (
            max_sleep_between_runs,
            tolerance_for_outdated,
            tolerance_for_outdated_on_error,
            pickle_file_path,         # (<- may be `None`)
            pickle_signature_secret,  # (<- may be `None`)
        )


    @staticmethod
    def _get_backends_tick_callback_checking_for_cancel(future):
        MIN_INTERVAL_BETWEEN_CHECKS = 0.1

        class PrefetchingCancelled(Exception):
            pass

        future_cancelled = future.cancelled
        cur_time = time.monotonic
        prev_t = cur_time()

        def backends_tick_callback():
            nonlocal prev_t

            t = cur_time()
            if t >= prev_t + MIN_INTERVAL_BETWEEN_CHECKS:
                if future_cancelled():
                    # Note that the following exception will be
                    # "shadowed" by a FutureCancelled exception.
                    raise PrefetchingCancelled
                prev_t = t

        # Note: the returned callable does *not* need to be
        # thread-safe (see the comment in `__init__()`...).
        return backends_tick_callback



class InsideCriteriaResolver:

    """
    The class implements efficiently the main part of the Filter's job:
    to determine the contents of the `client` and `urls_matched`
    normalized event data items.

    The InsideCriteriaResolver constructor takes one argument: a
    sequence of criteria for the `inside` access zone (as returned by
    _DataPreparer._get_inside_criteria(root_node), i.e., a list of dicts:

        [
            {
                'org_id': <organization id (str)>,

                # the rest of items are optional:
                'fqdn_seq': [<fqdn suffix (str)>, ...],
                'asn_seq': [<asn (int)>, ...],
                'cc_seq': [<cc (str)>, ...],
                'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],
                'url_seq': [<url (str)>, ...],
            },
            ...
        ]

    An InsideCriteriaResolver instance has one public method:
    get_client_org_ids_and_urls_matched() (see its docs for details).

    It is assumed that the given data are valid (correct types, no org
    id duplicates in the criteria passed in to the constructor, min. ip
    is never greater than the corresponding max. ip...); it is the
    responsibility of the callers of the constructor and the callers of
    the get_client_org_ids_and_urls_matched() method to ensure that.
    """

    _IP_LO_GUARD = -1
    _IP_HI_GUARD = 2 ** 32


    def __init__(self, inside_criteria):
        if not inside_criteria:
            LOGGER.warning('something wrong: `inside_criteria` is empty!')

        # a mapping containing information extracted from `n6ip-network`
        # values; it maps integers representing IP addresses to lists of
        # pairs (2-tuples):
        #   (<org id (str)>,
        #    <is it the *lower* endpoint of an IP interval? (bool)>)
        # important: IP addresses of *upper* endpoints are
        # converted to delimit a particular IP interval in an
        # *exclusive* manner (that is, 1 is added to integer
        # representing the *upper* IP of each IP network range)
        ip_to_id_endpoints = collections.defaultdict(list, {
            # (these guards are needed because of how the
            # get_client_org_ids_and_urls_matched() method
            # is implemented)
            self._IP_LO_GUARD: [],
            self._IP_HI_GUARD: [],
        })

        # mappings that map values of `n6fqdn`/`n6asn`/`n6cc` (coerced
        # or normalized if applicable...) to lists of org ids
        self._fqdn_suffix_to_ids = collections.defaultdict(list)
        self._asn_to_ids = collections.defaultdict(list)
        self._cc_to_ids = collections.defaultdict(list)

        # a list of pairs: (<org id>, <tuple of `n6url` values>)
        self._ids_and_urls = []

        _seen_ids = set()  # <- for sanity assertions only
        for cri in inside_criteria:
            org_id = cri['org_id']
            assert org_id not in _seen_ids
            _seen_ids.add(org_id)

            # IPs
            for min_ip, max_ip in cri.get('ip_min_max_seq', ()):
                assert min_ip >= 1
                if (min_ip, max_ip) == (1, 0):
                    # (corner case related to exclusion of 0, see: #8861...)
                    continue
                assert min_ip <= max_ip
                ip_to_id_endpoints[min_ip].append((org_id, True))
                ip_to_id_endpoints[max_ip + 1].append((org_id, False))

            # FQDN suffixes, ASNs, CCs
            for mapping, which_seq in [
                (self._fqdn_suffix_to_ids, 'fqdn_seq'),
                (self._asn_to_ids, 'asn_seq'),
                (self._cc_to_ids, 'cc_seq'),
            ]:
                for key in cri.get(which_seq, ()):
                    mapping[key].append(org_id)

            # URLs
            url_seq = cri.get('url_seq')
            if url_seq:
                self._ids_and_urls.append((org_id, tuple(url_seq)))

        # [related to IPs]
        # a pair (2-tuple) consisting of:
        #
        # * the `border ips` list -- being a sorted list of unique
        #   integers that represent borderline IPs, that is, IPs being
        #   lower and/or upper endpoints of IP intervals extracted from
        #   `n6ip-network` IP ranges; remember that upper endpoints
        #   delimit their intervals in an *exclusive* manner
        #
        # * the `corresponding id sets` list -- containing sets of org
        #   ids; each set includes org ids appropriate for a particular
        #   IP interval; each interval is half-closed, that is, could be
        #   denoted as "[a, b)" (or "a <= `IP within the interval` < b")
        #   where *a* is the corresponding borderline IP from the
        #   `border ips` list and *b* is the next IP from that list
        self._border_ips_and_corresponding_id_sets = (
            self._get_border_ips_and_corresponding_id_sets(ip_to_id_endpoints))


    def _get_border_ips_and_corresponding_id_sets(self, ip_to_id_endpoints):
        border_ips = []
        corresponding_id_sets = []
        org_id_to_unclosed_ranges_count = collections.Counter()

        def current_id_set():
            return frozenset(org_id_to_unclosed_ranges_count.elements())

        for ip, id_endpoints in sorted(ip_to_id_endpoints.items()):
            for org_id, is_lower_endpoint in sorted(id_endpoints):
                if is_lower_endpoint:
                    org_id_to_unclosed_ranges_count[org_id] += 1
                else:
                    org_id_to_unclosed_ranges_count[org_id] -= 1
            border_ips.append(ip)
            corresponding_id_sets.append(current_id_set())
        assert not current_id_set()

        assert (
            border_ips[0] == self._IP_LO_GUARD and
            border_ips[-1] == self._IP_HI_GUARD and
            corresponding_id_sets[0] == corresponding_id_sets[-1] == frozenset())
        return border_ips, corresponding_id_sets


    def get_client_org_ids_and_urls_matched(self,
                                            record_dict,
                                            fqdn_only_categories=frozenset()):

        """
        Get org ids that the given event's `clients` attribute should
        include + additional information about `org <-> URL` matches
        according to the event's `url_pattern` attribute.

        Obligatory args:
            `record_dict` (a RecordDict instance):
                The examined event data.  Note that this method does
                *not* add anything to `record_dict`.

        Optional args/kwargs:
            `fqdn_only_categories` (a set-like container):
                The categories for whom only `fqdn` shall be checked
                (for rest categories also `address` and `url_pattern`
                are checked).  Default value: empty frozenset.

        Returns:
            A pair (2-tuple) containing the following items:

            * a set (note: a set, not a list) of all matching org ids,
            * a dict mapping org ids to lists of (sorted) matching URLs.
        """
        client_org_ids = set()
        urls_matched = dict()

        # FQDN
        fqdn = record_dict.get('fqdn')
        if fqdn is not None:
            fqdn_suffix_to_ids = self._fqdn_suffix_to_ids
            fqdn_parts = fqdn.split('.')
            for i in range(len(fqdn_parts)):
                suffix = '.'.join(fqdn_parts[i:])
                id_seq = fqdn_suffix_to_ids.get(suffix)
                if id_seq is not None:
                    client_org_ids.update(id_seq)

        # the rest of the criteria...
        if record_dict['category'] not in fqdn_only_categories:
            asn_to_ids = self._asn_to_ids
            cc_to_ids = self._cc_to_ids

            bisect_right = bisect.bisect_right
            border_ips, corresponding_id_sets = self._border_ips_and_corresponding_id_sets
            border_ips_length = len(border_ips)
            assert len(corresponding_id_sets) == border_ips_length

            for adr in record_dict.get('address', ()):

                # ASN
                asn = adr.get('asn')
                if asn is not None:
                    id_seq = asn_to_ids.get(asn)
                    if id_seq is not None:
                        client_org_ids.update(id_seq)

                # CC
                cc = adr.get('cc')
                if cc is not None:
                    id_seq = cc_to_ids.get(cc)
                    if id_seq is not None:
                        client_org_ids.update(id_seq)

                # IP
                ip = ipv4_to_int(adr['ip'])
                index = bisect_right(border_ips, ip) - 1
                client_org_ids.update(corresponding_id_sets[index])

                # sanity assertion (can be commented out):
                assert index + 1 < border_ips_length and ip < border_ips[index + 1] and (
                    index >= 1 and ip > border_ips[index - 1] if ip == border_ips[index]
                    else index >= 0 and ip > border_ips[index])

            # URL
            url_pattern = record_dict.get('url_pattern')
            if url_pattern is not None:
                assert url_pattern  # (already assured by RecordDict machinery)
                try:
                    try:
                        ### XXX: don't we want to use the re.ASCII flag here???
                        match1 = re.compile(url_pattern).search
                    except re.error:
                        match1 = re.compile(fnmatch.translate(url_pattern)).match
                        match2 = None
                    else:
                        try:
                            match2 = re.compile(fnmatch.translate(url_pattern)).match
                        except re.error:
                            match2 = None
                except Exception as exc:
                    LOGGER.warning(
                        'Exception occurred when trying to process `url_pattern` (%a) '
                        '-- %s', url_pattern, make_exc_ascii_str(exc))
                else:
                    for org_id, urls in self._ids_and_urls:
                        org_matching_urls = set()
                        for url in urls:
                            if match1(url) is not None or (
                                    match2 is not None and
                                    match2(url) is not None):
                                client_org_ids.add(org_id)
                                org_matching_urls.add(url)
                        if org_matching_urls:
                            urls_matched[org_id] = sorted(org_matching_urls)

        return client_org_ids, urls_matched



class _IgnoreListsCriteriaResolver:

    def __init__(self, ignored_ip_networks: Iterable[str]):
        self._ignored_ips = IPv4Container(*(
            ipaddress.IPv4Network(network, strict=False)
            for network in ignored_ip_networks))

    def __call__(self, record_dict: Mapping[str, object]) -> bool:
        if address := record_dict.get('address'):  # noqa
            address: list[dict]
            return all(
                addr['ip'] in self._ignored_ips
                for addr in address)
        return False



class _DataPreparer:

    def __init__(self):
        # Can be set by client code to an arbitrary argumentless callable
        # (to be called relatively often during long-lasting operations):
        self.tick_callback = lambda: None

        self._using_legacy_version_of_access_filtering_conditions = (
            self._is_env_var_non_empty('N6_USE_LEGACY_VERSION_OF_ACCESS_FILTERING_CONDITIONS'))
        self._skipping_optimization_of_access_filtering_conditions = (
            self._is_env_var_non_empty('N6_SKIP_OPTIMIZATION_OF_ACCESS_FILTERING_CONDITIONS'))

        self._cond_builder = CondBuilder()
        self._cond_optimizer = self._make_access_filtering_cond_optimizer()
        self._cond_hardener = self._make_access_filtering_cond_hardener()
        self._cond_to_sqla_converter = self._make_access_filtering_cond_to_sqla_converter()
        ### XXX uncomment when predicates-related parts support new `Cond` et consortes.
        #self._cond_to_predicate_converter = CondPredicateMaker()

    def _is_env_var_non_empty(self, env_var_name):
        is_set = bool(os.environ.get(env_var_name))
        LOGGER.info(
            f'{env_var_name} is {"*set*" if is_set else "*not* set"} '
            f'(to a non-empty value)')
        return is_set

    def _make_access_filtering_cond_optimizer(self):
        if self._skipping_optimization_of_access_filtering_conditions:
            return (lambda cond: cond)

        # (visitors each of which takes a `Cond` and returns a `Cond`)
        cond_optimizing_transformers = (
            CondFactoringTransformer(),
            CondEqualityMergingTransformer(),
        )
        def optimizer(cond):
            assert isinstance(cond, Cond)
            for transformer in cond_optimizing_transformers:
                cond = transformer(cond)
            assert isinstance(cond, Cond)
            return cond
        return optimizer

    def _make_access_filtering_cond_hardener(self):
        # (visitors each of which takes a `Cond` and returns a `Cond`)
        cond_hardening_transformers = (
            CondDeMorganTransformer(),
            _CondToCondWithNullSafeNegationsTransformer(),
        )
        def hardener(cond):
            assert isinstance(cond, Cond)
            for transformer in cond_hardening_transformers:
                cond = transformer(cond)
            assert isinstance(cond, Cond)
            return cond
        return hardener

    def _make_access_filtering_cond_to_sqla_converter(self):
        # (a visitor that takes a `Cond` and returns an SQLAlchemy object)
        return _CondToSQLAlchemyConverter()

    def get_user_ids_to_org_ids(self, root_node):
        result = {}
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.items():
            self._check_org_length(org_id)
            user_id_to_node = org.get('n6login', {})
            for user_id, user in user_id_to_node.items():
                user_is_blocked = self._is_flag_enabled(
                    user,
                    caption='the user {0!a}'.format(user_id),
                    attribute='n6blocked')
                if user_is_blocked:
                    continue
                stored_org_id = result.setdefault(user_id, org_id)
                if stored_org_id != org_id:
                    LOGGER.error(
                        'Problem with LDAP data: user %a belongs to '
                        'more than one organization (%a and %a '
                        '-- only the former will be stored in the '
                        'user-id-to-org-id mapping)',
                        user_id, stored_org_id, org_id)
        return result

    def get_org_ids(self, root_node):
        all_org_ids = frozenset(root_node['ou']['orgs'].get('o', frozenset()))
        for org_id in all_org_ids:
            self._check_org_length(org_id)
        return all_org_ids

    def get_inside_criteria_resolver(self, root_node):
        inside_criteria = self._get_inside_criteria(root_node)
        inside_criteria_resolver = InsideCriteriaResolver(inside_criteria)
        return inside_criteria_resolver

    def get_ignore_lists_criteria_resolver(self, root_node):
        ignored_ip_networks = root_node['_extra_']['ignored_ip_networks']
        ignore_lists_criteria_resolver = _IgnoreListsCriteriaResolver(ignored_ip_networks)
        return ignore_lists_criteria_resolver

    def get_anonymized_source_mapping(self, root_node):
        # {
        #     'forward_mapping': {
        #          <source id>: <anonymized source id>,
        #          ...
        #     },
        #     'reverse_mapping': {
        #          <anonymized source id>: <source id>,
        #          ...
        #     },
        # }
        source_id_to_node = root_node['ou']['sources'].get('cn', {})
        forward_mapping = {}
        for source_id, node in source_id_to_node.items():
            try:
                forward_mapping[source_id] = get_attr_value(node, 'n6anonymized')
            except ValueError as exc:
                LOGGER.error('Problem with LDAP data for the source %a -- %s',
                             source_id, make_exc_ascii_str(exc))
        reverse_mapping = {anonymized_id: source_id
                           for source_id, anonymized_id in forward_mapping.items()}
        return {'forward_mapping': forward_mapping,
                'reverse_mapping': reverse_mapping}

    def get_dip_anonymization_disabled_source_ids(self, root_node):
        source_id_to_node = root_node['ou']['sources'].get('cn', {})
        return frozenset(
            source_id
            for source_id, node in source_id_to_node.items()
            if not self._is_flag_enabled(
                node,
                caption='the source {!a}'.format(source_id),
                attribute='n6dip-anonymization-enabled',
                on_missing=False,  # <- by default, anonymization is disabled -- though...
                on_illegal=True,   # <- ...let's be on the safe side when LDAP data are malformed
            ))

    def obtain_ready_access_info(self, unready_access_info):
        access_info = copy.deepcopy(unready_access_info)
        for cond_list in access_info['access_zone_conditions'].values():
            [cond_with_null_safe_negations] = cond_list
            sqla_obj = self._cond_to_sqla_converter(cond_with_null_safe_negations)
            cond_list[:] = [sqla_obj]
        return access_info

    def get_org_ids_to_access_infos(self, root_node):
        # {
        #     <organization id as str>: {
        #         'access_zone_conditions': {
        #             <access zone: 'inside' or 'threats' or 'search'>: [
        #                 <an instance of `n6lib.data_selection_tools.Cond` (or of
        #                 `sqlalchemy.sql.expression.ColumnElement` in the legacy mode),
        #                 representing subsources criteria + `full_access` flag etc.>,
        #                 ...
        #             ],
        #             ...
        #         },
        #         'rest_api_resource_limits': {
        #             <resource id (one of EVENT_DATA_RESOURCE_IDS)>: {
        #                 'window': <int>,
        #                 'queries_limit': <int>,
        #                 'results_limit': <int>,
        #                 'max_days_old': <int>,
        #                 'request_parameters': <None or {
        #                     <user query parameter name>: <is required?
        #                                                   -- True or False>
        #                     ...
        #                 }>,
        #             },
        #             ...
        #         'rest_api_full_access': <True or False>,
        #         },
        #     },
        #     ...
        # }
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        result = self._make_org_ids_to_access_infos(root_node, org_id_to_node)
        self._set_resource_limits(result, root_node, org_id_to_node)
        return result

    def get_org_ids_to_actual_names(self, root_node):
        # {
        #     <organization id as a str>: <organization's *actual name* (`name`) as a str>
        #     ...
        # }
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        org_id_name_pairs = (
            (org_id,
             get_attr_value(org, 'name', default=None))
            for org_id, org in org_id_to_node.items())
        return {
            org_id: name
            for org_id, name in org_id_name_pairs
            if name is not None}


    def get_org_ids_to_combined_configs(self, root_node):
        # {
        #     <org id>: {
        #         'email_notifications': {                                 # optional
        #             'email_notification_addresses': [<str>, ...],                  # sorted
        #             'email_notification_times': [<datetime.time>, ...],            # sorted
        #             'email_notification_language': <str>,                          # optional
        #             'email_notification_business_days_only': <bool>,
        #         },
        #         'inside_criteria': {                                     # optional
        #             'fqdn_seq': [<fqdn (str)>, ...],                               # sorted
        #             'asn_seq': [<asn (int)>, ...],                                 # sorted
        #             'cc_seq': [<cc (str)>, ...],                                   # sorted
        #             'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],   # sorted
        #             'url_seq': [<url (str)>, ...],                                 # sorted
        #         },
        #     },
        #     ...
        # }
        result = {}

        for org_id, nt_conf in self.get_org_ids_to_notification_configs(root_node).items():
            result[org_id] = {
                'email_notifications': {
                    'email_notification_addresses': nt_conf['n6email-notifications-address'],
                    'email_notification_times': nt_conf['n6email-notifications-times'],
                    'email_notification_business_days_only':
                            nt_conf['n6email-notifications-business-days-only'],
                },
            }
            email_notification_language = nt_conf.get('n6email-notifications-language')
            if email_notification_language is not None:
                result[org_id]['email_notifications'][
                        'email_notification_language'] = email_notification_language

        for org_criteria in self._get_inside_criteria(root_node):
            org_id = org_criteria.pop('org_id')
            if org_criteria:
                if org_id not in result:
                    result[org_id] = {}
                assert all(isinstance(seq, list) for seq in org_criteria.values())
                result[org_id]['inside_criteria'] = {key: sorted(seq)
                                                     for key, seq in org_criteria.items()}

        return result

    def get_stream_api_enabled_org_ids(self, root_node):
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return frozenset(self._generate_stream_api_enabled_org_ids(org_id_to_node))

    def get_stream_api_disabled_org_ids(self, root_node):
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return frozenset(self._generate_stream_api_disabled_org_ids(org_id_to_node))

    def get_source_ids_to_subs_to_stream_api_access_infos(self, root_node):
        # {
        #     <source id>: {
        #         <subsource DN (str)>: (
        #             <filtering predicate: a callable that takes an instance of
        #              n6lib.db_filtering_abstractions.RecordFacadeForPredicates
        #              as the sole argument and returns True or False>,
        #             {
        #                 'inside': <set of organization ids (str)>,
        #                 'threats': <set of organization ids (str)>,
        #                 'search': <set of organization ids (str)>,
        #             }
        #         ),
        #         ...
        #     },
        #     ...
        # }
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return self._make_source_ids_to_subs_to_stream_api_access_infos(
            root_node,
            org_id_to_node)

    def get_source_ids_to_notification_access_info_mappings(self, root_node):
        # {
        #     <source id>: {
        #         (<subsource DN (str)>, <for full access orgs? (bool)>): (
        #             <filtering predicate: a callable that takes an instance of
        #               n6lib.db_filtering_abstractions.RecordFacadeForPredicates
        #               as the sole argument and returns True or False>,
        #             <set of organization ids (str)>,
        #         ),
        #         ...
        #     },
        #     ...
        # }
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return self._make_source_ids_to_notification_access_info_mappings(
            root_node,
            org_id_to_node)

    def get_org_ids_to_notification_configs(self, root_node):
        # {
        #     <org id>: {
        #         'name': <a str or False (bool)>,
        #         'n6stream-api-enabled': <bool>,
        #         'n6email-notifications-address': [<str>, ...],                # sorted
        #         'n6email-notifications-times': [<datetime.time>, ...],        # sorted
        #         'n6email-notifications-language': <str>,                      # optional
        #         'n6email-notifications-business-days-only': <bool>,
        #     },
        #     ...
        # }
        result = {}
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.items():
            org_notification_config = self._get_org_notification_config(org_id, org)
            if org_notification_config is not None:
                result[org_id] = org_notification_config
        return result

    #
    # Internal methods

    def _get_inside_criteria(self, root_node):
        # [
        #     {
        #         'org_id': <organization id (str)>,
        #
        #         # the rest of items are optional:
        #         'fqdn_seq': [<fqdn (str)>, ...],
        #         'asn_seq': [<asn (int)>, ...],
        #         'cc_seq': [<cc (str)>, ...],
        #         'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],
        #         'url_seq': [<url (str)>, ...],
        #     },
        #     ...
        # ]
        result = []
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.items():
            self._check_org_length(org_id)
            asn_seq = list(map(int, get_attr_value_list(org, 'n6asn')))
            cc_seq = list(get_attr_value_list(org, 'n6cc'))
            fqdn_seq = list(get_attr_value_list(org, 'n6fqdn'))
            convert_to_min_max_ip = functools.partial(
                ip_network_tuple_to_min_max_ip,
                force_min_ip_greater_than_zero=True)
            ip_min_max_seq = list(map(convert_to_min_max_ip,
                                      map(ip_network_as_tuple,
                                          get_attr_value_list(org, 'n6ip-network'))))
            url_seq = list(get_attr_value_list(org, 'n6url'))
            org_criteria = {'org_id': org_id}
            if asn_seq:
                org_criteria['asn_seq'] = asn_seq
            if cc_seq:
                org_criteria['cc_seq'] = cc_seq
            if fqdn_seq:
                org_criteria['fqdn_seq'] = fqdn_seq
            if ip_min_max_seq:
                org_criteria['ip_min_max_seq'] = ip_min_max_seq
            if url_seq:
                org_criteria['url_seq'] = url_seq
            result.append(org_criteria)
        return result

    def _generate_stream_api_enabled_org_ids(self, org_id_to_node):
        for org_id, org in org_id_to_node.items():
            if self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                yield org_id

    def _generate_stream_api_disabled_org_ids(self, org_id_to_node):
        for org_id, org in org_id_to_node.items():
            if not self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                yield org_id

    def _make_org_ids_to_access_infos(self, root_node, org_id_to_node):
        result = {}
        cond_builder = self._get_access_info_filtering_condition_builder()
        grouped_set = self._get_org_subsource_az_tuples(root_node, org_id_to_node)
        for org_id, subsource_refint, access_zone in sorted(grouped_set):  # (deterministic order)
            self.tick_callback()
            org = org_id_to_node[org_id]
            source_id = get_dn_segment_value(subsource_refint, 1)
            full_access = self._is_flag_enabled_for_org(
                org, org_id, 'n6rest-api-full-access')
            cond = self._get_condition_for_subsource_and_full_access_flag(
                root_node, source_id, subsource_refint,
                cond_builder, full_access)
            access_info = result.get(org_id)
            if access_info is None:
                access_info = {
                    'access_zone_conditions': {access_zone: [cond]},
                    'rest_api_resource_limits': {},  # <- to be populated in _set_resource_limits()
                    'rest_api_full_access': full_access,
                }
                result[org_id] = access_info
            else:
                access_info['access_zone_conditions'].setdefault(access_zone, []).append(cond)
        self._postprocess_access_info_filtering_cond_instances(result)
        return result

    def _get_access_info_filtering_condition_builder(self):
        if self._using_legacy_version_of_access_filtering_conditions:
            return LegacySQLAlchemyConditionBuilder(n6NormalizedData)
        return self._cond_builder

    def _postprocess_access_info_filtering_cond_instances(self, org_ids_to_access_infos):
        if self._using_legacy_version_of_access_filtering_conditions:
            return
        for access_info in org_ids_to_access_infos.values():
            for or_subconditions in access_info['access_zone_conditions'].values():
                self.tick_callback()
                cond_optimized = self._optimized_cond_from_or_subconditions(or_subconditions)
                cond_with_null_safe_negations = self._cond_hardener(cond_optimized)
                or_subconditions[:] = [cond_with_null_safe_negations]

    def _optimized_cond_from_or_subconditions(self, or_subconditions):
        assert isinstance(or_subconditions, list) and or_subconditions
        cond_unoptimized = self._cond_builder.or_(or_subconditions)
        cond_optimized = self._cond_optimizer(cond_unoptimized)
        return cond_optimized

    def _make_source_ids_to_subs_to_stream_api_access_infos(self, root_node, org_id_to_node):
        result = {}
        cond_builder = self._get_predicates_dedicated_condition_builder()
        grouped_set = self._get_org_subsource_az_tuples(root_node, org_id_to_node)
        for org_id, subsource_refint, access_zone in sorted(grouped_set):  # (deterministic order)
            org = org_id_to_node[org_id]
            if not self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                continue
            resource_id = ACCESS_ZONE_TO_RESOURCE_ID[access_zone]
            if not self._is_resource_enabled_for_org(resource_id, org, org_id):
                continue
            self.tick_callback()
            source_id = get_dn_segment_value(subsource_refint, 1)
            subsource_to_saa_info = result.setdefault(source_id, {})
            saa_info = subsource_to_saa_info.get(subsource_refint)
            if saa_info is None:
                cond = self._get_condition_for_subsource_and_full_access_flag(
                    root_node, source_id, subsource_refint, cond_builder)
                saa_info = predicate, az_to_org_ids = (
                    self._predicate_from_cond(cond),
                    {access_zone: set() for access_zone in ACCESS_ZONES},
                )
                subsource_to_saa_info[subsource_refint] = saa_info
            else:
                predicate, az_to_org_ids = saa_info
            az_to_org_ids[access_zone].add(org_id)

            # paranoic sanity check :)
            # (could be removed but let it stay here for a while...)
            assert (
                (
                    result.get(source_id) is subsource_to_saa_info and
                    isinstance(subsource_to_saa_info, dict)
                ) and (
                    subsource_to_saa_info.get(subsource_refint) is saa_info and
                    isinstance(saa_info, tuple) and
                    len(saa_info) == 2
                ) and (
                    saa_info[0] is predicate and (
                        callable(predicate) or
                        isinstance(predicate, (  # <- for unit tests only
                            LegacyBaseCond))
                            # XXX: uncomment when this part supports new `Cond` et consortes.
                            #if self._using_legacy_version_of_access_filtering_conditions
                            #else Cond))
                    )
                ) and (
                    saa_info[1] is az_to_org_ids and
                    isinstance(az_to_org_ids, dict) and
                    az_to_org_ids.keys() == ACCESS_ZONES and
                    access_zone in ACCESS_ZONES and
                    isinstance(az_to_org_ids[access_zone], set) and
                    org_id in az_to_org_ids[access_zone]))
        return result

    def _make_source_ids_to_notification_access_info_mappings(self, root_node, org_id_to_node):
        result = {}
        cond_builder = self._get_predicates_dedicated_condition_builder()
        grouped_set = self._get_org_subsource_az_tuples(root_node, org_id_to_node)
        for org_id, subsource_refint, access_zone in sorted(grouped_set):  # (deterministic order)
            if access_zone == 'inside':
                org = org_id_to_node[org_id]
                if not self._is_flag_enabled_for_org(
                        org, org_id, 'n6email-notifications-enabled'):
                    continue
                resource_id = ACCESS_ZONE_TO_RESOURCE_ID[access_zone]
                if not self._is_resource_enabled_for_org(resource_id, org, org_id):
                    continue
                self.tick_callback()
                source_id = get_dn_segment_value(subsource_refint, 1)
                full_access = self._is_flag_enabled_for_org(
                    org, org_id, 'n6rest-api-full-access')
                na_info_mapping = result.setdefault(source_id, {})
                na_info_key = (subsource_refint, full_access)
                na_info = na_info_mapping.get(na_info_key)
                if na_info is None:
                    cond = self._get_condition_for_subsource_and_full_access_flag(
                        root_node, source_id, subsource_refint,
                        cond_builder, full_access)
                    na_info = predicate, na_org_ids = self._predicate_from_cond(cond), set()
                    na_info_mapping[na_info_key] = na_info
                else:
                    predicate, na_org_ids = na_info
                na_org_ids.add(org_id)
        return result

    def _get_predicates_dedicated_condition_builder(self):
        ### XXX: uncomment when this part supports new `Cond` et consortes.
        #if self._using_legacy_version_of_access_filtering_conditions:
            return LegacyPredicateConditionBuilder()
        #return self._cond_builder

    def _predicate_from_cond(self, cond):
        ### XXX: uncomment when this part supports new `Cond` et consortes.
        #if self._using_legacy_version_of_access_filtering_conditions:
            return cond.predicate
        #return self._cond_to_predicate_converter(self._cond_optimizer(cond))

    def _set_resource_limits(self, org_id_to_access_info, root_node, org_id_to_node):
        event_data_resource_ids = sorted(EVENT_DATA_RESOURCE_IDS)  # (deterministic order)
        for org_id, access_info in org_id_to_access_info.items():
            self.tick_callback()
            org = org_id_to_node[org_id]
            for resource_id in event_data_resource_ids:
                limits = self._get_resource_limits_for_org(resource_id, org, org_id)
                if limits is not None:
                    access_info['rest_api_resource_limits'][resource_id] = limits

    def _get_org_notification_config(self, org_id, org):
        #   None
        # or
        #   {
        #       'name': <a str or False (bool)>,
        #       'n6stream-api-enabled': <bool>,
        #       'n6email-notifications-address': [<str>, ...],                # sorted
        #       'n6email-notifications-times': [<datetime.time>, ...],        # sorted
        #       'n6email-notifications-language': <str>,                      # optional
        #       'n6email-notifications-business-days-only': <bool>,
        #   }
        self._check_org_length(org_id)

        if not self._is_flag_enabled_for_org(org, org_id, 'n6email-notifications-enabled'):
            return None

        name = get_attr_value(org, 'name', default=False)
        if not name:
            LOGGER.info('No name for org id %a', org_id)

        email_notification_addresses = get_attr_value_list(org, 'n6email-notifications-address')
        if not email_notification_addresses:
            LOGGER.warning('No notification email addresses for org id %a', org_id)

        email_notification_times = []
        for time in get_attr_value_list(org, 'n6email-notifications-times'):
            try:
                email_notification_times.append(self._parse_notification_time(time))
            except ValueError as exc:
                LOGGER.error(
                    'Incorrect format of notification time %a for org id %a (%s)',
                    time, org_id, make_exc_ascii_str(exc))
        if not email_notification_times:
            LOGGER.warning('No notification times for org id %a', org_id)

        result = {
            'name': name,
            'n6stream-api-enabled': self._is_flag_enabled_for_org(
                org, org_id, 'n6stream-api-enabled'),
            'n6email-notifications-address': sorted(email_notification_addresses),
            'n6email-notifications-times': sorted(email_notification_times),
            'n6email-notifications-business-days-only': self._is_flag_enabled_for_org(
                org, org_id, 'n6email-notifications-business-days-only'),
        }

        email_notification_language = get_attr_value(org,
                                                     'n6email-notifications-language',
                                                     default=None)
        if email_notification_language:
            result['n6email-notifications-language'] = email_notification_language

        return result

    def _get_org_subsource_az_tuples(self, root_node, org_id_to_node):
        # returns a set of (<org id>, <subsource DN>, <access zone>) tuples
        included = set()
        excluded = set()
        for (org_id, subsource_refint, access_zone, is_excluding
             ) in self._iter_org_subsource_az_off_tuples(root_node, org_id_to_node):
            if is_excluding:
                excluded.add((org_id, subsource_refint, access_zone))
            else:
                included.add((org_id, subsource_refint, access_zone))
        included -= excluded
        return included

    def _iter_org_subsource_az_off_tuples(self, root_node, org_id_to_node):
        # yields (<org id>, <subsource DN>, <access zone>, <is excluding?>) tuples
        for org_id, org in org_id_to_node.items():
            self.tick_callback()
            self._check_org_length(org_id)
            org_props = org.get('cn')
            if org_props:
                for access_zone in ACCESS_ZONES:
                    for off_suffix in ('', '-ex'):
                        channel = org_props.get(access_zone + off_suffix)
                        for subsource_refint in (
                                self._iter_channel_subsource_refints(root_node, channel)):
                            # for org <-> subsource
                            # and org <-> subsource group <-> subsource
                            yield org_id, subsource_refint, access_zone, bool(off_suffix)

            for org_group_refint in get_attr_value_list(org, 'n6org-group-refint'):
                org_group = get_node(root_node, org_group_refint)
                org_group_props = org_group.get('cn')
                if org_group_props:
                    for access_zone in ACCESS_ZONES:
                        channel = org_group_props.get(access_zone)
                        for subsource_refint in (
                                self._iter_channel_subsource_refints(root_node, channel)):
                            # for org <-> org group <-> subsource
                            # and org <-> org group <-> subsource group <-> subsource
                            yield org_id, subsource_refint, access_zone, False

    def _iter_channel_subsource_refints(self, root_node, channel):
        # yields subsource DNs
        if channel:
            for subsource_refint in get_attr_value_list(channel, 'n6subsource-refint'):
                yield subsource_refint
            for subsource_group_refint in get_attr_value_list(channel, 'n6subsource-group-refint'):
                subsource_group = get_node(root_node, subsource_group_refint)
                for subsource_refint in get_attr_value_list(subsource_group, 'n6subsource-refint'):
                    yield subsource_refint

    def _get_condition_for_subsource_and_full_access_flag(self,
                                                          root_node,
                                                          source_id,
                                                          subsource_refint,
                                                          cond_builder,
                                                          full_access=False):
        condition = self._get_subsource_condition(
            root_node,
            source_id,
            subsource_refint,
            cond_builder)
        if not full_access:
            condition = cond_builder.and_(
                condition,
                cond_builder.not_(cond_builder['restriction'] == 'internal'),
                self._get_only_not_ignored_events_condition(cond_builder))
        return condition

    def _get_only_not_ignored_events_condition(self, cond_builder):
        if isinstance(cond_builder, CondBuilder):
            return cond_builder.not_(cond_builder['ignored'].is_true())
        # Below: legacy stuff (XXX: to be removed later + then inline the
        #                           above condition, removing this method)
        if type(cond_builder) is LegacySQLAlchemyConditionBuilder:
            return cond_builder.or_(
                # (`== None` will be converted by SQLAlchemy to `IS NULL`)
                cond_builder['ignored'] == None,
                cond_builder['ignored'] == 0)
        else:
            assert type(cond_builder) is LegacyPredicateConditionBuilder
            return cond_builder.not_(cond_builder['ignored'] == True)

    def _get_subsource_condition(self, root_node, source_id, subsource_refint, cond_builder):
        subsource = get_node(root_node, subsource_refint)
        inclusion_container_conditions = self._iter_container_conditions(
            root_node,
            subsource,
            'inclusion',
            cond_builder)
        exclusion_container_conditions = self._iter_container_conditions(
            root_node,
            subsource,
            'exclusion',
            cond_builder)
        return cond_builder.and_(
            cond_builder['source'] == source_id,
            cond_builder.and_(*inclusion_container_conditions),
            cond_builder.and_(*(cond_builder.not_(container_condition)
                                for container_condition in exclusion_container_conditions)))

    def _iter_container_conditions(self, root_node, subsource, kind, cond_builder):
        assert kind in ('inclusion', 'exclusion')
        for criteria_refint in get_attr_value_list(subsource,
                                                   'n6{0}-criteria-refint'.format(kind)):
            criteria_container_node = get_node(root_node, criteria_refint)
            criteria_container_items = sorted(  # (sorting to make the order deterministic)
                (attr_name[2:], value_list)
                for attr_name, value_list in criteria_container_node['attrs'].items()
                if attr_name in ('n6asn', 'n6cc', 'n6ip-network', 'n6category', 'n6name'))
            if criteria_container_items:
                crit_conditions = tuple(
                    self._iter_crit_conditions(criteria_container_items, cond_builder))
                if not crit_conditions:
                    raise AssertionError(
                        'criteria_container_items containing (only) empty value '
                        'lists??? ({!a})'.format(criteria_container_items))
                yield cond_builder.or_(*crit_conditions)

    def _iter_crit_conditions(self, criteria_container_items, cond_builder):
        for name, value_list in criteria_container_items:
            if not value_list:
                continue
            if None in value_list:
                raise AssertionError(
                    'value_list containing None??? ({!a}; whole '
                    'criteria_container_items: {!a})'.format(
                        value_list, criteria_container_items))
            if name == 'ip-network':
                for ip_network_str in value_list:
                    ip_network_tuple = ip_network_as_tuple(ip_network_str)
                    min_ip, max_ip = ip_network_tuple_to_min_max_ip(
                        ip_network_tuple,
                        force_min_ip_greater_than_zero=True)
                    column = cond_builder['ip']
                    yield column.between(min_ip, max_ip)
            else:
                column = cond_builder[name]
                if name == 'asn':
                    value_list = list(map(int, value_list))
                yield column.in_(value_list)

    def _is_flag_enabled_for_org(self, org, org_id, attribute,
                                 on_missing=False, on_illegal=False):
        return self._is_flag_enabled(
            org,
            caption='the organization {0!a}'.format(org_id),
            attribute=attribute,
            on_missing=on_missing,
            on_illegal=on_illegal)

    def _is_flag_enabled(self, node, caption, attribute,
                         on_missing=False, on_illegal=False):
        try:
            attrib_flag = get_attr_value(node, attribute, _BOOL_TO_FLAG[on_missing]).upper()
            if attrib_flag not in _FLAG_TO_BOOL:
                raise ValueError(
                    "{} is neither 'TRUE' nor 'FALSE' (got: {!a})"
                    .format(attribute, attrib_flag))
        except ValueError as exc:
            LOGGER.error(
                'Problem with LDAP data for %s: %s',
                ascii_str(caption), make_exc_ascii_str(exc))
            return on_illegal
        else:
            return _FLAG_TO_BOOL[attrib_flag]

    def _is_resource_enabled_for_org(self, resource_id, org, org_id):
        return (self._get_resource_limits_for_org(resource_id, org, org_id) is not None)

    def _get_resource_limits_for_org(self, resource_id, org, org_id):
        org_props = org.get('cn')
        if org_props:
            resource_ldap_cn = self._get_resource_ldap_cn(resource_id)
            rest_api_resource = org_props.get(resource_ldap_cn)
            if rest_api_resource:
                try:
                    return self._make_resource_limits_dict(rest_api_resource)
                except ValueError as exc:
                    LOGGER.error('Problem with LDAP data for the organization %a: %s',
                                 org_id, make_exc_ascii_str(exc))
        return None

    def _get_resource_ldap_cn(self, resource_id):
        access_zone = RESOURCE_ID_TO_ACCESS_ZONE[resource_id]
        return 'res-' + access_zone

    def _make_resource_limits_dict(self, rest_api_resource):
        ## FIXME: queries_limit and results_limit should have some non-None defaults
        time_window = get_attr_value(rest_api_resource, 'n6time-window',
                                     DEFAULT_RESOURCE_LIMIT_WINDOW)
        queries_limit = get_attr_value(rest_api_resource, 'n6queries-limit', None)
        results_limit = get_attr_value(rest_api_resource, 'n6results-limit', None)
        max_days_old = get_attr_value(rest_api_resource, 'n6max-days-old',
                                      DEFAULT_MAX_DAYS_OLD)
        return {
            # [note: for historical reasons it is "window", not "time_window"]
            'window': int(time_window),
            'queries_limit': (int(queries_limit) if queries_limit is not None else None),
            'results_limit': (int(results_limit) if results_limit is not None else None),
            'request_parameters': self._make_request_parameters_dict(rest_api_resource),
            'max_days_old': int(max_days_old),
        }

    def _make_request_parameters_dict(self, rest_api_resource):
        all_parameters = get_attr_value_list(rest_api_resource, 'n6request-parameters')
        required_parameters = set(get_attr_value_list(rest_api_resource,
                                                      'n6request-required-parameters'))
        if all_parameters:
            if not required_parameters.issubset(all_parameters):
                raise ValueError('n6request-required-parameters ({}) '
                                 'is not a subset of n6request-parameters ({})'
                                 .format(', '.join(sorted(map(ascii, required_parameters))),
                                         ', '.join(sorted(map(ascii, all_parameters)))))
        else:
            if required_parameters:
                raise ValueError('n6request-required-parameters are illegal when the '
                                 'n6request-parameters limitation is not specified')
            # n6request-parameters not specified -> all parameters enabled (as optional ones)
            return None
        return {param: (param in required_parameters)
                for param in all_parameters}

    def _check_org_length(self, org_id):
        """Check the `org_id` length; log a warning if it is too long."""
        if len(org_id) > CLIENT_ORGANIZATION_MAX_LENGTH:
            LOGGER.warning(
                'The length of the organization id %a is %s '
                '-- so it exceeded the limit (which is %s)',
                org_id, len(org_id), CLIENT_ORGANIZATION_MAX_LENGTH)

    def _parse_notification_time(self, time_str):
        """
        Validate time string from LDAP.

        Returns: <datetime.time object>

        Raises: ValueError
        """
        time_str = time_str.strip().replace(' ', '').replace('.', ':')
        try:
            dt = datetime.datetime.strptime(time_str, '%H:%M')
        except ValueError:
            dt = datetime.datetime.strptime(time_str, '%H')
        return dt.time()


class _CondToCondWithNullSafeNegationsTransformer(CondTransformer):

    # This transformer protects us against the #3379 bug.
    #
    # **Important:** any condition it is applied to should have
    # already been prepared with `CondDeMorganTransformer`.

    _NON_NULLABLE_COLUMNS = {
        # (the content of this set needs to be consistent
        # with `etc/mysql/initdb/1_create_tables.sql`...)
        'id',
        'rid',
        'source',
        'restriction',
        'confidence',
        'category',
        'time',
        'ip',
        'dip',
        'modified',
    }

    def visit_NotCond(self, cond):
        subcond = cond.subcond
        assert isinstance(subcond, RecItemCond)  # (<- thanks to `CondDeMorganTransformer`...)

        if (subcond.rec_key in self._NON_NULLABLE_COLUMNS
              or isinstance(subcond, (IsTrueCond, IsNullCond))):
            null_safe_cond = cond
        else:
            is_null_cond = self.make_cond(IsNullCond, subcond.rec_key)
            null_safe_cond = self.make_cond(OrCond, [is_null_cond, cond])

        return null_safe_cond


class _CondToSQLAlchemyConverter(CondVisitor):

    # This transformer converts instances of `Cond` subclasses to
    # SQLAlchemy objects representing SQL `WHERE ...` conditions.
    #
    # **Important:** any condition it is applied to should have
    # already been prepared with `CondDeMorganTransformer` and
    # `_CondToCondWithNullSafeNegationsTransformer`.

    def __init__(self):
        import sqlalchemy
        self._sqla_not = sqlalchemy.not_
        self._sqla_and = sqlalchemy.and_
        self._sqla_or = sqlalchemy.or_
        self._sqla_make_true = sqlalchemy.true
        self._sqla_make_false = sqlalchemy.false
        self._sqla_column = functools.partial(getattr, n6NormalizedData)

    def visit_NotCond(self, cond):
        subcond = cond.subcond
        assert isinstance(subcond, RecItemCond)  # (<- thanks to `CondDeMorganTransformer`...)

        if isinstance(subcond, EqualCond):
            return self._sqla_column(subcond.rec_key) != subcond.op_param

        if isinstance(subcond, InCond):
            values = list(subcond.op_param)
            assert values  # guaranteed by InCond
            return self._sqla_column(subcond.rec_key).notin_(values)

        if isinstance(subcond, IsTrueCond):
            return self._sqla_column(subcond.rec_key).isnot(sqla_text('TRUE'))

        if isinstance(subcond, IsNullCond):
            return self._sqla_column(subcond.rec_key).isnot(null())

        return self._sqla_not(self(subcond))

    def visit_AndCond(self, cond):
        assert cond.subconditions  # guaranteed by AndCond
        return self._sqla_and(*map(self, cond.subconditions))

    def visit_OrCond(self, cond):
        assert cond.subconditions  # guaranteed by OrCond
        return self._sqla_or(*map(self, cond.subconditions))

    def visit_EqualCond(self, cond):
        return self._sqla_column(cond.rec_key) == cond.op_param

    def visit_GreaterCond(self, cond):
        return self._sqla_column(cond.rec_key) > cond.op_param

    def visit_GreaterOrEqualCond(self, cond):
        return self._sqla_column(cond.rec_key) >= cond.op_param

    def visit_LessCond(self, cond):
        return self._sqla_column(cond.rec_key) < cond.op_param

    def visit_LessOrEqualCond(self, cond):
        return self._sqla_column(cond.rec_key) <= cond.op_param

    def visit_InCond(self, cond):
        values = list(cond.op_param)
        assert values  # guaranteed by InCond
        return self._sqla_column(cond.rec_key).in_(values)

    def visit_BetweenCond(self, cond):
        min_value, max_value = cond.op_param
        return self._sqla_column(cond.rec_key).between(min_value, max_value)

    def visit_IsTrueCond(self, cond):
        return self._sqla_column(cond.rec_key).is_(sqla_text('TRUE'))

    def visit_IsNullCond(self, cond):
        return self._sqla_column(cond.rec_key).is_(null())

    def visit_FixedCond(self, cond):
        return (self._sqla_make_true() if cond.truthness else self._sqla_make_false())



class _PrefetchingPickleStorage:

    #
    # Storage's interface

    # * Auxiliary stuff:

    class Error(Exception):
        """Raised on retrieval/storing errors."""

    class PickleMetadata(TypedDict):
        ver: int
        timestamp: Union[float, int]
        job_duration: Union[float, int]

    # * Initialization:

    def __init__(self, pickle_file_path, pickle_signature_secret):
        self._metadata_file_accessor = SignedStampedFileAccessor(
            path=f'{pickle_file_path}.meta',
            secret_key=pickle_signature_secret)
        self._pickle_file_accessor = SignedStampedFileAccessor(
            path=pickle_file_path,
            secret_key=pickle_signature_secret)

    # * Retrieval/storing operations:

    def retrieve_metadata_or_none(self):
        accessor = self._metadata_file_accessor
        error_wrapping = self._error_wrapping(accessor)
        no_error_if_missing = contextlib.suppress(FileNotFoundError)
        no_error_if_outdated = contextlib.suppress(accessor.OutdatedError)
        reader = accessor.text_reader(minimum_timestamp=self._get_minimum_header_timestamp())
        with error_wrapping, no_error_if_missing, no_error_if_outdated, reader as file:
            return json.load(file)
        return None  # noqa

    def retrieve_root_node(self, expected_ver, expected_timestamp):
        accessor = self._pickle_file_accessor
        error_wrapping = self._error_wrapping(accessor)
        reader = accessor.binary_reader(minimum_timestamp=self._get_minimum_header_timestamp())
        with error_wrapping, reader as file:
            root_node = pickle.load(file)
            self._check_ver_and_timestamp(root_node, expected_ver, expected_timestamp)
            return root_node

    def store_everything(self, root_node, job_start_monotime):
        m_accessor = self._metadata_file_accessor
        p_accessor = self._pickle_file_accessor
        with contextlib.ExitStack() as es, \
             self._error_wrapping(m_accessor), m_accessor.text_atomic_writer() as metadata_file, \
             self._error_wrapping(p_accessor), p_accessor.binary_atomic_writer() as pickle_file:

            pickle.dump(root_node, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)

            # OK, now the time-consuming parts of the job of loading and
            # pickling data are completed, so we can measure the total
            # duration of this job, and make the stored metadata include
            # that information.
            job_duration = time.monotonic() - job_start_monotime
            metadata = self._metadata_from(root_node, job_duration)
            json.dump(metadata, metadata_file)

            # Each of the accessors provides *atomic* write operations
            # (i.e., effectively, either the whole file is successfully
            # written, or "nothing happened"). However, it is possible
            # that the atomic write of the *pickle file* will succeed,
            # but then -- due to whatever exception -- the *metadata
            # file* will *not* be successfully written, so its previous
            # version will be kept. If such a case arises, we prefer to
            # completely *remove* the metadata file -- to avoid a data
            # version mismatch (which would be detected anyway, but at
            # the cost of a futile execution of the whole unpickling
            # procedure, which is rather performance-heavy).
            es.enter_context(self._removing_metadata_file_on_exception())

        return job_duration

    #
    # Internal helpers

    @contextlib.contextmanager
    def _error_wrapping(self, accessor):
        try:
            yield
        except accessor.SignatureError as exc:
            raise self.Error(
                f'content integrity error: "{make_exc_ascii_str(exc)}"! '
                f'(Did somebody tampered with the content of the file '
                f'{str(accessor.path)!a}?! Or maybe the config option '
                f'`auth_api_prefetching.pickle_cache_signature_secret` '
                f'was recently changed?...)'
            ) from exc
        except (accessor.OutdatedError, ValueError, FileNotFoundError) as exc:
            raise self.Error(
                f'error while dealing with the file {str(accessor.path)!a}: '
                f'"{make_exc_ascii_str(exc)}"'
            ) from exc

    _MAX_ACCEPTABLE_FILE_AGE = 7200

    def _get_minimum_header_timestamp(self):
        # Note that the *header timestamp* of a file and the *timestamp*
        # of a *root node* (being a part of *pickle metadata*) -- are
        # completely unrelated concepts! *Header timestamp* belongs to
        # the `SignedStampedFileAccessor`'s machinery...
        return time.time() - self._MAX_ACCEPTABLE_FILE_AGE

    def _check_ver_and_timestamp(self, root_node, expected_ver, expected_timestamp):
        extra = root_node['_extra_']
        if extra['ver'] != expected_ver:
            raise ValueError(
                f"expected root node version: {expected_ver!a}, "
                f"got: {extra['ver']!a}")
        if extra['timestamp'] != expected_timestamp:
            raise ValueError(
                f"expected root node timestamp: {expected_timestamp!a}, "
                f"got: {extra['timestamp']!a}")

    def _metadata_from(self, root_node, job_duration):
        extra = root_node['_extra_']
        return self.PickleMetadata(
            ver=extra['ver'],
            timestamp=extra['timestamp'],
            job_duration=job_duration)

    @contextlib.contextmanager
    def _removing_metadata_file_on_exception(self):
        try:
            yield
        except:
            self._try_remove_metadata_file()
            raise

    def _try_remove_metadata_file(self):
        try:
            self._metadata_file_accessor.path.unlink()
        except OSError:
            pass


class _InterprocessPrefetchingSynchronizer:

    # *Note:* it offers a best-effort synchronization, thanks to which
    # processes that share the same pickle-file-based cache can:
    #
    # * avoid duplication of work;
    #
    # * reduce to a minimum -- though not eliminate completely -- time
    #   intervals within which different processes "see" (and cache in
    #   their memory) different versions of data.

    #
    # Synchronizer's interface

    def __init__(self, pickle_file_path, min_safe_job_duration):
        assert (isinstance(pickle_file_path, pathlib.Path) and pickle_file_path.name)
        assert isinstance(min_safe_job_duration, (float, int))
        self._min_safe_job_duration = min_safe_job_duration
        self._pickle_file_path = pickle_file_path
        self._getjob_lock = self._make_lock('GETJOB')
        self._job_lock = self._make_lock('JOB')
        self._activity_lock = self._make_lock('ACTIVITY')
        self._outcome_lock = self._make_lock('OUTCOME')

    def __repr__(self):
        return (f'<{self.__class__.__qualname__}'
                f'({self._min_safe_job_duration!r}, {self._pickle_file_path!r}) '
                f'with locks: '
                f'{self._getjob_lock}, '
                f'{self._job_lock}, '
                f'{self._activity_lock}, '
                f'{self._outcome_lock}>')

    def __enter__(self):
        if self._is_any_lock_acquired_by_us():
            LOGGER.warning('%a was not exited properly, so it needs '
                           'to be forcibly cleaned up now!...', self)
            self._release_all_locks()
            LOGGER.info('OK, cleaned up %a (that is, made '
                        'it release all its locks).', self)

        assert not self._is_any_lock_acquired_by_us()
        try:
            self._getjob_lock.acquire(shared=True)
            if self._job_lock.acquire(shared=True, nonblocking=True):
                self._activity_lock_acquire_in_shared_mode_immediately()
                self._job_lock.release()
                self._getjob_lock.release()
            else:
                self._getjob_lock.release()

                # OK, some other process, just now, is doing the job of
                # loading and pickling fresh data... Let us attempt to
                # cause that when that process finishes the job, it will
                # wait until we (and, possibly, any other processes like
                # us) unpickle the data (*root node*) being the outcome
                # of the job.
                self._outcome_lock.acquire(shared=True)

                # But first -- when it comes to us -- let us wait until
                # that process actually finishes the job...
                LOGGER.info("Another process loads and pickles a "
                            "fresh root node. Let's wait for it...")
                self._job_lock.acquire(shared=True)

                self._activity_lock_acquire_in_shared_mode_immediately()
                self._job_lock.release()

            assert not self._getjob_lock.acquired_by_us
            assert not self._job_lock.acquired_by_us
            assert self._activity_lock.shared
            assert self._outcome_lock.shared or not self._outcome_lock.acquired_by_us

            return self
        except:
            self._release_all_locks()
            raise

    def __exit__(self, *_):
        try:
            assert self._activity_lock.shared
        finally:
            self._release_all_locks()

    def designate_loading_and_pickling_job(self):
        assert not self._getjob_lock.acquired_by_us
        assert not self._job_lock.acquired_by_us
        assert self._activity_lock.shared
        assert self._outcome_lock.shared or not self._outcome_lock.acquired_by_us

        # (Let us release the *OUTCOME* lock if we have acquired it...)
        self._outcome_lock.release()

        # Let us attempt to get the job of loading and pickling...
        self._getjob_lock.acquire()
        if self._job_lock.acquire(nonblocking=True):
            self._getjob_lock.release()
            # OK, we (the current process) got the job! None of the
            # other engaged processes (if any) can be here now, only
            # us...

            # So let us wait until *each* of those processes is outside
            # its synchronizer's `with` block -- either sleeping before
            # its next prefetching run or already being blocked in its
            # synchronizer's `__enter__()` (on the *JOB* lock we just
            # acquired using the *exclusive* mode).
            # (**Technical detail:** below we switch the mode of the
            # *ACTIVITY* lock from *shared* to *exclusive*; that will
            # make us wait until *all* other engaged processes reach
            # their synchronizers' `__exit__()`...)
            self._activity_lock.acquire()

            # (Switching the *ACTIVITY* lock's mode back to *shared*.)
            self._activity_lock.acquire(shared=True)

            # Now, as for us, we are ready to start the actual job of
            # loading and pickling fresh data!
            return True

        # OK, some other process got the job of loading and pickling...
        self._getjob_lock.release()
        return False

    def wait_giving_others_chance_to_unpickle(self, job_duration):
        # We just *finished* the job of loading and pickling fresh data.
        # (This is the continuation of the execution path that included
        # the `if` block in `designate_loading_and_pickling_job()`...)

        assert not self._getjob_lock.acquired_by_us
        assert self._job_lock.acquired_by_us and not self._job_lock.shared
        assert self._activity_lock.shared
        assert not self._outcome_lock.acquired_by_us

        assert isinstance(job_duration, (float, int))

        necessary_sleep = self._min_safe_job_duration - job_duration
        if necessary_sleep > 0:
            LOGGER.info("Synchronization pause (let's wait so that other "
                        "processes have a chance to block on our lock)...")
            time.sleep(necessary_sleep)

        # OK, all other processes should have had enough time to reach
        # their synchronizers' `__enter__()` (and block on the *JOB* lock
        # acquired by us) -- so, now, let us allow them to proceed...
        LOGGER.info("Now, let's give other processes a chance to "
                    "unpickle the fresh root node pickled by us...")
        self._job_lock.release()

        # ...and let us wait until they unpickle the data (*root node*)
        # being the outcome of the job.
        self._outcome_lock.acquire()
        self._outcome_lock.release()

    #
    # Internal helpers

    def _make_lock(self, label):
        return _FileBasedInterprocessLock(self._pickle_file_path, label)

    def _is_any_lock_acquired_by_us(self):
        return (self._getjob_lock.acquired_by_us or
                self._job_lock.acquired_by_us or
                self._activity_lock.acquired_by_us or
                self._outcome_lock.acquired_by_us)

    def _release_all_locks(self):
        try:
            try:
                try:
                    try:
                        self._outcome_lock.release()
                    finally:
                        self._activity_lock.release()
                finally:
                    self._job_lock.release()
            finally:
                self._getjob_lock.release()
        except KeyboardInterrupt:
            raise
        except BaseException as exc:
            exc_descr = make_exc_ascii_str(exc)
            sys_exit = SystemExit(f'A fatal error occurred while trying '
                                  f'to clean up the state (release all '
                                  f'locks) of {self!a}! ({exc_descr})')
            try:
                LOGGER.critical('Rough exit! %s', sys_exit)
            except:    # noqa
                pass   # noqa
            raise sys_exit from exc

    def _activity_lock_acquire_in_shared_mode_immediately(self):
        # Thanks to this, no new job can actually be started until all
        # engaged processes -- except the one which is to do the job --
        # reach their synchronizers' `__exit__()`.
        if not self._activity_lock.acquire(shared=True, nonblocking=True):
            # (Here, the *ACTIVITY* lock should have been able to be
            # acquired without blocking, i.e., immediately. If -- for
            # any reason -- this could not be done, we prefer an
            # explicit error rather than a blocking operation...)
            raise RuntimeError(f'this is unexpected: failed to acquire '
                               f'the {self._activity_lock} lock')


class _FileBasedInterprocessLock:

    # (Note that the implementation of this interprocess lock is *not*
    # -- and does *not* need to be -- thread-safe.)

    def __init__(self, base_path, label):
        assert isinstance(base_path, pathlib.Path) and base_path.name
        assert isinstance(label, str) and label and label.isascii()
        self._base_path = base_path
        self._label = label
        self._file = None
        self._shared = False

    @property
    def path(self):
        lock_filename = f'{self._base_path.name}.{self._label}.lock'
        return self._base_path.with_name(lock_filename)

    @property
    def acquired_by_us(self):
        return self._file is not None

    @property
    def shared(self):
        if self._shared:
            assert self.acquired_by_us
            return True
        return False

    __repr__ = attr_repr('path', 'acquired_by_us', 'shared')

    def __str__(self):
        annotation = (f'*{self._get_mode_descr(self.shared)}*'
                      if self.acquired_by_us else '-')
        return ascii_str(f'{self._label} ({annotation})')

    def acquire(self, *, shared=False, nonblocking=False):
        # *Note:* assuming the same arguments and external conditions
        # (and ignoring internal and logging-related details...), this
        # method is *idempotent*: it makes no difference whether the
        # method is invoked once or multiple times (however, note that
        # it may block, unless `nonblocking=True` is given...). Also,
        # it is OK to invoke this method several times with different
        # arguments (even when not interspersing such invocations with
        # invocations of `release()`); this is how the lock mode can be
        # switched from *shared* to *exclusive* or vice versa (but note
        # that such switching is *not* guaranteed to be atomic -- see:
        # https://manpages.debian.org/bookworm/manpages-dev/flock.2.en.html#NOTES).
        LOGGER.debug('Acquiring lock %s, switching it to *%s* mode...',
                     self, self._get_mode_descr(shared))

        flock_op = (fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        if nonblocking:
            flock_op |= fcntl.LOCK_NB

        file = self._file
        if file is None:
            LOGGER.debug('File %a will be opened...', str(self.path))
        try:
            if file is None:
                file = open(self.path, 'wb')
            fcntl.flock(file, flock_op)
        except OSError as exc:
            # *Note:* in the case of a failure, we
            # do *not* change the object's state.
            if self._file is None and file is not None:
                # `file` was just opened (has not been stored in the
                # object) => let's close it.
                file.close()
            else:
                # Either `file` had already been stored in the object
                # (then do not touch it!) or it is None (because the
                # `open(...)` call raised the exception).
                assert self._file is file

            failure_msg = (f'Lock %s could not be acquired (%s).')
            exc_descr = make_exc_ascii_str(exc)

            if isinstance(exc, BlockingIOError):
                assert nonblocking
                LOGGER.debug(failure_msg, self, exc_descr)
                return False

            LOGGER.error(failure_msg, self, exc_descr)
            raise

        assert file is not None
        self._file = file
        self._shared = shared
        LOGGER.debug('Lock %s acquired successfully.', self)
        return True

    def release(self):
        # *Note:* assuming the same external conditions (and that we
        # ignore internal and logging-related details...), this method
        # is idempotent: it makes no difference whether the method is
        # invoked once or multiple times. Invoking it on an object that
        # has never been `acquire()`-ed is also OK.
        if self._file is not None:
            self._file.close()
            self._file = None
        self._shared = False
        LOGGER.debug('Lock %s released.', self)

    @staticmethod
    def _get_mode_descr(shared):
        return ('shared' if shared else 'exclusive')

# Copyright (c) 2013-2023 NASK. All rights reserved.

import collections
import bisect
import datetime
import fnmatch
import functools
import os
import re
import time
import traceback
import threading

from sqlalchemy.exc import SQLAlchemyError

from n6lib.api_key_auth_helper import (
    APIKeyAuthError,
    APIKeyAuthHelper,
)
from n6lib.common_helpers import (
    LimitedDict,
    ascii_str,
    ip_network_as_tuple,
    ip_network_tuple_to_min_max_ip,
    ipv4_to_int,
    make_exc_ascii_str,
    memoized,
    deep_copying_result,
)
from n6lib.config import Config
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.context_helpers import ThreadLocalContextDeposit
from n6lib.data_selection_tools import (
    Cond,
    CondBuilder,
    CondDeMorganTransformer,
    CondEqualityMergingTransformer,
    CondFactoringTransformer,
    ## XXX: uncomment when predicates stuff in `_DataPreparer` supports new `Cond` et consortes.
    #CondPredicateMaker,
    CondVisitor,
    EqualCond,
    InCond,
    IsNullCond,
    RecItemCond,
)
from n6lib.db_events import n6NormalizedData
from n6lib.db_filtering_abstractions import (
    BaseCond as LegacyBaseCond,
    PredicateConditionBuilder as LegacyPredicateConditionBuilder,
    SQLAlchemyConditionBuilder as LegacySQLAlchemyConditionBuilder,
)
from n6lib.jwt_helpers import (
    JWT_ALGO_RSA_SHA256,
    JWTDecodeError,
    jwt_decode,
)
from n6lib.log_helpers import get_logger
from n6lib.ldap_api_replacement import (
    LdapAPI,
    LdapAPIConnectionError,
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
        super(AuthAPICommunicationError, self).__init__(self, exc_info_msg, low_level_exc)
        self.exc_info_msg = exc_info_msg
        self.low_level_exc = low_level_exc

    def __str__(self):
        return self.exc_info_msg



# This is a decorator for those AuthAPI methods which use AuthAPI's
# get_ldap_root_node().  Those methods must be argumentless.
# Their results will be cached as long as the result of
# AuthAPI._get_root_node()'s is cached.
def cached_basing_on_ldap_root_node(func):
    NO_RESULT = object()
    per_func_cache = [(None, NO_RESULT)]  # <root node>, <cached result>

    @functools.wraps(func)
    def func_wrapper(self):
        with self:
            root_node = self.get_ldap_root_node()
            assert root_node is not None
            recent_root_node, result = per_func_cache[0]
            if recent_root_node is not root_node:
                result = func(self)
                per_func_cache[0] = root_node, result
            assert result is not NO_RESULT
            return result

    func_wrapper.func = func  # making the original function still available
    return func_wrapper



class AuthAPI(object):

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

    config_spec = '''
        [api_key_based_auth]
        server_secret = :: str
    '''

    def __init__(self, settings=None):
        self._root_node_deposit = ThreadLocalContextDeposit(repr_token=self.__class__.__qualname__)
        self._ldap_api = LdapAPI(settings)
        self._data_preparer = _DataPreparer()
        self._config_full = Config(self.config_spec, settings=settings)
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
                                            audience):
        try:
            return jwt_decode(access_token,
                              json_web_key,
                              accepted_algorithms=(JWT_ALGO_RSA_SHA256,),
                              required_claims=required_claims,
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
            getting: <AuthAPI instance>.get_org_ids_to_access_infos().get(<org id>)

        Note: even if the organization exists, this method may still
        return None (this is the case when the organization has no
        access to any subsource for any access zone).
        """
        org_id = auth_data['org_id']
        all_access_infos = self.get_org_ids_to_access_infos()
        access_info = all_access_infos.get(org_id)
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
                        <an sqlalchemy.sql.expression.ColumnElement instance
                         implementing SQL condition for a subsource>,
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
        return self._data_preparer.get_org_ids_to_access_infos(
            self.get_ldap_root_node())

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
    # Non-public, but overridable, methods

    @memoized(expires_after=600, max_size=3)
    def _get_root_node(self):
        try:
            with self._ldap_api as ldap_api:
                return ldap_api.search_structured()
        except (LdapAPIConnectionError, SQLAlchemyError) as exc:
            raise AuthAPICommunicationError(traceback.format_exc(), exc)



def _make_method_with_result_cache_bound_to_prefetched_root_nodes(
        parent_qualname,
        name,
        list_of_such_method_names):

    def method_func(self):
        assert hasattr(AuthAPI, name)
        assert hasattr(_DataPreparer, name)
        with self:
            root_node = self.get_ldap_root_node()
            method_to_cached_result = self._result_cache_bound_to_prefetched_root_nodes[root_node]
            try:
                return method_to_cached_result[name]
            except KeyError:
                # Honestly, this should not happen, unless some
                # `with <AuthAPIWithPrefetching instance>: ...`
                # block lasts a few dozens of minutes (hardly
                # probable); anyway, in such a case we still
                # obtain the desired data, just with a worse
                # performance (which then should not matter).
                AuthAPI_method = getattr(AuthAPI, name)
                return AuthAPI_method(self)

    method_func.__name__ = name
    method_func.__qualname__ = '{}.{}'.format(parent_qualname, name)
    list_of_such_method_names.append(name)

    return method_func


class AuthAPIWithPrefetching(AuthAPI):

    """
    A variant of the Auth API that spawns an internal *prefetch
    task* that refreshes the data cache in the background.  Thanks
    to that we can eliminate the nasty delays encountered on
    data cache expiration by the base variant of the Auth API.
    """

    # Note: we want the *prefetch task* to repeatedly obtain
    # the following data in the background (as obtaining
    # them in the foreground is too much time-consuming,
    # at least in the case of the REST API and Portal):
    #
    # * the "root node", i.e., the result of calling the
    #   `LdapAPI`'s method `search_structured()` (which
    #   involves a lot of Auth DB queries as well as much
    #   of Python-level data processing);
    #
    # * the results of certain Auth API's public methods
    #   -- such ones that use the "root node" as their input,
    #   and involve much of additional, time-consuming, data
    #   processing.
    #
    # At the same time, we *do* want to keep the guarantee that Auth
    # API's public methods provide consistent results when used within
    # the same `with <Auth API instance>:` block.  That's why we make
    # the task's future object expose the "root node" as its result
    # value *and* use the `_result_cache_bound_to_prefetched_root_nodes`
    # key-value store -- keyed by "root node" objects -- to cache the
    # results of the most time-consuming Auth API's public methods.


    _SLEEP_BETWEEN_PREFETCH_TASK_FUNCTION_CALLS = 300

    _methods_with_result_cache_bound_to_prefetched_root_nodes = []


    def __init__(self, settings=None):
        super(AuthAPIWithPrefetching, self).__init__(settings=settings)

        self._result_cache_bound_to_prefetched_root_nodes = (
            _IdentityBasedThreadSafeCache(max_size=3))

        self._prefetch_task_data_preparer = _DataPreparer()
        self._prefetch_task = LoopedTask(
            target=self._get_prefetch_task_func(),
            loop_iteration_hook=self._get_loop_iteration_hook(),
            cancel_and_join_at_python_exit=True,

            # This initial delay is added to make sure that the
            # following *tick-callback*-related stuff is set up
            # before the start of the actual task's operation.
            initial_sleep=0.5)

        self._future = self._prefetch_task.async_start()

        backends_tick_callback = self._get_backends_tick_callback_checking_for_cancel(self._future)
        # Note: the `backends_tick_callback` callable does *not* need to
        # be thread-safe because all relevant uses of `self._ldap_api`
        # and `self._prefetch_task_data_preparer` are local to the
        # prefetching task thread.
        self._ldap_api.tick_callback = backends_tick_callback
        self._prefetch_task_data_preparer.tick_callback = backends_tick_callback


    #
    # Overridden AuthAPI methods

    get_org_ids_to_access_infos = _make_method_with_result_cache_bound_to_prefetched_root_nodes(
        'AuthAPIWithPrefetching',
        'get_org_ids_to_access_infos',
        _methods_with_result_cache_bound_to_prefetched_root_nodes)

    get_org_ids_to_combined_configs = _make_method_with_result_cache_bound_to_prefetched_root_nodes(
        'AuthAPIWithPrefetching',
        'get_org_ids_to_combined_configs',
        _methods_with_result_cache_bound_to_prefetched_root_nodes)


    def _get_root_node(self):
        return self._future.result()


    #
    # Internal helpers

    def _get_prefetch_task_func(self):
        ldap_api_cm = self._ldap_api
        preparer = self._prefetch_task_data_preparer

        methods_with_result_cache = self._methods_with_result_cache_bound_to_prefetched_root_nodes
        result_cache = self._result_cache_bound_to_prefetched_root_nodes

        def prefetch_task_func():
            try:
                with ldap_api_cm as ldap_api:
                    root_node = ldap_api.search_structured()
            except (LdapAPIConnectionError, SQLAlchemyError) as exc:
                raise AuthAPICommunicationError(traceback.format_exc(), exc)
            else:
                method_to_cached_result = result_cache[root_node]
                for name in methods_with_result_cache:
                    method = getattr(preparer, name)
                    method_to_cached_result[name] = method(root_node)
                return root_node

        return prefetch_task_func


    @classmethod
    def _get_loop_iteration_hook(cls):
        max_duration = cls._SLEEP_BETWEEN_PREFETCH_TASK_FUNCTION_CALLS

        def loop_iteration_hook(future):
            future.sleep_until_cancelled(max_duration)

        return loop_iteration_hook


    @staticmethod
    def _get_backends_tick_callback_checking_for_cancel(future):
        MIN_INTERVAL_BETWEEN_CHECKS = 0.1

        class PrefetchingCancelled(Exception):
            pass

        future_cancelled = future.cancelled
        cur_time = time.time
        tbox = [cur_time()]         # PY3: we can replace it with a free variable...

        def backends_tick_callback():
            t = cur_time()
            if t >= tbox[0] + MIN_INTERVAL_BETWEEN_CHECKS:
                if future_cancelled():
                    # Note that the following exception will be
                    # "shadowed" by a FutureCancelled exception.
                    raise PrefetchingCancelled
                tbox[0] = t

        # Note: the returned callable does *not* need to be
        # thread-safe (see the comment in `__init__()`...).
        return backends_tick_callback



class InsideCriteriaResolver(object):

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



class _DataPreparer(object):

    def __init__(self):
        # Can be set by client code to an arbitrary argumentless callable
        # (to be called relatively often during long-lasting operations):
        self.tick_callback = lambda: None

        self._using_legacy_version_of_access_filtering_conditions = (
            self._is_env_var_non_empty('N6_USE_LEGACY_VERSION_OF_ACCESS_FILTERING_CONDITIONS'))

        self._cond_builder = CondBuilder()
        self._cond_optimizer = self._make_access_filtering_cond_optimizer()
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
        if self._is_env_var_non_empty('N6_SKIP_OPTIMIZATION_OF_ACCESS_FILTERING_CONDITIONS'):
            return (lambda cond: cond)

        cond_optimizing_transformers = (    # (visitors that always *take* and *return* `Cond`s)
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

    def _make_access_filtering_cond_to_sqla_converter(self):
        cond_preparation_and_conversion_visitors = (
            CondDeMorganTransformer(),
            _CondToSQLAlchemyConverter(),
        )
        def converter(cond):
            assert isinstance(cond, Cond)
            for visitor in cond_preparation_and_conversion_visitors:
                cond = visitor(cond)
            assert not isinstance(cond, Cond)   # (now it is an SQLAlchemy object...)
            return cond
        return converter

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

    def get_org_ids_to_access_infos(self, root_node):
        # {
        #     <organization id as str>: {
        #         'access_zone_conditions': {
        #             <access zone: 'inside' or 'threats' or 'search'>: [
        #                 <an sqlalchemy.sql.expression.ColumnElement instance
        #                  implementing SQL condition for a subsource>,
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
        self._postprocess_access_info_filtering_conditions(result)
        return result

    def _get_access_info_filtering_condition_builder(self):
        if self._using_legacy_version_of_access_filtering_conditions:
            return LegacySQLAlchemyConditionBuilder(n6NormalizedData)
        return self._cond_builder

    def _postprocess_access_info_filtering_conditions(self, org_ids_to_access_infos):
        if self._using_legacy_version_of_access_filtering_conditions:
            return
        for access_info in org_ids_to_access_infos.values():
            for or_subconditions in access_info['access_zone_conditions'].values():
                self.tick_callback()
                cond_optimized = self._optimized_cond_from_or_subconditions(or_subconditions)
                sqla_optimized = self._cond_to_sqla_converter(cond_optimized)
                or_subconditions[:] = [sqla_optimized]

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
                cond_builder.not_(cond_builder['restriction'] == 'internal'))
        return condition

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


class _CondToSQLAlchemyConverter(CondVisitor):

    _NON_NULLABLE_COLUMNS = {
        # based on content of `etc/mysql/initdb/1_create_tables.sql`
        'id',
        'rid',
        'source',
        'restriction',
        'confidence',
        'category',
        'time',
        'ip',
    }

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

        if isinstance(subcond, IsNullCond):
            # (`!= None` will be converted by SQLAlchemy to `IS NOT NULL`)
            return self._sqla_column(subcond.rec_key) != None                  # noqa

        if isinstance(subcond, EqualCond):
            sqla_null_unsafe_neg = self._sqla_column(subcond.rec_key) != subcond.op_param
        elif isinstance(subcond, InCond):
            values = list(subcond.op_param)
            assert values  # guaranteed by InCond
            sqla_null_unsafe_neg = self._sqla_column(subcond.rec_key).notin_(values)
        else:
            sqla_null_unsafe_neg = self._sqla_not(self(subcond))

        # The following stuff protects us against the #3379 bug.
        if subcond.rec_key in self._NON_NULLABLE_COLUMNS:
            return sqla_null_unsafe_neg
        return self._sqla_or(
            # (`== None` will be converted by SQLAlchemy to `IS NULL`)
            self._sqla_column(subcond.rec_key) == None,                        # noqa
            sqla_null_unsafe_neg)

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

    def visit_IsNullCond(self, cond):
        # (`== None` will be converted by SQLAlchemy to `IS NULL`)
        return self._sqla_column(cond.rec_key) == None                         # noqa

    def visit_FixedCond(self, cond):
        return (self._sqla_make_true() if cond.truthness else self._sqla_make_false())


class _IdentityBasedThreadSafeCache(object):

    def __init__(self, max_size):
        self.__mutex = threading.RLock()
        self.__limited_dict = LimitedDict(maxlen=max_size)

    def __getitem__(self, key_obj):
        actual_key = _IdentityBasedKey(key_obj)
        with self.__mutex:
            try:
                method_to_cached_result = self.__limited_dict[actual_key]
            except KeyError:
                self.__limited_dict[actual_key] = method_to_cached_result = {}
        return method_to_cached_result


class _IdentityBasedKey(object):

    def __init__(self, obj):
        self._obj = obj

    def __hash__(self):
        return object.__hash__(self._obj)

    def __eq__(self, other):
        if isinstance(other, _IdentityBasedKey):
            return self._obj is other._obj
        return NotImplemented

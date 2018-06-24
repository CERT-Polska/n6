# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import collections
import bisect
import datetime
import fnmatch
import functools
import os
import re
import threading
import traceback

import ldap

from n6lib.class_helpers import (
    get_class_name,
    singleton,
)
from n6lib.common_helpers import (
    ascii_str,
    ip_network_as_tuple,
    ip_network_tuple_to_min_max_ip,
    ipv4_to_int,
    memoized,
    deep_copying_result,
)
from n6lib.const import CLIENT_ORGANIZATION_MAX_LENGTH
from n6lib.db_events import n6NormalizedData
from n6lib.db_filtering_abstractions import (
    BaseCond,
    PredicateConditionBuilder,
    SQLAlchemyConditionBuilder,
)
from n6lib.log_helpers import get_logger
try:
    if os.getenv('N6_FORCE_LDAP_API_REPLACEMENT') is not None:
        raise ImportError
    import n6lib.ldap_api
except ImportError:
    from n6lib.ldap_api_replacement import (
        LdapAPI,
        LdapAPIConnectionError,
        get_attr_value,
        get_attr_value_list,
        get_dn_segment_value,
        get_node,
    )
    LDAP_API_REPLACEMENT = True
else:
    from n6lib.ldap_api import (
        LdapAPI,
        LdapAPIConnectionError,
        get_attr_value,
        get_attr_value_list,
        get_dn_segment_value,
        get_node,
    )
    LDAP_API_REPLACEMENT = False



__all__ = 'AuthAPI', 'AuthAPIUnauthenticatedError'



LOGGER = get_logger(__name__)



DEFAULT_MAX_DAYS_OLD = 100
DEFAULT_RESOURCE_LIMIT_WINDOW = 3600

# There is a direct 1-to-1 relation between the following three REST API
# resources ("data stream" resources) and the three access zones.  NOTE
# that, apart from them, there are also other REST API resources (such
# as /device/...) which are *not* related to any particular access zone.
RESOURCE_ID_TO_ACCESS_ZONE = {
    '/report/inside': 'inside',
    '/report/threats': 'threats',
    '/search/events': 'search',
}
ACCESS_ZONE_TO_RESOURCE_ID = dict(
    (az, res_id)
    for res_id, az in RESOURCE_ID_TO_ACCESS_ZONE.iteritems())
ACCESS_ZONES = frozenset(ACCESS_ZONE_TO_RESOURCE_ID)

_BOOL_TO_FLAG = {True: 'TRUE', False: 'FALSE'}
_FLAG_TO_BOOL = {f: b for b, f in _BOOL_TO_FLAG.iteritems()}



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



@singleton
class AuthAPI(object):

    """
    An API that provides common set of authentication/authorization methods.

    The constructor takes one optional argument: `settings` (to be used
    by n6lib.{ldap_api,ldap_api_replacement}.LdapAPI constructor; see
    also the docs of the n6lib.config.Config class).

    Use the (reentrant) context manager interface to ensure that a series
    of method calls will be consistent in terms of LDAP data state (i.e.
    all the calls will use the same set of data, produced with the same
    LDAP query).  Example:

        with auth_api:
            inside_crit_resolver = auth_api.get_inside_criteria_resolver()
            org_id_to_acc_inf = auth_api.get_org_ids_to_access_infos()
    """

    # XXX: [ticket #3312] Is this tween operational for stream responses???
    # [ad: "Note: n6lib.pyramid_commons.N6ConfigHelper adds a tween that
    # automatically applies that context manager to pyramid requests."]


    def __init__(self, settings=None):
        self._thread_local = threading.local()
        self._ldap_api = LdapAPI(settings)


    #
    # Context manager interface

    def __enter__(self):
        loc = self._thread_local
        context_count = getattr(loc, 'context_count', 0)
        if context_count == 0:
            loc.ldap_root_node = self._get_root_node()
        assert getattr(loc, 'ldap_root_node', None) is not None
        loc.context_count = context_count + 1
        return self

    def __exit__(self, exc_type, exc, tb):
        loc = self._thread_local
        assert getattr(loc, 'ldap_root_node', None) is not None
        loc.context_count = context_count = loc.context_count - 1
        if context_count == 0:
            loc.ldap_root_node = None


    #
    # Public methods

    # WARNING: when you call this function you should *never* modify its results!
    def get_ldap_root_node(self):
        root_node = getattr(self._thread_local, 'ldap_root_node', None)
        if root_node is None:
            root_node = self._get_root_node()
        return root_node

    def authenticate(self, org_id, user_id):
        """
        Authenticates by org_id and user_id.

        Args/kwargs:
            `org_id`: organization id as a string.
            `user_id`: user id as a string.

        Returns:
            {'org_id': <organization id>,
             'user_id': <user id>}

        Raises:
            AuthAPIUnauthenticatedError: user or organization does not exist.
        """
        assert org_id is not None
        assert user_id is not None
        user_ids_to_org_ids = self.get_user_ids_to_org_ids()
        try:
            stored_org_id = user_ids_to_org_ids[user_id]
        except KeyError:
            raise AuthAPIUnauthenticatedError
        if stored_org_id != org_id:
            raise AuthAPIUnauthenticatedError
        return {'user_id': user_id, 'org_id': org_id}

    def authenticate_with_password(self, org_id, user_id, password):
        self._ldap_api.authenticate_with_password(org_id, user_id, password)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_user_ids_to_org_ids(self):
        """
        Returns the user-id-to-org-id mapping (as a dict).
        """
        result = {}
        org_id_to_node = self.get_ldap_root_node()['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.iteritems():
            self._check_org_length(org_id)
            user_id_to_node = org.get('n6login', {})
            for user_id, user in user_id_to_node.iteritems():
                stored_org_id = result.setdefault(user_id, org_id)
                if stored_org_id != org_id:
                    LOGGER.error(
                        'Problem with LDAP data: user %r belongs to '
                        'more than one organization (%r and %r '
                        '-- only the former will be stored in the '
                        'user-id-to-org-id mapping)',
                        user_id, stored_org_id, org_id)
        return result

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_org_ids(self):
        """
        Returns a frozenset of all organization ids (typically, already cached).
        """
        all_org_ids = frozenset(self.get_ldap_root_node()['ou']['orgs'].get('o', frozenset()))
        for org_id in all_org_ids:
            self._check_org_length(org_id)
        return all_org_ids

    # note: @deep_copying_result is unnecessary here as InsideCriteriaResolver's
    # public interface does not include any mutating methods or properties
    @cached_basing_on_ldap_root_node
    def get_inside_criteria_resolver(self):
        """
        Returns an InsideCriteriaResolver instance (typically already cached).
        """
        inside_criteria = self._get_inside_criteria()
        return InsideCriteriaResolver(inside_criteria)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_anonymized_source_mapping(self):
        """
        Returns a dict (typically already cached):

        {
            'forward_mapping': {
                 <source id>: <anonymized source id>,
                 ...
            },
            'reverse_mapping': {
                 <anonymized source id>: <source id>,
                 ...
            },
        }
        """
        source_id_to_node = self.get_ldap_root_node()['ou']['sources'].get('cn', {})
        forward_mapping = {}
        for source_id, node in source_id_to_node.iteritems():
            try:
                forward_mapping[source_id] = get_attr_value(node, 'n6anonymized')
            except ValueError as exc:
                LOGGER.error('Problem with LDAP data for the source %r: %s',
                             source_id, exc)
        reverse_mapping = {anonymized_id: source_id
                           for source_id,
                               anonymized_id in forward_mapping.iteritems()}
        return {'forward_mapping': forward_mapping,
                'reverse_mapping': reverse_mapping}

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_dip_anonymization_disabled_source_ids(self):
        """
        Returns a frozenset of source ids (typically already cached) for
        which anonymization of `dip` is *not enabled*.
        """
        source_id_to_node = self.get_ldap_root_node()['ou']['sources'].get('cn', {})
        return frozenset(
            source_id
            for source_id, node in source_id_to_node.iteritems()
            if not self._is_flag_enabled(
                node,
                caption='the source {!r}'.format(source_id),
                attribute='n6dip-anonymization-enabled',
                on_missing=False,  # <- by default, anonymization is disabled -- though...
                on_illegal=True,   # <- ...let's be on the safe side when LDAP data are malformed
            ))

    #@deep_copying_result <- we cannot use it here as part of defensive programming
    #                        because there are problems with copying ColumnElement objects
    #                        (instead, you need to be careful: to *never* modify resulting dicts)
    def get_access_info(self, auth_data):
        """
        Get the REST API access information for the specified organization.

        Args:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id>, 'user_id': <user id>}.

        Returns:
            None or a dictionary (for a single organization), provided by
            getting: <AuthAPI instance>.get_org_ids_to_access_infos()[<org id>]
        """
        org_id = auth_data['org_id']
        all_access_infos = self.get_org_ids_to_access_infos()
        return all_access_infos.get(org_id)

    #@deep_copying_result <- we cannot use it here as part of defensive programming
    #                        because there are problems with copying ColumnElement objects
    #                        (instead, you need to be careful: to *never* modify resulting dicts)
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_access_infos(self):
        """
        Get a dict that maps organization ids to REST API access information.

        Returns a dict (typically already cached):

        {
            <organization id as string>: {
                'access_zone_conditions': {
                    <access zone: 'inside' or 'threats' or 'search'>: [
                        <an sqlalchemy.sql.expression.ColumnElement instance
                         implementing SQL condition for a subsource>,
                        ...
                    ],
                    ...
                },
                'rest_api_full_access': <True or False>,
                'rest_api_resource_limits': {
                    <resource id (URL-path-based)>: {
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
                },
            },
            ...
        }

        Note that:

        * Organizations for whom some (or even all) REST API "data
          stream" resources are *disabled* (i.e., whose LDAP entries do
          not have any `cn=res-...` child entries) *are still included*.

        * NOTE, however, that organizations that do *not* have access to
          any subsource for any access zone *are excluded*.

        * The `access_zone_conditions` information includes only access
          zones for whom the given organization does have access to any
          subsource.

        * Only the "data stream" resources of REST API (those identified
          by the resource ids: '/report/inside', '/report/threats',
          '/search/events'; *not* other REST API resources such as
          '/device/...') are covered by the `rest_api_resource_limits`
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
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        result = self._make_org_ids_to_access_infos(root_node, org_id_to_node)
        self._set_resource_limits(result, root_node, org_id_to_node)
        return result

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_stream_api_enabled_org_ids(self):
        """
        Returns a frozenset of ids (typically, already cached) of the
        organizations for whom the `n6stream-api-enabled` flag is set
        to "TRUE".
        """
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return frozenset(self._generate_stream_api_enabled_org_ids(org_id_to_node))

    # note: @deep_copying_result is unnecessary here as results are purely immutable
    @cached_basing_on_ldap_root_node
    def get_stream_api_disabled_org_ids(self):
        """
        Returns a frozenset of ids (typically, already cached) of the
        organizations for whom the `n6stream-api-enabled` flag is set
        to "FALSE", or to some illegal content (e.g., multiple values).
        """
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return frozenset(self._generate_stream_api_disabled_org_ids(org_id_to_node))

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_source_ids_to_subs_to_stream_api_access_infos(self):
        """
        Get a dict that maps source ids to per-subsource Stream (STOMP) API
        access information.

        Returns a dict (typically already cached):

        {
            <source id>: {
                <subsource DN (string)>: (
                    <filtering predicate: a callable that takes an instance of
                     n6lib.db_filtering_abstractions.RecordFacadeForPredicates
                     as the sole argument and returns True or False>,
                    {
                        'inside': <set of organization ids>,
                        'threats': <set of organization ids>,
                        'search': <set of organization ids>,
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
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return self._make_source_ids_to_subs_to_stream_api_access_infos(
            root_node,
            org_id_to_node)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_source_ids_to_notification_access_info_mappings(self):
        """
        Get a dict that maps source ids to per-subsource access information
        related to e-mail notifications.

        Returns a dict (typically already cached):

        {
            <source id>: {
                (<subsource DN (string)>, <for full access orgs? (bool)>): (
                    <filtering predicate: a callable that takes an instance of
                      n6lib.db_filtering_abstractions.RecordFacadeForPredicates
                      as the sole argument and returns True or False>,
                    <set of organization ids>,
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
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        return self._make_source_ids_to_notification_access_info_mappings(
            root_node,
            org_id_to_node)

    @deep_copying_result  # <- just defensive programming
    @cached_basing_on_ldap_root_node
    def get_org_ids_to_notification_configs(self):
        """
        Get a dict that maps organization ids to e-mail notification configs.

        Returns a dict (typically already cached):

        {
            <org id>: {
                'n6email-notifications-times': [<datetime.time instance>, ...],  # sorted
                'n6email-notifications-address': [<string>, ...],                # sorted
                'name': <a string or False (bool)>,
                'n6stream-api-enabled': <bool>,
            },
            ...
        }

        Organizations for whom e-mail notifications are not enabled (the
        `n6email-notifications-enabled` flag is not set to sole "TRUE")
        are *not* included.

        A value for 'n6email-notifications-times' or
        'n6email-notifications-address' is always a sorted list; it can
        be an empty list.
        """
        notification_config = {}
        root_node = self.get_ldap_root_node()
        org_id_to_node = root_node['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.iteritems():
            self._check_org_length(org_id)
            if self._is_flag_enabled_for_org(org, org_id, 'n6email-notifications-enabled'):
                email_notification_time = []
                for time in get_attr_value_list(org, 'n6email-notifications-times'):
                    try:
                        email_notification_time.append(self._parse_notification_time(time))
                    except ValueError as exc:
                        LOGGER.error(
                            'Incorrect format of notification time %r for org id %r (%s)',
                            time, org_id, exc)
                if not email_notification_time:
                    LOGGER.warning('No notification times for org id %r', org_id)
                email_notification_address = get_attr_value_list(
                    org, 'n6email-notifications-address')
                if not email_notification_address:
                    LOGGER.warning('No notification email addresses for org id %r', org_id)
                name = get_attr_value(org, 'name', default=False)
                if not name:
                    LOGGER.info('No name for org id %r', org_id)
                if self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                    n6stream_api_enabled = True
                else:
                    n6stream_api_enabled = False
                if self._is_flag_enabled_for_org(
                        org, org_id, 'n6email-notifications-business-days-only'):
                    notifications_business_days_only = True
                else:
                    notifications_business_days_only = False
                email_notifications_language = get_attr_value(org, 'n6email-notifications-language', default='pl')

                notification_config[org_id] = {
                    'n6email-notifications-times': sorted(email_notification_time),
                    'n6email-notifications-address': sorted(email_notification_address),
                    'name': name,
                    'n6stream-api-enabled': n6stream_api_enabled,
                    'n6email-notifications-business-days-only': notifications_business_days_only,
                    'n6email-notifications-language': email_notifications_language,
                }

        return notification_config


    #
    # Non-public methods

    @memoized(expires_after=600, max_size=3)
    def _get_root_node(self):
        ## NOTE: possible future optimization: fetching ldap root node
        ## data in a separate thread... (see n6lib.ldap_dict at changeset
        ## 98b8dca0b01d for inspiration)
        try:
            with self._ldap_api as ldap_api:
                return ldap_api.search_structured()
        except (LdapAPIConnectionError, ldap.LDAPError) as exc:
            raise AuthAPICommunicationError(traceback.format_exc(), exc)

    def _get_inside_criteria(self):
        # returns a list of dicts, such as:
        #     [
        #         {
        #             'org_id': <organization id (string)>,
        #
        #             # the rest of items are optional:
        #             'fqdn_seq': [<fqdn (unicode string)>, ...],
        #             'asn_seq': [<asn (int)>, ...],
        #             'cc_seq': [<cc (unicode string)>, ...],
        #             'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],
        #             'url_seq': [<url (unicode string)>, ...],
        #         },
        #         ...
        #     ]
        result = []
        org_id_to_node = self.get_ldap_root_node()['ou']['orgs'].get('o', {})
        for org_id, org in org_id_to_node.iteritems():
            self._check_org_length(org_id)
            asn_seq = list(map(int, get_attr_value_list(org, 'n6asn')))
            cc_seq = list(get_attr_value_list(org, 'n6cc'))
            fqdn_seq = list(get_attr_value_list(org, 'n6fqdn'))
            ip_min_max_seq = list(map(ip_network_tuple_to_min_max_ip,
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
        for org_id, org in org_id_to_node.iteritems():
            if self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                yield org_id

    def _generate_stream_api_disabled_org_ids(self, org_id_to_node):
        for org_id, org in org_id_to_node.iteritems():
            if not self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                yield org_id

    def _make_org_ids_to_access_infos(self, root_node, org_id_to_node):
        result = {}
        cond_builder = SQLAlchemyConditionBuilder(n6NormalizedData)
        grouped_set = self._get_org_subsource_az_tuples(root_node, org_id_to_node)
        for org_id, subsource_refint, access_zone in sorted(grouped_set):  # (deterministic order)
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
                    'rest_api_full_access': full_access,
                    # to be filled in _set_resource_limits():
                    'rest_api_resource_limits': {},
                }
                result[org_id] = access_info
            else:
                access_info['access_zone_conditions'].setdefault(access_zone, []).append(cond)
        return result

    def _make_source_ids_to_subs_to_stream_api_access_infos(self, root_node, org_id_to_node):
        result = {}
        cond_builder = PredicateConditionBuilder()
        grouped_set = self._get_org_subsource_az_tuples(root_node, org_id_to_node)
        for org_id, subsource_refint, access_zone in sorted(grouped_set):  # (deterministic order)
            org = org_id_to_node[org_id]
            if not self._is_flag_enabled_for_org(org, org_id, 'n6stream-api-enabled'):
                continue
            resource_id = ACCESS_ZONE_TO_RESOURCE_ID[access_zone]
            if not self._is_resource_enabled_for_org(resource_id, org, org_id):
                continue
            source_id = get_dn_segment_value(subsource_refint, 1)
            subsource_to_saa_info = result.setdefault(source_id, {})
            saa_info = subsource_to_saa_info.get(subsource_refint)
            if saa_info is None:
                cond = self._get_condition_for_subsource_and_full_access_flag(
                    root_node, source_id, subsource_refint, cond_builder)
                saa_info = predicate, az_to_org_ids = (
                    cond.predicate,
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
                        isinstance(predicate, BaseCond)  # <- for unit tests only
                    )
                ) and (
                    saa_info[1] is az_to_org_ids and
                    isinstance(az_to_org_ids, dict) and
                    az_to_org_ids.viewkeys() == ACCESS_ZONES and
                    access_zone in ACCESS_ZONES and
                    isinstance(az_to_org_ids[access_zone], set) and
                    org_id in az_to_org_ids[access_zone]))
        return result

    def _make_source_ids_to_notification_access_info_mappings(self, root_node, org_id_to_node):
        ### TODO later?: get rid of code duplication with the
        ### _make_source_ids_to_subs_to_stream_api_access_infos()
        ### method.
        result = {}
        cond_builder = PredicateConditionBuilder()
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
                    na_info = predicate, na_org_ids = cond.predicate, set()
                    na_info_mapping[na_info_key] = na_info
                else:
                    predicate, na_org_ids = na_info
                na_org_ids.add(org_id)
        return result

    def _set_resource_limits(self, org_id_to_access_info, root_node, org_id_to_node):
        for org_id, access_info in org_id_to_access_info.iteritems():
            org = org_id_to_node[org_id]
            for resource_id in RESOURCE_ID_TO_ACCESS_ZONE:
                limits = self._get_resource_limits_for_org(resource_id, org, org_id)
                if limits is not None:
                    access_info['rest_api_resource_limits'][resource_id] = limits

    def _get_org_subsource_az_tuples(self, root_node, org_id_to_node):
        # returns a set of (<org id>, <subsource DN>, <access zone>) tuples
        included = set()
        excluded = set()
        for (org_id, subsource_refint, access_zone, is_excluding
             ) in self._iter_org_subsource_az_ex_tuples(root_node, org_id_to_node):
            if is_excluding:
                excluded.add((org_id, subsource_refint, access_zone))
            else:
                included.add((org_id, subsource_refint, access_zone))
        included -= excluded
        return included

    def _iter_org_subsource_az_ex_tuples(self, root_node, org_id_to_node):
        # yields (<org id>, <subsource DN>, <access zone>, <is excluding?>) tuples
        for org_id, org in org_id_to_node.iteritems():
            self._check_org_length(org_id)
            org_props = org.get('cn')
            if org_props:
                for access_zone in ACCESS_ZONES:
                    for ex_suffix in ('', '-ex'):
                        channel = org_props.get(access_zone + ex_suffix)
                        for subsource_refint in (
                                self._iter_channel_subsource_refints(root_node, channel)):
                            # for org <-> subsource
                            # and org <-> subsource group <-> subsource
                            yield org_id, subsource_refint, access_zone, bool(ex_suffix)

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
            ### FIXME: a bug! -- see: #3379
            cond_builder.and_(*(cond_builder.not_(container_condition)
                                for container_condition in exclusion_container_conditions)))

    def _iter_container_conditions(self, root_node, subsource, kind, cond_builder):
        assert kind in ('inclusion', 'exclusion')
        for criteria_refint in get_attr_value_list(subsource,
                                                   'n6{0}-criteria-refint'.format(kind)):
            criteria_container_node = get_node(root_node, criteria_refint)
            criteria_container_items = sorted(  # (sorting to make the order deterministic)
                (attr_name[2:], value_list)
                for attr_name, value_list in criteria_container_node['attrs'].iteritems()
                if attr_name in ('n6asn', 'n6cc', 'n6ip-network', 'n6category', 'n6name'))
            if criteria_container_items:
                crit_conditions = tuple(
                    self._iter_crit_conditions(criteria_container_items, cond_builder))
                if not crit_conditions:
                    raise AssertionError(
                        'criteria_container_items containing (only) empty value '
                        'lists??? ({!r})'.format(criteria_container_items))
                yield cond_builder.or_(*crit_conditions)

    def _iter_crit_conditions(self, criteria_container_items, cond_builder):
        for name, value_list in criteria_container_items:
            if not value_list:
                continue
            if None in value_list:
                raise AssertionError(
                    'value_list containing None??? ({!r}; whole '
                    'criteria_container_items: {!r})'.format(
                        value_list, criteria_container_items))
            if name == 'ip-network':
                for ip_network_str in value_list:
                    ip_network_tuple = ip_network_as_tuple(ip_network_str)
                    min_ip, max_ip = ip_network_tuple_to_min_max_ip(ip_network_tuple)
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
            caption='the organization {0!r}'.format(org_id),
            attribute=attribute,
            on_missing=on_missing,
            on_illegal=on_illegal)

    def _is_flag_enabled(self, node, caption, attribute,
                         on_missing=False, on_illegal=False):
        try:
            attrib_flag = get_attr_value(node, attribute, _BOOL_TO_FLAG[on_missing]).upper()
            if attrib_flag not in _FLAG_TO_BOOL:
                raise ValueError(
                    "{} is neither 'TRUE' nor 'FALSE' (got: {!r})"
                    .format(attribute, attrib_flag))
        except ValueError as exc:
            LOGGER.error('Problem with LDAP data for %s: %s', caption, exc)
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
                    LOGGER.error('Problem with LDAP data for the organization %r: %s',
                                 org_id, exc)
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
                                 .format(', '.join(sorted(map(repr, required_parameters))),
                                         ', '.join(sorted(map(repr, all_parameters)))))
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
                'The length of the organization id %r is %s '
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



class InsideCriteriaResolver(object):

    """
    The class implements efficiently the main part of the Filter's job:
    to determine the contents of the `client` and `urls_matched`
    normalized event data items.

    The InsideCriteriaResolver constructor takes one argument: a
    sequence of criteria for the `inside` access zone, as returned by
    AuthAPI._get_inside_criteria(), i.e., a list of dicts:

        [
            {
                'org_id': <organization id (string)>,

                # the rest of items are optional:
                'fqdn_seq': [<fqdn suffix (unicode string)>, ...],
                'asn_seq': [<asn (int)>, ...],
                'cc_seq': [<cc (string)>, ...],
                'ip_min_max_seq': [(<min. ip (int)>, <max. ip (int)>), ...],
                'url_seq': [<url (unicode string)>, ...],
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
        #   (<org id (string)>,
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

        for ip, id_endpoints in sorted(ip_to_id_endpoints.iteritems()):
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
        Get org ids that the given event's `clients` attribute should include.

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
            * a dict mapping org ids to lists of (sorted) matching ulrs.
        """

        client_org_ids = set()
        urls_matched = dict()

        # FQDN
        fqdn = record_dict.get('fqdn')
        if fqdn is not None:
            fqdn_suffix_to_ids = self._fqdn_suffix_to_ids
            fqdn_parts = fqdn.split('.')
            for i in xrange(0, len(fqdn_parts)):
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
                        ### XXX: do we really want to use the re.UNICODE flag here???
                        match1 = re.compile(url_pattern, re.UNICODE).search
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
                        'Exception occurred when trying to process `url_pattern` (%r) '
                        '-- %s: %s', url_pattern, get_class_name(exc), ascii_str(exc))
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

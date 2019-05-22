# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import collections
import datetime
import functools
import json
import operator
utcnow = datetime.datetime.utcnow  # for easier mocking in unit tests

from ldap import INVALID_CREDENTIALS
from pyramid.httpexceptions import HTTPForbidden
from pyramid.response import Response
from pyramid.security import (
    forget,
    remember,
)
from sqlalchemy import engine_from_config, or_, and_
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import contains_eager

from n6lib.auth_api import (
    ACCESS_ZONES,
    AuthAPIUnauthenticatedError,
)
from n6lib.class_helpers import singleton
from n6lib.common_helpers import (
    ascii_str,
    memoized,
    with_flipped_args,
)
from n6lib.db_events import (
    DBSession,
    Base,
    n6NormalizedData,
    n6ClientToEvent,
)
from n6lib.generate_test_events import RandomEvent
from n6lib.log_helpers import get_logger
from n6lib.pyramid_commons import get_certificate_credentials
from n6lib.transaction_helpers import autotransact

from n6sdk.exceptions import (
    DataAPIError,
    TooMuchDataError,
)


LOGGER = get_logger(__name__)


## TODO: implement applying per-resource limits!

@singleton
class N6DataBackendAPI(object):

    """
    An API that provides common set of event-database methods.
    """

    DEFAULT_DATE_STEP = 1


    __db_config_guard = collections.deque([None])

    @classmethod
    def configure_db_session(cls, engine):
        """
        Configure and get the scoped session object

        This method cannot be called more than once (or RuntimeError is
        raised) -- including implicit calling by __init__().
        """
        try:
            # deque operations are documented as thread-safe
            cls.__db_config_guard.pop()
        except IndexError:
            raise RuntimeError('cannot configure db session more than once')
        DBSession.configure(bind=engine)
        Base.metadata.bind = engine
        return DBSession

    @staticmethod
    def get_db_session():
        """Get the scoped session object."""
        return DBSession


    def __init__(self, settings, engine=None):
        """
        Set up the Master API and initialize DB connections.

        Kwargs:
            `settings` (required):
                A dictionary which could be passed to an
                `sqlalchemy.engine_from_config(..., prefix='sqlalchemy.')`
                call (e.g. a Pyramid settings dict).
            `engine` (optional):
                An sqlalchemy.engine.Engine instance (overrides engine
                config from `settings`.
        """

        self.day_step = float(settings.get('day_step', self.DEFAULT_DATE_STEP))
        if engine is None:
            ssl_args = {}
            if 'mysql.api.ssl_key' in settings:
                ssl_args = {'ssl': {'cert': settings['mysql.api.ssl_cert'],
                                    'key': settings['mysql.api.ssl_key'],
                                    'ca': settings['mysql.api.ssl_cacert'], }}
            engine = engine_from_config(settings, 'sqlalchemy.', connect_args=ssl_args)
        self.configure_db_session(engine)


    @autotransact
    def report_inside(self, auth_data, params, data_spec,
                      access_zone_conditions, res_limits,
                      item_number_limit=None):
        """
        Get iterator over events inside organization's network.

        Args/kwargs:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id>, 'user_id': <user id>}.
            `params`:
                A dictionary of cleaned and deanonymized parameters.
            `data_spec`:
                A n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (strings)
                to lists of SQLAlchemy conditions (see:
                n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `res_limits`:
                A dict of limits for the particular REST API resource
                (see: n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).

        Optional kwargs:
            `item_number_limit` (int or None; default: None):
                Maximum number of result items.

        Returns:
            An iterator yielding JSON-serializable dicts representing
            the queried events.
        """
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           res_limits,
                                           item_number_limit,
                                           access_zone='inside',
                                           client_id=auth_data['org_id'])

    @autotransact
    def report_threats(self, auth_data, params, data_spec,
                       access_zone_conditions, res_limits,
                       item_number_limit=None):
        """
        Get iterator over events associated with/available for organization.

        Args/kwargs:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id>, 'user_id': <user id>}.
            `params`:
                A dictionary of cleaned and deanonymized parameters.
            `data_spec`:
                A n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (strings)
                to lists of SQLAlchemy conditions (see:
                n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `res_limits`:
                A dict of limits for the particular REST API resource
                (see: n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).

        Optional kwargs:
            `item_number_limit` (int or None; default: None):
                Maximum number of result items.

        Returns:
            An iterator yielding JSON-serializable dicts representing
            the queried events.
        """
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           res_limits,
                                           item_number_limit,
                                           access_zone='threats')

    @autotransact
    def search_events(self, auth_data, params, data_spec,
                      access_zone_conditions, res_limits,
                      item_number_limit=None):
        """
        Get iterator over events matching the specified parameters.

        Args/kwargs:
            `auth_data`:
                Authenticated organization data in format:
                {'org_id': <org id>, 'user_id': <user id>}.
            `params`:
                A dictionary of cleaned and deanonymized parameters.
            `data_spec`:
                A n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (strings)
                to lists of SQLAlchemy conditions (see:
                n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `res_limits`:
                A dict of limits for the particular REST API resource
                (see: n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).

        Optional kwargs:
            `item_number_limit` (int or None; default: None):
                Maximum number of result items.

        Returns:
            An iterator yielding JSON-serializable dicts representing
            the queried events.
        """
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           res_limits,
                                           item_number_limit,
                                           access_zone='search')

    def get_user_info(self,
                      is_authenticated,
                      available_resources=None,
                      full_access=False,
                      certificate_fetched=False):
        body = {
            'authenticated': is_authenticated,
            'certificate_fetched': certificate_fetched,
        }
        if is_authenticated:
            body['available_resources'] = available_resources
            if full_access:
                body['full_access'] = full_access
        serialized_body = json.dumps(body)
        return Response(serialized_body, content_type='application/json')

    def login(self, request, auth_api):
        post_data = request.POST
        try:
            user_id = post_data.getone('user_id')
            org_id = post_data.getone('org_id')
            password = post_data.getone('password')
        except KeyError as e:
            LOGGER.debug('User has not filled all credential fields for authentication. %s.',
                         e.message)
            raise HTTPForbidden
        if user_id and org_id and password:
            try:
                auth_api.authenticate_with_password(org_id, user_id, password)
            except INVALID_CREDENTIALS:
                LOGGER.warning('User tried to authenticate with invalid credentials. '
                               'User id: %r, organization id: %r.', user_id, org_id)
                raise HTTPForbidden
            credentials = self._join_org_id_user_id(org_id, user_id)
            headers = remember(request, credentials)
            self._add_content_type_header(headers)
            return Response(headerlist=headers)

    def login_with_cert(self, request, auth_api):
        org_id, user_id = get_certificate_credentials(request)
        try:
            auth_api.authenticate(org_id, user_id)
        except AuthAPIUnauthenticatedError:
            LOGGER.warning('Could not authenticate with certificate for '
                           'organization id %r + user id %r.', org_id, user_id)
            raise HTTPForbidden
        else:
            credentials = self._join_org_id_user_id(org_id, user_id)
            headers = remember(request, credentials)
            self._add_content_type_header(headers)
            return Response(headerlist=headers)

    def logout(self, request, auth_api):
        headers = forget(request)
        self._add_content_type_header(headers)
        return Response(headerlist=headers)

    def _generate_result_dicts(self, params, data_spec, access_zone_conditions,
                               res_limits, item_number_limit, access_zone,
                               client_id=None):
        """
        Common code for the report_inside/report_threats/search_events methods.

        Args/kwargs:
            `params`:
                A dictionary of cleaned and deanonymized parameters.
            `data_spec`:
                A n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (strings)
                to lists of SQLAlchemy conditions (see:
                n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `res_limits`:
                A dict of limits for the particular REST API resource
                (see: n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `item_number_limit` (int or None):
                Maximum number of result items.
            `access_zone`:
                The requested resource's acces_zone (a string; one of those
                in n6lib.auth_api.ACCESS_ZONES).

        Optional kwargs:
            `client_id` (string or None; default: None):
                The organization id of the client (for the 'inside'
                access zone).

        Returns:
            An iterator yielding JSON-serializable dicts representing
            the queried events.

        See also: _QueryProcessor.generate_query_results().
        """
        assert access_zone in ACCESS_ZONES
        query_processor = _QueryProcessor(
            data_spec,
            access_filtering_conditions=access_zone_conditions.get(access_zone),
            max_days_old=res_limits['max_days_old'],
            client_id=client_id,
        )
        return query_processor.generate_query_results(
            params,
            item_number_limit=item_number_limit,
            day_step=self.day_step,
        )

    @staticmethod
    def _add_content_type_header(headers):
        """
        Add a 'Content-Type' header to a list of headers returned
        by `remember` or `forget` function of authentication policy.

        It resolves an XML parsing error during request from GUI.

        Args:
            `headers` (list):
                a list of headers generated by a proper function
                provided by authentication policy class.
        """
        headers.append(('Content-Type', 'text/plain'))

    @staticmethod
    def _join_org_id_user_id(org_id, user_id):
        return ','.join((org_id, user_id))


class _QueryProcessor(object):

    YIELD_PER = 100

    queried_model_class = n6NormalizedData
    client_relationship = 'clients'
    client_asoc_model_class = n6ClientToEvent
    client_asoc_column = 'client'
    param_keys_without_query_func = {
        # here an element can end with the '.*' wildcard (not regex)
        'opt.*',   # <- e.g. 'opt.primary'
        'time.*',  # <- e.g. 'time.min'
        client_asoc_column,
    }

    #
    # Initialization stuff

    def __init__(self, data_spec, access_filtering_conditions, max_days_old,
                 client_id=None):
        """
        Initialize the query processor.

        Args/kwargs:
            `data_spec`:
                A n6lib.data_spec.N6DataSpec instance.
            `access_filtering_conditions`:
                A list of SQLAlchemy conditions (see:
                n6lib.auth_api.AuthAPI.get_org_ids_to_access_infos()).
            `max_days_old`:
                [NOTE: not used yet, to be implemented...]
                [TODO: doc].

        Optional kwargs:
            `client_id` (string or None; default: None):
                The organization id of the client (for the 'inside'
                access zone).
        """
        self.key_to_query_func = self._get_key_to_query_func(data_spec)
        self.access_filtering_conditions = access_filtering_conditions
        self.max_days_old = max_days_old
        self.the_client_id = client_id

    @classmethod
    @memoized
    def _get_key_to_query_func(cls, data_spec):
        key_to_query_func = {}
        model_class = cls.queried_model_class
        assert data_spec.sql_relationship_field_keys == {cls.client_asoc_column}
        assert (data_spec.sql_relationship_field_keys  # {'client'}
                ).issubset(cls.param_keys_without_query_func)
        for key, field in data_spec.param_field_specs().iteritems():
            if not any(
                    k in cls.param_keys_without_query_func
                    for k in cls._generate_key_wildcards(key)):
                query_func_name = field.custom_info.get('func', 'key_query')
                query_func = getattr(model_class, query_func_name)
                key_to_query_func[key] = query_func
        return key_to_query_func

    @staticmethod
    def _generate_key_wildcards(key):
        """
        >>> list(_QueryProcessor._generate_key_wildcards('foo'))
        ['foo']
        >>> list(_QueryProcessor._generate_key_wildcards('foo.bar'))
        ['foo.bar', 'foo.*']
        >>> list(_QueryProcessor._generate_key_wildcards('foo.bar.spam'))
        ['foo.bar.spam', 'foo.*', 'foo.bar.*']
        >>> list(_QueryProcessor._generate_key_wildcards('foo.bar.spam.ham'))
        ['foo.bar.spam.ham', 'foo.*', 'foo.bar.*', 'foo.bar.spam.*']
        """
        yield key
        key_segments = key.split('.')
        for i in xrange(1, len(key_segments)):
            yield '.'.join(key_segments[:i]) + '.*'

    #
    # Building and running queries

    def generate_query_results(self, params, item_number_limit, day_step):
        """
        Generate the queried events.

        Args/kwargs:
            `params`:
                A dictionary of cleaned parameters.
            `item_number_limit` (int or None):
                Maximum number of result items.
            `day_step` (int or float):
                The length of the time window for a single query -- in
                days.

        Yields:
            Subsequent result dicts (each representing an event).

        Raises:
            TooMuchDataError:
                if `item_number_limit` is exceeded.
            DataAPIError:
                if database operations go wrong.

        Note that exceptions (if any) are being raised during iterating
        over the generator (not during the N6DataBackendAPI method call
        that only produces a fresh generator).
        """

        YIELD_PER = self.YIELD_PER
        queried_model_class = self.queried_model_class
        client_asoc_model_class = self.client_asoc_model_class
        client_relationship_obj = getattr(queried_model_class,
                                          self.client_relationship)

        opt_limit = self.pop_limit(params)
        if opt_limit is not None and YIELD_PER < opt_limit:
            YIELD_PER = opt_limit

        self.delete_opt_prefixed_params(params)
        time_min, time_max, time_until = self.pop_time_min_max_until(params)
        time_cmp_generator = self.make_time_cmp_generator(
            time_min, time_max, time_until, day_step)
        client_ids = self.pop_client_ids(params)
        base_query = self.build_query(params, client_ids)

        processed_items = 0
        for compare_to_time_lower, compare_to_time_upper in time_cmp_generator:
            per_query_yielded_items = 0
            query = base_query.filter(and_(
                compare_to_time_lower(queried_model_class.time),
                compare_to_time_upper(queried_model_class.time)))
            # added join at this point, because a join condition (time) changes each query
            query = query.outerjoin(
                client_asoc_model_class,
                and_(
                    client_asoc_model_class.id == queried_model_class.id,
                    compare_to_time_lower(client_asoc_model_class.time),
                    compare_to_time_upper(client_asoc_model_class.time)))
            query = query.options(contains_eager(client_relationship_obj))
            query = self.query__ordering_by(query)
            query = self.query__limit(query, opt_limit)
            try:
                seen = set()
                for result in query.yield_per(YIELD_PER):
                    if (item_number_limit is not None and
                          processed_items > item_number_limit):
                        raise TooMuchDataError(public_message=(
                            "Too much data requested. "
                            "Try again with more specific search."))
                    event_id = result.id
                    if event_id not in seen:
                        seen.add(event_id)
                        yield result.to_raw_result_dict()
                        per_query_yielded_items += 1
                    processed_items += 1
            except DBAPIError:
                LOGGER.error(
                        'error when trying to perform the query:\n%s',
                        ascii_str(query), exc_info=True)
                raise DataAPIError

            # Update query limit and end
            # function if it is exhausted
            if opt_limit is not None:
                opt_limit -= per_query_yielded_items
                if opt_limit <= 0:
                    break


    def delete_opt_prefixed_params(self, params):
        for key in list(params):
            if key.startswith('opt.'):
                del params[key]


    def pop_time_min_max_until(self, params):
        """
        Pop 'time.min', 'time.max' and 'time.until' from the given param dict.

        Args/kwargs:
            `params` (dict):
                Cleaned query parameters.

        Returns:
            A tuple: (<time min>, <time max>, <time_until>) -- where the
            first element is a datetime.datetime object and each of the
            rest two elements is a datetime.datetime object or None.
        """
        assert params.get('time.min') is not None, (
            'Client queries are expected to always '
            'include the `time.min` parameter')  # see: n6web.RestAPIViewBase.prepare_params()
        # unpacking the values from 1-element lists:
        [time_min] = params.pop('time.min')
        [time_max] = params.pop('time.max', [None])
        [time_until] = params.pop('time.until', [None])
        return time_min, time_max, time_until


    def make_time_cmp_generator(self, time_min, time_max, time_until, day_step):
        """
        Generate pairs of partially applied time comparison functions.

        (The generated functions are meant to be applied to an
        SQLAlchemy objects that represent the `event.time` and
        `client_to_event.time` SQL database columns.)

        Args/kwargs:
            `time_min` (datetime.datetime):
                The value of the client query parameter "time.min".
            `time_max` (datetime.datetime or None):
                The value of the client query parameter "time.max"
                (None if not specified).
            `time_until` (datetime.datetime or None):
                The value of the client query parameter "time.until"
                (None if not specified).
            `day_step` (int or float):
                The length of the time window for a single query -- in
                days.
        """
        step_delta = datetime.timedelta(days=day_step)

        # we use with_flipped_args() here because we want to be able to use
        # functools.partial() specifying the *second* argument (see below...)
        ge = with_flipped_args(operator.ge)
        le = with_flipped_args(operator.le)
        lt = with_flipped_args(operator.lt)

        if time_until is None:
            time_upper = (
                time_max if time_max is not None
                else utcnow() + datetime.timedelta(hours=1))
            time_lower = max(time_min, time_upper - step_delta)
            yield (
                functools.partial(ge, time_lower),  # `time` >= time_lower
                functools.partial(le, time_upper))  # `time` <= time_upper
        else:
            time_upper = None
            time_lower = time_until

        while time_lower > time_min or time_upper is None:
            time_upper = time_lower
            time_lower = max(time_min, time_upper - step_delta)
            yield (
                functools.partial(ge, time_lower),  # `time` >= time_lower
                functools.partial(lt, time_upper))  # `time`  < time_upper


    def pop_client_ids(self, params):
        # Note that N6InsideDataSpec ensures that for the `inside`
        # access zone the 'client' query parameter cannot be specified
        # by users (the client id should be taken from the user's
        # certificate).  So here, for the `inside` access zone,
        # params['client'] is *never* present and self.the_client_id is
        # *always* set to some client identifier.  On the other hand,
        # for the rest of the access zones, params['clients'] *may* be
        # present here and self.the_client_id is *never* set to anything
        # but None.
        client_ids = params.pop('client', None)
        if client_ids is None:
            return (None if self.the_client_id is None
                    else [self.the_client_id])
        else:
            assert self.the_client_id is None
            return client_ids

    def pop_limit(self, params):
        [opt_limit] = params.pop('opt.limit', [None])
        return opt_limit

    def build_query(self, params, client_ids):
        """
        Build an SQLAlchemy query.

        Args/kwargs:
            `params` (dict):
                Cleaned query parameters.
            `client_ids` (list or None):
                List of clients (actually, their ids being strings)
                the queried events should belong to.

        Returns:
            A DBSession.query() object.

        This is a template method that calls the following methods:

        * create_query(),
        * query__param_filtering(),
        * query__access_filtering(),
        * query__client_filtering().
        """
        query = self.create_query()
        #query = self.query__client_join(query)
        query = self.query__param_filtering(query, params)
        ## TODO: reimplement max_days_limit taking into account generating result with yield
        #query = self.query__max_days_limit(query)
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query, client_ids)
        return query

    def create_query(self):
        """Called in the build_query() template method."""
        return DBSession.query(self.queried_model_class)

    ## commented out, as the necessary join is already in
    ## generate_query_results()
    #def query__client_join(self, query):
    #    """Called in the build_query() template method."""
    #    if self.client_relationship is not None:
    #        relationship_obj = getattr(self.queried_model_class,
    #                                   self.client_relationship)
    #        query = query.outerjoin(relationship_obj)
    #        query = query.options(contains_eager(relationship_obj))
    #    return query

    def query__param_filtering(self, query, query_params):
        """Called in the build_query() template method."""
        for key, value in query_params.iteritems():
            query_func = self.key_to_query_func[key]
            filter_term = query_func(key, value)
            query = query.filter(filter_term)
        return query

    ## to be implemented in a different way??
    #def query__max_days_limit(self, query):
    #    """Called in the build_query() template method."""
    #    if self.max_days_old is not None:
    #        dt = datetime.datetime.utcnow() - datetime.timedelta(days=self.max_days_old)
    #        dt = datetime.datetime(dt.year, dt.month, dt.day)
    #        query = query.filter(self.queried_model_class.time >= dt)
    #    return query

    def query__access_filtering(self, query):
        """Called in the build_query() template method."""
        assert self.access_filtering_conditions
        query = query.filter(or_(*self.access_filtering_conditions))
        return query

    def query__client_filtering(self, query, client_ids):
        """Called in the build_query() template method."""
        if client_ids is not None:
            assert client_ids
            client_column = getattr(self.client_asoc_model_class,
                                    self.client_asoc_column)
            if len(client_ids) == 1:
                query = query.filter(client_column == client_ids[0])
            else:
                query = query.filter(client_column.in_(client_ids))
        return query

    def query__ordering_by(self, query):
        """Called in the generate_query_results() method."""
        return query.order_by(self.queried_model_class.time.desc())

    def query__limit(self, query, limit):
        """Called in the build_query() template method."""
        if limit is not None:
            query = query.limit(limit)
        return query


class N6TestDataBackendAPI(N6DataBackendAPI):

    def __init__(self, settings, **kwargs):
        self.max_num_of_events = int(settings['max_num_of_events'])
        self.settings = settings

    def _generate_result_dicts(self, params, data_spec, access_zone_conditions,
                               res_limits, item_number_limit, access_zone,
                               client_id=None):
        opt_limit = 0
        opt_limit_vals = params.get('opt.limit')
        if opt_limit_vals:
            opt_limit = opt_limit_vals[0]
        if 0 < opt_limit < self.max_num_of_events:
            num_of_events = opt_limit
        elif 0 < item_number_limit < self.max_num_of_events:
            num_of_events = item_number_limit
        else:
            num_of_events = self.max_num_of_events
        return RandomEvent.generate_multiple_event_data(num_of_events,
                                                        settings=self.settings,
                                                        access_zone=access_zone,
                                                        client_id=client_id,
                                                        params=params)

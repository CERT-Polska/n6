# Copyright (c) 2013-2025 NASK. All rights reserved.

import base64
import collections
import datetime
import functools
import operator
from collections.abc import (
    Callable,
    Generator,
    Iterator,
    Sequence,
    Set,
)
from contextlib import (
    closing,
    contextmanager,
)
from typing import (
    Any,
    Final,
    Optional,
    TypeVar,
    Union,
)

import sqlalchemy.event
from sqlalchemy import (
    desc,
    distinct,
    engine_from_config,
    func as sqla_func,
    or_,
    and_,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.util import KeyedTuple as FetchedRow

from n6lib.auth_api import ACCESS_ZONES
from n6lib.class_helpers import singleton
from n6lib.common_helpers import (
    PY_NON_ASCII_ESCAPED_WITH_BACKSLASHREPLACE_HANDLER_REGEX,
    ascii_str,
    as_str_with_minimum_esc,
    iter_grouped_by_attr,
    make_exc_ascii_str,
    memoized,
    with_flipped_args,
)
from n6lib.const import CATEGORY_ENUMS
from n6lib.data_spec import N6DataSpec
from n6lib.data_spec.typing_helpers import (
    ParamsDict,
    ResultDict,
)
from n6lib.datetime_helpers import midnight_datetime
from n6lib.db_events import (
    _DBSession,
    Base,
    n6NormalizedData,
    n6ClientToEvent,
    make_raw_result_dict,
)
from n6lib.generate_test_events import RandomEvent
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import (
    AccessZone,
    AccessZoneConditionsDict,
    AuthData,
    ColumnElementTransformer,
    DateTime,
)
from n6lib.url_helpers import (
    PROVISIONAL_URL_SEARCH_KEY_PREFIX,
    normalize_url,
    prepare_norm_brief,
)
from n6lib.context_helpers import (
    NoContextToExitFrom,
    ThreadLocalContextDeposit,
)
from n6sdk.exceptions import DataAPIError

utcnow = datetime.datetime.utcnow  # for easier mocking in unit tests


LOGGER = get_logger(__name__)


#
# Auxiliary Event-DB-with-SQLAlchemy-related tools
#

class EventDatabaseError(DataAPIError):
    """Can be used to indicate a problem with an Event DB operation."""


class _EventDatabaseTransactionContextManager:

    """
    A context manager to wrap Event DB operations in a transaction.

    It provides an additional property, `is_entered` (of type
    `bool`), which tells whether the context manager is currently
    "entered" (after `__enter__()` and before `__exit__()`),
    i.e., being currently engaged in a `with` statement.

    Raises:
        `n6lib.context_helpers.ContextManagerIsNotReentrantError`:
            When trying to start a new transaction and
            another transaction is already in progress in
            the current thread (transactions are thread-local
            and nested transactions are not allowed).

    Only one instance of this context manager is intended to be
    used multiple times, so one global public instance, `transact`,
    is provided.  A usage example:

        from n6lib.data_backend_api import (
            N6DataBackendAPI,
            transact,
        )
        [...]
        thread_local_session = N6DataBackendAPI.get_db_session()
        with transact:
            # A new transaction has begun. (Note: if the
            # session had any active transaction, it has
            # been rolled back!)
            [...]
            for event in new_events:
                thread_local_session.add(event)
            # If no error occurred up to now
            # the transaction will be committed.
        # The transaction has been committed.
        with transact:
            # A new transaction has begun.
            [...]
            thread_local_session.add(another_event)
            raise ValueError  # The transaction will be rolled back!
        # The transaction has been rolled back.

    This context manager can be used regardless of whether it is
    used in a Pyramid application or not -- but it is *required*
    that you use the SQLAlchemy scoped session object obtained by
    calling either `N6DataBackendAPI.configure_db_session()` or
    `N6DataBackendAPI.get_db_session()` (in fact, that object is
    just the `_DBSession` attribute of the `n6lib.db_events` module
    but getting it directly from `n6lib.db_events` is discouraged
    as an unnecessary digging into implementation details).
    """

    def __init__(self):
        self._context_deposit = ThreadLocalContextDeposit(repr_token='transact')

    @property
    def is_entered(self):
        return self._context_deposit.context_count > 0

    def __enter__(self):
        self._context_deposit.on_enter(
            # We just rollback, as the SQLAlchemy session machinery
            # will take care of everything else (in particular, of
            # creating a new transaction).  The resultant "context
            # data" is just None (as `_DBSession.rollback()` returns
            # None).  Note that `.rollback()` called on a fresh
            # session, or directly after a `.commit()` call or
            # another `.rollback()` call, is relatively cheap
            # because, then, no real DB connection is involved.
            outermost_context_factory=_DBSession.rollback,
            context_factory=NotImplemented)  # <- Nesting is not allowed.

    def __exit__(self, exc_type, exc, tb):
        try:
            flush_exc = self._context_deposit.on_exit(
                exc_type, exc, tb,
                outermost_context_finalizer=self._transaction_finalizer,
                context_finalizer=self._never_called)
        except NoContextToExitFrom:
            # When the `force_exit_on_any_remaining_entered_contexts()`
            # helper is applied to the context manager, this exception
            # is expected.
            assert not self.is_entered  # => `.rollback()` should *not* be needed.
            raise
        except:
            # Unexpected exception from `self._transaction_finalizer()`
            # or `self._context_deposit.on_exit()` (rare situation).
            _DBSession.remove()
            raise
        else:
            if flush_exc is not None:
                raise flush_exc
        finally:
            # Let's break traceback-related reference cycles (if any).
            # noinspection PyUnusedLocal
            flush_exc = None

    def _transaction_finalizer(self, _dummy_context, exc_type, _exc, _tb):
        del _exc, _tb
        if exc_type is None:
            # noinspection PyBroadException
            try:
                _DBSession.flush()
            except Exception as flush_exc:
                # An exception from `.flush()` is typically caused
                # by a constraint violation error or a similar one...
                # (Note, however, that as long as our `_DBSession` has
                # the option `autoflush=True`, this `except` block is
                # rather irrelevant.)
                _DBSession.rollback()
                return flush_exc
            else:
                _DBSession.commit()
                return None
        else:
            _DBSession.rollback()
            return None

    def _never_called(*args):
        assert False, 'this code should never be called'


"""See the docstring of the `_EventDatabaseTransactionContextManager` class."""
transact = _EventDatabaseTransactionContextManager()


#
# Actual Event DB's *data backend API* stuff
#

@singleton
class N6DataBackendAPI:

    """
    An API that provides common set of event-database methods.
    """

    DEFAULT_DAY_STEP = 1

    EVENT_DB_CONNECT_CHARSET_DEFAULT = 'utf8mb4'
    EVENT_DB_SQL_MODE = (
        # See: https://mariadb.com/kb/en/library/sql-mode/ (and see also somewhat similar
        # stuff in `n6lib.auth_db.config.SQLAuthDBConfigMixin.constant_session_variables`).
        "'STRICT_TRANS_TABLES"          # <- default restriction for >= MariaDB 10.2.4
        ",ERROR_FOR_DIVISION_BY_ZERO"   # <- default restriction for >= MariaDB 10.2.4
        ",NO_AUTO_CREATE_USER"          # <- default restriction for >= MariaDB 10.1.7
        ",NO_AUTO_VALUE_ON_ZERO"        # <- non-default restriction
        ",NO_ENGINE_SUBSTITUTION"       # <- default restriction for >= MariaDB 10.1.7
        ",NO_ZERO_DATE"                 # <- non-default restriction
        ",NO_ZERO_IN_DATE"              # <- non-default restriction
        "'")

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
        _DBSession.configure(bind=engine)
        Base.metadata.bind = engine
        return _DBSession

    @staticmethod
    def get_db_session():
        """Get the scoped session object."""
        return _DBSession


    def __init__(self, settings):
        """
        Set up the Master API and initialize DB connections.

        Kwargs:
            `settings` (required):
                A dictionary which could be passed to an
                `sqlalchemy.engine_from_config(..., prefix='sqlalchemy.')`
                call (e.g. a Pyramid settings dict).
        """

        # TODO: most of (if not all) the settings used here are a legacy
        #       stuff.  In the future we'll get rid of them and/or
        #       replace them with new `event_db.*` options...
        self.day_step = int(settings.get('day_step', self.DEFAULT_DAY_STEP))
        if 'mysql.api.ssl_key' in settings:
            ssl_args = dict(
                ssl=dict(
                    ca=settings['mysql.api.ssl_cacert'],
                    cert=settings['mysql.api.ssl_cert'],
                    key=settings['mysql.api.ssl_key']))
        else:
            ssl_args = dict()
        connect_args = dict(
            ssl_args,
            charset=settings.get(
                'sqlalchemy_event_db_connect_charset',
                self.EVENT_DB_CONNECT_CHARSET_DEFAULT),
            use_unicode=True,
            binary_prefix=True)
        pool_options = dict(              # (<- TODO later: make these options configurable...)
            pool_pre_ping=True,
            pool_recycle=3600,   # (<- needs to be less than `wait_timeout`; see below...)
            pool_timeout=20,
            pool_size=15,
            max_overflow=12)
        engine = engine_from_config(
            settings,
            'sqlalchemy.',
            isolation_level='REPEATABLE READ',
            connect_args=connect_args,
            **pool_options)
        self._install_session_variables_setter(
            engine,
            wait_timeout="7200",        # (<- TODO later: make these variables configurable...)
            sql_mode=self.EVENT_DB_SQL_MODE,
            time_zone="'+00:00'")
        self.configure_db_session(engine)

    def _install_session_variables_setter(self, engine, **session_variables):
        setter_sql = 'SET ' + ' , '.join(
            'SESSION {} = {}'.format(name, value)
            for name, value in session_variables.items())

        @sqlalchemy.event.listens_for(engine, 'connect')
        def set_session_variables(dbapi_connection, connection_record):
            """
            Execute
            "SET SESSION <var1> = <val1>, SESSION <var2> = <val2>, ..."
            to set the specified variables.

            To be called automatically whenever a new low-level
            connection to the database is established.

            WARNING: for simplicity, the variable names and values are
            inserted "as is", *without* any escaping -- we assume we
            can treat them as *trusted* data.
            """
            with dbapi_connection.cursor() as cursor:
                cursor.execute(setter_sql)

    def get_the_most_frequent_categories(self,
                                         auth_data: AuthData,
                                         access_filtering_conditions: list[ColumnElement],
                                         since: DateTime) -> tuple[str]:
        if not access_filtering_conditions:
            raise AssertionError('filtering conditions not provided')
        query_processor = _DailyEventsCountsQueryProcessor(
            access_filtering_conditions=access_filtering_conditions,
            client_org_ids=[auth_data['org_id']])
        return query_processor.get_the_most_frequent_events_categories(since)

    def get_counts_per_day_per_category(self,
                                        auth_data: AuthData,
                                        access_filtering_conditions: list[ColumnElement],
                                        since: DateTime) -> dict[str, list]:
        if not access_filtering_conditions:
            raise AssertionError('filtering conditions not provided')
        query_processor = _DailyEventsCountsQueryProcessor(
            access_filtering_conditions=access_filtering_conditions,
            client_org_ids=[auth_data['org_id']])
        return query_processor.get_counts_per_day_per_category(since)

    def get_names_ranking_per_category(self,
                                       auth_data: AuthData,
                                       access_filtering_conditions: list[ColumnElement],
                                       since: DateTime,
                                       category: str,
                                       ) -> Optional[dict[str, Optional[dict]]]:
        if not access_filtering_conditions:
            # We are dealing with access rights, so let's be on a safe side.
            raise AssertionError('filtering conditions not provided')
        query_processor = _NamesRankingQueryProcessor(
            access_filtering_conditions=access_filtering_conditions,
            client_org_ids=[auth_data['org_id']])
        return query_processor.get_names_ranking_counts_per_category(since, category)

    def get_counts_per_category(self,
                                auth_data: AuthData,
                                access_filtering_conditions: list[ColumnElement],
                                since: DateTime,
                                ) -> dict[str, int]:
        """
        Obtain numbers of security events in each of the event categories,
        for the specified criteria.

        Args/kwargs:
            `auth_data`:
                An authenticated client's data as a dict:
                {'org_id': <org id>, 'user_id': <user id aka login>}.
            `access_filtering_conditions`:
                A non-empty list of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).
            `since`:
                A datetime.datetime object that specifies the minimum
                *time* value for which events should be considered.

        Returns:
            A dict that maps `str`s identifying all *n6* event
            categories to numbers (`int`) of events found for each
            category.

        Raises:
            EventDatabaseError:
                If something with an underlying database operation goes
                wrong.
        """
        if not access_filtering_conditions:
            # We are dealing with access rights, so let's be on a safe side.
            raise AssertionError('filtering conditions not provided')
        query_processor = _CountsQueryProcessor(
            access_filtering_conditions=access_filtering_conditions,
            client_org_ids=[auth_data['org_id']])
        return query_processor.get_counts_per_category(since)

    def report_inside(self,
                      auth_data: AuthData,
                      params: ParamsDict,
                      data_spec: N6DataSpec,
                      access_zone_conditions: AccessZoneConditionsDict,
                      ) -> Iterator[ResultDict]:
        """
        Obtain the data of security events matching the given request
        parameters, limited to the "inside" access zone (according to
        the per-access-zone defined conditions, typically related to
        the querying client's organization and/or one or more groups of
        organizations it belongs to), with the additional constraint
        that *only* events that occurred *inside* the organization's
        network (given the "client" attribute of events, determined
        earlier by the *n6*'s component called *n6filter*) are reported.

        Args/kwargs:
            `auth_data`:
                An authenticated client's data as a dict:
                {'org_id': <org id>, 'user_id': <user id aka login>}.
            `params`:
                A dictionary of cleaned (appropriately for the "inside"
                access zone -- which means, among other things, that the
                "client" item is not included) and deanonymized request
                parameters (in our parlance -- a *cleaned params dict*).
                An additional expectation: the dictionary should always
                contain the "time.min" item.
            `data_spec`:
                An n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (`str` values) to
                non-empty lists of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).

        Returns:
            An iterator that yields dicts, each containing the data of
            a single event obtained from Event DB (note: in our parlance
            those dicts are *raw result dicts*, that is, *result dicts*
            not yet data-spec-cleaned, nor anonymized). The order of the
            generated dicts is descending -- by the `time` event field.

        When the returned iterator is being consumed, EventDatabaseError
        can be raised if something with an underlying database operation
        goes wrong.
        """
        if 'client' in params:
            raise AssertionError(
                'the `client` parameter is *not* expected for the '
                '"inside" access zone (something wrong with the '
                'parameter cleaning?)')
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           access_zone='inside',
                                           client_org_ids=[auth_data['org_id']])

    def report_threats(self,
                       auth_data: AuthData,  # noqa (not used but accepted for consistency)
                       params: ParamsDict,
                       data_spec: N6DataSpec,
                       access_zone_conditions: AccessZoneConditionsDict,
                       ) -> Iterator[ResultDict]:
        """
        Obtain the data of security events matching the given request
        parameters, limited to the "threats" access zone (according to
        the per-access-zone defined conditions, typically related to
        the querying client's organization and/or one or more groups
        of organizations it belongs to).

        Args/kwargs:
            `auth_data`:
                An authenticated client's data as a dict:
                {'org_id': <org id>, 'user_id': <user id aka login>}.
            `params`:
                A dictionary of cleaned (appropriately for the "threats"
                access zone) and deanonymized request parameters (in
                our parlance -- a *cleaned params dict*). An additional
                expectation: it should always contain the "time.min"
                item.
            `data_spec`:
                An n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (`str` values) to
                non-empty lists of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).

        Returns:
            An iterator that yields dicts, each containing the data of
            a single event obtained from Event DB (note: in our parlance
            those dicts are *raw result dicts*, that is, *result dicts*
            not yet data-spec-cleaned, nor anonymized). The order of the
            generated dicts is descending -- by the `time` event field.

        When the returned iterator is being consumed, EventDatabaseError
        can be raised if something with an underlying database operation
        goes wrong.
        """
        client_org_ids = params.pop('client', None) or None
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           access_zone='threats',
                                           client_org_ids=client_org_ids)

    def search_events(self,
                      auth_data: AuthData,  # noqa (not used but accepted for consistency)
                      params: ParamsDict,
                      data_spec: N6DataSpec,
                      access_zone_conditions: AccessZoneConditionsDict,
                      ) -> Iterator[ResultDict]:
        """
        Obtain the data of security events matching the given request
        parameters, limited to the "search" access zone (according to
        the per-access-zone defined conditions, typically related to
        the querying client's organization and/or one or more groups
        of organizations it belongs to).

        Args/kwargs:
            `auth_data`:
                An authenticated client's data as a dict:
                {'org_id': <org id>, 'user_id': <user id aka login>}.
            `params`:
                A dictionary of cleaned (appropriately for the "search"
                access zone) and deanonymized request parameters (in
                our parlance -- a *cleaned params dict*). An additional
                expectation: it should always contain the "time.min"
                item.
            `data_spec`:
                An n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (`str` values) to
                non-empty lists of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).

        Returns:
            An iterator that yields dicts, each containing the data of
            a single event obtained from Event DB (note: in our parlance
            those dicts are *raw result dicts*, that is, *result dicts*
            not yet data-spec-cleaned, nor anonymized). The order of the
            generated dicts is descending -- by the `time` event field.

        When the returned iterator is being consumed, EventDatabaseError
        can be raised if something with an underlying database operation
        goes wrong.
        """
        client_org_ids = params.pop('client', None) or None
        return self._generate_result_dicts(params,
                                           data_spec,
                                           access_zone_conditions,
                                           access_zone='search',
                                           client_org_ids=client_org_ids)

    def _generate_result_dicts(self,
                               params: ParamsDict,
                               data_spec: N6DataSpec,
                               access_zone_conditions: AccessZoneConditionsDict,
                               access_zone: AccessZone,
                               client_org_ids: Optional[list[str]],
                               ) -> Iterator[ResultDict]:
        """
        Common code for the report_inside/report_threats/search_events methods.

        Args/kwargs:
            `params`:
                A dictionary of cleaned (appropriately for the given
                `access_zone`) and deanonymized request parameters (in
                our parlance -- a *cleaned params dict*), but after
                removing from it the "client" item if it was present
                (note: if its value is needed, it should be given as
                the `client_org_ids` argument instead). Additional
                expectation: the dictionary should always contain
                the "time.min" item.
            `data_spec`:
                An n6lib.data_spec.N6DataSpec instance.
            `access_zone_conditions`:
                A dict that maps access zones (`str` values) to
                non-empty lists of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).
            `access_zone`:
                The requested resource's access zone (a `str`; one of
                those in n6lib.auth_api.ACCESS_ZONES).
            `client_org_ids`:
                A non-empty list of client organization ids (to
                constraint the results to events owned by at least
                one of the specified clients) **or** None (if no such
                constraint is desired).

        Returns:
            An iterator that yields dicts, each containing the data of
            a single event obtained from Event DB (note: in our parlance
            those dicts are *raw result dicts*, that is, *result dicts*
            not yet data-spec-cleaned, nor anonymized). The order of the
            generated dicts is descending -- by the `time` event field.

        When the returned iterator is being consumed, EventDatabaseError
        can be raised if something with an underlying database operation
        goes wrong.
        """
        access_filtering_conditions = self._get_access_filtering_conditions(
            access_zone_conditions,
            access_zone)
        opt_limit = self._pop_opt_limit(params)
        time_constraints = self._pop_time_constraints(params)
        self._delete_opt_prefixed_params(params)
        self._assert_internal_guarantees(params, access_zone, client_org_ids)
        query_processor = _EventsQueryProcessor(
            access_filtering_conditions=access_filtering_conditions,
            client_org_ids=client_org_ids,
            data_spec=data_spec,
            day_step=self.day_step,
            opt_limit=opt_limit,
            time_constraints=time_constraints,
            filtering_params=params)
        return query_processor.generate_query_results()

    def _get_access_filtering_conditions(self,
                                         access_zone_conditions: AccessZoneConditionsDict,
                                         access_zone: AccessZone,
                                         ) -> list[ColumnElement]:
        access_filtering_conditions = access_zone_conditions.get(access_zone)
        if not access_filtering_conditions:
            # We are dealing with access rights, so let's be on a safe side.
            raise AssertionError(
                'filtering conditions for the {!a} access '
                'zone not provided'.format(access_zone))
        return access_filtering_conditions

    def _pop_opt_limit(self,
                       params: ParamsDict,
                       ) -> Optional[int]:
        [opt_limit] = params.pop('opt.limit', [None])
        return opt_limit

    def _pop_time_constraints(self,
                              params: ParamsDict,
                              ) -> tuple[DateTime, Optional[DateTime], Optional[DateTime]]:
        if params.get('time.min') is None:
            raise AssertionError('request parameters are expected to '
                                 'include the `time.min` parameter')
        # unpacking the values from 1-element lists:
        [time_min] = params.pop('time.min')
        [time_max] = params.pop('time.max', [None])
        [time_until] = params.pop('time.until', [None])
        return time_min, time_max, time_until

    def _delete_opt_prefixed_params(self,
                                    params: ParamsDict,
                                    ) -> None:
        for key in list(params):
            if key.startswith('opt.'):
                del params[key]

    def _assert_internal_guarantees(self,
                                    params: ParamsDict,
                                    access_zone: AccessZone,
                                    client_org_ids: Optional[list[str]],
                                    ) -> None:
        # (the conditions asserted below should be already
        # guaranteed by some code in this class)
        assert 'client' not in params
        assert access_zone in ACCESS_ZONES
        if access_zone == 'inside':
            assert (client_org_ids is not None
                    and len(client_org_ids) == 1)
        else:
            assert client_org_ids or client_org_ids is None


class N6TestDataBackendAPI(N6DataBackendAPI):

    def __init__(self, settings):
        self.max_num_of_events = int(settings['max_num_of_events'])
        self.settings = settings

    def _generate_result_dicts(self,
                               params: ParamsDict,
                               data_spec: N6DataSpec,
                               access_zone_conditions: AccessZoneConditionsDict,
                               access_zone: AccessZone,
                               client_org_ids: Optional[list[str]],
                               ) -> Iterator[ResultDict]:
        params, client_id_or_none = self._adapt_to_random_event_interface(access_zone,
                                                                          params,
                                                                          client_org_ids)
        opt_limit = 0
        opt_limit_vals = params.get('opt.limit')
        if opt_limit_vals:
            opt_limit = opt_limit_vals[0]
        if 0 < opt_limit < self.max_num_of_events:
            num_of_events = opt_limit
        else:
            num_of_events = self.max_num_of_events
        return RandomEvent.generate_multiple_event_data(num_of_events,
                                                        settings=self.settings,
                                                        access_zone=access_zone,
                                                        client_id=client_id_or_none,
                                                        params=params)

    def _adapt_to_random_event_interface(self,
                                         access_zone: AccessZone,
                                         params: ParamsDict,
                                         client_org_ids: Optional[list[str]],
                                         ) -> tuple[ParamsDict, Optional[str]]:
        # (the conditions asserted below should be already
        # guaranteed by some code in N6DataBackendAPI)
        assert 'client' not in params
        assert access_zone in ACCESS_ZONES
        if access_zone == 'inside':
            assert (client_org_ids is not None
                    and len(client_org_ids) == 1)
            return params, client_org_ids[0]
        else:
            if client_org_ids:
                params['client'] = client_org_ids
            else:
                assert client_org_ids is None
            return params, None


#
# Implementation details of Event DB's *data backend API* 
#

class _BaseQueryProcessor:

    DB_API_ERROR_MESSAGE_MAX_LENGTH = 200

    queried_model_class = n6NormalizedData
    client_asoc_model_class = n6ClientToEvent
    client_asoc_column = 'client'

    def __init__(self,
                 access_filtering_conditions: list[ColumnElement],
                 client_org_ids: Optional[list[str]]):
        """
        Initialize the query processor.

        Kwargs:
            `access_filtering_conditions`:
                A non-empty list of SQLAlchemy conditions (see:
                `n6lib.auth_api.AuthAPI.get_access_info()`).
            `client_org_ids`:
                A non-empty list of client organization ids (to
                constraint the results to events owned by at least
                one of the specified clients) **or** None (if no such
                constraint is desired).
        """
        assert access_filtering_conditions
        assert client_org_ids or client_org_ids is None
        self._access_filtering_conditions = access_filtering_conditions
        self._client_org_ids = client_org_ids

    def query__access_filtering(self, query: Query) -> Query:
        assert self._access_filtering_conditions
        query = query.filter(or_(*self._access_filtering_conditions))
        return query

    def query__client_filtering(self, query: Query) -> Query:
        client_org_ids = self._client_org_ids
        if client_org_ids is not None:
            assert client_org_ids
            client_column = getattr(self.client_asoc_model_class, self.client_asoc_column)
            query = query.filter(client_column.in_(client_org_ids))
        return query

    @contextmanager
    def handling_db_api_error(self):
        try:
            yield
        except DBAPIError as exc:
            error_summary = self._format_db_api_error_summary(exc)
            LOGGER.error(
                '%s\n- when performing the query:\n%a\n- with params:\n%a',
                error_summary, exc.statement, exc.params)
            raise EventDatabaseError(error_summary)

    def _format_db_api_error_summary(self, exc):
        error_shortened_msg = make_exc_ascii_str(exc)[:self.DB_API_ERROR_MESSAGE_MAX_LENGTH]
        return 'DB API error - {}...'.format(error_shortened_msg.replace('\n', ' '))


class _DailyEventsCountsQueryProcessor(_BaseQueryProcessor):

    def get_counts_per_day_per_category(self, since: DateTime) -> dict[str, list]:
        query = self._build_query_for_counts_per_day_per_category(since)
        with self.handling_db_api_error():
            query_result = query.all()

        day_to_data = {}
        for date, category, count in query_result:
            date = date.strftime('%Y-%m-%d')
            event_data = [category, count]
            if date in day_to_data.keys():
                day_to_data[date].append(event_data)
            else:
                day_to_data[date] = [event_data]
        return day_to_data

    def _build_query_for_counts_per_day_per_category(self, since: DateTime) -> Query:
        event_model = self.queried_model_class
        client_model = self.client_asoc_model_class
        query = _DBSession.query(sqla_func.date(event_model.time).label('events_time'),
                                 event_model.category,
                                 sqla_func.count(distinct(event_model.id)))
        query = query.join(client_model,
                           and_(client_model.id == event_model.id,
                                client_model.time >= midnight_datetime(since)))
        query = query.filter(event_model.time >= midnight_datetime(since))
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query)
        query = query.group_by(sqla_func.date(event_model.time), event_model.category)
        query = query.order_by('events_time')
        return query

    def get_the_most_frequent_events_categories(self, since: DateTime) -> tuple[str]:
        category_to_count = {}
        query = self._build_query_for_the_most_frequent_events_categories(since)
        with self.handling_db_api_error():
            query_result = query.all()
            category_to_count.update(query_result)
        categories = [str(category) for category in category_to_count.keys()][:6]
        if 'other' in categories:
            categories = [str(category) for category in category_to_count.keys()][:7]
            categories.remove('other')
        assert 'other' not in categories
        categories = tuple(categories)
        return categories

    def _build_query_for_the_most_frequent_events_categories(self, since: DateTime) -> Query:
        event_model = self.queried_model_class
        client_model = self.client_asoc_model_class
        query = _DBSession.query(event_model.category,
                                 sqla_func.count(
                                     distinct(event_model.id)).label('categories_counts'))
        query = query.join(client_model,
                           and_(client_model.id == event_model.id,
                                client_model.time >= midnight_datetime(since)))
        query = query.filter(event_model.time >= midnight_datetime(since))
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query)
        query = query.group_by(event_model.category)
        query = query.order_by(desc('categories_counts'))
        return query


class _NamesRankingQueryProcessor(_BaseQueryProcessor):

    def get_names_ranking_counts_per_category(self, since: DateTime, category: str) \
            -> Optional[dict[str, Optional[dict]]]:
        query = self._build_query_for_ranking_per_category(since, category)
        with self.handling_db_api_error():
            names_to_count = dict(query.all())
        ranking = [str(number) for number in range(1, 10 + 1)]
        ranking_to_names: dict[str, Optional[dict]] = dict.fromkeys(ranking, None)
        names_to_count.pop(None, None)
        sorted_names_to_counts = dict(sorted(names_to_count.items(),
                                             key=operator.itemgetter(1),
                                             reverse=True)[:10])
        if sorted_names_to_counts:
            counter = 1
            for name, count in sorted_names_to_counts.items():
                ranking_value = {str(counter): {name: count}}
                ranking_to_names.update(ranking_value)
                counter += 1
            return ranking_to_names
        return None

    def _build_query_for_ranking_per_category(self, since: DateTime, category: str) -> Query:
        event_model = self.queried_model_class
        client_model = self.client_asoc_model_class
        query = _DBSession.query(event_model.name,
                                 sqla_func.count(distinct(event_model.id)).label('names_count'))
        query = query.join(client_model,
                           and_(client_model.id == event_model.id,
                                client_model.time >= midnight_datetime(since)))
        query = query.filter(event_model.time >= midnight_datetime(since))
        query = query.filter(event_model.category == category)
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query)
        query = query.group_by(event_model.name)
        query = query.order_by('names_count')
        return query


class _CountsQueryProcessor(_BaseQueryProcessor):

    def get_counts_per_category(self,
                                since: DateTime,
                                ) -> dict[str, int]:
        category_to_count: dict[str, int] = dict.fromkeys(CATEGORY_ENUMS, 0)
        query = self._build_query_for_counts_per_category(since)
        with self.handling_db_api_error():
            category_count_pairs: list[tuple[str, int]] = query.all()
        category_to_count.update(category_count_pairs)
        self._verify_no_illegal_categories(category_to_count)
        assert category_to_count.keys() == set(CATEGORY_ENUMS)
        return category_to_count

    def _build_query_for_counts_per_category(self,
                                             since: DateTime,
                                             ) -> Query:
        # * Auxiliary assignments:
        func_count = sqla_func.count
        model: Any = self.queried_model_class    # (use `Any` to silence overzealous attr checking)
        cl_model = self.client_asoc_model_class
        # * Actual query building:
        query = _DBSession.query(model.category, func_count(distinct(model.id)))
        query = query.join(
            cl_model,
            and_(cl_model.id == model.id,
                 cl_model.time >= midnight_datetime(since)))
        query = query.filter(model.time >= midnight_datetime(since))
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query)
        query = query.group_by(model.category)
        return query

    def _verify_no_illegal_categories(self,
                                      category_to_count: dict[str, int],
                                      ) -> None:
        illegal_categories = set(category_to_count).difference(CATEGORY_ENUMS)
        if illegal_categories:
            raise AssertionError('illegal categories got from the Event DB: {}'
                                 .format(', '.join(map(ascii, sorted(illegal_categories)))))


class _EventsQueryProcessor(_BaseQueryProcessor):

    YIELD_PER = 100

    queried_column_mapping_attrs = tuple(
        _BaseQueryProcessor.queried_model_class.get_column_mapping_attrs()
    )


    #
    # Initialization stuff

    def __init__(self,
                 data_spec: N6DataSpec,
                 day_step: int,
                 opt_limit: int,
                 time_constraints: tuple[DateTime, Optional[DateTime], Optional[DateTime]],
                 filtering_params: ParamsDict,
                 **kwargs):
        """
        Initialize the query processor.

        Kwargs:

            `data_spec`:
                An n6lib.data_spec.N6DataSpec instance.

            `day_step`:
                The length, in days, of events-`time`-based intervals,
                aka *steps* (aka *time windows*), in which separate
                (partial) queries will be performed.

                Typically, i.e., when this module is used by the *n6*'s
                REST API or Portal API, the value of `day_step` argument
                is taken from the `*.ini` configuration file (and, if
                not specified there, it is set to the value of the
                `N6DataBackendAPI.DEFAULT_DAY_STEP` constant).

                Note: we (the authors of *n6*) have decided to partition
                queries into narrower per-*step* queries for performance
                reasons, based on our real-world experience. You may
                want to adjust the value of `day_step` to your needs,
                preferably based on your own performance measurements.
                If your instance of *n6* does not have to deal with
                large amounts of data in its Event DB, you may even
                want to get rid of that partitioning completely, just
                by setting `day_step` to a sufficiently big value, such
                as 50000 (which represents an interval of ca 137 years).

            `opt_limit`:
                The value of the "opt.limit" request parameter (already
                cleaned).

            `time_constraints`:
                A 3-tuple containing all 'time.*' request parameter
                values (already cleaned), that is:

                (<time min>, <time max>, <time until>)

                -- where:

                * <time min> is the value of the 'time.min' parameter
                  (a datetime.datetime).
                * <time max> is the value of the 'time.max' parameter
                  (a datetime.datetime) or None if not specified.
                * <time until> is the value of the 'time.until' parameter
                  (a datetime.datetime) or None if not specified.

                (Note that <time min> is always a datetime.datetime
                object, whereas each of the rest two items may be a
                datetime.datetime object or None.)

            `filtering_params`:
                A dictionary of cleaned and deanonymized request
                parameters, after removing from it any 'time.*',
                'opt.*' and 'client' items.

            `**rest_kwargs`:
                See: the _BaseQueryProcessor class.
        """
        assert all(map(self._allowed_to_have_query_func,
                       filtering_params))
        super(_EventsQueryProcessor, self).__init__(**kwargs)
        self._key_to_query_func = self._get_key_to_query_func(data_spec)
        self._day_step = day_step
        self._opt_limit = opt_limit
        self._time_constraints = time_constraints
        self._filtering_params = filtering_params
        self._url_normalization_data_cache = {}
        self._query_base = self._build_query_base()


    @classmethod
    @memoized
    def _get_key_to_query_func(cls,
                               data_spec: N6DataSpec,
                               ) -> dict[str, Callable[[str, list], ColumnElement]]:
        key_to_query_func = {}
        model_class = cls.queried_model_class
        assert data_spec.sql_relationship_field_keys == {cls.client_asoc_column}  # {'client'}
        assert not any(map(cls._allowed_to_have_query_func,
                           data_spec.sql_relationship_field_keys))
        for key, field in data_spec.param_field_specs().items():
            if cls._allowed_to_have_query_func(key):
                query_func_name = field.custom_info.get('func', 'key_query')
                query_func = getattr(model_class, query_func_name)
                key_to_query_func[key] = query_func
        return key_to_query_func

    @staticmethod
    def _allowed_to_have_query_func(param_key: str) -> bool:
        return param_key != 'client' and not param_key.startswith(('time.', 'opt.'))


    def _build_query_base(self) -> Query:
        """
        Build the base of all queries.

        Returns:
            An instance of SQLAlchemy ORM's `Query`.

        This is a template method that calls the following methods:

        * create_query(),
        * query__param_filtering(),
        * query__access_filtering() (see: _BaseQueryProcessor),
        * query__client_filtering() (see: _BaseQueryProcessor).
        """
        query = self.create_query()
        query = self.query__param_filtering(query)
        query = self.query__access_filtering(query)
        query = self.query__client_filtering(query)
        return query

    def create_query(self) -> Query:
        """Called in the _build_query_base() template method."""
        return _DBSession.query(*self.queried_column_mapping_attrs)

    def query__param_filtering(self, query: Query) -> Query:
        """Called in the _build_query_base() template method."""
        for key, value in self._filtering_params.items():
            query_func = self._key_to_query_func[key]
            filter_term = query_func(key, value)
            query = query.filter(filter_term)
        return query


    #
    # Actual querying

    def generate_query_results(self) -> Iterator[ResultDict]:
        """
        Generate event data, executing appropriate database query(ies).

        Yields:
            Subsequent dicts, each containing the data of a single
            event obtained from Event DB (note: in our parlance those
            dicts are *raw result dicts*, that is, *result dicts* not
            yet data-spec-cleaned, nor anonymized). The order of the
            generated dicts is descending -- by the `time` event field.

        Raises:
            EventDatabaseError:
                If something with an underlying database operation goes
                wrong.

        Note that exceptions (if any) can be raised *only during
        iterating over (consuming) the resultant iterator*, which does
        not happen during execution of a N6DataBackendAPI's method that
        invokes this method (at that moment the iterator object is
        created, but *not* yet consumed).
        """
        (produce_result_or_none,
         get_produced_results_count,
         enough_results_produced) = self._prepare_result_production_tools()

        rows_generator = self._fetch_rows_from_db(get_produced_results_count)
        with closing(rows_generator):
            for same_time_rows in iter_grouped_by_attr(rows_generator, 'time'):
                for same_id_rows in iter_grouped_by_attr(same_time_rows, 'id', presort=True):
                    result_dict = produce_result_or_none(same_id_rows)
                    if result_dict is not None:
                        yield result_dict
                    if enough_results_produced():
                        assert get_produced_results_count() == self._opt_limit
                        return
        assert (self._opt_limit is None
                or get_produced_results_count() < self._opt_limit)


    def _prepare_result_production_tools(self) -> tuple[
                Callable[[Sequence[FetchedRow]], Optional[ResultDict]],
                Callable[[], int],
                Callable[[], bool]]:

        _opt_limit: Final[int] = self._opt_limit
        _results_counter: int = 0

        def produce_result_or_none(same_id_rows: Sequence[FetchedRow]) -> Optional[ResultDict]:
            nonlocal _results_counter
            result_dict = _make_result_dict(same_id_rows)
            result_dict = _preprocess(result_dict)
            if result_dict is not None:
                _results_counter += 1
                return result_dict
            return None

        def get_produced_results_count() -> int:
            return _results_counter

        def enough_results_produced() -> bool:
            return (_opt_limit is not None
                    and _results_counter >= _opt_limit)

        _make_result_dict: Callable[[Sequence[FetchedRow]], ResultDict] = self._make_result_dict
        _preprocess: Callable[[ResultDict], Optional[ResultDict]] = self._preprocess_result_dict

        return (produce_result_or_none,
                get_produced_results_count,
                enough_results_produced)


    def _fetch_rows_from_db(self,
                            get_produced_results_count: Callable[[], int],
                            ) -> Generator[FetchedRow, None, None]:
        for compare_to_time_lower, compare_to_time_upper in self._time_comparisons_per_step():
            yield from  self._fetch_rows_for_single_step(compare_to_time_lower,
                                                         compare_to_time_upper,
                                                         get_produced_results_count)


    def _time_comparisons_per_step(self) -> Iterator[tuple[ColumnElementTransformer,
                                                           ColumnElementTransformer]]:
        """
        Generate pairs of partially applied time comparison functions.

        Each pair is dedicated to the respective time window (*step*).
        Pairs are ordered descendingly (i.e., from newest to oldest).
        The comparison functions are meant to be applied to the
        SQLAlchemy model class attributes representing the Event DB's
        `event.time` and `client_to_event.time` columns.
        """
        time_min, time_max, time_until = self._time_constraints
        step_delta = datetime.timedelta(days=self._day_step)

        # We use with_flipped_args() here because we want to be able to use
        # functools.partial() leaving off the first argument and specifying
        # the second (see below...).
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


    def _fetch_rows_for_single_step(self,
                                    compare_to_time_lower: ColumnElementTransformer,
                                    compare_to_time_upper: ColumnElementTransformer,
                                    get_produced_results_count: Callable[[], int],
                                    ) -> Generator[FetchedRow, None, None]:

        cur_step_query_base = self._build_query_base_for_single_step(compare_to_time_lower,
                                                                     compare_to_time_upper)
        cur_step_fetched_rows_count = 0
        while True:
            query, query_limit = self._build_actual_query(cur_step_query_base,
                                                          cur_step_fetched_rows_count,
                                                          get_produced_results_count)
            cur_query_fetched_rows_count = 0

            with self.handling_db_api_error(), \
                 self._rows_fetching_iterator(query) as iterator:

                for row in iterator:
                    cur_step_fetched_rows_count += 1
                    cur_query_fetched_rows_count += 1
                    yield row

            if query_limit is None or cur_query_fetched_rows_count < query_limit:
                # The query/queries performed in this step did all they
                # were able to do for us.
                return
            # The query/queries performed in this step haven't completed
            # their job, so let's perform at least one query more (with
            # appropriately adjusted limit and offset -- see the method
            # `_build_actual_query()`).

    def _build_query_base_for_single_step(self,
                                          compare_to_time_lower: ColumnElementTransformer,
                                          compare_to_time_upper: ColumnElementTransformer,
                                          ) -> Query:
        query = self._query_base.filter(and_(
            compare_to_time_lower(self.queried_model_class.time),
            compare_to_time_upper(self.queried_model_class.time)))
        if self._client_org_ids is not None:
            query = query.join(
                self.client_asoc_model_class,
                and_(
                    self.client_asoc_model_class.id == self.queried_model_class.id,
                    compare_to_time_lower(self.client_asoc_model_class.time),
                    compare_to_time_upper(self.client_asoc_model_class.time)))
        query = query.order_by(self.queried_model_class.time.desc())
        return query

    def _build_actual_query(self,
                            cur_step_query_base: Query,
                            cur_step_fetched_rows_count: int,
                            get_produced_results_count: Callable[[], int],
                            ) -> tuple[Query, Optional[int]]:
        if self._opt_limit is not None:
            still_expected = self._opt_limit - get_produced_results_count()
            assert still_expected > 0, '_build_actual_query() called after reaching `opt.limit`?!'
            # Note: whereas often just a single row is transformed into
            # a single result dict, a case when multiple rows make up a
            # single result dict is also perfectly valid -- because of:
            # 1) the JOIN clause we use; 2) the database denormalization
            # we employ, causing that multiple rows can have the same
            # `id`, while varying by `ip` (and maybe also by `asn`/`cc`).
            # In other words, the "relation" between fetched Event DB
            # rows and the result dicts made from those rows by this
            # class is not necessarily a *1-to-1* but quite often (though
            # rather not in a majority of cases) an *n-to-1* (see the
            # helper function `produce_result_or_none()` provided by the
            # method `_prepare_result_production_tools()`).
            #
            # Moreover, to complicate things even more, let's notice
            # that not all created result dicts are finally emitted
            # (see the `_preprocess_result_dict()` method) -- so,
            # actually, the aforementioned relation is rather an
            # *n-to-1-but-sometimes-0*.
            #
            # So, in the following code -- to accommodate those facts
            # in a performance-friendly manner -- the query limit
            # is increased by some "reserve" to avoid a possible
            # obstruction near the end of a *step* (time window),
            # caused by an unnecessarily long series of more and
            # more narrow queries.
            reserve = max(100, still_expected // 4)
            query_limit = still_expected + reserve
            query = (cur_step_query_base
                     .limit(query_limit)
                     .offset(cur_step_fetched_rows_count))
        else:
            query_limit = None
            query = cur_step_query_base
        # Note: this will cause use of `MySQLdb`'s *server-side* cursor.
        query = query.yield_per(self.YIELD_PER)
        return query, query_limit

    @contextmanager
    def _rows_fetching_iterator(self, query: Query):
        iterator: Iterator[FetchedRow] = iter(query)
        try:
            yield iterator
        finally:
            # In the end, in particular when the generator iterator
            # created with `_fetch_rows_for_single_step()` is being
            # closed from the outside (with `close()`), we do our best
            # to ensure that the query's iterator is exhausted, to avoid
            # problems with unconsumed rows from a *server-side* cursor
            # (see: https://docs.sqlalchemy.org/en/14/core/connections.html#using-server-side-cursors-a-k-a-stream-results
            # as well as: https://stackoverflow.com/questions/47287558/how-to-prematurely-finish-mysql-use-result-mysql-fetch-row).
            self._try_to_exhaust_rows_fetching_iterator(iterator, query)

    def _try_to_exhaust_rows_fetching_iterator(self,
                                               iterator: Iterator[FetchedRow],
                                               query: Query,
                                               ) -> None:
        try:
            for _ in iterator:
                pass
        except Exception as exc:
            LOGGER.error(
                'When trying to exhaust a rows-fetching iterator, '
                'an error occurred (%s). The query was: %s',
                make_exc_ascii_str(exc), ascii_str(query),
                exc_info=True)


    def _make_result_dict(self,
                          same_id_rows: Sequence[FetchedRow],
                          ) -> Optional[ResultDict]:
        # Note: here we assume that the only fields that may vary in
        # fetched rows having the same `id` are: `ip`, `asn` and `cc`
        # (because of the database denormalization we employ), but we
        # neglect that because the information they hold is also in the
        # `address` column, already aggregated. (So, actually, the `ip`,
        # `asn` and `cc` columns are important only when it comes to
        # search criteria, *not* to search results...).
        sample_row = same_id_rows[0]
        return make_raw_result_dict(sample_row)


    # *EXPERIMENTAL* (likely to be changed or removed in the future
    # without any warning/deprecation/etc.)
    def _preprocess_result_dict(self,
                                result_dict: ResultDict,
                                ) -> Optional[ResultDict]:
        event_tag = self._get_event_tag_for_logging(result_dict)
        custom = result_dict.get('custom')
        url_data = (custom.pop('url_data', None) if custom is not None
                    else None)
        url = result_dict.get('url')
        if url_data is None:
            if url is not None and url.startswith(PROVISIONAL_URL_SEARCH_KEY_PREFIX):
                LOGGER.error(
                    '`url` (%a) starts with %a but no `url_data`! '
                    '(skipping this result dict)\n%s',
                    url,
                    PROVISIONAL_URL_SEARCH_KEY_PREFIX,
                    event_tag)
                return None
            # normal case: no `url_data` and: "traditional" `url` or no `url`
            return result_dict
        if url is None or not url.startswith(PROVISIONAL_URL_SEARCH_KEY_PREFIX):
            LOGGER.error(
                '`url_data` present (%a) but `url` (%a) does not '
                'start with %a! (skipping this result dict)\n%s',
                url_data,
                url,
                PROVISIONAL_URL_SEARCH_KEY_PREFIX,
                event_tag)
            return None
        if (not isinstance(url_data, dict)
            # specific set of keys is required:
            or (url_data.keys() != {'orig_b64', 'norm_brief'}
                and url_data.keys() != {'url_orig', 'url_norm_opts'})  # <- legacy format
            # original URL should not be empty:
            or (not url_data.get('orig_b64')
                and not url_data.get('url_orig'))):
            LOGGER.error(
                '`url_data` (%a) is not valid! '
                '(skipping this result dict)\n%s',
                url_data,
                event_tag)
            return None

        # case of `url_data`-based matching

        url_orig_b64 = url_data.get('orig_b64')
        if url_orig_b64 is not None:
            url_norm_brief = url_data['norm_brief']
        else:
            # dealing with legacy format (concerning older data stored in db)
            url_orig_b64 = url_data['url_orig']
            _legacy_url_norm_opts = url_data['url_norm_opts']
            if _legacy_url_norm_opts != {'transcode1st': True, 'epslash': True, 'rmzone': True}:
                raise ValueError(f'unexpected {_legacy_url_norm_opts=!a}')
            url_norm_brief = prepare_norm_brief(
                unicode_str=True,
                merge_surrogate_pairs=True,
                empty_path_slash=True,
                remove_ipv6_zone=True)

        assert isinstance(url_orig_b64, str)
        assert isinstance(url_norm_brief, str)

        url_norm_cache = self._url_normalization_data_cache
        url_norm_cache_item = url_norm_cache.get(url_norm_brief)
        if url_norm_cache_item is not None:
            normalizer, param_urls_norm = url_norm_cache_item
        else:
            normalizer = functools.partial(normalize_url, norm_brief=url_norm_brief)
            param_urls_bin: Optional[list[bytes]] = self._filtering_params.get('url.b64')
            if param_urls_bin is not None:
                call_silencing_decode_err = self._call_silencing_decode_err
                maybe_urls = (call_silencing_decode_err(normalizer, url) for url in param_urls_bin)
                param_urls_norm = frozenset(url for url in maybe_urls
                                            if url is not None)
            else:
                param_urls_norm = None
            url_norm_cache[url_norm_brief] = normalizer, param_urls_norm

        NormalizedURL = Union[str, bytes]  # noqa
        normalizer: Callable[[bytes], NormalizedURL]
        param_urls_norm: Optional[Set[NormalizedURL]]

        url_orig_bin: bytes = base64.urlsafe_b64decode(url_orig_b64)
        url_normalized: NormalizedURL = normalizer(url_orig_bin)

        if param_urls_norm is not None and url_normalized not in param_urls_norm:
            # application-level filtering
            return None

        result_dict['url'] = (
            url_normalized if isinstance(url_normalized, str)
            else as_str_with_minimum_esc(url_normalized))
        ## TODO later?
        # orig_was_unicode = 'u' in url_norm_brief  # ('u' corresponds to `unicode_str=True`)
        # if orig_was_unicode:
        #     url_orig = url_orig_bin.decode('utf-8', 'surrogatepass')
        #     assert isinstance(url_orig, str)
        # else:
        #     url_orig = url_orig_bin
        #     assert isinstance(url_orig, bytes)
        #
        # result_dict['url'] = as_str_with_minimum_esc(url_normalized)
        # result_dict['url_orig_ascii'] = ascii(url_orig)
        # result_dict['url_orig_b64'] = url_orig_b64

        return result_dict

    _NormalizedURL = TypeVar('_NormalizedURL', bytes, str)

    @staticmethod
    def _call_silencing_decode_err(normalizer: Callable[[bytes], _NormalizedURL],
                                   url: bytes,
                                   ) -> Optional[_NormalizedURL]:
        try:
            return normalizer(url)
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _get_event_tag_for_logging(result_dict: ResultDict) -> str:
        try:
            return (
                '(@event whose id is {}, time is {}, modified is {})'.format(
                    result_dict.get('id', 'not set'),
                    result_dict.get('time', 'not set'),
                    result_dict.get('modified', 'not set')))
        except (AttributeError, ValueError, TypeError):  # a bit of paranoia :)
            return '(@unknown event)'

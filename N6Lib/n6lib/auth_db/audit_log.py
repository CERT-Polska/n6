# Copyright (c) 2019-2024 NASK. All rights reserved.

import contextlib
import datetime
import json
import random
import sys
import weakref

from sqlalchemy import (
    event,
    text as sqla_text,
)
from sqlalchemy.engine import (
    Connection,
    Engine,
)
from sqlalchemy.exc import DatabaseError
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.orm.attributes import History
from sqlalchemy.orm.interfaces import MapperProperty
from sqlalchemy.orm.session import (
    Session,
    SessionTransaction,
)
from sqlalchemy.orm.state import (
    AttributeState,
    InstanceState,
)
from sqlalchemy.schema import Column
from typing import (
    Any,
    Iterable,
    Iterator,
    Tuple,
    Union,
)

from n6lib.auth_db.models import Base
from n6lib.common_helpers import (
    DictWithSomeHooks,
    dump_condensed_debug_msg,
    make_condensed_debug_msg,
    make_exc_ascii_str,
    make_hex_id,
)
from n6lib.const import (
    HOSTNAME,
    SCRIPT_BASENAME,
)
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import (
    Jsonable,
    JsonableDict,
    String,
)


LOGGER = get_logger(__name__)


class AuditLog:

    """
    Trace and log changes -- insertions, updates and deletions -- that
    are applied to the content of Auth DB.

    Constructor kwargs:

        `session_factory` (required):
            An argumentless callable that, whenever called, produces an
            instance of an `sqlalchemy.orm.session.Session` subclass
            which is specific to this particular `session_factory`
            object (i.e., a produced instance is not just an instance
            of the `sqlalchemy.orm.session.Session` class itself). The
            callable must be the same object that produces real sessions
            used to make changes in the Auth DB that are to be traced
            and logged. (Typically, the callable is an instance of
            `sqlalchemy.orm.session.sessionmaker` or
            `sqlalchemy.orm.scoped_session`.) An additional requirement
            is that all produced sessions need to be bound to *the same
            engine*, being an instance of `sqlalchemy.engine.Engine`,
            and *only* to it. (Generally, the consequences of failing to
            meet those requirements are undefined -- exceptions and/or
            incorrect behaviors are likely...)

        `external_meta_items_getter` (required):
            An argumentless callable that, when called, returns a
            JSON-serializable dict (or an equivalent iterable of
            key-value pairs) whose items will be added to the `meta`
            subdict of emitted Audit Log entries. Those items should,
            in particular, carry information identifying the user,
            component or client that (in the context of a particular
            session/HTTP request/etc.) ordered or triggered the
            (currently being logged) changes in the Auth DB.

        `logger` (optional):
            If given, it should specify (by name or by instance) the
            logger to be used to emit Audit Log entries (they will be
            emitted using the logger's `info()` method). If not given,
            the default logger, specified by the `DEFAULT_LOGGER_NAME`
            attribute of the `AuditLog` class, will be used.

    Some notes:

    * A Database operation is logged only if it has been successfully
      committed.

    * The **only** supported database operations are ORM-based inserts,
      updates and deletes of singular objects (records). Data modifying
      *bulk* operations are **not** supported, so they should **never**
      be performed on the Auth DB. In particular, `<query>.update(...)`
      and `<query>.delete(...)` are explicitly forbidden: they cause
      `RuntimeError`. Other *bulk* operations -- such as `<session>.
      bulk_save_objects(...)`, `<session>.insert_mappings(...)` or
      `<session>.update_mappings(...)` -- also should **never** be
      performed, even if they do not cause explicit errors.

    * Each log entry is a JSON-formatted single-line string whose
      content (when deserialized with `json.loads()`) is a dictionary
      -- such as, for example:

      ```
      {
          'changed_attrs' {
              'actual_name': 'Foo Bar Example Spam',
              'full_access': True,
              'full_access.old': False,
              'inside_subsources: [
                  {
                      'pk': {'id': 123},
                      'py_repr': "<Subsource: id=123, label='foo', source_id='some.src'>",
                      'table': 'subsource',
                  },
                  {
                      'pk': {'id': 456},
                      'py_repr': "<Subsource: id=456, label='bar', source_id='another.source'>",
                      'table': 'subsource',
                  },
              ],
              'inside_subsources.old: [],
              'threats_subsources: [],
              'threats_subsources.old: [
                  {
                      'pk': {'id': 123},
                      'py_repr': "<Subsource: id=123, label='foo', source_id='some.src'>",
                      'table': 'subsource',
                  },
              ],
              'org_id': 'org.example.info',
              'org_id.old': 'spam.example.com',
          },
          'meta': {
              'commit_tag': '2024-01-04T17:50:03.000123Z#9b40092c8511',
              'db_url': 'mysql+mysqldb://someuser:***@somehost/somedb',
              'n6_hostname': 'foo.bar',
              'n6_module: 'n6adminpanel.app',
              'n6_script_basename': 'n6some_example_script',
              'request_environ_remote_addr': '10.20.30.40',
              'request_org_id': 'example.com',
              'request_user_id': 'who@example.com',
          },
          'operation': 'update',
          'pk': {'org_id': 'org.example.info'},
          'py_repr': "<Org org_id='org.example.info'>",
          'table': 'org',
      }
      ```

    Additionally, successful Auth DB transaction commits traced by Audit
    Log are also, transiently, "registered" in a dedicated Auth DB table:
    `recent_write_op_commit` (see: `.models.RecentWriteOpCommit`). That
    table has two columns: `id` (auto-incremented positive integer) and
    `made_at` (UTC date+time with microsecond resolution).

    Note that `recent_write_op_commit` records:

    * may be automatically deleted after they become 24 hours old (with
      the exception that at least one record -- the newest one -- will
      always be kept until a newer record is added);

    * are inserted/deleted just by the Audit Log's internal machinery --
      and such changes are, themselves, exempted from being traced and
      logged by that machinery.
    """

    #
    # Public interface

    DEFAULT_LOGGER_NAME = 'AUTH_DB_AUDIT_LOG'

    def __init__(self,
                 session_factory,
                 external_meta_items_getter,
                 logger=None):
        self._logger = self._get_logger_obj(logger)
        (self._bind,
         self._relevant_session_type) = self._get_bind_and_relevant_session_type(session_factory)
        self._external_meta_items_getter = external_meta_items_getter
        self._register_event_handlers()

    #
    # Internal stuff

    # * Methods related to initialization:

    def _get_logger_obj(self, logger):
        return (get_logger(self.DEFAULT_LOGGER_NAME) if logger is None
                else (get_logger(logger) if isinstance(logger, str)
                      else logger))

    def _get_bind_and_relevant_session_type(self, session_factory):
        example_session = session_factory()
        bind = example_session.get_bind()
        detected_session_type = type(example_session)
        if isinstance(session_factory, scoped_session):
            # Because we just obtained a session object by calling a
            # `scoped_session` factory, now we need to ensure that the
            # obtained session will not stay as the active session in
            # the current scope (thread), so that the first session
            # object obtained in the same scope (thread) by application
            # code will be a *new* session (and, thanks to that, all
            # appropriate event handlers will be then properly called).
            session_factory.remove()
        if detected_session_type is Session or not issubclass(detected_session_type, Session):
            raise TypeError(
                '`session_factory` needs to be an object that, when '
                'called, returns a session object whose type is *not* '
                '`sqlalchemy.orm.session.Session` but *is* a (direct '
                'or indirect) subclass of it. Note: the Audit Log\'s '
                'machinery assumes that: 1) that subclass is specific '
                'to this particular `session_factory` object; 2) the '
                'object is *the one* that is really used to produce '
                'sessions which are used to modify the content of the '
                'Auth DB. We insist on that because then such sessions '
                'can be easily distinguished from any other sessions; '
                'so that, when it comes to event handling, *only* '
                'events from sessions that have been made by "our" '
                'factory are considered by the Audit Log machinery. '
                '(Typically, `session_factory` is an instance of '
                '`sqlalchemy.orm.session.sessionmaker` or of '
                '`sqlalchemy.orm.scoped_session`; note that such an '
                'instance, when called, produces a session whose type '
                'is the `Session` subclass specific to that instance.) '
                'TL;DR: don\'t know what `session_factory` should be? '
                'Use the same instance of `sessionmaker` (or of '
                '`scoped_session`) that produces sessions used to make '
                'changes in the Auth DB that you want to be logged by '
                'the Audit Log machinery.')
        if not isinstance(bind, Engine):
            raise TypeError(
                f"Wrong type of `session.get_bind()`'s result: {bind!a}! "
                f'Details: `session_factory` needs to be an object that, '
                f'when called, returns a session object whose method '
                f'`get_bind()` returns a `sqlalchemy.engine.Engine` '
                f'instance.')
        return bind, detected_session_type

    def _register_event_handlers(self):
        session_type = self._relevant_session_type
        event.listen(session_type, 'after_transaction_create', self._after_transaction_create)
        event.listen(self._bind, 'checkout', self._when_getting_connection_from_pool)
        event.listen(session_type, 'before_flush', self._before_flush)
        event.listen(Base, 'after_insert', self._after_insert, propagate=True)
        event.listen(Base, 'after_update', self._after_update, propagate=True)
        event.listen(Base, 'after_delete', self._after_delete, propagate=True)
        event.listen(self._bind, 'commit', self._just_before_commit)
        event.listen(session_type, 'after_commit', self._after_commit)
        event.listen(self._bind, 'checkin', self._when_returning_connection_to_pool)
        event.listen(session_type, 'after_transaction_end', self._after_transaction_end)
        self._register_event_handlers_for_unsupported_operations()

    def _register_event_handlers_for_unsupported_operations(self):
        # Let's ensure that the *bulk delete* and *bulk update*
        # operations -- which cannot be easily tracked, so should not
        # be used at all with the Auth DB -- will not pass unnoticed,
        # but will cause an explicit error.
        session_type = self._relevant_session_type
        event.listen(session_type, 'after_bulk_delete', self._after_bulk_delete)
        event.listen(session_type, 'after_bulk_update', self._after_bulk_update)
        # Let's ensure that the two-phase commit mechanism, which is
        # *not* supposed to be used (at least for now), will not pass
        # unnoticed if actually *is* used, but will cause an explicit
        # error (so that we'll know about the need of code adjustments).
        event.listen(self._bind, 'commit_twophase', self._just_before_commit_twophase)

    # * Handling SQLAlchemy Core/ORM events:

    def _after_transaction_create(self, session, transaction):
        assert isinstance(session, self._relevant_session_type)
        self._verify_and_get_session_bind(session)
        self._set_empty_entry_builders_list_on(transaction)
        if self._does_represent_actual_db_transaction(transaction):
            # Let's do this cleanup to be sure we do not have attached to the
            # session any remnants of earlier attempts to record write ops...
            self._discard_request_to_record_write_op_commit(session)

    def _when_getting_connection_from_pool(self, _dbapi_connection, connection_record, *_):
        # Let's do this cleanup to be sure we do not have attached to the
        # connection any remnants of earlier attempts to record write ops...
        # Note: `connection_record` (a `sqlalchemy.pool._ConnectionRecord`)
        # keeps *the same* `info` dict as `info` of the `Connection` that
        # will be related to it.
        self._discard_request_to_record_write_op_commit(connection_record)

    def _before_flush(self, session, _flush_context, _instances):
        assert isinstance(session, self._relevant_session_type)
        # Note: we are *not* 100% sure whether it is OK to trigger
        # SQLAlchemy's attribute loaders at the later stage -- within
        # an `after_{insert,update,delete}` event handler; whereas it
        # is clear that that's OK here (within the `before_flush` event
        # handler). So, just to be on a safe side, let's do it here --
        # so that, at that later stage, all needed attributes/history
        # stuff will have already been cached.
        self._perform_attr_preloading_on_inserted(inserted_model_instances=session.new)
        self._perform_attr_preloading_on_updated(updated_model_instances=session.dirty)
        self._perform_attr_preloading_on_deleted(deleted_model_instances=session.deleted)

    def _after_insert(self, mapper, _conn, model_instance):
        self._after_write_operation(mapper, model_instance, self._prepare_entry_builder_for_insert)

    def _after_update(self, mapper, _conn, model_instance):
        self._after_write_operation(mapper, model_instance, self._prepare_entry_builder_for_update)

    def _after_delete(self, mapper, _conn, model_instance):
        self._after_write_operation(mapper, model_instance, self._prepare_entry_builder_for_delete)

    def _after_write_operation(self, mapper, model_instance, prepare_entry_builder):
        assert (isinstance(mapper, Mapper) and
                isinstance(model_instance, Base))
        session = self._get_session_from_model_instance(model_instance)
        if isinstance(session, self._relevant_session_type):
            model_instance_wrapper = self._wrap_model_instance(mapper, model_instance)
            builder = prepare_entry_builder(model_instance_wrapper)
            self._store_entry_builder_in_current_real_transaction(session, builder)
            self._request_to_record_write_op_commit(session)

    def _just_before_commit(self, conn):
        if self._receive_request_to_record_write_op_commit(conn):
            self._record_write_op_commit(conn)

    def _after_commit(self, session):
        assert isinstance(session, self._relevant_session_type)
        with self._reporting_any_exception_as_critical_after_commit():
            transaction = self._get_current_transaction(session)
            if self._does_represent_actual_db_transaction(transaction):
                self._build_and_emit_log_entries(session, transaction)
                return
        assert self._does_represent_nested_db_savepoint(transaction), (
            'strange: has the `after_commit` event been triggered '
            'for a transaction that is *neither* the outermost one '
            '*nor* a nested savepoint one? (this should not happen!)')
        self._move_stored_entry_builders_to_nearest_real_ancestor_transaction(transaction)

    def _when_returning_connection_to_pool(self, _dbapi_connection, connection_record):
        # Note: `connection_record` (a `sqlalchemy.pool._ConnectionRecord`)
        # keeps *the same* `info` dict as `info` of the `Connection` that
        # was related to it.
        self._discard_request_to_record_write_op_commit(connection_record)

    def _after_transaction_end(self, session, transaction):
        assert isinstance(session, self._relevant_session_type)
        try:
            if self._does_represent_actual_db_transaction(transaction):
                self._discard_request_to_record_write_op_commit(session)
                self._maybe_delete_not_so_recent_write_op_commit_records(session)
        finally:
            # This cleanup part is not strictly necessary --
            # but let's be tidy. :-)
            self._remove_entry_builders_list_from(transaction)

    def _after_bulk_delete(self, delete_context):
        assert isinstance(delete_context.session, self._relevant_session_type)
        raise RuntimeError(f'bulk deletes are not supported by {self!a}')

    def _after_bulk_update(self, update_context):
        assert isinstance(update_context.session, self._relevant_session_type)
        raise RuntimeError(f'bulk updates are not supported by {self!a}')

    def _just_before_commit_twophase(self, *_):
        raise NotImplementedError(f'`commit_twophase` is not (yet?) supported by {self!a}')

    # * Preloading values/histories of model instance attributes:

    def _perform_attr_preloading_on_inserted(self, inserted_model_instances):
        for model_instance in inserted_model_instances:
            model_instance_wrapper = _ModelInstanceWrapper(model_instance)
            model_instance_wrapper.touch_all_own_attrs_and_identifying_stuff_of_related_instances()

    def _perform_attr_preloading_on_updated(self, updated_model_instances):
        for model_instance in updated_model_instances:
            model_instance_wrapper = _ModelInstanceWrapper(model_instance)
            model_instance_wrapper.touch_all_own_attrs_and_identifying_stuff_of_related_instances()
            model_instance_wrapper.ensure_all_own_attr_histories_are_loaded()

    def _perform_attr_preloading_on_deleted(self, deleted_model_instances):
        for model_instance in deleted_model_instances:
            model_instance_wrapper = _ModelInstanceWrapper(model_instance)
            model_instance_wrapper.touch_own_identifying_stuff()

    # * Building and emitting log entries:

    @staticmethod
    def _wrap_model_instance(mapper, model_instance):
        model_instance_wrapper = _ModelInstanceWrapper(model_instance)
        if not model_instance_wrapper.is_mapper_same_as(mapper):
            raise NotImplementedError(
                'The given mapper object {!a} is not the mapper of the '
                'model instance {!a}. Do you use some advanced or hackish '
                'techniques that could cause so? Then you need to adjust '
                'the implementation appropriately... But do we really need '
                'that?! Let\'s keep things simple!'.format(
                    mapper,
                    model_instance))
        return model_instance_wrapper

    @staticmethod
    def _prepare_entry_builder_for_insert(model_instance_wrapper):
        builder = _AuditLogEntryBuilder(model_instance_wrapper.get_identifying_data_dict(),
                                        operation='insert')
        builder.update_subdict('attrs', model_instance_wrapper.iter_nonvoid_attrs())
        return builder

    @staticmethod
    def _prepare_entry_builder_for_update(model_instance_wrapper):
        builder = _AuditLogEntryBuilder(model_instance_wrapper.get_identifying_data_dict(),
                                        operation='update')
        builder.update_subdict('changed_attrs', model_instance_wrapper.iter_changed_attrs())
        return builder

    @staticmethod
    def _prepare_entry_builder_for_delete(model_instance_wrapper):
        builder = _AuditLogEntryBuilder(model_instance_wrapper.get_identifying_data_dict(),
                                        operation='delete')
        return builder

    @classmethod
    @contextlib.contextmanager
    def _reporting_any_exception_as_critical_after_commit(cls):
        try:
            yield
        except:
            cls._report_critical_exception_after_commit()
            raise

    @staticmethod
    def _report_critical_exception_after_commit():
        debug_msg = None
        try:
            exc_info = sys.exc_info()
            debug_msg = make_condensed_debug_msg(exc_info)
            LOGGER.critical(
                'Most probably, some Auth DB changes *have been* committed '
                '*but* the corresponding Audit Log entries have *not* been '
                'emitted (!!!) because of an exception. Debug message: %s.',
                debug_msg,
                exc_info=exc_info)
        except:
            dump_condensed_debug_msg('EXCEPTION WHEN TRYING TO LOG AUDIT LOG CRITICAL EXCEPTION!')
            raise
        finally:
            # noinspection PyUnusedLocal
            exc_info = None  # (<- breaking traceback-related reference cycle, if any)
            dump_condensed_debug_msg('AUDIT LOG CRITICAL EXCEPTION!',
                                     debug_msg=(debug_msg or '[UNKNOWN EXCEPTION]'))

    def _build_and_emit_log_entries(self, session, transaction):
        assert self._does_represent_actual_db_transaction(transaction)
        for entry in self._generate_entries_from_stored_builders(session, transaction):
            self._logger.info(entry)

    def _generate_entries_from_stored_builders(self, session, transaction):
        meta_items = self._make_meta_items(session)
        for builder in self._get_entry_builders_list_from(transaction):
            builder.update_subdict('meta', meta_items)
            entry = builder()
            yield entry

    def _make_meta_items(self, session):
        return dict(self._external_meta_items_getter(),
                    commit_tag=self._make_commit_tag(),
                    db_url=self._get_db_url_from_session(session),
                    n6_hostname=HOSTNAME,
                    n6_script_basename=SCRIPT_BASENAME)

    def _make_commit_tag(self):
        return '{utc_datetime:%Y-%m-%dT%H:%M:%S.%fZ}#{random_id}'.format(
            utc_datetime=datetime.datetime.utcnow(),
            random_id=make_hex_id(length=12))

    def _get_db_url_from_session(self, session):
        bind = self._verify_and_get_session_bind(session)
        return bind.url.__to_string__(hide_password=True)

    # * Storing, retrieving, moving and removing entry builders:

    _ENTRY_BUILDERS_ATTR_NAME = '_n6_audit_log_entry_builders'

    def _set_empty_entry_builders_list_on(self, transaction):
        assert isinstance(transaction, SessionTransaction)
        assert getattr(transaction, self._ENTRY_BUILDERS_ATTR_NAME, None) is None
        setattr(transaction, self._ENTRY_BUILDERS_ATTR_NAME, [])

    def _get_entry_builders_list_from(self, transaction):
        assert isinstance(transaction, SessionTransaction)
        entry_builders = getattr(transaction, self._ENTRY_BUILDERS_ATTR_NAME, None)
        assert isinstance(entry_builders, list), (
            'the given transaction object does *not* have the {!a} '
            'attribute set to a list'.format(self._ENTRY_BUILDERS_ATTR_NAME))
        if entry_builders:
            assert self._is_real_transaction(transaction)
        return entry_builders

    def _remove_entry_builders_list_from(self, transaction):
        assert isinstance(transaction, SessionTransaction)
        assert isinstance(getattr(transaction, self._ENTRY_BUILDERS_ATTR_NAME, None), list)
        delattr(transaction, self._ENTRY_BUILDERS_ATTR_NAME)

    def _store_entry_builder_in_current_real_transaction(self, session, builder):
        current_transaction = self._get_current_transaction(session)
        current_real_transaction = self._search_for_nearest_real_transaction(current_transaction)
        entry_builders = self._get_entry_builders_list_from(current_real_transaction)
        entry_builders.append(builder)

    def _move_stored_entry_builders_to_nearest_real_ancestor_transaction(self, source_transaction):
        target_transaction = self._search_for_nearest_real_transaction(source_transaction.parent)
        self._move_entry_builders(source_transaction, target_transaction)

    def _move_entry_builders(self, source_transaction, target_transaction):
        assert source_transaction is not target_transaction
        source_list = self._get_entry_builders_list_from(source_transaction)
        target_list = self._get_entry_builders_list_from(target_transaction)
        target_list.extend(source_list)
        del source_list[:]

    # * Making and consuming requests to insert `recent_write_op_commit` records:

    _REC_REQUEST_INFO_KEY = f'{__name__}:request_to_record_write_op_commit'

    class _RecRequest:

        def __init__(self, conn: Connection):
            self._conn_getter = weakref.ref(conn)

        @property
        def conn(self) -> Union[Connection, None]:
            return self._conn_getter()

        def consume(self, obj) -> bool:
            try:
                # Is `obj` the `Connection` instance we were initialized with?
                # (Only then it can make sense to fulfill the request...)
                return (obj is self.conn is not None)
            finally:
                # Note: this method, once called (and returned `True` or
                # `False`), will return `False` every time thereafter.
                self._conn_getter = lambda: None

    def _request_to_record_write_op_commit(self, session: Session) -> None:
        conn: Connection = session.connection()
        key = self._REC_REQUEST_INFO_KEY
        req = session.info.get(key)
        if req is None:
            conn.info[key] = req = self._RecRequest(conn)
            session.info[key] = req
        assert isinstance(req, self._RecRequest)
        assert req is conn.info.get(key) is session.info.get(key)
        assert req.conn is conn

    def _receive_request_to_record_write_op_commit(self, obj) -> bool:
        assert hasattr(obj, 'info') and isinstance(obj.info, dict)
        key = self._REC_REQUEST_INFO_KEY
        req = obj.info.pop(key, None)
        if req is not None:
            assert isinstance(req, self._RecRequest)
            return req.consume(obj)
        return False

    def _discard_request_to_record_write_op_commit(self, obj) -> None:
        self._receive_request_to_record_write_op_commit(obj)

    # * Inserting and deleting `recent_write_op_commit` records into/from Auth DB:

    def _record_write_op_commit(self, conn: Connection) -> None:
        conn.execute('INSERT INTO recent_write_op_commit SET made_at = DEFAULT')

    def _maybe_delete_not_so_recent_write_op_commit_records(self, session: Session) -> None:
        if random.randrange(100) > 0:
            # In 99% of cases: refrain from acting (as it is *not*
            # necessary to attempt this kind of cleanup each time).
            # Let's save our resources! :)
            return
        bind = self._verify_and_get_session_bind(session)
        try:
            with bind.connect() as conn, conn.begin():
                [[time_of_newest_rec]] = conn.execute(
                    'SELECT made_at FROM recent_write_op_commit '
                    'ORDER BY id DESC LIMIT 1')
                delete_stmt = sqla_text(
                    'DELETE FROM recent_write_op_commit WHERE '
                    'made_at < '
                    # The following `IF(...)` expression evaluates to what
                    # is earlier:
                    # * *either* the given timestamp of the newest record,
                    # * *or* the time exactly 24 hours ago.
                    'IF('
                    '  (@time_of_newest_rec:= :time_of_newest_rec) '
                    '  < (@time_24h_ago:= (NOW(6) - INTERVAL 1 DAY)), '
                    '  @time_of_newest_rec, '
                    '  @time_24h_ago)')
                conn.execute(delete_stmt, time_of_newest_rec=time_of_newest_rec)
        except DatabaseError as exc:
            # Note: here we do *not* re-raise the exception or log a
            # warning/error, because it is *not a problem* if this
            # cleanup sometimes cannot be done (e.g., because of a
            # database-level deadlock or what...).
            LOGGER.debug(
                'Stale `recent_write_op_commit` records could not '
                'be deleted (because of %s)... Maybe next time?',
                make_exc_ascii_str(exc))

    # * Dealing with session and transaction objects:

    def _get_session_from_model_instance(self, model_instance):
        instance_state = inspect(model_instance)
        assert isinstance(instance_state, InstanceState)
        return instance_state.session

    def _get_current_transaction(self, session):
        current_transaction = session.transaction
        assert isinstance(current_transaction, SessionTransaction)
        return current_transaction

    def _is_real_transaction(self, transaction):
        return (
            self._does_represent_nested_db_savepoint(transaction) or
            self._does_represent_actual_db_transaction(transaction))

    def _does_represent_nested_db_savepoint(self, transaction):
        return transaction.nested

    def _does_represent_actual_db_transaction(self, transaction):
        # In other words: "Is it -- in the stack of
        # transaction objects -- the outermost one?".
        return transaction.parent is None

    def _search_for_nearest_real_transaction(self, transaction):
        # Let's walk through the stack of `SessionTransaction` objects
        # (towards the outermost one, starting with the given one) to
        # find the nearest "real" transaction object, that is, the
        # nearest one that *either* represents a nested savepoint *or*
        # is just the outermost one (which means it represents the
        # actual database transaction). We need to skip any other
        # transaction objects in the stack ("subtransactions" in the
        # SQLAlchemy's parlance), i.e., such `SessionTransaction`
        # objects that are *not* of either of those two kinds (and,
        # therefore, do not represent any real database-side
        # constructs).
        while True:
            assert isinstance(transaction, SessionTransaction)
            if self._is_real_transaction(transaction):
                return transaction
            assert self._get_entry_builders_list_from(transaction) == []
            transaction = transaction.parent

    def _verify_and_get_session_bind(self, session):
        bind = session.get_bind()
        if bind is not self._bind:
            raise RuntimeError(
                f'{bind=!a} from session.get_bind() is not '
                f'{self._bind=!a}')
        assert isinstance(bind, Engine)
        return bind


class _ModelInstanceWrapper:

    """
    A wrapper around an Auth DB ORM model instance (i.e., over an
    instance of a concrete subclass of the `n6lib.auth_db.models.Base`
    class). The purpose is to hide SQLAlchemy-specific stuff and
    provide callers with plain JSON-serializable data.
    """

    #
    # Public interface (to be used by methods of `AuditLog`)

    def __init__(self, model_instance):
        if not isinstance(model_instance, Base):
            raise TypeError('{!a} is not an instance of {!a}'.format(model_instance, Base))
        self._model_instance = model_instance
        self._mapper = model_instance.__class__.__mapper__
        assert isinstance(self._mapper, Mapper)

    def is_mapper_same_as(self, mapper):
        # type: (Mapper) -> bool
        return (self._mapper is mapper)

    # * Preloading values/histories of model instance attributes:

    def touch_own_identifying_stuff(self):
        # type: () -> None
        self.get_identifying_data_dict()

    def touch_all_own_attrs_and_identifying_stuff_of_related_instances(self):
        # type: () -> None
        for name, attr_state in self._iter_all_attr_name_state_pairs():
            value = attr_state.value
            if isinstance(value, Base):
                self.__class__(value).touch_own_identifying_stuff()
            if self._is_collection_attr(name):
                self._verify_collection_is_list(value)
                for related_instance in value:
                    self.__class__(related_instance).touch_own_identifying_stuff()

    def ensure_all_own_attr_histories_are_loaded(self):
        # type: () -> None
        for _, attr_state in self._iter_all_attr_name_state_pairs():
            attr_state.load_history()

    # * Accessing model instance data (in a JSON-serializable form):

    def get_identifying_data_dict(self):
        # type: () -> JsonableDict
        return {
            'table': self._get_table_name(),
            'pk': dict(self._iter_pk_attrs()),
            'py_repr': ascii(self._model_instance),
        }

    def iter_nonvoid_attrs(self):
        # type: () -> Iterator[Tuple[String, Jsonable]]
        for name, attr_state in self._iter_all_attr_name_state_pairs():
            jsonable_value = self._get_jsonable_attr_value(name, none_if_empty_coll=True)
            if jsonable_value is not None:
                yield name, jsonable_value

    def iter_changed_attrs(self):
        # type: () -> Iterator[Tuple[String, Jsonable]]
        for name, attr_state in self._iter_all_attr_name_state_pairs():
            history = attr_state.load_history()
            if history.has_changes():
                jsonable_value = self._get_jsonable_attr_value(name)
                jsonable_value_old = self._get_jsonable_attr_value_old(name, history)
                if jsonable_value_old is not None:
                    name_old = name + '.old'
                    yield name_old, jsonable_value_old
                yield name, jsonable_value

    #
    # Auxiliary/debugging stuff

    def __repr__(self):
        return '{class_name}({model_instance!r})'.format(
            class_name=self.__class__.__qualname__,
            model_instance=self._model_instance)

    #
    # Internal stuff

    @classmethod
    def _wrap_if_model_instance(cls, obj):
        return (cls(obj) if isinstance(obj, Base)
                else obj)

    @staticmethod
    def _unwrap_if_model_instance_wrapper(obj):
        return (obj._model_instance if isinstance(obj, _ModelInstanceWrapper)
                else obj)

    def __eq__(self, other):
        # We base the equality test on model instances' state objects
        # to mimic the way model instances are compared to each other
        # in `sqlalchemy.orm.attributes.History.from_collection()`.
        # In particular, we make use of this test in the method
        # `_get_current_without_added()` (when removing from a list
        # some values that may be instances of this class).
        if isinstance(other, _ModelInstanceWrapper):
            self_state = inspect(self._model_instance)
            other_state = inspect(other._model_instance)
            assert (isinstance(self_state, InstanceState) and
                    isinstance(other_state, InstanceState))
            return self_state == other_state
        return NotImplemented

    def _get_table_name(self):
        # type: () -> String
        # noinspection PyUnresolvedReferences
        return self._model_instance.__tablename__

    def _iter_pk_attrs(self):
        # type: () -> Iterator[Tuple[String, Jsonable]]
        for column_obj in self._mapper.primary_key:
            assert isinstance(column_obj, Column)
            name = self._attr_name_from_column_obj(column_obj)
            jsonable_value = self._get_jsonable_attr_value(name)
            yield name, jsonable_value

    def _attr_name_from_column_obj(self, column_obj):
        # type: (Column) -> String
        prop = self._mapper.get_property_by_column(column_obj)
        assert isinstance(prop, MapperProperty) and hasattr(prop, 'key')
        attr_name = prop.key
        assert attr_name == column_obj.name  # (see `AuthDBCustomDeclarativeMeta`...)
        return attr_name

    def _iter_all_attr_name_state_pairs(self):
        # type: () -> Iterator[String, AttributeState]
        instance_state = inspect(self._model_instance)
        assert isinstance(instance_state, InstanceState)
        for attr_state in instance_state.attrs:
            assert isinstance(attr_state, AttributeState) and (hasattr(attr_state, 'key'))
            name = attr_state.key
            value = getattr(self._model_instance, name)  # <- loads value if not already loaded
            assert attr_state.value is value
            yield name, attr_state

    def _get_jsonable_attr_value(self, name, none_if_empty_coll=False):
        # type: (String, ...) -> Jsonable
        value = getattr(self._model_instance, name)
        if self._is_collection_attr(name):
            self._verify_collection_is_list(value)
            if none_if_empty_coll and not value:
                value = None
        return self._make_jsonable_from_attr_value(name, value)

    def _get_jsonable_attr_value_old(self, name, history):
        # type: (String, History) -> Jsonable
        current = getattr(self._model_instance, name)
        # noinspection PyUnresolvedReferences
        added = list(history.added or ())
        # noinspection PyUnresolvedReferences
        deleted = list(history.deleted or ())
        if self._is_collection_attr(name):
            self._verify_collection_is_list(current)
            old = self._reconstruct_old_collection(current, added, deleted)
        else:
            old = self._reconstruct_old_single_value(current, added, deleted)
        return self._make_jsonable_from_attr_value(name, old)

    def _is_collection_attr(self, name):
        # type: (String) -> bool
        prop = self._mapper.attrs[name]
        assert isinstance(prop, MapperProperty) and hasattr(prop, 'key') and prop.key == name
        return bool(getattr(prop, 'uselist', False))

    def _verify_collection_is_list(self, collection):
        # type: (Any) -> None
        if not isinstance(collection, list):
            raise NotImplementedError(
                '{!a} is *not* a list, and non-list collection attributes '
                'are *unsupported*. If you insist that they should be '
                'supported, you need to adjust the implementation of Audit '
                'Log appropriately. But do we really need that?! Let\'s '
                'keep things simple!'.format(collection))

    def _reconstruct_old_collection(self, current, added, deleted):
        # type: (list, list, list) -> list
        current_without_added = self._get_current_without_added(current, added)
        return current_without_added + deleted

    def _get_current_without_added(self, current, added):
        proc = list(map(self._wrap_if_model_instance, current))
        for val in map(self._wrap_if_model_instance, added):
            assert val in proc
            proc.remove(val)
        return list(map(self._unwrap_if_model_instance_wrapper, proc))

    def _reconstruct_old_single_value(self, current_single_value, added, deleted):
        added = list(added or [None])
        deleted = list(deleted or [None])
        assert added == [current_single_value]
        assert len(deleted) == 1
        return deleted[0]

    def _make_jsonable_from_attr_value(self, name, value):
        # type: (String, Any) -> Jsonable
        value = self._wrap_if_model_instance(value)
        if value is None:
            return None
        if name in self._HIDDEN_STRING_ATTR_NAMES:
            if not isinstance(value, str):
                raise TypeError(
                    'any non-`None` value of the {!a} attribute of a '
                    'model instance is expected to be a string (got a '
                    'value of the type {!a})'.format(name, type(value)))
            return self._HIDDEN_STRING_ATTR_VALUE_PLACEHOLDER
        if isinstance(value, _ModelInstanceWrapper):
            return value.get_identifying_data_dict()
        if isinstance(value, list):
            return [self._make_jsonable_from_attr_value(name, val) for val in value]
        if isinstance(value, (str, bool, int, float)):
            return value
        if isinstance(value, datetime.datetime):
            return {'dt': value.isoformat()}
        if isinstance(value, datetime.date):
            return {'d': value.isoformat()}
        if isinstance(value, datetime.time):
            return {'t': value.isoformat()}
        return {'py_repr': ascii(value)}

    _HIDDEN_STRING_ATTR_NAMES = frozenset({'password'})
    _HIDDEN_STRING_ATTR_VALUE_PLACEHOLDER = '***'


class _AuditLogEntryBuilder(DictWithSomeHooks):

    """
    Log entry builder, implemented as a subclass of `dict`.

    First, it should be populated (using the standard `dict` interface
    as well as the additional 'update_subdict()' method) -- so that all
    necessary items are provided; it is required that at least the keys
    specified by `_AuditLogEntryBuilder.REQUIRED_GENERIC_FINAL_KEYS`
    and the appropriate (for the type of the operation) item of
    `_AuditLogEntryBuilder.OPERATION_TO_REQUIRED_FINAL_KEYS` be
    provided. It is also required that all added items be serializable
    with `json.dumps()`.

    Finally, the builder instance itself needs to be called. The return
    value -- a JSON-formatted, single-line, ASCII-only string -- is the
    resultant Audit Log entry, ready to be emitted.
    """

    #
    # Public interface (apart from the standard `dict` interface)

    # * constants:

    VALID_OPERATIONS = {'insert', 'update', 'delete'}
    REQUIRED_GENERIC_FINAL_KEYS = {
        'meta',
        'operation',
        'pk',
        'py_repr',
        'table',
    }
    OPERATION_TO_REQUIRED_FINAL_KEYS = {
        'insert': {'attrs'},
        'update': {'changed_attrs'},
        'delete': set(),
    }
    assert OPERATION_TO_REQUIRED_FINAL_KEYS.keys() == VALID_OPERATIONS

    # * helper useful when populating with items:

    def update_subdict(self, key, jsonable_items):
        # type: (String, Union[JsonableDict, Iterable[Tuple[String, Jsonable]]]) -> None
        if key not in self:
            self[key] = {}
        self[key].update(jsonable_items)

    # * final log entry factory:

    def __call__(self):
        # type: () -> String
        self._verify_required_final_keys_provided()
        return json.dumps(self, sort_keys=True)

    #
    # Internal stuff

    def _verify_required_final_keys_provided(self):
        operation = self._verify_and_get_operation()
        required_keys = (self.REQUIRED_GENERIC_FINAL_KEYS |
                         self.OPERATION_TO_REQUIRED_FINAL_KEYS[operation])
        missing_keys = required_keys.difference(self)
        if missing_keys:
            raise ValueError('the following required keys are missing: {}'.format(
                ', '.join(map(ascii, sorted(missing_keys)))))

    def _verify_and_get_operation(self):
        key = 'operation'
        try:
            operation = self[key]
        except KeyError:
            raise ValueError('the required key {!a} is missing'.format(key))
        if operation not in self.VALID_OPERATIONS:
            raise ValueError('{}={!a} is not valid'.format(key, operation))
        assert operation in self.OPERATION_TO_REQUIRED_FINAL_KEYS
        return operation

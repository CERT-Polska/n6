# Copyright (c) 2019-2020 NASK. All rights reserved.

import contextlib
import datetime
import json
import sys

from sqlalchemy import event
from sqlalchemy.inspection import inspect
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


class AuditLog(object):

    """
    Trace (using SQLAlchemy hooks) and log changes in the Auth DB.

    Constructor kwargs:

        `session_factory` (required):
            An argumentless callable that, when called, produces an
            instance of an `sqlalchemy.orm.session.Session` subclass
            specific to this particular `session_factory` object (not
            of the `sqlalchemy.orm.session.Session` class itself). A
            typical instance of `sqlalchemy.orm.session.sessionmaker`
            or `sqlalchemy.orm.scoped_session` is a good candidate for
            `session_factory`.

        `external_meta_items_getter` (required):
            An argumentless callable that, when called, returns a
            JSON-able dict (or equivalent iterable of key-value pairs)
            whose items will be added to the `meta` subdict of each
            emitted Audit Log entry. They should, in particular, carry
            information identifying the user, component or client that
            (in the context of a particular session/HTTP request/etc.)
            ordered or triggered the (currently being logged) changes
            in the Auth DB.

        `logger` (optional):
            If given, it should specify (by name or by instance) the
            logger to be used to emit Audit Log entries (they will be
            emitted using the logger's `info()` method). If not given,
            the default logger, specified by the `DEFAULT_LOGGER_NAME`
            class attribute, will be used.

    Some notes:

    * Supported operations (*insert*, *update* and *delete*) are logged
      only if they have been committed successfully.

    * The *bulk update* and *bulk delete* operations are explicitly
      forbidden -- they cause `RuntimeError`.

    * Each log entry is a JSON-formatted single-line string whose
      content (when deserialized with `json.loads()`) is a dictionary
      -- such as, for example:

      ```
      {
          'changed_attrs' {
              'actual_name': 'Foo Bar Example Spam',
              'org_id': 'org.example.info',
              'org_id.old': 'spam.example.com',
              'full_access': True,
              'full_access.old': False,
              'inside_subsources: [
                  {
                      'pk': {'id': 123},
                      'py_repr': "<Subsource: id=123, label=u'foo', source_id=u'some.src'>",
                      'table': 'subsource',
                  },
                  {
                      'pk': {'id': 456},
                      'py_repr': "<Subsource: id=456, label=u'bar', source_id=u'another.source'>",
                      'table': 'subsource',
                  },
              ],
              'threats_subsources: [],
              'threats_subsources.old: [
                  {
                      'pk': {'id': 123},
                      'py_repr': "<Subsource: id=123, label=u'foo', source_id=u'some.src'>",
                      'table': 'subsource',
                  },
              ],
          },
          'meta': {
              'commit_tag': '2019-12-30T17:50:03.000123Z#9b40092c8511',
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
          'py_repr': "<Org org_id=u'org.example.info'>",
          'table': 'org',
      }
      ```
    """

    #
    # Public interface

    DEFAULT_LOGGER_NAME = 'AUTH_DB_AUDIT_LOG'

    def __init__(self,
                 session_factory,
                 external_meta_items_getter,
                 logger=None):
        self._logger = self._get_logger_obj(logger)
        self._relevant_session_type = self._get_relevant_session_type(session_factory)
        self._external_meta_items_getter = external_meta_items_getter
        self._register_event_handlers()

    #
    # Internal stuff

    # * Methods related to initialization:

    def _get_logger_obj(self, logger):
        return (get_logger(self.DEFAULT_LOGGER_NAME) if logger is None
                else (get_logger(logger) if isinstance(logger, basestring)
                      else logger))

    def _get_relevant_session_type(self, session_factory):
        detected_session_type = type(session_factory())
        if detected_session_type is not Session and issubclass(detected_session_type, Session):
            return detected_session_type
        else:
            raise TypeError(
                '`session_factory` needs to be an object that, when '
                'called, returns a session object whose type is *not* '
                '`sqlalchemy.orm.session.Session` but *is* a (direct '
                'or indirect) subclass of it. We insist on that '
                'because then such sessions can be distinguished from '
                'any other sessions; so that, when it comes to event '
                'handling, *only* events from sessions of "our" type '
                'are considered. Hint: a typical *instance* of '
                '`sqlalchemy.orm.session.sessionmaker` (or of '
                '`sqlalchemy.orm.scoped_session`), when called, '
                'produces sessions of a type (being a subclass of '
                '`Session`) specific to that instance; so such an '
                'instance meets the above requirement out-of-the-box. '
                'TL;DR: don\'t know what `session_factory` should be? '
                'Use an instance of `sessionmaker` or an instance of '
                '`scoped_session` (of course, the one that is really '
                'used to produce sessions to be used to modify the '
                'content of Auth DB.')

    def _register_event_handlers(self):
        session_type = self._relevant_session_type
        event.listen(session_type, 'after_transaction_create', self._after_transaction_create)
        event.listen(session_type, 'before_flush', self._before_flush)
        event.listen(Base, 'after_insert', self._after_insert, propagate=True)
        event.listen(Base, 'after_update', self._after_update, propagate=True)
        event.listen(Base, 'after_delete', self._after_delete, propagate=True)
        event.listen(session_type, 'after_commit', self._after_commit)
        event.listen(session_type, 'after_transaction_end', self._after_transaction_end)
        self._register_event_handlers_for_unsupported_operations()

    def _register_event_handlers_for_unsupported_operations(self):
        # Let's ensure that the *bulk delete* and *bulk update*
        # operations -- which cannot be easily tracked, so should not
        # be used at all with Auth DB -- will not pass unnoticed, but
        # will cause an explicit error.
        session_type = self._relevant_session_type
        event.listen(session_type, 'after_bulk_delete', self._after_bulk_delete)
        event.listen(session_type, 'after_bulk_update', self._after_bulk_update)

    # * Handlers of SQLAlchemy ORM events:

    def _after_transaction_create(self, session, transaction):
        assert isinstance(session, self._relevant_session_type)
        self._set_empty_entry_builders_list_on(transaction)

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
        self._move_entry_builders_to_nearest_real_ancestor_of(transaction)

    def _after_transaction_end(self, session, transaction):
        assert isinstance(session, self._relevant_session_type)
        # This cleanup is not strictly necessary -- but let's be tidy. :-)
        self._remove_entry_builders_list_from(transaction)

    def _after_bulk_delete(self, delete_context):
        assert isinstance(delete_context.session, self._relevant_session_type)
        raise RuntimeError('bulk deletes are not supported by {!r}'.format(self))

    def _after_bulk_update(self, update_context):
        assert isinstance(update_context.session, self._relevant_session_type)
        raise RuntimeError('bulk updates are not supported by {!r}'.format(self))

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
                'The given mapper object {!r} is not the mapper of the '
                'model instance {!r}. Do you use some advanced or hackish '
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
        return session.bind.url.__to_string__(hide_password=True)

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
            'the given transaction object does *not* have the {!r} '
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

    def _move_entry_builders_to_nearest_real_ancestor_of(self, source_transaction):
        source_parent_transaction = self._get_parent_of(source_transaction)
        target_transaction = self._search_for_nearest_real_transaction(source_parent_transaction)
        self._move_entry_builders(source_transaction, target_transaction)

    def _move_entry_builders(self, source_transaction, target_transaction):
        assert source_transaction is not target_transaction
        source_list = self._get_entry_builders_list_from(source_transaction)
        target_list = self._get_entry_builders_list_from(target_transaction)
        target_list.extend(source_list)
        del source_list[:]

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
        return isinstance(transaction, SessionTransaction) and (
            self._does_represent_nested_db_savepoint(transaction) or
            self._does_represent_actual_db_transaction(transaction))

    def _does_represent_nested_db_savepoint(self, transaction):
        return transaction.nested

    def _does_represent_actual_db_transaction(self, transaction):
        # In other words: "Is it -- in the stack of
        # transaction objects -- the outermost one?".
        return self._get_parent_of(transaction) is None

    def _get_parent_of(self, transaction):
        # Note: using the `_parent` attribute of a `SessionTransaction`
        # object is officially documented as a workaround -- acceptable
        # when using versions of SQLAlchemy older than the version
        # 1.0.16 (which introduced the `parent` public attribute; see:
        # https://docs.sqlalchemy.org/en/latest/orm/session_api.html#sqlalchemy.orm.session.SessionTransaction.parent).
        # noinspection PyProtectedMember
        return transaction._parent

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
            if self._does_represent_nested_db_savepoint(transaction):
                break
            parent_transaction = self._get_parent_of(transaction)
            if parent_transaction is None:
                break
            assert not self._is_real_transaction(transaction)
            assert self._get_entry_builders_list_from(transaction) == []
            transaction = parent_transaction
        assert self._is_real_transaction(transaction)
        return transaction


class _ModelInstanceWrapper(object):

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
            raise TypeError('{!r} is not an instance of {!r}'.format(model_instance, Base))
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
            'py_repr': repr(self._model_instance),
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
            class_name=self.__class__.__name__,
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
        return False

    def __ne__(self, other):
        return not (self == other)

    # Because we have the equality test implemented (see:  `__eq__()`)
    # and we don't need the hashability feature, let's be on a safe
    # side and have this feature explicitly disabled.
    __hash__ = None

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
        if attr_name != column_obj.name:
            raise NotImplementedError(
                'The property key (model attribute name) {!r} is not equal '
                'to the corresponding database column name {!r}. SQLAlchemy '
                'supports such cases but n6\'s Auth DB and Audit Log do not. '
                'If you insist that such cases should be supported, you need '
                'to implement all needed stuff (in particular, to make Audit '
                'Log messages include information that attribute x refers '
                'to column y...). But do we really need that?! Let\'s keep '
                'things simple!'.format(attr_name, column_obj.name))
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
                '{!r} is *not* a list, and non-list collection attributes '
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
            if not isinstance(value, basestring):
                raise TypeError(
                    'any non-`None` value of the {!r} attribute of a '
                    'model instance is expected to be a string (got a '
                    'value of the type {!r})'.format(name, type(value)))
            return self._HIDDEN_STRING_ATTR_VALUE_PLACEHOLDER
        if isinstance(value, _ModelInstanceWrapper):
            return value.get_identifying_data_dict()
        if isinstance(value, list):
            return [self._make_jsonable_from_attr_value(name, val) for val in value]
        if isinstance(value, (basestring, bool, int, long, float)):
            return value
        if isinstance(value, datetime.datetime):
            return {'dt': value.isoformat()}
        if isinstance(value, datetime.date):
            return {'d': value.isoformat()}
        if isinstance(value, datetime.time):
            return {'t': value.isoformat()}
        return {'py_repr': repr(value)}

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
    assert OPERATION_TO_REQUIRED_FINAL_KEYS.viewkeys() == VALID_OPERATIONS

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
                ', '.join(map(repr, sorted(missing_keys)))))

    def _verify_and_get_operation(self):
        key = 'operation'
        try:
            operation = self[key]
        except KeyError:
            raise ValueError('the required key {!r} is missing'.format(key))
        if operation not in self.VALID_OPERATIONS:
            raise ValueError('{}={!r} is not valid'.format(key, operation))
        assert operation in self.OPERATION_TO_REQUIRED_FINAL_KEYS
        return operation

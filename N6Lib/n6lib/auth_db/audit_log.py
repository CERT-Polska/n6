# Copyright (c) 2019 NASK. All rights reserved.

import threading
from collections import namedtuple

from sqlalchemy import (
    event,
    inspect,
)

from n6lib.auth_db.models import Base
from n6lib.common_helpers import ascii_str
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


PrimaryKey = namedtuple('PrimaryKey', ('name', 'value', 'repr'))


class AuditLogThreadLocalState(threading.local):

    def __init__(self):
        self.inserted = []
        self.updated = []
        self.deleted = []


class AuditLog(object):

    """
    Log user actions on an SQL database through SQLAlchemy hooks.

    AuditLog log actions permitted in N6AdminPanel (INSERT, UPDATE
    and DELETE) after they are committed.
    """

    def __init__(self, db_session):
        event.listen(Base, 'after_insert', self.insert_listener, propagate=True)
        event.listen(Base, 'after_update', self.update_listener, propagate=True)
        event.listen(Base, 'after_delete', self.delete_listener, propagate=True)
        event.listen(db_session, 'after_commit', self.action_after_commit)
        self.state = AuditLogThreadLocalState()

    def insert_listener(self, mapper, connection, target):
        pk_names, pk_reprs = self._get_pk_related_items(mapper, target.__dict__)
        table_name = target.__tablename__
        # a dict mapping table's field names to their values
        fields_repr = sorted("{} = {}".format(ascii_str(key),
                                              ascii_str(val))
                             for key, val in target.__dict__.iteritems()
                             # ignore empty fields; not comparing to None,
                             # so empty lists are ignored
                             if (val or val is False or val == 0)
                             # ignore private attributes that are not fields
                             and not key.startswith('_')
                             # ignore primary key fields, because their
                             # representation list will be kept separately
                             and key not in pk_names
                             # ignore not a field "metadata" attribute
                             and key != 'metadata')
        self.state.inserted.append((table_name, pk_reprs, fields_repr))

    def update_listener(self, mapper, connection, target):
        insp = inspect(target)
        hist_attrs = insp.attrs
        pk_names, pk_reprs = self._get_pk_related_items(mapper, target.__dict__)
        table_name = target.__tablename__
        # create representation of updated fields
        fields_repr = sorted("{} = {}".format(ascii_str(x.key),
                                              ascii_str(target.__dict__[x.key]))
                             for x in hist_attrs
                             # include only updated fields
                             if x.history.has_changes()
                             # make sure the field is a part of table
                             and x.key in target.__dict__
                             # ignore primary key fields, because their
                             # representation list will be kept separately
                             and x.key not in pk_names)
        self.state.updated.append((table_name, pk_reprs, fields_repr))

    def delete_listener(self, mapper, connection, target):
        _, pk_reprs = self._get_pk_related_items(mapper, target.__dict__)
        table_name = target.__tablename__
        # a deleted record can be represented just by a primary key
        self.state.deleted.append((table_name, pk_reprs))

    def action_after_commit(self, session):
        self.log_actions(remote_addr=session.info['remote_addr'],
                         username=session.bind.url.username)

    def log_actions(self, remote_addr, username):
        safe_remote_addr = ascii_str(remote_addr)
        safe_username = ascii_str(username)
        for table, pks, fields_repr in self.state.inserted:
            LOGGER.info("INSERT -- table: %s, PK (%s): %s -- by: %s @ %s",
                        ascii_str(table),
                        '; '.join(pks),
                        fields_repr,
                        safe_username,
                        safe_remote_addr)
        self.state.inserted = []
        for table, pks, fields_repr in self.state.updated:
            LOGGER.info("UPDATE -- table: %s, PK (%s), changes: %s -- by %s @ %s",
                        ascii_str(table),
                        '; '.join(pks),
                        fields_repr,
                        safe_username,
                        safe_remote_addr)
        self.state.updated = []
        for table, pks in self.state.deleted:
            LOGGER.info("DELETE -- table: %s, PK (%s) -- by %s @ %s",
                        ascii_str(table),
                        '; '.join(pks),
                        safe_username,
                        safe_remote_addr)
        self.state.deleted = []

    @staticmethod
    def _get_pk_related_items(mapper, attrs):
        pks = []
        for pk in mapper.primary_key:
            pk_value = attrs.get(pk.name)
            pks.append(PrimaryKey(name=pk.name,
                                  value=pk_value,
                                  repr="{} = {}".format(ascii_str(pk.name),
                                                        ascii_str(pk_value))))
        pk_names = [pk.name for pk in pks]
        # create a list of strings representing primary keys and their
        # values in user-friendly form ('field_name': 'value')
        pk_reprs = [pk.repr for pk in pks]
        return pk_names, pk_reprs

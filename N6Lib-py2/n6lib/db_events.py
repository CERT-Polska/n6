# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.
#
# For some portions of the code (marked in the comments as copied from
# SQLAlchemy -- which is a library licensed under the MIT license):
# Copyright (C) 2005-2021 the SQLAlchemy authors and contributors
# <see SQLAlchemy's AUTHORS file>. SQLAlchemy is a trademark of Michael
# Bayer (mike(&)zzzcomputing.com). All rights reserved.

from builtins import map                                                         #3--
import json
import socket
import types                                                                     #3--
from typing import Iterable

import sqlalchemy.types
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
)
from sqlalchemy.dialects import mysql
from sqlalchemy import (
    or_,
    and_,
    null,
)

from n6lib.common_helpers import (
    ip_network_tuple_to_min_max_ip,
    ip_str_to_int,
)
from n6lib.data_spec import N6DataSpec
from n6lib.data_spec.typing_helpers import ResultDict
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger
from n6lib.url_helpers import make_provisional_url_search_key
from n6lib.typing_helpers import String as Str


LOGGER = get_logger(__name__)


_DBSession = scoped_session(sessionmaker(autocommit=False))


Base = declarative_base()

CustomInteger = sqlalchemy.types.Integer()
CustomInteger = CustomInteger.with_variant(mysql.INTEGER(unsigned=True), "mysql")


class IPAddress(sqlalchemy.types.TypeDecorator):
    impl = CustomInteger

    # `ip` cannot be NULL as it is part of the primary key
    ### XXX: but whis field is used also for `dip` -- should it??? (see: #3490)
    NONE = 0
    NONE_STR = '0.0.0.0'

    def process_bind_param(self, value, dialect):
        if value == -1:
            ## CR: remove or raise a loud error? (anything uses -1???)
            return self.NONE
        if value is None:
            ## XXX: ensure that process_bind_param() is (not?) called
            ## by the SQLAlchemy machinery when `ip` value is None
            return self.NONE
        int = (type(1), long)                                                    #3--
        if isinstance(value, int):
            return value
        try:
            return ip_str_to_int(value)
        except socket.error:
            raise ValueError

    def process_result_value(self, value, dialect):
        if value is None or value == self.NONE:
            return None
        if not hasattr(bytes, 'fromhex'):                                        #3--
            return socket.inet_ntoa(hex(int(value))[2:].zfill(8).decode('hex'))  #3--
        # TODO: the same can be expressed in a simpler way by using value.to_bytes...
        return socket.inet_ntoa(bytes.fromhex(hex(value)[2:].zfill(8)))



class _HashTypeMixIn(object):

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        try:
            if not hasattr(bytes, 'fromhex'):                                    #3--
                return value.decode('hex')                                       #3--
            return bytes.fromhex(value)
        except TypeError:
            raise ValueError

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not hasattr(bytes, 'fromhex'):                                        #3--
            return value.encode('hex')                                           #3--
        return value.hex()


class MD5(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(16)


class SHA1(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(20)


class SHA256(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(32)


class JSONText(sqlalchemy.types.TypeDecorator):

    impl = Text

    def bind_processor(self, dialect):
        # Copied from SQLAlchemy's `sqlalchemy.types.PickleType`
        # and adjusted appropriately.

        impl_processor = self.impl.bind_processor(dialect)
        dumps = json.dumps
        if impl_processor:

            def process(value):
                if value is not None:
                    value = dumps(value)
                return impl_processor(value)

        else:

            def process(value):
                if value is not None:
                    value = dumps(value)
                return value

        return process

    def result_processor(self, dialect, coltype):
        # Copied from SQLAlchemy's `sqlalchemy.types.PickleType`
        # and adjusted appropriately.

        impl_processor = self.impl.result_processor(dialect, coltype)
        loads = json.loads
        if impl_processor:

            def process(value):
                value = impl_processor(value)
                if value is None:
                    return None
                return loads(value)

        else:

            def process(value):
                if value is None:
                    return None
                return loads(value)

        return process


class n6ClientToEvent(Base):
    __tablename__ = 'client_to_event'

    id = Column(MD5, primary_key=True)
    time = Column(DateTime, primary_key=True)
    client = Column(String(N6DataSpec.client.max_length), primary_key=True)

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.client = kwargs.pop("client", None)
        self.time = parse_iso_datetime_to_utc(kwargs.pop("time"))

        ## we know that recorder passes in a lot of redundant **kwargs
        ## (appropriate rather for n6NormalizedData than for n6ClientToEvent) so
        ## we do not want to clutter the logs -- that's why the following code
        ## is commented out:
        #if kwargs:
        #    LOGGER.warning(
        #        'n6ClientToEvent.__init__() got unexpected **kwargs: %r',
        #        kwargs)

    ## XXX: is this method necessary anymore?
    def __json__(self, request):
        return self.client



class n6NormalizedData(Base):

    __tablename__ = 'event'

    _n6columns = dict(N6DataSpec().generate_sqlalchemy_columns(
        id=dict(primary_key=True),
        time=dict(primary_key=True),
        ip=dict(primary_key=True, autoincrement=False)))

    locals().update(_n6columns)  # hack, but a simple one, and it works :)

    clients = relationship(
        n6ClientToEvent,
        # XXX: is it necessary anymore?
        primaryjoin=and_(
            #_n6columns['time'] == n6ClientToEvent.time, ### redundant join condition
            _n6columns['id'] == n6ClientToEvent.id),
        #foreign_keys=[n6ClientToEvent.time, n6ClientToEvent.id],
        # XXX: is it necessary anymore?
        foreign_keys=[n6ClientToEvent.id],
        backref="events")

    def __init__(self, **kwargs):
        if kwargs.get('ip') is None:
            # adding the "no IP" placeholder ('0.0.0.0') which should be
            # transformed into 0 in the database (because `ip` cannot be
            # NULL in our SQL db; and apparently, for unknown reason,  # XXX: <- check whether that's true...
            # IPAddress.process_bind_param() is not called by the
            # SQLAlchemy machinery if the value of `ip` is just None)
            kwargs['ip'] = IPAddress.NONE_STR
        kwargs['time'] = parse_iso_datetime_to_utc(kwargs["time"])
        kwargs['expires'] = (
            parse_iso_datetime_to_utc(kwargs.get("expires"))
            if kwargs.get("expires") is not None
            else None)
        kwargs['modified'] = (
            parse_iso_datetime_to_utc(kwargs.get("modified"))
            if kwargs.get("modified") is not None
            else None)
        for name in self._n6columns:
            setattr(self, name, kwargs.pop(name, None))
        ### XXX: the 'until' field is not converted here to utc datetime!
        ### (see ticket #3113)

        kwargs.pop('client', None)  # here we just ignore this arg if present
        kwargs.pop('type', None)    # here we just ignore this arg if present
        if kwargs:
            LOGGER.warning(
                'n6NormalizedData.__init__() got unexpected **kwargs: %r',
                kwargs)

    @classmethod
    def get_column_mapping_attrs(cls):
        return [getattr(cls, name) for name in sorted(cls._n6columns)]

    @classmethod
    def key_query(cls, key, value):
        return getattr(cls, key).in_(value)

    @classmethod
    def like_query(cls, key, value):
        mapping = {"url.sub": "url", "fqdn.sub": "fqdn"}
        return or_(*[getattr(cls, mapping[key]).like(u"%{}%".format(val))
                     for val in value])

    @classmethod
    def url_b64_experimental_query(cls, key, value):
        # *EXPERIMENTAL* (likely to be changed or removed in the future
        # without any warning/deprecation/etc.)
        if key != 'url.b64':
            raise AssertionError("key != 'url.b64' (but == {!r})".format(key))
        db_key = 'url'
        url_search_keys = list(map(make_provisional_url_search_key, value))
        return or_(getattr(cls, db_key).in_(value),
                   getattr(cls, db_key).in_(url_search_keys))

    @classmethod
    def ip_net_query(cls, key, value):
        if key != 'ip.net':
            # (`assert` not used because of the check in a unit test...)
            raise AssertionError
        queries = []
        for val in value:
            min_ip, max_ip = ip_network_tuple_to_min_max_ip(val)
            queries.append(and_(cls.ip >= min_ip, cls.ip <= max_ip))
        return or_(*queries)

    @classmethod
    def active_bl_query(cls, key, value):
        assert len(value) == 1
        value = value[0]
        if key == "active.min":
            return or_(cls.expires >= value, cls.time >= value)
        elif key == "active.max":
            return or_(
                and_(cls.expires.isnot(null()), cls.expires <= value),
                and_(cls.expires.is_(null()), cls.time <= value))
        elif key == "active.until":
            return or_(
                and_(cls.expires.isnot(null()), cls.expires < value),
                and_(cls.expires.is_(null()), cls.time < value))
        else:
            raise AssertionError

    @classmethod
    def modified_query(cls, key, value):
        assert len(value) == 1
        value = value[0]
        if key == "modified.min":
            return cls.modified >= value
        elif key == "modified.max":
            return cls.modified <= value
        elif key == "modified.until":
            return cls.modified < value
        else:
            raise AssertionError

    def to_raw_result_dict(self):
        client_org_ids = (c.client for c in self.clients)                                    # noqa
        return make_raw_result_dict(self, client_org_ids)


# names of columns whose `type` attribute
# is IPAddress or its subclass/instance
_IP_COLUMN_NAMES = tuple(sorted(
    name for name, column in n6NormalizedData._n6columns.items()
    if (isinstance(column.type, IPAddress)
        or (isinstance(column.type, (type, types.ClassType))                     #3: remove `types.ClassType`
            and issubclass(column.type, IPAddress)))))


# possible "no IP" placeholder values (such that they
# cause recording `ip` in db as 0) -- excluding None
_NO_IP_PLACEHOLDERS = frozenset([IPAddress.NONE_STR, IPAddress.NONE, -1])


def make_raw_result_dict(column_values_source_object,  # getattr() will be used on it to get values

                         # a collection of client organization ids (to populate
                         # the `client` field of the result -- if not empty)
                         client_org_ids,   # type: Iterable[Str]

                         # not real parameters, just quasi-constants for faster access
                         _getattr=getattr,
                         _all_column_objects=n6NormalizedData.__table__.columns,             # noqa
                         _is_no_ip_placeholder=_NO_IP_PLACEHOLDERS.__contains__):

    # type: (...) -> ResultDict

    # make the dict, skipping all None values
    result_dict = {
        name: value
        for name, value in [
            (c.name, _getattr(column_values_source_object, c.name))
            for c in _all_column_objects]
        if value is not None}

    # get rid of any "no IP" placeholders
    for ip_col_name in _IP_COLUMN_NAMES:
        value = result_dict.get(ip_col_name)
        if _is_no_ip_placeholder(value):                                                     # noqa
            del result_dict[ip_col_name]

    # set the 'client' item if any org ids given
    client_org_ids = sorted(client_org_ids)
    if client_org_ids:
        result_dict['client'] = client_org_ids

    return result_dict

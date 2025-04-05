# Copyright (c) 2013-2025 NASK. All rights reserved.
#
# For some portions of the code (marked in the comments as copied from
# SQLAlchemy -- which is a library licensed under the MIT license):
# Copyright (C) 2005-2021 the SQLAlchemy authors and contributors
# <see SQLAlchemy's AUTHORS file>. SQLAlchemy is a trademark of Michael
# Bayer (mike(&)zzzcomputing.com). All rights reserved.

import datetime
import json
import socket
from binascii import unhexlify
from collections.abc import Iterable

import sqlalchemy.types
from sqlalchemy import (
    Boolean,
    Column,
    String,
    DateTime,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    validates,
)
from sqlalchemy.dialects import mysql
from sqlalchemy import (
    or_,
    and_,
    null,
    text as sqla_text,
)

from n6lib.common_helpers import (
    ip_network_tuple_to_min_max_ip,
    ip_str_to_int,
    ip_int_to_str,
)
from n6lib.const import (
    LACK_OF_IPv4_PLACEHOLDER_AS_INT,
    LACK_OF_IPv4_PLACEHOLDER_AS_STR,
)
from n6lib.data_spec import N6DataSpec
from n6lib.data_spec.typing_helpers import ResultDict
from n6lib.datetime_helpers import (
    datetime_utc_normalize,
    parse_iso_datetime,
)
from n6lib.log_helpers import get_logger
from n6lib.url_helpers import make_provisional_url_search_key


LOGGER = get_logger(__name__)


_DBSession = scoped_session(sessionmaker(autocommit=False))

Base = declarative_base()


class IPAddress(sqlalchemy.types.TypeDecorator):

    impl = sqlalchemy.types.Integer().with_variant(mysql.INTEGER(unsigned=True), 'mysql')

    _LACK_OF_IPv4_AS_INT_LEGACY = -1   # <- TODO later: remove

    def process_bind_param(self, value, dialect):
        assert value != self._LACK_OF_IPv4_AS_INT_LEGACY  # <- Shouldn't appear. TODO later: remove
        if value is None:
            # (neither `ip` nor `dip` can be NULL)
            return LACK_OF_IPv4_PLACEHOLDER_AS_INT
        if isinstance(value, int):
            return value
        assert isinstance(value, str)
        try:
            return ip_str_to_int(value)
        except socket.error:
            raise ValueError

    def process_result_value(self, value, dialect):
        assert value != self._LACK_OF_IPv4_AS_INT_LEGACY  # <- Shouldn't appear. TODO later: remove
        if value is None:
            return None
        assert isinstance(value, int)
        if value == LACK_OF_IPv4_PLACEHOLDER_AS_INT:
            # (neither `ip` nor `dip` can be NULL)
            return None
        return ip_int_to_str(value)


class _HashTypeMixIn:

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not value:
            raise ValueError
        try:
            return unhexlify(value)
        except TypeError:
            raise ValueError

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.hex()


class MD5(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(16)


class SHA1(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(20)


class SHA256(_HashTypeMixIn, sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.BINARY(32)


class JSONMediumText(sqlalchemy.types.TypeDecorator):

    impl = MEDIUMTEXT

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


def _is_ip_addr_column(col):
    assert isinstance(col, Column)
    return (isinstance(col.type, IPAddress)
            or (isinstance(col.type, type) and issubclass(col.type, IPAddress)))

def _is_flag_column(col):
    assert isinstance(col, Column)
    return (isinstance(col.type, Boolean)
            or (isinstance(col.type, type) and issubclass(col.type, Boolean)))

def _is_dt_column(col):
    assert isinstance(col, Column)
    return (isinstance(col.type, DateTime)
            or (isinstance(col.type, type) and issubclass(col.type, DateTime)))

def _to_utc_datetime(value):
    if isinstance(value, str):
        value = parse_iso_datetime(value)
    elif not isinstance(value, datetime.datetime):
        raise TypeError(f'unsupported type for date+time: {type(value)=!a}')
    assert isinstance(value, datetime.datetime)
    value = datetime_utc_normalize(value)
    return value


class n6ClientToEvent(Base):

    __tablename__ = 'client_to_event'

    id = Column(MD5, primary_key=True)
    time = Column(DateTime, primary_key=True)
    client = Column(String(N6DataSpec.client.max_length), primary_key=True)

    assert _is_dt_column(time)  # noqa
    @validates('time')
    def _adjust_time(self, name, value):
        assert name == 'time'
        return _to_utc_datetime(value)

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.client = kwargs.pop("client", None)
        self.time = kwargs.pop("time")

        ## We know that recorder passes in a lot of redundant **kwargs
        ## (appropriate rather for n6NormalizedData than for n6ClientToEvent) so
        ## we do not want to clutter the logs -- that's why the following code
        ## is commented out:
        #if kwargs:
        #    LOGGER.warning(
        #        'n6ClientToEvent.__init__() got unexpected **kwargs: %a',
        #        kwargs)


class n6NormalizedData(Base):

    __tablename__ = 'event'

    _n6columns = dict(sorted(N6DataSpec().generate_sqlalchemy_columns(
        id=dict(primary_key=True),
        time=dict(primary_key=True),
        ip=dict(primary_key=True, autoincrement=False))))

    _n6columns_ip_addr = {
        name: col for name, col in _n6columns.items()
        if _is_ip_addr_column(col)}

    _n6columns_flag = {
        name: col for name, col in _n6columns.items()
        if _is_flag_column(col)}

    _n6columns_dt = {
        name: col for name, col in _n6columns.items()
        if _is_dt_column(col)}

    assert _n6columns_ip_addr.keys() == {
        'ip',
        'dip',
    }
    assert _n6columns_flag.keys() == {
        'ignored',
    }
    assert _n6columns_dt.keys() == {
        'time',
        'modified',
        'expires',
        'until',
    }

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

    @validates(*_n6columns_ip_addr.keys())
    def _adjust_ip_addr_column_value(self, name, value):
        assert name in self._n6columns_ip_addr
        # Using the "no IP" placeholder ('0.0.0.0') which should be
        # transformed into 0 in the database (because `ip` and `dip`
        # cannot be NULL in our SQL db)
        # (XXX: is it necessary here, considering the `IPAddress.process_*()` methods?...)
        if value is None:
            value = LACK_OF_IPv4_PLACEHOLDER_AS_STR
        return value

    @validates(*_n6columns_flag.keys())
    def _adjust_flag_column_value(self, name, value):
        assert name in self._n6columns_flag
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        raise TypeError(f'{name}={value!a} is neither None '
                        f'nor an instance of bool')

    @validates(*_n6columns_dt.keys())
    def _adjust_dt_column_value(self, name, value):
        assert name in self._n6columns_dt
        if value is None:
            return None
        return _to_utc_datetime(value)

    def __init__(self, **kwargs):
        for name in self._n6columns:
            # Note: as we do this for all columns, the `@validates()`-
            # -decorated methods (see above) are always invoked for
            # each of the columns they are destined to.
            setattr(self, name, kwargs.pop(name, None))
        kwargs.pop('client', None)  # here we just ignore this arg if present
        kwargs.pop('type', None)    # here we just ignore this arg if present
        if kwargs:
            LOGGER.warning(
                'n6NormalizedData.__init__() got unexpected **kwargs: %a',
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
        col = getattr(cls, mapping[key])
        return or_(*[
            # Note: Each `col.contains(val, autoescape=True)` call is
            # translated into a suitable `LIKE` SQL condition, with `%`
            # and `_` escaped as appropriate (considering that those
            # characters, when used in a `LIKE`'s pattern, play a role
            # of *wildcard* markers).
            col.contains(val, autoescape=True)
            for val in value])

    @classmethod
    def single_flag_query(cls, key, value):
        assert len(value) == 1
        [flag] = value
        assert isinstance(flag, bool)
        col = getattr(cls, key)
        col_op = (col.is_ if flag else col.isnot)
        return col_op(sqla_text('TRUE'))

    @classmethod
    def url_b64_experimental_query(cls, key, value):
        # *EXPERIMENTAL* (likely to be changed or removed in the future
        # without any warning/deprecation/etc.)
        expected_key = 'url.b64'
        if key != expected_key:
            raise AssertionError(f'key != {expected_key!a} (got: {key = !a})')
        assert all(isinstance(url, bytes) for url in value)
        url_search_keys = value + list(map(make_provisional_url_search_key, value))
        return cls.url.in_(url_search_keys)

    @classmethod
    def ip_net_query(cls, key, value):
        if key != 'ip.net':
            # (`assert` not used because of the check in a unit test...)
            raise AssertionError
        queries = []
        for val in value:
            min_ip, max_ip = ip_network_tuple_to_min_max_ip(
                val,
                force_min_ip_greater_than_zero=True)
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


# Names of columns whose `type` attribute
# is IPAddress or its subclass/instance
_IP_COLUMN_NAMES = tuple(sorted(n6NormalizedData._n6columns_ip_addr.keys()))                 # noqa


# Possible "no IP" placeholder values (such that they
# cause recording `ip` in db as 0) -- excluding None
_NO_IP_PLACEHOLDERS = frozenset({
    LACK_OF_IPv4_PLACEHOLDER_AS_STR,
    LACK_OF_IPv4_PLACEHOLDER_AS_INT,
    IPAddress._LACK_OF_IPv4_AS_INT_LEGACY,   # <- TODO later: remove this one
})


def make_raw_result_dict(column_values_source_object,  # getattr() will be used on it to get values

                         # not real parameters, just quasi-constants for faster access
                         _getattr=getattr,
                         _all_column_objects=n6NormalizedData.__table__.columns,             # noqa
                         _is_no_ip_placeholder=_NO_IP_PLACEHOLDERS.__contains__,

                         ) -> ResultDict:

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

    # extract 'client' from `custom` if possible
    custom = result_dict.get('custom')
    if custom:
        client_org_ids = custom.pop('client', None)
        if client_org_ids:
            result_dict['client'] = client_org_ids
        if not custom:
            del result_dict['custom']

    return result_dict


# Below we work around a strange behavior of SQLAlchemy 1.3: the
# `n6ClientToEvent.events` attribute is not present *until* any
# model class is instantiated (it does not matter which one!).
#
# (The first assertion is commented out, as this behavior looks like
# an SQLAlchemy's implementation incident, not an intended behavior.)

#assert not hasattr(n6ClientToEvent, 'events')

n6NormalizedData()

assert hasattr(n6ClientToEvent, 'events')

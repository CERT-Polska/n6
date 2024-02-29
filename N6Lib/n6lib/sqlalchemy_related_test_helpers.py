# Copyright (c) 2013-2023 NASK. All rights reserved.

from sqlalchemy.dialects import mysql
from sqlalchemy.types import TypeEngine
from MySQLdb.converters import escape, conversions

from n6lib.common_helpers import as_unicode


def sqlalchemy_expr_to_str(sqlalchemy_expr):
    dialect = mysql.dialect()
    compiler = sqlalchemy_expr.compile(dialect=dialect)
    params = (compiler.params[k] for k in compiler.positiontup)
    escaped_params = tuple(as_unicode(escape(p, conversions)) for p in params)
    return compiler.string % escaped_params


def sqlalchemy_type_to_str(sqlalchemy_type):
    assert isinstance(sqlalchemy_type, TypeEngine)
    dialect = mysql.dialect()
    return str(sqlalchemy_type.compile(dialect=dialect))


def prep_sql_str(s):
    return u' '.join(s.split())

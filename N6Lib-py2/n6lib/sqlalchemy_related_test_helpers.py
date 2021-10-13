# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

from sqlalchemy.dialects import mysql
from MySQLdb.converters import escape, conversions


def sqlalchemy_expr_to_str(sqlalchemy_expr):
    dialect = mysql.dialect()
    compiler = sqlalchemy_expr.compile(dialect=dialect)
    params = (compiler.params[k] for k in compiler.positiontup)
    coerced_params = (p.encode('utf-8') if isinstance(p, unicode) else p         #3--
                      for p in params)                                           #3--
    escaped_params = tuple(escape(p, conversions) for p in coerced_params)         #3: `coerced_params` -> `params`
    return compiler.string % escaped_params


def prep_sql_str(s):
    return u' '.join(s.split())

# Copyright (c) 2013-2025 NASK. All rights reserved.

from __future__ import annotations

import contextlib
import types
from collections.abc import (
    Generator,
    Mapping,
    Sequence,
    Set,
)
from typing import (
    Any,
    Union,
)

from MySQLdb.converters import (
    conversions,
    escape,  # noqa
)
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import (
    Connection,
    Engine,
    RowProxy as SqlaRow,  # noqa
    reflection,
)
from sqlalchemy.schema import MetaData
from sqlalchemy.types import TypeEngine

from n6lib.common_helpers import as_unicode


#
# Auxiliary type aliases (for readability...)
#


DatabaseTableName = str
DatabaseColumnName = str
DatabaseColumnValue = Any

DatabaseRowAsDict = dict[DatabaseColumnName, DatabaseColumnValue]
DatabaseContentDict = dict[DatabaseTableName, list[DatabaseRowAsDict]]


#
# Actual helper functions
#


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


def get_declared_db_structure(
    metadata: MetaData,
    *,
    excluding_tables: Set[DatabaseTableName] = frozenset(),
) -> Mapping[DatabaseTableName, Sequence[DatabaseColumnName]]:
    """
    Get a `Mapping` that maps table names to sorted `Sequence`s of
    column names -- according to the given `MetaData` object.
    """
    return types.MappingProxyType({
        # Deliberately convert `str` subclasses to `str`.
        str(table.name): tuple(sorted(
            str(column.name)
            for column in table.columns
        ))
        for table in metadata.tables.values()
        if table.name not in excluding_tables
    })


def get_reflected_db_structure(
    engine: Engine,
    *,
    including_tables_beyond_sqla_metadata: bool = False,
    excluding_tables: Set[DatabaseTableName] = frozenset(),
) -> Mapping[DatabaseTableName, Sequence[DatabaseColumnName]]:
    """
    Get a `Mapping` that maps table names to sorted `Sequence`s of
    column names -- reflecting the actual structure of the database
    (obtained using the given `Engine` object).
    """
    if not including_tables_beyond_sqla_metadata:
        excluding_tables |= _TABLES_BEYOND_SQLA_METADATA

    insp = reflection.Inspector.from_engine(engine)
    return types.MappingProxyType({
        # Deliberately convert `str` subclasses to `str`.
        str(table_name): tuple(sorted(
            str(column_info['name'])
            for column_info in insp.get_columns(table_name)
        ))
        for table_name in insp.get_table_names()
        if table_name not in excluding_tables
    })


def fetch_db_content(
    metadata: MetaData,
    conn: Connection,
    *,
    including_empty_tables: bool = False,
    excluding_tables: Set[DatabaseTableName] = frozenset(),
    stringifying_types: tuple[type, ...] = (),
) -> DatabaseContentDict:
    """
    Get the database content -- as a dict that maps table names to lists
    of "rows" (each of which is just a dict that maps column names to
    values).
    """
    stringifying_types += (str,)  # <- To convert `str` subclasses to `str`.

    def _convert_sqla_row(sqla_row: SqlaRow) -> DatabaseRowAsDict:
        return {
            # Deliberately convert `str` subclasses to `str`.
            str(key): (
                str(val) if isinstance(val := sqla_row[key], stringifying_types)
                else val
            )
            for key in sqla_row.keys()
        }

    content = {}
    for table in metadata.tables.values():
        # Deliberately convert `str` subclasses to `str`.
        table_name = str(table.name)
        if table_name in excluding_tables:
            continue
        result = conn.execute(
            table.select().order_by(
                *table.primary_key,
            ),
        )
        rows = list(map(_convert_sqla_row, result.fetchall()))
        if rows or including_empty_tables:
            content[table_name] = rows
    return content


def insert_db_content(
    metadata: MetaData,
    conn: Connection,
    content: DatabaseContentDict,
    *,
    disallowing_tables: Set[DatabaseTableName] = frozenset(),
    defaults: Union[Mapping[DatabaseTableName, DatabaseRowAsDict], None] = None,
) -> None:
    """
    Insert some content to the database. The content should be given as
    a dict that maps table names to lists of "rows" (each of which is
    just a dict that maps column names to values).
    """
    illegal = content.keys() & disallowing_tables
    if illegal:
        raise ValueError(
            f'inserted content should not include the table(s): '
            f'{", ".join(map(repr, sorted(illegal)))}')
    remaining = set(content)
    with disabled_foreign_key_checks(conn):
        for table in metadata.tables.values():
            table_name = table.name
            if rows := content.get(table_name):
                if defaults is not None and (table_defaults := defaults.get(table_name)):
                    rows = [table_defaults | row for row in rows]
                conn.execute(
                    table.insert(rows, inline=True),
                )
                remaining.discard(table_name)
        if remaining:
            raise ValueError(
                f'unknown table name(s) (according to given metadata): '
                f'{", ".join(map(repr, sorted(remaining)))}')


def delete_db_content(
    metadata: MetaData,
    conn: Connection,
    *,
    excluding_tables: Set[DatabaseTableName] = frozenset(),
) -> None:
    """Delete the database content."""
    with disabled_foreign_key_checks(conn):
        for table in metadata.tables.values():
            if table.name in excluding_tables:
                continue
            conn.execute(
                table.delete(),
            )


@contextlib.contextmanager
def disabled_foreign_key_checks(conn: Connection) -> Generator:
    try:
        conn.execute('SET SESSION FOREIGN_KEY_CHECKS = 0')
        yield
    finally:
        conn.execute('SET SESSION FOREIGN_KEY_CHECKS = 1')


#
# Auxiliary non-public stuff
#


_TABLES_BEYOND_SQLA_METADATA: Set[DatabaseTableName] = frozenset({'alembic_version'})

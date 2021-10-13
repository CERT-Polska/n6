# Copyright (c) 2020-2021 NASK. All rights reserved.

from builtins import map                                                         #3--
import hashlib
import re
import string
from inspect import isfunction

import sqlalchemy.sql.naming
from sqlalchemy.schema import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Table,
)
from sqlalchemy.sql.elements import conv

from n6lib.common_helpers import (
    as_bytes,
    ascii_str,
)


def make_metadata_naming_convention():
    # see:
    # * https://docs.sqlalchemy.org/en/latest/core/constraints.html#configuring-constraint-naming-conventions
    # * https://alembic.sqlalchemy.org/en/latest/naming.html#integration-of-naming-conventions-into-operations-autogenerate
    naming_convention = {
        'ix': ('ix'
               '__%(table_abbrev_key)s'
               '__%(all_column_abbrev_names)s'
               '%(optional_suffix_with_abbrev_constraint_name)s'),
        'uq': ('uq'
               '__%(table_abbrev_key)s'
               '__%(all_column_abbrev_names)s'
               '%(optional_suffix_with_abbrev_constraint_name)s'),
        'ck': ('ck'
               '__%(table_abbrev_key)s'
               '__%(all_column_abbrev_names)s'
               '%(optional_suffix_with_abbrev_constraint_name)s'),
        'fk': ('fk'
               '__%(table_abbrev_key)s'
               '__%(all_column_abbrev_names)s'
               '__%(fk_all_target_abbrev_fullnames)s'
               '%(optional_suffix_with_abbrev_constraint_name)s'),
        # Note:
        # no 'pk' as in the case of MariaDB we do not want to specify it
        # (see: https://mariadb.com/kb/en/create-table/#primary-key --
        # in particular, the fragment: "you can specify a name for the
        # index, but it is ignored, and the name of the index is always
        # PRIMARY. [...] a warning is explicitly issued if a name is
        # specified")

        'table_abbrev_key': table_abbrev_key,
        'all_column_abbrev_names': all_column_abbrev_names,
        'fk_all_target_abbrev_fullnames': fk_all_target_abbrev_fullnames,

        # Note: the string used as the following key *must*
        # contain the 'constraint_name' substring, because we want
        # to have a guarantee that our naming convention is applied
        # consistently, no matter whether the constraint is explicitly
        # named or not -- see the implementation of the function
        # `sqlalchemy.sql.naming._constraint_name_for_table()`.
        'optional_suffix_with_abbrev_constraint_name':
            optional_suffix_with_abbrev_constraint_name,
    }
    # noinspection PyProtectedMember
    assert (naming_convention.viewkeys()                                         #3: `viewkeys`->`keys`
            >= set(sqlalchemy.sql.naming._prefix_dict.values()) - {'pk'})
    str = basestring                                                             #3--
    assert all(isinstance(value, str) or (isfunction(value) and
                                          value.__name__ == key)
               for key, value in naming_convention.items()
               if isinstance(key, str))
    assert 'constraint_name' in optional_suffix_with_abbrev_constraint_name.__name__
    return naming_convention


def table_abbrev_key(_constraint, table):
    table_key_parts = _get_table_key_parts(table)
    assert isinstance(table_key_parts, list)
    return _abbrev(table_key_parts)


def all_column_abbrev_names(constraint, table):
    columns = _get_constraint_columns(constraint, table)
    column_names = [col.name for col in columns]
    return _abbrev(column_names)


def fk_all_target_abbrev_fullnames(constraint, _table):
    assert isinstance(constraint, ForeignKeyConstraint)
    target_full_names = [fk.target_fullname for fk in constraint.elements]
    return _abbrev(target_full_names)


def optional_suffix_with_abbrev_constraint_name(constraint, _table):
    name = getattr(constraint, 'name', None)
    assert not isinstance(name, conv), (
        'SQLAlchemy machinery should have ensured that {!r} is *not* '
        'an instance of {!r} -- but it is!'.format(name, conv))
    if (not isinstance(name, (str, unicode))                                     #3: `(str, unicode)` -> `str`
          or name in ('', '_unnamed_')):
        return ''
    # Note: here, to be on a safe side, we want to deal with a str,
    # *not* with some fancy SQLAlchemy-specific subclass of str, so:
    str_name = str(name)
    assert (type(str_name) is str
            and str_name == name)
    abbrev_name = _abbrev([str_name])
    return '__' + abbrev_name


#
# Internal stuff
#

_BESIDES_ASCII_WORDS_AND_ESCAPES_REGEX = re.compile(r'[^\w\\]+', re.ASCII)

_SUPPORTED_NAME_CHARACTERS = frozenset(string.ascii_lowercase + string.digits + '_' + '.')
_ABBREV_NAME_CHARACTERS = frozenset(string.ascii_lowercase + string.digits + '_')

_HASH_SUFFIX_LENGTH = 6


def _get_table_key_parts(table):
    assert isinstance(table, Table)
    key = table.key
    str = basestring                                                             #3--
    assert (isinstance(key, str)
            and (key == table.name
                 or key.endswith('.{}'.format(table.name))))
    return key.split('.')


def _get_constraint_columns(constraint, table):
    if isinstance(constraint, ForeignKeyConstraint):
        columns = [fk.parent for fk in constraint.elements]
    elif isinstance(constraint, CheckConstraint):
        columns = list(constraint.columns)
        if not columns:
            coerced_to_ascii = ascii_str(constraint.sqltext)
            words = _BESIDES_ASCII_WORDS_AND_ESCAPES_REGEX.split(coerced_to_ascii)
            columns = [col for col in table.columns
                       if col.name in words]
    else:
        columns = list(constraint.columns)
    if not columns:
        raise NotImplementedError(
            'unsupported case: constraint {!r} seems '
            'to have no columns'.format(constraint))
    assert (isinstance(columns, list)
            and all(isinstance(col, Column) for col in columns))
    return columns


def _abbrev(names):
    assert isinstance(names, list) and names
    for name in names:
        _verify_name_is_supported(name)
    abbrev_name = _make_abbrev_name(names)
    str = basestring                                                             #3--
    assert (isinstance(abbrev_name, str)
            and abbrev_name
            and _ABBREV_NAME_CHARACTERS.issuperset(abbrev_name))
    return abbrev_name


def _verify_name_is_supported(name):
    str = basestring                                                             #3--
    if not isinstance(name, str):
        raise NotImplementedError(
            'unsupported case: name {!r} is not a `str`'.format(name))
    if not name:
        raise ValueError("'name is empty (that's strange!)'")
    unsupported_characters = set(name) - _SUPPORTED_NAME_CHARACTERS
    if unsupported_characters:
        raise NotImplementedError(
            'name {!r} contains the following unsupported characters: {}'.format(
                name,
                ', '.join(map(repr, sorted(unsupported_characters)))))


def _make_abbrev_name(names):
    hash_of_names = _get_hex_hash_of_names(names)
    abbrev_name_trunk = '_'.join(_iter_abbrev_name_parts(names))
    abbrev_name = '{}_{}'.format(
        abbrev_name_trunk,
        hash_of_names[:_HASH_SUFFIX_LENGTH])
    return abbrev_name


def _get_hex_hash_of_names(names):
    hash_base = as_bytes('-'.join(names))
    return hashlib.sha256(hash_base).hexdigest()


def _iter_abbrev_name_parts(names):
    for name in names:
        yield ''.join(_iter_first_characters_of_words_in(name))


def _iter_first_characters_of_words_in(name):
    name = name.replace('.', ' ')
    name = name.replace('_', ' ')
    words_in_name = name.split()
    for word in words_in_name:
        assert word
        first_char = word[0]
        yield first_char

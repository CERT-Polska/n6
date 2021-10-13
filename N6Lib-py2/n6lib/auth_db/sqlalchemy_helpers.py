# Copyright (c) 2020-2021 NASK. All rights reserved.

from sqlalchemy.exc import DBAPIError
from typing import (
    Any,
    Iterable,
    Iterator,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Type,
)

from n6lib.common_helpers import ascii_str
from n6lib.typing_helpers import String


# See:
# * https://mariadb.com/kb/en/mariadb-error-codes/
# * https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html
MYSQL_ERROR_CODE_BAD_NULL = 1048
MYSQL_ERROR_CODE_BAD_TABLE = 1051
MYSQL_ERROR_CODE_DUP_ENTRY = 1062
MYSQL_ERROR_CODE_WARN_DATA_TRUNCATED = 1265
MYSQL_ERROR_CODE_TRUNCATED_WRONG_VALUE = 1292
# [...more constants can be added here if needed...]


def is_specific_db_error(exc, mysql_error_code):
    # type: (object, int) -> bool
    if isinstance(exc, DBAPIError):
        assert hasattr(exc, 'orig')
        orig_error_args = getattr(exc.orig, 'args', ())
        assert isinstance(orig_error_args, Sequence)
        if orig_error_args and orig_error_args[0] == mysql_error_code:
            return True
    return False


class DuplicateEntryErrorInfo(NamedTuple('DuplicateEntryErrorInfo', [
            ('exc_type', Type[DBAPIError]),
            ('ascii_exc', str),
            ('ascii_message', Optional[str]),
            ('ascii_sql_statement', Optional[str]),
            ('ascii_probable_culprit', Optional[str]),
            ('involved_values', List[Any]),
        ])):

    @classmethod
    def from_exc(cls, exc):
        # type: (BaseException) -> Optional[DuplicateEntryErrorInfo]
        if is_specific_db_error(exc, MYSQL_ERROR_CODE_DUP_ENTRY):
            orig_message = _get_orig_message(exc)
            return cls(
                exc_type=type(exc),
                ascii_exc=ascii_str(exc),
                ascii_message=(ascii_str(orig_message) if orig_message else None),
                ascii_sql_statement=_get_sql_statement_as_ascii(exc),
                ascii_probable_culprit=cls._extract_probable_culprit_as_ascii(orig_message),
                involved_values=list(_iter_involved_values(exc)))
        return None

    def __str__(self):
        friendly_msg = 'duplicate data entry'
        if self.ascii_probable_culprit:
            friendly_msg += (
                ' (the probable culprit value is:'
                ' {})'.format(self.ascii_probable_culprit))
        elif self.involved_values:
            ascii_involved_values = _format_values_as_ascii(self.involved_values)
            assert ascii_involved_values
            if len(self.involved_values) == 1:
                friendly_msg += (
                    ' (the culprit may be the involved value:'
                    ' {})'.format(ascii_involved_values))
            else:
                assert len(self.involved_values) > 1
                friendly_msg += (
                    ' (the culprit may be among the involved values:'
                    ' {})'.format(ascii_involved_values))
        return friendly_msg

    #
    # Private helpers

    @staticmethod
    def _extract_probable_culprit_as_ascii(orig_message):
        if orig_message is None:
            return
        str = basestring                                                         #3--
        assert isinstance(orig_message, str)
        EXPECTED_PREFIX = 'Duplicate entry '
        if orig_message.startswith(EXPECTED_PREFIX):
            rest = orig_message[len(EXPECTED_PREFIX):]
            if rest.startswith("'"):
                return repr(ascii_str(rest.split("'")[1]))
            else:
                rest_parts = rest.split()
                if rest_parts:
                    return ascii_str(rest_parts[0])
        return None


#
# Private helpers
#

def _get_orig_message(exc):
    # type: (DBAPIError) -> Optional[String]
    assert isinstance(exc, DBAPIError)
    assert (hasattr(exc, 'orig')
            and hasattr(exc.orig, 'args')
            and isinstance(exc.orig.args, Sequence))
    str = basestring                                                             #3--
    if len(exc.orig.args) > 1 and isinstance(exc.orig.args[1], str):
        return exc.orig.args[1]
    return None


def _get_sql_statement_as_ascii(exc):
    # type: (DBAPIError) -> Optional[str]
    assert isinstance(exc, DBAPIError)
    assert hasattr(exc, 'statement')
    if exc.statement is not None:
        return ascii_str(exc.statement)
    return None


def _iter_involved_values(exc):
    # type: (DBAPIError) -> Iterator
    assert isinstance(exc, DBAPIError)
    assert hasattr(exc, 'params') and isinstance(exc.params, Iterable)
    return _iter_flattened_non_none(exc.params)


def _iter_flattened_non_none(obj):
    # type: (Any) -> Iterator
    if _is_regular_iterable_collection(obj):
        for o in obj:
            for scalar in _iter_flattened_non_none(o):
                assert not _is_regular_iterable_collection(scalar)
                assert scalar is not None
                yield scalar
    elif obj is not None:
        yield obj


def _format_values_as_ascii(values):
    # type: (Iterable) -> str
    assert _is_regular_iterable_collection(values)
    #return ', '.join(map(ascii, values))                                        #3: uncomment this line and remnove the next statement
    return ', '.join(repr(ascii_str(obj)) if isinstance(obj, basestring)
                     else repr(obj)
                     for obj in values)


def _is_regular_iterable_collection(obj):
    # type: (Any) -> bool
    str = basestring                                                             #3--
    return (isinstance(obj, Iterable)
            and not isinstance(obj, (str, bytes, bytearray, memoryview, Mapping)))

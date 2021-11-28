# Copyright (c) 2020-2021 NASK. All rights reserved.

import csv
import cStringIO                                                                 #3--
from io import StringIO

import sys                                                                       #3--

from n6lib.common_helpers import open_file


def open_csv_file(file, mode=None, **open_kwargs):
    """
    Open a file suitable for a CSV reader's source or writer's target.
    """
    if sys.version_info[0] < 3:                                                  #3--
        # Python 2:                                                              #3--
        if mode is None:                                                         #3--
            mode = 'rb'                                                          #3--
        return open_file(file, mode, **open_kwargs)                              #3--

    # Python 3:
    if mode is None:
        mode = 'r'
    elif 'b' in mode:
        raise ValueError("the given mode ({0!a}) is binary (which is "
                         "not suitable for a CSV reader's source or "
                         "writer's target in Python 3)".format(mode))
    # Important: CSV source/target file should be opened with newline=''
    # (see: https://docs.python.org/3/library/csv.html#module-contents).
    return open_file(file, mode, newline='', **open_kwargs)


def csv_string_io(s=''):
    """
    Make a *String IO* pseudo-file suitable for a CSV reader's source or
    writer's target.

    The function takes one optional argument (a `str`; empty by default)
    and returns an appropriate *String IO* object.
    """
    if sys.version_info[0] < 3:                                                  #3--
        # Python 2:                                                              #3--
        return cStringIO.StringIO(s) if s else cStringIO.StringIO()              #3--

    # Python 3:
    # Important: CSV source/target file should be opened with newline=''
    # (see: https://docs.python.org/3/library/csv.html#module-contents).
    return StringIO(s, newline='')


def split_csv_row(row, delimiter=',', quotechar='"', **kwargs):
    [csv_row] = csv.reader([row], delimiter=delimiter, quotechar=quotechar, **kwargs)
    return csv_row


def extract_field_from_csv_row(row, column_index, **kwargs):
    fields = split_csv_row(row, **kwargs)
    return fields[column_index]


def csv_row_as_dict(field_names, field_values):
    """
    Associate headers with fields to obtain a dictionary.

    Args:
        `field_names` (iterable of `str`):
            Headers (i.e., keys of the resultant dictionary).
        `field_values` (iterable of `str`):
            Fields (i.e., values of the resultant dictionary).

    Returns:
        A dictionary that maps field names (headers) to field values.
    """
    return dict(zip(field_names, field_values))


def strip_fields(fields):
    """
    Strip whitespace from the given string(s).

    Args:
        `fields` (`str` or iterable of `str`):
            Field(s) to be `.strip()`-ed.

    Returns:
        Stripped string (if a single `str` is given) or a list of
        stripped strings (if an iterable providing `str` items is
        given).
    """
    str = basestring                                                             #3--
    return (
        fields.strip() if isinstance(fields, str)
        else [field.strip() for field in fields]
    )

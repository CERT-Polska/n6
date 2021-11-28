# Copyright (c) 2020-2021 NASK. All rights reserved.

import csv
from io import StringIO
from typing import Optional

from n6lib.common_helpers import open_file


def open_csv_file(file, mode='r', **open_kwargs):
    """
    Open a file suitable for a CSV reader's source or writer's target.

    Args/kwargs:
        `file`:
            Typically it is a string specifying the name (path) of the
            file to be opened. For more information, see the docs of the
            built-in function `open()`.
        `mode` (default: `'r'`):
            An optional string that specifies the mode in which the file
            is opened. It should *not* contain `'b'` as then it would
            specify a binary mode which is inappropriate for CSV readers
            and writers. See also: the docs of the built-in function
            `open()`.
        Other optional arguments, only as *keyword* (named) ones:
            See the docs of `n6lib.common_helpers.open_file()`, except
            that the `newline` argument should *not* be given (because
            it will be automatically set to `''`, as that is the
            appropriate setting for CSV readers and writers; see also:
            the docs of the Python's standard library module `csv`.

    Returns:
        A file object (for details, see the docs of the built-in
        function `open()`).

    Raises:
        `ValueError`:
            if the `mode` argument specifies a binary mode (i.e.,
            contains `'b'`).
        `TypeError`:
            if the `newline` argument is given.
        See also: the docs of the built-in function `open()`.
    """
    if 'b' in mode:
        raise ValueError(f"the given mode ({mode!a}) is binary (which "
                         f"is not suitable for a CSV reader's source "
                         f"or writer's target)")
    # Important: CSV source/target file should be opened with newline=''
    # (see: https://docs.python.org/3/library/csv.html#module-contents).
    return open_file(file, mode, newline='', **open_kwargs)


def csv_string_io(s: str = ''):
    """
    Make a *String IO* pseudo-file suitable for a CSV reader's source or
    writer's target.

    The function takes one optional argument (a `str`; empty by default)
    and returns an appropriate `io.StringIO` instance.
    """
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
    return (
        fields.strip() if isinstance(fields, str)
        else [field.strip() for field in fields]
    )

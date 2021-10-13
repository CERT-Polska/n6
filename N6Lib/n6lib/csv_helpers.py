# Copyright (c) 2020-2021 NASK. All rights reserved.

import csv

from n6lib.common_helpers import open_file


def open_csv_file(*args, **kwargs):
    # From the docs: "If *csvfile* is a file object, it should be opened with newline=''."
    # (https://docs.python.org/3/library/csv.html#module-contents)
    return open_file(*args, newline='', **kwargs)


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

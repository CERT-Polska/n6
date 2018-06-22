# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

from n6lib.unit_test_helpers import run_module_doctests

# for convenience and backward-compatibility
from n6sdk.datetime_helpers import *


def date_to_datetime(date):
    """
    Convert a datetime.date to a datetime.datetime, assuming time 00:00.

    Args:
        `date`: datetime.date instance

    Returns:
        A datetime.datetime instance (naive) with time 00:00.

    Raises:
        TypeError for invalid input type.
    """
    return datetime.datetime.combine(date, datetime.time(0, 0))


def parse_iso_date_to_datetime(s, prestrip=True):
    """
    Parse *ISO-8601*-formatted date and convert it to a datetime,
    assuming time 00:00.

    Args:
        `s`: *ISO-8601*-formatted date -- as a string.

    Kwargs:
        `prestrip` (default: True):
            Whether the `strip` method should be called on the
            input string before performing the actual processing.

    Returns:
        A datetime.datetime instance (a naive one).

    Raises:
        ValueError for invalid input.

    This function processes input by calling `parse_iso_date`, and
    `date_to_datetime`.
    """
    return date_to_datetime(parse_iso_date(s, prestrip=prestrip))


if __name__ == '__main__':
    run_module_doctests()

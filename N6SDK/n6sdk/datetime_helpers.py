# Copyright (c) 2013-2021 NASK. All rights reserved.
#
# For some parts of the source code of the FixedOffsetTimezone class:
# Copyright (c) 2001-2014 Python Software Foundation. All rights reserved.
# (For more information -- see the FixedOffsetTimezone's docstring and
# the https://docs.python.org/license.html web page.)


import calendar
import datetime

from n6sdk.regexes import (
    ISO_DATE_REGEX,
    ISO_TIME_REGEX,
    ISO_DATETIME_REGEX,
)


# TODO: replace this with `datetime.timezone` or redefine in terms of it...
# TODO: provide `fold` and any other modern-datetime.tzinfo stuff...
class FixedOffsetTimezone(datetime.tzinfo):

    """
    TZ-info to represent fixed offset in minutes east from UTC.

    The source code of the class has been copied from
    http://docs.python.org/2.7/library/datetime.html#tzinfo-objects,
    then adjusted, enriched and documented.

    >>> tz = FixedOffsetTimezone(180)
    >>> tz
    FixedOffsetTimezone(180)

    >>> import copy
    >>> tz is copy.copy(tz)
    True
    >>> tz is copy.deepcopy(tz)
    True

    >>> dt = datetime.datetime(2014, 5, 31, 1, 2, 3, tzinfo=tz)
    >>> dt.utcoffset()
    datetime.timedelta(seconds=10800)
    >>> dt.dst()
    datetime.timedelta(0)
    >>> dt.tzname()
    '<UTC Offset: +180>'
    >>> dt.astimezone(FixedOffsetTimezone(-60))
    datetime.datetime(2014, 5, 30, 21, 2, 3, tzinfo=FixedOffsetTimezone(-60))
    """

    # FIXME: to make instances picklable a non-argument constructor call needs to be allowed...
    #        (see: https://docs.python.org/3.9/library/datetime.html#datetime.tzinfo)
    def __init__(self, offset):
        self.__ZERO = datetime.timedelta(0)
        self.__offset = offset
        self.__td_offset = datetime.timedelta(minutes=offset)
        self.__name = '<UTC Offset: {0:+04}>'.format(offset)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __repr__(self):
        return '{0}({1!r})'.format(self.__class__.__qualname__,
                                   self.__offset)

    def utcoffset(self, dt):
        return self.__td_offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return self.__ZERO


def int_timestamp_from_datetime(dt):
    """
    Convert a :class:`datetime.datetime` to an `int` representing the
    corresponding UNIX timestamp without the fractional part (i.e., the
    *microsecond* part is omitted).

    Args:
        `dt`:
            A :class:`datetime.datetime` instance: a naive or TZ-aware
            one. **Note:** if it is naive, it will be interpreted as an
            UTC date+time (*not* as a local date+time) -- that is an
            important difference between this function and the standard
            :meth:`datetime.datetime.timestamp` method.

    Returns:
        The equivalent timestamp as an :class:`int` number.

    >>> naive_dt = datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)
    >>> t = int_timestamp_from_datetime(naive_dt)
    >>> t
    1370520837
    >>> datetime.datetime.utcfromtimestamp(t)
    datetime.datetime(2013, 6, 6, 12, 13, 57)

    >>> tzinfo = FixedOffsetTimezone(120)
    >>> tz_aware_dt = datetime.datetime(2013, 6, 6, 14, 13, 57, 654321,
    ...                                 tzinfo=tzinfo)
    >>> t2 = int_timestamp_from_datetime(tz_aware_dt)
    >>> t2
    1370520837
    >>> t2 == t
    True
    >>> utc_naive_dt = datetime.datetime.utcfromtimestamp(t2)
    >>> utc_naive_dt == naive_dt.replace(microsecond=0)
    True
    >>> utc_tzinfo = FixedOffsetTimezone(0)  # just UTC
    >>> utc_tz_aware_dt = utc_naive_dt.replace(tzinfo=utc_tzinfo)
    >>> utc_tz_aware_dt.hour
    12
    >>> tz_aware_dt.hour
    14
    >>> utc_tz_aware_dt == tz_aware_dt.replace(microsecond=0)
    True
    """
    return calendar.timegm(dt.utctimetuple())


def timestamp_from_datetime(dt):
    """
    Convert a :class:`datetime.datetime` to a `float` representing the
    corresponding UNIX timestamp.

    Args:
        `dt`:
            A :class:`datetime.datetime` instance: a naive or TZ-aware
            one. **Note:** if it is naive, it will be interpreted as an
            UTC date+time (*not* as a local date+time) -- that is the
            difference between this function and the standard
            :meth:`datetime.datetime.timestamp` method.

    Returns:
        The equivalent timestamp as a :class:`float` number.

    >>> naive_dt = datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)
    >>> t = timestamp_from_datetime(naive_dt)
    >>> t
    1370520837.751219
    >>> datetime.datetime.utcfromtimestamp(t)
    datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)

    >>> tzinfo = FixedOffsetTimezone(120)
    >>> tz_aware_dt = datetime.datetime(2013, 6, 6, 14, 13, 57, 751219,
    ...                                 tzinfo=tzinfo)
    >>> t2 = timestamp_from_datetime(tz_aware_dt)
    >>> t2
    1370520837.751219
    >>> t2 == t
    True
    >>> utc_naive_dt = datetime.datetime.utcfromtimestamp(t2)
    >>> utc_naive_dt == naive_dt
    True
    >>> utc_tzinfo = FixedOffsetTimezone(0)  # just UTC
    >>> utc_tz_aware_dt = utc_naive_dt.replace(tzinfo=utc_tzinfo)
    >>> utc_tz_aware_dt.hour
    12
    >>> tz_aware_dt.hour
    14
    >>> utc_tz_aware_dt == tz_aware_dt
    True
    """
    int_timestamp = int_timestamp_from_datetime(dt)
    fractional_part = dt.microsecond / 1000000.0
    return int_timestamp + fractional_part


def datetime_utc_normalize(dt):
    """
    Normalize a :class:`datetime.datetime` to a naive UTC one.

    Args:
        `dt`: A :class:`datetime.datetime` instance (naive or TZ-aware).

    Returns:
        An equivalent *naive* :class:`datetime.datetime` instance.

    >>> naive_dt = datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)
    >>> datetime_utc_normalize(naive_dt)
    datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)

    >>> tzinfo = FixedOffsetTimezone(120)
    >>> tz_aware_dt = datetime.datetime(2013, 6, 6, 14, 13, 57, 751219,
    ...                                 tzinfo=tzinfo)
    >>> datetime_utc_normalize(tz_aware_dt)
    datetime.datetime(2013, 6, 6, 12, 13, 57, 751219)
    """
    int_timestamp = int_timestamp_from_datetime(dt)
    utc_dt_without_microsecond = datetime.datetime.utcfromtimestamp(int_timestamp)
    utc_dt_with_microsecond = utc_dt_without_microsecond.replace(microsecond=dt.microsecond)
    return utc_dt_with_microsecond


# TODO -- better tests:
# * translate doctests into unittests
# * add more corner cases
def parse_iso_date(s, prestrip=True):
    """
    Parse *ISO-8601*-formatted date.

    Args:
        `s`: *ISO-8601*-formatted date as a `str`.

    Kwargs:
        `prestrip` (default: :obj:`True`):
            Whether the :meth:`strip` method should be called on the
            input string before performing the actual processing.

    Returns:
        A :class:`datetime.date` instance.

    Raises:
        :exc:`~exceptions.ValueError` for invalid input.

    Intentional limitation: specified date must include unambiguous day
    specification (inputs such as ``'2013-05'`` or ``'2013'`` are not
    supported).

    >>> parse_iso_date('2013-06-12')
    datetime.date(2013, 6, 12)

    >>> parse_iso_date('99991231')
    datetime.date(9999, 12, 31)

    >>> parse_iso_date('2013-W24-3')
    datetime.date(2013, 6, 12)
    >>> datetime.date(2013, 6, 12).isocalendar()    # checking this was OK...
    datetime.IsoCalendarDate(year=2013, week=24, weekday=3)

    >>> parse_iso_date('2013-W01-1')
    datetime.date(2012, 12, 31)
    >>> datetime.date(2012, 12, 31).isocalendar()   # checking this was OK...
    datetime.IsoCalendarDate(year=2013, week=1, weekday=1)

    >>> parse_iso_date('2011-W52-7')
    datetime.date(2012, 1, 1)
    >>> datetime.date(2012, 1, 1).isocalendar()     # checking this was OK...
    datetime.IsoCalendarDate(year=2011, week=52, weekday=7)

    >>> parse_iso_date('2013-001')
    datetime.date(2013, 1, 1)
    >>> parse_iso_date('2013-365')
    datetime.date(2013, 12, 31)
    >>> parse_iso_date('2012-366')   # 2012 was a leap year
    datetime.date(2012, 12, 31)

    >>> parse_iso_date('0000-01-01')     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('13-01-01')       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('01-01-2013')     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-6-01')      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-02-31')     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-W54-1')     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-W22-8')     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-W1-1')      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-W01-01')    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-000')       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-366')       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> parse_iso_date('2013-1')         # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    """
    if prestrip:
        s = s.strip()
    match = ISO_DATE_REGEX.match(s)
    if match:
        return _make_date_from_match(match)
    raise ValueError('could not parse {!a} as ISO date'.format(s))


# TODO: tests
def parse_iso_time(s, prestrip=True):
    """
    Parse *ISO-8601*-formatted time.

    Args:
        `s`: *ISO-8601*-formatted time as a `str`.

    Kwargs:
        `prestrip` (default: :obj:`True`):
            Whether the strip() method should be called on the input string
            before performing the actual processing.

    Returns:
        A :class:`datetime.time` instance (a TZ-aware one if the input
        does include time zone information, otherwise a naive one).

    Raises:
        :exc:`~exceptions.ValueError` for invalid input.

    Intentional limitation: specified time must include at least hour and
    minute. Second, microsecond and timezone information are optional.

    *ISO-8601*-enabled "leap second" (60) is accepted but silently converted
    to 59 seconds + 999999 microseconds.

    The optional fractional-part-of-second part can be specified with bigger
    or smaller precision -- it will always be transformed to microseconds.
    """
    if prestrip:
        s = s.strip()
    match = ISO_TIME_REGEX.match(s)
    if match:
        return _make_time_from_match(match)
    raise ValueError('could not parse {!a} as ISO time'.format(s))


# TODO: tests
def parse_iso_datetime(s, prestrip=True):
    """
    Parse *ISO-8601*-formatted combined date and time.

    Args:
        `s`: *ISO-8601*-formatted combined date and time -- as a `str`.

    Kwargs:
        `prestrip` (default: :obj:`True`):
            Whether the :meth:`strip` method should be called on the
            input string before performing the actual processing.

    Returns:
        A :class:`datetime.datetime` instance (a TZ-aware one if the
        input does include time zone information, otherwise a naive
        one).

    Raises:
        :exc:`~exceptions.ValueError` for invalid input.

    For notes about some limitations -- see :func:`parse_iso_date` and
    :func:`parse_iso_time`.
    """
    if prestrip:
        s = s.strip()
    match = ISO_DATETIME_REGEX.match(s)
    if match:
        d = _make_date_from_match(match)
        t = _make_time_from_match(match)
        if match.group('hour') == '24':
            d += datetime.timedelta(1)
        return datetime.datetime.combine(d, t)
    raise ValueError('could not parse {!a} as ISO combined date + time'
                     .format(s))


# TODO: more tests (and convert doctests into unittests)
def parse_iso_datetime_to_utc(s, prestrip=True):
    """
    Parse *ISO-8601*-formatted combined date and time, and normalize it to UTC.

    Args:
        `s`: *ISO-8601*-formatted combined date and time -- as a `str`.

    Kwargs:
        `prestrip` (default: :obj:`True`):
            Whether the :meth:`strip` method should be called on the
            input string before performing the actual processing.

    Returns:
        A :class:`datetime.datetime` instance (a naive one, normalized
        to UTC).

    Raises:
        :exc:`~exceptions.ValueError` for invalid input.

    This function processes input by calling :func:`parse_iso_datetime`
    and :func:`datetime_utc_normalize`.

    >>> parse_iso_datetime_to_utc('2013-06-13T10:02Z')
    datetime.datetime(2013, 6, 13, 10, 2)

    >>> parse_iso_datetime_to_utc('2013-06-13 10:02')
    datetime.datetime(2013, 6, 13, 10, 2)

    >>> parse_iso_datetime_to_utc('2013-06-13 10:02+02:00')
    datetime.datetime(2013, 6, 13, 8, 2)

    >>> parse_iso_datetime_to_utc('2013-06-13T22:02:04.1234-07:00')
    datetime.datetime(2013, 6, 14, 5, 2, 4, 123400)

    >>> parse_iso_datetime_to_utc('2013-06-13 10:02:04.123456789Z')
    datetime.datetime(2013, 6, 13, 10, 2, 4, 123456)

    >>> parse_iso_datetime_to_utc('  2013-06-13T10:02Z  \t')
    datetime.datetime(2013, 6, 13, 10, 2)

    >>> parse_iso_datetime_to_utc('  2013-06-13T10:02Z  \t', prestrip=False)
    ... # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: ...
    """
    return datetime_utc_normalize(parse_iso_datetime(s, prestrip=prestrip))


# TODO: doc, tests
def parse_python_formatted_datetime(s):
    """
    A limited version of :func:`parse_iso_datetime`: accepts only a
    string in the format: ``%Y-%m-%d %H:%M:%S`` or ``%Y-%m-%d
    %H:%M:%S.%f`` in terms of :meth:`datetime.datetime.strptime`.
    """
    dt_format = ('%Y-%m-%d %H:%M:%S.%f' if '.' in s else '%Y-%m-%d %H:%M:%S')
    return datetime.datetime.strptime(s, dt_format)


# TODO: doc, maybe more tests
def is_datetime_format_normalized(s):
    """
    >>> is_datetime_format_normalized('2013-06-13 10:02:00')
    True
    >>> is_datetime_format_normalized('2013-06-13 10:02:00.123400')
    True

    >>> is_datetime_format_normalized('2013-06-13 10:02')
    False
    >>> is_datetime_format_normalized('2013-06-13 10:02:00.000000')
    False
    >>> is_datetime_format_normalized('2013-06-13 10:02:00.1234')
    False
    >>> is_datetime_format_normalized('2013-06-13 10:02:00.12345678')
    False
    >>> is_datetime_format_normalized('2013-06-13T10:02:00')
    False
    >>> is_datetime_format_normalized('2013-06-13 10:02:00Z')
    False
    """
    try:
        if str(parse_python_formatted_datetime(s)) == s:
            return True
    except ValueError:
        pass
    return False


# TODO: doc, tests
def _make_date_from_match(match):
    g = match.groupdict()
    if g['month']:
        return datetime.date(int(g['year']),
                             int(g['month']),
                             int(g['day']))
    elif g['isoweek']:
        return date_by_isoweekday(int(g['year']),
                                  int(g['isoweek']),
                                  int(g['isoweekday']))
    else:
        year = int(g['year'])
        ordinalday = int(g['ordinalday'])
        if not 1 <= ordinalday <= 366:
            raise ValueError('ordinal day number {!a} is out of '
                             'range 001..366'.format(ordinalday))
        if ordinalday == 366 and not calendar.isleap(year):
            raise ValueError('ordinal day number {!a} is out of range '
                             'for year {!a} (which is not a leap year)'
                             .format(ordinalday, year))
        return date_by_ordinalday(year, ordinalday)


def _make_time_from_match(match):
    g = match.groupdict()
    hour = int(g['hour'])
    if hour == 24:
        hour = 0
    minute = int(g['minute'])
    if g['secondfraction']:
        fract_str = g['secondfraction']
        microsecond = (int(fract_str) * 1000000) // (10 ** len(fract_str))
        microsecond = min(microsecond, 999999)  # must be less than million
    else:
        microsecond = 0
    if g['second']:
        second = int(g['second'])
        if second == 60:  # ISO 'leap second' -- not supported by datetime
            second = 59
            microsecond = max(microsecond, 999999)
    else:
        second = 0
    if g['tzhour']:
        utc_offset = int(g['tzhour']) * 60
        if 'tzminute' in g:
            tzminute = int(g['tzminute'])
            if tzminute > 59:
                raise ValueError('minute part {!a} in time zone designator '
                                 'is out of range 00..59'.format(tzminute))
            if utc_offset >= 0:
                utc_offset += tzminute
            else:
                utc_offset -= tzminute
        tzinfo = FixedOffsetTimezone(utc_offset)
    else:
        tzinfo = None
    return datetime.time(hour, minute, second, microsecond, tzinfo)


# TODO: better doc, tests
def date_by_ordinalday(year, ordinalday):
    """
    Returns:
        An equivalent :class:`datetime.date` instance.
    """
    try:
        return datetime.date(year, 1, 1) + datetime.timedelta(ordinalday - 1)
    except OverflowError as exc:
        raise ValueError(*exc.args)


# TODO: better doc, better tests (see below)
def date_by_isoweekday(isoyear, isoweek, isoweekday):
    """
    Returns:
        An equivalent :class:`datetime.date` instance
        (see: http://en.wikipedia.org/wiki/ISO_week_date).
    """
    if not 1 <= isoweek <= 53:
        raise ValueError('ISO week number {!a} is out of range 01..53'
                         .format(isoweek))
    if not 1 <= isoweekday <= 7:
        raise ValueError('ISO week day number {!a} is out of range 1..7'
                         .format(isoweekday))
    year_specific_correction = datetime.date(isoyear, 1, 4).isoweekday() + 3
    ordinalday = 7 * isoweek + isoweekday - year_specific_correction
    d = date_by_ordinalday(isoyear, ordinalday)
    d_isocalendar = d.isocalendar()
    if d_isocalendar != (isoyear, isoweek, isoweekday):
        assert isoweek == 53 and d_isocalendar == (isoyear + 1, 1, isoweekday)
        raise ValueError('ISO week number {!a} is out of range for ISO-week-'
                         'numbering year {!a}'.format(isoweek, isoyear))
    return d


### XXX: make a unittest from it
def _test_date_by_isoweekday():
    """
    Quick'n'dirty test of date_by_isoweekday().

    >>> _test_date_by_isoweekday()
    """
    from random import randint as r
    for i in range(100000):
        isoyear = r(1, 9998)
        isoweek = r(1, 53)
        isoweekday = r(1, 7)
        try:
            d = date_by_isoweekday(isoyear, isoweek, isoweekday)
        except ValueError:
            # resulting date's year would be > 9999 (illegal for datetime)...
            if (isoyear, isoweek, isoweekday) < (9999, 52, 6):
                # ...or iso_week=53 is too big for a particular iso_year
                assert isoweek == 53
                d2 = date_by_isoweekday(isoyear, 52, isoweekday)
                assert d2.isocalendar() == (isoyear, 52, isoweekday)
        else:
            assert d.isocalendar() == (isoyear, isoweek, isoweekday)

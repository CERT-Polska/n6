# Copyright (c) 2013-2021 NASK. All rights reserved.

import enum

from dateutil.tz import (
    datetime_ambiguous,
    datetime_exists,
    gettz,
)

from n6lib.unit_test_helpers import run_module_doctests
from n6sdk.datetime_helpers import *   # <- for convenience and backward-compatibility


__all__ = [
    # defined in `n6sdk.datetime_helpers`:
    'FixedOffsetTimezone',
    'int_timestamp_from_datetime',
    'timestamp_from_datetime',
    'datetime_utc_normalize',
    'parse_iso_date',
    'parse_iso_time',
    'parse_iso_datetime',
    'parse_iso_datetime_to_utc',
    'parse_python_formatted_datetime',
    'is_datetime_format_normalized',
    'date_by_ordinalday',
    'date_by_isoweekday',

    # defined here:
    'TIME_DELTA_ZERO',
    'TIME_DELTA_ONE_DAY',
    'TIME_DELTA_ONE_HOUR',
    'TIME_DELTA_ONE_MINUTE',
    'TIME_DELTA_ONE_SECOND',
    'TIME_DELTA_ONE_MILLISECOND',
    'TIME_DELTA_ONE_MICROSECOND',
    'ProblematicTimeValueError',
    'ReactionToProblematicTime',
    'datetime_with_tz_to_utc',
    'date_to_datetime',
    'parse_iso_date_to_datetime',
]


TIME_DELTA_ZERO = datetime.timedelta()

TIME_DELTA_ONE_DAY = datetime.timedelta(days=1)
TIME_DELTA_ONE_HOUR = datetime.timedelta(hours=1)
TIME_DELTA_ONE_MINUTE = datetime.timedelta(minutes=1)
TIME_DELTA_ONE_SECOND = datetime.timedelta(seconds=1)
TIME_DELTA_ONE_MILLISECOND = datetime.timedelta(milliseconds=1)
TIME_DELTA_ONE_MICROSECOND = datetime.timedelta(microseconds=1)


class ProblematicTimeValueError(ValueError):
    """
    To be raised by `datetime_with_tz_to_utc()` in the cases
    related to `ReactionToProblematicTime.RAISE_ERROR`.
    """


class ReactionToProblematicTime(enum.Enum):
    PICK_THE_LATER = 1
    PICK_THE_EARLIER = 2
    RELY_ON_OBJECTS = 3
    RAISE_ERROR = 4


def datetime_with_tz_to_utc(dt,
                            tz=None,
                            on_ambiguous_time=ReactionToProblematicTime.PICK_THE_LATER,
                            on_non_existent_time=ReactionToProblematicTime.RAISE_ERROR):
    """
    Convert a date+time, interpreted in the context of a certain time
    zone (obligatorily specified), to the UTC time zone. The result of
    the conversion is represented by a *naive* `datetime.datetime`
    instance.

    This function (*contrary* to `datetime_utc_normalize()`) makes it
    possible to customize behavior for the corner cases related to
    transitions to/from *daylight saving time* (aka DST, aka "summer
    time").

    Terminological note: by a *naive* `datetime.datetime` instance we
    mean such one that does *not* include any time zone information
    (i.e., that has `tzinfo=None`) -- in contrast to an *aware* one
    (i.e., with `tzinfo` set to a *time zone info* object); see:
    https://docs.python.org/3/library/datetime.html#aware-and-naive-objects

    ***

    Args/kwargs:

        `dt` (a `datetime.datetime` or `str`):
            The date+time to be converted.

            **If** the `tz` argument (see below) is also specified (and
            is not `None`) `dt` must be a *naive* `datetime.datetime`;
            **otherwise** `dt` must be an *aware* `datetime.datetime`.

            Alternatively, `dt` can be a `str`; if so, then:

            * the string is required to represent a certain date+time,
              using the *ISO 8601* format (or, more precisely, the subset
              of that format accepted by the `parse_iso_datetime()`
              function);

            * the string *must* include the time zone (offset) part
              **if** the `tz` argument (see below) is left unspecified
              (or is `None`); **otherwise** the string *must not* include
              the time zone part.

        `tz` (a `datetime.tzinfo` or `str`, or `None`):
            Must be left unspecified (or set to `None`) **if** `dt` (see
            above) is either an *aware* `datetime.datetime` or a string
            being *ISO-8601*-compliant date+time representation that
            includes the time zone (offset) part.

            **Otherwise** -- that is, if `dt` does not include the time
            zone information -- it is `tz` that must provide that
            information; if so, then `tz` should be:

            * *either* an instance of any concrete subclass of the
              `datetime.tzinfo` abstract base class (e.g., an instance
              of `n6lib.datetime_helpers.FixedOffsetTimezone`, or an
              object obtained with the `dateutil.tz.gettz()` function);

            * *or* a `str` being a time zone name recognized by the
              `dateutil.tz.gettz()` function (including such names as
              `"Europe/Warsaw"` or `"UTC"`...); note that the exact
              sets of recognized names may vary across systems (see:
              https://dateutil.readthedocs.io/en/stable/tz.html#dateutil.tz.gettz).

        `on_ambiguous_time` (a `ReactionToProblematicTime` enum value):
            Specifies what to do if `dt` represents a date+time that is
            ambiguous because of daylight saving time (DST) intricacies
            (namely, of transition from "summer time" to "winter time").

            One of:

            * `ReactionToProblematicTime.PICK_THE_LATER` **(the default)**
              -- prescribes interpreting such an ambiguity in favor of
              the *later* of the two possible (equally appropriate)
              variants of a corresponding date+time in UTC;

            * `ReactionToProblematicTime.PICK_THE_EARLIER`
              -- prescribes interpreting such an ambiguity in favor of
              the *earlier* of the two possible (equally appropriate)
              variants of a corresponding date+time in UTC;

            * `ReactionToProblematicTime.RELY_ON_OBJECTS`
              -- prescribes relying on the behavior of the
              `datetime.datetime` and `datetime.tzinfo` instances
              being used (in particular, of their `utcoffset()`);
              this will be helpful, especially, if you want to make
              the `dt`'s `fold` attribute be taken into account (see:
              https://docs.python.org/3/library/datetime.html#datetime.datetime.fold
              as well as some of the examples below...);

            * `ReactionToProblematicTime.RAISE_ERROR`
              -- prescribes raising `ProblematicTimeValueError` in the
              face of such an ambiguity (*not* a recommended reaction
              because an *ambiguous* date+time is still a valid datum).

        `on_non_existent_time` (a `ReactionToProblematicTime` enum value):
            Specifies what to do if `dt` represents a date+time that
            *does not exist* in the specified time zone because of
            daylight saving time (DST) intricacies (namely, of
            transition from "winter time" to "summer time").

            One of:

            * `ReactionToProblematicTime.PICK_THE_LATER`
              -- prescribes replacing such a non-existent date+time with
              the *later* of the two candidates for the substitute
              date+time in UTC (see below...);

            * `ReactionToProblematicTime.PICK_THE_EARLIER`
              -- prescribes replacing such a non-existent date+time with
              the *earlier* of the two candidates for the substitute
              date+time in UTC (see below...);

            * `ReactionToProblematicTime.RELY_ON_OBJECTS`
              -- prescribes relying on the behavior of the
              `datetime.datetime` and `datetime.tzinfo` instances
              being used (in particular, of their `utcoffset()`);
              note that in the case of `on_non_existent_time` the
              `dt`'s `fold` attribute is *not* relevant;

            * `ReactionToProblematicTime.RAISE_ERROR` **(the default)**
              -- prescribes raising `ProblematicTimeValueError` if such
              a non-existent date+time is given (this is a *correct*
              reaction because, in fact, such a *non-existent* date+time
              is *not* a valid datum; however, for practical reasons,
              choosing another reaction may also be justified -- it
              depends on what the particular use case is).

            The two aforementioned *candidates for the substitute
            date+time in UTC* are calculated by subtracting the
            time-zone-specific UTC offset from the naive date+time that
            is being converted -- *with* and *without* (respectively)
            daylight-saving-time-specific adjustment.

    Returns:

        A *naive* `datetime.datetime` instance that represents the
        resultant UTC date+time.

    Raises:

        `ValueError`:

            * if `dt` does not include the time zone information *and*
              `tz` is not given (or is `None`);

            * if `dt` includes the time zone information *and* `tz` is
              given (and is not `None`);

            * if `dt` is a string that cannot be parsed by the
              `parse_iso_datetime()` function.

        `ProblematicTimeValueError` (a subclass of `ValueError`):

            * if `on_ambiguous_time` is `ReactionToProblematicTime.RAISE_ERROR`
              *and* `dt` specifies a date+time which is ambiguous in the
              specified time zone (because of DST intricacies);

            * if `on_non_existent_time` is `ReactionToProblematicTime.RAISE_ERROR`
              (the default value of the argument) *and* `dt` specifies a
              date+time which does not exist in the specified time zone
              (because of DST intricacies).

        `LookupError`:

            * if `tz` is a string for whom `dateutil.tz.gettz()` returns
              `None`.

    ***

    Let the examples speak...

    >>> mk_dt = datetime.datetime
    >>> from dateutil.tz import gettz
    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5),                     # CEST (*with* DST)
    ...                         'Europe/Warsaw')
    datetime.datetime(2020, 9, 20, 4, 5)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5),                     # (equivalent)
    ...                         gettz('Europe/Warsaw'))
    datetime.datetime(2020, 9, 20, 4, 5)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5,                      # (equivalent)
    ...                               tzinfo=gettz('Europe/Warsaw')))
    datetime.datetime(2020, 9, 20, 4, 5)

    >>> datetime_with_tz_to_utc(mk_dt(2020, 11, 20, 6, 5),                    # CET (*without* DST)
    ...                         'Europe/Warsaw')
    datetime.datetime(2020, 11, 20, 5, 5)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 11, 20, 6, 5),                    # (equivalent)
    ...                         gettz('Europe/Warsaw'))
    datetime.datetime(2020, 11, 20, 5, 5)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 11, 20, 6, 5,                     # (equivalent)
    ...                               tzinfo=gettz('Europe/Warsaw')))
    datetime.datetime(2020, 11, 20, 5, 5)

    >>> datetime_with_tz_to_utc('2020-10-25 01:38', 'Europe/Warsaw')          # CEST (*with* DST)
    datetime.datetime(2020, 10, 24, 23, 38)
    >>> datetime_with_tz_to_utc('2020-10-25 01:38', gettz('Europe/Warsaw'))   # (equivalent)
    datetime.datetime(2020, 10, 24, 23, 38)

    >>> datetime_with_tz_to_utc('2020-10-25 03:38', 'Europe/Warsaw')          # CET (*without* DST)
    datetime.datetime(2020, 10, 25, 2, 38)
    >>> datetime_with_tz_to_utc('2020-10-25 03:38', gettz('Europe/Warsaw'))   # (equivalent)
    datetime.datetime(2020, 10, 25, 2, 38)

    >>> datetime_with_tz_to_utc('2020-03-29 03:45', 'Europe/Warsaw')          # CEST (*with* DST)
    datetime.datetime(2020, 3, 29, 1, 45)
    >>> datetime_with_tz_to_utc('2020-03-29 03:45', gettz('Europe/Warsaw'))   # (equivalent)
    datetime.datetime(2020, 3, 29, 1, 45)

    >>> datetime_with_tz_to_utc('2020-03-29 01:45', 'Europe/Warsaw')          # CET (*without* DST)
    datetime.datetime(2020, 3, 29, 0, 45)
    >>> datetime_with_tz_to_utc('2020-03-29 01:45', gettz('Europe/Warsaw'))   # (equivalent)
    datetime.datetime(2020, 3, 29, 0, 45)

    >>> tz90 = FixedOffsetTimezone(90)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 11, 20, 6, 5), tz90)          # fixed UTC offset: +1.5h
    datetime.datetime(2020, 11, 20, 4, 35)
    >>> datetime_with_tz_to_utc(mk_dt(2020, 11, 20, 6, 5, tzinfo=tz90))   # (equivalent)
    datetime.datetime(2020, 11, 20, 4, 35)
    >>> datetime_with_tz_to_utc('2020-11-20 06:05+01:30')                 # (equivalent)
    datetime.datetime(2020, 11, 20, 4, 35)

    ***

    A few examples of handling ambiguous date+time (the corner case
    related to transition from "summer time" to "winter time"):

    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.PICK_THE_LATER)
    datetime.datetime(2020, 10, 25, 1, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.PICK_THE_EARLIER)
    datetime.datetime(2020, 10, 25, 0, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 0, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.RAISE_ERROR)           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib.datetime_helpers.ProblematicTimeValueError: ... 2, 38) is ambiguous in time zone...

    As mentioned above, the default value of the `on_ambiguous_time`
    argument is `ReactionToProblematicTime.PICK_THE_LATER` (unlike the
    default value of the `on_non_existent_time` argument!):

    >>> datetime_with_tz_to_utc(mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw')
    datetime.datetime(2020, 10, 25, 1, 38)

    ***

    Note that, when dealing with *ambiguous* times, if `dt`
    (the given `datetime.datetime` object) has the attribute
    `fold=1` it can be taken into account in computation of
    the result -- but *only* if the `on_ambiguous_time` argument
    is set to `ReactionToProblematicTime.RELY_ON_OBJECTS`:

    >>> datetime_with_tz_to_utc(                                  # first look at the results
    ...     mk_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',          # for dt *without* fold=1...
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 0, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 10, 25, 2, 38, tzinfo=gettz('Europe/Warsaw')),
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 0, 38)
    >>> mk_folded_dt = lambda *a, **kw: mk_dt(*a, fold=1, **kw)
    >>> datetime_with_tz_to_utc(                                  # ...and now note the *different*
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',   # results for dt *with* fold=1
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 1, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38, tzinfo=gettz('Europe/Warsaw')),
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 1, 38)

    Let us emphasize it: `dt`'s `fold=1` is *not* relevant if
    the `on_ambiguous_time` argument is set to anything but
    `ReactionToProblematicTime.RELY_ON_OBJECTS`:

    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.PICK_THE_LATER)
    datetime.datetime(2020, 10, 25, 1, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.PICK_THE_EARLIER)
    datetime.datetime(2020, 10, 25, 0, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'Europe/Warsaw',
    ...     on_ambiguous_time=ReactionToProblematicTime.RAISE_ERROR)           # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib.datetime_helpers.ProblematicTimeValueError: ... 38, fold=1) is ambiguous in time zone...

    Note that `fold=1` is *never* preserved in the resultant
    `datetime.datetime` object; even if the resultant date+time
    is equal to the given `dt`:

    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'UTC',
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 10, 25, 2, 38)
    >>> datetime_with_tz_to_utc(
    ...     mk_folded_dt(2020, 10, 25, 2, 38), 'UTC',
    ...     on_ambiguous_time=ReactionToProblematicTime.PICK_THE_LATER)
    datetime.datetime(2020, 10, 25, 2, 38)

    ***

    A few examples of handling non-existent date+time (the corner case
    related to transition from "winter time" to "summer time"):

    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',
    ...     on_non_existent_time=ReactionToProblematicTime.PICK_THE_LATER)
    datetime.datetime(2020, 3, 29, 1, 45)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',
    ...     on_non_existent_time=ReactionToProblematicTime.PICK_THE_EARLIER)
    datetime.datetime(2020, 3, 29, 0, 45)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',
    ...     on_non_existent_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    datetime.datetime(2020, 3, 29, 0, 45)
    >>> datetime_with_tz_to_utc(
    ...     mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',
    ...     on_non_existent_time=ReactionToProblematicTime.RAISE_ERROR)        # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib.datetime_helpers.ProblematicTimeValueError: ... 2, 45) does not exist in time zone...

    As mentioned above, the default value of the `on_non_existent_time`
    argument is `ReactionToProblematicTime.RAISE_ERROR` (unlike the
    default value of the `on_ambiguous_time` argument!):

    >>> datetime_with_tz_to_utc(mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw')    # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    n6lib.datetime_helpers.ProblematicTimeValueError: ... 2, 45) does not exist in time zone...

    ***

    Also, note that `dt`'s `fold=1` (see above...) should *never*
    be relevant when dealing with *non-existent* times -- even if
    the `on_non_existent_time` argument is set to
    `ReactionToProblematicTime.RELY_ON_OBJECTS`:

    >>> datetime_with_tz_to_utc(                                             # (first, passing dt
    ...     mk_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',                      # *without* fold=1 --
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS,     # just for comparison)
    ...     on_non_existent_time=ReactionToProblematicTime.RELY_ON_OBJECTS)
    ...
    datetime.datetime(2020, 3, 29, 0, 45)
    >>> datetime_with_tz_to_utc(                                             # the result for dt
    ...     mk_folded_dt(2020, 3, 29, 2, 45), 'Europe/Warsaw',               # *with* fold=1 is
    ...     on_ambiguous_time=ReactionToProblematicTime.RELY_ON_OBJECTS,     # the same as for dt
    ...     on_non_existent_time=ReactionToProblematicTime.RELY_ON_OBJECTS)  # *without* fold=1
    ...
    datetime.datetime(2020, 3, 29, 0, 45)

    ***

    As mentioned above, if the `tz` argument is `None` (or is not
    specified at all) then the given `datetime.datetime` instance (`dt`)
    must be *aware* (not *naive*); otherwise `ValueError` is raised:

    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5))                      # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: no time zone information given...

    >>> datetime_with_tz_to_utc('2020-09-20 06:05')                            # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: no time zone information given...

    On the other hand, if `tz` is specified (and not `None`) then the
    given `datetime.datetime` instance (`dt`) must be *naive*; otherwise
    `ValueError` is raised:

    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5, tzinfo=FixedOffsetTimezone(90)),
    ...                         'Europe/Warsaw')                               # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: too much time zone information given...

    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5, tzinfo=FixedOffsetTimezone(90)),
    ...                         FixedOffsetTimezone(90))                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: too much time zone information given...

    >>> datetime_with_tz_to_utc('2020-09-20 06:05+01:30',
    ...                         FixedOffsetTimezone(90))                       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: too much time zone information given...

    ***

    If `dt` is a string that cannot be parsed by `parse_iso_datetime()`
    then `ValueError is raised:

    >>> datetime_with_tz_to_utc('Ala ma kota.')                                # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: could not parse 'Ala ma kota.'...

    ***

    If `tz` is a string which is not a known time zone name (i.e.,
    `dateutil.tz.gettz()` returns `None` when applied to that string)
    then `LookupError` is raised:

    >>> datetime_with_tz_to_utc(mk_dt(2020, 9, 20, 6, 5), 'FooBar/Spam')       # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    LookupError: 'FooBar/Spam' is *not* a known time zone name
    """

    #
    # Adjustment and validation of function parameters

    if isinstance(dt, str):
        dt = parse_iso_datetime(dt)

    if tz is None:
        if dt.tzinfo is None:
            raise ValueError('no time zone information given: tz is None '
                             '*and* dt={!a} is a "naive" datetime object '
                             '(i.e., with tzinfo being None)'.format(dt))
        tz = dt.tzinfo
        dt = dt.replace(tzinfo=None)

    else:
        if dt.tzinfo is not None:
            raise ValueError('too much time zone information given: tz is not '
                             'None *and* dt={!a} is an "aware" datetime object '
                             '(i.e., with tzinfo *not* being None)'.format(dt))

        if isinstance(tz, str):
            got_tz = gettz(tz)
            if got_tz is None:
                raise LookupError('{!a} is *not* a known time zone name'.format(tz))
            tz = got_tz

    for reaction_arg_name, reaction_arg in [('on_ambiguous_time', on_ambiguous_time),
                                            ('on_non_existent_time', on_non_existent_time)]:
        if not isinstance(reaction_arg, ReactionToProblematicTime):
            raise TypeError('{}={!a} is not a {} enum instance'.format(
                reaction_arg_name,
                reaction_arg,
                ReactionToProblematicTime.__name__))

    assert (dt is not None and not isinstance(dt, str)
            and dt.tzinfo is None
            and tz is not None and not isinstance(tz, str)
            and isinstance(on_ambiguous_time, ReactionToProblematicTime)
            and isinstance(on_non_existent_time, ReactionToProblematicTime))

    #
    # Helper functions

    def get_actual_utc_offset():
        reaction = get_reaction_if_time_is_problematic()
        if reaction in (None,
                        ReactionToProblematicTime.RELY_ON_OBJECTS):
            return get_offset_for(dt)
        if reaction is ReactionToProblematicTime.RAISE_ERROR:
            raise get_problematic_time_value_error()
        assert reaction in (ReactionToProblematicTime.PICK_THE_EARLIER,
                            ReactionToProblematicTime.PICK_THE_LATER)
        offset_candidates = [
            get_offset_for(find_existing_unambiguous_dt(search_direction='earlier')),
            get_offset_for(find_existing_unambiguous_dt(search_direction='later')),
        ]
        if reaction is ReactionToProblematicTime.PICK_THE_EARLIER:
            return max(offset_candidates)
        return min(offset_candidates)

    def get_reaction_if_time_is_problematic():
        if datetime_ambiguous(dt, tz):
            return on_ambiguous_time
        if not datetime_exists(dt, tz):
            return on_non_existent_time
        return None

    def get_offset_for(some_dt):
        assert some_dt.tzinfo is None
        return some_dt.replace(tzinfo=tz).utcoffset()

    def get_problematic_time_value_error():
        if datetime_ambiguous(dt, tz):
            return ProblematicTimeValueError(
                '{!a} is ambiguous in time zone {!a} (because of '
                'daylight-saving-time intricacies...)'.format(dt, tz))
        else:
            assert not datetime_exists(dt, tz)
            return ProblematicTimeValueError(
                '{!a} does not exist in time zone {!a} (because of '
                'daylight-saving-time intricacies...)'.format(dt, tz))

    def find_existing_unambiguous_dt(search_direction):
        assert search_direction in ('earlier', 'later')
        MAX_ATTEMPTS = 32
        delta = TIME_DELTA_ONE_HOUR
        if search_direction == 'earlier':
            delta = (-delta)
        for i in range(MAX_ATTEMPTS):
            tried_dt = dt + i*delta
            if datetime_exists(tried_dt, tz) and not datetime_ambiguous(tried_dt, tz):
                return tried_dt
        raise RuntimeError('failed to find existing unambiguous datetime '
                           'that would be close enough to dt={!a} (maybe '
                           'class of tz={!a} is defective?)'.format(dt, tz))

    #
    # Actual conversion

    utc_offset = get_actual_utc_offset()
    return dt - utc_offset


def date_to_datetime(date):
    """
    Convert a `datetime.date` to a `datetime.datetime`, assuming time 00:00.

    Args:
        `date`: `datetime.date` instance

    Returns:
        A `datetime.datetime` instance (naive) with time 00:00.

    ***

    Usage examples:

    >>> import datetime

    >>> date_form = datetime.date
    >>> date_to_datetime(date_form(2020,11,24))
    datetime.datetime(2020, 11, 24, 0, 0)

    >>> date_to_datetime(date_form(year=2020, month=11, day=24))
    datetime.datetime(2020, 11, 24, 0, 0)

    ***

    Invalid inputs' type will raise a TypeError exception.
    >>> date_to_datetime('2020,11,24')                                      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    TypeError: combine() argument 1 must be datetime.date, not ...

    >>> date_to_datetime(2020-11-24)                                        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    TypeError: combine() argument 1 must be datetime.date, not ...

    ***

    A date that is out of range will also raise an exception (ValueError).
    >>> date_to_datetime(date_form(2020,14,24))                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: ...
    """

    return datetime.datetime.combine(date, datetime.time(0, 0))


def parse_iso_date_to_datetime(s, prestrip=True):
    """
    Parse an *ISO-8601*-formatted date and convert it to a
    `datetime.datetime` instance, assuming time 00:00.

    Args:
        `s`: *ISO-8601*-formatted date as a `str`.

    Kwargs:
        `prestrip` (default: True):
            Whether the `strip` method should be called on the
            input string before performing the actual processing.

    Returns:
        A `datetime.datetime` instance (a naive one).

    Raises:
        `ValueError` for invalid input.

    This function processes input by applying to its argument the
    'parse_iso_date()' and `date_to_datetime()` functions.

    Usage examples:

    >>> import datetime

    >>> parse_iso_date_to_datetime('2020-11-25')
    datetime.datetime(2020, 11, 25, 0, 0)

    >>> parse_iso_date_to_datetime('2020-W48-3')
    datetime.datetime(2020, 11, 25, 0, 0)

    >>> parse_iso_date_to_datetime('2020-330')
    datetime.datetime(2020, 11, 25, 0, 0)

    >>> parse_iso_date_to_datetime(' 2020-11-25 ')
    datetime.datetime(2020, 11, 25, 0, 0)

    ***

    Prestrip argument.
    >>> parse_iso_date_to_datetime(' 2020-11-25 ', prestrip=False)          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: could not parse ... as ISO date

    ***

    Input should be a full date covering a year, month, and day, otherwise
    it will raise an exception, even though it is a valid ISO-8601-formatted date.

    >>> parse_iso_date_to_datetime('2020-11')                               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: could not parse ... as ISO date

    ***

    A full date is valid only in this order: a year, month, and day.
    >>> parse_iso_date_to_datetime('25-11-2020')                            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError:

    ***

    A date has to be provided correctly.
    >>> parse_iso_date_to_datetime('2020-6-01')                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError: could not parse ... as ISO date

    ***

    A date that is out of range will also raise an exception (ValueError).
    >>> parse_iso_date_to_datetime('2020-12-33')                            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    ValueError:...
    """
    return date_to_datetime(parse_iso_date(s, prestrip=prestrip))


def midnight_datetime(dt):
    """
    Trim a `datetime.datetime`, so that the result's time is 00:00.

    Args:
        `dt`:
            A `datetime.datetime` instance (a naive or TZ-aware one).

    Returns:
        A `datetime.datetime` instance which:

        * denotes midnight (time 00:00) on the date taken from `dt`,
        * has the `fold` attribute set to 0,
        * has the `tzinfo` attribute taken from `dt`.

    ***

    Usage examples:

    >>> import datetime

    >>> dt1 = datetime.datetime(2022, 2, 2, 2, 2)
    >>> dt1
    datetime.datetime(2022, 2, 2, 2, 2)
    >>> midnight_datetime(dt1)
    datetime.datetime(2022, 2, 2, 0, 0)

    >>> dt2 = datetime.datetime(2022, 3, 28, 23, 29, fold=1, tzinfo=FixedOffsetTimezone(120))
    >>> dt2
    datetime.datetime(2022, 3, 28, 23, 29, fold=1, tzinfo=FixedOffsetTimezone(120))
    >>> midnight_datetime(dt2)
    datetime.datetime(2022, 3, 28, 0, 0, tzinfo=FixedOffsetTimezone(120))

    >>> dt3 = datetime.datetime(2022, 1, 28, 22, 34, 59, 279632, tzinfo=FixedOffsetTimezone(-60))
    >>> dt3
    datetime.datetime(2022, 1, 28, 22, 34, 59, 279632, tzinfo=FixedOffsetTimezone(-60))
    >>> midnight_datetime(dt3)
    datetime.datetime(2022, 1, 28, 0, 0, tzinfo=FixedOffsetTimezone(-60))
    """
    return datetime.datetime.combine(dt.date(), datetime.time(0, fold=0), dt.tzinfo)


if __name__ == '__main__':
    run_module_doctests()

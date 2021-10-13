# -*- coding: utf-8 -*-

# Copyright (c) 2019 NASK. All rights reserved.

import collections
import functools
import heapq
import inspect
import signal
import threading
import time
import weakref

from n6corelib.concurrency_helpers import protected_from_concurrency

# ATTENTION:
# Because of the need of some early monkey patching, this module should
# import only standard library modules; that is, it should *not* depend
# on any external libraries or any n6-specific libraries -- **except**
# `n6corelib.concurrency_helpers`.
# (But, of course, other n6 modules *can* import this module.)



#
# Public constants and classes
#

CONCURRENCY_PROTECTION_OPTIONS = dict(
    mutex_key='n6corelib.timeout_callback_manager.TimeoutCallbackManager',
    expiration_timeout=15,
    thread_local_mutexes_and_queues=True,
)



class TimeoutCallbackManager(object):

    """
    A context manager to ensure that the specified `callback` (with the
    specified optional positional and keyword arguments) will be called
    after the specified `timeout` (in seconds) elapses, **unless**,
    earlier, the related `with` block is finished (or `deactivate()`
    is called).

    tl;dr: A nice tool (see the examples below...) but *please read*
    the **Warning** section near the end of this docstring.

    ***

    Constructor args/kwargs:
        `timeout` (int or float):
            See the description above.  The value should be greater
            than or equal to `TimeoutCallbackManager.MINIMAL_TIMEOUT`
            (if smaller it will be automatically set to that constant).
        `callback` (a callable object):
            See the description above.
        Any other positional and/or keyword arguments:
            To be passed into the call of `callback`.

    ***

    Apart from the context manager protocol -- i.e., the `with`-block
    protocol, based on the `__enter__()` and `__exit__()` methods --
    this class provides an alternative interface, consisting of the
    following two methods:

    * `activate()`: the same as `__enter__()` except that `__enter__()`
      returns the `TimeoutCallbackManager` instance, whereas `activate()`
      returns `None`; neither `__enter__()` nor `activate()` should be
      called after an earlier `__enter__()`/`activate()` call on the
      same instance if that earlier call has not been followed by an
      `__exit__()`/`deactivate()` call on the same instance (when this
      constraint is violated `RuntimeError` is raised);

    * `deactivate()`: the same as `__exit__()` except that the former
      can be called on the same instance multiple times consecutively
      and that it returns a `bool` value that indicates whether the
      instance was activated before the call, whereas `__exit__()` does
      not return such an information but, instead, each `__exit__()` on
      a certain `TimeoutCallbackManager` instance must be paired with
      exactly one earlier `__enter__()/`activate()` call on the same
      instance (`RuntimeError` is raised when this constraint is
      violated by a redundant call of `__exit__()` ).

    (Under the hood `__enter__()` makes use  of `activate()`, and
    `__exit__()` makes use of `deactivate()`.)

    ***

    Some examples and comments...

        >>> TimeoutCallbackManager.ensure_preparations_and_monkey_patching_done()
        >>> def callback(msg):
        ...     raise RuntimeError(msg)
        ...
        >>> ticks = []
        >>> with TimeoutCallbackManager(0.35, callback, 'surprise!') as mgr:
        ...     while True:
        ...         time.sleep(0.1)
        ...         ticks.append('tick')            # doctest: +ELLIPSIS
        ...
        Traceback (most recent call last):
          ...
        RuntimeError: surprise!
        >>> mgr.timeout
        0.35
        >>> ticks
        ['tick', 'tick', 'tick']

        >>> mgr.callback is callback
        True
        >>> mgr.callback_args
        ('surprise!',)
        >>> mgr.callback_kwargs
        {}
        >>> mgr
        <TimeoutCallbackManager: 0.35/callback('surprise!') [-]>

    Activities of distinct `TimeoutCallbackManager()` instances can
    freely overlap.  In particular, their `with` blocks can be nested
    (one within another).

        >>> go_on = True
        >>> memo = []
        >>> def goodbye():
        ...     global go_on
        ...     go_on = False
        ...     memo.append('Good bye.')
        ...
        >>> with TimeoutCallbackManager(1, goodbye):
        ...     time.sleep(0.167)
        ...     greeting_mgr = TimeoutCallbackManager(0.33, callback, 'Hi!')
        ...     for i in range(2):
        ...         try:
        ...             print 1, greeting_mgr
        ...             with greeting_mgr:
        ...                 print 2, greeting_mgr
        ...                 while True:
        ...                     try:
        ...                         time.sleep(0.1)
        ...                     except RuntimeError:
        ...                         print 3, greeting_mgr
        ...                         raise
        ...                     memo.append(i)
        ...         except RuntimeError as exc:
        ...             memo.append(str(exc))
        ...             print 4, greeting_mgr
        ...     memo.append("Let's wait...")
        ...     time.sleep(1)
        ...
        1 <TimeoutCallbackManager: 0.33/callback('Hi!') [-]>
        2 <TimeoutCallbackManager: 0.33/callback('Hi!') [+,scheduled]>
        3 <TimeoutCallbackManager: 0.33/callback('Hi!') [+,called]>
        4 <TimeoutCallbackManager: 0.33/callback('Hi!') [-]>
        1 <TimeoutCallbackManager: 0.33/callback('Hi!') [-]>
        2 <TimeoutCallbackManager: 0.33/callback('Hi!') [+,scheduled]>
        3 <TimeoutCallbackManager: 0.33/callback('Hi!') [+,called]>
        4 <TimeoutCallbackManager: 0.33/callback('Hi!') [-]>
        >>> go_on
        False
        >>> memo
        [0, 0, 0, 'Hi!', 1, 1, 1, 'Hi!', "Let's wait...", 'Good bye.']

    Of course, if the `with` block exits before the timeout expires,
    the `callback` is *not* to be called.

        >>> go_on = True
        >>> memo = []
        >>> with TimeoutCallbackManager(1, goodbye):
        ...     time.sleep(0.167)
        ...     greeting_mgr = TimeoutCallbackManager(0.33, callback, 'Hi!')
        ...     for i in range(2):
        ...         try:
        ...             with greeting_mgr:
        ...                 while True:
        ...                     time.sleep(0.1)
        ...                     memo.append(i)
        ...         except RuntimeError as exc:
        ...             memo.append(str(exc))
        ...     memo.append("Let's don't wait!")
        ...
        >>> go_on
        True
        >>> memo
        [0, 0, 0, 'Hi!', 1, 1, 1, 'Hi!', "Let's don't wait!"]

    Also, note that an "outer" timeout can be shorter than an "inner"
    one -- that's OK! For example:

        >>> go_on = True
        >>> memo = []
        >>> with TimeoutCallbackManager(1, goodbye):
        ...     try:
        ...         with TimeoutCallbackManager(2, callback, 'Hi!'):
        ...             while True:
        ...                 t0 = time.time()
        ...                 time.sleep(0.3)
        ...                 print round(time.time() - t0, 1)
        ...                 memo.append(go_on)
        ...     except RuntimeError as exc:
        ...         memo.append(str(exc))
        ...
        0.3
        0.3
        0.3
        0.1
        0.3
        0.3
        0.3
        >>> # ^ note that the 4th `time.sleep(0.3)` call has been interrupted
        >>> # with the incoming signal (without an exception!) -- that's why
        >>> # the 4th printed number is `0.1`, not `0.3` as the others...
        >>> memo
        [True, True, True, 'Good bye.', False, False, False, False, 'Hi!']

    Note that direct use of `activate()` and `deactivate()` makes it
    possible to deal with `TimeoutCallbackManager` instances in even
    less "structured" way.

        >>> class T(float):
        ...     '''A hack to make this doctest 10 x faster...'''
        ...     _FACTOR = 10.0
        ...     @classmethod
        ...     def mk(cls, val): return cls(val / cls._FACTOR)
        ...     def __repr__(self): return str(int(round(self._FACTOR * self)))
        ...
        >>> def t(t0=time.time()):
        ...     print repr(T(time.time() - t0))
        ...
        >>> def sleep(n):
        ...     time.sleep(T.mk(n))
        ...
        >>> t()
        0
        >>> memo = []
        >>> mgr_a = TimeoutCallbackManager(T.mk(3), memo.append, 'a')
        >>> mgr_b = TimeoutCallbackManager(T.mk(2), memo.append, 'b')
        >>> mgr_c = TimeoutCallbackManager(T.mk(5), memo.append, 'c')
        >>> mgr_x = TimeoutCallbackManager(T.mk(1), lambda: memo.append('x') or 1/0)
        >>> mgr_a
        <TimeoutCallbackManager: 3/append('a') [-]>
        >>> t()
        0
        >>> mgr_a.activate()
        >>> mgr_a
        <TimeoutCallbackManager: 3/append('a') [+,scheduled]>
        >>> t()
        0

        >>> sleep(2)
        >>> t()
        2
        >>> memo
        []
        >>> mgr_a.activate()  # illegal: mgr_a is already activated     # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: ... already activated
        >>> mgr_a.__enter__()  # illegal: mgr_a is already activated    # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: ... already activated
        >>> mgr_b.activate()
        >>> mgr_b
        <TimeoutCallbackManager: 2/append('b') [+,scheduled]>
        >>> memo
        []

        >>> sleep(1.5)  # (will be interrupted by mgr_a's alarm)
        >>> t()
        3
        >>> memo
        ['a']
        >>> mgr_a
        <TimeoutCallbackManager: 3/append('a') [+,called]>
        >>> mgr_a.deactivate()  # mgr_a's callback has already been called
        True
        >>> mgr_a
        <TimeoutCallbackManager: 3/append('a') [-]>
        >>> mgr_a.deactivate()  # it is OK to repeat deactivate() calls...
        False
        >>> mgr_a.deactivate()  # it is OK to repeat deactivate() calls...
        False
        >>> mgr_a.deactivate()  # it is OK to repeat deactivate() calls...
        False
        >>> mgr_a.__exit__(None, None, None)  # ...but *not* __exit__()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: ... not activated

        >>> sleep(1.5)  # (will be interrupted by mgr_b's alarm)
        >>> mgr_b
        <TimeoutCallbackManager: 2/append('b') [+,called]>
        >>> mgr_b.deactivate()  # mgr_b's callback has already been called
        True
        >>> mgr_b
        <TimeoutCallbackManager: 2/append('b') [-]>
        >>> t()
        4
        >>> memo
        ['a', 'b']
        >>> mgr_c.activate()
        >>> mgr_b.activate()
        >>> mgr_a.activate()
        >>> mgr_x.activate()
        >>> t()
        4
        >>> memo
        ['a', 'b']

        >>> sleep(1.5)  # (will be interrupted by mgr_x's alarm)   # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ZeroDivisionError: integer division or modulo by zero
        >>> t()
        5
        >>> memo
        ['a', 'b', 'x']
        >>> mgr_b
        <TimeoutCallbackManager: 2/append('b') [+,scheduled]>
        >>> mgr_b.deactivate()  # cancelling mgr_b before its callback is called
        True
        >>> mgr_b
        <TimeoutCallbackManager: 2/append('b') [-]>
        >>> mgr_x.deactivate()  # mgr_x's callback has already been called
        True
        >>> mgr_x.activate()

        >>> sleep(1.5)  # (will be interrupted by mgr_x's alarm)   # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        ZeroDivisionError: integer division or modulo by zero
        >>> memo
        ['a', 'b', 'x', 'x']
        >>> mgr_x.deactivate()  # mgr_x's callback has already been called
        True
        >>> mgr_x.activate()
        >>> mgr_x.deactivate()  # cancelling mgr_x before its callback is called
        True
        >>> t()
        6
        >>> memo
        ['a', 'b', 'x', 'x']

        >>> sleep(2)  # (will be interrupted by mgr_a's alarm)
        >>> t()
        7
        >>> memo
        ['a', 'b', 'x', 'x', 'a']

        >>> sleep(1)
        >>> t()
        8
        >>> memo
        ['a', 'b', 'x', 'x', 'a']
        >>> mgr_a.deactivate()  # mgr_a's callback has already been called
        True
        >>> mgr_a.activate()

        >>> sleep(1.5)  # (will be interrupted by mgr_c's alarm)
        >>> t()
        9
        >>> memo
        ['a', 'b', 'x', 'x', 'a', 'c']

        >>> sleep(2.5)  # (will be interrupted by mgr_a's alarm)
        >>> t()
        11
        >>> memo
        ['a', 'b', 'x', 'x', 'a', 'c', 'a']

        >>> # do *not* try manipulate SIGALRM-related stuff
        >>> # when any TimeoutCallbackManager is active!
        >>> signal.alarm(1)                                             # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: calling signal.alarm() is not allowed now...
        >>> signal.setitimer(signal.ITIMER_REAL, 1.0)                   # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: calling signal.setitimer(signal.ITIMER_REAL, <...>) is not allowed now...
        >>> signal.signal(signal.SIGALRM, signal.SIG_DFL)               # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        RuntimeError: calling signal.signal(signal.SIGALRM, <...>) is not allowed now...

        >>> mgr_a.deactivate()
        True
        >>> mgr_c.deactivate()
        True
        >>> signal.signal(signal.SIGALRM, signal.SIG_DFL)  # now it's OK
        0

    When the `with` block exits, or `deactivate()` is called, and there
    are no other activated instances of TimeoutCallbackManager, the
    context manager/the `deactivate()` method does its best to restore
    the previous SIGALRM handler and the previous alarm setting (i.e.,
    remaining timeout and repeat interval), if any.

        >>> ticks = []
        >>> signal.alarm(1)
        0
        >>> signal.signal(signal.SIGALRM,  # signal.SIG_DFL == 0
        ...               lambda *_: ticks.append('FINAL TICK'))
        0
        >>> with TimeoutCallbackManager(0.35, callback, msg='surprise!'):
        ...     while True:
        ...         time.sleep(0.1)
        ...         ticks.append('tick')                                # doctest: +ELLIPSIS
        ...
        Traceback (most recent call last):
          ...
        RuntimeError: surprise!
        >>> ticks
        ['tick', 'tick', 'tick']
        >>> time.sleep(1)
        >>> # the alarm ordered with signal.alarm(2) finally triggered
        >>> # the handler registered with signal.signal(..., lambda...)
        >>> ticks
        ['tick', 'tick', 'tick', 'FINAL TICK']

        >>> ticks = []
        >>> signal.setitimer(signal.ITIMER_REAL, 0.67)                  # doctest: +ELLIPSIS
        (0.0, 0.0)
        >>> signal.signal(signal.SIGALRM,  # signal.SIG_DFL == 0
        ...               lambda *_: ticks.append('FINAL TICK'))        # doctest: +ELLIPSIS
        <function <lambda> at ...>
        >>> with TimeoutCallbackManager(0.35, callback, msg='surprise!'):
        ...     while True:
        ...         time.sleep(0.1)
        ...         ticks.append('tick')                                # doctest: +ELLIPSIS
        ...
        Traceback (most recent call last):
          ...
        RuntimeError: surprise!
        >>> ticks
        ['tick', 'tick', 'tick']
        >>> time.sleep(0.5)
        >>> # the alarm ordered with signal.alarm(2) finally triggered
        >>> # the handler registered with signal.signal(..., lambda...)
        >>> ticks
        ['tick', 'tick', 'tick', 'FINAL TICK']

        >>> # let's restore the state before signal.signal(..., lambda...)
        >>> signal.signal(signal.SIGALRM, signal.SIG_DFL)                # doctest: +ELLIPSIS
        <function <lambda> at ...>

    ***

    *Note*: when the `callback` is called, that does not, by itself,
    make the `with` block exit.  If such an exit is desired, it is the
    responsibility of the `callback` (which can achieve that by raising
    some exception or changing some state...).

    ***

    **Warning**: this tool is based on the OS signal handling mechanism
    -- namely, custom implementations of `signal.SIGALRM` handler +
    `signal.setitimer(signal.ITIMER_REAL, ...)` + `signal.alarm()` --
    so please take into consideration the following limitations/issues:

    * Instances of this class can be used *only in the main thread*
      (otherwise `RuntimeError` will be raised).

    * While any instance of this class is active any other uses of
      `signal.setitimer(signal.ITIMER_REAL, ...)`, `signal.alarm()`
      or `signal.signal(signal.SIGALRM, ...)` should not by tried
      (or `RuntimeError` will be raised). [This restriction may be
      lifted in some future versions of this module.]

    * As the Python docs state, when "a signal arrives during an I/O
      operation, it is possible that the I/O operation raises an
      exception after the signal handler returns." Especially, there is
      a known problem of interrupting currently executed system calls
      with EINTR; see https://www.python.org/dev/peps/pep-0475/ to find
      out what generally the issue with EINTR is and how it manifests
      itself: a) in Python older than version 3.5; b) in Python 3.5+.

      In practice -- when a signal arrives, then, for example:

      * `time.sleep()` does not raise any exception but returns
        immediately (prematurely!) -- at least in Python 2.7.12 on
        Linux;
      * many other OS/IO-related calls raise, e.g., OSError/IOError
        with errno set to `errno.EINTR` -- at least in Python older
        than 3.5.

      Note that in case of this tool these symptoms will, typically, be
      more visible if `callback` does *not* raise an an exception (if
      it does, the exception raised by the `callback` will typically
      "cover" the exception or strange behaviour caused by the broken
      I/O operation).

    * Because callbacks are called asynchronously, any exception raised
      by such as callback can be thrown in an arbitrary moment from
      the point of view of the currently executed code (always in the
      main thread), potentially breaking some `with`-or-`finally`-based
      invariants.  A similar problem is with the standard Python's
      handler of SIGINT (Ctrl+C signal) that raises `KeyboardInterrupt`
      (the problem is discussed in an interesting way, e.g., here:
      https://vorpus.org/blog/control-c-handling-in-python-and-trio/).

    """

    #
    # Non-public class attributes

    _activated_instances = weakref.WeakSet()

    # necessary to protect our methods from any external
    # signal.alarm()/signal.setitimer() calls in other threads
    _alarm_setting_funcs_mutex = threading.RLock()

    # to be used to preserve alarm handlers/timers that
    # were set externally while no instance was active
    _preserved_alarm_data = None

    # to be set in ensure_preparations_and_monkey_patching_done() (see below...)
    _scheduled_calls = None
    _signal = None
    _setitimer = None


    #
    # Public interface

    MINIMAL_TIMEOUT = 0.01

    def __init__(self, timeout, callback, *callback_args, **callback_kwargs):
        self.timeout = timeout
        self.callback = callback
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
        self._stored_alarm_obj = None
        self._the_call = None

    @property
    def status_tag(self):
        for_self = ('+' if self._is_activated()
                    else '-')
        for_the_call = ('' if self._the_call is None
                        else ',{}'.format(self._the_call.status_tag))
        return for_self + for_the_call

    def __repr__(self):
        return '<{class_name}: {timeout!r}/{callback_repr} [{status_tag}]>'.format(
            class_name=self.__class__.__name__,
            timeout=self.timeout,
            callback_repr=_format_callback_repr(self.callback,
                                                self.callback_args,
                                                self.callback_kwargs),
            status_tag=self.status_tag)

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.deactivate():
            raise RuntimeError('{!r} not activated'.format(self))

    def activate(self):
        self._ensure_correct_context()
        with self._alarm_setting_funcs_mutex:
            self._do_activate()

    def deactivate(self):
        self._ensure_correct_context()
        with self._alarm_setting_funcs_mutex:
            was_already_activated = self._is_activated()
            self._do_deactivate()
            return was_already_activated


    #
    # Internal (non-public) methods

    def _ensure_correct_context(self):
        cls = self.__class__
        base_cls = TimeoutCallbackManager  # <- not the same as `cls` (in subclasses, if any)
        if (cls._scheduled_calls is None
              or cls._signal is None
              or cls._setitimer is None):
            raise RuntimeError(
                'something wrong: it seems that {}.{}.{}() has not '
                'been executed! (at least not successfully)'.format(
                    base_cls.__module__,
                    base_cls.__name__,
                    base_cls.ensure_preparations_and_monkey_patching_done.__name__))
        if not cls._in_main_thread():
            raise RuntimeError(
                '{}.{}: operations allowed only '
                'in the main thread!'.format(
                    base_cls.__module__,
                    base_cls.__name__))

    @protected_from_concurrency(**CONCURRENCY_PROTECTION_OPTIONS)
    def _do_activate(self):
        try:
            self._unset_and_store_alarm()
            if self._is_activated():
                raise _AlreadyActivatedError
            should_set_up = not self._activated_instances
            self._mark_as_activated()
            if should_set_up:
                self._set_up_custom_alarm_stuff()
            self._schedule()
        except _AlreadyActivatedError:
            raise RuntimeError('{!r} already activated'.format(self))
        except:
            self.deactivate()
            raise
        finally:
            self._set_stored_alarm_if_any()

    @protected_from_concurrency(**CONCURRENCY_PROTECTION_OPTIONS)
    def _do_deactivate(self):
        self._unset_alarm_and_store_it_if_not_stored()
        try:
            if self._is_activated():
                self._remove_from_schedule()
                self._mark_as_deactivated()
                if not self._activated_instances:
                    self._reproduce_preserved_alarm_stuff()
                elif self._scheduled_calls:
                    self._store_alarm(self._scheduled_calls.peek_next_deadline() - time.time())
        finally:
            self._set_stored_alarm_if_any()

    def _is_activated(self):
        return self in self._activated_instances

    def _mark_as_activated(self):
        self._activated_instances.add(self)

    def _mark_as_deactivated(self):
        self._activated_instances.discard(self)

    def _unset_and_store_alarm(self):
        self._store_alarm(*self._unset_alarm())

    def _unset_alarm_and_store_it_if_not_stored(self):
        self._store_alarm(*self._unset_alarm(), allow_overwriting=False)

    def _store_alarm(self, timeout, repeat_interval=0, allow_overwriting=True):
        alarm = _Alarm(timeout, repeat_interval)
        if allow_overwriting or self._stored_alarm_obj is None:
            self._stored_alarm_obj = alarm

    def _set_stored_alarm_if_any(self):
        alarm = self._stored_alarm_obj
        try:
            if alarm is not None:
                if alarm.timeout:
                    self._set_nonzero_alarm(alarm.timeout, alarm.repeat_interval)
                else:
                    self._unset_alarm()
        finally:
            self._stored_alarm_obj = None

    def _set_up_custom_alarm_stuff(self):
        custom_handler = self._get_concurrency_protection_wrapped_handler(
            self._custom_alarm_handler_of_TimeoutCallbackManager)
        assert self._stored_alarm_obj
        prev_alarm = self._stored_alarm_obj
        prev_handler = self._signal(signal.SIGALRM, custom_handler)
        self._set_preserved_alarm_data(prev_handler,
                                       prev_alarm.timeout,
                                       prev_alarm.repeat_interval)

    def _reproduce_preserved_alarm_stuff(self):
        preserved = self._preserved_alarm_data
        if preserved is not None:
            assert preserved.handler is not None
            # set the preserved handler as well as timeout and repeat
            # interval (if any; note: if the timeout has already passed
            # it will be set, by `_set_nonzero_alarm()`, to `MINIMAL_TIMEOUT`)
            self._signal(signal.SIGALRM, preserved.handler)
            if preserved.timeout:
                already_elapsed = time.time() - preserved.preserved_at
                self._store_alarm(preserved.timeout - already_elapsed, preserved.repeat_interval)
            else:
                self._store_alarm(0)
            self._clear_preserved_alarm_data()
        else:
            self._store_alarm(0)

    def _schedule(self):
        now = time.time()
        self._the_call = self._scheduled_calls.schedule_new(
            deadline=(now + self.timeout),
            callback=self.callback,
            callback_args=self.callback_args,
            callback_kwargs=self.callback_kwargs)
        self._store_alarm(self._scheduled_calls.peek_next_deadline() - now)

    def _remove_from_schedule(self):
        if self._the_call is not None:
            self._the_call.remove_from_schedule()
            self._the_call = None


    @classmethod
    def _set_nonzero_alarm(cls, timeout, repeat_interval=0):
        actual_timeout = max(cls.MINIMAL_TIMEOUT, timeout)
        cls._setitimer(signal.ITIMER_REAL, actual_timeout, repeat_interval)

    @classmethod
    def _unset_alarm(cls):
        return cls._setitimer(signal.ITIMER_REAL, 0)

    @classmethod
    def _get_concurrency_protection_wrapped_handler(cls, handler):
        if handler is None or handler in (signal.SIG_DFL, signal.SIG_IGN):
            return handler
        wrapped_handler = protected_from_concurrency(handler, **CONCURRENCY_PROTECTION_OPTIONS)
        wrapped_handler._TimeoutCallbackManager__protected_from_concurrency_orig_handler = handler
        return wrapped_handler

    @classmethod
    def _get_concurrency_protection_unwrapped_handler(cls, handler):
        if handler is None or handler in (signal.SIG_DFL, signal.SIG_IGN):
            return handler
        return getattr(handler,
                       '_TimeoutCallbackManager__protected_from_concurrency_orig_handler',
                       handler)

    @classmethod
    def _custom_alarm_handler_of_TimeoutCallbackManager(cls, signum, frame):
        sc = cls._scheduled_calls
        if sc:
            call = sc.peek_next()
            try:
                call.execute(signum, frame)
            finally:
                with cls._alarm_setting_funcs_mutex:
                    if sc and cls._activated_instances:
                        cls._set_nonzero_alarm(sc.peek_next_deadline() - time.time())


    @staticmethod
    def _set_preserved_alarm_data(handler, timeout, repeat_interval):
        base_cls = TimeoutCallbackManager  # <- not the same as `cls` (in subclasses, if any)
        base_cls._preserved_alarm_data = _OrigAlarmData(handler,
                                                        timeout,
                                                        repeat_interval,
                                                        preserved_at=time.time())

    @staticmethod
    def _clear_preserved_alarm_data():
        base_cls = TimeoutCallbackManager  # <- not the same as `cls` (in subclasses, if any)
        base_cls._preserved_alarm_data = None

    @staticmethod
    def _in_main_thread():
        # noinspection PyUnresolvedReferences
        return isinstance(threading.current_thread(), threading._MainThread)


    #
    # Class preparation with external monkey patching

    @staticmethod
    def ensure_preparations_and_monkey_patching_done():
        # should called very early (e.g., in `n6corelib`'s `__init__.py` )
        # -- so that the `signal.getsignal`, `signal.signal`,
        # `signal.alarm` and `signal.setitimer` functions are
        # monkey patched as early as possible

        tcm_cls = TimeoutCallbackManager
        tcm_cls_module = tcm_cls.__module__
        tcm_cls_name = tcm_cls.__name__

        # we check `_setitimer` because it is set in this
        # method as the last attribute (see below...)
        if tcm_cls._setitimer is not None:
            return

        if not tcm_cls._in_main_thread():
            raise RuntimeError(
                '{}.{}.{}() should be called only in the main thread!'.format(
                    tcm_cls_module,
                    tcm_cls_name,
                    tcm_cls.ensure_preparations_and_monkey_patching_done.__name__))

        _SIGALRM = signal.SIGALRM
        _ITIMER_REAL = signal.ITIMER_REAL
        orig_getsignal_func = signal.getsignal
        orig_signal_func = signal.signal
        orig_alarm_func = signal.alarm
        orig_setitimer_func = signal.setitimer

        concurrency_protection_wrapped = tcm_cls._get_concurrency_protection_wrapped_handler
        concurrency_protection_unwrapped = tcm_cls._get_concurrency_protection_unwrapped_handler
        activated_instances = tcm_cls._activated_instances
        alarm_setting_funcs_mutex = tcm_cls._alarm_setting_funcs_mutex

        def custom_wrapper_of(orig_func):
            def decorator(custom):
                if inspect.isbuiltin(orig_func):
                    # without function-to-method transformation
                    custom = functools.update_wrapper(functools.partial(custom), custom)
                return custom
            return decorator

        # our custom wrappers to be used for monkey patching

        @custom_wrapper_of(orig_getsignal_func)
        def _custom_n6tcm_getsignal_wrapper(signalnum):
            with alarm_setting_funcs_mutex:
                if signalnum == _SIGALRM:
                    handler = orig_getsignal_func(signalnum)
                    return concurrency_protection_unwrapped(handler)
                return orig_getsignal_func(signalnum)

        @custom_wrapper_of(orig_signal_func)
        def _custom_n6tcm_signal_wrapper(signalnum, handler):
            with alarm_setting_funcs_mutex:
                if signalnum == _SIGALRM:
                    if activated_instances:
                        raise RuntimeError(
                            'calling signal.signal(signal.SIGALRM, <...>) is not allowed '
                            'now because some {}.{} instances are activated!'.format(
                                tcm_cls_module,
                                tcm_cls_name))
                    handler = concurrency_protection_wrapped(handler)
                    prev_handler = orig_signal_func(signalnum, handler)
                    return concurrency_protection_unwrapped(prev_handler)
                return orig_signal_func(signalnum, handler)

        @custom_wrapper_of(orig_alarm_func)
        def _custom_n6tcm_alarm_wrapper(*args, **kwargs):
            with alarm_setting_funcs_mutex:
                if activated_instances:
                    raise RuntimeError(
                        'calling signal.alarm() is not allowed now because '
                        'some {}.{} instances are activated!'.format(
                            tcm_cls_module,
                            tcm_cls_name))
                return orig_alarm_func(*args, **kwargs)

        @custom_wrapper_of(orig_setitimer_func)
        def _custom_n6tcm_setitimer_wrapper(which, *args, **kwargs):
            with alarm_setting_funcs_mutex:
                if which == _ITIMER_REAL and activated_instances:
                    raise RuntimeError(
                        'calling signal.setitimer(signal.ITIMER_REAL, <...>) is not allowed '
                        'now because some {}.{} instances are activated!'.format(
                            tcm_cls_module,
                            tcm_cls_name))
                return orig_setitimer_func(which, *args, **kwargs)

        # a few sanity checks:

        if tcm_cls._scheduled_calls is not None:
            raise RuntimeError(
                'something strange: {}.{}._scheduled_calls seems to '
                'be already set to some non-`None` value!'.format(
                    tcm_cls_module,
                    tcm_cls_name))

        if (getattr(orig_getsignal_func, '__name__', None)
                == _custom_n6tcm_getsignal_wrapper.__name__):
            raise RuntimeError(
                'something strange: signal.getsignal seems to '
                'be already set to _custom_n6tcm_getsignal_wrapper!')

        if (getattr(orig_signal_func, '__name__', None)
                == _custom_n6tcm_signal_wrapper.__name__):
            raise RuntimeError(
                'something strange: signal.signal seems to '
                'be already set to _custom_n6tcm_signal_wrapper!')

        if (getattr(orig_alarm_func, '__name__', None)
                == _custom_n6tcm_alarm_wrapper.__name__):
            raise RuntimeError(
                'something strange: signal.alarm seems to '
                'be already set to _custom_n6tcm_alarm_wrapper!')

        if (getattr(orig_setitimer_func, '__name__', None)
                == _custom_n6tcm_setitimer_wrapper.__name__):
            raise RuntimeError(
                'something strange: signal.setitimer seems to '
                'be already set to _custom_n6tcm_setitimer_wrapper!')

        # actual monkey patching + completing necessary class attributes:

        signal.getsignal = _custom_n6tcm_getsignal_wrapper
        signal.signal = _custom_n6tcm_signal_wrapper
        signal.alarm = _custom_n6tcm_alarm_wrapper
        signal.setitimer = _custom_n6tcm_setitimer_wrapper

        _orig_handler = orig_getsignal_func(signal.SIGALRM)
        if _orig_handler is not None:
            _wrapped_handler = concurrency_protection_wrapped(
                # (unwrapping before wrapping -- just in case...)
                concurrency_protection_unwrapped(_orig_handler))
            orig_signal_func(signal.SIGALRM, _wrapped_handler)

        tcm_cls._scheduled_calls = _CallSchedule()
        tcm_cls._signal = staticmethod(orig_signal_func)
        tcm_cls._setitimer = staticmethod(orig_setitimer_func)



#
# Non-public auxiliary classes and functions
#

class _AlreadyActivatedError(Exception):
    """Internal exception to be raised and caught in `activate()`..."""


_Alarm = collections.namedtuple('_OrigAlarmData', [
    'timeout',
    'repeat_interval',
])


_OrigAlarmData = collections.namedtuple('_OrigAlarmData', [
    'handler',
    'timeout',
    'repeat_interval',
    'preserved_at',
])



class _HandlerArgForRepr(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{}>'.format(self.name)



class _CallSchedule(object):

    def __init__(self):
        self._calls_heapq = []

    def __repr__(self):
        return '<{class_name}: {seq_of_calls!r}>'.format(
            class_name=self.__class__.__name__,
            seq_of_calls=sorted(self._calls_heapq))

    def __nonzero__(self):
        try:
            self.peek_next()
        except ValueError:
            return False
        return True

    def peek_next_deadline(self):
        call = self.peek_next()
        return call.deadline

    def peek_next(self):
        try:
            while not self._calls_heapq[0]:
                heapq.heappop(self._calls_heapq)
            return self._calls_heapq[0]
        except IndexError:
            raise ValueError('no scheduled calls')

    def schedule_new(self, deadline, callback, callback_args, callback_kwargs,
                     append_handler_args=False):
        # noinspection PyProtectedMember
        call = _Call(deadline, callback, callback_args, callback_kwargs, append_handler_args)
        heapq.heappush(self._calls_heapq, call)
        return call



@functools.total_ordering
class _Call(object):

    _HANDLER_ARGS_FOR_REPR = _HandlerArgForRepr('signum'), _HandlerArgForRepr('frame')

    def __init__(self, deadline, callback, callback_args, callback_kwargs,
                 append_handler_args=False):
        self.deadline = deadline
        self.callback = callback
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
        self.append_handler_args = append_handler_args
        self._scheduled = True
        self._called = False

    @property
    def status_tag(self):
        return ('scheduled' if self._scheduled
                else ('called' if self._called else 'cancelled'))

    def remove_from_schedule(self):
        self._scheduled = False

    def execute(self, signum, frame):
        if self._scheduled:
            actual_args, actual_kwargs = self._prepare_actual_call_arguments(signum, frame)
            self.remove_from_schedule()
            try:
                self.callback(*actual_args, **actual_kwargs)
            finally:
                self._called = True

    def __repr__(self):
        (actual_args,
         actual_kwargs) = self._prepare_actual_call_arguments(*self._HANDLER_ARGS_FOR_REPR)
        callback_repr = _format_callback_repr(
            self.callback,
            actual_args,
            actual_kwargs)
        return '<{class_name}: {deadline}/{callback_repr} [{status_tag}]>'.format(
            class_name=self.__class__.__name__,
            deadline=self.deadline,
            callback_repr=callback_repr,
            status_tag=self.status_tag)

    def _prepare_actual_call_arguments(self, *handler_args):
        completed_callback_args = self.callback_args
        if self.append_handler_args:
            completed_callback_args += handler_args
        return completed_callback_args, self.callback_kwargs

    def __nonzero__(self):
        return self._scheduled

    def __eq__(self, other):
        if isinstance(other, _Call):
            return self is other
        return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if isinstance(other, _Call):
            return self.deadline < other.deadline
        return NotImplemented



def _format_callback_repr(callback, callback_args, callback_kwargs):
    callback_cls = callback.__class__
    callback_cls_name = getattr(callback_cls, '__name__', '...')
    name = _force_asc(getattr(callback, '__name__', callback_cls_name))
    args_repr = ', '.join(map(repr, callback_args))
    kwargs_repr = ', '.join(map(_repr_kw_arg, sorted(callback_kwargs.iteritems())))
    arguments_repr = ', '.join(s for s in [args_repr, kwargs_repr] if s)
    return '{0}({1})'.format(name, arguments_repr)


def _repr_kw_arg(kw_arg):
    return _force_asc('{}={!r}'.format(*kw_arg))


def _force_asc(s):
    return (s.encode('ascii', 'replace') if isinstance(s, unicode)
            else s.decode('ascii', 'replace').encode('ascii', 'replace'))

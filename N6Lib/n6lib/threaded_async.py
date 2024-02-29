# Copyright (c) 2020-2021 NASK. All rights reserved.

# TODO: Here -- in `threaded_async` (+ its client code if needed) --
#       replace `exc_info` tuple handling with exception instance
#       handling (in Py3 exception instances have all information,
#       including traceback...).

import atexit
import sys
import threading
import time
import traceback

from n6lib.common_helpers import make_exc_ascii_str
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class FutureCancelled(Exception):
    """Raised when trying to get the result from a cancelled `Future`."""


class Future(object):

    """
    A `Future` encapsulates an eventual result of some asynchronous
    operation.

    All public methods provided by this class are thread-safe.

    ***

    A `Future` object (hereinafter referred to just as a *future*) is
    always in one of the following 4 states:


    * *unfinished* -- the initial state of every future;

      if a future is in this state, the future's public methods behave
      in the following way:

        * `result()`
          -- blocks until the state changes (then it behaves according
             to the new state...);

        * `done()`
          -- returns `False';

        * `peek_exc_info()`
          -- returns `None';

        * `cancelled()`
          -- returns `False';

        * `sleep_until_cancelled()`
          -- sleeps indefinitely or until the specified time elapses
             (then the method returns `False`), except that the sleep is
             interrupted when the state is changed to *cancelled* (then
             the method immediately returns `True`);

        * `cancel()`
          -- changes the state to *cancelled*;

      you can confirm a future `f` is in this state by testing the condition:
      `not f.done()`


    * *successful* -- entered when the result value is set;

      if a future is in this state, the future's public methods behave
      in the following way:

        * `result()`
          -- returns the result value;

        * `done()`
          -- returns `True';

        * `peek_exc_info()`
          -- returns `None';

        * `cancelled()`
          -- returns `False';

        * `sleep_until_cancelled()`
          -- sleeps indefinitely or until the specified time elapses
             (then the method returns `False`), except that the sleep is
             interrupted when the state is changed to *cancelled* (then
             the method immediately returns `True`);

        * `cancel()`
          -- changes the state to *cancelled*;

      you can confirm a future `f` is in this state by testing the condition:
      `f.done() and not f.peek_exc_info()` (note that this order of the
      component expressions makes the test resistant to race-conditions)


    * *failed* -- entered when the resultant exception is set;

      (this state signals that the operation that was supposed to compute
      the result value could not be completed because of a certain exception);

      if a future is in this state, the future's public methods behave
      in the following way:

        * `result()`
          -- raises the exception;

        * `done()`
          -- returns `True';

        * `peek_exc_info()`
          -- returns the exception info, i.e., a 3-tuple:
             `(<exception type>, <exception value>, <traceback>)`;

        * `cancelled()`
          -- returns `False';

        * `sleep_until_cancelled()`
          -- sleeps indefinitely or until the specified time elapses
             (then the method returns `False`), except that the sleep is
             interrupted when the state is changed to *cancelled* (then
             the method immediately returns `True`);

        * `cancel()`
          -- changes the state to *cancelled*;

      you can confirm a future `f` is in this state by testing the condition:
      `f.peek_exc_info() and not f.cancelled()` (note that this order of the
      component expressions makes the test resistant to race-conditions)


    * *cancelled* -- entered when the future is `cancel()`-ed

      (that can be done, for example, by the thread that created the
      future or the one that was supposed to obtain the result value...);

      if a future is in this state, the future's public methods behave
      in the following way:

        * `result()`
          -- raises `FutureCancelled()`;

        * `done()`
          -- returns `True';

        * `peek_exc_info()`
          -- returns a cancel-specific exception info, i.e., a 3-tuple:
             `(<the FutureCancelled type>, <a FutureCancelled obj>, None)`;

        * `cancelled()`
          -- returns `True';

        * `sleep_until_cancelled()`
          -- returns `True` (immediately);

        * `cancel()`
          -- does nothing.

      you can confirm a future `f` is in this state by testing the condition:
      `f.cancelled()`
    """

    #
    # Public interface

    def __init__(self,
                 cond_var=None,
                 cancel_event=None,
                 repr_token=None):
        """
        Initialization of a new `Future`.

        Args/kwargs:
            cond_var (optional):
                A conditional variable, i.e., a `threading.Condition`
                instance, used to guard the access to the future's state
                data (its resultant value/exception and whether the
                future has been cancelled) and to notify any callers
                blocked on `result()`.  Typically you do not need
                to specify it explicitly; if not given or `None`, a
                `threading.Condition` instance is created automatically.
            cancel_event (optional):
                An event object, i.e., a `threading.Event` instance,
                used internally when dealing with future cancellation
                (in particular, it is an important element of the
                implementation of the `cancel()`, `cancelled()` and
                `sleep_until_cancelled` methods).  Typically you do not
                need to specify it explicitly; if not given or `None`,
                a `threading.Event` instance is created automatically.
            repr_token (optional):
                Can be specified to make the `repr()` of the instance
                more informative.
        """
        if cond_var is None:
            cond_var = threading.Condition()
        if cancel_event is None:
            cancel_event = threading.Event()
        if repr_token is None:
            repr_token = hex(id(self))
        self._cond_var = cond_var
        self._cancel_event = cancel_event
        self._repr_token = repr_token
        self._done = False
        self._res = None
        # (Note: *exc info* tuple, needed in Py2 to remember the
        # traceback, can be replaced just by *exception* in Py3...)
        self._exc_info = None

    @property
    def state_label(self):
        with self._cond_var:
            if self._done:
                if self._cancel_event.is_set():
                    return 'cancelled'
                if self._exc_info is None:
                    return 'successful'
                return 'failed'
            return 'unfinished'

    def __repr__(self):
        return ('<{0.__class__.__qualname__}:'
                ' {0.state_label},'
                ' {0._repr_token}>'.format(self))

    def result(self):
        """
        Block until the result value is available (then return it)
        or an exception is obtained (then raise it -- signalling
        that the operation that was supposed to compute the
        result value could not be completed), or the future is
        cancelled (then raise a `FutureCancelled` exception).

        Returns:
            The future's result value (when it is computed,
            only if the future has *not* been cancelled).

        Raises:
            A `FutureCancelled` exception (when a future is cancelled)
            or the future's resultant exception (when it appears that
            the result value could not be computed, because of that
            exception).
        """
        with self._cond_var:
            while not self._done:
                self._cond_var.wait()
            if self._exc_info is not None:
                assert self._exc_info[1] is not None
                raise self._exc_info[1]
            return self._res

    def peek_result(self, default=None):
        """
        Check, without blocking or raising any exception, if the future
        has already made its result value available (and if that has not
        been spoiled by an exception or cancellation), and what that
        result value is.

        Args/kwargs:
            `default` (optional, defaults to `None`):
                The default value -- to be returned if the actual result
                value cannot be retrieved.

        Returns:
            The future's result value if the check described above is
            successful. Otherwise, the value of `default`.
        """
        with self._cond_var:
            if self._done and self._exc_info is None:
                return self._res
            return default

    def done(self):
        """
        Check, without blocking or raising any exception, if the
        future is no longer waiting for its result (no matter
        whether it has successfully obtained its result value,
        or has got an exception instead, or has been cancelled).

        Returns:
            `True` -- if the future already holds the resultant value
            or exception (the latter can be a `FutureCancelled`
            exception, if the future has been cancelled);

            `False` -- otherwise (i.e., if no resultant value or
            exception has been set yet).
        """
        with self._cond_var:
            return self._done

    def peek_exc_info(self):
        """
        Check, without blocking or raising any exception,
        if the future has been cancelled or has got
        an exception, and what that exception is.

        Returns:
            `None`
            -- if the future is still waiting for its result
            *or* it already has successfully obtained its
            result value (and has *not* been cancelled);

            an exception info, i.e., a 3-tuple:
                (<resultant exception type>,
                 <resultant exception value>,
                 <traceback object>)
            -- if the future has got an exception (which
            informs that the operation that was supposed to
            compute the result value could not be completed)
            and has *not* been cancelled;

            a cancel-specific exception info, i.e., a 3-tuple:
                (<the `FutureCancelled` type>,
                 <a `FutureCancelled` instance>,
                 None)
            -- if the future has been cancelled.
        """
        with self._cond_var:
            return self._exc_info

    def cancelled(self):
        """
        Check, without blocking or raising any
        exception, if the future has been cancelled.
        """
        with self._cond_var:
            return self._cancel_event.is_set()

    def sleep_until_cancelled(self, max_duration=None):
        """
        Sleep indefinitely or until the optional maximum sleep duration
        elapses, except that if the future is cancelled during the
        sleep, the sleep is interrupted immediately; if the future is
        already cancelled when this method is called, the call returns
        without any sleep.

        Args/kwargs:
            max_duration (optional):
                If given and not `None` it should be a `float` or `int`
                that specifies the maximum duration of the sleep, in
                seconds (or fractions thereof).

        Returns:
            `True` if the future is cancelled (in the moment just
            before returning from the function); `False` otherwise.
        """
        if max_duration is not None:
            max_duration = float(max_duration)
        self._cancel_event.wait(max_duration)
        return self.cancelled()

    def cancel(self):
        """
        Change the state of the future to *cancelled* and
        unconditionally and permanently set the future's
        resultant exception to a `FutureCancelled` instance
        (replacing any resultant value or exception,
        even if it is to be or has already been set!).

        Because, typically, a future object is owned by some task
        (i.e., an instance of `Task` or of some subclass of it), we
        can say that the task has been cancelled as well.  If the
        state of the future is set to *cancelled* before the task's
        target function has been invoked it will never be invoked.

        **Note**, however, that cancellation does *not* make the
        task's target function be immediately stopped if it has
        already been invoked; it just makes the state of the future
        be changed (see the description of the `Future` class
        itself) -- and, obviously, the task's target function can
        make use of that (if it has access to the future object).

        Additionally, if the task that owns the future is a
        `LoopedTask` one, cancellation interrupts its main loop
        (more precisely: once the state of the future is set to
        *cancelled*, neither the task's target function nor the
        `loop_iteration_hook` will be invoked anymore, and the loop
        will be finished as soon as the control is returned to it).

        Calling `cancel()` more than once is allowed (just no-op).
        """
        with self._cond_var:
            exc_info = FutureCancelled, FutureCancelled(), None
            just_set = self.__set(exc_info=exc_info)
            if just_set:
                self._cancel_event.set()
        if just_set:
            LOGGER.debug('%a has been cancelled', self)

    #
    # Non-public methods

    # (intended to be referred to only by
    # the classes defined in this module)

    def _set_result(self, res):
        with self._cond_var:
            just_set = self.__set(res=res)
        if just_set:
            LOGGER.debug('%a got result value: %a', self, res)

    def _set_exc_info(self, exc_info):
        with self._cond_var:
            just_set = self.__set(exc_info=exc_info)
        if just_set:
            exc_info_str = ''.join(traceback.format_exception(*exc_info))
            LOGGER.debug('%a got exception:\n%s', self, exc_info_str)

    #
    # Internal helpers

    def __set(self, res=None, exc_info=None):
        if self._cancel_event.is_set():
            return False
        self._res = res
        self._exc_info = exc_info
        self._done = True
        self._cond_var.notify_all()
        return True


class Task(threading.Thread):

    """
    A subclass of `threading.Thread` designed to cooperate with the
    stuff provided by the `Future` class.

    A `Task` instance represents an operation to be executed in the
    background -- in its own thread.  The result of the operation
    can be retrieved via the `Future` instance owned by the task.

    To start execution of the task's target function (in its own
    thread), call the `async_start()` method (typically, you will want
    to do that from the main thread).  It will spawn the operation
    and immediately return the `Future` instance the task owns
    (which will hold the result value if the operation completes, or
    an exception if one is raised, or if the future is cancelled).

    The thread terminates when execution of the operation finishes.
    """

    #
    # Public interface

    def __init__(self, *, target, args=(), kwargs=None,
                 future=None,
                 cancel_and_join_at_python_exit=False,
                 force_daemon=None,
                 initial_sleep=None,
                 initial_trigger_event=None,
                 initial_trigger_event_timeout=30,
                 **other_thread_kwargs):
        """
        Initialization of a new `Task`.

        Kwargs:
            target (required):
                The target function (to be executed in the task's own
                thread).
            args (optional):
                A sequence of positional arguments to be passed to
                the target function.
            kwargs (optional):
                A mapping of keyword arguments to be passed to the
                target function.
            future (optional):
                A `Future` instance to become the future owned by the
                task.  If not given or `None`, a new `Future` instance
                is created automatically.
            cancel_and_join_at_python_exit (optional; default: `False`):
                A flag indicating whether an `atexit` callback shall
                be registered (just before the task is started) that
                will -- when the Python interpreter will be about to
                exit -- automatically try to cancel the task's future
                *and* join the task's thread.  If this argument is
                true, the `daemon` flag of the thread is automatically
                set to `True`; this is necessary because existence
                of any running `Thread` objects with `daemon` set to
                `False` prevents Python from exiting and, consequently,
                prevents all `atexit` callbacks from being called (!).
            force_daemon (optional; default: `None`):
                If given and not `None`, the `daemon` flag of
                the thread (see the documentation of the Python
                standard library's `threading` module...) will
                be set to the value of this argument coerced to
                `bool` (that is, `True` or `False`).  However, it
                *must* be true or `None` (or just unspecified)
                if the `cancel_and_join_at_python_exit` argument
                is true -- otherwise `ValueError` will be raised.
            initial_sleep (optional; default: `None`):
                If given and not `None`, `time.sleep(initial_sleep)`
                will be called in the task's thread before running
                the actual task's operation.
            initial_trigger_event (optional; default: `None`):
                If given and not `None`, its method `wait()`, with the
                value of `initial_trigger_event_timeout` (see below) as
                the sole positional argument, will be called in the
                task's thread before running the actual task's operation
                (but *after* `time.sleep(initial_sleep)` if the argument
                `initial_sleep` is given and not `None`); if the call
                returns false then a `RuntimeError` is raised.
                Typically, `initial_trigger_event` (if not `None`)
                is a `threading.Event` instance.
            initial_trigger_event_timeout (optional; default: `30`):
                If given and not `None`, it is supposed to be an `int`
                or `float` number. See the above description of
                `initial_trigger_event`.
            **other_thread_kwargs (optional):
                Keyword arguments to be passed to `Thread.__init__()`.

        Raises:
            `ValueError` if the `cancel_and_join_at_python_exit`
            argument is true *and* the `force_daemon` argument is
            false and not `None`.

        *Note* that instantiation of a task does not start it; the task
        needs to be started using its `async_start()` method.
        """
        super(Task, self).__init__(**other_thread_kwargs)

        self._modify_daemon_flag_if_necessary(cancel_and_join_at_python_exit,
                                              force_daemon)
        if kwargs is None:
            kwargs = {}
        if future is None:
            future = Future(repr_token=target)
        self._func = target
        self._func_args = args
        self._func_kwargs = kwargs
        self._future = future
        self._cancel_and_join_at_python_exit = cancel_and_join_at_python_exit
        self._initial_sleep = initial_sleep
        self._initial_trigger_event = initial_trigger_event
        self._initial_trigger_event_timeout = initial_trigger_event_timeout

    def __repr__(self):
        repr_text = super(Task, self).__repr__()
        if repr_text.endswith(')>'):
            repr_text = repr_text[:-2] + ', target={!r})>'.format(self._func)
        return repr_text

    def async_start(self):
        """
        Spawn the task's thread in which the target function will be called.

        Returns:
            The future owned by the task, i.e., a `Future` instance that
            will hold the resultant value or exception (once the task is
            finished/cancelled).
        """
        if self._cancel_and_join_at_python_exit:
            @atexit.register
            def try_to_cancel_task_then_join_its_thread():
                self.cancel_and_join(suppress_exc_from_cancel=True)
        self.start()
        return self._future

    def cancel_and_join(self, *, suppress_exc_from_cancel=False):
        """
        Cancel the task's future, then join the task's thread (i.e.,
        wait until it terminates).

        Kwargs:
            `suppress_exc_from_cancel` (optional):
                Whether any `Exception`-derived exceptions from the
                future's `.cancel()` call shall be silently suppressed.
                To ensure that -- set the argument to `True`. To make
                any such exceptions be propagated (*not* suppressed) --
                just leave the argument unspecified (or explicitly set
                it to `False`).
        """
        # noinspection PyBroadException
        try:
            self._future.cancel()
        except Exception:
            if not suppress_exc_from_cancel:
                raise
        self.join()

    #
    # Overridden `Thread` methods

    def run(self):
        LOGGER.debug('Started: %a (with %a)', self, self._future)
        try:
            if self._initial_sleep is not None:
                time.sleep(self._initial_sleep)
            if self._initial_trigger_event is not None:
                timeout = self._initial_trigger_event_timeout
                if not self._initial_trigger_event.wait(timeout):
                    raise RuntimeError(f'initial trigger event timeout ({timeout!a})')
            LOGGER.debug('Starting actual operation of %a...', self)
            self._actual_operation()
        except:
            LOGGER.error('Finishes abruptly: %a (with %a)', self, self._future, exc_info=True)
            raise
        else:
            LOGGER.debug('Finishes normally: %a (with %a)', self, self._future)

    #
    # Non-public methods

    # (intended to be referred to only by this class
    # and/or its subclasses defined in this module)

    def _modify_daemon_flag_if_necessary(self,
                                         cancel_and_join_at_python_exit,
                                         force_daemon):
        if cancel_and_join_at_python_exit:
            if force_daemon or force_daemon is None:
                self.daemon = True
            else:
                # Disallowed combination of arguments:
                # * `cancel_and_join_at_python_exit` is true, *and*
                # * `force_daemon` is explicitly false (not `None`).
                raise ValueError(
                    'the `cancel_and_join_at_python_exit` argument is {!a} '
                    'so the `force_daemon` argument should not be {!a}'.format(
                        cancel_and_join_at_python_exit,
                        force_daemon))
        elif force_daemon is not None:
            self.daemon = bool(force_daemon)

    def _actual_operation(self):
        # noinspection PyBroadException
        try:
            self._run_func()
        except Exception:
            # It is fine to silence the exception here as we
            # have passed it to the future so it will resurface
            # in the thread(s) calling the future's `result()`.
            pass

    def _run_func(self):
        if not self._future.cancelled():
            try:
                res = self._func(*self._func_args, **self._func_kwargs)
            except:
                # noinspection PyProtectedMember
                self._future._set_exc_info(sys.exc_info())
                raise
            else:
                # noinspection PyProtectedMember
                self._future._set_result(res)


class LoopedTask(Task):

    """
    A `LoopedTask` is such a task that, after executing its target
    function once and setting the result value on the owned future,
    executes that function again and again -- in an infinite loop,
    each time setting the future's result value -- *until* the target
    function raises an exception or the future is cancelled.
    """

    def __init__(self, *, loop_iteration_hook, **task_kwargs):
        """
        Initialization of a new `LoopedTask`.

        Kwargs:
            loop_iteration_hook (required):
                A function that takes the `Future` instance owned by
                the task as its only argument.  The function is called
                after each completed iteration (that is, after each
                successful call to the task's target function), unless
                the future has been cancelled.  The hook can be used,
                in particular, to control the time interval between
                consecutive target function calls -- e.g., by using
                the `sleep_until_cancelled()` method of the obtained
                future object.  The hook can even cancel the future (by
                calling its `cancel()` method) if this is what you need.
                *Note:* any `Exception`-based exceptions raised by the
                hook are logged and suppressed (they do *not* stop the
                task's loop).
            **task_kwargs (some required, some optional):
                See the description of `Task.__init__()`.
                Note: the *sleep* (delay) related to the `initial_sleep`
                argument (if given) is one-off, i.e., is *not* part of
                the task's loop.

        Raises:
            See the description of `Task.__init__()`.
        """
        super(LoopedTask, self).__init__(**task_kwargs)
        self.loop_iteration_hook = loop_iteration_hook

    def _actual_operation(self):
        while True:
            # noinspection PyBroadException
            try:
                self._run_func()
                if self._future.cancelled():
                    break
                # noinspection PyBroadException
                try:
                    self.loop_iteration_hook(self._future)
                except Exception:
                    LOGGER.warning(
                        '%a: suppressing exception got from '
                        '`loop_iteration_hook()`: %s',
                        self, make_exc_ascii_str())
            except Exception:
                # It is fine to silence the exception here as we
                # have passed it to the future so it will resurface
                # in the thread(s) calling the future's `result()`.
                break

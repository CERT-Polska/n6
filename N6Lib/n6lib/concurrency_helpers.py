# -*- coding: utf-8 -*-

# Copyright (c) 2019 NASK. All rights reserved.

import collections
import functools
import itertools
import logging
import sys
import threading
import time

# ATTENTION:
# Because this module is used by the `n6lib.timeout_callback_manager`
# module which needs some early monkey patching, this module (that is,
# `n6lib.concurrency_helpers`) should import only standard library
# modules -- that is, it should *not* depend on any external libraries
# or any n6-specific libraries.
# (But, of course, other n6 modules *can* import this module.)



class NonBlockingLockWrapper(object):

    """
    A lock wrapper to acquire a lock in non-blocking manner.

    Constructor args/kwargs:
        `lock`:
            The threading.Lock or threading.RLock instance to be wrapped.
        `lock_description` (optional):
            The lock description (for debug purposes).

    Instance interface includes:
        * the context manager (`with` statement) interface,
        * explicit `acquire()` (argumentless, always non-blocking),
        * explicit `release()`.

    If `lock` cannot be acquired, `RuntimeError` is raised (with
    `lock_description`, if provided, used in the error message).

    Example use:
        my_lock = threading.Lock()  # or threading.RLock()
        ...
        with NonBlockingLockWrapper(my_lock, 'my very important lock')
            ...
    """

    def __init__(self, lock, lock_description=None):
        self.lock = lock
        self._lock_ascii_description = self._make_lock_ascii_description(lock_description)

    def _make_lock_ascii_description(self, lock_description):
        if lock_description is None:
            return repr(self.lock)
        else:
            if isinstance(lock_description, str):
                lock_description = lock_description.decode('utf-8')
            return lock_description.encode('ascii', 'backslashreplace')

    def __enter__(self):
        self.acquire()
        return self.lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        if self.lock.acquire(False):
            return True
        raise RuntimeError('could not acquire {}'.format(self._lock_ascii_description))

    def release(self):
        self.lock.release()



def protected_from_concurrency(func=None,
                               mutex_key=None,
                               propagated_exc=Exception,
                               propagated_base_exc=BaseException,
                               expiration_timeout=None,
                               thread_local_mutexes_and_queues=False):
    """
    A decorator which guarantees protection of the decorated function
    (or method, or other callable) from concurrent execution, **without
    the need of any blocking operations** (such as `Lock.acquire()`).

    Here, "concurrent execution" means: any situation when execution
    of the code of the decorated function and/or of other functions
    decorated using the same `mutex_key` parameter value (see below)
    begins while another execution of such code has not been finished
    (it is not only about threading but also about such stuff as
    recursive calls, as well as calls from signal handlers etc.).

    The protection causes that the following concessions are necessary:

    * the *inner* call, i.e. the call of the original function to which
      this decorator was applied, may be --

      (a) either performed directly -- within its *outer* call, i.e.,
          the call made by the client code (where, what is actually
          called by the client code is the function wrapper that was
          created by applying this decorator);

      (b) or just queued for execution, i.e., designated to be performed
          by another (concurrent) *outer* call (then execution may
          happen even in another thread -- if any *outer* calls are made
          in other threads **and** the `thread_local_mutexes_and_queues`
          argument is false); note that an *inner* call may be performed
          **after** its *outer* call returned (although, most often, it
          will happen very soon).

    * any value returned by the function is ignored; the caller will
      always get a Boolean flag as the return value, indicating one of
      the (a) and (b) cases described above:

      * `True` for (a),

      * `False` for (b).

    ***

    Skipping the details, the core idea is that on each call the
    underlying wrapper that encloses the decorated function performs
    the following steps:

    1) places the call data in the queue of pending calls; the queue is
       specific to the particular `mutex_key` (see below);

    2) tries to acquire a kind of non-blocking mutex, also specific to
       the `mutex_key`, and then, only if managed to acquire the mutex,
       pops and performs (executes) all enqueued calls -- i.e., all calls
       that have been or are being added to the queue of pending calls
       (including all calls that will be being added to it until the
       mutex is released -- see the next step).

    3) releases the mutex.

    ***

    Optional decorator kwargs:

        `mutex_key`:

            If specified as a non-`None` value, it should be an object
            usable as a dictionary key (e.g., a string) -- all
            functions decorated using equal `mutex_key` values will
            share the same mutex and queue of pending calls (with
            the reservation discussed in the description of the
            `thread_local_mutexes_and_queues` argument).

            If not specified (or specified as `None`), it is
            automatically set to the decorated function object itself
            (so that it will not be shared with any other decorated
            functions).

        `propagated_exc` and/or
        `propagated_base_exc`:

            If any (or both) of these arguments is/are specified as a
            non-`None` value(s), it/they should be either an exception
            class or a tuple of such classes -- defining what exceptions
            shall be propagated when an *inner* call (of the original
            function to which this decorator was applied) raises an
            exception.  Any exceptions that do not match these
            parameters will be suppressed, i.e., **not** raised.  (But
            please don't be sad, as for **each** exception a warning
            with a traceback will be logged anyway).

            The following constraints must be satisfied (or `TypeError`
            will be raised when the decorator is applied):

            * `propagated_exc` shall include **only** exception classes
              being (direct or indirect) subclasses of `Exception`.

            * `propagated_base_exc` shall include exception classes
              being (direct or indirect) subclasses of `BaseException`
              but **not** of `Exception` (!).

            The exact procedure of catching and re-raising exceptions
            is the following: when individual inner calls (popped from
            the queue of pending calls, specific to the particular
            `mutex_key`; see the 3-step description above) are
            performed **and** any of these calls raises an exception:

            * being a (direct or indirect) subclass of `Exception`
              **and** matching `propagated_exc`,

            or

            * being a (direct or indirect) subclass of `BaseException`
              **and** matching `propagated_base_exc`,

            -- then the exception will be propagated (i.e., re-raised)
            **after** all calls have been finished, and the mutex has
            been released.

            However, if more than one call raised an exception, **only
            one** of the exceptions will be propagated; it will be
            selected according to the following rules: any exception
            matching `propagated_base_exc` takes precedence over any
            exception matching `propagated_exc`; then, if there is
            still ambiguity, the exception that occurred **earlier**
            takes precedence.

            By default, `propagated_exc` is set to `Exception` and
            `propagated_base_exc` is set to `BaseException` (so
            that **any** exception classes will be qualified as
            *to-be-propagated*).

            Setting any of these arguments to `None` is equivalent to
            setting it to an empty tuple (meaning: no propagation).

            **Warning:** setting the `propagated_base_exc` argument
            to anything that does not cover `SystemExit` and
            `KeyboardInterrupt` (especially to an empty tuple or
            `None`) is *highly discouraged*.

            Note: the `propagated_exc` and `propagated_base_exc`
            arguments are specific to each application of the decorator
            (**not** just to all applications that share a particular
            `mutex_key` value), that is, even if some decorated
            functions share a `mutex_key`, these two arguments can be
            set, for each of the decorated functions, to different
            values.

        `expiration_timeout`:

            Specifying this argument makes it possible to break a
            permanent vacation from performing *inner* calls -- where
            by "permanent vacation" we mean such a state, for a certain
            `mutex_key`, that *inner* calls can only be enqueued and
            never performed, because the mutex can no longer be
            acquired, as it has not been released when it should have
            been, due to some asynchronous breakage in an unfortunate
            moment (where "asynchronous breakage" is typically an
            exception raised by a signal handler; a notable example is
            `KeyboardInterrupt` raised by the default Python's SIGINT
            handler; to learn more about the problem of asynchronous
            exceptions raised by signal handlers -- see:
            https://vorpus.org/blog/control-c-handling-in-python-and-trio/).

            Therefore, the `expiration_timeout` argument, if given as a
            non-`None` value, should be an `int` or `float` specifying
            the number of seconds which, when elapsed since last
            successful acquisition of the mutex, makes the machinery of
            this decorator recognize the acquisition as expired, so
            that the mutex can be forcibly released and re-acquired by
            any *outer* call (i.e., a call of a wrapper of any function
            decorated using the same `mutex_key`).

            Be careful: the number specified as the argument should be
            big enough to make it **improbable** that some pending calls
            of decorated function(s) (using a particular `mutex_key`)
            are still being performed when this number of seconds
            elapsed (since last successful mutex acquisition).  Too
            small number is likely to lead to violation of invariants
            of this decorator's machinery!

            If `expiration_timeout` is not specified (or equal to
            `float('inf')`, or is `None` which is automatically coerced
            to `float('inf')`), there is no such timeout, i.e., the
            mutex, after is was acquired by an *outer* call, cannot --
            no matter how long it has been being acquired -- be forcibly
            acquired (by any other *outer* call) **until** it is
            released by the *outer* call which acquired it.

            It is required that all applications of this decorator
            that share a certain `mutex_key` have equal values of
            `expiration_timeout` (or `ValueError` will be raised when
            discrepancy is detected, when the decorator is applied).

        `thread_local_mutexes_and_queues`:

            If specified as `True` (or another value that is true in
            the Boolean context), for a particular `mutex_key`, there
            will be mutexes and pending calls queues **separate for
            each thread**.

            That means that:

            * there is an additional guarantee: each *inner* call is
              performed **in the same thread** its *outer* call was
              made in;

            * but there is **no protection from concurrent execution in
              different threads** (so you may want to use some other
              mechanism, e.g., a `threading.RLock`, to provide such
              kind of protection).

            The default value of the argument is `False` (meaning that
            all calls of functions decorated using a particular
            `mutex_key` share the same mutex and queue of pending
            calls).

            It is required that all applications of this decorator
            that share a certain `mutex_key` have matching values of
            `thread_local_mutexes_and_queues` (or `ValueError` will be
            raised when discrepancy is detected, when the decorator is
            applied).

    ***

    A simple example:

        @protected_from_concurrency
        def perform_some_sensitive_and_fragile_process(foo, bar=42):
            spam = foo.begin(bar)
            try:
                spam.do_it()
            finally:
                spam.clean_up()


    An example with some keyword arguments (especially, a shared
    `mutex_key`):

        class ParrotDoctor(ParrotResponsibleStuff):

            @protected_from_concurrency(mutex_key='parrot',
                                        expiration_timeout=600,
                                        thread_local_mutexes_and_queues=True)
            def treat_parrot(self, kind_of_surgery):
                with parrot.surgery(kind_of_surgery) as operation:
                    operation.perform_carefully()

            @protected_from_concurrency(mutex_key='parrot',
                                        propagated_exc=(TooHardNutsError,
                                                        BellyacheError),
                                        expiration_timeout=600,
                                        thread_local_mutexes_and_queues=True)
            def feed_parrot(self, food='nuts'):
                while parrot.is_hungry():
                    parrot.feed(food)

    """

    if func is None:
        # (let's handle use of the decorator with keyword arguments)
        return functools.partial(protected_from_concurrency,
                                 mutex_key=mutex_key,
                                 propagated_exc=propagated_exc,
                                 propagated_base_exc=propagated_base_exc,
                                 expiration_timeout=expiration_timeout,
                                 thread_local_mutexes_and_queues=thread_local_mutexes_and_queues)


    #
    # Preliminary stuff

    # * external tools

    # note: here we use `logging.getLogger()` on purpose
    # (*not* `n6lib.logging_helpers.get_logger()`) [see
    # the comment near the beginning of this source file]
    LOGGER = logging.getLogger(__name__)

    get_time = time.time
    itertools_count = itertools.count

    # * classes and data objects:

    ThisCallAlreadyPopped = _protected_from_concurrency__ThisCallAlreadyPopped
    MultiThreadLocalDeque = _protected_from_concurrency__MultiThreadLocalDeque
    CallLike = _protected_from_concurrency__CallLike
    Call = _protected_from_concurrency__Call

    mutex_key_to_call_data = _protected_from_concurrency__mutex_key_to_call_data

    if mutex_key is None:
        mutex_key = func

    if expiration_timeout is None:
        expiration_timeout = float('inf')

    pending_calls_queue_factory = (MultiThreadLocalDeque if thread_local_mutexes_and_queues
                                   else collections.deque)
    (_stored_expiration_timeout,
     pending_calls) = mutex_key_to_call_data.setdefault(mutex_key, (expiration_timeout,
                                                                    pending_calls_queue_factory()))

    # * validation of some arguments:

    if propagated_exc is None:
        propagated_exc = ()
    if not isinstance(propagated_exc, tuple):
         propagated_exc = (propagated_exc,)
    if not all(isinstance(exc_type, type) and issubclass(exc_type, Exception)
               for exc_type in propagated_exc):
        raise TypeError(
            'wrong propagated_exc={!r}: found '
            'non-subclass of Exception'.format(propagated_exc))

    if propagated_base_exc is None:
        propagated_base_exc = ()
    if not isinstance(propagated_base_exc, tuple):
         propagated_base_exc = (propagated_base_exc,)
    if not all(isinstance(exc_type, type) and issubclass(exc_type, BaseException)
               for exc_type in propagated_base_exc):
        raise TypeError(
            'wrong propagated_base_exc={!r}: found '
            'non-subclass of BaseException'.format(propagated_base_exc))
    if any(issubclass(exc_type, Exception) for exc_type in propagated_base_exc):
        raise TypeError(
            'wrong propagated_base_exc={!r}: found '
            'subclass of Exception'.format(propagated_base_exc))

    if expiration_timeout != _stored_expiration_timeout:
        raise ValueError(
            'expiration_timeout={!r} is not equal '
            'to the value {!r} already stored for '
            'the mutex_key={!r}'.format(
                expiration_timeout,
                _stored_expiration_timeout,
                mutex_key))
    # (they are equal but -- just to keep things consistent --
    # let the stored object be used as `expiration_timeout`)
    expiration_timeout = _stored_expiration_timeout

    if thread_local_mutexes_and_queues:
        if isinstance(pending_calls, collections.deque):
            raise ValueError(
                'thread_local_mutexes_and_queues being true ({!r})'
                'does not match a false value of this flag '
                'already used for the mutex_key={!r}'.format(
                    thread_local_mutexes_and_queues,
                    mutex_key))
        assert isinstance(pending_calls, MultiThreadLocalDeque)
    else:
        if isinstance(pending_calls, MultiThreadLocalDeque):
            raise ValueError(
                'thread_local_mutexes_and_queues being false ({!r})'
                'does not match a true value of this flag '
                'already used for the mutex_key={!r}'.format(
                    thread_local_mutexes_and_queues,
                    mutex_key))
        assert isinstance(pending_calls, collections.deque)


    #
    # Helper functions

    def new_pending_call(**kwargs):
        call = Call(timestamp=get_time(), logger=LOGGER, **kwargs)
        pending_calls.append(call)
        return call

    def get_previous_pending_calls(this_call):
        return set(_iter_previous_pending_calls(this_call))

    def _iter_previous_pending_calls(this_call):
        for i in itertools_count():
            try:
                call = pending_calls[i]
            except IndexError:
                # although `this_call` was recently appended to `pending_calls`
                # now it has *not* been found there -> that means that in the
                # meantime it has been popped...
                raise ThisCallAlreadyPopped
            if call is this_call:
                return
            yield call
        assert False, 'can never be here'

    def empty_or_all_expired(calls):
        exp_timestamp_threshold = get_time() - expiration_timeout
        return all(c.timestamp < exp_timestamp_threshold
                   for c in calls)

    def pop_and_perform_pending_calls(this_call):
        sentinel_pseudo_call = _new_sentinel_pseudo_call(this_call)
        exc_info = base_exc_info = e_type = e = tb = None
        try:
            while True:
                call = _pop_next_pending_call()
                if call is sentinel_pseudo_call:
                    break
                exc_info, base_exc_info = call(exc_info, base_exc_info)
            # now we can assume that `pending_calls` has been
            # emptied -- and that means that our imaginary mutex
            # has been released (however, we cannot place here
            # an assert that would confirm that, because it
            # could fail do to a race: it might be very soon
            # made non-empty by a concurrent wrapper call...)
            if base_exc_info is not None:
                e_type, e, tb = base_exc_info
                raise e_type, e, tb
            if exc_info is not None:
                e_type, e, tb = exc_info
                raise e_type, e, tb
        finally:
            # let's break any traceback-related reference cycles
            del exc_info, base_exc_info, e_type, e, tb

    def _new_sentinel_pseudo_call(this_call):
        sentinel_pseudo_call = CallLike(timestamp=this_call.timestamp)
        pending_calls.appendleft(sentinel_pseudo_call)
        return sentinel_pseudo_call

    def _pop_next_pending_call():
        try:
            return pending_calls.pop()
        except IndexError:
            raise RuntimeError(_format_violated_invariant_error_msg('no pending calls'))

    def _format_violated_invariant_error_msg(unexpected_condition_descr=None):
        about_expiration_timeout = (
            ' (maybe expiration_timeout={!r} is too small?!)'.format(expiration_timeout)
            if expiration_timeout != float('inf')
            else '')
        about_unexpected_condition = (
            ' [unexpected condition: {}]'.format(unexpected_condition_descr)
            if unexpected_condition_descr
            else '')
        return (
            '`@protected_from_concurrency`-specific invariant '
            'has been violated for mutex_key={!r}{}{}'.format(
                mutex_key,
                about_expiration_timeout,
                about_unexpected_condition))


    #
    # The actual wrapper

    def wrapper(*args, **kwargs):
        this_call = new_pending_call(func=func,
                                     args=args,
                                     kwargs=kwargs,
                                     propagated_exc=propagated_exc,
                                     propagated_base_exc=propagated_base_exc)
        try:
            previous_calls = get_previous_pending_calls(this_call)
        except ThisCallAlreadyPopped:
            # we detected that `this_call` has already been
            # popped from `pending_calls` -> that means that
            # `pop_and_perform_pending_calls()` has been or is
            # just being executed concurrently and, therefore, that
            # `this_call` has been/is being/is shortly to be handled
            # by another (concurrent) outer call -> so we do not need
            # to do anything more
            return False
        if empty_or_all_expired(previous_calls):
            # `this_call` is the first (the leftmost) of non-"aged"
            # call, i.e., the one that acquired our imaginary mutex ->
            # that means that it is our responsibility to handle all
            # pending calls...
            pop_and_perform_pending_calls(this_call)
            return True
        # `this_call` was *not* the first (the leftmost) non-"aged"
        # call in `pending_calls`, i.e., we detected presence of some
        # other non-"aged" call(s) before (to the left of) it -> that
        # means that `this_call` has been/is being/is shortly to be
        # handled by another (concurrent) outer call -> so we do not
        # need to do anything more
        return False

    try:
        functools.update_wrapper(wrapper, func)
    except Exception:
        pass

    return wrapper


#
# `protected_from_concurrency()`'s private classes and data objects

class _protected_from_concurrency__ThisCallAlreadyPopped(Exception):
    """
    To be raised when detected -- while trying to collect all calls
    previous to the given one -- that the given call has already been
    popped.
    """


class _protected_from_concurrency__MultiThreadLocalDeque(threading.local):

    def __init__(self,
                 __make_deque=collections.deque):
        self._deque = __make_deque()

    def __getattr__(self, name):
        return getattr(self._deque, name)

    def __getitem__(self, index):
        return self._deque[index]


class _protected_from_concurrency__CallLike(object):

    repr_pattern = '<{ident} [{timestamp!r}]>'

    def __init__(self, timestamp):
        self.timestamp = timestamp

    def __call__(self, exc_info, base_exc_info):
        return exc_info, base_exc_info

    def __repr__(self):
        return self.repr_pattern.format(ident=object.__repr__(self).rstrip('<>'),
                                        **vars(self))


class _protected_from_concurrency__Call(_protected_from_concurrency__CallLike):

    repr_pattern = ('<{ident} [{timestamp!r}]: {_func!r}(*{_args!r}, **{_kwargs!r}); '
                    'propagated_exc={_propagated_exc!r}; '
                    'propagated_base_exc={_propagated_base_exc!r}>')

    def __init__(self, func, args, kwargs, propagated_exc, propagated_base_exc, logger, **kw):
        super(_protected_from_concurrency__Call, self).__init__(**kw)
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._propagated_exc = propagated_exc
        self._propagated_base_exc = propagated_base_exc
        self._logger = logger

    def __call__(self, exc_info, base_exc_info,
                 __get_exc_info=sys.exc_info):
        try:
            try:
                self._func(*self._args, **self._kwargs)
            except Exception as e:
                self._logger.warning('Exception %r '
                                    '(being a direct or indirect '
                                    'instance of `Exception`) '
                                    'raised by the call %r',
                                     e, self, exc_info=True)
                if exc_info is None and isinstance(e, self._propagated_exc):
                    exc_info = __get_exc_info()
            except BaseException as e:
                self._logger.warning('Exception %r '
                                    '(being a direct or indirect '
                                    'instance of `BaseException`, '
                                    'but not of `Exception`) '
                                    'raised by the call %r',
                                     e, self, exc_info=True)
                if base_exc_info is None and isinstance(e, self._propagated_base_exc):
                    base_exc_info = __get_exc_info()
            return exc_info, base_exc_info
        finally:
            # let's break any traceback-related reference cycles
            del exc_info, base_exc_info


_protected_from_concurrency__mutex_key_to_call_data = {}

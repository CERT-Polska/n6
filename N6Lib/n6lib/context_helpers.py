# Copyright (c) 2019-2021 NASK. All rights reserved.

import threading

from n6lib.common_helpers import (
    ThreadLocalNamespace,
    ascii_str,
    make_exc_ascii_str,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class ContextManagerIsNotReentrantError(TypeError):

    """
    Raised when a client code that uses a *non-reentrant* context manager,
    whose implementation makes use of `ThreadLocalContextDeposit`, tries
    to use that manager as a *reentrant* one.

    For more details -- see: `ThreadLocalContextDeposit.on_enter()` (in
    particular, the description of the `context_factory` parameter).
    """


class NoContextToExitFrom(RuntimeError):

    """
    Raised when the `__exit__()` method of a context manager, whose
    implementation makes use of `ThreadLocalContextDeposit`, is called
    but there is no context to exit from (no corresponding call to
    `__enter__()` was previously made).
    """


class ContextManagerForcedExit(Exception):

    """
    Used by the `force_exit_on_any_remaining_entered_contexts()`
    function as the exception passed into context manager's
    `__exit__()`.
    """


class ThreadLocalContextDeposit(ThreadLocalNamespace):

    """
    A utility class that makes it easy to implement context managers
    that need to deal with some resources (e.g., database stuff) in a
    thread-safe way -- by storing and maintaining any context-related
    state *separately* in each thread.

    Moreover, using an instance of this class can be helpful in
    implementing such context managers that support using an instance
    of such a manager with nested `with`s (so called reentrant context
    managers; see: https://docs.python.org/3/library/contextlib.html#reentrant-context-managers).
    The tools this class provides make it easy to handle context data
    by pushing them to and popping them from an automatically
    maintained thread-local stack.

    Some tools to implement *explicitly non-reentrant* context managers
    are also provided (see also: `ContextManagerIsNotReentrantError`).

    ***

    Here a short note about the terminology is necessary:

    * whenever we say about a *context manager*, we use this term in
      its well established meaning -- described, for example, here:
      https://docs.python.org/library/stdtypes.html#context-manager-types

    * whenever we say about a *context data object* or *context data*,
      or just a *context*, we refer to an object which represents the
      data/state that needs to be stored during the lifetime of whatever
      is *entered* and *exited* by your context manager; the type of a
      *context data object* is not constrained -- it can be anything,
      depending on the desired semantics and implementation of your
      context manager (in some cases it can be just `None` -- if no data
      need to be stored under the hood between your context manager's
      `__enter__()` and `__exit__(...)` calls).

    ***

    The public interface that this class defines includes:

    * the constructor (`ThreadLocalContextDeposit`) -- intended to be
      called in the `__init__()` method of your context manager;

    * the `on_enter()` instance method (makes a new context and pushes
      it to the aforementioned stack) -- intended to be called in the
      `__enter__()` method of your context manager;

    * the `on_exit()` instance method (pops a context from the
      aforementioned stack and finalizes that context) -- intended to
      be called in the `__exit__()` method of your context manager;

    * auxiliary properties (read-only):
      * `context_count` (the size of the aforementioned stack),
      * `innermost_context` (the most recent element of the
        aforementioned stack),
      * `outermost_context` (the least recent, i.e. "root", element of
        the aforementioned stack).

    For more information -- see the docstrings of these methods and
    properties, as well as the examples below.

    Also, note that -- to help dealing with thread-local state -- this
    class inherits from the `n6lib.common_helpers.ThreadLocalNamespace`
    class -- so, apart from the interface referred to above, it also
    offers all features of `ThreadLocalNamespace` (including the
    `attr_factories` constructor argument) -- see its docstring.

    ***

    An overview (quite detailed, including some corner cases) of the
    `ThreadLocalContextDeposit`'s public interface is presented through
    the following examples and in the docstrings of the `on_enter()` and
    `on_exit()` methods.

    Note, however, that these examples are somewhat contrived. If you
    are interested in the overall picture rather than numerous details,
    taking a look at real-life uses of this class may be more helpful.
    If so, see how the `__enter__()` and `__exit__()` methods are
    implemented by each of the following classes:

    * `n6lib.auth_api.AuthAPI` (a reentrant context manager),

    * `n6lib.auth_db.SQLAuthDBConnector` (also a reentrant context
      manager),

    * `n6corelib.manage_api._manage_api.ManageAPIAuthDBConnector`
      (a non-reentrant context manager).

    ***

    >>> class MyMightyDatabaseSessionManager(object):
    ...
    ...     class MyTransaction(object):
    ...         def __init__(self, session, parent_transaction=None):
    ...             self.session = session
    ...             self.id_within_session = (    # a lowercase letter ('a', 'b', 'c' and so on...)
    ...                 chr(ord(parent_transaction.id_within_session) + 1)
    ...                 if parent_transaction is not None
    ...                 else 'a')
    ...         def __str__(self):
    ...             return '{}.{}'.format(self.session, self.id_within_session)
    ...         def begin(self):
    ...             print('*** BEGIN {} ***'.format(self))
    ...         def insert(self, something):
    ...             print('*** INSERT {} within {} ***'.format(something, self))
    ...         def commit(self):
    ...             print('*** COMMIT {} ***'.format(self))
    ...         def rollback(self):
    ...             print('*** ROLLBACK {} ***'.format(self))
    ...
    ...     def __init__(self, my_session_factory):
    ...         self._my_session_factory = my_session_factory
    ...         self._ctx_deposit = ThreadLocalContextDeposit(attr_factories={
    ...             'current_session': (lambda: None),  # note: these attributes'll be initialized
    ...             'my_log': list})                    # automatically, separately in each thread!
    ...
    ...     @property
    ...     def current_session_in_this_thread(self):
    ...         return self._ctx_deposit.current_session
    ...
    ...     @property
    ...     def innermost_transaction_in_this_thread(self):
    ...         return self._ctx_deposit.innermost_context
    ...
    ...     @property
    ...     def outermost_transaction_in_this_thread(self):
    ...         return self._ctx_deposit.outermost_context
    ...
    ...     def __enter__(self):
    ...         self.log(' %s', self._ctx_deposit.context_count)
    ...         transaction = self._ctx_deposit.on_enter(
    ...             outermost_context_factory=self.initialize_session_and_get_first_transaction,
    ...             context_factory=self.get_nested_transaction)
    ...         self.log('%s,', self._ctx_deposit.context_count)
    ...         return transaction
    ...
    ...     def __exit__(self, exc_type, exc, tb):
    ...         self.log(' %s', self._ctx_deposit.context_count)
    ...         order = self._ctx_deposit.on_exit(
    ...             exc_type, exc, tb,
    ...             outermost_context_finalizer=self.finalize_whole_session,
    ...             context_finalizer=self.finalize_transaction)
    ...         self.log('%s', self._ctx_deposit.context_count)
    ...         if order == 'Suppress any exceptions from `with` block!':
    ...             self.log('|')
    ...             return True
    ...         else:
    ...             self.log('.')
    ...             return False
    ...
    ...     def initialize_session_and_get_first_transaction(self):
    ...         self.log('-')
    ...         self._ctx_deposit.current_session = self._my_session_factory()
    ...         assert self.innermost_transaction_in_this_thread is None
    ...         return self.get_nested_transaction()
    ...
    ...     def get_nested_transaction(self):
    ...         self.log('-')
    ...         transaction = self.MyTransaction(self.current_session_in_this_thread,
    ...                                          self.innermost_transaction_in_this_thread)
    ...         transaction.begin()
    ...         self.log('>')
    ...         return transaction
    ...
    ...     def finalize_whole_session(self, transaction, *exc_info):
    ...         self.log('=')
    ...         assert self.innermost_transaction_in_this_thread is None
    ...         self._ctx_deposit.current_session = None
    ...         self.finalize_transaction(transaction, *exc_info)
    ...         return 'Suppress any exceptions from `with` block!'
    ...
    ...     def finalize_transaction(self, transaction, exc_type, exc_val, tb):
    ...         self.log('=')
    ...         if exc_type is None:
    ...             try:
    ...                 transaction.commit()
    ...             except:
    ...                 self.log('COMMIT ERROR?!')
    ...                 transaction.rollback()
    ...                 raise
    ...         else:
    ...             self.log('ERR!')
    ...             transaction.rollback()
    ...         self.log('>')
    ...
    ...     # debug log helpers:
    ...     def log(self, msg, *args):
    ...         return self._ctx_deposit.my_log.append(msg % args)
    ...     def reset_my_log(self):
    ...         del self._ctx_deposit.my_log[:]
    ...     def format_my_log(self):
    ...         return ''.join(self._ctx_deposit.my_log)
    ...
    >>> def test_it(manager, call_tag=''):
    ...     def print_line(caption, value):
    ...         print(' '.join(filter(None, [
    ...             call_tag,
    ...             '#{}'.format(step),
    ...             '{}:'.format(caption),
    ...             str(value),
    ...         ])))
    ...     def print_manager_info():
    ...         print_line('current-ses', manager.current_session_in_this_thread)
    ...         print_line('innermost-tr', manager.innermost_transaction_in_this_thread)
    ...         print_line('outermost-tr', manager.outermost_transaction_in_this_thread)
    ...         print_line('log', manager.format_my_log())
    ...     def print_transaction_from_cm_info(transaction):
    ...         print_line('tr-from-cm', transaction)
    ...     step = 1
    ...     manager.reset_my_log()
    ...     manager.log('START')
    ...     print_manager_info()
    ...     with manager as transaction:
    ...         step = 2
    ...         print_manager_info()
    ...         print_transaction_from_cm_info(transaction)
    ...         transaction.insert('foo')
    ...         with manager as transaction:
    ...             step = 3
    ...             print_manager_info()
    ...             print_transaction_from_cm_info(transaction)
    ...             transaction.insert('bar')
    ...             if call_tag == '':
    ...                 import threading
    ...                 t = threading.Thread(target=test_it, args=(manager, '(thread)'))
    ...                 t.start()
    ...                 t.join()
    ...         step = 4
    ...         print_manager_info()
    ...     step = 5
    ...     print_manager_info()
    ...     with manager as transaction:
    ...         step = 6
    ...         print_manager_info()
    ...         print_transaction_from_cm_info(transaction)
    ...         try:
    ...             with manager as transaction:
    ...                 step = 7
    ...                 print_manager_info()
    ...                 print_transaction_from_cm_info(transaction)
    ...                 transaction.insert('spam')
    ...                 raise ValueError('SPAM SPAM SPAM')
    ...         finally:
    ...             step = 8
    ...             print_manager_info()
    ...         print('(NOT PRINTED BECAUSE OF UNCAUGHT EXCEPTION)')
    ...     step = 9
    ...     print_manager_info()
    ...     step = 10
    ...     manager.log(' STOP')
    ...     print_line('final-log', manager.format_my_log())
    ...
    >>> from functools import partial as p
    >>> dummy_session_factory = p(next, iter('ABCD'))  # here session is 'A', 'B', 'C' or 'D' (str)
    >>> dummy_manager = MyMightyDatabaseSessionManager(my_session_factory=dummy_session_factory)
    >>> test_it(dummy_manager)
    #1 current-ses: None
    #1 innermost-tr: None
    #1 outermost-tr: None
    #1 log: START
    *** BEGIN A.a ***
    #2 current-ses: A
    #2 innermost-tr: A.a
    #2 outermost-tr: A.a
    #2 log: START 0-->1,
    #2 tr-from-cm: A.a
    *** INSERT foo within A.a ***
    *** BEGIN A.b ***
    #3 current-ses: A
    #3 innermost-tr: A.b
    #3 outermost-tr: A.a
    #3 log: START 0-->1, 1->2,
    #3 tr-from-cm: A.b
    *** INSERT bar within A.b ***
    (thread) #1 current-ses: None
    (thread) #1 innermost-tr: None
    (thread) #1 outermost-tr: None
    (thread) #1 log: START
    *** BEGIN B.a ***
    (thread) #2 current-ses: B
    (thread) #2 innermost-tr: B.a
    (thread) #2 outermost-tr: B.a
    (thread) #2 log: START 0-->1,
    (thread) #2 tr-from-cm: B.a
    *** INSERT foo within B.a ***
    *** BEGIN B.b ***
    (thread) #3 current-ses: B
    (thread) #3 innermost-tr: B.b
    (thread) #3 outermost-tr: B.a
    (thread) #3 log: START 0-->1, 1->2,
    (thread) #3 tr-from-cm: B.b
    *** INSERT bar within B.b ***
    *** COMMIT B.b ***
    (thread) #4 current-ses: B
    (thread) #4 innermost-tr: B.a
    (thread) #4 outermost-tr: B.a
    (thread) #4 log: START 0-->1, 1->2, 2=>1.
    *** COMMIT B.a ***
    (thread) #5 current-ses: None
    (thread) #5 innermost-tr: None
    (thread) #5 outermost-tr: None
    (thread) #5 log: START 0-->1, 1->2, 2=>1. 1==>0|
    *** BEGIN C.a ***
    (thread) #6 current-ses: C
    (thread) #6 innermost-tr: C.a
    (thread) #6 outermost-tr: C.a
    (thread) #6 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1,
    (thread) #6 tr-from-cm: C.a
    *** BEGIN C.b ***
    (thread) #7 current-ses: C
    (thread) #7 innermost-tr: C.b
    (thread) #7 outermost-tr: C.a
    (thread) #7 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2,
    (thread) #7 tr-from-cm: C.b
    *** INSERT spam within C.b ***
    *** ROLLBACK C.b ***
    (thread) #8 current-ses: C
    (thread) #8 innermost-tr: C.a
    (thread) #8 outermost-tr: C.a
    (thread) #8 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1.
    *** ROLLBACK C.a ***
    (thread) #9 current-ses: None
    (thread) #9 innermost-tr: None
    (thread) #9 outermost-tr: None
    (thread) #9 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1. 1==ERR!>0|
    (thread) #10 final-log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1. 1==ERR!>0| STOP
    *** COMMIT A.b ***
    #4 current-ses: A
    #4 innermost-tr: A.a
    #4 outermost-tr: A.a
    #4 log: START 0-->1, 1->2, 2=>1.
    *** COMMIT A.a ***
    #5 current-ses: None
    #5 innermost-tr: None
    #5 outermost-tr: None
    #5 log: START 0-->1, 1->2, 2=>1. 1==>0|
    *** BEGIN D.a ***
    #6 current-ses: D
    #6 innermost-tr: D.a
    #6 outermost-tr: D.a
    #6 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1,
    #6 tr-from-cm: D.a
    *** BEGIN D.b ***
    #7 current-ses: D
    #7 innermost-tr: D.b
    #7 outermost-tr: D.a
    #7 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2,
    #7 tr-from-cm: D.b
    *** INSERT spam within D.b ***
    *** ROLLBACK D.b ***
    #8 current-ses: D
    #8 innermost-tr: D.a
    #8 outermost-tr: D.a
    #8 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1.
    *** ROLLBACK D.a ***
    #9 current-ses: None
    #9 innermost-tr: None
    #9 outermost-tr: None
    #9 log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1. 1==ERR!>0|
    #10 final-log: START 0-->1, 1->2, 2=>1. 1==>0| 0-->1, 1->2, 2=ERR!>1. 1==ERR!>0| STOP

    ***

    Let's take a closer look at some elements of the interface... (But
    see also the docs of `on_enter()` and `on_exit()`!)

    >>> dep = ThreadLocalContextDeposit(attr_factories={
    ...     # in each thread a separate instance will be created automatically
    ...     'my_auto_initialized_attribute': (lambda: ['bar']),
    ... })
    >>> # (first, we need to define two small helpers that will
    >>> # let us show the behavior of user-defined attributes of
    >>> # a ThreadLocalContextDeposit instance)
    >>> def _test_attr(dep, attr_name, same_as_obj=None, obj_var_to_print=None):
    ...     try:
    ...         attr_value = getattr(dep, attr_name)
    ...     except AttributeError:
    ...         print('* dep does NOT have attribute `{}`'.format(attr_name))
    ...     else:
    ...         print('* dep.{} == {!r}'.format(attr_name, attr_value))
    ...         rel = ('is' if attr_value is same_as_obj
    ...                else 'is NOT')
    ...         print('* dep.{} {} {}'.format(attr_name, rel, obj_var_to_print))
    ...
    >>> def _test_attr_in_another_thread(*args, **kwargs):
    ...     import threading
    ...     t = threading.Thread(target=_test_attr, args=args, kwargs=kwargs)
    ...     t.start()
    ...     t.join()
    ...

    >>> bar = dep.my_auto_initialized_attribute
    >>> bar
    ['bar']
    >>> _test_attr(dep, 'my_auto_initialized_attribute',
    ...            same_as_obj=bar, obj_var_to_print='bar')
    * dep.my_auto_initialized_attribute == ['bar']
    * dep.my_auto_initialized_attribute is bar
    >>> _test_attr_in_another_thread(
    ...            dep, 'my_auto_initialized_attribute',
    ...            same_as_obj=bar, obj_var_to_print='bar')
    * dep.my_auto_initialized_attribute == ['bar']
    * dep.my_auto_initialized_attribute is NOT bar

    >>> # thread-local attributes can also be added after deposit
    >>> # initialization; but attributes added this way are missing
    >>> # in other threads if not added in those threads explicitly:
    >>> foo = {'foo': 'goo'}
    >>> dep.my_dynamically_added_attribute = foo
    >>> _test_attr(dep, 'my_dynamically_added_attribute',
    ...            same_as_obj=foo, obj_var_to_print='foo')
    * dep.my_dynamically_added_attribute == {'foo': 'goo'}
    * dep.my_dynamically_added_attribute is foo
    >>> _test_attr_in_another_thread(
    ...            dep, 'my_dynamically_added_attribute',
    ...            same_as_obj=foo, obj_var_to_print='foo')
    * dep does NOT have attribute `my_dynamically_added_attribute`

    >>> dep  # doctest: +ELLIPSIS
    <ThreadLocalContextDeposit(...) with 0 contexts deposited (for thread <...>)>

    >>> dep.context_count
    0
    >>> dep.innermost_context, dep.outermost_context
    (None, None)
    >>> dep.on_enter(outermost_context_factory=lambda: 42,   # <- given and *used* (is outermost)
    ...              context_factory=lambda: 'ignore me')    # <- given, *not* used
    42
    >>> dep  # doctest: +ELLIPSIS
    <ThreadLocalContextDeposit(...) with 1 contexts deposited (for thread <...>)>

    >>> dep.context_count
    1
    >>> dep.innermost_context, dep.outermost_context
    (42, 42)
    >>> dep.on_enter(outermost_context_factory=lambda: 42,   # <- given, *not* used
    ...              context_factory=lambda: 'see me')       # <- given and *used* (non-outermost)
    'see me'
    >>> dep  # doctest: +ELLIPSIS
    <ThreadLocalContextDeposit(...) with 2 contexts deposited (for thread <...>)>

    >>> dep.context_count
    2
    >>> dep.innermost_context, dep.outermost_context
    ('see me', 42)

    >>> # now let's repeat the tests of user-defined attributes -- to
    >>> # show that populating the deposit with some contexts changed
    >>> # nothing to those attributes (so the results are the same as
    >>> # previously):
    >>> _test_attr(dep, 'my_auto_initialized_attribute',
    ...            same_as_obj=bar, obj_var_to_print='bar')
    * dep.my_auto_initialized_attribute == ['bar']
    * dep.my_auto_initialized_attribute is bar
    >>> _test_attr_in_another_thread(
    ...            dep, 'my_auto_initialized_attribute',
    ...            same_as_obj=bar, obj_var_to_print='bar')
    * dep.my_auto_initialized_attribute == ['bar']
    * dep.my_auto_initialized_attribute is NOT bar
    >>> _test_attr(dep, 'my_dynamically_added_attribute',
    ...            same_as_obj=foo, obj_var_to_print='foo')
    * dep.my_dynamically_added_attribute == {'foo': 'goo'}
    * dep.my_dynamically_added_attribute is foo
    >>> _test_attr_in_another_thread(
    ...            dep, 'my_dynamically_added_attribute',
    ...            same_as_obj=foo, obj_var_to_print='foo')
    * dep does NOT have attribute `my_dynamically_added_attribute`

    >>> dep.on_exit(None, None, None,
    ...             outermost_context_finalizer=lambda ctx, *_: 1/0,   # <- given, *not* used
    ...             context_finalizer=lambda ctx, *_: 'ya man')        # <- given and *used*
    'ya man'
    >>> dep.context_count
    1
    >>> dep.innermost_context, dep.outermost_context
    (42, 42)
    >>> dep.on_exit(None, None, None,
    ...             outermost_context_finalizer=lambda ctx, *_: 1/0,   # <- given and *used*
    ...             context_finalizer=lambda ctx, *_: 'ya man',        # <- given, *not* used
    ...             )   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> dep.context_count
    0
    >>> dep.innermost_context, dep.outermost_context
    (None, None)
    >>> dep.on_exit(None, None, None,
    ...             outermost_context_finalizer=lambda ctx, *_: 1/0,   # surplus call (not paired
    ...             context_finalizer=lambda ctx, *_: 'ya man',        # with earlier `on_enter()`)
    ...             )   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NoContextToExitFrom: ...
    >>> dep.context_count
    0
    >>> dep.innermost_context, dep.outermost_context
    (None, None)

    ***

    The `ThreadLocalContextDeposit`'s constructor accepts one optional
    keyword argument: `repr_token` -- to be used to make the `repr()`
    of the created instance more informative:

    >>> ThreadLocalContextDeposit(repr_token='xyz')  # doctest: +ELLIPSIS
    <ThreadLocalContextDeposit(repr_token='xyz', ...) with 0 contexts deposited (for thread <...>)>

    >>> ThreadLocalContextDeposit(repr_token=123)  # doctest: +ELLIPSIS
    <ThreadLocalContextDeposit(repr_token=123, ...) with 0 contexts deposited (for thread <...>)>
    """

    def __init__(self,
                 repr_token=None,
                 **kwargs):
        self._repr_token = repr_token
        self._context_stack = []
        super(ThreadLocalContextDeposit, self).__init__(**kwargs)

    def __repr__(self):
        arguments_repr = ('...' if self._repr_token is None
                          else 'repr_token={!r}, ...'.format(self._repr_token))
        return '<{}({}) with {} contexts deposited (for thread {!r})>'.format(
            type(self).__qualname__,
            arguments_repr,
            self.context_count,
            threading.current_thread())

    @property
    def context_count(self):
        """
        The number of contexts that are currently stored in the deposit.
        """
        return len(self._context_stack)

    @property
    def innermost_context(self):
        """
        The context data object that is currently stored in the deposit
        as the innermost context, or `None` if no contexts are currently
        stored.
        """
        try:
            return self._context_stack[-1]
        except IndexError:
            return None

    @property
    def outermost_context(self):
        """
        The context data object that is currently stored in the deposit
        as the outermost context, or `None` if no contexts are currently
        stored.
        """
        try:
            return self._context_stack[0]
        except IndexError:
            return None

    def on_enter(self,
                 context_factory=None,
                 outermost_context_factory=None):
        """
        Intended to be called in your context manager's `__enter__()`.

        This method invokes the callback given as one of its arguments
        (see the "Kwargs..." paragraph below) to provide a context data
        object, then puts it in the deposit as the innermost context,
        and then returns it.

        Kwargs (optional, keyword-only):
            `context_factory`:
                An argumentless callable that returns a context data
                object (which may be whatever you need). The callable
                is used to provide a context of *any* nesting level if
                the `outermost_context_factory` parameter is *not*
                given; otherwise (if `outermost_context_factory` *is*
                given as a non-`None` value) `context_factory` is used
                *only* when a *non-outermost* (non-root) context is to
                be provided.

                If `context_factory` is not given (or given as `None`
                which is equivalent) the default dummy context factory
                is used in place of it; the dummy factory produces
                an `int` number equal to the current value of the
                `context_count` property (see the `context_count`'s
                docs).

                `context_factory` can also be set to `NotImplemented`
                (see: https://docs.python.org/library/constants.html --
                *not* to be confused with `NotImplementedError`, which
                is explicitly forbidden to avoid accidental confusions).
                This special value means that when a non-outermost
                context is to be provided, the exception
                `ContextManagerIsNotReentrantError` will be raised
                instead. Such an explicit behaviour is desirable for
                a context manager that is *non-reentrant* (i.e., does
                *not* support using an instance of it *simultaneously*
                with more than one `with` statement per thread; i.e.,
                does *not* support nested `with` blocks).

            `outermost_context_factory`:
                An argumentless callable that returns a context data
                object (which may be whatever you need). The callable
                is used *only* to provide the outermost (root) context.

                If not given (or given as `None` which is equivalent)
                and, at the same time, `context_factory` (see above) is
                given as something else than `None` or `NotImplemented`,
                then `context_factory` is used in place of it.

                If not given (or given as `None` which is equivalent),
                and `context_factory` is not given as well or is given
                as `None` or `NotImplemented`, the default dummy context
                factory is used; the dummy factory produces an `int`
                number equal to the current value of the `context_count`
                property (which in the case of the outermost context
                must always be `0`).

                Note: `NotImplemented` is *not* a meaningful value of
                `outermost_context_factory`.

        Returns:
            The context data object (returned by one of the factories
            described above).

            Note: your context manager's `__enter__()` *may*, but *does
            not have to*, be implemented to use that object as the
            return value. What implementation is appropriate depends
            on the intended behavior of your context manager.

        ***

        The following examples focus on the ways this method (together
        with factory callbacks passed into it) cooperates with a
        context manager that makes use of it.

        >>> class MyContextManagerToTestOnEnter(object):
        ...
        ...     def __init__(self):
        ...         import itertools
        ...         self._context_deposit = ThreadLocalContextDeposit()
        ...         self._my_counter = itertools.count(start=1)
        ...         self.my_outermost_context_factory = self.factory_impl_X
        ...         self.my_context_factory = self.factory_impl_Y
        ...
        ...     def test_me(self):
        ...         try:
        ...             d = self._context_deposit
        ...             print('Before 1st: context_count == {}'.format(d.context_count))
        ...             print('Before 1st: innermost_context == {}'.format(d.innermost_context))
        ...             print('Will enter 1st...')
        ...             with self:
        ...                 print('Before 2nd: context_count == {}'.format(d.context_count))
        ...                 print('Before 2nd: innermost_context == {}'.format(d.innermost_context))
        ...                 print('Will enter 2nd...')
        ...                 with self:
        ...                     print('Within 2nd: context_count == {}'.format(d.context_count))
        ...                     print('Within 2nd: innermost_context == {}'.format(d.innermost_context))
        ...                     print('Will exit 2nd gracefully...')
        ...                 print('After 2nd: context_count == {}'.format(d.context_count))
        ...                 print('After 2nd: innermost_context == {}'.format(d.innermost_context))
        ...                 print('Will exit 1st gracefully...')
        ...         except Exception as exc:
        ...             print('Caught EXCEPTION: {}...'.format(type(exc).__name__))
        ...         print('After 1st: context_count == {}'.format(d.context_count))
        ...         print('After 1st: innermost_context == {}'.format(d.innermost_context))
        ...
        ...     def __enter__(self):
        ...         d = self._context_deposit
        ...         print('* at __enter__()\\\'s start: '
        ...                 'context_count == {}; '
        ...                 'innermost_context == {}'.format(
        ...                     d.context_count,
        ...                     d.innermost_context))
        ...         ctx = self._context_deposit.on_enter(
        ...             context_factory=self.my_context_factory,
        ...             outermost_context_factory=self.my_outermost_context_factory)
        ...         print('* at __enter__()\\\'s end: '
        ...                 'on_enter() returned {!r};\\n'
        ...               '                        '
        ...                 'context_count == {}; '
        ...                 'innermost_context == {}'.format(
        ...                     ctx,
        ...                     d.context_count,
        ...                     d.innermost_context))  # <- note: here it is the same as `ctx`
        ...         return self  # e.g. `ctx` could also be returned (it's up to the implementer)
        ...
        ...     def __exit__(self, exc_type, exc_value, tb):
        ...         if exc_type is not None:
        ...             print('* in __exit__(): observing EXCEPTION...')
        ...         self._context_deposit.on_exit(exc_type, exc_value, tb)
        ...
        ...     def factory_impl_X(self):
        ...         return self._factory_impl_details(tag='X')
        ...
        ...     def factory_impl_Y(self):
        ...         return self._factory_impl_details(tag='YYY')
        ...
        ...     def _factory_impl_details(self, tag):
        ...         d = self._context_deposit
        ...         ctx = [tag]
        ...         print('  * (factory-{}) created {}'.format(tag, ctx))
        ...         print('  * (factory-{}) context_count == {}; innermost_context == {}'.format(
        ...             tag,
        ...             d.context_count,
        ...             d.innermost_context))  # <- note: here it is the parent context of `ctx`
        ...         return ctx
        ...
        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
          * (factory-X) created ['X']
          * (factory-X) context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned ['X'];
                                context_count == 1; innermost_context == ['X']
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == ['X']
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == ['X']
          * (factory-YYY) created ['YYY']
          * (factory-YYY) context_count == 1; innermost_context == ['X']
        * at __enter__()'s end: on_enter() returned ['YYY'];
                                context_count == 2; innermost_context == ['YYY']
        Within 2nd: context_count == 2
        Within 2nd: innermost_context == ['YYY']
        Will exit 2nd gracefully...
        After 2nd: context_count == 1
        After 2nd: innermost_context == ['X']
        Will exit 1st gracefully...
        After 1st: context_count == 0
        After 1st: innermost_context == None

        When `on_enter()` does not get the `context_factory` argument,
        the default dummy factory is used in place of it:

        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.my_context_factory = None  # `my_outermost_context_factory` still has be set
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
          * (factory-X) created ['X']
          * (factory-X) context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned ['X'];
                                context_count == 1; innermost_context == ['X']
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == ['X']
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == ['X']
        * at __enter__()'s end: on_enter() returned 1;
                                context_count == 2; innermost_context == 1
        Within 2nd: context_count == 2
        Within 2nd: innermost_context == 1
        Will exit 2nd gracefully...
        After 2nd: context_count == 1
        After 2nd: innermost_context == ['X']
        Will exit 1st gracefully...
        After 1st: context_count == 0
        After 1st: innermost_context == None

        When `on_enter()` does not get the `outermost_context_factory`
        argument but `context_factory` is given, the latter is used also
        in place of `outermost_context_factory`:

        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.my_outermost_context_factory = None  # `my_context_factory` still has be set
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
          * (factory-YYY) created ['YYY']
          * (factory-YYY) context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned ['YYY'];
                                context_count == 1; innermost_context == ['YYY']
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == ['YYY']
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == ['YYY']
          * (factory-YYY) created ['YYY']
          * (factory-YYY) context_count == 1; innermost_context == ['YYY']
        * at __enter__()'s end: on_enter() returned ['YYY'];
                                context_count == 2; innermost_context == ['YYY']
        Within 2nd: context_count == 2
        Within 2nd: innermost_context == ['YYY']
        Will exit 2nd gracefully...
        After 2nd: context_count == 1
        After 2nd: innermost_context == ['YYY']
        Will exit 1st gracefully...
        After 1st: context_count == 0
        After 1st: innermost_context == None

        When `on_enter()` does not get the `outermost_context_factory`
        and `context_factory` arguments, the default dummy factory is
        used in place of each of them:

        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.my_context_factory = cm.my_outermost_context_factory = None   # both unset
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned 0;
                                context_count == 1; innermost_context == 0
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == 0
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == 0
        * at __enter__()'s end: on_enter() returned 1;
                                context_count == 2; innermost_context == 1
        Within 2nd: context_count == 2
        Within 2nd: innermost_context == 1
        Will exit 2nd gracefully...
        After 2nd: context_count == 1
        After 2nd: innermost_context == 0
        Will exit 1st gracefully...
        After 1st: context_count == 0
        After 1st: innermost_context == None

        When `context_factory` is specified as `NotImplemented`, nested
        `with` blocks are disallowed -- but this does not affect how the
        outermost context is created with `outermost_context_factory`
        (or with the default dummy factory if `outermost_context_factory`
        is not given):

        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.my_context_factory = NotImplemented  # disallowing nested `with`s
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
          * (factory-X) created ['X']
          * (factory-X) context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned ['X'];
                                context_count == 1; innermost_context == ['X']
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == ['X']
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == ['X']
        * in __exit__(): observing EXCEPTION...
        Caught EXCEPTION: ContextManagerIsNotReentrantError...
        After 1st: context_count == 0
        After 1st: innermost_context == None

        >>> cm = MyContextManagerToTestOnEnter()
        >>> cm.my_context_factory = NotImplemented  # disallowing nested `with`s
        >>> cm.my_outermost_context_factory = None
        >>> cm.test_me()
        Before 1st: context_count == 0
        Before 1st: innermost_context == None
        Will enter 1st...
        * at __enter__()'s start: context_count == 0; innermost_context == None
        * at __enter__()'s end: on_enter() returned 0;
                                context_count == 1; innermost_context == 0
        Before 2nd: context_count == 1
        Before 2nd: innermost_context == 0
        Will enter 2nd...
        * at __enter__()'s start: context_count == 1; innermost_context == 0
        * in __exit__(): observing EXCEPTION...
        Caught EXCEPTION: ContextManagerIsNotReentrantError...
        After 1st: context_count == 0
        After 1st: innermost_context == None
        """
        if context_factory is NotImplementedError:
            raise TypeError(
                '`context_factory` should *not* be NotImplementedError! '
                '(did you mean NotImplemented?)'.format(context_factory))
        if (outermost_context_factory is None
              and context_factory is not NotImplemented):
            outermost_context_factory = context_factory
        context_stack = self._context_stack
        if context_stack:
            if context_factory is None:
                context = self.context_count
            elif context_factory is NotImplemented:
                # If your context manager is *not* reentrant then it
                # should specify `context_factory` as `NotImplemented`
                # -- so that any client code that tries to use an
                # instance of your context manager with more than one
                # simultaneous `with` statement per thread will obtain
                # the following error:
                raise ContextManagerIsNotReentrantError(
                    '[error message from {!a}] the context manager being '
                    'used is not reentrant, that is, nesting of contexts '
                    '(using the same context manager instance in the same '
                    'thread) is *not* supported (i.e., only one level of '
                    '`with` per thread is allowed)'.format(self))
            else:
                context = context_factory()
        else:
            if outermost_context_factory is None:
                context = self.context_count
                assert context == 0
            else:
                context = outermost_context_factory()
        self._context_stack.append(context)
        return context

    def on_exit(self, exc_type, exc_value, exc_traceback,
                context_finalizer=None,
                outermost_context_finalizer=None):
        """
        Intended to be called in your context manager's `__exit__()`.

        This method removes from the deposit the context data object
        that, until now, has been the innermost context, and then
        invokes the callback given as one of the arguments (see the
        "Kwargs..." paragraph below) to finalize that (just removed)
        context. If no contexts have been stored, `NoContextToExitFrom`
        is raised.

        Args (obligatory, positional-only):
            `exc_type`,
            `exc_value`,
            `exc_traceback`:
                The arguments received by your context manager's `__exit__()`.

        Kwargs (optional, keyword-only):
            `context_finalizer`:
                A callable that takes the arguments specified below (in
                the "Callback args..." paragraph). The callable is used
                to finalize a context of *any* nesting level if the
                `outermost_context_finalizer` parameter is *not* given;
                otherwise (if `outermost_context_finalizer` *is* given
                as a non-`None` value) `context_finalizer` is used
                *only* to finalize a *non-outermost* (non-root)
                context.

                If `context_finalizer` is not given (or given as `None`
                which is equivalent) the default dummy finalizer is
                used in place of it; the dummy finalizer does nothing
                and returns `None`.

            `outermost_context_finalizer`:
                A callable that takes the arguments specified below (in
                the "Callback args..." paragraph). The callable is used
                *only* to provide the outermost (root) context.

                If not given (or given as `None` which is equivalent)
                and, at the same time, a non-`None` `context_finalizer`
                (see above) is given, then the latter is used in place
                of it.

                If not given (or given as `None` which is equivalent),
                and `context_finalizer` is not given as well (or is
                given as `None`), the default dummy finalizer is used;
                the dummy finalizer does nothing and returns `None`.

        Returns:
            The finalizer's return value (i.e., the object -- whatever
            it would be -- returned by one of the finalizers described
            above).

            Note: your context manager's `__exit__()` *may*, but *does
            not have to*, be implemented to use that object as the
            return value (recall that if the value returned by
            `__exit__()` is a logical true, then any exception
            propagated from the `with` block will be silenced by
            Python's `with`-statement-specific mechanisms). What
            implementation is appropriate depends on the intended
            behavior of your context manager.

        Callback args (obligatory, positional-only):
            `context`:
                The context data object to be finalized. Note that,
                *when the appropriate finalizer callback is called*,
                `context` is no longer stored in the deposit (i.e., it
                *was* there a moment ago as the innermost context, but
                has already been popped from the deposit's context
                stack); that means that now the `innermost_context`
                property points to the parent of `context` (or to
                `None`, if `context` was the outermost context).
            `exc_type`,
            `exc_value`,
            `exc_traceback`:
                The arguments received by your context manager's `__exit__()`.

        ***

        The following examples focus on the ways this method (together
        with finalizer callbacks passed into it) cooperates with a
        context manager that makes use of it.

        >>> class MyContextManagerToTestOnExit(object):
        ...
        ...     def __init__(self):
        ...         import itertools
        ...         self._context_deposit = ThreadLocalContextDeposit()
        ...         self._my_counter = itertools.count(start=1)
        ...         self.my_exit_return_val = None
        ...         self.my_context_finalizer = self.finalizer_impl_X
        ...         self.my_outermost_context_finalizer = self.finalizer_impl_Y
        ...
        ...     def test_me(self, error1=None, error2=None, error3=None):
        ...         try:
        ...             d = self._context_deposit
        ...             ctx2 = None
        ...             print('Before 1st: context_count == {}'.format(d.context_count))
        ...             print('Will enter 1st...')
        ...             with self as ctx1:
        ...                 print('Before 2nd: context_count == {}'.format(d.context_count))
        ...                 print('Before 2nd: ctx1 == {}'.format(ctx1))
        ...                 print('Before 2nd: ctx2 == {}'.format(ctx2))
        ...                 if error1 is not None:
        ...                     print('Will break 1st with error...')
        ...                     raise error1
        ...                 print('Will enter 2nd...')
        ...                 with self as ctx2:
        ...                     print('Within 2nd: context_count == {}'.format(d.context_count))
        ...                     print('Within 2nd: ctx1 == {}'.format(ctx1))
        ...                     print('Within 2nd: ctx2 == {}'.format(ctx2))
        ...                     if error2 is not None:
        ...                         print('Will break 2nd with error...')
        ...                         raise error2
        ...                     print('Will exit 2nd gracefully...')
        ...                 print('After 2nd: context_count == {}'.format(d.context_count))
        ...                 print('After 2nd: ctx1 == {}'.format(ctx1))
        ...                 print('After 2nd: ctx2 == {}'.format(ctx2))
        ...                 if error3 is not None:
        ...                     print('Will break 1st with error...')
        ...                     raise error3
        ...                 print('Will exit 1st gracefully...')
        ...         except Exception as exc:
        ...             print('Caught EXCEPTION: {}...'.format(type(exc).__name__))
        ...         print('After 1st: context_count == {}'.format(d.context_count))
        ...         print('After 1st: ctx1 == {}'.format(ctx1))
        ...         print('After 1st: ctx2 == {}'.format(ctx2))
        ...
        ...     def __enter__(self):
        ...         return self._context_deposit.on_enter(
        ...             context_factory=lambda: [next(self._my_counter)])
        ...
        ...     def __exit__(self, exc_type, exc_value, tb):
        ...         d = self._context_deposit
        ...         print('* at __exit__()\\\'s start: '
        ...                 'context_count == {}; '
        ...                 'innermost_context == {}'.format(
        ...                     d.context_count,
        ...                     d.innermost_context))  # <- here it is the context to be finalized
        ...         returned_val = self._context_deposit.on_exit(
        ...             exc_type, exc_value, tb,
        ...                 context_finalizer=self.my_context_finalizer,
        ...                 outermost_context_finalizer=self.my_outermost_context_finalizer)
        ...         print('* at __exit__()\\\'s end: '
        ...                 'on_exit() returned {!r};\\n'
        ...               '                       '
        ...                 'context_count == {}; '
        ...                 'innermost_context == {}'.format(
        ...                     returned_val,
        ...                     d.context_count,
        ...                     d.innermost_context))  # <- here it is the parent of the finalized
        ...         return self.my_exit_return_val
        ...
        ...     def finalizer_impl_X(self, ctx, exc_type, exc_value, tb):
        ...         return self._finalizer_impl_details('X', ctx, exc_type, exc_value, tb)
        ...
        ...     def finalizer_impl_Y(self, ctx, exc_type, exc_value, tb):
        ...         return self._finalizer_impl_details('YYY', ctx, exc_type, exc_value, tb)
        ...
        ...     def _finalizer_impl_details(self, tag, ctx, exc_type, exc_value, tb):
        ...         d = self._context_deposit
        ...         print('  * (finalizer-{}) context_count == {}; innermost_context == {}'.format(
        ...             tag,
        ...             d.context_count,
        ...             d.innermost_context))  # <- note: here it is the parent context of `ctx`
        ...         print('  * (finalizer-{}) starting finalization of {}'.format(tag, ctx))
        ...         ctx[0] = -ctx[0] * 111  # <- our emulation of context finalization
        ...         if exc_type is not None:
        ...             exc_name = exc_type.__name__
        ...             print('  * (finalizer-{}) observing EXCEPTION: {}'.format(tag, exc_name))
        ...         print('  * (finalizer-{}) finishing finalization of {}'.format(tag, ctx))
        ...         return next(self._my_counter) * 11
        ...
        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.test_me()
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will exit 2nd gracefully...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
          * (finalizer-X) context_count == 1; innermost_context == [1]
          * (finalizer-X) starting finalization of [2]
          * (finalizer-X) finishing finalization of [-222]
        * at __exit__()'s end: on_exit() returned 33;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [-222]
        Will exit 1st gracefully...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-YYY) context_count == 0; innermost_context == None
          * (finalizer-YYY) starting finalization of [1]
          * (finalizer-YYY) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 44;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == [-222]
        >>> try:
        ...     cm.__exit__(None, None, None)  # => surplus `on_exit()` call
        ... except NoContextToExitFrom:
        ...     print('Caught EXCEPTION: NoContextToExitFrom...')
        ...
        * at __exit__()'s start: context_count == 0; innermost_context == None
        Caught EXCEPTION: NoContextToExitFrom...

        When `on_exit()` does not get the `context_finalizer` argument,
        the default dummy finalizer is used in place of it:

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_context_finalizer = None  # `my_outermost_context_finalizer` still has be set
        >>> cm.test_me()
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will exit 2nd gracefully...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
        * at __exit__()'s end: on_exit() returned None;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [2]
        Will exit 1st gracefully...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-YYY) context_count == 0; innermost_context == None
          * (finalizer-YYY) starting finalization of [1]
          * (finalizer-YYY) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 33;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == [2]

        When `on_exit()` does not get the `outermost_context_finalizer`
        argument but `context_finalizer` is given, the latter is used
        also in place of `outermost_context_finalizer`:

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_outermost_context_finalizer = None  # `my_context_finalizer` still has be set
        >>> cm.test_me()
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will exit 2nd gracefully...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
          * (finalizer-X) context_count == 1; innermost_context == [1]
          * (finalizer-X) starting finalization of [2]
          * (finalizer-X) finishing finalization of [-222]
        * at __exit__()'s end: on_exit() returned 33;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [-222]
        Will exit 1st gracefully...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-X) context_count == 0; innermost_context == None
          * (finalizer-X) starting finalization of [1]
          * (finalizer-X) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 44;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == [-222]

        When `on_exit()` does not get the `outermost_context_finalizer`
        and `context_finalizer` arguments, the default dummy finalizer
        is used in place of each of them:

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_context_finalizer = cm.my_outermost_context_finalizer = None   # both unset
        >>> cm.test_me()
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will exit 2nd gracefully...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
        * at __exit__()'s end: on_exit() returned None;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [2]
        Will exit 1st gracefully...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
        * at __exit__()'s end: on_exit() returned None;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [1]
        After 1st: ctx2 == [2]

        Let's observe some cases that involve exceptions raised within
        `with` block(s)...

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.test_me(error1=ValueError('foo'))  # error within 1st, before entering 2nd
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will break 1st with error...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-YYY) context_count == 0; innermost_context == None
          * (finalizer-YYY) starting finalization of [1]
          * (finalizer-YYY) observing EXCEPTION: ValueError
          * (finalizer-YYY) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 22;
                               context_count == 0; innermost_context == None
        Caught EXCEPTION: ValueError...
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == None

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_exit_return_val = True     # error will be suppressed by `__exit__()`
        >>> cm.test_me(error1=ValueError('foo'))  # error within 1st, before entering 2nd
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will break 1st with error...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-YYY) context_count == 0; innermost_context == None
          * (finalizer-YYY) starting finalization of [1]
          * (finalizer-YYY) observing EXCEPTION: ValueError
          * (finalizer-YYY) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 22;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == None

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_exit_return_val = True   # errors will be suppressed by `__exit__()`
        >>> cm.test_me(error2=KeyError('bar'),              # error before exiting 2nd
        ...            error3=ZeroDivisionError('spam'))    # error before exiting 1st
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will break 2nd with error...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
          * (finalizer-X) context_count == 1; innermost_context == [1]
          * (finalizer-X) starting finalization of [2]
          * (finalizer-X) observing EXCEPTION: KeyError
          * (finalizer-X) finishing finalization of [-222]
        * at __exit__()'s end: on_exit() returned 33;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [-222]
        Will break 1st with error...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
          * (finalizer-YYY) context_count == 0; innermost_context == None
          * (finalizer-YYY) starting finalization of [1]
          * (finalizer-YYY) observing EXCEPTION: ZeroDivisionError
          * (finalizer-YYY) finishing finalization of [-111]
        * at __exit__()'s end: on_exit() returned 44;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [-111]
        After 1st: ctx2 == [-222]

        >>> cm = MyContextManagerToTestOnExit()
        >>> cm.my_context_finalizer = cm.my_outermost_context_finalizer = None    # both unset
        >>> cm.my_exit_return_val = True            # errors will be suppressed by `__exit__()`
        >>> cm.test_me(error2=KeyError('bar'),              # error before exiting 2nd
        ...            error3=ZeroDivisionError('spam'))    # error before exiting 1st
        Before 1st: context_count == 0
        Will enter 1st...
        Before 2nd: context_count == 1
        Before 2nd: ctx1 == [1]
        Before 2nd: ctx2 == None
        Will enter 2nd...
        Within 2nd: context_count == 2
        Within 2nd: ctx1 == [1]
        Within 2nd: ctx2 == [2]
        Will break 2nd with error...
        * at __exit__()'s start: context_count == 2; innermost_context == [2]
        * at __exit__()'s end: on_exit() returned None;
                               context_count == 1; innermost_context == [1]
        After 2nd: context_count == 1
        After 2nd: ctx1 == [1]
        After 2nd: ctx2 == [2]
        Will break 1st with error...
        * at __exit__()'s start: context_count == 1; innermost_context == [1]
        * at __exit__()'s end: on_exit() returned None;
                               context_count == 0; innermost_context == None
        After 1st: context_count == 0
        After 1st: ctx1 == [1]
        After 1st: ctx2 == [2]
        """
        if outermost_context_finalizer is None:
            outermost_context_finalizer = context_finalizer
        context_stack = self._context_stack
        if not context_stack:
            raise NoContextToExitFrom('{!a}.on_exit(): no context to pop!'.format(self))
        context = context_stack.pop()
        if context_stack:
            if context_finalizer is not None:
                return context_finalizer(context, exc_type, exc_value, exc_traceback)
        else:
            if outermost_context_finalizer is not None:
                return outermost_context_finalizer(context, exc_type, exc_value, exc_traceback)
        return None


    def _unsafe_replace_outermost_context(self, new_outermost_context):
        # This method should *not* be used in any production code!
        # It is intended to be used only in tests, if your really need
        # it and know what you are doing.
        self._context_stack[0] = new_outermost_context


def force_exit_on_any_remaining_entered_contexts(context_manager,
                                                 expected_exc_class=NoContextToExitFrom,
                                                 suppressed_exc_class=Exception,
                                                 max_exit_attempts=25):
    """
    Ensure that the given `context_manager` does not have any
    remaining entered contexts -- by calling its `__exit__()`
    (with `ContextManagerForcedExit` as the passed-in exception)
    until `expected_exc_class` is raised (which is then
    silenced), but not more than `max_exit_attempts` times.

    If some other exception is raised by such an `__exit__()`
    call the obtained exception is propagated (breaking the whole
    operation) *if* it does not match `suppressed_exc_class`;
    if it does, only a warning is logged (and the operation
    continues). You can specify `suppressed_exc_class` as `None`
    to propagate any exceptions.

    If `__exit__()` has been called `max_exit_attempts` times
    without `expected_exc_class` being raised by any of them
    then `RuntimeError` is raised.

    ***

    This function is intended to be applied to long-living context
    managers (such as an `AuthManageAPI` instance residing in the
    Pyramid's registry) to prevent the application from falling into a
    faulty state after some unexpected/intrusive event (such as an OS
    signal arrival) that prevented some context(s) from being properly
    `__exit__()`-ed.

    For example, a good candidate for a place where this function
    can be useful is somewhere near the beginning of the activity
    of an HTTP request handler.

    ***

    Note: the default value of the `expected_exc_class` parameter
    is the `NoContextToExitFrom` exception class. It means that
    this function is particularly convenient when dealing with
    context managers that make use of `ThreadLocalContextDeposit`
    (see also: the docs of the `NoContextToExitFrom` and
    `ThreadLocalContextDeposit` classes).

    ***

    `expected_exc_class`, as well as `suppressed_exc_class`, can be set
    not only to an exception class but also to a non-empty tuple of such
    classes.

    ***

    Somewhat contrived example that presents the core parts of the
    interface of this function:

    >>> class MySillyReentrantCM(object):
    ...
    ...     def __init__(self):
    ...         self.exc_on_exit = None
    ...         self._context_deposit = ThreadLocalContextDeposit()
    ...
    ...     @property
    ...     def context_count(self):
    ...         return self._context_deposit.context_count
    ...
    ...     def __enter__(self):
    ...         self._context_deposit.on_enter()
    ...
    ...     def __exit__(self, *exc_info):
    ...         # note: it will raise `NoContextToExitFrom`
    ...         # if there are no remaining entered contexts
    ...         self._context_deposit.on_exit(*exc_info, context_finalizer=self._fin)
    ...
    ...     def _fin(self, *_):
    ...         if self.exc_on_exit is not None:
    ...             raise self.exc_on_exit
    ...
    >>> cm = MySillyReentrantCM()
    >>> cm.context_count
    0
    >>> cm.__enter__(); cm.__enter__(); cm.__enter__(); cm.context_count
    3
    >>> force_exit_on_any_remaining_entered_contexts(cm)
    >>> cm.context_count
    0

    >>> # a subclass of Exception which is the default value of `suppressed_exc_class`
    >>> cm.exc_on_exit = ZeroDivisionError('spam')
    >>> cm.__enter__(); cm.__enter__(); cm.__enter__(); cm.context_count
    3
    >>> force_exit_on_any_remaining_entered_contexts(cm)
    >>> cm.context_count
    0

    >>> cm.__enter__(); cm.__enter__(); cm.__enter__(); cm.context_count
    3
    >>> force_exit_on_any_remaining_entered_contexts(cm, suppressed_exc_class=None
    ...                                              )   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm.context_count
    2

    >>> force_exit_on_any_remaining_entered_contexts(cm, suppressed_exc_class=(ZeroDivisionError,
    ...                                                                        KeyError))
    >>> cm.context_count
    0

    >>> cm.__enter__(); cm.__enter__(); cm.__enter__(); cm.context_count
    3
    >>> force_exit_on_any_remaining_entered_contexts(cm, expected_exc_class=(FloatingPointError,
    ...                                                                      NoContextToExitFrom))
    >>> cm.context_count
    0

    >>> cm.__enter__(); cm.__enter__(); cm.__enter__(); cm.context_count
    3
    >>> force_exit_on_any_remaining_entered_contexts(cm, expected_exc_class=FloatingPointError
    ...                                              )   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    RuntimeError: ...none of the expected exceptions (FloatingPointError) ... raised

    >>> force_exit_on_any_remaining_entered_contexts(cm, expected_exc_class=(KeyError, ValueError)
    ...                                              )   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    RuntimeError: ...none of the expected exceptions (KeyError, ValueError) ... raised
    """
    if not isinstance(expected_exc_class, tuple):
        expected_exc_class = (expected_exc_class,)
    if suppressed_exc_class is None:
        # No exception will be suppressed (note that, in Python, `except
        # <empty tuple>:` means that *no* exceptions will be caught; did
        # you know it? :-)).
        suppressed_exc_class = ()
    this_func_name = force_exit_on_any_remaining_entered_contexts.__name__
    exit_exc_name = ContextManagerForcedExit.__name__
    exit_exc = ContextManagerForcedExit('thrown by {}'.format(this_func_name))
    for _ in range(max_exit_attempts):
        try:
            type(context_manager).__exit__(context_manager,
                                           ContextManagerForcedExit, exit_exc, None)
        except expected_exc_class:
            break
        except suppressed_exc_class as exc:
            LOGGER.warning(
                'When trying (using %s()) to do a forced exit (by '
                'calling the `__exit__()` method with %s as the '
                'thrown exception), the context manager %a raised '
                'an exception that will be silenced (%s)',
                this_func_name,
                exit_exc_name,
                context_manager,
                make_exc_ascii_str(exc))
    else:
        raise RuntimeError(
            '{}() tried to do a forced exit on the context manager '
            '{!a} (by calling {} times its `__exit__()` with {} as '
            'the thrown exception) but none of the expected '
            'exceptions ({}) have been raised'.format(
                this_func_name,
                context_manager,
                max_exit_attempts,
                exit_exc_name,
                ascii_str(', '.join(
                    getattr(exc_cls, '__name__', exc_cls)
                    for exc_cls in expected_exc_class))))

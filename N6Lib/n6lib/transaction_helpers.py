# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import functools
import threading

import transaction as zope_transaction

__all__ = 'transact', 'autotransact'


class _TransactionContextManager(threading.local):

    """
    A context manager to wrap execution of code blocks in transactions.

    It is a kind of proxy to the Zope transaction manager, providing
    some additional features, that is:

    * the thread-local `active` attribute which is the currently managed
      transaction object or None;

    * some checks that in case of failure raise an exception: see below.

    Raises:
        RuntimeError:
            When trying start a new transaction and another transaction
            is already in progress in the current thread (transactions
            are thread-local and nested transactions are not allowed).
        AssertionError:
            When finishing the active transaction in the current thread
            and it appears than the get() method of the zope transaction
            manager returns another transaction (which means that some
            silly by-hand operations on transaction management machinery
            were made in the meantime).

    Only one instance of this context manager is intended to be used
    multiple times so one global public instance `transact` is
    provided out-of-the-box. A usage example:

        with transact:
            for event in new_events:
                some_db_api.add_event(event)
            # if no error occurred to this point thansaction will be commited
        with transact:
            # new transaction
            some_db_api.add_event(another_event)
            raise ValueError  # transaction will be rolled back
    """

    def __init__(self):
        self.active = None

    def __enter__(self):
        if self.active is not None:
            raise RuntimeError('nested transactions are not allowed')
        active = self.active = zope_transaction.manager.begin()
        return active

    def __exit__(self, exc_type, exc_value, tb):
        try:
            active = self.active
            manager = zope_transaction.manager
            final = manager.get()
            if active is final:
                if exc_value is None:
                    manager.commit()
                else:
                    manager.abort()
            else:
                raise AssertionError('something wrong: the real final transaction {!r} '
                                     'is not the transaction {!r} that has been managed'
                                     .format(final, active))
        except:
            manager.abort()
            raise
        finally:
            self.active = None


transact = _TransactionContextManager()


def autotransact(func):
    """
    A decorator to automatically wrap operations in transactions.

    Each call of the decorated function/method will be wrapped in
    a transaction unless a transaction is already in progress in
    the current thread (if it is, the call will be made without
    wrapping it in a new transaction).

    This decorator "does the right thing" for transaction-capable-storage
    operations, i.e. you can safely wrap your functions/methods with this
    decorator, regardless of whether they are called in Pyramid
    applications or non-Pyramid applications -- *provided that*:

    * Your storage API is properly configured to use Zope transaction
      mechanisms. In case of sqlalchemy it means that your global
      session factory is created by calling something like:
      scoped_session(sessionmaker(extension=ZopeTransactionExtension())).

    * *No other* transaction-related magic (such as pyramid_tm) is in use!
      (But, of course, using our n6sdk/n6lib.pyramid_commons stuff is OK).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if transact.active is None:
            # no transaction is active
            # -> let's wrap the call in a new transaction
            with transact:
                return func(*args, **kwargs)
        else:
            # a transaction is already active
            # -> no need to wrap the call in a transaction
            return func(*args, **kwargs)
    return wrapper

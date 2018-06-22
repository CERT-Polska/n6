# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.


import threading
import functools


def singleton(cls):
    """
    A class decorator ensuring that the class can be instantiated only once.

    Args:
        `cls`: the decorated class.

    Returns:
        The same class (`cls`).

    Trying to instantiate the decorated class more than once causes
    :exc:`~exceptions.RuntimeError` -- unless, during provious
    instantiations, :meth:`__init__` of the decorated class did not
    succeed (caused an exception).

    Subclasses are also bound by this restriction (i.e. the decorated
    class and its subclasses are "counted" as one entity) -- unless
    their :meth:`__init__` is overridden in such a way that the
    :meth:`__init__` of the decorated class is not called.

    The check is thread-safe (protected with a lock).

    >>> @singleton
    ... class X(object):
    ...     pass
    ...
    >>> o = X()
    >>> o = X()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> @singleton
    ... class X2(object):
    ...     def __init__(self, exc=None):
    ...         if exc is not None:
    ...             raise exc
    ...
    >>> o = X2(ValueError('foo'))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: foo
    >>> o = X2()
    >>> o = X2()                   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = X2(ValueError('foo'))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> @singleton
    ... class Y(object):
    ...     def __init__(self, a, b, c=42):
    ...         print a, b, c
    ...
    >>> class Z(Y):
    ...     pass
    ...
    >>> class ZZZ(Y):
    ...     def __init__(self, a, b):
    ...         # will *not* call Y.__init__
    ...         print 'zzz', a, b
    ...
    >>> o = Y('spam', b='ham')
    spam ham 42
    >>> o = Y('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = Z('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = ZZZ('spam', b='ham')
    zzz spam ham

    >>> @singleton
    ... class Y2(object):
    ...     def __init__(self, a, b, c=42):
    ...         print a, b, c
    ...
    >>> class Z2(Y2):
    ...     pass
    ...
    >>> class ZZZZZ(Y):
    ...     def __init__(self, a, b):
    ...         # *will* call Y.__init__
    ...         super(ZZZZZ, self).__init__(a, b=b)
    ...
    >>> o = Z2('spam', b='ham')
    spam ham 42
    >>> o = Z2('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = Y2('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = ZZZZZ('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...

    >>> class A(object):
    ...     def __init__(self, a, b, c=42):
    ...         print a, b, c
    ...
    >>> @singleton
    ... class B(A):
    ...     pass
    ...
    >>> o = A('spam', b='ham')
    spam ham 42
    >>> o = B('spam', b='ham')
    spam ham 42
    >>> o = B('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    >>> o = A('spam', b='ham')
    spam ham 42
    >>> o = B('spam', b='ham')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    RuntimeError: ...
    """
    cls._singleton_check_lock = threading.Lock()
    cls._singleton_already_instantiated = False

    def singleton_check(cls):
        with cls._singleton_check_lock:
            if cls._singleton_already_instantiated:
                raise RuntimeError('an instance of singleton class {0!r} '
                                   'has already been created'.format(cls))
            cls._singleton_already_instantiated = True

    if '__init__' in vars(cls):
        _orig_init = vars(cls)['__init__']

        @functools.wraps(_orig_init)
        def __init__(*args, **kwargs):
            singleton_check(cls)
            try:
                _orig_init(*args, **kwargs)
            except:
                with cls._singleton_check_lock:
                    cls._singleton_already_instantiated = False
                raise
    else:
        def __init__(*args, **kwargs):
            self = args[0]  # to avoid arg name clash ('self' may be in kwargs)
            singleton_check(cls)
            try:
                super(cls, self).__init__(*args[1:], **kwargs)
            except:
                with cls._singleton_check_lock:
                    cls._singleton_already_instantiated = False
                raise

    cls.__init__ = __init__
    return cls


def attr_required(*attr_names, **kwargs):
    """
    A method decorator: provides a check for presence of specified attributes.

    Some positional args:
        Names of attributes that are required to be present *and*
        not to be the `dummy_placeholder` object (see below) when
        the decorated method is called.

    Kwargs:
        `dummy_placeholder` (default: :obj:`None`):
            The object that is not treated as a required value.

    The decorated function (method) will raise:
        :exc:`~exceptions.NotImplementedError`:
            When at least one of the specified attributes is set to
            the `dummy_placeholder` object or does not exist.

    >>> class XX(object):
    ...     a = 1
    ...
    ...     @attr_required('a')
    ...     def meth_a(self):
    ...          print 'OK'
    ...
    ...     @attr_required('a', 'b')
    ...     def meth_ab(self):
    ...          print 'Excellent'
    ...
    ...     @attr_required('z', dummy_placeholder=NotImplemented)
    ...     def meth_z(self):
    ...          print 'Nice'
    ...
    ...     @classmethod
    ...     @attr_required('c')
    ...     def meth_c(self):
    ...          print 'Cool'
    ...
    >>> x = XX()
    >>> x.meth_a()
    OK
    >>> x.meth_ab()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> x.b = 42
    >>> x.meth_ab()
    Excellent
    >>> del XX.a
    >>> x.meth_ab()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> XX.a = None
    >>> x.meth_ab()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> x.meth_z()   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> x.z = None
    >>> x.meth_z()  # OK as here `dummy_placeholder` is not None
    Nice
    >>> x.z = NotImplemented
    >>> x.meth_z()   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> XX.c = 'see'
    >>> x.meth_c()
    Cool
    >>> XX.meth_c()
    Cool
    >>> del XX.c
    >>> x.meth_c()   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> XX.meth_c()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> x.c = 'see'  # (note: instance attrs do not matter for a classmethod)
    >>> x.meth_c()   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    >>> XX.meth_c()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...
    """
    dummy_placeholder = kwargs.pop('dummy_placeholder', None)
    if kwargs:
        raise TypeError('illegal keyword arguments: ' +
                        ', '.join(sorted(map(repr, kwargs))))
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self = args[0]  # to avoid arg name clash ('self' may be in kwargs)
            for name in attr_names:
                if getattr(self, name, dummy_placeholder) is dummy_placeholder:
                    raise NotImplementedError('attribute {0!r} is required to '
                                              'be present and not to be {1!r}'
                                              .format(name, dummy_placeholder))
            return func(*args, **kwargs)
        return wrapper
    return decorator

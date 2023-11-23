# Copyright (c) 2013-2023 NASK. All rights reserved.
#
# For some code in this module:
# Copyright (c) 2001-2013 Python Software Foundation. All rights reserved.
# (For more information -- see the docstrings below...)

import abc
import collections
import contextlib
import copy
import errno
import io
import pickle
import functools
import hashlib
import itertools
import operator
import os
import os.path as osp
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import weakref
from collections.abc import (
    Callable,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSequence,
    Reversible,
    Set,
)
from importlib import import_module
from threading import get_ident as get_current_thread_ident
from typing import (
    TypeVar,
    Union,
)

# for backward-compatibility and/or for convenience, the following
# constants and functions importable from some of the n6sdk.* modules
# are also accessible via this module:
from n6sdk.addr_helpers import (
    ip_network_as_tuple,
    ip_network_tuple_to_min_max_ip,
    ip_str_to_int,
)
from n6sdk.encoding_helpers import (
    ascii_str,
    ascii_py_identifier_str,
    as_str_with_minimum_esc,
    as_unicode,
    str_to_bool,
    replace_surrogate_pairs_with_proper_codepoints,
)
from n6sdk.regexes import (
    CC_SIMPLE_REGEX,
    DOMAIN_ASCII_LOWERCASE_REGEX,
    DOMAIN_ASCII_LOWERCASE_STRICT_REGEX,
    IPv4_STRICT_DECIMAL_REGEX,  # <- NOTE: not (yet?) used by this module's IP-related functions
    IPv4_ANONYMIZED_REGEX,
    IPv4_CIDR_NETWORK_REGEX,
    PY_IDENTIFIER_REGEX,
)
from n6lib.class_helpers import (
    is_seq,
    properly_negate_eq,
)
from n6lib.const import (
    HOSTNAME,
    SCRIPT_BASENAME,
)
from n6lib.typing_helpers import (
    HashableT,
    T,
)


_DOMAIN_ASCII_LOWERCASE_STRICT_REGEX_SUBPATTERN = (
    DOMAIN_ASCII_LOWERCASE_STRICT_REGEX.pattern
        .lstrip('A\\ \r\n')
        .rstrip('Z\\ \r\n'))

# more restrictive than actual e-mail address syntax but sensible in most cases
EMAIL_OVERRESTRICTED_SIMPLE_REGEX = re.compile(
    rf'''
        \A
        (?P<local>
            (?!
                \.       # local part cannot start with dot
            )
            (
                         # see: http://en.wikipedia.org/wiki/Email_address#Local-part
                [\-0-9a-zA-Z!#$%&'*+/=?^_`{{|}}~]
            |
                \.
                (?!
                    \.   # local part cannot contain two or more non-separated dots
                )
            )+     # (note: according to RFC 5321, maximum length of local part is 64, but here
                   # we are more liberal -- for historical reasons / backward compatibility...)
            (?<!
                \.       # local part cannot end with dot
            )
        )
        @
        (?P<domain>
            {_DOMAIN_ASCII_LOWERCASE_STRICT_REGEX_SUBPATTERN}
        )
        \Z
    ''',
    re.ASCII | re.VERBOSE)

# search()-only regexes of source code path prefixes that do not include
# any valuable information (so they can be cut off from debug messages)
USELESS_SRC_PATH_PREFIX_REGEXES = (
    re.compile(r'/N6'
               r'(?:'
               r'AdminPanel|BrokerAuthApi|Core|CoreLib|GitLabTools'
               r'|GridFSMount|KscApi|Lib|Portal|Push|RestApi|SDK'
               r')'
               r'/(?=n6)',
               re.ASCII),
    re.compile(r'/[^/]+\.egg/', re.ASCII),
    re.compile(r'/(?:site|dist)-packages/', re.ASCII),
    re.compile(r'/python[23](?:\.\d+)+/', re.ASCII),
    re.compile(r'^/home/\w+/', re.ASCII),
    re.compile(r'^/usr/(?:(?:local/)?lib/)?', re.ASCII),
)


class RsyncFileContextManager:

    """
    A context manager that retrieves data using rsync,
    creates a temporary directory in most secure manner possible,
    stores the downloaded file in that directory,
    returns the downloaded file
    and deletes the temporary directory and its contents.

    The user provides rsync option (e.g. '-z'), source link and name of the temporary file.
    """

    def __init__(self, option, source, dest_tmp_file_name="rsynced_data"):
        self._option = option
        self._source = source
        self._file_name = dest_tmp_file_name
        self._dir_name = None
        self._file = None

    def __enter__(self):
        if self._file is not None:
            raise RuntimeError('Context manager {!a} is not reentrant'.format(self))
        self._dir_name = tempfile.mkdtemp()
        try:
            full_file_path = osp.join(self._dir_name, self._file_name)
            try:
                subprocess.check_output(["rsync", self._option, self._source, full_file_path],
                                        stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError('Cannot download source file (CalledProcessError exception '
                                   'message: "{}"; command output: "{}")'
                                   .format(ascii_str(exc), ascii_str(exc.output)))
            self._file = open(full_file_path)
        except:
            try:
                if self._file is not None:
                    self._file.close()
            finally:
                try:
                    shutil.rmtree(self._dir_name)
                finally:
                    self._dir_name = None
            raise
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._file.close()
        finally:
            try:
                shutil.rmtree(self._dir_name)
            finally:
                self._dir_name = None
                self._file = None


class PlainNamespace:

    """
    Provides attribute access to its namespace, as well as
    namespace-content-based implementation of the `==`/`!=` operators
    and `repr()`.

    It is similar to Python 3's `types.SimpleNamespace`. In fact, its
    initial version was copied from the `SimpleNamespace` example from
    http://docs.python.org/3.4/library/types.html.

    However, some modifications/additions has been made by us, so we
    decided to keep this class here even after migration to Python 3.
    """

    @classmethod
    def from_class(cls, decorated_class):
        return cls(**{
            name: getattr(decorated_class, name) for name in vars(decorated_class)
            if not (name.startswith('__') and name.endswith('__'))})

    def __init__(self, /, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        namespace = self.__dict__
        items = ("{}={!r}".format(k, namespace[k])
                 for k in sorted(namespace))
        return "{.__qualname__}({})".format(type(self), ", ".join(items))

    def __eq__(self, other):
        if hasattr(other, '__dict__'):
            return self.__dict__ == other.__dict__
        return NotImplemented

    __ne__ = properly_negate_eq


class ThreadLocalNamespace(PlainNamespace, threading.local):

    """
    Somewhat similar to `PlainNamespace` (which is one of its base
    classes) -- but with two significant differences:

    * it is also a subclass of `threading.local` -- so its instances
      provide a *separate namespace for each thread*;

    * the constructor takes *only* one optional keyword argument:
      `attr_factories` -- it should be a dict that maps attribute names
      to attribute factories, i.e., argumentless callables that will be
      called *separately in each thread* to obtain corresponding
      attribute values.

    >>> TLN = ThreadLocalNamespace(attr_factories={'foo': lambda: ['xyz']})
    >>> TLN.foo
    ['xyz']
    >>> TLN                                                                    # doctest: +ELLIPSIS
    <ThreadLocalNamespace object as visible from thread ...: foo=['xyz']>

    >>> PN = PlainNamespace(foo=['xyz', 123])
    >>> TLN == PN
    False
    >>> TLN.foo.append(123)
    >>> TLN.foo
    ['xyz', 123]
    >>> TLN == PN
    True
    >>> TLN                                                                    # doctest: +ELLIPSIS
    <ThreadLocalNamespace object as visible from thread ...: foo=['xyz', 123]>

    >>> def test_it(tln, sn, with_appended=None):
    ...     if with_appended is not None:
    ...         tln.foo.append(with_appended)
    ...     print(
    ...         'TLN with foo={tln.foo}'
    ...         ' is {equality} to'
    ...         ' PN with foo={sn.foo}'.format(
    ...             tln=tln,
    ...             sn=sn,
    ...             equality=('equal' if tln==sn else '*not* equal')))
    ...
    >>> def test_it_in_another_thread(tln, sn, with_appended=None):
    ...     t = threading.Thread(target=test_it, args=(tln, sn, with_appended))
    ...     t.start()
    ...     t.join()
    ...
    >>> test_it(TLN, PN)
    TLN with foo=['xyz', 123] is equal to PN with foo=['xyz', 123]
    >>> test_it_in_another_thread(TLN, PN)
    TLN with foo=['xyz'] is *not* equal to PN with foo=['xyz', 123]
    >>> test_it_in_another_thread(TLN, PN, with_appended=123)
    TLN with foo=['xyz', 123] is equal to PN with foo=['xyz', 123]
    >>> PN.foo.pop()
    123
    >>> test_it(TLN, PN)
    TLN with foo=['xyz', 123] is *not* equal to PN with foo=['xyz']
    >>> test_it_in_another_thread(TLN, PN)
    TLN with foo=['xyz'] is equal to PN with foo=['xyz']
    >>> test_it_in_another_thread(TLN, PN, with_appended=123)
    TLN with foo=['xyz', 123] is *not* equal to PN with foo=['xyz']
    """

    @classmethod
    def from_class(cls, decorated_class):
        return cls(attr_factories={
            name: getattr(decorated_class, name) for name in vars(decorated_class)
            if not (name.startswith('__') and name.endswith('__'))})

    def __init__(self, attr_factories=None):
        attrs = {}
        if attr_factories is not None:
            for name, factory in sorted(attr_factories.items()):
                value = factory()
                attrs[name] = value
        super().__init__(**attrs)

    def __repr__(self):
        namespace = self.__dict__
        items = ("{}={!r}".format(k, namespace[k])
                 for k in sorted(namespace))
        return '<{} object as visible from thread {!r}: {}>'.format(
            type(self).__qualname__,
            threading.current_thread(),
            ', '.join(items))


class NonBlockingLockWrapper:

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
            lock_description = ascii(self.lock)
        return ascii_str(lock_description)

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


class FilePagedSequence(MutableSequence):

    """
    A mutable sequence that reduces memory usage by keeping data as files.

    Under the hood, the sequence is "paged" -- only the current page
    (consisting of a defined number of items) is kept in memory; other
    pages are pickled and saved as temporary files.

    The interface is similar to the built-in `list`'s one, except that:

    * slices are not supported;

    * the `remove()`, `insert()`, `reverse()`, `sort()` and `copy()`
      methods are *not supported* (though the `reversed()` built-in
      function *is* supported);

    * the `+`, `*` and `*=` operators are *not supported* (though `+=`
      *is* supported);

    * the `del` operation is *not supported*, and the `pop()` method
      supports *only* popping the last item, i.e., it works only if the
      argument is specified as `-1` or not specified at all; also, note
      that `clear()` *is* supported (use it instead of `del seq[:]`);

    * all sequence items must be picklable (effects of using unpicklable
      items are undefined; generally, that will cause an exception, but
      -- typically -- that exception will be deferred until the moment
      when, after adding more items, the current data page needs to be
      saved...);

    * pickling and the `copy()`/`deepcopy()` functions from the `copy`
      module should also be considered *unsupported* (i.e., effects of
      trying to apply them to instances of this class are undefined;
      exceptions and/or unexpected behavior are likely);

    * the constructor accepts an additional argument: `page_size` --
      being the number of items each page may consist of (its default
      value is `1000`);

    * there are additional methods:

      * `close()` -- clears the sequence and removes all temporary files
        (if any); after that, the instance can be used again, just as if
        it was a newly created empty instance (new temporary files will
        be created when needed);

      * a context-manager (`with`-statement) interface:

        * its `__enter__()` returns the instance;
        * its `__exit__()` calls the aforementioned `close()` method.

    Unsupported `list`-specific operations raise `NotImplementedError`.

    Temporary files are created lazily. No disk (filesystem) operations
    are performed at all if all data fit on one page.

    Normally, when an instance of this class is garbage-collected or
    when the program exits in an undisturbed way (*also* if it exits
    due to an unhandled exception), the instance's temporary files
    are automatically removed (thanks to a `weakref.finalize()`-based
    mechanism used internally by the class).

    The implementation of `FilePagedSequence` is *not* thread-safe.

    >>> seq = FilePagedSequence([1, 'foo', {'a': None}, ['b']], page_size=3)
    >>> seq
    FilePagedSequence(<4 items...>, page_size=3)
    >>> seq[0]
    1
    >>> seq[-1]
    ['b']
    >>> seq[2]
    {'a': None}
    >>> seq[-2]
    {'a': None}
    >>> seq[1]
    'foo'
    >>> len(seq)
    4
    >>> bool(seq)
    True

    >>> itr = iter(seq)
    >>> isinstance(itr, Iterator)
    True
    >>> list(itr)   # (`itr` is a proper *iterator*, so any future uses of it will yield no items)
    [1, 'foo', {'a': None}, ['b']]
    >>> list(itr)
    []
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b']]
    >>> list(seq)   # (`seq` is a real *sequence*, so -- obviously -- you can use it many times)
    [1, 'foo', {'a': None}, ['b']]

    >>> empty1 = FilePagedSequence()
    >>> empty1
    FilePagedSequence(<0 items...>, page_size=1000)
    >>> empty2 = FilePagedSequence(page_size=3)
    >>> empty2
    FilePagedSequence(<0 items...>, page_size=3)
    >>> len(empty1) == len(empty2) == 0
    True
    >>> list(empty1) == list(empty2) == []
    True
    >>> bool(empty1)
    False
    >>> bool(empty2)
    False

    >>> seq.append(42.0)
    >>> seq
    FilePagedSequence(<5 items...>, page_size=3)
    >>> len(seq)   # (length increased)
    5
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b'], 42.0]

    >>> @picklable
    ... class NotEqual:   # (a helper for tests of some item-membership-related operations...)
    ...     def __init__(self):
    ...         self._key = f'__NotEqual_object_{id(self)}'
    ...         setattr(self.__class__, self._key, self)
    ...     def __repr__(self):
    ...         return '<NotEqual...>'
    ...     def __eq__(self, other):
    ...         return False                     # <- *not equal* to anything, even to itself
    ...     def __reduce__(self):
    ...         return f'NotEqual.{self._key}'   # <- preserves its identity when (un)pickled
    ...
    >>> ne1 = NotEqual()
    >>> ne2 = NotEqual()
    >>> ne1 != ne1 != ne2
    True
    >>> ne1 is ne1 is not ne2
    True

    >>> seq.append(ne1)
    >>> seq
    FilePagedSequence(<6 items...>, page_size=3)
    >>> len(seq)
    6
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b'], 42.0, <NotEqual...>]

    >>> all(item in seq
    ...     for item in [1, 1.0, 'foo', {'a': None}, ['b'], 42, 0j+42, ne1])
    True
    >>> any(item not in seq
    ...     for item in [1, 1.0, 'foo', {'a': None}, ['b'], 42, 0j+42, ne1])
    False
    >>> all(item not in seq
    ...     for item in [0, -1.0, 'fo', {'aa': None}, ['B'], '42', 42.000000001, ne2])
    True
    >>> any(item in seq
    ...     for item in [0, -1.0, 'fo', {'aa': None}, ['B'], '42', 42.000000001, ne2])
    False

    >>> seq[4] = 1.0
    >>> seq[4]
    1.0
    >>> len(seq)   # (length not changed)
    6
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b'], 1.0, <NotEqual...>]

    >>> seq.index(1)
    0
    >>> seq.index(1, 2)
    4
    >>> seq.index(1, 2, 5)
    4
    >>> seq.index(1, 2, 3)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError
    >>> seq.index(ne1)
    5
    >>> seq.index(ne1, 4, 6)
    5
    >>> seq.index(ne2)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError

    >>> seq.count(1)
    2
    >>> seq.count(ne1)
    1
    >>> seq.count(ne2)
    0

    >>> seq[1:2]
    Traceback (most recent call last):
      ...
    NotImplementedError: slices are not supported
    >>> seq[1:4:2]
    Traceback (most recent call last):
      ...
    NotImplementedError: slices are not supported
    >>> seq[1:2] = ['a', 'b']
    Traceback (most recent call last):
      ...
    NotImplementedError: slices are not supported
    >>> seq[1:4:2] = ['a', 'b']
    Traceback (most recent call last):
      ...
    NotImplementedError: slices are not supported

    >>> seq + [3, 'spam']  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: sequence concatenation is not supported
    >>> [3, 'spam'] + seq  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: sequence concatenation is not supported
    >>> seq * 2  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: sequence multiplication is not supported
    >>> 3 * seq  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: sequence multiplication is not supported
    >>> seq *= 4  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: sequence multiplication is not supported

    >>> seq.copy()
    Traceback (most recent call last):
      ...
    NotImplementedError: copying is not supported
    >>> seq.sort()
    Traceback (most recent call last):
      ...
    NotImplementedError: in-place sorting is not supported
    >>> seq.reverse()
    Traceback (most recent call last):
      ...
    NotImplementedError: in-place reversion is not supported
    >>> seq.insert(2, 'bar')
    Traceback (most recent call last):
      ...
    NotImplementedError: random insertion is not supported
    >>> seq.remove('foo')
    Traceback (most recent call last):
      ...
    NotImplementedError: random deletion is not supported
    >>> del seq[-1]
    Traceback (most recent call last):
      ...
    NotImplementedError: random deletion is not supported
    >>> del seq[1:-2]
    Traceback (most recent call last):
      ...
    NotImplementedError: random deletion is not supported
    >>> del seq[1:-2:2]
    Traceback (most recent call last):
      ...
    NotImplementedError: random deletion is not supported
    >>> seq.pop(-2)
    Traceback (most recent call last):
      ...
    NotImplementedError: popping using index other than -1 is not supported

    >>> seq.pop(-1) is ne1
    True
    >>> seq.pop(-1)
    1.0
    >>> seq
    FilePagedSequence(<4 items...>, page_size=3)
    >>> len(seq)
    4
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b']]

    >>> seq.pop(-1)
    ['b']
    >>> seq.pop()   # same as `.pop(-1)`
    {'a': None}
    >>> list(seq)
    [1, 'foo']
    >>> len(seq)
    2

    >>> seq.append(430)
    >>> seq.extend([440, 450])
    >>> list(seq)
    [1, 'foo', 430, 440, 450]
    >>> len(seq)
    5

    >>> seq[2] = 43
    >>> seq[3] = 44
    >>> seq[4] = 45
    >>> list(seq)
    [1, 'foo', 43, 44, 45]
    >>> len(seq)
    5

    >>> seq.append(46)
    >>> seq[5]
    46
    >>> seq[-6]
    1
    >>> len(seq)
    6

    >>> seq.append(47)
    >>> list(seq)
    [1, 'foo', 43, 44, 45, 46, 47]
    >>> len(seq)
    7

    >>> seq.pop()
    47
    >>> list(seq)
    [1, 'foo', 43, 44, 45, 46]

    >>> seq.pop(-1)
    46
    >>> list(seq)
    [1, 'foo', 43, 44, 45]

    >>> seq.pop()
    45
    >>> list(seq)
    [1, 'foo', 43, 44]
    >>> len(seq)
    4

    >>> seq.pop()
    44
    >>> seq[-1]
    43
    >>> list(seq)
    [1, 'foo', 43]

    >>> seq.extend(['a', 'b', 'c'])
    >>> list(seq)
    [1, 'foo', 43, 'a', 'b', 'c']
    >>> len(seq)
    6

    >>> seq[0]
    1

    >>> seq[5] = 'CCC'
    >>> seq[5]
    'CCC'
    >>> len(seq)
    6

    >>> seq.append('DDD')
    >>> seq[1]
    'foo'
    >>> seq[-1]
    'DDD'
    >>> list(seq)
    [1, 'foo', 43, 'a', 'b', 'CCC', 'DDD']

    >>> seq.clear()
    >>> seq
    FilePagedSequence(<0 items...>, page_size=3)
    >>> len(seq)
    0
    >>> bool(seq)
    False
    >>> list(seq)
    []
    >>> seq.pop()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError

    >>> seq += [1, 'foo', {'a': None}, ['b']]   # same as `.extend([1, 'foo', {'a': None}, ['b']])`
    >>> seq[0]
    1
    >>> seq[-1]
    ['b']
    >>> seq[2]
    {'a': None}
    >>> seq[-2]
    {'a': None}
    >>> seq[1]
    'foo'
    >>> len(seq)
    4

    >>> list(seq)
    [1, 'foo', {'a': None}, ['b']]

    >>> seq.append(42.0)
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b'], 42.0]

    >>> seq.pop()
    42.0
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b']]

    >>> seq.pop(-1)
    ['b']
    >>> seq.pop()
    {'a': None}
    >>> list(seq)
    [1, 'foo']

    >>> seq.append(ne1)
    >>> seq.append(44)
    >>> seq.append(45)
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45]

    >>> seq.append(46)
    >>> seq[5]
    46
    >>> seq[4]
    45
    >>> seq[3]
    44
    >>> seq[-6]
    1

    >>> seq.append(47)
    >>> seq[6]
    47
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45, 46, 47]

    >>> seq.pop()
    47
    >>> seq[5]
    46
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45, 46]

    >>> seq.append(47)
    >>> seq[-1]
    47
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45, 46, 47]

    >>> seq.pop()
    47
    >>> seq[-1]
    46
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45, 46]

    >>> len(seq)
    6

    >>> seq.pop()
    46
    >>> len(seq)
    5

    >>> seq[-1]
    45
    >>> seq[4]
    45
    >>> list(reversed(seq))
    [45, 44, <NotEqual...>, 'foo', 1]
    >>> seq[5]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[6]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[7]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[8]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError

    >>> seq[-5]
    1
    >>> list(seq)
    [1, 'foo', <NotEqual...>, 44, 45]
    >>> list(iter(seq))
    [1, 'foo', <NotEqual...>, 44, 45]
    >>> seq[-6]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[0]
    1
    >>> seq[-7]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[-8]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError
    >>> seq[-9]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError

    >>> seq == FilePagedSequence([1, 'foo', ne1, 44, 45], page_size=3)
    True
    >>> seq == FilePagedSequence([1, 'foo', ne1, 44, 45], page_size=4)
    True
    >>> seq == [1, 'foo', ne1, 44, 45]
    True
    >>> [1, 'foo', ne1, 44, 45] == seq
    True
    >>> seq != FilePagedSequence([1, 'foo', ne1, 44, 45], page_size=3)
    False
    >>> seq != FilePagedSequence([1, 'foo', ne1, 44, 45], page_size=4)
    False
    >>> seq != [1, 'foo', ne1, 44, 45]
    False
    >>> [1, 'foo', ne1, 44, 45] != seq
    False

    >>> seq == FilePagedSequence([1, 'foo', ne1, 6544, 45], page_size=3)
    False
    >>> seq == FilePagedSequence([1, 'foo', ne1, 6544, 45], page_size=4)
    False
    >>> seq == [1, 'foo', ne1, 6544, 45]
    False
    >>> [1, 'foo', ne1, 6544, 45] == seq
    False
    >>> seq != FilePagedSequence([1, 'foo', ne1, 6544, 45], page_size=3)
    True
    >>> seq != FilePagedSequence([1, 'foo', ne1, 6544, 45], page_size=4)
    True
    >>> seq != [1, 'foo', ne1, 6544, 45]
    True
    >>> [1, 'foo', ne1, 6544, 45] != seq
    True

    >>> FilePagedSequence('abcdef', page_size=4) == ('a', 'b', 'c', 'd', 'e', 'f')
    True
    >>> FilePagedSequence(b'abcdef', page_size=4) == range(97, 103)
    True

    >>> FilePagedSequence('abcdef', page_size=4) == 'abcdef'
    False
    >>> FilePagedSequence(b'abcdef', page_size=4) == b'abcdef'
    False
    >>> FilePagedSequence(b'abcdef', page_size=4) == bytearray(b'abcdef')
    False

    >>> '_dir' in seq.__dict__    # (here we use a *non-public stuff*, never do that in real code!)
    True
    >>> _dir = seq._dir      # (it's a *non-public descriptor*, never use it in real code!)
    >>> osp.exists(_dir)
    True
    >>> sorted(os.listdir(_dir))
    ['0', '1', '2']
    >>> seq
    FilePagedSequence(<5 items...>, page_size=3)
    >>> seq.close()
    >>> seq
    FilePagedSequence(<0 items...>, page_size=3)
    >>> list(seq)
    []
    >>> '_dir' in seq.__dict__    # (filesystem no longer used)
    False
    >>> osp.exists(_dir)
    False

    >>> with seq as cm_target:       # (note: reusing the same instance)
    ...     seq is cm_target
    ...     '_dir' not in seq.__dict__   # (filesystem not used yet)
    ...     seq.extend(map(int, '1234567890'))
    ...     '_dir' in seq.__dict__       # (filesystem used)
    ...     seq == [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    ...     repr(seq) == 'FilePagedSequence(<10 items...>, page_size=3)'
    ...     _dir2 = seq._dir
    ...     osp.exists(_dir2)
    ...     sorted(os.listdir(_dir2)) == ['0', '1', '2', '3']
    ...     _dir2 != _dir and not osp.exists(_dir)
    ...
    True
    True
    True
    True
    True
    True
    True
    True
    >>> seq
    FilePagedSequence(<0 items...>, page_size=3)
    >>> list(seq)
    []
    >>> '_dir' in seq.__dict__   # (filesystem no longer used)
    False
    >>> osp.exists(_dir2)
    False
    >>> osp.exists(_dir)
    False

    >>> log_list = []; log = log_list.append
    >>> for j in range(10):     # (here we test certain edge/corner cases of the implementation...)
    ...     for i in range(10):
    ...         n = 10*j + i
    ...         seq.append(n)
    ...         seq_last = seq[-1]
    ...         seq_equal_to_range = (seq == range(n + 1))
    ...         rev_equal_to_rev_range = (list(reversed(seq)) == list(reversed(range(n + 1))))
    ...         seq_j = seq[j]      # (<- it's important for this test that the `seq[j]` lookup
    ...         log({               #     is always done directly before next `seq.append(n)`...)
    ...             'j_i': (j, i),
    ...             'n': n,
    ...             'seq_last': seq_last,
    ...             'seq_equal_to_range': seq_equal_to_range,
    ...             'rev_equal_to_rev_range': rev_equal_to_rev_range,
    ...             'seq[j]': seq_j,
    ...         })
    ...
    >>> seq == range(100)
    True
    >>> log_list == [
    ...     {
    ...         'j_i': (j, i),
    ...         'n': 10*j + i,
    ...         'seq_last': 10*j + i,
    ...         'seq_equal_to_range': True,
    ...         'rev_equal_to_rev_range': True,
    ...         'seq[j]': j,
    ...     }
    ...     for j in range(10)
    ...         for i in range(10)]
    True

    >>> seq2 = FilePagedSequence('abc', page_size=3)
    >>> list(seq2)
    ['a', 'b', 'c']
    >>> '_dir' in seq2.__dict__   # all items in current page -> no disk op.
    False
    >>> seq2.extend('d')          # (now page 0 must be saved)
    >>> '_dir' in seq2.__dict__   # new page created -> filesystem used
    True
    >>> _dir = seq2._dir
    >>> osp.exists(_dir)
    True
    >>> sorted(os.listdir(_dir))
    ['0']
    >>> seq2.extend('ef')
    >>> sorted(os.listdir(_dir))
    ['0']
    >>> seq2.extend('g')          # (now page 1 must be saved)
    >>> sorted(os.listdir(_dir))
    ['0', '1']
    >>> seq2[0]                   # (now page 2 must be saved)
    'a'
    >>> sorted(os.listdir(_dir))
    ['0', '1', '2']
    >>> seq2.pop()
    'g'
    >>> sorted(os.listdir(_dir))
    ['0', '1', '2']
    >>> seq2.clear()
    >>> sorted(os.listdir(_dir))
    ['0', '1', '2']
    >>> seq2.close()
    >>> '_dir' in seq2.__dict__   # (filesystem no longer used)
    False
    >>> osp.exists(_dir)
    False
    >>> list(seq2)
    []

    >>> seq3 = FilePagedSequence(page_size=3)
    >>> '_dir' in seq3.__dict__   # (filesystem not used yet)
    False
    >>> seq3.close()
    >>> '_dir' in seq3.__dict__   # (filesystem still not used at all)
    False

    >>> with FilePagedSequence(page_size=3) as seq4:
    ...     '_dir' not in seq4.__dict__   # (filesystem not used yet)
    ...     seq4.append(('foo', 1))
    ...     list(seq4) == [('foo', 1)]
    ...     seq4[0] = 'bar', 2
    ...     seq4[0] == ('bar', 2)
    ...     list(seq4) == [('bar', 2)]
    ...     seq4.append({'x'})
    ...     seq4.append({'z': 3})
    ...     list(seq4) == [('bar', 2), {'x'}, {'z': 3}]
    ...     '_dir' not in seq4.__dict__   # (filesystem still not used, yet)
    ...     seq4.append(['d'])
    ...     '_dir' in seq4.__dict__       # (filesystem used)
    ...     _dir = seq4._dir
    ...     osp.exists(_dir)
    ...     sorted(os.listdir(_dir)) == ['0']
    ...     seq4[2] = {'ZZZ': 333}
    ...     sorted(os.listdir(_dir)) == ['0', '1']
    ...     list(seq4) == [('bar', 2), {'x'}, {'ZZZ': 333}, ['d']]
    ...     osp.exists(_dir)
    ...
    True
    True
    True
    True
    True
    True
    True
    True
    True
    True
    True
    True
    >>> '_dir' in seq4.__dict__   # (filesystem no longer used)
    False
    >>> osp.exists(_dir)
    False
    """

    def __init__(self, iterable=(), page_size=1000):
        self._page_size = page_size
        self._cur_len = 0
        self._cur_page_no = None
        self._cur_page_data = []
        self._dir_lifecycle_op_rlock = threading.RLock()
        self._dir_finalizer = lambda: None
        self.extend(iterable)

    def __repr__(self):
        constructor_args_repr = f'<{len(self)} items...>, page_size={self._page_size}'
        return f'{self.__class__.__qualname__}({constructor_args_repr})'

    def __eq__(self, other):
        if is_seq(other):
            return len(self) == len(other) and all(
                # This is how items are compared by built-in `list`.
                # *Side note:* there may exist objects (for example,
                # `float('nan')`) which compare unequal to themselves
                # *and* for whom pickling and unpickling (important for
                # the `FilePagedSequence`'s machinery and -- obviously
                # -- irrelevant for built-in `list`) *may not* keep
                # their identities; but that is so rare/insubstantial
                # case that we don't care.
                my_item is their_item or my_item == their_item
                for my_item, their_item in zip(self, other))
        return NotImplemented

    __ne__ = properly_negate_eq

    def __len__(self):
        return self._cur_len

    def __getitem__(self, index):
        local_index = self._local_index(index)
        return self._cur_page_data[local_index]

    def __setitem__(self, index, value):
        local_index = self._local_index(index)
        self._cur_page_data[local_index] = value

    def append(self, value):
        page_no, local_index = divmod(self._cur_len, self._page_size)
        if page_no != self._cur_page_no:
            self._switch_to(page_no, new=(local_index == 0))
        self._cur_page_data.append(value)
        self._cur_len += 1

    def pop(self, index=-1):
        if index != -1:
            raise NotImplementedError('popping using index other '
                                      'than -1 is not supported')
        local_index = self._local_index(-1)
        value = self._cur_page_data.pop(local_index)
        self._cur_len -= 1
        return value

    def __delitem__(self, index):
        raise NotImplementedError('random deletion is not supported')

    def insert(self, index, value):
        raise NotImplementedError('random insertion is not supported')

    def reverse(self):
        raise NotImplementedError('in-place reversion is not supported')

    def sort(self, cmp=None, key=None, reverse=None):
        raise NotImplementedError('in-place sorting is not supported')

    def copy(self):
        raise NotImplementedError('copying is not supported')

    def __add__(self, other):
        raise NotImplementedError('sequence concatenation is not supported')

    def __radd__(self, other):
        raise NotImplementedError('sequence concatenation is not supported')

    def __mul__(self, other):
        raise NotImplementedError('sequence multiplication is not supported')

    def __rmul__(self, other):
        raise NotImplementedError('sequence multiplication is not supported')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def clear(self):
        self._cur_page_data = []
        self._cur_page_no = None
        self._cur_len = 0

    def close(self):
        self.clear()
        self._dir_clear()

    #
    # Non-public stuff

    @functools.cached_property
    def _dir(self):
        dir_rlock = self._dir_lifecycle_op_rlock
        with dir_rlock:
            temp_dir = self.__dict__.get('_dir')
            if temp_dir is None:
                temp_dir = self._make_temp_dir()
                self._dir_finalizer = weakref.finalize(
                    self,
                    self._do_filesystem_cleanup,
                    temp_dir,
                    dir_rlock)
                # Note: the machinery of `weakref.finalize()` automatically
                # ensures that the finalizer will be called at program exit
                # if it is not called earlier.
                assert self._dir_finalizer.atexit
            return temp_dir

    def _dir_clear(self):
        with self._dir_lifecycle_op_rlock:
            self.__dict__.pop('_dir', None)
            self._dir_finalizer()

    def _make_temp_dir(self):
        return tempfile.mkdtemp(prefix='n6-FilePagedSequence-tmp')

    @staticmethod
    def _do_filesystem_cleanup(temp_dir, dir_rlock):
        with dir_rlock:
            for filename in os.listdir(temp_dir):
                os.remove(osp.join(temp_dir, filename))
            os.rmdir(temp_dir)

    def _local_index(self, index):
        if isinstance(index, slice):
            raise NotImplementedError('slices are not supported')
        if index < 0:
            index = self._cur_len + index
        if 0 <= index < self._cur_len:
            page_no, local_index = divmod(index, self._page_size)
            if page_no != self._cur_page_no:
                self._switch_to(page_no)
            return local_index
        else:
            raise IndexError(f'{index=!a} is out of range for {self!a}')

    def _switch_to(self, page_no, new=False):
        if self._cur_page_no is not None:
            self._save_page(self._cur_page_data)
        self._cur_page_data = [] if new else self._load_page(page_no)
        self._cur_page_no = page_no

    def _save_page(self, page_data):
        filename = self._get_page_filename(self._cur_page_no)
        with self._writable_page_file(filename) as f:
            pickle.dump(page_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _load_page(self, page_no):
        filename = self._get_page_filename(page_no)
        with self._readable_page_file(filename) as f:
            return pickle.load(f)

    def _get_page_filename(self, page_no):
        return osp.join(self._dir, str(page_no))

    @contextlib.contextmanager
    def _writable_page_file(self, filename):
        with AtomicallySavedFile(filename, 'wb') as f:
            yield f

    @contextlib.contextmanager
    def _readable_page_file(self, filename):
        with open(filename, 'rb') as f:
            yield f

    #
    # Unittest helper (to test a code that makes use of instances of the class)

    @staticmethod
    def _instance_mock(iterable=(), *, page_size=1000):
        """
        Make a mock of a `FilePagedSequence` instance.

        The returned object provides the *public* interface and
        semantics of a `FilePagedSequence` instance, but it never
        attempts any filesystem operations.

        At the same time, it is a real *mock* object, i.e., it provides
        all those fancy goodies specific to `unittest.mock`-made mocks.

        We can describe it with [the vocabulary used by Martin Fowler
        ](https://martinfowler.com/articles/mocksArentStubs.html#TheDifferenceBetweenMocksAndStubs)
        as a hybrid of a *fake* (as it provides a working implementation
        of the `FilePagedSequence`'s public interface) and *spy* (as it
        is a `unittest.mock`'s `NonCallableMock` object, with all its
        post-inspection capabilities, such as `mock_calls` etc.; note
        that in the Python world such a *spy* object is usually referred
        to just as *mock*, not to be confused with what is called *mock*
        according to the vocabulary used by Fowler).
        """

        import unittest.mock

        #
        # determining the list of methods

        public_methods_from_mutable_sequence = (
            # (those invoking `FilePagedSequence`'s real stuff)
            '__contains__', '__iter__', '__reversed__',
            'index', 'count', 'extend', '__iadd__',
            # (the one invoking `FilePagedSequence`'s stuff that
            # raises `NotImplementedError`)
            'remove',
        )
        public_methods_defined_here = (     # <- except `__init__()` and `__repr__()`
            # (with real implementations)
            '__eq__', '__ne__', '__len__', '__getitem__', '__setitem__',
            '__enter__', '__exit__', 'append', 'pop', 'clear', 'close',
            # (raising `NotImplementedError`)
            '__delitem__', 'insert', 'reverse', 'sort', 'copy',
            '__add__', '__radd__', '__mul__', '__rmul__',
        )
        assert set(public_methods_from_mutable_sequence).issubset(dir(MutableSequence))
        assert set(public_methods_defined_here).isdisjoint(public_methods_from_mutable_sequence)
        assert set(public_methods_defined_here) == {
            name for name, val in vars(FilePagedSequence).items()
            if (isinstance(val, (Callable, classmethod, staticmethod))
                and name not in ('__init__', '__repr__')
                and (name.startswith('__') and name.endswith('__')  # either __dunder__ or
                     or not name.startswith('_')))}                 # ordinary public name

        all_public_methods = public_methods_from_mutable_sequence + public_methods_defined_here

        #
        # defining the underlying behavior

        class _FakeFilePagedSequence(FilePagedSequence):  # noqa

            def _make_temp_dir(self):
                return f'<temp dir path placeholder no. {next(path_placeholder_counter)}>'

            @staticmethod
            def _do_filesystem_cleanup(*_):
                fake_filesystem.clear()

            @contextlib.contextmanager
            def _writable_page_file(self, filename):
                with io.BytesIO() as f:
                    try:
                        yield f
                    finally:
                        pickled_page = f.getvalue()
                        fake_filesystem[filename] = pickled_page

            @contextlib.contextmanager
            def _readable_page_file(self, filename):
                pickled_page = fake_filesystem.get(filename)
                if pickled_page is None:
                    raise FileNotFoundError(errno.ENOENT, 'No such file or directory', filename)
                with io.BytesIO(pickled_page) as f:
                    yield f

        path_placeholder_counter = itertools.count()
        fake_filesystem = {}
        obj = _FakeFilePagedSequence(iterable, page_size)

        #
        # making the actual mock

        obj_mock = unittest.mock.NonCallableMock(__class__=FilePagedSequence)
        for method_name in all_public_methods:
            method_obj = getattr(obj, method_name)
            method_mock = unittest.mock.MagicMock(
                wraps=method_obj,
                spec=method_obj)
            setattr(obj_mock, method_name, method_mock)

        # (we want the *as-target* of *with* blocks to be our mock,
        # not the underlying `_FakeFilePagedSequence` object)
        obj_mock.__enter__.side_effect = lambda: obj_mock

        # (additional tool to make introspection easier...)
        obj_mock._as_list = lambda: list(obj)

        unittest.mock.seal(obj_mock)
        return obj_mock


_ElemT_co = TypeVar('_ElemT_co', bound=Hashable, covariant=True)

class OPSet(Set[_ElemT_co], Reversible[_ElemT_co], Hashable):

    """
    An immutable set-like container that *preserves the order* of
    the elements, whereras average performance of containment tests
    (`in`/`not in`) is still `O(1)` (as for built-in dicts and sets).

    `OPSet` implements the interface of the following abstract classes
    defined in `collections.abc`: `Set`, `Reversible` and `Hashable`.

    Since `OPSet` objects are hashable, they can be used as dict keys
    and set elements (also elements of `OPSet`s).

    Note: the order of elements is preserved by the constructor as well
    as by any operators that produce new `OPSet` instances, but does not
    influence any set-specific tests (in particular, equality tests).

    >>> s = OPSet([1, 2, 6, 3, 2, 7, 1])
    >>> s
    OPSet([1, 2, 6, 3, 7])
    >>> len(s)
    5
    >>> bool(s)
    True
    >>> 1 in s
    True
    >>> 4 in s
    False
    >>> it = iter(s)
    >>> next(it)
    1
    >>> next(it)
    2
    >>> list(it)
    [6, 3, 7]
    >>> list(it)
    []
    >>> list(s)
    [1, 2, 6, 3, 7]
    >>> rv = reversed(s)
    >>> next(rv)
    7
    >>> next(rv)
    3
    >>> list(rv)
    [6, 2, 1]
    >>> list(it)
    []
    >>> list(reversed(s))
    [7, 3, 6, 2, 1]

    >>> e = OPSet()
    >>> e
    OPSet()
    >>> len(e)
    0
    >>> bool(e)
    False
    >>> 1 in e
    False
    >>> 4 in e
    False
    >>> list(e)
    []
    >>> list(reversed(e))
    []

    >>> s == s
    True
    >>> s == OPSet([1, 2, 6, 3, 7])
    True
    >>> s == OPSet([6, 2, 3, 7, 1])  # (order of elements is irrelevant for equality etc.)
    True
    >>> s == {1, 2, 6, 3, 7}
    True
    >>> {1, 2, 6, 3, 7} == s
    True
    >>> s == {1: None, 2: None, 6: None, 3: None, 7: None}.keys()  # (dict's keys view is set-like)
    True
    >>> s == {6: None, 2: None, 3: None, 7: None, 1: None}.keys()
    True
    >>> {6: None, 2: None, 3: None, 7: None, 1: None}.keys() == s
    True
    >>> class Submissive(Set):
    ...     def __init__(self, iterable=()): self.li = list(iter_deduplicated(iterable))
    ...     def __contains__(self, elem): return elem in self.li
    ...     def __iter__(self): return iter(self.li)
    ...     def __len__(self): return len(self.li)
    ...     def _submissive_impl(*_): return NotImplemented
    ...     __eq__ = __ne__ = __gt__ = __ge__ = __le__ = __lt__ = _submissive_impl
    ...     __and__ = __rand__ = __or__ = __ror__ = _submissive_impl
    ...     __sub__ = __rsub__ = __xor__ = __rxor__ = _submissive_impl
    ...
    >>> s == Submissive([1, 2, 6, 3, 7])
    True
    >>> Submissive([6, 2, 3, 7, 1]) == s
    True
    >>> e == e
    True
    >>> e == OPSet()
    True
    >>> e == set()
    True
    >>> set() == e
    True
    >>> e == {}.keys()
    True
    >>> {}.keys() == e
    True
    >>> e == Submissive()
    True
    >>> Submissive() == e
    True

    >>> s == OPSet([6, 2, 3, 7])
    False
    >>> s == {1, 2, 6, 3}
    False
    >>> {1, 2, 6, 3} == s
    False
    >>> s == frozenset({1, 2, 6, 3, 7, 8})
    False
    >>> frozenset({1, 2, 6, 3, 7, 8}) == s
    False
    >>> s == {1: None, 2: None, 6: None, 3: None, 8: None}.keys()
    False
    >>> {1: None, 2: None, 6: None, 3: None, 8: None}.keys() == s
    False
    >>> s == Submissive([2, 6, 3])
    False
    >>> Submissive([2, 6, 3]) == s
    False
    >>> s == e
    False
    >>> s == set()
    False
    >>> set() == s
    False
    >>> s == [1, 2, 6, 3, 7]   # (note: never equal to sequences and other non-set-like iterables)
    False
    >>> [1, 2, 6, 3, 7] == s
    False
    >>> s == (1, 2, 6, 3, 7)
    False
    >>> (1, 2, 6, 3, 7) == s
    False
    >>> s == {1: None, 2: None, 6: None, 3: None, 7: None}
    False
    >>> s == {6: None, 2: None, 3: None, 7: None, 1: None}
    False
    >>> {6: None, 2: None, 3: None, 7: None, 1: None} == s
    False
    >>> e == s
    False
    >>> e == OPSet([1, 2, 6, 3, 7])
    False
    >>> e == {1, 2, 6, 3, 7}
    False
    >>> {1, 2, 6, 3, 7} == e
    False
    >>> e == {1: None, 2: None, 6: None, 3: None, 7: None}.keys()
    False
    >>> {6: None, 2: None, 3: None, 7: None, 1: None}.keys() == e
    False
    >>> e == Submissive([1, 2, 6, 3, 7])
    False
    >>> Submissive([1, 2, 6, 3, 7]) == e
    False
    >>> e == []
    False
    >>> [] == e
    False
    >>> e == ()
    False
    >>> () == e
    False
    >>> e == {}
    False
    >>> {} == e
    False

    >>> s != s
    False
    >>> s != OPSet([1, 2, 6, 3, 7])
    False
    >>> s != OPSet([6, 2, 3, 7, 1])
    False
    >>> s != {1, 2, 6, 3, 7}
    False
    >>> {1, 2, 6, 3, 7} != s
    False
    >>> s != {1: None, 2: None, 6: None, 3: None, 7: None}.keys()
    False
    >>> s != {6: None, 2: None, 3: None, 7: None, 1: None}.keys()
    False
    >>> {6: None, 2: None, 3: None, 7: None, 1: None}.keys() != s
    False
    >>> s != Submissive([1, 2, 6, 3, 7])
    False
    >>> Submissive([6, 2, 3, 7, 1]) != s
    False
    >>> e != e
    False
    >>> e != OPSet()
    False
    >>> e != set()
    False
    >>> set() != e
    False
    >>> e != {}.keys()
    False
    >>> {}.keys() != e
    False
    >>> e != Submissive()
    False
    >>> Submissive() != e
    False

    >>> s != OPSet([6, 2, 3, 7])
    True
    >>> s != {1, 2, 6, 3}
    True
    >>> {1, 2, 6, 3} != s
    True
    >>> s != frozenset({1, 2, 6, 3, 7, 8})
    True
    >>> frozenset({1, 2, 6, 3, 7, 8}) != s
    True
    >>> s != {1: None, 2: None, 6: None, 3: None, 8: None}.keys()
    True
    >>> {1: None, 2: None, 6: None, 3: None, 8: None}.keys() != s
    True
    >>> s != Submissive([2, 6, 3])
    True
    >>> Submissive([2, 6, 3]) != s
    True
    >>> s != e
    True
    >>> s != set()
    True
    >>> set() != s
    True
    >>> s != [1, 2, 6, 3, 7]
    True
    >>> [1, 2, 6, 3, 7] != s
    True
    >>> s != (1, 2, 6, 3, 7)
    True
    >>> (1, 2, 6, 3, 7) != s
    True
    >>> s != {1: None, 2: None, 6: None, 3: None, 7: None}
    True
    >>> s != {6: None, 2: None, 3: None, 7: None, 1: None}
    True
    >>> {6: None, 2: None, 3: None, 7: None, 1: None} != s
    True
    >>> e != s
    True
    >>> e != OPSet([1, 2, 6, 3, 7])
    True
    >>> e != {1, 2, 6, 3, 7}
    True
    >>> {1, 2, 6, 3, 7} != e
    True
    >>> e != {1: None, 2: None, 6: None, 3: None, 7: None}.keys()
    True
    >>> {6: None, 2: None, 3: None, 7: None, 1: None}.keys() != e
    True
    >>> e != Submissive([1, 2, 6, 3, 7])
    True
    >>> Submissive([1, 2, 6, 3, 7]) != e
    True
    >>> e != []
    True
    >>> [] != e
    True
    >>> e != ()
    True
    >>> () != e
    True
    >>> e != {}
    True
    >>> {} != e
    True

    >>> s > s
    False
    >>> s > OPSet([1, 2, 6, 3, 7])
    False
    >>> s > OPSet([6, 2, 3, 7, 1])
    False
    >>> s > Submissive([1, 2, 6, 3, 7])
    False
    >>> Submissive([6, 2, 3, 7, 1]) < s
    False
    >>> s > {1, 2, 6, 3, 7}
    False
    >>> {1, 2, 6, 3, 7} < s
    False
    >>> s > OPSet([6, 2, 3, 1])
    True
    >>> s > Submissive([6, 2, 3, 1])
    True
    >>> Submissive([3, 2, 6, 1]) < s
    True
    >>> s > {1, 2, 6, 3}
    True
    >>> {1, 2, 6, 3} < s
    True
    >>> s > OPSet([6, 2, 3, 8, 7, 1])
    False
    >>> s > Submissive([6, 2, 3, 8, 7, 1])
    False
    >>> Submissive([3, 6, 8, 7, 2, 1]) < s
    False
    >>> s > {1, 2, 6, 3, 7, 8}
    False
    >>> {1, 2, 6, 3, 7, 8} < s
    False
    >>> s > OPSet([6, 2, 3, 8, 1])
    False
    >>> s > Submissive([6, 2, 3, 8, 1])
    False
    >>> Submissive([3, 1, 8, 6, 2]) < s
    False
    >>> s > {1, 2, 6, 3, 8}
    False
    >>> {1, 2, 6, 3, 8} < s
    False
    >>> s > e
    True
    >>> e < s
    True
    >>> e < e
    False
    >>> s > set()
    True
    >>> set() < s
    True
    >>> s > [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] < s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s >= s
    True
    >>> s >= OPSet([1, 2, 6, 3, 7])
    True
    >>> s >= OPSet([6, 2, 3, 7, 1])
    True
    >>> s >= Submissive([1, 2, 6, 3, 7])
    True
    >>> Submissive([6, 2, 3, 7, 1]) <= s
    True
    >>> s >= frozenset({1, 2, 6, 3, 7})
    True
    >>> frozenset({1, 2, 6, 3, 7}) <= s
    True
    >>> s >= OPSet([6, 2, 3, 1])
    True
    >>> s >= Submissive([6, 2, 3, 1])
    True
    >>> Submissive([3, 2, 6, 1]) <= s
    True
    >>> s >= frozenset({1, 2, 6, 3})
    True
    >>> frozenset({1, 2, 6, 3}) <= s
    True
    >>> s >= OPSet([6, 2, 3, 8, 7, 1])
    False
    >>> s >= Submissive([6, 2, 3, 8, 7, 1])
    False
    >>> Submissive([3, 6, 8, 7, 2, 1]) <= s
    False
    >>> s >= frozenset({1, 2, 6, 3, 7, 8})
    False
    >>> frozenset({1, 2, 6, 3, 7, 8}) <= s
    False
    >>> s >= OPSet([6, 2, 3, 8, 1])
    False
    >>> s >= Submissive([6, 2, 3, 8, 1])
    False
    >>> Submissive([3, 1, 8, 6, 2]) <= s
    False
    >>> s >= frozenset({1, 2, 6, 3, 8})
    False
    >>> frozenset({1, 2, 6, 3, 8}) <= s
    False
    >>> s >= e
    True
    >>> e <= s
    True
    >>> e <= e
    True
    >>> s >= frozenset({})
    True
    >>> frozenset({}) <= s
    True
    >>> s >= [1, 2, 6, 3, 7]                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] <= s                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s < s
    False
    >>> s < OPSet([1, 2, 6, 3, 7])
    False
    >>> s < OPSet([6, 2, 3, 7, 1])
    False
    >>> s < Submissive([1, 2, 6, 3, 7])
    False
    >>> Submissive([6, 2, 3, 7, 1]) > s
    False
    >>> s < {1: None, 2: None, 6: None, 3: None, 7: None}.keys()
    False
    >>> {1: None, 2: None, 6: None, 3: None, 7: None}.keys() > s
    False
    >>> s < OPSet([6, 2, 3, 1])
    False
    >>> s < Submissive([6, 2, 3, 1])
    False
    >>> Submissive([3, 2, 6, 1]) > s
    False
    >>> s < {1: None, 2: None, 6: None, 3: None}.keys()
    False
    >>> {1: None, 2: None, 6: None, 3: None}.keys() > s
    False
    >>> s < OPSet([6, 2, 3, 8, 7, 1])
    True
    >>> s < Submissive([6, 2, 3, 8, 7, 1])
    True
    >>> Submissive([3, 6, 8, 7, 2, 1]) > s
    True
    >>> s < {1: None, 2: None, 6: None, 3: None, 7: None, 8: None}.keys()
    True
    >>> {1: None, 2: None, 6: None, 3: None, 7: None, 8: None}.keys() > s
    True
    >>> s < OPSet([6, 2, 3, 8, 1])
    False
    >>> s < Submissive([6, 2, 3, 8, 1])
    False
    >>> Submissive([3, 1, 8, 6, 2]) > s
    False
    >>> s < {1: None, 2: None, 6: None, 3: None, 8: None}.keys()
    False
    >>> {1: None, 2: None, 6: None, 3: None, 8: None}.keys() > s
    False
    >>> s < e
    False
    >>> e < s
    True
    >>> e < e
    False
    >>> s < {}.keys()
    False
    >>> {}.keys() > s
    False
    >>> s < [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] > s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s <= s
    True
    >>> s <= OPSet([1, 2, 6, 3, 7])
    True
    >>> s <= OPSet([6, 2, 3, 7, 1])
    True
    >>> s <= Submissive([1, 2, 6, 3, 7])
    True
    >>> Submissive([6, 2, 3, 7, 1]) >= s
    True
    >>> s <= {1, 2, 6, 3, 7}
    True
    >>> {1, 2, 6, 3, 7} >= s
    True
    >>> s <= OPSet([6, 2, 3, 1])
    False
    >>> s <= Submissive([6, 2, 3, 1])
    False
    >>> Submissive([3, 2, 6, 1]) >= s
    False
    >>> s <= {1, 2, 6, 3}
    False
    >>> {1, 2, 6, 3} >= s
    False
    >>> s <= OPSet([6, 2, 3, 8, 7, 1])
    True
    >>> s <= Submissive([6, 2, 3, 8, 7, 1])
    True
    >>> Submissive([3, 6, 8, 7, 2, 1]) >= s
    True
    >>> s <= {1, 2, 6, 3, 7, 8}
    True
    >>> {1, 2, 6, 3, 7, 8} >= s
    True
    >>> s <= OPSet([6, 2, 3, 8, 1])
    False
    >>> s <= Submissive([6, 2, 3, 8, 1])
    False
    >>> Submissive([3, 1, 8, 6, 2]) >= s
    False
    >>> s <= {1, 2, 6, 3, 8}
    False
    >>> {1, 2, 6, 3, 8} >= s
    False
    >>> s <= e
    False
    >>> e <= s
    True
    >>> e <= e
    True
    >>> s <= set()
    False
    >>> set() >= s
    False
    >>> s <= [1, 2, 6, 3, 7]                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] >= s                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s.isdisjoint(OPSet([5, 8, 4]))
    True
    >>> s.isdisjoint(frozenset({5, 8, 4}))
    True
    >>> s.isdisjoint({5: None, 8: None, 4: None}.keys())
    True
    >>> s.isdisjoint([5, 8, 4])   # Note: `isdisjoint()` accepts any iterable of hashable objects.
    True
    >>> s.isdisjoint((5, 8, 4))
    True
    >>> s.isdisjoint({5: None, 8: None, 4: None})
    True
    >>> s.isdisjoint(e)
    True
    >>> e.isdisjoint(s)
    True
    >>> e.isdisjoint(e)
    True
    >>> e.isdisjoint(())
    True
    >>> s.isdisjoint(s)
    False
    >>> s.isdisjoint({1, 2, 6, 3, 7})
    False
    >>> s.isdisjoint({2: None, 6: None}.keys())
    False
    >>> s.isdisjoint([3, 6, 8, 7, 2, 1])
    False
    >>> s.isdisjoint((3, 1, 8, 6, 2))
    False
    >>> s.isdisjoint({2: None, 6: None})
    False
    >>> e.isdisjoint(2)                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s & s
    OPSet([1, 2, 6, 3, 7])
    >>> s & OPSet([9, 1, 2, 6, 3, 8])
    OPSet([1, 2, 6, 3])
    >>> s & OPSet([3, 9, 6, 8, 2, 1])
    OPSet([1, 2, 6, 3])
    >>> s & {1, 2, 6, 3, 8}
    OPSet([1, 2, 6, 3])
    >>> s & {9: None, 1: None, 2: None, 6: None, 3: None, 8: None}.keys()
    OPSet([1, 2, 6, 3])
    >>> s & Submissive([9, 1, 2, 6, 3, 8])
    OPSet([1, 2, 6, 3])
    >>> Submissive([9, 1, 2, 6, 3, 8]) & s
    OPSet([1, 2, 6, 3])
    >>> s & Submissive([3, 9, 6, 2, 8, 1])
    OPSet([1, 2, 6, 3])
    >>> Submissive([3, 9, 6, 2, 8, 1]) & s   # (note the order)
    OPSet([3, 6, 2, 1])
    >>> s & e
    OPSet()
    >>> e & s
    OPSet()
    >>> e & e
    OPSet()
    >>> s & set()
    OPSet()
    >>> s & [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] & s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s | s
    OPSet([1, 2, 6, 3, 7])
    >>> s | OPSet([9, 1, 2, 6, 3, 8])
    OPSet([1, 2, 6, 3, 7, 9, 8])
    >>> s | OPSet([3, 9, 6, 8, 2, 1])
    OPSet([1, 2, 6, 3, 7, 9, 8])
    >>> s | {1, 2, 6, 3, 8}
    OPSet([1, 2, 6, 3, 7, 8])
    >>> s | {9: None, 1: None, 2: None, 6: None, 3: None, 8: None}.keys()
    OPSet([1, 2, 6, 3, 7, 9, 8])
    >>> s | Submissive([9, 1, 2, 6, 3, 8])
    OPSet([1, 2, 6, 3, 7, 9, 8])
    >>> Submissive([9, 1, 2, 6, 3, 8]) | s   # (note the order)
    OPSet([9, 1, 2, 6, 3, 8, 7])
    >>> s | Submissive([3, 9, 6, 2, 8, 1])
    OPSet([1, 2, 6, 3, 7, 9, 8])
    >>> Submissive([3, 9, 6, 2, 8, 1]) | s   # (note the order)
    OPSet([3, 9, 6, 2, 8, 1, 7])
    >>> s | e
    OPSet([1, 2, 6, 3, 7])
    >>> e | s
    OPSet([1, 2, 6, 3, 7])
    >>> e | e
    OPSet()
    >>> s | set()
    OPSet([1, 2, 6, 3, 7])
    >>> s | [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] | s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s - s
    OPSet()
    >>> s - OPSet([9, 2, 6, 8])
    OPSet([1, 3, 7])
    >>> s - OPSet([6, 9, 8, 2])
    OPSet([1, 3, 7])
    >>> s - {9, 2, 6, 8}
    OPSet([1, 3, 7])
    >>> s - {9: None, 2: None, 6: None, 8: None}.keys()
    OPSet([1, 3, 7])
    >>> s - Submissive([9, 2, 6, 8])
    OPSet([1, 3, 7])
    >>> Submissive([1, 2, 6, 3, 7]) - OPSet([9, 2, 6, 8])
    OPSet([1, 3, 7])
    >>> s - Submissive([6, 9, 8, 2])
    OPSet([1, 3, 7])
    >>> Submissive([1, 2, 6, 3, 7]) - OPSet([2, 9, 6, 8])
    OPSet([1, 3, 7])
    >>> s - e
    OPSet([1, 2, 6, 3, 7])
    >>> e - s
    OPSet()
    >>> e - e
    OPSet()
    >>> s - set()
    OPSet([1, 2, 6, 3, 7])
    >>> s - [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] - s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> s ^ s
    OPSet()
    >>> s ^ OPSet([9, 2, 6, 8])
    OPSet([1, 3, 7, 9, 8])
    >>> s ^ OPSet([6, 9, 8, 2])
    OPSet([1, 3, 7, 9, 8])
    >>> s ^ {2, 6, 8}
    OPSet([1, 3, 7, 8])
    >>> s ^ {9: None, 2: None, 6: None, 8: None}.keys()
    OPSet([1, 3, 7, 9, 8])
    >>> s ^ Submissive([9, 2, 6, 8])
    OPSet([1, 3, 7, 9, 8])
    >>> Submissive([9, 2, 6, 8]) ^ s   # (note the order)
    OPSet([9, 8, 1, 3, 7])
    >>> s ^ Submissive([6, 9, 8, 2])
    OPSet([1, 3, 7, 9, 8])
    >>> Submissive([6, 9, 8, 2]) ^ s   # (note the order)
    OPSet([9, 8, 1, 3, 7])
    >>> s ^ e
    OPSet([1, 2, 6, 3, 7])
    >>> e ^ s
    OPSet([1, 2, 6, 3, 7])
    >>> e ^ e
    OPSet()
    >>> s ^ set()
    OPSet([1, 2, 6, 3, 7])
    >>> s ^ [1, 2, 6, 3, 7]                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> [1, 2, 6, 3, 7] ^ s                 # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> d = {
    ...     OPSet([1, 2, 6, 3, 7]): 62371,
    ...     frozenset({1, 2, 3}): 123,
    ... }
    >>> s2 = OPSet([
    ...     OPSet([1, 2, 6, 3, 7]),
    ...     frozenset({1, 2, 3}),
    ... ])
    >>> s in d and s in s2
    True
    >>> e in d or e in s2
    False
    >>> frozenset({6, 2, 3, 7, 1}) in d and frozenset({6, 2, 3, 7, 1}) in s2
    True
    >>> d[s]
    62371
    >>> d[OPSet([6, 2, 3, 7, 1])]
    62371
    >>> OPSet([6, 2, 3, 7, 1]) in s2
    True
    >>> OPSet([6, 2, 3, 7]) in s2
    False
    >>> OPSet([6, 2, 3, 7]) in d
    False
    >>> frozenset({6, 2, 3, 7, 1, 8}) in d
    False
    >>> frozenset({6, 2, 3, 7, 1, 8}) in s2
    False
    >>> OPSet([6, 2, 3, 7, 8]) in d
    False
    >>> OPSet([6, 2, 3, 7, 8]) in s2
    False
    >>> d[OPSet([1, 2, 3])]
    123
    >>> d[OPSet([3, 2, 1])]
    123
    >>> OPSet([1, 2, 3]) in s2
    True
    >>> OPSet([3, 2, 1]) in s2
    True
    >>> ((1, 2, 3) in d
    ...  or (1, 2, 6, 3, 7) in d
    ...  or (6, 2, 3, 7, 1) in d
    ...  or (1, 2, 3) in s2
    ...  or (1, 2, 6, 3, 7) in s2
    ...  or (6, 2, 3, 7, 1) in s2)
    False
    """

    def __new__(
            cls,
            elements: Iterable[_ElemT_co] = (),
            *,
            # (hack for efficiency)
            _type=type,
            _object_new=object.__new__,
            _dict_fromkeys=dict.fromkeys) -> 'OPSet[_ElemT_co]':

        if _type(elements) is cls:
            return elements  # noqa

        new = _object_new(cls)
        new._d = _dict_fromkeys(elements)
        return new

    # (non-public instance attribute, treated as immutable/read-only)
    _d: dict[_ElemT_co, None]

    def __repr__(self) -> str:
        cls_name = self.__class__.__qualname__
        arg_repr = repr(list(self._d)) if self else ''
        return f'{cls_name}({arg_repr})'

    def __len__(
            self,
            # (hack for efficiency)
            _dict_len=dict.__len__) -> int:
        return _dict_len(self._d)

    def __contains__(
            self, elem: Hashable,
            # (hack for efficiency)
            _dict_contains=dict.__contains__) -> bool:
        return _dict_contains(self._d, elem)

    def __iter__(
            self,
            # (hack for efficiency)
            _dict_iter=dict.__iter__) -> Iterator[_ElemT_co]:
        return _dict_iter(self._d)

    def __reversed__(
            self,
            # (hack for efficiency)
            _dict_reversed=dict.__reversed__) -> Iterator[_ElemT_co]:
        return _dict_reversed(self._d)

    def __hash__(self) -> int:
        return self._hash_value

    @functools.cached_property
    def _hash_value(
            self,
            # (hack for efficiency)
            _hash=hash,
            _frozenset=frozenset) -> int:
        return _hash(_frozenset(self._d))

    # `__eq__()`, `__ne__()`, `__le__()`, `__ge__()` and `isdisjoint()`
    # are overridden for efficiency, and also for better type hints:

    _dict_keys_type = type({}.keys())

    def __eq__(
            self,
            other: Set[Hashable],
            # (hack for efficiency)
            _type=type,
            _dict_keys=dict.keys,
            _dict_keys_eq=_dict_keys_type.__eq__) -> bool:
        if _type(other) is __class__:
            return _dict_keys_eq(_dict_keys(self._d), _dict_keys(other._d))
        res = _dict_keys_eq(_dict_keys(self._d), other)
        if res is NotImplemented:
            return super().__eq__(other)
        return res

    __ne__: Callable[[Set[Hashable]], bool] = object.__ne__

    def __le__(
            self,
            other: Set[Hashable],
            # (hack for efficiency)
            _type=type,
            _dict_keys=dict.keys,
            _dict_keys_le=_dict_keys_type.__le__) -> bool:
        if _type(other) is __class__:
            return _dict_keys_le(_dict_keys(self._d), _dict_keys(other._d))
        res = _dict_keys_le(_dict_keys(self._d), other)
        if res is NotImplemented:
            return super().__le__(other)
        return res

    def __ge__(
            self,
            other: Set[Hashable],
            # (hack for efficiency)
            _type=type,
            _dict_keys=dict.keys,
            _dict_keys_ge=_dict_keys_type.__ge__) -> bool:
        if _type(other) is __class__:
            return _dict_keys_ge(_dict_keys(self._d), _dict_keys(other._d))
        res = _dict_keys_ge(_dict_keys(self._d), other)
        if res is NotImplemented:
            return super().__ge__(other)
        return res

    def isdisjoint(
            self,
            other: Iterable[Hashable],
            *,
            # (hack for efficiency)
            _dict_keys=dict.keys,
            _dict_keys_isdisjoint=_dict_keys_type.isdisjoint) -> bool:
        return _dict_keys_isdisjoint(_dict_keys(self._d), other)

    # Implementations of `&`, `|`, `-` and `^` are overridden to provide
    # proper order of elements in results, to reject non-`Set` iterables
    # as well as for better type hints:

    def __and__(self, other: Set[Hashable]) -> 'OPSet[_ElemT_co]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(
            value for value in self
            if value in other)

    def __rand__(self, other: Set[Hashable]) -> 'OPSet[_ElemT_co]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(
            value for value in other
            if value in self)

    def __or__(self, other: Set[HashableT]) -> 'OPSet[Union[_ElemT_co, HashableT]]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(itertools.chain(self, other))

    def __ror__(self, other: Set[HashableT]) -> 'OPSet[Union[_ElemT_co, HashableT]]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(itertools.chain(other, self))

    def __sub__(self, other: Set[Hashable]) -> 'OPSet[_ElemT_co]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(
            value for value in self
            if value not in other)

    def __rsub__(self, other: Set[HashableT]) -> 'OPSet[HashableT]':
        if not isinstance(other, Set):
            return NotImplemented
        return self.__class__(
            value for value in other
            if value not in self)

    def __xor__(self, other: Set[HashableT]) -> 'OPSet[Union[_ElemT_co, HashableT]]':
        if not isinstance(other, Set):
            return NotImplemented
        other = self.__class__(other)
        return (self - other) | (other - self)

    def __rxor__(self, other: Set[HashableT]) -> 'OPSet[Union[_ElemT_co, HashableT]]':
        if not isinstance(other, Set):
            return NotImplemented
        other = self.__class__(other)
        return (other - self) | (self - other)


class DictWithSomeHooks(dict):

    """
    A convenient base for some kinds of `dict` subclasses.

    * It is a real subclass of the built-in `dict` type (contrary to
      some of the other mapping classes defined in this module).

    * You can extend/override the `_custom_key_error()` instance method
      in your subclasses to customize exceptions raised by the
      `__getitem__()`/`__delitem__()`/` pop()` methods, as well as --
      optionally -- by the `popitem()` method (the latter only if the
      attribute `_custom_key_error_also_for_popitem` is overridden
      by setting it to a true value). Your implementation of
      `_custom_key_error()` should take two positional arguments: the
      originally raised `KeyError` instance and the name of the method
      (`'__getitem__'` or `'__delitem__'`, or `'pop'`, or `'popitem'`);
      the standard implementation just returns the given `KeyError`
      instance intact.

    * The class provides a ready-to-use and recursion-proof `__repr__()`
      -- you can easily customize it by extending/overriding the
      `_constructor_args_repr()` method in your subclasses (see the
      example below); another option is, of course, to override
      the `__repr__()` method completely.

    * Important: you should *not* replace the `__init__()` method
      completely in your subclasses -- but only extend it (preferrably,
      using `super()`).

    * Your extended `__init__()` (provided by a subclass) can take any
      arguments, i.e., its signature does not need to be compatible with
      the standard one provided by `dict` (see the example below) --
      *except that*, in order to get sensible results of `__repr__()`,
      you may want to customize the `_constructor_args_repr()` method
      (see the relevant bullet point above...).

    * However, if you extend `__init__()` and still want your subclass
      to support the (rarely used) `fromkeys()` class method, you need
      to override the `_standard_fromkeys_enabled` class attribute (in
      your subclass) by setting it to a true value -- **and ensuring**
      that your extended `__init__()` is able to take a plain `dict`
      of items as the sole positional argument (note that the default
      version of `__init__()`, provided by `DictWithSomeHooks`, meets
      this requirement -- that's why there is no need to set the
      aforementioned class attribute if `__init__()` is not extended).
      Alternatively, you can provide your custom implementation of
      `fromkeys()`.

    * Instances of the class support copying: both shallow copying (do
      it by calling the `copy()` method or the `copy()` function from
      the `copy` module) and deep copying (do it by calling the
      `deepcopy()` function from the `copy` module) -- including copying
      instance attributes and including support for recursive mappings.

      Please note, however, that those copying operations are supposed
      to work properly **only if** the `items()` and `update()` methods
      meet the following requirements, if customized in a subclass (their
      standard implementations meet that requirements out-of-the-box):
      (1) `items()` should produce `(<hashable key>, <corresponding
      value>)` pairs (one for each item of the mapping); (2) `update()`
      should be able to update the content of the mapping with items
      specified as a plain `dict` passed in as the sole positional
      argument; note: the order of items is preserved *only if* those
      two methods preserve it.

    * The `|` operator (merging two instances) is supported as well
      -- **provided that** the `items()` and `update()` methods meet
      the requirements described above in the context of the copying
      operations. When it comes to allowed types of the other operand,
      the `DictWithSomeHooks`'s version of `|` is more liberal than the
      `dict`'s version: any instance (real or "virtual") of a subclass
      of `collections.abc.Mapping` is acceptable (not necessarily of
      `dict`).

    * The behavior of the `|=` operator is analogous to that of the
      `dict`'s version of it, i.e., is equivalent to the standard
      `update()` operation -- so, in particular, any mapping-like
      object, as well as any iterable producing `(<hashable key>,
      <corresponding value>)` pairs, is acceptable as the right-hand
      operand.

    ***

    >>> class MyStrangeDict(DictWithSomeHooks):
    ...
    ...     def __init__(self, a, b, c=42):
    ...         super().__init__(b=b)
    ...         self.a = a
    ...         self.c = self['c'] = c
    ...
    ...     # examples of implementation of the two customization hooks:
    ...
    ...     def _constructor_args_repr(self):
    ...         return '<' + repr(sorted(self.items(), key=repr)) + '>'
    ...
    ...     def _custom_key_error(self, key_error, method_name):
    ...         e = super()._custom_key_error(key_error, method_name)
    ...         return ValueError(*(e.args + (method_name,)))
    ...
    ...     # Note: `__init__()` of this class is extended in such a
    ...     # way that it is not able to take a dict of items as the
    ...     # sole argument -- so we must leave the class attribute
    ...     # `_standard_fromkeys_enabled` as it is (i.e., set to
    ...     # `False`). A possible alternative could be to provide our
    ...     # own implementation of the `fromkeys()` class method
    ...     # (however, in practice `fromkeys()` is rarely needed).
    ...
    >>> d = MyStrangeDict(['A'], {'B': 'BB'})
    >>> (isinstance(d, MyStrangeDict) and
    ...  isinstance(d, DictWithSomeHooks) and
    ...  isinstance(d, dict) and
    ...  isinstance(d, MutableMapping) and
    ...  isinstance(d, Mapping))
    True
    >>> d == {'b': {'B': 'BB'}, 'c': 42}
    True

    >>> d
    MyStrangeDict(<[('b', {'B': 'BB'}), ('c', 42)]>)
    >>> d.a
    ['A']
    >>> d.c
    42

    >>> d['a']
    Traceback (most recent call last):
      ...
    ValueError: ('a', '__getitem__')

    >>> 'a' in d
    False
    >>> d['a'] = d.a
    >>> d['a']
    ['A']
    >>> 'a' in d
    True

    >>> d['c']
    42
    >>> del d['c']
    >>> del d['c']
    Traceback (most recent call last):
      ...
    ValueError: ('c', '__delitem__')
    >>> d.pop('c')
    Traceback (most recent call last):
      ...
    ValueError: ('c', 'pop')
    >>> d.pop('c', 'CCC')
    'CCC'
    >>> d == {'a': ['A'], 'b': {'B': 'BB'}}
    True
    >>> bool(d)
    True

    >>> d
    MyStrangeDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
    >>> d.a
    ['A']
    >>> d.c
    42

    >>> d._repr_recur_thread_ids.add('xyz')  # (in all doctests, this attribute is touched only
    >>> from unittest.mock import ANY        # to test certain internal behaviors; doing anything
    >>> vars(d) == {                         # with it in a production code is not a good idea)
    ...     'a': ['A'],
    ...     'c': 42,
    ...     '_repr_recur_thread_ids': {'xyz'},
    ...     '_repr_recur_thread_ids_rlock': ANY,
    ... }
    True

    >>> d_shallowcopy = d.copy()  # the same as copy.copy(d)
    >>> d_shallowcopy
    MyStrangeDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
    >>> d_shallowcopy == d
    True
    >>> d_shallowcopy is d
    False
    >>> d.c == d_shallowcopy.c == 42
    True
    >>> d['a'] == d.a == d_shallowcopy['a'] == d_shallowcopy.a == ['A']
    True
    >>> d['a'] is d.a is d_shallowcopy['a'] is d_shallowcopy.a
    True
    >>> d['b'] == d_shallowcopy['b'] == {'B': 'BB'}
    True
    >>> d['b'] is d_shallowcopy['b']
    True
    >>> (d._repr_recur_thread_ids == set({'xyz'}) and
    ...  d_shallowcopy._repr_recur_thread_ids == set())  # note this!
    True

    >>> d_deepcopy = copy.deepcopy(d)
    >>> d_deepcopy
    MyStrangeDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
    >>> d_deepcopy == d
    True
    >>> d_deepcopy is d
    False
    >>> d.c == d_deepcopy.c == 42
    True
    >>> d['a'] == d.a == d_deepcopy['a'] == d_deepcopy.a == ['A']
    True
    >>> d['a'] is d_deepcopy['a']  # note this
    False
    >>> d['a'] is d_deepcopy.a     # note this
    False
    >>> d.a is d_deepcopy.a        # note this
    False
    >>> d.a is d_deepcopy['a']     # note this
    False
    >>> d['a'] is d.a
    True
    >>> d_deepcopy['a'] is d_deepcopy.a  # note this
    True
    >>> d['b'] == d_deepcopy['b'] == {'B': 'BB'}
    True
    >>> d['b'] is d_deepcopy['b']  # note this
    False
    >>> (d._repr_recur_thread_ids == set({'xyz'}) and
    ...  d_deepcopy._repr_recur_thread_ids == set())   # note this!
    True

    >>> class RecurKey:
    ...     def __repr__(self): return '$$$'
    ...     def __hash__(self): return 42
    ...     def __eq__(self, other): return isinstance(other, RecurKey)
    ...
    >>> recur_key = RecurKey()
    >>> recur_d = copy.deepcopy(d)
    >>> recur_d._repr_recur_thread_ids.add('quux')
    >>> vars(recur_d) == {
    ...     'a': ['A'],
    ...     'c': 42,
    ...     '_repr_recur_thread_ids': {'quux'},
    ...     '_repr_recur_thread_ids_rlock': ANY,
    ... }
    True
    >>> recur_d[recur_key] = recur_d
    >>> recur_d['b'] = recur_d.b = recur_d
    >>> recur_d
    MyStrangeDict(<[($$$, MyStrangeDict(<...>)), ('a', ['A']), ('b', MyStrangeDict(<...>))]>)

    >>> recur_d_deepcopy = copy.deepcopy(recur_d)
    >>> recur_d_deepcopy
    MyStrangeDict(<[($$$, MyStrangeDict(<...>)), ('a', ['A']), ('b', MyStrangeDict(<...>))]>)
    >>> recur_d_deepcopy is recur_d
    False
    >>> [dc_recur_key] = [k for k in recur_d_deepcopy if k == recur_key]
    >>> (dc_recur_key == recur_key and
    ...  hash(dc_recur_key) == hash(recur_key))
    True
    >>> dc_recur_key is recur_key
    False
    >>> (recur_d is                                      # note this!
    ...  recur_d[recur_key] is
    ...  recur_d[recur_key][recur_key] is
    ...  recur_d[recur_key][recur_key][recur_key] is
    ...  recur_d[dc_recur_key] is
    ...  recur_d[dc_recur_key][dc_recur_key] is
    ...  recur_d[dc_recur_key][dc_recur_key][dc_recur_key] is
    ...  recur_d[dc_recur_key][recur_key][dc_recur_key] is
    ...  recur_d[recur_key][dc_recur_key][recur_key] is
    ...  recur_d['b'] is
    ...  recur_d['b']['b'] is
    ...  recur_d['b']['b']['b'] is
    ...  recur_d.b is
    ...  recur_d.b.b is
    ...  recur_d.b.b.b)
    True
    >>> (recur_d_deepcopy is                             # note this!
    ...  recur_d_deepcopy[recur_key] is
    ...  recur_d_deepcopy[recur_key][recur_key] is
    ...  recur_d_deepcopy[recur_key][recur_key][recur_key] is
    ...  recur_d_deepcopy[dc_recur_key] is
    ...  recur_d_deepcopy[dc_recur_key][dc_recur_key] is
    ...  recur_d_deepcopy[dc_recur_key][dc_recur_key][dc_recur_key] is
    ...  recur_d_deepcopy[dc_recur_key][recur_key][dc_recur_key] is
    ...  recur_d_deepcopy[recur_key][dc_recur_key][recur_key] is
    ...  recur_d_deepcopy['b'] is
    ...  recur_d_deepcopy['b']['b'] is
    ...  recur_d_deepcopy['b']['b']['b'] is
    ...  recur_d_deepcopy.b is
    ...  recur_d_deepcopy.b.b is
    ...  recur_d_deepcopy.b.b.b)
    True
    >>> recur_d.c == recur_d_deepcopy.c == 42
    True
    >>> (recur_d['a'] == recur_d.a ==
    ...  recur_d_deepcopy['a'] == recur_d_deepcopy.a == ['A'])
    True
    >>> recur_d['a'] is recur_d_deepcopy['a']
    False
    >>> recur_d['a'] is recur_d_deepcopy.a
    False
    >>> recur_d.a is recur_d_deepcopy.a
    False
    >>> recur_d.a is recur_d_deepcopy['a']
    False
    >>> recur_d['a'] is recur_d.a
    True
    >>> recur_d_deepcopy['a'] is recur_d_deepcopy.a
    True
    >>> (recur_d._repr_recur_thread_ids == set({'quux'}) and
    ...  recur_d_deepcopy._repr_recur_thread_ids == set())
    True

    >>> recur_d_shallowcopy = copy.copy(recur_d)
    >>> recur_d_shallowcopy                               # doctest: +ELLIPSIS
    MyStrangeDict(<[($$$, MyStrangeDict(<[($$$, MyStrangeDict(<...>)), ('a', ...

    >>> recur_d_shallowcopy == recur_d
    True
    >>> recur_d_shallowcopy is recur_d
    False
    >>> [sc_recur_key] = [k for k in recur_d_shallowcopy if k == recur_key]
    >>> sc_recur_key is recur_key
    True
    >>> (recur_d is
    ...  recur_d_shallowcopy[recur_key] is
    ...  recur_d_shallowcopy[recur_key][recur_key] is
    ...  recur_d_shallowcopy[recur_key][recur_key][recur_key] is
    ...  recur_d_shallowcopy['b'] is
    ...  recur_d_shallowcopy['b']['b'] is
    ...  recur_d_shallowcopy['b']['b']['b'] is
    ...  recur_d_shallowcopy.b is
    ...  recur_d_shallowcopy.b.b is
    ...  recur_d_shallowcopy.b.b.b)
    True
    >>> recur_d.c == recur_d_shallowcopy.c == 42
    True
    >>> (recur_d['a'] == recur_d.a ==
    ...  recur_d_shallowcopy['a'] == recur_d_shallowcopy.a == ['A'])
    True
    >>> (recur_d['a'] is recur_d.a is
    ...  recur_d_shallowcopy['a'] is recur_d_shallowcopy.a)
    True
    >>> (recur_d._repr_recur_thread_ids == set({'quux'}) and
    ...  recur_d_shallowcopy._repr_recur_thread_ids == set())
    True

    >>> dd = MyStrangeDict(['A'], {'B': 'BB'})
    >>> dd._repr_recur_thread_ids.add('SPAM!')
    >>> dd['dd'] = True
    >>> dd
    MyStrangeDict(<[('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> another = MyStrangeDict(['Ale-Ale'], {'Be-Be-Be': 12345}, c=997)
    >>> another._repr_recur_thread_ids.add('fiu fiu')
    >>> another['an'] = 1.0
    >>> another
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997)]>)
    >>> (another.a, another.c)
    (['Ale-Ale'], 997)

    >>> dd_another_merged = dd | another
    >>> dd_another_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997), ('dd', True)]>)
    >>> dd_another_merged == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997, 'dd': True}
    True
    >>> dd_another_merged['b'] is another['b']
    True
    >>> (dd_another_merged.a, dd_another_merged.c)  # note this
    (['A'], 42)
    >>> dd_another_merged.a is dd.a
    True
    >>> another_dd_merged = another | dd
    >>> another_dd_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> another_dd_merged == {'an': 1.0, 'b': {'B': 'BB'}, 'c': 42, 'dd': True}
    True
    >>> another_dd_merged['b'] is dd['b']
    True
    >>> (another_dd_merged.a, another_dd_merged.c)  # note this
    (['Ale-Ale'], 997)
    >>> another_dd_merged.a is another.a
    True
    >>> (dd._repr_recur_thread_ids == set({'SPAM!'}) and
    ...  another._repr_recur_thread_ids == set({'fiu fiu'}) and
    ...  dd_another_merged._repr_recur_thread_ids == set() and
    ...  another_dd_merged._repr_recur_thread_ids == set())
    True

    >>> empty = MyStrangeDict(['A'], {'B': 'BB'})
    >>> empty._repr_recur_thread_ids.add('Eee!')
    >>> empty.clear()
    >>> empty
    MyStrangeDict(<[]>)
    >>> (empty.a, empty.c)
    (['A'], 42)
    >>> another
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997)]>)
    >>> (another.a, another.c)
    (['Ale-Ale'], 997)

    >>> empty_another_merged = empty | another
    >>> empty_another_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997)]>)
    >>> another == empty_another_merged == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997}
    True
    >>> empty_another_merged['b'] is another['b']
    True
    >>> (empty_another_merged.a, empty_another_merged.c)  # note this
    (['A'], 42)
    >>> empty_another_merged.a is empty.a
    True
    >>> another_empty_merged = another | empty
    >>> another_empty_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997)]>)
    >>> another == another_empty_merged == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997}
    True
    >>> another_empty_merged['b'] is another['b']
    True
    >>> (another_empty_merged.a, another_empty_merged.c)  # note this
    (['Ale-Ale'], 997)
    >>> another_empty_merged.a is another.a
    True
    >>> (empty._repr_recur_thread_ids == set({'Eee!'}) and
    ...  another._repr_recur_thread_ids == set({'fiu fiu'}) and
    ...  empty_another_merged._repr_recur_thread_ids == set() and
    ...  another_empty_merged._repr_recur_thread_ids == set())
    True

    >>> plain_dict = {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997}
    >>> dd
    MyStrangeDict(<[('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> dd_dict_merged = dd | plain_dict
    >>> dd_dict_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997), ('dd', True)]>)
    >>> dd_dict_merged == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997, 'dd': True}
    True
    >>> dd_dict_merged['b'] is plain_dict['b']
    True
    >>> (dd_dict_merged.a, dd_dict_merged.c)
    (['A'], 42)
    >>> dict_dd_merged = plain_dict | dd
    >>> dict_dd_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> dict_dd_merged == {'an': 1.0, 'b': {'B': 'BB'}, 'c': 42, 'dd': True}
    True
    >>> dict_dd_merged['b'] is dd['b']
    True
    >>> (dict_dd_merged.a, dict_dd_merged.c)
    (['A'], 42)
    >>> (dd._repr_recur_thread_ids == set({'SPAM!'}) and
    ...  dd_dict_merged._repr_recur_thread_ids == set() and
    ...  dict_dd_merged._repr_recur_thread_ids == set())
    True

    >>> class NonDictMapping(Mapping):
    ...     def __init__(self, d): self._d = d
    ...     def __getitem__(self, key): return self._d[key]
    ...     def __iter__(self): return iter(self._d)
    ...     def __len__(self): return len(self._d)
    ...
    >>> nondict_mapping = NonDictMapping({'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997})
    >>> dd
    MyStrangeDict(<[('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> dd_mapping_merged = dd | nondict_mapping
    >>> dd_mapping_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997), ('dd', True)]>)
    >>> dd_mapping_merged == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997, 'dd': True}
    True
    >>> dd_mapping_merged['b'] is nondict_mapping['b']
    True
    >>> (dd_mapping_merged.a, dd_mapping_merged.c)
    (['A'], 42)
    >>> mapping_dd_merged = nondict_mapping | dd
    >>> mapping_dd_merged
    MyStrangeDict(<[('an', 1.0), ('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> mapping_dd_merged == {'an': 1.0, 'b': {'B': 'BB'}, 'c': 42, 'dd': True}
    True
    >>> mapping_dd_merged['b'] is dd['b']
    True
    >>> (mapping_dd_merged.a, mapping_dd_merged.c)
    (['A'], 42)
    >>> (dd._repr_recur_thread_ids == set({'SPAM!'}) and
    ...  dd_mapping_merged._repr_recur_thread_ids == set() and
    ...  mapping_dd_merged._repr_recur_thread_ids == set())
    True

    >>> class SubclassWithOwnOr(MyStrangeDict):
    ...     def __or__(self, _): return 'a ku ku'
    ...     def __ror__(self, _): return 'tra-la-la'
    ...
    >>> subclass_with_own_or = SubclassWithOwnOr('Aaa', 'Bbb', 'Ccc')
    >>> dd | subclass_with_own_or  # note this
    'tra-la-la'
    >>> subclass_with_own_or | dd  # note this
    'a ku ku'

    >>> class NonDictMappingWithOwnOr(NonDictMapping):
    ...     def __or__(self, _): return 'a ku ku'
    ...     def __ror__(self, _): return 'tra-la-la'
    ...
    >>> mapping_with_own_or = NonDictMappingWithOwnOr({'an': 1.0, 'b': {'Ha-Ha': -1}, 'c': -2})
    >>> dd | mapping_with_own_or
    MyStrangeDict(<[('an', 1.0), ('b', {'Ha-Ha': -1}), ('c', -2), ('dd', True)]>)
    >>> mapping_with_own_or | dd  # note this
    'a ku ku'

    >>> class NonMappingWithOwnOr:
    ...     def __or__(self, _): return 'a ku ku'
    ...     def __ror__(self, _): return 'tra-la-la'
    ...
    >>> nonmapping_with_own_or = NonMappingWithOwnOr()
    >>> dd | nonmapping_with_own_or
    'tra-la-la'
    >>> nonmapping_with_own_or | dd
    'a ku ku'

    >>> nonmapping_iterable = [('b', []), ('x', 3)]
    >>> dd | nonmapping_iterable        # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> dd
    MyStrangeDict(<[('b', {'B': 'BB'}), ('c', 42), ('dd', True)]>)
    >>> another
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997)]>)
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> (another.a, another.c)
    (['Ale-Ale'], 997)
    >>> dd |= another
    >>> dd
    MyStrangeDict(<[('an', 1.0), ('b', {'Be-Be-Be': 12345}), ('c', 997), ('dd', True)]>)
    >>> dd == {'an': 1.0, 'b': {'Be-Be-Be': 12345}, 'c': 997, 'dd': True}
    True
    >>> dd['b'] is another['b']
    True
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> another_plain_dict = {'b': {'IBU': 90}, 'q': 4}
    >>> dd |= another_plain_dict
    >>> dd
    MyStrangeDict(<[('an', 1.0), ('b', {'IBU': 90}), ('c', 997), ('dd', True), ('q', 4)]>)
    >>> dd == {'an': 1.0, 'b': {'IBU': 90}, 'c': 997, 'dd': True, 'q': 4}
    True
    >>> dd['b'] is another_plain_dict['b']
    True
    >>> another_nondict_mapping = NonDictMapping({'b': {}, 'dd': 1, 'y': 2})
    >>> dd |= another_nondict_mapping
    >>> dd
    MyStrangeDict(<[('an', 1.0), ('b', {}), ('c', 997), ('dd', 1), ('q', 4), ('y', 2)]>)
    >>> dd == {'an': 1.0, 'b': {}, 'c': 997, 'dd': True, 'q': 4, 'y': 2}
    True
    >>> dd['b'] is another_nondict_mapping['b']
    True
    >>> nonmapping_iterable
    [('b', []), ('x', 3)]
    >>> dd |= nonmapping_iterable  # possible with `|=`, not with `|` (like in the case of `dict`)
    >>> dd
    MyStrangeDict(<[('an', 1.0), ('b', []), ('c', 997), ('dd', 1), ('q', 4), ('x', 3), ('y', 2)]>)
    >>> dd == {'an': 1.0, 'b': [], 'c': 997, 'dd': True, 'q': 4, 'x': 3, 'y': 2}
    True
    >>> dd['b'] is nonmapping_iterable[0][1]
    True
    >>> (dd.a, dd.c)
    (['A'], 42)
    >>> (dd._repr_recur_thread_ids == set({'SPAM!'}) and
    ...  another._repr_recur_thread_ids == set({'fiu fiu'}))
    True

    >>> sorted([d.popitem(), d.popitem()])
    [('a', ['A']), ('b', {'B': 'BB'})]
    >>> d
    MyStrangeDict(<[]>)
    >>> d == {}
    True
    >>> bool(d)
    False

    >>> d.popitem()
    Traceback (most recent call last):
      ...
    KeyError: 'popitem(): dictionary is empty'

    >>> MyStrangeDict._custom_key_error_also_for_popitem = True
    >>> d.popitem()
    Traceback (most recent call last):
      ...
    ValueError: ('popitem(): dictionary is empty', 'popitem')

    >>> class MyBoringDict(DictWithSomeHooks):
    ...     pass
    ...
    >>> MyBoringDict({'a': 1, False: ['b']}, x=b'xyz')
    MyBoringDict({'a': 1, False: ['b'], 'x': b'xyz'})
    >>> d2 = MyBoringDict.fromkeys(['a', 'b', 42])
    >>> d2
    MyBoringDict({'a': None, 'b': None, 42: None})
    >>> d3 = MyBoringDict.fromkeys(['a', 'b', 42], {'la'})
    >>> d3
    MyBoringDict({'a': {'la'}, 'b': {'la'}, 42: {'la'}})
    >>> d3['a'] is d3['b'] is d3[42]
    True

    >>> class WorseBoringDict(DictWithSomeHooks):
    ...
    ...     def __init__(self, /, *args, **kwargs):
    ...         super().__init__(*args, **kwargs)
    ...         self.my_attr_set_in_init = 'foo-bar'
    ...
    >>> WorseBoringDict({'a': 1, False: ['b']}, x=b'xyz')
    WorseBoringDict({'a': 1, False: ['b'], 'x': b'xyz'})
    >>> WorseBoringDict.fromkeys(['a', 'b', 42])  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    NotImplementedError: ...

    >>> class BetterBoringDict(DictWithSomeHooks):
    ...
    ...     # Let's re-enable the default implementation of `fromkeys()`
    ...     # (by setting this flag to `True` we explicitly promise
    ...     # that our extended `__init__()` is able to take a plain
    ...     # `dict` of items as the sole argument).
    ...     _standard_fromkeys_enabled = True
    ...
    ...     def __init__(self, /, *args, **kwargs):
    ...         super().__init__(*args, **kwargs)
    ...         self.my_attr_set_in_init = 'foo-bar'
    ...
    >>> d4 = BetterBoringDict.fromkeys(['a', 'b', 42])
    >>> d4
    BetterBoringDict({'a': None, 'b': None, 42: None})
    >>> d4.my_attr_set_in_init
    'foo-bar'

    >>> class TotallyWeirdDict(DictWithSomeHooks):
    ...
    ...     def __eq__(self, other):
    ...         return 'equal' in other
    ...
    >>> d5 = TotallyWeirdDict()
    >>> d5 == {}
    False
    >>> d5 != {}
    True
    >>> d5 == ['equal']
    True
    >>> d5 != ['equal']
    False
    """

    def __init__(self, /, *args, **kwargs):
        self.__init_internals()
        super().__init__(*args, **kwargs)

    @classmethod
    def fromkeys(cls, iterable, value=None, /):
        if (cls.__init__ is not DictWithSomeHooks.__init__) and not cls._standard_fromkeys_enabled:
            raise NotImplementedError(
                'the class method `fromkeys()` is not enabled (to enable '
                'it in a subclass that extends `__init__()`, you need '
                'to: *either* set the `_standard_fromkeys_enabled` class '
                'attribute to `True` and ensure that `__init__()` really '
                'accepts a plain dict of items as the sole argument; *or* '
                'provide your own implementation of `fromkeys()`)')
        items = zip(iterable, itertools.repeat(value))
        # (below we apply `dict()` to `items`, as we prefer to minimize
        # the requirements imposed on the `__init__()` method's interface
        # if extended in a subclass)
        return cls(dict(items))

    def __repr__(self):
        repr_recur_thread_ids = self._repr_recur_thread_ids
        cur_thread_id = get_current_thread_ident()
        with self._repr_recur_thread_ids_rlock:
            if cur_thread_id in self._repr_recur_thread_ids:
                # recursion detected
                constructor_args_repr = '<...>'
            else:
                try:
                    repr_recur_thread_ids.add(cur_thread_id)
                    constructor_args_repr = self._constructor_args_repr()
                finally:
                    repr_recur_thread_ids.discard(cur_thread_id)
        return f'{self.__class__.__qualname__}({constructor_args_repr})'

    __ne__ = properly_negate_eq

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError as key_error:
            raise self.__get_only_custom_key_error(key_error, '__getitem__') from key_error

    def __delitem__(self, key):
        try:
            super().__delitem__(key)
        except KeyError as key_error:
            raise self.__get_only_custom_key_error(key_error, '__delitem__') from key_error

    def pop(self, *args):
        try:
            return super().pop(*args)
        except KeyError as key_error:
            raise self.__get_only_custom_key_error(key_error, 'pop') from key_error

    def popitem(self):
        try:
            return super().popitem()
        except KeyError as key_error:
            if self._custom_key_error_also_for_popitem:
                raise self.__get_only_custom_key_error(key_error, 'popitem') from key_error
            raise

    def __get_only_custom_key_error(self, key_error, method_name):
        custom_key_error = self._custom_key_error(key_error, method_name)
        if custom_key_error is key_error:
            raise
        return custom_key_error

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return self.__new_with_given_items_and_our_attrs(self.items())

    def __deepcopy__(self, memo):
        cls = type(self)
        new = cls.__new__(cls)
        new.__init_internals()
        memo[id(self)] = new  # <- needed in case of a recursive mapping
        # (below we apply `dict()` to `items`, as we prefer to minimize
        # the requirements imposed on the `update()` method's interface
        # if customized in a subclass)
        copied_items = copy.deepcopy(dict(self.items()), memo)
        copied_attrs = copy.deepcopy(list(self.__iter_copyable_attrs()), memo)
        new.update(copied_items)
        vars(new).update(copied_attrs)
        return new

    def __or__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        # (the following `dict()` and both `.items()` calls may seem
        # redundant, but they are here for a reason -- to impose modest
        # yet well-defined requirements on the engaged types' interfaces)
        other_as_plain_dict = dict(other.items())
        merged_items = super().__or__(other_as_plain_dict).items()
        return self.__new_with_given_items_and_our_attrs(merged_items)

    def __ror__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        # (the following `dict()` and both `.items()` calls may seem
        # redundant, but they are here for a reason -- to impose modest
        # yet well-defined requirements on the engaged types' interfaces)
        other_as_plain_dict = dict(other.items())
        merged_items = super().__ror__(other_as_plain_dict).items()
        return self.__new_with_given_items_and_our_attrs(merged_items)

    def __new_with_given_items_and_our_attrs(self, items):
        cls = type(self)
        new = cls.__new__(cls)
        new.__init_internals()
        # (below we apply `dict()` to `items`, as we prefer to minimize
        # the requirements imposed on the `update()` method's interface
        # if customized in a subclass)
        new.update(dict(items))
        vars(new).update(self.__iter_copyable_attrs())
        return new

    def __init_internals(self):
        self._repr_recur_thread_ids = set()
        self._repr_recur_thread_ids_rlock = threading.RLock()

    def __iter_copyable_attrs(self):
        return (
            (k, v) for k, v in vars(self).items()
            if k not in (
                '_repr_recur_thread_ids',
                '_repr_recur_thread_ids_rlock',
            ))

    # overridable hooks and attributes:

    def _constructor_args_repr(self):
        return repr(dict(self.items()))

    def _custom_key_error(self, key_error, method_name):
        return key_error

    _custom_key_error_also_for_popitem = False
    _standard_fromkeys_enabled = False  # <- relevant in a subclass if `__init__()` is extended


## TODO: doc + maybe more tests (now only the CIDict subclass is doc-tested...)
class NormalizedDict(MutableMapping):

    def __init__(self, /, *args, **kwargs):
        self._mapping = {}
        self.update(*args, **kwargs)

    @abc.abstractmethod
    def normalize_key(self, key):
        return key

    def __getitem__(self, key):
        nkey = self.normalize_key(key)
        return self._mapping[nkey][1]

    def __setitem__(self, key, value):
        nkey = self.normalize_key(key)
        self._mapping[nkey] = (key, value)

    def __delitem__(self, key):
        nkey = self.normalize_key(key)
        del self._mapping[nkey]

    def __repr__(self):
        return '{0.__class__.__qualname__}({1!r})'.format(self, dict(self.items()))

    def __len__(self):
        return len(self._mapping)

    def __eq__(self, other):
        if isinstance(other, NormalizedDict):
            return (dict(self.iter_normalized_items()) ==
                    dict(other.iter_normalized_items()))
        return super().__eq__(other)

    __ne__ = properly_negate_eq

    def __iter__(self):
        return map(operator.itemgetter(0), self._mapping.values())

    def __reversed__(self):
        return map(operator.itemgetter(0), reversed(self._mapping.values()))

    def iter_normalized_items(self):
        for nkey, (key, value) in self._mapping.items():
            yield nkey, value

    def copy(self):
        return type(self)(self)

    def clear(self):
        self._mapping.clear()

    @classmethod
    def fromkeys(cls, seq, value=None):
        return cls(zip(seq, itertools.repeat(value)))


class CIDict(NormalizedDict):

    """
    A dict that provides case-insensitive key lookup but keeps original keys.

    (Intended to be used with string keys only).

    >>> d = CIDict({'Aa': 1}, B=2)

    >>> d['aa'], d['AA'], d['Aa'], d['aA']
    (1, 1, 1, 1)
    >>> d['b'], d['B']
    (2, 2)
    >>> del d['b']

    >>> d
    CIDict({'Aa': 1})
    >>> d['cC'] = 3
    >>> d['CC'], d['cc']
    (3, 3)

    >>> sorted(d.keys())
    ['Aa', 'cC']
    >>> sorted(d.values())
    [1, 3]
    >>> sorted(d.items())
    [('Aa', 1), ('cC', 3)]

    >>> d['aA'] = 42
    >>> sorted(d.items())
    [('aA', 42), ('cC', 3)]

    >>> d2 = d.copy()
    >>> d == d2
    True
    >>> d is d2
    False
    >>> len(d), len(d2)
    (2, 2)

    >>> d3 = CIDict.fromkeys(['Cc'], 3)
    >>> d != d3
    True

    >>> d.pop('aa')
    42
    >>> d == d2
    False

    >>> bool(d2)
    True
    >>> d2.clear()
    >>> d2
    CIDict({})
    >>> bool(d2)
    False

    >>> d
    CIDict({'cC': 3})
    >>> d3
    CIDict({'Cc': 3})
    >>> d == d3
    True
    >>> d == {'Cc': 3}
    False
    >>> d == {'cC': 3}
    True

    >>> d.setdefault('CC', 42), d3.setdefault('cc', 43)
    (3, 3)
    >>> d
    CIDict({'cC': 3})
    >>> d3
    CIDict({'Cc': 3})

    >>> d.popitem()
    ('cC', 3)
    >>> d3.popitem()
    ('Cc', 3)
    >>> d == d3 == {}
    True

    >>> d.update([('zz', 1), ('ZZ', 1), ('XX', 5)], xx=6)
    >>> sorted(d.items())
    [('ZZ', 1), ('xx', 6)]
    >>> sorted(d.iter_normalized_items())
    [('xx', 6), ('zz', 1)]
    >>> del d['Xx']
    >>> list(d.iter_normalized_items())
    [('zz', 1)]
    """

    def normalize_key(self, key):
        key = super().normalize_key(key)
        return key.lower()


class LimitedDict(collections.OrderedDict):

    """
    Ordered dict whose length never exceeds the specified limit.

    To prevent exceeding the limit the oldest items are dropped.

    >>> from collections import OrderedDict
    >>> lo = LimitedDict([('b', 2), ('a', 1)], maxlen=3)
    >>> lo['c'] = 3
    >>> lo == OrderedDict([('b', 2), ('a', 1), ('c', 3)])
    True
    >>> lo['d'] = 4
    >>> lo == OrderedDict([('a', 1), ('c', 3), ('d', 4)])
    True
    >>> lo.update([((1,2,3), 42), (None, True)])
    >>> lo == OrderedDict([('d', 4), ((1,2,3), 42), (None, True)])
    True
    >>> lo.setdefault('a', 1)
    1
    >>> lo == OrderedDict([((1,2,3), 42), (None, True), ('a', 1)])
    True
    >>> lo |= [('c', 3), ('d', 4)]
    >>> lo == OrderedDict([('a', 1), ('c', 3), ('d', 4)])
    True

    >>> lo = LimitedDict([('b', 2), ('a', 1), ('c', 3), ('d', 4)], maxlen=3)
    >>> lo == OrderedDict([('a', 1), ('c', 3), ('d', 4)])
    True
    >>> lo = LimitedDict([('b', 2), ('a', 1), ('c', 3)], d=4, maxlen=3)
    >>> lo == OrderedDict([('a', 1), ('c', 3), ('d', 4)])
    True

    >>> lo = LimitedDict([('b', 2), ('a', 1), ('c', 3)], maxlen=3)
    >>> lo == OrderedDict([('b', 2), ('a', 1), ('c', 3)])
    True

    >>> lo = LimitedDict(b=2, maxlen=3)
    >>> lo == OrderedDict(b=2)
    True
    >>> lo = LimitedDict([('b', 2)], maxlen=3)
    >>> lo == OrderedDict([('b', 2)])
    True

    >>> LimitedDict([('b', 2)])  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """

    def __init__(self, /, *args, maxlen, **kwargs):
        self._maxlen = maxlen
        super().__init__(*args, **kwargs)

    def __repr__(self):
        """
        >>> LimitedDict(maxlen=3)
        LimitedDict(maxlen=3)

        >>> LimitedDict({1: 2}, maxlen=3)
        LimitedDict([(1, 2)], maxlen=3)

        >>> class StrangeBase(collections.OrderedDict):
        ...     def __repr__(self): return 'SOMETHING NON-STANDARD'
        ...
        >>> class StrangeSubclass(LimitedDict, StrangeBase):
        ...     pass
        ...
        >>> StrangeSubclass({1: 2}, maxlen=3)  # doctest: +ELLIPSIS
        <...StrangeSubclass object at 0x...>
        """
        s = super().__repr__()
        if s.endswith(')'):
            ending = 'maxlen={})'
            if not s.endswith('()'):
                ending = ', ' + ending
            return s[:-1] + ending.format(self._maxlen)
        else:
            # only if super()'s __repr__ returned something weird
            # (theoretically possible in subclasses)
            return object.__repr__(self)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if len(self) > self._maxlen:
            self.popitem(last=False)

    def copy(self):
        """
        >>> lo = LimitedDict([(1, 2)], maxlen=3)
        >>> lo
        LimitedDict([(1, 2)], maxlen=3)
        >>> lo.copy()
        LimitedDict([(1, 2)], maxlen=3)
        >>> lo == lo.copy()
        True
        >>> lo is lo.copy()
        False
        """
        return self.__class__(self, maxlen=self._maxlen)

    @classmethod
    def fromkeys(cls, iterable, value=None, *, maxlen):
        """
        >>> LimitedDict.fromkeys([1,2,3,4], maxlen=3)
        LimitedDict([(2, None), (3, None), (4, None)], maxlen=3)

        >>> LimitedDict.fromkeys([4,3,2,1], value='x', maxlen=3)
        LimitedDict([(3, 'x'), (2, 'x'), (1, 'x')], maxlen=3)

        >>> LimitedDict.fromkeys([   # (maxlen not given)
        ...               1,2,3,4])  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        TypeError: ...
        """
        items = zip(iterable, itertools.repeat(value))
        return cls(items, maxlen=maxlen)


class _CacheKey:

    def __init__(self, *args):
        self.args = args
        self.args_hash = hash(args)

    def __repr__(self):
        return '{0.__class__.__qualname__}{0.args!r}'.format(self)

    def __hash__(self):
        return self.args_hash

    def __eq__(self, other):
        return self.args == other.args


def memoized(func=None,
             expires_after=None,
             max_size=None,
             max_extra_time=30,
             time_func=time.monotonic):
    """
    A decorator that provides function call memoization based on a FIFO cache.

    Note: this tool provides a FIFO (*first in, first out*) cache.
    If you need a LRU (*least recently used*-discarding) cache, use
    `@functools.lru_cache` instead.

    Args:
        `func`:
            The decorated function. (Typically, it is ommited to
            be bound later with the decorator syntax -- see the
            examples below.)

    Kwargs:
        `expires_after` (default: `None`):
            Time interval (in seconds) between caching a call
            result and its expiration. If set to `None` -- there
            is no time-based cache expiration.
        `max_size` (default: `None`):
            Maximum number of memoized results (formally, this is
            not a strict maximum: some extra cached results can be
            kept a bit longer -- until their keys' weak references
            are garbage-collected -- though it is hardly probable
            under CPython, and even then it would be practically
            harmless). If set to None -- there is no such limit.
        `max_extra_time` (default: 30):
            Maximum for a random number of seconds to be added to
            `expires_after` for a particular cached result. `None`
            means the same as 0: no extra time. Non-zero values
            help in "desynchronization" of `@memoized`-based caches,
            i.e., in avoiding unwanted regularity in coincidences of
            cache expirations (in particular, when `expires_after`
            of one cache is, by accident, equal to `expires_after`
            of another cache, or to a multiplicity of it).
        `time_func` (default: `time.monotonic()`):
            A function used to determine the *current time*: it should
            return an `int` or `float` number (one second is assumed to
            be the unit, fractional part is welcome).

    Recursion is not supported (the decorated function raises
    `RuntimeError` when a recursive call occurs).

    Function arguments of different types are *not* cached separately
    (as long as their hashes and values compare *equal*).

    ***

    >>> @memoized(expires_after=None, max_size=2)
    ... def add(a, b):
    ...     print('calculating: {} + {} = ...'.format(a, b))
    ...     return a + b
    ...
    >>> add(1, 2)  # first time: calling the add() function
    calculating: 1 + 2 = ...
    3
    >>> add(1, 2)  # now, getting cached results...
    3
    >>> add(1+0j, 2.0)   # (argument types are irrelevant as long as values are equal)
    3
    >>> add(1, 3)
    calculating: 1 + 3 = ...
    4
    >>> add(1, 2)
    3
    >>> add(1, 3)
    4
    >>> add(3, 1)  # exceeding max_size: forgeting for (1, 2)
    calculating: 3 + 1 = ...
    4
    >>> add(1, 3)
    4
    >>> add(3, 1)
    4
    >>> add(1, 2)  # already forgotten (max_size had been exceeded)
    calculating: 1 + 2 = ...
    3
    >>> add(3, 1)
    4
    >>> add(1, 3)  # already forgotten (max_size had been exceeded)
    calculating: 1 + 3 = ...
    4
    >>> add(3, 1)  # already forgotten (max_size had been exceeded)
    calculating: 3 + 1 = ...
    4
    >>> add(1, 2)  # already forgotten (max_size had been exceeded)
    calculating: 1 + 2 = ...
    3

    >>> t = 0
    >>> fake_time = lambda: t
    >>> @memoized(expires_after=4, max_extra_time=None, time_func=fake_time)
    ... def sub(a, b):
    ...     print('calculating: {} - {} = ...'.format(a, b))
    ...     return a - b
    ...
    >>> sub(1, 2)
    calculating: 1 - 2 = ...
    -1

    >>> t = 1
    >>> sub(1, 2.0)
    -1

    >>> t = 2
    >>> sub(2, 1)
    calculating: 2 - 1 = ...
    1

    >>> t = 3
    >>> sub(4, 2)
    calculating: 4 - 2 = ...
    2

    >>> t = 4      # (t reaches `expires_after` for the (1, 2) call result)
    >>> sub(1, 2)  # forgotten
    calculating: 1 - 2 = ...
    -1

    >>> t = 5      # is still memoized
    >>> sub(2, 1)
    1

    >>> t = 6      # is still memoized (+ expiry of the (2, 1) call result)
    >>> sub(4, 2)
    2

    >>> t = 7      # has already been forgotten
    >>> sub(2, 1)
    calculating: 2 - 1 = ...
    1
    >>> sub(1, 2)  # is still memoized...
    -1

    >>> t = 8
    >>> sub(1, 2)  # and forgotten
    calculating: 1 - 2 = ...
    -1

    >>> @memoized(max_size=2, expires_after=4, max_extra_time=1, time_func=fake_time)
    ... def mul(a, b):
    ...     print('calculating: {} * {} = ...'.format(a, b))
    ...     return a * b
    ...
    >>> t = 10
    >>> mul(2, 2)  # first time: calling the mul() function
    calculating: 2 * 2 = ...
    4
    >>> mul(2, 2)  # now, getting cached results...
    4
    >>> mul(2, 2.0)
    4
    >>> t = 20
    >>> mul(2, 2)  # already expired
    calculating: 2 * 2 = ...
    4
    >>> mul(2, 2)  # now, getting cached results again...
    4
    >>> mul(2, 2.0)
    4
    >>> mul(2, 3)
    calculating: 2 * 3 = ...
    6
    >>> mul(2, 2)
    4
    >>> mul(2, 3)
    6
    >>> mul(3, 2)  # exceeding max_size: forgeting for (2, 2)
    calculating: 3 * 2 = ...
    6
    >>> mul(2, 3)
    6
    >>> mul(3, 2)
    6
    >>> mul(2, 2)  # already forgotten (max_size had been exceeded)
    calculating: 2 * 2 = ...
    4
    >>> mul(3, 2)
    6
    >>> mul(2, 3)  # already forgotten (max_size had been exceeded)
    calculating: 2 * 3 = ...
    6
    >>> mul(3, 2)  # already forgotten (max_size had been exceeded)
    calculating: 3 * 2 = ...
    6
    >>> mul(2, 2)  # already forgotten (max_size had been exceeded)
    calculating: 2 * 2 = ...
    4
    >>> t = 30
    >>> mul(2, 2)  # already expired
    calculating: 2 * 2 = ...
    4
    >>> mul(3, 2)  # already expired
    calculating: 3 * 2 = ...
    6

    >>> @memoized(expires_after=None, max_size=2)
    ... def div(a, b):
    ...     print('calculating: {} / {} = ...'.format(a, b))
    ...     return a / b
    ...
    >>> div(6, 2)
    calculating: 6 / 2 = ...
    3.0
    >>> div(8, 2)
    calculating: 8 / 2 = ...
    4.0
    >>> div(15, 3)
    calculating: 15 / 3 = ...
    5.0
    >>> try: div(7, 0)
    ... except ZeroDivisionError: print('Uff')
    calculating: 7 / 0 = ...
    Uff
    >>> try: div(7, 0)
    ... except ZeroDivisionError: print('Uff')
    calculating: 7 / 0 = ...
    Uff
    >>> try: div(7, 0)
    ... except ZeroDivisionError: print('Uff')
    calculating: 7 / 0 = ...
    Uff
    >>> div(15, 3)
    5.0
    >>> div(8.0, 2+0j)
    4.0
    >>> div(6, 2)
    calculating: 6 / 2 = ...
    3.0

    >>> @memoized
    ... def recur(n):
    ...     return (recur(n+1) if n <= 1 else n)
    ...
    >>> recur(1)   # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    RuntimeError: recursive calls cannot be memoized (...)
    """
    if func is None:
        return functools.partial(memoized,
                                 expires_after=expires_after,
                                 max_size=max_size,
                                 max_extra_time=max_extra_time,
                                 time_func=time_func)

    NOT_FOUND = object()
    CacheKey = _CacheKey
    CacheRegItem = collections.namedtuple('CacheRegItem', 'key, expiry_time')
    cache_register = collections.deque(maxlen=max_size)
    keys_to_results = weakref.WeakKeyDictionary()
    mutex = threading.RLock()
    recursion_guard = []

    @functools.wraps(func)
    def wrapper(*args):
        with mutex:
            if recursion_guard:
                raise RuntimeError(
                    'recursive calls cannot be memoized ({0!a} appeared '
                    'to be called recursively)'.format(wrapper))
            try:
                recursion_guard.append(None)
                try:
                    if expires_after is not None:
                        # delete expired items
                        current_time = time_func()
                        while cache_register and cache_register[0].expiry_time <= current_time:
                            key = cache_register.popleft().key
                            del keys_to_results[key]
                    key = CacheKey(*args)
                    result = keys_to_results.get(key, NOT_FOUND)
                    if result is NOT_FOUND:
                        result = keys_to_results[key] = func(*args)
                        expiry_time = (
                            (time_func() + expires_after +
                             random.randint(0, max_extra_time or 0))
                            if expires_after is not None else None)
                        cache_register.append(CacheRegItem(key, expiry_time))
                    return result
                finally:
                    recursion_guard.pop()
            except:
                # additional safety measures in the event of an
                # intrusive exception (e.g., an exception from a
                # signal handler, such as `KeyboardInterrupt` caused
                # by Ctrl+C) that breaks the guarantee that the above
                # `recursion_guard.pop()` call is always made
                del recursion_guard[:]
                raise

    wrapper.func = func  # making the original function still available
    return wrapper



class DictDeltaKey(collections.namedtuple('DictDeltaKey', ('op', 'key_obj'))):

    """
    The class of special marker keys in dicts returned by `make_dict_delta()`.

    >>> DictDeltaKey('+', 42)
    DictDeltaKey(op='+', key_obj=42)
    >>> DictDeltaKey(op='-', key_obj='foo')
    DictDeltaKey(op='-', key_obj='foo')
    >>> DictDeltaKey('*', 42)
    Traceback (most recent call last):
      ...
    ValueError: `op` must be one of: '+', '-'

    >>> DictDeltaKey('+', 42) == DictDeltaKey('+', 42)
    True
    >>> DictDeltaKey('+', 42) == DictDeltaKey('-', 42)
    False
    >>> DictDeltaKey('+', 42) == ('+', 42)
    False
    >>> ('-', 'foo') != DictDeltaKey('-', 'foo')
    True
    """

    def __new__(cls, op, key_obj):
        if op not in ('+', '-'):
            raise ValueError("`op` must be one of: '+', '-'")
        return super().__new__(cls, op, key_obj)

    def __eq__(self, other):
        if isinstance(other, DictDeltaKey):
            return super().__eq__(other)
        # We don't want to be equal to anything else,
        # in particular, not to any other tuples...
        return False

    __ne__ = properly_negate_eq

    def __hash__(self):
        # Needed because Python 3.x implicitly sets `__hash__` to `None`
        # if `__eq__()` is redefined and `__hash__()` is not.
        return super().__hash__()


def make_dict_delta(dict1, dict2):
    """
    Compare two dicts and produce a "delta dict".

    Here, "delta dict" is just a dict that contains only differing
    items, with their keys wrapped with DictDeltaKey() instances
    (appropriately: `DictDeltaKey('-', <key>)` or `DictDeltaKey('+', <key>)`).

    A few simple examples:

    >>> make_dict_delta({}, {}) == {}
    True
    >>> make_dict_delta({42: 'foo'}, {}) == {DictDeltaKey('-', 42): 'foo'}
    True
    >>> make_dict_delta({}, {'bar': 42}) == {DictDeltaKey('+', 'bar'): 42}
    True
    >>> make_dict_delta({'spam': 42}, {'spam': 42}) == {}
    True
    >>> make_dict_delta({'spam': 42}, {'spam': 42.0}) == {}
    True
    >>> make_dict_delta({42: 'spam'}, {42.0: 'spam'}) == {}
    True
    >>> make_dict_delta({'spam': 42}, {'spam': 'HAM'}) == {
    ...     DictDeltaKey('-', 'spam'): 42,
    ...     DictDeltaKey('+', 'spam'): 'HAM'}
    True
    >>> make_dict_delta({'spam': 42}, {'HAM': 'spam'}) == {
    ...     DictDeltaKey('-', 'spam'): 42,
    ...     DictDeltaKey('+', 'HAM'): 'spam'}
    True
    >>> delta = make_dict_delta(
    ...     {'a': 1, 'b': 2.0, 'c': 3, 'd': 4.0},
    ...     {'b': 2, 'c': 3.0, 'd': 42, 'e': 555})
    >>> delta == {
    ...     DictDeltaKey('-', 'a'): 1,
    ...     DictDeltaKey('-', 'd'): 4.0,
    ...     DictDeltaKey('+', 'd'): 42,
    ...     DictDeltaKey('+', 'e'): 555}
    True
    >>> delta.pop(DictDeltaKey('+', 'e'))
    555
    >>> delta.pop(DictDeltaKey('+', 'd'))
    42
    >>> delta.pop(DictDeltaKey('-', 'd'))
    4.0
    >>> delta.popitem()
    (DictDeltaKey(op='-', key_obj='a'), 1)

    Important feature: nested deltas are supported as well.
    For example:

    >>> delta = make_dict_delta({
    ...         'q': 'foo',
    ...         'w': 42,
    ...         'e': ['spam', {42: 'spam'}, 'spam'],
    ...         'r': {
    ...             3: 3.0,
    ...             2: {
    ...                 'a': {
    ...                     'aa': 42,
    ...                     'YYY': 'blablabla',
    ...                 },
    ...                 'b': 'bb',
    ...                 'c': {'cc': {'ccc': 43}},
    ...                 'd': {'dd': {'ddd': 44}},
    ...                 'z': {'zz': {'zzz': 123.0}},
    ...             },
    ...             1.0: 7.0,
    ...         },
    ...         't': {'a': 42},
    ...         'y': {},
    ...         'i': 42,
    ...         'o': {'b': 43, 'c': {'d': {'e': 456}}},
    ...         'p': {'b': 43, 'c': {'d': {'e': 456}}},
    ...     }, {
    ...         'q': 'foo',
    ...         'w': 42.0,
    ...         'e': ['spam', {42: 'HAM'}, 'spam'],
    ...         'r': {
    ...             3: 3.0,
    ...             2: {
    ...                 'a': {'aa': 43},
    ...                 'b': 'bb',
    ...                 'c': {'cc': {'CCC': 43}},
    ...                 'e': {'ee': {'eee': 45}},
    ...                 'z': {
    ...                     'zz': {'zzz': 123},
    ...                     'xx': ['bar'],
    ...                 },
    ...             },
    ...             1: 777,
    ...         },
    ...         't': 42,
    ...         'y': {},
    ...         'i': {'a': 42},
    ...         'o': {'b': 43, 'c': {'d': {'e': 456}}},
    ...         'p': {'b': 43, 'c': {'d': {'e': 456789}}},
    ...     })
    >>> delta == {
    ...     DictDeltaKey('-', 'e'): ['spam', {42: 'spam'}, 'spam'],
    ...     DictDeltaKey('+', 'e'): ['spam', {42: 'HAM'}, 'spam'],
    ...     'r': {
    ...         2: {
    ...             'a': {
    ...                 DictDeltaKey('-', 'aa'): 42,
    ...                 DictDeltaKey('+', 'aa'): 43,
    ...                 DictDeltaKey('-', 'YYY'): 'blablabla',
    ...             },
    ...             'c': {
    ...                 'cc': {
    ...                     DictDeltaKey('-', 'ccc'): 43,
    ...                     DictDeltaKey('+', 'CCC'): 43,
    ...                 },
    ...             },
    ...             DictDeltaKey('-', 'd'): {'dd': {'ddd': 44}},
    ...             DictDeltaKey('+', 'e'): {'ee': {'eee': 45}},
    ...             'z': {
    ...                 DictDeltaKey('+', 'xx'): ['bar'],
    ...             },
    ...         },
    ...         DictDeltaKey('-', 1): 7.0,
    ...         DictDeltaKey('+', 1): 777,
    ...     },
    ...     DictDeltaKey('-', 't'): {'a': 42},
    ...     DictDeltaKey('+', 't'): 42,
    ...     DictDeltaKey('-', 'i'): 42,
    ...     DictDeltaKey('+', 'i'): {'a': 42},
    ...     'p': {
    ...         'c': {
    ...             'd': {
    ...                 DictDeltaKey('-', 'e'): 456,
    ...                 DictDeltaKey('+', 'e'): 456789,
    ...             },
    ...         },
    ...     },
    ... }
    True
    >>> list(delta['r'])   # (a corner case detail: within both
    ...                    # DictDeltaKey instances `key_obj` is 1, not 1.0)
    [2, DictDeltaKey(op='-', key_obj=1), DictDeltaKey(op='+', key_obj=1)]

    Making deltas from dicts that already contain keys being
    DictDeltaKey instances is (consciously) unsupported:

    >>> make_dict_delta(                 # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     {1: 42},
    ...     {DictDeltaKey('+', 1): 43})
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> make_dict_delta(                 # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     {'a': {'b': {'c': {DictDeltaKey('-', 'd'): 42}}}},
    ...     {'a': {'b': {'c': {'d': 43}}}})
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    keys1 = set(dict1)
    keys2 = set(dict2)
    common_keys = keys1 & keys2
    del_keys = keys1 - common_keys
    add_keys = keys2 - common_keys
    if any(isinstance(key, DictDeltaKey)
           for key in itertools.chain(common_keys, del_keys, add_keys)):
        raise TypeError(
            'make_dict_delta() does not accept dicts that '      # TODO: Let's analyze whether this
            'already contain keys being DictDeltaKey instances'  #       limitation can be lifted.
            '(keys of given dicts: {0!a} and {1!a})'.format(
                sorted(dict1), sorted(dict2)))
    delta = {}
    for key in common_keys:
        val1 = dict1[key]
        val2 = dict2[key]
        if isinstance(val1, dict) and isinstance(val2, dict):
            subdelta = make_dict_delta(val1, val2)  # recursion
            if subdelta:
                delta[key] = subdelta
            else:
                assert val1 == val2
        elif val1 != val2:
            del_keys.add(key)
            add_keys.add(key)
    for key in del_keys:
        delta[DictDeltaKey('-', key)] = dict1[key]
    for key in add_keys:
        delta[DictDeltaKey('+', key)] = dict2[key]
    return delta


def update_mapping_recursively(*args, **kwargs):
    """
    Update the given mapping recursively with items from other mappings.

    Args:
        `target_mapping` (a collections.abc.MutableMapping, e.g. a dict):
            The target mapping, that is, the mapping to be mutated.
        <other positional arguments>:
            The source mappings (e.g., dicts); their items will be
            used to recursively update `target_mapping`. The mappings
            will be used in the given order. Instead of a mapping
            (collections.abc.Mapping instance) any iterable object
            can be given, provided it yields `(<key>, <value>)` pairs.

    Kwargs:
        <all keyword arguments (if any)>:
            Items that form yet another source mapping that will be used
            (as the last one) in the same way the mappings specified as
            <other positional arguments> will be.

    Here, *recursive update* means that for each key in each of the
    source mappings:

    * if the corresponding value in the target mapping *is* a dict or
      another instance of collections.abc.MutableMapping -- it will be
      *recursively updated* with the contents of the value from the
      source mapping (which then must be either an instance of
      collections.abc.Mapping or any iterable that yields
      `(<key>, <value>)` pairs);

    * if the corresponding value in the target mapping is *not* such
      a mutable mapping or does *not* exist at all -- the result of
      applying copy.deepcopy() will be applied to the value from the
      source mapping, and that copy will be stored in the target
      mapping (replacing the aforementioned value, if any).

    For example:

    >>> target = {
    ...     'abc': 42,
    ...     'foo': 'BAR',
    ...     'xyz': {1: 2, 3: {4: 5, 'spam': 'ham'}, 6: 7},
    ...     123: [set(['FOO', 'BAR']), 'S', 'P', 'AM'],
    ... }
    >>> src1 = {
    ...     'abc': {'x': 'y', 'ZZZ': {'A': 789, 'B': 'C'}},
    ...     'SPAMMY': 'hammy',
    ...     True: {'no': False},
    ... }
    >>> src2 = {
    ...     'abc': {'qqq': 'rrr', 'ZZZ': [('A', 456)]},
    ...     'xyz': {3: {4: 55, 8: 99}, 6: 77, 'z': 0},
    ...     'SPAMMY': 'non-hammy',
    ...     123: [333, 22, 1],
    ... }
    >>> kwarg_xyz = [(44.0, 't'), ('z', None)]
    >>> update_mapping_recursively(target, src1, src2,
    ...                            xyz=kwarg_xyz,
    ...                            YetAnother=43)
    >>> target == {
    ...     'abc': {'x': 'y', 'qqq': 'rrr', 'ZZZ': {'A': 456, 'B': 'C'}},
    ...     'foo': 'BAR',
    ...     'xyz': {1: 2, 3: {4: 55, 8: 99, 'spam': 'ham'},
    ...             6: 77, 44.0: 't', 'z': None},
    ...     'SPAMMY': 'non-hammy',
    ...     'YetAnother': 43,
    ...     123: [333, 22, 1],
    ...     True: {'no': False},
    ... }
    True
    >>> # NOTE that the source data containers have *not* been changed:
    ... src1 == {
    ...     'abc': {'x': 'y', 'ZZZ': {'A': 789, 'B': 'C'}},
    ...     'SPAMMY': 'hammy',
    ...     True: {'no': False},
    ... } and src2 == {
    ...     'abc': {'qqq': 'rrr', 'ZZZ': [('A', 456)]},
    ...     'xyz': {3: {4: 55, 8: 99}, 6: 77, 'z': 0},
    ...     'SPAMMY': 'non-hammy',
    ...     123: [333, 22, 1],
    ... } and kwarg_xyz == [(44.0, 't'), ('z', None)]
    True
    """
    target_mapping = args[0]
    source_mappings = args[1:] + (kwargs,)
    for src_mapping in source_mappings:
        src_items = (
            src_mapping.items()
            if isinstance(src_mapping, Mapping)
            else src_mapping)
        for key, src_val in src_items:
            target_val = target_mapping.get(key)
            if isinstance(target_val, MutableMapping):
                update_mapping_recursively(target_val, src_val)
            else:
                target_mapping[key] = copy.deepcopy(src_val)


def merge_mappings_recursively(*args, **kwargs):
    """
    Create a dict whose contents is the result of applying the
    update_mapping_recursively() function to a new empty dict plus any
    source mappings specified as positional/keyword arguments (see the
    following example as well as the docstring of the
    update_mapping_recursively() function).

    >>> src0 = {
    ...     'abc': 42,
    ...     'foo': 'BAR',
    ...     'xyz': {1: 2, 3: {4: 5, 'spam': 'ham'}, 6: 7},
    ...     123: [set(['FOO', 'BAR']), 'S', 'P', 'AM'],
    ... }
    >>> src1 = {
    ...     'abc': {'x': 'y', 'ZZZ': {'A': 789, 'B': 'C'}},
    ...     'SPAMMY': 'hammy',
    ...     True: {'no': False},
    ... }
    >>> src2 = {
    ...     'abc': {'qqq': 'rrr', 'ZZZ': [('A', 456)]},
    ...     'xyz': {3: {4: 55, 8: 99}, 6: 77, 'z': 0},
    ...     'SPAMMY': 'non-hammy',
    ...     123: [333, 22, 1],
    ... }
    >>> kwarg_xyz = [(44.0, 't'), ('z', None)]
    >>> new = merge_mappings_recursively(src0, src1, src2,
    ...                                  xyz=kwarg_xyz,
    ...                                  YetAnother=43)
    >>> new == {
    ...     'abc': {'x': 'y', 'qqq': 'rrr', 'ZZZ': {'A': 456, 'B': 'C'}},
    ...     'foo': 'BAR',
    ...     'xyz': {1: 2, 3: {4: 55, 8: 99, 'spam': 'ham'},
    ...             6: 77, 44.0: 't', 'z': None},
    ...     'SPAMMY': 'non-hammy',
    ...     'YetAnother': 43,
    ...     123: [333, 22, 1],
    ...     True: {'no': False},
    ... }
    True
    >>> # NOTE that the source data containers have *not* been changed:
    ... src0 == {
    ...     'abc': 42,
    ...     'foo': 'BAR',
    ...     'xyz': {1: 2, 3: {4: 5, 'spam': 'ham'}, 6: 7},
    ...     123: [set(['FOO', 'BAR']), 'S', 'P', 'AM'],
    ... } and src1 == {
    ...     'abc': {'x': 'y', 'ZZZ': {'A': 789, 'B': 'C'}},
    ...     'SPAMMY': 'hammy',
    ...     True: {'no': False},
    ... } and src2 == {
    ...     'abc': {'qqq': 'rrr', 'ZZZ': [('A', 456)]},
    ...     'xyz': {3: {4: 55, 8: 99}, 6: 77, 'z': 0},
    ...     'SPAMMY': 'non-hammy',
    ...     123: [333, 22, 1],
    ... } and kwarg_xyz == [(44.0, 't'), ('z', None)]
    True
    """
    target_dict = {}
    update_mapping_recursively(target_dict, *args, **kwargs)
    return target_dict


def deep_copying_result(func):
    """
    A decorator which ensures that the result of each call is deep-copied.

    >>> @deep_copying_result
    ... def func(obj):
    ...     global obj_itself
    ...     obj_itself = obj
    ...     return obj
    ...
    >>> a = [1, 2, {'x': {'y': []}}]
    >>> b = func(a)

    >>> a is b
    False
    >>> a[2] is b[2]
    False
    >>> a[2]['x'] is b[2]['x']
    False
    >>> a[2]['x']['y'] is b[2]['x']['y']
    False

    >>> b == a == obj_itself
    True
    >>> a is obj_itself
    True
    """

    deepcopy = copy.deepcopy

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        orig_result = func(*args, **kwargs)
        return deepcopy(orig_result)

    wrapper.func = func  # making the original function still available
    return wrapper


def exiting_on_exception(func=None,
                         exc_factory=SystemExit,
                         exc_message_pattern=(
                             'FATAL ERROR!\n'
                             '{traceback_msg}\n'
                             'CONDENSED DEBUG INFO:'
                             ' [thread {thread_name!a}'
                             ' (#{thread_ident})]'
                             ' {condensed_debug_msg}'
                         )):
    """
    A decorator which ensures that any exception not being SystemExit or
    KeyboardInterrupt will be transformed to SystemExit (the default) or
    an exception made with the custom `exc_factory`.

    By default, the exception is made with a 'FATAL ERROR...' message
    as the argument, containing appropriate debug information. You can
    customize that message by specifying `exc_message_pattern`, in
    which you can use any of the following `str.format()`-able fields:
    `{traceback_msg}` (already nicely formatted traceback), `{exc_info}`
    (`sys.exc_info()` call result), `{thread_name}`, `{thread_ident}`,
    `{condensed_debug_msg}` (from a `make_condensed_debug_msg()` call).

    Simple usage (using the defaults: SystemExit and the default message):

        @exiting_on_exception
        def some(...):
            ...

    Usage with keyword arguments:

        @exiting_on_exception(exc_factory=RuntimeError)
        def some(...):
            ...

        @exiting_on_exception(
            exc_message_pattern='Exiting with error! {condensed_debug_msg}')
        def another(...):
            ...

        @exiting_on_exception(
            exc_factory=n6CollectorException,
            exc_message_pattern='Could not collect data! {condensed_debug_msg}')
        def yet_another(...):
            ...
    """
    if func is None:
        return functools.partial(exiting_on_exception,
                                 exc_factory=exc_factory,
                                 exc_message_pattern=exc_message_pattern)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:
            exc_info = sys.exc_info()
            try:
                condensed_debug_msg = make_condensed_debug_msg(
                    exc_info,
                    total_limit=None,
                    exc_str_limit=1000,
                    tb_str_limit=None,
                    stack_str_limit=None)
                traceback_msg = ''.join(traceback.format_exception(*exc_info)).strip()
                cur_thread = threading.current_thread()
                raised_exc = exc_factory(exc_message_pattern.format(
                    traceback_msg=traceback_msg,
                    exc_info=exc_info,
                    thread_name=ascii_str(cur_thread.name),
                    thread_ident=cur_thread.ident,
                    condensed_debug_msg=condensed_debug_msg))
                raise raised_exc from exc
            finally:
                # (to break any traceback-related reference cycles)
                exc_info = raised_exc = None  # noqa

    wrapper.func = func  # making the original function still available
    return wrapper


def picklable(func_or_class):
    """
    Make the given (possibly non-top-level) function or class picklable.

    Note: this decorator may change values of the `__module__` and/or
    `__name__` and/or `__qualname__` attributes of the given function
    or class.

    >>> from pickle import PicklingError, dumps, loads
    >>> def _make_nontoplevel():
    ...     def func_a(x, y): return x, y
    ...     func_b = lambda: None
    ...     func_b2 = lambda: None
    ...     func_b3 = lambda: None
    ...     class class_C: z = 3
    ...     return func_a, func_b, func_b2, func_b3, class_C
    ...
    >>> a, b, b2, b3, C = _make_nontoplevel()

    >>> a.__module__.endswith('common_helpers')
    True
    >>> a.__name__
    'func_a'
    >>> a.__qualname__
    '_make_nontoplevel.<locals>.func_a'
    >>> try: dumps(a)
    ... except (PicklingError, TypeError, AttributeError): print('Nie da rady!')
    ...
    Nie da rady!
    >>> picklable(a) is a    # applying the decorator
    True
    >>> a.__module__
    'n6lib._picklable_objs'
    >>> a.__name__
    'func_a'
    >>> a.__qualname__
    'func_a'
    >>> import n6lib._picklable_objs
    >>> n6lib._picklable_objs.func_a is a
    True
    >>> loads(dumps(a)) is a
    True

    >>> b is not b2 and b is not b3 and b2 is not b3
    True
    >>> (b.__module__.endswith('common_helpers')
    ...  and b.__module__ == b2.__module__ == b3.__module__)
    True
    >>> b.__name__ == b2.__name__ == b3.__name__ == '<lambda>'
    True
    >>> b.__qualname__ == b2.__qualname__ == b3.__qualname__ == (
    ...     '_make_nontoplevel.<locals>.<lambda>')
    True
    >>> try: dumps(b)
    ... except (PicklingError, TypeError, AttributeError): print('Nie da rady!')
    ...
    Nie da rady!
    >>> try: dumps(b2)
    ... except (PicklingError, TypeError, AttributeError): print('Nie da rady!')
    ...
    Nie da rady!
    >>> try: dumps(b3)
    ... except (PicklingError, TypeError, AttributeError): print('Nie da rady!')
    ...
    Nie da rady!
    >>> picklable(b) is b    # applying the decorator
    True
    >>> picklable(b2) is b2  # applying the decorator
    True
    >>> picklable(b3) is b3  # applying the decorator
    True
    >>> (b.__module__ == b2.__module__ == b3.__module__ ==
    ...  'n6lib._picklable_objs')
    True
    >>> b.__name__
    '<lambda>'
    >>> b2.__name__          # note this value!
    '<lambda>__2'
    >>> b3.__name__          # note this value!
    '<lambda>__3'
    >>> b.__qualname__
    '<lambda>'
    >>> b2.__qualname__
    '<lambda>__2'
    >>> b3.__qualname__
    '<lambda>__3'
    >>> getattr(n6lib._picklable_objs, '<lambda>') is b
    True
    >>> getattr(n6lib._picklable_objs, '<lambda>__2') is b2
    True
    >>> getattr(n6lib._picklable_objs, '<lambda>__3') is b3
    True
    >>> loads(dumps(b)) is b
    True
    >>> loads(dumps(b2)) is b2
    True
    >>> loads(dumps(b3)) is b3
    True

    >>> C.__module__.endswith('common_helpers')
    True
    >>> C.__name__
    'class_C'
    >>> C.__qualname__
    '_make_nontoplevel.<locals>.class_C'
    >>> try: dumps(C)
    ... except (PicklingError, TypeError, AttributeError): print('Nie da rady!')
    ...
    Nie da rady!
    >>> picklable(C) is C    # applying the decorator
    True
    >>> C.__module__
    'n6lib._picklable_objs'
    >>> C.__name__
    'class_C'
    >>> C.__qualname__
    'class_C'
    >>> n6lib._picklable_objs.class_C is C
    True
    >>> loads(dumps(C)) is C
    True

    >>> mod = picklable.__module__
    >>> mod.endswith('common_helpers')
    True
    >>> picklable.__name__
    'picklable'
    >>> picklable.__qualname__
    'picklable'
    >>> loads(dumps(picklable)) is picklable
    True
    >>> picklable(picklable) is picklable   # nothing changes after applying:
    True
    >>> picklable.__module__ == mod
    True
    >>> picklable.__name__
    'picklable'
    >>> picklable.__qualname__
    'picklable'
    >>> loads(dumps(picklable)) is picklable
    True
    """
    import importlib
    name = func_or_class.__name__
    try:
        mod = importlib.import_module(func_or_class.__module__)
        if getattr(mod, name, None) is not func_or_class:
            raise ImportError
    except ImportError:
        from n6lib import _picklable_objs
        namespace = vars(_picklable_objs)
        count = 1
        while namespace.setdefault(name, func_or_class) is not func_or_class:
            count += 1
            name = '{}__{}'.format(func_or_class.__name__, count)
        func_or_class.__name__ = func_or_class.__qualname__ = name
        func_or_class.__module__ = 'n6lib._picklable_objs'
    return func_or_class


def reduce_indent(s):
    r"""
    Reduce indent, retaining relative indentation, except that the first
    line's indent is completely ignored and erased.

    Args:
        `s` (str or bytes/bytearray):
            The input string (or bytes sequence).

    Returns:
        A copy of the input string (or bytes sequence) with minimized
        indentation; its type is the type of `s`.

        Note #1: All tab (`\t`) characters (or bytes) are, at first,
        converted to spaces (by applying the expandtabs() method to
        the input string).

        Note #2: The splitlines_asc() helper is applied to the input
        string. That means that, in particular, different newline styles
        are recognized (`\n`, `\r` and `\r\n`) but in the returned
        string all newlines are normalized to `\n` (the Unix style).

        Note #3: The first line as well as any lines that consist only
        of whitespace characters (or bytes) -- are:

        * omitted when it comes to inspection and reduction of
          indentation depth;

        * treated (individually) with the lstrip() string method (so any
          indentation is unconditionally removed from them).

        The remaining lines are subject of uniform reduction of
        indentation -- as deep as possible without changing indentation
        differences between the lines.


    A few examples (including some corner cases):

    >>> reduce_indent(b''' Lecz
    ...   Nie za bardzo.
    ...     Za bardzo nie.
    ...       Raczej te\xc5\xbc.''') == (b'''Lecz
    ... Nie za bardzo.
    ...   Za bardzo nie.
    ...     Raczej te\xc5\xbc.''')
    True

    >>> reduce_indent('''\tAzaliż
    ...      Ala ma kota.
    ...       A kot ma Alę.
    ...     Ala go kocha...
    ...
    ... \tA kot na to:
    ...         niemożliwe.
    ... ''') == ('''Azaliż
    ...  Ala ma kota.
    ...   A kot ma Alę.
    ... Ala go kocha...
    ...
    ...     A kot na to:
    ...     niemożliwe.
    ... ''')
    True

    >>> reduce_indent('''
    ...      Ala ma kota.
    ...       A kot ma Alę.\r
    ...    \vAla go kocha...
    ... \t\f
    ...  \tA kot na to:\f
    ...         niemożliwe.\v
    ... ''') == ('''
    ...  Ala ma kota.
    ...   A kot ma Alę.
    ... Ala go kocha...
    ...
    ...     A kot na to:\f
    ...     niemożliwe.\v
    ... ''')
    True

    >>> reduce_indent('\n \n X\n  ABC')
    '\n\nX\n ABC'
    >>> reduce_indent(' ---\n \n\t\n  ABC\n\r\n')
    '---\n\n\nABC\n\n'
    >>> reduce_indent(bytearray(b'  abc\t\n    def\r\n   123\r        '))
    bytearray(b'abc   \n def\n123\n')
    >>> reduce_indent('    abc\n    def\r\n   123\r        x ')
    'abc\n def\n123\n     x '

    >>> reduce_indent('')
    ''
    >>> reduce_indent(b' ')
    b''
    >>> reduce_indent('\n')
    '\n'
    >>> reduce_indent(b'\r\n')
    b'\n'
    >>> reduce_indent('\n \n')
    '\n\n'
    >>> reduce_indent(b' \r \r\n ')
    b'\n\n'
    >>> reduce_indent('x')
    'x'
    >>> reduce_indent(b' x')
    b'x'
    >>> reduce_indent('\nx\n')
    '\nx\n'
    >>> reduce_indent(b' \r x\r\n ')
    b'\nx\n'
    >>> reduce_indent(bytearray(b' \r  x\r\n y\n '))
    bytearray(b'\n x\ny\n')
    """
    tp = type(s)
    empty, lf, cr = '', '\n', '\r'
    if issubclass(tp, (bytes, bytearray)):
        empty, lf, cr = map(as_bytes, (empty, lf, cr))
    elif not issubclass(tp, str):
        raise TypeError('{!a} is neither a `str` nor a `bytes`/`bytearray`'.format(s))

    if not s:
        return s

    empty, lf, cr = map(tp, (empty, lf, cr))
    inf = float('inf')

    def _get_lines(s):
        lines = splitlines_asc(s.expandtabs(8))
        assert s and lines
        if s.endswith((lf, cr)):
            lines.append(empty)
        return lines

    def _get_min_indent(lines):
        min_indent = inf
        for i, li in enumerate(lines):
            lstripped = li.lstrip()
            if lstripped and i > 0:
                cur_indent = len(li) - len(lstripped)
                min_indent = min(min_indent, cur_indent)
        return min_indent

    def _modify_lines(lines, min_indent):
        for i, li in enumerate(lines):
            lstripped = li.lstrip()
            if lstripped and i > 0:
                assert min_indent < inf
                lines[i] = li[min_indent:]
            else:
                lines[i] = lstripped

    lines = _get_lines(s)
    min_indent = _get_min_indent(lines)
    _modify_lines(lines, min_indent)
    return lf.join(lines)


def replace_segment(s, segment_index, new_content, sep='.'):
    """
    Replace the specified separator-surrounded segment in the given text
    string or bytes sequence (producing a new string or bytes sequence).

    Args:
        `s` (str or bytes/bytearray):
            The input string or bytes sequence.
        `segment_index` (int or slice)
            The number (0-indexed) of the segment to be replaced,
            or a slice object specifying that segment.
        `new_content` (str or bytes/bytearray, auto-coerced to type of `s`):
            The string (or bytes sequence) to be placed as the segment.

    Kwargs:
        `sep` (default: '.'; str or bytes/bytearray, auto-coerced to type of `s`):
            The string (or bytes sequence) that separates segments.

    Returns:
        A copy of the input string (or bytes sequence) with the specified
        segment replaced.

    >>> replace_segment('a.b.c.d', 1, 'ZZZ')
    'a.ZZZ.c.d'
    >>> replace_segment('a.b.c.d', 1, b'ZZZ')
    'a.ZZZ.c.d'
    >>> replace_segment(b'a.b.c.d', 1, b'ZZZ')
    b'a.ZZZ.c.d'
    >>> replace_segment(b'a.b.c.d', 1, 'ZZZ')
    b'a.ZZZ.c.d'
    >>> replace_segment('a.b.c.d', slice(1, 3), 'AAA.ZZZ')
    'a.AAA.ZZZ.d'
    >>> replace_segment('a.b.c.d', slice(1, 3), 'AAA')
    'a.AAA.d'
    >>> replace_segment('a.b.c.d', slice(1, 3), 'q.w.e.r.t.y')
    'a.q.w.e.r.t.y.d'
    >>> replace_segment('a.b.c.d', slice(1, 3), b'AAA.ZZZ', sep=b'.')
    'a.AAA.ZZZ.d'
    >>> replace_segment(b'a.b.c.d', slice(1, 3), 'AAA.ZZZ', sep='.')
    b'a.AAA.ZZZ.d'
    >>> replace_segment(b'a;b;c;d', slice(1, 3), 'AAA;ZZZ', sep=b';')
    b'a;AAA;ZZZ;d'
    >>> replace_segment(bytearray(b'a::b::c::d'), 2, 'ZZZ', sep=b'::')
    bytearray(b'a::b::ZZZ::d')
    >>> replace_segment('a::b::c::d', 2, b'ZZZ', sep=bytearray(b'::'))
    'a::b::ZZZ::d'
    """
    tp = type(s)
    if issubclass(tp, (bytes, bytearray)):
        new_content = as_bytes(new_content)
        sep = as_bytes(sep)
    elif issubclass(tp, str):
        if isinstance(new_content, (bytes, bytearray)):
            new_content = new_content.decode('utf-8')
        if isinstance(sep, (bytes, bytearray)):
            sep = sep.decode('utf-8')
    else:
        raise TypeError('{!a} is neither a `str` nor a `bytes`/`bytearray`'.format(s))
    new_content = tp(new_content)
    sep = tp(sep)
    segments = s.split(sep)
    if isinstance(segment_index, slice):
        segments[segment_index] = new_content.split(sep)
    else:
        segments[segment_index] = new_content
    return sep.join(segments)


def splitlines_asc(s, keepends=False, *, append_empty_ending=False):
    r"""
    Like the built-in `{str/bytes/bytearray}.splitlines()` method, but
    split only at ASCII line boundaries (`\n`, `\r\n`, `\r`), even if
    the argument is a `str` (whereas the standard `str.splitlines()`
    method does the splits also at some other line boundary characters,
    including `\v`, `\f`, `\u2028` and a few others...).

    Additionally, an extra optional keyword-only argument can be given:
    `append_empty_ending` (it is `False` by default). If you set it to
    a truthy value (such as `True`) *and* the input string (or input
    binary data) ends with a line boundary, the resultant list will
    contain an additional empty item (see the examples below).

    **Note:** the input need *not* to be ASCII-only.

    ***

    For `str`:

    >>> s = 'abc\ndef\rghi\vjkl\f\u2028mno\r\npqr\n'
    >>> splitlines_asc(s)
    ['abc', 'def', 'ghi\x0bjkl\x0c\u2028mno', 'pqr']
    >>> splitlines_asc(s, True)
    ['abc\n', 'def\r', 'ghi\x0bjkl\x0c\u2028mno\r\n', 'pqr\n']
    >>> splitlines_asc(s + 'xyz')
    ['abc', 'def', 'ghi\x0bjkl\x0c\u2028mno', 'pqr', 'xyz']
    >>> splitlines_asc(s + 'xyz', True)
    ['abc\n', 'def\r', 'ghi\x0bjkl\x0c\u2028mno\r\n', 'pqr\n', 'xyz']

    ...the results are *different* than when using the method:

    >>> s.splitlines()
    ['abc', 'def', 'ghi', 'jkl', '', 'mno', 'pqr']
    >>> s.splitlines(True)
    ['abc\n', 'def\r', 'ghi\x0b', 'jkl\x0c', '\u2028', 'mno\r\n', 'pqr\n']
    >>> (s + 'xyz').splitlines()
    ['abc', 'def', 'ghi', 'jkl', '', 'mno', 'pqr', 'xyz']
    >>> (s + 'xyz').splitlines(True)
    ['abc\n', 'def\r', 'ghi\x0b', 'jkl\x0c', '\u2028', 'mno\r\n', 'pqr\n', 'xyz']

    Note that the results *may* be even slightly *more different* if
    `append_empty_ending=True` is passed to `splitlines_asc()`:

    >>> splitlines_asc(s, append_empty_ending=True)
    ['abc', 'def', 'ghi\x0bjkl\x0c\u2028mno', 'pqr', '']
    >>> splitlines_asc(s, True, append_empty_ending=True)
    ['abc\n', 'def\r', 'ghi\x0bjkl\x0c\u2028mno\r\n', 'pqr\n', '']
    >>> splitlines_asc(s + 'xyz', append_empty_ending=True)
    ['abc', 'def', 'ghi\x0bjkl\x0c\u2028mno', 'pqr', 'xyz']
    >>> splitlines_asc(s + 'xyz', True, append_empty_ending=True)
    ['abc\n', 'def\r', 'ghi\x0bjkl\x0c\u2028mno\r\n', 'pqr\n', 'xyz']

    ***

    For `bytes`/`bytearray`:

    >>> b = b"abc\ndef\rghi\vjkl\fmno\r\npqr\n"
    >>> splitlines_asc(b)
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr']
    >>> splitlines_asc(b, True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n']
    >>> splitlines_asc(b + b'xyz')
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr', b'xyz']
    >>> splitlines_asc(b + b'xyz', True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n', b'xyz']
    >>> splitlines_asc(bytearray(b'ghi\vjkl\rspam\r\n'))
    [bytearray(b'ghi\x0bjkl'), bytearray(b'spam')]

    ...the results are *the same* as when using the method:

    >>> b.splitlines()
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr']
    >>> b.splitlines(True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n']
    >>> splitlines_asc(b + b'xyz')
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr', b'xyz']
    >>> splitlines_asc(b + b'xyz', True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n', b'xyz']
    >>> bytearray(b'ghi\vjkl\rspam\r\n').splitlines()
    [bytearray(b'ghi\x0bjkl'), bytearray(b'spam')]

    ...*except that* the results *may* be *slightly* different if
    `append_empty_ending=True` is passed to `splitlines_asc()`:

    >>> splitlines_asc(b, append_empty_ending=True)
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr', b'']
    >>> splitlines_asc(b, True, append_empty_ending=True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n', b'']
    >>> splitlines_asc(b + b'xyz', append_empty_ending=True)
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr', b'xyz']
    >>> splitlines_asc(b + b'xyz', True, append_empty_ending=True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n', b'xyz']
    >>> splitlines_asc(bytearray(b'ghi\vjkl\rspam\r\n'), append_empty_ending=True)
    [bytearray(b'ghi\x0bjkl'), bytearray(b'spam'), bytearray(b'')]
    """
    if isinstance(s, (bytes, bytearray)):
        result = s.splitlines(keepends)
        if append_empty_ending and s.endswith((b'\n', b'\r')):
            result.append(b'' if isinstance(s, bytes) else bytearray(b''))
        return result
    if isinstance(s, str):
        result = [
            b.decode('utf-8', 'surrogatepass')
            for b in s.encode('utf-8', 'surrogatepass').splitlines(keepends)]
        if append_empty_ending and s.endswith(('\n', '\r')):
            result.append('')
        return result
    raise TypeError('{!a} is neither a `str` nor a `bytes`/`bytearray`'.format(s))


def limit_str(s, char_limit, cut_indicator='[...]', middle_cut=False):
    r"""
    Shorten the given text string (`s`) to the specified number of
    characters (`char_limit`) by replacing exceeding stuff with the
    given `cut_indicator` ("[...]" by default).

    Note: this function accepts only text strings (`str`), *not* binary
    data (such as `bytes`/`bytearray`).

    By default, the cut is made at the end of the string but doing it in
    the middle of the string can be requested by specifying `middle_cut`
    as True.

    The `char_limit` number (an `int`) must be greater than or equal to
    the length of `cut_indicator`; otherwise ValueError is raised.

    >>> limit_str('Alą mą ĸóŧą', 10)
    'Alą m[...]'
    >>> limit_str('Alą mą ĸóŧą', 11)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 12)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 1000000)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 9)
    'Alą [...]'
    >>> limit_str('Alą mą ĸóŧą', 8)
    'Alą[...]'
    >>> limit_str('Alą mą ĸóŧą', 7)
    'Al[...]'
    >>> limit_str('Alą mą ĸóŧą', 6)
    'A[...]'
    >>> limit_str('Alą mą ĸóŧą', 5)
    '[...]'
    >>> limit_str('Alą mą ĸóŧą', 4)                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą mą ĸóŧą', 3)                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą mą ĸóŧą', 0)                             # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> limit_str('Alą mą ĸóŧą', 10, middle_cut=True)
    'Alą[...]ŧą'
    >>> limit_str('Alą mą ĸóŧą', 11, middle_cut=True)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 12, middle_cut=True)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 1000000, middle_cut=True)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 9, middle_cut=True)
    'Al[...]ŧą'
    >>> limit_str('Alą mą ĸóŧą', 8, middle_cut=True)
    'Al[...]ą'
    >>> limit_str('Alą mą ĸóŧą', 7, middle_cut=True)
    'A[...]ą'
    >>> limit_str('Alą mą ĸóŧą', 6, middle_cut=True)
    'A[...]'
    >>> limit_str('Alą mą ĸóŧą', 5, middle_cut=True)
    '[...]'
    >>> limit_str('Alą mą ĸóŧą', 4, middle_cut=True)            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą mą ĸóŧą', 3, middle_cut=True)            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą mą ĸóŧą', 0, middle_cut=True)            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> limit_str('Alą mą ĸóŧą', 12, cut_indicator='**Ś*')
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 12, cut_indicator='**Ś*', middle_cut=True)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 11, cut_indicator='**Ś*')
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 11, cut_indicator='**Ś*', middle_cut=True)
    'Alą mą ĸóŧą'
    >>> limit_str('Alą mą ĸóŧą', 10, cut_indicator='**Ś*')
    'Alą mą**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 10, cut_indicator='**Ś*', middle_cut=True)
    'Alą**Ś*óŧą'
    >>> limit_str('Alą mą ĸóŧą', 6, cut_indicator='**Ś*')
    'Al**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 6, cut_indicator='**Ś*', middle_cut=True)
    'A**Ś*ą'
    >>> limit_str('Alą mą ĸóŧą', 5, cut_indicator='**Ś*')
    'A**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 5, cut_indicator='**Ś*', middle_cut=True)
    'A**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 4, cut_indicator='**Ś*')
    '**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 4, cut_indicator='**Ś*', middle_cut=True)
    '**Ś*'
    >>> limit_str('Alą mą ĸóŧą', 3, cut_indicator='**Ś*')       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą mą ĸóŧą', 3, cut_indicator='**Ś*',
    ...           middle_cut=True)                              # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> limit_str('Alą', 4, cut_indicator='')
    'Alą'
    >>> limit_str('Alą', 4, cut_indicator='', middle_cut=True)
    'Alą'
    >>> limit_str('Alą', 3, cut_indicator='')
    'Alą'
    >>> limit_str('Alą', 3, cut_indicator='', middle_cut=True)
    'Alą'
    >>> limit_str('Alą', 2, cut_indicator='')
    'Al'
    >>> limit_str('Alą', 2, cut_indicator='', middle_cut=True)
    'Aą'
    >>> limit_str('Alą', 1, cut_indicator='')
    'A'
    >>> limit_str('Alą', 1, cut_indicator='', middle_cut=True)
    'A'
    >>> limit_str('Alą', 0, cut_indicator='')
    ''
    >>> limit_str('Alą', 0, cut_indicator='', middle_cut=True)
    ''

    >>> limit_str('Alą', 0, cut_indicator='*')                  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('Alą', 0, cut_indicator='*',
    ...           middle_cut=True)                              # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> limit_str('', 10)
    ''
    >>> limit_str('', 10, middle_cut=True)
    ''
    >>> limit_str('', 0, cut_indicator='')
    ''
    >>> limit_str('', 0, cut_indicator='', middle_cut=True)
    ''

    >>> limit_str('', 0, cut_indicator='*')                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> limit_str('', 0, cut_indicator='*', middle_cut=True)    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    """
    if not isinstance(s, str):
        raise TypeError('{!a} is not a `str`'.format(s))
    if not isinstance(cut_indicator, str):
        raise TypeError('cut_indicator={!a} is not a `str`'.format(cut_indicator))
    effective_limit = char_limit - len(cut_indicator)
    if effective_limit < 0:
        raise ValueError(
            '`char_limit` is too small: {}, i.e., smaller than '
            'the length of `cut_indicator` ({!a})'.format(
                char_limit,
                cut_indicator))
    if len(s) > char_limit:
        right_limit, odd = divmod(effective_limit, 2)
        if middle_cut and right_limit:
            left_limit = right_limit + odd
            s = s[:left_limit] + cut_indicator + s[-right_limit:]
        else:
            s = s[:effective_limit] + cut_indicator
    assert len(s) <= char_limit
    return s


def as_bytes(obj, encode_error_handling='surrogatepass'):
    r"""
    Convert the given object to `bytes`.

    If the given object is a `str` -- encode it using `utf-8` with the
    error handler specified as the second argument, `encode_error_handling`
    (whose default value is `'surrogatepass'`).

    If the given object is a `bytes`, `bytearray` or `memoryview`,
    or an object whose type provides the `__bytes__()` special method
    (actually, the check is whether the type's `__bytes__` attribute
    exists and is not `None`), coerce it with the `bytes()` constructor.

    In any other case -- raise `TypeError`.

    >>> s = 'zażółć\udcdd'
    >>> b = s[:-1].encode('utf-8') + b'\xed\xb3\x9d'
    >>> type(b) is bytes and as_bytes(b) is b
    True
    >>> b2 = as_bytes(s)
    >>> b2 == b and type(b2) is bytes
    True
    >>> b3 = as_bytes(bytearray(b))
    >>> b3 == b and type(b3) is bytes
    True
    >>> b4 = as_bytes(memoryview(b))
    >>> b4 == b and type(b4) is bytes
    True
    >>> class WithDunderBytes:
    ...     def __bytes__(self):
    ...         return b
    ...
    >>> b5 = as_bytes(WithDunderBytes())
    >>> b5 == b and type(b5) is bytes
    True
    >>> as_bytes(123)               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    if isinstance(obj, str):
        return obj.encode('utf-8', encode_error_handling)
    if (isinstance(obj, (bytes, bytearray, memoryview))
          or getattr(type(obj), '__bytes__', None) is not None):
        return bytes(obj)
    raise TypeError('{!a} cannot be converted to bytes'.format(obj))


### CR: db_event (and maybe some other stuff) uses different implementation
### -- fix it?? (unification needed??)
# TODO: support ipaddress.* stuff...
def ipv4_to_int(ipv4, accept_no_dot=False):
    r"""
    Return, as `int`, an IPv4 address specified as a `str` or `int`.

    Args/kwargs:
        `ipv4`:
            IPv4 as a `str` (formatted as 4 dot-separated decimal numbers
            or, if `accept_no_dot` is true, possibly also as one decimal
            number) or as an `int` number.
        `accept_no_dot` (bool, default: False):
            If true -- accept `ipv4` *also* as a `str` formatted as one
            decimal number.

    Returns:
        The IPv4 address as an `int` number.

    Raises:
        `ValueError` or `TypeError`.

    >>> ipv4_to_int('193.59.204.91')
    3241921627
    >>> ipv4_to_int('193.059.0204.91')   # (for good or for bad, extra leading `0`s are ignored)
    3241921627
    >>> ipv4_to_int('193.59.204.91 ')
    3241921627
    >>> ipv4_to_int(' 193 . 59 . 204.91')
    3241921627
    >>> ipv4_to_int(' 193.59. 204 .91 ')
    3241921627
    >>> ipv4_to_int(3241921627)
    3241921627
    >>> ipv4_to_int('3241921627', accept_no_dot=True)
    3241921627
    >>> ipv4_to_int(' 000003241921627 ', accept_no_dot=True)
    3241921627
    >>> ipv4_to_int('4294967295 ', accept_no_dot=True)
    4294967295
    >>> ipv4_to_int(4294967295)
    4294967295
    >>> ipv4_to_int('255.255.255.255')
    4294967295
    >>> from n6lib.const import (
    ...     LACK_OF_IPv4_PLACEHOLDER_AS_INT,  # 0
    ...     LACK_OF_IPv4_PLACEHOLDER_AS_STR,  # '0.0.0.0'
    ... )
    >>> ipv4_to_int(LACK_OF_IPv4_PLACEHOLDER_AS_INT) == LACK_OF_IPv4_PLACEHOLDER_AS_INT
    True
    >>> ipv4_to_int(LACK_OF_IPv4_PLACEHOLDER_AS_STR) == LACK_OF_IPv4_PLACEHOLDER_AS_INT
    True
    >>> ipv4_to_int(' 0.\t000000. 0000.0000000000 ') == LACK_OF_IPv4_PLACEHOLDER_AS_INT
    True
    >>> ipv4_to_int(str(LACK_OF_IPv4_PLACEHOLDER_AS_INT),
    ...             accept_no_dot=True) == LACK_OF_IPv4_PLACEHOLDER_AS_INT
    True

    >>> ipv4_to_int(str(LACK_OF_IPv4_PLACEHOLDER_AS_INT))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('3241921627')          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('3241921627', accept_no_dot=False)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('193.59.204.91.123')   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('193.59.204.256')      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int(-1)                    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int(4294967296)            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int(32419216270000000)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('-1',                  # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('4294967296',          # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('32419216270000000',   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int(bytearray(b'193.59.204.91'))      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> ipv4_to_int(b'3241921627', accept_no_dot=True)   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> ipv4_to_int(3241921627.0)                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    try:
        if isinstance(ipv4, int):
            int_value = ipv4
        elif not isinstance(ipv4, str):
            raise TypeError('{!a} is neither `str` nor `int`'.format(ipv4))
        elif accept_no_dot and ipv4.strip().isdigit():
            int_value = int(ipv4)
        else:
            numbers = list(map(int, ipv4.split('.')))  ## FIXME: 04.05.06.0222 etc. are accepted and interpreted as decimal, should they???
            if len(numbers) != 4:
                raise ValueError
            if not all(0 <= num <= 0xff for num in numbers):
                raise ValueError
            multiplied = [num << rot
                          for num, rot in zip(numbers, (24, 16, 8, 0))]
            int_value = sum(multiplied)
        if not 0 <= int_value <= 0xffffffff:
            raise ValueError
    except ValueError as exc:
        raise ValueError('{!a} is not a valid IPv4 address'.format(ipv4)) from exc
    return int_value


### CR: db_event (and maybe some other stuff) uses different implementation
### -- fix it?? (unification needed??)
# TODO: support stuff from the `ipaddress` std lib module...
def ipv4_to_str(ipv4, accept_no_dot=False):
    r"""
    Return, as a `str`, the IPv4 address specified as a `str` or `int`.

    Args/kwargs:
        `ipv4`:
            IPv4 as a `str` (formatted as 4 dot-separated decimal numbers
            or, if `accept_no_dot` is true, possibly also as one decimal
            number) or as an `int` number.
        `accept_no_dot` (bool, default: False):
            If true -- accept `ipv4` *also* as a `str` formatted as one
            decimal number.

    Returns:
        The IPv4 address, in its normalized form, as a `str`.

    Raises:
        `ValueError` or `TypeError`.

    >>> ipv4_to_str('193.59.204.91')
    '193.59.204.91'
    >>> ipv4_to_str('193.059.0204.91')   # (for good or for bad, extra leading `0`s are ignored)
    '193.59.204.91'
    >>> ipv4_to_str('193.59.204.91 ')
    '193.59.204.91'
    >>> ipv4_to_str(' 193 . 59 . 204.91')
    '193.59.204.91'
    >>> ipv4_to_str(' 193.59. 204 .91 ')
    '193.59.204.91'
    >>> ipv4_to_str(3241921627)
    '193.59.204.91'
    >>> ipv4_to_str('3241921627', accept_no_dot=True)
    '193.59.204.91'
    >>> ipv4_to_str(' 000003241921627 ', accept_no_dot=True)
    '193.59.204.91'
    >>> ipv4_to_str('4294967295 ', accept_no_dot=True)
    '255.255.255.255'
    >>> ipv4_to_str(4294967295)
    '255.255.255.255'
    >>> ipv4_to_str('255.255.255.255')
    '255.255.255.255'
    >>> from n6lib.const import (
    ...     LACK_OF_IPv4_PLACEHOLDER_AS_INT,  # 0
    ...     LACK_OF_IPv4_PLACEHOLDER_AS_STR,  # '0.0.0.0'
    ... )
    >>> ipv4_to_str(LACK_OF_IPv4_PLACEHOLDER_AS_STR) == LACK_OF_IPv4_PLACEHOLDER_AS_STR
    True
    >>> ipv4_to_str('\t0000 .\r\n0.  00\t.000000\t') == LACK_OF_IPv4_PLACEHOLDER_AS_STR
    True
    >>> ipv4_to_str(LACK_OF_IPv4_PLACEHOLDER_AS_INT) == LACK_OF_IPv4_PLACEHOLDER_AS_STR
    True
    >>> ipv4_to_str(str(LACK_OF_IPv4_PLACEHOLDER_AS_INT),
    ...             accept_no_dot=True) == LACK_OF_IPv4_PLACEHOLDER_AS_STR
    True

    >>> ipv4_to_str(str(LACK_OF_IPv4_PLACEHOLDER_AS_INT))  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('3241921627')          # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('3241921627', accept_no_dot=False)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('193.59.204.91.123')   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('193.59.204.256')      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str(-1)                    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str(4294967296)            # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str(32419216270000000)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('-1',                  # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('4294967296',          # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('32419216270000000',   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str(b'193.59.204.91')      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> ipv4_to_str(bytearray(b'3241921627'),
    ...             accept_no_dot=True)               # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> ipv4_to_str(3241921627.0)                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    int_value = ipv4_to_int(ipv4, accept_no_dot)
    numbers = [(int_value >> rot) & 0xff
               for rot in (24, 16, 8, 0)]
    return '{0}.{1}.{2}.{3}'.format(*numbers)


def import_by_dotted_name(dotted_name):
    """
    Import an object specified by the given `dotted_name`.

    >>> obj = import_by_dotted_name('n6lib.tests._dummy_module_used_by_some_tests.DummyObj')
    >>> from n6lib.tests._dummy_module_used_by_some_tests import DummyObj
    >>> obj is DummyObj
    True

    >>> import_by_dotted_name('n6lib.tests._dummy_module_used_by_some_tests.NonExistentObj'
    ...                       )  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ImportError: ...
    """
    all_name_parts = dotted_name.split('.')
    importable_name = all_name_parts[0]
    obj = import_module(importable_name)
    for part in all_name_parts[1:]:
        importable_name += '.{}'.format(part)
        try:
            obj = getattr(obj, part)
        except AttributeError:
            try:
                import_module(importable_name)
            except ModuleNotFoundError as exc:
                raise ImportError(
                    f'cannot import {importable_name!a}',
                    name=exc.name, path=exc.path) from None
            obj = getattr(obj, part)
    return obj


def with_flipped_args(func):
    """
    From a given function that accepts exactly two positional parameters
    -- make a new function that accepts these parameters in the reversed
    order.

    >>> def foo(first, second):
    ...     print(first, second)
    ...
    >>> foo(42, 'zzz')
    42 zzz
    >>> flipped_foo = with_flipped_args(foo)
    >>> flipped_foo(42, 'zzz')
    zzz 42
    >>> flipped_foo.__name__
    'foo__with_flipped_args'
    >>> flipped_foo.__qualname__
    'with_flipped_args.<locals>.foo__with_flipped_args'

    >>> flipped_print = with_flipped_args(print)
    >>> flipped_print(42, 'zzz')
    zzz 42
    >>> flipped_print.__name__
    'print__with_flipped_args'
    >>> flipped_print.__qualname__
    'with_flipped_args.<locals>.print__with_flipped_args'

    This function can be useful when combined with functools.partial(),
    e.g.:

    >>> from functools import partial
    >>> from operator import contains
    >>> is_42_in = partial(with_flipped_args(contains), 42)
    >>> is_42_in([42, 43, 44])
    True
    >>> is_42_in({42: 43})
    True
    >>> is_42_in([1, 2, 3])
    False
    >>> is_42_in({43: 44})
    False
    """
    def flipped_func(a, b):
        return func(b, a)
    flipped_func.__name__ = func.__name__ + '__with_flipped_args'
    flipped_func.__qualname__ = '{}.<locals>.{}'.format(with_flipped_args.__name__,
                                                        flipped_func.__name__)
    return flipped_func


def iter_deduplicated(collection_of_objects: Iterable[HashableT]) -> Iterator[HashableT]:
    """
    For an iterable of objects given as the only argument
    (`collection_of_objects`), return an iterator which yields the same
    objects (in the same order) but omitting any duplicates. Duplicates
    are detected using `dict`/`set`-like containment tests, so all
    objects yielded by the iterable should be *hashable*.

    >>> some_string = 'abracadabra'
    >>> list(iter_deduplicated(some_string))
    ['a', 'b', 'r', 'c', 'd']

    >>> some_iterator = map(ord, some_string)
    >>> list(iter_deduplicated(some_iterator))
    [97, 98, 114, 99, 100]
    >>> list(some_iterator)
    []

    >>> some_list = [
    ...     5.0, 3, 5, 'dwa', 3.0, 1, b'dwa',
    ...     (1+0j,), frozenset({1}), 'dwa', 2,
    ...     frozenset({1+0j}), (1,), 'DWA', memoryview(b'dwa'),
    ... ]
    >>> it = iter_deduplicated(some_list)
    >>> next(it)
    5.0
    >>> next(it)
    3
    >>> next(it)
    'dwa'
    >>> next(it)
    1
    >>> next(it)
    b'dwa'
    >>> list(it)
    [((1+0j),), frozenset({1}), 2, 'DWA']

    >>> list(iter_deduplicated([                                # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     1, [1], [1.0], {},  # unhashable objects present...
    ... ]))
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    return iter(dict.fromkeys(collection_of_objects))


def iter_altered(collection_of_objects: Iterable[HashableT],
                 *,
                 without_items: Iterable[Hashable] = (),
                 extra_items: Iterable[T] = ()) -> Iterator[Union[HashableT, T]]:
    """
    For an iterable of objects given as the first argument
    (`collection_of_objects`), return an iterator which yields the
    same objects (in the same order) but omitting those present in
    the iterable given as the `without_items` keyword-only argument
    (the presence of objects in `without_items` is checked using
    `dict`/`set`-like containment tests, so all objects in both
    `collection_of_objects` and `without_items` need to be *hashable*).

    Additionally, at the first of those ommisions, yield all items from
    the iterable given as the `extra_items` keyword-only argument --
    except that if there are no omissions (i.e., `collection_of_objects`
    and `without_items` are disjoint) then the items from `extra_items`
    are yielded after all items from `collection_of_objects`.

    The default values of both `without_items` and `extra_items` are
    empty collections.

    >>> abracadabra = 'abracadabra'
    >>> ''.join(iter_altered(abracadabra, without_items='bc'))
    'araadara'
    >>> ''.join(iter_altered(abracadabra, without_items='bc', extra_items=''))
    'araadara'
    >>> ''.join(iter_altered(abracadabra, without_items='bc', extra_items='qwerty'))
    'aqwertyraadara'
    >>> ''.join(iter_altered(abracadabra, without_items='NOT in', extra_items='qwerty'))
    'abracadabraqwerty'
    >>> ''.join(iter_altered(abracadabra, without_items='', extra_items='qwerty'))
    'abracadabraqwerty'
    >>> ''.join(iter_altered(abracadabra, extra_items='qwerty'))
    'abracadabraqwerty'

    >>> ''.join(iter_altered(abracadabra))
    'abracadabra'
    >>> ''.join(iter_altered(abracadabra, without_items=''))
    'abracadabra'
    >>> ''.join(iter_altered(abracadabra, extra_items=''))
    'abracadabra'
    >>> ''.join(iter_altered(abracadabra, without_items='', extra_items=''))
    'abracadabra'
    >>> ''.join(iter_altered(abracadabra, without_items='NOT in'))
    'abracadabra'
    >>> ''.join(iter_altered(abracadabra, without_items='NOT in', extra_items=''))
    'abracadabra'

    >>> some_iterator = map(ord, abracadabra)
    >>> list(iter_altered(some_iterator, without_items=list(map(ord, 'bc'))))
    [97, 114, 97, 97, 100, 97, 114, 97]
    >>> list(some_iterator)
    []

    >>> some_list = [
    ...     5.0, 3, 5, 'dwa', 3.0, 1, b'dwa',
    ...     (1+0j,), frozenset({1}), 'dwa', 2,
    ...     frozenset({1+0j}), (1,), 'DWA', memoryview(b'dwa'),
    ... ]
    >>> it = iter_altered(some_list,
    ...                   without_items=iter(['DWA', 3+0j, b'dwa', 5, 123456789, (1.0,)]))
    >>> next(it)
    'dwa'
    >>> next(it)
    1
    >>> list(it)
    [frozenset({1}), 'dwa', 2, frozenset({(1+0j)})]

    >>> it = iter_altered(some_list,
    ...                   without_items=iter(['DWA', 3+0j, b'dwa', 5, 123456789, (1.0,)]),
    ...                   extra_items=iter((5, [4], 3, (2,), [4.0], 3.0, (2,), (1.0,))))
    >>> next(it)  # (objects in `extra_items` can be equal to some objects in `without_items`)
    5
    >>> next(it)  # (objects in `extra_items` do not need to be hashable)
    [4]
    >>> list(it)  # (keeping `extra_items`'s order and duplicates, like `collection_of_objects`'s)
    [3, (2,), [4.0], 3.0, (2,), (1.0,), 'dwa', 1, frozenset({1}), 'dwa', 2, frozenset({(1+0j)})]

    >>> list(iter_altered(abracadabra,                         # doctest: +IGNORE_EXCEPTION_DETAIL
    ...                   without_items=['b', [None]]))  # <- unhashable object present...
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> list(iter_altered([                                    # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     1, [1], [1.0], {},  # <- unhashable objects present...
    ... ], without_items=(1, 2)))
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    without = frozenset(without_items)
    extra = iter(extra_items)  # Note: only first `yield from extra` will yield anything.
    for obj in collection_of_objects:
        if obj in without:
            yield from extra
        else:
            yield obj
    yield from extra


def iter_grouped_by_attr(collection_of_objects: Iterable[T],
                         attr_name: str,
                         *,
                         presort: bool = False,

                         # not real parameters, just quasi-constants for faster access:
                         _attrgetter=operator.attrgetter,
                         _groupby=itertools.groupby,
                         _list=list,
                         _sorted=sorted) -> Iterator[list[T]]:
    """
    For an iterable of objects given as the first argument
    (`collection_of_objects`) and attribute name specified as the second
    argument (`attr_name`), return an iterator which yields lists that
    group adjacent objects having equal values of the designated
    attribute.

    All objects the given collection contains are expected to have the
    designated attribute. `AttributeError` will be raised if an object
    without that attribute is encountered.

    By default, the collection is processed in a "lazy" manner (it may be
    especially important if it is, for example, a generator that yields
    a huge number of objects).

    However, if the optional keyword-only argument `presort` is true
    (its default value is `False`) then, in the first place, the given
    collection of objects is consumed to construct a list of those
    objects, **sorted by the designated attribute**, and only then the
    main part of the operation is performed -- using that sorted list as
    the source collection.

    >>> a = PlainNamespace(pi=3.14, tau='spam')
    >>> b = PlainNamespace(pi=3.14, tau='ni', mu=None)
    >>> c = collections.namedtuple('TimTheEnchanter', ['pi', 'tau', 'mu'])(pi=3, tau='ni', mu=3.14)
    >>> class d:
    ...     pi = 3
    ...     tau = 'spam'
    ...     mu = 3.14
    ...
    >>> assert a != b and a != c and a !=d and b != c and b != d and c != d, (
    ...     'Failure of this assertion might mean '
    ...     'incorrectness of the following doctests.')

    >>> grouped = iter_grouped_by_attr([a, b, c, d], 'pi')
    >>> list(grouped) == [[a, b], [c, d]]
    True
    >>> grouped = iter_grouped_by_attr([a, b, c, d], 'pi', presort=True)
    >>> list(grouped) == [[c, d], [a, b]]
    True

    >>> grouped = iter_grouped_by_attr([a, b, c, d], 'tau')
    >>> list(grouped) == [[a], [b, c], [d]]
    True
    >>> grouped = iter_grouped_by_attr([a, b, c, d], 'tau', presort=True)
    >>> list(grouped) == [[b, c], [a, d]]
    True

    >>> grouped = iter_grouped_by_attr([a, c, b, d, c, a], 'pi')
    >>> list(grouped) == [[a], [c], [b], [d, c], [a]]
    True
    >>> grouped = iter_grouped_by_attr([a, c, b, d, c, a], 'pi', presort=True)
    >>> list(grouped) == [[c, d, c], [a, b, a]]
    True

    >>> grouped = iter_grouped_by_attr([a, c, b, d, c, a], 'tau')
    >>> list(grouped) == [[a], [c, b], [d], [c], [a]]
    True
    >>> grouped = iter_grouped_by_attr([a, c, b, d, c, a], 'tau', presort=True)
    >>> list(grouped) == [[c, b, c], [a, d, a]]
    True

    >>> grouped = iter_grouped_by_attr([d, c, a, d, d, c, b], 'pi')
    >>> list(grouped) == [[d, c], [a], [d, d, c], [b]]
    True
    >>> grouped = iter_grouped_by_attr([d, c, a, d, d, c, b], 'pi', presort=True)
    >>> list(grouped) == [[d, c, d, d, c], [a, b]]
    True

    >>> grouped = iter_grouped_by_attr([d, c, a, d, d, c, b], 'tau')
    >>> list(grouped) == [[d], [c], [a, d, d], [c, b]]
    True
    >>> grouped = iter_grouped_by_attr([d, c, a, d, d, c, b], 'tau', presort=True)
    >>> list(grouped) == [[c, c, b], [d, a, d, d]]
    True

    >>> grouped = iter_grouped_by_attr([d, c, b], 'tau')
    >>> next(grouped) == [d]
    True
    >>> next(grouped) == [c, b]
    True
    >>> next(grouped)  # just end of iteration (not an error)   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    StopIteration: ...

    >>> grouped = iter_grouped_by_attr([d, c, b], 'tau', presort=True)
    >>> next(grouped) == [c, b]
    True
    >>> next(grouped) == [d]
    True
    >>> next(grouped)  # just end of iteration (not an error)   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    StopIteration: ...

    >>> grouped = iter_grouped_by_attr([d, c, b], 'mu')
    >>> next(grouped) == [d, c]
    True
    >>> next(grouped) == [b]
    True
    >>> next(grouped)  # just end of iteration (not an error)   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    StopIteration: ...

    >>> grouped = iter_grouped_by_attr([d, c, b], 'mu', presort=True)
    >>> next(grouped)   # 3.14 and None cannot be ordered       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> grouped = iter_grouped_by_attr([d, c, b, a], 'mu')
    >>> next(grouped) == [d, c]
    True
    >>> next(grouped)   # `a` does not have `mu`                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    AttributeError: ...

    >>> grouped = iter_grouped_by_attr([d, c, b, a], 'mu', presort=True)
    >>> next(grouped)   # `a` does not have `mu`                # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    AttributeError: ...
    """
    key = _attrgetter(attr_name)
    if presort:
        collection_of_objects = _sorted(collection_of_objects, key=key)
    for _, grouped_items in _groupby(collection_of_objects, key):
        yield _list(grouped_items)


def open_file(file, mode='r', **open_kwargs):
    """
    Open `file` and return a corresponding file object. Similar to
    the built-in function `open()` but with the *additional feature*
    described below.

    Args/kwargs:
        `file`:
            Typically it is a string specifying the name (path) of the
            file to be opened. For more information, see the docs of the
            built-in function `open()`.
        `mode` (default: `'r'`):
            An optional string that specifies the mode in which the file
            is opened. If it contains `'b'` then it will be a binary mode;
            otherwise -- a text mode. For more information, see the docs
            of the built-in function `open()`.
        Other optional arguments, only as *keyword* (named) ones:
            See the docs of the built-in function `open()`.
            *Additional feature:* if `mode` does *not* contain the `'b'`
            marker (i.e., if the file is being opened in a text mode)
            *and* keyword arguments do *not* include `encoding` then the
            `encoding` argument is automatically set to `'utf-8'`;
            see: https://www.python.org/dev/peps/pep-0597/ and
            https://docs.python.org/3.10/library/io.html#text-encoding

    Returns:
        A file object (for details, see the docs of the built-in
        function `open()`).

    Raises:
        See the docs of the built-in function `open()`.
    """
    if 'b' not in mode:
        open_kwargs.setdefault('encoding', 'utf-8')
    return open(file, mode, **open_kwargs)


def read_file(file, mode='r', **open_kwargs):
    """
    Open `file` using the `open_file()` helper, then read the file's
    content (using the `read()` method) and return it.

    Args/kwargs:
        See the docstring of the `open_file()` helper.

    Returns:
        The file's content (`str` or `bytes`, depending on `mode` --
        see the docs of the `open()` built-in function).

    Raises:
        See the docs of the built-in function `open()` and of the
        Python's standard library module `io`.
    """
    with open_file(file, mode, **open_kwargs) as f:
        return f.read()


def make_hex_id(length=96, additional_salt=b''):
    """
    Make a random, unpredictable id consisting of hexadecimal digits.

    Args/kwargs:
        `length` (int; default: 96):
            The number of hexadecimal digits the generated id shall
            consist of.  Must not be less than 1 or greater than 96 --
            or ValueError will be raised.
        `additional_salt` (default: b''):
            Additional bytes to be mixed in when generating the id.
            Hardly needed but it does not hurt to specify it. :)

    Returns:
        A `str` consisting of `length` hexadecimal lowercase digits.

    Raises:
        ValueError -- if `length` is lesser than 1 or greater than 96.
        TypeError -- if `additional_salt` is of a type that cannot be
        converted to bytes with the `as_bytes()` helper function.

    >>> import string; is_hex = set(string.hexdigits.lower()).issuperset
    >>> h = make_hex_id()
    >>> isinstance(h, str) and is_hex(h) and len(h) == 96
    True
    >>> h = make_hex_id(additional_salt=b'some salt')
    >>> isinstance(h, str) and is_hex(h) and len(h) == 96
    True
    >>> h = make_hex_id(additional_salt=bytearray(b'some salt'))
    >>> isinstance(h, str) and is_hex(h) and len(h) == 96
    True
    >>> h = make_hex_id(additional_salt='some salt')
    >>> isinstance(h, str) and is_hex(h) and len(h) == 96
    True
    >>> h = make_hex_id(96)
    >>> isinstance(h, str) and is_hex(h) and len(h) == 96
    True
    >>> h = make_hex_id(1, additional_salt='some other salt')
    >>> isinstance(h, str) and is_hex(h) and len(h) == 1
    True
    >>> h = make_hex_id(length=40)
    >>> isinstance(h, str) and is_hex(h) and len(h) == 40
    True

    >>> make_hex_id(0)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> make_hex_id(97)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> make_hex_id(additional_salt=42)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    if not 1 <= length <= 96:
        raise ValueError(
            '`length` must be in the range 1..96 ({0!a} given)'.format(length))
    try:
        additional_salt = as_bytes(additional_salt)
    except TypeError:
        raise TypeError(
            '`additional_salt` cannot be converted to bytes (its '
            'type is {})'.format(type(additional_salt).__qualname__)) from None
    time_derived_bytes = '{:.24f}'.format(time.time()).encode('ascii')
    hash_base = os.urandom(40) + additional_salt + time_derived_bytes
    hex_id = hashlib.sha384(hash_base).hexdigest()[:length]
    return hex_id


def normalize_hex_id(hex_id, min_digit_num=0):
    """
    Normalize the given `hex_id` string (`str`) so that the result
    is a `str` instance, without the '0x prefix and at least
    `min_digit_num`-long (padded with zeroes if necessary;
    `min_digit_num` defaults to 0) and containing only
    lowercase hexadecimal digits.

    Examples:

    >>> normalize_hex_id('1')
    '1'
    >>> normalize_hex_id('10')
    '10'
    >>> normalize_hex_id('10aBc')
    '10abc'
    >>> normalize_hex_id('0x10aBc')
    '10abc'
    >>> normalize_hex_id('10aBc', 0)
    '10abc'
    >>> normalize_hex_id('10aBc', 4)
    '10abc'
    >>> normalize_hex_id('10aBc', 5)
    '10abc'
    >>> normalize_hex_id('10aBc', 6)
    '010abc'
    >>> normalize_hex_id('0x10aBc', 6)
    '010abc'
    >>> normalize_hex_id('12A4E415E1E1B36FF883D1')
    '12a4e415e1e1b36ff883d1'
    >>> normalize_hex_id('12A4E415E1E1B36FF883D1', 30)
    '0000000012a4e415e1e1b36ff883d1'
    >>> normalize_hex_id('0x12A4E415E1E1B36FF883D1', 30)
    '0000000012a4e415e1e1b36ff883d1'
    >>> normalize_hex_id('')                                    # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...
    >>> normalize_hex_id(bytearray(b'1'))                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    >>> normalize_hex_id(1)                                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    if not isinstance(hex_id, str):
        raise TypeError('`hex_id` must be str, not {}'.format(type(hex_id).__qualname__))
    int_id = int(hex_id, 16)
    return int_id_to_hex(int_id, min_digit_num)


def int_id_to_hex(int_id, min_digit_num=0):
    """
    Convert the given `int_id` integer so that the result is a `str`
    instance, without the '0x prefix and at least `min_digit_num`-long
    (padded with zeroes if necessary; `min_digit_num` defaults to 0)
    and containing only lowercase hexadecimal digits.

    Examples:

    >>> int_id_to_hex(1)
    '1'
    >>> int_id_to_hex(31, 0)
    '1f'
    >>> int_id_to_hex(31, 1)
    '1f'
    >>> int_id_to_hex(31, 2)
    '1f'
    >>> int_id_to_hex(31, 3)
    '01f'
    >>> int_id_to_hex(31, 10)
    '000000001f'
    >>> int_id_to_hex(22539340290692258087863249)
    '12a4e415e1e1b36ff883d1'
    >>> int_id_to_hex(22539340290692258087863249, 30)
    '0000000012a4e415e1e1b36ff883d1'
    >>> int_id_to_hex('1')   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...
    """
    hex_id = hex(int_id)
    assert hex_id[:2] == '0x'
    # get it *without* the '0x' prefix
    hex_id = hex_id[2:]
    # pad with zeroes if necessary
    hex_id = hex_id.rjust(min_digit_num, '0')
    return hex_id


def make_exc_ascii_str(exc=None):
    r"""
    Generate an ASCII-only string representing the (given) exception.

    Args:
        `exc`:
            The given exception instance or a tuple whose length is not
            less than 2 and whose first two items are: the exception
            type and instance (value).  If not given or `None` it will
            be retrieved automatically with `sys.exc_info()`.

    Returns:
        A textual representation (coerced to be an ASCII-only `str`
        instance) of the exception (if given or successfully retrieved
        automatically), containing the name of its class (type) and,
        typically, also its normal `str()`-representation.  If `exc`
        was not given (or given as `None`) and auto-retrieval failed
        then the `'Unknown exception (if any)'` string is returned
        (obviously also being an ASCII-only `str` instance).

    >>> make_exc_ascii_str(RuntimeError('whoops!'))
    'RuntimeError: whoops!'

    >>> make_exc_ascii_str((RuntimeError, RuntimeError('whoops!')))
    'RuntimeError: whoops!'
    >>> make_exc_ascii_str((RuntimeError, RuntimeError('whoops!'), 'irrelevant stuff', 42, 'SPAM'))
    'RuntimeError: whoops!'
    >>> make_exc_ascii_str((RuntimeError, None))
    'RuntimeError'

    >>> make_exc_ascii_str(ValueError('Zażółć jaźń!\udccc'))
    'ValueError: Za\\u017c\\xf3\\u0142\\u0107 ja\\u017a\\u0144!\\udccc'

    >>> try:
    ...     raise RuntimeError('whoops!')
    ... except Exception:
    ...     exc_string = make_exc_ascii_str()
    ...
    >>> exc_string
    'RuntimeError: whoops!'

    >>> make_exc_ascii_str()
    'Unknown exception (if any)'
    """
    if exc is None or isinstance(exc, tuple):
        if exc is None:
            exc = sys.exc_info()[:2]
        assert isinstance(exc, tuple)
        exc_type, exc = exc[:2]
        if exc is None and exc_type is not None:
            try:
                # Note: to be consistent with standard error displays
                # we use the exc type's `__name__`, not `__qualname__`.
                return ascii_str(exc_type.__name__)
            except Exception:
                pass
    if exc is None:
        return 'Unknown exception (if any)'
    # Note: to be consistent with standard error displays
    # we use the exc type's `__name__`, not `__qualname__`.
    return '{}: {}'.format(ascii_str(type(exc).__name__), ascii_str(exc))


def make_condensed_debug_msg(exc_info=None,
                             total_limit=2000,
                             exc_str_limit=500,
                             tb_str_limit=1000,
                             stack_str_limit=None,
                             cut_indicator='[...]'):
    """
    Generate a one-line string containing condensed debug information,
    including: script basename, hostname, exception class, exception
    str() representation, condensed traceback info, condensed outer
    stack frames info.

    Args/kwargs:
        `exc_info` (default: None):
            None or a 3-tuple, as returned by sys.exc_info().  If None:
            sys.exc_info() will be called to obtain the exception
            information.

    Kwargs:
        `total_limit` (default: 2000):
            Maximum length of the resultant str.  If None: no limit.
        `exc_str_limit` (default: 500):
            Maximum length of the exception str() representation part of
            the resultant str.  If None: no limit.
        `tb_str_limit` (default: 1000):
            Maximum length of the traceback part of the resultant str.
            If None: no limit.
        `stack_str_limit` (default: None):
            Maximum length of the outer stack frames info part of the
            resultant str.  If None: no limit.
        `cut_indicator` (default: "[...]"):
            The string that will replace cut fragments.  It should be a
            pure ASCII str (if not it will be automatically converted to
            such a str).

    Returns:
        The resultant debug info (being a pure ASCII str).

    Raises:
        ValueError -- if any of the `*_limit` arguments is smaller than
        the length of the string specified as `cut_indicator`.
    """
    try:
        def format_entry(entry_tuple):
            filename, lineno, funcname, codequote = entry_tuple
            if not filename:
                filename = '<unknown file>'
            for useless_prefix_regex in USELESS_SRC_PATH_PREFIX_REGEXES:
                match = useless_prefix_regex.search(filename)
                if match:
                    filename = filename[match.end(0):]
                    break
            s = filename
            if lineno:
                s = '{0}#{1}'.format(s, lineno)
            if funcname and funcname != '<module>':
                s = '{0}/{1}()'.format(s, funcname)
            if codequote:
                s = '{0}:`{1}`'.format(s, codequote)
            return s

        def make_msg(obj, limit, middle_cut=True):
            if obj is None:
                return ''
            if isinstance(obj, type):  # (exception type)
                # Note: to be consistent with standard error displays
                # we use the exc type's `__name__`, not `__qualname__`.
                obj = obj.__name__
            s = ascii_str(obj).replace('\n', '\\n').replace('\r', '\\r')
            if limit is not None:
                s = limit_str(s, limit, cut_indicator, middle_cut)
            return s

        cut_indicator = ascii_str(cut_indicator)
        if exc_info is None:
            exc_info = sys.exc_info()
        exc_type, exc, tb = exc_info

        if tb is None:
            tb_formatted = None
            stack_entry_tuples = traceback.extract_stack()[:-1]
        else:
            tb_entry_tuples = traceback.extract_tb(tb)
            tb_formatted = ' <- '.join(map(
                format_entry,
                reversed(tb_entry_tuples)))
            stack_entry_tuples = traceback.extract_stack(tb.tb_frame)
        stack_formatted = ' <- '.join(map(
            format_entry,
            reversed(stack_entry_tuples)))

        full_msg = '[{0}@{1}] {2}: {3} <<= {4} <-(*)- {5}'.format(
            SCRIPT_BASENAME,
            HOSTNAME,
            make_msg(exc_type, 100) or '<no exc>',
            make_msg(exc, exc_str_limit) or '<no msg>',
            make_msg(tb_formatted, tb_str_limit) or '<no traceback>',
            make_msg(stack_formatted, stack_str_limit))
        return make_msg(full_msg, total_limit, middle_cut=False)

    finally:
        # (to break any traceback-related reference cycles)
        exc_info = exc_type = exc = tb = None


_dump_condensed_debug_msg_lock = threading.RLock()

def _try_to_release_dump_condensed_debug_msg_lock(
            # this object is intended to be accessible even when this
            # module is in a weird state on interpreter exit...
            _release_lock=_dump_condensed_debug_msg_lock.release):
    try:
        _release_lock()
    except RuntimeError:
        # *either* already unlocked *or* owned+locked by another thread
        pass

def dump_condensed_debug_msg(header=None, stream=None, debug_msg=None,
                             # these objects are intended to be accessible even when
                             # this module is in a weird state on interpreter exit...
                             _acquire_lock=_dump_condensed_debug_msg_lock.acquire,
                             _try_to_release_lock=_try_to_release_dump_condensed_debug_msg_lock):
    """
    Call `make_condensed_debug_msg(total_limit=None, exc_str_limit=1000,
    tb_str_limit=None, stack_str_limit=None)` and print the resultant
    debug message (adding to it an appropriate caption, containing
    current thread's identifier and name, and optionally preceding it
    with the specified `header`) to the standard error output or to the
    specified `stream`.

    If `debug_msg` is given (as a non-`None` value) then the
    `make_condensed_debug_msg(...)` call is not made but, instead of
    its result, the given value is used.

    This function is thread-safe (guarded with an RLock).

    Args/kwargs:
        `header` (default: `None`):
            Optional header -- to be printed above the actual debug
            information.
        `stream` (default: None):
            The stream the debug message is to be printed to.  If `None`
            the message will be printed to the standard error output.
        `debug_msg` (default: None):
            Typically it is left as `None`.  In some cases, however, it
            may be appropriate to specify it (e.g., if the client code
            has already called `make_condensed_debug_msg(...)`, so
            another call would be redundant).
    """
    try:
        _acquire_lock()
        try:
            header = (
                '\n{}\n'.format(ascii_str(header)) if header is not None
                else '')
            if stream is None:
                stream = sys.stderr
            if debug_msg is None:
                debug_msg = make_condensed_debug_msg(
                    total_limit=None,
                    exc_str_limit=1000,
                    tb_str_limit=None,
                    stack_str_limit=None)
            cur_thread = threading.current_thread()
            print(
                '{0}\nCONDENSED DEBUG INFO: [thread {1!r} (#{2})] {3}\n'.format(
                    header,
                    ascii_str(cur_thread.name),
                    cur_thread.ident,
                    debug_msg),
                file=stream)
            try:
                stream.flush()
            except Exception:
                pass
        finally:
            _try_to_release_lock()
    except:
        # The purpose of the following call is to reduce probability of
        # deadlocks in a rare case when the normal lock release (above)
        # has been omitted (because of some asynchronous exception, such
        # as a KeyboardInterrupt raised by a signal handler, in an
        # unfortunate moment...). (Note that an attempt to release
        # an `RLock` which is not owned by the current thread causes
        # `RuntimeError` without releasing the lock, so there is no fear
        # that we could prematurely unlock the lock when it is owned by
        # another thread.)
        _try_to_release_lock()
        raise


class AtomicallySavedFile:

    """
    A context manager that saves a file atomically (the file will
    *either* be saved successfully *or* remain untouched).

    It takes the target file path and mode as arguments,
    creates a temporary file in the same directory as the target file;
    returns the opened temporary file.
    Finally, the context manager closes the temporary file and then
    renames it to the name of the target file (overwriting the latter
    atomically) if no exception occurred. Otherwise, it removes the
    temporary file (without touching the target file) and re-raises
    the exception.

    *Additional feature:* if `mode` does *not* contain the 'b' marker
    (i.e., if the file is being opened in a text mode) *and* keyword
    arguments do *not* include `encoding` then the `encoding` argument
    is automatically set to 'utf-8'.
    """

    def __init__(self, dest_path, mode, **kwargs):
        if 'w' not in mode and 'x' not in mode:
            # Maybe TODO: we may want to support also 'a' and 'r+...' (but it
            #             would require careful modification of implementation
            #             of `__enter__()` and `__exit__()`...).
            raise ValueError('mode {!a} not supported'.format(mode))
        kwargs = self._adjust_kwargs(mode, **kwargs)
        self._dest_path = os.fspath(dest_path)
        self._mode = mode
        self._kwargs = kwargs

    __NOT_GIVEN = object()

    def _adjust_kwargs(self,
                       mode,
                       buffering=__NOT_GIVEN,
                       encoding=__NOT_GIVEN,
                       errors=__NOT_GIVEN,
                       newline=__NOT_GIVEN):
        NOT_GIVEN = self.__NOT_GIVEN
        if 'b' not in mode and encoding is NOT_GIVEN:
            encoding = 'utf-8'
        kwargs = {}
        if buffering is not NOT_GIVEN:
            kwargs['buffering'] = buffering
        if encoding is not NOT_GIVEN:
            kwargs['encoding'] = encoding
        if errors is not NOT_GIVEN:
            kwargs['errors'] = errors
        if newline is not NOT_GIVEN:
            kwargs['newline'] = newline
        return kwargs

    def __enter__(self):
        self.tmp_file = tempfile.NamedTemporaryFile(
            mode=self._mode,
            dir=osp.dirname(self._dest_path),
            delete=False,
            **self._kwargs)
        self.tmp_file_path = self.tmp_file.name
        return self.tmp_file

    def __exit__(self, exc_type, exc_value, exc_traceback):
        from n6lib.log_helpers import get_logger
        LOGGER = get_logger(__name__)

        self.tmp_file.close()
        if exc_type is not None:
            LOGGER.warning("Exception occurred when trying to save the %a file atomically "
                           "(so the file is not touched): %s.",
                           self._dest_path, make_exc_ascii_str((exc_type, exc_value)))
            os.unlink(self.tmp_file_path)
        else:
            os.rename(self.tmp_file_path, self._dest_path)


if __name__ == '__main__':
    from n6lib.unit_test_helpers import run_module_doctests
    run_module_doctests()

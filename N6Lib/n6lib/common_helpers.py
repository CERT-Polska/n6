# Copyright (c) 2013-2021 NASK. All rights reserved.
#
# For some code in this module:
# Copyright (c) 2001-2013 Python Software Foundation. All rights reserved.
# (For more information -- see the docstrings below...)

import abc
import collections
import collections.abc as collections_abc
import copy
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
from importlib import import_module
from threading import get_ident as get_current_thread_ident
from typing import (
    Iterable,
    Iterator,
    List,
)

from pkg_resources import cleanup_resources
from pyramid.decorator import reify

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
    as_unicode,
    str_to_bool,
    try_to_normalize_surrogate_pairs_to_proper_codepoints,
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
from n6lib.class_helpers import properly_negate_eq
from n6lib.const import (
    HOSTNAME,
    SCRIPT_BASENAME,
)
from n6lib.typing_helpers import (
    String as Str,
    T,
)


# more restrictive than actual e-mail address syntax but sensible in most cases
EMAIL_OVERRESTRICTED_SIMPLE_REGEX = re.compile(r'''
        \A
        (?P<local>
            (?!          # local part cannot start with dot
                \.
            )
            (
                         # see: http://en.wikipedia.org/wiki/Email_address#Local_part
                [\-0-9a-zA-Z!#$%&'*+/=?^_`{{|}}~]
            |
                \.
                (?!
                    \.   # local part cannot contain two or more non-separated dots
                )
            )+
            (?<!         # local part cannot end with dot
                \.
            )
        )
        @
        (?P<domain>
            {domain}
        )
        \Z
    '''.format(
        domain=DOMAIN_ASCII_LOWERCASE_STRICT_REGEX.pattern.lstrip('A\\ \r\n').rstrip('Z\\ \r\n'),
    ), re.ASCII | re.VERBOSE)

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


class RsyncFileContextManager(object):

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


class PlainNamespace(object):

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
        super(ThreadLocalNamespace, self).__init__(**attrs)

    def __repr__(self):
        namespace = self.__dict__
        items = ("{}={!r}".format(k, namespace[k])
                 for k in sorted(namespace))
        return '<{} object as visible from thread {!r}: {}>'.format(
            type(self).__qualname__,
            threading.current_thread(),
            ', '.join(items))


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


class FilePagedSequence(collections_abc.MutableSequence):

    """
    A mutable sequence that reduces memory usage by keeping data as files.

    Under the hood, the sequence is "paged" -- only the current page
    (consisting of a defined number of items) is kept in memory; other
    pages are pickled and saved as temporary files.

    The interface is similar to the built-in list's one, except that:

    * slices are not supported;
    * del, remove(), insert(), reverse() and sort() are not supported;
    * pop() supports only popping the last item -- and works only if the
      argument is specified as -1 or not specified at all;
    * index() accepts only one argument (does not accept the `start` and
      `stop` range limiting arguments);
    * all sequence items must be picklable;
    * the constructor accepts an additional argument: `page_size` --
      being the number of items each page may consist of (its default
      value is 1000);
    * there are additional methods:
      * clear() -- use it instead of `del seq[:]`;
      * close() -- you should call it when you no longer use the sequence
        (it clears the sequence and removes all temporary files);
      * a context-manager (`with`-statement) interface:
        * its __enter__() returns the instance;
        * its __exit__() calls the close() method.

    Unsupported actions raise NotImplementedError.

    Unpicklable items must *not* be used -- consequences of using them are
    undefined (i.e., apart from an exception being raised, the sequence may
    be left in a defective, inconsistent state).

    Temporary directory and files are created lazily -- no disk operations
    are performed at all if all data fit on one page.

    The implementation is *not* thread-safe.

    >>> list(FilePagedSequence())
    []
    >>> list(FilePagedSequence(page_size=3))
    []
    >>> len(FilePagedSequence(page_size=3))
    0
    >>> bool(FilePagedSequence(page_size=3))
    False

    >>> seq = FilePagedSequence([1, 'foo', {'a': None}, ['b']], page_size=3)
    >>> len(seq)
    4
    >>> bool(seq)
    True
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
    >>> len(seq)
    5
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b'], 42.0]

    >>> seq.pop()
    42.0
    >>> len(seq)
    4
    >>> list(seq)
    [1, 'foo', {'a': None}, ['b']]

    >>> seq.pop(-1)
    ['b']
    >>> seq.pop()
    {'a': None}
    >>> list(seq)
    [1, 'foo']
    >>> len(seq)
    2

    >>> seq.append(430)
    >>> seq.append(440)
    >>> seq.append(450)
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
    >>> list(seq)
    []
    >>> len(seq)
    0
    >>> seq.pop()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError

    >>> seq.extend([1, 'foo', {'a': None}, ['b']])
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

    >>> seq.append(43)
    >>> seq.append(44)
    >>> seq.append(45)
    >>> list(seq)
    [1, 'foo', 43, 44, 45]

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
    [1, 'foo', 43, 44, 45, 46, 47]

    >>> seq.pop()
    47
    >>> seq[5]
    46
    >>> list(seq)
    [1, 'foo', 43, 44, 45, 46]

    >>> seq.append(47)
    >>> seq[-1]
    47
    >>> list(seq)
    [1, 'foo', 43, 44, 45, 46, 47]

    >>> seq.pop()
    47
    >>> seq[-1]
    46
    >>> list(seq)
    [1, 'foo', 43, 44, 45, 46]

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
    [45, 44, 43, 'foo', 1]
    >>> seq[5]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[6]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[7]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[8]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError

    >>> seq[-5]
    1
    >>> list(seq)
    [1, 'foo', 43, 44, 45]
    >>> seq[-6]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[0]
    1
    >>> seq[-7]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[-8]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError
    >>> seq[-9]  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    IndexError

    >>> osp.exists(seq._dir)
    True
    >>> sorted(os.listdir(seq._dir))
    ['0', '1', '2']
    >>> seq.close()
    >>> list(seq)
    []
    >>> osp.exists(seq._dir)
    False

    >>> seq2 = FilePagedSequence('abc', page_size=3)
    >>> list(seq2)
    ['a', 'b', 'c']
    >>> seq2._filesystem_used()   # all items in current page -> no disk op.
    False
    >>> seq2.extend('d')          # (now page 0 must be saved)
    >>> seq2._filesystem_used()
    True
    >>> osp.exists(seq2._dir)
    True
    >>> sorted(os.listdir(seq2._dir))
    ['0']
    >>> seq2.extend('ef')
    >>> sorted(os.listdir(seq2._dir))
    ['0']
    >>> seq2.extend('g')          # (now page 1 must be saved)
    >>> sorted(os.listdir(seq2._dir))
    ['0', '1']
    >>> seq2[0]                   # (now page 2 must be saved)
    'a'
    >>> sorted(os.listdir(seq2._dir))
    ['0', '1', '2']
    >>> seq2.pop()
    'g'
    >>> sorted(os.listdir(seq2._dir))
    ['0', '1', '2']
    >>> seq2.clear()
    >>> sorted(os.listdir(seq2._dir))
    ['0', '1', '2']
    >>> seq2.close()
    >>> seq2._filesystem_used()
    True
    >>> osp.exists(seq2._dir)
    False
    >>> list(seq2)
    []

    >>> seq3 = FilePagedSequence(page_size=3)
    >>> seq3._filesystem_used()
    False
    >>> seq3.close()
    >>> seq3._filesystem_used()
    False

    >>> with FilePagedSequence(page_size=3) as seq4:
    ...     not seq4._filesystem_used()
    ...     seq4.append(('foo', 1))
    ...     list(seq4) == [('foo', 1)]
    ...     seq4[0] = 'bar', 2
    ...     seq4[0] == ('bar', 2)
    ...     list(seq4) == [('bar', 2)]
    ...     seq4.append({'x'})
    ...     seq4.append({'z': 3})
    ...     list(seq4) == [('bar', 2), {'x'}, {'z': 3}]
    ...     not seq4._filesystem_used()
    ...     seq4.append(['d'])
    ...     seq4._filesystem_used()
    ...     osp.exists(seq4._dir)
    ...     sorted(os.listdir(seq4._dir)) == ['0']
    ...     seq4[2] = {'ZZZ': 333}
    ...     sorted(os.listdir(seq4._dir)) == ['0', '1']
    ...     list(seq4) == [('bar', 2), {'x'}, {'ZZZ': 333}, ['d']]
    ...     osp.exists(seq4._dir)
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
    >>> osp.exists(seq4._dir)
    False
    """

    def __init__(self, iterable=(), page_size=1000):
        self._page_size = page_size
        self._cur_len = 0
        self._cur_page_no = None
        self._cur_page_data = []
        self._closed = False
        self.extend(iterable)

    def __len__(self):
        return self._cur_len

    def __getitem__(self, index):
        local_index = self._local_index(index)
        return self._cur_page_data[local_index]

    def __setitem__(self, index, value):
        local_index = self._local_index(index)
        self._cur_page_data[local_index] = value

    def __reversed__(self):
        for i in range(len(self) - 1, -1, -1):
            yield self[i]

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.close()

    def clear(self):
        self._cur_page_data = []
        self._cur_page_no = None
        self._cur_len = 0

    def close(self):
        if not self._closed:
            self.clear()
            if self._filesystem_used():
                for filename in os.listdir(self._dir):
                    os.remove(osp.join(self._dir, filename))
                os.rmdir(self._dir)
            self._closed = True

    #
    # Non-public stuff

    @reify
    def _dir(self):
        return tempfile.mkdtemp(prefix='n6-FilePagedSequence-tmp')

    def _filesystem_used(self):
        return '_dir' in self.__dict__

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
            raise IndexError

    def _switch_to(self, page_no, new=False):
        if self._cur_page_no is not None:
            # save the current page
            with open(self._get_page_filename(self._cur_page_no), 'wb') as f:
                pickle.dump(self._cur_page_data, f, -1)
        if new:
            # initialize a new page...
            self._cur_page_data = []
        else:
            # load an existing page...
            with open(self._get_page_filename(page_no), 'rb') as f:
                self._cur_page_data = pickle.load(f)
        # ...and set it as the current one
        self._cur_page_no = page_no

    def _get_page_filename(self, page_no):
        return osp.join(self._dir, str(page_no))

    #
    # Unittest helper (to test a code that makes use of instances of the class)

    @staticmethod
    def _instance_mock():
        from unittest.mock import create_autospec

        NOT_IMPLEMENTED_METHODS = (
            '__delitem__', 'remove', 'insert', 'reverse', 'sort')

        GENERIC_LIST_METHODS = (
            '__iter__', '__len__', '__contains__', '__reversed__',
            'index', 'count', 'append', 'extend', '__iadd__')

        #
        # implementation of method side effects

        li = []

        def make_list_method_side_effect(meth):
            meth_obj = getattr(li, meth)
            def side_effect(*args, **kwargs):
                return meth_obj(*args, **kwargs)
            side_effect.__name__ = meth
            side_effect.__qualname__ = '{}.{}'.format(FilePagedSequence.__name__, meth)
            return side_effect

        def getitem_side_effect(index):
            if isinstance(index, slice):
                raise NotImplementedError
            return li[index]

        def setitem_side_effect(index, value):
            if isinstance(index, slice):
                raise NotImplementedError
            li[index] = value

        def pop_side_effect(index=-1):
            if index != -1:
                raise NotImplementedError
            return li.pop(index)

        def clear_side_effect():
            del li[:]

        close_side_effect = itertools.chain(
            [clear_side_effect],
            itertools.repeat(lambda: None))

        def enter_side_effect():
            return FilePagedSequence.__enter__(m)

        def exit_side_effect(*args):
            return FilePagedSequence.__exit__(m, *args)

        #
        # configuring the actual mock

        m = create_autospec(FilePagedSequence)()

        # for some mysterious reason (a bug in the mock
        # library?) __reversed__ must be set explicitly
        m.__reversed__ = create_autospec(FilePagedSequence.__reversed__)

        for meth in NOT_IMPLEMENTED_METHODS:
            getattr(m, meth).side_effect = NotImplementedError

        for meth in GENERIC_LIST_METHODS:
            getattr(m, meth).side_effect = make_list_method_side_effect(meth)

        m.__getitem__.side_effect = getitem_side_effect
        m.__setitem__.side_effect = setitem_side_effect
        m.pop.side_effect = pop_side_effect
        m.clear.side_effect = clear_side_effect
        m.close.side_effect = close_side_effect
        m.__enter__.side_effect = enter_side_effect
        m.__exit__.side_effect = exit_side_effect

        m._list = li  # (for introspection in unit tests)
        return m


class DictWithSomeHooks(dict):

    """
    A convenient base for some kinds of dict subclasses.

    * It is a real subclass of the built-in `dict` type (contrary to
      some of the other mapping classes defined in this module).

    * You can extend/override the _custom_key_error() instance method in
      your subclasses to customize exceptions raised by
      __getitem__()/__delitem__()/ pop()/popitem() methods.  The
      _custom_key_error() method should take two positional arguments:
      the originally raised KeyError instance and the name of the method
      ('__getitem__' or '__delitem__, or 'pop', or 'popitem'); for
      details, see the standard implementation of _custom_key_error().

    * The class provides a ready-to-use and recursion-proof __repr__()
      -- you can easily customize it by extending/overriding the
      _constructor_args_repr() method in your subclasses (see the
      example below); another option is, of course, to override
      __repr__() completely.

    * The __ne__ () method (the `!=` operator) is already -- for your
      convenience -- implemented as negation of __eq__() (`==`) --
      so if you need, in your subclass, to reimplement/extend the
      equality/inequality operations, typically, you will need
      to override/extend only the __eq__() method.

    * Important: you should not replace the __init__() method completely
      in your subclasses -- but only extend it (e.g., using super()).

    * Your custom __init__() can take any arguments, i.e., its signature
      does not need to be compatible with standard dict's __init__()
      (see the example below).

    * Instances of the class support copying: both shallow copying (do
      it by calling the copy() method or the copy() function from the
      `copy` module) and deep copying (do it by calling the deepcopy()
      function from the `copy` module) -- including copying instance
      attributes and including support for recursive mappings.

      Please note, however, that those copying operations are supposed
      to work properly only if the items() and update() methods work
      as expected for an ordinary dict -- i.e., that items() provides
      `(<hashable key>, <corresponding value>)` pairs (one for each item
      of the mapping) and that update() is able to "consume" an input
      data object being an iterable of such pairs; the order of items
      is preserved *only if* those two methods preserve it.

    >>> class MyUselessDict(DictWithSomeHooks):
    ...
    ...     def __init__(self, a, b, c=42):
    ...         super(MyUselessDict, self).__init__(b=b)
    ...         self.a = a
    ...         self.c = self['c'] = c
    ...
    ...     # examples of implementation of the two customization hooks:
    ...
    ...     def _constructor_args_repr(self):
    ...         return '<' + repr(sorted(self.items(), key=repr)) + '>'
    ...
    ...     def _custom_key_error(self, key_error, method_name):
    ...         e = super(MyUselessDict, self)._custom_key_error(
    ...                 key_error, method_name)
    ...         return ValueError(*(e.args + (method_name,)))
    ...
    >>> d = MyUselessDict(['A'], {'B': 'BB'})
    >>> isinstance(d, dict) and isinstance(d, MyUselessDict)
    True
    >>> d
    MyUselessDict(<[('b', {'B': 'BB'}), ('c', 42)]>)
    >>> d == {'b': {'B': 'BB'}, 'c': 42}
    True
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
    MyUselessDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
    >>> d.a
    ['A']
    >>> d.c
    42

    >>> d._repr_recur_thread_ids.add('xyz')
    >>> vars(d) == {'a': ['A'], 'c': 42, '_repr_recur_thread_ids': {'xyz'}}
    True

    >>> d_shallowcopy = d.copy()  # the same as copy.copy(d)
    >>> d_shallowcopy
    MyUselessDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
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
    MyUselessDict(<[('a', ['A']), ('b', {'B': 'BB'})]>)
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

    >>> class RecurKey(object):
    ...     def __repr__(self): return '$$$'
    ...     def __hash__(self): return 42
    ...     def __eq__(self, other): return isinstance(other, RecurKey)
    ...     def __ne__(self, other): return not (self == other)
    ...
    >>> recur_key = RecurKey()
    >>> recur_d = copy.deepcopy(d)
    >>> recur_d._repr_recur_thread_ids.add('xyz')
    >>> vars(recur_d) == {'a': ['A'], 'c': 42, '_repr_recur_thread_ids': {'xyz'}}
    True
    >>> recur_d[recur_key] = recur_d
    >>> recur_d['b'] = recur_d.b = recur_d
    >>> recur_d
    MyUselessDict(<[($$$, MyUselessDict(<...>)), ('a', ['A']), ('b', MyUselessDict(<...>))]>)

    >>> recur_d_deepcopy = copy.deepcopy(recur_d)
    >>> recur_d_deepcopy
    MyUselessDict(<[($$$, MyUselessDict(<...>)), ('a', ['A']), ('b', MyUselessDict(<...>))]>)
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
    >>> (recur_d._repr_recur_thread_ids == set({'xyz'}) and
    ...  recur_d_deepcopy._repr_recur_thread_ids == set())
    True

    >>> recur_d_shallowcopy = copy.copy(recur_d)
    >>> recur_d_shallowcopy                               # doctest: +ELLIPSIS
    MyUselessDict(<[($$$, MyUselessDict(<[($$$, MyUselessDict(<...>)), ('a', ...

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
    >>> (recur_d._repr_recur_thread_ids == set({'xyz'}) and
    ...  recur_d_shallowcopy._repr_recur_thread_ids == set())
    True

    >>> sorted([d.popitem(), d.popitem()])
    [('a', ['A']), ('b', {'B': 'BB'})]
    >>> d
    MyUselessDict(<[]>)
    >>> d == {}
    True
    >>> bool(d)
    False

    >>> d.popitem()
    Traceback (most recent call last):
      ...
    KeyError: 'popitem(): dictionary is empty'

    >>> class AnotherWeirdSubclass(DictWithSomeHooks):
    ...     def __eq__(self, other):
    ...         return 'equal' in other
    ...
    >>> d2 = AnotherWeirdSubclass()
    >>> d2 == {}
    False
    >>> d2 != {}
    True
    >>> d2 == ['equal']
    True
    >>> d2 != ['equal']
    False
    """

    def __init__(self, /, *args, **kwargs):
        super(DictWithSomeHooks, self).__init__(*args, **kwargs)
        self._repr_recur_thread_ids = set()

    @classmethod
    def fromkeys(cls, *args, **kwargs):
        raise NotImplementedError(
            'the fromkeys() class method is not implemented '
            'for the {.__qualname__} class', cls)

    def __repr__(self):
        repr_recur_thread_ids = self._repr_recur_thread_ids
        cur_thread_id = get_current_thread_ident()
        if cur_thread_id in self._repr_recur_thread_ids:
            # recursion detected
            constructor_args_repr = '<...>'
        else:
            try:
                repr_recur_thread_ids.add(cur_thread_id)
                constructor_args_repr = self._constructor_args_repr()
            finally:
                repr_recur_thread_ids.discard(cur_thread_id)
        return '{.__class__.__qualname__}({})'.format(self, constructor_args_repr)

    __ne__ = properly_negate_eq

    def __getitem__(self, key):
        try:
            return super(DictWithSomeHooks, self).__getitem__(key)
        except KeyError as key_error:
            raise self._custom_key_error(key_error, '__getitem__') from key_error

    def __delitem__(self, key):
        try:
            super(DictWithSomeHooks, self).__delitem__(key)
        except KeyError as key_error:
            raise self._custom_key_error(key_error, '__delitem__') from key_error

    def pop(self, *args):
        try:
            return super(DictWithSomeHooks, self).pop(*args)
        except KeyError as key_error:
            raise self._custom_key_error(key_error, 'pop') from key_error

    def popitem(self):
        try:
            return super(DictWithSomeHooks, self).popitem()
        except KeyError as key_error:
            raise self._custom_key_error(key_error, 'popitem') from key_error

    def copy(self):
        return copy.copy(self)

    def __copy__(self):
        cls = type(self)
        new = cls.__new__(cls)
        new._repr_recur_thread_ids = set()
        new.update(self.items())
        vars(new).update((k, v) for k, v in vars(self).items()
                         if k != '_repr_recur_thread_ids')
        return new

    def __deepcopy__(self, memo):
        cls = type(self)
        new = cls.__new__(cls)
        new._repr_recur_thread_ids = set()
        memo[id(self)] = new  # <- needed in case of a recursive mapping
        copied_items = copy.deepcopy(list(self.items()), memo)
        copied_attrs = copy.deepcopy(list(vars(self).items()), memo)
        new.update(copied_items)
        vars(new).update((k, v) for k, v in copied_attrs
                         if k != '_repr_recur_thread_ids')
        return new

    # the overridable/extendable hooks:

    def _constructor_args_repr(self):
        return repr(dict(self.items()))

    def _custom_key_error(self, key_error, method_name):
        if method_name == 'popitem':
            # for popitem() the standard behaviour is mostly the desired one
            raise
        return key_error


## TODO: doc + maybe more tests (now only the CIDict subclass is doc-tested...)
class NormalizedDict(collections_abc.MutableMapping):

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
        return super(NormalizedDict, self).__eq__(other)

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
        key = super(CIDict, self).normalize_key(key)
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
        super(LimitedDict, self).__init__(*args, **kwargs)

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
        s = super(LimitedDict, self).__repr__()
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
        super(LimitedDict, self).__setitem__(key, value)
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


class _CacheKey(object):

    def __init__(self, *args):
        self.args = args
        self.args_hash = hash(args)

    def __repr__(self):
        return '{0.__class__.__qualname__}{0.args!r}'.format(self)

    def __hash__(self):
        return self.args_hash

    def __eq__(self, other,
               _type=type):
        assert _type(other) == _type(self)
        return self.args == other.args


def memoized(func=None,
             expires_after=None,
             max_size=None,
             max_extra_time=30,
             time_func=time.time):
    """
    A simple in-memory-LRU-cache-providing call memoizing decorator.

    Args:
        `func`:
            The decorated function. Typically it is ommited to
            be bound later with the decorator syntax (see the
            examples below).

    Kwargs:
        `expires_after` (default: None):
            Time interval (in seconds) between caching a call
            result and its expiration. If set to None -- there
            is no time-based cache expiration.
        `max_size` (default: None):
            Maximum number of memoized results (formally, this is
            not a strict maximum: some extra cached results can be
            kept a bit longer -- until their keys' weak references
            are garbage-collected -- though it is hardly probable
            under CPython, and even then it would be practically
            harmless). If set to None -- there is no such limit.
        `max_extra_time` (default: 30):
            Maximum for a random number of seconds to be added to
            `expires_after` for a particular cached result. None
            means the same as 0: no extra time.
        `time_func` (default time.time()):
            A function used to determine current time: it should
            return a timestamp as an int or float number (one second
            is assumed to be the unit).

    Note: recursion is not supported (the decorated function raises
    RuntimeError when a recursive call occurs).

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
    >>> add(1, 2)
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

    >>> t = 0
    >>> pseudo_time = lambda: t
    >>> @memoized(expires_after=4, max_extra_time=None, time_func=pseudo_time)
    ... def sub(a, b):
    ...     print('calculating: {} - {} = ...'.format(a, b))
    ...     return a - b
    ...
    >>> sub(1, 2)
    calculating: 1 - 2 = ...
    -1

    >>> t = 1
    >>> sub(1, 2)
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
    >>> div(8, 2)
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
    The class of special marker keys in dicts returned by make_dict_delta().

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
        return super(DictDeltaKey, cls).__new__(cls, op, key_obj)

    def __eq__(self, other):
        if isinstance(other, DictDeltaKey):
            return super(DictDeltaKey, self).__eq__(other)
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
    (appropriately: DictDeltaKey('-', <key>) or DictDeltaKey('+', <key>)).

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
            if isinstance(src_mapping, collections_abc.Mapping)
            else src_mapping)
        for key, src_val in src_items:
            target_val = target_mapping.get(key)
            if isinstance(target_val, collections_abc.MutableMapping):
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
    ...     class class_C(object): z = 3
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
        `segment_index` (int)
            The number (0-indexed) of the segment to be replaced.
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
    segments[segment_index] = new_content
    return sep.join(segments)


def splitlines_asc(s, keepends=False):
    r"""
    Like the built-in `{str/bytes/bytearray}.splitlines()` method, but
    split only at ASCII line boundaries (`\n`, `\r\n`, `\r`), even if
    the argument is a `str` (whereas the standard `str.splitlines()`
    method does the splits also at some other line boundary characters,
    including `\v`, `\f`, `\u2028` and a few others...).

    **Note:** the argument need *not* to be ASCII-only.

    ***

    For `str`:

    >>> s = 'abc\ndef\rghi\vjkl\f\u2028mno\r\npqr\n'
    >>> splitlines_asc(s)
    ['abc', 'def', 'ghi\x0bjkl\x0c\u2028mno', 'pqr']
    >>> splitlines_asc(s, True)
    ['abc\n', 'def\r', 'ghi\x0bjkl\x0c\u2028mno\r\n', 'pqr\n']

    ...the results are *different* than when using the method:

    >>> s.splitlines()
    ['abc', 'def', 'ghi', 'jkl', '', 'mno', 'pqr']
    >>> s.splitlines(True)
    ['abc\n', 'def\r', 'ghi\x0b', 'jkl\x0c', '\u2028', 'mno\r\n', 'pqr\n']

    ***

    For `bytes`/`bytearray`:

    >>> b = b"abc\ndef\rghi\vjkl\fmno\r\npqr\n"
    >>> splitlines_asc(b)
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr']
    >>> splitlines_asc(b, True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n']
    >>> splitlines_asc(bytearray(b'ghi\vjkl\rspam'))
    [bytearray(b'ghi\x0bjkl'), bytearray(b'spam')]

    ...the results are *the same* as when using the method:

    >>> b.splitlines()
    [b'abc', b'def', b'ghi\x0bjkl\x0cmno', b'pqr']
    >>> b.splitlines(True)
    [b'abc\n', b'def\r', b'ghi\x0bjkl\x0cmno\r\n', b'pqr\n']
    >>> bytearray(b'ghi\vjkl\rspam').splitlines()
    [bytearray(b'ghi\x0bjkl'), bytearray(b'spam')]
    """
    if isinstance(s, (bytes, bytearray)):
        return s.splitlines(keepends)
    if isinstance(s, str):
        return [b.decode('utf-8', 'surrogatepass')
                for b in s.encode('utf-8', 'surrogatepass').splitlines(keepends)]
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


# TODO: docs + tests
def is_pure_ascii(s):
    if isinstance(s, str):
        return s == s.encode('ascii', 'ignore').decode('ascii', 'ignore')
    elif isinstance(s, (bytes, bytearray)):
        return s == s.decode('ascii', 'ignore').encode('ascii', 'ignore')
    else:
        raise TypeError('{!a} is neither a `str` nor a `bytes`/`bytearray`'.format(s))


# TODO: docs + tests
def lower_if_pure_ascii(s):
    if is_pure_ascii(s):
        return s.lower()
    return s


def as_bytes(obj, encode_error_handling='surrogatepass'):
    r"""
    Convert the given object to `bytes`.

    If the given object is a `str` -- encode it using `utf-8` with the
    error handler specified as the second argument, `encode_error_handling`
    (whose default value is `'surrogatepass'`).                                # TODO: change the default to 'strict' (adjusting client code where needed...)

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
    >>> class WithDunderBytes(object):
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


# TODO: doc, tests
### CR: db_event (and maybe some other stuff) uses different implementation
### -- fix it?? (unification needed??)
# TODO: support ipaddress.* stuff...
def ipv4_to_int(ipv4, accept_no_dot=False):
    """
    Return, as int, an IPv4 address specified as a string or integer.

    Args:
        `ipv4`:
            IPv4 as a `str` (formatted as 4 dot-separated decimal numbers
            or, if `accept_no_dot` is true, possible also as one decimal
            number) or as an `int` number.
        `accept_no_dot` (bool, default: False):
            If true -- accept `ipv4` as a string formatted as one decimal
            number.

    Returns:
        The IPv4 address as an int number.

    Raises:
        ValueError or TypeError.

    >>> ipv4_to_int('193.59.204.91')
    3241921627
    >>> ipv4_to_int('193.59.204.91 ')
    3241921627
    >>> ipv4_to_int(' 193 . 59 . 204.91')
    3241921627
    >>> ipv4_to_int(' 193.59. 204 .91 ')
    3241921627
    >>> ipv4_to_int(3241921627)
    3241921627

    >>> ipv4_to_int('3241921627')          # doctest: +IGNORE_EXCEPTION_DETAIL
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

    >>> ipv4_to_int(32419216270000000)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int('3241921627', accept_no_dot=True)
    3241921627
    >>> ipv4_to_int(' 3241921627 ', accept_no_dot=True)
    3241921627
    >>> ipv4_to_int('3241921627 ', accept_no_dot=True)
    3241921627

    >>> ipv4_to_int('32419216270000000',   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_int(bytearray(b'193.59.204.91'))      # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    TypeError: ...

    >>> ipv4_to_int(bytearray(b'3241921627'),
    ...             accept_no_dot=True)               # doctest: +IGNORE_EXCEPTION_DETAIL
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
    """
    Return, as a `str`, the IPv4 address specified as a `str` or `int`.

    Args:
        `ipv4`:
            IPv4 as a `str` (formatted as 4 dot-separated decimal numbers
            or, if `accept_no_dot` is true, possible also as one decimal
            number) or as an `int` number.
        `accept_no_dot` (bool, default: False):
            If true -- accept `ipv4` as a string formatted as one decimal
            number.

    Returns:
        The IPv4 address as a `str`.

    Raises:
        ValueError or TypeError.

    >>> ipv4_to_str('193.59.204.91')
    '193.59.204.91'
    >>> ipv4_to_str('193.59.204.91 ')
    '193.59.204.91'
    >>> ipv4_to_str(' 193 . 59 . 204.91')
    '193.59.204.91'
    >>> ipv4_to_str(' 193.59. 204 .91 ')
    '193.59.204.91'
    >>> ipv4_to_str(3241921627)
    '193.59.204.91'

    >>> ipv4_to_str('3241921627')          # doctest: +IGNORE_EXCEPTION_DETAIL
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

    >>> ipv4_to_str(32419216270000000)     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str('3241921627', accept_no_dot=True)
    '193.59.204.91'
    >>> ipv4_to_str(' 3241921627 ', accept_no_dot=True)
    '193.59.204.91'
    >>> ipv4_to_str('3241921627 ', accept_no_dot=True)
    '193.59.204.91'

    >>> ipv4_to_str('32419216270000000',   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...             accept_no_dot=True)
    Traceback (most recent call last):
      ...
    ValueError: ...

    >>> ipv4_to_str(bytearray(b'193.59.204.91'))      # doctest: +IGNORE_EXCEPTION_DETAIL
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


# maybe TODO later: more tests
# maybe TODO: support ipaddress.* stuff?...
def is_ipv4(value):
    r"""
    Check if the given `str` value is a properly formatted IPv4 address.

    Attrs:
        `value` (str): the value to be tested.

    Returns:
        Whether the value is properly formatted IPv4 address: True or False.

    >>> is_ipv4('255.127.34.124')
    True
    >>> is_ipv4('192.168.0.1')
    True
    >>> is_ipv4(' 192.168.0.1 ')
    False
    >>> is_ipv4('192. 168.0.1')
    False
    >>> is_ipv4('192.168.0.0.1')
    False
    >>> is_ipv4('333.127.34.124')
    False
    >>> is_ipv4('3241921627')
    False
    >>> is_ipv4('www.nask.pl')
    False
    >>> is_ipv4('www.jaźń\udcdd.pl')
    False
    """
    fields = value.split(".")
    if len(fields) != 4:
        return False
    for value in fields:
        if not (value == value.strip() and (
                value == '0' or value.strip().lstrip('0'))):  ## FIXME: 04.05.06.0333 etc. are accepted, should they???
            return False
        try:
            intvalue = int(value)
        except ValueError:
            return False
        if intvalue > 255 or intvalue < 0:
            return False
    return True


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


def iter_grouped_by_attr(collection_of_objects,   # type: Iterable[T]
                         attr_name,               # type: Str
                         presort=False,           # type: bool

                         # not real parameters, just quasi-constants for faster access:
                         _attrgetter=operator.attrgetter,
                         _groupby=itertools.groupby,
                         _list=list,
                         _sorted=sorted):
    # type: (...) -> Iterator[List[T]]
    """
    For the given collection of objects (`collection_of_objects`) and
    attribute name (`attr_name`), return an iterator which yields lists
    that group adjacent objects having equal values of the designated
    attribute.

    All objects the given collection contains are expected to have the
    designated attribute. `AttributeError` will be raised if an object
    without that attribute is encountered.

    By default the collection is processed in a "lazy" manner (it may be
    especially important if it is, for example, a generator that yields
    a huge number of objects).

    However, if the optional argument `presort` is true (its default
    value is `False`) then, in the first place, the given collection of
    objects is consumed to construct a list of those objects, **sorted
    by the designated attribute**, and only then the main part of the
    operation is performed -- using that sorted list as the source
    collection.

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
        `mode` (default: 'r'):
            An optional string that specifies the mode in which the file
            is opened. If it contains 'b' then it will be a binary mode;
            otherwise -- a text mode. For more information, see the docs
            of the built-in function `open()`.
        Other optional arguments, only as *keyword* (named) ones:
            See the docs of the built-in function `open()`.

    Returns:
        A file object (for details, see the docs of the built-in
        function `open()`).

    Raises:
        See the docs of the built-in function `open()`.

    *Additional feature:* if `mode` does *not* contain the 'b' marker
    (i.e., if the file is being opened in a text mode) *and* keyword
    arguments do *not* include `encoding` then the `encoding` argument
    is automatically set to 'utf-8'.
    """
    if 'b' not in mode:
        open_kwargs.setdefault('encoding', 'utf-8')
    return open(file, mode, **open_kwargs)


def read_file(file, mode='r', **open_kwargs):
    """
    Open `file` using the `open_file()` helper (see its docstring...),
    then read and return the file's content.

    Args/kwargs:
        See the docstring of `open_file()`.

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


def cleanup_src():
    """
    Delete all extracted resource files and directories,
    logs a list of the file and directory names that could not be successfully removed.
    [see: https://setuptools.readthedocs.io/en/latest/pkg_resources.html?highlight=cleanup_resources#resource-extraction]
    """
    from n6lib.log_helpers import get_logger
    _LOGGER = get_logger(__name__)

    fail_cleanup = cleanup_resources()
    if fail_cleanup:
        _LOGGER.warning('Fail cleanup resources: %a', fail_cleanup)


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
        # already unlocked
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
        # has been omitted (because of some asynchronous exception,
        # such as a KeyboardInterrupt raised by a signal handler, in an
        # unfortunate moment...).  Note that, even if -- in a very rare
        # case -- this additional lock release attempt was redundant
        # (and therefore premature), the only risk of executing
        # simultaneously this function's code by more than one thread
        # seems to be printing intermixed debug messages (not a big
        # deal, especially compared with a possibility of a deadlock).
        _try_to_release_lock()
        raise


class AtomicallySavedFile(object):

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
        self._dest_path = dest_path
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

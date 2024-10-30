# Copyright (c) 2024 NASK. All rights reserved.

import contextlib
import dataclasses
import functools
import hashlib
import math
import os
import random
import re
import secrets
import shutil
import tempfile
import time
from collections.abc import (
    Callable,
    Generator,
)
from pathlib import Path
from typing import (
    BinaryIO,
    ContextManager,
    Final,
    IO,
    Optional,
    TextIO,
    Union,
    cast,
)

from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    AtomicallySavedFile,
    RsyncFileContextManager,
    as_bytes,
    ascii_str,
    open_file,
    read_file,
)
from n6lib.typing_helpers import (
    HashObj,
    KwargsDict,
)


__all__ = [
    'AnyPath',
    'FileAccessor',
    'StampedFileAccessor',
    'SignedStampedFileAccessor',
    'as_path',

    # TODO: move the definitions of following classes and functions
    #       from `n6lib.common_helpers` into this module.
    'AtomicallySavedFile',
    'RsyncFileContextManager',
    'open_file',
    'read_file',
]


#
# Static typing helpers
#

AnyPath = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]


#
# The *file accessor* family of tools
#

class FileAccessor:

    r"""
    Each instance of this class has a target file path assigned
    (normalized to a `pathlib.Path` object, accessible as the `path`
    attribute), and provides the following factory methods:

    * `text_reader()`,
    * `text_atomic_writer()`,
    * `binary_reader()`,
    * `binary_atomic_writer()`.

    Each of them returns a context manager which produces a [file-like
    object](https://docs.python.org/3/glossary.html#term-file-object) of
    the corresponding kind. The `*_atomic_writer()` ones employ, under
    the hood, our `AtomicallySavedFile` tool which ensures that the file
    the target path points to is *either* successfully saved *or* left
    untouched (or non-existent if it did not exist before).

    Each of these four factories accepts a set of optional keyword-only
    arguments. Generally, they are analogous to the keyword arguments
    you can pass to `open()` (more precisely: all those accepted by our
    `open_file()` helper when it comes to reading, and the subset of
    them accepted by `AtomicallySavedFile()` when it comes to writing)
    -- *excluding* the `mode` argument, which is determined automatically
    (respectively, as: `'rt'`, `'wt'`, `'rb'`, `'wb'`). Subclasses may
    define other sets of accepted keyword-only arguments (possibly --
    yet not necessarily -- being supersets or subsets of those standard
    ones).

    This class itself is not very interesting. It is subclasses that are
    worth your attention.

    ***

    Anyway, let's show the basics.

    We need to prepare auxiliary stuff for our examples...

    >>> import pathlib, tempfile
    >>> our_dir_obj = tempfile.TemporaryDirectory(prefix='n6-test-n6lib.file_helpers-')
    >>> our_dir = as_path(our_dir_obj.name)  # `as_path()` is another helper defined in this module
    >>> our_path = our_dir / 'test-file'

    Now, let's create our first instance.

    >>> accessor = FileAccessor(our_path)

    The specified target path is accessible as the `path` attribute:

    >>> isinstance(accessor.path, pathlib.Path) and accessor.path == pathlib.Path(our_path)
    True

    ...and visible in the instance's *repr* string:

    >>> repr(accessor) == f'<FileAccessor path={our_path!r}>'
    True

    OK, let's prepare some data for further examples...

    >>> example_text = 'uważny\nturysta\n...'
    >>> len(example_text)
    18
    >>> example_bytes = example_text.encode('utf-8')
    >>> example_bytes
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> len(example_bytes)
    19

    Now, let's start with confirming that all writes are atomic:

    >>> with accessor.text_atomic_writer() as file:
    ...     file.write(example_text)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = accessor.text_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    >>> with accessor.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = accessor.binary_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    Now, let's really store and retrieve some stuff:

    >>> with accessor.text_atomic_writer() as file:  # Here `encoding` defaults to `utf-8` (see:
    ...     file.write(example_text)                 # `open_file()` which has the same feature...)
    ...
    18
    >>> with accessor.text_reader() as file:  # Here `encoding` defaults to `utf-8` (see:
    ...     got = file.read()                 # `open_file()` which has the same feature...)
    ...
    >>> got == example_text
    True

    >>> with accessor.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> with accessor.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> got == example_bytes
    True

    And, also, let's make use of some legal keyword arguments:

    >>> with accessor.text_atomic_writer(encoding='latin2', newline='\r\n') as file:
    ...     file.write(example_text)
    ...
    18
    >>> with accessor.binary_reader(buffering=0) as file:
    ...     got = file.read()
    ...
    >>> got
    b'uwa\xbfny\r\nturysta\r\n...'
    >>> got == example_bytes
    False
    >>> got == example_text.replace('\n', '\r\n').encode('latin2')
    True

    >>> with accessor.binary_atomic_writer(buffering=2) as file:
    ...     file.write(got)
    ...
    20
    >>> with accessor.text_reader(errors='surrogateescape') as file:
    ...     list(file)
    ...
    ['uwa\udcbfny\n', 'turysta\n', '...']
    >>> with accessor.text_reader(encoding='ascii', errors='ignore', newline='\r') as file:
    ...     list(file)
    ...
    ['uwany\r', '\nturysta\r', '\n...']
    >>> import os
    >>> with accessor.binary_reader(opener=os.open, closefd=True) as file:
    ...     list(file)
    ...
    [b'uwa\xbfny\r\n', b'turysta\r\n', b'...']

    Naturally, `TypeError` is raised if unsupported arguments are given
    -- although the check is deferred until the returned context manager
    is entered:

    >>> cm = accessor.binary_reader(tralala=42, hu_ha='Pełni optymistycznego ducha.', Ż='aba')
    >>> with cm: pass
    Traceback (most recent call last):
      ...
    TypeError: got unexpected/unsupported keyword argument(s): 'hu_ha', 'tralala', '\u017b'
    >>> cm = accessor.text_reader(flags=0x80, bum_bum='abc')
    >>> with cm: pass
    Traceback (most recent call last):
      ...
    TypeError: got unexpected/unsupported keyword argument(s): 'bum_bum', 'flags'
    >>> cm = accessor.binary_atomic_writer(opener=os.open)  # (`opener` -- not for atomic writer)
    >>> with cm: pass
    Traceback (most recent call last):
      ...
    TypeError: got unexpected/unsupported keyword argument(s): 'opener'
    >>> cm = accessor.text_atomic_writer(closefd=True)  # (`closefd` -- not for atomic writer)
    >>> with cm: pass
    Traceback (most recent call last):
      ...
    TypeError: got unexpected/unsupported keyword argument(s): 'closefd'

    As said earlier, the target path (passed to the constructor as the
    `path` argument) is always coerced to an instance of `pathlib.Path`
    (under the hood, our `as_path()` helper is used to do that):

    >>> path = FileAccessor('/foo/bar').path
    >>> isinstance(path, pathlib.Path) and path == pathlib.Path('/foo/bar')
    True
    >>> path = FileAccessor(path=b'/foo/bar').path   # (passing the path as a kwarg is also OK)
    >>> isinstance(path, pathlib.Path) and path == pathlib.Path('/foo/bar')
    True
    >>> path = FileAccessor(pathlib.PurePath('/foo/bar/')).path
    >>> isinstance(path, pathlib.Path) and path == pathlib.Path('/foo/bar')
    True
    >>> class MyPathLike: __fspath__ = lambda self: b'/foo/bar'
    >>> path = FileAccessor(MyPathLike()).path
    >>> isinstance(path, pathlib.Path) and path == pathlib.Path('/foo/bar')
    True
    """

    #
    # Public interface

    path: Path

    def __init__(self, path: AnyPath, **kwargs):
        super().__init__(**kwargs)
        self.path = as_path(path)

    def text_reader(self, **kwargs) -> ContextManager[TextIO]:
        cm = self._obtain_context_manager(mode='rt', **kwargs)
        return cast(ContextManager[TextIO], cm)

    def text_atomic_writer(self, **kwargs) -> ContextManager[TextIO]:
        cm = self._obtain_context_manager(mode='wt', **kwargs)
        return cast(ContextManager[TextIO], cm)

    def binary_reader(self, **kwargs) -> ContextManager[BinaryIO]:
        cm = self._obtain_context_manager(mode='rb', **kwargs)
        return cast(ContextManager[BinaryIO], cm)

    def binary_atomic_writer(self, **kwargs) -> ContextManager[BinaryIO]:
        cm = self._obtain_context_manager(mode='wb', **kwargs)
        return cast(ContextManager[BinaryIO], cm)

    __repr__ = attr_repr('path')


    #
    # Non-public stuff (using/extending it in subclasses is OK)

    def _obtain_context_manager(self,
                                *,
                                mode: str,
                                **given_kwargs) -> ContextManager[IO]:
        (open_kwargs,
         rest_kwargs) = self._adjust_and_split_kwargs(mode=mode, **given_kwargs)
        self._validate_open_kwargs(**open_kwargs)
        file_cm = self._get_file_cm(self.path, mode, open_kwargs, **rest_kwargs)
        if file_cm is None:
            raise NotImplementedError(ascii_str(
                f'{self.__class__.__qualname__}: no file context manager '
                f'implementation for {mode=!a} and {given_kwargs=!a}'))
        enclosing_cm = self._enclosing_cm(file_cm, **rest_kwargs)
        return enclosing_cm

    def _adjust_and_split_kwargs(self,
                                 *,
                                 mode: str,
                                 **given_kwargs) -> tuple[KwargsDict, KwargsDict]:
        names_of_supported_open_kwargs = self._get_names_of_supported_open_kwargs(mode)
        open_kwargs = {
            name: given_kwargs.pop(name)
            for name in sorted(names_of_supported_open_kwargs)
            if name in given_kwargs}
        if 'encoding' in names_of_supported_open_kwargs:
            # (behavior similar to that of our `open_file()` helper)
            open_kwargs.setdefault('encoding', 'utf-8')
        rest_kwargs = given_kwargs
        rest_kwargs.setdefault('_set_on_success', {})
        return open_kwargs, rest_kwargs

    def _get_names_of_supported_open_kwargs(self, mode: str) -> set[str]:
        # (see: https://docs.python.org/3/library/functions.html#open)
        names = {'buffering'}
        if self._is_text_mode(mode):
            names.update({'encoding', 'errors', 'newline'})
        if not self._is_atomic_writer_mode(mode):
            # (not supported by `AtomicallySavedFile`)
            names.update({'closefd', 'opener'})
        return names

    def _validate_open_kwargs(self, **open_kwargs) -> None:
        pass  # (can be overridden/extended in subclasses)

    def _get_file_cm(self,
                     path: Path,
                     mode: str,
                     open_kwargs: KwargsDict,
                     **rest_kwargs) -> Optional[ContextManager[IO]]:
        if self._is_pure_reader_mode(mode):
            return self._pure_reader_cm(path, mode, open_kwargs, **rest_kwargs)
        if self._is_atomic_writer_mode(mode):
            return self._atomic_writer_cm(path, mode, open_kwargs, **rest_kwargs)
        return None

    def _is_text_mode(self, mode: str) -> bool:
        return not self._is_binary_mode(mode)

    def _is_binary_mode(self, mode: str) -> bool:
        return 'b' in mode

    def _is_pure_reader_mode(self, mode: str) -> bool:
        return ('r' in mode) and ('+' not in mode)

    def _is_atomic_writer_mode(self, mode: str) -> bool:
        return ('w' in mode) and ('+' not in mode)

    @contextlib.contextmanager
    def _pure_reader_cm(self,
                        path: Path,
                        mode: str,
                        open_kwargs: KwargsDict,
                        *,
                        _set_on_success: dict,
                        **unexpected_kwargs) -> Generator[IO]:
        if unexpected_kwargs:
            raise self._get_unexpected_kwargs_error(**unexpected_kwargs)
        with self._get_pure_reader_underlying_cm(path, mode, open_kwargs) as file:
            yield file

    def _get_pure_reader_underlying_cm(self,
                                       path: Path,
                                       mode: str,
                                       open_kwargs: KwargsDict) -> ContextManager[IO]:
        return open_file(path, mode, **open_kwargs)

    @contextlib.contextmanager
    def _atomic_writer_cm(self,
                          path: Path,
                          mode: str,
                          open_kwargs: KwargsDict,
                          *,
                          _set_on_success: dict,
                          **unexpected_kwargs) -> Generator[IO]:
        if unexpected_kwargs:
            raise self._get_unexpected_kwargs_error(**unexpected_kwargs)
        with self._get_atomic_writer_underlying_cm(path, mode, open_kwargs) as file:
            yield file

    def _get_atomic_writer_underlying_cm(self,
                                         path: Path,
                                         mode: str,
                                         open_kwargs: KwargsDict) -> ContextManager[IO]:
        return AtomicallySavedFile(path, mode, **open_kwargs)

    def _get_unexpected_kwargs_error(self, **unexpected_kwargs) -> TypeError:
        listing = ', '.join(map(ascii, sorted(unexpected_kwargs)))
        return TypeError(f'got unexpected/unsupported keyword argument(s): {listing}')

    @contextlib.contextmanager
    def _enclosing_cm(self,
                      file_cm: ContextManager[IO],
                      *,
                      _set_on_success: dict,
                      **_) -> Generator[IO]:
        with file_cm as file:
            yield file
        for attr_name, obj in _set_on_success.items():
            setattr(self, attr_name, obj)


class StampedFileAccessor(FileAccessor):

    r"""
    A subclass of `FileAccessor` which provides read and write access to
    *stamped* files, i.e., such ones that include an ASCII-only header
    (in a format specific to this class) -- prepended to their contents.
    The header contains the following metadata:

    * a *stamper id* -- an identifier consisting of 40 hexadecimal
      digits;

    * a Unix timestamp of the last write (stored in a decimal format,
      with the fractional part always consisting of 6 digits, i.e.,
      offering the microseconds precision).

    Subclasses may add other fields...

    *Note:* although the intent is that, for client code, the presence
    of that header should be transparent/invisible, invoking `seek()`
    or `tell()` (on a file-like object provided by the file accessor
    interface) may lead you to read or even overwrite that header; note,
    however, that -- when it comes to write operations that change the
    header -- such cases are always detected and cause an error which,
    effectively, prevents those changes from being actually written.

    ***

    OK, let's start with the basics.

    We need to prepare auxiliary stuff for our examples...

    >>> import pathlib, string, tempfile, time
    >>> HEX_DIGITS_LOWERCASE = set(string.hexdigits.lower().encode('ascii'))
    >>> our_dir_obj = tempfile.TemporaryDirectory(prefix='n6-test-n6lib.file_helpers-')
    >>> our_dir = as_path(our_dir_obj.name)
    >>> our_path = our_dir / 'test-file'

    First, let's examine the instance attributes that belong to the public
    interface (note: generally, they should be considered read-only, even
    though that's not technically enforced...):

    >>> acc = StampedFileAccessor(our_path)
    >>> repr(acc) == f'<StampedFileAccessor path={our_path!r}>'
    True
    >>> isinstance(acc.path, pathlib.Path) and acc.path == our_path
    True
    >>> acc.time_func is time.time   # <- This is the default, you can customize it (see below...).
    True
    >>> own_stamper_id = acc.own_stamper_id   # <- We did not specify it (but see below...), so a
    >>> isinstance(own_stamper_id, bytes)     #    securely random id has been generated for us.
    True
    >>> len(own_stamper_id) == 40
    True
    >>> HEX_DIGITS_LOWERCASE.issuperset(own_stamper_id)
    True
    >>> # The other attributes are initially set to `None`:
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp is None
    True
    >>> acc.last_read_or_written_timestamp is None
    True

    Let's make another `StampedFileAccessor` instance -- customizing
    what we can:

    >>> our_custom_stamper_id = b'0123456789abcdef0123456789abcdef01234567'
    >>> t = -42.59999901
    >>> def fake_time(): return t
    ...
    >>> acc = StampedFileAccessor(our_path,
    ...                           time_func=fake_time,
    ...                           own_stamper_id=our_custom_stamper_id)
    ...
    >>> acc.time_func is fake_time
    True
    >>> acc.own_stamper_id == our_custom_stamper_id
    True

    *Note:* `time_func` needs to be a callable that always returns a
    `float` or `int` number between (circa) `-(10 ** 12)` and `10 ** 13`;
    otherwise errors will be raised, e.g.:

    >>> StampedFileAccessor('/foo/bar', time_func=lambda: '123456789')   # Error: wrong type.
    Traceback (most recent call last):
      ...
    TypeError: timestamp must be a `float` or `int` (wrong `time_func`)
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: float('nan'))  # Error: non-finite/NaN.
    Traceback (most recent call last):
      ...
    ValueError: timestamp must be a finite number (wrong `time_func`)
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: 10.0**13)      # Error: too big.
    Traceback (most recent call last):
      ...
    ValueError: timestamp=10000000000000.0 is out of range (wrong `time_func`)
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: -(10**12))     # Error: too small.
    Traceback (most recent call last):
      ...
    ValueError: timestamp=-1000000000000.0 is out of range (wrong `time_func`)
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: 123456789)         # (OK)
    <StampedFileAccessor path=PosixPath('/foo/bar')>
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: 0)                 # (OK)
    <StampedFileAccessor path=PosixPath('/foo/bar')>
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: 42.123456789)      # (OK)
    <StampedFileAccessor path=PosixPath('/foo/bar')>
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: 10**13 - 0.1)      # (OK)
    <StampedFileAccessor path=PosixPath('/foo/bar')>
    >>> StampedFileAccessor('/foo/bar', time_func=lambda: -(10**12) + 0.1)   # (OK)
    <StampedFileAccessor path=PosixPath('/foo/bar')>

    OK, now let's prepare some data for further examples...

    >>> example_text = 'uważny\nturysta\n...'
    >>> len(example_text)
    18
    >>> example_bytes = example_text.encode('utf-8')
    >>> example_bytes
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> len(example_bytes)
    19

    Now, let's confirm that, as in the case of `FileAccessor`, all
    writes are atomic:

    >>> with acc.text_atomic_writer() as file:
    ...     file.write(example_text)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = acc.text_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = acc.binary_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    Nothing has been read or written yet:

    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp is None
    True
    >>> acc.last_read_or_written_timestamp is None
    True

    Now, let's really write and read some stuff -- and see that the
    aforementioned header, conveying the `StampedFileAccessor`-specific
    metadata, is also stored...

    >>> with acc.text_atomic_writer() as file:  # Here `encoding` defaults to `utf-8` (see:
    ...     file.write(example_text)            # `open_file()` which has the same feature...)
    ...
    18
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == -42.6  # (Timestamps are "floor-rounded" to 6 decimal places)
    True
    >>> acc.last_read_or_written_timestamp == -42.6 < -42.59999901 == t < -42.599999
    True

    >>> with acc.text_atomic_writer() as file:
    ...     file.write('Coś ZUPEŁNIE innego...')   # (Again: thanks to atomicity,
    ...     file.flush()                           # error will "rollback" this)
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == -42.6
    True
    >>> acc.last_read_or_written_timestamp == -42.6
    True

    >>> t = -42.599999
    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(b'Completely DIFFERENT!' * 42)   # (Again: thanks to atomicity,
    ...     file.flush()                                # error will "rollback" this)
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == -42.6
    True
    >>> acc.last_read_or_written_timestamp == -42.6
    True

    >>> with acc.text_reader() as file:   # Here `encoding` defaults to `utf-8` (see:
    ...     got = file.read()             # `open_file()` which has the same feature...)
    ...
    >>> got == example_text
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == -42.6 < t          # [sic!]
    True
    >>> acc.last_written_timestamp == -42.6
    True
    >>> acc.last_read_or_written_timestamp == -42.6   # [sic!]
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == -42.6
    True
    >>> acc.last_written_timestamp == -42.599999 == t > -42.59999901 > -42.6
    True
    >>> acc.last_read_or_written_timestamp == -42.599999
    True

    >>> acc2 = StampedFileAccessor(our_path,  # (same path and other args...)
    ...                            time_func=fake_time,
    ...                            own_stamper_id=our_custom_stamper_id)
    ...
    >>> with acc2.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> got == example_bytes
    True
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == -42.599999
    True
    >>> acc2.last_written_timestamp is None
    True
    >>> acc2.last_read_or_written_timestamp == -42.599999
    True

    ***

    One *limitation* is that *for text I/O*, **only** encodings being
    supersets of ASCII (such as `utf-8`, `windows-1252`, `iso-8859-...`)
    are supported correctly. If an *ASCII-incompatible* encoding is
    detected, `ValueError` is raised:

    >>> with acc.text_reader(encoding='cp500'):
    ...    pass
    ...
    Traceback (most recent call last):
      ...
    ValueError: encoding='cp500' is unsupported as it is not ASCII-compatible

    >>> with acc.text_atomic_writer(encoding='cp500'):
    ...    pass
    ...
    Traceback (most recent call last):
      ...
    ValueError: encoding='cp500' is unsupported as it is not ASCII-compatible

    Obviously, this limitation does *not* apply to *binary I/O*.

    ***

    When reading, you can request to check that the file's timestamp is
    not older (not smaller) than the specified value -- then, if it is,
    the exception `StampedFileAccessor.OutdatedError` is raised:

    >>> with acc.text_reader(minimum_timestamp=-42.3) as file:
    ...     pass    # Nothing can be read when the timestamp is too old.
    ...                                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.StampedFileAccessor.OutdatedError: ...
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == -42.6    # (<- not updated because of error)
    True
    >>> acc.last_written_timestamp == -42.599999
    True
    >>> acc.last_read_or_written_timestamp == -42.599999
    True
    >>> with acc.text_reader(minimum_timestamp=-42.7) as file:        # Now OK.
    ...     got = file.read()
    ...
    >>> got == example_text
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == -42.599999
    True
    >>> acc.last_written_timestamp == -42.599999
    True
    >>> acc.last_read_or_written_timestamp == -42.599999
    True

    >>> with acc.binary_reader(minimum_timestamp=-42.3) as file:
    ...     pass    # Nothing can be read when the timestamp is too old.
    ...                                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.StampedFileAccessor.OutdatedError: ...
    >>> with acc.binary_reader(minimum_timestamp=-42.7) as file:      # Now OK.
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True

    ***

    The `StampedFileAccessor`-specific header is "seen" by the file
    methods `seek()` and `tell()`, e.g.:

    >>> with acc.text_reader() as file:
    ...     told = file.tell()
    ...     seen = file.seek(0)
    ...     told2 = file.tell()
    ...     got = file.read(21)
    ...
    >>> told == 62 and seen == told2 == 0
    True
    >>> got == '-000000000042.599999\n'  # (timestamp + separator)
    True

    But note that any attempt to change that header will be detected --
    causing an error and making all changes being "rolled back".

    >>> with acc.text_atomic_writer() as file:
    ...     _ = file.seek(0)                     # Trying to *change* header...
    ...     _ = file.write('ala ma kota')  # (<- *invalid* as part of timestamp)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'uwa\xc5\xbcny\nturysta\n...'           # *No* changes written.
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     _ = file.seek(0)                     # Trying to *change* header...
    ...     _ = file.write(b'0000009876543.210000')  # (<- *valid* as timestamp)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> with acc.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == 'uważny\nturysta\n...'                   # *No* changes written.
    True

    >>> with acc.text_atomic_writer() as file:
    ...     _ = file.seek(61)                    # Trying to *change* header...
    ...     _ = file.write('ala ma kota')
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'uwa\xc5\xbcny\nturysta\n...'           # *No* changes written.
    True

    >>> with acc.text_atomic_writer() as file:
    ...     _ = file.seek(62)    # OK, the header will *not* be touched at all.
    ...     _ = file.write('ala ma kota')
    ...
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'ala ma kota'      # The content has been written successfully.
    True

    >>> with acc.text_atomic_writer() as file:
    ...     _ = file.seek(61)    # OK, the header will be touched, but *not* effectively changed.
    ...     _ = file.write('\nala ma kota')
    ...
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'ala ma kota'      # The content has been written successfully.
    True

    ***

    Of course, you can always corrupt your files manually... :-)

    >>> with open(our_path, 'r+b') as f:
    ...     _ = f.seek(30)                # Obviously, this *will* change the header!
    ...     _ = f.write(b'ala ma kota')
    ...
    >>> with acc.binary_reader() as file:
    ...     file.read()                        # doctest: +NORMALIZE_WHITESPACE
    ...
    Traceback (most recent call last):
      ...
    ValueError: not a valid stamper id
                (b'012345678ala ma kota456789abcdef01234567'
                does not match the expected pattern)

    >>> with open(our_path, 'wt') as f:   # Obviously, this *will* change the header!
    ...     _ = f.write('ala ma kota')
    ...
    >>> with acc.text_reader() as file:
    ...     file.read()
    ...
    Traceback (most recent call last):
      ...
    ValueError: not a valid timestamp (b'ala ma kota' does not match the expected pattern)

    ***

    In the following example we inspect some internal details (note that
    they *may change when the implementation changes*).

    >>> with acc2.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> with open(our_path, 'rb') as f:
    ...     h_timestamp = f.read(20)
    ...     h_sep1 = f.read(1)
    ...     h_stamper_id = f.read(40)
    ...     h_sep2 = f.read(1)
    ...     body = f.read()
    ...
    >>> h_sep1 == h_sep2 == b'\n'
    True
    >>> h_timestamp == b'-000000000042.599999' and float(h_timestamp) == -42.599999
    True
    >>> h_stamper_id == our_custom_stamper_id
    True
    >>> body == example_bytes
    True

    """

    #
    # Public interface extensions

    class OutdatedError(ValueError):
        """Raised when the file's timestamp is older than requested."""

    time_func: Callable[[], Union[float, int]]

    own_stamper_id: bytes
    last_read_stamper_id: Optional[bytes]

    last_read_timestamp: Optional[float]
    last_written_timestamp: Optional[float]
    last_read_or_written_timestamp: Optional[float]

    def __init__(self,
                 path: AnyPath,
                 *,
                 time_func: Callable[[], Union[float, int]] = time.time,
                 own_stamper_id: Optional[bytes] = None,
                 **kwargs):

        super().__init__(path, **kwargs)

        self._meta_field_properties = self._get_meta_field_properties()

        self.time_func = time_func
        self._current_timestamp_raw()  # (=> early error if `time_func` is inherently wrong...)

        if own_stamper_id is None:
            own_stamper_id = self._generate_new_stamper_id()
        self._verify_meta_field_validity('stamper id', own_stamper_id)
        self.own_stamper_id = own_stamper_id
        self.last_read_stamper_id = None

        self.last_read_timestamp = None
        self.last_written_timestamp = None
        self.last_read_or_written_timestamp = None


    #
    # Non-public stuff extensions

    _FIELD_SEPARATOR: Final[bytes] = b'\n'

    _TIMESTAMP_INT_DIGITS: Final[int] = 13
    _TIMESTAMP_FRACT_DIGITS: Final[int] = 6
    _TIMESTAMP_RAW_FORMAT: Final[bytes] = as_bytes(
        f'%0{_TIMESTAMP_INT_DIGITS + 1 + _TIMESTAMP_FRACT_DIGITS}'
        f'.'
        f'{_TIMESTAMP_FRACT_DIGITS}f')


    @dataclasses.dataclass(frozen=True)
    class _FieldProps:
        """Properties of a metadata field."""
        regex: re.Pattern[bytes]
        length: int


    _meta_field_properties: dict[str, _FieldProps]

    def _get_meta_field_properties(self) -> dict[str, _FieldProps]:
        _stamper_id_length = 40
        meta_field_properties = {
            'separator': self._FieldProps(
                regex=re.compile(rb'\A%b\Z' % (
                    re.escape(self._FIELD_SEPARATOR),
                )),
                length=len(self._FIELD_SEPARATOR),
            ),
            'timestamp': self._FieldProps(
                regex=re.compile(rb'\A[-0-9][0-9]{%d}\.[0-9]{%d}\Z' % (
                    self._TIMESTAMP_INT_DIGITS - 1,
                    self._TIMESTAMP_FRACT_DIGITS,
                )),
                length=(self._TIMESTAMP_INT_DIGITS + 1 + self._TIMESTAMP_FRACT_DIGITS),
            ),
            'stamper id': self._FieldProps(
                regex=re.compile(rb'\A[0-9a-f]{%d}\Z' % _stamper_id_length),
                length=_stamper_id_length,
            ),
        }
        if __debug__:
            _example_timestamp_raw = self._TIMESTAMP_RAW_FORMAT % 123.456
            _example_stamper_id = _stamper_id_length * b'a'
            assert meta_field_properties['separator'].regex.search(self._FIELD_SEPARATOR)
            assert meta_field_properties['separator'].length == len(self._FIELD_SEPARATOR)
            assert meta_field_properties['timestamp'].regex.search(_example_timestamp_raw)
            assert meta_field_properties['timestamp'].length == len(_example_timestamp_raw)
            assert meta_field_properties['stamper id'].regex.search(_example_stamper_id)
            assert meta_field_properties['stamper id'].length == len(_example_stamper_id)
        return meta_field_properties

    def _current_timestamp_raw(self) -> bytes:
        obtained_timestamp = self.time_func()
        if not isinstance(obtained_timestamp, (float, int)):
            raise TypeError('timestamp must be a `float` or `int` (wrong `time_func`)')
        if not math.isfinite(obtained_timestamp):
            raise ValueError('timestamp must be a finite number (wrong `time_func`)')
        factor = 10 ** self._TIMESTAMP_FRACT_DIGITS
        timestamp = (
            # We "floor-round" the number to `_TIMESTAMP_FRACT_DIGITS` decimal
            # places (note: for positive numbers this is similar to truncation).
            math.floor(factor * obtained_timestamp) / factor)
        timestamp_raw = self._TIMESTAMP_RAW_FORMAT % timestamp
        max_length = self._meta_field_properties['timestamp'].length
        if len(timestamp_raw) > max_length:
            raise ValueError(f'{timestamp=!a} is out of range (wrong `time_func`)')
        assert len(timestamp_raw) == max_length
        # The following validation may be redundant, but let's be on a safe side.
        self._verify_meta_field_validity('timestamp', timestamp_raw)
        return timestamp_raw

    def _generate_new_stamper_id(self) -> bytes:
        hex_digits_count = self._meta_field_properties['stamper id'].length
        stamper_id_str = secrets.token_hex(nbytes=hex_digits_count // 2)
        return stamper_id_str.encode('ascii')

    def _validate_open_kwargs(self, **open_kwargs) -> None:
        super()._validate_open_kwargs(**open_kwargs)
        if 'encoding' in open_kwargs:
            self._verify_encoding_seems_ascii_compatible(open_kwargs['encoding'])

    def _verify_encoding_seems_ascii_compatible(self, encoding: str) -> None:
        ascii_s = self._sample_ascii_str
        ascii_b = ascii_s.encode('ascii', 'strict')
        try:
            encoded = ascii_s.encode(encoding, 'strict')
            if encoded != ascii_b:
                raise ValueError(f'{encoded=!a} not equal to expected {ascii_b!a}')
            decoded = ascii_b.decode(encoding, 'strict')
            if decoded != ascii_s:
                raise ValueError(f'{decoded=!a} not equal to expected {ascii_s!a}')
        except ValueError as exc:
            raise ValueError(
                f'{encoding=!a} is unsupported as it is not ASCII-compatible'
            ) from exc

    @functools.cached_property
    def _sample_ascii_str(self) -> str:
        ascii_count = 128
        ascii_range = range(ascii_count)
        code_seq = []
        code_seq.extend(ascii_range)
        code_seq.extend(reversed(ascii_range))
        code_seq.extend(random.sample(ascii_range, k=ascii_count))
        code_seq.extend(random.choices(ascii_range, k=ascii_count))
        return ''.join(map(chr, code_seq))

    @contextlib.contextmanager
    def _pure_reader_cm(self,
                        path: Path,
                        mode: str,
                        open_kwargs: KwargsDict,
                        *,
                        _set_on_success: dict,
                        minimum_timestamp: Union[int, float, None] = None,
                        **kwargs) -> Generator[IO]:

        with super()._pure_reader_cm(path, mode, open_kwargs,
                                     _set_on_success=_set_on_success,
                                     **kwargs) as file:
            (timestamp,
             stamper_id) = self._parse_header(file)

            if minimum_timestamp is not None and timestamp < minimum_timestamp:
                raise self.OutdatedError(f"file's timestamp is older than requested "
                                         f"({timestamp=!a}, {minimum_timestamp=!a})")

            yield file

        _set_on_success.update(
            last_read_or_written_timestamp=timestamp,
            last_read_timestamp=timestamp,
            last_read_stamper_id=stamper_id,
        )

    def _parse_header(self, file: IO) -> tuple[float, bytes]:
        timestamp_raw = self._consume_meta_field('timestamp', file)
        timestamp = float(timestamp_raw)
        self._consume_meta_field('separator', file)
        stamper_id = self._consume_meta_field('stamper id', file)
        self._consume_meta_field('separator', file)
        return timestamp, stamper_id

    def _consume_meta_field(self, field_name: str, file: IO) -> bytes:
        max_length = self._meta_field_properties[field_name].length
        value = as_bytes(file.read(max_length))
        self._verify_meta_field_validity(field_name, value)
        assert value.isascii()
        return value

    def _verify_meta_field_validity(self, field_name: str, value: bytes) -> None:
        if not isinstance(value, bytes):
            raise TypeError(
                f'not a valid {field_name} ({value!a} '
                f'is not a `bytes` object)')
        if not value.isascii():
            raise ValueError(
                f'not a valid {field_name} ({value!a} '
                f'contains some non-ASCII bytes)')
        regex = self._meta_field_properties[field_name].regex
        if regex.search(value) is None:
            raise ValueError(
                f'not a valid {field_name} ({value!a} '
                f'does not match the expected pattern)')

    @contextlib.contextmanager
    def _atomic_writer_cm(self,
                          path: Path,
                          mode: str,
                          open_kwargs: KwargsDict,
                          *,
                          _set_on_success: dict,
                          **kwargs) -> Generator[IO]:

        timestamp_raw = self._current_timestamp_raw()

        with super()._atomic_writer_cm(path, mode, open_kwargs,
                                       _set_on_success=_set_on_success,
                                       **kwargs) as file:
            # (`file` is supposed to be from an `AtomicallySavedFile`/`NamedTemporaryFile`...)
            assert getattr(file, 'name', '').startswith(tempfile.gettempdir())

            header = self._prepare_new_header(mode, timestamp_raw)
            file.write(header)

            yield file

            file.flush()
            if self._any_header_difference(header, path=as_path(file.name)):
                raise RuntimeError('not allowed to change header by overwriting it')

        timestamp = float(timestamp_raw)
        _set_on_success.update(
            last_read_or_written_timestamp=timestamp,
            last_written_timestamp=timestamp,
        )

    def _prepare_new_header(self, mode: str, timestamp_raw: bytes) -> Union[str, bytes]:
        separator = self._FIELD_SEPARATOR
        header = b'%b%b%b%b' % (timestamp_raw, separator, self.own_stamper_id, separator)
        assert header.isascii()
        if self._is_text_mode(mode):
            header = header.decode('ascii')
        return header

    def _any_header_difference(self, header: Union[str, bytes], path: Path) -> bool:
        assert header.isascii()
        orig = as_bytes(header)
        with open(path, 'rb') as reader:
            found = reader.read(len(orig))
            return found != orig


class SignedStampedFileAccessor(StampedFileAccessor):

    r"""
    A subclass of `StampedFileAccessor` which provides cryptographic
    verification of file content integrity.

    ***

    Usage of `SignedStampedFileAccessor` is like `StampedFileAccessor`'s,
    except that one additional argument to the constructor is required:
    `secret_key`, being an instance of `bytes`. It should be a reasonably
    long, unpredictable (preferably, generated using a cryptographically
    strong random number generator) secret.

    The cryptographic (roughly speaking, HMAC-like) *signature* is always
    *automatically added* when the file is written, and *automatically
    verified* when the file is read. It is placed at the beginning of the
    file -- that is, *before* the `StampedFileAccessor`-specific header;
    what is worth emphasizing, the content being signed includes *also*
    that header.

    When reading, no content is exposed to the client code until the
    `SignedStampedFileAccessor`'s internal machinery verifies that the
    signature matches the whole file's content. In other words, you can
    safely consider as already verified *all data you read* from the
    file-like object provided by the `text_reader()`/`binary_reader()`
    method.

    When writing, there is no need to worry about damaging the signature
    (at least, as long as you just use the public interface with good
    will `:-)`) -- even if you (ab)use the method `seek()` of file-like
    objects provided by `text_atomic_writer()`/`binary_atomic_writer()`
    (as the `seek()` and `tell()` methods of those objects do not "see"
    the *signature* part of the file content; even though they "see" the
    *header* related to the features provided by `StampedFileAccessor`,
    just like in the case of that class; see its docs...).

    ***

    OK, again, let's start with the basics.

    We need to prepare auxiliary stuff for our examples...

    >>> import pathlib, string, tempfile, time
    >>> HEX_DIGITS_LOWERCASE = set(string.hexdigits.lower().encode('ascii'))
    >>> our_dir_obj = tempfile.TemporaryDirectory(prefix='n6-test-n6lib.file_helpers-')
    >>> our_dir = as_path(our_dir_obj.name)
    >>> our_path = our_dir / 'test-file'

    First, let's examine the instance attributes that belong to the public
    interface (note: like for the superclasses, those attributes should
    be considered read-only, even though that's not technically enforced):

    >>> acc = SignedStampedFileAccessor(our_path, secret_key=b'my secret')
    >>> repr(acc) == f'<SignedStampedFileAccessor path={our_path!r}>'
    True
    >>> isinstance(acc.path, pathlib.Path) and acc.path == our_path
    True
    >>> acc.time_func is time.time   # <- This is the default, you can customize it (see below...).
    True
    >>> own_stamper_id = acc.own_stamper_id   # <- We did not specify it (but see below...), so a
    >>> isinstance(own_stamper_id, bytes)     #    securely random id has been generated for us.
    True
    >>> len(own_stamper_id) == 40
    True
    >>> HEX_DIGITS_LOWERCASE.issuperset(own_stamper_id)
    True
    >>> # The other attributes are initially set to `None`:
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp is None
    True
    >>> acc.last_read_or_written_timestamp is None
    True

    Let's make another `SignedStampedFileAccessor` instance -- customizing
    what we can:

    >>> our_secret_key = b'our beautiful secret key!'
    >>> our_custom_stamper_id = b'0123456789abcdef0123456789abcdef01234567'
    >>> t = 321.0123999999
    >>> def fake_time(): return t
    ...
    >>> acc = SignedStampedFileAccessor(our_path,
    ...                                 secret_key=our_secret_key,
    ...                                 time_func=fake_time,
    ...                                 own_stamper_id=our_custom_stamper_id)
    ...
    >>> acc.time_func is fake_time
    True
    >>> acc.own_stamper_id == our_custom_stamper_id
    True

    Also, let's prepare some data for further examples...

    >>> example_text = 'uważny\nturysta\n...'
    >>> len(example_text)
    18
    >>> example_bytes = example_text.encode('utf-8')
    >>> example_bytes
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> len(example_bytes)
    19

    Now, let's confirm that, as in the case of the base classes, all
    writes are atomic:

    >>> with acc.text_atomic_writer() as file:
    ...     file.write(example_text)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = acc.text_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...     file.flush()
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> cm = acc.binary_reader()
    >>> with cm: pass                       # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    FileNotFoundError: ...

    Nothing has been read or written yet:

    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp is None
    True
    >>> acc.last_read_or_written_timestamp is None
    True

    Now, let's really write and read some stuff -- and see that the
    `StampedFileAccessor`-superclass-specific header (conveying the
    metadata specific to that superclass) is also stored...

    >>> with acc.text_atomic_writer() as file:  # Here `encoding` defaults to `utf-8` (see:
    ...     file.write(example_text)            # `open_file()` which has the same feature...)
    ...
    18
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == 321.012399   # (Timestamps "floor-rounded" to 6 dec. places)
    True
    >>> acc.last_read_or_written_timestamp == 321.012399 < 321.0123999 < 321.0123999999 == t
    True

    >>> with acc.text_atomic_writer() as file:
    ...     file.write('Coś ZUPEŁNIE innego...')   # (Again: thanks to atomicity,
    ...     file.flush()                           # error will "rollback" this)
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == 321.012399
    True
    >>> acc.last_read_or_written_timestamp == 321.012399
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(b'Completely DIFFERENT!' * 42)   # (Again: thanks to atomicity,
    ...     file.flush()                                # error will "rollback" this)
    ...     1 / 0                           # doctest: +IGNORE_EXCEPTION_DETAIL
    ...
    Traceback (most recent call last):
      ...
    ZeroDivisionError: ...
    >>> acc.last_read_stamper_id is None
    True
    >>> acc.last_read_timestamp is None
    True
    >>> acc.last_written_timestamp == 321.012399
    True
    >>> acc.last_read_or_written_timestamp == 321.012399
    True

    >>> t = 2048
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got
    b'uwa\xc5\xbcny\nturysta\n...'
    >>> got == example_bytes
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 321.012399              # [sic!]
    True
    >>> acc.last_written_timestamp == 321.012399
    True
    >>> acc.last_read_or_written_timestamp == 321.012399   # [sic!]
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 321.012399
    True
    >>> acc.last_written_timestamp == 2048
    True
    >>> acc.last_read_or_written_timestamp == 2048
    True

    >>> t = 12345.678
    >>> different_custom_stamper_id = b'ffff456789abcdef0123456789abcdef01234567'
    >>> acc2 = SignedStampedFileAccessor(our_path,  # (same path and secret key)
    ...                                  secret_key=our_secret_key,
    ...                                  time_func=fake_time,
    ...                                  own_stamper_id=different_custom_stamper_id)
    ...
    >>> with acc2.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 2048
    True
    >>> acc2.last_written_timestamp is None
    True
    >>> acc2.last_read_or_written_timestamp == 2048
    True

    >>> with acc.text_reader() as file:   # Here `encoding` defaults to `utf-8` (see:
    ...     got = file.read()             # `open_file()` which has the same feature...)
    ...
    >>> got == example_text
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 2048
    True
    >>> acc.last_written_timestamp == 2048
    True
    >>> acc.last_read_or_written_timestamp == 2048
    True

    >>> acc3 = SignedStampedFileAccessor(our_path,
    ...                                  # And now: **different** secret key!
    ...                                  secret_key=our_secret_key + b'?',
    ...                                  time_func=fake_time,
    ...                                  own_stamper_id=different_custom_stamper_id)
    ...

    As said earlier, nothing can be read if the signature does not match
    the content; then the exception `StampedFileAccessor.SignatureError`
    is raised:

    >>> with acc3.binary_reader() as file:  # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...
    >>> acc3.last_read_stamper_id is None
    True
    >>> acc3.last_read_timestamp is None
    True
    >>> acc3.last_written_timestamp is None
    True
    >>> acc3.last_read_or_written_timestamp is None
    True

    >>> with acc3.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> acc3.last_read_stamper_id is None
    True
    >>> acc3.last_read_timestamp is None
    True
    >>> acc3.last_written_timestamp == 12345.678
    True
    >>> acc3.last_read_or_written_timestamp == 12345.678
    True

    >>> with acc.binary_reader() as file:   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...

    >>> acc4 = SignedStampedFileAccessor(our_path,
    ...                                  secret_key=our_secret_key + b'?')
    ...
    >>> with acc4.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True
    >>> acc4.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc4.last_read_timestamp == 12345.678
    True
    >>> acc4.last_written_timestamp is None
    True
    >>> acc4.last_read_or_written_timestamp == 12345.678
    True

    >>> with acc3.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True
    >>> acc3.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc3.last_read_timestamp == 12345.678
    True
    >>> acc3.last_written_timestamp == 12345.678
    True
    >>> acc3.last_read_or_written_timestamp == 12345.678
    True

    >>> with acc2.text_reader() as file:    # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 2048
    True
    >>> acc2.last_written_timestamp is None
    True
    >>> acc2.last_read_or_written_timestamp == 2048
    True

    >>> with acc2.binary_atomic_writer() as file:
    ...     file.write(example_bytes)
    ...
    19
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 2048
    True
    >>> acc2.last_written_timestamp == 12345.678
    True
    >>> acc2.last_read_or_written_timestamp == 12345.678
    True

    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True
    >>> acc.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 12345.678
    True
    >>> acc.last_written_timestamp == 2048
    True
    >>> acc.last_read_or_written_timestamp == 12345.678
    True

    >>> with acc2.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_text
    True
    >>> acc2.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 12345.678
    True
    >>> acc2.last_written_timestamp == 12345.678
    True
    >>> acc2.last_read_or_written_timestamp == 12345.678
    True

    >>> t = 8192.42
    >>> with acc.text_atomic_writer() as file:
    ...     file.write(example_text)
    ...
    18
    >>> acc.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 12345.678
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True

    ***

    A `StampedFileAccessor`-specific *limitation* applies also here:
    *for text I/O*, **only** encodings being supersets of ASCII (such
    as `utf-8`, `windows-1252`, `iso-8859-...`) are supported correctly.
    If an *ASCII-incompatible* encoding is detected, `ValueError` is
    raised:

    >>> with acc.text_reader(encoding='cp500'):
    ...    pass
    ...
    Traceback (most recent call last):
      ...
    ValueError: encoding='cp500' is unsupported as it is not ASCII-compatible

    >>> with acc.text_atomic_writer(encoding='cp500'):
    ...    pass
    ...
    Traceback (most recent call last):
      ...
    ValueError: encoding='cp500' is unsupported as it is not ASCII-compatible

    Obviously, this limitation does *not* apply to *binary I/O*.

    ***

    Note that when reading, as in the case of the `StampedFileAccessor`
    superclass, you can request to check that the file's timestamp is
    not older (not smaller) than the specified value -- then, if it is,
    the exception `StampedFileAccessor.OutdatedError` is raised:

    >>> with acc.binary_reader(minimum_timestamp=8193) as file:
    ...     pass    # Nothing can be read when the timestamp is too old.
    ...                                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.StampedFileAccessor.OutdatedError: ...
    >>> acc.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 12345.678   # (<- ^ not updated because of error)
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True
    >>> with acc.binary_reader(minimum_timestamp=8192) as file:       # Now OK.
    ...     got = file.read()
    ...
    >>> got == example_bytes
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True

    >>> with acc.text_reader(minimum_timestamp=8193) as file:
    ...     pass    # Nothing can be read when the timestamp is too old.
    ...                                     # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.StampedFileAccessor.OutdatedError: ...
    >>> with acc.text_reader(minimum_timestamp=8192) as file:         # Now OK.
    ...     got = file.read()
    ...
    >>> got == example_text
    True

    ***

    Also, the `StampedFileAccessor`-superclass-specific header is "seen"
    by the file methods `seek()` and `tell()`, e.g.:

    >>> with acc.binary_reader() as file:
    ...     told = file.tell()
    ...     seen = file.seek(0)
    ...     told2 = file.tell()
    ...     got = file.read(21)
    ...
    >>> told == 62 and seen == told2 == 0
    True
    >>> got == b'0000000008192.420000\n'  # (timestamp + separator)
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True

    Note, however, that the signature (specific to this class) is *not*
    "seen" by `seek()` and `tell()` at all!

    Also, note that any attempt to change any part of the aforementioned
    header (`StampedFileAccessor`-superclass-specific) will be detected
    -- causing an error and making all changes being "rolled back".

    >>> t = 424242
    >>> with acc.binary_atomic_writer() as file:
    ...     _ = file.write(b'Blah-blah-blah')
    ...     _ = file.seek(0)                     # Trying to *change* header...
    ...     _ = file.write(b'ala ma kota')  # (<- *invalid* as part of timestamp)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True
    >>> with acc.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == 'uważny\nturysta\n...'                   # *No* changes written.
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True

    >>> with acc.text_atomic_writer() as file:
    ...     _ = file.seek(0)                     # Trying to *change* header...
    ...     _ = file.write('0000009876543.210000')  # (<- *valid* as timestamp)
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> with acc.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'uwa\xc5\xbcny\nturysta\n...'           # *No* changes written.
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     _ = file.seek(61)                    # Trying to *change* header...
    ...     _ = file.write(b'ala ma kota')
    ...
    Traceback (most recent call last):
      ...
    RuntimeError: not allowed to change header by overwriting it
    >>> with acc.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == 'uważny\nturysta\n...'                   # *No* changes written.
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 8192.42
    True
    >>> acc.last_read_or_written_timestamp == 8192.42
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     _ = file.seek(62)    # OK, the header will *not* be touched at all.
    ...     _ = file.write(b'ala ma kota???')
    ...
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 8192.42
    True
    >>> acc.last_written_timestamp == 424242
    True
    >>> acc.last_read_or_written_timestamp == 424242
    True
    >>> with acc.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == 'ala ma kota???'    # The content has been written successfully.
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 424242
    True
    >>> acc.last_written_timestamp == 424242
    True
    >>> acc.last_read_or_written_timestamp == 424242
    True

    >>> with acc.binary_atomic_writer() as file:
    ...     _ = file.seek(61)    # OK, the header will be touched, yet *not* effectively changed.
    ...     _ = file.write(b'\nala ma kota')
    ...
    >>> with acc.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == 'ala ma kota'       # The content has been written successfully.
    True
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 424242
    True
    >>> acc.last_written_timestamp == 424242
    True
    >>> acc.last_read_or_written_timestamp == 424242
    True

    ***

    Of course, you can always corrupt your files by tampering with their
    contents manually... :-) And, obviously, it can also be done by some
    other actor/process. *Note*, however, that -- unless they know the
    secret key -- by doing that they will always make your instances of
    `SignedStampedFileAccessor` detect the problem and raise an error
    (`SignedStampedFileAccessor.SignatureError`). This will prevent you
    from even beginning to read any forged data.

    >>> with open(our_path, 'r+b') as f:      # Here we will change some content
    ...     content_before = f.read()         # (without adjusting the signature).
    ...     f.seek(len(content_before) - 2)
    ...     f.write(b'T')        # <- Manually "damaging" the file content...
    ...     f.seek(0)
    ...     content_damaged = f.read()
    ...
    200
    1
    0
    >>> content_before.endswith(b'ala ma kota')
    True
    >>> content_before[-2:]
    b'ta'
    >>> content_damaged[-2:]
    b'Ta'

    >>> with acc2.binary_reader() as file:  # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...
    >>> acc2.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 12345.678
    True
    >>> acc2.last_written_timestamp == 12345.678
    True
    >>> acc2.last_read_or_written_timestamp == 12345.678
    True

    >>> with open(our_path, 'r+b') as f:
    ...     content_before = f.read()
    ...     f.seek(len(content_before) - 2)
    ...     f.write(b't')        # <- Manually "repairing" the file content...
    ...     f.seek(0)
    ...     content_repaired = f.read()
    ...
    200
    1
    0
    >>> content_before[-2:]
    b'Ta'
    >>> content_repaired[-2:]
    b'ta'
    >>> content_repaired.endswith(b'ala ma kota')
    True

    >>> with acc2.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == b'ala ma kota'
    True
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 424242
    True
    >>> acc2.last_written_timestamp == 12345.678
    True
    >>> acc2.last_read_or_written_timestamp == 424242
    True

    >>> with open(our_path, 'a') as f:      # Here we will append some content
    ...     _ = f.write('ala ma kota')      # (without adjusting the signature).
    ...
    >>> with acc.text_reader() as file:     # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...

    >>> with acc2.text_atomic_writer() as file:    # (Let's renovate the file...)
    ...     _ = file.write(example_text)
    ...
    >>> acc2.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 424242
    True
    >>> acc2.last_written_timestamp == 424242
    True
    >>> acc2.last_read_or_written_timestamp == 424242
    True
    >>> with acc2.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes                       # (OK, the file's valid again)
    True
    >>> acc2.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 424242
    True
    >>> acc2.last_written_timestamp == 424242
    True
    >>> acc2.last_read_or_written_timestamp == 424242
    True
    >>> with open(our_path, 'r+b') as f:    # Here we will change some part of
    ...     _ = f.seek(140)                 # the superclass-specific header
    ...     _ = f.write(b'ala ma kota')     # (without adjusting the signature).
    ...
    >>> with acc.binary_reader() as file:   # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...

    >>> with acc2.binary_atomic_writer() as file:  # (Let's renovate the file...)
    ...     _ = file.write(example_bytes)
    ...
    >>> with acc2.binary_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_bytes                       # (OK, the file's valid again)
    True
    >>> with open(our_path, 'r+b') as f:
    ...     _ = f.seek(30)                  # This will damage the signature.
    ...     _ = f.write(b'0124fab3')
    ...
    >>> with acc.text_reader() as file:     # doctest: +IGNORE_EXCEPTION_DETAIL
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    n6lib.file_helpers.SignedStampedFileAccessor.SignatureError: ...

    >>> with acc2.binary_atomic_writer() as file:  # (Let's renovate the file...)
    ...     _ = file.write(example_bytes)
    ...
    >>> with acc2.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_text                        # (OK, the file's valid again)
    True
    >>> with open(our_path, 'r+b') as f:
    ...     _ = f.seek(30)                  # This also will damage the signature.
    ...     _ = f.write(b'ala ma kota')
    ...
    >>> with acc.binary_reader() as file:   # doctest: +ELLIPSIS
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    ValueError: not a valid sig-hexdigest (b'f14a4b4aba6440bb1fa2b02bfb2d07ala ma kota...

    >>> t = 5555.9999999999
    >>> with acc2.text_atomic_writer() as file:    # (Let's renovate the file...)
    ...     _ = file.write(example_text)
    ...
    >>> acc2.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 424242
    True
    >>> acc2.last_written_timestamp == 5555.999999
    True
    >>> acc2.last_read_or_written_timestamp == 5555.999999
    True
    >>> with acc2.text_reader() as file:
    ...     got = file.read()
    ...
    >>> got == example_text                        # (OK, the file's valid again)
    True
    >>> acc2.last_read_stamper_id == different_custom_stamper_id
    True
    >>> acc2.last_read_timestamp == 5555.999999
    True
    >>> acc2.last_written_timestamp == 5555.999999
    True
    >>> acc2.last_read_or_written_timestamp == 5555.999999
    True
    >>> with open(our_path, 'wt') as f:   # Obviously, this also will damage the signature.
    ...     _ = f.write('ala ma kota')
    ...
    >>> with acc.binary_reader() as file:
    ...     pass  # Nothing can be read when the signature verification is negative.
    ...
    Traceback (most recent call last):
      ...
    ValueError: not a valid sig-hexdigest (b'ala ma kota' does not match the expected pattern)
    >>> acc.last_read_stamper_id == our_custom_stamper_id
    True
    >>> acc.last_read_timestamp == 424242
    True
    >>> acc.last_written_timestamp == 424242
    True
    >>> acc.last_read_or_written_timestamp == 424242
    True

    ***

    In the following example we inspect some internal details (note that
    they *may change when the implementation changes*).

    >>> with acc2.text_atomic_writer() as file:
    ...     file.write(example_text)
    ...
    18
    >>> with open(our_path, 'rb') as f:
    ...     sig_hexdigest = f.read(128)
    ...     sig_sep = f.read(1)
    ...     h_timestamp = f.read(20)
    ...     h_sep1 = f.read(1)
    ...     h_stamper_id = f.read(40)
    ...     h_sep2 = f.read(1)
    ...     body = f.read()
    ...
    >>> sig_hexdigest == hashlib.blake2b(
    ...     h_timestamp + h_sep1 + h_stamper_id + h_sep2 + body,
    ...     key=our_secret_key,
    ... ).hexdigest().encode('ascii')
    True
    >>> sig_sep == h_sep1 == h_sep2 == b'\n'
    True
    >>> h_timestamp == b'0000000005555.999999' and float(h_timestamp) == 5555.999999
    True
    >>> h_stamper_id == different_custom_stamper_id
    True
    >>> body == example_bytes
    True

    """

    #
    # Public interface extensions

    class SignatureError(ValueError):
        """Raised when the file's signature verification fails."""

    def __init__(self,
                 path: AnyPath,
                 *,
                 secret_key: bytes,
                 **kwargs):
        super().__init__(path, **kwargs)
        self._secret_key = secret_key


    #
    # Non-public stuff extensions

    class _HashUpdatingWriter:

        def __init__(self, file: BinaryIO, hash_obj: HashObj):
            self._file = file
            self._hash_obj = hash_obj

        def write(self, data: bytes) -> int:
            self._hash_obj.update(data)
            return self._file.write(data)

    @staticmethod
    def _make_hash_obj(secret_key) -> HashObj:
        # Note: the BLAKE2 algorithm supports *keyed mode* -- "a faster
        # and simpler replacement for HMAC" (see the docs of `hashlib`).
        BLAKE2_KEY_MAX_LENGTH = 64  # noqa
        blake2_key = secret_key[:BLAKE2_KEY_MAX_LENGTH]
        secret_rest = secret_key[BLAKE2_KEY_MAX_LENGTH:]
        hash_obj = hashlib.blake2b(secret_rest, key=blake2_key)
        assert isinstance(hash_obj, HashObj)
        return hash_obj

    def _get_meta_field_properties(self) -> dict[str, StampedFileAccessor._FieldProps]:
        example_hash_obj = self._make_hash_obj(secret_key=b'example')
        hexdigest_length = 2 * example_hash_obj.digest_size
        meta_field_properties = super()._get_meta_field_properties() | {
            'sig-hexdigest': self._FieldProps(
                regex=re.compile(rb'\A[0-9a-f]{%d}\Z' % hexdigest_length),
                length=hexdigest_length,
            ),
        }
        if __debug__:
            example_hexdigest = example_hash_obj.hexdigest().encode('ascii')
            assert meta_field_properties['sig-hexdigest'].regex.search(example_hexdigest)
            assert meta_field_properties['sig-hexdigest'].length == len(example_hexdigest)
        return meta_field_properties

    def _get_names_of_supported_open_kwargs(self, mode: str) -> set[str]:
        if self._is_atomic_writer_mode(mode):
            # (let's be explicit; only these arguments are supported
            # by `tempfile.NamedTemporaryFile()` -- see: the method
            # `_get_atomic_writer_underlying_cm()` defined below...)
            names = {'buffering'}
            if self._is_text_mode(mode):
                names.update({'encoding', 'errors', 'newline'})
            return names
        return super()._get_names_of_supported_open_kwargs(mode)

    @contextlib.contextmanager
    def _pure_reader_cm(self,
                        path: Path,
                        mode: str,
                        open_kwargs: KwargsDict,
                        **kwargs) -> Generator[IO]:

        with tempfile.NamedTemporaryFile('wb', prefix=__name__) as temp_writer:
            hash_obj = self._make_hash_obj(self._secret_key)
            hash_upd_writer = self._HashUpdatingWriter(temp_writer, hash_obj)

            with open(path, 'rb') as target_reader:
                sig_hexdigest = self._consume_signature(target_reader)
                shutil.copyfileobj(target_reader, hash_upd_writer)

            self._verify_sig_hexdigest(hash_obj, sig_hexdigest)

            temp_writer.flush()
            temp_path = Path(temp_writer.name)
            with super()._pure_reader_cm(temp_path, mode, open_kwargs, **kwargs) as file:

                yield file

    def _consume_signature(self, file: IO) -> bytes:
        hexdigest = self._consume_meta_field('sig-hexdigest', file)
        self._consume_meta_field('separator', file)
        return hexdigest

    def _verify_sig_hexdigest(self, hash_obj: HashObj, sig_hexdigest: bytes) -> None:
        computed_hexdigest = hash_obj.hexdigest().encode('ascii')
        if not secrets.compare_digest(sig_hexdigest, computed_hexdigest):
            raise self.SignatureError('signature does not match rest of file content')

    @contextlib.contextmanager
    def _atomic_writer_cm(self,
                          path: Path,
                          mode: str,
                          open_kwargs: KwargsDict,
                          **kwargs) -> Generator[IO]:

        with AtomicallySavedFile(path, 'wb') as target_writer:

            with super()._atomic_writer_cm(path, mode, open_kwargs, **kwargs) as file:
                # (`file` is supposed to be from a `NamedTemporaryFile`; see the
                # `_get_atomic_writer_underlying_cm()` method defined below...)
                assert getattr(file, 'name', '').startswith(tempfile.gettempdir())

                yield file

                dummy_signature = self._prepare_new_signature(hash_obj=None)
                assert target_writer.tell() == 0
                target_writer.write(dummy_signature)
                target_writer.flush()
                after_sig_pos = target_writer.tell()

                hash_obj = self._make_hash_obj(self._secret_key)
                hash_upd_writer = self._HashUpdatingWriter(target_writer, hash_obj)

                file.flush()
                with open(file.name, 'rb') as temp_reader:
                    shutil.copyfileobj(temp_reader, hash_upd_writer)

            real_signature = self._prepare_new_signature(hash_obj)
            assert len(real_signature) == len(dummy_signature)
            target_writer.flush()
            target_writer.seek(0)
            target_writer.write(real_signature)
            target_writer.flush()
            assert after_sig_pos == target_writer.tell()

    def _get_atomic_writer_underlying_cm(self,
                                         path: Path,
                                         mode: str,
                                         open_kwargs: KwargsDict) -> ContextManager[IO]:
        # Note: here `path` is ignored.
        return tempfile.NamedTemporaryFile(mode, prefix=__name__, **open_kwargs)

    def _prepare_new_signature(self, hash_obj: Optional[HashObj]) -> bytes:
        sig_hexdigest = (
            hash_obj.hexdigest().encode('ascii') if hash_obj is not None
            else self._meta_field_properties['sig-hexdigest'].length * b'0')
        return b'%b%b' % (sig_hexdigest, self._FIELD_SEPARATOR)


#
# Other helpers
#

def as_path(path: AnyPath) -> Path:
    """
    Convert an object representing a filesystem path to an instance of
    `pathlib.Path`.

    Args:
        `path`:
            An object representing a filesystem path: a `str` or `bytes`
            object, or any *path-like* object (e.g., a `pathlib.Path`).
            By *path-like* object we mean an object whose class provides
            an implementation of `__fspath__()` (which should return a
            `str` or `bytes` object; see the docs of `os.PathLike`...).

    Returns:
        A `pathlib.Path` instance derived from the given `path`.

    >>> p1 = as_path('/some/thing')
    >>> p2 = as_path(b'/some/thing/')
    >>> import pathlib
    >>> p3 = as_path(pathlib.PurePath('/some/thing/'))
    >>> p4 = as_path(pathlib.Path('/some/thing'))
    >>> class MyPathLike:
    ...     def __init__(self, fspath):
    ...         self._fspath = fspath
    ...     def __fspath__(self):
    ...         return self._fspath
    ...
    >>> p5 = as_path(MyPathLike('/some/thing///'))
    >>> p6 = as_path(MyPathLike(b'///some/thing'))
    >>> isinstance(p1, pathlib.Path) and p1 == pathlib.Path('/some/thing')
    True
    >>> isinstance(p2, pathlib.Path) and p2 == pathlib.Path('/some/thing')
    True
    >>> isinstance(p3, pathlib.Path) and p3 == pathlib.Path('/some/thing')
    True
    >>> isinstance(p4, pathlib.Path) and p4 == pathlib.Path('/some/thing')
    True
    >>> isinstance(p5, pathlib.Path) and p5 == pathlib.Path('/some/thing')
    True
    >>> isinstance(p6, pathlib.Path) and p6 == pathlib.Path('/some/thing')
    True
    """
    return Path(os.fsdecode(path))

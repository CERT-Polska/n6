# Copyright (c) 2013-2021 NASK. All rights reserved.

import io
import gzip
import os.path
import tempfile
import zipfile

from n6lib.common_helpers import (
    as_bytes,
    as_unicode,
)


# TODO: remove this function, replacing its
#    uses with `gzip.decompress(...)` calls.
def gzip_decompress(gzipped):
    """
    Decompress GZip-compressed data (note: in Python 3 this function
    just calls `gzip.decompress(gzipped)`).

    Args:
        `gzipped`: GZip-compressed data as a *bytes-like* object.

    Returns:
        Decompressed data as a `bytes` object.

    Raises:
        OSError (or subclasses), EOFError:
            as gzip.GzipFile can raise them for invalid input.
    """
    return gzip.decompress(gzipped)


def iter_unzip_from_bytes(zipped,
                          *,
                          password=None,
                          filenames=None,
                          yielding_with_dirs=False):
    """
    Extract files from a ZIP archive.

    Args:
        `zipped` (typically a `bytes`/`bytearray`; *cannot* be a `str`):
            The ZIP archive as a *bytes-like* object.

    Kwargs:
        `password` (optional; if given, typically a `str`/`bytes`):
            The password to extract encrypted files. If given (and not
            `None`), it will be, firstly, coerced to `bytes` using the
            `as_bytes()` helper from `n6lib.common_helpers` (by
            performing an `as_bytes(password, 'strict')` call).
        `filenames` (optional; if given, typically a list of `str`/`bytes`):
            A container (e.g., a sequence or a set) of the filenames
            (without dir parts) we are interested in. If given (and
            not `None`) then only the specified files will be extracted,
            ignoring non-existent ones. Each filename will be, firstly,
            coerced to `str` using the `as_unicode()` helper from
            `n6lib.common_helpers`.                                     # maybe TODO: add support for Py3's *path*/*path-like* objects...
        `yielding_with_dirs` (default: False):
            If False -- dir names will be stripped off from yielded file names.
            If True -- file names will be yielded as found in the archive
            (including dir parts).

    Yields:
        Pairs: `(<file name (a str obj)>, <file content (a bytes obj)>).`

    Raises:
        zipfile.BadZipfile, EOFError:
            as zipfile.ZipFile can raise it for invalid input.
        RuntimeError (or subclasses, in particular NotImplementedError):
            as zipfile.ZipFile can raise it for unsupported input
            features, as well as for unspecified or incorrect password.
    """
    if password is not None:
        password = as_bytes(password, 'strict')
    if filenames is not None:
            filenames = frozenset(map(as_unicode, filenames))
    zfile = zipfile.ZipFile(io.BytesIO(zipped))
    for fullname in zfile.namelist():
        assert isinstance(fullname, str)
        basename = (os.path.basename(fullname) if fullname else fullname)
        assert isinstance(basename, str)
        if filenames is None or basename in filenames:
            content = zfile.read(fullname, pwd=password)
            yield (fullname if yielding_with_dirs else basename), content

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import cStringIO
import gzip
import os.path
import tempfile
import zipfile


def gunzip_from_string(gzipped):
    """
    Decompress GZip-compressed data.

    Args:
        `gzipped`: GZip-compressed data as a string.

    Returns:
        Decompressed data as a string.

    Raises:
        IOError, EOFError:
            as gzip.GzipFile can raise them for invalid input.
    """
    with tempfile.TemporaryFile(mode='w+b') as f:
        f.write(gzipped)
        f.flush()
        f.seek(0)
        gzfile = gzip.GzipFile(mode='rb', fileobj=f)
        return gzfile.read()


def iter_unzip_from_string(zipped, password=None, filenames=None,
                           yielding_with_dirs=False):
    """
    Extract files from a ZIP archive.

    Args:
        `zipped`:
            The ZIP archive as a string.
        `password` (optional):
            The password to extract encrypted files.
        `filenames` (optional):
            A sequence of file names we are interested in.
            If specified -- only the specified files will be extracted.
            Non-existent files are ignored.
        `yielding_with_dirs` (default: False):
            If False -- dir names will be stripped off from yielded file names.
            If True -- file names will be yielded as found in the archive
            (including dir parts).

    Yields:
        Pairs: (<file fullname>, <file content>).

    Raises:
        zipfile.BadZipfile:
            as zipfile.ZipFile can raise it for invalid input.
        RuntimeError:
            as zipfile.ZipFile can raise it for lacking or incorrect password.
    """
    zfile = zipfile.ZipFile(cStringIO.StringIO(zipped))
    for fullname in zfile.namelist():
        basename = (os.path.basename(fullname) if fullname else fullname)
        if not filenames or basename in filenames:
            content = zfile.read(fullname, pwd=password)
            yield (fullname if yielding_with_dirs else basename), content

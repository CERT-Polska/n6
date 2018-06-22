# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.
#
# For some code in this module:
# Copyright (c) 2001-2013 Python Software Foundation. All rights reserved.
# (For more information -- see some comments below...)

import base64
import binascii
import datetime
import email.iterators
import email.message
import email.utils
import os
import quopri
import re
import uu
import zipfile
from cStringIO import StringIO

from n6lib.log_helpers import get_logger
from n6lib.unpacking_helpers import iter_unzip_from_string, gunzip_from_string


LOGGER = get_logger(__name__)


class NoMatchingFileError(ValueError):
    """
    Raised by EmailMessage.get_matching_file_content if no file matches.
    """


# TODO: doc
class EmailMessage(email.message.Message):

    #
    # Some constants

    ZIP_CONTENT_TYPES = frozenset([
        'application/zip',
        'application/x-zip',
        'application/x-zip-compressed',
    ])
    ZIP_FILENAME_EXTENSIONS = frozenset([
        '.zip',
    ])
    GZIP_CONTENT_TYPES = frozenset([
        'application/gzip',
        'application/gzip-compressed',
        'application/gzipped',
        'application/x-gunzip',
        'application/x-gzip',
        'application/x-gzip-compressed',
        'gzip/document',
    ])
    GZIP_FILENAME_EXTENSIONS = frozenset([
        '.gzip',
        '.gz',
    ])

    #
    # Instantiation helpers

    @classmethod
    def from_string(cls, s):
        return email.message_from_string(s, _class=cls)

    @classmethod
    def from_file(cls, fp):
        return email.message_from_file(fp, _class=cls)

    #
    # Additional helper methods

    def get_utc_timestamp(self):
        """
        Parse the 'Date' header and return UTC time as float, like time.time().
        """
        return email.utils.mktime_tz(email.utils.parsedate_tz(self['Date']))

    def get_utc_datetime(self):
        """
        Parse the 'Date' header and return UTC time as datetime.datetime.
        """
        # NOTE: this method returns a *UTC* date + time (*unlike*
        # MailTransfer.get_date() from the old data-repo which
        # seem to compute dates using local times...)
        return datetime.datetime.utcfromtimestamp(self.get_utc_timestamp())

    def get_subject(self):
        """
        Get subject from msg, return str or None.
        """
        for item in self._headers:
            if item[0] == 'Subject':
                return " ".join(item[1].split())
        return None

    def get_matching_file_content(self, filename_regex=None,
                                  maintype=None, subtype=None):
        messages = self.iter_matching_messages(filename_regex,
                                               maintype, subtype)
        items = ((name, content)
                 for msg in messages
                     for name, content in msg.iter_filenames_and_contents())
        first_item = next(items, None)
        if first_item is None:
            raise NoMatchingFileError('No file matches the criteria: '
                                      'filename_regex={0!r}, maintype={1!r}, '
                                      'subtype={2!r}'.format(
                                          filename_regex, maintype, subtype))
        name, content = first_item
        second_item = next(items, None)
        if second_item is not None:
            ### CR: rethink if an exception shouldn't be raised
            LOGGER.warning('More than one file matched but only '
                           'one (named: %r) will be used', name)
        return content

    def iter_matching_messages(self, filename_regex=None,
                               maintype=None, subtype=None):
        messages = (self.walk() if maintype is None else
                    email.iterators.typed_subpart_iterator(self,
                                                           maintype, subtype))
        if filename_regex is None:
            return messages
        if isinstance(filename_regex, basestring):
            filename_regex = re.compile(filename_regex)
        return (msg for msg, filename in ((msg, msg.get_filename())
                                          for msg in messages)
                if (filename is not None and
                    filename_regex.search(filename) is not None))

    def iter_filenames_and_contents(self, multifile_unpacking=False):
        if self.is_multipart():
            for msg in self.get_payload():
                # recursive calls on sub-messages
                # (NOTE that all of them are instances of this class
                # because all have been created within a call of this
                # class' from_string()/from_file())
                for name, content in msg.iter_filenames_and_contents(
                             multifile_unpacking=multifile_unpacking):
                    yield name, content
        else:
            content_type = self.get_content_type()
            payload = self.get_decoded_payload()
            filename = self.get_filename(None)
            ext = os.path.splitext(filename or '')[1].lower()
            # un-Gzip if necessary
            if (ext in self.GZIP_FILENAME_EXTENSIONS or
                  content_type in self.GZIP_CONTENT_TYPES):
                try:
                    payload = gunzip_from_string(payload)
                except (IOError, EOFError) as exc:
                    LOGGER.warning('Could not decompress file %r using GZip '
                                   'decoder (%s)', filename, exc)
            # un-ZIP if necessary
            elif (ext in self.ZIP_FILENAME_EXTENSIONS or
                  content_type in self.ZIP_CONTENT_TYPES):
                try:
                    names_and_contents = list(iter_unzip_from_string(payload))
                except (zipfile.BadZipfile, RuntimeError) as exc:
                    LOGGER.warning('Could not unpack file %r using ZIP '
                                   'decoder (%s)', filename, exc)
                else:
                    if not names_and_contents:
                        LOGGER.warning('No files in archive %r', filename)
                        # yielding nothing
                        return
                    if multifile_unpacking:
                        # all files from the archive will be yielded (with
                        # their names prefixed with archive file name + '/')
                        name_pattern = (filename or '') + '/{0}'
                        for name, content in names_and_contents:
                            yielded_name = name_pattern.format(name)
                            LOGGER.debug('Yielding file %r...', yielded_name)
                            yield yielded_name, content
                        return
                    # only one file from the archive will be yielded
                    name, payload = names_and_contents[0]
                    if len(names_and_contents) > 1:
                        LOGGER.warning('Archive %r contains more than '
                                       'one file but only one (named '
                                       '%r in the archive) will be '
                                       'yielded as the payload of %r',
                                       filename, name, filename)
            LOGGER.debug('Yielding file %r...', filename)
            yield filename, payload

    def get_decoded_payload(self):
        """
        As get_payload(decode=True) but logging warnings on decoding failures.
        """
        # copied from Py2.7's email.message.Message.get_payload() and adjusted
        if self.is_multipart():
            return self.get_payload()[0].get_payload(decode=True)
        payload = self._payload
        cte = self.get('content-transfer-encoding', '').lower()
        if cte == 'quoted-printable':
            payload = quopri.decodestring(payload)
        elif cte == 'base64':
            if payload:
                try:
                    payload = base64.decodestring(payload)
                except binascii.Error:
                    LOGGER.warning('Could not decode the payload using base64'
                                   ' => not decoding')
                    LOGGER.debug('The payload: %r', payload)
        elif cte in ('x-uuencode', 'uuencode', 'uue', 'x-uue'):
            sfp = StringIO()
            try:
                uu.decode(StringIO(payload + '\n'), sfp, quiet=True)
                payload = sfp.getvalue()
            except uu.Error:
                LOGGER.warning('Could not decode the payload using %s'
                               ' => not decoding', cte)
                LOGGER.debug('The payload: %r', payload)
        elif cte not in ('', '7bit', '8bit', 'binary'):
            LOGGER.warning('Unsupported content-transfer-encoding: %s'
                           ' => not decoding', cte)
            LOGGER.debug('The payload: %r', payload)
        return payload

    @staticmethod
    def get_single_regexp_match(payload, pattern, regex_flags=re.MULTILINE | re.DOTALL):
        regex = re.compile(pattern, flags=regex_flags)
        return regex.search(payload)

    @staticmethod
    def get_regexp_match(payload, patterns):
        """Parse multiline"""
        for i in patterns:
            regex = re.compile(i, flags=re.MULTILINE | re.DOTALL)
            for match in regex.finditer(payload):
                return match.groups()

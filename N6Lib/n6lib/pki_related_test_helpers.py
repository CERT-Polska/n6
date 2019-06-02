# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import glob
import os.path as osp
import subprocess

from pkg_resources import Requirement, resource_filename, cleanup_resources

from n6lib.common_helpers import (
    memoized,
    read_file,
)
from n6lib.const import CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM
from n6lib.datetime_helpers import parse_iso_datetime_to_utc



# This module contains helpers related to loading example PKI data from
# the "N6Lib/n6lib/tests/certs_and_requests_for_testing/*" directory.
#
# See also: the `n6lib.ldap_related_test_helpers`.



#
# Abstract code components

# note: this is a kind of "subclassable function", not a typical class
class _AbstractPKITestDataFileLoader(object):

    #
    # the actual callable (implemented as a kind of "pattern method")

    def __new__(cls, *args, **kwargs):
        params = cls.get_params(*args, **kwargs)
        file_path_glob = cls._get_file_path_glob(
            cls.file_pattern,
            params)
        file_path = cls._glob_to_file_path(file_path_glob)
        return cls.get_data(file_path, params)

    #
    # abstract attributes (that *must* be set in concrete subclasses)

    ext = None   # 'pem' or 'der'
    what = None  # 'cert' or 'csr' or 'key'
    file_pattern = None

    #
    # overridable/extendable methods
    # (that *can* be overridden/extended in concrete subclasses)

    @classmethod
    def get_params(cls, ca_label=None):
        params = {
            'ext': cls.ext,
            'what': cls.what,
        }
        if ca_label is not None:
            params['ca_label'] = ca_label
        return params

    @classmethod
    def get_data(cls, file_path, params):
        return cls._memoized_read_file(file_path)

    #
    # internal helpers

    @staticmethod
    def _get_file_path_glob(file_pattern, params):
        return osp.join(
            _get_pki_test_data_path(),
            file_pattern.format(**params))

    @staticmethod
    def _glob_to_file_path(file_path_glob):
        matching_paths = glob.glob(file_path_glob)
        if not matching_paths:
            raise IOError(
                'there is no test data file '
                'matching the {!r} glob pattern'
                .format(file_path_glob))
        if len(matching_paths) > 1:
            raise IOError(
                'there are more than one test data file '
                'matching the {!r} glob pattern'
                .format(file_path_glob))
        [file_path] = matching_paths
        return file_path

    @staticmethod
    @memoized
    def _memoized_read_file(file_path):
        return read_file(file_path)



class _LoadCAMixin(object):

    file_pattern = 'ca-{what}-{ca_label}.{ext}'



class _LoadByCALabelAndCertSerialMixin(object):

    file_pattern = '*-{what}---{ca_label}-{serial}.{ext}'

    @classmethod
    def get_params(cls, ca_label, serial):
        # noinspection PyUnresolvedReferences
        params = super(_LoadByCALabelAndCertSerialMixin, cls).get_params(ca_label)
        params['serial'] = serial
        return params



class _LoadByCertLabelMixin(object):

    file_pattern = '{cert_label}-{what}---*-*.{ext}'

    @classmethod
    def get_params(cls, cert_label):
        # noinspection PyUnresolvedReferences
        params = super(_LoadByCertLabelMixin, cls).get_params()
        params['cert_label'] = cert_label
        return params



class _LoadCertMetadataMixin(object):

    ext = 'pem'
    what = 'cert'

    @classmethod
    def get_data(cls, file_path, params):
        return {
            'ca_label': cls._get_ca_label(file_path),
            'cert_label': cls._get_cert_label(file_path),
            'serial_number': cls._get_serial_number(file_path),
            'usage': cls._get_usage(file_path),
            'valid_from': cls._get_valid_from(file_path),
            'expires_on': cls._get_expires_on(file_path),
            'subject_dict': cls._get_subject_dict(file_path),
        }

    @classmethod
    def _get_ca_label(cls, file_path):
        return osp.basename(file_path).split('-{0}---'.format(cls.what), 1)[1].rsplit('-', 1)[0]

    @classmethod
    def _get_cert_label(cls, file_path):
        return osp.basename(file_path).split('-{0}---'.format(cls.what), 1)[0]

    @classmethod
    def _get_serial_number(cls, file_path):
        [serial] = cls._bash(
            r"""openssl x509 -noout -in "{0}" """
            r"""-serial | sed -r 's/\bserial=//'"""
            .format(file_path)).splitlines()
        return serial.lower().zfill(CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM)

    @classmethod
    def _get_usage(cls, file_path):
        usage = 0
        purposes = cls._bash(
            r"""openssl x509 -noout -in "{0}" -purpose"""
            .format(file_path)).splitlines()
        if 'SSL client : Yes' in purposes:
            usage += 1
        if 'SSL server : Yes' in purposes:
            usage += 2
        assert usage in (1, 3)
        return usage

    @classmethod
    def _get_valid_from(cls, file_path):
        [valid_from_str] = cls._bash(
            r"""LC_ALL=C date -u -d "`openssl x509 -noout """
            r"""-in "{0}" -startdate """
            r"""| sed -r 's/\w+=(.*)/\1/'`" '+%Y-%m-%dT%H:%M:%S'"""
            .format(file_path)).splitlines()
        return parse_iso_datetime_to_utc(valid_from_str)

    @classmethod
    def _get_expires_on(cls, file_path):
        [expires_on_str] = cls._bash(
            r"""LC_ALL=C date -u -d "`openssl x509 -noout """
            r"""-in "{0}" -enddate """
            r"""| sed -r 's/\w+=(.*)/\1/'`" '+%Y-%m-%dT%H:%M:%S'"""
            .format(file_path)).splitlines()
        return parse_iso_datetime_to_utc(expires_on_str)

    @classmethod
    def _get_subject_dict(cls, file_path):
        subject_str = cls._get_subject_str(file_path)
        return cls._parse_subject(subject_str)

    @classmethod
    def _get_subject_str(cls, file_path):
        [subject_str] = cls._bash(
            r"""openssl x509 -noout -in "{0}" """
            r"""-subject -nameopt RFC2253 """
            r"""| sed -r 's/\w+=\s*(.*)/\1/'"""
            .format(file_path)).splitlines()
        return subject_str

    @classmethod
    def _parse_subject(cls, subject_str):
        raw_items = subject_str.split(',')
        key_val_pairs = (item.split('=', 1) for item in raw_items)
        return {key.lower(): val
                for key, val in key_val_pairs}

    @staticmethod
    @memoized
    def _bash(cmd):
        return subprocess.check_output(['/bin/bash', '-c', cmd])



#
# Actual helpers

class _load_ca_cert_pem(_LoadCAMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'cert'

class _load_ca_cert_der(_LoadCAMixin, _AbstractPKITestDataFileLoader):
    ext = 'der'
    what = 'cert'

class _load_ca_key_pem(_LoadCAMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'key'

class _load_ca_ssl_config_cnf(_LoadCAMixin, _AbstractPKITestDataFileLoader):
    ext = 'cnf'
    what = 'config'



class _load_csr_pem(_LoadByCALabelAndCertSerialMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'csr'

class _load_csr_pem_by_label(_LoadByCertLabelMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'csr'



class _load_cert_pem(_LoadByCALabelAndCertSerialMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'cert'

class _load_cert_pem_by_label(_LoadByCertLabelMixin, _AbstractPKITestDataFileLoader):
    ext = 'pem'
    what = 'cert'

class _load_cert_der(_LoadByCALabelAndCertSerialMixin, _AbstractPKITestDataFileLoader):
    ext = 'der'
    what = 'cert'

class _load_cert_der_by_label(_LoadByCertLabelMixin, _AbstractPKITestDataFileLoader):
    ext = 'der'
    what = 'cert'



class _load_cert_metadata(_LoadByCALabelAndCertSerialMixin,
                          _LoadCertMetadataMixin,
                          _AbstractPKITestDataFileLoader):
    """
    >>> from datetime import datetime as dt
    >>> _load_cert_metadata('service-1', '1234') == {
    ...     'cert_label': 'svrc-one',
    ...     'ca_label': 'service-1',
    ...     'serial_number': '00000000000000001234',
    ...     'valid_from': dt(2015, 11, 26, 20, 29, 36),
    ...     'expires_on': dt(2030, 7, 22, 0, 0),
    ...     'usage': 3,
    ...     'subject_dict': {
    ...         'o': 'Naukowa i Akademicka Siec Komputerowa',
    ...         'ou': 'CERT Polska',
    ...         'cn': 'example.com',
    ...     },
    ... }
    True
    """


class _load_cert_metadata_by_label(_LoadByCertLabelMixin,
                                   _LoadCertMetadataMixin,
                                   _AbstractPKITestDataFileLoader):
    """
    >>> from datetime import datetime as dt
    >>> _load_cert_metadata_by_label('user-one') == {
    ...     'cert_label': 'user-one',
    ...     'ca_label': 'client-2',
    ...     'serial_number': '00000000000000009abc',
    ...     'valid_from': dt(2015, 11, 26, 23, 59, 52),
    ...     'expires_on': dt(2030, 7, 22, 0, 0),
    ...     'usage': 1,
    ...     'subject_dict': {
    ...         'o': 'x.example.jp',
    ...         'cn': 'somebody@example.eu',
    ...     },
    ... }
    True
    """



def _get_pki_test_data_path():
    try:
        return resource_filename(
            Requirement.parse("n6lib"),
            'n6lib/tests/certs_and_requests_for_testing/')
    finally:
        cleanup_resources()



def _parse_crl_pem(crl_pem):
    process = subprocess.Popen(
        [
            'openssl', 'crl',
            '-noout',
            '-text',
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process.communicate(crl_pem)



if __name__ == "__main__":
    import doctest
    doctest.testmod()

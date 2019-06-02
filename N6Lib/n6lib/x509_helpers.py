# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

from M2Crypto import X509
from M2Crypto.m2 import (
    NID_organizationName as ORG,
    NID_organizationalUnitName as OU,
    NID_commonName as CN,
    X509_PURPOSE_SSL_CLIENT,
    X509_PURPOSE_SSL_SERVER,
)

from n6lib.datetime_helpers import datetime_utc_normalize
from n6lib.common_helpers import int_id_to_hex, normalize_hex_id


_THIS_MODULE = __name__   # for patching in doctest

_SUBJECT_KEY_TO_NID = {
    'cn': CN,
    'o': ORG,
    'ou': OU,
}
_NID_TO_SUBJECT_KEY = {
    nid: key for key, nid in _SUBJECT_KEY_TO_NID.iteritems()}


FORMAT_DER = X509.FORMAT_DER
FORMAT_PEM = X509.FORMAT_PEM

CLIENT_USAGE_FLAG = 1
SERVER_USAGE_FLAG = 2


load_cert = X509.load_cert

load_cert_string = X509.load_cert_string

load_request = X509.load_request

load_request_string = X509.load_request_string

normalize_hex_serial_number = normalize_hex_id

serial_number_int_to_hex = int_id_to_hex


class UnexpectedCertificateDataError(ValueError):
    """To be raised when a certificate contains unexpected data."""


def verify_cert(cert, ca_cert):
    return bool(cert.verify(ca_cert.get_pubkey()))


def verify_request(request, cert):
    return bool(request.verify(cert.get_pubkey()))


def get_cert_serial_number_as_hex(cert, min_digit_num=0):
    """
    >>> class CertMock:
    ...     @staticmethod
    ...     def get_serial_number(): return mock_sn
    ...
    >>> mock_sn = 1
    >>> get_cert_serial_number_as_hex(CertMock)
    '1'
    >>> mock_sn = 1L
    >>> get_cert_serial_number_as_hex(CertMock)
    '1'
    >>> mock_sn = 31
    >>> get_cert_serial_number_as_hex(CertMock, 0)
    '1f'
    >>> mock_sn = 31L
    >>> get_cert_serial_number_as_hex(CertMock, 1)
    '1f'
    >>> mock_sn = 31
    >>> get_cert_serial_number_as_hex(CertMock, 2)
    '1f'
    >>> mock_sn = 31
    >>> get_cert_serial_number_as_hex(CertMock, 3)
    '01f'
    >>> mock_sn = 31
    >>> get_cert_serial_number_as_hex(CertMock, 10)
    '000000001f'
    >>> mock_sn = 22539340290692258087863249L
    >>> get_cert_serial_number_as_hex(CertMock)
    '12a4e415e1e1b36ff883d1'
    >>> mock_sn = 22539340290692258087863249L
    >>> get_cert_serial_number_as_hex(CertMock, 30)
    '0000000012a4e415e1e1b36ff883d1'
    >>> mock_sn = 0
    >>> get_cert_serial_number_as_hex(CertMock)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: ...
    >>> mock_sn = -1000L
    >>> get_cert_serial_number_as_hex(CertMock)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: ...
    """
    sn_int = get_cert_serial_number_as_int(cert)
    return serial_number_int_to_hex(sn_int, min_digit_num)


def get_cert_serial_number_as_int(cert):
    """
    >>> class CertMock:
    ...     @staticmethod
    ...     def get_serial_number(): return mock_sn
    ...
    >>> mock_sn = 31
    >>> get_cert_serial_number_as_int(CertMock)
    31
    >>> mock_sn = 31L
    >>> get_cert_serial_number_as_int(CertMock)
    31
    >>> mock_sn = 22539340290692258087863249L
    >>> get_cert_serial_number_as_int(CertMock)
    22539340290692258087863249L
    >>> mock_sn = 0
    >>> get_cert_serial_number_as_int(CertMock)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: ...
    >>> mock_sn = -1000L
    >>> get_cert_serial_number_as_int(CertMock)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: ...
    """
    sn_int = int(cert.get_serial_number())
    if sn_int < 1:
        raise UnexpectedCertificateDataError(
            'non-positive serial number: {0}'.format(sn_int))
    return sn_int


def is_ca_cert(cert):
    return bool(cert.check_ca())


def is_client_cert(cert):
    return bool(cert.check_purpose(X509_PURPOSE_SSL_CLIENT, 0))


def is_server_cert(cert):
    return bool(cert.check_purpose(X509_PURPOSE_SSL_SERVER, 0))


def get_cert_not_after(cert):
    return datetime_utc_normalize(cert.get_not_after().get_datetime())


def get_cert_not_before(cert):
    return datetime_utc_normalize(cert.get_not_before().get_datetime())


def get_cert_subject_dict(cert_or_request, include_ou=False):
    """
    Get a dict of n6-relevant certificate subject components (RDN values).

    Args/kwargs:
        `cert_or_request`:
            An M2Crypto.X509.X509 object (containing a certificate) or
            a M2Crypto.X509.Request object (containing a CSR).
        `include_ou` (default: False):
            Whether the 'ou' item should be required and included.

    Returns:
        A dict containing the items: 'cn', 'o' and maybe 'ou' (the
        latest only if `include_ou` is true).

    Raises:
        UnexpectedCertificateDataError:
            If any of the required subject components ('o'/'cn' and
            optionally 'ou') is missing, or there is more than one value
            for any of the components.

    >>> from mock import (
    ...     MagicMock, call, patch, sentinel,
    ... )
    >>> def get_single_x509_rdn_value_side_effect(x509_name, nid):
    ...     return '<value of {}>'.format(_NID_TO_SUBJECT_KEY[nid])
    ...
    >>> cert_or_req = MagicMock()
    >>> cert_or_req.get_subject.return_value = sentinel.x509_name

    >>> with patch(_THIS_MODULE + '.get_single_x509_rdn_value',
    ...            side_effect=get_single_x509_rdn_value_side_effect) as getv:
    ...     subject_dict = get_cert_subject_dict(cert_or_req)
    ...
    >>> getv.mock_calls == [
    ...     call(sentinel.x509_name, CN),
    ...     call(sentinel.x509_name, ORG),
    ... ]
    True
    >>> subject_dict == {
    ...     'cn': '<value of cn>',
    ...     'o': '<value of o>',
    ... }
    True

    >>> with patch(_THIS_MODULE + '.get_single_x509_rdn_value',
    ...            side_effect=get_single_x509_rdn_value_side_effect) as getv:
    ...     subject_dict = get_cert_subject_dict(cert_or_req, include_ou=True)
    ...
    >>> getv.mock_calls == [
    ...     call(sentinel.x509_name, CN),
    ...     call(sentinel.x509_name, ORG),
    ...     call(sentinel.x509_name, OU),
    ... ]
    True
    >>> subject_dict == {
    ...     'cn': '<value of cn>',
    ...     'o': '<value of o>',
    ...     'ou': '<value of ou>',
    ... }
    True

    >>> with patch(_THIS_MODULE + '.get_single_x509_rdn_value',
    ...            side_effect=UnexpectedCertificateDataError('foo!')) as getv:
    ...     subject_dict = get_cert_subject_dict(cert_or_req)  # doctest: +ELLIPSIS
    ...
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: for certificate subject's item 'cn' -- foo!
    """
    def get_single_rdn_value(subject_key):
        nid = _SUBJECT_KEY_TO_NID[subject_key]
        try:
            return get_single_x509_rdn_value(x509_name, nid)
        except UnexpectedCertificateDataError as exc:
            raise UnexpectedCertificateDataError(
                "for certificate subject's item '{}' -- {}".format(
                    subject_key,
                    exc))

    x509_name = get_subject_as_x509_name_obj(cert_or_request)
    subject_dict = dict(
        cn=get_single_rdn_value('cn'),
        o=get_single_rdn_value('o'),
    )
    if include_ou:
        subject_dict['ou'] = get_single_rdn_value('ou')

    # sanity assertions:
    assert all(isinstance(v, basestring) for v in subject_dict.itervalues())
    if include_ou:
        assert subject_dict.viewkeys() == {'cn', 'o', 'ou'}
    else:
        assert subject_dict.viewkeys() == {'cn', 'o'}

    return subject_dict


def get_subject_as_x509_name_obj(cert_or_request):
    """
    Gen the subject of the given certificate or CSR.

    Args/kwargs:
        `cert_or_request`:
            An M2Crypto.X509.X509 object (containing a certificate) or
            a M2Crypto.X509.Request object (containing a CSR).

    Returns:
        The subject as a M2Crypto.X509.X509_Name instance.
    """
    return cert_or_request.get_subject()


def get_single_x509_rdn_value(x509_name, nid):
    """
    Get a single RDN value or None.

    Args/kwargs:
        `x509_name`:
            A M2Crypto.X509.X509_Name instance.
        `nid`:
            An integer constant value as defined as M2Crypto.m2.NID_*
            (note: M2Crypto.m2.NID_organizationName == n6lib.x509_helpers.ORG;
            M2Crypto.m2.NID_organizationalUnitName == n6lib.x509_helpers.OU;
            M2Crypto.m2.NID_commonName == n6lib.x509_helpers.CN).

    Returns:
        A single RDN value as a string (e.g. 'cert.pl' for
        nid=n6lib.x509_helpers.ORG or 'kowalski@example.com' for
        nid=n6lib.x509_helpers.CN...).

    Raises:
        UnexpectedCertificateDataError if -- for the given `nid` --
        there is *no* value or *more* than one value.

    >>> from mock import MagicMock, call, sentinel
    >>> entry = MagicMock()
    >>> entry.get_data.return_value = MagicMock()
    >>> entry.get_data.return_value.as_text.return_value = sentinel.rdn_value
    >>> x509_name = MagicMock()
    >>> x509_name.get_entries_by_nid.return_value = [entry]

    >>> get_single_x509_rdn_value(x509_name, sentinel.nid)
    sentinel.rdn_value

    >>> x509_name.mock_calls == [call.get_entries_by_nid(sentinel.nid)]
    True
    >>> entry.mock_calls == [
    ...     call.get_data(),
    ...     call.get_data().as_text(),
    ... ]
    True

    >>> x509_name.get_entries_by_nid.return_value = [
    ...     entry,
    ...     sentinel.another_entry,
    ... ]
    >>> get_single_x509_rdn_value(x509_name, sentinel.nid)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: encountered more than one value (expected only one)

    >>> x509_name.get_entries_by_nid.return_value = []
    >>> get_single_x509_rdn_value(x509_name, sentinel.nid)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    UnexpectedCertificateDataError: no value
    """
    entries = x509_name.get_entries_by_nid(nid)
    if entries:
        try:
            [entry] = entries
        except ValueError:
            raise UnexpectedCertificateDataError(
                'encountered more than one value (expected only one)')
        return entry.get_data().as_text()
    raise UnexpectedCertificateDataError('no value')


if __name__ == "__main__":
    import doctest
    doctest.testmod()

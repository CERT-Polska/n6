# -*- coding: utf-8 -*-

# Copyright (c) 2014-2021 NASK. All rights reserved.

"""
Low-level details of certificate generation (OpenSSL-based).
"""

import datetime
import logging
import os
import os.path as osp
import shutil
import tempfile
import subprocess

from n6lib.auth_db.models import SERVICE_CA_PROFILE_NAME
from n6lib.auth_db.validators import is_cert_serial_number_valid
from n6lib.common_helpers import (
    ascii_str,
    read_file,
)
from n6lib.config import ConfigString
from n6lib.const import CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM
from n6lib.datetime_helpers import datetime_utc_normalize
from n6corelib.x509_helpers import normalize_hex_serial_number


SERVER_COMPONENT_POLICY_SECT_NAME = 'server_component_serviceCA_policy'
SERVER_COMPONENT_ADDITIONAL_OPENSSL_COMMAND_ARGS = ('-policy', SERVER_COMPONENT_POLICY_SECT_NAME)

X509_EXTENSIONS_OPT_NAME = 'x509_extensions'

DEFAULT_INDEX_ATTR_CONTENT = 'unique_subject = no'

PKCS11_OPTS_PATTERN = '''
openssl_conf = openssl_def

[openssl_def]
engines = engine_section

[engine_section]
pkcs11 = pkcs11_section

[pkcs11_section]
engine_id = pkcs11
MODULE_PATH = {pkcs11_module_path}
init = 0
'''
# ^
# An example value of the `pkcs11_module_path` formattable field:
# "opensc-pkcs11.so". The value of that field will taken from the
# appropriate `ca_key_...` option (e.g., `ca_key_client_2 =
# pkcs11:opensc-pkcs11.so:-keyfile foo:bar -keyform spam`)
# in the appropriate section of the n6 config (by default, the
# section is `[manage_api]`).


#
# Functions used by the ._manage_api stuff
#

def get_ca_env_configuration(ca, ca_key_path):
    ca_env_configuration = dict(
        ca=ca,
        tmp_env_init_kwargs_base=dict(
            ssl_conf=ca.ssl_config,
            index_attr=DEFAULT_INDEX_ATTR_CONTENT,
            ca_cert=ca.certificate,
        ),
    )
    if ca_key_path.startswith('pkcs11:'):
        (_,
         pkcs11_module_path,
         pkcs11_additional_openssl_cmd_args) = ca_key_path.split(':', 2)
        ca_env_configuration['tmp_env_init_kwargs_base']['pkcs11_opts_dict'] = {
            'pkcs11_module_path': pkcs11_module_path,
            'pkcs11_additional_openssl_cmd_arg_list': pkcs11_additional_openssl_cmd_args.split(),
        }
    else:
        ca_env_configuration['tmp_env_init_kwargs_base']['ca_key'] = read_file(ca_key_path)
    return ca_env_configuration


def generate_certificate_pem(ca_env_configuration, csr_pem, serial_number,
                             server_component_n6login=None):
    """
    Generate a certificate.

    Args:
        `ca_env_configuration`:
            The result of a get_ca_env_configuration() call.
        `csr_pem`:
            The certificate signing request (CSR) in the PEM format, as
            a string.
        `serial_number`:
            The serial number for the generated certificate, as a string
            being a hexadecimal number.
        `server_component_n6login` (None or a string; default: None):
            Must be specified (as a non-None value) if the
            certificate that is being created belongs to an n6
            public server (the certificate's `kind` is
            "server-component"); otherwise it must be None.

    Returns:
        The generated certificate in the PEM format (as a string).
    """
    serial_number = normalize_hex_serial_number(
        serial_number,
        CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM)
    serial_openssl = _format_openssl_serial_number(serial_number)
    tmp_env_init_kwargs = dict(
        ca_env_configuration['tmp_env_init_kwargs_base'],
        csr=csr_pem,
        serial=serial_openssl,
        index='',
    )
    if server_component_n6login is None:
        additional_openssl_command_args = ()
        is_server_component = False
    else:
        assert ca_env_configuration['ca'].profile == SERVICE_CA_PROFILE_NAME
        additional_openssl_command_args = SERVER_COMPONENT_ADDITIONAL_OPENSSL_COMMAND_ARGS
        is_server_component = True
    with TmpEnv(**tmp_env_init_kwargs) as tmp_env:
        if is_server_component:
            tmp_env.ssl_conf.value.validate_for_public_server_cert()
        else:
            tmp_env.ssl_conf.value.validate_for_nonpublic_cert()
        cert_pem = tmp_env.execute_cert_generation(additional_openssl_command_args)
    return cert_pem


def generate_crl_pem(ca_env_configuration):
    """
    Generate a certificate revocation list (CRL) for the specified CA.

    Args:
        `ca_env_configuration`:
            The result of a get_ca_env_configuration() call (among
            others, it specifies also the concerned CA).

    Returns:
        The generated CRL in the PEM format (as a string).
    """
    ca = ca_env_configuration['ca']
    index = _make_openssl_index_file_content(ca.iter_all_certificates())
    tmp_env_init_kwargs = dict(
        ca_env_configuration['tmp_env_init_kwargs_base'],
        index=index,
        serial='',
    )
    with TmpEnv(**tmp_env_init_kwargs) as tmp_env:
        tmp_env.ssl_conf.value.validate_for_crl()
        crl_pem = tmp_env.execute_crl_generation()
    return crl_pem


def revoke_certificate_and_generate_crl_pem(ca_env_configuration, cert_data):
    """
    Revoke the specified certificate and generate a certificate
    revocation list (CRL) (for the specified CA).

    Args:
        `ca_env_configuration`:
            The result of a get_ca_env_configuration() call (among
            others, it specifies also the concerned CA).
        `cert_data`:
            The certificate that is being revoked as an instance of
            a subclass of ._manage_api._CertificateBase.

    Returns:
        The generated CRL in the PEM format (as a string).
    """
    ca = ca_env_configuration['ca']
    index = _make_openssl_index_file_content(ca.iter_all_certificates())
    serial_openssl = _format_openssl_serial_number(cert_data.serial_hex)
    tmp_env_init_kwargs = dict(
        ca_env_configuration['tmp_env_init_kwargs_base'],
        index=index,
        serial=serial_openssl,
        revoke_cert=cert_data.certificate,
    )
    with TmpEnv(**tmp_env_init_kwargs) as tmp_env:
        tmp_env.ssl_conf.value.validate_for_crl()
        tmp_env.execute_cert_revocation()
        crl_pem = tmp_env.execute_crl_generation()
    return crl_pem


#
# Local helper classes
#

## For historical reasons, some implementation details are strange and
## can be made more straightforward and clean [maybe TODO later]...

class InvalidSSLConfigError(Exception):

    def __init__(self, general_msg, actual_reason):
        self.actual_reason = actual_reason
        msg = '{}: {}'.format(general_msg, actual_reason)
        super(InvalidSSLConfigError, self).__init__(msg)


class IncompleteSSLConfigError(InvalidSSLConfigError):

    general_msg = "Incomplete SSL config error"

    def __init__(self, reason):
        super(IncompleteSSLConfigError, self).__init__(self.general_msg, reason)


class SSLConfigMissingOptError(IncompleteSSLConfigError):

    def __init__(self, missing_opt_name, sect_name=None):
        reason = "the option {!r} is missing".format(ascii_str(missing_opt_name))
        if sect_name is not None:
            reason = "{} (section: {!r})".format(reason, ascii_str(sect_name))
        super(SSLConfigMissingOptError, self).__init__(reason)


class SSLConfigMissingSectError(IncompleteSSLConfigError):

    def __init__(self, missing_sect_name):
        reason = "the section {!r} is missing".format(ascii_str(missing_sect_name))
        super(SSLConfigMissingSectError, self).__init__(reason)


class SSLConfigEmptySectError(IncompleteSSLConfigError):

    def __init__(self, empty_sect_name):
        reason = "the section {!r} exists, but it is empty".format(ascii_str(empty_sect_name))
        super(SSLConfigEmptySectError, self).__init__(reason)


class OpenSSLConfig(object):

    _REQUIRED_CA_OPTS_MAPPING = {
        'for_cert': [
            'default_md',
            'default_days',
        ],
        'for_crl': [
            'default_md',
            'default_crl_days',
        ],
    }

    def __init__(self,
                 config_string,
                 current_dir_path,
                 paths_to_substitute=None,
                 pkcs11_opts_dict=None):
        try:
            self.parsed_config = ConfigString(config_string)
        except ValueError as exc:
            raise InvalidSSLConfigError("SSL config is not valid", exc)
        self._check_nonempty_sect_provided('ca')
        self.ca_opt_pattern = self.ca_sect_name + '.{}'
        self._substitute_config_opts(paths_to_substitute, current_dir_path)
        self._apply_pkcs11_opts(pkcs11_opts_dict)

    def validate_for_public_server_cert(self):
        self._validate_required_opt_names('for_cert')
        self._check_nonempty_sect_provided(SERVER_COMPONENT_POLICY_SECT_NAME)
        self._check_x509_extensions()

    def validate_for_nonpublic_cert(self):
        self._validate_required_opt_names('for_cert')
        self._check_ca_opt_provided('policy')
        policy_sect_name = self.parsed_config.get_opt_value(self.ca_opt_pattern.format('policy'))
        self._check_nonempty_sect_provided(policy_sect_name)
        self._check_x509_extensions()

    def validate_for_crl(self):
        self._validate_required_opt_names('for_crl')

    def __str__(self):
        return str(self.parsed_config)

    @property
    def ca_sect_name(self):
        try:
            return self.parsed_config.get_opt_value('ca.default_ca')
        except KeyError as exc:
            raise SSLConfigMissingOptError(exc.args[0], sect_name='ca')

    def _substitute_config_opts(self, paths_mapping, current_dir_path):
        self.parsed_config = self._substitute_ca_opt('dir', current_dir_path)
        # unify temporary environment paths and config paths,
        # so they do not differ when used by OpenSSL
        if paths_mapping:
            for opt_name, opt_value in paths_mapping.iteritems():
                self.parsed_config = self._substitute_ca_opt(opt_name, opt_value)

    def _apply_pkcs11_opts(self, pkcs11_opts_dict):
        if pkcs11_opts_dict:
            pkcs11_opts = PKCS11_OPTS_PATTERN.format(**pkcs11_opts_dict)
            self.parsed_config = self.parsed_config.insert_above('ca', pkcs11_opts)
            # there is no need to catch a KeyError here, absence of
            # this config option is noticed earlier in current
            # implementation
            self.parsed_config = self.parsed_config.remove(
                self.ca_opt_pattern.format('private_key'))

    def _substitute_ca_opt(self, opt_name, opt_value):
        config_opt = self.ca_opt_pattern.format(opt_name)
        try:
            return self.parsed_config.substitute(config_opt, '{} = {}'.format(opt_name, opt_value))
        except KeyError as exc:
            raise SSLConfigMissingOptError(exc.args[0], sect_name=self.ca_sect_name)

    def _validate_required_opt_names(self, kind_of_operation):
        try:
            required_opt_names = self._REQUIRED_CA_OPTS_MAPPING[kind_of_operation]
        except KeyError:
            raise RuntimeError("Unknown 'kind of operation' = {!r}".format(kind_of_operation))
        for opt_name in required_opt_names:
            self._check_ca_opt_provided(opt_name)

    def _check_x509_extensions(self):
        opt_location = self.ca_opt_pattern.format(X509_EXTENSIONS_OPT_NAME)
        if not self.parsed_config.contains(opt_location):
            logging.warning("The option {!r} in OpenSSL config (section {!r}) is missing; "
                            "the section, which is referred to by the option, is not "
                            "required, but most likely "
                            "should be configured".format(X509_EXTENSIONS_OPT_NAME,
                                                          ascii_str(self.ca_sect_name)))
        else:
            sect_name = self.parsed_config.get_opt_value(opt_location)
            try:
                self._check_nonempty_sect_provided(sect_name)
            except SSLConfigEmptySectError:
                logging.warning("The section {!r} in OpenSSL config, referred to by the option "
                                "{!r}, is empty; although it is not required, it most likely "
                                "should be configured".format(ascii_str(sect_name),
                                                              X509_EXTENSIONS_OPT_NAME,
                                                              ascii_str(self.ca_sect_name)))

    def _check_ca_opt_provided(self, opt_name):
        opt_location = self.ca_opt_pattern.format(opt_name)
        if not self.parsed_config.contains(opt_location):
            raise SSLConfigMissingOptError(opt_name, sect_name=self.ca_sect_name)

    def _check_nonempty_sect_provided(self, sect_name):
        try:
            opts = self.parsed_config.get_opt_names(sect_name)
        except KeyError:
            raise SSLConfigMissingSectError(sect_name)
        if not opts:
            raise SSLConfigEmptySectError(sect_name)


class DirectoryStructure(object):

    """The directory structure for a TmpEnv's component."""

    def __init__(self, name, rel_pth, path, opts=None):
        assert isinstance(name, basestring)
        assert isinstance(rel_pth, basestring)
        assert isinstance(path, basestring)
        self.name = name
        self.relative_pth = rel_pth
        self._value = None
        self._path = path.rstrip('/') + '/'
        self.opts = opts
        self._makedir_if_nonexistent()


    def _makedir_if_nonexistent(self):
        dir_path = osp.dirname(self.path)
        if not osp.exists(dir_path):
            os.makedirs(dir_path)


    @property
    def path(self):
        return self._path + self.relative_pth + self.name


    @property
    def value(self):
        return self._value


    @value.setter
    def value(self, value):
        if self.name == 'openssl.cnf':
            value = self._get_adjusted_openssl_config_str(value)
        self._value = value
        self._create_file()


    def _get_adjusted_openssl_config_str(self, value):
        paths_mapping = self.opts.get('paths_to_substitute') if self.opts is not None else None
        pkcs11_opts_dict = self.opts.get('pkcs11_opts_dict') if self.opts is not None else None

        try:
            return OpenSSLConfig(value,
                                 osp.dirname(self.path),
                                 paths_to_substitute=paths_mapping,
                                 pkcs11_opts_dict=pkcs11_opts_dict)
        except ValueError as exc:
            raise InvalidSSLConfigError("SSL config is not valid", exc)


    def _create_file(self):
        if not osp.isdir(self.path):
            with open(self.path, 'w') as f:
                f.write(str(self.value))



class TmpEnv(object):

    """
    Temporary environment for OpenSSL CA operations.
    """

    def __init__(self, pkcs11_opts_dict=None, **init_values):
        self.pkcs11_opts_dict = pkcs11_opts_dict
        path = self.tmp_path_templ = tempfile.mkdtemp()
        try:
            self._prepare_dir_structures(path)
            for name, value in sorted(init_values.iteritems()):
                dir_struct = getattr(self, name)
                dir_struct.value = value
        except:
            self._cleanup()
            raise

    def _prepare_dir_structures(self, path):
        self.ca_cert = DirectoryStructure(name='cacert.pem', rel_pth='', path=path)
        self.ca_key = DirectoryStructure(name='cakey.pem', rel_pth='private/', path=path)
        self.certs_dir = DirectoryStructure(name='', rel_pth='certs/', path=path)
        self.csr = DirectoryStructure(name='client.csr', rel_pth='csr/', path=path)
        self.index = DirectoryStructure(name='index.txt', rel_pth='', path=path)
        self.index_attr = DirectoryStructure(name='index.txt.attr', rel_pth='', path=path)
        self.revoke_cert = DirectoryStructure(name='revoke_cert.pem', rel_pth='', path=path)
        self.ca_crl = DirectoryStructure(name='ca.crl', rel_pth='', path=path)
        self.serial = DirectoryStructure(name='serial', rel_pth='', path=path)
        self.gen_cert = DirectoryStructure(name='cert.pem', rel_pth=self.certs_dir.relative_pth,
                                           path=path)
        paths_to_substitute = self._get_paths_to_substitute_dict()
        self.ssl_conf = DirectoryStructure(name='openssl.cnf', rel_pth='', path=path,
                                           opts={'pkcs11_opts_dict': self.pkcs11_opts_dict,
                                                 'paths_to_substitute': paths_to_substitute})

    def _get_paths_to_substitute_dict(self):
        return {
            'certificate': self.ca_cert.path,
            'private_key': self.ca_key.path,
            'new_certs_dir': self.certs_dir.path,
            'database': self.index.path,
            'serial': self.serial.path,
        }

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._cleanup()

    def _cleanup(self):
        shutil.rmtree(self.tmp_path_templ)

    def execute_cert_generation(self, additional_openssl_command_args):
        self._execute_command(
            [
                'openssl', 'ca',
                '-config', self.ssl_conf.path,
                '-notext',
                '-in', self.csr.path,
                '-out', self.gen_cert.path,
                '-batch',
            ]
            + self._get_pkcs11_openssl_command_args()
            + list(additional_openssl_command_args))
        return read_file(self.gen_cert.path)

    def execute_cert_revocation(self):
        self._execute_command(
            [
                'openssl', 'ca',
                '-config', self.ssl_conf.path,
                '-revoke', self.revoke_cert.path,
                '-batch',
            ] + self._get_pkcs11_openssl_command_args())

    def execute_crl_generation(self):
        self._execute_command(
            [
                'openssl', 'ca',
                '-config', self.ssl_conf.path,
                '-gencrl',
                '-out', self.ca_crl.path,
                '-batch',
            ] + self._get_pkcs11_openssl_command_args())
        return read_file(self.ca_crl.path)

    @staticmethod
    def _execute_command(cmd_args):
        try:
            subprocess.check_output(cmd_args, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError('CA env error ({0}; {1!r})'.format(exc, exc.output))

    def _get_pkcs11_openssl_command_args(self):
        openssl_command_args = []
        if self.pkcs11_opts_dict is not None:
            ca_sect_name = self.ssl_conf.value.ca_sect_name
            openssl_command_args.extend([
                '-engine', 'pkcs11',
            ] + self.pkcs11_opts_dict['pkcs11_additional_openssl_cmd_arg_list'] + [
                '-name', ca_sect_name,
            ])
        return openssl_command_args


#
# Local helper functions
#

def _make_openssl_index_file_content(cert_data_iterator):
    # [The following comment was copied from ???]
    #
    # The index.txt file is an ascii file consisting of 6 tab-separated
    # fields.  Some of those fields may be empty and might appear not to exist at all.
    #
    # The 6 fields are:
    #
    # 0)  Entry type.  May be "V" (valid), "R" (revoked) or "E" (expired).
    #     Note that an expired may have the type "V" because the type has
    #     not been updated.  'openssl ca updatedb' does such an update.
    # 1)  Expiration datetime.
    #     The format of the date is YYMMDDHHMMSSZ
    #      (the same as an ASN1 UTCTime structure)
    # 2)  Revokation datetime.  This is set for any entry of the type "R".
    #     The format of the date is YYMMDDHHMMSSZ
    #      (the same as an ASN1 UTCTime structure)
    # 3)  Serial number.
    # 4)  File name of the certificate.  This doesn't seem to be used,
    #     ever, so it's always "unknown".
    # 5)  Certificate subject name.
    #
    # So the format is:
    #     E|R|V<tab>Expiry<tab>[RevocationDate]<tab>Serial<tab>unknown<tab>SubjectDN

    index_file_lines = []

    for cert_data in cert_data_iterator:
        entry_type = 'V'
        expires_openssl = revoked_openssl = ''

        if cert_data.expires_on is not None:
            if datetime.datetime.utcnow() > cert_data.expires_on:
                entry_type = 'E'
            expires_openssl = _format_openssl_dt(cert_data.expires_on)

        if cert_data.revoked_on is not None:
            entry_type = 'R'
            revoked_openssl = _format_openssl_dt(cert_data.revoked_on)

        serial_openssl = _format_openssl_serial_number(cert_data.serial_hex)
        subject = cert_data.subject

        index_file_lines.append("{0}\t{1}\t{2}\t{3}\tunknown\t{4}\n".format(
            entry_type,
            expires_openssl,
            revoked_openssl,
            serial_openssl,
            subject))

    return ''.join(index_file_lines)


def _format_openssl_dt(dt):
    """The format of the date is YYMMDDHHMMSSZ (the same as an ASN1 UTCTime structure)

           Arg: dt <datetime>

           Ret: <string> (format YYMMDDHHMMSSZ)

           Raises: AssertionError (if format is not datetime)

    >>> naive_dt_1 = datetime.datetime(2013, 6, 6, 12, 13, 57)
    >>> _format_openssl_dt(naive_dt_1)
    '130606121357Z'

    >>> naive_dt_2 = datetime.datetime(2013, 6, 6, 12, 13, 57, 951211)
    >>> _format_openssl_dt(naive_dt_2)
    '130606121357Z'

    >>> from n6lib.datetime_helpers import FixedOffsetTimezone
    >>> tz_aware_dt = datetime.datetime(
    ...     2013, 6, 6, 14, 13, 57, 951211,   # note: 14 instead of 12
    ...     tzinfo=FixedOffsetTimezone(120))
    >>> _format_openssl_dt(tz_aware_dt)
    '130606121357Z'

    >>> _format_openssl_dt('2014-08-08 12:01:23')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    TypeError: a datetime.datetime instance is required
    >>> _format_openssl_dt(None)                   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    TypeError: a datetime.datetime instance is required
    """
    if isinstance(dt, datetime.datetime):
        return datetime_utc_normalize(dt).strftime("%y%m%d%H%M%SZ")
    raise TypeError('a datetime.datetime instance is required')


def _format_openssl_serial_number(serial_number):
    if isinstance(serial_number, unicode):
        serial_number = str(serial_number)
    if not isinstance(serial_number, str):
        raise TypeError('serial_number {!r} has a wrong type ({})'.format(
            serial_number,
            type(serial_number).__name__))
    serial_number = serial_number.upper()
    if len(serial_number) % 2:
        # force even number of digits
        serial_number = '0' + serial_number
    # sanity check
    if not is_cert_serial_number_valid(serial_number.lower()):
        raise ValueError(
            'something really wrong: a certificate serial number '
            'prepared for OpenSSL tools ({0!r}) is not valid'
            .format(serial_number))
    return serial_number


if __name__ == "__main__":
    import doctest
    doctest.testmod()

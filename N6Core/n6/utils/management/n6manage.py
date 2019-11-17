#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

import argparse
import datetime
import errno
import logging
import os.path as osp
import socket
import sys
import traceback

from n6lib.common_helpers import ascii_str
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.manage_api import ManageAPI


#
# Helper classes

class Spec(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __iter__(self):
        yield self.args
        yield self.kwargs


#
# Command-line argument specs

COMMON_ARG_SPECS = [
    Spec(
        '--debug',
        action='store_true',
        help='show the full Python traceback on any fatal error',
    ),
]

COMMAND_PARSER_SPECS = []
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'list-ca',
            help='get a list of CA certificates stored in the Auth DB',
        ),
        [],
    )
])
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'add-cert',
            help='add the given (externally created) certificate to the Auth DB',
        ),
        [
            Spec(
                'ca_label',
                metavar='CA-LABEL',
                help='the label of one of CA certificates stored in the Auth DB',
            ),
            Spec(
                'cert_file',
                type=argparse.FileType(),
                metavar='CERT-FILE',
                help=(
                    "the name of the file containing the certificate to be "
                    "added (or '-' to read it from the standard input)"),
            ),
            Spec(
                'created_on',
                type=parse_iso_datetime_to_utc,
                metavar='CREATED-ON-DT',
                help=(
                    'when the certificate was created '
                    '(date+time in ISO-8601 format)'),
            ),
            Spec(
                '-a', '--adding-owner',
                action='store_true',
                help='add also the owner (user or component) of the certificate',
            ),
            Spec(
                '-s', '--server-component-login',
                metavar='LOGIN',
                help=(
                    'the login of the owner, *explicitly* specified (instead '
                    'of being taken from the certificate) -- allowed (and '
                    'required) *only* for a server-component'),
            ),
        ],
    ),
])
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'make-cert',
            help='create a new certificate and add it to the Auth DB',
        ),
        [
            Spec(
                'ca_label',
                metavar='CA-LABEL',
                help='the label of one of CA certificates stored in the Auth DB',
            ),
            Spec(
                'csr_file',
                type=argparse.FileType(),
                metavar='CSR-FILE',
                help=(
                    "the name of the file containing a CSR [certificate "
                    "signing request] (or '-' to read it from the standard "
                    "input)"),
            ),
            Spec(
                '-a', '--adding-owner',
                action='store_true',
                help='add also the owner (user or component) of the certificate',
            ),
            Spec(
                '-d', '--dump-into',
                type=osp.abspath,
                metavar='DIRECTORY',
                help=(
                    'if specified: dump the generated certificate to a file '
                    'in the DIRECTORY'),
            ),
            Spec(
                '-s', '--server-component-login',
                metavar='LOGIN',
                help=(
                    'the login of the owner, *explicitly* specified (instead '
                    'of being taken from the certificate) -- allowed (and '
                    'required) *only* for a server-component'),
            ),
        ],
    ),
])
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'revoke-cert',
            help=(
                'mark the specified certificate as revoked in the Auth DB '
                'and dump the current CRL [certificate revocation list] '
                'for the specified CA (to the standard output, by default)'),
        ),
        [
            Spec(
                'ca_label',
                metavar='CA-LABEL',
                help='the label of one of CA certificates stored in the Auth DB',
            ),
            Spec(
                'cert_serial',
                metavar='CERT-SERIAL',
                help='the certificate serial number as a hexadecimal integer',
            ),
            Spec(
                'revocation_comment',
                metavar='REVOCATION-COMMENT',
                help=(
                    'a comment that explains why the certificate '
                    'is being revoked'),
            ),
            Spec(
                '-d', '--dump-into',
                type=osp.abspath,
                metavar='DIRECTORY',
                help=(
                    'if specified: a file in the DIRECTORY will be used '
                    '(the CRL will be dumped to it) instead of the standard '
                    'output'),
            ),
        ],
    ),
])
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'dump-cert',
            help=('dump the specified certificate '
                  '(to the standard output, by default)'),
        ),
        [
            Spec(
                'ca_label',
                metavar='CA-LABEL',
                help='the label of one of CA certificates stored in the Auth DB',
            ),
            Spec(
                'cert_serial',
                metavar='CERT-SERIAL',
                help='the certificate serial number as a hexadecimal integer',
            ),
            Spec(
                '-d', '--dump-into',
                type=osp.abspath,
                metavar='DIRECTORY',
                help=(
                    'if specified: a file in the DIRECTORY will be used '
                    '(the certificate be dumped to it) instead of the '
                    'standard output'),
            ),
        ],
    ),
])
COMMAND_PARSER_SPECS.extend([
    (
        Spec(
            'dump-crl',
            help=(
                'dump the current CRL [certificate revocation list] for the '
                'specified CA (to the standard output, by default)'),
        ),
        [
            Spec(
                'ca_label',
                metavar='CA-LABEL',
                help='the label of one of CA certificates stored in the Auth DB',
            ),
            Spec(
                '-d', '--dump-into',
                type=osp.abspath,
                metavar='DIRECTORY',
                help=(
                    'if specified: a file in the DIRECTORY will be used '
                    '(the CRL will be dumped to it) instead of the standard '
                    'output'),
            ),
        ],
    ),
])

## maybe TODO later: some commands that could be added in the future:
# n6manage dump-ca-cert CA-LABEL
# n6manage list-certs CA-LABEL
# n6manage list-users CA-LABEL
# n6manage owner-search OWNER-SELECTION [OWNER-SELECTION ...]
#   where OWNER-SELECTION is "app-user[:LOGIN][/ORGANIZATION]" or
#                            "admin[:LOGIN]", or "component[:LOGIN]", or "all"
# n6manage add-user SINGLE-OWNER-SPEC
#   where SINGLE-OWNER-SPEC is "app-user:LOGIN/ORGANIZATION"
# n6manage show-user LOGIN [ORG]
# n6manage show-cert CA-LABEL CERT-SERIAL
# n6manage dump-csr ...
# ...


#
# Actual script functions

def main():
    COMMAND_NAME_TO_FUNC = {
        'list-ca': list_ca,
        'add-cert': add_cert,
        'make-cert': make_cert,
        'revoke-cert': revoke_cert,
        'dump-cert': dump_cert,
        'dump-crl': dump_crl,
    }
    arguments = _parse_arguments(sys.argv)
    logging.basicConfig()
    command_func = COMMAND_NAME_TO_FUNC.get(
        arguments.command_name,
        _command_not_implemented)
    try:
        manage_api = ManageAPI()
        command_func(manage_api, arguments)
    except Exception as exc:
        print >>sys.stderr, 'FATAL ERROR:', ascii_str(exc)
        print >>sys.stderr
        if arguments.debug:
            traceback.print_exc()
            print >>sys.stderr
            print >>sys.stderr, 'Arguments:', arguments
        else:
            print >>sys.stderr, '(use --debug to see error tracebacks)'
        sys.exit(1)


def _parse_arguments(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest='command_name',
        metavar='COMMAND',
        help=(
            'try "%(prog)s COMMAND --help" for the description '
            'of the arguments for a particular COMMAND'
        ),
    )
    for (cp_spec_args, cp_spec_kwargs), arg_specs in COMMAND_PARSER_SPECS:
        command_parser = subparsers.add_parser(*cp_spec_args, **cp_spec_kwargs)
        for arg_spc in (arg_specs + COMMON_ARG_SPECS):
            if isinstance(arg_spc, Spec):
                arg_spec_args, arg_spec_kwargs = arg_spc
                command_parser.add_argument(*arg_spec_args, **arg_spec_kwargs)
            else:
                assert isinstance(arg_spc, list) and arg_spc
                mutually_exclusive_group_caption = arg_spc[0].lower()
                assert 'excl' in mutually_exclusive_group_caption
                required = ('req' in mutually_exclusive_group_caption)
                grp = command_parser.add_mutually_exclusive_group(required)
                for arg_spec_args, arg_spec_kwargs in arg_spc[1:]:
                    grp.add_argument(*arg_spec_args, **arg_spec_kwargs)
    arguments = parser.parse_args(argv[1:])
    return arguments


def _command_not_implemented(manage_api, arguments):
    raise NotImplementedError('command not implemented!')


def list_ca(manage_api, arguments):
    print 'CA label | CA profile | CA subject key identifier | CA authority key identifier'
    for ca in manage_api.iter_all_ca_data():
        profile = ca.profile or '-'
        subject_key_identifier = ascii_str(ca.subject_key_identifier or '-').strip()
        authority_key_identifier = ascii_str(ca.authority_key_identifier or '-').strip()
        print '{} | {} | {} | {}'.format(ca.ca_label,
                                         profile,
                                         subject_key_identifier,
                                         authority_key_identifier)


def add_cert(manage_api, arguments):
    cert_pem = _read_and_close(arguments.cert_file)
    manage_api.add_given_cert(
        arguments.ca_label,
        cert_pem,
        created_on=arguments.created_on,
        creator_hostname=_get_creator_hostname(),
        adding_owner=arguments.adding_owner,
        server_component_login=arguments.server_component_login)


def make_cert(manage_api, arguments):
    csr_pem = _read_and_close(arguments.csr_file)
    cert_pem, cert_slug = manage_api.make_new_cert(
        arguments.ca_label,
        csr_pem,
        creator_hostname=_get_creator_hostname(),
        adding_owner=arguments.adding_owner,
        server_component_login=arguments.server_component_login)
    if arguments.dump_into:
        _dump_cert_into(cert_pem, cert_slug, arguments.dump_into)


def revoke_cert(manage_api, arguments):
    crl_pem = manage_api.revoke_cert(
        arguments.ca_label,
        serial_number=arguments.cert_serial,
        revocation_comment=arguments.revocation_comment)
    if arguments.dump_into:
        # dump_into should be a directory name...
        _dump_crl_into(
            crl_pem,
            arguments.ca_label,
            datetime.datetime.utcnow(),
            arguments.dump_into)
    else:
        # ...or None -- then dump into stdout
        print crl_pem


def dump_cert(manage_api, arguments):
    cert_pem, cert_slug = manage_api.get_cert_pem_and_slug(
        arguments.ca_label,
        serial_number=arguments.cert_serial)
    if arguments.dump_into:
        # dump_into should be a directory name...
        _dump_cert_into(cert_pem, cert_slug, arguments.dump_into)
    else:
        # ...or None -- then dump into stdout
        print cert_pem


def dump_crl(manage_api, arguments):
    crl_pem = manage_api.get_crl_pem(arguments.ca_label)
    if arguments.dump_into:
        # dump_into should be a directory name...
        _dump_crl_into(
            crl_pem,
            arguments.ca_label,
            datetime.datetime.utcnow(),
            arguments.dump_into)
    else:
        # ...or None -- then dump into stdout
        print crl_pem


def _get_creator_hostname():
    return socket.gethostname()


def _read_and_close(stream):
    try:
        return stream.read()
    finally:
        if stream is not sys.stdin:
            stream.close()


def _dump_cert_into(cert_pem, cert_slug, dump_into):
    filename = cert_slug + '.pem'
    _do_dump(cert_pem, dump_into, filename)


def _dump_crl_into(crl_pem, ca_label, dt, dump_into):
    filename = '{0}-ca-{1:%Y%m%d-%H%M}Z.crl'.format(ca_label, dt)
    _do_dump(crl_pem, dump_into, filename)


def _do_dump(dumped_content, dump_into, filename, open_mode='w'):
    try:
        with open(osp.join(dump_into, filename), open_mode) as file_dump:
            file_dump.write(dumped_content)
    except IOError as exc:
        # if path does not exist, provide clearer message
        if exc.errno == errno.ENOENT:
            raise IOError("A provided path: {!r} does not exist.".format(dump_into))
        raise


if __name__ == '__main__':
    main()

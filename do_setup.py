#!/usr/bin/env python

# Copyright (c) 2013-2018 NASK. All rights reserved.

import ast
import argparse
import logging
import logging.config
import os
import os.path as osp
import sys
import traceback


LOGGER = None  # to be set in configure_logging() (see below)

DEFAULT_ACTION = 'install'
DEFAULT_ADDITIONAL_PACKAGES = 'nose', 'coverage', 'pylint'
DEFAULT_LOG_CONFIG = {
    'version': 1,
    'formatters': {
        'brief': {'format': '\n%(asctime)s [%(levelname)s] %(message)s'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'brief',
            'stream': 'ext://sys.stdout',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}
N6_LIB = 'N6Lib'
N6_SDK = 'N6SDK'

this_script_dir = osp.dirname(osp.abspath(__file__))
venv_dir = os.environ.get('VIRTUAL_ENV')


def iter_nonfalse_unique(iterable):
    seen = set()
    for item in iterable:
        if item and item not in seen:
            seen.add(item)
            yield item


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('components',
                        nargs='+',
                        metavar='N6-COMPONENT-DIRECTORY',
                        help=('one or more directory names identifying n6 components, '
                              'or a special value "all" (to set up all N6* stuff)'))
    parser.add_argument('-a', '--action',
                        default=DEFAULT_ACTION,
                        metavar='ARGUMENT-FOR-SETUP',
                        help=('argument for setup.py, for example "install" or "develop" '
                              '(default: "{}")'.format(DEFAULT_ACTION)))
    parser.add_argument('-L', '--no-n6lib',
                        action='store_true',
                        help=('disable automatic setup of N6Lib and N6SDK (by default '
                              'they are always set up before any other component)'))
    parser.add_argument('-p', '--additional-packages',
                        nargs='+',
                        default=list(DEFAULT_ADDITIONAL_PACKAGES),
                        metavar='PACKAGE',
                        help=('names of PyPi packages to be installed after the actual '
                              'setup (defaults: {}; note that this option overrides them)'
                              .format(' '.join(DEFAULT_ADDITIONAL_PACKAGES))))
    parser.add_argument('-P', '--no-additional-packages',
                        action='store_true',
                        help=('disable installation of any additional packages '
                              '(see: -p/--additional-packages)'))
    parser.add_argument('-u', '--update-pip-and-setuptools',
                        action='store_true',
                        help='execute "pip install --upgrade pip setuptools" before any actions')
    parser.add_argument('-v', '--virtualenv-dir',
                        metavar='DIRECTORY',
                        help=('custom virtualenv directory (by default it is determined '
                              'from the VIRTUAL_ENV environment variable)'))
    parser.add_argument('--log-config',
                        default=repr(DEFAULT_LOG_CONFIG),
                        metavar='DICT',
                        help=('a Python dict literal specifying logging config in the '
                              'logging.config.dictConfig format (default: {!r})'
                              .format(repr(DEFAULT_LOG_CONFIG).replace('%', '%%'))))

    arguments = parser.parse_args()

    arguments.components = [name.rstrip('/') for name in arguments.components]
    if 'all' in arguments.components:
        arguments.components.remove('all')
        arguments.components.extend(name for name in os.listdir(this_script_dir)
                                    if name.startswith('N6') and osp.isdir(name))
    # By default N6SDK and N6Lib are always provided first,
    # *unless explicitly disabled*.  If provided, they must
    # be the set up before other components.
    if N6_LIB in arguments.components:
        arguments.components.remove(N6_LIB)
        arguments.components.insert(0, N6_LIB)
    elif not arguments.no_n6lib:
        arguments.components.insert(0, N6_LIB)
    if N6_SDK in arguments.components:
        arguments.components.remove(N6_SDK)
        arguments.components.insert(0, N6_SDK)
    elif not arguments.no_n6lib:  # [sic]
        arguments.components.insert(0, N6_SDK)
    arguments.components = list(iter_nonfalse_unique(arguments.components))

    if arguments.no_additional_packages:
        arguments.additional_packages = []
    else:
        arguments.additional_packages = list(
                iter_nonfalse_unique(arguments.additional_packages))

    try:
        arguments.log_config = ast.literal_eval(arguments.log_config)
        if not isinstance(arguments.log_config, dict):
            raise ValueError
    except (ValueError, SyntaxError):
        parser.error('{!r} is not a literal-evaluable dict'
                     .format(arguments.log_config))

    return arguments


def configure_logging(arguments):
    global LOGGER
    try:
        logging.config.dictConfig(arguments.log_config)
        LOGGER = logging.getLogger('n6_do_setup')
    except Exception:
        sys.exit('could not configure logging using config: {!r}\ncause: {}'
                 .format(arguments.log_config, traceback.format_exc()))
    LOGGER.debug('logging configured')


def command(cmd):
    if venv_dir is not None:
        cmd = '{}/bin/{}'.format(venv_dir, cmd)
    LOGGER.info('executing: %r in %r', cmd, os.getcwd())
    error = bool(os.system(cmd))
    if error:
        sys.exit('exiting after an external command error ({})'.format(cmd))


def main():
    global venv_dir

    arguments = parse_arguments()
    configure_logging(arguments)

    original_wd = os.getcwd()
    try:
        os.chdir(this_script_dir)
        if arguments.virtualenv_dir:
            venv_dir = osp.abspath(arguments.virtualenv_dir)

        if arguments.update_pip_and_setuptools:
            command('pip install --upgrade pip setuptools')
            LOGGER.info("'pip' and 'setuptools' updated")

        for dirname in arguments.components:
            os.chdir(osp.join(this_script_dir, dirname))
            command('python setup.py {}'.format(arguments.action))
            LOGGER.info("%r setup done", dirname)

        os.chdir(this_script_dir)
        for pkgname in arguments.additional_packages:
            command('pip install {}'.format(pkgname))
            LOGGER.info("%r installed", pkgname)

    except SystemExit as exc:
        status = exc.args[0] if exc.args else 0
        msg = (status if isinstance(status, basestring)
               else 'exiting with status: {!r}'.format(status))
        LOGGER.error(msg)
        raise
    except:
        LOGGER.critical('fatal error:', exc_info=True)
        raise
    finally:
        os.chdir(original_wd)


if __name__ == '__main__':
    main()

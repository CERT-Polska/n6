#!/usr/bin/env python

# Copyright (c) 2013-2022 NASK. All rights reserved.

import ast
import argparse
import logging
import logging.config
import os
import os.path as osp
import sys
import traceback


# TODO: remove all, no longer needed, stuff related to Python 2 and the
#       removed Py2 components.


LOGGER = None   # type: logging.Logger   # (to be set in configure_logging(), see below)

PY2 = sys.version_info[0] < 3

DEFAULT_ACTION = 'install'
if PY2:
    DEFAULT_ADDITIONAL_PACKAGES = [
        'pytest==4.6.11',
        'pytest-cov==2.12.1',
        'coverage<6.0',
        'astroid==1.6.6',
        'pylint==1.9.5',
        'waitress<2.0',
    ]
else:
    DEFAULT_ADDITIONAL_PACKAGES = [
        'pytest==7.1.2',
        'pytest-cov==3.0.0',
        'coverage',
        'pylint',
        'mkdocs==1.2.3',
        'mkdocs-material==8.0.3',
        'waitress',
    ]
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
N6_CORE = 'N6Core'
N6_CORE_LIB = 'N6CoreLib'
N6_LIB = 'N6Lib'
N6_LIB_py2 = 'N6Lib-py2'
N6_SDK = 'N6SDK'
N6_SDK_py2 = 'N6SDK-py2'

this_script_dir = osp.dirname(osp.abspath(__file__))
venv_dir = environ_venv_dir = os.environ.get('VIRTUAL_ENV')


def get_excluded_from_all():
    """
    Get a set of component directory names that are explicitly excluded
    from those denoted by the "all" special value.
    """
    excluded_from_all = {
        'N6GridFSMount',    # maybe TODO later: move to the appropriate branch of the following `if`...
    }
    if PY2:
        # For Python 2: let's exclude any Python-3-only stuff.
        excluded_from_all.update({
            'N6AdminPanel',
            'N6BrokerAuthApi',
            'N6DataPipeline',
            'N6DataPush',
            'N6DataSources',
            'N6GitLabTools',
            'N6KscApi',
            'N6Portal',
            'N6Push',
            'N6RestApi',
        })
    else:
        # For Python 3: let's exclude any Python-2-only stuff.
        excluded_from_all.update({
            N6_CORE,
            N6_CORE_LIB,
        })
    return excluded_from_all


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
                        help=('one or more N6* directory names identifying n6 '
                              'components to be set up, or a special value '
                              '"all" (to set up all components considered '
                              'default for the Python version being used)'))
    parser.add_argument('-a', '--action',
                        default=DEFAULT_ACTION,
                        metavar='ARGUMENT-FOR-SETUP',
                        help=('argument for setup.py, for example "install" '
                              'or "develop" (default: "{}")'.format(
                                  DEFAULT_ACTION)))
    parser.add_argument('-L', '--no-n6lib',
                        action='store_true',
                        help=('disable automatic setup of N6Lib and N6SDK '
                              '(by default they are always set up before any '
                              'other component) and of N6CoreLib (by default '
                              'it is set up just after them if N6Core is to '
                              'be set up)'))
    parser.add_argument('-p', '--additional-packages',
                        nargs='+',
                        default=list(DEFAULT_ADDITIONAL_PACKAGES),
                        metavar='PACKAGE',
                        help=('names of PyPi packages to be installed after '
                              'the actual setup (defaults: {}; note that this '
                              'option overrides them completely)'.format(
                                  ' '.join(DEFAULT_ADDITIONAL_PACKAGES))))
    parser.add_argument('-P', '--no-additional-packages',
                        action='store_true',
                        help=('disable installation of any additional '
                              'packages (see: -p/--additional-packages)'))
    parser.add_argument('-u', '--update-basic-setup-tools',
                        action='store_true',
                        help=('execute "pip install --upgrade pip '
                              'setuptools wheel" before any actions'))
    parser.add_argument('-v', '--virtualenv-dir',
                        metavar='DIRECTORY',
                        help=('custom virtualenv directory (by default it is '
                              'determined from the VIRTUAL_ENV environment '
                              'variable, which now is {})'.format(
                                  'unset' if environ_venv_dir is None
                                  else 'set to {!r}'.format(environ_venv_dir))))
    parser.add_argument('--log-config',
                        default=repr(DEFAULT_LOG_CONFIG),
                        metavar='DICT',
                        help=('a Python dict literal specifying logging '
                              'config in the logging.config.dictConfig format '
                              '(default: {!r})'.format(
                                  repr(DEFAULT_LOG_CONFIG).replace('%', '%%'))))

    arguments = parser.parse_args()

    arguments.components = [name.rstrip('/') for name in arguments.components]
    if 'all' in arguments.components:
        excluded_from_all = get_excluded_from_all()
        arguments.components.remove('all')
        arguments.components.extend(name
                                    for name in sorted(os.listdir(this_script_dir))
                                    if (name.startswith('N6')
                                        and name not in excluded_from_all
                                        and (PY2 or not name.endswith('-py2'))
                                        and osp.isdir(name)))

    arguments.components = list(iter_nonfalse_unique(arguments.components))

    # N6SDK & N6Lib are automatically provided *if* the `L`/`--no-n6lib`
    # flag is *not* set. Also: N6CoreLib is automatically provided *if*
    # N6Core is being installed *and* the `L`/`--no-n6lib` flag is *not*
    # set.

    # * N6CoreLib, if needed, must be set up **before** any other components,
    #   **except** N6SDK and N6Lib (see below).
    if N6_CORE_LIB in arguments.components:
        arguments.components.remove(N6_CORE_LIB)
        arguments.components.insert(0, N6_CORE_LIB)
    elif N6_CORE in arguments.components and not arguments.no_n6lib:
        arguments.components.insert(0, N6_CORE_LIB)

    # * N6Lib, if needed, must be set up **before** any other components,
    #   **except** N6SDK (see below).
    if PY2:
        # (Python 2: always coerce `N6Lib` to `N6Lib-py2`)
        if (not arguments.no_n6lib) or (N6_LIB in arguments.components
                                        or N6_LIB_py2 in arguments.components):
            if N6_LIB in arguments.components: arguments.components.remove(N6_LIB)
            if N6_LIB_py2 in arguments.components: arguments.components.remove(N6_LIB_py2)
            arguments.components.insert(0, N6_LIB_py2)
    else:
        if N6_LIB in arguments.components:
            arguments.components.remove(N6_LIB)
            arguments.components.insert(0, N6_LIB)
        elif not arguments.no_n6lib:
            arguments.components.insert(0, N6_LIB)

    # * N6SDK, if needed, must the set up **before** any other components.
    if PY2:
        # (Python 2: always coerce `N6SDK` to `N6SDK-py2`)
        if (not arguments.no_n6lib) or (N6_SDK in arguments.components
                                        or N6_SDK_py2 in arguments.components):
            if N6_SDK in arguments.components: arguments.components.remove(N6_SDK)
            if N6_SDK_py2 in arguments.components: arguments.components.remove(N6_SDK_py2)
            arguments.components.insert(0, N6_SDK_py2)
    else:
        if N6_SDK in arguments.components:
            arguments.components.remove(N6_SDK)
            arguments.components.insert(0, N6_SDK)
        elif not arguments.no_n6lib:
            arguments.components.insert(0, N6_SDK)

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


successful_command_memos = []

def command(cmd):
    if venv_dir:
        cmd = '{}/bin/{}'.format(venv_dir, cmd)
    cur_dir = os.getcwd()
    LOGGER.info('executing: %r in %r', cmd, cur_dir)
    error = bool(os.system(cmd))
    if error:
        sys.exit('exiting after an external command error ({})'.format(cmd))
    successful_command_memos.append('{!r} (in {!r})'.format(cmd, cur_dir))


def main():
    global venv_dir

    arguments = parse_arguments()
    configure_logging(arguments)

    original_wd = os.getcwd()
    try:
        os.chdir(this_script_dir)
        if arguments.virtualenv_dir:
            venv_dir = osp.abspath(arguments.virtualenv_dir)

        if arguments.update_basic_setup_tools:
            command("pip install --upgrade pip setuptools wheel")
            LOGGER.info("'pip', 'setuptools' and 'wheel' updated (if possible)")

        if PY2:
            # This is a temporary workaround (see: #8602).
            importlib_metadata_pkg = 'importlib-metadata==2.1.3'
            command("pip install {}".format(importlib_metadata_pkg))
            LOGGER.info("'{}' installed".format(importlib_metadata_pkg))

        for dirname in arguments.components:
            os.chdir(osp.join(this_script_dir, dirname))
            command("python setup.py {}".format(arguments.action))
            LOGGER.info("%r setup done", dirname)

        os.chdir(this_script_dir)
        for pkgname in arguments.additional_packages:
            command("pip install '{}'".format(pkgname))
            LOGGER.info("%r installed", pkgname)

    except SystemExit as exc:
        status = exc.args[0] if exc.args else 0
        msg = (status if isinstance(status, str)
               else 'exiting with status: {!r}'.format(status))
        LOGGER.error(msg)
        raise
    except:
        LOGGER.critical('fatal error:', exc_info=True)
        raise
    finally:
        os.chdir(original_wd)

    if successful_command_memos:
        LOGGER.info('the following external commands '
                    'have been successfully executed:\n* '
                    + '\n* '.join(successful_command_memos))


if __name__ == '__main__':
    main()

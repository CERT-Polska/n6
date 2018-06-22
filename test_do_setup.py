#!/usr/bin/env python

import contextlib
import unittest
import sys
from collections import Iterator, namedtuple

from do_setup import (
    parse_arguments,
    iter_nonfalse_unique,
    command,
    main,
)


#
# Some helpers (here we don't use any external libs, such as mock...)

Case = namedtuple('Case', 'input, expected')

_CallBase = namedtuple('_CallBase', 'name, args, kwargs')


class Call(_CallBase):
    def __new__(cls, name, *args, **kwargs):
        return super(Call, cls).__new__(cls, name, args, kwargs)


class PrototypeDict(dict):
    def copy_with(self, **kwargs):
        return dict(self, **kwargs)


def using_template_and_cases(cls):
    """
    A class decorator that generates test methods and ads them to the class...
    """

    def make_test(label, test_args):
        def test(self):
            return self.TEMPLATE(*test_args)
        test.__name__ = 'test__{}'.format(label)
        return test

    for label, test_args in cls.CASES.items():
        test = make_test(label, test_args)
        setattr(cls, test.__name__, test)

    return cls


@contextlib.contextmanager
def patch(obj, attr_name, mock_value):
    """A very simple substitute of mock.patch."""
    no_attr = object()
    orig_value = getattr(obj, attr_name, no_attr)
    try:
        setattr(obj, attr_name, mock_value)
        yield
    finally:
        if orig_value is no_attr:
            delattr(obj, attr_name)
        else:
            setattr(obj, attr_name, orig_value)


def callable_mock(name):
    def mock(self, *args, **kwargs):
        self.calls.append(Call(name, *args, **kwargs))
        result = self.call_results.get(name)
        if callable(result):
            return result(*args, **kwargs)
        else:
            return result
    mock.__name__ = 'mock__{}'.format(name)
    return mock


#
# Template of a dict of parsed arguments

PARSED_ARGS = PrototypeDict({
    'action': 'install',
    'additional_packages': ['mock==1.0.1', 'nose', 'coverage', 'pylint'],
    'components': ['N6SDK', 'N6Lib', 'foo'],
    'log_config': {
        'formatters': {'brief': {'format': '\n%(asctime)s [%(levelname)s] %(message)s'}},
        'handlers': {'console': {'class': 'logging.StreamHandler',
                                 'formatter': 'brief',
                                 'stream': 'ext://sys.stdout'}},
        'root': {'handlers': ['console'], 'level': 'INFO'},
        'version': 1},
    'no_additional_packages': False,
    'no_n6lib': False,
    'update_pip_and_setuptools': False,
    'virtualenv_dir': None,
 })


#
# Actual tests

class Test__iter_nonfalse_unique(unittest.TestCase):

    def setUp(self):
        self.INPUT_SEQ = [1, 7, 3, 1, 4, 0, '', [], 6, 4, '7', 4, 4]
        self.EXPECTED_SEQ = [1, 7, 3, 4, 6, '7']

    def _test(self, input):
        result = iter_nonfalse_unique(input)
        self.assertIsInstance(result, Iterator)
        self.assertEqual(list(result), self.EXPECTED_SEQ)

    def test__seq(self):
        seq = self.INPUT_SEQ
        self._test(seq)

    def test__iterator(self):
        iterator = iter(self.INPUT_SEQ)
        self._test(iter(iterator))


@using_template_and_cases
class Test__parse_arguments(unittest.TestCase):

    CASES = dict(
        one_component = Case(
            input=['foo'],
            expected=PARSED_ARGS.copy(),
        ),
        several_components = Case(
            input=['N6Core', 'N6Lib', 'N6Blablabla'],  # note: 'N6SDK' and 'N6Lib' will be first
            expected=PARSED_ARGS.copy_with(components=['N6SDK', 'N6Lib', 'N6Core', 'N6Blablabla']),
        ),
        several_components2 = Case(
            input=['N6Core', 'N6Lib',
                   'N6SDK', 'N6Blablabla'],            # note: 'N6SDK' and 'N6Lib' will be first
            expected=PARSED_ARGS.copy_with(components=['N6SDK', 'N6Lib', 'N6Core', 'N6Blablabla']),
        ),
        with_all = Case(
            input=['all', 'foo'],  # patched os.listdir() will return ['N6-a', 'N6-b', 'N6-c']
            expected=PARSED_ARGS.copy_with(components=['N6SDK', 'N6Lib',
                                                       'foo', 'N6-a', 'N6-b', 'N6-c']),
        ),
        # --action
        opt_action = Case(
            input=['--action', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam'),
        ),
        opt_action_short = Case(
            input=['-a', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam'),
        ),
        # --no-n6lib
        opt_no_n6lib = Case(
            input=['--no-n6lib', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True, components=['foo']),
        ),
        opt_no_n6lib_short = Case(
            input=['-L', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True, components=['foo']),
        ),
        # --additional-packages
        opt_additional_packages = Case(
            input=['--additional-packages', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham']),
        ),
        opt_additional_packages_short = Case(
            input=['-p', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham']),
        ),
        # --no-additional-packages
        opt_no_additional_packages = Case(
            input=['--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True, additional_packages=[]),
        ),
        opt_no_additional_packages_short = Case(
            input=['-P', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True, additional_packages=[]),
        ),
        opt_additional_packages_and_no_additional_packages = Case(
            input=['--additional-packages', 'spam', 'ham', '--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True, additional_packages=[]),
        ),
        # --update-pip-and-setuptools
        opt_update_pip_and_setuptools = Case(
            input=['--update-pip-and-setuptools', 'foo'],
            expected=PARSED_ARGS.copy_with(update_pip_and_setuptools=True),
        ),
        opt_update_pip_and_setuptools_short = Case(
            input=['-u', 'foo'],
            expected=PARSED_ARGS.copy_with(update_pip_and_setuptools=True),
        ),
        # --virtualenv-dir
        opt_virtualenv_dir = Case(
            input=['--virtualenv-dir', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir'),
        ),
        opt_virtualenv_dir_short = Case(
            input=['-v', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir'),
        ),
        # --log-config
        opt_log_config = Case(
            input=['--log-config', '{"spam": "ham"}', 'foo'],
            expected=PARSED_ARGS.copy_with(log_config={'spam': 'ham'}),
        ),
    )

    def TEMPLATE(self, raw, parsed_expected):
        import os
        import os.path as osp
        with patch(os, 'listdir', (lambda s: ['N6-a', 'N6-b', 'N6-c', 'other-dir'])), \
             patch(osp, 'isdir', (lambda s: True)), \
             patch(sys, 'argv', ['do_setup.py'] + raw):
            parsed_actual = vars(parse_arguments())
            self.assertEqual(parsed_actual,
                             parsed_expected)


class Test__command(unittest.TestCase):

    mock__os_system = callable_mock('os.system')
    mock__os_getcwd = callable_mock('os.getcwd')
    mock__sys_exit = callable_mock('sys.exit')
    mock__do_setup_LOGGER_info = callable_mock('do_setup.LOGGER.info')

    def setUp(self):
        self.SOME_COMMAND = 'some-command --foo'
        self.SOME_CWD = '/some/cwd'
        self.call_results = {
            'os.system': 0,
            'os.getcwd': self.SOME_CWD,
        }
        self.calls = []

    @contextlib.contextmanager
    def _patch(self, venv_dir=None):
        import os
        import do_setup
        class mock__do_setup_LOGGER: pass
        with patch(do_setup, 'LOGGER', mock__do_setup_LOGGER), \
             patch(do_setup.LOGGER, 'info', self.mock__do_setup_LOGGER_info), \
             patch(os, 'system', self.mock__os_system), \
             patch(os, 'getcwd', self.mock__os_getcwd), \
             patch(sys, 'exit', self.mock__sys_exit), \
             patch(do_setup, 'venv_dir', venv_dir):
            yield

    def test__no_venv_dir(self):
        with self._patch():
            command(self.SOME_COMMAND)
            self.assertEqual(self.calls, [
                Call('os.getcwd'),
                Call('do_setup.LOGGER.info',
                     'executing: %r in %r', self.SOME_COMMAND, self.SOME_CWD),
                Call('os.system', self.SOME_COMMAND),
            ])

    def test__with_venv_dir(self):
        SOME_VENV_DIR = '/my/venv'
        BIN = SOME_VENV_DIR + '/bin/'
        with self._patch(venv_dir=SOME_VENV_DIR):
            command(self.SOME_COMMAND)
            self.assertEqual(self.calls, [
                Call('os.getcwd'),
                Call('do_setup.LOGGER.info',
                     'executing: %r in %r', BIN + self.SOME_COMMAND, self.SOME_CWD),
                Call('os.system', BIN + self.SOME_COMMAND),
            ])

    def test__error(self):
        self.call_results['os.system'] = 12345  # non-zero -> error
        with self._patch():
            command(self.SOME_COMMAND)
            self.assertEqual(self.calls, [
                Call('os.getcwd'),
                Call('do_setup.LOGGER.info',
                     'executing: %r in %r', self.SOME_COMMAND, self.SOME_CWD),
                Call('os.system', self.SOME_COMMAND),
                Call('sys.exit', ('exiting after an external '
                                  'command error ({})'.format(self.SOME_COMMAND))),
            ])


@using_template_and_cases
class Test__main(unittest.TestCase):

    mock__os_getcwd = callable_mock('os.getcwd')
    mock__os_chdir = callable_mock('os.chdir')
    mock__osp_abspath = callable_mock('osp.abspath')
    mock__do_setup_LOGGER_info = callable_mock('do_setup.LOGGER.info')
    mock__do_setup_LOGGER_error = callable_mock('do_setup.LOGGER.error')
    mock__do_setup_LOGGER_critical = callable_mock('do_setup.LOGGER.critical')
    mock__do_setup_parse_arguments = callable_mock('do_setup.parse_arguments')
    mock__do_setup_configure_logging = callable_mock('do_setup.configure_logging')
    mock__do_setup_command = callable_mock('do_setup.command')

    def setUp(self):
        import argparse
        self.THIS_SCRIPT_DIR = '/this/script/dir'
        self.ORIGINAL_WD = '/original/wd'
        self.ORIGINAL_VENV_DIR = '/original/venv/dir'
        self.CUSTOM_VENV_DIR = '/custom/venv/dir'
        self.ABSPATH_PREFIX = '/ABSPATH'
        self.call_results = {
            'os.getcwd': self.ORIGINAL_WD,
            'osp.abspath': (lambda *args, **kwargs: self.ABSPATH_PREFIX + args[0]),
            'do_setup.parse_arguments': argparse.Namespace(**PARSED_ARGS),
        }
        self.calls = []

    @contextlib.contextmanager
    def _patch(self):
        import os
        import os.path as osp
        import do_setup
        class mock__do_setup_LOGGER: pass
        with patch(do_setup, 'LOGGER', mock__do_setup_LOGGER), \
             patch(do_setup.LOGGER, 'info', self.mock__do_setup_LOGGER_info), \
             patch(do_setup.LOGGER, 'error', self.mock__do_setup_LOGGER_error), \
             patch(do_setup.LOGGER, 'critical', self.mock__do_setup_LOGGER_critical), \
             patch(do_setup, 'this_script_dir', self.THIS_SCRIPT_DIR), \
             patch(do_setup, 'venv_dir', self.ORIGINAL_VENV_DIR), \
             patch(do_setup, 'parse_arguments', self.mock__do_setup_parse_arguments), \
             patch(do_setup, 'configure_logging', self.mock__do_setup_configure_logging), \
             patch(do_setup, 'command', self.mock__do_setup_command), \
             patch(os, 'getcwd', self.mock__os_getcwd), \
             patch(os, 'chdir', self.mock__os_chdir), \
             patch(osp, 'abspath', self.mock__osp_abspath):
            yield

    def test__install__components__additional_packages(self):
        import do_setup
        with self._patch():
            main()
            self.assertEqual(do_setup.venv_dir, self.ORIGINAL_VENV_DIR)
            self.assertEqual(self.calls, [
                Call('do_setup.parse_arguments'),
                Call('do_setup.configure_logging', self.call_results['do_setup.parse_arguments']),
                Call('os.getcwd'),
                Call('os.chdir', self.THIS_SCRIPT_DIR),

                Call('os.chdir', self.THIS_SCRIPT_DIR + '/N6SDK'),
                Call('do_setup.command', 'python setup.py install'),
                Call('do_setup.LOGGER.info', "%r setup done", 'N6SDK'),
                Call('os.chdir', self.THIS_SCRIPT_DIR + '/N6Lib'),
                Call('do_setup.command', 'python setup.py install'),
                Call('do_setup.LOGGER.info', "%r setup done", 'N6Lib'),
                Call('os.chdir', self.THIS_SCRIPT_DIR + '/foo'),
                Call('do_setup.command', 'python setup.py install'),
                Call('do_setup.LOGGER.info', "%r setup done", 'foo'),

                Call('os.chdir', self.THIS_SCRIPT_DIR),
                Call('do_setup.command', 'pip install mock==1.0.1'),
                Call('do_setup.LOGGER.info', "%r installed", 'mock==1.0.1'),
                Call('do_setup.command', 'pip install nose'),
                Call('do_setup.LOGGER.info', "%r installed", 'nose'),
                Call('do_setup.command', 'pip install coverage'),
                Call('do_setup.LOGGER.info', "%r installed", 'coverage'),
                Call('do_setup.command', 'pip install pylint'),
                Call('do_setup.LOGGER.info', "%r installed", 'pylint'),

                Call('os.chdir', self.ORIGINAL_WD),
            ])

    def test__develop__virtualenv_dir__update_pip_and_setuptools(self):
        import do_setup
        ARGUMENTS = self.call_results['do_setup.parse_arguments']
        ARGUMENTS.action = 'develop'
        ARGUMENTS.update_pip_and_setuptools = True
        ARGUMENTS.virtualenv_dir = self.CUSTOM_VENV_DIR
        ARGUMENTS.components = ['spaaam']
        ARGUMENTS.additional_packages = []
        with self._patch():
            main()
            self.assertEqual(do_setup.venv_dir, self.ABSPATH_PREFIX + self.CUSTOM_VENV_DIR)
            self.assertEqual(self.calls, [
                Call('do_setup.parse_arguments'),
                Call('do_setup.configure_logging', self.call_results['do_setup.parse_arguments']),
                Call('os.getcwd'),
                Call('os.chdir', self.THIS_SCRIPT_DIR),

                Call('osp.abspath', self.CUSTOM_VENV_DIR),

                Call('do_setup.command', 'pip install --upgrade pip setuptools'),
                Call('do_setup.LOGGER.info', "'pip' and 'setuptools' updated"),

                Call('os.chdir', self.THIS_SCRIPT_DIR + '/spaaam'),
                Call('do_setup.command', 'python setup.py develop'),
                Call('do_setup.LOGGER.info', "%r setup done", 'spaaam'),

                Call('os.chdir', self.THIS_SCRIPT_DIR),

                Call('os.chdir', self.ORIGINAL_WD),
            ])

    #
    # cases when command() raises an exception:

    CASES = dict(
        sys_exit = Case(
            input=(lambda *args, **kwargs: sys.exit()),
            expected=(Call('do_setup.LOGGER.error', 'exiting with status: 0'),
                      SystemExit),
        ),
        sys_exit_None = Case(
            input=(lambda *args, **kwargs: sys.exit(None)),
            expected=(Call('do_setup.LOGGER.error', 'exiting with status: 0'),
                      SystemExit),
        ),
        sys_exit_0 = Case(
            input=(lambda *args, **kwargs: sys.exit(0)),
            expected=(Call('do_setup.LOGGER.error', 'exiting with status: 0'),
                      SystemExit),
        ),
        sys_exit_1 = Case(
            input=(lambda *args, **kwargs: sys.exit(1)),
            expected=(Call('do_setup.LOGGER.error', 'exiting with status: 1'),
                      SystemExit),
        ),
        sys_exit_text = Case(
            input=(lambda *args, **kwargs: sys.exit('error message')),
            expected=(Call('do_setup.LOGGER.error', 'error message'),
                      SystemExit),
        ),
        other_exception = Case(
            input=(lambda *args, **kwargs: 1 / 0),
            expected=(Call('do_setup.LOGGER.critical', 'fatal error:', exc_info=True),
                      ZeroDivisionError),
        ),
    )

    def TEMPLATE(self, command_result, (expected_error_call, expected_exc_type)):
        self.call_results['do_setup.command'] = command_result
        with self._patch():
            with self.assertRaises(expected_exc_type):
                main()
            self.assertEqual(self.calls, [
                Call('do_setup.parse_arguments'),
                Call('do_setup.configure_logging', self.call_results['do_setup.parse_arguments']),
                Call('os.getcwd'),
                Call('os.chdir', self.THIS_SCRIPT_DIR),

                Call('os.chdir', self.THIS_SCRIPT_DIR + '/N6SDK'),
                Call('do_setup.command', 'python setup.py install'),

                expected_error_call,

                Call('os.chdir', self.ORIGINAL_WD),
            ])


if __name__ == '__main__':
    unittest.main(verbosity=2)

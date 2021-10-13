#!/usr/bin/env python

# Copyright (c) 2013-2021 NASK. All rights reserved.

import argparse
import collections as collections_abc               #3: `import collections.abc as collections_abc`
import contextlib
import copy
import os
import os.path as osp
import sys
import unittest
from collections import namedtuple

import do_setup
from do_setup import (
    parse_arguments,
    iter_nonfalse_unique,
    command,
    main,
)


#
# Some helpers (here we don't use any external libs, such as mock...)

class Case(namedtuple('Case', 'input, expected, py')):
    def __new__(cls, input, expected, py=None):
        return super(Case, cls).__new__(cls, input, expected, py)


class Call(namedtuple('Call', 'name, args, kwargs')):
    def __new__(cls, name, *args, **kwargs):
        return super(Call, cls).__new__(cls, name, args, kwargs)


class PrototypeDict(dict):
    def copy_with(self, **kwargs):
        return copy.deepcopy(dict(self, **kwargs))


def using_template_and_cases(cls):
    """
    A class decorator that generates test methods and ads them to the class...
    """

    def make_test(cls, label, test_args, py):
        def test(self):
            with patch(do_setup, 'PY2', (py == 2)):
                return self.TEMPLATE(*test_args)
        test.__name__ = 'test__{}'.format(label)
        test.__qualname__ = '{}.{}'.format(cls.__name__, test.__name__)        #3: `cls.__name__` -> `cls.__qualname__`
        return test

    for label, case in cls.CASES.items():
        test_args = case[:2]
        test = make_test(cls, label, test_args, case.py)
        setattr(cls, test.__name__, test)

    return cls


@contextlib.contextmanager
def patch(obj, attr_name, mock_value):
    """
    A very simple substitute of mock.patch.

    Note: this module cannot use anything but the standard library *and*
    initial versions of the module were written for Python 2.x -- whose
    standard library did not include mocking/patching tools; that's why
    we defined here our own (very simple) tools.
    """
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
    mock.__qualname__ = '<...>.{}'.format(mock.__name__)
    return mock


#
# Template of a dict of parsed arguments

PARSED_ARGS = PrototypeDict({
    'action': 'install',
    'additional_packages': copy.deepcopy(do_setup.DEFAULT_ADDITIONAL_PACKAGES),
    'components': ['N6SDK', 'N6Lib', 'foo'],
    'log_config': copy.deepcopy(do_setup.DEFAULT_LOG_CONFIG),
    'no_additional_packages': False,
    'no_n6lib': False,
    'update_basic_setup_tools': False,
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
        self.assertIsInstance(result, collections_abc.Iterator)
        self.assertEqual(list(result), self.EXPECTED_SEQ)

    def test__seq(self):
        seq = self.INPUT_SEQ
        self._test(seq)

    def test__iterator(self):
        iterator = iter(self.INPUT_SEQ)
        self._test(iter(iterator))


@using_template_and_cases
class Test__parse_arguments(unittest.TestCase):

    maxDiff = None

    N6SDK_2 = 'N6SDK-py2'
    N6SDK_3 = 'N6SDK'

    N6Lib_2 = 'N6Lib-py2'
    N6Lib_3 = 'N6Lib'

    COMPONENTS_2 = [N6SDK_2, N6Lib_2, 'foo']

    CASES = dict(
        # note that always, when it comes to given component dir names:
        # * trailing '/' are removed
        # * duplicates are omitted
        # * 'N6SDK', 'N6Lib', 'N6CoreLib' (if present, in this order)
        #   are moved to the beginning
        one_component = Case(
            input=['foo'],
            expected=PARSED_ARGS.copy_with(),
        ),
        several_components1_py2 = Case(
            py=2,
            input=['N6Core/', 'N6Blabla///', 'N6Blabla', '7', 'N6Core/'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',    # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components1_py3 = Case(
            py=3,
            input=['N6Core/', 'N6Blabla///', 'N6Blabla', '7', 'N6Core/'],
            # (note: expecting the same as for Python 2)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3, 'N6CoreLib',    # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components2_py2_coerced_n6lib = Case(
            py=2,
            input=['N6Core', 'N6Lib', 'N6Blabla', '7'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2,                          # auto
                                                       N6Lib_2,                          # coerced
                                                       'N6CoreLib',                      # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components2_py2_explicit_n6lib = Case(
            py=2,
            input=['N6Core', 'N6Lib-py2', 'N6Blabla', '7'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2,                          # auto
                                                       N6Lib_2,                          # explicit
                                                       'N6CoreLib',                      # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components2_py2_excess_n6lib = Case(
            py=2,
            input=['N6Core', 'N6Lib', 'N6Lib-py2', 'N6Blabla', '7'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2,                          # auto
                                                       N6Lib_2,                     # excess merged
                                                       'N6CoreLib',                      # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components2_py3 = Case(
            py=3,
            input=['N6Core', 'N6Lib', 'N6Blabla', '7'],
            # (note: expecting the same as for Python 2)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3,                          # auto
                                                       N6Lib_3,                          # explicit
                                                       'N6CoreLib',                      # auto
                                                       'N6Core', 'N6Blabla', '7']),      # explicit
        ),
        several_components3_py2 = Case(
            py=2,
            input=['N6Core', 'N6Lib/', 'N6CoreLib', 'N6CoreLib///', '7', 'N6CoreLib//',
                   'N6CoreLib/', 'N6CoreLib', 'N6SDK', 'N6Blabla', 'N6SDK'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2,                 # coerced
                                                       'N6CoreLib',                      # explicit
                                                       'N6Core', '7', 'N6Blabla']),      # explicit
        ),
        several_components3_py3 = Case(
            py=3,
            input=['N6Core', 'N6Lib/', 'N6CoreLib', 'N6CoreLib///', '7', 'N6CoreLib//',
                   'N6CoreLib/', 'N6CoreLib', 'N6SDK', 'N6Blabla', 'N6SDK'],
            # (note: expecting the same as for Python 2)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3, 'N6CoreLib',    # explicit
                                                       'N6Core', '7', 'N6Blabla']),      # explicit
        ),
        several_components4_py2 = Case(
            py=2,
            input=['N6Blabla', 'N6Core'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',    # auto
                                                       'N6Blabla', 'N6Core']),           # explicit
        ),
        several_components4_py3 = Case(
            py=3,
            input=['N6Blabla', 'N6Core'],
            # (note: expecting the same as for Python 2)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3, 'N6CoreLib',    # auto
                                                       'N6Blabla', 'N6Core']),           # explicit
        ),
        several_components5_py2 = Case(
            py=2,
            input=['N6Blabla'],
            # (note: `N6Core` is *not* given, so 'N6CoreLib' is *not* auto-provided)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2,                 # auto
                                                       'N6Blabla']),                     # explicit
        ),
        several_components5_py3 = Case(
            py=3,
            input=['N6Blabla'],
            # (note: expecting the same as for Python 2)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3,                 # auto
                                                       'N6Blabla']),                     # explicit
        ),

        # (patched os.listdir() provides: 'x','N6b','N6-py2','N6a','N6GridFSMount','N6Core','yyy')
        with_all1_py2 = Case(
            py=2,
            input=['all'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',       # auto
                                                       'N6-py2', 'N6Core', 'N6a', 'N6b']),  # "all"
        ),
        with_all1_py3 = Case(
            py=3,
            input=['all'],
            # (note: for Python 3, the "all" special value *neither* denotes
            # any Py3-excluded components *nor* any "*-py2" components)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3,                 # auto
                                                       'N6a', 'N6b']),                   # "all"
        ),
        with_all2_py2 = Case(
            py=2,
            input=['all', 'foo'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',       # auto
                                                       'foo',                               # expl.
                                                       'N6-py2', 'N6Core', 'N6a', 'N6b']),  # "all"
        ),
        with_all2_py3 = Case(
            py=3,
            input=['all', 'foo'],
            # (note: for Python 3, the "all" special value *neither* denotes
            # any Py3-excluded components *nor* any "*-py2" components)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3,                 # auto
                                                       'foo',                            # explicit
                                                       'N6a', 'N6b']),                   # "all"
        ),
        with_all3_py2_auto_n6sdk_and_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'foo'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',    # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py2_coerced_n6sdk_and_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'N6Lib', 'foo', 'N6SDK'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2,                 # coerced
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py2_excess_n6sdk_and_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'N6Lib', 'foo', 'N6SDK-py2', 'N6SDK', 'N6Lib-py2'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2,            # excess merged
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py2_coerced_n6sdk_explicit_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'N6Lib-py2', 'foo', 'N6SDK'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2,                          # coerced
                                                       N6Lib_2,                          # explicit
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py2_explicit_n6sdk_coerced_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'N6Lib', 'foo', 'N6SDK-py2'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2,                          # explicit
                                                       N6Lib_2,                          # coerced
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py2_explicit_n6sdk_and_n6lib = Case(
            py=2,
            input=['all', 'N6b', 'N6Core', 'N6Lib-py2', 'foo', 'N6SDK-py2'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2,                 # explicit
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6-py2', 'N6a']),                # "all"
        ),
        with_all3_py3 = Case(
            py=3,
            input=['all', 'N6b', 'N6Core', 'N6Lib', 'foo', 'N6SDK'],
            # (note: for Python 3, the "all" special value *neither* denotes
            # any Py3-excluded components *nor* any "*-py2" components; but,
            # also, note that here `N6Core` is given explicitly -- so it
            # *is* expected, and 'N6CoreLib' is expected as well because
            # of being auto-provided)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3,                 # explicit
                                                       'N6CoreLib',                      # auto
                                                       'N6b', 'N6Core', 'foo',           # explicit
                                                       'N6a']),                          # "all"
        ),
        with_all4_py2 = Case(
            py=2,
            input=['all', 'foo', 'N6-py2'],
            expected=PARSED_ARGS.copy_with(components=[N6SDK_2, N6Lib_2, 'N6CoreLib',    # auto
                                                       'foo', 'N6-py2',                  # explicit
                                                       'N6Core', 'N6a', 'N6b']),         # "all"
        ),
        with_all4_py3 = Case(
            py=3,
            input=['all', 'foo', 'N6-py2'],
            # (note: for Python 3, the "all" special value *neither* denotes
            # any Py3-excluded components *nor* any "*-py2" components; but,
            # also, note that here "N6-py2" is given explicitly -- so it
            # *is* expected)
            expected=PARSED_ARGS.copy_with(components=[N6SDK_3, N6Lib_3,                 # auto
                                                       'foo', 'N6-py2',                  # explicit
                                                       'N6a', 'N6b']),                   # "all"
        ),

        # --action
        opt_action_py2 = Case(
            py=2,
            input=['--action', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam',
                                           components=COMPONENTS_2),
        ),
        opt_action_py3 = Case(
            py=3,
            input=['--action', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam'),
        ),
        opt_action_short_py2 = Case(
            py=2,
            input=['-a', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam',
                                           components=COMPONENTS_2),
        ),
        opt_action_short_py3 = Case(
            py=3,
            input=['-a', 'spam', 'foo'],
            expected=PARSED_ARGS.copy_with(action='spam'),
        ),

        # --no-n6lib
        opt_no_n6lib_py2 = Case(
            py=2,
            input=['--no-n6lib', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True,
                                           components=['foo']),
        ),
        opt_no_n6lib_py3 = Case(
            py=3,
            input=['--no-n6lib', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True,
                                           components=['foo']),
        ),
        opt_no_n6lib_short_py2 = Case(
            py=2,
            input=['-L', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True,
                                           components=['foo']),
        ),
        opt_no_n6lib_short_py3 = Case(
            py=3,
            input=['-L', 'foo'],
            expected=PARSED_ARGS.copy_with(no_n6lib=True,
                                           components=['foo']),
        ),

        # --additional-packages
        opt_additional_packages_py2 = Case(
            py=2,
            input=['--additional-packages', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham'],
                                           components=COMPONENTS_2),
        ),
        opt_additional_packages_py3 = Case(
            py=3,
            input=['--additional-packages', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham']),
        ),
        opt_additional_packages_short_py2 = Case(
            py=2,
            input=['-p', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham'],
                                           components=COMPONENTS_2),
        ),
        opt_additional_packages_short_py3 = Case(
            py=3,
            input=['-p', 'spam', 'ham', '--', 'foo'],
            expected=PARSED_ARGS.copy_with(additional_packages=['spam', 'ham']),
        ),

        # --no-additional-packages
        opt_no_additional_packages_py2 = Case(
            py=2,
            input=['--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[],
                                           components=COMPONENTS_2),
        ),
        opt_no_additional_packages_py3 = Case(
            py=3,
            input=['--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[]),
        ),
        opt_no_additional_packages_short_py2 = Case(
            py=2,
            input=['-P', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[],
                                           components=COMPONENTS_2),
        ),
        opt_no_additional_packages_short_py3 = Case(
            py=3,
            input=['-P', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[]),
        ),
        opt_additional_packages_and_no_additional_packages_py2 = Case(
            py=2,
            input=['--additional-packages', 'spam', 'ham', '--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[],
                                           components=COMPONENTS_2),
        ),
        opt_additional_packages_and_no_additional_packages_py3 = Case(
            py=3,
            input=['--additional-packages', 'spam', 'ham', '--no-additional-packages', 'foo'],
            expected=PARSED_ARGS.copy_with(no_additional_packages=True,
                                           additional_packages=[]),
        ),

        # --update-basic-setup-tools
        opt_update_basic_setup_tools_py2 = Case(
            py=2,
            input=['--update-basic-setup-tools', 'foo'],
            expected=PARSED_ARGS.copy_with(update_basic_setup_tools=True,
                                           components=COMPONENTS_2),
        ),
        opt_update_basic_setup_tools_py3 = Case(
            py=3,
            input=['--update-basic-setup-tools', 'foo'],
            expected=PARSED_ARGS.copy_with(update_basic_setup_tools=True),
        ),
        opt_update_basic_setup_tools_short_py2 = Case(
            py=2,
            input=['-u', 'foo'],
            expected=PARSED_ARGS.copy_with(update_basic_setup_tools=True,
                                           components=COMPONENTS_2),
        ),
        opt_update_basic_setup_tools_short_py3 = Case(
            py=3,
            input=['-u', 'foo'],
            expected=PARSED_ARGS.copy_with(update_basic_setup_tools=True),
        ),

        # --virtualenv-dir
        opt_virtualenv_dir_py2 = Case(
            py=2,
            input=['--virtualenv-dir', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir',
                                           components=COMPONENTS_2),
        ),
        opt_virtualenv_dir_py3 = Case(
            py=3,
            input=['--virtualenv-dir', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir'),
        ),
        opt_virtualenv_dir_short_py2 = Case(
            py=2,
            input=['-v', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir',
                                           components=COMPONENTS_2),
        ),
        opt_virtualenv_dir_short_py3 = Case(
            py=3,
            input=['-v', 'some-dir', 'foo'],
            expected=PARSED_ARGS.copy_with(virtualenv_dir='some-dir'),
        ),

        # --log-config
        opt_log_config_py2 = Case(
            py=2,
            input=['--log-config', '{"spam": "ham"}', 'foo'],
            expected=PARSED_ARGS.copy_with(log_config={'spam': 'ham'},
                                           components=COMPONENTS_2),
        ),
        opt_log_config_py3 = Case(
            py=3,
            input=['--log-config', '{"spam": "ham"}', 'foo'],
            expected=PARSED_ARGS.copy_with(log_config={'spam': 'ham'}),
        ),
    )

    def TEMPLATE(self, raw, parsed_expected):
        with patch(os, 'listdir', (lambda s: ['x',
                                              'N6b', 'N6-py2', 'N6a', 'N6GridFSMount', 'N6Core',
                                              'yyy'])), \
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
        self.SOME_COMMAND = 'some-command --some-arg'
        self.SOME_CWD = '/some/cwd'
        self.call_results = {
            'os.system': 0,
            'os.getcwd': self.SOME_CWD,
        }
        self.calls = []

    @contextlib.contextmanager
    def _patch(self, venv_dir=None):
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
        cmd_memos = do_setup.successful_command_memos
        del cmd_memos[:]
        self.THIS_SCRIPT_DIR = '/this/script/dir'
        self.ORIGINAL_WD = '/original/wd'
        self.ORIGINAL_VENV_DIR = '/original/venv/dir'
        self.CUSTOM_VENV_DIR = '/custom/venv/dir'
        self.ABSPATH_PREFIX = '/ABSPATH'
        self.call_results = {
            'os.getcwd': self.ORIGINAL_WD,
            'osp.abspath': (lambda *args, **kwargs: self.ABSPATH_PREFIX + args[0]),
            'do_setup.parse_arguments': argparse.Namespace(**PARSED_ARGS),
            'do_setup.command': (lambda cmd: cmd_memos.append('<mocked memo: {!r}>'.format(cmd)))
        }
        self.calls = []

    @contextlib.contextmanager
    def _patch(self):
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

                ] + ([
                    Call('do_setup.command', "pip install 'pytest==4.6.11'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pytest==4.6.11'),
                    Call('do_setup.command', "pip install 'pytest-cov==2.12.1'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pytest-cov==2.12.1'),
                    Call('do_setup.command', "pip install 'coverage<6.0'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'coverage<6.0'),
                    Call('do_setup.command', "pip install 'astroid==1.6.6'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'astroid==1.6.6'),
                    Call('do_setup.command', "pip install 'pylint==1.9.5'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pylint==1.9.5'),
                    Call('do_setup.command', "pip install 'mkdocs==1.0.4'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'mkdocs==1.0.4'),
                    Call('do_setup.command', "pip install 'waitress<2.0'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'waitress<2.0'),
                ] if do_setup.PY2 else [
                    Call('do_setup.command', "pip install 'pytest==4.6.11'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pytest==4.6.11'),
                    Call('do_setup.command', "pip install 'pytest-cov==2.12.1'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pytest-cov==2.12.1'),
                    Call('do_setup.command', "pip install 'coverage'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'coverage'),
                    Call('do_setup.command', "pip install 'pylint'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'pylint'),
                    Call('do_setup.command', "pip install 'mkdocs'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'mkdocs'),
                    Call('do_setup.command', "pip install 'waitress'"),
                    Call('do_setup.LOGGER.info', "%r installed", 'waitress'),
                ]) + [
                Call('os.chdir', self.ORIGINAL_WD),
                Call('do_setup.LOGGER.info',
                     "the following external commands "
                     "have been successfully executed:"
                     "\n* <mocked memo: 'python setup.py install'>"
                     "\n* <mocked memo: 'python setup.py install'>"
                     "\n* <mocked memo: 'python setup.py install'>"
                     + ("\n* <mocked memo: \"pip install 'pytest==4.6.11'\">"
                        "\n* <mocked memo: \"pip install 'pytest-cov==2.12.1'\">"
                        "\n* <mocked memo: \"pip install 'coverage<6.0'\">"
                        "\n* <mocked memo: \"pip install 'astroid==1.6.6'\">"
                        "\n* <mocked memo: \"pip install 'pylint==1.9.5'\">"
                        "\n* <mocked memo: \"pip install 'mkdocs==1.0.4'\">"
                        "\n* <mocked memo: \"pip install 'waitress<2.0'\">"
                        if do_setup.PY2 else
                        "\n* <mocked memo: \"pip install 'pytest==4.6.11'\">"
                        "\n* <mocked memo: \"pip install 'pytest-cov==2.12.1'\">"
                        "\n* <mocked memo: \"pip install 'coverage'\">"
                        "\n* <mocked memo: \"pip install 'pylint'\">"
                        "\n* <mocked memo: \"pip install 'mkdocs'\">"
                        "\n* <mocked memo: \"pip install 'waitress'\">")),
                ]
            )

    def test__develop__virtualenv_dir__update_basic_setup_tools(self):
        ARGUMENTS = self.call_results['do_setup.parse_arguments']
        ARGUMENTS.action = 'develop'
        ARGUMENTS.update_basic_setup_tools = True
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

                Call('do_setup.command', 'pip install --upgrade pip setuptools wheel'),
                Call('do_setup.LOGGER.info', ("'pip', 'setuptools' and 'wheel' "
                                              "updated (if possible)")),

                Call('os.chdir', self.THIS_SCRIPT_DIR + '/spaaam'),
                Call('do_setup.command', 'python setup.py develop'),
                Call('do_setup.LOGGER.info', "%r setup done", 'spaaam'),

                Call('os.chdir', self.THIS_SCRIPT_DIR),
                Call('os.chdir', self.ORIGINAL_WD),
                Call('do_setup.LOGGER.info',
                     "the following external commands have "
                     "been successfully executed:"
                     "\n* <mocked memo: 'pip install --upgrade pip setuptools wheel'>"
                     "\n* <mocked memo: 'python setup.py develop'>")
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

    def TEMPLATE(self, command_result, expected_error_stuff):
        expected_error_call, expected_exc_type = expected_error_stuff
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

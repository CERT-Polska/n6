# Copyright (c) 2013-2018 NASK. All rights reserved.

import sys
import types
import unittest

from mock import call, patch

from n6lib.unit_test_helpers import run_module_doctests


@patch('sys.stdout')
class Test__run_module_doctests(unittest.TestCase):

    def setUp(self):
        self.module = types.ModuleType('blablabla')
        self.success = ('3 doctests ran successfully for module {!r}\n'
                        .format(self.module))

    @patch('doctest.testmod', return_value=(0, 3))
    def test_success_for_specified_module(self,
                                          mocked__testmod,
                                          mocked__stdout):
        failures, tests = run_module_doctests(self.module, 'foo', bar='spam')
        mocked__testmod.assert_called_once_with(self.module, 'foo', bar='spam')
        self._do_assertions_for_success(mocked__stdout, failures, tests)

    @patch('doctest.testmod', return_value=(3, 3))
    def test_failure_for_specified_module(self,
                                          mocked__testmod,
                                          mocked__stdout):
        failures, tests = run_module_doctests(self.module, 'foo', bar='spam')
        mocked__testmod.assert_called_once_with(self.module, 'foo', bar='spam')
        self._do_assertions_for_failure(mocked__stdout, failures, tests)

    @patch('doctest.testmod', return_value=(0, 3))
    def test_success_for_unspecified_module(self,
                                            mocked__testmod,
                                            mocked__stdout):
        with patch.dict(sys.modules, {'__main__': self.module}):
            failures, tests = run_module_doctests(bar='spam')
        mocked__testmod.assert_called_once_with(None, bar='spam')
        self._do_assertions_for_success(mocked__stdout, failures, tests)

    @patch('doctest.testmod', return_value=(3, 3))
    def test_failure_for_unspecified_module(self,
                                            mocked__testmod,
                                            mocked__stdout):
        with patch.dict(sys.modules, {'__main__': self.module}):
            failures, tests = run_module_doctests(bar='spam')
        mocked__testmod.assert_called_once_with(None, bar='spam')
        self._do_assertions_for_failure(mocked__stdout, failures, tests)

    def _do_assertions_for_success(self, mocked__stdout, failures, tests):
        mocked__stdout.write.assert_called_once_with(self.success)
        self.assertEqual(failures, 0)
        self.assertEqual(tests, 3)

    def _do_assertions_for_failure(self, mocked__stdout, failures, tests):
        self.assertNotIn(call(self.success), mocked__stdout.write.mock_calls)
        self.assertEqual(failures, 3)
        self.assertEqual(tests, 3)

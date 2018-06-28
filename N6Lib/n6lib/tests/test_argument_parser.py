# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest
from argparse import Namespace

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.argument_parser import N6ArgumentParser, N6ConfigValuesAction


@expand
class TestN6ConfigValuesAction(unittest.TestCase):

    @paramseq
    def _test_cases(cls):
        yield param(data=None, expected=TypeError)
        yield param(data=['section1.option1=value1', 'section1.option2=value2',
                          'section2.option1=value3'],
                    expected={'section1': {'option1': 'value1', 'option2': 'value2'},
                              'section2': {'option1': 'value3'}})
        yield param(data=[], expected={})

    @foreach(_test_cases)
    def test_custom_config_action_call(self, data, expected):
        try:
            arg_parser = N6ArgumentParser()
            action = N6ConfigValuesAction(data, 'n6config_override', default={})
            namespace = Namespace(n6config_override={})
            action(arg_parser, namespace, data)
            self.assertEqual(namespace.n6config_override, expected)
        except Exception as e:
            if isinstance(e, AssertionError):
                raise
            self.assertIsInstance(e, expected)

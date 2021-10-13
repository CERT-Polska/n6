# Copyright (c) 2013-2021 NASK. All rights reserved.

import doctest
import pkgutil

import n6sdk


# induce the standard unittest discovery machinery
# to load doctests from all n6sdk submodules

def load_tests(loader, tests, *args):
    for _, name, _ in pkgutil.walk_packages(n6sdk._ABS_PATH):
        mod_suite = doctest.DocTestSuite(name)
        tests.addTests(mod_suite)
    return tests


# dissuade pytest from using that function
# (note that pytest has its own ways to discover doctests)

load_tests.__test__ = False

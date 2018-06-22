# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.


import doctest
import pkgutil

import n6sdk


# induce the standard unittest discovery machinery
# to load doctests from all n6sdk submodules

def load_tests(loader, tests, *args):
    for _, name, _ in pkgutil.walk_packages(n6sdk._ABS_PATH):
        try:
            mod_suite = doctest.DocTestSuite(name)
        except ValueError as exc:
            try:
                msg = getattr(exc, 'args', ())[1]
            except (IndexError, TypeError):
                msg = None
            if msg != 'has no tests':
                raise
        else:
            tests.addTests(mod_suite)
    return tests


# dissuade nose from using that function
# (note that nose has its own ways to discover doctests)

load_tests.__test__ = False

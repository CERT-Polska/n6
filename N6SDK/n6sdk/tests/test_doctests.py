# Copyright (c) 2014-2025 NASK. All rights reserved.

# the following function used to induce the standard *unittest*'s
# discovery machinery to load doctests from all *n6sdk* submodules;
# that's no longer supported -- *pytest* should be used instead!

def load_tests(loader, tests, *args):  # noqa
    raise RuntimeError(
        '*unittest*-specific discovery mechanism is '
        'no longer supported, use *pytest* instead!')


# dissuade *pytest* from using that function
# (note that pytest has its own ways to discover doctests)

load_tests.__test__ = False

# Copyright (c) 2013-2025 NASK. All rights reserved.

import pathlib
import sys
try:
    import do_setup
except ImportError:
    _THIS_DIR = pathlib.Path(__file__).parent.resolve()
    sys.path.insert(0, str(_THIS_DIR))
    import do_setup


def test_stub():
    assert True

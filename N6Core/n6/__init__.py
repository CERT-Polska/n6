# Copyright (c) 2020-2021 NASK. All rights reserved.

import threading

is_main_thread = isinstance(threading.current_thread(), threading._MainThread)          #3: replace `isinstance(...)` with `threading.current_thread() is threading.main_thread()`
if is_main_thread:
    # [^ This is a workaround for a problem with a late import of the n6
    # package (occurring, e.g., when trying to load some jinja templates
    # from a `@n6:...` location in a non-N6Core-related component,
    # because of some misconfiguration).]


    # Let's ensure that `TimeoutCallbackManager`, if needed, is prepared
    # as early as possible, especially to make it have full control over
    # any `signal.alarm()` calls.
    # (Note: the N6_TIMEOUT_CALLBACK_MANAGER variable needs to be set
    # *before* any import from `n6corelib` -- see the `n6corelib`'s
    # `__init__.py` file...)
    import os
    os.environ['N6_TIMEOUT_CALLBACK_MANAGER'] = 'y'
    from n6corelib.timeout_callback_manager import TimeoutCallbackManager

    # Typically, a call like the following one should have already been
    # done in  `n6corelib`'s `__init__.py` -- but in some cases (e.g., when
    # the test suite is executed) it may *not* have been done, and then
    # the following call is needed.
    TimeoutCallbackManager.ensure_preparations_and_monkey_patching_done()


    # Let's trigger the `n6lib`-provided monkey-patching (if not triggered yet).
    import n6lib                                                                   # noqa

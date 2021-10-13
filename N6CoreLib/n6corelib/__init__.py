# Copyright (c) 2020-2021 NASK. All rights reserved.

# Let's ensure that `TimeoutCallbackManager`, if needed, is prepared
# as early as possible (especially because it needs to have full
# control over any `signal.alarm()` calls...).
import os
if os.environ.get('N6_TIMEOUT_CALLBACK_MANAGER'):
    # *Only* for `N6Core` (especially, *not* for web/WSGI components --
    # such as REST API, Portal or AdminPanel [at least for now; reason:
    # Apache's `mod_wsgi` has its own signal handling machinery that may
    # conflict with TimeoutCallbackManager; also, in these components
    # TimeoutCallbackManager is hardly useful...]).
    from n6corelib.timeout_callback_manager import TimeoutCallbackManager
    TimeoutCallbackManager.ensure_preparations_and_monkey_patching_done()

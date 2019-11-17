# Let's ensure that `TimeoutCallbackManager`, if needed, is prepared
# as early as possible, especially to be sure that it has full control
# over any `signal.alarm()` calls.
# (Note: the N6_TIMEOUT_CALLBACK_MANAGER variable needs to be set
# *before* any import from `n6lib` -- see `n6lib`'s `__init__.py`...)
import os
os.environ['N6_TIMEOUT_CALLBACK_MANAGER'] = 'y'
from n6lib.timeout_callback_manager import TimeoutCallbackManager

# Typically, a call like the following one should have already been
# done in  `n6lib`'s `__init__.py` -- but in some cases (e.g., when
# the test suite is executed) it may *not* have been done, and then
# the following call is needed.
TimeoutCallbackManager.ensure_preparations_and_monkey_patching_done()


from n6lib.common_helpers import provide_surrogateescape
provide_surrogateescape()

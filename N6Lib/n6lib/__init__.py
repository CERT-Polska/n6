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
    from n6lib.timeout_callback_manager import TimeoutCallbackManager
    TimeoutCallbackManager.ensure_preparations_and_monkey_patching_done()


import atexit
import locale

from n6lib.amqp_helpers import pika_connection_client_properties_monkeypatching
from n6lib.common_helpers import provide_surrogateescape, cleanup_src
from n6lib.log_helpers import early_Formatter_class_monkeypatching

# Ensure that locale is set to 'C'.
# Especially, it is necessary for any components that parse date/time
# strings containing some C-locale-dependant elements, such as
# abbreviations of month/day names...
locale.setlocale(locale.LC_ALL, 'C')

# Provide the Python-3-like 'surrogateescape' decode error handler.
provide_surrogateescape()

# Monkey-patch logging.Formatter to use UTC time.
early_Formatter_class_monkeypatching()

# Ensure that resource files and directories extracted with
# pkg_resources stuff are removed (or at least tried to be removed).
# noinspection PyUnresolvedReferences
import logging  # <- Must be imported *before* registering cleanup_src().
atexit.register(cleanup_src)

# Monkey patch pika.Connection._client_properties to provide AMQP
# messages with better diagnosis information.
pika_connection_client_properties_monkeypatching()


# Monkey patch SQLAlchemy 0.9.x
# -- so that MySQL's/MariaDB's `utf8mb4` charset is supported
# (XXX: to be removed after SQLAlchemy upgrade)
def ensure_sqlalchemy_supports_utf8mb4():
    import functools

    import sqlalchemy
    from sqlalchemy.dialects.mysql.base import _DecodingRowProxy as mysql_DecodingRowProxy

    if sqlalchemy.__version__ >= '1.':
        return

    if getattr(mysql_DecodingRowProxy, '_n6_monkeypatched_to_enable_utf8mb4', False):
        return

    # utf8mb4-support related fix (~ backported from SQLAlchemy 1.0.0b2,
    # see: https://github.com/sqlalchemy/sqlalchemy/issues/2771)
    @functools.wraps(mysql_DecodingRowProxy.__init__)
    def __init__(self, rowproxy, charset):
        self.rowproxy = rowproxy
        self.charset = ('utf8' if charset == 'utf8mb4' else charset)

    mysql_DecodingRowProxy.__init__ = __init__
    mysql_DecodingRowProxy._n6_monkeypatched_to_enable_utf8mb4 = True

ensure_sqlalchemy_supports_utf8mb4()

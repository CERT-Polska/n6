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
import logging  # Must be imported *before* registering cleanup_src().
atexit.register(cleanup_src)

# Monkey-patch pika.Connection._client_properties to provide AMQP
# messages with better diagnosis information.
pika_connection_client_properties_monkeypatching()

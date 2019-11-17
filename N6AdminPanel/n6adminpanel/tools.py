# Copyright (c) 2013-2018 NASK. All rights reserved.

from flask_admin.tools import (
    CHAR_ESCAPE,
    CHAR_SEPARATOR,
)

from n6lib.common_helpers import as_unicode
from n6lib.data_spec import FieldValueError


ESC_TO_ORIG_CHARS = {
    '{0}{0}'.format(CHAR_ESCAPE): CHAR_ESCAPE,
    '{0}{1}'.format(CHAR_ESCAPE, CHAR_SEPARATOR): CHAR_SEPARATOR,
}


def unescape_html_attr(value):
    """
    Return original value, which had some of its characters escaped
    for it to be safe as an HTML attribute.
    """
    for esc, orig in ESC_TO_ORIG_CHARS.iteritems():
        value = value.replace(esc, orig)
    return value


def get_exception_message(exc):
    """
    Try to get a message from a raised exception.

    Args:
        `exc`:
            An instance of a raised exception.

    Returns:
        Message from exception, as unicode, or None.
    """
    if isinstance(exc, FieldValueError):
        return exc.public_message.rstrip('.') + '.'
    else:
        exc_message = getattr(exc, 'message', None)
        if exc_message and isinstance(exc_message, basestring):
            return as_unicode(exc_message).rstrip('.') + '.'
    return None

# Copyright (c) 2018-2022 NASK. All rights reserved.

import wtforms.meta
from flask_admin.tools import (
    CHAR_ESCAPE,
    CHAR_SEPARATOR,
)

from n6lib.data_spec import FieldValueError


CSRF_FIELD_NAME = 'csrf_token'
assert CSRF_FIELD_NAME == wtforms.meta.DefaultMeta.csrf_field_name

ESC_TO_ORIG_CHARS = {
    '{0}{0}'.format(CHAR_ESCAPE): CHAR_ESCAPE,
    '{0}{1}'.format(CHAR_ESCAPE, CHAR_SEPARATOR): CHAR_SEPARATOR,
}


def unescape_html_attr(value):
    """
    Return original value, which had some of its characters escaped
    for it to be safe as an HTML attribute.
    """
    for esc, orig in ESC_TO_ORIG_CHARS.items():
        value = value.replace(esc, orig)
    return value


def get_exception_message(exc):
    """
    Try to get a message from the given exception.

    Args:
        `exc`:
            An instance of a raised exception.

    Returns:
        Message from the exception, as a `str`, or None.
    """
    if isinstance(exc, FieldValueError):
        return exc.public_message.rstrip('.') + '.'
    exc_message = getattr(exc, 'message',
                          (exc.args[0] if exc.args else None))
    if exc_message and isinstance(exc_message, str):
        return exc_message.rstrip('.') + '.'
    return None

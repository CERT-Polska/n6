# Copyright (c) 2020 NASK. All rights reserved.

import unittest

from n6adminpanel.tools import unescape_html_attr
from n6adminpanel.tools import get_exception_message
from n6lib.data_spec import FieldValueError


class TestN6AdminPanelTools(unittest.TestCase):
    """Testing N6AdminPanel tools"""

    def test_unescape_html_attr(self):
        unescaped = unescape_html_attr("cert..nask.,pl")

        self.assertEqual(unescaped, "cert.nask,pl")

    def test_get_exception_message_field_value_error(self):
        exc = FieldValueError(public_message='Example FieldValueError message.')
        exc_message = get_exception_message(exc)

        self.assertEqual(exc_message, 'Example FieldValueError message.')

    def test_get_exception_message_non_field_value_error_non_empty_message_string(self):
        exc = NameError("Name error message")
        exc_message = get_exception_message(exc)

        self.assertEqual(exc_message, "Name error message.")

    def test_get_exception_message_non_field_value_error_empty_message_string(self):
        exc = NameError("")
        exc_message = get_exception_message(exc)

        self.assertEqual(exc_message, None)

    def test_get_exception_message_non_field_value_error_non_string_message(self):
        exc = NameError(5)
        exc_message = get_exception_message(exc)

        self.assertEqual(exc_message, None)

    def test_get_exception_message_non_field_value_error_without_message(self):
        exc = NameError()
        exc_message = get_exception_message(exc)

        self.assertEqual(exc_message, None)

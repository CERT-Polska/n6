#  Copyright (c) 2021-2025 NASK. All rights reserved.

from typing import Any

from n6lib.auth_db import WEB_TOKEN_TYPES
from n6lib.common_helpers import (
    ascii_str,
    as_unicode,
)
from n6lib.config import Config
from n6lib.const import CATEGORY_ENUMS
from n6lib.structured_data_conversion.converters import (
    NameValuePairConverter,
    NamespaceMappingConverter,
)
from n6lib.structured_data_conversion.exceptions import DataConversionError


#
# Actual converters provided by this module
#


# TODO: some of them are quite generic =>
#       could be moved to a more suitable place...

# TODO: tests...


def conv_int_only_positive(opt_value: str) -> int:
    n = Config.BASIC_CONVERTERS['int'](opt_value)
    if n < 1:
        raise ValueError('should be >= 1')
    return n


def conv_tuple_of_categories(opt_value: str) -> tuple[str]:
    categories = Config.BASIC_CONVERTERS['list_of_str'](opt_value)
    illegal_categories = set(categories).difference(CATEGORY_ENUMS)
    if illegal_categories:
        listing = ', '.join(map(ascii, sorted(illegal_categories)))
        raise ValueError(f'illegal (non-existent) categories: {listing}')
    return tuple(categories)


def conv_server_secret_str(opt_value: str) -> str:
    value = Config.BASIC_CONVERTERS['str'](opt_value)
    [result] = _adjust_server_secret(value)
    return result


def conv_token_type_to_settings(opt_value: str) -> dict[str, dict[str, Any]]:
    raw_dict = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)
    [result] = _adjust_token_type_to_settings(raw_dict)
    return result


def conv_web_url(opt_value: str) -> str:
    value = Config.BASIC_CONVERTERS['str'](opt_value)
    if value != ascii_str(value):
        raise ValueError('contains non-ASCII characters')
    if not value.lower().startswith(_LEGAL_WEB_URL_PREFIXES):
        descr = ' or '.join(map(ascii, _LEGAL_WEB_URL_PREFIXES))
        raise ValueError(f'does not start with {descr}')
    return value


#
# Private (module-local-only) constants and helpers
#


_LEGAL_WEB_URL_PREFIXES = ('https://', 'http://')


def _adjust_server_secret(value) -> str:
    if not isinstance(value, (str, bytes)):
        raise DataConversionError(ascii_str(
            f'not a `str` or `bytes` - its type '
            f'is `{type(value).__qualname__}`'))
    try:
        value = as_unicode(value)
    except UnicodeDecodeError:
        # We don't want to reveal the value in the traceback etc.
        raise DataConversionError('contains non-UTF-8 binary data') from None
    if not value.strip():
        raise DataConversionError('an empty or whitespace-only value')
    assert isinstance(value, str)
    yield value


def _adjust_token_max_age(value) -> int:
    orig_value = value
    value = int(value)
    if value == orig_value and not isinstance(orig_value, bool):
        yield value
    else:
        raise DataConversionError(f'{orig_value!a} is not an integer number')


_adjust_settings_of_single_token_type = NamespaceMappingConverter(
    required_input_names=[
        'server_secret',
        'token_max_age',
    ],
    input_name_to_item_converter_maker={
        'server_secret': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_server_secret,
        ),
        'token_max_age': NameValuePairConverter.maker(
            value_converter_maker=lambda: _adjust_token_max_age,
        ),
    },
)

_adjust_token_type_to_settings = NamespaceMappingConverter(
    required_input_names=sorted(WEB_TOKEN_TYPES),
    free_item_converter_maker=NameValuePairConverter.maker(
        value_converter_maker=lambda: _adjust_settings_of_single_token_type,
    ),
)

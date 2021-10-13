#  Copyright (c) 2021 NASK. All rights reserved.

from builtins import map                                                         #3--
from typing import (
    Any,
    Dict,
    Tuple,
)

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

def conv_int_only_positive(opt_value):
    # type: (str) -> int
    n = Config.BASIC_CONVERTERS['int'](opt_value)
    if n < 1:
        raise ValueError('should be >= 1')
    return n


def conv_tuple_of_categories(opt_value):
    # type: (str) -> Tuple[str]
    categories = Config.BASIC_CONVERTERS['list_of_str'](opt_value)
    illegal_categories = set(categories).difference(CATEGORY_ENUMS)
    if illegal_categories:
        raise ValueError('illegal (non-existent) categories: {}'.format(
            ', '.join(map(repr, sorted(illegal_categories)))))
    return tuple(categories)


def conv_server_secret_str(opt_value):
    # type: (...) -> str
    value = Config.BASIC_CONVERTERS['str'](opt_value)
    [result] = _adjust_server_secret(value)
    return result


def conv_token_type_to_settings(opt_value):
    # type: (str) -> Dict[str, Dict[str, Any]]
    raw_dict = Config.BASIC_CONVERTERS['py_namespaces_dict'](opt_value)
    [result] = _adjust_token_type_to_settings(raw_dict)
    return result


def conv_web_url(opt_value):
    # type: (...) -> str
    value = Config.BASIC_CONVERTERS['str'](opt_value)
    if value != ascii_str(value):
        raise ValueError('contains non-ASCII characters')
    if not value.lower().startswith(_LEGAL_WEB_URL_PREFIXES):
        raise ValueError('does not start with {}'.format(
            ' or '.join(map(repr, _LEGAL_WEB_URL_PREFIXES))))
    return value


#
# Private (module-local-only) constants and helpers
#

_LEGAL_WEB_URL_PREFIXES = ('https://', 'http://')


def _adjust_server_secret(value):
    # type: (...) -> str
    if not isinstance(value, (unicode, bytes)):                                  #3: `unicode` -> `str`
        raise DataConversionError('not a `str` or `bytes` - its type is `{}`'
                                  .format(ascii_str(type(value).__name__)))      #3: `__name__` -> `__qualname__`
    try:
        value = as_unicode(value)
    except UnicodeDecodeError:
        # We don't want to reveal the value in the traceback etc.
        raise DataConversionError('contains non-UTF-8 binary data')              #3: add: `from None`
    if not value.strip():
        raise DataConversionError('an empty or whitespace-only value')
    value = value.encode('utf-8')                                                #3--
    assert isinstance(value, str)
    yield value


def _adjust_token_max_age(value):
    # type: (...) -> int
    orig_value = value
    value = int(value)
    if value == orig_value and not isinstance(orig_value, bool):
        yield value
    else:
        raise DataConversionError('{!r} is not an integer number'.format(orig_value))


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

#  Copyright (c) 2021-2024 NASK. All rights reserved.

import base64
import hashlib
import hmac
import os
from collections.abc import Callable
from typing import (
    TypeVar,
    Union,
)

# TODO: upgrade pyotp to the newest stable version (checking all relevant
#       pyotp's change notes, and adjusting our code if necessary...).
import pyotp

from n6lib.common_helpers import (
    ascii_str,
    as_bytes,
    as_unicode,
)
from n6lib.typing_helpers import StrOrBinary


LEN_OF_SECRET_KEY = 32

TIME_STEP_WINDOW_IN_SECONDS = 30
ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS = 1

MFA_CODE_NUM_OF_DIGITS = 6
MFA_CODE_STR_PATTERN = '{:0%s}' % MFA_CODE_NUM_OF_DIGITS
MFA_CODE_MAX_VALIDITY_DURATION_IN_SECONDS = (TIME_STEP_WINDOW_IN_SECONDS *
                                             (ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS * 2 + 1))
# Let us be resistant to some system clock turbulence...
DELAY_TO_BE_SURE_THAT_MFA_CODE_EXPIRES = MFA_CODE_MAX_VALIDITY_DURATION_IN_SECONDS + 3


def generate_new_mfa_key_base() -> str:
    return as_unicode(base64.b64encode(os.urandom(64)))


def generate_secret_key(mfa_key_base: StrOrBinary,
                        server_secret: StrOrBinary) -> str:
    mfa_key_base = _conv_secret_val(mfa_key_base, as_bytes, 'the given MFA key base to `bytes`')
    server_secret = _conv_secret_val(server_secret, as_bytes, 'the given server secret to `bytes`')
    hmac_result = hmac.new(server_secret, mfa_key_base, hashlib.sha384).digest()
    return as_unicode(base64.b32encode(hmac_result)[:LEN_OF_SECRET_KEY])


def generate_secret_key_qr_code_url(secret_key: str,
                                    login: str,
                                    issuer_name: str) -> str:
    login = as_unicode(login)
    issuer_name = as_unicode(issuer_name)
    return make_totp_handler(secret_key).provisioning_uri(
        name=login,
        issuer_name=issuer_name)


def does_mfa_code_matches_now(mfa_code: Union[int, str],
                              secret_key: str) -> bool:
    mfa_code = int(mfa_code)
    mfa_code_str = MFA_CODE_STR_PATTERN.format(mfa_code)
    return make_totp_handler(secret_key).verify(
        mfa_code_str,
        valid_window=ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS)


def make_totp_handler(secret_key: str) -> pyotp.TOTP:
    secret_key = _conv_secret_val(secret_key, as_unicode, 'the given TOTP secret key to `str`')
    return pyotp.TOTP(
        secret_key,
        digits=MFA_CODE_NUM_OF_DIGITS,
        interval=TIME_STEP_WINDOW_IN_SECONDS)


_ConvArg = TypeVar('_ConvArg')
_ConvResult = TypeVar('_ConvResult')

def _conv_secret_val(val: _ConvArg,
                     conv_func: Callable[[_ConvArg], _ConvResult],
                     descr_what_to_what: str) -> _ConvResult:
    # We don't want to reveal the value in any error messages/tracebacks etc.
    try:
        return conv_func(val)
    except Exception as exc:
        exc_type = type(exc)
        error_msg = (
            f'could not convert {descr_what_to_what} '
            f'({ascii_str(exc_type.__name__)})')
    if issubclass(exc_type, ValueError):
        error_factory = ValueError
    elif issubclass(exc_type, TypeError):
        error_factory = TypeError
    else:
        error_factory = RuntimeError
    raise error_factory(error_msg)

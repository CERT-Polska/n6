#  Copyright (c) 2021 NASK. All rights reserved.

import base64
import hashlib
import hmac
import os
import sys                                                                       #3--
from typing import Union

# TODO: upgrade pyotp to the newest stable version (checking all relevant
#       pyotp's change notes, and adjusting our code if necessary...).
import pyotp

from n6lib.common_helpers import (
    ascii_str,
    as_bytes,
    as_unicode,
)
from n6lib.typing_helpers import (
    StrOrBinary,
    String,
)


LEN_OF_SECRET_KEY = 32

TIME_STEP_WINDOW_IN_SECONDS = 30
ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS = 1

MFA_CODE_NUM_OF_DIGITS = 6
MFA_CODE_STR_PATTERN = '{:0%s}' % MFA_CODE_NUM_OF_DIGITS
MFA_CODE_MAX_ACCEPTABLE_AGE_IN_SECONDS = (TIME_STEP_WINDOW_IN_SECONDS *
                                          (ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS + 1))


def generate_new_mfa_key_base():
    # type: () -> (String)
    return as_unicode(base64.b64encode(os.urandom(64)))


def generate_secret_key(mfa_key_base, server_secret):
    # type: (StrOrBinary, StrOrBinary) -> String
    mfa_key_base = _conv_secret_val(mfa_key_base, as_bytes, 'the given MFA key base to `bytes`')
    server_secret = _conv_secret_val(server_secret, as_bytes, 'the given server secret to `bytes`')
    hmac_result = hmac.new(server_secret, mfa_key_base, hashlib.sha384).digest()
    return as_unicode(base64.b32encode(hmac_result)[:LEN_OF_SECRET_KEY])


def generate_secret_key_qr_code_url(secret_key, login, issuer_name):
    # type: (String, String, String) -> String
    login = as_unicode(login)
    issuer_name = as_unicode(issuer_name)
    if sys.version_info[0] < 3:                                                  #3--
        login = as_bytes(login)                                                  #3--
        issuer_name = as_bytes(issuer_name)                                      #3--
    return make_totp_handler(secret_key).provisioning_uri(
        name=login,
        issuer_name=issuer_name)


def does_mfa_code_matches_now(mfa_code, secret_key):
    # type: (Union[int, String], String) -> bool
    mfa_code = int(mfa_code)
    mfa_code_str = MFA_CODE_STR_PATTERN.format(mfa_code)
    return make_totp_handler(secret_key).verify(
        mfa_code_str,
        valid_window=ACCEPTABLE_DRIFT_IN_TIME_STEP_WINDOWS)


def make_totp_handler(secret_key):
    # type: (String) -> pyotp.TOTP
    secret_key = _conv_secret_val(secret_key, as_unicode, 'the given TOTP secret key to `str`')
    return pyotp.TOTP(
        secret_key,
        digits=MFA_CODE_NUM_OF_DIGITS,
        interval=TIME_STEP_WINDOW_IN_SECONDS)


def _conv_secret_val(val, conv_func, descr_what_to_what):
    # We don't want to reveal the value in any error messages/tracebacks etc.
    try:
        return conv_func(val)
    except Exception as exc:
        exc_type = type(exc)
        error_msg = 'could not convert {} ({})'.format(
            descr_what_to_what,
            ascii_str(exc_type.__name__))
    if issubclass(exc_type, ValueError):
        error_factory = ValueError
    elif issubclass(exc_type, TypeError):
        error_factory = TypeError
    else:
        error_factory = RuntimeError
    raise error_factory(error_msg)

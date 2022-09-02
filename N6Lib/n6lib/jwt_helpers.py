#  Copyright (c) 2021-2022 NASK. All rights reserved.

import re
from collections.abc import Iterable
from typing import (
    Any,
    Union,
)

# TODO: upgrade PyJWT to the newest stable version (checking all relevant
#       PyJWT's change notes, and adjusting our code if necessary...).
import jwt

from n6lib.class_helpers import attr_required
from n6lib.common_helpers import (
    ascii_str,
    as_unicode,
)
from n6lib.typing_helpers import (
    ExcFactory,
    StrOrBinary,
)


#
# Public constants

JWT_ALGO_HMAC_SHA256 = 'HS256'
JWT_ALGO_DEFAULT = JWT_ALGO_HMAC_SHA256

JWT_ROUGH_REGEX = re.compile(r'\A[a-zA-Z0-9\-_.]+\Z', re.ASCII)


#
# Public exceptions

class AbstractJWTError(Exception):

    _op_descr: str = None

    @attr_required('_op_descr')
    def __init__(self, msg_or_underlying_exc: Union[str, Exception, None] = None):
        if isinstance(msg_or_underlying_exc, Exception):
            # (only the exception type's name as we don't want to reveal too much...)
            msg_or_underlying_exc = type(msg_or_underlying_exc).__name__
        self._msg = ascii_str(msg_or_underlying_exc or '<unknown error>')
        super().__init__(self._msg)

    def __repr__(self) -> str:
        return f'{type(self).__qualname__}({self._msg!r})'

    def __str__(self) -> str:
        return f'could not properly {self._op_descr} a JSON Web Token - {self._msg}'

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)


class JWTDecodeError(AbstractJWTError):
    _op_descr = 'decode'


class JWTEncodeError(AbstractJWTError):
    _op_descr = 'encode'


#
# Public utility functions

def jwt_decode(token: StrOrBinary,
               secret_key: StrOrBinary,
               accepted_algorithms: Iterable[str] = (JWT_ALGO_DEFAULT,),
               required_claims: Union[Iterable[str], dict[str, type]] = (),
               ) -> dict[str, Any]:
    try:
        token = as_unicode(token)
        secret_key = as_unicode(secret_key)
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=sorted(accepted_algorithms))
    except Exception as exc:
        raise JWTDecodeError(exc) from None   # (Because we don't want to reveal too much...)
    assert JWT_ROUGH_REGEX.search(token)
    assert isinstance(payload, dict)
    _verify_required_claims(payload, required_claims, JWTDecodeError)
    return payload


def jwt_encode(payload: dict[str, Any],
               secret_key: StrOrBinary,
               algorithm: str = JWT_ALGO_DEFAULT,
               required_claims: Union[Iterable[str], dict[str, type]] = (),
               ) -> str:
    _verify_required_claims(payload, required_claims, JWTEncodeError)
    try:
        secret_key = as_unicode(secret_key)
        token = jwt.encode(
            payload,
            secret_key,
            algorithm=algorithm)
        token = as_unicode(token)  # <- TODO later: can be removed after upgrade of PyJWT...
    except Exception as exc:
        raise JWTEncodeError(exc) from None   # (Because we don't want to reveal too much...)
    assert JWT_ROUGH_REGEX.search(token)
    return token


#
# Internal (module-local-use-only) helpers

def _verify_required_claims(payload: dict[str, Any],
                            required_claims: Union[Iterable[str], dict[str, type]],
                            exc_factory: ExcFactory,
                            ) -> None:
    _verify_no_missing_claims(payload, required_claims, exc_factory)
    if isinstance(required_claims, dict):
        _verify_no_claims_of_wrong_types(payload, required_claims, exc_factory)


def _verify_no_missing_claims(payload: dict[str, Any],
                              required_claims: Union[Iterable[str], dict[str, type]],
                              exc_factory: ExcFactory,
                              ) -> None:
    missing_claims = frozenset(required_claims).difference(payload)
    if missing_claims:
        listing = ', '.join(map(ascii, sorted(missing_claims)))
        raise exc_factory('missing claims: ' + listing)


def _verify_no_claims_of_wrong_types(payload: dict[str, Any],
                                     required_claims: dict[str, type],
                                     exc_factory: ExcFactory,
                                     ) -> None:
    claims_of_wrong_types = [
        claim_key
        for claim_key, required_type in required_claims.items()
        if not isinstance(payload[claim_key], required_type)]
    if claims_of_wrong_types:
        listing = ascii_str(', '.join(
            f'{claim_key!a} '
            f'(required `{required_claims[claim_key].__qualname__}`, '
            f'got `{type(payload[claim_key]).__qualname__}`)'
            for claim_key in sorted(claims_of_wrong_types)))
        raise exc_factory('claims whose types are wrong: ' + listing)

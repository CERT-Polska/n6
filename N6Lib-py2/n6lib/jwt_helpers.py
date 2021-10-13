#  Copyright (c) 2021 NASK. All rights reserved.

import re
from typing import (
    Any,
    Dict,
    Iterable,
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
    String,                                                                      #3--
)


#
# Public constants

JWT_ALGO_HMAC_SHA256 = 'HS256'
JWT_ALGO_DEFAULT = JWT_ALGO_HMAC_SHA256

JWT_ROUGH_REGEX = re.compile(r'\A[a-zA-Z0-9\-_.]+\Z', re.ASCII)


#
# Public exceptions

class AbstractJWTError(Exception):

    _op_descr = None

    @attr_required('_op_descr')
    def __init__(self,
                 msg_or_underlying_exc=None,  # type: Union[str, Exception, None]
                 ):
        if isinstance(msg_or_underlying_exc, Exception):
            # (only the exception type's name as we don't want to reveal too much...)
            msg_or_underlying_exc = type(msg_or_underlying_exc).__name__
        self._msg = ascii_str(msg_or_underlying_exc or '<unknown error>')
        super(AbstractJWTError, self).__init__(self._msg)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self._msg)

    def __str__(self):
        return 'could not properly {} a JSON Web Token - {}'.format(self._op_descr, self._msg)

    def __unicode__(self):                                                       #3--
        return str(self).decode('utf-8')                                         #3--

    def __format__(self, format_spec):
        return format(str(self), format_spec)


class JWTDecodeError(AbstractJWTError):
    _op_descr = 'decode'


class JWTEncodeError(AbstractJWTError):
    _op_descr = 'encode'


#
# Public utility functions

def jwt_decode(token,                                     # type: StrOrBinary
               secret_key,                                # type: StrOrBinary
               accepted_algorithms=(JWT_ALGO_DEFAULT,),   # type: Iterable[str]
               required_claims=(),                        # type: Iterable[str]
               ):
    # type: (...) -> Dict[String, Any]
    try:
        token = as_unicode(token)
        secret_key = as_unicode(secret_key)
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=sorted(accepted_algorithms))
    except Exception as exc:
        raise JWTDecodeError(exc)                                                #3: add: ```from None  # as we don't want to reveal too much...```
    assert JWT_ROUGH_REGEX.search(token)
    assert isinstance(payload, dict)
    _verify_required_claims(payload, required_claims, JWTDecodeError)
    return payload


def jwt_encode(payload,                      # type: Dict[String, Any]
               secret_key,                   # type: StrOrBinary
               algorithm=JWT_ALGO_DEFAULT,   # type: str
               required_claims=(),           # type: Iterable[str]
               ):
    # type: (...) -> String                                                      #3: ```String``` -> ```str```
    _verify_required_claims(payload, required_claims, JWTEncodeError)
    try:
        secret_key = as_unicode(secret_key)
        token = jwt.encode(
            payload,
            secret_key,
            algorithm=algorithm)
        token = as_unicode(token)  # <- TODO later: can be removed after upgrade of PyJWT...
    except Exception as exc:
        raise JWTEncodeError(exc)                                                #3: add: ```from None  # as we don't want to reveal too much...```
    assert JWT_ROUGH_REGEX.search(token)
    return token


#
# Internal (module-local-use-only) helpers

def _verify_required_claims(payload, required_claims, exc_factory):
    # type: (Dict[String, Any], Iterable[str], ExcFactory) -> None
    missing_claims = frozenset(required_claims).difference(payload)
    if missing_claims:
        missing_claims_repr = ', '.join(sorted(map(repr, missing_claims)))
        raise exc_factory('missing claims: ' + missing_claims_repr)

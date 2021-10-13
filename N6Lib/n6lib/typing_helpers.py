# Copyright (c) 2020-2021 NASK. All rights reserved.

import datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)

from sqlalchemy.sql.expression import ColumnElement


T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)

DateTime = datetime.datetime
String = str  # <- TODO: replace with `str` everywhere...
StrOrBinary = Union[str, bytes, bytearray]
KwargsDict = Dict[String, Any]

Jsonable = Union['JsonableScalar', 'JsonableCollection']
JsonableScalar = Union[String, int, float, bool, None]
JsonableDict = Dict[String, Jsonable]
JsonableSeq = Union[List[Jsonable], Tuple[Jsonable, ...]]
JsonableCollection = Union[JsonableDict, JsonableSeq]

TypeSpec = Union[type, Tuple['TypeSpec', ...]]  # type of `isinstance()/issubclass()`'s second arg

ExcFactory = Callable[..., BaseException]
ColumnElementTransformer = Callable[[ColumnElement], ColumnElement]

EventDataResourceId = Literal['/report/inside', '/report/threats', '/search/events']
AccessZone = Literal['inside', 'threats', 'search']
AccessZoneConditions = Dict[AccessZone, List[ColumnElement]]

AuthData = TypedDict('AuthData', {
    'org_id': String,               # `Org.org_id`
    'user_id': String,              # `User.login` (here named `user_id` for historical reasons)
})

AccessInfo = TypedDict('AccessInfo', {
    'access_zone_conditions': AccessZoneConditions,
    'rest_api_resource_limits': Dict[EventDataResourceId, dict],
    'rest_api_full_access': bool,   # `Org.full_access`
})

WebTokenData = TypedDict('WebTokenData', {
    'token_id': String,             # `WebToken.token_id` (or random UUID4 for pseudo-tokens)
    'created_on': DateTime,         # `WebToken.created_on` (or just date+time for pseudo-tokens)
})

MFAConfigData = TypedDict('MFAConfigData', {
    'login': String,                # `User.login`
    'mfa_key_base': String,         # `User.mfa_key_base`|`UserProvisionalMFAConfig.mfa_key_base`
})

MFASecretConfig = TypedDict('MFASecretConfig', {
    'secret_key': String,               # BASE-32-compliant, exactly-32-character-long
    'secret_key_qr_code_url': String,   # An 'otpauth://...' URL
})

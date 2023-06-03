# Copyright (c) 2020-2023 NASK. All rights reserved.

import datetime
import os
from collections.abc import (
    Callable,
    Hashable,
)
from typing import (
    Any,
    Literal,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
)

from sqlalchemy.sql.expression import ColumnElement


T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)

HashableT = TypeVar('HashableT', bound=Hashable)

DateTime = datetime.datetime
String = str  # <- TODO: replace with `str` everywhere...
StrOrBinary = Union[str, bytes, bytearray]
KwargsDict = dict[str, Any]

FilePath = Union[str, bytes, os.PathLike]

class SupportsRead(Protocol[T_co]):
    def read(self, length: int = ..., /) -> T_co: ...

class SupportsWrite(Protocol[T_contra]):
    def write(self, data: T_contra, /) -> Any: ...

Jsonable = Union['JsonableScalar', 'JsonableCollection']
JsonableScalar = Union[str, int, float, bool, None]
JsonableDict = dict[str, Jsonable]
JsonableSeq = Union[list[Jsonable], tuple[Jsonable, ...]]
JsonableCollection = Union[JsonableDict, JsonableSeq]

TypeSpec = Union[type, tuple['TypeSpec', ...]]  # type of `isinstance()/issubclass()`'s second arg

ExcFactory = Callable[..., Exception]
BaseExcFactory = Callable[..., BaseException]

ColumnElementTransformer = Callable[[ColumnElement], ColumnElement]

EventDataResourceId = Literal['/report/inside', '/report/threats', '/search/events']
AccessZone = Literal['inside', 'threats', 'search']
AccessZoneConditionsDict = dict[AccessZone, list[ColumnElement]]


class AuthData(TypedDict):
    org_id: str                   # `Org.org_id`
    user_id: str                  # `User.login` (here named `user_id` for historical reasons)

class AccessInfo(TypedDict):      # (see: `n6lib.auth_api.AuthAPI.get_access_info()`)
    access_zone_conditions: AccessZoneConditionsDict
    rest_api_resource_limits: dict[EventDataResourceId, dict]
    rest_api_full_access: bool    # `Org.full_access`

class WebTokenData(TypedDict):
    token_id: str                 # `WebToken.token_id` (or random UUID4 for pseudo-tokens)
    created_on: DateTime          # `WebToken.created_on` (or just date+time for pseudo-tokens)

class MFAConfigData(TypedDict):
    login: str                    # `User.login`
    mfa_key_base: str             # `User.mfa_key_base`|`UserProvisionalMFAConfig.mfa_key_base`

class MFASecretConfig(TypedDict):
    secret_key: str               # BASE-32-compliant, exactly-32-character-long
    secret_key_qr_code_url: str   # An 'otpauth://...' URL

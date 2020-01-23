# Copyright (c) 2020 NASK. All rights reserved.

from typing import (
    Dict,
    List,
    Tuple,
    Union,
)

Jsonable = Union['JsonableScalar', 'JsonableCollection']
JsonableScalar = Union[basestring, int, long, float, bool, None]
JsonableDict = Dict[basestring, Jsonable]
JsonableSeq = Union[List[Jsonable], Tuple[Jsonable, ...]]
JsonableCollection = Union[JsonableDict, JsonableSeq]

String = Union[str, unicode]

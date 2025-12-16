# Copyright (c) 2025 NASK. All rights reserved.

"""
A simple, general-purpose, *n6*-system-wide cache (Auth-DB-based).

To make use of it, implement your concrete subclass of the class
`AuxiliaryCacheEntryRetriever`. To learn from an existing example,
see the code in `n6lib.moje_cve_advisories_retriever`.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime
from typing import (
    TYPE_CHECKING,
    Generic,
    TypeVar,
)

from n6lib.datetime_helpers import datetime_utc_normalize

if TYPE_CHECKING:
    from n6lib.auth_db.api import AuthManageAPI


ContentT = TypeVar('ContentT')


class AuxiliaryCacheEntryRetriever(Generic[ContentT], abc.ABC):

    @property
    @abc.abstractmethod
    def cache_key(self) -> str:
        """The key identifying the concerned cache entry."""
        raise NotImplementedError

    def __init__(self, *, cache_validity_period_seconds: int, **kwargs):
        super().__init__(**kwargs)
        self._cache_validity_period = datetime.timedelta(seconds=cache_validity_period_seconds)

    def retrieve(self, auth_manage_api: AuthManageAPI) -> ContentT:
        now = datetime.datetime.utcnow()
        handle: AuxiliaryCacheEntryHandle
        with auth_manage_api.working_on_auxiliary_cache_entry(self.cache_key) as handle:

            if handle.updated_at is None:
                # No cache entry found, we need to create it.
                assert handle.raw_content is None
                initial_content = self.get_initial()
                handle.prescribe_new_raw_content(self.serialize(initial_content))
                return initial_content

            assert handle.raw_content is not None

            if now > handle.updated_at + self._cache_validity_period:
                # Cache entry has expired.
                content = self.deserialize(handle.raw_content)
                content_after_update = self.get_updated(content)
                handle.prescribe_new_raw_content(self.serialize(content_after_update))
                return content_after_update

            # Cache entry is still valid.
            cached_content = self.deserialize(handle.raw_content)
            return cached_content

    @abc.abstractmethod
    def get_initial(self) -> ContentT:
        """
        Return the initial content (when no content has been cached yet).
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_updated(self, content: ContentT, /) -> ContentT | None:
        """
        Return the result of updating the given content with some new
        stuff, or return the content intact, as appropriate.

        Never mutate the given content in place! Create a new object if
        any changes are needed.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def deserialize(self, raw_content: bytes, /) -> ContentT:
        """
        Transform the given bytes into content.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def serialize(self, content: ContentT, /) -> bytes:
        """
        Transform the given content into bytes.

        Never mutate the given content in place!
        """
        raise NotImplementedError


@dataclasses.dataclass(frozen=True)
class AuxiliaryCacheEntryHandle:
    raw_content: bytes | None = None
    updated_at: datetime.datetime | None = None

    def __post_init__(self):
        if self.updated_at is not None:
            object.__setattr__(self, 'updated_at', datetime_utc_normalize(self.updated_at))
        object.__setattr__(self, '_newly_prescribed_raw_content', None)

    def prescribe_new_raw_content(self, new_raw_content: bytes) -> None:
        object.__setattr__(self, '_newly_prescribed_raw_content', new_raw_content)

    def get_newly_prescribed_raw_content_or_none(self) -> bytes | None:
        return self._newly_prescribed_raw_content  # noqa

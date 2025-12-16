# Copyright (c) 2025 NASK. All rights reserved.

from __future__ import annotations

from collections import defaultdict
from collections.abc import Set

from n6lib.auth_db.auxiliary_cache import AuxiliaryCacheEntryRetriever
from n6lib.moje_api_client import (
    MojeApiClient,
    MojeCveAdvisoriesFullInfo,
    MojeCveAdvisoriesUpdateInfo,
)


__all__ = [
    'MojeCveAdvisoriesFullInfo',
    'MojeCveAdvisoriesInfoRetriever',
]


class MojeCveAdvisoriesInfoRetriever(AuxiliaryCacheEntryRetriever[MojeCveAdvisoriesFullInfo]):

    cache_key = 'n6portal:moje_cve_advisories_info'

    def __init__(
        self,
        *,
        moje_api_key: str,
        moje_api_url: str,
        moje_api_timeout: int | float,
        moje_api_retries: int,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._moje_api_client = MojeApiClient(
            api_key=moje_api_key,
            api_url=moje_api_url,
            api_timeout=moje_api_timeout,
            api_retries=moje_api_retries,
        )

    def get_initial(self) -> MojeCveAdvisoriesFullInfo:
        return self._moje_api_client.obtain_cve_advisories_full_info()

    def get_updated(self, previous: MojeCveAdvisoriesFullInfo) -> MojeCveAdvisoriesFullInfo | None:
        update: MojeCveAdvisoriesUpdateInfo | None
        update = self._moje_api_client.obtain_cve_advisories_update_info_or_none(
            cve_updated_after=previous.moje_cve_updated_at,
        )
        if update is None:
            return previous
        return MojeCveAdvisoriesFullInfo.make(
            cve_id_to_urls_collection=self._get_updated_cve_id_to_urls_set(previous, update),
            moje_cve_updated_at=update.moje_cve_updated_at,
        )

    def _get_updated_cve_id_to_urls_set(
        self,
        previous: MojeCveAdvisoriesFullInfo,
        update: MojeCveAdvisoriesUpdateInfo,
    ) -> defaultdict[str, Set[str]]:
        cve_id_to_urls_set = defaultdict(set)
        for cve_id, urls in previous.cve_id_to_urls.items():
            for url in urls:
                updated_advisory_cve_ids = update.updated_adv_url_to_all_its_cve_ids_set.get(url)
                this_advisory_was_not_updated = (updated_advisory_cve_ids is None)
                if this_advisory_was_not_updated or (cve_id in updated_advisory_cve_ids):
                    cve_id_to_urls_set[cve_id].add(url)
        for encountered_cve_id, urls_set in update.encountered_cve_id_to_all_its_urls_set.items():
            cve_id_to_urls_set[encountered_cve_id].update(urls_set)
        return cve_id_to_urls_set

    def deserialize(self, raw_data: bytes) -> MojeCveAdvisoriesFullInfo:
        return MojeCveAdvisoriesFullInfo.from_json(raw_data)

    def serialize(self, info: MojeCveAdvisoriesFullInfo) -> bytes:
        return info.as_json_bytes()

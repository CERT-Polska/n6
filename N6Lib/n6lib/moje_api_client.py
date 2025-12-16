# Copyright (c) 2025 NASK. All rights reserved.

from __future__ import annotations

import dataclasses
import datetime
import json
import urllib.parse
from collections import defaultdict
from collections.abc import (
    Callable,
    Iterable,
    Mapping,
    Sequence,
    Set,
)
from typing import Any

from typing_extensions import Self

from n6lib.datetime_helpers import (
    datetime_utc_normalize,
    parse_iso_datetime_to_utc,
)
from n6lib.http_helpers import MultiRequestPerformer
from n6lib.typing_helpers import JsonableDict


# TODO: doc, tests...


class MojeApiClient:

    _API_FETCH_MAX_PAGES = 2000
    _MOJE_SITE_URL_PREFIX = 'https://moje.cert.pl/'

    def __init__(self,
                 api_key: str,
                 api_url: str,
                 api_timeout: int | float,
                 api_retries: int):
        self._api_url_prefix = api_url + '/'
        self._advisories_url = self._api_url_prefix + 'v1/advisories'
        self._advisories_updated_after_url_pattern = self._advisories_url + '?cve_updated_after={}'
        self._advisories_for_single_cve_url_pattern = self._advisories_url + '?cve={}'
        self._perf = MultiRequestPerformer(
            method='GET',
            headers={'Authorization': f'Token {api_key}'},
            allow_redirects=True,
            timeout=api_timeout,
            retries=api_retries,
        )

    def obtain_cve_advisories_full_info(self) -> MojeCveAdvisoriesFullInfo:
        with self._perf:
            results = self._fetch_and_validate(
                url=self._advisories_url,
                result_key_to_validator={
                    'cve': self._validate_cve_id_seq,
                    'cve_updated_at': parse_iso_datetime_to_utc,
                    'url': self._validate_advisory_url,
                },
            )
        if not results:
            raise ValueError(f'something wrong: no results')

        cve_id_to_urls_set: defaultdict[str, set[str]] = defaultdict(set)
        for res in results:
            for cve_id in res['cve']:
                cve_id_to_urls_set[cve_id].add(res['url'])

        return MojeCveAdvisoriesFullInfo.make(
            cve_id_to_urls_set,
            moje_cve_updated_at=max(res['cve_updated_at'] for res in results),
        )

    def obtain_cve_advisories_update_info_or_none(
        self,
        cve_updated_after: datetime.datetime,
    ) -> MojeCveAdvisoriesUpdateInfo | None:
        with self._perf:
            update_summary = self._fetch_cve_advisories_update_summary_or_none(cve_updated_after)
            if update_summary is None:
                return None
            (updated_adv_url_to_all_its_cve_ids_set,
             encountered_cve_ids,
             moje_cve_updated_at) = update_summary

            encountered_cve_id_to_all_its_urls_set: dict[str, Set[str]] = {}
            for cve_id in sorted(encountered_cve_ids):
                all_urls_for_cve = self._fetch_all_advisory_urls_for_cve(cve_id)
                encountered_cve_id_to_all_its_urls_set[cve_id] = all_urls_for_cve

        return MojeCveAdvisoriesUpdateInfo.make(
            updated_adv_url_to_all_its_cve_ids_set,
            encountered_cve_id_to_all_its_urls_set,
            moje_cve_updated_at,
        )

    def _fetch_cve_advisories_update_summary_or_none(
        self,
        cve_updated_after: datetime.datetime,
    ) -> tuple[
        dict[str, Set[str]],
        Set[str],
        datetime.datetime,
    ] | None:
        cve_updated_after_param = urllib.parse.quote(
            datetime_utc_normalize(cve_updated_after)
            .replace(tzinfo=datetime.timezone.utc)
            .isoformat()
        )
        results = self._fetch_and_validate(
            url=self._advisories_updated_after_url_pattern.format(cve_updated_after_param),
            result_key_to_validator={
                'cve': self._validate_cve_id_seq,
                'cve_updated_at': parse_iso_datetime_to_utc,
                'url': self._validate_advisory_url,
            },
        )
        if not results:
            return None

        updated_adv_url_to_all_its_cve_ids_set = {
            res['url']: frozenset(res['cve'])
            for res in results
        }
        encountered_cve_ids = {
            cve_id
            for res in results
            for cve_id in res['cve']
        }
        moje_cve_updated_at = max(res['cve_updated_at'] for res in results)
        return (
            updated_adv_url_to_all_its_cve_ids_set,
            encountered_cve_ids,
            moje_cve_updated_at,
        )

    def _fetch_all_advisory_urls_for_cve(self, cve_id: str) -> Set[str]:
        cve_id_param = urllib.parse.quote(cve_id.upper())
        results = self._fetch_and_validate(
            url=self._advisories_for_single_cve_url_pattern.format(cve_id_param),
            result_key_to_validator={
                'url': self._validate_advisory_url,
            },
        )
        return {res['url'] for res in results}

    def _fetch_and_validate(
        self, url: str,
        result_key_to_validator: dict[str, Callable[[Any], str]],
    ) -> list[JsonableDict]:
        results: list[JsonableDict] = []
        prev_count = None
        next_page_url = url
        for _ in range(self._API_FETCH_MAX_PAGES):
            raw_data = self._request_raw_data(next_page_url)
            page_items, next_page_url, count = self._parse_raw_data(raw_data)

            if prev_count is not None and count != prev_count:
                # Value of `count` changed, meaning that the Moje's database
                # was updated in the meantime. To avoid inconsistency in the
                # results, let's fetch all data from the beginning!
                results.clear()
                prev_count = None
                next_page_url = url
                continue
            prev_count = count

            for item in page_items:
                results.append(
                    {
                        key: validator(item[key])
                        for key, validator in result_key_to_validator.items()
                    },
                )
            if next_page_url is None:
                break
        else:
            raise RuntimeError(f'something wrong, exceeded {self._API_FETCH_MAX_PAGES=!a}')
        return results

    def _request_raw_data(self, url: str) -> bytes:
        if not isinstance(url, str):
            raise TypeError(f'{url=!a} is not a str')
        if not url.startswith(self._api_url_prefix):
            raise ValueError(f'{url=!a} does not start with {self._api_url_prefix!a}')
        return self._perf.fetch(url=url)

    def _parse_raw_data(self, raw_data: bytes) -> tuple[list[JsonableDict], str | None, int]:
        parsed_data = json.loads(raw_data)
        if not isinstance(parsed_data, dict):
            raise TypeError(f'{parsed_data=!a} is not a dict')
        page_items = parsed_data.get('results')
        if not (isinstance(page_items, list)
                and all(isinstance(item, dict) for item in page_items)):
            raise TypeError(f'{page_items=!a} is not a list of dicts')
        next_page_url = parsed_data.get('next')
        if next_page_url is not None and not isinstance(next_page_url, str):
            raise TypeError(f'{next_page_url=!a} is neither a str nor None')
        count = parsed_data.get('count')  # (this is supposed to be total count of items)
        if not isinstance(count, int):
            raise TypeError(f'{count=!a} is not an int')
        return page_items, next_page_url, count

    @classmethod
    def _validate_cve_id_seq(cls, cve_ids: Sequence[str]) -> list[str]:
        return list(map(cls._validate_cve_id, cve_ids))

    @classmethod
    def _validate_cve_id(cls, cve_id: str) -> str:
        if not isinstance(cve_id, str):
            raise TypeError(f'{cve_id=!a} is not a str')
        cve_id = cve_id.lower()
        prefix, year, num = cve_id.split('-')
        if (prefix != 'cve'
              or not cve_id.isascii()
              or not year.isdecimal()
              or not num.isdecimal()
              or len(year) != 4
              or len(num) < 4):
            raise ValueError(f'{cve_id!a} is not a valid CVE identifier')
        return cve_id

    @classmethod
    def _validate_advisory_url(cls, url: str) -> str:
        if not isinstance(url, str):
            raise TypeError(f'{url=!a} is not a str')
        if not url.startswith(cls._MOJE_SITE_URL_PREFIX):
            raise ValueError(f'{url=!a} does not start with {cls._MOJE_SITE_URL_PREFIX!a}')
        return url


@dataclasses.dataclass(frozen=True)
class MojeCveAdvisoriesFullInfo:
    cve_id_to_urls: dict[str, list[str]]
    moje_cve_updated_at: datetime.datetime

    @classmethod
    def make(
        cls,
        cve_id_to_urls_collection: Mapping[str, Iterable[str]],
        moje_cve_updated_at: datetime.datetime | str,
    ) -> Self:
        return cls(
            cve_id_to_urls={
                cve_id: sorted(urls_set)
                for cve_id, urls_collection in cve_id_to_urls_collection.items()
                if (urls_set := frozenset(urls_collection))
            },
            moje_cve_updated_at=(
                parse_iso_datetime_to_utc(moje_cve_updated_at)
                if isinstance(moje_cve_updated_at, str)
                else datetime_utc_normalize(moje_cve_updated_at)
            ),
        )

    @classmethod
    def from_json(cls, json_data: str | bytes | bytearray) -> Self:
        data = json.loads(json_data)
        data['cve_id_to_urls_collection'] = data.pop('cve_id_to_urls')
        return cls.make(**data)

    def as_json_bytes(self) -> bytes:
        data = dataclasses.asdict(self)
        data['moje_cve_updated_at'] = data['moje_cve_updated_at'].isoformat()
        return json.dumps(data).encode('ascii')


@dataclasses.dataclass(frozen=True)
class MojeCveAdvisoriesUpdateInfo:
    updated_adv_url_to_all_its_cve_ids_set: dict[str, Set[str]]  # (<- this may contain empty sets)
    encountered_cve_id_to_all_its_urls_set: dict[str, Set[str]]
    moje_cve_updated_at: datetime.datetime

    @classmethod
    def make(
        cls,
        updated_adv_url_to_all_its_cve_ids_collection: Mapping[str, Iterable[str]],
        encountered_cve_id_to_all_its_urls_collection: Mapping[str, Iterable[str]],
        moje_cve_updated_at: datetime.datetime | str,
    ) -> Self:
        return cls(
            updated_adv_url_to_all_its_cve_ids_set={
                url: frozenset(cve_ids_collection)   # (<- these sets may be empty)
                for url, cve_ids_collection
                in updated_adv_url_to_all_its_cve_ids_collection.items()
            },
            encountered_cve_id_to_all_its_urls_set={
                cve_id: urls_set
                for cve_id, urls_collection
                in encountered_cve_id_to_all_its_urls_collection.items()
                if (urls_set := frozenset(urls_collection))
            },
            moje_cve_updated_at=(
                parse_iso_datetime_to_utc(moje_cve_updated_at)
                if isinstance(moje_cve_updated_at, str)
                else datetime_utc_normalize(moje_cve_updated_at)
            ),
        )

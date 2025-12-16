#  Copyright (c) 2021-2025 NASK. All rights reserved.

from __future__ import annotations

import ast
import datetime
import json
import logging
import urllib.parse
from collections.abc import Generator
from copy import deepcopy
from textwrap import dedent
from types import SimpleNamespace
from typing import (
    Any,
    TypedDict,
)
from unittest.mock import (
    MagicMock,
    call,
    patch,
)

import pytest
import pytest_httpserver

from n6lib.auth_api import EVENT_DATA_RESOURCE_IDS
from n6lib.auth_db import models
from n6lib.auth_db.api import AuthManageAPI
from n6lib.config import ConfigError
from n6lib.file_helpers import FilesystemPathMapping
from n6lib.moje_api_client import MojeCveAdvisoriesFullInfo
from n6lib.pyramid_commons import N6LimitedStreamView
from n6lib.pyramid_commons.knowledge_base_helpers import KnowledgeBaseDataError
from n6lib.unit_test_helpers import (
    DBConnectionPatchMixin,
    dt_seconds_ago,
)
from n6portal import (
    N6PortalStreamView,
    RESOURCES,
)
from n6sdk.datetime_helpers import parse_iso_datetime_to_utc


def test_data_resource_ids():
    assert {res.resource_id for res in RESOURCES
            if res.view_base is N6PortalStreamView} == EVENT_DATA_RESOURCE_IDS


class TestEnrichingEventsWithNameDetailsByN6PortalStreamView:

    #
    # Constants/fixtures related to *n6 Knowledge Base*

    KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA = {
        'en': {
            '_title.txt': 'Our Example Knowledge Base',

            '10-bots': {
                '_title.txt': 'About Bots',

                '1010-basics.md': dedent('''\
                    # Basics
                    ...
                    ## loremipsum
                    ### Ugly Stuff
                    ### ?What ; the , heck!
                    #### Extra Notes
                    ...
                    #### Ha Ha Ha
                    ...
                    ### virut
                '''),

                '1020-extra-info.md': dedent('''\
                    # Some extra information
                    ...
                    ### feodo
                    ...
                    ## asdf
                    ...
                    ### ?what ; the , heck!
                    ...
                    #### Ugly Stuff
                    ...
                    ### -asdf-
                    ...
                    ### citadel
                    ...
                    ##### loremipsum
                '''),
            },

            '20-vulnerabilities-in-services': {
                '_title.txt': 'Something About Vulnerable Services',

                '2010-some.md': dedent('''\
                    # Some Vulnerabilities...
                    ...
                    ## asdf
                    ...
                    ## blah blah
                    ...
                    ### Ugly Stuff
                    ...
                    #### Ha Ha Ha
                    ...
                    ### loremipsum
                    ...
                    ### ftp allow password wo ssl
                    ...
                '''),

                '2020-nothing-interesting.md': '# Boring Stuff, You Know...',
            },
        },

        'pl': {
            '_title.txt': 'Nasza przykładowa Baza Wiedzy',

            '10-o-botach': {
                '_title.txt': 'O botach',

                '1010-podstawy.md': dedent('''\
                    # Podstawy
                    ...
                    ## loremipsum
                    ...
                    ### Ugly Stuff     \

                    ...
                    ###   ?WHAT ; THE , HECK!
                    ...
                    #### Dodatkowe uwagi
                    ...
                    #### Ha Ha Ha
                    ...
                    ###  \t   virut  \t
                '''),

                '1020-rozne-info.md': dedent('''\
                    # Różne dodatkowe informacje
                    ...
                    ### feodo
                    ...
                    ## asdf
                    ...
                    ## tralala
                    ...
                    ### ?What ; the , heck!
                    ...
                    ####   Ugly Stuff
                    ...
                    ### -asdf-
                    ...

                    ### citadel

                    Coś tam o cytadeli...
                    Coś tam o cytadeli...

                    ...
                    ##### loremipsum
                    ...
                '''),
            },

            '20-o-podanych-uslugach': {
                '_title.txt': 'Coś o podatnych usługach',

                '2010-jakies.md': dedent('''\
                    # Jakieś podatności...
                    ...
                    ## asdf
                    ...
                    ### UGLY stuff
                    ...
                    #### Hłe Hłe Hłe
                    ...
                    ### loremipsum
                    Cosik tam, cosik innego.
                    Tudzież ówdzie jakkolwiek również.
                    ...
                    ### ftp allow password wo ssl
                '''),

                '2020-nic-ciekawego.md': '# Dłużyzna, proszę pana...',
            },
        },
    }

    @pytest.fixture(
        scope='class',
        params=[KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA],
    )
    def knowledge_base_fs_tree(self, request) -> FilesystemPathMapping:
        return FilesystemPathMapping(
            populate_with=deepcopy(request.param),
        )

    #
    # Constants/fixtures related to fetching and caching data from *Moje* API

    MOJE_FAKE_API_KEY = 64 * 'c'
    MOJE_FAKE_API_CVE_ADVISORIES_DATA = dict(
        with_replaced_cve={
            'url': 'https://moje.cert.pl/komunikaty/2025/41/with-replaced-cve',
            'cve': [
                'CVE-2222-2222',
            ],
            'cve_updated_at': '2025-11-10T21:20:42.123457+01:00',
            '...other keys...': '...irrelevant...',
        },
        with_cve_completely_removed={
            'url': 'https://moje.cert.pl/komunikaty/2025/17/with-cve-completely-removed',
            'cve': [],
            'cve_updated_at': '2025-11-10T21:20:42.123457+01:00',
            '...other keys...': '...irrelevant...',
        },
        without_changes_1={
            'url': 'https://moje.cert.pl/komunikaty/2025/40/without-changes-1',
            'cve': [
                'CVE-1111-1111',
                'CVE-7777-7777777',
            ],
            'cve_updated_at': '2025-05-01T02:03:04.050607+02:00',
            '...other keys...': '...irrelevant...',
        },
        without_changes_2={
            'url': 'https://moje.cert.pl/komunikaty/2025/42/without-changes-2',
            'cve': [
                'CVE-1234-123456',
                'CVE-2222-2222',
            ],
            'cve_updated_at': '2025-06-12T13:14:15.000001Z',
            '...other keys...': '...irrelevant...',
        },
        with_removed_cve={
            'url': 'https://moje.cert.pl/komunikaty/2025/11/with-removed-cve',
            'cve': [],
            'cve_updated_at': '2025-11-14T17:18:19.999999+00:00',
            '...other keys...': '...irrelevant...',
        },
        with_known_cve_added={
            'url': 'https://moje.cert.pl/komunikaty/2025/44/with-known-cve-added',
            'cve': [
                'CVE-1234-123456',
                'CVE-2222-2222',
            ],
            'cve_updated_at': '2025-11-10T21:20:42.123457+01:00',
            '...other keys...': '...irrelevant...',
        },
        new_with_new_cve={
            'url': 'https://moje.cert.pl/komunikaty/2025/45/new-with-new-cve',
            'cve': [
                'CVE-5555-55555',
            ],
            'cve_updated_at': '2025-11-11T12:13:14.151617+01:00',
            '...other keys...': '...irrelevant...',
        },
        with_new_cve_added={
            'url': 'https://moje.cert.pl/komunikaty/2025/43/with-new-cve-added',
            'cve': [
                'CVE-1234-123456',
                'CVE-4444-4444',
            ],
            'cve_updated_at': '2025-11-13T01:02:03+01:00',
            '...other keys...': '...irrelevant...',
        },
        new_with_known_cve={
            'url': 'https://moje.cert.pl/komunikaty/2025/46/new-with-known-cve',
            'cve': [
                'CVE-2222-2222',
            ],
            'cve_updated_at': '2025-11-11T16:17:18.192021+01:00',
            '...other keys...': '...irrelevant...',
        },
    )

    INITIALLY_CACHED_MOJE_FULL_INFO = MojeCveAdvisoriesFullInfo.make(
        {
            'cve-1111-1111': [
                'https://moje.cert.pl/komunikaty/2025/40/without-changes-1',
            ],
            'cve-1234-123456': [
                'https://moje.cert.pl/komunikaty/2025/11/with-removed-cve',
                'https://moje.cert.pl/komunikaty/2025/41/with-replaced-cve',
                'https://moje.cert.pl/komunikaty/2025/42/without-changes-2',
                'https://moje.cert.pl/komunikaty/2025/43/with-new-cve-added',
            ],
            'cve-2222-2222': [
                'https://moje.cert.pl/komunikaty/2025/42/without-changes-2',
                'https://moje.cert.pl/komunikaty/2025/44/with-known-cve-added',
            ],
            'cve-3333-3333': [
                'https://moje.cert.pl/komunikaty/2025/17/with-cve-completely-removed',
            ],
            'cve-7777-7777777': [
                'https://moje.cert.pl/komunikaty/2025/40/without-changes-1',
            ],
        },
        moje_cve_updated_at=datetime.datetime(2025, 11, 10, 20, 20, 42, 123456),
    )
    EXPECTED_UPDATED_MOJE_FULL_INFO = MojeCveAdvisoriesFullInfo.make(
        {
            'cve-1111-1111': [
                'https://moje.cert.pl/komunikaty/2025/40/without-changes-1',
            ],
            'cve-1234-123456': [
                'https://moje.cert.pl/komunikaty/2025/42/without-changes-2',
                'https://moje.cert.pl/komunikaty/2025/43/with-new-cve-added',
                'https://moje.cert.pl/komunikaty/2025/44/with-known-cve-added',
            ],
            'cve-2222-2222': [
                'https://moje.cert.pl/komunikaty/2025/41/with-replaced-cve',
                'https://moje.cert.pl/komunikaty/2025/42/without-changes-2',
                'https://moje.cert.pl/komunikaty/2025/44/with-known-cve-added',
                'https://moje.cert.pl/komunikaty/2025/46/new-with-known-cve',
            ],
            'cve-4444-4444': [
                'https://moje.cert.pl/komunikaty/2025/43/with-new-cve-added',
            ],
            'cve-5555-55555': [
                'https://moje.cert.pl/komunikaty/2025/45/new-with-new-cve',
            ],
            'cve-7777-7777777': [
                'https://moje.cert.pl/komunikaty/2025/40/without-changes-1',
            ],
        },
        moje_cve_updated_at=max(
            parse_iso_datetime_to_utc(data['cve_updated_at'])
            for data in MOJE_FAKE_API_CVE_ADVISORIES_DATA.values()
        ),
    )

    @pytest.fixture(params=[
        dict(
            initial_cache_state=dict(
                moje_full_info=INITIALLY_CACHED_MOJE_FULL_INFO,
                cache_updated_at=dt_seconds_ago(
                    # Less than `name_details.moje_data_cache_validity_period_seconds` setting
                    # => cache is valid, so only its content is to be used (no use of *Moje* API).
                    2000,
                    without_microseconds=True,
                ),
            ),
            cache_update_need_expected=False,
        ),
        dict(
            initial_cache_state=dict(
                moje_full_info=INITIALLY_CACHED_MOJE_FULL_INFO,
                cache_updated_at=dt_seconds_ago(
                    # More than `name_details.moje_data_cache_validity_period_seconds` setting
                    # => cache expired, so update needs to be fetched from (our fake) *Moje* API.
                    5000,
                    without_microseconds=True,
                ),
            ),
            cache_update_need_expected=True,
        ),
        dict(
            # Nothing is cached initially
            # => full info needs to be fetched from (our fake) *Moje* API.
            initial_cache_state=None,
            cache_update_need_expected=True,
        ),
    ])
    def moje_data_cache_state_case(self, request) -> _MojeDataCacheStateCase:
        return deepcopy(request.param)

    @pytest.fixture
    def auth_db_faker(
        self,
        moje_data_cache_state_case: _MojeDataCacheStateCase,
    ) -> _AuthDBFaker:
        initial_cache_state: _MojeDataCacheState | None = (
            moje_data_cache_state_case['initial_cache_state']
        )
        return _AuthDBFaker(initial_cache_state)

    @pytest.fixture
    def fake_moje_api_url(
        self,
        moje_data_cache_state_case: _MojeDataCacheStateCase,
        httpserver: pytest_httpserver.HTTPServer,
    ) -> Generator[str]:
        httpserver.expect_request('/')
        api_url = httpserver.url_for('/').rstrip('/')
        httpserver.clear()

        const_kwargs = dict(
            method='GET',
            headers={'Authorization': f'Token {self.MOJE_FAKE_API_KEY}'},
        )

        if moje_data_cache_state_case['initial_cache_state'] is None:

            # * Providing full info data (+ also simulating a `count`
            #   value change caused by a *Moje*'s database update...):

            httpserver.expect_ordered_request(
                '/v1/advisories', query_string='', **const_kwargs,
            ).respond_with_json({
                'next': f'{api_url}/v1/advisories?page=2',
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_replaced_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_cve_completely_removed'],
                    # Here we place a weird item -- just to check that
                    # it will *not* be used at all, because of a `count`
                    # value change (see below...).
                    {
                        'url': 'https://moje.cert.pl/komunikaty/2025/123/this-will-not-be-used',
                        'cve': [
                            'CVE-4242-4242',
                            'CVE-2345-678910',
                        ],
                        'cve_updated_at': '2025-11-10T11:12:13.141516+01:00',
                        '...other keys...': '...irrelevant...',
                    },
                ],
                'count': 8,
                '...other keys...': '...irrelevant...',
            })
            httpserver.expect_ordered_request(
                '/v1/advisories', query_string='page=2', **const_kwargs,
            ).respond_with_json({
                'next': f'{api_url}/v1/advisories?page=3',
                'results': [
                    # Here we place a weird item -- just to check that
                    # it will *not* be used at all, because of a `count`
                    # value change (see below...).
                    {
                        'url': 'https://moje.cert.pl/komunikaty/2025/456/this-will-not-be-used',
                        'cve': [
                            'CVE-9999-999999999999999999',
                        ],
                        'cve_updated_at': '2025-11-21T22:23:24.252627+01:00',
                        '...other keys...': '...irrelevant...',
                    },
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['without_changes_1'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_removed_cve'],
                ],
                # *Note*: here we are changing the value of `count`
                # to simulate the (rare) case of a possible results
                # inconsistency caused by a *Moje*'s database update.
                'count': 9,
                '...other keys...': '...irrelevant...',
            })

            # *Note*: because of the changed `count`, *n6* is expected
            # to begin fetching the data from the beginning (now we'll
            # provide the correct test data...).

            httpserver.expect_ordered_request(
                '/v1/advisories', query_string='', **const_kwargs,
            ).respond_with_json({
                'next': f'{api_url}/v1/advisories?page=2',
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_replaced_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_cve_completely_removed'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['without_changes_1'],
                ],
                'count': 9,
                '...other keys...': '...irrelevant...',
            })
            httpserver.expect_ordered_request(
                '/v1/advisories', query_string='page=2', **const_kwargs,
            ).respond_with_json({
                'next': f'{api_url}/v1/advisories?page=3',
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['without_changes_2'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_removed_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_known_cve_added'],
                ],
                'count': 9,
                '...other keys...': '...irrelevant...',
            })
            httpserver.expect_ordered_request(
                '/v1/advisories', query_string='page=3', **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_new_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_new_cve_added'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_known_cve'],
                ],
                'count': 9,
                '...other keys...': '...irrelevant...',
            })

        elif moje_data_cache_state_case['cache_update_need_expected']:

            # * Providing update info data:

            cve_updated_after = (
                self.INITIALLY_CACHED_MOJE_FULL_INFO.moje_cve_updated_at.isoformat()
            )
            cve_updated_after_query = {'cve_updated_after': f'{cve_updated_after}+00:00'}
            cve_updated_after_query_param = urllib.parse.quote(
                cve_updated_after_query['cve_updated_after'],
            )
            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string=cve_updated_after_query, **const_kwargs,
            ).respond_with_json({
                'next': (
                    f'{api_url}/v1/advisories'
                    f'?cve_updated_after={cve_updated_after_query_param}'
                    f'&page=2'
                ),
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_replaced_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_cve_completely_removed'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_removed_cve'],
                ],
                'count': 7,
                '...other keys...': '...irrelevant...',
            })
            cve_updated_after_query_page_2 = cve_updated_after_query | {'page': '2'}
            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string=cve_updated_after_query_page_2, **const_kwargs,
            ).respond_with_json({
                'next': (
                    f'{api_url}/v1/advisories'
                    f'?cve_updated_after={cve_updated_after_query_param}'
                    f'&page=3'
                ),
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_known_cve_added'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_new_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_new_cve_added'],
                ],
                'count': 7,
                '...other keys...': '...irrelevant...',
            })
            cve_updated_after_query_page_3 = cve_updated_after_query | {'page': '3'}
            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string=cve_updated_after_query_page_3, **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_known_cve'],
                ],
                'count': 7,
                '...other keys...': '...irrelevant...',
            })

            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string='cve=CVE-1234-123456', **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['without_changes_2'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_known_cve_added'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_new_cve_added'],
                ],
                'count': 3,
                '...other keys...': '...irrelevant...',
            })

            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string='cve=CVE-2222-2222', **const_kwargs,
            ).respond_with_json({
                'next': f'{api_url}/v1/advisories?cve=CVE-2222-2222&page=2',
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_replaced_cve'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['without_changes_2'],
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_known_cve_added'],
                ],
                'count': 4,
                '...other keys...': '...irrelevant...',
            })
            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string='cve=CVE-2222-2222&page=2', **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_known_cve'],
                ],
                'count': 4,
                '...other keys...': '...irrelevant...',
            })

            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string='cve=CVE-4444-4444', **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['with_new_cve_added'],
                ],
                'count': 1,
                '...other keys...': '...irrelevant...',
            })

            httpserver.expect_oneshot_request(
                '/v1/advisories', query_string='cve=CVE-5555-55555', **const_kwargs,
            ).respond_with_json({
                'next': None,
                'results': [
                    self.MOJE_FAKE_API_CVE_ADVISORIES_DATA['new_with_new_cve'],
                ],
                'count': 1,
                '...other keys...': '...irrelevant...',
            })

        yield api_url

        httpserver.check()

    #
    # Other constants/fixtures

    PORTAL_BASE_URL = 'https://n6portal.example.com/here'

    @pytest.fixture(params=[
        {
            # * Minimal settings to enable all features
            #   (rest options to be taken from `config_spec`'s defaults):

            'knowledge_base.active': 'true',

            'name_details.active': 'true',
            'name_details.moje_api_key': MOJE_FAKE_API_KEY,
            'name_details.category_to_n6kb_article_ids': (
                # (see constant `KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA` defined earlier...)
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': [2010],"
                "}"
            ),

            'portal_frontend_properties.base_url': PORTAL_BASE_URL,
        },

        {
            # * All options specified explicitly (+ extra custom site
            #   declared in `name_details.cve_extra_url_formats`, apart
            #   from 'enisa'):

            'knowledge_base.active': 'true',

            'name_details.active': 'true',
            'name_details.cve_regex': r'(?ai)\bcve-\d{4}-\d{4,}\b',
            'name_details.moje_api_key': MOJE_FAKE_API_KEY,
            'name_details.moje_api_timeout': '3',
            'name_details.moje_api_retries': '2',
            'name_details.moje_data_cache_validity_period_seconds': '3600',
            'name_details.cve_extra_url_formats': (
                "{"
                "'enisa': 'https://euvd.enisa.europa.eu/vulnerability/{cve_id_lowercase}',"
                "'my_custom_site': 'https://my-custom-site.example.rg/cve-db/{cve_id_uppercase}',"
                "}"
            ),
            'name_details.category_to_n6kb_article_ids': (
                # (see constant `KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA` defined earlier...)
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': ['2010', '2020'],"   # (<- strings are also accepted)
                "}"
            ),
            'name_details.n6kb_phrase_regex': (
                r'(?m)^\x23{3}(?!\x23)(?P<phrase>.+)$'
            ),

            'portal_frontend_properties.base_url': PORTAL_BASE_URL,
        },

        {
            # * Option `name_details.moje_api_key` left as empty
            #   string => no URLs to *Moje* advisories:

            'knowledge_base.active': 'true',

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': (
                # (see constant `KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA` defined earlier...)
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': [2010],"
                "}"
            ),

            'portal_frontend_properties.base_url': PORTAL_BASE_URL,
        },

        {
            # * Option `name_details.category_to_n6kb_article_ids`
            #   left as empty dict => no URLs to *n6 Knowledge Base*:

            'knowledge_base.active': 'true',

            'name_details.active': 'true',
            'name_details.moje_api_key': MOJE_FAKE_API_KEY,

            'portal_frontend_properties.base_url': PORTAL_BASE_URL,
        },

        {
            # * Option `name_details.cve_extra_url_formats` explicitly
            #   changed to empty dict => no URLs to *ENISA* database
            #   (or any custom site):

            'knowledge_base.active': 'true',

            'name_details.active': 'true',
            'name_details.moje_api_key': MOJE_FAKE_API_KEY,
            'name_details.cve_extra_url_formats': '{}',
            'name_details.category_to_n6kb_article_ids': (
                # (see constant `KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA` defined earlier...)
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': [2010],"
                "}"
            ),

            'portal_frontend_properties.base_url': PORTAL_BASE_URL,
        },
    ])
    def settings(
        self,
        request,
        fake_moje_api_url: str,
        knowledge_base_fs_tree: FilesystemPathMapping,
    ) -> dict:
        return request.param | {
            'name_details.moje_api_url': fake_moje_api_url,
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),
        }

    SUITABLE_MOJE_URLS = '<to be substituted by `event_case()` fixture>'

    @pytest.fixture(params=[
        dict(
            given_event={
                'category': 'bots',
                'name': 'nothing interesting',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details=None,
        ),

        dict(
            given_event={
                'category': 'other',
                'name': 'cve-1234-123456',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'cve': {
                    'cve-1234-123456': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-1234-123456',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-1234-123456',
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'other',
                'name': '-cVE-1234-123456-',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'cve': {
                    'cve-1234-123456': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-1234-123456',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-1234-123456',
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'other',
                'name': 'ccVE-1234-123456c',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details=None,
        ),

        dict(
            given_event={
                'category': 'vulnerable',
                'name': (
                    'A few vulnerabilities detected: '
                    'CCVE-1234-123456, CVE-4444-444, VE-1234-123456, '   # <- not valid CVE ids
                    'Cve-2222-2222, CVE-3333-3333333333, cve-5555-55555, '   # <- valid CVE ids
                    'Cve-2222-2222, cvE-5555-55555, '   # <- repeated some of the valid CVE ids
                ),
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'cve': {
                    'cve-2222-2222': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-2222-2222',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-2222-2222',
                        ],
                    },
                    'cve-3333-3333333333': {
                        # (note: 'cve-3333-3333333333' is *not* in our *Moje*'s test data)
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-3333-3333333333',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-3333-3333333333',
                        ],
                    },
                    'cve-5555-55555': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-5555-55555',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-5555-55555',
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': 'virut,asdf,citadel',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    'citadel': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-citadel",
                        ],
                    },
                    'virut': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#n6kb-virut",
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': '?VIRUT,-ASDF-,CITADEL?',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    '-asdf-': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-_2dasdf_2d",
                        ],
                    },
                    'citadel': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-citadel",
                        ],
                    },
                    'virut': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#n6kb-virut",
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': '-Virut-Asdf-Citadel-',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    '-asdf-': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-_2dasdf_2d",
                        ],
                    },
                    'citadel': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-citadel",
                        ],
                    },
                    'virut': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#n6kb-virut",
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': '?WHAT ; THE , HECK!',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    '?what ; the , heck!': {
                        'n6kb': [
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': '???what ; the , heck!!! ---asdf---',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    '-asdf-': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-_2dasdf_2d",
                        ],
                    },
                    '?what ; the , heck!': {
                        'n6kb': [
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': (
                    'What ; the , heck! ?What ; the , heck and ?What; the, heck! -a s d f-'
                    'O?hWhat ; The , HeckDunno... ?WWHAT ; THE HECKK! vvirut virutt vvirutt'
                ),
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details=None,
        ),

        dict(
            given_event={
                'category': 'bots',
                'name': 'Oh, UGLY stuff: loremipsum + citadel + asdf... ?!?What ; The , Heck!?!',
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'phrase': {
                    'ugly stuff': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#n6kb-ugly-stuff",
                        ],
                    },
                    '?what ; the , heck!': {
                        'n6kb': [
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1010#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#"
                                f"n6kb-_3fwhat-_3b-the-_2c-heck_21"
                            ),
                        ],
                    },
                    'citadel': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/1020#n6kb-citadel",
                        ],
                    },
                },
            },
        ),

        dict(
            given_event={
                'category': 'vulnerable',
                'name': (
                    'ugly stuff: not only cve-2222-2222, but also: FTP allow password wo SSL '
                    '+ Cve-3333-3333, cvE-4444-4444 and 1 more vulnerability (CVE-1111-1111); '
                    'and loremipsum? ?What ; The , Heck! And perhaps nothing more? '
                    'But let us repeat that: ugly stuff and LOREMIPSUM!'   # <- repeated phrases
                ),
                '...other keys...': '...irrelevant...',
            },
            possible_expected_name_details={
                'cve': {
                    'cve-1111-1111': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-1111-1111',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-1111-1111',
                        ],
                    },
                    'cve-2222-2222': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-2222-2222',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-2222-2222',
                        ],
                    },
                    'cve-3333-3333': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-3333-3333',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-3333-3333',
                        ],
                    },
                    'cve-4444-4444': {
                        'moje': SUITABLE_MOJE_URLS,
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-4444-4444',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-4444-4444',
                        ],
                    },
                },
                'phrase': {
                    'ugly stuff': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/2010#n6kb-ugly-stuff",
                        ],
                    },
                    'ftp allow password wo ssl': {
                        'n6kb': [
                            (
                                f"{PORTAL_BASE_URL}/knowledge_base/articles/2010#"
                                f"n6kb-ftp-allow-password-wo-ssl"
                            ),
                        ],
                    },
                    'loremipsum': {
                        'n6kb': [
                            f"{PORTAL_BASE_URL}/knowledge_base/articles/2010#n6kb-loremipsum",
                        ],
                    },
                },
            },
        ),
    ])
    def event_case(
        self,
        request,
        settings: dict,
        moje_data_cache_state_case: _MojeDataCacheStateCase,
        httpserver: pytest_httpserver.HTTPServer,
    ) -> _EventCase:
        event_case_params: dict = deepcopy(request.param)
        given_event = event_case_params['given_event']

        moje_enabled = bool(settings.get('name_details.moje_api_key'))
        enisa_enabled = _opt_as_bool(settings.get('name_details.cve_extra_url_formats', '1'))
        custom_enabled = 'my_custom_site' in settings.get('name_details.cve_extra_url_formats', '')
        n6kb_enabled = _opt_as_bool(settings.get('name_details.category_to_n6kb_article_ids', '0'))

        expected_available_cve_id_to_moje_urls = (
            deepcopy(
                self.EXPECTED_UPDATED_MOJE_FULL_INFO.cve_id_to_urls
                if moje_data_cache_state_case['cache_update_need_expected']
                else self.INITIALLY_CACHED_MOJE_FULL_INFO.cve_id_to_urls
            )
            if moje_enabled
            else {}
        )
        expected_name_details = event_case_params['possible_expected_name_details'] or {}
        if cve_part := expected_name_details.get('cve'):
            for cve_id, site_label_to_urls in dict(cve_part).items():
                if moje_urls := expected_available_cve_id_to_moje_urls.get(cve_id):
                    assert (site_label_to_urls.get('moje')
                            == self.SUITABLE_MOJE_URLS), 'internal assumption'
                    site_label_to_urls['moje'] = moje_urls
                else:
                    site_label_to_urls.pop('moje', None)
                if not enisa_enabled:
                    site_label_to_urls.pop('enisa', None)
                if not custom_enabled:
                    site_label_to_urls.pop('my_custom_site', None)
                if not site_label_to_urls:
                    del cve_part[cve_id]
            if not cve_part:
                del expected_name_details['cve']
            reaching_for_moje_data = moje_enabled
        else:
            reaching_for_moje_data = False
        if not n6kb_enabled:
            expected_name_details.pop('phrase', None)
        expected_postprocessed_event = deepcopy(given_event)
        if expected_name_details:
            expected_postprocessed_event['name_details'] = expected_name_details

        if reaching_for_moje_data and moje_data_cache_state_case['cache_update_need_expected']:
            expected_final_moje_cve_updated_at = (
                self.EXPECTED_UPDATED_MOJE_FULL_INFO.moje_cve_updated_at
            )
        else:
            httpserver.clear()  # <- Let's always catch unexpected uses of *Moje* API.
            expected_final_moje_cve_updated_at = (
                self.INITIALLY_CACHED_MOJE_FULL_INFO.moje_cve_updated_at
                if reaching_for_moje_data
                else None
            )

        return _EventCase(
            given_event=given_event,
            expected_postprocessed_event=expected_postprocessed_event,
            expected_final_moje_cve_updated_at=expected_final_moje_cve_updated_at,
        )

    #
    # Actual tests

    def test_enriches_as_appropriate(
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
        moje_data_cache_state_case: _MojeDataCacheStateCase,
        auth_db_faker: _AuthDBFaker,
        settings: dict,
        event_case: _EventCase
    ):
        processed_event = deepcopy(event_case['given_event'])

        view_instance = _prepare_and_instantiate_view(settings, auth_db_faker)
        view_instance.postprocess_cleaned_result(processed_event)

        assert processed_event == event_case['expected_postprocessed_event']
        if event_case['expected_final_moje_cve_updated_at']:
            final_moje_cve_updated_at = _get_final_moje_cve_updated_at(auth_db_faker)
            assert final_moje_cve_updated_at == event_case['expected_final_moje_cve_updated_at']


    @pytest.mark.parametrize(
        'option_name_details_active_explicitly_set_to_false',
        [True, False]  # (to show that here it doesn't matter)
    )
    @pytest.mark.parametrize(
        'knowledge_base_active',
        [True, False]  # (to show that here it doesn't matter)
    )
    def test_does_not_enrich_if_option_name_details_active_is_false(
        self,
        option_name_details_active_explicitly_set_to_false: bool,
        knowledge_base_active: bool,
        knowledge_base_fs_tree: FilesystemPathMapping,
    ):
        settings = {
            'knowledge_base.active': 'true' if knowledge_base_active else 'false',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.moje_api_key': self.MOJE_FAKE_API_KEY,
            'name_details.moje_api_url': 'https://127.0.0.1/NOT-A-USABLE-URL',
            'name_details.category_to_n6kb_article_ids': (
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': [2010],"
                "}"
            ),

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }
        if option_name_details_active_explicitly_set_to_false:
            settings['name_details.active'] = 'false'
        given_event = {
            'category': 'vulnerable',
            'name': (
                'ugly stuff: not only cve-2222-2222, but also: FTP allow password wo SSL '
                '+ Cve-3333-3333, cvE-4444-4444 and 1 more vulnerability (CVE-1111-1111); '
                'and loremipsum? ?What ; The , Heck! And perhaps nothing more? '
                'But let us repeat that: ugly stuff and LOREMIPSUM!'
            ),
            '...other keys...': '...irrelevant...',
        }
        processed_event = deepcopy(given_event)

        view_instance = _prepare_and_instantiate_view(settings)
        view_instance.postprocess_cleaned_result(processed_event)

        assert processed_event == given_event


    def test_raises_config_error_at_start_if_name_details_n6kb_stuff_is_configured_but_n6kb_itself_is_inactive(
        self,
    ):
        settings = {
            'knowledge_base.active': 'false',  # (<- this is the culprit)

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': "{'bots': [123]}",

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }

        with pytest.raises(ConfigError) as err_info:
            _prepare_and_instantiate_view(settings)
        assert err_info.match(
            r'given that option `name_details.active` is true and option '
            r'`name_details.category_to_n6kb_article_ids` is not empty, '
            r'option `knowledge_base.active` should be true \(but is false\)',
        )


    def test_raises_config_error_at_start_if_specified_n6kb_article_does_not_exist(
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
    ):
        settings = {
            'knowledge_base.active': 'true',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': "{'bots': [123]}",  # No article #123.

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }

        with pytest.raises(ConfigError) as err_info:
            _prepare_and_instantiate_view(settings)
        assert err_info.match(
            r"option `name_details.category_to_n6kb_article_ids` "
            r"contains Knowledge Base article identifier '123' "
            r"which refers to non-existent article",
        )


    @pytest.mark.parametrize(
        'knowledge_base_fs_tree',
        [
            {
                'en': {
                    '_title.txt': '...',
                    '1-ch': {
                        '_title.txt': '...',
                        '123-abcd.md': '#...\n### one\n### two',  # ("two" not in `pl` below)
                    },
                },
                'pl': {
                    '_title.txt': '...',
                    '1-rozdz': {
                        '_title.txt': '...',
                        '123-edfg.md': '#...\n### ONE\n### THREE',  # ("three" not in `en` above)
                    },
                },
            },

            {
                'en': {
                    '_title.txt': '...',
                    '1-ch': {
                        '_title.txt': '...',
                        '123-abcd.md': '#...\n### two\n### THREE'
                    },
                },
                'pl': {
                    '_title.txt': '...',
                    '1-rozdz': {
                        '_title.txt': '...',
                        '123-edfg.md': '#...\n',  # (no phrases at all, but there are some in `en`)
                    },
                },
            },

            {
                'en': {
                    '_title.txt': '...',
                    '1-ch': {
                        '_title.txt': '...',
                        '123-abcd.md': '#...\n',  # (no phrases at all, but there are some in `pl`)
                    },
                },
                'pl': {
                    '_title.txt': '...',
                    '1-rozdz': {
                        '_title.txt': '...',
                        '123-edfg.md': '#...\n### three\n### TWO'
                    },
                },
            },
        ],
        indirect=True,
    )
    def test_raises_knowledge_base_data_error_at_start_if_n6kb_article_lang_versions_differ_in_phrases(  # noqa
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
    ):
        settings = {
            'knowledge_base.active': 'true',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': "{'bots': [123]}",

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }

        with pytest.raises(KnowledgeBaseDataError) as err_info:
            _prepare_and_instantiate_view(settings)
        assert err_info.match(
            r"discrepancy between language versions of Knowledge "
            r"Base article \#123 regarding presence of "
            r"`name_details`-related phrases: 'three', 'two'",
        )


    @pytest.mark.parametrize(
        'knowledge_base_fs_tree',
        [
            {
                'en': {
                    '_title.txt': '...',
                    '1-ch': {
                        '_title.txt': '...',
                        '123-abcd.md': '#...\n### sześć',
                    },
                },
                'pl': {
                    '_title.txt': '...',
                    '1-rozdz': {
                        '_title.txt': '...',
                        '123-edfg.md': '#...\n### SZEŚĆ',
                    },
                },
            },
        ],
        indirect=True,
    )
    def test_logs_warning_at_start_if_n6kb_article_contains_unmatchable_phrase_with_non_ascii_characters(
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
        caplog: pytest.LogCaptureFixture,
    ):
        settings = {
            'knowledge_base.active': 'true',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': "{'bots': [123]}",

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }
        caplog.set_level(logging.WARNING, logger=None)

        _prepare_and_instantiate_view(settings)

        for lang in ['en', 'pl']:
            assert (
                f"ignoring `name_details`-related phrase 'sze\\u015b\\u0107' "
                f"(extracted from Knowledge Base article #123 in its {lang!a} "
                f"version) because it contains non-ASCII character(s)"
            ) in caplog.text


    @pytest.mark.parametrize(
        'knowledge_base_fs_tree',
        [
            {
                'en': {
                    '_title.txt': '...',
                    '1-ch': {
                        '_title.txt': '...',
                        '123-abcd.md': '#...\n### one !\n### one !',
                    },
                },
                'pl': {
                    '_title.txt': '...',
                    '1-rozdz': {
                        '_title.txt': '...',
                        '123-edfg.md': '#...\n###   oNE !\n###One !\t',
                    },
                },
            },
        ],
        indirect=True,
    )
    def test_logs_warning_at_start_if_n6kb_article_contains_phrase_duplicate(
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
        caplog: pytest.LogCaptureFixture,
    ):
        settings = {
            'knowledge_base.active': 'true',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.active': 'true',
            'name_details.category_to_n6kb_article_ids': "{'bots': [123]}",

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }
        caplog.set_level(logging.WARNING, logger=None)

        _prepare_and_instantiate_view(settings)

        for lang in ['en', 'pl']:
            assert (
                f"ignoring duplicate of `name_details`-related "
                f"phrase 'one !' in Knowledge Base article #123 "
                f"(in its {lang!a} version)"
            ) in caplog.text


    def test_enriches_without_moje_urls_and_logs_error_if_moje_advisories_info_cannot_be_retrieved(
        self,
        knowledge_base_fs_tree: FilesystemPathMapping,
        caplog: pytest.LogCaptureFixture,
    ):
        settings = {
            'knowledge_base.active': 'true',
            'knowledge_base.base_dir': str(knowledge_base_fs_tree.as_posix_path()),

            'name_details.active': 'true',
            'name_details.moje_api_key': 'Whatever...',
            'name_details.moje_api_url': 'https://127.0.0.1/NOT-A-USABLE-URL',
            'name_details.cve_extra_url_formats': (
                "{"
                "'enisa': 'https://euvd.enisa.europa.eu/vulnerability/{cve_id_lowercase}',"
                "'my_custom_site': 'https://my-custom-site.example.rg/cve-db/{cve_id_uppercase}',"
                "}"
            ),
            'name_details.category_to_n6kb_article_ids': (
                # (see constant `KNOWLEDGE_BASE_FILESYSTEM_TREE_DATA` defined earlier...)
                "{"
                "'bots': [1010, 1020],"
                "'vulnerable': [2010, 2020],"
                "}"
            ),

            'portal_frontend_properties.base_url': self.PORTAL_BASE_URL,
        }
        given_event = {
            'category': 'vulnerable',
            'name': (
                'ugly stuff: not only cve-2222-2222, but also: FTP allow password wo SSL '
                '+ Cve-3333-3333, cvE-4444-4444 and 1 more vulnerability (CVE-1111-1111); '
                'and loremipsum? ?What ; The , Heck! And perhaps nothing more? '
                'But let us repeat that: ugly stuff and LOREMIPSUM!'
            ),
            '...other keys...': '...irrelevant...',
        }
        expected_postprocessed_event = deepcopy(given_event) | {
            'name_details': {
                # (everything except stuff from *Moje*)
                'cve': {
                    'cve-1111-1111': {
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-1111-1111',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-1111-1111',
                        ],
                    },
                    'cve-2222-2222': {
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-2222-2222',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-2222-2222',
                        ],
                    },
                    'cve-3333-3333': {
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-3333-3333',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-3333-3333',
                        ],
                    },
                    'cve-4444-4444': {
                        'enisa': [
                            'https://euvd.enisa.europa.eu/vulnerability/cve-4444-4444',
                        ],
                        'my_custom_site': [
                            'https://my-custom-site.example.rg/cve-db/CVE-4444-4444',
                        ],
                    },
                },
                'phrase': {
                    'ugly stuff': {
                        'n6kb': [
                            f"{self.PORTAL_BASE_URL}/knowledge_base/articles/2010#n6kb-ugly-stuff",
                        ],
                    },
                    'ftp allow password wo ssl': {
                        'n6kb': [
                            (
                                f"{self.PORTAL_BASE_URL}/knowledge_base/articles/2010#"
                                f"n6kb-ftp-allow-password-wo-ssl"
                            ),
                        ],
                    },
                    'loremipsum': {
                        'n6kb': [
                            f"{self.PORTAL_BASE_URL}/knowledge_base/articles/2010#n6kb-loremipsum",
                        ],
                    },
                },
            },
        }
        processed_event = deepcopy(given_event)
        caplog.set_level(logging.ERROR, logger=None)

        view_instance = _prepare_and_instantiate_view(settings, auth_db_faker=None)
        view_instance.postprocess_cleaned_result(processed_event)

        assert processed_event == expected_postprocessed_event
        assert "Could not retrieve `moje.cert.pl`'s CVE-related advisories" in caplog.text


#
# Module-local helpers
#


class _MojeDataCacheStateCase(TypedDict):
    initial_cache_state: _MojeDataCacheState | None
    cache_update_need_expected: bool


class _MojeDataCacheState(TypedDict):
    moje_full_info: MojeCveAdvisoriesFullInfo
    cache_updated_at: datetime.datetime


class _EventCase(TypedDict):
    given_event: dict[str, Any]
    expected_postprocessed_event: dict[str, Any]
    expected_final_moje_cve_updated_at: datetime.datetime | None


class _AuthDBFaker(DBConnectionPatchMixin):

    #
    # Interface for fixtures and tests

    def __init__(self, initial_cache_state: _MojeDataCacheState | None):
        self._auth_db_connector_mock = MagicMock()
        with patch('n6lib.auth_db.api.SQLAuthDBConnector',
                   return_value=self._auth_db_connector_mock):
            self._auth_manage_api = AuthManageAPI()
        self._fake_auth_db_content = self._get_fake_auth_db_content(initial_cache_state)
        self.make_patches(collection=self._fake_auth_db_content, session_state={})

    @property
    def auth_manage_api(self) -> AuthManageAPI:
        return self._auth_manage_api

    @property
    def fake_auth_db_content(self) -> dict[str, list[models.AuxiliaryCacheEntry]]:
        return self._fake_auth_db_content

    #
    # Internals

    # noinspection PyArgumentList
    def _get_fake_auth_db_content(
        self,
        initial_cache_state: _MojeDataCacheState | None,
    ) -> dict[str, list[models.AuxiliaryCacheEntry]]:
        table_name = 'auxiliary_cache_entry'
        fake_auth_db_content = {
            table_name: [
                models.AuxiliaryCacheEntry(
                    key='unrelated_key:irrelevant',
                    raw_content=b'\x00 whatever \n\r\n\t\b',
                    updated_at=datetime.datetime.utcnow(),
                ),
                models.AuxiliaryCacheEntry(
                    key='also_unrelated_key:also_irrelevant',
                    raw_content=b'blah blah blah...',
                    updated_at=datetime.datetime(2020, 1, 2, 3, 4, 5),
                ),
            ],
        }
        if initial_cache_state is not None:
            raw_data_in_cache = initial_cache_state['moje_full_info'].as_json_bytes()
            fake_auth_db_content[table_name].append(
                models.AuxiliaryCacheEntry(
                    key='n6portal:moje_cve_advisories_info',
                    raw_content=raw_data_in_cache,
                    updated_at=initial_cache_state['cache_updated_at'],
                ),
            )
        return fake_auth_db_content

    def patch_db_connector(self, session_mock) -> None:
        self._auth_db_connector_mock.__enter__.return_value = session_mock
        self._auth_db_connector_mock.get_current_session.return_value = session_mock


def _opt_as_bool(settings_raw_option: str) -> bool:
    if settings_raw_option:
        return bool(ast.literal_eval(settings_raw_option))
    return False


def _prepare_and_instantiate_view(
    settings: dict,
    auth_db_faker: _AuthDBFaker | None = None,
) -> N6PortalStreamView:

    class _N6PortalStreamView_subclass(N6PortalStreamView):  # noqa
        pass

    with patch.object(N6LimitedStreamView, 'concrete_view_class',
                      new=classmethod(lambda cls, **kwargs: _N6PortalStreamView_subclass),
                      create=True):
        view_class = N6PortalStreamView.concrete_view_class(
            pyramid_configurator=SimpleNamespace(
                registry=SimpleNamespace(settings=settings),
            ),
        )
    with patch.object(N6LimitedStreamView, '__init__', return_value=None) as init_mock:
        view_instance = view_class()

    assert init_mock.mock_calls == [call()], 'internal assumption'
    assert view_class is _N6PortalStreamView_subclass, 'internal assumption'
    assert isinstance(view_instance, _N6PortalStreamView_subclass), 'internal assumption'
    assert isinstance(view_instance, N6PortalStreamView)
    assert view_instance.config_full.keys() == {
        'name_details',
        'portal_frontend_properties',
        'knowledge_base',
    }
    assert set(dir(view_instance)) >= {
        '_name_details_config',
        '_portal_base_url',
        '_knowledge_base_data',
        '_category_to_phrase_to_knowledge_base_urls',
        '_category_to_phrase_regex',
    }

    if auth_db_faker is not None:
        view_instance.request = SimpleNamespace(
            registry=SimpleNamespace(
                auth_manage_api=auth_db_faker.auth_manage_api,
            ),
        )

    return view_instance


def _get_final_moje_cve_updated_at(auth_db_faker: _AuthDBFaker) -> datetime.datetime:
    cache_entry = auth_db_faker.fake_auth_db_content['auxiliary_cache_entry'][-1]
    cached_info = json.loads(cache_entry.raw_content)
    return parse_iso_datetime_to_utc(cached_info['moje_cve_updated_at'])

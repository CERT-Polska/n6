# Copyright (c) 2013-2025 NASK. All rights reserved.

from __future__ import annotations

# Ensure all monkey-patching provided by `n6lib`
# and `n6sdk` is applied as early as possible.
import n6lib  # noqa

from collections import defaultdict
from collections.abc import (
    Callable,
    Set,
)
import functools
import re
import urllib.parse
from typing import (
    Any,
    ClassVar,
    Literal,
)

from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.interfaces import IRouter
from typing_extensions import LiteralString

from n6lib.auth_api import AuthAPIWithPrefetching
from n6lib.auth_db.api import AuthManageAPI
from n6lib.common_helpers import make_exc_ascii_str
from n6lib.config import (
    ConfigError,
    ConfigSection,
    combined_config_spec,
)
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.data_spec import (
    N6DataSpec,
    N6InsideDataSpec,
)
from n6lib.log_helpers import get_logger
from n6lib.mail_notices_api import MailNoticesAPI
from n6lib.moje_cve_advisories_retriever import (
    MojeCveAdvisoriesFullInfo,
    MojeCveAdvisoriesInfoRetriever,
)
from n6lib.oidc_provider_api import OIDCProviderAPI
from n6lib.pyramid_commons import (
    ConfigFromPyramidSettingsViewMixin,
    KnowledgeBaseRelatedViewMixin,
    N6APIKeyView,
    N6AvailableSourcesView,
    N6ConfigHelper,
    N6DailyEventsCountsView,
    N6DashboardView,
    N6InfoConfigView,
    N6InfoView,
    N6KnowledgeBaseArticlesView,
    N6KnowledgeBaseContentsView,
    N6KnowledgeBaseSearchView,
    N6LimitedStreamView,
    N6LoginMFAView,
    N6LoginMFAConfigConfirmView,
    N6LoginOIDCView,
    N6LoginView,
    N6LogoutView,
    N6MFAConfigConfirmView,
    N6MFAConfigView,
    N6NamesRankingView,
    N6OIDCCallbackView,
    N6OIDCInfoView,
    N6OIDCRefreshTokenView,
    N6OrgConfigView,
    N6OrgAgreementsView,
    N6AgreementsView,
    N6PasswordForgottenView,
    N6PasswordResetView,
    N6PortalRootFactory,
    N6RegistrationView,
    OIDCUserAuthenticationPolicy,
    conv_web_url,
)
from n6lib.pyramid_commons.knowledge_base_helpers import KnowledgeBaseDataError
from n6lib.rt_client_api import RTClientAPI
from n6portal._config_conv import config_conv_py_dict_category_to_n6kb_article_ids
from n6sdk.pyramid_commons import HttpResource


LOGGER = get_logger(__name__)


class N6PortalStreamView(KnowledgeBaseRelatedViewMixin,
                         ConfigFromPyramidSettingsViewMixin,
                         N6LimitedStreamView):

    @classmethod
    def prepare_config_custom_converters(cls) -> dict[str, Callable[[str], Any]]:
        return {
            'web_url': conv_web_url,
            'regex': re.compile,
            'py_dict_category_to_n6kb_article_ids': (
                config_conv_py_dict_category_to_n6kb_article_ids
            ),
        }

    config_spec = combined_config_spec(r'''
        [name_details]

        # Should the *name details* feature be enabled at all? If this
        # option is false, the other options will not be really used:
        active = false :: bool

        # The regex to match a CVE identifier in the `name` attribute of
        # an event:
        cve_regex = (?ai)\bcve-\d{4}-\d{4,}\b :: regex

        # API key, API URL and other options related to the `moje.cert.pl`'s
        # REST API (which is to be used *only if the API key is specified!*):
        moje_api_key = :: str
        moje_api_url = https://moje.cert.pl/api :: str
        moje_api_timeout = 6.1 :: float
        moje_api_retries = 1 :: int

        # Regarding any data from the `moje.cert.pl`'s REST API, for how
        # many seconds should that data be kept in our (*n6*-local) cache
        # before trying to fetch another update.
        moje_data_cache_validity_period_seconds = 3600 :: int

        # This dict's keys should be simple labels, and the corresponding
        # values should be `.format()`-able patterns of URLs (of websites
        # providing information about CVEs); each such URL pattern should
        # contain the `{cve_id_lowercase}` and/or `{cve_id_uppercase}`
        # format field(s):
        cve_extra_url_formats = {
            'enisa': 'https://euvd.enisa.europa.eu/vulnerability/{cve_id_lowercase}',
          } :: py_namespaces_dict

        # In this dict: each key should be a valid *n6* event category
        # identifier; each value should be a list of int numbers, each
        # being the identifier of an existing article in *n6 Knowledge
        # Base*. If the `active` option (see above) is true and this dict
        # is *not* empty, then the `active` option in the `knowledge_base`
        # config section *is required to be also true*.
        category_to_n6kb_article_ids = {} :: py_dict_category_to_n6kb_article_ids

        # The regex to match (within a *Markdown*-formatted article in
        # our *n6 Knowledge Base*) any of the security-related *phrases*
        # (naming a threat, insecure service or practice, etc.) that
        # shall be recognized when encountered in the `name` attribute
        # of an *event*. The *phrase* is to be singled out from each
        # matched article fragment by referring to the named regex group
        # `phrase`, then stripped of leading/trailing whitespace and
        # converted to lowercase (note: the default regex extracts a
        # *phrase* just from each `###`-prefixed Markdown header, that
        # is, an `h3` header):
        n6kb_phrase_regex = (?m)^\x23{3}(?!\x23)(?P<phrase>.+)$ :: regex


        [portal_frontend_properties]

        # (See the relevant comments in `etc/web/conf/portal.ini`...)
        base_url :: web_url
    ''')

    @classmethod
    def concrete_view_class(cls, **kwargs):
        view_class = super().concrete_view_class(**kwargs)
        assert hasattr(view_class, '_knowledge_base_data')

        view_class._name_details_config = (
            view_class.config_full['name_details']
        )
        view_class._portal_base_url = (
            view_class.config_full['portal_frontend_properties']['base_url']
        )

        if (view_class.config_full['name_details']['active']
              and view_class.config_full['name_details']['category_to_n6kb_article_ids']):
            if view_class._knowledge_base_data is None:
                raise ConfigError(
                    'given that option `name_details.active` is true and '
                    'option `name_details.category_to_n6kb_article_ids` '
                    'is not empty, option `knowledge_base.active` should '
                    'be true (but is false)',
                )
            assert isinstance(view_class._knowledge_base_data, dict)
            view_class._category_to_phrase_to_knowledge_base_urls = (
                view_class._prepare_category_to_phrase_to_knowledge_base_urls()
            )
            view_class._category_to_phrase_regex = (
                view_class._prepare_category_to_phrase_regex()
            )
        else:
            view_class._category_to_phrase_to_knowledge_base_urls = {}
            view_class._category_to_phrase_regex = {}

        assert (
            view_class._category_to_phrase_regex.keys()
            == view_class._category_to_phrase_to_knowledge_base_urls.keys()
        )

        return view_class

    _name_details_config: ClassVar[ConfigSection]
    _portal_base_url: ClassVar[str]
    _knowledge_base_data: ClassVar[dict[str, Any] | None]
    _category_to_phrase_to_knowledge_base_urls: ClassVar[dict[str, dict[str, Set[str]]]]
    _category_to_phrase_regex: ClassVar[dict[str, re.Pattern[str]]]

    @classmethod
    def _prepare_category_to_phrase_to_knowledge_base_urls(cls) -> dict[str, dict[str, Set[str]]]:
        assert cls._knowledge_base_data is not None
        category_to_phrase_to_urls = {}
        category_to_article_ids = cls._name_details_config['category_to_n6kb_article_ids']
        for category, article_ids in category_to_article_ids.items():
            phrase_to_urls = cls._get_phrase_to_knowledge_base_urls(article_ids)
            if phrase_to_urls:
                category_to_phrase_to_urls[category] = phrase_to_urls
        return category_to_phrase_to_urls

    @classmethod
    def _get_phrase_to_knowledge_base_urls(cls, article_ids: list[str]) -> dict[str, Set[str]]:
        phrase_to_urls = defaultdict(set)
        for art_id in article_ids:
            article_url = f"{cls._portal_base_url}/knowledge_base/articles/{art_id}"
            for phrase in cls._extract_phrases_from_knowledge_base_article(art_id):
                anchor = cls._convert_phrase_to_anchor(phrase)
                url_with_anchor = f"{article_url}#{anchor}"
                phrase_to_urls[phrase].add(url_with_anchor)
        return dict(phrase_to_urls)

    @classmethod
    def _extract_phrases_from_knowledge_base_article(cls, art_id: str) -> list[str]:
        lang_to_extracted_phrases = cls._get_lang_to_extracted_phrases(art_id)
        en_phrases = lang_to_extracted_phrases['en']
        pl_phrases = lang_to_extracted_phrases['pl']

        phrases_diff = en_phrases.symmetric_difference(pl_phrases)
        if phrases_diff:
            outlier_phrase_listing = ', '.join(map(ascii, sorted(phrases_diff)))
            raise KnowledgeBaseDataError(
                f'discrepancy between language versions of Knowledge Base article '
                f'#{art_id} regarding presence of `name_details`-related phrases: '
                f'{outlier_phrase_listing}'
            )

        assert en_phrases == pl_phrases
        return sorted(en_phrases)

    @classmethod
    def _get_lang_to_extracted_phrases(
        cls,
        art_id: str,
    ) -> dict[Literal['en', 'pl'], set[str]]:
        article = cls._knowledge_base_data['articles'].get(art_id)
        if article is None:
            raise ConfigError(
                f'option `name_details.category_to_n6kb_article_ids` '
                f'contains Knowledge Base article identifier {art_id!a} '
                f'which refers to non-existent article'
            )
        lang_to_extracted_phrases = {}
        n6kb_phrase_regex = cls._name_details_config['n6kb_phrase_regex']
        for lang in ['en', 'pl']:
            content = article['content'][lang]
            lang_phrases = set()
            for match in n6kb_phrase_regex.finditer(content):
                phrase = match.group('phrase').strip().lower()
                if phrase:
                    if not phrase.isascii():
                        LOGGER.warning(
                            'ignoring `name_details`-related phrase %a '
                            '(extracted from Knowledge Base article #%s '
                            'in its %a version) because it contains '
                            'non-ASCII character(s)',
                            phrase, art_id, lang,
                        )
                        continue
                    if phrase in lang_phrases:
                        LOGGER.warning(
                            f'ignoring duplicate of `name_details`-related '
                            f'phrase %a in Knowledge Base article #%s (in '
                            f'its %a version)',
                            phrase, art_id, lang,
                        )
                        continue
                    lang_phrases.add(phrase)
            lang_to_extracted_phrases[lang] = lang_phrases
        return lang_to_extracted_phrases

    @classmethod
    def _convert_phrase_to_anchor(cls, phrase: str) -> str:
        adjusted = cls._ANCHOR_UNWANTED_CHARS_REGEX.sub(
            cls._replace_char_in_anchor,
            phrase,
        )
        return f'n6kb-{adjusted}'

    _ANCHOR_UNWANTED_CHARS_REGEX = re.compile(r'[^a-z0-9]')

    @staticmethod
    def _replace_char_in_anchor(match: re.Pattern[str]) -> str:
        matched = match.group(0)
        if matched == ' ':
            return '-'
        return f'_{ord(matched):x}'

    @classmethod
    def _prepare_category_to_phrase_regex(cls) -> dict[str, re.Pattern[str]]:
        category_to_phrase_regex = {}
        for category, phrase_keyed_dict in cls._category_to_phrase_to_knowledge_base_urls.items():
            phrase_alternatives = phrase_keyed_dict.keys()
            assert all(
                phrase and phrase.isascii() and phrase == phrase.strip()
                for phrase in phrase_alternatives
            )
            category_to_phrase_regex[category] = re.compile(
                '|'.join(sorted(
                    (
                        (r'(?:\b|^)' if phrase[0].isalnum() or phrase.startswith('_') else '')
                        + re.escape(phrase)
                        + (r'(?:\b|$)' if phrase[-1].isalnum() or phrase.endswith('_') else '')
                    )
                    for phrase in phrase_alternatives
                )),
                re.IGNORECASE,
            )
        return category_to_phrase_regex

    @functools.cached_property
    def _cve_id_to_urls(self) -> dict[str, list[str]]:
        # Note: it is a `cached_property`, so it will be invoked at most
        # once per view instance (that is, once per entire request).
        cfg = self._name_details_config
        if not cfg['moje_api_key']:
            return {}
        retriever = MojeCveAdvisoriesInfoRetriever(
            moje_api_key=cfg['moje_api_key'],
            moje_api_url=cfg['moje_api_url'],
            moje_api_timeout=cfg['moje_api_timeout'],
            moje_api_retries=cfg['moje_api_retries'],
            cache_validity_period_seconds=cfg['moje_data_cache_validity_period_seconds'],
        )
        try:
            with self.auth_manage_api as api:
                info: MojeCveAdvisoriesFullInfo = retriever.retrieve(auth_manage_api=api)
        except Exception as exc:
            LOGGER.error(
                "Could not retrieve `moje.cert.pl`'s CVE-related advisories "
                "info (%s). Resultant event(s) will be generated *without* "
                "enriching them with any `moje.cert.pl` advisories' URLs!",
                make_exc_ascii_str(exc),
                exc_info=True,
            )
            return {}
        return info.cve_id_to_urls

    def postprocess_cleaned_result(self, cleaned_result: dict[str, Any]) -> None:
        if 'name' in cleaned_result and self._name_details_config['active']:
            name_details = self._get_name_details(cleaned_result)
            if name_details:
                cleaned_result['name_details'] = name_details

    def _get_name_details(
        self,
        cleaned_result: dict[str, Any],
    ) -> dict[LiteralString, dict[str, dict[str, list[str]]]]:
        assert 'category' in cleaned_result
        assert 'name' in cleaned_result
        assert 'name_details' not in cleaned_result
        name_details = {}
        if cve_part := self._get_cve_part(cleaned_result):
            name_details['cve'] = cve_part
        if phrase_part := self._get_phrase_part(cleaned_result):
            name_details['phrase'] = phrase_part
        return name_details

    def _get_cve_part(
        self,
        cleaned_result: dict[str, Any],
    ) -> dict[str, dict[str, list[str]]]:
        cve_part = {}
        for cve_id in self._find_cve_ids(cleaned_result):
            if cve_id in cve_part:
                continue
            site_label_to_urls = self._get_extra_site_label_to_urls_for_single_cve(cve_id)
            if moje_urls := self._get_moje_urls_for_single_cve(cve_id):
                site_label_to_urls['moje'] = moje_urls
            if site_label_to_urls:
                cve_part[cve_id] = site_label_to_urls
        return cve_part

    def _find_cve_ids(
        self,
        cleaned_result: dict[str, Any],
    ) -> list[str]:
        name_lowercase = cleaned_result['name'].lower()
        cve_regex = self._name_details_config['cve_regex']
        return cve_regex.findall(name_lowercase)

    def _get_extra_site_label_to_urls_for_single_cve(
        self,
        cve_id: str,
    ) -> dict[str, list[str]]:
        format_items = {
            'cve_id_lowercase': urllib.parse.quote(cve_id),
            'cve_id_uppercase': urllib.parse.quote(cve_id.upper()),
        }
        return {
            site_label: [pattern.format_map(format_items)]
            for site_label, pattern in self._name_details_config['cve_extra_url_formats'].items()
        }

    def _get_moje_urls_for_single_cve(self, cve_id: str) -> list[str]:
        return list(self._cve_id_to_urls.get(cve_id, ()))

    def _get_phrase_part(
        self,
        cleaned_result: dict[str, Any],
    ) -> dict[str, dict[str, list[str]]]:
        category = cleaned_result['category']
        phrase_to_urls = self._category_to_phrase_to_knowledge_base_urls.get(category)
        if not phrase_to_urls:
            return {}

        phrase_part = {}
        for phrase in self._find_phrases(cleaned_result):
            if phrase in phrase_part:
                continue
            urls = phrase_to_urls.get(phrase)
            assert urls
            phrase_part[phrase] = {
                'n6kb': sorted(urls)
            }
        return phrase_part

    def _find_phrases(
        self,
        cleaned_result: dict[str, Any],
    ) -> list[str]:
        category = cleaned_result['category']
        name_lowercase = cleaned_result['name'].lower()
        phrase_regex = self._category_to_phrase_regex[category]
        return phrase_regex.findall(name_lowercase)


n6_data_spec = N6DataSpec()
n6_inside_data_spec = N6InsideDataSpec()


RESOURCES = [

    #
    # Event data resources

    HttpResource(
        resource_id='/search/events',
        url_pattern='/search/events.{renderer}',
        view_base=N6PortalStreamView,
        view_properties=dict(
            data_spec=n6_data_spec,
            data_backend_api_method='search_events',
            renderers='json',
        ),
        # 'OPTIONS' -- required for [Cross-Origin Resource Sharing](https://www.w3.org/TR/cors/).
        http_methods=('GET', 'OPTIONS'),
        permission='auth',
    ),
    HttpResource(
        resource_id='/report/inside',
        url_pattern='/report/inside.{renderer}',
        view_base=N6PortalStreamView,
        view_properties=dict(
            data_spec=n6_inside_data_spec,
            data_backend_api_method='report_inside',
            renderers='json',
        ),
        # 'OPTIONS' -- required for [Cross-Origin Resource Sharing](https://www.w3.org/TR/cors/).
        http_methods=('GET', 'OPTIONS'),
        permission='auth',
    ),
    HttpResource(
        resource_id='/report/threats',
        url_pattern='/report/threats.{renderer}',
        view_base=N6PortalStreamView,
        view_properties=dict(
            data_spec=n6_data_spec,
            data_backend_api_method='report_threats',
            renderers='json',
        ),
        # 'OPTIONS' -- required for [Cross-Origin Resource Sharing](https://www.w3.org/TR/cors/).
        http_methods=('GET', 'OPTIONS'),
        permission='auth',
    ),

    #
    # Event summary resources

    HttpResource(
        resource_id='/dashboard',
        url_pattern='/dashboard',
        view_base=N6DashboardView,
        http_methods='GET',
        permission='auth',
        http_cache=600,
    ),
    HttpResource(
        resource_id='/daily_events_counts',
        url_pattern='/daily_events_counts',
        view_base=N6DailyEventsCountsView,
        http_methods='GET',
        permission='auth',
        http_cache=600,
    ),
    HttpResource(
        resource_id='/names_ranking',
        url_pattern='/names_ranking',
        view_base=N6NamesRankingView,
        http_methods='GET',
        permission='auth',
        http_cache=600,
    ),

    #
    # Informational resources

    # Note: for each of the following 3 resources, `url_pattern` includes
    # the `.json` suffix -- just for consistency with the corresponding
    # *event data resource* (see earlier...).
    HttpResource(
        resource_id='/search/events/sources',
        url_pattern='/search/events/sources.json',
        view_base=N6AvailableSourcesView,
        http_methods='GET',
        permission='auth',
    ),
    HttpResource(
        resource_id='/report/inside/sources',
        url_pattern='/report/inside/sources.json',
        view_base=N6AvailableSourcesView,
        http_methods='GET',
        permission='auth',
    ),
    HttpResource(
        resource_id='/report/threats/sources',
        url_pattern='/report/threats/sources.json',
        view_base=N6AvailableSourcesView,
        http_methods='GET',
        permission='auth',
    ),

    HttpResource(
        resource_id='/info',
        url_pattern='/info',
        view_base=N6InfoView,
        http_methods='GET',
        permission='all',
    ),
    HttpResource(
        resource_id='/info/config',
        url_pattern='/info/config',
        view_base=N6InfoConfigView,
        http_methods='GET',
        permission='auth',
    ),
    HttpResource(
        resource_id='/info/oidc',
        url_pattern='/info/oidc',
        view_base=N6OIDCInfoView,
        http_methods=('GET', 'POST'),
        permission='all',
    ),

    #
    # Authentication/configuration/management resources

    # * Related to authentication of Portal users:

    HttpResource(
        resource_id='/login',
        url_pattern='/login',
        view_base=N6LoginView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/login/mfa',
        url_pattern='/login/mfa',
        view_base=N6LoginMFAView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/login/mfa_config/confirm',
        url_pattern='/login/mfa_config/confirm',
        view_base=N6LoginMFAConfigConfirmView,
        http_methods='POST',
        permission='all',
    ),

    HttpResource(
        resource_id='/oidc/callback',
        url_pattern='/oidc/callback',
        view_base=N6OIDCCallbackView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/login/oidc',
        url_pattern='/login/oidc',
        view_base=N6LoginOIDCView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/oidc/refresh_token',
        url_pattern='/oidc/refresh_token',
        view_base=N6OIDCRefreshTokenView,
        http_methods='POST',
        permission='all',
    ),

    HttpResource(
        resource_id='/mfa_config',
        url_pattern='/mfa_config',
        view_base=N6MFAConfigView,
        http_methods=('GET', 'POST'),
        permission='auth',
    ),
    HttpResource(
        resource_id='/mfa_config/confirm',
        url_pattern='/mfa_config/confirm',
        view_base=N6MFAConfigConfirmView,
        http_methods='POST',
        permission='auth',
    ),

    HttpResource(
        resource_id='/password/forgotten',
        url_pattern='/password/forgotten',
        view_base=N6PasswordForgottenView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/password/reset',
        url_pattern='/password/reset',
        view_base=N6PasswordResetView,
        http_methods='POST',
        permission='all',
    ),

    HttpResource(
        resource_id='/logout',
        url_pattern='/logout',
        view_base=N6LogoutView,
        http_methods='GET',  # <- maybe FIXME later? - shouldn't it be POST?
        permission='all',
    ),

    # * Registration/configuration of organizations:

    HttpResource(
        resource_id='/register',
        url_pattern='/register',
        view_base=N6RegistrationView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/org_config',
        url_pattern='/org_config',
        view_base=N6OrgConfigView,
        http_methods=('GET', 'POST'),
        permission='auth',
    ),
    HttpResource(
        resource_id='/org_agreements',
        url_pattern='/org_agreements',
        view_base=N6OrgAgreementsView,
        http_methods=('GET', 'POST'),
        permission='auth',
    ),

    # * API key management (configuring REST API authentication):

    HttpResource(
        resource_id='/api_key',
        url_pattern='/api_key',
        view_base=N6APIKeyView,
        http_methods=('GET', 'POST', 'DELETE'),
        permission='auth',
    ),

    #
    # Knowledge-base-related resources

    HttpResource(
        resource_id='/knowledge_base/contents',
        url_pattern='/knowledge_base/contents',
        view_base=N6KnowledgeBaseContentsView,
        http_methods='GET',
        permission='auth',
    ),
    HttpResource(
        resource_id='/knowledge_base/articles',
        url_pattern='/knowledge_base/articles/{article_id}',
        view_base=N6KnowledgeBaseArticlesView,
        http_methods='GET',
        permission='auth',
    ),
    HttpResource(
        resource_id='/knowledge_base/search',
        url_pattern='/knowledge_base/search',
        view_base=N6KnowledgeBaseSearchView,
        http_methods='GET',
        permission='auth',
    ),
    
    # * Agreements list

    HttpResource(
        resource_id='/agreements',
        url_pattern='/agreements',
        view_base=N6AgreementsView,
        http_methods='GET',
        permission='all',
    ),
]


def main(global_config: dict[str, str], **settings) -> IRouter:
    return N6ConfigHelper(
        settings=settings,
        data_backend_api_class=N6DataBackendAPI,
        component_module_name='n6portal',
        auth_api_class=AuthAPIWithPrefetching,  # <- XXX: legacy stuff, to be removed in the future
        auth_manage_api=AuthManageAPI(settings),
        mail_notices_api=MailNoticesAPI(settings),
        oidc_provider_api=OIDCProviderAPI(settings),
        rt_client_api=RTClientAPI(settings),
        authentication_policy=OIDCUserAuthenticationPolicy(settings),
        resources=RESOURCES,
        authorization_policy=ACLAuthorizationPolicy(),
        root_factory=N6PortalRootFactory,
    ).make_wsgi_app()

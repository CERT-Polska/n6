# Copyright (c) 2013-2024 NASK. All rights reserved.

# Ensure all monkey-patching provided by `n6lib`
# and `n6sdk` is applied as early as possible.
import n6lib  # noqa

from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.interfaces import IRouter

from n6lib.auth_api import AuthAPIWithPrefetching
from n6lib.auth_db.api import AuthManageAPI
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.data_spec import (
    N6DataSpec,
    N6InsideDataSpec,
)
from n6lib.mail_notices_api import MailNoticesAPI
from n6lib.oidc_provider_api import OIDCProviderAPI
from n6lib.pyramid_commons import (
    AuthTktUserAuthenticationPolicy,
    N6APIKeyView,
    N6ConfigHelper,
    N6DailyEventsCountsView,
    N6DashboardView,
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
    N6OrgConfigView,
    N6OrgAgreementsView,
    N6AgreementsView,
    N6PasswordForgottenView,
    N6PasswordResetView,
    N6PortalRootFactory,
    N6RegistrationView,
    N6InfoConfigView,
    OIDCUserAuthenticationPolicy,
)
from n6lib.rt_client_api import RTClientAPI
from n6sdk.pyramid_commons import (
    HttpResource,
)


n6_data_spec = N6DataSpec()
n6_inside_data_spec = N6InsideDataSpec()


RESOURCES = [

    #
    # Event data resources

    HttpResource(
        resource_id='/search/events',
        url_pattern='/search/events.{renderer}',
        view_base=N6LimitedStreamView,
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
        view_base=N6LimitedStreamView,
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
        view_base=N6LimitedStreamView,
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
        resource_id='/login/oidc',
        url_pattern='/login/oidc',
        view_base=N6LoginOIDCView,
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

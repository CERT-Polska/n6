# Copyright (c) 2013-2024 NASK. All rights reserved.

# (note: this package provides the actual n6-specific versions of the
# Pyramid-related n6 stuff -- based on the `n6sdk` stuff, but richer/
# /more sophisticated...)

from n6lib.pyramid_commons._pyramid_commons import (
    N6AgreementsView,
    N6APIKeyView,
    N6DailyEventsCountsView,
    N6DashboardView,
    N6DefaultStreamViewBase,
    N6InfoView,
    N6KnowledgeBaseArticlesView,
    N6KnowledgeBaseContentsView,
    N6KnowledgeBaseSearchView,
    N6LimitedStreamView,
    N6LoginOIDCView,
    N6LoginView,
    N6LoginMFAConfigConfirmView,
    N6LoginMFAView,
    N6LogoutView,
    N6MFAConfigConfirmView,
    N6MFAConfigView,
    N6NamesRankingView,
    N6OrgAgreementsView,
    N6OrgConfigView,
    N6PasswordForgottenView,
    N6PasswordResetView,
    N6PortalRootFactory,
    N6RegistrationView,
    N6InfoConfigView,

    N6ConfigHelper,

    BaseUserAuthenticationPolicy,
    DevFakeUserAuthenticationPolicy,
    AuthTktUserAuthenticationPolicy,
    SSLUserAuthenticationPolicy,
    OIDCUserAuthenticationPolicy,
    APIKeyOrSSLUserAuthenticationPolicy,

    get_certificate_credentials,
)
from n6lib.pyramid_commons._tween_factories import (
    auth_api_context_tween_factory,
    auth_db_apis_maintenance_tween_factory,
    event_db_session_maintenance_tween_factory,
    preflight_requests_handler_tween_factory,
)


__all__ = [
    'N6AgreementsView',
    'N6APIKeyView',
    'N6DailyEventsCountsView',
    'N6DashboardView',
    'N6DefaultStreamViewBase',
    'N6InfoView',
    'N6KnowledgeBaseArticlesView',
    'N6KnowledgeBaseContentsView',
    'N6KnowledgeBaseSearchView',
    'N6LimitedStreamView',
    'N6LoginOIDCView',
    'N6LoginView',
    'N6LoginMFAConfigConfirmView',
    'N6LoginMFAView',
    'N6LogoutView',
    'N6MFAConfigConfirmView',
    'N6MFAConfigView',
    'N6NamesRankingView',
    'N6OrgAgreementsView',
    'N6OrgConfigView',
    'N6PasswordForgottenView',
    'N6PasswordResetView',
    'N6PortalRootFactory',
    'N6RegistrationView',
    'N6InfoConfigView',

    'N6ConfigHelper',

    'BaseUserAuthenticationPolicy',
    'DevFakeUserAuthenticationPolicy',
    'AuthTktUserAuthenticationPolicy',
    'SSLUserAuthenticationPolicy',
    'OIDCUserAuthenticationPolicy',
    'APIKeyOrSSLUserAuthenticationPolicy',

    'get_certificate_credentials',

    'auth_api_context_tween_factory',
    'auth_db_apis_maintenance_tween_factory',
    'event_db_session_maintenance_tween_factory',
    'preflight_requests_handler_tween_factory',
]

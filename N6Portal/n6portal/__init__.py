# Copyright (c) 2013-2021 NASK. All rights reserved.

# Ensure all monkey-patching provided by `n6lib`
# and `n6sdk` is applied as early as possible.
import n6lib  # noqa

import os
import sys
from typing import Dict

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
from n6lib.pyramid_commons import (
    AuthTktUserAuthenticationPolicy,
    N6APIKeyView,
    N6CertificateLoginView,
    N6ConfigHelper,
    N6DashboardView,
    N6InfoView,
    N6LegacyLoginView,
    N6LimitedStreamView,
    N6LoginMFAView,
    N6LoginMFAConfigConfirmView,
    N6LoginView,
    N6LogoutView,
    N6MFAConfigConfirmView,
    N6MFAConfigView,
    N6OrgConfigView,
    N6PasswordForgottenView,
    N6PasswordResetView,
    N6PortalRootFactory,
    N6RegistrationView,
    N6InfoConfigView,
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
]

    #
    # Authentication/configuration/management resources

    # * Related to authentication of Portal users:

if os.environ.get('N6_PORTAL_AUTH_2021'):
  RESOURCES += [
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
  ]
else:
  # TODO later: remove the `N6_PORTAL_AUTH_2021` env variable +
  #             the following 2 deprecated resource declarations...
  RESOURCES += [
    HttpResource(
        resource_id='/login',
        url_pattern='/login',
        view_base=N6LegacyLoginView,
        http_methods='POST',
        permission='all',
    ),
    HttpResource(
        resource_id='/cert_login',
        url_pattern='/cert_login',
        view_base=N6CertificateLoginView,
        http_methods='GET',
        permission='all',
    ),
  ]

RESOURCES += [
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

    # * Related to authentication of REST API users:

    HttpResource(
        resource_id='/api_key',
        url_pattern='/api_key',
        view_base=N6APIKeyView,
        http_methods=('GET', 'POST', 'DELETE'),
        permission='auth',
    ),
]


def main(global_config,  # type: Dict[str, str]
         **settings):
    # type: (...) -> IRouter
    return N6ConfigHelper(
        settings=settings,
        data_backend_api_class=N6DataBackendAPI,
        component_module_name='n6portal',
        auth_api_class=AuthAPIWithPrefetching,  # <- XXX: legacy stuff, to be removed in the future
        auth_manage_api=AuthManageAPI(settings),
        mail_notices_api=MailNoticesAPI(settings),
        rt_client_api=RTClientAPI(settings),
        authentication_policy=AuthTktUserAuthenticationPolicy(settings),
        resources=RESOURCES,
        authorization_policy=ACLAuthorizationPolicy(),
        root_factory=N6PortalRootFactory,
    ).make_wsgi_app()

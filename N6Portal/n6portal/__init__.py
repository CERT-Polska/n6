# Copyright (c) 2013-2020 NASK. All rights reserved.

from pyramid.authorization import ACLAuthorizationPolicy

from n6lib.auth_api import AuthAPI
from n6lib.auth_db.api import (
    AuthQueryAPI,
    AuthManageAPI,
)
from n6lib.common_helpers import provide_surrogateescape
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.data_spec import (
    N6DataSpec,
    N6InsideDataSpec,
)
from n6lib.pyramid_commons import (
    N6AuthView,
    N6ConfigHelper,
    N6InfoView,
    N6LimitedStreamView,
    N6PortalRootFactory,
    N6RegistrationView,
    LoginOrSSLUserAuthenticationPolicy,
)
from n6sdk.pyramid_commons import (
    HttpResource,
)

provide_surrogateescape()


n6_data_spec = N6DataSpec()
n6_inside_data_spec = N6InsideDataSpec()

RESOURCES = [
    HttpResource(
        resource_id='/search/events',
        url_pattern='/search/events.{renderer}',
        view_base=N6LimitedStreamView,
        view_properties=dict(
            data_spec=n6_data_spec,
            data_backend_api_method='search_events',
            renderers='json',
        ),
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
        permission='auth',
    ),
    HttpResource(
        resource_id='/info',
        url_pattern='/info',
        view_base=N6InfoView,
        view_properties=dict(
            data_backend_api_method='get_user_info',
        ),
        permission='all',
    ),
    HttpResource(
        resource_id='/login',
        url_pattern='/login',
        view_base=N6AuthView,
        view_properties=dict(
            data_backend_api_method='login',
        ),
        permission='all',
    ),
    HttpResource(
        resource_id='/cert_login',
        url_pattern='/cert_login',
        view_base=N6AuthView,
        view_properties=dict(
            data_backend_api_method='login_with_cert',
        ),
        http_methods='GET',  # XXX: shouldn't it be POST?
        permission='all',
    ),
    HttpResource(
        resource_id='/logout',
        url_pattern='/logout',
        view_base=N6AuthView,
        view_properties=dict(
            data_backend_api_method='logout',
        ),
        http_methods='GET',  # XXX: shouldn't it be POST?
        permission='all',
    ),
    HttpResource(
        resource_id='/register',
        url_pattern='/register',
        view_base=N6RegistrationView,
        http_methods='POST',
        permission='all',
    ),
]


def main(global_config, **settings):
    return N6ConfigHelper(
        settings=settings,
        data_backend_api_class=N6DataBackendAPI,
        component_module_name='n6portal',
        auth_api_class=AuthAPI,                 # <- XXX: legacy stuff, to be removed in the future
        auth_query_api=AuthQueryAPI(settings),  # <- XXX: dummy stuff yet; to be used in the future
        auth_manage_api=AuthManageAPI(settings),
        authentication_policy=LoginOrSSLUserAuthenticationPolicy(settings),
        resources=RESOURCES,
        authorization_policy=ACLAuthorizationPolicy(),
        root_factory=N6PortalRootFactory,
    ).make_wsgi_app()

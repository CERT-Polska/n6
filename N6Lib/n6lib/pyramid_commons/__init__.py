# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

# (note: this package provides the actual n6-specific versions of the
# Pyramid-related n6 stuff -- based on the `n6sdk` stuff, but richer/
# /more sophisticated...)


from n6lib.pyramid_commons._pyramid_commons import (
    N6AuthView,
    N6DefaultStreamViewBase,
    N6CorsSupportStreamView,
    N6InfoView,
    N6LimitedStreamView,
    N6PortalRootFactory,

    auth_api_context_tween_factory,
    transact_tween_factory,

    N6ConfigHelper,

    BaseUserAuthenticationPolicy,
    DevFakeUserAuthenticationPolicy,
    LoginOrSSLUserAuthenticationPolicy,
    SSLUserAuthenticationPolicy,

    get_certificate_credentials,
)


__all__ = [
    'N6AuthView',
    'N6CorsSupportStreamView',
    'N6DefaultStreamViewBase',
    'N6InfoView',
    'N6LimitedStreamView',
    'N6PortalRootFactory',

    'auth_api_context_tween_factory',
    'transact_tween_factory',

    'N6ConfigHelper',

    'BaseUserAuthenticationPolicy',
    'DevFakeUserAuthenticationPolicy',
    'LoginOrSSLUserAuthenticationPolicy',
    'SSLUserAuthenticationPolicy',

    'get_certificate_credentials',
]

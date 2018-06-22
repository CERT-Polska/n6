# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

# this package provides the actual n6 versions (beyond the SDK)
# of the Pyramid-related n6 stuff


from n6lib.pyramid_commons._pyramid_commons import (
    N6AuthView,
    N6DefaultStreamViewBase,
    N6CorsSupportStreamView,
    N6InfoView,
    N6LimitedStreamView,
    N6PortalRootFactory,
    DeviceRequestGetViewBase,
    DeviceRequestPostViewBase,

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
    'DeviceRequestGetViewBase',
    'DeviceRequestPostViewBase',

    'auth_api_context_tween_factory',
    'transact_tween_factory',

    'N6ConfigHelper',

    'BaseUserAuthenticationPolicy',
    'DevFakeUserAuthenticationPolicy',
    'LoginOrSSLUserAuthenticationPolicy',
    'SSLUserAuthenticationPolicy',

    'get_certificate_credentials',
]

# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
.. note::

   Most of the stuff defined in this module is not fully documented yet.
   For basic information how to use it (or at least most of it) --
   please consult the :ref:`tutorial`.
"""


from n6sdk.pyramid_commons._pyramid_commons import (
    DUMMY_PERMISSION,
    exc_to_http_exc,

    DefaultRootFactory,
    StreamResponse,

    AbstractViewBase,
    CommaSeparatedParamValuesViewMixin,
    OmittingEmptyParamsViewMixin,
    PreparingNoParamsViewMixin,
    SingleParamValuesViewMixin,
    DefaultStreamViewBase,

    HttpResource,
    BasicConfigHelper,
    ConfigHelper,

    register_stream_renderer,
    registered_stream_renderers,

    BaseAuthenticationPolicy,
    AnonymousAuthenticationPolicy,
)


__all__ = [
    'DUMMY_PERMISSION',
    'exc_to_http_exc',

    'DefaultRootFactory',
    'StreamResponse',

    'AbstractViewBase',
    'CommaSeparatedParamValuesViewMixin',
    'OmittingEmptyParamsViewMixin',
    'PreparingNoParamsViewMixin',
    'SingleParamValuesViewMixin',
    'DefaultStreamViewBase',

    'HttpResource',
    'BasicConfigHelper',
    'ConfigHelper',

    'register_stream_renderer',
    'registered_stream_renderers',

    'BaseAuthenticationPolicy',
    'AnonymousAuthenticationPolicy',
]

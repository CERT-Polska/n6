# -*- coding: utf-8 -*-

# Copyright (c) 2013-2016 NASK. All rights reserved.


import functools
import itertools
import logging

from pyramid.config import Configurator
from pyramid.httpexceptions import (
    HTTPException,
    HTTPBadRequest,
    HTTPForbidden,
    HTTPNotFound,
    HTTPServerError,
)
from pyramid.response import Response
from pyramid.security import (
    #ALL_PERMISSIONS,
    Allow,
    Authenticated,
    Everyone,
)

from n6sdk.class_helpers import attr_required
from n6sdk.data_spec import BaseDataSpec
from n6sdk.encoding_helpers import (
    ascii_str,
    py_identifier_str,
)
from n6sdk.exceptions import (
    DataAPIError,
    AuthorizationError,
    ParamCleaningError,
    ResultCleaningError,
    TooMuchDataError
)
from n6sdk.pyramid_commons import renderers as standard_stream_renderers


LOGGER = logging.getLogger(__name__)



#
# Auxiliary constants

DUMMY_PERMISSION = "dummy_permission"



#
# Helper functions

def exc_to_http_exc(exc):
    """
    Takes any :exc:`~exceptions.Exception` instance, returns a
    :exc:`pyramid.httpexceptions.HTTPException` instance.
    """
    if isinstance(exc, HTTPException):
        code = getattr(exc, 'code', None)
        if isinstance(code, (int, long)) and 200 <= code < 500:
            LOGGER.debug(
                'HTTPException: %r ("%s", code: %s)',
                exc, ascii_str(exc), code)
        else:
            LOGGER.error(
                'HTTPException: %r ("%s", code: %r)',
                exc, ascii_str(exc), code,
                exc_info=True)
        http_exc = exc
    elif isinstance(exc, AuthorizationError):
        LOGGER.debug(
            'Authorization not successful: %r (public message: "%s")',
            exc, ascii_str(exc.public_message))
        http_exc = HTTPForbidden(exc.public_message)
    elif isinstance(exc, ParamCleaningError):
        LOGGER.debug(
            'Request parameters not valid: %r (public message: "%s")',
            exc, ascii_str(exc.public_message))
        http_exc = HTTPBadRequest(exc.public_message)
    elif isinstance(exc, TooMuchDataError):
        LOGGER.debug(
            'Too much data requested: %r (public message: "%s")',
            exc, ascii_str(exc.public_message))
        http_exc = HTTPForbidden(exc.public_message)
    else:
        if isinstance(exc, DataAPIError):
            if isinstance(exc, ResultCleaningError):
                LOGGER.error(
                    'Result cleaning error: %r (public message: "%s")',
                    exc, ascii_str(exc.public_message),
                    exc_info=True)
            else:
                LOGGER.error(
                    '%r (public message: "%s")',
                    exc, ascii_str(exc.public_message),
                    exc_info=True)
            public_message = (
                None
                if exc.public_message == DataAPIError.default_public_message
                else exc.public_message)
        else:
            LOGGER.error(
                'Non-HTTPException/DataAPIError exception: %r',
                exc,
                exc_info=True)
            public_message = None
        http_exc = HTTPServerError(public_message)
    return http_exc



#
# Basic classes

class DefaultRootFactory(object):

    """
    A Pyramid-URL-dispatch-related class.

    Typically, when using *n6sdk*, you do not need to bother about it.
    """

    __acl__ = [
        #(Allow, "group:admin", ALL_PERMISSIONS),
        (Allow, Authenticated, DUMMY_PERMISSION),
    ]

    def __init__(self, request):
        self.request = request



class StreamResponse(Response):

    """
    A *response* class used to serve streamed HTTP responses to client queries.

    Constructor args/kwargs:
        `data_generator`:
            An iterator/generator (being a data backend API's method
            call result) that yields subsequent result dictionaries.
        `renderer_name`:
            The name of the stream renderer to be used to render the
            response (e.g., ``'json'``).  The renderer should have been
            registered -- see the documentation of
            :func:`register_stream_renderer`.
        `request`:
            A Pyramid *request* object.
    """

    def __init__(self, data_generator, renderer_name, request):
        super(StreamResponse, self).__init__(conditional_response=True)
        renderer_factory = registered_stream_renderers[renderer_name]
        self.stream_renderer = renderer_factory(data_generator, request)
        self.content_type = self.stream_renderer.content_type
        app_iter = self.stream_renderer.generate_content()
        self.app_iter = app_iter



class AbstractViewBase(object):

    # to be specified as a keyword argument for concrete_view_class()
    resource_id = None

    @classmethod
    def validate_url_pattern(cls, url_pattern):
        """
        In subclasses this method may implement URL path pattern validation
        (just as a means of defensive programming).
        """

    @classmethod
    def concrete_view_class(cls, resource_id, config):
        """
        Create a concrete view subclass (for a particular REST API resource).

        This method is called automatically (by
        :meth:`HttpResource.configure_views`).

        Kwargs:
            `resource_id` (string):
                The identifier of the HTTP resource (as given as the
                `resource_id` argument for the :class:`HttpResource`
                constructor).
            `config` (mapping):
                The pyramid.config.Configurator instance used to
                configure the whole application (it is not used in
                :meth:`concrete_view_class` of the standard *n6sdk* view
                base classes but you may want to make use of it in your
                custom subclasses).

        Returns:
            A concrete subclass of the class.
        """
        _resource_id = resource_id

        class view_class(cls):
            resource_id = _resource_id

        view_class.__name__ = '_{0}_subclass_for_{1}'.format(
              cls.__name__,
              py_identifier_str(resource_id).lstrip('_'))

        return view_class

    @classmethod
    def get_default_http_methods(cls):
        """
        Get name(s) of the HTTP method(s) that are supported by default.

        This method should return a string or a sequence of strings.
        The method can be overridden or extended in subclasses.  The
        default implementation returns the ``'GET'`` string.
        """
        return 'GET'

    @attr_required('resource_id')
    def __init__(self, context, request):
        self.request = request

    def __call__(self):
        self.params = self.prepare_params()
        return self.make_response()

    def prepare_params(self):
        return dict(self.iter_deduplicated_params())

    def iter_deduplicated_params(self):
        chain_iterables = itertools.chain.from_iterable
        params = self.request.params
        for key in params:
            values = params.getall(key)
            assert values and all(isinstance(val, basestring) for val in values)
            yield key, list(chain_iterables(val.split(',') for val in values))

    def make_response(self):
        raise NotImplementedError



class DefaultStreamViewBase(AbstractViewBase):

    # to be specified as keyword arguments for concrete_view_class()
    renderers = None
    data_spec = None
    data_backend_api_method = None

    #: A callable that will be called when an exception
    #: (derived from :exc:`~exceptions.Exception`) occurs
    #: during response generation.  The callable must take one
    #: argument: an instance of :exc:`~exceptions.Exception`
    #: (or of its subclass).  The callable must return any
    #: exception object -- it can be either a new exception or
    #: the given exception object (possibly somewhat enriched).
    #:
    #: .. note::
    #:
    #:     By default, this class attribute is a static method whose
    #:     implementation is :func:`exc_to_http_exc` (for details, see
    #:     its source).
    adjust_exc = staticmethod(exc_to_http_exc)

    #: This flag can be set to :obj:`False` in a subclass to skip result
    #: records that could not be cleaned.  By default (when it is set to
    #: :obj:`True`), an error is raised if a result record could not be
    #: cleaned (then, typically, the final outcome is discontinuation of
    #: the -- already partially sent -- response).
    break_on_result_cleaning_error = True

    @classmethod
    def validate_url_pattern(cls, url_pattern):
        """
        Ensure that the given URL path pattern ends with the ``.{renderer}``
        placeholder.  Example value: ``"/some-url-path/incidents.{renderer}"``.
        """
        super(DefaultStreamViewBase, cls).validate_url_pattern(url_pattern)
        if not url_pattern.endswith('.{renderer}'):
            LOGGER.error("url_pattern must contain '.{renderer}' suffix")
            raise HTTPServerError

    @classmethod
    def concrete_view_class(cls, data_spec, data_backend_api_method, renderers,
                            **kwargs):
        """
        Create a concrete view subclass (for a particular REST API resource).

        This method is called automatically (by
        :meth:`HttpResource.configure_views`).

        Kwargs are the same as \
        for :meth:`AbstractViewBase.concrete_view_class`, plus:
            `data_spec` (instance of a :class:`.BaseDataSpec` subclass):
                The data specification object used to validate and
                adjust query parameters and output data.  (As given as
                the `data_spec` item of the `view_properties` argument
                for the :class:`HttpResource` costructor.)
            `data_backend_api_method` (string):
                The name of the data backend api method to be called by
                the view.  (As given as the `data_backend_api_method`
                item of the `view_properties` argument for the
                :class:`HttpResource` costructor.)
            `renderers` (string or iterable of strings):
                Names of available stream renderers (each of them should
                have been registered -- see the documentation of
                :func:`register_stream_renderer`).  (As given as the
                `renderers` item of the `view_properties` argument for
                the :class:`HttpResource` costructor.)  Example value:
                ``("json", "sjson")``.

        Returns:
            A concrete subclass of the class.

        Raises:
            :exc:`~exceptions.ValueError`:
                If any of the `renderers` has not been registered.
            :exc:`~exceptions.TypeError`:
                If `data_spec` is a class and not an instance of a
                data specification class.
        """

        if isinstance(data_spec, type) and issubclass(data_spec, BaseDataSpec):
            raise TypeError(
                'a BaseDataSpec *subclass* given but an *instance* '
                'of a BaseDataSpec subclass is needed')

        renderers = (
            frozenset([renderers]) if isinstance(renderers, basestring)
            else frozenset(renderers))
        illegal_renderers = renderers - registered_stream_renderers.viewkeys()
        if illegal_renderers:
            raise ValueError(
                'the following stream renderers have not been registered: ' +
                ', '.join(sorted(map(repr, illegal_renderers))))

        view_class = super(DefaultStreamViewBase,
                           cls).concrete_view_class(**kwargs)

        view_class.renderers = renderers
        view_class.data_spec = data_spec
        view_class.data_backend_api_method = data_backend_api_method

        return view_class


    @attr_required(
        'resource_id', 'renderers', 'data_spec',
        'data_backend_api_method', 'adjust_exc',
    )
    def __init__(self, context, request):
        super(DefaultStreamViewBase, self).__init__(context, request)
        self.renderer_name = self._get_renderer_name()

    def _get_renderer_name(self):
        renderer_name = self.request.matchdict.get('renderer', None)
        if renderer_name not in self.renderers:
            raise HTTPNotFound(u'{} - unknown format: "{}".'.format(
                self.request.path_info,
                renderer_name))
        return renderer_name

    def prepare_params(self):
        param_dict = super(DefaultStreamViewBase, self).prepare_params()
        clean_param_dict_kwargs = self.get_clean_param_dict_kwargs()
        return self.data_spec.clean_param_dict(
            param_dict,
            **clean_param_dict_kwargs)

    def make_response(self):
        data_generator = self.call_api()
        return StreamResponse(data_generator, self.renderer_name, self.request)

    def call_api(self):
        api_method_name = self.data_backend_api_method
        api_method = getattr(self.request.registry.data_backend_api, api_method_name)
        clean_result_dict = self.data_spec.clean_result_dict
        clean_result_dict_kwargs = self.get_clean_result_dict_kwargs()
        try:
            for result_dict in self.call_api_method(api_method):
                try:
                    cleaned_result = clean_result_dict(
                        result_dict,
                        **clean_result_dict_kwargs)
                except ResultCleaningError as exc:
                    if self.break_on_result_cleaning_error:
                        raise
                    else:
                        LOGGER.error(
                            'Some results not yielded due '
                            'to the cleaning error: %r', exc)
                else:
                    if cleaned_result is not None:
                        yield cleaned_result
        except Exception as exc:
            raise self.adjust_exc(exc)

    def call_api_method(self, api_method):
        return api_method(
            self.request.auth_data,
            self.params,
            **self.get_extra_api_kwargs())

    def get_clean_param_dict_kwargs(self):
        return {}

    def get_clean_result_dict_kwargs(self):
        return {}

    def get_extra_api_kwargs(self):
        return {}



class HttpResource(object):

    """
    A class of containers of REST API resource properties.

    Required constructor arguments (all of them are keyword-only!):
        `resource_id` (string):
            The identifier of the HTTP resource.
            It will be used as the Pyramid route name.
        `url_pattern` (string):
            A URL path pattern.  Example value:
            ``"/some-url-path/incidents.{renderer}"``.

    Optional constructor arguments (all of them are keyword-only!):
        `view_base` (:class:`DefaultStreamViewBase` subclass):
            The base class of the view; default:
            :class:`DefaultStreamViewBase`.
        `view_properties` (:class:`dict`):
            A dictionary of keyword arguments that will be automatically
            passed in -- in addition to `resource_id` (see above) and
            `config` (the pyramid.config.Configurator instance used to
            configure the application) -- to the
            :meth:`concrete_view_class` class method of the `view_base`
            class; the set of obligatory keys depends on the `view_base`
            class -- for example, for :class:`DefaultStreamViewBase`
            (the default) they are: ``data_spec``,
            ``data_backend_api_method`` and ``renderers`` (see the
            documentation of
            :meth:`DefaultStreamViewBase.concrete_view_class` for
            details).  Default value: empty :class:`dict` (note,
            however, that it must not be empty for the default
            `view_base` class).
        `http_methods` (string, or iterable of strings, or ``None``):
            Name(s) of HTTP method(s) enabled for the resource; if
            ``None`` then the name(s) will be determined by calling
            the :meth:`~AbstractViewBase.get_default_http_methods`
            of the concrete view class; default: ``None``.
        `parmission`:
            An object representing a Pyramid permission; default:
            string ``"dummy_permission"``.

    .. seealso::

       See:

       * :meth:`DefaultStreamViewBase.concrete_view_class`,
       * :class:`ConfigHelper`.
    """

    def __init__(self, resource_id,
                 url_pattern,
                 view_base=DefaultStreamViewBase,
                 view_properties=None,
                 http_methods=None,
                 permission=DUMMY_PERMISSION,
                 **kwargs):
        self.resource_id = resource_id
        self.url_pattern = url_pattern
        self.view_properties = (
            {} if view_properties is None
            else view_properties)
        self.view_base = view_base
        self.http_methods = http_methods
        self.permission = permission
        return super(HttpResource, self).__init__(**kwargs)

    def configure_views(self, config):
        """
        Automatically called by :meth:`ConfigHelper.make_wsgi_app` or
        :meth:`ConfigHelper.complete`.
        """
        route_name = self.resource_id
        view_class = self.view_base.concrete_view_class(
            resource_id=self.resource_id,
            config=config,
            **self.view_properties)
        view_class.validate_url_pattern(self.url_pattern)
        http_methods = (
            view_class.get_default_http_methods() if self.http_methods is None
            else self.http_methods)
        actual_http_methods = (
            (http_methods,) if isinstance(http_methods, basestring)
            else tuple(http_methods))
        config.add_route(route_name, self.url_pattern)
        config.add_view(
            view=view_class,
            route_name=route_name,
            request_method=actual_http_methods,
            permission=self.permission)



#
# Application startup/configuration

class ConfigHelper(object):

    """
    Class of an object that automatizes necessary WSGI app setup steps.

    Typical usage in your Pyramid application's ``__init__.py``:

    .. code-block:: python

        RESOURCES = <list of HttpResource instances>

        def main(global_config, **settings):
            helper = ConfigHelper(
                settings=settings,
                data_backend_api_class=MyDataBackendAPI,
                authentication_policy=MyCustomAuthenticationPolicy(settings),
                resources=RESOURCES,
            )
            ...  # <- here you can call any methods of the helper.config object
            ...  #    which is a pyramid.config.Configurator instance
            return helper.make_wsgi_app()

    Note: all constructor arguments should be specified as keyword arguments.
    """

    #: (overridable attribute)
    default_static_view_config = None

    #: (overridable attribute)
    default_root_factory = DefaultRootFactory

    def __init__(self,
                 settings,
                 data_backend_api_class,
                 authentication_policy,
                 resources,
                 static_view_config=None,
                 root_factory=None,
                 **rest_configurator_kwargs):
        self.settings = self.prepare_settings(settings)
        self.data_backend_api_class = data_backend_api_class
        self.authentication_policy = authentication_policy
        self.resources = resources
        if static_view_config is None:
            static_view_config = self.default_static_view_config
        self.static_view_config = static_view_config
        if root_factory is None:
            root_factory = self.default_root_factory
        self.root_factory = root_factory
        self.rest_configurator_kwargs = rest_configurator_kwargs
        self.config = self.prepare_config(self.make_config())
        self._completed = False

    def make_wsgi_app(self):
        if not self._completed:
            self.complete()
        return self.config.make_wsgi_app()

    # overridable/extendable methods (hooks):

    def prepare_settings(self, settings):
        return dict(settings)

    def make_config(self):
        return Configurator(
              settings=self.settings,
              authentication_policy=self.authentication_policy,
              root_factory=self.root_factory,
              **self.rest_configurator_kwargs)

    def prepare_config(self, config):
        config.registry.data_backend_api = self.make_data_backend_api()
        config.add_request_method(self.authentication_policy.get_auth_data,
                                  'auth_data', reify=True)
        return config

    def make_data_backend_api(self):
        return self.data_backend_api_class(settings=self.settings)

    def complete(self):
        self.config.add_view(view=self.exception_view, context=Exception)
        self.config.add_view(view=self.exception_view, context=HTTPException)
        for res in self.resources:
            res.configure_views(self.config)
        if self.static_view_config:
            self.config.add_static_view(**self.static_view_config)
        self._completed = True

    @classmethod
    def exception_view(cls, exc, request):
        http_exc = exc_to_http_exc(exc)
        assert isinstance(http_exc, HTTPException)
        # force a plain-text (non-HTML) response
        # if http_exc.body has not been set yet
        environ_copy = request.environ.copy()
        environ_copy.pop('HTTP_ACCEPT', None)
        http_exc.prepare(environ_copy)
        return http_exc



#
# Stream renderer registration

registered_stream_renderers = {}


def register_stream_renderer(name, renderer_factory=None, allow_replace=False):
    """
    Register a stream renderer factory under the specified name.

    Args:
        `name` (:class:`str`):
            The name of the renderer (such as ``'json'``, ``'csv'`` or
            whatever...).
        `renderer_factory` (callable object):
            A callable that takes two *positional* arguments:
            `data_generator` and `request` (see the documentation of
            :class:`StreamResponse` for the description of them),
            and returns a *stream renderer* (see the
            :mod:`n6sdk.pyramid_commons.renderers` module).
        `allow_replace` (:class:`bool`; default: :obj:`False`):
            If set to true you can register `renderer_factory` under
            `name` *replacing* any renderer factory that has already
            been registered under that `name` (if no renderer factory
            has been registered under `name` the `allow_replace` flag
            is irrelevant).

    Raises:
        :exc:`~exceptions.RuntimeError`:
            If some renderer factory has already been registered under
            `name` and `allow_replace` is *not* true.

    Basic usage:

    .. code-block:: python

        register_stream_renderer(<renderer name>, <renderer factory>)

    or:

    .. code-block:: python

        @register_stream_renderer(<renderer name>)
        def make_my_renderer(data_generator, request):
            ...

    or:

    .. code-block:: python

        @register_stream_renderer(<renderer name>)
        class MyRenderer(...):
            def __init__(self, data_generator, request):
                ...
            ...
    """
    if renderer_factory is None:
        return functools.partial(
            register_stream_renderer,
            name, allow_replace=allow_replace)
    if name in registered_stream_renderers and not allow_replace:
        raise RuntimeError('renderer {0!r} already registered'.format(name))
    registered_stream_renderers[name] = renderer_factory
    return renderer_factory


register_stream_renderer('json', standard_stream_renderers.StreamRenderer_json)
register_stream_renderer('sjson', standard_stream_renderers.StreamRenderer_sjson)



#
# Authentication policies

class BaseAuthenticationPolicy(object):

    """
    The base class for authentication policy classes.

    See: http://docs.pylonsproject.org/projects/pyramid/en/\
latest/narr/security.html#creating-your-own-authentication-policy
    """

    def unauthenticated_userid(self, request):
        raise NotImplementedError(
            'abstract method unauthenticated_userid() not implemented')

    @staticmethod
    def get_auth_data(request):
        """
        Determines the value that will be set as the :attr:`auth_data` of
        the `request` object.

        This function is used as a `request` method that provides the
        :attr:`auth_data` `request` attribute (see:
        :meth:`ConfigHelper.prepare_config` above), which means that
        this function is called *after* :meth:`unauthenticated_userid`
        and *before* :meth:`authenticated_userid`.

        It should be implemented as a *static method*.

        Concrete implementation of this method will probably make use
        of the :attr:`unauthenticated_userid` attribute of `request`
        (in older versions of Pyramid the
        :func:`unauthenticated_userid` function from the
        :mod:`pyramid.security` module was used instead of that
        attribute).

        Returns:
            Authentication data (in an application-specific format).
            The default implementation returns :obj:`None`.
        """
        return None

    def authenticated_userid(self, request):
        """
        Concrete implementation of this method will probably make use of
        the :attr:`auth_data` attribute of `request`.  (The value of
        that attribute is produced by the :meth:`get_auth_data`
        method.)
        """
        return None

    def effective_principals(self, request):
        effective_principals = [Everyone]
        if request.auth_data is not None:
            effective_principals.append(Authenticated)
        return effective_principals

    def forget(self, request):
        """
        Can be left dummy if users are recognized externally, e.g. by SSL cert.
        """
        return []

    def remember(self, request, principal, **kw):
        """
        Can be left dummy if users are recognized externally, e.g. by SSL cert.
        """
        return []



class AnonymousAuthenticationPolicy(BaseAuthenticationPolicy):

    """
    A dummy authentication policy: authenticates everybody (as
    ``"anonymous"``).

    It sets, for all requests, the *user id* and the *authentication
    data* to the string ``"anonymous"``.
    """

    def unauthenticated_userid(self, request):
        return "anonymous"

    @staticmethod
    def get_auth_data(request):
        return request.unauthenticated_userid   # just string "anonymous"

    def authenticated_userid(self, request):
        return request.auth_data                # just string "anonymous"

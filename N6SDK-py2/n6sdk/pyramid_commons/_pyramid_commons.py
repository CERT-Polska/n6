# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

from builtins import map                                                         #3--
import datetime
import functools
import itertools
import logging
import re
from json import dumps as json_dumps

from pyramid.config import Configurator
from pyramid.httpexceptions import (
    HTTPException,
    HTTPBadRequest,
    HTTPForbidden,
    HTTPNotFound,
    HTTPInternalServerError,
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
from n6sdk.datetime_helpers import datetime_utc_normalize
from n6sdk.encoding_helpers import (
    ascii_str,
    ascii_py_identifier_str,
)
from n6sdk.exceptions import (
    AuthorizationError,
    DataAPIError,
    DataFromClientError,
    DataLookupError,
    ParamCleaningError,
    ResultCleaningError,
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
        # (Already a Pyramid HTTP exception
        # -> let's log it and keep intact.)
        code = getattr(exc, 'code', None)
        if isinstance(code, (int, long)) and 200 <= code < 500:                #3: `long`--
            # HTTP >=200 and <500
            LOGGER.debug(
                'HTTPException: %r ("%s", code: %s)',
                exc, ascii_str(exc), code)
        else:
            # HTTP >=500 or unexpected/undefined
            LOGGER.error(
                'HTTPException: %r ("%s", code: %r)',
                exc, ascii_str(exc), code,
                exc_info=True)
        http_exc = exc
    elif isinstance(exc, DataFromClientError):
        # HTTP 400
        if isinstance(exc, ParamCleaningError):
            LOGGER.debug(
                'Request parameters not valid: %r (public message: "%s")',
                exc, ascii_str(exc.public_message))
        else:
            LOGGER.debug(
                'Request-content-related error: %r (public message: "%s")',
                exc, ascii_str(exc.public_message))
        http_exc = HTTPBadRequest(exc.public_message)
    elif isinstance(exc, AuthorizationError):
        # HTTP 403
        LOGGER.debug(
            'Authorization denied: %r (public message: "%s")',
            exc, ascii_str(exc.public_message))
        http_exc = HTTPForbidden(exc.public_message)
    elif isinstance(exc, DataLookupError):
        # HTTP 404
        LOGGER.debug(
            'Could not find the requested stuff: %r (public message: "%s")',
            exc, ascii_str(exc.public_message))
        http_exc = HTTPNotFound(exc.public_message)
    else:
        # HTTP 500
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
        http_exc = HTTPInternalServerError(public_message)
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

    # Must be specified as a keyword argument to concrete_view_class().
    resource_id = None

    # In subclasses (or their instances) the following attribute can be
    # set to True -- then, for the particular view, only params from the
    # request body will be considered, and params from the query string
    # will be ignored.
    params_only_from_body = False

    @classmethod
    def validate_url_pattern(cls, url_pattern):
        """
        In subclasses this method may implement URL path pattern validation
        (just as a means of defensive programming).
        """

    @classmethod
    def concrete_view_class(cls, resource_id, pyramid_configurator):
        """
        Create a concrete view subclass (for a particular REST API resource).

        This method is called automatically (by
        :meth:`HttpResource.configure_views`).

        Kwargs:
            `resource_id` (str):
                The identifier of the HTTP resource (as given as the
                `resource_id` argument for the :class:`HttpResource`
                constructor).
            `pyramid_configurator` (mapping):
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
              ascii_py_identifier_str(resource_id).lstrip('_'))
        view_class.__qualname__ = '.'.join(getattr(view_class, '__qualname__', '').split('.')[:-1]   #3: replace getattr with simple attr access
                                           + [view_class.__name__])

        return view_class

    @classmethod
    def get_default_http_methods(cls):
        """
        Get name(s) of the HTTP method(s) that are supported by default.

        This method should return a str or a sequence of str objects.
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
        params = self.get_params_from_request()
        for key in params:
            if not isinstance(key, (str, unicode)):                                #3: `unicode`--
                raise AssertionError('{!r} is not a str'.format(key))
            values = params.getall(key)
            if not (values
                    and isinstance(values, list)
                    and all(isinstance(val, (str, unicode)) for val in values)):   #3: `unicode`--
                raise AssertionError(
                    '{}={!r}, *not* being a non-empty list '
                    'of str!'.format(ascii_str(key), values))
            yield key, self.preprocess_param_values(key, values)

    def get_params_from_request(self):
        if self.params_only_from_body:
            return self.request.POST
        else:
            return self.request.params

    def preprocess_param_values(self, key, values):
        chain_iterables = itertools.chain.from_iterable
        return list(chain_iterables(self.iter_values_from_param_value(key, val)
                    for val in values))

    def iter_values_from_param_value(self, key, value):
        yield value

    def make_response(self):
        raise NotImplementedError

    #
    # Utility methods (can be useful in some subclasses)

    def json_response(self,
                      json,
                      content_type='application/json',
                      headerlist=None,
                      **response_kwargs):
        self.__ensure_no_unwanted_kwargs(response_kwargs, ['body', 'app_iter', 'json_body'])
        self.__ensure_no_content_type_in_headerlist(headerlist)
        data = self.prepare_jsonable_data(json)
        body = json_dumps(data)
        return self.__make_response(body, content_type, headerlist, **response_kwargs)

    def cleaned_json_response(self,
                              json,
                              data_spec,
                              **json_response_kwargs):
        cleaned_json = data_spec.clean_result_dict(json)
        return self.json_response(cleaned_json, **json_response_kwargs)

    def text_response(self,
                      body,
                      content_type='text/plain; charset=utf-8',
                      headerlist=None,
                      **response_kwargs):
        self.__ensure_no_unwanted_kwargs(response_kwargs, ['app_iter', 'json', 'json_body'])
        self.__ensure_no_content_type_in_headerlist(headerlist)
        return self.__make_response(body, content_type, headerlist, **response_kwargs)

    #
    # Auxiliary hooks (can be extended/overridden in some subclasses)

    def prepare_jsonable_data(self, data):
        jsonable_data = self.__with_times_and_datetimes_converted_to_strings(data)
        return jsonable_data

    #
    # Internal helpers

    # * `Response`-constructor-arguments consistency checks:

    def __ensure_no_unwanted_kwargs(self, response_kwargs, unwanted_kwarg_names):
        for name in unwanted_kwarg_names:
            if response_kwargs.get(name) is not None:
                raise TypeError('unexpected keyword argument: {}'.format(name))

    def __ensure_no_content_type_in_headerlist(self, headerlist):
        # (just for clarity/coherence of the interface)
        if headerlist:
            found_content_type_headers = [k for k, _ in headerlist
                                          if k.lower() == 'content-type']
            if found_content_type_headers:
                raise ValueError(
                    'the `headerlist` argument contains header(s) '
                    'that should not be placed in it: {} (use the '
                    '`content_type` argument instead)'.format(
                        ', '.join(map(repr, found_content_type_headers))))

    # * Making the actual `Response` instance:

    def __make_response(self,
                        body,
                        content_type,
                        headerlist=None,
                        **response_kwargs):
        charset = response_kwargs.pop('charset', None)
        content_type, charset = self.__get_complete_content_type_and_charset(content_type, charset)
        body = self.__get_encoded_body(body, content_type, charset)
        # Let's make the behavior of the `pyramid.response.Response`
        # constructor consistent regardless of the presence of the
        # `headerlist` argument.
        if headerlist is None:
            headerlist = []
        # Note: when calling the `Response` constructor we do not pass
        # `content_type` as the keyword argument because it is ignored
        # when a non-None 'headerlist' argument is specified...
        response = Response(
            body=body,
            headerlist=headerlist,
            **response_kwargs)
        # ...so, instead of that, we set the `content_type` property on
        # the ready `Response` instance.
        response.content_type = content_type
        return response

    def __get_complete_content_type_and_charset(self, content_type, charset):
        content_type, charset = self.__get_disjoint_content_type_and_charset(content_type, charset)
        if charset:
            content_type = '{}; charset={}'.format(content_type, charset)
        assert self.__WITH_CHARSET_REGEX.search(content_type) or not charset
        return content_type, charset

    def __get_disjoint_content_type_and_charset(self, content_type, charset):
        charset_match = self.__WITH_CHARSET_REGEX.search(content_type)
        if charset_match:
            if charset:
                # (just for clarity/coherence of the interface)
                raise ValueError(
                    "the `content_type` argument ({!r}) should not include "
                    "the 'charset=...' part when the `charset` argument "
                    "({!r}) is given".format(content_type, charset))
            charset = charset_match.group('charset').rstrip(' \t')
            before_charset = content_type[:charset_match.start()]
            after_charset = content_type[charset_match.end():]
            if after_charset or '\\' in charset:
                # To support such cases properly we would need more
                # complicated parsing of `content_type` (with its
                # `charset` part). In practice, we do not need that,
                # so let's just raise the following error (instead of
                # producing possibly wrong results silently).
                raise NotImplementedError(
                    "the `content_type` argument ({!r}) contains "
                    "some stuff after the 'charset=...' part, or "
                    "that 'charset=...' part contains some backslash "
                    "character(s) - unfortunately we do not support "
                    "such cases".format(content_type))
            content_type = before_charset.rstrip(' \t')
        assert not self.__WITH_CHARSET_REGEX.search(content_type)
        return content_type, charset

    __WITH_CHARSET_REGEX = re.compile(
        # (compatible with the Pyramid's internal way of charset   # <- TODO analyze: is necessary?
        # extraction; that's why here it is without re.ASCII...)
        r';\s*charset=(?P<charset>[^;]*)',
        re.IGNORECASE)

    def __get_encoded_body(self, body, content_type, charset):
        str = unicode                                                          #3--
        if isinstance(body, str):
            if charset:
                body_encoding = charset.strip('"')
            elif self.__JSON_CONTENT_TYPE_REGEX.search(content_type):
                body_encoding = 'utf-8'
            else:
                raise ValueError(
                    'the `body` argument is a Unicode string but the '
                    'response charset is not specified and cannot be '
                    'implied from the {!r} content-type; to prevent '
                    'this error you need to provide an already encoded '
                    'body or specify the charset'.format(content_type))
            body = body.encode(body_encoding)
        assert not isinstance(body, str)
        return body

    __JSON_CONTENT_TYPE_REGEX = re.compile(
        r'\A'
        r'application/json'
        r'[ \t]*'
        r'(?:'
        r'\Z'
        r'|'
        r';)',
        re.IGNORECASE)                                                         #3: add `|re.ASCII`

    # * JSON-serializable data preparation:

    def __with_times_and_datetimes_converted_to_strings(self, data):
        if isinstance(data, dict):
            return {k: self.__with_times_and_datetimes_converted_to_strings(v)
                    for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return list(map(self.__with_times_and_datetimes_converted_to_strings, data))
        if isinstance(data, datetime.datetime):
            return self._datetime_to_str(data)
        if isinstance(data, datetime.time):
            return self._time_do_str(data)
        return data

    def _datetime_to_str(self, dt):
        return datetime_utc_normalize(dt).isoformat() + "Z"

    def _time_do_str(self, t):
        if t.tzinfo is not None:
            raise ValueError(
                'automatic to-str conversion of time objects with a '
                'non-None `tzinfo` attribute is not supported (got: '
                '{!r})'.format(t))
        s = t.isoformat()
        assert self.__TIME_ISOFORMAT_REGEX.search(s)              # 'HH:MM:SS' or 'HH.MM.SS.mmmmmm'
        if s.endswith(':00'):
            assert self.__TIME_ISOFORMAT_00_SEC_REGEX.search(s)   # 'HH:MM:00'
            s = s[:-3]
            assert self.__TIME_WITH_TRIMMED_SEC_REGEX.search(s)   # 'HH:MM'
        return s

    # (just for assertions; see the `_time_do_str()` method defined above)
    __TIME_ISOFORMAT_REGEX = re.compile('\A[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{6})?\Z', re.ASCII)
    __TIME_ISOFORMAT_00_SEC_REGEX = re.compile('\A[0-9]{2}:[0-9]{2}:0{2}\Z', re.ASCII)
    __TIME_WITH_TRIMMED_SEC_REGEX = re.compile('\A[0-9]{2}:[0-9]{2}\Z', re.ASCII)


class CommaSeparatedParamValuesViewMixin(object):

    # In a subclass it can be set to a container (e.g., a `frozenset`)
    # of param names (or to a property that provides such a container)
    # -- then the operation of *separation-by-comma* will be performed
    # only for the specified params (instead of performing it for all
    # params).
    comma_separated_only_for = None

    def iter_values_from_param_value(self, key, value):
        sep_only_for = self.comma_separated_only_for
        assert isinstance(self, AbstractViewBase)
        assert isinstance(key, (str, unicode))                                 #3: `unicode`--
        assert isinstance(value, (str, unicode))                               #3: `unicode`--
        iter_values = super(CommaSeparatedParamValuesViewMixin,
                            self).iter_values_from_param_value(key, value)
        if sep_only_for is None or (key in sep_only_for):
            for val in iter_values:
                assert isinstance(val, (str, unicode))                         #3: `unicode`--
                for val_part in val.split(','):
                    yield val_part
        else:
            for val in iter_values:
                assert isinstance(val, (str, unicode))                         #3: `unicode`--
                yield val


class OmittingEmptyParamsViewMixin(object):

    def iter_deduplicated_params(self):
        assert isinstance(self, AbstractViewBase)
        params = super(OmittingEmptyParamsViewMixin, self).iter_deduplicated_params()
        for param_name, values in params:
            if not (isinstance(values, list)
                    and all(isinstance(val, (str, unicode)) for val in values)):   #3: `unicode`--
                raise TypeError('{}={!r}, not being a list of str'
                                .format(ascii_str(param_name), values))
            nonempty_values = list(filter(None, values))
            if nonempty_values:
                yield param_name, nonempty_values


class SingleParamValuesViewMixin(object):

    def iter_deduplicated_params(self):
        assert isinstance(self, AbstractViewBase)
        params = super(SingleParamValuesViewMixin, self).iter_deduplicated_params()
        for param_name, values in params:
            if len(values) != 1:
                raise ParamCleaningError(public_message=(
                    'Received a request with more than or less than exactly one '
                    'value of the parameter "{}".'.format(ascii_str(param_name))))
            yield (param_name,
                   values[0])   # <- here: the value itself (not a list of values)


class PreparingNoParamsViewMixin(object):

    def prepare_params(self):
        return {}


class DefaultStreamViewBase(CommaSeparatedParamValuesViewMixin, AbstractViewBase):

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
            raise HTTPInternalServerError

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
            `data_backend_api_method` (str):
                The name of the data backend api method to be called by
                the view.  (As given as the `data_backend_api_method`
                item of the `view_properties` argument for the
                :class:`HttpResource` costructor.)
            `renderers` (str or iterable of str):
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
            frozenset([renderers]) if isinstance(renderers, (str, unicode))      #3: `unicode`--
            else frozenset(renderers))
        illegal_renderers = renderers - registered_stream_renderers.viewkeys()   #3
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
            result_iterable = self.call_api_method(api_method)
            try:
                for result_dict in result_iterable:
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
            finally:
                close = getattr(result_iterable, 'close', None)
                if close is not None:
                    # Apparently, `result_iterable` is an iterable
                    # object which is closable (e.g., a generator).
                    close()
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
        `resource_id` (str):
            The identifier of the HTTP resource.
            It will be used as the Pyramid route name.
        `url_pattern` (str):
            A URL path pattern.  Example value:
            ``"/some-url-path/incidents.{renderer}"``.

    Optional constructor arguments (all of them are keyword-only!):
        `view_base` (:class:`DefaultStreamViewBase` subclass):
            The base class of the view; default:
            :class:`DefaultStreamViewBase`.
        `view_properties` (:class:`dict`):
            A dictionary of keyword arguments that will be automatically
            passed in -- in addition to `resource_id` (see above) and
            `pyramid_configurator` (the pyramid.config.Configurator
            instance used to configure the application) -- to the
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
        `http_methods` (str, or iterable of str, or ``None``):
            Name(s) of HTTP method(s) enabled for the resource; if
            ``None`` then the name(s) will be determined by calling
            the :meth:`~AbstractViewBase.get_default_http_methods`
            of the concrete view class; default: ``None``.
        `parmission`:
            An object representing a Pyramid permission; default:
            the ``"dummy_permission"`` string.

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
                 http_cache=0,
                 permission=DUMMY_PERMISSION,
                 **kwargs):
        self.resource_id = resource_id
        self.url_pattern = url_pattern
        self.view_properties = (
            {} if view_properties is None
            else view_properties)
        self.view_base = view_base
        self.http_methods = http_methods
        self.http_cache = http_cache
        self.permission = permission
        return super(HttpResource, self).__init__(**kwargs)

    def configure_views(self, pyramid_configurator):
        """
        Automatically called by :meth:`ConfigHelper.make_wsgi_app` or
        :meth:`ConfigHelper.complete`.
        """
        route_name = self.resource_id
        view_class = self.view_base.concrete_view_class(
            resource_id=self.resource_id,
            pyramid_configurator=pyramid_configurator,
            **self.view_properties)
        view_class.validate_url_pattern(self.url_pattern)
        http_methods = (
            view_class.get_default_http_methods() if self.http_methods is None
            else self.http_methods)
        actual_http_methods = (
            (http_methods,) if isinstance(http_methods, (str, unicode))          #3: `unicode`--
            else tuple(http_methods))
        pyramid_configurator.add_route(route_name, self.url_pattern)
        pyramid_configurator.add_view(
            view=view_class,
            route_name=route_name,
            request_method=actual_http_methods,
            http_cache=self.http_cache,
            permission=self.permission)



#
# Application startup/configuration

class BasicConfigHelper(object):

    """
    The class provides methods to help with necessary setup steps
    for a basic WSGI app.

    This class does not yet implement any application-specific
    components to be added to application's registry, like for
    example an authentication policy object. Several attributes
    and methods are therefore overridable/extendable.

    Typical usage in your Pyramid application's ``__init__.py``:

    .. code-block:: python

        RESOURCES = <list of HttpResource instances>

        def main(global_config, **settings):
            helper = <some subclass of BasicConfigHelper>(
                settings=settings,
                resources=RESOURCES,
            )
            ...  # <- Here you can call any methods of the
            ...  #    helper.pyramid_configurator object which
            ...  #    is a pyramid.config.Configurator instance.
            return helper.make_wsgi_app()

    Note: all constructor arguments should be specified as keyword arguments.
    """

    #: (overridable attribute)
    default_static_view_config = None

    #: (overridable attribute)
    default_root_factory = DefaultRootFactory

    def __init__(self,
                 settings,
                 resources,
                 static_view_config=None,
                 root_factory=None,
                 **rest_configurator_kwargs):
        self.settings = self.prepare_settings(settings)
        self.resources = resources
        if static_view_config is None:
            static_view_config = self.default_static_view_config
        self.static_view_config = static_view_config
        if root_factory is None:
            root_factory = self.default_root_factory
        self.root_factory = root_factory
        self.rest_configurator_kwargs = rest_configurator_kwargs
        self.pyramid_configurator = self.prepare_pyramid_configurator(
            self.make_pyramid_configurator())
        self._completed = False

    def make_wsgi_app(self):
        if not self._completed:
            self.complete()
        return self.pyramid_configurator.make_wsgi_app()

    # overridable/extendable methods (hooks):

    def prepare_settings(self, settings):
        return dict(settings)

    def make_pyramid_configurator(self):
        return Configurator(
              settings=self.settings,
              root_factory=self.root_factory,
              **self.rest_configurator_kwargs)

    def prepare_pyramid_configurator(self, pyramid_configurator):
        return pyramid_configurator

    def complete(self):
        self.pyramid_configurator.add_view(view=self.exception_view, context=Exception)
        self.pyramid_configurator.add_view(view=self.exception_view, context=HTTPException)
        for res in self.resources:
            res.configure_views(self.pyramid_configurator)
        if self.static_view_config:
            self.pyramid_configurator.add_static_view(**self.static_view_config)
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


class ConfigHelper(BasicConfigHelper):

    """
    The class provides methods to help with necessary setup steps
    for a WSGI app.

    This subclass of the `BasicConfigHelper` additionally registers
    an authentication policy and a "data backend API" class, which
    is then used by specific apps.

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
            ...  # <- Here you can call any methods of the
            ...  #    helper.pyramid_configurator object which
            ...  #    is a pyramid.config.Configurator instance.
            return helper.make_wsgi_app()

    Note: all constructor arguments should be specified as keyword arguments.
    """

    def __init__(self,
                 settings,
                 resources,
                 data_backend_api_class,
                 authentication_policy,
                 **rest_init_kwargs):
        self.data_backend_api_class = data_backend_api_class
        self.authentication_policy = authentication_policy
        super(ConfigHelper, self).__init__(settings=settings,
                                           resources=resources,
                                           authentication_policy=authentication_policy,
                                           **rest_init_kwargs)

    def prepare_pyramid_configurator(self, pyramid_configurator):
        pyramid_configurator.registry.data_backend_api = self.make_data_backend_api()
        pyramid_configurator.add_request_method(self.authentication_policy.get_auth_data,
                                                'auth_data', reify=True)
        return pyramid_configurator

    def make_data_backend_api(self):
        return self.data_backend_api_class(settings=self.settings)



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
        :meth:`ConfigHelper.prepare_pyramid_configurator` above), which means
        that this function is called *after* :meth:`unauthenticated_userid`
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

    def remember(self, request, userid, **kw):
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

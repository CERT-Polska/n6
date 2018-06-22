# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import json
from collections import MutableSequence

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPForbidden,
    HTTPGone,
    HTTPNotFound,
    HTTPServerError,
)
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.response import Response
from pyramid.security import (
    Allow,
    Authenticated,
    Everyone,
)
from pyramid.tweens import EXCVIEW

import n6lib.config
from n6lib.auth_api import (
    RESOURCE_ID_TO_ACCESS_ZONE,
    AuthAPIUnauthenticatedError,
)
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import (
    make_condensed_debug_msg,
    make_hex_id,
)
from n6lib.log_helpers import get_logger
from n6lib.pyramid_commons.renderers import (
    # by importing that submodule we ensure that
    # these stream renderers are registered
    # (see the assertions at the end of the current module)
    StreamRenderer_csv,
    StreamRenderer_iodef,
    SnortDNSRenderer,
    SnortHTTPRenderer,
    SnortIPRenderer,
    SnortIPBlacklistRenderer,
    SuricataDNSRenderer,
    SuricataHTTPRenderer,
    SuricataIPRenderer,
    SuricatatIPBlacklistRenderer,
)
from n6lib.transaction_helpers import transact
from n6sdk.pyramid_commons import (
    AbstractViewBase,
    BaseAuthenticationPolicy,
    ConfigHelper,
    DefaultStreamViewBase,
    registered_stream_renderers,
)
try:
    from n6lib.manage_api import ManageAPIClientError
except ImportError:
    _MANAGE_API = False
else:
    _MANAGE_API = True


LOGGER = get_logger(__name__)


#
# Debugging info helpers

def log_debug_info_on_http_exc(http_exc):
    code = getattr(http_exc, 'code', None)
    if not isinstance(code, (int, long)) or not 200 <= code < 500:
        LOGGER.error(
            'Condensed debug info related to %r:\n%s',
            http_exc, make_condensed_debug_msg())


#
# Basic helpers

# SSL_CLIENT_S_DN_O is assumed to be organization id
SSL_ORG_ID_FIELD = 'SSL_CLIENT_S_DN_O'
# SSL_CLIENT_S_DN_CN is assumed to be user id
SSL_USER_ID_FIELD = 'SSL_CLIENT_S_DN_CN'


def get_certificate_credentials(request):
    org_id = request.environ.get(SSL_ORG_ID_FIELD)
    user_id = request.environ.get(SSL_USER_ID_FIELD)
    if org_id is not None and user_id is not None:
        if ',' in org_id:
            LOGGER.warning('Comma in org_id %r.', org_id)
            return None, None
        if ',' in user_id:
            LOGGER.warning('Comma in user_id %r.', user_id)
            return None, None
    return org_id, user_id


#
# Basic classes

class N6PortalRootFactory(object):

    """
    A simple Root Factory for a website using URL dispatch,
    providing a simple access control list.
    """

    __acl__ = [
        (Allow, Everyone, 'all'),
        (Allow, Authenticated, 'auth'),
    ]

    def __init__(self, request):
        self.request = request


class N6DefaultStreamViewBase(DefaultStreamViewBase):

    IODEF_ITEM_NUMBER_LIMIT = 1000

    break_on_result_cleaning_error = False

    def __init__(self, *args, **kwargs):
        super(N6DefaultStreamViewBase, self).__init__(*args, **kwargs)
        self.auth_api = self.request.registry.auth_api
        self._set_access_attributes()

    def _set_access_attributes(self):
        assert self.resource_id in RESOURCE_ID_TO_ACCESS_ZONE
        access_info = self.auth_api.get_access_info(self.request.auth_data)
        if self._is_access_forbidden(access_info):
            raise HTTPForbidden(u'Access not allowed.')
        self.access_zone_conditions = access_info['access_zone_conditions']
        self.full_access = access_info['rest_api_full_access']
        self.res_limits = access_info['rest_api_resource_limits'][self.resource_id]

    def _is_access_forbidden(self, access_info):
        access_zone = RESOURCE_ID_TO_ACCESS_ZONE[self.resource_id]
        return (access_info is None or
                self.resource_id not in access_info['rest_api_resource_limits'] or
                not access_info['access_zone_conditions'].get(access_zone))

    def get_clean_param_dict_kwargs(self):
        return dict(
            auth_api=self.auth_api,
            full_access=self.full_access,
            res_limits=self.res_limits,
        )

    def get_clean_result_dict_kwargs(self):
        # in the `params` dict, the value for the 'opt.primary' key, if
        # present, must be a 1-element list containing the cleaned value
        # of the `opt.primary` flag: True or False (the `opt.primary` data
        # spec field has single_param=True, and its type is FlagField)
        [opt_primary] = self.params.get('opt.primary', [False])
        return dict(
            auth_api=self.auth_api,
            full_access=self.full_access,
            opt_primary=opt_primary,
        )

    def get_extra_api_kwargs(self):
        return dict(
            data_spec=self.data_spec,
            access_zone_conditions=self.access_zone_conditions,
            res_limits=self.res_limits,
            item_number_limit=(
                self.IODEF_ITEM_NUMBER_LIMIT if self.renderer_name == 'iodef'
                else None
            ),
        )

    @classmethod
    def adjust_exc(cls, exc):
        http_exc = super(N6DefaultStreamViewBase, cls).adjust_exc(exc)
        log_debug_info_on_http_exc(http_exc)
        return http_exc


class N6CorsSupportStreamView(N6DefaultStreamViewBase):

    @classmethod
    def get_default_http_methods(cls):
        """
        Add 'OPTIONS' to supported http methods.

        This is required http method for Cross-Origin Resource Sharing
        (https://www.w3.org/TR/cors/) support.
        """
        return super(N6CorsSupportStreamView, cls).get_default_http_methods(), 'OPTIONS'


class N6LimitedStreamView(N6CorsSupportStreamView):

    """
    A view class that implements global limit for returned items.

    Results are limited by adding an `opt.limit` parameter to
    a query, if it is not present already, or its value is too high.
    """

    GLOBAL_ITEM_NUMBER_LIMIT = 1000

    def prepare_params(self):
        params = super(N6LimitedStreamView, self).prepare_params()
        if 'opt.limit' not in params or params['opt.limit'][0] > self.GLOBAL_ITEM_NUMBER_LIMIT:
            params['opt.limit'] = [self.GLOBAL_ITEM_NUMBER_LIMIT]
        return params


class _AbstractInfoView(AbstractViewBase):

    """
    An abstract class for creating views that return some simple info,
    without accessing database.
    """

    data_backend_api_method = None

    def __init__(self, *args):
        super(_AbstractInfoView, self).__init__(*args)
        self.auth_api = self.request.registry.auth_api
        self._certificate_fetched = self._check_for_certificate(self.request)
        self._auth_data = getattr(self.request, 'auth_data', None)
        if self._auth_data:
            self._access_info = self.auth_api.get_access_info(self.request.auth_data)
        else:
            self._access_info = None

    def prepare_params(self):
        return {}

    @classmethod
    def concrete_view_class(cls, data_backend_api_method, **kwargs):
        view_class = super(_AbstractInfoView, cls).concrete_view_class(**kwargs)
        view_class.data_backend_api_method = data_backend_api_method
        return view_class

    @staticmethod
    def _check_for_certificate(request):
        if request.environ.get(SSL_ORG_ID_FIELD) and request.environ.get(SSL_USER_ID_FIELD):
            return True
        return False


class N6InfoView(_AbstractInfoView):

    """
    Get info about REST API resources, to which user has access
    and his 'full access' status, and call proper API method.
    """

    def make_response(self):
        api_method_name = self.data_backend_api_method
        api_method = getattr(self.request.registry.data_backend_api, api_method_name)
        if not self._auth_data:
            return api_method(False, certificate_fetched=self._certificate_fetched)
        available_resources, full_access = self._get_access_info()
        if (not isinstance(available_resources, MutableSequence) or
                not isinstance(full_access, bool)):
            raise HTTPServerError
        for res in available_resources:
            if res not in RESOURCE_ID_TO_ACCESS_ZONE:
                raise HTTPServerError
        return api_method(True,
                          available_resources=available_resources,
                          full_access=full_access,
                          certificate_fetched=self._certificate_fetched)

    def _get_access_info(self):
        return (self._access_info['rest_api_resource_limits'].keys(),
                self._access_info['rest_api_full_access'])


class N6AuthView(_AbstractInfoView):

    @classmethod
    def get_default_http_methods(cls):
        return 'POST'

    def make_response(self):
        api_method_name = self.data_backend_api_method
        api_method = getattr(self.request.registry.data_backend_api, api_method_name)
        return api_method(self.request, self.auth_api)


class _AbstractDeviceRequestViewBase(AbstractViewBase):

    view_config_spec = '''
        [device_request_resource]
        finalized_request_case_expiry_days = 30 :: int
    '''

    @classmethod
    def concrete_view_class(cls, config, **kwargs):
        # note: here the `config` argument is a pyramid.config.Configurator
        # instance (*not* a n6lib.config.Config instance!)
        view_class = super(_AbstractDeviceRequestViewBase,
                           cls).concrete_view_class(config=config, **kwargs)
        view_class.view_config_section = n6lib.config.Config.section(
            view_class.view_config_spec,
            settings=config.registry.settings)
        return view_class

    @attr_required('view_config_section')
    def __init__(self, *args, **kwargs):
        super(_AbstractDeviceRequestViewBase, self).__init__(*args, **kwargs)
        self.manage_api = self.request.registry.manage_api

    def prepare_params(self):
        return {}


if _MANAGE_API:
    class DeviceRequestPostViewBase(_AbstractDeviceRequestViewBase):

        @classmethod
        def get_default_http_methods(cls):
            return 'POST'

        def make_response(self):
            request_case = self._new_request_case(
                csr_pem=self.request.body,
                auth_data=self.request.auth_data)
            body = json.dumps({'request_id': request_case.request_id})
            return Response(
                body,
                content_type='application/json')

        def _new_request_case(self, csr_pem, auth_data):
            try:
                return self.manage_api.make_new_request_case(csr_pem, auth_data)
            except ManageAPIClientError as exc:
                if exc.remote_user_error_label == 'not-a-csr':
                    raise HTTPBadRequest(exc.remote_user_error_descr)
                if exc.remote_user_error_label in (
                        'csr-non-compliance', 'csr-for-different-user'):
                    raise HTTPForbidden(exc.remote_user_error_descr)
                raise
else:
    DeviceRequestPostViewBase = None


if _MANAGE_API:
    class DeviceRequestGetViewBase(_AbstractDeviceRequestViewBase):

        @classmethod
        def validate_url_pattern(cls, url_pattern):
            if not url_pattern.endswith('/{request_id}'):
                LOGGER.error("url_pattern must contain '/{request_id}' suffix")
                raise HTTPServerError

        @classmethod
        def get_default_http_methods(cls):
            return 'GET'

        def make_response(self):
            request_id = self.request.matchdict['request_id']
            with self.manage_api as manage_api:
                request_case = self._get_request_case(manage_api, request_id)
                if request_case.status in ('new', 'registered'):
                    body = ''
                    status_code = 202
                elif request_case.status == 'finalized':
                    self._check_request_case_expiry(request_case)
                    cert_data = self._get_valid_cert_data(manage_api, request_case)
                    body = cert_data.cert_pem
                    status_code = 200
                else:
                    assert request_case.status == 'cancelled'
                    raise HTTPGone('The specified remote certificate request case is cancelled.')
            return Response(
                body,
                status_code=status_code,
                content_type='text/plain')

        def _get_request_case(self, manage_api, request_id):
            try:
                return manage_api.get_request_case(request_id)
            except ManageAPIClientError as exc:
                if exc.remote_user_error_label == 'request-id-not-found':
                    raise HTTPNotFound(exc.remote_user_error_descr)
                raise

        def _check_request_case_expiry(self, request_case):
            assert request_case.status == 'finalized'
            request_case_expiry_days = self.view_config_section['finalized_request_case_expiry_days']
            if request_case_expiry_days > 0 and (
                  datetime.datetime.utcnow() - request_case.status_changed_on >
                    datetime.timedelta(days=request_case_expiry_days)):
                raise HTTPGone('The specified remote certificate request case expired.')

        def _get_valid_cert_data(self, manage_api, request_case):
            cert_data = manage_api.get_cert(
                request_case.cert_ca_label,
                request_case.cert_serial_number)
            cert_data.ensure_cert_verified()
            if cert_data.revoked_on is not None:
                raise HTTPGone('The requested certificate has been revoked.')
            if cert_data.expires_on < datetime.datetime.utcnow():
                raise HTTPGone('The requested certificate already expired.')
            return cert_data
else:
    DeviceRequestGetViewBase = None


#
# Custom tweens (see: http://docs.pylonsproject.org/projects/pyramid/en/newest/narr/hooks.html#registering-tweens)

### XXX: [ticket #3312] Is this tween effective with stream renderers???
def auth_api_context_tween_factory(handler, registry):

    """
    Factory of AuthAPI context tween.

    This tween automatically wraps requests in the AuthAPI context
    (using the AuthAPI context manager interface).

    See also: n6lib.auth_api.AuthAPI.
    """

    auth_api = registry.auth_api

    def auth_api_context_tween(request):
        with auth_api:
            return handler(request)

    return auth_api_context_tween


### XXX: [ticket #3312] Is this tween effective with stream renderers???
def transact_tween_factory(handler, registry):

    """
    Factory of transaction management tween (somehow similar to pyramid_tm).

    See also: n6lib.transaction_helpers.
    """

    NOTE_FORMAT = u'unauthenticated_userid: {!r}; request_path: {!r}'

    class _AbortTransact(Exception):
        pass

    def transact_tween(request):
        userid = request.unauthenticated_userid
        try:
            with transact:
                transact.active.note(NOTE_FORMAT.format(userid, request.path_info))
                response = handler(request)
                if transact.active.isDoomed():
                    raise _AbortTransact
        except _AbortTransact:
            pass
        return response

    return transact_tween


#
# Application startup/configuration

class N6ConfigHelper(ConfigHelper):

    # (see: ConfigHelper docs)

    ### XXX: is it used??? should it be used??? [ticket #3688]
    default_static_view_config = {
        'name': 'static',
        'path': 'static',
        'cache_max_age': 3600,
    }

    # note: all constructor arguments (including `auth_api_class`)
    # should be specified as keyword arguments
    def __init__(self, auth_api_class, manage_api_class=None, **kwargs):
        self.auth_api_class = auth_api_class
        self.manage_api_class = manage_api_class
        super(N6ConfigHelper, self).__init__(**kwargs)

    def prepare_config(self, config):
        #config.add_tween(
        #    'n6lib.profiling_helpers.profiling_tween_factory',
        #    under=INGRESS)
        config.add_tween(
            'n6lib.pyramid_commons.transact_tween_factory',
            under=EXCVIEW)
        config.add_tween(
            'n6lib.pyramid_commons.auth_api_context_tween_factory',
            under=EXCVIEW)
        config.registry.auth_api = self.auth_api_class(settings=self.settings)
        if self.manage_api_class is not None:
            config.registry.manage_api = self.manage_api_class(settings=self.settings)
        return super(N6ConfigHelper, self).prepare_config(config)

    @classmethod
    def exception_view(cls, exc, request):
        http_exc = super(N6ConfigHelper, cls).exception_view(exc, request)
        log_debug_info_on_http_exc(http_exc)
        return http_exc


#
# Authentication policies

class BaseUserAuthenticationPolicy(BaseAuthenticationPolicy):

    """
    Base class for user+organization-based authentication policy classes.
    """

    _dev_fake_auth_flag_config_spec = '''
        dev_fake_auth = false :: bool
        ...
    '''

    def __new__(cls, settings):
        dev_fake_auth_flag_config = n6lib.config.Config.section(
            cls._dev_fake_auth_flag_config_spec,
            settings=settings)
        if dev_fake_auth_flag_config['dev_fake_auth']:
            # this is a hack for developers only
            return DevFakeUserAuthenticationPolicy(settings)
        return super(BaseUserAuthenticationPolicy, cls).__new__(cls)

    @staticmethod
    def merge_orgid_userid(org_id, user_id):
        return '{},{}'.format(org_id, user_id)

    @staticmethod
    def get_auth_data(request):
        """
        Queries auth api for auth_data.

        Returns:
            A dict {'org_id': <organization id>, 'user_id': <user id>}
            or None.
        """
        unauthenticated_userid = request.unauthenticated_userid
        if unauthenticated_userid is not None:
            org_id, user_id = unauthenticated_userid.split(',')
            try:
                auth_data = request.registry.auth_api.authenticate(org_id, user_id)
            except AuthAPIUnauthenticatedError:
                LOGGER.warning('could not authenticate for organization id %r + user id %r',
                               org_id, user_id)
            else:
                return auth_data
        else:
            # TODO: if this method is called from the
            # `LoginOrSSLUserAuthenticationPolicy` class, it should
            # not log this warning (maybe move part of a code
            # outside of the method and create two different
            # implementations?)
            LOGGER.warning('no unauthenticated_userid given!')
        return None

    def authenticated_userid(self, request):
        if request.auth_data is not None:
            return self.merge_orgid_userid(request.auth_data['org_id'],
                                           request.auth_data['user_id'])
        return None

    def effective_principals(self, request):
        effective_principals = super(BaseUserAuthenticationPolicy,
                                     self).effective_principals(request)
        assert Everyone in effective_principals
        if request.auth_data is not None:
            assert Authenticated in effective_principals
            effective_principals.append(self.merge_orgid_userid(request.auth_data['org_id'],
                                                                request.auth_data['user_id']))
            #if <organization.rest_api_full_access>:
            #    effective_principals.append("group:admin")
        return effective_principals


class SSLUserAuthenticationPolicy(BaseUserAuthenticationPolicy):

    """Authentication based on mod_ssl env variables."""

    def unauthenticated_userid(self, request):
        org_id, user_id = get_certificate_credentials(request)
        if org_id is not None and user_id is not None:
            return self.merge_orgid_userid(org_id, user_id)
        return None


class LoginOrSSLUserAuthenticationPolicy(SSLUserAuthenticationPolicy):

    """
    Authentication based on a signed cookie.

    The cookie is created, after user signs in using his credentials
    through login form, or using SSL certificate. After that, each
    request is authenticated with the cookie.
    """

    def __init__(self, settings):
        self._auth_tkt_policy = AuthTktAuthenticationPolicy(secret=make_hex_id(),
                                                            hashalg='sha384',
                                                            secure=False)

    def unauthenticated_userid(self, request):
        credentials = self._auth_tkt_policy.unauthenticated_userid(request)
        if credentials and self._validate_credentials(credentials):
            return credentials

    def authenticated_userid(self, request):
        return request.auth_data

    def effective_principals(self, request):
        return self._auth_tkt_policy.effective_principals(request)

    def remember(self, *args, **kwargs):
        return self._auth_tkt_policy.remember(*args, **kwargs)

    def forget(self, request):
        return self._auth_tkt_policy.forget(request)

    @staticmethod
    def _validate_credentials(credentials):
        try:
            _org_id, _user_id = credentials.split(',')
        except ValueError:
            LOGGER.warning("User tried to authenticate with invalid credentials: %s.",
                           credentials)
            return False
        return True

    # https://docs.pylonsproject.org/projects/pyramid/en/latest/tutorials/wiki2/authentication
    # .html#add-login-logout-and-forbidden-views


class DevFakeUserAuthenticationPolicy(BaseUserAuthenticationPolicy):

    """
    A fake version for developers only...
    """

    _dev_fake_auth_config_spec = '''
        [dev_fake_auth]
        org_id = example.org
        user_id = example@example.org
    '''

    def __new__(cls, settings):
        self = super(BaseUserAuthenticationPolicy,  # [sic]
                     cls).__new__(cls)
        self._dev_fake_auth_config = n6lib.config.Config.section(
            self._dev_fake_auth_config_spec,
            settings=settings)
        return self

    def unauthenticated_userid(self, request):
        return self.merge_orgid_userid(
            self._dev_fake_auth_config['org_id'],
            self._dev_fake_auth_config['user_id'])


#
# Asserting that our non-sdk n6 renderers are registered

assert registered_stream_renderers.get('csv') is StreamRenderer_csv
assert registered_stream_renderers.get('iodef') is StreamRenderer_iodef
assert registered_stream_renderers.get('snort-dns') is SnortDNSRenderer
assert registered_stream_renderers.get('snort-http') is SnortHTTPRenderer
assert registered_stream_renderers.get('snort-ip') is SnortIPRenderer
assert registered_stream_renderers.get('snort-ip-bl') is SnortIPBlacklistRenderer
assert registered_stream_renderers.get('suricata-dns') is SuricataDNSRenderer
assert registered_stream_renderers.get('suricata-http') is SuricataHTTPRenderer
assert registered_stream_renderers.get('suricata-ip') is SuricataIPRenderer
assert registered_stream_renderers.get('suricata-ip-bl') is SuricatatIPBlacklistRenderer

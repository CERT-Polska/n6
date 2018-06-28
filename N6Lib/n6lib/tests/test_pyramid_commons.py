# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import json
import unittest

from mock import (
    ANY,
    Mock,
    MagicMock,
    call,
    patch,
    sentinel as sen,
)
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPForbidden,
    HTTPGone,
    HTTPNotFound,
    HTTPServerError,
)
from pyramid.response import Response
from pyramid.security import (
    Authenticated,
    Everyone,
)
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.pyramid_commons._pyramid_commons import (
    SSL_ORG_ID_FIELD,
    SSL_USER_ID_FIELD,
)
from n6lib.auth_api import AuthAPIUnauthenticatedError
from n6lib.config import ConfigError
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.pyramid_commons import (
    DeviceRequestPostViewBase,
    DeviceRequestGetViewBase,
    N6InfoView,
    BaseUserAuthenticationPolicy,
    SSLUserAuthenticationPolicy,
    LoginOrSSLUserAuthenticationPolicy,
    DevFakeUserAuthenticationPolicy,
)
from n6lib.unit_test_helpers import MethodProxy

if DeviceRequestPostViewBase is not None or DeviceRequestGetViewBase is not None:
    from n6lib.manage_api import (
        ManageAPIError,
        ManageAPIClientError,
        RequestCase,
    )



if DeviceRequestPostViewBase is not None:

    @expand
    class TestDeviceRequestPostViewBase(unittest.TestCase):

        SOME_REQUEST_ID = '0123456789abcdef0123456789ab'


        def test__get_default_http_methods(self):
            result = DeviceRequestPostViewBase.get_default_http_methods()
            self.assertEqual(result, 'POST')


        def test__make_response__ok(self):
            expected_status_code = 200
            expected_content_type = 'application/json'
            expected_deserialized_body = {'request_id': self.SOME_REQUEST_ID}
            self._prepare_for_make_response()
            self.manage_api.make_new_request_case.side_effect = (
                    self._side_effect__make_new_request_case__ok)

            response = self.view.make_response()

            self.assertIsInstance(response, Response)
            self.assertEqual(response.status_code, expected_status_code)
            self.assertEqual(response.content_type, expected_content_type)
            self.assertEqual(json.loads(response.body), expected_deserialized_body)
            self.assertEqual(self.manage_api.mock_calls, [
                call.make_new_request_case(
                    sen.csr_pem,
                    sen.auth_data,
                ),
            ])


        @foreach(
            param(
                ManageAPIClientError(remote_user_error_label='not-a-csr'),
                expected_exc_class=HTTPBadRequest,
                expected_exc_regexp='not a valid CSR',
                expected_status_code=400,
            ),
            param(
                ManageAPIClientError(remote_user_error_label='csr-non-compliance'),
                expected_exc_class=HTTPForbidden,
                expected_exc_regexp='CSR does not comply',
                expected_status_code=403,
            ),
            param(
                ManageAPIClientError(remote_user_error_label='csr-for-different-user'),
                expected_exc_class=HTTPForbidden,
                expected_exc_regexp='CSR subject does not match.*user',
                expected_status_code=403,
            ),
            param(
                ManageAPIError('tralalala'),
                expected_exc_class=ManageAPIError,
                expected_exc_regexp='tralalala',
            ),
        )
        def test__make_response__err(self,
                                     side_effect__make_new_request_case,
                                     expected_exc_class,
                                     expected_exc_regexp,
                                     expected_status_code=None):
            self._prepare_for_make_response()
            self.manage_api.make_new_request_case.side_effect = side_effect__make_new_request_case

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp) as cm:
                self.view.make_response()

            if expected_status_code is not None:
                self.assertIsInstance(cm.exception, Response)
                self.assertEqual(cm.exception.status_code, expected_status_code)
            self.assertEqual(self.manage_api.mock_calls, [
                call.make_new_request_case(
                    sen.csr_pem,
                    sen.auth_data,
                ),
            ])


        def _prepare_for_make_response(self):
            # request mock
            self.request = MagicMock()
            self.request.body = sen.csr_pem
            self.request.auth_data = sen.auth_data
            self.manage_api = self.request.registry.manage_api

            # view instance
            configurator = MagicMock()
            configurator.registry.settings = {}
            concrete_cls = DeviceRequestPostViewBase.concrete_view_class(
                resource_id=sen.resource_id,
                config=configurator)
            self.view = concrete_cls(sen.context, self.request)


        def _side_effect__make_new_request_case__ok(self, csr_pem, auth_data):
            return RequestCase(self.SOME_REQUEST_ID, csr_pem, sen.sender_dn)



if DeviceRequestGetViewBase is not None:

    @expand
    class TestDeviceRequestGetViewBase(unittest.TestCase):

        SOME_URL_PREFIX = '/some-url/path'

        SOME_CERT_CA_LABEL = 'client-2'
        SOME_CERT_SERIAL_NUMBER = '0123456789abcdef0123'
        SOME_CERT_DN = 'n6cert-serial-hex={0},cn={1},cn=root,dc=n6,dc=cert,dc=pl'.format(
            SOME_CERT_SERIAL_NUMBER,
            SOME_CERT_CA_LABEL)

        SOME_CERT_PEM = '<<< (-: \n instead of some certificate pem \r\n :-) >>>'

        DT_TODAY = datetime.datetime.utcnow()
        DT_TOMMOROW = DT_TODAY + datetime.timedelta(days=1)
        DT_YESTERDAY = DT_TODAY - datetime.timedelta(days=1)
        DT_DAY_BEFORE_YESTERDAY = DT_TODAY - datetime.timedelta(days=2)

        PARAMS__REQ_EXPIRY_SETTING__OK = [
            param(
                settings={},
            ),
            param(
                # finalized_request_case_expiry_days<=0 means: no expiration
                settings={'device_request_resource.finalized_request_case_expiry_days': '0'},
            ),
            param(
                settings={'device_request_resource.finalized_request_case_expiry_days': '1'},
            ),
            param(
                settings={'device_request_resource.finalized_request_case_expiry_days': '30'},
            ),
            param(
                # finalized_request_case_expiry_days<=0 means: no expiration
                settings={'device_request_resource.finalized_request_case_expiry_days': '0'},
                status_changed_on=DT_DAY_BEFORE_YESTERDAY,
            ),
            param(
                # finalized_request_case_expiry_days<=0 means: no expiration
                settings={'device_request_resource.finalized_request_case_expiry_days': '-1'},
                status_changed_on=DT_DAY_BEFORE_YESTERDAY,
            ),
            param(
                settings={'device_request_resource.finalized_request_case_expiry_days': '30'},
                status_changed_on=DT_DAY_BEFORE_YESTERDAY,
            ),
        ]

        PARAMS__REQ_EXPIRY_SETTING__EXPIRED = [
            param(
                settings={'device_request_resource.finalized_request_case_expiry_days': '1'},
                status_changed_on=DT_DAY_BEFORE_YESTERDAY,
            ),
        ]


        def test__validate_url_pattern__ok(self):
            url_pattern = self.SOME_URL_PREFIX + '/{request_id}'
            none = DeviceRequestGetViewBase.validate_url_pattern(url_pattern)
            self.assertIsNone(none)


        @foreach(
            '{request_id}',
            '/foo{request_id}',
            '/{request_id}foo',
            '/{foo}',
            '/foo',
        )
        def test__validate_url_pattern__err(self, suffix):
            url_pattern = self.SOME_URL_PREFIX + suffix
            with self.assertRaises(HTTPServerError):
                DeviceRequestGetViewBase.validate_url_pattern(url_pattern)


        def test__get_default_http_methods(self):
            result = DeviceRequestGetViewBase.get_default_http_methods()
            self.assertEqual(result, 'GET')


        @foreach(PARAMS__REQ_EXPIRY_SETTING__OK)
        def test__make_response__ok_200(self,
                                        settings,
                                        status_changed_on=sen.NOT_SET):
            expected_status_code = 200
            expected_content_type = 'text/plain'
            expected_body = self.SOME_CERT_PEM
            self._prepare_for_make_response_calling_get_cert(settings)
            self.cert_dn = self.SOME_CERT_DN
            self.status = 'finalized'
            self.status_changed_on = status_changed_on

            response = self.view.make_response()

            self.assertIsInstance(response, Response)
            self.assertEqual(response.status_code, expected_status_code)
            self.assertEqual(response.content_type, expected_content_type)
            self.assertEqual(response.body, expected_body)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)
            self.assertEqual(self.cert_data.mock_calls, [call.ensure_cert_verified()])


        @foreach(PARAMS__REQ_EXPIRY_SETTING__OK + PARAMS__REQ_EXPIRY_SETTING__EXPIRED)
        @foreach(
            param(status='new'),
            param(status='registered'),
        )
        def test__make_response__ok_202(self,
                                        status,
                                        settings,
                                        status_changed_on=sen.NOT_SET):
            expected_status_code = 202
            expected_content_type = 'text/plain'
            expected_body = ''
            self._prepare_for_make_response(settings)
            self.status = status
            self.status_changed_on = status_changed_on

            response = self.view.make_response()

            self.assertIsInstance(response, Response)
            self.assertEqual(response.status_code, expected_status_code)
            self.assertEqual(response.content_type, expected_content_type)
            self.assertEqual(response.body, expected_body)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        def test__make_response__err_404(self):
            expected_exc_class = HTTPNotFound
            expected_exc_regexp = 'remote certificate request case not found'
            expected_status_code = 404
            self._prepare_for_make_response(
                settings={},
                expected_exc_class=expected_exc_class)
            self.manage_api.get_request_case.side_effect = ManageAPIClientError(
                remote_user_error_label='request-id-not-found')

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp) as cm:
                self.view.make_response()

            self.assertEqual(cm.exception.status_code, expected_status_code)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        @foreach(PARAMS__REQ_EXPIRY_SETTING__OK + PARAMS__REQ_EXPIRY_SETTING__EXPIRED)
        def test__make_response__err_410_req_cancelled(self,
                                                       settings,
                                                       status_changed_on=sen.NOT_SET):
            expected_exc_class = HTTPGone
            expected_exc_regexp = 'remote certificate request case is cancelled'
            expected_status_code = 410
            self._prepare_for_make_response(settings, expected_exc_class)
            self.status = 'cancelled'
            self.status_changed_on = status_changed_on

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp) as cm:
                self.view.make_response()

            self.assertEqual(cm.exception.status_code, expected_status_code)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        @foreach(PARAMS__REQ_EXPIRY_SETTING__EXPIRED)
        def test__make_response__err_410_req_expired(self,
                                                     settings,
                                                     status_changed_on=sen.NOT_SET):
            expected_exc_class = HTTPGone
            expected_exc_regexp = 'remote certificate request case expired'
            expected_status_code = 410
            self._prepare_for_make_response(settings, expected_exc_class)
            self.cert_dn = self.SOME_CERT_DN
            self.status = 'finalized'
            self.status_changed_on = status_changed_on

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp) as cm:
                self.view.make_response()

            self.assertEqual(cm.exception.status_code, expected_status_code)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        @foreach(PARAMS__REQ_EXPIRY_SETTING__OK)
        @foreach(
            param(
                'certificate already expired',
                cert_expires_on=DT_YESTERDAY,  # <- expired
                cert_revoked_on=None,
            ),
            param(
                'certificate has been revoked',
                cert_expires_on=DT_TOMMOROW,
                cert_revoked_on=DT_YESTERDAY,  # <- revoked
            ),
        )
        def test__make_response__err_410_cert_inactive(self,
                                                       expected_exc_regexp,
                                                       cert_expires_on,
                                                       cert_revoked_on,
                                                       settings,
                                                       status_changed_on=sen.NOT_SET):
            expected_exc_class = HTTPGone
            expected_status_code = 410
            self._prepare_for_make_response_calling_get_cert(settings, expected_exc_class)
            self.cert_expires_on = cert_expires_on
            self.cert_revoked_on = cert_revoked_on
            self.cert_dn = self.SOME_CERT_DN
            self.status = 'finalized'
            self.status_changed_on = status_changed_on

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp) as cm:
                self.view.make_response()

            self.assertEqual(cm.exception.status_code, expected_status_code)
            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)
            self.assertEqual(self.cert_data.mock_calls, [call.ensure_cert_verified()])


        def test__make_response__err_ManageAPIError_from_get_request_case(self):
            expected_exc_class = ManageAPIError
            expected_exc_regexp = 'tralalala'
            self._prepare_for_make_response(
                settings={},
                expected_exc_class=expected_exc_class)
            self.manage_api.get_request_case.side_effect = expected_exc_class(expected_exc_regexp)

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp):
                self.view.make_response()

            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        def test__make_response__err_ManageAPIError_from_get_cert(self):
            expected_exc_class = ManageAPIError
            expected_exc_regexp = 'tralalala'
            self._prepare_for_make_response_calling_get_cert(
                settings={},
                expected_exc_class=expected_exc_class)
            self.cert_dn = self.SOME_CERT_DN
            self.status = 'finalized'
            self.manage_api.get_cert.side_effect = expected_exc_class(expected_exc_regexp)

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp):
                self.view.make_response()

            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)


        def test__make_response__err_ManageAPIError_from_ensure_cert_verified(self):
            expected_exc_class = ManageAPIError
            expected_exc_regexp = 'tralalala'
            self._prepare_for_make_response_calling_get_cert(
                settings={},
                expected_exc_class=expected_exc_class)
            self.cert_dn = self.SOME_CERT_DN
            self.status = 'finalized'
            self.cert_data.ensure_cert_verified.side_effect = expected_exc_class(expected_exc_regexp)

            with self.assertRaisesRegexp(expected_exc_class, expected_exc_regexp):
                self.view.make_response()

            self.assertEqual(self.manage_api.mock_calls, self.expected_manage_api_calls)
            self.assertEqual(self.cert_data.mock_calls, [call.ensure_cert_verified()])


        def _prepare_for_make_response(self,
                                       settings,
                                       expected_exc_class=None):
            # request mock
            self.request = MagicMock()
            self.request.matchdict = {'request_id': sen.request_id}
            self.manage_api = self.request.registry.manage_api
            self.manage_api.__enter__.return_value = self.manage_api
            self.manage_api.get_request_case.side_effect = self._side_effect__get_request_case

            # view instance
            self.configurator = MagicMock()
            self.configurator.registry.settings = settings
            concrete_cls = DeviceRequestGetViewBase.concrete_view_class(
                resource_id=sen.resource_id,
                config=self.configurator)
            self.view = concrete_cls(sen.context, self.request)

            # defaults for stuff used in _side_effect__get_request_case()
            self.cert_dn = None
            self.status = sen.NOT_SET
            self.status_changed_on = sen.NOT_SET

            # expected ManageAPI method calls
            self.expected_manage_api_calls = [
                call.__enter__(),
                call.get_request_case(sen.request_id),
                call.__exit__(expected_exc_class, ANY, ANY),
            ]


        def _prepare_for_make_response_calling_get_cert(self,
                                                        settings=None,
                                                        expected_exc_class=None):
            self._prepare_for_make_response(settings)
            self.manage_api.get_cert.side_effect = self._side_effect__get_cert

            # to be returned by _side_effect__get_cert()
            self.cert_data = MagicMock()

            # defaults for stuff used in _side_effect__get_cert()
            self.cert_pem = self.SOME_CERT_PEM
            self.cert_expires_on = self.DT_TOMMOROW
            self.cert_revoked_on = None

            # expected ManageAPI method calls (overwritten)
            self.expected_manage_api_calls = [
                call.__enter__(),
                call.get_request_case(sen.request_id),
                call.get_cert(self.SOME_CERT_CA_LABEL, self.SOME_CERT_SERIAL_NUMBER),
                call.__exit__(expected_exc_class, ANY, ANY),
            ]


        def _side_effect__get_request_case(self, request_id):
            request_case = RequestCase(request_id, sen.csr_pem, sen.sender_dn)
            request_case.cert_dn = self.cert_dn
            request_case.status = self.status
            if self.status_changed_on is not sen.NOT_SET:
                request_case._status_changed_on = self.status_changed_on
            return request_case


        def _side_effect__get_cert(self, ca_label, serial_number):
            cert_data = self.cert_data
            cert_data.cert_pem = self.cert_pem
            cert_data.expires_on = self.cert_expires_on
            cert_data.revoked_on = self.cert_revoked_on
            return cert_data



sample_access_info_items = {
    'queries_limit': None,
    'window': 3600,
    'request_parameters': None,
    'max_days_old': 100,
    'results_limit': None,
}


access_info_to_response = [
    param(
        res_limits={
            '/search/events': sample_access_info_items,
        },
        full_access=True,
        is_authenticated=True,
        is_cert_available=True,
        expected_response={
            'available_resources': ['/search/events'],
            'certificate_fetched': True,
            'full_access': True,
            'authenticated': True,
        },
    ),
    # `full_access` is hidden if False
    param(
        res_limits={
            '/search/events': sample_access_info_items,
            '/report/inside': sample_access_info_items,
        },
        full_access=False,
        is_authenticated=True,
        is_cert_available=False,
        expected_response={
            'available_resources': [
                '/search/events',
                '/report/inside',
            ],
            'certificate_fetched': False,
            'authenticated': True,
        },
    ),
    param(
        res_limits={
            '/search/events': sample_access_info_items,
            '/report/inside': sample_access_info_items,
            '/report/threats': sample_access_info_items,
        },
        full_access=False,
        is_authenticated=True,
        is_cert_available=True,
        expected_response={
            'available_resources': [
                '/report/threats',
                '/search/events',
                '/report/inside',
            ],
            'certificate_fetched': True,
            'authenticated': True,
        },
    ),
    # if not authenticated, `available_resources` item is hidden
    param(
            res_limits={
                '/search/events': sample_access_info_items,
                '/report/inside': sample_access_info_items,
                '/report/threats': sample_access_info_items,
            },
            full_access=False,
            is_authenticated=False,
            is_cert_available=True,
            expected_response={
                'certificate_fetched': True,
                'authenticated': False,
            },
    ),
    param(
            res_limits={},
            full_access=False,
            is_authenticated=False,
            is_cert_available=False,
            expected_response={
                'certificate_fetched': False,
                'authenticated': False,
            },
    ),
    # if user is authenticated, `available_resources` is shown,
    # even if it is empty
    param(
            res_limits={},
            full_access=False,
            is_authenticated=True,
            is_cert_available=False,
            expected_response={
                'available_resources': [],
                'certificate_fetched': False,
                'authenticated': True,
            },
    ),
]


access_info_to_exc = [
    param(
        res_limits={
            '/search/events': sample_access_info_items,
            '/report/inside': sample_access_info_items,
            '/report/threats': sample_access_info_items,
        },
        full_access='false',
        is_authenticated=True,
        expected_exc=HTTPServerError,
    ),
    param(
        res_limits={
            '/search/events': sample_access_info_items,
            '/unknown/resource': sample_access_info_items,
            '/report/threats': sample_access_info_items,
        },
        full_access=True,
        is_authenticated=True,
        expected_exc=HTTPServerError,
    ),
]


@expand
class TestN6InfoView(unittest.TestCase):

    api_method_name = 'get_user_info'
    info_res_id = '/info'
    mocked_context = sen.context
    expected_content_type = 'application/json'
    http_method = 'GET'

    class MockedRequest(object):
        registry = Mock()
        registry.auth_api = Mock()
        registry.data_backend_api = N6DataBackendAPI.__new__(N6DataBackendAPI)

        def __init__(self, res_limits, full_access, is_authenticated, is_cert_available):
            self.auth_data = {}
            self.environ = {}
            access_info = dict(rest_api_resource_limits=res_limits,
                               rest_api_full_access=full_access)
            self.registry.auth_api.get_access_info.return_value = access_info
            if is_authenticated:
                self.auth_data['org_id'] = sen.org_id
                self.auth_data['user_id'] = sen.user_id
            if is_cert_available:
                self.environ[SSL_ORG_ID_FIELD] = sen.ssl_org_id
                self.environ[SSL_USER_ID_FIELD] = sen.ssl_user_id

    def _get_mocked_request(self,
                            res_limits,
                            full_access,
                            is_authenticated=False,
                            is_cert_available=False):
        return self.MockedRequest(res_limits, full_access, is_authenticated, is_cert_available)

    def _get_view_instance(self, mocked_request):
        N6InfoView.resource_id = self.info_res_id
        N6InfoView.data_backend_api_method = self.api_method_name
        return N6InfoView(self.mocked_context, mocked_request)

    @foreach(access_info_to_response)
    def test_response(self,
                      res_limits,
                      full_access,
                      is_authenticated,
                      is_cert_available,
                      expected_response):
        mocked_request = self._get_mocked_request(res_limits,
                                                  full_access,
                                                  is_authenticated,
                                                  is_cert_available)
        view_inst = self._get_view_instance(mocked_request)
        resp = view_inst.make_response()
        self.assertIsInstance(resp, Response)
        resp_body = json.loads(resp.body)
        self.assertDictEqual(resp_body, expected_response)
        self.assertEqual(resp.content_type, self.expected_content_type)
        self.assertEqual(resp.status_int, 200)

    @foreach(access_info_to_exc)
    def test_bad_response(self, res_limits, full_access, is_authenticated, expected_exc):
        mocked_request = self._get_mocked_request(res_limits, full_access, is_authenticated)
        view_inst = self._get_view_instance(mocked_request)
        with self.assertRaises(expected_exc):
            resp = view_inst.make_response()
            self.assertEqual(resp.status_int, 500)

    def test_get_default_http_methods(self):
        self.assertEqual(self.http_method, N6InfoView.get_default_http_methods())


@expand
class TestInstantiationOfAuthenticationPolicies(unittest.TestCase):

    _param_policy_class = [
        param(policy_class=BaseUserAuthenticationPolicy),
        param(policy_class=SSLUserAuthenticationPolicy),
        param(policy_class=LoginOrSSLUserAuthenticationPolicy),
    ]
    _param_side_settings = [
        param(side_settings={}),
        param(side_settings={'foo': 'bar'}),
        param(side_settings={
            'foo': 'bar',
            'foo.bar': 'spam.ham',
            'dev_fake_auth.org_id': 'nask.waw.pl',
            'dev_fake_auth.user_id': "all that doesn't matter",
        }),
    ]


    @foreach(_param_policy_class)
    @foreach(_param_side_settings)
    @foreach(
        param(settings={}),
        param(settings={'dev_fake_auth': 'false'}),
        param(settings={'dev_fake_auth': 'No'}),
        param(settings={'dev_fake_auth': 'OFF'}),
    )
    def test_no_dev_fake_auth(self, policy_class, settings, side_settings):
        given_settings = dict(settings, **side_settings)
        policy_instance = policy_class(given_settings)
        self.assertIs(policy_instance.__class__, policy_class)


    @foreach(_param_policy_class)
    @foreach(_param_side_settings)
    @foreach(
        param(settings={'dev_fake_auth': 'true'}),
        param(settings={'dev_fake_auth': 'YES'}),
        param(settings={'dev_fake_auth': 'On'}),
    )
    def test_with_dev_fake_auth(self, policy_class, settings, side_settings):
        given_settings = dict(settings, **side_settings)
        with patch(
                'n6lib.pyramid_commons._pyramid_commons.DevFakeUserAuthenticationPolicy',
                return_value=sen.DevFakeUserAuthenticationPolicy_instance,
        ) as DevFakeUserAuthenticationPolicy_mock:
            policy_instance = policy_class(given_settings)
            self.assertIs(policy_instance, sen.DevFakeUserAuthenticationPolicy_instance)
            self.assertEqual(DevFakeUserAuthenticationPolicy_mock.mock_calls, [
                call(given_settings),
            ])


    @foreach(_param_policy_class)
    @foreach(_param_side_settings)
    def test_config_error(self, policy_class, side_settings):
        settings = {'dev_fake_auth': 'illegalvalue'}
        given_settings = dict(settings, **side_settings)
        with self.assertRaises(ConfigError):
            policy_class(given_settings)



class TestBaseUserAuthenticationPolicy(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=BaseUserAuthenticationPolicy)
        self.meth = MethodProxy(BaseUserAuthenticationPolicy, self.mock, [
            'merge_orgid_userid',
        ])

    def test__get_auth_data__ok(self):
        request = MagicMock()
        request.unauthenticated_userid = 'org_id,user_id'
        request.registry.auth_api.authenticate.return_value = sen.auth_data
        expected_result = sen.auth_data
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertEqual(request.registry.auth_api.authenticate.mock_calls,
                         [call('org_id', 'user_id')])
        self.assertEqual(result, expected_result)

    def test__get_auth_data__unauthenticated_userid_is_None(self):
        request = MagicMock()
        request.unauthenticated_userid = None
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertIsNone(result)

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__get_auth_data__authenticate_raises_exception(self, LOGGER_warning_mock):
        request = MagicMock()
        request.unauthenticated_userid = 'org_id,user_id'
        request.registry.auth_api.authenticate.side_effect = AuthAPIUnauthenticatedError
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls, [call('could not authenticate for '
                                                               'organization id %r + user id '
                                                               '%r', 'org_id', 'user_id')])

    def test__authenticated_userid__is_ok(self):
        request = MagicMock()
        request.auth_data = {'org_id': 'ORGid', 'user_id': 'USERid'}
        result = self.meth.authenticated_userid(request)
        expected_value = 'ORGid,USERid'
        self.assertEqual(result, expected_value)

    def test__authenticated_userid__is_None(self):
        request = MagicMock()
        request.auth_data = None
        result = self.meth.authenticated_userid(request)
        self.assertIsNone(result)

    def test__effective_principals__when_authenticated(self):
        self._patch_super_for_effective_principals()
        request = MagicMock()
        request.auth_data = {'org_id': 'ORGid', 'user_id': 'USERid'}
        result = self.meth.effective_principals(request)
        self.assertIn(Everyone, result)
        self.assertIn(Authenticated, result)
        self.assertIn('ORGid,USERid', result)

    def test__effective_principals__when_not_authenticated(self):
        self._patch_super_for_effective_principals()
        request = MagicMock()
        request.auth_data = None
        result = self.meth.effective_principals(request)
        self.assertIn(Everyone, result)
        self.assertNotIn(Authenticated, result)

    def _patch_super_for_effective_principals(self):
        cls = BaseUserAuthenticationPolicy
        super_effective_principals = super(cls, cls).effective_principals.__func__
        patcher = patch('n6lib.pyramid_commons._pyramid_commons.super', create=True)
        super_mock = patcher.start()
        self.addCleanup(patcher.stop)
        super_mock().effective_principals.side_effect = (
            lambda request: super_effective_principals(sen.self, request))



class TestSSLUserAuthenticationPolicy(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=SSLUserAuthenticationPolicy)
        self.meth = MethodProxy(SSLUserAuthenticationPolicy, self.mock, [
            'merge_orgid_userid',
        ])

    def test__unauthenticated_userid__ok(self):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'OrgName1', 'SSL_CLIENT_S_DN_CN': 'UserName1'}
        result = self.meth.unauthenticated_userid(request)
        expected_result = 'OrgName1,UserName1'
        self.assertEqual(result, expected_result)

    def test__unauthenticated_userid__user_id_is_None(self):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'testorgname2', 'SSL_CLIENT_S_DN_CN': None}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)

    def test__unauthenticated_userid__org_id_is_None(self):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': None, 'SSL_CLIENT_S_DN_CN': 'testusername3'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__unauthenticated_userid__comma_in_user_id(self, LOGGER_warning_mock):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname4', 'SSL_CLIENT_S_DN_CN': 'user,name4'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls,
                         [call('Comma in user_id %r.', 'user,name4')])

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__unauthenticated_userid__comma_in_org_id(self, LOGGER_warning_mock):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname,5', 'SSL_CLIENT_S_DN_CN': 'username5'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls,
                         [call('Comma in org_id %r.', 'orgname,5')])

    def test_other_important_methods_are_from_BaseUserAuthenticationPolicy(self):
        self.assertIs(SSLUserAuthenticationPolicy.get_auth_data,
                      BaseUserAuthenticationPolicy.get_auth_data)
        self.assertIs(SSLUserAuthenticationPolicy.authenticated_userid.__func__,
                      BaseUserAuthenticationPolicy.authenticated_userid.__func__)
        self.assertIs(SSLUserAuthenticationPolicy.effective_principals.__func__,
                      BaseUserAuthenticationPolicy.effective_principals.__func__)



@expand
class TestDevFakeUserAuthenticationPolicy(unittest.TestCase):

    _param_side_settings = [
        param(side_settings={}),
        param(side_settings={'foo': 'bar'}),
        param(side_settings={'foo.bar': 'spam.ham'}),
        param(side_settings={'dev_fake_auth': 'true'}),
        param(side_settings={'dev_fake_auth': 'false'}),
        param(side_settings={'dev_fake_auth': "doesn't matter"}),
    ]


    @foreach(_param_side_settings)
    @foreach(
        param(
            settings={},
            expected_unauthenticated_userid='example.org,example@example.org',
        ),
        param(
            settings={'dev_fake_auth.org_id': 'nask.waw.pl'},
            expected_unauthenticated_userid='nask.waw.pl,example@example.org',
        ),
        param(
            settings={'dev_fake_auth.user_id': 'foo@example.com'},
            expected_unauthenticated_userid='example.org,foo@example.com',
        ),
        param(
            settings={
                'dev_fake_auth.org_id': 'nask.waw.pl',
                'dev_fake_auth.user_id': 'foo@example.com',
            },
            expected_unauthenticated_userid='nask.waw.pl,foo@example.com',
        ),
    )
    def test_ok(self, settings, side_settings, expected_unauthenticated_userid):
        given_settings = dict(settings, **side_settings)
        policy_instance = DevFakeUserAuthenticationPolicy(given_settings)
        self.assertIsInstance(policy_instance, DevFakeUserAuthenticationPolicy)
        self.assertEqual(
            policy_instance.unauthenticated_userid(sen.request),
            expected_unauthenticated_userid)


    @foreach(_param_side_settings)
    @foreach(
        param(settings={}),
        param(settings={'dev_fake_auth.org_id': 'nask.waw.pl'}),
        param(settings={'dev_fake_auth.user_id': 'foo@example.com'}),
        param(settings={
            'dev_fake_auth.org_id': 'nask.waw.pl',
            'dev_fake_auth.user_id': 'foo@example.com',
        }),
    )
    def test_config_error(self, settings, side_settings):
        given_settings = dict(settings, **side_settings)
        given_settings['dev_fake_auth.illegal_opt'] = 'whatever'
        with self.assertRaises(ConfigError):
            DevFakeUserAuthenticationPolicy(given_settings)



### TODO: test other classes...

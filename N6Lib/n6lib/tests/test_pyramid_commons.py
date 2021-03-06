# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

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
from pyramid.httpexceptions import HTTPServerError
from pyramid.response import Response
from pyramid.security import (
    Authenticated,
    Everyone,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

import n6lib.auth_db.models as models
from n6lib.auth_api import AuthAPIUnauthenticatedError
from n6lib.auth_db import REGISTRATION_REQUEST_STATUS_NEW
from n6lib.auth_db.api import (
    AuthDatabaseAPIClientError,
    AuthQueryAPI,
    AuthManageAPI,
)
from n6lib.config import ConfigError
from n6lib.const import (
    WSGI_SSL_ORG_ID_FIELD,
    WSGI_SSL_USER_ID_FIELD,
)
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.pyramid_commons import (
    N6InfoView,
    N6RegistrationView,
    BaseUserAuthenticationPolicy,
    SSLUserAuthenticationPolicy,
    LoginOrSSLUserAuthenticationPolicy,
    DevFakeUserAuthenticationPolicy,
)
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyInstanceOfWhoseVarsInclude,
    DBConnectionPatchMixin,
    MethodProxy,
    RequestHelperMixin,
)
from n6sdk.exceptions import (
    DataAPIError,
    ParamKeyCleaningError,
    ParamValueCleaningError,
)


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
                self.environ[WSGI_SSL_ORG_ID_FIELD] = sen.ssl_org_id
                self.environ[WSGI_SSL_USER_ID_FIELD] = sen.ssl_user_id

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
class TestN6RegistrationView(RequestHelperMixin, DBConnectionPatchMixin, unittest.TestCase):

    def setUp(self):
        self.added_to_session = []
        self.session_mock = MagicMock()
        self.session_mock.add.side_effect = self.added_to_session.append
        self.auth_db_connector_mock = MagicMock()
        self.auth_db_connector_mock.get_current_session.return_value = self.session_mock
        self.pyramid_config = self.prepare_pyramid_testing()
        self._set_up_auth_apis()

    def _set_up_auth_apis(self):
        self.patch('n6lib.auth_db.api.SQLAuthDBConnector',
                   return_value=self.auth_db_connector_mock)
        self.pyramid_config.registry.auth_query_api = AuthQueryAPI(sen.settings)
        self.pyramid_config.registry.auth_manage_api = AuthManageAPI(sen.settings)

    @staticmethod
    def basic_cases():
        request_params_base = dict(
            org_id=[u'example.com'],
            email=[u'foo@example.info'],
            actual_name=[u'Śome Ńąmę'],
            submitter_title=[u'CEO'],
            submitter_firstname_and_surname=[u'Marian Examplówski'],
            csr=[u'-----BEGIN CERTIFICATE REQUEST-----\nabc\n-----END CERTIFICATE REQUEST-----'],
        )
        expected_db_obj_attributes_base = dict(
            submitted_on=AnyInstanceOf(datetime.datetime),
            modified_on=AnyInstanceOf(datetime.datetime),
            status=REGISTRATION_REQUEST_STATUS_NEW,
            org_id=u'example.com',
            email=u'foo@example.info',
            actual_name=u'Śome Ńąmę',
            submitter_title=u'CEO',
            submitter_firstname_and_surname=u'Marian Examplówski',
            csr=u'-----BEGIN CERTIFICATE REQUEST-----\nabc\n-----END CERTIFICATE REQUEST-----',
        )
        yield (
            dict(request_params_base),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
            )),
        )
        yield (
            dict(
                request_params_base,
                notification_language=[u'EN'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_language=u'EN',
            )),
        )
        yield (
            dict(
                request_params_base,
                notification_emails=[u'foo@bar'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_addresses=[AnyInstanceOfWhoseVarsInclude(
                    models.RegistrationRequestEMailNotificationAddress,
                    email=u'foo@bar'),
                ],
            )),
        )
        yield (
            dict(
                request_params_base,
                notification_emails=[u'spam@ham', u'foo@bar'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_addresses=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestEMailNotificationAddress,
                        email=u'foo@bar',
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestEMailNotificationAddress,
                        email=u'spam@ham',
                    ),
                ],
            )),
        )
        yield (
            dict(
                request_params_base,
                notification_language=[u'EN'],
                notification_emails=[u'foo@bar'],
                asns=[u'42'],
                fqdns=[u'foo.example.org'],
                ip_networks=[u'1.2.3.4/24'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_language=u'EN',
                email_notification_addresses=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestEMailNotificationAddress,
                        email=u'foo@bar',
                    ),
                ],
                asns=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestASN,
                        asn=42,
                    ),
                ],
                fqdns=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestFQDN,
                        fqdn=u'foo.example.org',
                    ),
                ],
                ip_networks=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestIPNetwork,
                        ip_network=u'1.2.3.4/24',
                    ),
                ],
            )),
        )
        yield (
            dict(
                request_params_base,
                notification_language=[u'EN'],
                notification_emails=[u'spam@ham', u'foo@bar'],
                asns=[u'1.1', u'42', u'65537'],  # note: `1.1` and `65537` means the same
                fqdns=[u'foo.example.org', u'baz.ham', u'example.net'],
                ip_networks=[u'10.20.30.40/24', u'192.168.0.3/32'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_language=u'EN',
                email_notification_addresses=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestEMailNotificationAddress,
                        email=u'foo@bar',
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestEMailNotificationAddress,
                        email=u'spam@ham',
                    ),
                ],
                asns=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestASN,
                        asn=42,
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestASN,
                        asn=65537,
                    ),
                ],
                fqdns=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestFQDN,
                        fqdn=u'baz.ham',
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestFQDN,
                        fqdn=u'example.net',
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestFQDN,
                        fqdn=u'foo.example.org',
                    ),
                ],
                ip_networks=[
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestIPNetwork,
                        ip_network=u'10.20.30.40/24',
                    ),
                    AnyInstanceOfWhoseVarsInclude(
                        models.RegistrationRequestIPNetwork,
                        ip_network=u'192.168.0.3/32',
                    ),
                ],
            )),
        )

    @paramseq
    def ok_cases(cls):
        for str_values in (True, False):
            for whitespace_surrounded_values in (True, False):
                for unpacked_single_values in (True, False):
                    for request_params, expected_db_obj in cls.basic_cases():
                        if whitespace_surrounded_values:
                            request_params = {
                                key: [u' \t {} \n '.format(v) for v in val]
                                for key, val in request_params.iteritems()}
                        if str_values:
                            request_params = {
                                key: [v.encode('utf-8') for v in val]
                                for key, val in request_params.iteritems()}
                        if unpacked_single_values:
                            request_params = {
                                key: (val[0] if len(val) == 1
                                      else val)
                                for key, val in request_params.iteritems()}
                        yield param(
                                request_params=request_params,
                                expected_db_obj=expected_db_obj,
                            ).label('ok:{}{}{}/{}'.format(
                                's' if str_values else '-',
                                'u' if unpacked_single_values else '-',
                                'w' if whitespace_surrounded_values else '-',
                                len(request_params)))

    @foreach(ok_cases)
    def test_ok(self, request_params, expected_db_obj):
        req = self.create_request(N6RegistrationView, **request_params)
        response = req.perform()
        self._assert_response_ok(response)
        self._assert_db_operations_as_expected(expected_db_obj=expected_db_obj)

    # TODO: more cleaning error cases...
    @foreach(
        param(
            with_set={'org_id': u'blabla@not-valid'},
            with_deleted=(),
            expected_exc_type=ParamValueCleaningError,
        ),
        param(
            with_set={},
            with_deleted={'org_id'},
            expected_exc_type=ParamKeyCleaningError,
        ),
    )
    def test_kwargs_cleaning_error(self, with_set, with_deleted, expected_exc_type):
        request_params, _ = next(self.basic_cases())
        request_params.update(with_set)
        for key in with_deleted:
            del request_params[key]
        req = self.create_request(N6RegistrationView, **request_params)
        with self.assertRaises(expected_exc_type):
            req.perform()
        self._assert_db_not_touched()

    # TODO: more cleaning error cases...
    @foreach(
        param(
            exc_type_from_add=DataAPIError,
            expected_exc_type=AuthDatabaseAPIClientError,
        ).label('client data error'),
        param(
            exc_type_from_add=ZeroDivisionError,
            expected_exc_type=ZeroDivisionError,
        ).label('internal error'),
    )
    def test_later_error(self, exc_type_from_add, expected_exc_type):
        self.session_mock.add.side_effect = exc_type_from_add
        valid_request_params, _ = next(self.basic_cases())
        req = self.create_request(N6RegistrationView, **valid_request_params)
        with self.assertRaises(expected_exc_type):
            req.perform()
        self._assert_db_operations_as_expected(expected_exc_type=exc_type_from_add)

    def _assert_response_ok(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, 'ok')
        self.assertEqual(response.content_type, 'text/plain')
        self.assertEqual(response.charset, 'UTF-8')

    def _assert_db_operations_as_expected(self, expected_db_obj=None, expected_exc_type=None):
        self.assertEqual(self.auth_db_connector_mock.mock_calls, [
            call.__enter__(),
            call.get_current_session(),
            call.get_current_session().add(ANY),
            call.__exit__(expected_exc_type, ANY, ANY),
        ])
        if expected_db_obj is None:
            self.assertEqual(self.added_to_session, [])
        else:
            self.assertEqual(len(self.added_to_session), 1)
            self.assertEqual(self.added_to_session[0], expected_db_obj)

    def _assert_db_not_touched(self):
        self.assertEqual(self.auth_db_connector_mock.mock_calls, [])
        self.assertEqual(self.added_to_session, [])


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

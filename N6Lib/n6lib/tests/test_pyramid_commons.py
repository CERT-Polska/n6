# Copyright (c) 2013-2021 NASK. All rights reserved.

import datetime
import json
import os
import unittest
from unittest.mock import (
    ANY,
    Mock,
    MagicMock,
    call,
    patch,
    sentinel as sen,
)

from pyramid.response import Response
from pyramid.security import (
    Authenticated,
    Everyone,
)
from rt import RtError
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

import n6lib.auth_db.models as models
from n6lib.auth_db import ORG_REQUEST_STATUS_NEW
from n6lib.auth_db.api import (
    AuthDatabaseAPIClientError,
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
    AuthTktUserAuthenticationPolicy,
    DevFakeUserAuthenticationPolicy,
)
from n6lib.rt_client_api import (
    RTClientAPI,
    RTClientAPIError,
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
    DataFromClientError,
    ParamCleaningError,
    ParamKeyCleaningError,
    ParamValueCleaningError,
)


YES_BUT_IS_BLOCKED_ACCORDING_TO_AUTH_API_CACHE = (
    "<this marker means that the authenticated "
    "user, according to the `auth_api`'s cache, "
    "is blocked>")

YES_BUT_HAS_ANOTHER_ORG_ACCORDING_TO_AUTH_API_CACHE = (
    "<this marker means that the authenticated "
    "user, according to the `auth_api`'s cache, "
    "belongs to another org than in auth data>")

example_access_info_res_limits = {
    'queries_limit': None,
    'window': 3600,
    'request_parameters': None,
    'max_days_old': 100,
    'results_limit': None,
}
example_user_id = 'user@example.com'
example_org_id = 'org-id.example.com'
example_org_actual_name = 'Example Organization Name'

info_endpoint_cases = [
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
        },
        full_access=True,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': ['/search/events'],
            'certificate_fetched': True,
            'full_access': True,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    # `api_key_auth_enabled` is hidden if key authentication
    # stuff is disabled in the server's configuration
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
        },
        full_access=True,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=False,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': ['/search/events'],
            'certificate_fetched': True,
            'full_access': True,
            'authenticated': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
        },
        full_access=True,
        is_authenticated=YES_BUT_IS_BLOCKED_ACCORDING_TO_AUTH_API_CACHE,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': True,
            'full_access': True,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
        },
        full_access=True,
        is_authenticated=YES_BUT_HAS_ANOTHER_ORG_ACCORDING_TO_AUTH_API_CACHE,
        is_api_key_stuff_enabled_on_server=False,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': True,
            'full_access': True,
            'authenticated': True,
        },
    ),
    # `full_access` is hidden if False
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
            '/report/inside': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
                '/search/events',
            ],
            'certificate_fetched': False,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
            '/report/inside': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=YES_BUT_IS_BLOCKED_ACCORDING_TO_AUTH_API_CACHE,
        is_api_key_stuff_enabled_on_server=False,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': False,
            'authenticated': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
            '/report/inside': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=YES_BUT_HAS_ANOTHER_ORG_ACCORDING_TO_AUTH_API_CACHE,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': False,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,  # (but no '/report/inside' in `res_limits`)
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=False,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/search/events',
            ],
            'certificate_fetched': False,
            'authenticated': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,   # (but no non-empty 'search'
            '/report/inside': example_access_info_res_limits,   #  in `access_zone_conditions`)
        },
        access_zone_conditions={
            'search': [],
            'inside': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
            ],
            'certificate_fetched': False,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
            '/report/inside': example_access_info_res_limits,
            '/report/threats': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,
            'threats': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
                '/report/threats',
                '/search/events',
            ],
            'certificate_fetched': True,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    # if not authenticated, several items are hidden...
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
            '/report/inside': example_access_info_res_limits,
            '/report/threats': example_access_info_res_limits,
        },
        access_zone_conditions={
            'search': sen.list_of_conditions,
            'inside': sen.list_of_conditions,
            'threats': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=False,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=True,
        expected_response={
            'certificate_fetched': True,
            'authenticated': False,
        },
    ),
    param(
        res_limits={},
        access_zone_conditions={},
        full_access=False,
        is_authenticated=False,
        is_api_key_stuff_enabled_on_server=True,
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
        access_zone_conditions={},
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': False,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={    # (but `access_zone_conditions` is empty)
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={},
        full_access=True,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': False,
            'full_access': True,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={},
        access_zone_conditions={    # (but `res_limits` is empty)
            'search': sen.list_of_conditions,
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': True,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    param(
        res_limits={
            '/search/events': example_access_info_res_limits,
        },
        access_zone_conditions={
            'inside': sen.list_of_conditions,  # ('inside' does not match '/search/events')
        },
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=True,
        is_cert_available=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'certificate_fetched': False,
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
]


@expand
class TestN6InfoView(unittest.TestCase):

    api_method_name = 'get_user_info'
    info_res_id = '/info'
    mocked_context = sen.context
    expected_content_type = 'application/json'
    http_method = 'GET'

    class MockedAuthAPI(object):

        def __init__(self, is_authenticated, is_api_key_stuff_enabled_on_server, access_info):
            assert (isinstance(is_authenticated, bool)
                    or is_authenticated in {
                        YES_BUT_IS_BLOCKED_ACCORDING_TO_AUTH_API_CACHE,
                        YES_BUT_HAS_ANOTHER_ORG_ACCORDING_TO_AUTH_API_CACHE}), \
                f'unexpected test case data: is_authenticated={is_authenticated!a}'
            self.__is_authenticated = is_authenticated
            self.__is_api_key_stuff_enabled_on_server = is_api_key_stuff_enabled_on_server
            self.__access_info = access_info

        def get_access_info(self, auth_data):
            assert auth_data == {'org_id': example_org_id, 'user_id': example_user_id}
            assert self.__is_authenticated
            return self.__access_info

        def get_org_actual_name(self, auth_data):
            assert auth_data == {'org_id': example_org_id, 'user_id': example_user_id}
            assert self.__is_authenticated
            return example_org_actual_name

        def get_user_ids_to_org_ids(self):
            assert self.__is_authenticated
            result = {
                example_user_id: example_org_id,
                sen.random_user_id: sen.random_org_id,
            }
            if self.__is_authenticated == YES_BUT_IS_BLOCKED_ACCORDING_TO_AUTH_API_CACHE:
                del result[example_user_id]
            elif self.__is_authenticated == YES_BUT_HAS_ANOTHER_ORG_ACCORDING_TO_AUTH_API_CACHE:
                result[example_user_id] = sen.another_org_id
            return result

        def is_api_key_authentication_enabled(self):
            return self.__is_api_key_stuff_enabled_on_server

    class MockedRequest(object):

        def __init__(self, is_authenticated, is_cert_available, auth_api):
            self.registry = Mock()
            self.registry.auth_api = auth_api
            self.registry.data_backend_api = N6DataBackendAPI.__new__(N6DataBackendAPI)

            self.auth_data = (
                {'org_id': example_org_id, 'user_id': example_user_id}
                if is_authenticated
                else None)

            self.environ = {}
            if is_cert_available:
                self.environ[WSGI_SSL_ORG_ID_FIELD] = sen.ssl_org_id
                self.environ[WSGI_SSL_USER_ID_FIELD] = sen.ssl_user_id

    def _get_mocked_request(self,
                            res_limits,
                            access_zone_conditions,
                            full_access,
                            is_authenticated,
                            is_api_key_stuff_enabled_on_server,
                            is_cert_available):
        auth_api = self.MockedAuthAPI(
            is_authenticated,
            is_api_key_stuff_enabled_on_server,
            access_info=dict(
                rest_api_resource_limits=res_limits,
                access_zone_conditions=access_zone_conditions,
                rest_api_full_access=full_access))
        return self.MockedRequest(is_authenticated, is_cert_available, auth_api)

    def _get_view_instance(self, mocked_request):
        N6InfoView.resource_id = self.info_res_id
        N6InfoView.data_backend_api_method = self.api_method_name
        return N6InfoView(self.mocked_context, mocked_request)

    @foreach(info_endpoint_cases)
    def test_response(self,
                      res_limits,
                      access_zone_conditions,
                      full_access,
                      is_authenticated,
                      is_api_key_stuff_enabled_on_server,
                      is_cert_available,
                      expected_response):
        # TODO later: get rid of the `N6_PORTAL_AUTH_2021` env variable
        #             and of the following condition, together with the
        #             deprecated certificate-based auth, and with the
        #             `is_cert_available` arg (here and in the related
        #             helpers in this test class), and with the
        #             'certificate_fetched' item of the
        #             `expected_response` arg...
        if os.environ.get('N6_PORTAL_AUTH_2021'):
            expected_response.pop('certificate_fetched', None)
        mocked_request = self._get_mocked_request(res_limits,
                                                  access_zone_conditions,
                                                  full_access,
                                                  is_authenticated,
                                                  is_api_key_stuff_enabled_on_server,
                                                  is_cert_available)
        view_inst = self._get_view_instance(mocked_request)
        resp = view_inst.make_response()
        self.assertIsInstance(resp, Response)
        resp_body = json.loads(resp.body)
        self.assertDictEqual(resp_body, expected_response)
        self.assertEqual(resp.content_type, self.expected_content_type)
        self.assertEqual(resp.status_int, 200)

    def test_get_default_http_methods(self):
        self.assertEqual(self.http_method, N6InfoView.get_default_http_methods())


## TODO:
#class TestN6InfoConfigView
#class TestN6LoginView
#class TestN6LogoutView
#class ...


@expand
class TestN6RegistrationView(RequestHelperMixin, DBConnectionPatchMixin, unittest.TestCase):

    _REGISTRATION_REQUEST_ID = 'cdef0123456789abcdef0123456789abcdef'
    _RT_TICKET_ID = 42

    def setUp(self):
        self.added_to_session = []
        (self.auth_db_connector_mock,
         self.session_mock,
         self.db_obj_from_query_get_mock) = self._make_db_mocks()
        (self.rt_main_mock,
         self.rt_instance_mock) = self._make_rt_mocks()
        self.pyramid_config = self.prepare_pyramid_unittesting()
        self._set_up_auth_manage_api()

    def _make_db_mocks(self):
        auth_db_connector_mock = MagicMock()
        session_mock = auth_db_connector_mock.get_current_session.return_value
        session_mock.add.side_effect = self._session_mock_add_side_effect
        db_obj_from_query_get_mock = session_mock.query.return_value.get.return_value
        db_obj_from_query_get_mock.ticket_id = None
        return auth_db_connector_mock, session_mock, db_obj_from_query_get_mock

    def _session_mock_add_side_effect(self, actual_db_obj):
        self.assertIsInstance(actual_db_obj, models.RegistrationRequest)
        self.added_to_session.append(actual_db_obj)
        actual_db_obj.id = self._REGISTRATION_REQUEST_ID

    def _make_rt_mocks(self):
        rt_main_mock = MagicMock()
        rt_instance_mock = rt_main_mock.return_value
        rt_instance_mock.login.return_value = True    # (`True` indicates a successful log-in)
        rt_instance_mock.create_ticket.return_value = self._RT_TICKET_ID
        rt_instance_mock.logout.return_value = True   # (`True` indicates a successful log-out)
        return rt_main_mock, rt_instance_mock

    def _set_up_auth_manage_api(self):
        self.patch('n6lib.auth_db.api.SQLAuthDBConnector',
                   return_value=self.auth_db_connector_mock)
        self.pyramid_config.registry.auth_manage_api = AuthManageAPI(sen.settings)


    # (parametrized with `rt_settings` so must be called in test methods)
    def _set_up_rt_client_api(self, rt_settings):
        self.patch('n6lib.rt_client_api.Rt', self.rt_main_mock)
        self.pyramid_config.registry.rt_client_api = RTClientAPI(rt_settings)


    @staticmethod
    def basic_cases(use_rt):
        rt_settings = {
            'rt.active': ('yes' if use_rt else 'no'),
            'rt.rest_api_url': '<URL>',
            'rt.username': '<login>',
            'rt.password': '<password>',
            'rt.new_ticket_kind_to_fields_render_spec':
                r'''{'registration_requested': {
                 'Queue': '& {{ data_dict.asns|join(" & ") }} &',
                 'Text': '{{data_dict.email}}\n{{ data_dict["submitter_firstname_and_surname"] }}',
                }}''',
        }
        request_params_base = dict(
            org_id=[u'example.com'],
            email=[u'foo@example.info'],
            actual_name=[u'Śome , Ńąmę'],
            submitter_title=[u'CEO'],
            submitter_firstname_and_surname=[u'Marian <script>hax0r</script> Examplówski'],
            csr=[u'-----BEGIN CERTIFICATE REQUEST-----\nabc\n-----END CERTIFICATE REQUEST-----'],
        )
        expected_db_obj_attributes_base = dict(
            submitted_on=AnyInstanceOf(datetime.datetime),
            modified_on=AnyInstanceOf(datetime.datetime),
            status=ORG_REQUEST_STATUS_NEW,
            org_id=u'example.com',
            email=u'foo@example.info',
            actual_name=u'Śome , Ńąmę',
            submitter_title=u'CEO',
            submitter_firstname_and_surname=u'Marian <script>hax0r</script> Examplówski',
            csr=u'-----BEGIN CERTIFICATE REQUEST-----\nabc\n-----END CERTIFICATE REQUEST-----',
        )
        if use_rt:
            def get_expected_rt_calls(Queue='&  &'):
                return [
                    call(url='<URL>'),
                    call.__call__().login(login='<login>', password='<password>'),
                    call.__call__().create_ticket(
                        Queue=Queue,
                        Text='foo@example.info\n'
                             'Marian &lt;script&gt;hax0r&lt;/script&gt; Examplówski'),
                    call.__call__().logout(),
                ]
        else:
            def get_expected_rt_calls(**_kwargs):
                return []

        yield (
            dict(rt_settings),
            dict(request_params_base),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
            )),
            get_expected_rt_calls(),
        )
        yield (
            dict(rt_settings),
            dict(
                request_params_base,
                notification_language=[u'EN'],
            ),
            AnyInstanceOfWhoseVarsInclude(models.RegistrationRequest, **dict(
                expected_db_obj_attributes_base,
                email_notification_language=u'EN',
            )),
            get_expected_rt_calls(),
        )
        yield (
            dict(rt_settings),
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
            get_expected_rt_calls(),
        )
        yield (
            dict(rt_settings),
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
            get_expected_rt_calls(),
        )
        yield (
            dict(rt_settings),
            dict(
                request_params_base,
                notification_language=[u'EN'],
                notification_emails=[u'foo@bar'],
                asns=[u'99'],
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
                        asn=99,
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
            get_expected_rt_calls(Queue='& 99 &'),
        )
        yield (
            dict(rt_settings),
            dict(
                request_params_base,
                notification_language=[u'EN'],
                notification_emails=[u'spam@ham', u'foo@bar'],
                asns=[u'1.1', u'99', u'65537'],  # note: `1.1` and `65537` means the same
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
                        asn=99,
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
            get_expected_rt_calls(Queue='& 99 &amp; 65537 &'),
        )

    @paramseq
    def ok_cases(cls):
        for use_rt in (True, False):
            for whitespace_surrounded_values in (True, False):
                for unpacked_single_values in (True, False):
                    for (rt_settings,
                         request_params,
                         expected_db_obj,
                         expected_rt_calls) in cls.basic_cases(use_rt):
                        if whitespace_surrounded_values:
                            request_params = {
                                key: [u' \t {} \n '.format(v) for v in val]
                                for key, val in request_params.items()}
                        if unpacked_single_values:
                            request_params = {
                                key: (val[0] if len(val) == 1
                                      else val)
                                for key, val in request_params.items()}
                        yield param(
                            use_rt=use_rt,
                            rt_settings=rt_settings,
                            request_params=request_params,
                            expected_db_obj=expected_db_obj,
                            expected_rt_calls=expected_rt_calls,
                        ).label('ok:{}{}{}/{}'.format(
                            'r' if use_rt else '-',
                            'u' if unpacked_single_values else '-',
                            'w' if whitespace_surrounded_values else '-',
                            len(request_params)))

    @paramseq
    def use_rt_or_not(cls):
        for use_rt in (True, False):
            yield param(use_rt=use_rt)


    @foreach(ok_cases)
    def test_ok(self, use_rt, rt_settings, request_params, expected_db_obj, expected_rt_calls):
        self._set_up_rt_client_api(rt_settings)

        req = self.create_request(N6RegistrationView, **request_params)
        response = req.perform()

        self._assert_response_ok(response)
        self._assert_db_operations_as_expected(use_rt, expected_db_obj=expected_db_obj)
        self._assert_rt_operations_as_expected(expected_rt_calls=expected_rt_calls)


    # TODO: more cleaning error cases...
    @foreach(use_rt_or_not)
    @foreach(
        param(
            changing={'org_id': u'blabla@not-valid'},
            omitting=[],
            orig_exc_expected_instance_of=ParamValueCleaningError,
        ),
        param(
            changing={},
            omitting=['org_id'],
            orig_exc_expected_instance_of=ParamKeyCleaningError,
        ),
    )
    def test_request_params_cleaning_error(self, use_rt, changing, omitting,
                                           orig_exc_expected_instance_of):
        rt_settings, request_params, _, _ = next(self.basic_cases(use_rt))
        request_params.update(changing)
        for key in omitting:
            del request_params[key]
        self._set_up_rt_client_api(rt_settings)

        req = self.create_request(N6RegistrationView, **request_params)
        with self.assertRaises(AuthDatabaseAPIClientError) as exc_cm:
            req.perform()

        self._assert_db_not_really_touched()
        self._assert_rt_not_touched()
        exc = exc_cm.exception
        self.assertIsInstance(exc.orig_exc, orig_exc_expected_instance_of)
        self.assertEqual(exc.public_message, exc.orig_exc.public_message)


    # TODO: more db-related error cases...
    @foreach(use_rt_or_not)
    @foreach(
        param(
            exc_type_from_add=ParamCleaningError,
            expected_exc_type=AuthDatabaseAPIClientError,
        ).label('client data error - ParamCleaningError'),
        param(
            exc_type_from_add=DataFromClientError,
            expected_exc_type=AuthDatabaseAPIClientError,
        ).label('client data error - DataFromClientError'),
        param(
            exc_type_from_add=DataAPIError,
            expected_exc_type=DataAPIError,
        ).label('internal error - DataAPIError'),
        param(
            exc_type_from_add=ZeroDivisionError,
            expected_exc_type=ZeroDivisionError,
        ).label('internal error - some arbitrary'),
    )
    def test_db_related_error(self, use_rt, exc_type_from_add, expected_exc_type):
        self.session_mock.add.side_effect = exc_from_add = exc_type_from_add()
        assert type(exc_from_add) is exc_type_from_add, 'bug in test?'
        rt_settings, valid_request_params, _, _ = next(self.basic_cases(use_rt))
        self._set_up_rt_client_api(rt_settings)

        req = self.create_request(N6RegistrationView, **valid_request_params)
        with self.assertRaises(expected_exc_type) as exc_cm:
            req.perform()

        self._assert_db_operations_as_expected(use_rt, expected_exc_type=exc_type_from_add)
        self._assert_rt_not_touched()
        exc = exc_cm.exception
        if expected_exc_type is AuthDatabaseAPIClientError:
            assert issubclass(exc_type_from_add, DataFromClientError), 'bug in test?'
            self.assertIs(exc.orig_exc, exc_from_add)
            self.assertEqual(exc.public_message, exc_from_add.public_message)
        else:
            assert expected_exc_type is exc_type_from_add, 'bug in test?'
            self.assertIs(exc, exc_from_add)


    # TODO: more rt-related error cases...
    @foreach(
        param(
            # `-1` from `rt.create_ticket()` indicates a failure
            create_ticket_effect=lambda **_kwargs: -1,
            expected_exc_type=RTClientAPIError,
        ).label('rt non-exc error'),
        param(
            create_ticket_effect=RtError,
            expected_exc_type=RTClientAPIError,
        ).label('rt exc error'),
        param(
            create_ticket_effect=ZeroDivisionError,
            expected_exc_type=ZeroDivisionError,
        ).label('unspecific error'),
    )
    def test_rt_related_error(self, create_ticket_effect, expected_exc_type):
        self.rt_instance_mock.create_ticket.side_effect = create_ticket_effect
        use_rt = True
        (rt_settings,
         valid_request_params,
         expected_db_obj,
         expected_rt_calls) = next(self.basic_cases(use_rt))
        self._set_up_rt_client_api(rt_settings)

        req = self.create_request(N6RegistrationView, **valid_request_params)
        with self.assertRaises(expected_exc_type):
            req.perform()

        self._assert_db_operations_as_expected(use_rt,
                                               expected_db_obj=expected_db_obj,
                                               expected_exc_type=expected_exc_type)
        self._assert_rt_operations_as_expected(expected_rt_calls=expected_rt_calls)


    def _assert_response_ok(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{}')
        self.assertEqual(response.content_type, 'application/json')

    def _assert_db_operations_as_expected(self,
                                          use_rt,
                                          expected_db_obj=None,
                                          expected_exc_type=None):
        # The <AuthManageAPI instance>.create_registration_request(...)
        # call has been made, and within it...
        expected_db_connector_calls = [
            call.__enter__(),
            call.get_current_session(),
            call.get_current_session().add(ANY),
        ]
        if expected_db_obj is None:
            # The `db_session.add(...)` call raised an error...
            assert expected_exc_type is not None, 'bug in test?'
            self.assertEqual(self.added_to_session, [])
            self.assertIsNone(self.db_obj_from_query_get_mock.ticket_id)
        else:
            # A `RegistrationRequest` has been created and `.add()`-ed,
            # and `.flush()` has also been made...
            self.assertEqual(len(self.added_to_session), 1)
            self.assertEqual(self.added_to_session[0], expected_db_obj)
            expected_db_connector_calls.extend([
                call.get_current_session(),
                call.get_current_session().flush(),
            ])
            if use_rt and expected_exc_type is None:
                # RT is in use
                # *and* the
                #     <AuthManageAPI instance>.create_registration_request(...) and
                #     <RTClientAPI instance (mock)>.new_ticket(...) and
                #     <AuthManageAPI instance>.set_registration_request_ticket_id(
                #         <RegistrationRequest id>,
                #         <RT ticket id coerced to str>)
                # calls have been made...
                expected_db_connector_calls.extend([
                    call.get_current_session(),
                    call.get_current_session().query(
                        models.RegistrationRequest),
                    call.get_current_session().query().get(
                        self._REGISTRATION_REQUEST_ID),
                ])
                # ...so the RT ticket id has been successfully stored
                # in the Auth DB -- in the `ticket_id` field of the
                # previously created `registration_request` record.
                self.assertEqual(self.db_obj_from_query_get_mock.ticket_id,
                                 str(self._RT_TICKET_ID))
            else:
                # No RT ticket id has been stored in the Auth DB.
                self.assertIsNone(self.db_obj_from_query_get_mock.ticket_id)
        expected_db_connector_calls.append(call.__exit__(expected_exc_type, ANY, ANY))
        self.assertEqual(self.auth_db_connector_mock.mock_calls, expected_db_connector_calls)

    def _assert_db_not_really_touched(self):
        self.assertEqual(self.auth_db_connector_mock.mock_calls, [
            call.__enter__(),
            call.__exit__(ANY, ANY, ANY),
        ])
        self.assertEqual(self.added_to_session, [])
        self.assertIsNone(self.db_obj_from_query_get_mock.ticket_id)

    def _assert_rt_operations_as_expected(self, expected_rt_calls):
        self.assertEqual(self.rt_main_mock.mock_calls, expected_rt_calls)

    def _assert_rt_not_touched(self):
        self.assertEqual(self.rt_main_mock.mock_calls, [])


@expand
class TestInstantiationOfAuthenticationPolicies(unittest.TestCase):

    _param_policy_class = [
        param(policy_class=BaseUserAuthenticationPolicy),
        param(policy_class=SSLUserAuthenticationPolicy),
        param(policy_class=AuthTktUserAuthenticationPolicy),
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
        request.unauthenticated_userid = 'some_org_id,some_login'
        api = request.registry.auth_manage_api
        api.__enter__.return_value = api
        api.do_nonblocked_user_and_org_exist_and_match.return_value = True
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertEqual(result, dict(
            org_id='some_org_id',
            user_id='some_login',
        ))
        self.assertEqual(api.mock_calls, [
            call.__enter__(),
            call.do_nonblocked_user_and_org_exist_and_match('some_login', 'some_org_id'),
            call.__exit__(None, None, None),
        ])

    def test__get_auth_data__unauthenticated_userid_is_None(self):
        request = MagicMock()
        request.unauthenticated_userid = None
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertIsNone(result)
        self.assertEqual(request.mock_calls, [])

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__get_auth_data__false_from_auth_manage_api(self, LOGGER_warning_mock):
        request = MagicMock()
        request.unauthenticated_userid = 'some_org_id,some_login'
        api = request.registry.auth_manage_api
        api.__enter__.return_value = api
        api.do_nonblocked_user_and_org_exist_and_match.return_value = False
        result = BaseUserAuthenticationPolicy.get_auth_data(request)
        self.assertIsNone(result)
        self.assertEqual(api.mock_calls, [
            call.__enter__(),
            call.do_nonblocked_user_and_org_exist_and_match('some_login', 'some_org_id'),
            call.__exit__(None, None, None),
        ])
        self.assertEqual(LOGGER_warning_mock.mock_calls, [
            call(
                'Failed to find non-blocked user whose organization id is '
                '%a and login (user id) is %a', 'some_org_id', 'some_login',
            ),
        ])

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
        super_effective_principals = super(cls, cls).effective_principals
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
                         [call('Comma in user_id %a.', 'user,name4')])

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__unauthenticated_userid__comma_in_org_id(self, LOGGER_warning_mock):
        request = MagicMock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname,5', 'SSL_CLIENT_S_DN_CN': 'username5'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls,
                         [call('Comma in org_id %a.', 'orgname,5')])

    def test_other_important_methods_are_from_BaseUserAuthenticationPolicy(self):
        self.assertIs(SSLUserAuthenticationPolicy.get_auth_data,
                      BaseUserAuthenticationPolicy.get_auth_data)
        self.assertIs(SSLUserAuthenticationPolicy.authenticated_userid,
                      BaseUserAuthenticationPolicy.authenticated_userid)
        self.assertIs(SSLUserAuthenticationPolicy.effective_principals,
                      BaseUserAuthenticationPolicy.effective_principals)



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

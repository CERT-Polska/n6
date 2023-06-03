# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
import json
import unittest
from contextlib import contextmanager
from unittest.mock import (
    ANY,
    Mock,
    MagicMock,
    call,
    patch,
    sentinel as sen,
)

from jwt.exceptions import DecodeError
from pyramid.httpexceptions import (
    HTTPForbidden,
    HTTPUnauthorized,
)
from pyramid.response import Response
from pyramid.request import Request
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
from n6lib.auth_api import AuthAPI
from n6lib.auth_db import ORG_REQUEST_STATUS_NEW
from n6lib.auth_db.api import (
    AuthDatabaseAPIClientError,
    AuthDatabaseAPILookupError,
    AuthManageAPI,
)
from n6lib.config import ConfigError
from n6lib.const import (
    WSGI_SSL_ORG_ID_FIELD,
    WSGI_SSL_USER_ID_FIELD,
)
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.oidc_provider_api import (
    OIDCProviderAPI,
    TokenValidationError,
)
from n6lib.pyramid_commons import (
    N6InfoView,
    N6LoginOIDCView,
    N6RegistrationView,
    BaseUserAuthenticationPolicy,
    OIDCUserAuthenticationPolicy,
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': ['/search/events'],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': ['/search/events'],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
                '/search/events',
            ],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/search/events',
            ],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
            ],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [
                '/report/inside',
                '/report/threats',
                '/search/events',
            ],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'authenticated': False,
        },
    ),
    param(
        res_limits={},
        access_zone_conditions={},
        full_access=False,
        is_authenticated=False,
        is_api_key_stuff_enabled_on_server=True,
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
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
        is_knowledge_base_stuff_enabled_on_server=False,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'authenticated': True,
            'api_key_auth_enabled': True,
        },
    ),
    # if user is authenticated and knowledge base is enabled
    # `knowledge_base_enabled` is shown and equals `True`
    param(
        res_limits={},
        access_zone_conditions={},
        full_access=False,
        is_authenticated=True,
        is_api_key_stuff_enabled_on_server=False,
        is_knowledge_base_stuff_enabled_on_server=True,
        expected_response={
            'org_id': example_org_id,
            'org_actual_name': example_org_actual_name,
            'available_resources': [],
            'authenticated': True,
            'knowledge_base_enabled': True,
        },
    ),
    # if user is not authenticated and knowledge base is enabled
    # `knowledge_base_enabled` is not shown
    param(
        res_limits={},
        access_zone_conditions={},
        full_access=False,
        is_authenticated=False,
        is_api_key_stuff_enabled_on_server=False,
        is_knowledge_base_stuff_enabled_on_server=True,
        expected_response={
            'authenticated': False,
        },
    ),
]


@expand
class TestN6InfoView(unittest.TestCase):

    api_method_name = 'get_user_info'
    info_res_id = '/info'
    context_dummy = sen.context
    expected_content_type = 'application/json'
    http_method = 'GET'

    class AuthAPIStub(object):

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

    class RequestStub(object):

        def __init__(self, is_authenticated, auth_api):
            self.registry = Mock()
            self.registry.auth_api = auth_api
            self.registry.data_backend_api = N6DataBackendAPI.__new__(N6DataBackendAPI)

            self.auth_data = (
                {'org_id': example_org_id, 'user_id': example_user_id}
                if is_authenticated
                else None)

    def _get_request_stub(self,
                          res_limits,
                          access_zone_conditions,
                          full_access,
                          is_authenticated,
                          is_api_key_stuff_enabled_on_server):
        auth_api = self.AuthAPIStub(
            is_authenticated,
            is_api_key_stuff_enabled_on_server,
            access_info=dict(
                rest_api_resource_limits=res_limits,
                access_zone_conditions=access_zone_conditions,
                rest_api_full_access=full_access))
        return self.RequestStub(is_authenticated, auth_api)

    def _get_view_instance(self, request_stub):
        N6InfoView.resource_id = self.info_res_id
        N6InfoView.data_backend_api_method = self.api_method_name
        return N6InfoView(self.context_dummy, request_stub)

    @foreach(info_endpoint_cases)
    def test_response(self,
                      res_limits,
                      access_zone_conditions,
                      full_access,
                      is_authenticated,
                      is_api_key_stuff_enabled_on_server,
                      is_knowledge_base_stuff_enabled_on_server,
                      expected_response):
        request_stub = self._get_request_stub(
            res_limits,
            access_zone_conditions,
            full_access,
            is_authenticated,
            is_api_key_stuff_enabled_on_server)
        view_inst = self._get_view_instance(request_stub)
        with patch('n6lib.pyramid_commons._pyramid_commons._AbstractKnowledgeBaseRelatedView.'
                   'is_knowledge_base_enabled',
                    return_value=is_knowledge_base_stuff_enabled_on_server):
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
            terms_version=[u'Zażółć #2'],
            terms_lang=[u'PL'],
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
            terms_version=u'Zażółć #2',
            terms_lang=u'PL',
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
            changing={'email': 'USEr@example.com'},  # (not valid: disallowed uppercase)
            omitting=[],
            orig_exc_expected_instance_of=ParamValueCleaningError,
        ),
        param(
            changing={'org_id': 'blabla@not-valid'},  # (not a valid org id)
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


class TestN6LoginOIDCView(RequestHelperMixin, DBConnectionPatchMixin, unittest.TestCase):

    SAMPLE_OIDC_PROVIDER_CONFIG = {
        'oidc_provider_api': {
            'active': 'true',
            'server_url': 'http://example.com/keycloak',
            'realm_name': 'test_realm',
            'client_id': 'test',
            'client_secret_key': 'secret',
        },
    }
    SAMPLE_USER_ID = 'test@example.com'
    USER_ID_NOT_IN_DB = 'other@example.com'
    SAMPLE_ORG_ID = 'example.com'
    ORG_ID_NOT_IN_DB = 'example.org'
    SAMPLE_AUTH_DATA = dict(user_id=SAMPLE_USER_ID, org_id=SAMPLE_ORG_ID)

    def setUp(self):
        self.db_connector_patch = self.patch('n6lib.auth_db.api.SQLAuthDBConnector')
        self._collection = self._get_mock_db_collection()
        self._session_state = {}
        self.make_patches(self._collection, self._session_state)
        self.pyramid_config = self.prepare_pyramid_unittesting()
        self._set_up_auth_manage_api()
        self._set_up_oidc_provider_api()

    def patch_db_connector(self, session_mock):
        self.db_connector_patch.return_value.get_current_session.return_value = session_mock

    @classmethod
    def get_concrete_view_class_kwargs(cls, view_class, request):
        config_mock = Mock()
        return dict(resource_id='mock_resource_id', pyramid_configurator=config_mock)

    def _get_mock_db_collection(self):
        sample_user = models.User(login=self.SAMPLE_USER_ID, org_id=self.SAMPLE_ORG_ID)
        sample_org = models.Org(org_id=self.SAMPLE_ORG_ID, users=[sample_user])
        return {
            'user': [
                sample_user,
            ],
            'org': [
                sample_org,
            ],
        }

    def _set_up_auth_manage_api(self):
        self.pyramid_config.registry.auth_manage_api = AuthManageAPI(sen.settings)

    def _set_up_oidc_provider_api(self):
        with patch('n6lib.config.Config._load_n6_config_files',
                   return_value=self.SAMPLE_OIDC_PROVIDER_CONFIG),\
                patch('n6lib.oidc_provider_api.KeycloakOpenID') as provider_mock:
            provider_mock.return_value.certs.return_value = dict(keys={})
            self.pyramid_config.registry.oidc_provider_api = OIDCProviderAPI()
            self.oidc_provider_api = self.pyramid_config.registry.oidc_provider_api

    def _assert_json_response_attrs(self, response, status_code, json_body):
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response.json_body, json_body)
        self.assertEqual(response.content_type, 'application/json')

    def _test_user_not_created(self, user_id, org_id):
        request = self.create_request(N6LoginOIDCView)
        request.auth_data = None
        self.oidc_provider_api.unauthenticated_credentials.user_id = user_id
        self.oidc_provider_api.unauthenticated_credentials.org_id = org_id
        response = request.perform()
        self._assert_json_response_attrs(response, 403, {'status': 'user_not_created'})
        self.assertEqual(1, len(self._collection['user']))
        self.session_mock.flush.assert_not_called()

    def test_valid_auth_data(self):
        request = self.create_request(N6LoginOIDCView)
        request.auth_data = self.SAMPLE_AUTH_DATA
        response = request.perform()
        self._assert_json_response_attrs(response, 200, {'status': 'logged_in'})

    def test_no_temporary_credentials(self):
        request = self.create_request(N6LoginOIDCView)
        request.auth_data = None
        with self.assertRaises(HTTPForbidden):
            request.perform()

    def test_create_user_ok(self):
        request = self.create_request(N6LoginOIDCView)
        request.auth_data = None
        self.oidc_provider_api.unauthenticated_credentials.user_id = self.USER_ID_NOT_IN_DB
        self.oidc_provider_api.unauthenticated_credentials.org_id = self.SAMPLE_ORG_ID
        response = request.perform()
        self._assert_json_response_attrs(response, 200, {'status': 'user_created'})
        self.assertEqual(2, len(self._collection['user']))
        new_user = self._collection['user'][-1]
        self.assertEqual(self.USER_ID_NOT_IN_DB, new_user.login)
        self.assertEqual(self.SAMPLE_ORG_ID, new_user.org.org_id)
        self.session_mock.flush.assert_called_once()

    def test_create_user__user_exists(self):
        self._test_user_not_created(self.SAMPLE_USER_ID, self.SAMPLE_ORG_ID)

    def test_create_user__org_not_exists(self):
        self._test_user_not_created(self.SAMPLE_USER_ID, self.ORG_ID_NOT_IN_DB)

    def test_oidc_provider_api_inactive(self):
        request = self.create_request(N6LoginOIDCView)
        self.oidc_provider_api.is_active = False
        request.auth_data = None
        with self.assertRaises(HTTPForbidden):
            request.perform()


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

    def _make_request_mock(self):
        request = MagicMock()
        request.registry.auth_manage_api.adjust_if_is_legacy_user_login = \
            AuthManageAPI.adjust_if_is_legacy_user_login
        return request

    def test__unauthenticated_userid__ok(self):
        request = self._make_request_mock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname', 'SSL_CLIENT_S_DN_CN': 'LogIn@mail'}
        result = self.meth.unauthenticated_userid(request)
        expected_result = 'orgname,login@mail'  # (note the lower-cased "login" part)
        self.assertEqual(result, expected_result)

    def test__unauthenticated_userid__user_id_is_None(self):
        request = self._make_request_mock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname', 'SSL_CLIENT_S_DN_CN': None}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)

    def test__unauthenticated_userid__org_id_is_None(self):
        request = self._make_request_mock()
        request.environ = {'SSL_CLIENT_S_DN_O': None, 'SSL_CLIENT_S_DN_CN': 'LogIn@mail'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__unauthenticated_userid__comma_in_user_id(self, LOGGER_warning_mock):
        request = self._make_request_mock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'orgname', 'SSL_CLIENT_S_DN_CN': 'Log,In@mail'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls,
                         [call('Comma in user_id %a.', 'Log,In@mail')])

    @patch('n6lib.pyramid_commons._pyramid_commons.LOGGER.warning')
    def test__unauthenticated_userid__comma_in_org_id(self, LOGGER_warning_mock):
        request = self._make_request_mock()
        request.environ = {'SSL_CLIENT_S_DN_O': 'org,name', 'SSL_CLIENT_S_DN_CN': 'LogIn@mail'}
        result = self.meth.unauthenticated_userid(request)
        self.assertIsNone(result)
        self.assertEqual(LOGGER_warning_mock.mock_calls,
                         [call('Comma in org_id %a.', 'org,name')])

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



class TestOIDCUserAuthenticationPolicy(unittest.TestCase):

    SAMPLE_CLIENT_ID = 'example'
    SAMPLE_VALID_TOKEN = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxkZX'
                          'IiLCJpYXQiOjE2NzMzNTc3NTMsImV4cCI6MTcwNDg5Mzc1MywiYXVkIjoid3d3LmV4YW1wb'
                          'GUuY29tIiwic3ViIjoianJvY2tldEBleGFtcGxlLmNvbSIsIkdpdmVuTmFtZSI6IkpvaG5u'
                          'eSIsIlN1cm5hbWUiOiJSb2NrZXQiLCJFbWFpbCI6Impyb2NrZXRAZXhhbXBsZS5jb20iLCJ'
                          'Sb2xlIjpbIk1hbmFnZXIiLCJQcm9qZWN0IEFkbWluaXN0cmF0b3IiXX0.jK9voJzP_DONJ6'
                          'aBVtMYIASArGLuoCbTqUDM0htWXj8')
    MISSING_CLAIMS_TOKEN = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxk'
                            'ZXIiLCJpYXQiOjE2NzM1Mjk0MDAsImV4cCI6MTcwNTA2NTQwMCwiYXVkIjoid3d3LmV4Y'
                            'W1wbGUuY29tIiwic3ViIjoiZGprZmtAZmRqaWsuY29tIiwiR2l2ZW5OYW1lIjoiVG9tbX'
                            'kiLCJTdXJuYW1lIjoiUm9ja2V0IiwiRW1haWwiOiJqcm9ja2V0QGV4YW1wbGUuY29tIiw'
                            'iUm9sZSI6WyJNYW5hZ2VyIiwiUHJvamVjdCBBZG1pbmlzdHJhdG9yIl19.GMn4WKDtBLC'
                            'QT608_UFNVj853V3yHVy2b6yG3HKz9ao')
    USER_NOT_IN_DB_TOKEN = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxk'
                            'ZXIiLCJpYXQiOjE2NzM1Mjk0MDAsImV4cCI6MTcwNTA2NTQwMCwiYXVkIjoiZGZrbHNqZ'
                            'i5vcmciLCJzdWIiOiJkamtma0BmZGppay5jb20iLCJHaXZlbk5hbWUiOiJUb21teSIsIl'
                            'N1cm5hbWUiOiJSb2NrZXQiLCJFbWFpbCI6Impyb2NrZXRAZXhhbXBsZS5jb20iLCJSb2x'
                            'lIjpbIk1hbmFnZXIiLCJQcm9qZWN0IEFkbWluaXN0cmF0b3IiXX0.zJ8kKFMU1P0q7wnS'
                            'CPA6wk4RVOi35Mj95cBinUZPcvI')
    DIFFERENT_ORG_ID_TOKEN = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJPbmxpbmUgSldUIEJ1aW'
                              'xkZXIiLCJpYXQiOjE2NzM1Mjk0MDAsImV4cCI6MTcwNTA2NTQwMCwiYXVkIjoiZGZhZ'
                              'nNmc2Rmc2Rmc2RmLm9yZyIsInN1YiI6ImRqa2ZrQGZkamlrLmNvbSIsIkdpdmVuTmFt'
                              'ZSI6IlRvbW15IiwiU3VybmFtZSI6IlJvY2tldCIsIkVtYWlsIjoianJvY2tldEBleGF'
                              'tcGxlLmNvbSIsIlJvbGUiOlsiTWFuYWdlciIsIlByb2plY3QgQWRtaW5pc3RyYXRvci'
                              'JdfQ.sdzkt77k6ajF6OYwyTzHJTRoUMJ4CaWy4ZhU98iwBEM')
    EMPTY_HEADERS_TOKEN = ('eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJPbmxpbmUgSldUIEJ1aWxkZ'
                           'XIiLCJpYXQiOjE2NzM1Mjk0MDAsImV4cCI6MTcwNTA2NTQwMCwiYXVkIjoid3d3LmV4YW1'
                           'wbGUuY29tIiwic3ViIjoianJvY2tldEBleGFtcGxlLmNvbSIsIkdpdmVuTmFtZSI6Ikpva'
                           'G5ueSIsIlN1cm5hbWUiOiJSb2NrZXQiLCJFbWFpbCI6Impyb2NrZXRAZXhhbXBsZS5jb20'
                           'iLCJSb2xlIjpbIk1hbmFnZXIiLCJQcm9qZWN0IEFkbWluaXN0cmF0b3IiXX0.fW5DJ8sxB'
                           'nMMbFeir9nSGvDM32S8XJnOR1GHvPmkRcM')
    SAMPLE_VALID_MERGED_CREDENTIALS = 'example.com,test@example.com'
    SAMPLE_AUTH_DATA = dict(user_id='test@example.com', org_id='example.com')
    TOKENS_MAP = [
        {
            'token': SAMPLE_VALID_TOKEN,
            'headers': {
                'alg': 'RS256',
                'typ': 'JWT',
                'kid': 'aVR2rFvXc57uEnZq3dbwxJ94WIthUg1poGLfAy6lYHP',
            },
            'claims': {
                'name': 'Thomas Kowalski',
                'preferred_username': 'test@example.com',
                'org_name': 'example.com',
                'email': 'test@example.com',
            },
        },
        # the token is valid, but user does not exist in database
        {
            'token': USER_NOT_IN_DB_TOKEN,
            'headers': {
                'alg': 'RS256',
                'typ': 'JWT',
                'kid': 'aVR2rFvXc57uEnZq3dbwxJ94WIthUg1poGLfAy6lYHP',
            },
            'claims': {
                'name': 'Bernice Foley',
                'preferred_username': 'bernice@example.com',
                'org_name': 'example.com',
                'email': 'bernice@example.com',
            },
        },
        # the token is valid, but user is assigned to a different
        # organization than it is claimed in token
        {
            'token': DIFFERENT_ORG_ID_TOKEN,
            'headers': {
                'alg': 'RS256',
                'typ': 'JWT',
                'kid': 'aVR2rFvXc57uEnZq3dbwxJ94WIthUg1poGLfAy6lYHP',
            },
            'claims': {
                'name': 'Oliver Case',
                'preferred_username': 'oliver@example.com',
                'org_name': 'example.com',
                'email': 'oliver@example.com',
            },
        },
        {
            'token': MISSING_CLAIMS_TOKEN,
            'headers': {
            'alg': 'RS256',
            'typ': 'JWT',
            'kid': 'gxf5sJqkLbOuPrijMY1n09R2SoEdAQVcwhW76vDZNl4',
        },
        # the 'org_name' claim is missing
            'claims': {
                'name': 'John Smith',
                'preferred_username': 'john@example.org',
                'email': 'john@example.org',
            },
        },
        {
            'token': EMPTY_HEADERS_TOKEN,
            'headers': {},
            'claims': None,
        },
    ]
    SAMPLE_JWKS = {
        'aVR2rFvXc57uEnZq3dbwxJ94WIthUg1poGLfAy6lYHP': sen.jwk0,
        'gxf5sJqkLbOuPrijMY1n09R2SoEdAQVcwhW76vDZNl4': sen.jwk1,
    }

    def setUp(self):
        with patch('n6lib.pyramid_commons._pyramid_commons.Config') as config_mock:
            config_mock.section.return_value = {'dev_fake_auth': False}
            self.inst = OIDCUserAuthenticationPolicy.__new__(OIDCUserAuthenticationPolicy, None)
        self.inst._auth_tkt_policy = self._get_auth_tkt_policy_mock()
        self._request_registry_mock = MagicMock()
        self.request_mock = Mock(spec=Request,
                                 auth_data=None,
                                 headers={},
                                 registry=self._request_registry_mock)
        self.request_mock.route_url.side_effect = lambda url: url

    def test__unauthenticated_userid__ok(self):
        self.request_mock.authorization.authtype = 'Bearer'
        self.request_mock.authorization.params = self.SAMPLE_VALID_TOKEN
        self.request_mock.headers = self._get_sample_authorization_header()
        userid = self.inst.unauthenticated_userid(self.request_mock)
        self.assertEqual(f'access_token:{self.SAMPLE_VALID_TOKEN}', userid)
        self.inst._auth_tkt_policy.unauthenticated_userid.assert_not_called()

    def test__unauthenticated_userid__no_header(self):
        self.request_mock.authorization.authtype = 'Bearer'
        self.request_mock.authorization.params = self.SAMPLE_VALID_TOKEN
        self._test__auth_tkt_unauthenticated_userid_called()

    def test__unauthenticated_userid__no_authorization_attr(self):
        self.request_mock.authorization.return_value = None
        self._test__auth_tkt_unauthenticated_userid_called()

    def test__unauthenticated_userid__oidc_api_inactive(self):
        self._request_registry_mock.oidc_provider_api.is_active = False
        self._test__auth_tkt_unauthenticated_userid_called()

    def test__effective_principals__with_auth_header__auth_data(self):
        self.request_mock.headers = self._get_sample_authorization_header()
        self.request_mock.auth_data = self.SAMPLE_AUTH_DATA
        effective_principals = self.inst.effective_principals(self.request_mock)
        self.assertIn(Everyone, effective_principals)
        self.assertIn(Authenticated, effective_principals)
        self.assertIn(self.SAMPLE_VALID_MERGED_CREDENTIALS, effective_principals)

    def test__effective_principals__with_auth_header__no_auth_data(self):
        self.request_mock.headers = self._get_sample_authorization_header()
        effective_principals = self.inst.effective_principals(self.request_mock)
        self.assertIn(Everyone, effective_principals)

    def test__effective_principals__without_auth_header(self):
        effective_principals = self.inst.effective_principals(self.request_mock)
        self.assertIsInstance(effective_principals, Mock)
        self.inst._auth_tkt_policy.effective_principals.assert_called_once()

    def test__effective_principals__with_auth_header__oidc_api_inactive(self):
        self._request_registry_mock.oidc_provider_api.is_active = False
        effective_principals = self.inst.effective_principals(self.request_mock)
        self.assertIsInstance(effective_principals, Mock)
        self.inst._auth_tkt_policy.effective_principals.assert_called_once()

    def test__get_auth_data__ok(self):
        with self._prepare__get_auth_data_mocks(self.SAMPLE_VALID_TOKEN):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertEqual(self.SAMPLE_AUTH_DATA, auth_data)

    def test__get_auth_data__missing_claims(self):
        with self._prepare__get_auth_data_mocks(self.MISSING_CLAIMS_TOKEN):
            with self.assertRaises(HTTPUnauthorized):
                self.inst.get_auth_data(self.request_mock)

    def test__get_auth_data__user_not_in_db(self):
        with self._prepare__get_auth_data_mocks(self.USER_NOT_IN_DB_TOKEN):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertIsNone(auth_data)

    def test__get_auth_data__user_not_in_db__oidc_login_url(self):
        self.request_mock.url = '/login/oidc'
        with self._prepare__get_auth_data_mocks(self.USER_NOT_IN_DB_TOKEN):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertIsNone(auth_data)
            saved_user_id =\
                self._request_registry_mock.oidc_provider_api.unauthenticated_credentials.user_id
            saved_org_id =\
                self._request_registry_mock.oidc_provider_api.unauthenticated_credentials.org_id
            self.assertEqual('bernice@example.com', saved_user_id)
            self.assertEqual('example.com', saved_org_id)

    def test__get_auth_data__different_org_id(self):
        with self._prepare__get_auth_data_mocks(self.DIFFERENT_ORG_ID_TOKEN):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertIsNone(auth_data)

    def test__get_auth_data__empty_headers(self):
        # no 'kid' header in token headers
        with self._prepare__get_auth_data_mocks(self.EMPTY_HEADERS_TOKEN):
            with self.assertRaises(HTTPUnauthorized):
                self.inst.get_auth_data(self.request_mock)

    def test__get_auth_data__no_token(self):
        with self._prepare__get_auth_data_mocks(None):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertEqual(self.SAMPLE_AUTH_DATA, auth_data)

    def test__get_auth_data__oidc_api_inactive(self):
        with self._prepare__get_auth_data_mocks(None, is_oidc_active=False):
            auth_data = self.inst.get_auth_data(self.request_mock)
            self.assertEqual(self.SAMPLE_AUTH_DATA, auth_data)

    def _get_auth_tkt_policy_mock(self):
        m = Mock()
        m.unauthenticated_userid.return_value = self.SAMPLE_VALID_MERGED_CREDENTIALS
        return m

    def _get_sample_authorization_header(self):
        return {'Authorization': f'Bearer {self.SAMPLE_VALID_TOKEN}'}

    def _test__auth_tkt_unauthenticated_userid_called(self):
        userid = self.inst.unauthenticated_userid(self.request_mock)
        self.assertEqual(self.SAMPLE_VALID_MERGED_CREDENTIALS, userid)
        self.inst._auth_tkt_policy.unauthenticated_userid.assert_called_once()

    @contextmanager
    def _prepare__get_auth_data_mocks(self, token, is_oidc_active=True):
        self._request_registry_mock.oidc_provider_api = Mock(spec=OIDCProviderAPI)
        self._request_registry_mock.oidc_provider_api.client_id = self.SAMPLE_CLIENT_ID
        self._request_registry_mock.oidc_provider_api.unauthenticated_credentials = Mock()
        self._request_registry_mock.oidc_provider_api.is_active = is_oidc_active
        oidc_provider_self_mock = Mock()
        oidc_provider_self_mock._get_json_web_keys.return_value = self.SAMPLE_JWKS
        self._request_registry_mock.oidc_provider_api.get_signing_key_from_token.side_effect =\
            self._get__get_signing_key_from_token_meth(oidc_provider_self_mock)
        self._request_registry_mock.auth_api.authenticate_with_oidc_access_token.side_effect =\
            self._get__authenticate_with_oidc_access_token_meth()
        self._request_registry_mock.auth_manage_api.__enter__.return_value.\
            do_nonblocked_user_and_org_exist_and_match.side_effect = \
            self._do_nonblocked_user_and_org_exist_and_match_side_effect
        self.request_mock.unauthenticated_userid = (f'access_token:{token}' if token
                                                    else self.SAMPLE_VALID_MERGED_CREDENTIALS)
        patchers = []
        jwt__get_unverified_header_patch = patch('jwt.get_unverified_header',
              side_effect=self._jwt__get_unverified_header__side_effect)
        patchers.append(jwt__get_unverified_header_patch)
        jwt__decode_patch = patch('jwt.decode', side_effect=self._jwt__decode__side_effect)
        patchers.append(jwt__decode_patch)
        patch_instances = {
            'get_unverified_header': jwt__get_unverified_header_patch.start(),
            'decode': jwt__decode_patch.start(),
        }
        yield patch_instances
        for p in patchers:
            p.stop()

    @staticmethod
    def _get__get_signing_key_from_token_meth(self_mock):
        mp = MethodProxy(OIDCProviderAPI, self_mock)
        return mp.get_signing_key_from_token

    @staticmethod
    def _get__authenticate_with_oidc_access_token_meth():
        inst = AuthAPI.__new__(AuthAPI)
        return inst.authenticate_with_oidc_access_token

    @classmethod
    def _do_nonblocked_user_and_org_exist_and_match_side_effect(cls, *args, **kwargs):
        inst = Mock()
        inst._get_user_by_login.side_effect = cls._get_user_by_login_side_effect
        return AuthManageAPI.do_nonblocked_user_and_org_exist_and_match(inst, *args, **kwargs)

    def _jwt__get_unverified_header__side_effect(self, token):
        for token_attrs in self.TOKENS_MAP:
            if token == token_attrs['token']:
                return token_attrs['headers']
        else:
            self.fail("The `jwt.get_unverified_header()` method's patch could not find "
                      "the token passed as argument in the test fixtures")

    def _jwt__decode__side_effect(self, token, key, *args, **kwargs):
        # The `key` parameter passes a JSON Web Key, which normally
        # is used to decode the token in the patched
        # `decode()` method. It is fetched by
        # `get_signing_key_from_token()` method
        # of `n6lib.oidc_provider_api.OIDCProviderAPI` instance (called
        # by `get_auth_data()` policy method).
        for token_attrs in self.TOKENS_MAP:
            if token == token_attrs['token'] and token_attrs['claims'] is not None:
                kid = token_attrs['headers']['kid']
                jwk = self.SAMPLE_JWKS.get(kid)
                # compare sentinel object's string representation,
                # because the key is converted to string if it is
                # not an instance of `RSAPublicKey`
                if key != jwk.__repr__():
                    # If the passed key is different from expected,
                    # the `TokenValidationError` is raised, like
                    # in the original method.
                    raise TokenValidationError
                return token_attrs['claims']
        raise DecodeError

    @staticmethod
    def _get_user_by_login_side_effect(login, **kwargs):
        if login == 'test@example.com':
            return Mock(login='test@example.com', org_id='example.com', is_blocked=False)
        if login == 'oliver@example.com':
            return Mock(login='oliver@example.com', org_id='example.org', is_blocked=False)
        raise AuthDatabaseAPILookupError



### TODO: test other classes...

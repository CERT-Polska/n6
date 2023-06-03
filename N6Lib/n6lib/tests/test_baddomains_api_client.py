# Copyright (c) 2022 NASK. All rights reserved.

import datetime
import time
import unittest
import jwt
from requests import HTTPError
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.baddomains_api_client import (
    AuthTokenError,
    BaddomainsApiClient,
    ContactUidFetchError,
    ClientDetailsFetchError,
    URLType,
)
from n6lib.unit_test_helpers import TestCaseMixin


# Note that this function is only for test purposes
# and should never be used in the production code.
def _create_test_jwt_token(expired: bool = False,
                           aud: str = "example:com"
                           ) -> str:
    date = datetime.date(2022, 1, 1) + datetime.timedelta(days=3650)
    if expired:
        date = datetime.date(2022, 1, 1)
    timestamp = time.mktime(date.timetuple())
    # TODO: In case of upgrading `pyjwt` version to 2.0.0+
    #       remove `.decode('utf-8').
    #       (Or, maybe better, use `n6lib.jwt_helpers.jwt_encode()`...)
    payload = {"aud": aud, "exp": timestamp}
    return jwt.encode(payload, "secret").decode('utf-8')


# Note that this function is only for test purposes
# and should never be used in the production code.
def _create_custom_expiration_time_jwt_token(timestamp,
                                             aud: str = "example:com"
                                             ) -> str:
    # TODO: In case of upgrading `pyjwt` version to 2.0.0+
    #       remove `.decode('utf-8').
    #       (Or, maybe better, use `n6lib.jwt_helpers.jwt_encode()`...)
    payload = {"aud": aud, "exp": timestamp}
    return jwt.encode(payload, "secret",).decode('utf-8')


DEFAULT__VALID_CLIENT_ESSENTIALS = {
    'base_api_url': 'https://www.example.com',
    'username': 'example_username',
    'password': 'example_password',
    'auth_token_audience': 'example:com',
    'auth_token_cache_dir': '/home/user/example_dir',
}
DEFAULT__VALID_EXAMPLE_DOMAIN = 'our-example-test-domain.com'

EXPIRED_JWT_TOKEN = _create_test_jwt_token(expired=True)
NOT_EXPIRED_JWT_TOKEN = _create_test_jwt_token(expired=False)

REQUEST_AUTH_TOKEN_200 = {
    'status_code': 200,
    'response': {
        'access_token': NOT_EXPIRED_JWT_TOKEN,
        'token_type': 'bearer'
    },
    'error': None,
}

REQUEST_CONTACT_UID_200 = {
    'status_code': 200,
    'response': {
        'id': 0,
        'name': 'string',
        'created': '2022-01-01T01:00:00.000Z',
        'last_updated': '2022-01-01T01:00:00.000Z',
        'expires': '2022-01-01T01:00:00.000Z',
        'status': 'clientDeleteProhibited',
        'contact_uid': 0,
    },
    'error': None,
}

REQUEST_CONTACT_UID_301 = {
    'status_code': 301,
    'response': {
        'id': 0,
        'name': 'string',
        'created': '2022-01-01T01:00:00.000Z',
        'last_updated': '2022-01-01T01:00:00.000Z',
        'expires': '2022-01-01T01:00:00.000Z',
        'status': 'clientDeleteProhibited',
        'contact_uid': 0,
    },
    'error': None
}

REQUEST_CLIENT_DETAILS_200 = {
    'status_code': 200,
    'response': {
        "id": 0,
        "name1": "Example_First_Name_1",
        "name2": "Example_Sur_Name_2",
        "org1": "Example_Org_1",
        "org2": "Example_Org_2",
        "address1": "Example_Address_1",
        "address2": "Example_Address_2",
        "phone": "123456789",
        "email": "email@example.com",
        "is_org": True,
        "created": "2022-01-01T01:00:00.000Z",
        "last_updated": "2022-01-01T01:00:00.000Z"
        },
    'error': None,
}

REQUEST_CLIENT_DETAILS_301 = {
    'status_code': 301,
    'response': {
        "id": 0,
        "name1": "Example_First_Name_1",
        "name2": "Example_Sur_Name_2",
        "org1": "Example_Org_1",
        "org2": "Example_Org_2",
        "address1": "Example_Address_1",
        "address2": "Example_Address_2",
        "phone": "123456789",
        "email": "email@example.com",
        "is_org": True,
        "created": "2022-01-01T01:00:00.000Z",
        "last_updated": "2022-01-01T01:00:00.000Z"
        },
    'error': None,
}


@expand
class TestBaddomainsApiClient(unittest.TestCase, TestCaseMixin):

    @foreach(
        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
            expected_error=None,
        ).label('1. Valid example.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config={
                'username': 'example_username',
                'password': 'example_password',
                'auth_token_audience': 'example:com',
                'auth_token_cache_dir': '~/example_loc',
            },
            expected_error=TypeError,
        ).label('2. Invalid example - argument `base_api_url` is None.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config={
                'base_api_url': 'https://www.example.com',
                'password': 'example_password',
                'auth_token_audience': 'example:com',
                'auth_token_cache_dir': '~/example_loc',
            },
            expected_error=TypeError,
        ).label('3. Invalid example - argument `username` is None.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config={
                'base_api_url': 'https://www.example.com',
                'username': 'example_username',
                'auth_token_audience': 'example:com',
                'auth_token_cache_dir': '~/example_loc',
            },
            expected_error=TypeError,
        ).label('4. Invalid example - argument `password` is None.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config={
                'base_api_url': 'https://www.example.com',
                'username': 'example_username',
                'password': 'example_password',
                'auth_token_cache_dir': '~/example_loc',
            },
            expected_error=TypeError,
        ).label('5. Invalid example - argument `auth_token_audience` is None.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            external_config={
                'base_api_url': 'https://www.example.com',
                'username': 'example_username',
                'password': 'example_password',
                'auth_token_audience': 'example:com',
            },
            expected_error=TypeError,
        ).label('6. Invalid example - argument `auth_token_cache_dir` is None.'),
    )
    def test___init__(self,
                      custom_domain=None,
                      external_config=None,
                      expected_error=None,
                      ):

        if expected_error is not None:
            with self.assertRaises(expected_error):
                instance = BaddomainsApiClient(
                    # this is just sample valid domain to let us
                    # test other aspects of the client
                    domain=custom_domain,
                    **external_config)
        else:
            instance = BaddomainsApiClient(
                # this is just sample valid domain to let us
                # test other aspects of the client
                domain=custom_domain,
                **external_config)


    @foreach(
        param(
            custom_domain='example.com',
            expected_domain='example.com',
        ).label('Valid domain.'),

        param(
            custom_domain='http://example.com',
            expected_domain='example.com',
        ).label('Domain with http:// prefix (will be removed).'),

        param(
            custom_domain='https://example.com',
            expected_domain='example.com',
        ).label('Domain with https:// prefix (will be removed).'),

        param(
            custom_domain='123@456',
            expected_error=ValueError,
        ).label('Invalid domain.'),
    )
    # In this test case we focus on checking if our domain validation
    # works correctly on - let's call it - basic level.
    # You might want to check more detailed/advanced test cases which cover
    # usage of the `DOMAIN_ASCII_LOWERCASE_REGEX` regex there:
    # n6sdk.tests.test_regexes.Test_DOMAIN_ASCII_LOWERCASE_REGEX
    def test__get_validated_domain(self,
                                   custom_domain=None,
                                   expected_domain=None,
                                   expected_error=None,
                                   custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
                                   ):
        instance = BaddomainsApiClient(
            # this (valid) domain will be replaced
            # - we are not testing __init__() here
            domain='sample-valid-domain-which-will-be-replaced.com',
            **custom_config
        )
        instance._base_url = custom_domain
        if expected_error is not None:
            with self.assertRaises(expected_error):
                instance._get_validated_domain(custom_domain)
        else:
            actual_domain = instance._get_validated_domain(custom_domain)
            self.assertEqual(actual_domain, expected_domain)


    @foreach(
        param(
            custom_url_type=URLType.AUTH,
            expected_url='https://www.example.com/auth/login'
        ).label('1. Valid auth url.'),

        param(
            custom_url_type=URLType.DOMAIN,
            custom_data='test1.com',
            expected_url='https://www.example.com/domains/test1.com'
        ).label('2. Valid domain url.'),

        param(
            custom_url_type=URLType.CLIENT_UID,
            custom_data='1',
            expected_url='https://www.example.com/clients/1'
        ).label('3. Valid client_id url.'),

        param(
            custom_url_type=URLType.DOMAIN,
            expected_error=ValueError,
        ).label('4. No data provided while creating a domain_url.'),

        param(
            custom_url_type=URLType.CLIENT_UID,
            expected_error=ValueError,
        ).label('5. No data provided while creating a client_id_url.'),

        param(
            custom_url_type=URLType.AUTH,
            custom_data='This should not be provided',
            expected_error=ValueError,
        ).label('6. Data while creating auth_url.'),

        param(
            expected_error=ValueError,
        ).label('7. Invalid or none URL type provided.'),

        param(
            custom_url_type=URLType.AUTH,
            expected_url='https://www.example.com/auth/login',
            custom_config={
                'base_api_url': 'https://www.example.com//',
                'username': 'example_username',
                'password': 'example_password',
                'auth_token_audience': 'example:com',
                'auth_token_cache_dir': '~/example_loc',
                }
        ).label('8. Invalid `_base_url` - correctly fixed.'),
    )
    def test__create_url(self,
                         custom_url_type=None,
                         custom_data=None,
                         expected_url=None,
                         expected_error=None,
                         custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
                         ):
        instance = BaddomainsApiClient(
            # this is just sample valid domain to let us
            # test other aspects of the client.
            domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            **custom_config)
        if expected_error is not None:
            with self.assertRaises(ValueError):
                url = instance._create_url(
                    url_type=custom_url_type,
                    data=custom_data,
                )
                self.assertEqual(url, expected_url)
        else:
            url = instance._create_url(
                url_type=custom_url_type,
                data=custom_data,
            )
            self.assertEqual(url, expected_url)


    @foreach(
        param(
            expiration_timestamp=datetime.datetime.now().timestamp() + 1000,
            expected_result__is_expired=False,
        ).label('1. Token not expired.'),

        param(
            expiration_timestamp=datetime.datetime.now().timestamp() - 1000,
            expected_result__is_expired=True,
        ).label('2. Expired token.'),

        param(
            expiration_timestamp=datetime.datetime.now().timestamp() + 30,
            expected_result__is_expired=True,
        ).label('3. Expired token (less than 60 seconds to expiration time.'),
    )
    def test__is_access_token_expired(
            self,
            expiration_timestamp,
            expected_result__is_expired,
            custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS):
        instance = BaddomainsApiClient(
            # this is just sample valid domain to let us
            # test other aspects of the client
            domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            **custom_config)
        token = _create_custom_expiration_time_jwt_token(
            expiration_timestamp,
            custom_config['auth_token_audience']
        )
        result = instance._is_access_token_expired(token)
        self.assertEqual(result, expected_result__is_expired)


    @foreach(
        param(
            custom_response={
                "status_code": 200,
                "response": {"valid": "response"},
                "error": None,
            },
        ).label('1. Valid response.'),

        param(
            custom_response={
                "status_code": 404,
                "response": HTTPError,
                "error": HTTPError,
            },
            custom_mandatory_response_keys=None,
            custom_exc=ContactUidFetchError,
            expected_error=ContactUidFetchError,
        ).label(
            '2. '
            'Invalid response. Error in `error` '
            '- we expect to catch `custom_exc`.'
        ),

        param(
            custom_response={
                "status_code": None,
                "response": "Example",
                "error": None,
            },
            custom_mandatory_response_keys=None,
            custom_exc=AuthTokenError,
            expected_error=AuthTokenError,
        ).label(
            '3. '
            'Invalid response. No `status_code` '
            '- we expect to catch `custom_exc`.'
        ),

        param(
            custom_response={
                "status_code": 200,
                "response": {
                    "key_1": "1",
                    "key_2": "2",
                },
                "error": None,
            },
            custom_mandatory_response_keys=None,
        ).label(
            '4. '
            'Valid response. Mandatory key in response.'
        ),

        param(
            custom_response={
                "status_code": 200,
                "response": {
                    "key_1": "1",
                    "key_2": "2",
                },
                "error": None,
            },
            custom_mandatory_response_keys=['key_3'],
            custom_exc=AuthTokenError,
            expected_error=AuthTokenError,
        ).label(
            '5. '
            'Invalid response. '
            'Mandatory key `"key_3"` not in response.'
        ),

        param(
            custom_response={
                "status_code": 200,
                "response": {
                    "key_1": "1",
                    "key_2": "2",
                },
                "error": None,
            },
            custom_mandatory_response_keys=['key_3', 'key_4'],
            custom_exc=AuthTokenError,
            expected_error=AuthTokenError,
        ).label(
            '5. '
            'Invalid response. '
            'Mandatory keys `key_3` and `key_4` not in response.'
        ),

        param(
            custom_response={
                "status_code": 200,
                "response": {
                    "key_1": "1",
                    "key_2": "2",
                    "key_3": "3",
                },
                "error": None,
            },
            custom_mandatory_response_keys=['key_3', 'key_4'],
            custom_exc=AuthTokenError,
            expected_error=AuthTokenError,
        ).label(
            '6. '
            'Invalid response. '
            'Just one of two mandatory keys (`key_3`) in response.'
        ),
    )
    def test__react_to_response_dict_errors_or_checks(
            self,
            custom_response=None,
            custom_mandatory_response_keys=None,
            custom_exc=None,
            expected_error=None):
        instance = BaddomainsApiClient(
            # this is just sample valid domain to let us
            # test other aspects of the client.
            domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            **DEFAULT__VALID_CLIENT_ESSENTIALS)
        if expected_error:
            with self.assertRaises(expected_error):
                instance._check_response_dict(
                    response_dict=custom_response,
                    mandatory_response_keys=custom_mandatory_response_keys,
                    custom_exception=custom_exc,
                )
        else:
            instance._check_response_dict(
                response_dict=custom_response,
                mandatory_response_keys=custom_mandatory_response_keys,
                custom_exception=custom_exc,
            )


    @foreach(
        param(
            perform_request_mocked_responses=[REQUEST_CONTACT_UID_200],
            expected_result=REQUEST_CONTACT_UID_200,
        ).label(
            '1. '
            'Response: status_code==200; '
            'obtained contact_uid; '
            'no errors'
        ),

        param(
            perform_request_mocked_responses=[REQUEST_CONTACT_UID_301],
            expected_result=REQUEST_CONTACT_UID_301,
            expected_logs_msg=[
                    f'WARNING:n6lib.baddomains_api_client:'
                    f'We expected status code: 200, instead we have: '
                    f'{REQUEST_CONTACT_UID_301["status_code"]}. '
                    f'See: {REQUEST_CONTACT_UID_301}'
            ],
        ).label(
            '2. '
            'Response: status_code==301; '
            'obtained `contact_uid` response; '
            '1x warning in logs (status_code != 200)'
        ),

        param(
            perform_request_mocked_responses=[ContactUidFetchError(exc=HTTPError)],
            expected_error=ContactUidFetchError,
        ).label(
            '3. '
            'Simulation of `HTTPError`-related `ContactUidFetchError`)'
            'We expect to raise this `ContactUidFetchError`.'
            'See more: `_react_to_response_dict_errors_or_checks()` tests.'
        ),

        param(
            perform_request_mocked_responses=[ContactUidFetchError(
                exc=ValueError())],
            expected_error=ContactUidFetchError,
        ).label(
            '4. '
            'Simulation of non`HTTPError`-related `ContactUidFetchError`)'
            'We expect to raise this `ContactUidFetchError`.'
            'See more: `_react_to_response_dict_errors_or_checks()` tests.'
        ),
    )
    def test__get_contact_uid(
            self,
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            perform_request_mocked_responses=None,
            expected_result=None,
            expected_logs_msg=None,
            expected_error=None,
            custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
            ):
        self.patch(
            "n6lib.baddomains_api_client.BaddomainsApiClient._perform_custom_request",
            side_effect=perform_request_mocked_responses)
        baddomains_api_client = BaddomainsApiClient(
            domain=custom_domain,
            **custom_config)
        if expected_error:
            with self.assertRaises(expected_error):
                baddomains_api_client._get_contact_uid(
                    NOT_EXPIRED_JWT_TOKEN,
                    DEFAULT__VALID_EXAMPLE_DOMAIN)
        elif expected_logs_msg:
            with self.assertLogs('n6lib.baddomains_api_client',
                                 level='WARNING') as log:
                contact_uid_response = baddomains_api_client._get_contact_uid(
                    NOT_EXPIRED_JWT_TOKEN,
                    DEFAULT__VALID_EXAMPLE_DOMAIN)
                self.assertEqual(expected_logs_msg, log.output)
                self.assertEqual(contact_uid_response, expected_result)
        else:
            contact_uid_response = baddomains_api_client._get_contact_uid(
                NOT_EXPIRED_JWT_TOKEN,
                'example-domain.com',
            )
            self.assertEqual(contact_uid_response, expected_result)


    @foreach(
        param(
            perform_request_mocked_responses=[REQUEST_CLIENT_DETAILS_200],
            expected_result=REQUEST_CLIENT_DETAILS_200,
        ).label(
            '1. '
            'Response: status_code==200; '
            'obtained `contact_uid`; '
            'no errors'
        ),

        param(
            perform_request_mocked_responses=[REQUEST_CLIENT_DETAILS_301],
            expected_result=REQUEST_CLIENT_DETAILS_301,
            expected_logs_msg=[
                    f'WARNING:n6lib.baddomains_api_client:'
                    f'We expected status code: 200, instead we have: '
                    f'{REQUEST_CLIENT_DETAILS_301["status_code"]}. '
                    f'See: {REQUEST_CLIENT_DETAILS_301}'
            ],

        ).label(
            '2. '
            'Response: status_code==301; '
            'obtained `client_details`; '
            'no errors'
        ),

        param(
            perform_request_mocked_responses=[ClientDetailsFetchError(exc=HTTPError)],
            expected_error=ClientDetailsFetchError,
        ).label(
            '3. '
            'Simulation of `HTTPError`-related `ClientDetailsFetchError`'
            'We expect to raise this `ClientDetailsFetchError`.'
            'See more: `_react_to_response_dict_errors_or_checks()` tests.'
        ),

        param(
            perform_request_mocked_responses=[ClientDetailsFetchError(
                exc=ValueError())],
            expected_error=ClientDetailsFetchError,
        ).label(
            '4. '
            'Simulation of non`HTTPError`-related `ClientDetailsFetchError`)'
            'We expect to raise this `ClientDetailsFetchError`.'
            'See more: `_react_to_response_dict_errors_or_checks()` tests.'
        ),
    )
    def test__get_client_details(
            self,
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            perform_request_mocked_responses=None,
            expected_result=None,
            expected_logs_msg=None,
            expected_error=None,
            custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
            ):
        self.patch("n6lib.baddomains_api_client.BaddomainsApiClient._perform_custom_request",
                   side_effect=perform_request_mocked_responses)
        baddomains_api_client = BaddomainsApiClient(domain=custom_domain,
                                                    **custom_config)
        if expected_error:
            with self.assertRaises(expected_error):
                baddomains_api_client._get_client_details(
                    NOT_EXPIRED_JWT_TOKEN,
                    DEFAULT__VALID_EXAMPLE_DOMAIN)
        elif expected_logs_msg:
            with self.assertLogs('n6lib.baddomains_api_client',
                                 level='WARNING') as log:
                response = baddomains_api_client._get_client_details(
                    NOT_EXPIRED_JWT_TOKEN,
                    DEFAULT__VALID_EXAMPLE_DOMAIN)
                self.assertEqual(expected_logs_msg, log.output)
                self.assertEqual(response, expected_result)
        else:
            response = baddomains_api_client._get_client_details(
                NOT_EXPIRED_JWT_TOKEN,
                'example-domain.com',
            )
            self.assertEqual(response, expected_result)


    @foreach(
        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            perform_request_mocked_responses=[
                REQUEST_AUTH_TOKEN_200,
                REQUEST_CONTACT_UID_200,
                REQUEST_CLIENT_DETAILS_200,
            ],
            expected_client_details=REQUEST_CLIENT_DETAILS_200['response']
        ).label('1. Full run: no stored token in a file'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            mock_token_stored_in_file=NOT_EXPIRED_JWT_TOKEN,
            perform_request_mocked_responses=[
                REQUEST_CONTACT_UID_200,
                REQUEST_CLIENT_DETAILS_200,
            ],
            expected_client_details=REQUEST_CLIENT_DETAILS_200['response']
        ).label('2. Full run: token stored in a file **is not** expired.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            mock_token_stored_in_file=EXPIRED_JWT_TOKEN,
            perform_request_mocked_responses=[
                REQUEST_AUTH_TOKEN_200,
                REQUEST_CONTACT_UID_200,
                REQUEST_CLIENT_DETAILS_200,
            ],
            expected_client_details=REQUEST_CLIENT_DETAILS_200['response']
        ).label('3. Full run: token stored in a file **is** expired.'),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            mock_token_stored_in_file=EXPIRED_JWT_TOKEN,
            perform_request_mocked_responses=[
                AuthTokenError(HTTPError),
            ],
            expected_error=AuthTokenError,
        ).label(
            '4. '
            'Full run: we could not get `access_token`. '
            'We expect `AuthTokenError`.'
        ),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            mock_token_stored_in_file=NOT_EXPIRED_JWT_TOKEN,
            perform_request_mocked_responses=[
                ContactUidFetchError(HTTPError),
            ],
            expected_error=ContactUidFetchError,
        ).label(
            '5. '
            'Full run: we could not get `contact_uid`. '
            'We expect `ContactUidFetchError`.'
        ),

        param(
            custom_domain=DEFAULT__VALID_EXAMPLE_DOMAIN,
            mock_token_stored_in_file=EXPIRED_JWT_TOKEN,
            perform_request_mocked_responses=[
                ClientDetailsFetchError(HTTPError),
            ],
            expected_error=ClientDetailsFetchError,
        ).label(
            '6. '
            'Full run: we could not get `client_details`. '
            'We expect `ContactUidFetchError`.'
        ),
    )
    def test_complete_run(self,
                          custom_domain=None,
                          mock_token_stored_in_file=None,
                          perform_request_mocked_responses=None,
                          expected_client_details=None,
                          expected_error=None,
                          expected_logs_msg=None,
                          custom_config=DEFAULT__VALID_CLIENT_ESSENTIALS,
                          ):
        self.patch(
            "n6lib.baddomains_api_client.BaddomainsApiClient._perform_custom_request",
            side_effect=perform_request_mocked_responses)
        self.patch(
            "n6lib.baddomains_api_client.BaddomainsApiClient._save_access_token_to_file")
        self.patch(
            "n6lib.baddomains_api_client.BaddomainsApiClient._read_access_token_from_file",
            return_value=mock_token_stored_in_file)
        baddomains_api_client = BaddomainsApiClient(
            domain=custom_domain,
            **custom_config)
        if expected_error:
            with self.assertRaises(expected_error):
                baddomains_api_client.run()
        elif expected_logs_msg:
            with self.assertLogs('n6lib.baddomains_api_client',
                                 level='WARNING') as log:
                client_details = baddomains_api_client()
                self.assertEqual(expected_logs_msg, log.output)
                self.assertEqual(client_details, expected_client_details)
        else:
            client_details = baddomains_api_client()
            self.assertEqual(client_details, expected_client_details)

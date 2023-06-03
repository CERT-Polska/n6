# Copyright (c) 2022 NASK. All rights reserved.

import datetime
import json
import re
from enum import Enum
from pathlib import Path
from typing import (
    Optional,
    Type,
)
from urllib.parse import urljoin

import jwt
from requests import HTTPError
from requests.exceptions import RequestException

from n6lib.common_helpers import read_file
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import get_logger
from n6sdk.regexes import DOMAIN_ASCII_LOWERCASE_REGEX


LOGGER = get_logger(__name__)


class BaseBaddomainsRequestError(Exception):

    def __init__(self, exc=None):
        self.exc = exc

    def __str__(self):
        return f'{type(self.exc)} {str(self.exc)}'


class AuthTokenError(BaseBaddomainsRequestError):
    """An AuthToken error occurred."""


class ContactUidFetchError(BaseBaddomainsRequestError):
    """A ContactUidFetch error occurred."""


class ClientDetailsFetchError(BaseBaddomainsRequestError):
    """A ClientDetailsFetch error occurred."""


class URLType(Enum):

    AUTH: str = 'AUTH'
    DOMAIN: str = 'DOMAIN'
    CLIENT_UID: str = 'CLIENT_UID'


class BaddomainsApiClient:

    """
    A simple tool to search for information about the client associated
    with a specified domain via BaddomainsAPI.

    Required constructor kwargs:

    `domain` (str):
        The domain to check through BaddomainsAPI. Its lowercase
        representation should match
        `n6sdk.regexes.DOMAIN_ASCII_LOWERCASE_REGEX` regex.

    `username` (str):
        Username in the Baddomains API.

    `password` (str):
        Password related to the `Username` given above.

    `auth_token_audience` (str):
        The `aud` value used in the Baddomains API access token.

    `auth_token_cache_dir` (str):
        Path to directory where the file containing the Baddomains API
        access token will be stored in.

    Returns:
        The downloaded content, as we call it in the code:
        `client_details` (dict).

    Raises:
        * `ValueError` -- for:
          * invalid `domain` values;
          * incorrect arguments provided to `_create_url()` method.
        * `AuthTokenError` -- for:
          * any Exception raised during **Phase II** (Auth).
          * Specified exception is stored in the `exc` attribute.
        * `ContactUidFetchError` -- for:
          * any Exception raised during **Phase III** (ContactUid).
          * Specified exception is stored in the `exc` attribute.
        * `ClientDetailsFetchError` -- for
          * any Exception raised during **Phase IV** (ClientDetails).
          * Specified exception is stored in the `exc` attribute.

    ***

    Typically, the client performs the following operations
    divided into four main phases:

    Phase I (Validation):
        * Validates input data.

    Phase II (Auth):
        * Authenticates itself to BaddomainsAPI:
          * by using existing access token (stored in a file) or
          * by obtaining a new access token (using provided credentials:
            the `username` and the `password`) - if there is no token
            stored in the file or the token is already expired. It also
            saves the new access token to the file.

    Phase III (ContactUid):
        * Sends a `GET` request with the specified domain to obtain
          the `contact_uid`.

    Phase IV (ClientDetails):
        * Sends a `GET` query with the specified `contact_uid` to obtain
          the `client_details`.

    ***

    Example code:
    ```
    baddomains_client = BaddomainsApiClient(
        domain='example.com',
        base_api_url='https://www.example.com',
        username='username',
        password='password',
        auth_token_audience='example:com',
        auth_token_cache_dir='/home/user/example_dir'
    )
    client_details = baddomains_client.run()
    ```
    """

    BADDOMAINS_TOKEN_FILE_NAME = 'baddomains_access_token'
    URL_PROTOCOL_PREFIXES_PATTERN = r'^(http|https)://'


    def __init__(self,
                 domain: str,
                 *,
                 base_api_url: str,
                 username: str,
                 password: str,
                 auth_token_audience: str,
                 auth_token_cache_dir: str,
                 ) -> None:

        self._domain = self._get_validated_domain(domain)

        self._access_token = None
        self.client_details = None

        # external config
        self._bd_base_url = base_api_url
        self._bd_username = username
        self._bd_password = password
        self._bd_auth_token_audience = auth_token_audience
        self._bd_auth_token_cache_dir = self._get_validated_path(
            auth_token_cache_dir
        )

        self._validate_external_config()

    @staticmethod
    def _get_validated_path(path):
        return Path(path).expanduser()

    def _validate_external_config(self):
        # TODO: + additional validation (?)
        if self._bd_base_url is None:
            raise ValueError('The `base_api_url` argument '
                             'should not be None.')
        if self._bd_username is None:
            raise ValueError('The `username` argument '
                             'should not be None.')
        if self._bd_password is None:
            raise ValueError('The `password` argument '
                             'should not be None.')
        if self._bd_password is None:
            raise ValueError('The `auth_token_audience` argument '
                             'should not be None.')
        if self._bd_password is None:
            raise ValueError('The `auth_token_cache_dir` argument '
                             'should not be None.')


    def __call__(self) -> dict:
        return self.run()

    def run(self) -> dict:
        access_token = self._read_access_token_from_file()
        if access_token is None or self._is_access_token_expired(access_token):
            access_token = self._get_new_access_token()
            self._save_access_token_to_file(access_token)
        contact_uid_response = self._get_contact_uid(
            access_token=access_token,
            domain=self._domain)
        contact_uid = contact_uid_response['response']['contact_uid']
        client_details_response = self._get_client_details(
            access_token=access_token,
            contact_uid=str(contact_uid))
        self.client_details = client_details_response['response']
        return self.client_details

    def _get_new_access_token(self) -> Optional[str]:
        auth_api_url = self._create_url(url_type=URLType.AUTH)
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'username': f'{self._bd_username}',
            'password': f'{self._bd_password}',
        }
        response = self._perform_custom_request(
            method='POST',
            url=auth_api_url,
            headers=headers,
            data=data,
            mandatory_response_keys=['access_token'],
            custom_exception=AuthTokenError,
            )
        if response['status_code'] != 200:
            LOGGER.warning(
                f'We expected status code: 200 but we '
                f'received {response["status_code"]} instead. '
                f'See full response: {response}')
        return response['response']['access_token']

    def _get_contact_uid(self, access_token: str, domain: str) -> dict:
        domain_url = self._create_url(url_type=URLType.DOMAIN, data=domain)
        response = self._perform_custom_request(
            method='GET',
            url=domain_url,
            headers={
                'accept': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            mandatory_response_keys=['contact_uid'],
            custom_exception=ContactUidFetchError,
        )
        if response['status_code'] != 200:
            LOGGER.warning(
                f'We expected status code: 200, instead we have: '
                f'{response["status_code"]}. See: '
                f'{response}')
        return response

    def _get_client_details(self,
                            access_token: str,
                            contact_uid: str,
                            ) -> Optional[dict]:
        contact_uid_url = self._create_url(url_type=URLType.CLIENT_UID,
                                           data=str(contact_uid))
        response = self._perform_custom_request(
            method='GET',
            url=contact_uid_url,
            headers={
                'accept': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            custom_exception=ClientDetailsFetchError,
        )
        if response['status_code'] != 200:
            LOGGER.warning(
                f'We expected status code: 200, instead we have: '
                f'{response["status_code"]}. See: '
                f'{response}')
        return response


    #
    # Helpers

    def _read_access_token_from_file(self) -> Optional[str]:
        try:
            dir_path = self._bd_auth_token_cache_dir
            filename = self.BADDOMAINS_TOKEN_FILE_NAME
            access_token = read_file(
                Path(dir_path, filename),
                mode='r',
                encoding='utf-8'
            )
            if access_token:
                return access_token
        except FileNotFoundError:
            return None
        return None

    def _save_access_token_to_file(self, access_token):
        if access_token is not None:
            with open(Path(self._bd_auth_token_cache_dir,
                           self.BADDOMAINS_TOKEN_FILE_NAME),
                      mode='w',
                      encoding='utf-8') as f:
                f.write(access_token)

    def _is_access_token_expired(self, access_token: str) -> bool:
        """
        Note that without having a secret, we cannot authenticate
        this token. The following check is only intended to reduce
        the server load by not sending unnecessary requests.

        We assume, that - due to some lags etc. - token is expired when
        datetime.now().timestamp() >= expiration time - 60 seconds.
        """
        try:
            # (maybe TODO: use our `n6lib.jwt_helpers` after enhancing them appropriately?...)
            decoded_token = jwt.decode(
                access_token,
                audience=self._bd_auth_token_audience,
                options={"verify_signature": False}
            )
            exp_timestamp = decoded_token['exp']
            now_timestamp = datetime.datetime.now().timestamp()
            if now_timestamp >= exp_timestamp - 60:
                return True
        except jwt.exceptions.ExpiredSignatureError:
            return True
        return False

    def _create_url(self,
                    url_type: URLType,
                    data: Optional[str] = None,
                    ) -> str:
        no_data_msg = 'Unable to create a URL - no data provided.'
        if url_type is URLType.AUTH:
            if data:
                raise ValueError(
                    'You should not provide data while creating an auth_url'
                )
            return urljoin(self._bd_base_url, '/auth/login')
        if url_type is URLType.DOMAIN:
            if data is None:
                raise ValueError(no_data_msg)
            return urljoin(f'{self._bd_base_url}/domains/', data)
        if url_type is URLType.CLIENT_UID:
            if data is None:
                raise ValueError(no_data_msg)
            return urljoin(f'{self._bd_base_url}/clients/', data)
        raise ValueError(f'Provide valid URL type: {URLType}')

    def _extract_domain_from_url(self, url) -> list:
        return re.split(
            pattern=self.URL_PROTOCOL_PREFIXES_PATTERN,
            string=url,
            maxsplit=1
        )

    def _get_validated_domain(self, domain: str) -> str:
        if re.match(self.URL_PROTOCOL_PREFIXES_PATTERN, domain):
            LOGGER.warning(
                f'Looks like this domain {domain} has http(s) prefix '
                f'which will be removed before further processing.'
            )
            domain = self._extract_domain_from_url(domain)[2].lower()
        if not DOMAIN_ASCII_LOWERCASE_REGEX.search(domain):
            raise ValueError(
                f'Looks like there is something wrong '
                f'with domain: {domain}.'
            )
        return domain

    def _perform_custom_request(
            self, *,
            method: str,
            url: str,
            data: Optional[dict] = None,
            headers: Optional[dict] = None,
            mandatory_response_keys: Optional[list[str]] = None,
            custom_exception: Optional[Type[BaseBaddomainsRequestError]] = None,
            ) -> dict:
        try:
            with RequestPerformer(method=method,
                                  url=url,
                                  data=data,
                                  headers=headers) as perf:
                response_dict = self._create_response_dict(
                    status_code=perf.response.status_code,
                    response=json.loads(perf.response.content),
                    error=None,
                )
        except HTTPError as http_exc:
            response_dict = self._create_response_dict(
                status_code=http_exc.response.status_code,
                response=http_exc.response,
                error=http_exc,
            )
        except Exception as other_exc:
            response_dict = self._create_response_dict(
                status_code=None,
                response=None,
                error=other_exc,
            )
        self._check_response_dict(
            response_dict=response_dict,
            mandatory_response_keys=mandatory_response_keys,
            custom_exception=custom_exception,
        )
        return response_dict

    @staticmethod
    def _create_response_dict(status_code: Optional[int] = None,
                              response: Optional[str] = None,
                              error: Optional[Exception] = None
                              ) -> dict:
        response_dict = {
            'status_code': status_code,
            'response': response,
            'error': error,
        }
        return response_dict

    @staticmethod
    def _check_response_dict(
            *,
            response_dict: dict,
            mandatory_response_keys: Optional[list[str]] = None,
            custom_exception: Type[BaseBaddomainsRequestError],
    ) -> None:
        if response_dict['error'] is not None:
            raise custom_exception(exc=response_dict['error'])
        if response_dict['status_code'] is None:
            raise custom_exception(exc=RequestException(
                f'Invalid response: {response_dict}'))
        if mandatory_response_keys is not None:
            non_existing_keys = []
            for key in mandatory_response_keys:
                if response_dict['response'].get(key) is None:
                    non_existing_keys.append(key)
            if non_existing_keys:
                raise custom_exception(exc=RequestException(
                    f'Invalid response. These mandatory keys do not appear '
                    f'in response: {", ".join(non_existing_keys)}. '
                    f'Full response: {response_dict}'))

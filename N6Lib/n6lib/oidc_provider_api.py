# Copyright (c) 2022-2025 NASK. All rights reserved.

import json
from functools import (
    lru_cache,
    partial,
)
from typing import Optional
from urllib3 import Retry

from n6lib.common_helpers import (
    ThreadLocalNamespace,
    as_unicode,
)
from n6lib.config import ConfigMixin
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import StrOrBinary

import jwt
from jwt.algorithms import (
    RSAAlgorithm,
    RSAPublicKey,
)
from jwt.exceptions import InvalidTokenError
from requests import (
    RequestException,
    Session,
)
from requests.adapters import HTTPAdapter


LOGGER = get_logger(__name__)


class TokenValidationError(Exception):
    pass


class IdPServerResponseError(Exception):
    pass


class OIDCProviderAPI(ConfigMixin):

    config_spec = '''
        [oidc_provider_api]
        active = false :: bool
        server_url = :: str
        realm_name = :: str
        cache_jwks = true :: bool
        max_cached_keys = 10 :: int

        # whether the 'aud' claim in access token should be verified
        verify_audience = false :: bool

        # Value that the access token's 'aud' claim should contain,
        # it can be N6Portal's URL or some application name.
        # If `verify_audience` is disabled and the option is left
        # empty, the claim will not be checked. Otherwise, the claim's
        # presence in a token will be verified. In this case, not
        # setting the option (setting to empty string), the required
        # claim's value defaults to the application URL.
        required_audience = :: str

        idp_server_request_retries = 3 :: int

        # the backoff factor applies to sleep times between retries,
        # according to the formula:
        # {backoff factor} * (2 ** ({number of previous retries}))
        # https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry
        idp_server_request_backoff_factor = 0.2 :: float

        idp_server_request_timeout = 10 :: int
    '''

    oidc_config_endpoint_pattern = "{server_url}/realms/{realm}/.well-known/openid-configuration"

    def __init__(self, settings: Optional[dict] = None) -> None:
        self._config = self.get_config_section(settings)
        self._retries = Retry(total=self._config['idp_server_request_retries'],
                              backoff_factor=self._config['idp_server_request_backoff_factor'])
        self._request_session_namespace = ThreadLocalNamespace(attr_factories={
            'request_session': self._request_session_factory(),
        })
        self.is_active = self._config['active']
        self.realm_name = self._config['realm_name']
        self.required_audience = (None if not self._config['required_audience']
                                  else self._config['required_audience'])
        self.verify_audience = self._config['verify_audience']
        self.decoding_options = dict(verify_aud=self.verify_audience)
        self._server_url = self._config['server_url']
        self._cache_jwks = self._config['cache_jwks']
        self._max_cached_keys = self._config['max_cached_keys']
        self._request_timeout = self._config['idp_server_request_timeout']
        if self._cache_jwks:
            self.get_signing_key_from_token = (
                lru_cache(self._max_cached_keys)(self.get_signing_key_from_token)
            )
        if self.is_active:
            self._oidc_config_endpoint_url = self._get_config_endpoint_url()
            try:
                # fetching the external identity provider's
                # configuration serves also as the first check
                # of connection to the server
                self._jwks_uri = self._fetch_jwks_endpoint_url()
            except IdPServerResponseError as exc:
                LOGGER.error('%s. Authentication through external identity provider '
                             'will be disabled', exc)
                self.is_active = False

    def get_signing_key_from_token(self, token: StrOrBinary) -> RSAPublicKey:
        try:
            json_web_keys = self._get_json_web_keys()
        except IdPServerResponseError as exc:
            raise TokenValidationError(exc)
        token = as_unicode(token)
        try:
            headers = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise TokenValidationError(f"The token could not be decoded: {exc}")
        try:
            kid = headers['kid']
            return json_web_keys[kid]
        except KeyError:
            raise TokenValidationError("No 'kid' key in token's headers or no JWK fitting "
                                       "the 'kid' could be found")

    def _request_session_factory(self):
        return partial(self._get_request_session, self._retries)

    @staticmethod
    def _get_request_session(retries: Retry) -> Session:
        request_session = Session()
        for schema in ("https://", "http://"):
            request_session.mount(schema, HTTPAdapter(max_retries=retries))
        return request_session

    def _get_config_endpoint_url(self):
        return self.oidc_config_endpoint_pattern.format(server_url=self._server_url.rstrip('/'),
                                                        realm=self.realm_name)

    def _fetch_openid_configuration(self) -> dict:
        try:
            response = self._request_session_namespace.request_session.get(
                self._oidc_config_endpoint_url,
                timeout=self._request_timeout)
            response.raise_for_status()
        except RequestException as exc:
            raise IdPServerResponseError(f'Failed to fetch OpenID server\'s configuration: {exc}')
        try:
            resp_json = response.json()
            if not resp_json or not isinstance(resp_json, dict):
                raise ValueError
            return resp_json
        except ValueError:
            raise IdPServerResponseError(f'Invalid format of OpenID configuration '
                                         f'request\'s response')

    def _fetch_jwks_endpoint_url(self) -> str:
        openid_config = self._fetch_openid_configuration()
        jwks_uri = openid_config.get('jwks_uri')
        if not jwks_uri or not isinstance(jwks_uri, str):
            LOGGER.error('Failed to fetch OpenID server\'s JWKS endpoint URL from OpenID '
                         'configuration due to invalid format of response')
            raise IdPServerResponseError('Failed to fetch OpenID server\'s JWKS endpoint URI '
                                         'from OpenID configuration')
        return jwks_uri

    def _fetch_jwks_document(self) -> dict:
        try:
            response = self._request_session_namespace.request_session.get(
                self._jwks_uri, timeout=self._request_timeout)
            response.raise_for_status()
        except RequestException as exc:
            raise IdPServerResponseError(f'Failed to fetch JSON Web Key Set: {exc}')
        try:
            resp_json = response.json()
            if (
                not resp_json
                or not isinstance(resp_json, dict)
                or 'keys' not in resp_json
                or not isinstance(resp_json['keys'], list)
            ):
                raise ValueError
        except ValueError:
            raise IdPServerResponseError('Invalid format of JSON Web Key Set')
        return resp_json

    def _get_json_web_keys(self) -> dict[str, RSAPublicKey]:
        signing_keys = {}
        jwks = self._fetch_jwks_document()
        for jwk in jwks['keys']:
            try:
                signing_keys[jwk['kid']] = RSAAlgorithm.from_jwk(json.dumps(jwk))
            except (KeyError, TypeError, ValueError):
                raise IdPServerResponseError('Invalid format of JSON Web Key Set')
        return signing_keys

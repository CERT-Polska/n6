# Copyright (c) 2022-2023 NASK. All rights reserved.

import json
from functools import lru_cache
from typing import Optional

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
from keycloak import KeycloakOpenID


LOGGER = get_logger(__name__)


class TokenValidationError(Exception):
    pass


class OIDCProviderAPI(ConfigMixin):

    config_spec = '''
        [oidc_provider_api]
        active = false :: bool
        server_url = :: str
        realm_name = :: str
        client_id = :: str
        client_secret_key = :: str
        verify_ssl = false :: bool
        cache_jwks = true :: bool
        max_cached_keys = 10 :: int
    '''

    def __init__(self, settings: Optional[dict] = None) -> None:
        self.unauthenticated_credentials = ThreadLocalNamespace(attr_factories={
            'user_id': lambda: None,
            'org_id': lambda: None,
        })
        self._config = self.get_config_section(settings)
        self.is_active = self._config['active']
        self.realm_name = self._config['realm_name']
        self.client_id = self._config['client_id']
        self._server_url = self._config['server_url']
        self._client_secret_key = self._config['client_secret_key']
        self._verify_ssl = self._config['verify_ssl']
        self._cache_jwks = self._config['cache_jwks']
        self._max_cached_keys = self._config['max_cached_keys']
        if self._cache_jwks:
            self.get_signing_key_from_token = (
                lru_cache(self._max_cached_keys)(self.get_signing_key_from_token)
            )
        if self.is_active:
            try:
                self.oidc_client = self._connect()
            except Exception:
                LOGGER.error('Failed to connect to external identity provider. '
                             'Authentication through external identity provider will be disabled')
                self.is_active = False

    def get_signing_key_from_token(self, token: StrOrBinary) -> RSAPublicKey:
        json_web_keys = self._get_json_web_keys()
        token = as_unicode(token)
        try:
            headers = jwt.get_unverified_header(token)
        except InvalidTokenError:
            raise TokenValidationError
        try:
            kid = headers['kid']
            return json_web_keys[kid]
        except KeyError:
            raise TokenValidationError

    def _connect(self):
        return KeycloakOpenID(self._server_url,
                              self.realm_name,
                              self.client_id,
                              client_secret_key=self._client_secret_key,
                              verify=self._verify_ssl)

    def _get_json_web_keys(self) -> dict[str, RSAPublicKey]:
        signing_keys = {}
        jwks = self.oidc_client.certs()
        for jwk in jwks['keys']:
            signing_keys[jwk['kid']] = RSAAlgorithm.from_jwk(json.dumps(jwk))
        return signing_keys

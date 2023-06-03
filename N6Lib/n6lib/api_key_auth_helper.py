# Copyright (c) 2022-2023 NASK. All rights reserved.

from n6lib.auth_db.api import AuthManageAPI
from n6lib.jwt_helpers import (
    JWT_ALGO_HMAC_SHA256,
    JWTDecodeError,
    jwt_decode,
    jwt_encode,
)


class APIKeyAuthError(Exception):
    """To be raised on authentication failures."""


class APIKeyAuthHelper:

    def __init__(self, server_secret, authenticate_with_user_id_and_api_key_id):
        self._server_secret = server_secret
        self._authenticate_with_user_id_and_api_key_id = authenticate_with_user_id_and_api_key_id

    def is_api_key_authentication_enabled(self):
        return bool(self._get_api_key_server_secret_or_none())

    def get_api_key_as_jwt_or_none(self, user_id, api_key_id):
        server_secret = self._get_api_key_server_secret_or_none()
        if server_secret is None:
            return None
        api_key = jwt_encode({'login': user_id, 'api_key_id': api_key_id},
                             server_secret,
                             algorithm=JWT_ALGO_HMAC_SHA256,
                             required_claims={'login': str, 'api_key_id': str})
        return api_key

    def authenticate_with_api_key(self, api_key):
        server_secret = self._get_api_key_server_secret_or_none()
        if server_secret is None:
            raise APIKeyAuthError
        api_key_payload = self._verify_and_decode_api_key(api_key, server_secret)
        # Note: `auth_result` can be anything (it depends solely on
        # the `_authenticate_with_user_id_and_api_key_id()` callback).
        auth_result = self._authenticate_with_user_id_and_api_key_id(
            user_id=AuthManageAPI.adjust_if_is_legacy_user_login(api_key_payload['login']),
            api_key_id=api_key_payload['api_key_id'])
        return auth_result

    def _verify_and_decode_api_key(self, api_key, server_secret):
        try:
            payload = jwt_decode(api_key,
                                 server_secret,
                                 accepted_algorithms=[JWT_ALGO_HMAC_SHA256],
                                 required_claims={'login': str, 'api_key_id': str})
        except JWTDecodeError as exc:
            raise APIKeyAuthError from exc
        return payload

    def _get_api_key_server_secret_or_none(self):
        server_secret = self._server_secret
        return (server_secret if server_secret.strip() else None)

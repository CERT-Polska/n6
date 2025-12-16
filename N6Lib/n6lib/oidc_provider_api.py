# Copyright (c) 2022-2025 NASK. All rights reserved.

from __future__ import annotations

import json
import time
from dataclasses import (
    InitVar,
    asdict,
    dataclass,
    fields as dataclass_fields,
)
from functools import (
    lru_cache,
    partial,
)
from typing import (
    Callable,
    Literal,
    Optional,
)
from urllib.parse import (
    urljoin,
    urlsplit,
    urlunsplit,
)

import jwt
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2.rfc6750 import (
    InsufficientScopeError,
    InvalidTokenError as InvalidOAuth2TokenError,
)
from authlib.oauth2.client import OAuth2Error
from authlib.oauth2.rfc6749.parameters import (
    parse_authorization_code_response,
    prepare_token_request,
)
from authlib.oauth2.rfc6749.requests import BasicOAuth2Payload
from authlib.oauth2.rfc7662 import IntrospectTokenValidator
from jwt.algorithms import (
    RSAAlgorithm,
    RSAPublicKey,
)
from jwt.exceptions import InvalidTokenError
from pyramid.session import SignedSerializer
from requests import (
    Response,
    RequestException,
)
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3 import Retry

from n6lib.common_helpers import (
    ThreadLocalNamespace,
    as_unicode,
    ascii_str,
    make_exc_ascii_str,
    make_hex_id,
)
from n6lib.config import ConfigMixin
from n6lib.jwt_helpers import jwt_decode
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import StrOrBinary


LOGGER = get_logger(__name__)


class OIDCProviderError(Exception):
    pass


class TokenValidationError(OIDCProviderError):
    pass


class IdPServerResponseError(OIDCProviderError):
    pass


class StateValidationError(OIDCProviderError):
    pass


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str
    id_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int
    not_before_policy: int
    session_state: str
    scope: str
    valid_token_type: InitVar[str] = 'Bearer'

    def __post_init__(self, valid_token_type: str):
        if self.token_type != valid_token_type:
            raise IdPServerResponseError(f'Invalid token type in response: '
                                         f'{ascii_str(self.token_type)!a}')

    @classmethod
    def from_response(cls, response: dict) -> "TokenResponse":
        """
        Create a dataclass instance from a dict containing the token
        endpoint response body.

        Replace dict key name containing hyphens with a version without
        them to allow dataclass instantiation.
        """
        normalized_response = None
        try:
            normalized_response = {'not_before_policy'
                                   if key == 'not-before-policy'
                                   else key: val
                                   for key, val in response.items()}
            return cls(**normalized_response)
        except TypeError:
            if normalized_response is None:
                raise IdPServerResponseError('Invalid response body')
            payload_set = set(normalized_response)
            missing = ascii_str(', '.join(cls.missing_field_names(payload_set))) or '-'
            redundant = ascii_str(', '.join(cls.redundant_field_names(payload_set))) or '-'
            raise IdPServerResponseError(f'Missing required fields in the response: '
                                         f'{missing!a}; '
                                         f'redundant fields: {redundant!a}')

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def field_names(cls):
        return set(field.name for field in dataclass_fields(cls))

    @classmethod
    def missing_field_names(cls, payload: set):
        return tuple(cls.field_names() - payload)

    @classmethod
    def redundant_field_names(cls, payload: set):
        return tuple(payload - cls.field_names())


class OIDCProviderAPI(ConfigMixin):

    config_spec = '''
        [oidc_provider_api]
        enabled = false :: bool
        # URL accessible by the N6Portal back end for back-channel
        # communication (i.e., a URL that uses container's hostname
        # within the Docker network)
        server_url = :: str
        realm_name = :: str
        client_id = :: str
        client_secret = :: str
        # the 'redirect_uri' option may be left unset (an empty string
        # will be used by default) only if the exact URI (without wildcards)
        # has been added to the client's configuration in Keycloak
        # and no other URIs are configured
        redirect_uri = :: str
        # URI to redirect to after logging out of OpenID Connect
        # session. If not set, the user must manually return to
        # the login page.
        logout_redirect_uri = :: str
        cache_jwks = true :: bool
        max_cached_keys = 10 :: int

        # The required scopes of the authorization request. The list
        # will be validated against the scopes issued by
        # the authorization server. The default scopes - 'openid',
        # 'email', and 'profile' - should not be changed, but new
        # values can be added. The 'openid' scope is especially
        # important, as it indicates an authentication request
        # and is required to obtain an ID Token.
        client_scopes = openid, email, profile :: list_of_str

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

        # tokens with fewer minutes remaining until expiration than
        # this value are validated via the introspection endpoint
        jwt_introspection_time_threshold = 2 :: int

        state_cookie_name = oidc_state :: str
        state_cookie_sign_secret = :: str
        state_cookie_salt = n6portal|oidc-state-cookie|v1 :: str
        state_cookie_hash_algorithm = sha256 :: str
        state_cookie_max_age = 300 :: int
        state_cookie_path = / :: str
        state_cookie_secure = true :: bool
        state_cookie_http_only = true :: bool

        idp_server_request_retries = 3 :: int

        # the backoff factor applies to sleep times between retries,
        # according to the formula:
        # {backoff factor} * (2 ** ({number of previous retries}))
        # https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry
        idp_server_request_backoff_factor = 0.2 :: float

        idp_server_request_timeout = 10 :: int
    '''
    discovery_endpoint_path_pattern = "realms/{realm}/.well-known/openid-configuration"

    def __init__(self, settings: Optional[dict] = None) -> None:
        self._config = self.get_config_section(settings)
        self._retries = Retry(total=self._config['idp_server_request_retries'],
                              backoff_factor=self._config['idp_server_request_backoff_factor'])
        self.is_enabled = self._config['enabled']
        self.realm_name = self._config['realm_name']
        self.client_id = self._config['client_id']
        self.client_secret = self._config['client_secret']
        self.required_audience = self._config['required_audience'] or None
        self.verify_audience = self._config['verify_audience']
        # `is_connection_active` is distinct from `enabled`, the latter
        # indicates whether the service is enabled in the configuration,
        # while `is_connection_active` is true if the service is running
        # and responding.
        # The IdP server's status is checked when generating
        # the response from the /info/oidc endpoint, ensuring that
        # the value is up-to-date. The value may change according to
        # the IdP server's state.
        self.is_connection_active: bool = False
        self.server_url = self._config['server_url']
        self._parsed_server_url = urlsplit(self.server_url)
        self._redirect_uri = self._config['redirect_uri'] or None
        self._logout_redirect_uri = self._config['logout_redirect_uri'] or None
        if self._logout_redirect_uri is None:
            LOGGER.warning('The `oidc_provider_api.logout_redirect_uri` option has not been set')
        self._request_timeout = self._config['idp_server_request_timeout']
        self._cache_jwks = self._config['cache_jwks']
        self._max_cached_keys = self._config['max_cached_keys']
        self._required_scopes = self._config['client_scopes']
        self._jwt_introspection_time_threshold = self._config['jwt_introspection_time_threshold']
        self._state_cookie_name = self._config['state_cookie_name']
        self._state_cookie_sign_secret = self._config['state_cookie_sign_secret'] or make_hex_id()
        self._state_cookie_salt = self._config['state_cookie_salt'] or None
        self._state_cookie_hash_alg = self._config['state_cookie_hash_algorithm']
        self._state_cookie_max_age = self._config['state_cookie_max_age']
        self._state_cookie_path = self._config['state_cookie_path'] or None
        self._state_cookie_secure = self._config['state_cookie_secure']
        self._state_cookie_http_only = self._config['state_cookie_http_only']
        self.token_validator: "TokenValidator | None" = None
        self._signed_serializer: SignedSerializer | None = None
        discovery_endpoint_path = self.discovery_endpoint_path_pattern.format(
            realm=self.realm_name)
        self._discovery_endpoint_url = self._get_config_endpoint_url(self.server_url,
                                                                     discovery_endpoint_path)
        self._issuer = None
        self._auth_endpoint_uri = None
        self._end_session_endpoint_uri = None
        self._token_endpoint_uri = None
        self._token_introspection_endpoint_uri = None
        self._jwks_endpoint_uri = None
        self._oidc_client_namespace: ThreadLocalNamespace | None = None
        self._openid_metadata: dict[str, str] | None = None
        self.enable_oidc_service()

    def enable_oidc_service(self):
        if self.is_enabled and not self.is_connection_active:
            self._oidc_client_namespace = ThreadLocalNamespace(attr_factories={
                'oidc_client': self._oidc_client_factory(),
            })
            try:
                self._openid_metadata = self._fetch_openid_metadata()
                self._set_oidc_server_claims(self._openid_metadata)
                self._set_oidc_endpoint_uris(self._openid_metadata)
                self._signed_serializer = SignedSerializer(self._state_cookie_sign_secret,
                                                           salt=self._state_cookie_salt,
                                                           hashalg=self._state_cookie_hash_alg)
                self.token_validator = TokenValidator(self._oidc_client_namespace,
                                                      self.realm_name,
                                                      self._jwks_endpoint_uri,
                                                      self._token_introspection_endpoint_uri,
                                                      self._token_endpoint_uri,
                                                      self._required_scopes,
                                                      self._issuer,
                                                      self._cache_jwks,
                                                      self._max_cached_keys,
                                                      self.verify_audience,
                                                      self._jwt_introspection_time_threshold)
            except IdPServerResponseError as exc:
                LOGGER.error('Failed to fetch the OpenID metadata document; '
                             'the OpenID authentication will stay disabled: %s',
                             make_exc_ascii_str(exc))
            else:
                self.is_connection_active = True

    def get_signing_key_from_token(self, token: StrOrBinary) -> RSAPublicKey:
        return self.token_validator.get_signing_key_from_token(token)

    def get_end_session_uri(self):
        return self._end_session_endpoint_uri

    def get_end_session_redirect_uri(self):
        return self._logout_redirect_uri

    def create_auth_url_and_state(self) -> tuple[str, str]:
        return self._oidc_client_namespace.oidc_client.create_authorization_url(
            self._auth_endpoint_uri, scope=self._required_scopes)

    def json_response_with_state_cookie(self, response, state):
        response.set_cookie(self._state_cookie_name,
                            value=self._generate_state_cookie_value(state),
                            max_age=self._state_cookie_max_age,
                            path=self._state_cookie_path,
                            secure=self._state_cookie_secure,
                            httponly=self._state_cookie_http_only)
        return response

    def decode_state_cookie(self, cookies) -> str:
        try:
            value = cookies[self._state_cookie_name]
        except KeyError:
            raise StateValidationError('Signed cookie with \'state\' parameter value is missing')
        if value is None:
            raise StateValidationError('Value of the \'state\' parameter is required')
        try:
            return self._signed_serializer.loads(value)
        except ValueError as exc:
            raise StateValidationError(exc)

    def exchange_code_for_access_token(self,
                                       auth_response_uri: str,
                                       orig_state: str) -> TokenResponse:
        return self._oidc_client_namespace.oidc_client.fetch_token_simplified(
            self._token_endpoint_uri,
            redirect_uri=self._redirect_uri,
            callback_uri=auth_response_uri,
            state=orig_state)

    def json_response_with_cookie_deletion(self, response):
        response.delete_cookie(self._state_cookie_name, path=self._state_cookie_path)
        return response

    def refresh_token(self, token: str) -> TokenResponse:
        return self._oidc_client_namespace.oidc_client.refresh_token(self._token_endpoint_uri,
                                                                     token)

    def _oidc_client_factory(self):
        return partial(self._get_client,
                       self.client_id,
                       self.client_secret,
                       self._redirect_uri,
                       self._request_timeout,
                       self._retries)

    @staticmethod
    def _get_config_endpoint_url(server_url: str, discovery_endpoint_path: str) -> str:
        return urljoin(server_url, discovery_endpoint_path)

    @staticmethod
    def _get_client(client_id: str,
                    secret: str,
                    redirect_uri: str | None,
                    request_timeout: int,
                    retries: Retry) -> 'OIDCClientSession':
        return OIDCClientSession(client_id,
                                   max_retries=retries,
                                   http_adapter_class=HTTPAdapter,
                                   client_secret=secret,
                                   redirect_uri=redirect_uri,
                                   response_type='code',
                                   default_timeout=request_timeout)

    def _fetch_openid_metadata(self) -> dict[str, str]:
        try:
            response = self._oidc_client_namespace.oidc_client.get(self._discovery_endpoint_url)
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

    def _set_oidc_server_claims(self, openid_metadata: dict):
        try:
            self._issuer = openid_metadata['issuer']
        except KeyError as exc:
            raise IdPServerResponseError(f'The {exc} value of OpenID metadata '
                                         f'is missing') from exc

    def _set_oidc_endpoint_uris(self, openid_metadata: dict):
        try:
            # "authorization" and "end session" endpoint URLs should
            # remain as front-channel communication URLs
            self._auth_endpoint_uri = openid_metadata['authorization_endpoint']
            self._end_session_endpoint_uri = openid_metadata['end_session_endpoint']
            self._token_endpoint_uri = self._get_back_channel_uri(
                openid_metadata['token_endpoint'])
            self._token_introspection_endpoint_uri = self._get_back_channel_uri(
                openid_metadata['introspection_endpoint'])
            self._jwks_endpoint_uri = self._get_back_channel_uri(openid_metadata['jwks_uri'])
        except KeyError as exc:
            raise IdPServerResponseError(f'The {exc} value of OpenID configuration'
                                         f' is missing') from exc

    def _get_back_channel_uri(self, uri: str) -> str:
        scheme, netloc, path, *rest = self._parsed_server_url
        parsed_uri = urlsplit(uri)
        if path:
            new_path = urljoin(path, parsed_uri.path)
        else:
            new_path = parsed_uri.path
        # noinspection PyTypeChecker
        return urlunsplit((scheme, netloc, new_path, parsed_uri.query, parsed_uri.fragment))

    def _generate_state_cookie_value(self, state: str) -> bytes:
        return self._signed_serializer.dumps(state)


class OIDCClientSession(OAuth2Session):
    token_endpoint_request_headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    }
    client_auth_name: Literal['client_auth'] = 'client_auth'
    token_auth_name: Literal['token_auth'] = 'token_auth'
    token_placement: str = 'header'
    auth_method_with_client_secret: str = 'client_secret_basic'

    def __init__(self,
                 client_id: str,
                 *,
                 max_retries: Retry,
                 http_adapter_class: type[HTTPAdapter],
                 client_secret: str,
                 redirect_uri: str | None = None,
                 response_type: str = 'code',
                 default_timeout: int | None = None,
                 **kwargs):
        super().__init__(client_id,
                         client_secret=client_secret,
                         redirect_uri=redirect_uri,
                         response_type=response_type,
                         default_timeout=default_timeout,
                         **kwargs)
        self.mount('https://', http_adapter_class(max_retries=max_retries))

    def fetch_token_simplified(self,
                               token_endpoint_uri: str,
                               redirect_uri: str,
                               callback_uri: str,
                               method: str = 'POST',
                               state: str | None = None,
                               **kwargs) -> TokenResponse:
        session_kwargs = self._extract_session_request_params(kwargs)
        try:
            request_params = parse_authorization_code_response(callback_uri, state=state)
        except OAuth2Error as exc:
            LOGGER.error('Failed to parse OpenID Connect authorization code response. '
                         'Code: %s, description: %s', exc.error, exc.description)
            raise
        request_params['redirect_uri'] = redirect_uri
        payload = OIDCPayload(request_params, **kwargs)
        body = prepare_token_request(payload.grant_type, **payload.to_dict())
        auth = self._get_client_auth()
        response = self._fetch_token(token_endpoint_uri,
                                     body=body,
                                     auth=auth,
                                     headers=self.token_endpoint_request_headers,
                                     method=method,
                                     **session_kwargs)
        return TokenResponse.from_response(response)

    def introspect_token(
            self,
            token_introspection_uri: str,
            token: str | None = None,
            token_type_hint: Literal['access_token', 'refresh_token'] = 'access_token',
            **kwargs
    ) -> dict:
        if token is None:
            # the parameter is annotated to accept `None` only to match
            # the signature of the base method
            raise TypeError('The `token` parameter is required')
        auth = self._get_client_auth()
        resp = super().introspect_token(token_introspection_uri,
                                        token=token,
                                        token_type_hint=token_type_hint,
                                        auth=auth)
        return self.parse_response_token(resp)

    def refresh_token(self,
                      token_endpoint_uri: str | None = None,
                      token: str | None = None,
                      **kwargs) -> TokenResponse:
        if token_endpoint_uri is None or token is None:
            raise TypeError('The `token_endpoint_uri` and `token` parameters are required')
        auth = self._get_client_auth()
        resp = super().refresh_token(token_endpoint_uri, token, auth=auth)
        response = self.parse_response_token(resp)
        return TokenResponse.from_response(response)

    def request(self,
                method: str,
                url: str,
                auth: AuthBase | Callable | str | None = None,
                token: str | None = None,
                **kwargs) -> Response:
        if kwargs.get('withhold_token') is not None:
            raise TypeError('Do not pass `withhold_token` argument as a keyword argument '
                            'to the `OIDCClientSession.request()` method. Instead, use '
                            'the `token` and `auth` arguments to make an authenticated request.')
        if auth is not None:
            auth = self._get_request_auth(auth, token)
        # pass `withhold_token=True` to prevent the parent method
        # from using the `token` and `token_auth` instance methods
        return super().request(method, url, auth=auth, withhold_token=True, **kwargs)

    def parse_response_token(self, resp):
        token_resp = resp.json()
        error = token_resp.get('error')
        if error:
            error_description = token_resp.get('error_description')
            raise self.oauth_error_class(error=error, description=error_description)
        resp.raise_for_status()
        return token_resp

    def _get_request_auth(self,
                          auth: AuthBase | Callable | str,
                          token: str | None = None,
                          **kwargs) -> AuthBase:
        if isinstance(auth, AuthBase):
            return auth
        if callable(auth):
            # accept callable factory for `AuthBase` subclass
            # instance to create a custom authentication mechanism
            return auth(token, **kwargs)
        if auth == self.client_auth_name:
            return self._get_client_auth()
        if auth == self.token_auth_name:
            if token is None:
                raise ValueError('The `token` parameter is required for the token-based '
                                 'authentication')
            return self._get_token_auth(token)
        raise TypeError(f'Invalid authentication method name, or invalid callable, class, '
                        f'or instance used for request authentication: {ascii_str(auth)!a}')

    def _get_client_auth(self) -> AuthBase:
        return self.client_auth_class(self.client_id,
                                      self.client_secret,
                                      auth_method=self.auth_method_with_client_secret)

    def _get_token_auth(self, token: str) -> AuthBase:
        return self.token_auth_class(token,
                                     token_placement=self.token_placement,
                                     client=self)

    def _refresh_token(self,
                       url,
                       refresh_token: str | None = None,
                       body: str = "",
                       headers: dict | None = None,
                       auth: AuthBase | None = None,
                       **kwargs) -> str:
        """
        Override to avoid accessing instance attributes.

        This prevents the use of attributes such as `self.token`,
        ensuring that the OpenID Connect client does not depend
        on any specific session state and can operate in a more
        generic context.
        """
        # the method is overridden so it does not access instance
        # attributes, like `self.token`
        return self._http_post(url, body, auth=auth, headers=headers, **kwargs)


class OIDCPayload(BasicOAuth2Payload):
    default_grant_type = 'authorization_code'
    params_from_query: tuple[str, ...] = ('code', 'grant_type', 'redirect_uri')
    # the 'code' param is not listed as required - its value
    # is verified in `authlib.oauth2.rfc6749.parameters.prepare_token_request()`
    required_params: tuple[str, ...] = ('redirect_uri',)

    def __init__(self, query_params: dict[str, str], **kwargs):
        payload = self._prepare_payload(query_params, **kwargs)
        super().__init__(payload)
        for param in self.required_params:
            if param is None:
                raise ValueError(f'The {param!a} is missing in the payload')

    @property
    def grant_type(self) -> str:
        return self.data.pop('grant_type', self.default_grant_type)

    def to_dict(self) -> dict[str, str]:
        return self.data

    def _prepare_payload(self, query_params: dict[str, str], **kwargs) -> dict[str, str]:
        # The payload is constructed from keyword arguments passed to
        # the constructor, along with parameters extracted from
        # the query string of the redirect request to authorization
        # callback URI. Arguments provided explicitly as `kwargs` take
        # precedence over the ones from the query.
        return dict({key: val
                     for key, val in query_params.items()
                     if key in self.params_from_query},
                    **kwargs)


class TokenValidator:
    strongly_protected_http_methods: tuple[str, ...] = ('post',)

    def __init__(self,
                 client_namespace: ThreadLocalNamespace,
                 realm_name: str,
                 jwks_endpoint_uri: str,
                 token_introspection_uri: str,
                 token_endpoint_uri: str,
                 required_scopes: list[str],
                 issuer: str,
                 cache_jwks: bool = True,
                 max_cached_keys: int = 10,
                 verify_audience: bool = False,
                 introspection_time_threshold: int = 2):
        self._client_namespace = client_namespace
        self._jwks_endpoint_uri = jwks_endpoint_uri
        self._token_endpoint_uri = token_endpoint_uri
        self._prevalidate_required_scopes(required_scopes)
        self._issuer = issuer
        self._verify_audience = verify_audience
        self._decoding_options = dict(verify_aud=self._verify_audience,
                                      verify_exp=True,
                                      require_exp=True)
        self._introspection_time_threshold = introspection_time_threshold
        if cache_jwks:
            self.get_signing_key_from_token = (
                lru_cache(max_cached_keys)(self.get_signing_key_from_token)
            )
        self._introspection_validator = IntrospectionValidator(self._client_namespace,
                                                               realm_name,
                                                               token_introspection_uri,
                                                               required_scopes)

    def get_signing_key_from_token(self, token: str) -> RSAPublicKey:
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

    def validate_jwt(self,
                     access_token,
                     json_web_key,
                     accepted_algorithms,
                     required_claims,
                     required_audience):
        return jwt_decode(access_token,
                          json_web_key,
                          accepted_algorithms=accepted_algorithms,
                          required_claims=required_claims,
                          options=self._decoding_options,
                          required_audience=required_audience,
                          issuer=self._issuer)

    def requires_token_introspection(self,
                                     access_token: dict,
                                     request_method: str) -> bool:
        return (request_method in self.strongly_protected_http_methods
                or self.is_token_nearly_expired(access_token))

    def is_token_nearly_expired(self, access_token: dict) -> bool:
        try:
            exp_claim = access_token['exp']
        except KeyError:
            raise ValueError('Invalid token format: required \'exp\' claim not found '
                             'in the validated token')
        return exp_claim - int(time.time()) < self._introspection_time_threshold * 60

    def introspect_token(self,
                         token: str,
                         token_type: Literal['access_token', 'refresh_token'] = 'access_token'
                         ) -> dict:
        return self._introspection_validator.introspect_token(token, token_type)

    @staticmethod
    def _prevalidate_required_scopes(scopes: list[str]) -> None:
        if 'openid' not in scopes:
            LOGGER.warning('The \'openid\' scope is missing from the required scopes')

    def _get_json_web_keys(self) -> dict[str, RSAPublicKey]:
        signing_keys = {}
        jwks = self._fetch_jwks_document()
        for jwk in jwks['keys']:
            try:
                signing_keys[jwk['kid']] = RSAAlgorithm.from_jwk(json.dumps(jwk))
            except (KeyError, TypeError, ValueError):
                raise IdPServerResponseError('Invalid format of JSON Web Key Set')
        return signing_keys

    def _fetch_jwks_document(self) -> dict:
        try:
            response = self._client_namespace.oidc_client.get(self._jwks_endpoint_uri)
            response.raise_for_status()
        except RequestException as exc:
            raise IdPServerResponseError(f'Failed to fetch JSON Web Key Set') from exc
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


class IntrospectionValidator(IntrospectTokenValidator):

    def __init__(self,
                 client_namespace: ThreadLocalNamespace,
                 realm_name: str,
                 token_introspection_uri: str,
                 required_scopes: list[str]):
        self._client_namespace = client_namespace
        self._token_introspection_uri = token_introspection_uri
        self._required_scopes = required_scopes
        super().__init__(realm=realm_name)

    def introspect_token(self,
                         token: str,
                         token_type: Literal['access_token', 'refresh_token'] = 'access_token'
                         ) -> dict:
        token_resp = self._client_namespace.oidc_client.introspect_token(
            self._token_introspection_uri, token, token_type)
        try:
            self.validate_token(token_resp, self._required_scopes, None)
        except KeyError:
            LOGGER.warning('The \'active\' field is missing from the token introspection '
                           'response, the token is considered inactive')
            raise InvalidOAuth2TokenError
        except (InsufficientScopeError, InvalidOAuth2TokenError) as exc:
            LOGGER.warning('Token validation failed; error code: %a: %a',
                         ascii_str(exc.error), ascii_str(exc.description))
            raise
        return token_resp

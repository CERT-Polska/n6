#  Copyright (c) 2021 NASK. All rights reserved.

import datetime

from n6lib.data_spec.fields import (
    DictResultField,
    Field,
    IntegerField,
    UnicodeLimitedField,
    UnicodeRegexField,
)
from n6lib.auth_db.fields import (
    DateTimeCustomizedField,
    OrgIdField,
    NoWhitespaceSecretField,
    UserLoginField,
    UUID4SecretField,
)
from n6lib.datetime_helpers import int_timestamp_from_datetime
from n6lib.jwt_helpers import (
    JWT_ALGO_HMAC_SHA256,
    JWT_ROUGH_REGEX,
    jwt_decode,
    jwt_encode,
)
from n6lib.log_helpers import get_logger
from n6lib.pyramid_commons.mfa_helpers import (
    LEN_OF_SECRET_KEY,
    MFA_CODE_NUM_OF_DIGITS,
    generate_secret_key,
    generate_secret_key_qr_code_url,
)
from n6lib.pyramid_commons.web_token_helpers import (
    WEB_TOKEN_DATA_KEY_OF_CREATED_ON,
    WEB_TOKEN_DATA_KEY_OF_TOKEN_ID,
)
from n6lib.typing_helpers import (
    MFAConfigData,
    MFASecretConfig,
    String,
    WebTokenData,
)
from n6sdk.exceptions import (
    FieldValueError,
    FieldValueTooLongError,
)

assert issubclass(OrgIdField, Field)
assert issubclass(UserLoginField, Field)


LOGGER = get_logger(__name__)


class _BaseUnicodeSecretField(UnicodeLimitedField, UnicodeRegexField):

    sensitive = True

    disallow_empty = True
    regex = r'.+'

    def _validate_value(self, value):
        try:
            super(_BaseUnicodeSecretField, self)._validate_value(value)
        except FieldValueTooLongError:
            exc = self._field_value_error_marked_safe('too long value')
        except FieldValueError:
            exc = self._field_value_error_marked_safe(self.default_error_msg_if_sensitive if value
                                                      else 'empty value')
        else:
            return
        raise exc

    def _field_value_error_marked_safe(self, public_message):
        exc = FieldValueError(public_message=public_message)
        exc.safe_for_sensitive = True
        return exc


class _BasePasswordField(_BaseUnicodeSecretField):

    default_error_msg_if_sensitive = u'not a valid password'
    max_length = 255


class _BaseUnicodeSecretWithServerSecretField(_BaseUnicodeSecretField):

    server_secret = None

    def __init__(self, **kwargs):
        super(_BaseUnicodeSecretWithServerSecretField, self).__init__(**kwargs)
        if self.server_secret is None:
            raise TypeError("'server_secret' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        if not self.server_secret.strip():
            raise ValueError("'server_secret' must not be empty or "
                             "whitespace-only (got: {!a})"
                             .format(self.server_secret))


class PasswordToBeTestedField(_BasePasswordField):
    pass


class PasswordToBeSetField(_BasePasswordField):

    MIN_PASSWORD_LENGTH = 12

    def _validate_value(self, value):
        super(PasswordToBeSetField, self)._validate_value(value)
        assert isinstance(value, str)
        error_msg_components = list(self._generate_error_msg_components(value))
        if error_msg_components:
            raise self._field_value_error_marked_safe('; '.join(error_msg_components))

    def _generate_error_msg_components(self, value):
        if len(value) < self.MIN_PASSWORD_LENGTH:
            yield 'should contain at least {} characters'.format(self.MIN_PASSWORD_LENGTH)
        if not (any(c.upper() for c in value)
                and any(c.islower() for c in value)
                and any(c.isdigit() for c in value)):
            yield 'should contain at least 1 capital letter, 1 lowercase letter and 1 digit'
        if u'\0' in value:
            yield r'should not contain `null` (\0) characters'
        if value[0].isspace():
            yield 'should not start with a whitespace character'
        if value[-1].isspace():
            yield 'should not end with a whitespace character'


class WebTokenField(_BaseUnicodeSecretWithServerSecretField):

    #
    # Public stuff

    # * class attributes/constructor kwargs:

    default_error_msg_if_sensitive = u'not a valid web token'

    max_length = 10000
    regex = JWT_ROUGH_REGEX

    token_max_age = None

    # * actual initialization:

    def __init__(self, **kwargs):
        super(WebTokenField, self).__init__(**kwargs)
        if self.token_max_age is None:
            raise TypeError("'token_max_age' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        self._token_data_cleaning_field = DictResultField(key_to_subfield_factory = {
            WEB_TOKEN_DATA_KEY_OF_TOKEN_ID: UUID4SecretField,
            WEB_TOKEN_DATA_KEY_OF_CREATED_ON: DateTimeCustomizedField,
        })

    # * public `Field`'s interface:

    def clean_param_value(self, jwt_token):
        # type: (String) -> WebTokenData
        cleaned_jwt_token = super(WebTokenField, self).clean_param_value(jwt_token)
        jwt_payload = jwt_decode(
            cleaned_jwt_token,
            self.server_secret,
            accepted_algorithms=[self._JWT_ALGO],
            required_claims=self._REQUIRED_JWT_CLAIMS)
        token_id = jwt_payload[self._JWT_CLAIM_KEY_OF_TOKEN_ID]
        created_on_timestamp = jwt_payload[self._JWT_CLAIM_KEY_OF_CREATED_ON]
        created_on = self._dt_from_timestamp(created_on_timestamp)
        token_data = {
            WEB_TOKEN_DATA_KEY_OF_TOKEN_ID: token_id,
            WEB_TOKEN_DATA_KEY_OF_CREATED_ON: created_on,
        }
        # (here we consciously call `clean_result_value()`)
        cleaned_token_data = self._token_data_cleaning_field.clean_result_value(token_data)
        return cleaned_token_data

    def clean_result_value(self, token_data):
        # type: (WebTokenData) -> String
        cleaned_token_data = self._token_data_cleaning_field.clean_result_value(token_data)
        token_id = cleaned_token_data[WEB_TOKEN_DATA_KEY_OF_TOKEN_ID]
        created_on = cleaned_token_data[WEB_TOKEN_DATA_KEY_OF_CREATED_ON]
        created_on_timestamp = self._timestamp_from_dt(created_on)
        jwt_payload = {
            self._JWT_CLAIM_KEY_OF_TOKEN_ID: token_id,
            self._JWT_CLAIM_KEY_OF_CREATED_ON: created_on_timestamp,
            self._JWT_CLAIM_KEY_OF_EXPIRES_ON: created_on_timestamp + self.token_max_age,
        }
        jwt_token = jwt_encode(
            jwt_payload,
            self.server_secret,
            algorithm=self._JWT_ALGO,
            required_claims=self._REQUIRED_JWT_CLAIMS)
        cleaned_jwt_token = super(WebTokenField, self).clean_result_value(jwt_token)
        return cleaned_jwt_token

    #
    # Private stuff

    _JWT_ALGO = JWT_ALGO_HMAC_SHA256

    _JWT_CLAIM_KEY_OF_TOKEN_ID = 'jti'
    _JWT_CLAIM_KEY_OF_CREATED_ON = 'iat'
    _JWT_CLAIM_KEY_OF_EXPIRES_ON = 'exp'

    _REQUIRED_JWT_CLAIMS = (
        _JWT_CLAIM_KEY_OF_TOKEN_ID,
        _JWT_CLAIM_KEY_OF_CREATED_ON,
        _JWT_CLAIM_KEY_OF_EXPIRES_ON,
    )

    def _dt_from_timestamp(self, timestamp):
        # type: (int) -> datetime.datetime
        return datetime.datetime.utcfromtimestamp(timestamp)

    def _timestamp_from_dt(self, dt):
        # type: (datetime.datetime) -> int
        return int_timestamp_from_datetime(dt)


class MFASecretConfigField(_BaseUnicodeSecretWithServerSecretField):

    #
    # Public stuff

    # * constants:

    # (related to **input** result values)
    USER_LOGIN_KEY = 'login'
    MFA_KEY_BASE_KEY = 'mfa_key_base'
    assert set(MFAConfigData.__annotations__) == {USER_LOGIN_KEY, MFA_KEY_BASE_KEY}

    # (related to **output** result values)
    SECRET_KEY_KEY = 'secret_key'
    SECRET_KEY_QR_CODE_URL_KEY = 'secret_key_qr_code_url'
    assert set(MFASecretConfig.__annotations__) == {SECRET_KEY_KEY, SECRET_KEY_QR_CODE_URL_KEY}

    # * class attributes/constructor kwargs:

    max_length = LEN_OF_SECRET_KEY
    regex = r'\A[A-Z2-7]{%s}\Z' % LEN_OF_SECRET_KEY

    issuer_name = None

    # * actual initialization:

    def __init__(self, **kwargs):
        super(MFASecretConfigField, self).__init__(**kwargs)
        if self.issuer_name is None:
            raise TypeError("'issuer_name' not specified for {} "
                            "(neither as a class attribute nor "
                            "as a constructor argument)"
                            .format(self.__class__.__qualname__))
        self._mfa_config_data_cleaning_field = DictResultField(key_to_subfield_factory={
            self.USER_LOGIN_KEY: UserLoginField,
            self.MFA_KEY_BASE_KEY: NoWhitespaceSecretField,
        })

    # * public `Field`'s interface:

    def clean_param_value(self, value):
        raise TypeError("it's a result-only field")

    def clean_result_value(self, mfa_config_data):
        # type: (MFAConfigData) -> MFASecretConfig
        cleaned_data = self._mfa_config_data_cleaning_field.clean_result_value(mfa_config_data)
        user_login = cleaned_data[self.USER_LOGIN_KEY]
        mfa_key_base = cleaned_data[self.MFA_KEY_BASE_KEY]
        secret_key = generate_secret_key(mfa_key_base, self.server_secret)
        secret_key_qr_code_url = generate_secret_key_qr_code_url(secret_key,
                                                                 user_login,
                                                                 self.issuer_name)
        return {
            self.SECRET_KEY_KEY: super(MFASecretConfigField, self).clean_result_value(secret_key),
            self.SECRET_KEY_QR_CODE_URL_KEY: secret_key_qr_code_url,
        }


class MFACodeField(IntegerField):

    sensitive = True
    default_error_msg_if_sensitive = u'not a valid MFA code'

    min_value = 0
    max_value = (10 ** MFA_CODE_NUM_OF_DIGITS) - 1

    def clean_result_value(self, value):
        raise TypeError("it's a param-only field")

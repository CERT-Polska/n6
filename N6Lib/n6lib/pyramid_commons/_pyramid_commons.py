# Copyright (c) 2013-2024 NASK. All rights reserved.

import contextlib
import copy
import datetime
import os.path as osp
import uuid
from typing import Optional

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPForbidden,
    HTTPNotFound,
    HTTPUnauthorized,
)
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.security import (
    Allow,
    Authenticated,
    Everyone,
    forget,
    remember,
)
from pyramid.tweens import EXCVIEW

from n6lib.auth_api import (
    EVENT_DATA_RESOURCE_IDS,
    AuthAPIUnauthenticatedError,
)
from n6lib.auth_db import (
    WEB_TOKEN_TYPE_FOR_LOGIN,
    WEB_TOKEN_TYPE_FOR_MFA_CONFIG,
    WEB_TOKEN_TYPE_FOR_PASSWORD_RESET,
)
from n6lib.auth_db.api import (
    AuthDatabaseAPIClientError,
    AuthDatabaseAPILookupError,
)
from n6lib.common_helpers import (
    ascii_str,
    ipv4_to_str,
    make_condensed_debug_msg,
    make_exc_ascii_str,
    make_hex_id,
    memoized,
    str_to_bool,
)
from n6lib.config import (
    Config,
    join_config_specs,
)
from n6lib.const import (
    CATEGORY_ENUMS,
    WSGI_SSL_ORG_ID_FIELD,
    WSGI_SSL_USER_ID_FIELD,
)
from n6lib.log_helpers import get_logger
from n6lib.oidc_provider_api import TokenValidationError
from n6lib.pyramid_commons import mfa_helpers
from n6lib.pyramid_commons import web_token_helpers
from n6lib.pyramid_commons._config_converters import (
    conv_int_only_positive,
    conv_tuple_of_categories,
    conv_server_secret_str,
    conv_token_type_to_settings,
    conv_web_url,
)
from n6lib.pyramid_commons._generic_view_mixins import (
    ConfigFromPyramidSettingsViewMixin,
    EssentialAPIsViewMixin,
    WithDataSpecsAlsoForRequestParamsViewMixin,
)
from n6lib.pyramid_commons.data_spec_fields import (
    Field,
    KnowledgeBaseLangField,
    KnowledgeBaseSearchQueryField,
    MFACodeField,
    MFASecretConfigField,
    OrgIdField,
    PasswordToBeSetField,
    PasswordToBeTestedField,
    UserLoginField,
    WebTokenField,
)
from n6lib.pyramid_commons.knowledge_base_helpers import (
    build_knowledge_base_data,
    search_in_knowledge_base,
)
from n6lib.pyramid_commons.mfa_helpers import MFA_CODE_MAX_ACCEPTABLE_AGE_IN_SECONDS
from n6lib.pyramid_commons.renderers import (
    # by importing that submodule we ensure that
    # these stream renderers are registered
    # (see the assertions at the end of the current module)
    StreamRenderer_csv,
    SnortDNSRenderer,
    SnortHTTPRenderer,
    SnortIPRenderer,
    SnortIPBlacklistRenderer,
    SuricataDNSRenderer,
    SuricataHTTPRenderer,
    SuricataIPRenderer,
    SuricatatIPBlacklistRenderer,
)
from n6lib.pyramid_commons.web_token_helpers import WEB_TOKEN_DATA_KEY_OF_TOKEN_ID
from n6lib.typing_helpers import (
    AccessInfo,
    AuthData,
    JsonableDict,
    MFAConfigData,
    WebTokenData,
)
from n6sdk.pyramid_commons import (
    AbstractViewBase,
    BaseAuthenticationPolicy,
    ConfigHelper,
    DefaultStreamViewBase,
    registered_stream_renderers,
)
from n6sdk.pyramid_commons import (
    CommaSeparatedParamValuesViewMixin,
    OmittingEmptyParamsViewMixin,
    PreparingNoParamsViewMixin,
)


LOGGER = get_logger(__name__)


#
# Debugging info helpers

def log_debug_info_on_http_exc(http_exc):
    code = getattr(http_exc, 'code', None)
    if not isinstance(code, int) or not 200 <= code < 500:
        LOGGER.error(
            'Condensed debug info related to %a:\n%s',
            http_exc, make_condensed_debug_msg())


#
# SSL/TLS-based-auth helpers

def get_certificate_credentials(request):
    org_id = request.environ.get(WSGI_SSL_ORG_ID_FIELD)
    user_id = request.registry.auth_manage_api.adjust_if_is_legacy_user_login(
        request.environ.get(WSGI_SSL_USER_ID_FIELD))
    if org_id is not None and user_id is not None:
        if ',' in org_id:
            LOGGER.warning('Comma in org_id %a.', org_id)
            return None, None
        if ',' in user_id:
            LOGGER.warning('Comma in user_id %a.', user_id)
            return None, None
    return org_id, user_id


#
# Basic classes

class N6PortalRootFactory(object):

    """
    A simple Root Factory for a website using URL dispatch,
    providing a simple access control list.
    """

    __acl__ = [
        (Allow, Everyone, 'all'),
        (Allow, Authenticated, 'auth'),
    ]

    def __init__(self, request):
        self.request = request


#
# View (endpoint implementation) classes

class N6DefaultStreamViewBase(EssentialAPIsViewMixin, DefaultStreamViewBase):

    break_on_result_cleaning_error = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_access_attributes()

    def _set_access_attributes(self):
        assert self.resource_id in EVENT_DATA_RESOURCE_IDS
        access_info: Optional[AccessInfo] = self.auth_api.get_access_info(self.auth_data)
        if not self.is_event_data_resource_available(access_info, self.resource_id):
            LOGGER.warning('User %a (org_id=%a) is trying to access the '
                           'resource %a - but is not authorized to do so',
                           self.user_id, self.org_id, self.resource_id)
            raise HTTPForbidden(u'Access not allowed.')
        assert access_info is not None
        self.access_zone_conditions = access_info['access_zone_conditions']
        self.res_limits = access_info['rest_api_resource_limits'][self.resource_id]
        self.full_access = access_info['rest_api_full_access']

    def get_clean_param_dict_kwargs(self):
        return dict(
            auth_api=self.auth_api,
            full_access=self.full_access,
            res_limits=self.res_limits,
        )

    def get_clean_result_dict_kwargs(self):
        # in the `params` dict, the value for the 'opt.primary' key, if
        # present, must be a 1-element list containing the cleaned value
        # of the `opt.primary` flag: True or False (the `opt.primary` data
        # spec field has single_param=True, and its type is FlagField)
        [opt_primary] = self.params.get('opt.primary', [False])
        return dict(
            auth_api=self.auth_api,
            full_access=self.full_access,
            opt_primary=opt_primary,
        )

    def get_extra_api_kwargs(self):
        return dict(
            data_spec=self.data_spec,
            access_zone_conditions=self.access_zone_conditions,
        )

    @classmethod
    def adjust_exc(cls, exc):
        http_exc = super().adjust_exc(exc)
        log_debug_info_on_http_exc(http_exc)
        return http_exc


class N6LimitedStreamView(N6DefaultStreamViewBase):

    """
    A view class that implements global limit for returned items.

    Results are limited by adding an `opt.limit` parameter to
    a query, if it is not present already, or its value is too high.
    """

    GLOBAL_ITEM_NUMBER_LIMIT = 1000

    def prepare_params(self):
        params = super().prepare_params()
        if 'opt.limit' not in params or params['opt.limit'][0] > self.GLOBAL_ITEM_NUMBER_LIMIT:
            params['opt.limit'] = [self.GLOBAL_ITEM_NUMBER_LIMIT]
        return params


class _DashboardConfigViewMixin(ConfigFromPyramidSettingsViewMixin):

    @classmethod
    def prepare_config_custom_converters(cls):
        return {
            'int': conv_int_only_positive,
            'tuple_of_categories': conv_tuple_of_categories,
        }

    config_spec = '''
        [portal_dashboard]
        time_range_in_days = 30 :: int
        counted_categories =
            cnc ,
            bots ,
            vulnerable ,
            amplifier ,
            malurl ,
                :: tuple_of_categories
    '''

    def get_time_range_in_days(self):
        return self.config_full['portal_dashboard']['time_range_in_days']

    def get_counted_categories(self):
        return self.config_full['portal_dashboard']['counted_categories']


class N6DashboardView(EssentialAPIsViewMixin,
                      _DashboardConfigViewMixin,
                      PreparingNoParamsViewMixin,
                      AbstractViewBase):

    SUMMARY_KEY = 'all'

    def make_response(self):
        at = datetime.datetime.utcnow().replace(microsecond=0)
        time_range_in_days = self.get_time_range_in_days()
        since = at - datetime.timedelta(days=time_range_in_days-1)
        counts = self._obtain_counts(since)
        response_data = {
            'at': at,
            'time_range_in_days': time_range_in_days,
            'counts': counts,
        }
        return self.json_response(response_data)

    def _obtain_counts(self, since: datetime.datetime) -> dict[str, int]:
        access_filtering_conditions = self.get_access_zone_filtering_conditions('inside')
        all_counts: dict[str, int] = self.data_backend_api.get_counts_per_category(
            self.auth_data,
            access_filtering_conditions,
            since)
        assert all_counts.keys() == set(CATEGORY_ENUMS)
        counts: dict[str, int] = {
            category: all_counts[category]
            for category in self.get_counted_categories()}
        counts[self.SUMMARY_KEY] = sum(
            single_count
            for category, single_count in all_counts.items())
        return counts


# noinspection PyAbstractClass
class _AbstractClientFormalitiesView(EssentialAPIsViewMixin, AbstractViewBase):

    """
    A base class for creating views that focus on such "formalities"
    as client state, organization's configuration, authentication etc.
    """

    params_only_from_body = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Note that -- even if the client is authenticated (so the value
        # of `self.auth_data` is available and `self.auth_data_or_none`
        # is equal to it, and is not `None`) -- the `self._access_info`
        # attribute may here be set to `None`. It is like this because
        # the `self.auth_api.get_access_info(self.auth_data)` call may
        # still return `None` (this is the case when the organization
        # has no access to any subsources, no matter whether its fields
        # `access_to_{inside,threats,search}` are `True` or `False`).
        self._access_info: Optional[AccessInfo] = (
            self.auth_api.get_access_info(self.auth_data)
            if self.auth_data_or_none is not None
            else None)

    @property
    def full_access(self):
        return (self._access_info is not None
                and self._access_info['rest_api_full_access'])

    def iter_available_event_data_resource_ids(self):
        if self.auth_data_or_none is None:
            return
        for resource_id in EVENT_DATA_RESOURCE_IDS:
            if self.is_event_data_resource_available(self._access_info, resource_id):
                yield resource_id


class _AbstractKnowledgeBaseRelatedView(WithDataSpecsAlsoForRequestParamsViewMixin,
                                        ConfigFromPyramidSettingsViewMixin,
                                        AbstractViewBase):

    config_spec = '''
        [knowledge_base]
        active = false :: bool
        base_dir = ~/.n6_knowledge_base/ :: str
    '''

    @classmethod
    def concrete_view_class(cls, **kwargs):
        view_class = super().concrete_view_class(**kwargs)
        view_class._provide_knowledge_base_data()
        return view_class

    @classmethod
    def is_knowledge_base_enabled(cls) -> bool:
        return cls._knowledge_base_data is not None

    @classmethod
    def _provide_knowledge_base_data(cls) -> None:
        assert cls.config_full is not None
        if cls.config_full['knowledge_base']['active']:
            base_dir = osp.expanduser(cls.config_full['knowledge_base']['base_dir'])
            cls._knowledge_base_data = cls._get_knowledge_base_data(base_dir)
        else:
            cls._knowledge_base_data = None

    @staticmethod
    @memoized(max_size=1)
    def _get_knowledge_base_data(base_dir: str) -> dict:
        return build_knowledge_base_data(base_dir)


class N6InfoView(PreparingNoParamsViewMixin,
                 _AbstractClientFormalitiesView,
                 _AbstractKnowledgeBaseRelatedView):

    """
    Get info about the client (among others, whether the client is
    authenticated and, if it is, which REST API resources it has access
    to...) and about the Portal API itself (whether configuration of
    REST API keys is enabled).
    """

    def make_response(self):
        body = {}
        if self.request.auth_data:
            assert self.auth_data is self.request.auth_data
            body['authenticated'] = True
            body['org_id'] = self.org_id
            org_actual_name = self.auth_api.get_org_actual_name(self.auth_data)
            if org_actual_name is not None:
                body['org_actual_name'] = org_actual_name
            body['available_resources'] = sorted(self.iter_available_event_data_resource_ids())
            if self.full_access:
                body['full_access'] = True
            if self.auth_api.is_api_key_authentication_enabled():
                body['api_key_auth_enabled'] = True
            if self.is_knowledge_base_enabled():
                body['knowledge_base_enabled'] = True
        else:
            body['authenticated'] = False
        assert EVENT_DATA_RESOURCE_IDS >= set(body.get('available_resources', ()))
        return self.json_response(body)


class N6InfoConfigView(PreparingNoParamsViewMixin, _AbstractClientFormalitiesView):

    _ALLOWED_KEYS_OF_EMAIL_NOTIFICATIONS_INFO = frozenset({
        'email_notification_times',
        'email_notification_addresses',
        'email_notification_language',
        'email_notification_business_days_only',
    })
    _ALLOWED_KEYS_OF_INSIDE_CRITERIA_INFO = frozenset({
        'cc_seq',
        'fqdn_seq',
        'url_seq',
        'asn_seq',
        'ip_min_max_seq',
    })

    def make_response(self):
        conf = self._get_notifications_and_inside_criteria_conf()
        # * Obligatory items:
        body: JsonableDict = {
            'available_resources': sorted(self.iter_available_event_data_resource_ids()),
            'user_id': self.user_id,
            'org_id': self.org_id,
        }
        assert EVENT_DATA_RESOURCE_IDS >= set(body['available_resources'])
        # * Optional items:
        body.update(self._yield_org_actual_name())
        body.update(self._yield_email_notifications_info(conf.get('email_notifications')))
        body.update(self._yield_inside_criteria_info(conf.get('inside_criteria')))
        return self.json_response(body)

    def _get_notifications_and_inside_criteria_conf(self):
        conf = self.auth_api.get_combined_config(self.auth_data)
        if conf is None:
            conf = {}
        return conf

    def _yield_org_actual_name(self):
        org_actual_name = self.auth_api.get_org_actual_name(self.auth_data)
        if org_actual_name is not None:
            yield 'org_actual_name', org_actual_name

    def _yield_email_notifications_info(self, email_notifications_conf):
        if email_notifications_conf:
            # To be on a safe side, let's limit the
            # items to the explicitly allowed keys.
            info = {key: val
                    for key, val in email_notifications_conf.items()
                    if key in self._ALLOWED_KEYS_OF_EMAIL_NOTIFICATIONS_INFO}
            yield 'email_notifications', info

    def _yield_inside_criteria_info(self, inside_criteria_conf):
        if inside_criteria_conf:
            # To be on a safe side, let's limit the
            # items to the explicitly allowed keys.
            info = {key: val
                    for key, val in inside_criteria_conf.items()
                    if key in self._ALLOWED_KEYS_OF_INSIDE_CRITERIA_INFO}
            if 'ip_min_max_seq' in info:
                info['ip_min_max_seq'] = [{'min_ip': ipv4_to_str(min_ip),
                                           'max_ip': ipv4_to_str(max_ip)}
                                          for min_ip, max_ip in info['ip_min_max_seq']]
            yield 'inside_criteria', info


# noinspection PyAbstractClass
class _AbstractPortalAuthRelatedView(WithDataSpecsAlsoForRequestParamsViewMixin,
                                     ConfigFromPyramidSettingsViewMixin,
                                     _AbstractClientFormalitiesView):

    @classmethod
    def get_default_http_methods(cls):
        return 'POST'

    #
    # Configuration-related stuff

    @classmethod
    def prepare_config_custom_converters(cls):
        return {
            'token_type_to_settings': conv_token_type_to_settings,
            'server_secret_str': conv_server_secret_str,
            'web_url': conv_web_url,
        }

    config_spec = '''
        [web_tokens]
        token_type_to_settings :: token_type_to_settings
        server_secret_for_pseudo_tokens :: server_secret_str

        [portal_frontend_properties]
        base_url :: web_url
    '''

    @classmethod
    def get_token_server_secret(cls, token_type: str) -> str:
        return cls.config_full['web_tokens']['token_type_to_settings'][token_type]['server_secret']

    @classmethod
    def get_token_max_age(cls, token_type: str) -> int:
        return cls.config_full['web_tokens']['token_type_to_settings'][token_type]['token_max_age']

    @classmethod
    def get_server_secret_for_pseudo_tokens(cls) -> str:
        return cls.config_full['web_tokens']['server_secret_for_pseudo_tokens']

    @classmethod
    def get_portal_frontend_base_url(cls) -> str:
        return cls.config_full['portal_frontend_properties']['base_url']

    #
    # Data-spec-related stuff

    @classmethod
    def prepare_field_specs(cls) -> dict[str, Field]:

        # Typical combinations of field constructor's generic **kwargs:
        in_params = dict(in_params='required', single_param=True)
        in_result = dict(in_result='required')
        in_both = dict(in_params, **in_result)

        return dict(
            super().prepare_field_specs(),

            login = UserLoginField(**in_params),
            password_to_be_tested = PasswordToBeTestedField(**in_params),
            password_to_be_set = PasswordToBeSetField(**in_params),

            token_for_login=WebTokenField(
                server_secret=cls.get_token_server_secret(WEB_TOKEN_TYPE_FOR_LOGIN),
                token_max_age=cls.get_token_max_age(WEB_TOKEN_TYPE_FOR_LOGIN),
                **in_both),

            pseudo_token_for_login=WebTokenField(
                server_secret=cls.get_server_secret_for_pseudo_tokens(),
                token_max_age=cls.get_token_max_age(token_type=WEB_TOKEN_TYPE_FOR_LOGIN),
                **in_both),

            token_for_mfa_config=WebTokenField(
                server_secret=cls.get_token_server_secret(WEB_TOKEN_TYPE_FOR_MFA_CONFIG),
                token_max_age=cls.get_token_max_age(WEB_TOKEN_TYPE_FOR_MFA_CONFIG),
                **in_both),

            token_for_password_reset=WebTokenField(
                server_secret=cls.get_token_server_secret(WEB_TOKEN_TYPE_FOR_PASSWORD_RESET),
                token_max_age=cls.get_token_max_age(WEB_TOKEN_TYPE_FOR_PASSWORD_RESET),
                **in_params),
        )

    #
    # Helper methods related to web token generation/persistence

    generate_new_token_id = staticmethod(web_token_helpers.generate_new_token_id)
    generate_new_pseudo_token_data = staticmethod(web_token_helpers.generate_new_pseudo_token_data)

    @contextlib.contextmanager
    def ensure_deleting_token_on_exception(self, token_id, but_not_for=()):
        try:
            yield
        except but_not_for:
            raise
        except:
            with self.auth_manage_api:
                self.auth_manage_api.delete_web_token(token_id)
            raise

    def create_token(self,
                     token_type: str,
                     login: str) -> WebTokenData:
        token_id = self.generate_new_token_id()
        try:
            created_on = self.auth_manage_api.create_web_token_for_nonblocked_user(token_id,
                                                                                   token_type,
                                                                                   login)
        except AuthDatabaseAPILookupError:
            LOGGER.warning('Cannot create a %a web token for %a (%s)',
                           token_type, login, make_exc_ascii_str())
            raise HTTPForbidden
        assert isinstance(created_on, datetime.datetime)
        return dict(
            token_id=token_id,
            created_on=created_on,
        )

    def get_login_of_legit_token_owner(self,
                                       token_id: str,
                                       token_type: str) -> str:
        token_max_age = self.get_token_max_age(token_type)
        self.auth_manage_api.delete_outdated_web_tokens_of_given_type(token_type, token_max_age)
        # Note: after the above call we are sure that the token
        # identified by `token_id`, if found, is *not* expired.
        try:
            stored_token_type = self.auth_manage_api.get_web_token_type(token_id)
            if token_type != stored_token_type:
                LOGGER.warning('Web token type mismatch: %a vs %a', token_type, stored_token_type)
                raise HTTPForbidden
            return self.auth_manage_api.get_login_of_nonblocked_web_token_owner(token_id)
        except AuthDatabaseAPILookupError:
            LOGGER.warning('Could not obtain the owner of a %a web token', token_type)
            raise HTTPForbidden

    #
    # Helper method related to authentication headers

    def make_logged_in_response_headerlist(self,
                                           org_id: str,
                                           user_id: str) -> list[tuple[str, str]]:
        """
        A utility method: get a list of headers that provide
        authentication information (specific to the authentication
        policy currently in use) for subsequent request(s).
        """
        credentials = BaseUserAuthenticationPolicy.merge_orgid_userid(org_id, user_id)
        response_headerlist = remember(self.request, credentials)
        return response_headerlist


# noinspection PyAbstractClass
class _AbstractPortalMFARelatedView(_AbstractPortalAuthRelatedView):

    #
    # Configuration-related stuff

    config_spec = join_config_specs(_AbstractPortalAuthRelatedView.config_spec, '''
        [mfa]
        server_secret :: server_secret_str
        issuer_name = n6 Portal :: str
    ''')

    @classmethod
    def get_mfa_server_secret(cls) -> str:
        return cls.config_full['mfa']['server_secret']

    @classmethod
    def get_mfa_issuer_name(cls) -> str:
        return cls.config_full['mfa']['issuer_name']

    #
    # Data-spec related stuff

    @classmethod
    def prepare_field_specs(cls) -> dict[str, Field]:
        return dict(
            super().prepare_field_specs(),

            mfa_code = MFACodeField(
                in_params='required',
                single_param=True,
            ),
            mfa_config = MFASecretConfigField(
                in_result='required',
                server_secret=cls.get_mfa_server_secret(),
                issuer_name=cls.get_mfa_issuer_name(),
            ),
        )

    #
    # Helper methods related to MFA generation/persistence + actual authentication

    generate_new_mfa_key_base = staticmethod(mfa_helpers.generate_new_mfa_key_base)
    generate_secret_key = staticmethod(mfa_helpers.generate_secret_key)
    generate_secret_key_qr_code_url = staticmethod(mfa_helpers.generate_secret_key_qr_code_url)
    does_mfa_code_matches_now = staticmethod(mfa_helpers.does_mfa_code_matches_now)

    def create_provisional_mfa_config(self, login: str) -> tuple[MFAConfigData, WebTokenData]:
        token_data = self.create_token(WEB_TOKEN_TYPE_FOR_MFA_CONFIG, login)
        mfa_key_base = self.generate_new_mfa_key_base()
        self.auth_manage_api.create_provisional_mfa_config(mfa_key_base,
                                                           token_data['token_id'])
        mfa_config_data = dict(
            mfa_key_base=mfa_key_base,
            login=login,
        )
        assert isinstance(token_data, dict) and token_data
        return mfa_config_data, token_data

    def turn_provisional_mfa_config_into_actual(self,
                                                token_id: str,
                                                mfa_code: int,
                                                allow_overwrite_existing: bool = False,
                                                ) -> AuthData:
        login = self.get_login_of_legit_token_owner(token_id, WEB_TOKEN_TYPE_FOR_MFA_CONFIG)
        if (self.auth_manage_api.get_actual_mfa_key_base_or_none(login) is not None
              and not allow_overwrite_existing):
            LOGGER.warning('Actual MFA configuration for user %a already exists', login)
            raise HTTPForbidden
        mfa_key_base = self.auth_manage_api.get_provisional_mfa_key_base_or_none(token_id)
        if mfa_key_base is None:
            LOGGER.warning('Provisional MFA configuration for user %a not found', login)
            raise HTTPForbidden
        auth_data = self._try_to_authenticate_using_login_and_mfa(login, mfa_code, mfa_key_base)
        if auth_data is None:
            raise HTTPConflict
        self.auth_manage_api.set_actual_mfa_key_base(login, mfa_key_base)
        assert isinstance(auth_data, dict) and auth_data
        return auth_data

    def authenticate_with_mfa_code(self,
                                   login: str,
                                   mfa_code: int) -> AuthData:
        try:
            if self.auth_manage_api.is_user_blocked(login):
                LOGGER.warning('Auth of %a by MFA code failed - user is blocked', login)
                raise HTTPForbidden
        except AuthDatabaseAPILookupError:
            LOGGER.warning('Auth of %a by MFA code failed (%s)', login, make_exc_ascii_str())
            raise HTTPForbidden
        mfa_key_base = self.get_actual_mfa_key_base(login)
        auth_data = self._try_to_authenticate_using_login_and_mfa(login, mfa_code, mfa_key_base)
        if auth_data is None:
            raise HTTPForbidden
        assert isinstance(auth_data, dict) and auth_data
        return auth_data

    def get_actual_mfa_key_base(self, login: str) -> str:
        mfa_key_base = self.auth_manage_api.get_actual_mfa_key_base_or_none(login)
        if mfa_key_base is None:
            LOGGER.warning('Actual MFA configuration for user %a not found', login)
            raise HTTPForbidden
        assert isinstance(mfa_key_base, str) and mfa_key_base
        return mfa_key_base

    #
    # Internal helpers

    def _try_to_authenticate_using_login_and_mfa(self,
                                                 login: str,
                                                 mfa_code: int,
                                                 mfa_key_base: str) -> Optional[AuthData]:
        self.auth_manage_api.delete_outdated_spent_mfa_codes(
            mfa_code_max_age=MFA_CODE_MAX_ACCEPTABLE_AGE_IN_SECONDS)
        secret_key = self.generate_secret_key(mfa_key_base, self.get_mfa_server_secret())
        if not self.does_mfa_code_matches_now(mfa_code, secret_key):
            LOGGER.warning('Auth of %a by MFA code failed - MFA code does not match', login)
            return None
        if self.auth_manage_api.is_mfa_code_spent_for_user(mfa_code, login):
            LOGGER.warning('Auth of %a by MFA code failed - MFA code spent', login)
            return None
        org_id = self.auth_manage_api.get_user_org_id(login)
        return dict(
            org_id=org_id,
            user_id=login,
        )


class N6LoginView(_AbstractPortalMFARelatedView):

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            # data spec to clean request params
            request_params=cls.make_data_spec(
                login=cls.field_specs['login'],
                password=cls.field_specs['password_to_be_tested'],
            ),

            # data specs to clean response payload bodies
            success_response=cls.make_data_spec(
                token=cls.field_specs['token_for_login'],
            ),
            hidden_failure_response=cls.make_data_spec(
                token=cls.field_specs['pseudo_token_for_login'],
            ),
            forced_new_mfa_config_response=cls.make_data_spec(
                token=cls.field_specs['token_for_mfa_config'],
                mfa_config=cls.field_specs['mfa_config'],
            ),
        )

    def make_response(self):
        logged_out_response_headerlist = forget(self.request)
        login = self.params['login']
        password = self.params['password']

        with self.auth_manage_api as api:
            if api.do_nonblocked_user_and_password_exist_and_match(login, password):
                user_mfa_key_base = api.get_actual_mfa_key_base_or_none(login)
                if user_mfa_key_base is not None:
                    # Credentials OK, user not blocked and actual MFA
                    # config found -> let's make it possible to proceed
                    # to log-in step #2.
                    token_data_for_login = self.create_token(WEB_TOKEN_TYPE_FOR_LOGIN, login)
                    return self.cleaned_json_response(
                        {
                            'token': token_data_for_login,
                        },
                        data_spec=self.data_specs['success_response'],
                        headerlist=logged_out_response_headerlist,
                        status_code=200)
                else:
                    # Credentials OK and user not blocked, but no actual
                    # MFA config found -> let's create a provisional one...
                    try:
                        (provisional_mfa_config_data,
                         token_data_for_mfa_config) = self.create_provisional_mfa_config(login)
                    except HTTPForbidden:
                        # This should not be possible, but let's behave
                        # defensively and not-revealing-anything-ly here.
                        LOGGER.error('Could not create provisional MFA configuration for %a',
                                     login)
                    else:
                        # ...and then, let's make it possible to
                        # proceed to forced MFA config setup step.
                        return self.cleaned_json_response(
                            {
                                'token': token_data_for_mfa_config,
                                'mfa_config': provisional_mfa_config_data,
                            },
                            data_spec=self.data_specs['forced_new_mfa_config_response'],
                            headerlist=logged_out_response_headerlist,
                            status_code=403)
            else:
                # Credentials *not* OK, or user blocked.
                password_characterization = ('non-empty' if password else 'empty')
                LOGGER.warning('User failed to authenticate with credentials: '
                               'login (user id) set to %a + %s password',
                               login, password_characterization)

        # -> Let's make it possible to proceed to log-in step #2, *but*
        # with a guarantee that it will fail, as the returned token is
        # a pseudo-token (i.e., a *secretly invalid* token).
        return self.cleaned_json_response(
            {
                'token': self.generate_new_pseudo_token_data(),
            },
            data_spec=self.data_specs['hidden_failure_response'],
            headerlist=logged_out_response_headerlist,
            status_code=200)


class N6LoginMFAView(_AbstractPortalMFARelatedView):

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params=cls.make_data_spec(
                token=cls.field_specs['token_for_login'],
                mfa_code=cls.field_specs['mfa_code'],
            ),
        )

    def exc_on_param_value_cleaning_error(self, cleaning_error, invalid_params_set):
        return HTTPForbidden

    def make_response(self):
        token_id = self.params['token'][WEB_TOKEN_DATA_KEY_OF_TOKEN_ID]
        mfa_code = self.params['mfa_code']

        with self.ensure_deleting_token_on_exception(token_id):
            with self.auth_manage_api:
                auth_data = self._authenticate(token_id, mfa_code)
                self.auth_manage_api.delete_web_tokens_of_given_type_and_owner(
                    WEB_TOKEN_TYPE_FOR_LOGIN,
                    login=auth_data['user_id'])

        logged_in_response_headerlist = self.make_logged_in_response_headerlist(**auth_data)
        return self.json_response({}, headerlist=logged_in_response_headerlist)

    def _authenticate(self, token_id, mfa_code):
        login = self.get_login_of_legit_token_owner(token_id, WEB_TOKEN_TYPE_FOR_LOGIN)
        return self.authenticate_with_mfa_code(login, mfa_code)


class N6LoginMFAConfigConfirmView(_AbstractPortalMFARelatedView):

    NOTICE_KEY = 'mfa_config_done'

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params=cls.make_data_spec(
                token=cls.field_specs['token_for_mfa_config'],
                mfa_code=cls.field_specs['mfa_code'],
            ),
        )

    invalid_params_set_to_custom_exc_factory = {
        frozenset({'token'}): HTTPForbidden,
    }

    def make_response(self):
        token_id = self.params['token'][WEB_TOKEN_DATA_KEY_OF_TOKEN_ID]
        mfa_code = self.params['mfa_code']

        with self.ensure_deleting_token_on_exception(token_id, but_not_for=HTTPConflict):
            with self.auth_manage_api:
                auth_data = self.turn_provisional_mfa_config_into_actual(
                    token_id,
                    mfa_code,
                    allow_overwrite_existing=False)
                login = auth_data['user_id']
                self.auth_manage_api.delete_web_tokens_of_given_type_and_owner(
                    WEB_TOKEN_TYPE_FOR_MFA_CONFIG,
                    login)

        with self.auth_manage_api:
            self.send_mail_notice_to_user(login, self.NOTICE_KEY)

        logged_in_response_headerlist = self.make_logged_in_response_headerlist(**auth_data)
        return self.json_response({}, headerlist=logged_in_response_headerlist)


class N6LoginOIDCView(EssentialAPIsViewMixin, AbstractViewBase):

    class UserCreateFailure(Exception):
        pass

    def make_response(self):
        if not self.oidc_provider_api.is_active:
            raise HTTPForbidden('Authentication through external identity provider is disabled')
        if self.request.auth_data is not None:
            return self.json_response(dict(status='logged_in'))
        user_id = self.oidc_provider_api.unauthenticated_credentials.user_id
        org_id = self.oidc_provider_api.unauthenticated_credentials.org_id
        if user_id is not None and org_id is not None:
            try:
                self._try_to_create_new_user(user_id, org_id)
                return self.json_response(dict(status='user_created'))
            except self.UserCreateFailure:
                return self.json_response(dict(status='user_not_created'), status_code=403)
        raise HTTPForbidden

    def _try_to_create_new_user(self, user_id, org_id):
        with self.auth_manage_api as api:
            try:
                api.get_user_by_login(login=user_id)
                LOGGER.warning('User tried to authenticate through an external OpenID '
                               'Connect Identity Provider but failed, because although his '
                               'user record exists in the AuthDB, it is assigned to '
                               'a different organization. '
                               'User login: %s - organization: %s', user_id, org_id)
                raise self.UserCreateFailure
            except AuthDatabaseAPILookupError:
                try:
                    org = api.get_org_by_org_id(org_id=org_id)
                    api.create_new_user(org, user_id=user_id)
                    LOGGER.info('Created a new account for the user authenticated through '
                                'external OpenID Connect Identity Provider. '
                                'User login: %s - organization: %s', user_id, org_id)
                    return True
                except AuthDatabaseAPILookupError:
                    LOGGER.warning('User tried to authenticate through an external OpenID '
                                   'Connect Identity Provider but failed, because his '
                                   'organization does not exist in the AuthDB. '
                                   'User login: %s - organization: %s', user_id, org_id)
                    raise self.UserCreateFailure


class N6MFAConfigView(_AbstractPortalMFARelatedView):

    @classmethod
    def get_default_http_methods(cls):
        return 'GET', 'POST'

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            new_mfa_config_response=cls.make_data_spec(
                token=cls.field_specs['token_for_mfa_config'],
                mfa_config=cls.field_specs['mfa_config'],
            ),
            present_mfa_config_response=cls.make_data_spec(
                mfa_config=cls.field_specs['mfa_config'],
            ),
        )

    def make_response(self):
        if self.request.method == 'POST':
            return self._make_post_response()
        return self._make_get_response()

    def _make_post_response(self):
        login = self.user_id
        with self.auth_manage_api:
            provisional_mfa_config_data, token_data = self.create_provisional_mfa_config(login)
        return self.cleaned_json_response(
            {
                'token': token_data,
                'mfa_config': provisional_mfa_config_data,
            },
            data_spec=self.data_specs['new_mfa_config_response'],
            status_code=200)

    def _make_get_response(self):
        login = self.user_id
        with self.auth_manage_api:
            mfa_key_base = self.get_actual_mfa_key_base(login)
        return self.cleaned_json_response(
            {
                'mfa_config': {
                    'login': login,
                    'mfa_key_base': mfa_key_base,
                },
            },
            data_spec=self.data_specs['present_mfa_config_response'],
            status_code=200)


class N6MFAConfigConfirmView(_AbstractPortalMFARelatedView):

    NOTICE_KEY = 'mfa_config_done'

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params=cls.make_data_spec(
                token=cls.field_specs['token_for_mfa_config'],
                mfa_code=cls.field_specs['mfa_code'],
            ),
        )

    invalid_params_set_to_custom_exc_factory = {
        frozenset({'token'}): HTTPForbidden,
    }

    def make_response(self):
        login = self.user_id
        token_id = self.params['token'][WEB_TOKEN_DATA_KEY_OF_TOKEN_ID]
        mfa_code = self.params['mfa_code']

        with self.auth_manage_api:
            auth_data = self.turn_provisional_mfa_config_into_actual(
                token_id,
                mfa_code,
                allow_overwrite_existing=True)
            if auth_data['user_id'] != login:
                LOGGER.warning('The received web token belongs to the user '
                               '%a, not to the currently logged user %a!',
                               auth_data['user_id'], login)
                raise HTTPForbidden
            self.auth_manage_api.delete_web_tokens_of_given_type_and_owner(
                WEB_TOKEN_TYPE_FOR_MFA_CONFIG,
                login)

        with self.auth_manage_api:
            self.send_mail_notice_to_user(login, self.NOTICE_KEY)

        return self.json_response({})


class N6PasswordForgottenView(_AbstractPortalAuthRelatedView):

    NOTICE_KEY = 'password_reset_requested'
    PASSWORD_RESET_URL_SUFFIX_PATTERN = '/password-reset?token={token}'

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params=cls.make_data_spec(
                login=cls.field_specs['login'],
            ),
        )

    def make_response(self):
        login = self.params['login']

        with self.auth_manage_api:
            try:
                token_data = self.create_token(WEB_TOKEN_TYPE_FOR_PASSWORD_RESET, login)
            except HTTPForbidden:
                LOGGER.warning("Cannot do the password reset for the user %a "
                               "because the user is either blocked or does "
                               "not exist", login)
                return self.json_response({})

        token_field = self.field_specs['token_for_password_reset']
        token = token_field.clean_result_value(token_data)
        url = self._get_password_reset_url(token)
        with self.auth_manage_api:
            sent_to_anyone = self.send_mail_notice_to_user(login=login,
                                                           notice_key=self.NOTICE_KEY,
                                                           token=token,
                                                           url=url)
        if not sent_to_anyone:
            LOGGER.error("The user %a is trying to reset the password, "
                         "but sending an email from n6 has failed - either "
                         "because of an error (see the logs for more info) "
                         "or because *mail notices* for notice_key=%a are "
                         "disabled. If this is the latter case, to make the "
                         "stuff work, it is necessary to adjust the Portal "
                         "API configuration in its `mail_notices_api.*` "
                         "options.", login, self.NOTICE_KEY)

        return self.json_response({})

    def _get_password_reset_url(self, token):
        base_url = self.get_portal_frontend_base_url()
        suffix = self.PASSWORD_RESET_URL_SUFFIX_PATTERN.format(token=token)
        return base_url + suffix


class N6PasswordResetView(_AbstractPortalAuthRelatedView):

    NOTICE_KEY = 'password_reset_done'

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params = cls.make_data_spec(
                token=cls.field_specs['token_for_password_reset'],
                password=cls.field_specs['password_to_be_set'],
            ),
        )

    invalid_params_set_to_custom_exc_factory = {
        frozenset({'token'}): HTTPForbidden,
    }

    def make_response(self):
        token_id = self.params['token'][WEB_TOKEN_DATA_KEY_OF_TOKEN_ID]
        password = self.params['password']

        with self.auth_manage_api as api:
            login = self.get_login_of_legit_token_owner(
                token_id,
                WEB_TOKEN_TYPE_FOR_PASSWORD_RESET)
            api.set_user_password(login, password)
            api.delete_web_tokens_of_given_type_and_owner(
                WEB_TOKEN_TYPE_FOR_PASSWORD_RESET,
                login)

        with self.auth_manage_api:
            self.send_mail_notice_to_user(login, self.NOTICE_KEY)

        return self.json_response({})


class N6LogoutView(_AbstractPortalAuthRelatedView):

    def make_response(self):
        logged_out_response_headerlist = forget(self.request)
        return self.json_response({}, headerlist=logged_out_response_headerlist)


class N6RegistrationView(EssentialAPIsViewMixin,
                         OmittingEmptyParamsViewMixin,
                         CommaSeparatedParamValuesViewMixin,
                         AbstractViewBase):

    NOTICE_KEY = 'registration_requested'

    comma_separated_only_for = frozenset({
        'notification_emails',
        'asns',
        'fqdns',
        'ip_networks',
        'agreements',
    })

    @classmethod
    def get_default_http_methods(cls):
        return 'POST'

    def make_response(self):
        org_id_repr = self._repr_raw_org_id()
        req_id = rt_ticket_id = None
        err_logged = False
        try:
            try:
                with self.auth_manage_api as api:
                    req_id, req_pure_data = api.create_registration_request(**self.params)
                    assert (isinstance(req_id, str)
                            and isinstance(req_pure_data, dict))

                    rt_ticket_id = self.rt_client_api.new_ticket(ticket_kind=self.NOTICE_KEY,
                                                                 data_dict=dict(req_pure_data,
                                                                                id=req_id))
                    if rt_ticket_id is not None:
                        api.set_registration_request_ticket_id(req_id=req_id,
                                                               ticket_id=str(rt_ticket_id))
            except:
                if rt_ticket_id is not None:
                    assert req_id is not None
                    LOGGER.error(
                        'REGISTRATION FAILED! The RT ticket #%s related to '
                        'a new organization registration request (org_id=%s) '
                        '*has been created* (!) *but* then the registration '
                        'request itself (#%s) could *not* be stored! '
                        '(because of %s)',
                        rt_ticket_id,
                        org_id_repr,
                        req_id,
                        make_exc_ascii_str())
                    err_logged = True
                raise
        except AuthDatabaseAPIClientError:
            raise
        except:
            # For the *register new organization* form, in the case of
            # any error other than HTTP-400-like, we want to emit a log
            # message explicitly informing that the submitted client
            # registration request could not be handled properly.
            if not err_logged:
                LOGGER.error(
                    'REGISTRATION FAILED! A new organization registration '
                    'request (org_id=%s) could not be created/stored! '
                    '(because of %s)',
                    org_id_repr,
                    make_exc_ascii_str())
            raise
        else:
            return self.json_response({})

    def _repr_raw_org_id(self):
        try:
            [raw_org_id] = self.params['org_id']
        except (KeyError, ValueError):
            return '<unknown>'
        else:
            return ascii_str(f'"{raw_org_id}"')


class N6AgreementsView(EssentialAPIsViewMixin, PreparingNoParamsViewMixin, AbstractViewBase):

    @classmethod
    def get_default_http_methods(cls):
        return 'GET'

    def make_response(self):
        with self.auth_manage_api:
            return self.json_response(self.auth_manage_api.get_all_agreements_basic_data())

        
class N6OrgAgreementsView(EssentialAPIsViewMixin,
                          CommaSeparatedParamValuesViewMixin,
                          AbstractViewBase):
    
    params_only_from_body = True
    multi_value_param_keys = ('agreements',)

    @classmethod
    def get_default_http_methods(cls):
        return 'GET', 'POST'
    
    def make_response(self):
        with self.auth_manage_api:
            if self.request.method == 'POST':
                self.auth_manage_api.update_org_agreements(
                    org_id=self.org_id,
                    agreements=self.params['agreements']
                )
            return self.json_response(
                self.auth_manage_api.get_org_agreement_labels(org_id=self.org_id))


class N6OrgConfigView(EssentialAPIsViewMixin,
                      CommaSeparatedParamValuesViewMixin,
                      AbstractViewBase):

    NOTICE_KEY = 'org_config_update_requested'

    comma_separated_only_for = multi_value_param_keys = frozenset({
        'added_user_logins',
        'removed_user_logins',
        'notification_emails',
        'notification_times',
        'asns',
        'fqdns',
        'ip_networks',
    })

    @classmethod
    def get_default_http_methods(cls):
        return 'GET', 'POST'

    def preprocess_param_values(self, key, values):
        assert isinstance(values, list)
        if (key in self.multi_value_param_keys) and values == ['']:
            return []
        return super().preprocess_param_values(key, values)

    def make_response(self):
        if self.request.method == 'POST':
            return self._make_post_response()
        return self._make_get_response()

    def _make_get_response(self):
        with self.auth_manage_api:
            org_config_info = self.auth_manage_api.get_org_config_info(org_id=self.org_id)
        assert isinstance(org_config_info, dict)
        assert ('update_info' in org_config_info
                and (org_config_info['update_info'] is None
                     or isinstance(org_config_info['update_info'], dict)))
        org_config_info['post_accepted'] = None
        return self.json_response(org_config_info)

    def _make_post_response(self):
        self._verify_no_forbidden_params()
        req_id = rt_ticket_id = None
        try:
            with self.auth_manage_api as api:
                org_config_info = api.get_org_config_info(org_id=self.org_id)
                assert isinstance(org_config_info, dict)
                assert 'update_info' in org_config_info

                if org_config_info['update_info'] is not None:
                    org_config_info['post_accepted'] = False
                    notice_data = to_addresses = None

                else:
                    req_id, req_pure_data = api.create_org_config_update_request(
                         **dict(self.params,
                                org_id=self.org_id,
                                requesting_user_login=self.user_id))
                    assert (isinstance(req_id, str)
                            and isinstance(req_pure_data, dict))

                    to_addresses = api.get_org_user_logins(org_id=self.org_id,
                                                           only_nonblocked=True)
                    assert (isinstance(to_addresses, list)
                            and all(isinstance(email, str)
                                    for email in to_addresses))

                    # (for HTTP response...)
                    org_config_info['update_info'] = req_pure_data
                    org_config_info['post_accepted'] = True

                    # (for RT ticket and e-mail notices...)
                    notice_data = copy.deepcopy(org_config_info)
                    notice_data['update_info']['update_request_id'] = req_id

                    # It is intentional that all necessary database
                    # operations unrelated to RT are performed *before*
                    # RT ticket creation. The intent is to minimize the
                    # likelihood (even if not completely eliminate the
                    # possibility) of such a case that an RT ticket is
                    # created but *then* some error occurs, causing the
                    # whole database transaction to be rolled back,
                    # whereas the created RT ticket remains...
                    rt_ticket_id = self.rt_client_api.new_ticket(ticket_kind=self.NOTICE_KEY,
                                                                 data_dict=notice_data)
                    if rt_ticket_id is not None:
                        api.set_org_config_update_request_ticket_id(req_id=req_id,
                                                                    ticket_id=str(rt_ticket_id))

        except:
            if rt_ticket_id is not None:
                assert req_id is not None
                LOGGER.error(
                    'The RT ticket #%s related to an organization config '
                    'update request (org_id="%s") *has been created* (!) '
                    '*but* then the organization config update request '
                    'itself (#%s) could *not* be stored! (because of %s)',
                    rt_ticket_id,
                    self.org_id,
                    req_id,
                    make_exc_ascii_str())
            raise

        else:
            if notice_data is not None:
                assert to_addresses is not None
                assert req_id is not None
                if to_addresses:
                    self._try_to_send_email_notices(to_addresses, notice_data)
                else:
                    LOGGER.error(
                        'No e-mail notices about an organization config '
                        'update request (#%s, org_id="%s") could be sent '
                        'because no matching non-blocked users exist!',
                        req_id, self.org_id)

            assert isinstance(org_config_info['update_info'], dict)
            assert isinstance(org_config_info['post_accepted'], bool)
            return self.json_response(org_config_info)

    def _verify_no_forbidden_params(self,
                                    _forbidden=frozenset({'org_id', 'requesting_user_login'})):
        found = _forbidden.intersection(self.params)
        if found:
            listing = ', '.join(map('"{}"'.format, sorted(found)))
            raise HTTPBadRequest(
                f'Illegal, explicitly forbidden, '
                f'query parameters: {listing}.')

    def _try_to_send_email_notices(self, to_addresses, notice_data):
        lang = notice_data['notification_language']  # TODO?: separate per-user setting?...
        assert (isinstance(lang, str) and len(lang) == 2
                or lang is None)
        with self.mail_notices_api.dispatcher(self.NOTICE_KEY,
                                              suppress_and_log_smtp_exc=True) as dispatch:
            for email in to_addresses:
                dispatch(email, notice_data, lang)


class N6APIKeyView(EssentialAPIsViewMixin,
                   PreparingNoParamsViewMixin,
                   AbstractViewBase):

    @classmethod
    def get_default_http_methods(cls):
        return 'GET', 'POST', 'DELETE'

    def make_response(self):
        self._verify_api_key_support_enabled()
        if self.request.method == 'POST':
            return self._make_post_response()
        elif self.request.method == 'DELETE':
            return self._make_delete_response()
        return self._make_get_response()

    def _verify_api_key_support_enabled(self):
        if not self.auth_api.is_api_key_authentication_enabled():
            raise HTTPForbidden('API key support is not enabled')

    def _make_post_response(self):
        api_key_id = self._generate_api_key_id()
        with self.auth_manage_api:
            self.auth_manage_api.set_user_api_key_id(login=self.user_id, api_key_id=api_key_id)
        return self.json_response({'api_key': self._get_api_key(api_key_id)})

    def _make_delete_response(self):
        with self.auth_manage_api:
            self.auth_manage_api.delete_user_api_key_id(login=self.user_id)
            return self.json_response({})

    def _make_get_response(self):
        with self.auth_manage_api:
            api_key_id = self.auth_manage_api.get_user_api_key_id_or_none(login=self.user_id)
        if api_key_id is None:
            return self.json_response({'api_key': None})
        return self.json_response({'api_key': self._get_api_key(api_key_id)})

    @staticmethod
    def _generate_api_key_id():
        return str(uuid.uuid4())

    def _get_api_key(self, api_key_id):
        api_key = self.auth_api.get_api_key_as_jwt_or_none(self.user_id, api_key_id)
        assert api_key is not None  # (we ensured earlier that API key support is enabled)
        return api_key


class N6KnowledgeBaseContentsView(_AbstractKnowledgeBaseRelatedView):

    def make_response(self):
        if not self.is_knowledge_base_enabled():
            raise HTTPNotFound
        return self.json_response(self._get_table_of_contents())

    def _get_table_of_contents(self) -> dict:
        return self._knowledge_base_data["table_of_contents"]


class N6KnowledgeBaseArticlesView(_AbstractKnowledgeBaseRelatedView):

    def make_response(self):
        if not self.is_knowledge_base_enabled():
            raise HTTPNotFound
        article = self._get_article(self.request.matchdict.get('article_id'))
        if not article:
            raise HTTPNotFound
        return self.json_response(article)

    def _get_article(self, article_id: str) -> Optional[dict]:
        return self._knowledge_base_data["articles"].get(article_id)


class N6KnowledgeBaseSearchView(_AbstractKnowledgeBaseRelatedView):

    @classmethod
    def prepare_data_specs(cls):
        return dict(
            super().prepare_data_specs(),

            request_params=cls.make_data_spec(
                lang=KnowledgeBaseLangField(in_params='required', single_param=True),
                q=KnowledgeBaseSearchQueryField(in_params='required', single_param=True),
            ),
        )

    def make_response(self):
        if not self.is_knowledge_base_enabled():
            raise HTTPNotFound
        return self.json_response(self._get_search_result())

    def _get_search_result(self) -> dict:
        return search_in_knowledge_base(
            knowledge_base_data=self._knowledge_base_data,
            lang=self.params['lang'],
            search_phrase=self.params['q'],
        )


class N6DailyEventsCountsView(EssentialAPIsViewMixin,
                              _DashboardConfigViewMixin,
                              PreparingNoParamsViewMixin,
                              AbstractViewBase):

    def make_response(self):
        GROUPING_CATEGORY = 'remaining categories'
        time_range_in_days = self.get_time_range_in_days()
        at = datetime.datetime.utcnow().replace(microsecond=0)
        since = at - datetime.timedelta(days=(time_range_in_days-1))
        dates_range = sorted([(at - datetime.timedelta(days=day)).strftime('%Y-%m-%d')
                              for day in range(time_range_in_days)])
        access_filtering_conditions = self.get_access_zone_filtering_conditions('inside')
        most_frequent: tuple[str] = self.data_backend_api.get_the_most_frequent_categories(
            self.auth_data,
            access_filtering_conditions,
            since)
        all_events: dict[str, list] = self.data_backend_api.get_counts_per_day_per_category(
            self.auth_data,
            access_filtering_conditions,
            since)
        if not all_events:
            data = {
                'days_range': time_range_in_days,
                'empty_dataset': True,
            }
        else:
            events: dict[str, list] = self._group_events_and_count_remaining(all_events,
                                                                             most_frequent,
                                                                             GROUPING_CATEGORY)
            data_sets = self._get_events_sets(events, dates_range)
            categories = list(most_frequent)
            categories.append(GROUPING_CATEGORY)
            categories = tuple(categories)
            dataset = {category: [0] * time_range_in_days for category in categories}
            dataset = self._get_dataset(categories, GROUPING_CATEGORY, data_sets, dataset)
            data = {
                'days': dates_range,
                'datasets': dataset,
            }
        return self.json_response(data)

    @staticmethod
    def _group_events_and_count_remaining(events: dict[str, list],
                                          most_frequent: tuple,
                                          grouping_category: str) -> dict[str, list]:
        for date, group in events.items():
            count = 0
            counted = []
            for event in group:
                if event[0] in most_frequent:
                    counted.append(event)
                else:
                    count += event[1]
            if count != 0:
                counted.append([grouping_category, count])
            events[date] = counted
        return events

    @staticmethod
    def _get_events_sets(events: dict[str, list], days_range: list) -> list[tuple]:
        # Create a list of tuples, each consisting of:
        # 1. index in the final list
        # 2. event category
        # 3. number of events per category per specific day
        events_set = []
        for date, per_day_data in events.items():
            if date in days_range:
                position = days_range.index(date)
                if per_day_data:
                    for data in per_day_data:
                        category, count = data
                        events_set.append((position, category, count))
        return events_set

    @staticmethod
    def _get_dataset(categories: tuple,
                     grouping_category: str,
                     data_sets: list[tuple],
                     dataset: dict[str, list]) -> dict[str, list]:
        for event in data_sets:
            position, cat, count = event
            if cat in categories:
                dataset[cat][position] = count
        if grouping_category in dataset.keys() \
                and all(daily_count == 0 for daily_count in dataset[grouping_category]):
            dataset.pop(grouping_category, None)
        return dataset


class N6NamesRankingView(EssentialAPIsViewMixin,
                         _DashboardConfigViewMixin,
                         PreparingNoParamsViewMixin,
                         AbstractViewBase):
    @classmethod
    def get_default_http_methods(cls):
        return 'GET'

    def make_response(self):
        at = datetime.datetime.utcnow().replace(microsecond=0)
        time_range_in_days = self.get_time_range_in_days()
        since = at - datetime.timedelta(days=time_range_in_days-1)
        access_filtering_conditions = self.get_access_zone_filtering_conditions('inside')
        bots = self.data_backend_api.get_names_ranking_per_category(
            self.auth_data,
            access_filtering_conditions,
            since,
            category='bots')
        amplifier = self.data_backend_api.get_names_ranking_per_category(
            self.auth_data,
            access_filtering_conditions,
            since,
            category='amplifier')
        vulnerable = self.data_backend_api.get_names_ranking_per_category(
            self.auth_data,
            access_filtering_conditions,
            since,
            category='vulnerable')

        tables = {
            'bots': bots if bots else None,
            'amplifier': amplifier if amplifier else None,
            'vulnerable': vulnerable if vulnerable else None,
        }
        return self.json_response(tables)


#
# Application Pyramid-specific configuration/startup (with our extensions)

class N6ConfigHelper(ConfigHelper):

    # (see: ConfigHelper docs)

    ### XXX: is it used??? should it be used??? [ticket #3688]
    default_static_view_config = {
        'name': 'static',
        'path': 'static',
        'cache_max_age': 3600,
    }

    # note: all constructor arguments (including `auth_api_class`)
    # should be specified as keyword arguments
    def __init__(self,
                 auth_api_class,  # (<- deprecated, will be removed)
                 component_module_name,
                 auth_manage_api=None,
                 mail_notices_api=None,
                 oidc_provider_api=None,
                 rt_client_api=None,
                 **kwargs):
        self.component_module_name = component_module_name
        self.auth_api_class = auth_api_class
        self.auth_manage_api = auth_manage_api
        self.mail_notices_api = mail_notices_api
        self.oidc_provider_api = oidc_provider_api
        self.rt_client_api = rt_client_api
        super().__init__(**kwargs)

    def prepare_pyramid_configurator(self, pyramid_configurator):
        #pyramid_configurator.add_tween(
        #    'n6profihelpers.profiling_helpers.profiling_tween_factory',
        #    under=INGRESS)
        pyramid_configurator.add_tween(
            'n6lib.pyramid_commons.event_db_session_maintenance_tween_factory',
            under=EXCVIEW)
        pyramid_configurator.add_tween(
            'n6lib.pyramid_commons.auth_api_context_tween_factory',
            under=EXCVIEW)
        pyramid_configurator.add_tween(
            'n6lib.pyramid_commons.auth_db_apis_maintenance_tween_factory',
            under=EXCVIEW)
        pyramid_configurator.add_tween(
            'n6lib.pyramid_commons.preflight_requests_handler_tween_factory',
            under=EXCVIEW)
        pyramid_configurator.registry.component_module_name = self.component_module_name
        pyramid_configurator.registry.auth_api = self.auth_api_class(settings=self.settings)
        pyramid_configurator.registry.auth_manage_api = self.auth_manage_api
        pyramid_configurator.registry.mail_notices_api = self.mail_notices_api
        pyramid_configurator.registry.oidc_provider_api = self.oidc_provider_api
        pyramid_configurator.registry.rt_client_api = self.rt_client_api
        return super().prepare_pyramid_configurator(pyramid_configurator)

    @classmethod
    def exception_view(cls, exc, request):
        http_exc = super().exception_view(exc, request)
        log_debug_info_on_http_exc(http_exc)
        return http_exc


#
# Authentication policies

class BaseUserAuthenticationPolicy(BaseAuthenticationPolicy):

    """
    Base class for user+organization-based authentication policy classes.
    """

    _dev_fake_auth_flag_config_spec = '''
        dev_fake_auth = false :: bool
        ...
    '''

    def __new__(cls, settings):
        dev_fake_auth_flag_config = Config.section(
            cls._dev_fake_auth_flag_config_spec,
            settings=settings)
        if dev_fake_auth_flag_config['dev_fake_auth']:
            # this is a hack for developers only
            return DevFakeUserAuthenticationPolicy(settings)
        return super().__new__(cls)

    @staticmethod
    def merge_orgid_userid(org_id, user_id):
        return f'{org_id},{user_id}'

    @staticmethod
    def get_auth_data(request) -> Optional[AuthData]:
        """
        Queries the auth manage api for auth_data.

        Returns:
            A dict {'org_id': <organization id>,
                    'user_id': <user id (login)>}
            or None.
        """
        unauthenticated_userid = request.unauthenticated_userid
        if unauthenticated_userid is not None:
            org_id, user_id = unauthenticated_userid.split(',')
            with request.registry.auth_manage_api as api:
                if api.do_nonblocked_user_and_org_exist_and_match(user_id, org_id):
                    auth_data = dict(
                        org_id=org_id,
                        user_id=user_id,  # aka *login*
                    )
                    return auth_data
            LOGGER.warning('Failed to find non-blocked user whose organization id '
                           'is %a and login (user id) is %a', org_id, user_id)
        return None

    def authenticated_userid(self, request):
        if request.auth_data is not None:
            return self.merge_orgid_userid(request.auth_data['org_id'],
                                           request.auth_data['user_id'])
        return None

    def effective_principals(self, request):
        effective_principals = super().effective_principals(request)
        assert Everyone in effective_principals
        if request.auth_data is not None:
            assert Authenticated in effective_principals
            effective_principals.append(self.merge_orgid_userid(request.auth_data['org_id'],
                                                                request.auth_data['user_id']))
            #if <organization.rest_api_full_access>:
            #    effective_principals.append("group:admin")
        return effective_principals


class SSLUserAuthenticationPolicy(BaseUserAuthenticationPolicy):

    """Authentication based on mod_ssl env variables."""

    def unauthenticated_userid(self, request):
        org_id, user_id = get_certificate_credentials(request)
        if org_id is not None and user_id is not None:
            return self.merge_orgid_userid(org_id, user_id)
        return None


class AuthTktUserAuthenticationPolicy(BaseUserAuthenticationPolicy):

    """
    Authentication based on a signed cookie.

    Standard use in the n6 Portal: the cookie is created after user logs
    in (using their credentials) through `/login` and then (using the
    one-tome MFA code) either through `/login/mfa` or
    `/login/mfa_config/confirm`. After that, each request is
    authenticated with the cookie, using this authentication policy,
    until the user logs out or the cookie expires.
    """

    def __init__(self, settings):
        sess_cookie_secure = str_to_bool(settings.get('session_cookie_secure', 'true'))
        sess_timeout = settings.get('session_timeout', None)
        reissue_time = settings.get('session_reissue_time', None)
        sess_timeout = int(sess_timeout) if sess_timeout is not None else sess_timeout
        reissue_time = int(reissue_time) if reissue_time is not None else reissue_time
        self._auth_tkt_policy = AuthTktAuthenticationPolicy(secret=make_hex_id(),
                                                            hashalg='sha384',
                                                            secure=sess_cookie_secure,
                                                            timeout=sess_timeout,
                                                            reissue_time=reissue_time)

    def unauthenticated_userid(self, request):
        credentials = self._auth_tkt_policy.unauthenticated_userid(request)
        if credentials and self._validate_credentials(credentials):
            return credentials

    def authenticated_userid(self, request):
        return request.auth_data

    def effective_principals(self, request):
        return self._auth_tkt_policy.effective_principals(request)

    def remember(self, *args, **kwargs):
        return self._auth_tkt_policy.remember(*args, **kwargs)

    def forget(self, request):
        return self._auth_tkt_policy.forget(request)

    @staticmethod
    def _validate_credentials(credentials):
        try:
            _org_id, _user_id = credentials.split(',')
        except (TypeError, AttributeError, ValueError):
            LOGGER.warning("User tried to authenticate with invalid credentials: %a",
                           credentials)
            return False
        return True

    # https://docs.pylonsproject.org/projects/pyramid/en/latest/tutorials/wiki2/authentication
    # .html#add-login-logout-and-forbidden-views


class _AuthorizationHeaderAuthenticationPolicyMixin:

    HTTP_AUTH_HEADER = "Authorization"
    HTTP_AUTH_TYPE = "Bearer"
    HTTP_AUTH_REALM = NotImplemented

    def get_authorization_header_value(self, request):
        if (self.HTTP_AUTH_HEADER in request.headers
                and request.authorization
                and request.authorization.authtype == self.HTTP_AUTH_TYPE):
            try:
                return request.authorization.params
            except AttributeError:
                raise self._http_unauthorized()
        return None

    @classmethod
    def _http_unauthorized(cls):
        www_authenticate = f'{cls.HTTP_AUTH_TYPE} realm="{cls.HTTP_AUTH_REALM}"'
        response_exc = HTTPUnauthorized()
        response_exc.headers['WWW-Authenticate'] = www_authenticate
        return response_exc


class APIKeyOrSSLUserAuthenticationPolicy(_AuthorizationHeaderAuthenticationPolicyMixin,
                                          SSLUserAuthenticationPolicy):

    """
    Authentication based on an API key.
    """

    HTTP_AUTH_REALM = "Access to the REST API of n6"

    def unauthenticated_userid(self, request):
        if request.registry.auth_api.is_api_key_authentication_enabled():
            api_key = self.get_authorization_header_value(request)
            if api_key is not None:
                return f'api_key:{api_key}'
        return super().unauthenticated_userid(request)

    @classmethod
    def get_auth_data(cls, request):
        unauthenticated_userid = request.unauthenticated_userid
        if unauthenticated_userid and unauthenticated_userid.startswith('api_key:'):
            api_key = unauthenticated_userid.split(':', 1)[1]
            try:
                return request.registry.auth_api.authenticate_with_api_key(api_key)
            except AuthAPIUnauthenticatedError:
                LOGGER.warning('Could not authenticate - the given API key has not been accepted.')
                raise cls._http_unauthorized()
        auth_data = super().get_auth_data(request)
        if auth_data is None and request.registry.auth_api.is_api_key_authentication_enabled():
            raise cls._http_unauthorized()
        return auth_data


class OIDCUserAuthenticationPolicy(_AuthorizationHeaderAuthenticationPolicyMixin,
                                   AuthTktUserAuthenticationPolicy):

    """
    Authentication based on the bearer tokens fetched from the OpenID
    Connect Identity Provider.

    If the "Authorization" HTTP header with access token is missing
    from the request, the `AuthTktUserAuthenticationPolicy` mechanism
    will be used.
    """

    ACCESS_TOKEN_REQUIRED_CLAIMS = {
        'email': str,
        'org_name': str,
    }
    HTTP_AUTH_REALM = "Access to N6Portal API"

    def unauthenticated_userid(self, request):
        if request.registry.oidc_provider_api.is_active:
            access_token = self.get_authorization_header_value(request)
            if access_token:
                return f'access_token:{access_token}'
        return super().unauthenticated_userid(request)

    def effective_principals(self, request):
        if (request.registry.oidc_provider_api.is_active
                and self.HTTP_AUTH_HEADER in request.headers):
            return BaseUserAuthenticationPolicy.effective_principals(self, request)
        return super().effective_principals(request)

    @classmethod
    def get_auth_data(cls, request):
        unauthenticated_userid = request.unauthenticated_userid
        if (request.registry.oidc_provider_api.is_active
                and unauthenticated_userid
                and unauthenticated_userid.startswith('access_token:')):
            access_token = unauthenticated_userid.split(':', 1)[1]
            if access_token:
                return cls._get_auth_data_from_token(access_token, request)
        return super().get_auth_data(request)

    @classmethod
    def _get_auth_data_from_token(cls, access_token, request):
        json_web_key = cls._get_json_web_key(access_token, request)
        try:
            claims = request.registry.auth_api.authenticate_with_oidc_access_token(
                    access_token,
                    json_web_key,
                    required_claims=cls.ACCESS_TOKEN_REQUIRED_CLAIMS,
                    audience=request.registry.oidc_provider_api.client_id,
            )
        except AuthAPIUnauthenticatedError:
            raise cls._http_unauthorized()
        else:
            # presence of required claims should have been
            # checked by `jwt_decode()` function called by
            # `authenticate_with_oidc_access_token()` method
            assert 'org_name' in claims
            assert 'email' in claims
            org_id = claims['org_name']
            user_id = claims['email']
            with request.registry.auth_manage_api as api:
                if api.do_nonblocked_user_and_org_exist_and_match(user_id, org_id):
                    auth_data = dict(
                            org_id=org_id,
                            user_id=user_id,
                    )
                    return auth_data
                elif request.route_url('/login/oidc') == request.url:
                    # save unauthenticated credentials from the token,
                    # so they can be used to create user account
                    # in the `N6LoginOIDCView`
                    cls._save_temp_credentials_to_registry(request, user_id, org_id)
                return None

    @classmethod
    def _get_json_web_key(cls, access_token, request):
        try:
            return request.registry.oidc_provider_api.get_signing_key_from_token(access_token)
        except TokenValidationError:
            raise cls._http_unauthorized()

    @staticmethod
    def _save_temp_credentials_to_registry(request, user_id, org_id):
        request.registry.oidc_provider_api.unauthenticated_credentials.user_id = user_id
        request.registry.oidc_provider_api.unauthenticated_credentials.org_id = org_id


class DevFakeUserAuthenticationPolicy(BaseUserAuthenticationPolicy):

    """
    A fake version for developers only...
    """

    _dev_fake_auth_config_spec = '''
        [dev_fake_auth]
        org_id = example.org
        user_id = example@example.org
    '''

    def __new__(cls, settings):
        self = super(BaseUserAuthenticationPolicy,  # [sic]
                     cls).__new__(cls)
        self._dev_fake_auth_config = Config.section(
            self._dev_fake_auth_config_spec,
            settings=settings)
        return self

    def unauthenticated_userid(self, request):
        return self.merge_orgid_userid(
            self._dev_fake_auth_config['org_id'],
            self._dev_fake_auth_config['user_id'])


#
# Asserting that our non-sdk n6 renderers are registered

assert registered_stream_renderers.get('csv') is StreamRenderer_csv
assert registered_stream_renderers.get('snort-dns') is SnortDNSRenderer
assert registered_stream_renderers.get('snort-http') is SnortHTTPRenderer
assert registered_stream_renderers.get('snort-ip') is SnortIPRenderer
assert registered_stream_renderers.get('snort-ip-bl') is SnortIPBlacklistRenderer
assert registered_stream_renderers.get('suricata-dns') is SuricataDNSRenderer
assert registered_stream_renderers.get('suricata-http') is SuricataHTTPRenderer
assert registered_stream_renderers.get('suricata-ip') is SuricataIPRenderer
assert registered_stream_renderers.get('suricata-ip-bl') is SuricatatIPBlacklistRenderer

# Copyright (c) 2021-2025 NASK. All rights reserved.

from collections.abc import (
    Callable,
    Iterable,
)
from typing import (
    Any,
    ClassVar,
    Optional,
    Union,
)

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPForbidden
from sqlalchemy.sql.expression import ColumnElement

from n6lib.auth_api import (
    ACCESS_ZONE_TO_RESOURCE_ID,
    AuthAPI,
    RESOURCE_ID_TO_ACCESS_ZONE,
)
from n6lib.auth_db.api import (
    AuthDatabaseAPILookupError,
    AuthManageAPI,
)
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import (
    ascii_str,
    memoized,
)
from n6lib.config import Config
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.log_helpers import get_logger
from n6lib.mail_notices_api import MailNoticesAPI
from n6lib.oidc_provider_api import OIDCProviderAPI
from n6lib.pyramid_commons.knowledge_base_helpers import build_knowledge_base_data
from n6lib.rt_client_api import RTClientAPI
from n6lib.typing_helpers import (
    AccessInfo,
    AccessZone,
    AuthData,
    EventDataResourceId,
    ExcFactory,
    KwargsDict,
)
from n6sdk.data_spec import BaseDataSpec
from n6sdk.data_spec.fields import Field
from n6sdk.data_spec.utils import cleaning_kwargs_as_params_with_data_spec
from n6sdk.exceptions import ParamValueCleaningError


LOGGER = get_logger(__name__)


#
# Private (module-local-only) helpers
#


_APIS_MIXIN_CLASS_NAME = 'EssentialAPIsViewMixin'

def _api_property(api_name):

    def getter(self):
        api = getattr(self.request.registry, api_name)
        if api is None:
            raise RuntimeError(
                f'the {self!a} view cannot make use of '
                f'`{ascii_str(api_name)}` because it was '
                f'not specified (or was specified as `None`) '
                f'when the web app object was being configured')
        return api

    getter.__name__ = api_name
    getter.__qualname__ = f'{_APIS_MIXIN_CLASS_NAME}.{api_name}'

    return property(getter)


#
# Actual mixins provided by this module
#


class EssentialAPIsViewMixin(object):

    data_backend_api: N6DataBackendAPI = _api_property('data_backend_api')

    auth_manage_api: AuthManageAPI = _api_property('auth_manage_api')
    mail_notices_api: MailNoticesAPI = _api_property('mail_notices_api')
    oidc_provider_api: OIDCProviderAPI = _api_property('oidc_provider_api')
    rt_client_api: RTClientAPI = _api_property('rt_client_api')

    # (to be removed when we will get gid of AuthAPI)
    auth_api: AuthAPI = _api_property('auth_api')

    @property
    def org_id(self) -> str:                   # raises `HTTPForbidden` if no user is authenticated
        return self.auth_data['org_id']

    @property
    def user_id(self) -> str:                  # raises `HTTPForbidden` if no user is authenticated
        # (*used id*, i.e., user's *login*)
        return self.auth_data['user_id']

    @property
    def auth_data(self) -> AuthData:           # raises `HTTPForbidden` if no user is authenticated
        auth_data = self.auth_data_or_none
        if not auth_data:
            raise HTTPForbidden(u'Access not allowed.')
        return auth_data

    @property
    def auth_data_or_none(self) -> Optional[AuthData]:
        return self.request.auth_data or None  # noqa

    def get_access_zone_filtering_conditions(self, access_zone: AccessZone) -> list[ColumnElement]:
        access_info: AccessInfo = self.auth_api.get_access_info(self.auth_data)
        if not self.is_access_zone_available(access_info, access_zone):
            LOGGER.warning('User %a (org_id=%a) is trying to access data in '
                           'access zone %a - but is not authorized to do so',
                           self.user_id, self.org_id, access_zone)
            raise HTTPForbidden(u'Access not allowed.')
        assert access_info is not None
        assert access_zone in access_info['access_zone_conditions']
        access_filtering_conditions = access_info['access_zone_conditions'][access_zone]
        assert access_filtering_conditions
        return access_filtering_conditions
    
    def get_access_zone_source_ids(self, access_zone: AccessZone) -> list[str]:
        access_info: AccessInfo = self.auth_api.get_access_info(self.auth_data)
        if not self.is_access_zone_available(access_info, access_zone):
            LOGGER.warning('User %a (org_id=%a) is trying to list sources '
                           'available to them for access zone %a - but is not '
                           'authorized to get any data from that access zone',
                           self.user_id, self.org_id, access_zone)
            raise HTTPForbidden('Access not allowed.')
        assert access_info is not None
        assert access_zone in access_info['access_zone_source_ids']
        return access_info['access_zone_source_ids'][access_zone]

    def is_event_data_resource_available(self,
                                         access_info: Optional[AccessInfo],
                                         resource_id: EventDataResourceId) -> bool:
        assert resource_id in RESOURCE_ID_TO_ACCESS_ZONE
        access_zone = RESOURCE_ID_TO_ACCESS_ZONE[resource_id]
        return self.is_access_zone_available(access_info, access_zone)

    def is_access_zone_available(self,
                                 access_info: Optional[AccessInfo],
                                 access_zone: AccessZone) -> bool:
        assert access_zone in ACCESS_ZONE_TO_RESOURCE_ID
        resource_id = ACCESS_ZONE_TO_RESOURCE_ID[access_zone]
        if (access_info is None
              or resource_id not in access_info['rest_api_resource_limits']
              or not access_info['access_zone_conditions'].get(access_zone)):
            return False

        user_id = self.user_id
        org_id = self.org_id
        assert org_id in self.auth_api.get_org_ids_to_access_infos()

        # *Note*: the results of the following invocations of methods of
        # `auth_api` might be cached by `auth_api`. *We do want that*, as
        # we want the results to be in sync with the rest of the (cached)
        # authorization information from `auth_api` -- in particular, to
        # avoid granting to a user any undue access to event data that
        # were designated to be accessible to the present organization
        # of the user during the period when the user was blocked, or
        # when some user with this user's present login (user id)
        # belonged to another organization (these cases, especially the
        # latter, would be quite hypothetical but not impossible).
        nonblocked_user_org_mapping = self.auth_api.get_user_ids_to_org_ids()
        if user_id in self.auth_api.get_all_user_ids_including_blocked():
            return (nonblocked_user_org_mapping.get(user_id) == org_id)
        assert user_id not in nonblocked_user_org_mapping

        # A special, yet important, case (especially if OIDC is used):
        # when the *Auth API* machinery was caching the authorization
        # information, the user did *not* exist (but the organization
        # *did*); since then, the user might have been created (e.g.,
        # using the OIDC-based machinery) -- so that, now, the user
        # *does* exist, *belongs to the organization* and is *not
        # blocked* (and, apparently, has managed to log in). *If* that
        # is the case, let us *not* make the user wait for the *Auth
        # API* machinery to refresh its cache, but let us allow the
        # user to access the organization's resources immediately.
        with self.auth_manage_api as api:
            return api.do_nonblocked_user_and_org_exist_and_match(user_id, org_id)


    def send_mail_notice_to_user(self, /,

                                 # A user login (aka *user_id*) or a non-empty collection of such.
                                 login: Union[str, Iterable[str]],

                                 # A possible key in a dict being the value of the config option
                                 # `mail_notices_api.notice_key_to_lang_to_mail_components`.
                                 notice_key: str,

                                 # Custom items (additional to those from
                                 # `AuthManageAPI.get_user_and_org_basic_info()`)
                                 # to be placed in the `data_dict` to be passed to
                                 # the e-mail message content renderer. It is even
                                 # possible to override any of the items obtained
                                 # from `AuthManageAPI.get_user_and_org_basic_info()`
                                 # (including `lang`, used also to designate the
                                 # language variant of the notice message) but such
                                 # overriding is *not* recommended.
                                 **custom_notice_data) -> bool:

        login_seq = [login] if isinstance(login, str) else list(login)
        if not login_seq:
            raise ValueError('at least one user login must be given')

        sent_to_anyone = False
        with self.mail_notices_api.dispatcher(notice_key,
                                              suppress_and_log_smtp_exc=True) as dispatch:
            for user_login in login_seq:
                if self.auth_manage_api.is_user_blocked(user_login):
                    LOGGER.error('Cannot send a %a mail notice to the '
                                 'user %a because that user is blocked!',
                                 notice_key, user_login)
                    continue
                try:
                    basic_info = self.auth_manage_api.get_user_and_org_basic_info(user_login)
                except AuthDatabaseAPILookupError:
                    LOGGER.error('Cannot send a %a mail notice to the '
                                 'user %a because that user does not exist!',
                                 notice_key, user_login)
                else:
                    notice_data = {}
                    notice_data.update(basic_info)
                    notice_data.update(custom_notice_data)
                    notice_data.update(user_login=user_login)
                    assert set(notice_data) >= {'user_login', 'org_id', 'org_actual_name', 'lang'}
                    lang = notice_data['lang']
                    assert lang is None or isinstance(lang, str) and len(lang) == 2
                    ok_recipients, _ = dispatch(user_login, notice_data, lang)
                    sent_to_anyone = sent_to_anyone or bool(ok_recipients)
        return sent_to_anyone

assert (EssentialAPIsViewMixin.__name__ == _APIS_MIXIN_CLASS_NAME
        and EssentialAPIsViewMixin.__qualname__ == _APIS_MIXIN_CLASS_NAME)


class ConfigFromPyramidSettingsViewMixin(object):

    @classmethod
    @attr_required('config_spec')
    def concrete_view_class(cls, **kwargs):
        assert cls.config_spec is not None
        pyramid_configurator: Configurator = kwargs['pyramid_configurator']
        # noinspection PyUnresolvedReferences
        view_class = super().concrete_view_class(**kwargs)
        view_class.config_full = view_class.prepare_config_full(pyramid_configurator)
        assert view_class.config_full is not None
        return view_class

    # The following class attribute *needs* to be set in subclasses.
    config_spec: ClassVar[Optional[str]] = None

    # The following class attribute is to be set automatically (see
    # above...) -- it *can be used* by concrete view classes.
    config_full: ClassVar[Optional[Config]] = None

    # The following hooks are to be invoked automatically on concrete
    # class creation; they can be extended (with `super()`) in subclasses.

    @classmethod
    def prepare_config_full(cls, pyramid_configurator: Configurator) -> Config:
        config_constructor_kwargs = cls.prepare_config_constructor_kwargs(pyramid_configurator)
        return Config(cls.config_spec, **config_constructor_kwargs)

    @classmethod
    def prepare_config_constructor_kwargs(cls, pyramid_configurator: Configurator) -> KwargsDict:
        config_constructor_kwargs = {
            'settings': pyramid_configurator.registry.settings,
        }
        custom_converters = cls.prepare_config_custom_converters()
        if custom_converters:
            config_constructor_kwargs['custom_converters'] = custom_converters
        return config_constructor_kwargs

    @classmethod
    def prepare_config_custom_converters(cls) -> dict[str, Callable[[str], Any]]:
        return {}


class KnowledgeBaseRelatedViewMixin(ConfigFromPyramidSettingsViewMixin):

    config_spec = '''
        [knowledge_base]
        active = false :: bool
        base_dir = ~/.n6_knowledge_base :: path
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
            base_dir = str(cls.config_full['knowledge_base']['base_dir'])
            cls._knowledge_base_data = cls._get_knowledge_base_data(base_dir)
        else:
            cls._knowledge_base_data = None

    @staticmethod
    @memoized(max_size=1)
    def _get_knowledge_base_data(base_dir: str) -> dict:
        return build_knowledge_base_data(base_dir)


class WithDataSpecsViewMixin(object):

    @classmethod
    def concrete_view_class(cls, **kwargs):
        # noinspection PyUnresolvedReferences
        view_class = super().concrete_view_class(**kwargs)
        view_class.field_specs = view_class.prepare_field_specs()
        view_class.data_specs = view_class.prepare_data_specs()
        return view_class

    # The following attribute will be set **automatically** to the
    # result of invocation of `prepare_field_specs()` (performed when a
    # concrete view class is created by the `N6ConfigHelper` stuff...).
    # The reason this attribute exists is so that there is one place --
    # a concrete implementation of the `prepare_field_specs() method
    # (whose abstract stuff is defined below) -- where all needed *data
    # spec fields* are defined, so that any *data specs* defined in
    # subclasses can just refer to them (avoiding repeating data spec
    # field definitions).
    field_specs: dict[str, Field] = None

    # The following attribute will be set **automatically** to the
    # result of invocation of `prepare_data_specs()` (performed when a
    # concrete view class is created by the `N6ConfigHelper` stuff...).
    # For more information, see the docs of the `prepare_data_specs()`
    # method (defined below).
    data_specs: dict[str, BaseDataSpec] = None

    #
    # Hooks that can be extended (with `super()`) in subclasses

    @classmethod
    def prepare_field_specs(cls) -> dict[str, Field]:
        """
        Return a dict whose items are data spec *fields* (instances
        of `Field` subclasses) -- to be used by *data spec(s)* of a
        particular concrete view.  Invocation of this method is
        automatic (performed when a concrete view class is created by
        the `N6ConfigHelper` stuff...); the resultant dict is set as the
        value of the `field_specs` attribute of the concrete view class.

        Note: the default implementation returns an empty dict -- so you
        may want to extend/override this method in your view subclasses.
        """
        return {}

    @classmethod
    def prepare_data_specs(cls) -> dict[str, BaseDataSpec]:
        """
        Return  a dict whose items are *data specs* (instances of
        `BaseDataSpec` or of its subclasses) -- to be used by a
        particular concrete view.  Invocation of this method is
        automatic (performed when a concrete view class is created by
        the `N6ConfigHelper` stuff...); the resultant dict instance is
        set as the value of the `data_specs` attribute of the concrete
        view class.

        Note: the default implementation returns an empty dict -- so you
        may want to extend/override this method in your view subclasses.
        Typically, in your implementations of this method, you will want
        to make use of the `make_data_spec()` utility method; also, most
        probably, you will refer to items of the `cls.field_specs` dict.
        """
        return {}

    #
    # Helper methods -- to be used in subclasses

    @classmethod
    def make_data_spec(cls, /, **name_to_field: Field) -> BaseDataSpec:
        """
        Make a new *data spec* (an instance of a `BaseDataSpec` subclass).

        The keyword arguments (*kwargs*) should define the fields of the
        to-be-created data spec: argument names should be field names,
        and argument values should be field objects (i.e., instances of
        `Field`'s subclasses).
        """
        # noinspection PyPep8Naming
        class data_spec_class(BaseDataSpec):
            """A data spec class generated with a view's `make_data_spec()`."""

        new_name = f'data_spec_made_by_{cls.__name__}'
        qualname_prefix = data_spec_class.__qualname__[:-len(data_spec_class.__name__)]
        data_spec_class.__name__ = new_name
        data_spec_class.__qualname__ = qualname_prefix + new_name

        for field_name, field in sorted(name_to_field.items()):
            setattr(data_spec_class, field_name, field)

        data_spec = data_spec_class()
        return data_spec


class WithDataSpecsAlsoForRequestParamsViewMixin(WithDataSpecsViewMixin):

    #
    # Extended `AbstractViewBase`'s hooks

    @classmethod
    def concrete_view_class(cls, **kwargs):
        # noinspection PyUnresolvedReferences
        view_class = super().concrete_view_class(**kwargs)
        # noinspection PyProtectedMember
        view_class._provide_clean_request_params_method()
        return view_class

    def prepare_params(self) -> dict[str, Any]:
        # noinspection PyUnresolvedReferences
        params = super().prepare_params()
        try:
            return self._clean_request_params(**params)
        except ParamValueCleaningError as cleaning_error:
            raise self.exc_on_param_value_cleaning_error(
                cleaning_error,
                invalid_params_set=frozenset(
                    name for name, _, _ in cleaning_error.error_info_seq))

    #
    # Extended `WithDataSpecsViewMixin`'s hooks

    # Note: the following method can be *extended* (with `super()`) in
    # subclasses -- but it should *not* be overridden completely.
    @classmethod
    def prepare_data_specs(cls) -> dict[str, BaseDataSpec]:
        return dict(
            super().prepare_data_specs(),

            # This is the data spec that will be used automatically to
            # clean request params -- you can override it in subclasses.
            request_params=cls.make_data_spec(),
        )

    #
    # Attributes/methods that can be overridden/extended in subclasses

    invalid_params_set_to_custom_exc_factory: dict[frozenset[str], ExcFactory] = {}

    def exc_on_param_value_cleaning_error(self,
                                          cleaning_error: ParamValueCleaningError,
                                          invalid_params_set: frozenset[str]) -> Exception:
        custom_exc_factory = self.invalid_params_set_to_custom_exc_factory.get(invalid_params_set)
        if custom_exc_factory is not None:
            return custom_exc_factory()
        return cleaning_error  # (<- it will cause HTTP 400)

    #
    # Private implementation details

    # (provided automatically, see below)
    _clean_request_params: Callable[..., dict[str, Any]] = None

    @classmethod
    def _provide_clean_request_params_method(cls):
        assert hasattr(cls, 'data_specs') and isinstance(cls.data_specs, dict)
        assert 'request_params' in cls.data_specs

        @cleaning_kwargs_as_params_with_data_spec(cls.data_specs['request_params'])
        def _clean_request_params(*_, **cleaned_params) -> dict[str, Any]:
            return cleaned_params

        _clean_request_params.__module__ = cls.__module__
        _clean_request_params.__qualname__ = f'{cls.__qualname__}.{_clean_request_params.__name__}'

        cls._clean_request_params = _clean_request_params

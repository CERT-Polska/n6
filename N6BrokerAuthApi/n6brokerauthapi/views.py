# Copyright (c) 2019-2025 NASK. All rights reserved.

import logging
from collections.abc import (
    Container,
    Iterable,
    Mapping,
)
from typing import Optional

from pyramid.response import Response

from n6brokerauthapi.auth_base import (
    BaseBrokerAuthManager,
    BaseBrokerAuthManagerMaker,
)
from n6lib.auth_db.api import AuthManageAPI
from n6lib.class_helpers import (
    CombinedWithSuper,
    attr_required,
)
from n6lib.common_helpers import ascii_str
from n6lib.log_helpers import get_logger
from n6sdk.exceptions import ParamCleaningError
from n6sdk.pyramid_commons import (
    AbstractViewBase,
    SingleParamValuesViewMixin,
)


LOGGER = get_logger(__name__)


class _DenyAccess(Exception):

    error_log_message: Optional[str]

    def __init__(self, error_log_message: Optional[str] = None):
        super().__init__(error_log_message)
        self.error_log_message = error_log_message


class _N6BrokerAuthViewBase(SingleParamValuesViewMixin, AbstractViewBase):

    params: Mapping[str, str]

    #
    # Overridden/extended superclass-defined methods

    @classmethod
    def get_default_http_methods(cls) -> str:
        return 'POST'

    def __call__(self) -> Response:
        try:
            try:
                # (involves invocation of `prepare_params()` and `make_response()`)
                return super().__call__()
            except ParamCleaningError as exc:
                raise _DenyAccess(error_log_message=exc.public_message)
        except _DenyAccess as deny_exc:
            if deny_exc.error_log_message:
                self._log(logging.ERROR, deny_exc.error_log_message)
            return self.deny_response()

    def prepare_params(self) -> Mapping[str, str]:
        params = super().prepare_params()  # (involves invocation of `iter_deduplicated_params()`)
        if 'username' in params:
            params['username'] = AuthManageAPI.adjust_if_is_legacy_user_login(params['username'])
        return params

    def make_response(self) -> Response:
        self.validate_params()
        response = self.make_auth_response()
        assert isinstance(response, Response)
        return response

    #
    # Stuff that can or must be overridden/extended in subclasses

    # Attribute that in a subclass must be a dict that maps param
    # names (str) to `whether this param is required` flags (bool):
    param_name_to_required_flag: Mapping[str, bool] = None

    # Method that *can* be extended in subclasses (if needed):
    @attr_required('param_name_to_required_flag')
    def validate_params(self) -> None:
        self._ensure_all_param_names_and_values_are_strings()
        self._warn_if_unknown_params()
        self._deny_if_missing_params()

    # Abstract method (*must* be implemented in concrete subclasses):
    def make_auth_response(self) -> Response:
        raise NotImplementedError

    #
    # Stuff accessible (also) in subclasses

    @property
    def auth_manager_maker(self) -> BaseBrokerAuthManagerMaker:
        return self.request.registry.auth_manager_maker

    @classmethod
    @attr_required('param_name_to_required_flag')
    def get_required_param_names(cls) -> set[str]:
        return {name
                for name, required in cls.param_name_to_required_flag.items()
                if required}

    def allow_response(self) -> Response:
        return self.text_response('allow')

    def deny_response(self) -> Response:
        return self.text_response('deny')

    #
    # Private stuff

    def _log(self, level: int, log_message: str) -> None:
        LOGGER.log(level, '[%a: %s] %s',
                   self,
                   ascii_str(self.request.url),
                   ascii_str(log_message))

    def _ensure_all_param_names_and_values_are_strings(self) -> None:
        if not all(isinstance(key, str) and
                   isinstance(val, str)
                   for key, val in self.params.items()):
            raise AssertionError(
                f'this should never happen: not all request param names '
                f'and values are strings! (params: {self.params!a})')

    def _warn_if_unknown_params(self) -> None:
        known_param_names = set(self.param_name_to_required_flag)
        unknown_param_names = set(self.params) - known_param_names
        if unknown_param_names:
            listing = self._format_ascii_listing(unknown_param_names)
            self._log(logging.WARNING, f'Ignoring unknown request params: {listing}.')

    def _deny_if_missing_params(self) -> None:
        missing_param_names = self.get_required_param_names() - set(self.params)
        if missing_param_names:
            listing = self._format_ascii_listing(missing_param_names)
            raise _DenyAccess(f'Missing request params: {listing}.')

    def _format_ascii_listing(self, names: Iterable[str]) -> str:
        return ', '.join(map(ascii, sorted(names)))


class _N6BrokerAuthResourceViewBase(_N6BrokerAuthViewBase):

    param_name_to_required_flag: Mapping[str, bool] = {
        'username': True,
        'vhost': True,
        'resource': True,
        'name': True,
        'permission': True,
    }

    valid_permissions: Container[str] = None
    valid_resources: Container[str] = None

    @attr_required('valid_permissions', 'valid_resources')
    def validate_params(self) -> None:
        super().validate_params()
        assert self.params.keys() >= {'resource', 'permission'}
        resource = self.params['resource']
        permission = self.params['permission']
        if resource not in self.valid_resources:
            raise _DenyAccess(f'Invalid resource type: {resource!a}.')
        if permission not in self.valid_permissions:
            raise _DenyAccess(f'Invalid permission level: {permission!a}.')


# the *user_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthUserView(_N6BrokerAuthViewBase):

    param_name_to_required_flag: Mapping[str, bool] = {
        'username': True,
        'password': True,
    }

    def make_auth_response(self) -> Response:
        with self.auth_manager_maker(
                self.params,
                need_authentication=True) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.user_verified:
                return self.allow_response()
        return self.deny_response()


# the *vhost_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthVHostView(_N6BrokerAuthViewBase):

    param_name_to_required_flag: Mapping[str, bool] = {
        'username': True,
        'vhost': True,
        'ip': True,
    }

    def make_auth_response(self) -> Response:
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.apply_vhost_rules():
                return self.allow_response()
        return self.deny_response()


# the *resource_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthResourceView(_N6BrokerAuthResourceViewBase):

    valid_resources: Container[str] = ('exchange', 'queue')
    valid_permissions: Container[str] = ('configure', 'write', 'read')

    def make_auth_response(self) -> Response:
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if self.params['resource'] == 'exchange' and auth_manager.apply_exchange_rules():
                return self.allow_response()
            if self.params['resource'] == 'queue' and auth_manager.apply_queue_rules():
                return self.allow_response()
        return self.deny_response()


# the *topic_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthTopicView(_N6BrokerAuthResourceViewBase):

    param_name_to_required_flag: Mapping[str, bool] = CombinedWithSuper({'routing_key': True})

    valid_resources: Container[str] = ('topic',)
    valid_permissions: Container[str] = ('write', 'read')

    def make_auth_response(self) -> Response:
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.apply_topic_rules():
                return self.allow_response()
        return self.deny_response()

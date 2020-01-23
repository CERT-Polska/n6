# Copyright (c) 2013-2019 NASK. All rights reserved.

import logging

from pyramid.response import Response

from n6brokerauthapi.auth_base import BaseBrokerAuthManager
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import ascii_str
from n6lib.log_helpers import get_logger
from n6sdk.exceptions import ParamCleaningError
from n6sdk.pyramid_commons import (
    AbstractViewBase,
    SingleParamValuesViewMixin,
)


LOGGER = get_logger(__name__)


class _DenyAccess(Exception):

    def __init__(self, error_log_message=None):
        super(_DenyAccess, self).__init__(error_log_message)
        self.error_log_message = None


class _N6BrokerAuthViewBase(SingleParamValuesViewMixin, AbstractViewBase):

    #
    # Overridden/extended superclass-defined methods

    @classmethod
    def get_default_http_methods(cls):
        return 'POST'

    def __call__(self):
        try:
            # involves use of `iter_deduplicated_params()` and `make_response()`...
            try:
                return super(_N6BrokerAuthViewBase, self).__call__()
            except ParamCleaningError as exc:
                raise _DenyAccess(error_log_message = exc.public_message)
        except _DenyAccess as deny_exc:
            if deny_exc.error_log_message:
                self._log(logging.ERROR, deny_exc.error_log_message)
            return self.deny_response()

    def make_response(self):
        self.validate_params()
        response = self.make_auth_response()
        assert isinstance(response, Response)
        return response

    #
    # Stuff that can or must be overridden/extended in subclasses

    # Attribute that in a subclass must be a dict that maps param
    # names (str) to `whether this param is required` flags (bool):
    param_name_to_required_flag = None

    # Method that *can* be extended in subclasses (if needed):
    @attr_required('param_name_to_required_flag')
    def validate_params(self):
        self._ensure_all_param_names_and_values_are_strings()
        self._warn_if_unknown_params()
        self._deny_if_missing_params()

    # Abstract method (*must* be implemented in concrete subclasses):
    def make_auth_response(self):  # type: () -> Response
        raise NotImplementedError

    #
    # Stuff accessible (also) in subclasses

    @property
    def auth_manager_maker(self):
        return self.request.registry.auth_manager_maker

    @classmethod
    @attr_required('param_name_to_required_flag')
    def get_required_param_names(cls):
        return {name
                for name, required in cls.param_name_to_required_flag.iteritems()
                if required}

    def allow_response(self):
        return self.plain_text_response('allow')

    def allow_administrator_response(self):
        return self.plain_text_response('allow administrator')

    def deny_response(self):
        return self.plain_text_response('deny')

    def safe_name(self, name):
        return "'{}'".format(ascii_str(name))

    #
    # Private stuff

    def _log(self, level, log_message):
        LOGGER.log(level, '[%r: %s] %s',
                   self,
                   ascii_str(self.request.url),
                   ascii_str(log_message))

    def _ensure_all_param_names_and_values_are_strings(self):
        if not all(isinstance(key, basestring) and
                   isinstance(val, basestring)
                   for key, val in self.params.iteritems()):
            raise AssertionError(
                'this should never happen: not all request param names and '
                'values are strings! (params: {!r})'.format(self.params))

    def _warn_if_unknown_params(self):
        known_param_names = set(self.param_name_to_required_flag)
        unknown_param_names = set(self.params) - known_param_names
        if unknown_param_names:
            self._log(logging.WARNING, 'Ignoring unknown request params: {}.'.format(
                self._format_safe_names(unknown_param_names)))

    def _deny_if_missing_params(self):
        missing_param_names = self.get_required_param_names() - set(self.params)
        if missing_param_names:
            raise _DenyAccess(
                'Must sent "deny" response because of missing '
                'request params: {}.'.format(
                    self._format_safe_names(missing_param_names)))

    def _format_safe_names(self, names):
        return ', '.join(sorted(map(self.safe_name, names)))


class _N6BrokerAuthResourceViewBase(_N6BrokerAuthViewBase):

    param_name_to_required_flag = {
        'username': True,
        'vhost': True,
        'resource': True,
        'name': True,
        'permission': True,
    }

    valid_permissions = None
    valid_resources = None

    @attr_required('valid_permissions', 'valid_resources')
    def validate_params(self):
        super(_N6BrokerAuthResourceViewBase, self).validate_params()
        assert self.params.viewkeys() >= {'resource', 'permission'}
        resource = self.params['resource']
        permission = self.params['permission']
        if resource not in self.valid_resources:
            raise _DenyAccess('Invalid resource type: {}.'.format(self.safe_name(resource)))
        if permission not in self.valid_permissions:
            raise _DenyAccess('Invalid permission level: {}.'.format(self.safe_name(permission)))


# the *user_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthUserView(_N6BrokerAuthViewBase):

    param_name_to_required_flag = {
        'username': True,
        'password': False,
    }

    def make_auth_response(self):
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.client_verified:
                if auth_manager.client_type == 'user' and auth_manager.client_is_admin_user:
                    return self.allow_administrator_response()
                return self.allow_response()
        return self.deny_response()


# the *vhost_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthVHostView(_N6BrokerAuthViewBase):

    param_name_to_required_flag = {
        'username': True,
        'vhost': True,
        'ip': True,
    }

    def make_auth_response(self):
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.apply_privileged_access_rules():
                return self.allow_response()
            if auth_manager.apply_vhost_rules():
                return self.allow_response()
        return self.deny_response()


# the *resource_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthResourceView(_N6BrokerAuthResourceViewBase):

    valid_resources = ('exchange', 'queue')
    valid_permissions = ('configure', 'write', 'read')

    def make_auth_response(self):
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.apply_privileged_access_rules():
                return self.allow_response()
            if self.params['resource'] == 'exchange' and auth_manager.apply_exchange_rules():
                return self.allow_response()
            if self.params['resource'] == 'queue' and auth_manager.apply_queue_rules():
                return self.allow_response()
        return self.deny_response()


# the *topic_path* view (in rabbitmq-auth-backend-http's parlance)
class N6BrokerAuthTopicView(_N6BrokerAuthResourceViewBase):

    param_name_to_required_flag = dict(
        _N6BrokerAuthResourceViewBase.param_name_to_required_flag,
        **{'routing_key': True})

    valid_resources = ('topic',)
    valid_permissions = ('write', 'read')

    def make_auth_response(self):
        with self.auth_manager_maker(self.params) as auth_manager:
            assert isinstance(auth_manager, BaseBrokerAuthManager)
            if auth_manager.apply_privileged_access_rules():
                return self.allow_response()
            if auth_manager.apply_topic_rules():
                return self.allow_response()
        return self.deny_response()

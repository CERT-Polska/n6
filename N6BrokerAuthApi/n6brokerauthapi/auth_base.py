# Copyright (c) 2013-2019 NASK. All rights reserved.

import sys
import threading

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from typing import Union

from n6lib.auth_db import models
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.const import ADMINS_SYSTEM_GROUP_NAME
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class BaseBrokerAuthManagerMaker(object):

    def __init__(self, settings):
        self._db_connector = SQLAuthDBConnector(settings=settings)
        self._manager_creation_lock = threading.Lock()  # (just in case...)

    def __call__(self, params):
        force_exit_on_any_remaining_entered_contexts(self._db_connector)
        with self._manager_creation_lock:
            manager_factory = self.get_manager_factory(params)
            manager_factory_kwargs = self.get_manager_factory_kwargs(params)
            manager = manager_factory(**manager_factory_kwargs)
        assert isinstance(manager, BaseBrokerAuthManager)
        return manager

    #
    # Abstract method (*must* be implemented in concrete subclasses)

    def get_manager_factory(self, params):
        raise NotImplementedError

    #
    # Method that may need to be overridden/extended in subclasses
    # (depending on what `get_manager_factory()` returns)

    def get_manager_factory_kwargs(self, validated_view_params):
        return dict(db_connector=self._db_connector,
                    params=validated_view_params)


class BaseBrokerAuthManager(object):

    def __init__(self,
                 db_connector,
                 params):
        if 'username' not in params:
            raise ValueError("param 'username' not given")  # view code should have ensured that
        self.db_connector = db_connector
        self.params = params    # type: dict    # request params (already deduplicated + validated)
        self.db_session = None  # type: Session
        self.client_obj = None  # type: Union[models.User, models.Component, None]

    def __enter__(self):
        self.db_session = self.db_connector.__enter__()
        try:
            self.client_obj = self._verify_and_get_client_obj()
            return self
        except:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.db_connector.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.db_session = None

    def _verify_and_get_client_obj(self):
        client_obj = None
        if self.should_try_to_verify_client():
            client_obj = self.verify_and_get_user_obj()
            if client_obj is None:
                client_obj = self.verify_and_get_component_obj()
        return client_obj

    @property
    def broker_username(self):
        # may be relevant to any view
        return self.params['username']

    @property
    def password(self):
        # may be relevant to the *user_path* view
        return self.params.get('password')

    @property
    def res_name(self):
        # relevant to the *resource_path* and *topic_path* views
        return self.params.get('name')

    @property
    def permission_level(self):
        # relevant to the *resource_path* and *topic_path* views
        return self.params.get('permission')

    @property
    def client_verified(self):
        # may be relevant to any view
        return (self.client_obj is not None)

    @property
    def client_type(self):
        if not self.client_verified:
            return None
        assert self.client_obj is not None
        if isinstance(self.client_obj, models.User):
            return 'user'
        elif isinstance(self.client_obj, models.Component):
            return 'component'
        raise TypeError('the client object {!r} is an instance of '
                        'a wrong class'.format(self.client_obj))

    @property
    def client_is_admin_user(self):
        if self.client_type != 'user':
            return False
        assert self.client_verified and self.client_obj is not None
        admins_group = self._get_admins_group()
        if admins_group is not None:
            return admins_group in self.client_obj.system_groups
        return False

    def _get_admins_group(self):
        try:
            return self.db_session.query(models.SystemGroup).filter(
                models.SystemGroup.name == ADMINS_SYSTEM_GROUP_NAME).one()
        except NoResultFound:
            LOGGER.error('System group %r not found in auth db!', ADMINS_SYSTEM_GROUP_NAME)
            return None

    #
    # Abstract methods (*must* be implemented in concrete subclasses)

    # * Client verification methods:

    def verify_and_get_user_obj(self):        # type: () -> Union[models.User, None]
        """Try to verify user (for given params); get its Auth DB model instance or None."""
        raise NotImplementedError

    def verify_and_get_component_obj(self):   # type: () -> Union[models.Component, None]
        """Try to verify component (for given params); get its Auth DB model instance or None."""
        raise NotImplementedError

    # * Authorization methods:

    def apply_privileged_access_rules(self):  # type: () -> bool
        """Whether general "superuser" access should be granted (may be related to any view)."""
        raise NotImplementedError

    def apply_vhost_rules(self):              # type: () -> bool
        """Whether vhost access should be granted (related to the *vhost_path* view)."""
        raise NotImplementedError

    def apply_exchange_rules(self):           # type: () -> bool
        """Whether exchange access should be granted (related to the *resource_path* view)."""
        raise NotImplementedError

    def apply_queue_rules(self):              # type: () -> bool
        """Whether queue access should be granted (related to the *resource_path* view)."""
        raise NotImplementedError

    def apply_topic_rules(self):              # type: () -> bool
        """Whether topic access should be granted (related to the *topic_path* view)."""
        raise NotImplementedError

    #
    # A hook than *can* be overridden/extended in subclasses (if needed)

    def should_try_to_verify_client(self):    # type: () -> bool
        """Whether the method(s) `verify_and_get_..._obj()` should be called."""
        return True

# Copyright (c) 2019-2022 NASK. All rights reserved.

import sys
import threading
from collections.abc import (
    Callable,
    Mapping,
)

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from typing import (
    Literal,
    Optional,
    Union,
)

from n6lib.auth_db import models
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.const import ADMINS_SYSTEM_GROUP_NAME
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


class BaseBrokerAuthManagerMaker:

    def __init__(self, settings):
        self._db_connector = SQLAuthDBConnector(settings=settings)
        self._manager_creation_lock = threading.Lock()

    def __call__(self, params: Mapping[str, str]) -> 'BaseBrokerAuthManager':
        # Note: `params` is expected to be a mapping containing the HTTP
        # request params, already deduplicated+validated by the view code.
        force_exit_on_any_remaining_entered_contexts(self._db_connector)
        # Note: we guarantee thread-safety of *auth manager* creation.
        with self._manager_creation_lock:
            manager_factory = self.get_manager_factory(params)
            manager_factory_kwargs = self.get_manager_factory_kwargs(params)
            manager = manager_factory(**manager_factory_kwargs)
        assert isinstance(manager, BaseBrokerAuthManager)
        return manager

    #
    # Abstract method (*must* be implemented in concrete subclasses)

    def get_manager_factory(self, params: Mapping[str, str], /,
                            ) -> Callable[..., 'BaseBrokerAuthManager']:
        # (ad `params`: see the relevant comment in `__call__()`)
        raise NotImplementedError

    #
    # Method that may need to be overridden/extended in subclasses
    # (depending on what `get_manager_factory()` returns)

    def get_manager_factory_kwargs(self, params: Mapping[str, str], /,
                                   ) -> KwargsDict:
        # (ad `params`: see the relevant comment in `__call__()`)
        return dict(db_connector=self._db_connector,
                    params=params)


class BaseBrokerAuthManager:

    def __init__(self,
                 db_connector: SQLAuthDBConnector,
                 params: Mapping[str, str]):
        if 'username' not in params:
            raise ValueError("param 'username' not given")  # view code should have ensured that
        self.db_connector: SQLAuthDBConnector = db_connector
        self.params: Mapping[str, str] = params   # request params (already deduplicated+validated)
        self.db_session: Optional[Session] = None
        self.client_obj: Optional[Union[models.User, models.Component]] = None

    def __enter__(self) -> 'BaseBrokerAuthManager':
        self.db_session = self.db_connector.__enter__()
        try:
            self.client_obj = self._verify_and_get_client_obj()
            return self
        except:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.db_connector.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.db_session = None

    def _verify_and_get_client_obj(self) -> Optional[Union[models.User, models.Component]]:
        self._check_presence_of_db_session()
        client_obj = None
        if self.should_try_to_verify_client():
            client_obj = self.verify_and_get_user_obj()
            if client_obj is None:
                client_obj = self.verify_and_get_component_obj()
            elif client_obj.is_blocked:
                client_obj = None
        return client_obj

    def _check_presence_of_db_session(self) -> None:
        if self.db_session is None:
            raise RuntimeError(
                'no database session (use the context '
                'manager interface to provide it...)')

    @property
    def broker_username(self) -> str:
        # may be relevant to any view
        return self.params['username']

    @property
    def password(self) -> Optional[str]:
        # may be relevant to the *user_path* view
        return self.params.get('password')

    @property
    def res_name(self) -> Optional[str]:
        # relevant to the *resource_path* and *topic_path* views
        return self.params.get('name')

    @property
    def permission_level(self) -> Optional[str]:
        # relevant to the *resource_path* and *topic_path* views
        return self.params.get('permission')

    @property
    def client_verified(self) -> bool:
        # may be relevant to any view
        return (self.client_obj is not None)

    @property
    def client_type(self) -> Optional[Literal['user', 'component']]:
        if not self.client_verified:
            return None
        assert self.client_obj is not None
        if isinstance(self.client_obj, models.User):
            return 'user'
        if isinstance(self.client_obj, models.Component):
            return 'component'
        raise TypeError(f'the client object {self.client_obj!a} '
                        f'is an instance of a wrong class')

    @property
    def client_is_admin_user(self) -> bool:
        if self.client_type != 'user':
            return False
        assert self.client_verified and self.client_obj is not None
        self._check_presence_of_db_session()
        admins_group = self._get_admins_group()
        if admins_group is not None:
            return admins_group in self.client_obj.system_groups
        return False

    def _get_admins_group(self) -> Optional[models.SystemGroup]:
        assert self.db_session is not None
        try:
            return self.db_session.query(models.SystemGroup).filter(
                models.SystemGroup.name == ADMINS_SYSTEM_GROUP_NAME).one()
        except NoResultFound:
            LOGGER.error('System group %a not found in auth db!', ADMINS_SYSTEM_GROUP_NAME)
            return None

    #
    # Abstract methods (*must* be implemented in concrete subclasses)

    # * Client verification methods:

    def verify_and_get_user_obj(self) -> Optional[models.User]:
        """Try to verify user (for given params); get its Auth DB model instance or None."""
        raise NotImplementedError

    def verify_and_get_component_obj(self) -> Optional[models.Component]:
        """Try to verify component (for given params); get its Auth DB model instance or None."""
        raise NotImplementedError

    # * Authorization methods:

    def apply_privileged_access_rules(self) -> bool:
        """Whether general "superuser" access should be granted (may be related to any view)."""
        raise NotImplementedError

    def apply_vhost_rules(self) -> bool:
        """Whether vhost access should be granted (related to the *vhost_path* view)."""
        raise NotImplementedError

    def apply_exchange_rules(self) -> bool:
        """Whether exchange access should be granted (related to the *resource_path* view)."""
        raise NotImplementedError

    def apply_queue_rules(self) -> bool:
        """Whether queue access should be granted (related to the *resource_path* view)."""
        raise NotImplementedError

    def apply_topic_rules(self) -> bool:
        """Whether topic access should be granted (related to the *topic_path* view)."""
        raise NotImplementedError

    #
    # A hook than *can* be overridden/extended in subclasses (if needed)

    def should_try_to_verify_client(self) -> bool:
        """Whether the method(s) `verify_and_get_..._obj()` should be called."""
        return True

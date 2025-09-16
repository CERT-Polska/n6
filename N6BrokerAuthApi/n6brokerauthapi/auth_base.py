# Copyright (c) 2019-2025 NASK. All rights reserved.

import sys
import threading
from collections.abc import (
    Callable,
    Mapping,
)
from typing import Optional

from sqlalchemy.orm import Session

from n6lib.auth_db import models
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


class BaseBrokerAuthManagerMaker:

    def __init__(self, settings):
        self._db_connector = SQLAuthDBConnector(settings=settings)
        self._manager_creation_lock = threading.Lock()

    def __call__(self, params: Mapping[str, str],
                 *, need_authentication: bool = False,
                 ) -> 'BaseBrokerAuthManager':
        # Note: `params` is expected to be a mapping containing the HTTP
        # request params, already deduplicated+validated by the view code.
        force_exit_on_any_remaining_entered_contexts(self._db_connector)
        # Note: we guarantee thread-safety of *auth manager* creation.
        with self._manager_creation_lock:
            manager_factory = self.get_manager_factory(params, need_authentication)
            manager_factory_kwargs = self.get_manager_factory_kwargs(params, need_authentication)
            manager = manager_factory(**manager_factory_kwargs)
        assert isinstance(manager, BaseBrokerAuthManager)
        return manager

    #
    # Abstract method (*must* be implemented in concrete subclasses)

    def get_manager_factory(self, params: Mapping[str, str], /,
                            need_authentication: bool,
                            ) -> Callable[..., 'BaseBrokerAuthManager']:
        # (ad `params`: see the relevant comment in `__call__()`)
        raise NotImplementedError

    #
    # Method that may need to be overridden/extended in subclasses
    # (depending on what `get_manager_factory()` returns)

    def get_manager_factory_kwargs(self, params: Mapping[str, str], /,
                                   need_authentication: bool,
                                   ) -> KwargsDict:
        # (ad `params`: see the relevant comment in `__call__()`)
        return dict(db_connector=self._db_connector,
                    params=params,
                    need_authentication=need_authentication)


class BaseBrokerAuthManager:

    def __init__(self, *,
                 db_connector: SQLAuthDBConnector,
                 params: Mapping[str, str],
                 need_authentication: bool):
        if 'username' not in params:
            raise ValueError("param 'username' not given")  # view code should have ensured that
        if need_authentication and 'password' not in params:
            raise ValueError("param 'password' not given")  # view code should have ensured that
        self.db_connector: SQLAuthDBConnector = db_connector
        self.params: Mapping[str, str] = params   # request params (already deduplicated+validated)
        self.need_authentication = need_authentication
        self.db_session: Optional[Session] = None
        self.user_obj: Optional[models.User] = None

    def __enter__(self) -> 'BaseBrokerAuthManager':
        self.db_session = self.db_connector.__enter__()
        try:
            self.user_obj = self._verify_and_get_non_blocked_user_obj()
            return self
        except:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.db_connector.__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.db_session = None

    def _verify_and_get_non_blocked_user_obj(self) -> Optional[models.User]:
        self._check_presence_of_db_session()
        user_obj = None
        if self.should_try_to_verify_user():
            user_obj = self.verify_and_get_user_obj(self.need_authentication)
            if user_obj is not None and user_obj.is_blocked:
                user_obj = None
        return user_obj

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
    def user_verified(self) -> bool:
        # may be relevant to any view
        return (self.user_obj is not None)

    #
    # Abstract methods (*must* be implemented in concrete subclasses)

    # * User verification/authentication method:

    def verify_and_get_user_obj(self, need_authentication: bool) -> Optional[models.User]:
        """
        Try to verify the user and get their Auth DB model instance or None.
        If `need_authentication` is true, the verification **must** include
        authentication (which should, in particular, make use of `self.password`);
        otherwise, it **must not**.
        """
        raise NotImplementedError

    # * Authorization methods:

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

    def should_try_to_verify_user(self) -> bool:
        """Whether the method `verify_and_get_user_obj()` should be called."""
        return True

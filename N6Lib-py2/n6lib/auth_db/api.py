# Copyright (c) 2019-2022 NASK. All rights reserved.

from builtins import map                                                         #3--
import datetime
import operator
import re
import sys
from typing import (
    Iterable,
    List,
    Optional,
)

from sqlalchemy import and_
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
)
from sqlalchemy.orm.exc import (
    NoResultFound,
    ObjectDeletedError,
)

import n6lib.auth_db.models as models
from n6lib.auth_db import (
    MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
    ORG_REQUEST_STATUS_NEW,
)
from n6lib.common_helpers import ascii_str
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.auth_db.fields import (
    DomainNameCustomizedField,
    EmailCustomizedField,
    IPv4NetAlwaysAsStringField,
    IdHexField,
    OrgIdField,
    RegistrationRequestEmailField,
    RegistrationRequestEmailLDAPSafeField,
    TimeHourMinuteField,
    UserLoginField,
    UUID4SecretField,
)
from n6lib.data_spec.fields import (
    ASNField,
    CCField,
    UnicodeLimitedField,
)
from n6lib.typing_helpers import String as Str
from n6sdk.data_spec.fields import FlagField
from n6sdk.data_spec.utils import cleaning_kwargs_as_params_with_data_spec
from n6sdk.exceptions import (
    DataAPIError,
    DataFromClientError,
    DataLookupError,
)


class AuthDatabaseAPIError(DataAPIError):

    def __init__(self, *args, **kwargs):
        self.orig_exc = kwargs.pop('orig_exc', None)
        super(AuthDatabaseAPIError, self).__init__(*args, **kwargs)


class AuthDatabaseAPILookupError(AuthDatabaseAPIError, DataLookupError):
    """TODO docstring"""


class AuthDatabaseAPIClientError(AuthDatabaseAPIError, DataFromClientError):
    """TODO docstring"""


class _AuthDatabaseAPI(object):

    def __init__(self, settings=None, db_connector_config_section=None):
        self._db_connector = SQLAuthDBConnector(settings=settings,
                                                config_section=db_connector_config_section)

    #
    # Non-public helpers (intended to be used in subclasses)

    @property
    def _db_session(self):
        return self._db_connector.get_current_session()

    def _replace_related_objects(self, rel_collection, new_objects):
        del rel_collection[:]
        self._db_session.flush()
        rel_collection.extend(new_objects)
        self._db_session.flush()

    def _delete_all(self, model_class, filter_cond):
        objects = self._db_session.query(model_class).filter(filter_cond).with_for_update().all()
        for obj in objects:
            self._db_session.delete(obj)
        self._db_session.flush()

    def _get_by_primary_key(self, model_class, value):
        try:
            obj = self._db_session.query(model_class).get(value)
        except ObjectDeletedError:
            obj = None
        if obj is None:
            raise AuthDatabaseAPILookupError('{} "{}" does not exist.'.format(
                model_class.__name__,
                ascii_str(value)))
        return obj

    def _get_user_by_login(self, login, for_update=False):
        try:
            query = self._db_session.query(models.User).filter(models.User.login == login)
            if for_update:
                query = query.with_for_update()
            return query.one()
        except NoResultFound:
            raise AuthDatabaseAPILookupError('User "{}" does not exist.'.format(login))

    #
    # Audit-log-specific method (public)

    def set_audit_log_external_meta_items(self, **external_meta_items):
        self._db_connector.set_audit_log_external_meta_items(**external_meta_items)

    #
    # Context manager interface (public) + related helpers (non-public)

    def __enter__(self):
        self._db_connector.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            try:
                self._db_connector.__exit__(exc_type, exc_value, tb)
            except:
                client_error = self._try_to_get_client_error(*sys.exc_info()[:2])
                if client_error is None:
                    raise
            else:
                client_error = self._try_to_get_client_error(exc_type, exc_value)
                if client_error is None:
                    # Note: if `__exit__()` received an exception (`exc_type`
                    # is not None) then that exception is to be re-raised
                    # automatically by the Python `with`-statement mechanism.
                    return False
            raise client_error
        finally:
            # Let's break traceback-related reference cycles.
            client_error = None  # noqa

    def _try_to_get_client_error(self, exc_type, exc_value):
        if isinstance(exc_value, AuthDatabaseAPIError):
            # The exception is already an auth-db-APIs-specific one, so
            # we do not interfere with it (let it be just re-raised on
            # a higher level).
            assert exc_type is type(exc_value)
            return None
        if exc_type is None:
            # No exception to be raised.
            return None
        if exc_value is None:
            exc_value = exc_type()
        public_message = self._try_to_get_client_error_public_message(exc=exc_value)
        if public_message is not None:
            # The exception is a 400-like (i.e., caused by some of the
            # client-provided data; not 500-like) one, so let's replace
            # it with an auth-db-APIs-specific "client error" one.
            return AuthDatabaseAPIClientError(
                public_message=public_message,
                orig_exc=exc_value)
        # The exception is a 500-like (i.e., unexpected) one, so let it
        # be re-raised on a higher level.
        return None

    def _try_to_get_client_error_public_message(self, exc):
        if isinstance(exc, DataFromClientError):  # (e.g., a `ParamCleaningError`)
            return exc.public_message
        elif getattr(exc, '_is_n6_auth_db_validation_error_', False):
            assert hasattr(exc, 'invalid_field')
            return 'The value of the "{}" field is not valid.'.format(exc.invalid_field)
        elif isinstance(exc, DataError):
            return 'The submitted data are not valid.'
        elif isinstance(exc, (IntegrityError, OperationalError)):
            return 'The requested operation is not possible with the submitted data.'
        return None


class AuthManageAPI(_AuthDatabaseAPI):

    @cleaning_kwargs_as_params_with_data_spec(
        org_id=OrgIdField(
            single_param=True,
            in_params='required',
        ),
    )
    def get_org_user_logins(self, org_id):
        # type: (Str) -> List[Str]
        org = self._get_by_primary_key(models.Org, org_id)
        return _attr_list(org.users, 'login')

    def get_user_org_id(self, login):
        # type: (Str) -> Str
        user = self._get_user_by_login(login)
        return user.org_id

    def get_user_and_org_basic_info(self, login):
        # type: (Str) -> dict
        user = self._get_user_by_login(login)
        return {
            'org_id': user.org.org_id,
            'org_actual_name': user.org.actual_name,
            'lang': user.org.email_notification_language,  # TODO?: separate per-user setting?...
        }

    def set_user_password(self, login, password):
        # type: (Str, Str) -> None
        user = self._get_user_by_login(login, for_update=True)
        password_hash = models.User.get_password_hash_or_none(password)
        user.password = password_hash

    def is_user_blocked(self, login):
        # type: (Str) -> bool
        user = self._get_user_by_login(login)
        return bool(user.is_blocked)

    def do_nonblocked_user_and_password_exist_and_match(self, login, password):
        # type: (Str, Str) -> bool
        try:
            user = self._get_user_by_login(login)
        except AuthDatabaseAPILookupError:
            return False
        return bool(not user.is_blocked
                    and user.password
                    and user.verify_password(password))

    def do_nonblocked_user_and_org_exist_and_match(self, login, org_id):
        # type: (Str, Str) -> bool
        try:
            user = self._get_user_by_login(login)
        except AuthDatabaseAPILookupError:
            return False
        return bool(not user.is_blocked
                    and user.org_id == org_id)

    def create_web_token_for_nonblocked_user(self, token_id, token_type, login):
        # type: (Str, Str, Str) -> datetime.datetime
        if self.is_user_blocked(login):
            raise AuthDatabaseAPILookupError('User "{}" is blocked.'.format(login))
        # noinspection PyArgumentList
        token = models.WebToken(token_id=token_id,
                                token_type=token_type,
                                user_login=login,
                                created_on=datetime.datetime.utcnow())
        self._db_session.add(token)
        return token.created_on

    def get_login_of_nonblocked_web_token_owner(self, token_id):
        # type: (Str) -> Str
        token = self._get_by_primary_key(models.WebToken, token_id)
        if token.user.is_blocked:
            raise AuthDatabaseAPILookupError('User "{}" is blocked.'.format(token.user_login))
        return token.user_login

    def get_web_token_type(self, token_id):
        # type: (Str) -> Str
        token = self._get_by_primary_key(models.WebToken, token_id)
        return token.token_type

    def delete_web_token(self, token_id):
        # type: (Str) -> None
        self._delete_all(
            models.WebToken,
            models.WebToken.token_id == token_id)

    def delete_web_tokens_of_given_type_and_owner(self, token_type, login):
        # type: (Str, Str) -> None
        self._delete_all(
            models.WebToken,
            and_(models.WebToken.token_type == token_type,
                 models.WebToken.user_login == login))

    def delete_outdated_web_tokens_of_given_type(self, token_type, token_max_age):
        # type: (Str, int) -> None
        now = datetime.datetime.utcnow()
        self._delete_all(
            models.WebToken,
            and_(models.WebToken.token_type == token_type,
                 models.WebToken.created_on < now - datetime.timedelta(seconds=token_max_age)))

    def create_provisional_mfa_config(self, mfa_key_base, token_id):
        # type: (Str, Str) -> None
        # noinspection PyArgumentList
        provisional_mfa_config = models.UserProvisionalMFAConfig(mfa_key_base=mfa_key_base,
                                                                 token_id=token_id)
        self._db_session.add(provisional_mfa_config)

    def get_provisional_mfa_key_base_or_none(self, token_id):
        # type: (Str) -> Optional[Str]
        try:
            cfg = self._db_session.query(models.UserProvisionalMFAConfig).filter(
                models.UserProvisionalMFAConfig.token_id == token_id).one()
        except NoResultFound:
            return None
        return cfg.mfa_key_base

    def get_actual_mfa_key_base_or_none(self, login):
        # type: (Str) -> Optional[Str]
        try:
            user = self._db_session.query(models.User).filter(
                models.User.login == login).one()
        except NoResultFound:
            return None
        return user.mfa_key_base

    def set_actual_mfa_key_base(self, login, mfa_key_base):
        # type: (Str, Str) -> None
        user = self._get_user_by_login(login, for_update=True)
        user.mfa_key_base = mfa_key_base

    def is_mfa_code_spent_for_user(self, mfa_code, login):
        # type: (Str, Str) -> bool
        try:
            self._db_session.query(models.UserSpentMFACode).filter(
                and_(models.UserSpentMFACode.user_login == login,
                     models.UserSpentMFACode.mfa_code == mfa_code)).one()
        except NoResultFound:
            # noinspection PyArgumentList
            spent_code = models.UserSpentMFACode(mfa_code=mfa_code,
                                                 user_login=login,
                                                 spent_on=datetime.datetime.utcnow())
            self._db_session.add(spent_code)
            self._db_session.flush()
            return False
        return True

    def delete_outdated_spent_mfa_codes(self, mfa_code_max_age):
        # type: (int) -> None
        now = datetime.datetime.utcnow()
        self._delete_all(
            models.UserSpentMFACode,
            models.UserSpentMFACode.spent_on < now - datetime.timedelta(seconds=mfa_code_max_age))

    @cleaning_kwargs_as_params_with_data_spec(
        login=UserLoginField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
        api_key_id=UUID4SecretField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
    )
    def set_user_api_key_id(self, login, api_key_id):
        user = self._get_user_by_login(login, for_update=True)
        user.api_key_id = api_key_id

    @cleaning_kwargs_as_params_with_data_spec(
        login=UserLoginField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
    )
    def get_user_api_key_id(self, login):
        user = self._get_user_by_login(login)
        return user.api_key_id

    @cleaning_kwargs_as_params_with_data_spec(
        login=UserLoginField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
    )
    def delete_user_api_key_id(self, login):
        user = self._get_user_by_login(login, for_update=True)
        if user.api_key_id is not None:
            user.api_key_id = None

    @cleaning_kwargs_as_params_with_data_spec(
        # single-value params
        org_id=OrgIdField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
        actual_name=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
        email=RegistrationRequestEmailLDAPSafeField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
        submitter_title=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
        submitter_firstname_and_surname=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
        terms_version=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
        terms_lang=CCField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),

        notification_language=CCField(
            single_param=True,
            in_params='optional',
            auto_strip=True,
        ),

        # multi-value params:
        notification_emails=RegistrationRequestEmailField(
            in_params='optional',
            auto_strip=True,
        ),
        asns=ASNField(
            in_params='optional',
        ),
        fqdns=DomainNameCustomizedField(
            in_params='optional',
            auto_strip=True,
        ),
        ip_networks=IPv4NetAlwaysAsStringField(
            in_params='optional',
            auto_strip=True,
        ),
    )
    def create_registration_request(self,

                                    # *required param* arguments:
                                    org_id,
                                    actual_name,
                                    email,
                                    submitter_title,
                                    submitter_firstname_and_surname,
                                    terms_version,
                                    terms_lang,

                                    # *optional param* arguments:
                                    notification_language=None,
                                    notification_emails=(),
                                    asns=(),
                                    fqdns=(),
                                    ip_networks=()):

        now = datetime.datetime.utcnow()

        new_req_pure_data = dict(
            submitted_on=now,
            modified_on=now,
            status=ORG_REQUEST_STATUS_NEW,

            org_id=org_id,
            actual_name=actual_name,
            email=email,
            submitter_title=submitter_title,
            submitter_firstname_and_surname=submitter_firstname_and_surname,
            terms_version=terms_version,
            terms_lang=terms_lang,

            notification_language=notification_language,

            # (Note: we ensure that values of multi-value fields are
            # deduplicated and ordered in a deterministic way.)
            notification_emails=sorted(set(notification_emails)),
            asns=sorted(set(asns)),
            fqdns=sorted(set(fqdns)),
            ip_networks=sorted(set(ip_networks)),
        )

        init_kwargs = new_req_pure_data.copy()
        init_kwargs.update(
            email_notification_language=init_kwargs.pop('notification_language'),
            email_notification_addresses=[
                models.RegistrationRequestEMailNotificationAddress.from_value(notif_email)
                for notif_email in init_kwargs.pop('notification_emails')],
            asns=[
                models.RegistrationRequestASN.from_value(asn)
                for asn in init_kwargs.pop('asns')],
            fqdns=[
                models.RegistrationRequestFQDN.from_value(fqdn)
                for fqdn in init_kwargs.pop('fqdns')],
            ip_networks=[
                models.RegistrationRequestIPNetwork.from_value(ip_network)
                for ip_network in init_kwargs.pop('ip_networks')])

        # noinspection PyArgumentList
        new_req = models.RegistrationRequest(**init_kwargs)
        self._db_session.add(new_req)
        self._db_session.flush()

        return new_req.id, new_req_pure_data


    @cleaning_kwargs_as_params_with_data_spec(
        req_id=IdHexField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
        ticket_id=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
    )
    def set_registration_request_ticket_id(self, req_id, ticket_id):
        req = self._get_by_primary_key(models.RegistrationRequest, req_id)
        req.ticket_id = ticket_id


    @cleaning_kwargs_as_params_with_data_spec(
        req_id=IdHexField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
    )
    def create_org_and_user_according_to_registration_request(self, req_id):
        req = self._get_by_primary_key(models.RegistrationRequest, req_id)
        assert isinstance(req, models.RegistrationRequest)

        email_notification_enabled = bool(req.email_notification_addresses)
        email_notification_time_values = (
            list(self._NEW_ORG_EMAIL_NOTIFICATION_TIME_INITIAL_VALUES)
            if email_notification_enabled
            else [])

        # noinspection PyArgumentList
        new_user = models.User(login=req.email)

        # noinspection PyArgumentList
        new_org = models.Org(
            org_id=req.org_id,
            actual_name=req.actual_name,
            org_groups=[req.org_group],

            users=[new_user],

            access_to_inside=self._NEW_ORG_ACCESS_TO_INSIDE_VALUE,
            access_to_threats=self._NEW_ORG_ACCESS_TO_THREATS_VALUE,

            email_notification_enabled=email_notification_enabled,
            email_notification_addresses=[
                models.EMailNotificationAddress.from_value(obj.email)
                for obj in req.email_notification_addresses],
            email_notification_times=[
                models.EMailNotificationTime.from_value(notification_time)
                for notification_time in email_notification_time_values],
            email_notification_language=req.email_notification_language,

            inside_filter_asns=[
                models.InsideFilterASN.from_value(obj.asn)
                for obj in req.asns],
            inside_filter_fqdns=[
                models.InsideFilterFQDN.from_value(obj.fqdn)
                for obj in req.fqdns],
            inside_filter_ip_networks=[
                models.InsideFilterIPNetwork.from_value(obj.ip_network)
                for obj in req.ip_networks])

        self._db_session.add(new_org)
        self._db_session.flush()

    _NEW_ORG_ACCESS_TO_INSIDE_VALUE = True
    _NEW_ORG_ACCESS_TO_THREATS_VALUE = True
    _NEW_ORG_EMAIL_NOTIFICATION_TIME_INITIAL_VALUES = (datetime.time(9),)


    @cleaning_kwargs_as_params_with_data_spec(
        org_id=OrgIdField(
            single_param=True,
            in_params='required',
        ),
    )
    def get_org_config_info(self, org_id):
        org = self._get_by_primary_key(models.Org, org_id)
        req = org.pending_config_update_request
        return dict(
            org_id=org.org_id,
            actual_name=org.actual_name,
            notification_enabled=org.email_notification_enabled,
            notification_language=org.email_notification_language,
            notification_emails=_attr_list(org.email_notification_addresses, 'email'),
            notification_times=_notif_time_attr_list(org.email_notification_times,
                                                     'notification_time'),
            asns=_attr_list(org.inside_filter_asns, 'asn'),
            fqdns=_attr_list(org.inside_filter_fqdns, 'fqdn'),
            ip_networks=_attr_list(org.inside_filter_ip_networks, 'ip_network'),
            update_info=(None if req is None
                         else _pure_data_from_org_config_update_request(req)))


    @cleaning_kwargs_as_params_with_data_spec(
        _keep_empty_multi_value_param_lists=True,

        # single-value params
        org_id=OrgIdField(
            single_param=True,
            in_params='required',
        ),
        requesting_user_login=UserLoginField(
            single_param=True,
            in_params='required',
        ),

        additional_comment=UnicodeLimitedField(
            single_param=True,
            in_params='optional',
            auto_strip=True,
            max_length=4000,
        ),
        actual_name=UnicodeLimitedField(
            single_param=True,
            in_params='optional',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
        notification_enabled=FlagField(
            single_param=True,
            in_params='optional',
            enable_empty_param_as_true=False,
        ),
        notification_language=CCField(
            single_param=True,
            in_params='optional',
            auto_strip=True,
            regex=re.compile(
                r'\A'
                r'(?:'
                r'[A-Z][A-Z12]'
                r'|'  # can be empty
                r')'
                r'\Z', re.ASCII),
        ),

        # multi-value params:
        notification_emails=EmailCustomizedField(
            in_params='optional',
            auto_strip=True,
        ),
        notification_times=TimeHourMinuteField(
            in_params='optional',
        ),
        asns=ASNField(
            in_params='optional',
        ),
        fqdns=DomainNameCustomizedField(
            in_params='optional',
            auto_strip=True,
        ),
        ip_networks=IPv4NetAlwaysAsStringField(
            in_params='optional',
            auto_strip=True,
        ),
    )
    def create_org_config_update_request(self,

                                         # *required param* arguments:
                                         org_id,
                                         requesting_user_login,

                                         # *optional param* arguments:
                                         additional_comment=None,
                                         actual_name=None,
                                         notification_enabled=None,
                                         notification_language=None,
                                         notification_emails=None,
                                         notification_times=None,
                                         asns=None,
                                         fqdns=None,
                                         ip_networks=None):

        init_kwargs = {}

        if actual_name is not None:
            init_kwargs['actual_name_upd'] = True
            init_kwargs['actual_name'] = actual_name or None
        if notification_enabled is not None:
            init_kwargs['email_notification_enabled_upd'] = True
            init_kwargs['email_notification_enabled'] = notification_enabled
        if notification_language is not None:
            init_kwargs['email_notification_language_upd'] = True
            init_kwargs['email_notification_language'] = notification_language or None
        # (Note: we ensure that values of multi-value fields are
        # deduplicated and ordered in a deterministic way.)
        if notification_emails is not None:
            init_kwargs['email_notification_addresses_upd'] = True
            init_kwargs['email_notification_addresses'] = [
                models.OrgConfigUpdateRequestEMailNotificationAddress.from_value(notif_email)
                for notif_email in sorted(set(notification_emails))]
        if notification_times is not None:
            init_kwargs['email_notification_times_upd'] = True
            init_kwargs['email_notification_times'] = [
                models.OrgConfigUpdateRequestEMailNotificationTime.from_value(notif_time)
                for notif_time in sorted(set(notification_times))]
        if asns is not None:
            init_kwargs['asns_upd'] = True
            init_kwargs['asns'] = [
                models.OrgConfigUpdateRequestASN.from_value(asn)
                for asn in sorted(set(asns))]
        if fqdns is not None:
            init_kwargs['fqdns_upd'] = True
            init_kwargs['fqdns'] = [
                models.OrgConfigUpdateRequestFQDN.from_value(fqdn)
                for fqdn in sorted(set(fqdns))]
        if ip_networks is not None:
            init_kwargs['ip_networks_upd'] = True
            init_kwargs['ip_networks'] = [
                models.OrgConfigUpdateRequestIPNetwork.from_value(ip_network)
                for ip_network in sorted(set(ip_networks))]

        if not init_kwargs:
            raise AuthDatabaseAPIClientError('The requested org config update '
                                             'does not include any changes.')

        now = datetime.datetime.utcnow()
        init_kwargs.update(
            submitted_on=now,
            modified_on=now,
            status=ORG_REQUEST_STATUS_NEW,

            org_id=org_id,
            requesting_user_login=requesting_user_login,
        )
        if additional_comment:
            init_kwargs['additional_comment'] = additional_comment

        # noinspection PyArgumentList
        new_req = models.OrgConfigUpdateRequest(**init_kwargs)
        self._db_session.add(new_req)
        self._db_session.flush()

        new_req_id = new_req.id
        new_req_pure_data = _pure_data_from_org_config_update_request(new_req)

        return new_req_id, new_req_pure_data


    @cleaning_kwargs_as_params_with_data_spec(
        req_id=IdHexField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
        ticket_id=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
        ),
    )
    def set_org_config_update_request_ticket_id(self, req_id, ticket_id):
        req = self._get_by_primary_key(models.OrgConfigUpdateRequest, req_id)
        req.ticket_id = ticket_id


    @cleaning_kwargs_as_params_with_data_spec(
        req_id=IdHexField(
            single_param=True,
            in_params='required',
            auto_strip=True,
        ),
    )
    def update_org_according_to_org_config_update_request(self, req_id):
        req = self._get_by_primary_key(models.OrgConfigUpdateRequest, req_id)
        assert isinstance(req, models.OrgConfigUpdateRequest)

        org = req.org
        if org is None:
            raise AuthDatabaseAPIError('Org config update request #{} does not have its `org`?!'
                                       .format(ascii_str(req_id)))

        assert isinstance(org, models.Org)

        if req.actual_name_upd:
            org.actual_name = req.actual_name

        if req.email_notification_enabled_upd:
            org.email_notification_enabled = req.email_notification_enabled
        if req.email_notification_language_upd:
            org.email_notification_language = req.email_notification_language
        if req.email_notification_addresses_upd:
            self._replace_related_objects(org.email_notification_addresses, new_objects=(
                models.EMailNotificationAddress.from_value(obj.email)
                for obj in req.email_notification_addresses))
        if req.email_notification_times_upd:
            self._replace_related_objects(org.email_notification_times, new_objects=(
                models.EMailNotificationTime.from_value(obj.notification_time)
                for obj in req.email_notification_times))

        if req.asns_upd:
            self._replace_related_objects(org.inside_filter_asns, new_objects=(
                models.InsideFilterASN.from_value(obj.asn)
                for obj in req.asns))
        if req.fqdns_upd:
            self._replace_related_objects(org.inside_filter_fqdns, new_objects=(
                models.InsideFilterFQDN.from_value(obj.fqdn)
                for obj in req.fqdns))
        if req.ip_networks_upd:
            self._replace_related_objects(org.inside_filter_ip_networks, new_objects=(
                models.InsideFilterIPNetwork.from_value(obj.ip_network)
                for obj in req.ip_networks))


def _pure_data_from_org_config_update_request(req):
    assert isinstance(req, models.OrgConfigUpdateRequest)
    req_pure_data = {
        'update_request_time': req.submitted_on.replace(microsecond=0),
        'requesting_user': req.requesting_user_login
    }
    if req.additional_comment:
        req_pure_data['additional_comment'] = req.additional_comment
    if req.actual_name_upd:
        req_pure_data['actual_name'] = req.actual_name
    if req.email_notification_enabled_upd:
        req_pure_data['notification_enabled'] = req.email_notification_enabled
    if req.email_notification_language_upd:
        req_pure_data['notification_language'] = req.email_notification_language
    if req.email_notification_addresses_upd:
        req_pure_data['notification_addresses'] = _attr_list(req.email_notification_addresses,
                                                             'email')
    if req.email_notification_times_upd:
        req_pure_data['notification_times'] = _notif_time_attr_list(req.email_notification_times,
                                                                    'notification_time')
    if req.asns_upd:
        req_pure_data['asns'] = _attr_list(req.asns, 'asn')
    if req.fqdns_upd:
        req_pure_data['fqdns'] = _attr_list(req.fqdns, 'fqdn')
    if req.ip_networks_upd:
        req_pure_data['ip_networks'] = _attr_list(req.ip_networks, 'ip_network')
    return req_pure_data


def _attr_list(objects, attr_name):
    # type: (Iterable, Str) -> list
    return sorted(map(operator.attrgetter(attr_name), objects))  # type: list


def _notif_time_attr_list(objects, attr_name):
    # type: (Iterable, Str) -> List[datetime.time]
    values = _attr_list(objects, attr_name)
    return [t.replace(second=0, microsecond=0)  # (defense against overspecified values in DB)
            for t in values]

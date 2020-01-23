# Copyright (c) 2013-2020 NASK. All rights reserved.

import datetime
import re
import sys

from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
)

import n6lib.auth_db.models as models
from n6lib.auth_db import (
    MAX_LEN_OF_OFFICIAL_ACTUAL_NAME,
    MAX_LEN_OF_GENERIC_SHORT_STRING,
    REGISTRATION_REQUEST_STATUS_NEW,
)
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.auth_db.fields import (
    DomainNameCustomizedField,
    IPv4NetAlwaysAsStringField,
    OrgIdField,
    RegistrationRequestEmailField,
    RegistrationRequestEmailLDAPSafeField,
)
from n6lib.data_spec.fields import (
    ASNField,
    CCField,
    UnicodeLimitedField,
    UnicodeRegexField,
)
from n6sdk.data_spec.utils import cleaning_kwargs_as_params_with_data_spec
from n6sdk.exceptions import DataAPIError


class AuthDatabaseAPIClientError(DataAPIError):
    """TODO docstring"""


class _AuthDatabaseAPI(object):

    def __init__(self, settings=None, db_connector_config_section=None):
        self._db_connector = SQLAuthDBConnector(settings=settings,
                                                config_section=db_connector_config_section)

    @property
    def _db_session(self):
        return self._db_connector.get_current_session()

    def set_audit_log_external_meta_items(self, **external_meta_items):
        self._db_connector.set_audit_log_external_meta_items(**external_meta_items)

    def __enter__(self):
        self._db_connector.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            self._db_connector.__exit__(exc_type, exc_value, tb)
        except:
            exc = self._get_client_error_to_raise(*sys.exc_info()[:2])
            if exc is None:
                raise
        else:
            exc = self._get_client_error_to_raise(exc_type, exc_value)
            if exc is None:
                return
        raise exc

    def _get_client_error_to_raise(self, exc_type, exc_value):
        if exc_type is None:
            return None
        if exc_value is None:
            exc_value = exc_type()
        public_message = self._get_public_message_from_exc(exc=exc_value)
        if public_message is not None:
            return AuthDatabaseAPIClientError(public_message=public_message)
        return None

    def _get_public_message_from_exc(self, exc):
        if isinstance(exc, DataAPIError):
            return exc.public_message
        elif getattr(exc, '_is_n6_auth_db_validation_error_', False):
            assert hasattr(exc, 'invalid_field')
            return 'The value of the "{}" field is not valid.'.format(exc.invalid_field)
        elif isinstance(exc, DataError):
            return 'The submitted data are not valid.'
        elif isinstance(exc, (IntegrityError, OperationalError)):
            return 'The requested operation is not possible.'
        return None


class AuthQueryAPI(_AuthDatabaseAPI):
    "TODO"


class AuthManageAPI(_AuthDatabaseAPI):

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
            max_length=MAX_LEN_OF_OFFICIAL_ACTUAL_NAME,
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
            max_length=MAX_LEN_OF_GENERIC_SHORT_STRING,
        ),
        submitter_firstname_and_surname=UnicodeLimitedField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            max_length=MAX_LEN_OF_GENERIC_SHORT_STRING,
        ),
        csr=UnicodeRegexField(
            single_param=True,
            in_params='required',
            auto_strip=True,
            regex=re.compile(
                # see: https://tools.ietf.org/html/rfc7468#section-3
                r'\A'
                r'-----BEGIN CERTIFICATE REQUEST-----\s*'
                r'[a-zA-Z0-9+/=\s]+'
                r'-----END CERTIFICATE REQUEST-----\s*'
                r'\Z'
            ),
            error_msg_template=u'"Not a valid PEM-formatted Certificate Signing Request',
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
                                    org_id,
                                    actual_name,
                                    email,
                                    submitter_title,
                                    submitter_firstname_and_surname,
                                    csr,
                                    notification_language=None,
                                    notification_emails=(),
                                    asns=(),
                                    fqdns=(),
                                    ip_networks=()):
        now = datetime.datetime.utcnow()
        unique_sorted_notification_emails = sorted(set(notification_emails))
        unique_sorted_asns = sorted(set(asns))
        unique_sorted_fqdns = sorted(set(fqdns))
        unique_sorted_ip_networks = sorted(set(ip_networks))
        with self:
            registration_request = models.RegistrationRequest(
                submitted_on=now,
                modified_on=now,
                status=REGISTRATION_REQUEST_STATUS_NEW,
                org_id=org_id,
                actual_name=actual_name,
                email=email,
                submitter_title=submitter_title,
                submitter_firstname_and_surname=submitter_firstname_and_surname,
                csr=csr,
                email_notification_language=notification_language,
                email_notification_addresses=[
                    models.RegistrationRequestEMailNotificationAddress(email=notif_email)
                    for notif_email in unique_sorted_notification_emails],
                asns=[
                    models.RegistrationRequestASN(asn=asn)
                    for asn in unique_sorted_asns],
                fqdns=[
                    models.RegistrationRequestFQDN(fqdn=fqdn)
                    for fqdn in unique_sorted_fqdns],
                ip_networks=[
                    models.RegistrationRequestIPNetwork(ip_network=ip_network)
                    for ip_network in unique_sorted_ip_networks])
            self._db_session.add(registration_request)

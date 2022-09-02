# -*- coding: utf-8 -*-

# Copyright (c) 2014-2022 NASK. All rights reserved.

import contextlib
import datetime
import re
import string

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import StatementError

from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.auth_db.fields import EmailCustomizedField
from n6lib.auth_db.models import (
    CLIENT_CA_PROFILE_NAME,
    SERVICE_CA_PROFILE_NAME,
    CACert,
    Cert,
    Component,
    Org,
    SystemGroup,
    User,
)
from n6lib.auth_db.validators import is_cert_serial_number_valid
from n6lib.common_helpers import (
    ascii_str,
    make_hex_id,
)
from n6lib.config import (
    ConfigError,
    ConfigMixin,
)
from n6lib.const import (
    CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM,
    ADMINS_SYSTEM_GROUP_NAME,
)
from n6corelib.manage_api._ca_env import (
    InvalidSSLConfigError,
    generate_certificate_pem,
    generate_crl_pem,
    get_ca_env_configuration,
    revoke_certificate_and_generate_crl_pem,
)
from n6corelib.x509_helpers import (
    UnexpectedCertificateDataError,
    FORMAT_PEM,
    get_cert_authority_key_identifier,
    get_cert_not_after,
    get_cert_not_before,
    get_cert_serial_number_as_hex,
    get_cert_subject_dict,
    get_cert_subject_key_identifier,
    get_subject_as_x509_name_obj,
    is_ca_cert,
    is_client_cert,
    is_server_cert,
    load_cert_string,
    load_request_string,
    normalize_hex_serial_number,
    verify_cert,
    verify_request,
)

ADMIN_OU = 'n6admins'
COMPONENT_OU = 'n6components'
USER_KINDS_OF_OWNER = ('app-user', 'admin')
COMPONENT_KINDS_OF_OWNER = ('component', 'server-component')

_SLUG_CHARS = set(string.ascii_lowercase + string.digits + '-.')
SLUG_TRANS = ''.join(
    (c if c in _SLUG_CHARS else '-')
    for c in (
        chr(i).lower()
        for i in xrange(256)))


def db_property_factory(db_obj_attr_name):

    """
    Get a `database_property` class, which uses the factory's
    `db_obj_attr_name` value to refer to a proper attribute
    of a class, which uses `database_property` as a decorator
    for properties.

    Args:
        `db_obj_attr_name`:
            Name of an attribute referenced by `database_property`.

    Returns:
        A `database_property` class.
    """

    class database_property(property):
        """
        A subclass of built-in `property`. Value of a property
        is at first being fetched from an object, which represents
        database table. The object may be fetched from database,
        or created with local arguments yet to be saved to the
        database.

        If the object is not found, a return value of a method
        decorated by this class becomes a value of the property.

        This class is intended to be used inside the `_CertificateBase`
        class and its subclasses as a decorator of class attributes,
        like the original `property`.
        """

        def __init__(self, fget, **kwargs):
            property_name = getattr(fget, '__name__', None)
            if property_name is None:
                raise TypeError("A {!r} class should decorate a method, which "
                                "returns value of the property".format(self.__class__.__name__))
            self.property_name = property_name
            super(database_property, self).__init__(fget, **kwargs)

        def __get__(self, instance, owner=None):
            if instance is None:
                return self
            cert_db_obj = getattr(instance, db_obj_attr_name, None)
            if cert_db_obj is not None:
                try:
                    return getattr(cert_db_obj, self.property_name)
                except AttributeError:
                    raise ManageAPIError("A field {!r} is not present in the database "
                                         "table represented by the {!r} "
                                         "object".format(self.property_name, cert_db_obj))
            return super(database_property, self).__get__(instance, owner)
    database_property.__name__ = '{}__{}'.format(database_property.__name__, db_obj_attr_name)
    return database_property


def _adjust_if_is_legacy_user_login(login):
    # Even though, nowadays, *user logins* (aka *user ids*) cannot
    # contain any uppercase letters, user logins from subjects of
    # *legacy client certificates* can include such characters.
    if (login is not None
          and EmailCustomizedField.regex.search(login)
          and login != login.lower()):
        login = login.lower()
    return login



class ManageAPIError(Exception):

    """
    Raised from a ManageAPI to signal a problem.
    """


class AccessForbiddenError(ManageAPIError):

    """
    Raised when entity trying to use Manage API does not
    have access permission.
    """


class ManageAPIAuthDBConnector(SQLAuthDBConnector):

    """
    Example of a class handling auth database connection. Its
    implementation may change, if a type of database changes.

    It has to implement a context manager, which:
     * Returns a "connection context" - an object, which will be used
       to provide necessary attributes/methods inside methods, that are
       part of the auth database interface - on entering the
       context manager.
     * Saves changes made to the database (commits a session), or
       rolls them back in case of errors, and closes the session.

    A "connection context" may be a simple namespace, which stores
    references to objects necessary to communicate with database.
    In case of MySQL-like database and SQLAlchemy models, it provides
    a session object, so the interface methods, that have the
    "connection context" passed to as an argument, are able to query
    from database, insert new records, etc. via the session.

    Besides a reference to a session object, the "connection context"
    provides paths to CA, user certificate and key files, used to
    establish database connection. It may also contain a login
    of a user connecting to database.

    The idea behind the "connection context" is to include as little
    details as possible about a database and move those details to the
    interface. Methods, which are part of the interface, gets necessary
    objects from this context. Although, what they get and how they
    use it, may depend on a used database, ORM etc. - implementation
    of the context class should be adjusted accordingly.

    Having the "connection context" and database interface implemented,
    a user does not have to deal with communication details outside
    of the interface.

    Outside of the database interface, user only has to be concerned
    to pass the "connection context" to interface methods he uses.
    """

    assert ('ssl_cacert = none' in SQLAuthDBConnector.config_spec_pattern and
            'ssl_cert = none' in SQLAuthDBConnector.config_spec_pattern and
            'ssl_key = none' in SQLAuthDBConnector.config_spec_pattern)

    config_spec_pattern = (
        SQLAuthDBConnector.config_spec_pattern
        # (here these three config options are *required*, not optional)
        .replace('ssl_cacert = none', 'ssl_cacert')
        .replace('ssl_cert = none', 'ssl_cert')
        .replace('ssl_key = none', 'ssl_key'))


    class ConnectionContext(object):

        """
        Implementation of a "connection context" class, used
        within database interface methods, adjusted for an SQL
        database and SQLAlchemy library to handle a connection.

        Args:
            `db_session`:
                An SQLAlchemy session object.
            `ca_path`:
                Path to a CA certificate PEM file.
            `cert_path`:
                Path to a certificate PEM file.
            `key_path`:
                Path to an SSL private key PEM file.

        PEM files paths are then used to configure an SSL connection
        with a database - currently the SSL is mandatory.

        The session object is used to obtain database user login,
        stored in a class instance as `database_login` attribute.
        """

        def __init__(self, db_session, ca_path, cert_path, key_path):
            self.db_session = db_session
            self.ca_path = ca_path
            self.cert_path = cert_path
            self.key_path = key_path
            self.database_login = self.db_session.bind.url.username


    def __init__(self, *args, **kwargs):
        self._ssl_opts = None
        super(ManageAPIAuthDBConnector, self).__init__(*args, **kwargs)

    def get_ssl_related_create_engine_kwargs(self):
        ssl_engine_kwargs = super(ManageAPIAuthDBConnector,
                                  self).get_ssl_related_create_engine_kwargs()
        if not ssl_engine_kwargs:
            raise ManageAPIError(
                'Auth DB connection config for {} (section `{}`) '
                'has to specify SSL-related options'.format(
                    self.__class__.__name__,
                    self.config_section))
        self._ssl_opts = ssl_engine_kwargs['connect_args']['ssl']
        return ssl_engine_kwargs

    def __enter__(self):
        return self.context_deposit.on_enter(
            outermost_context_factory=self.make_connection_context,
            context_factory=NotImplemented)

    def __exit__(self, exc_type, exc, tb):
        return self.context_deposit.on_exit(
            exc_type, exc, tb,
            outermost_context_finalizer=self.finalize_connection_context)

    def get_current_session(self):
        # (this method seems to be unused in this module but let's
        # have it properly implemented for the sake of completenes)
        connection_context = self.context_deposit.outermost_context
        if connection_context is None:
            return None
        assert isinstance(connection_context, self.ConnectionContext)
        return connection_context.db_session

    def make_connection_context(self):
        session = self.db_session_factory()
        try:
            ca_path = self._ssl_opts['ca']
            cert_path = self._ssl_opts['cert']
            key_path = self._ssl_opts['key']
            return self.ConnectionContext(session, ca_path, cert_path, key_path)
        except:
            session.close()
            raise

    def finalize_connection_context(self, connection_context, exc_type, exc_value, tb):
        assert isinstance(connection_context, self.ConnectionContext)
        self.finalize_session(connection_context.db_session, exc_type, exc_value, tb)

    @contextlib.contextmanager
    def commit_wrapper(self, session):
        with super(ManageAPIAuthDBConnector, self).commit_wrapper(session):
            try:
                yield
            except StatementError as exc:
                raise ManageAPIError("Execution of the SQL statement: {!r} caused "
                                     "an error: {!r}".format(exc.statement, exc.message))
            except Exception as exc:
                raise ManageAPIError("Fatal error: {}".format(ascii_str(exc)))

    def set_manage_api_specific_audit_log_meta_items(self, managing_entity):
        assert isinstance(managing_entity, ManagingEntity)
        if managing_entity.entity_type == 'user':
            meta_items = {'request_user_id': managing_entity.user_db_obj.login,
                          'request_org_id': managing_entity.user_db_obj.org_id}
        else:
            assert managing_entity.entity_type == 'component'
            meta_items = {'request_component_id': managing_entity.component_db_obj.login}
        meta_items['n6_module'] = __name__
        self.set_audit_log_external_meta_items(**meta_items)


class ManageAPI(ConfigMixin):

    """
    A Manage API module's main, public class, implementing
    API's main functionalities.

    Kwargs:
        `manage_api_config_section` (default: "manage_api"):
            Name of Manage API config section.
        `auth_db_config_section` (default: None):
            Name of Auth DB config section, used to configure
            database connection. If default  value is used,
            a connector class will use "auth_db" section name.
        `settings` (default: None):
            If not None, it has to be a Pyramid-like settings
            dictionary, which will be used as a config instead
            of a standard n6 config.
    """

    auth_db_connector = ManageAPIAuthDBConnector

    config_spec_pattern = '''
        [{manage_api_config_section}]
        # Pattern validating an 'O' part of *internal* certificates'
        # subjects. It applies to "admin" and "component" kinds of owner
        # ("admin" kind if 'OU' of certificate's subject is "n6admins"
        # and the certificate is signed by a service CA;
        # "component" - if 'OU' is "n6components", certificate is signed
        # by a service CA).

        internal_o_regex_pattern


        # If an 'OU' part of added certificate's subject matches 
        # the regex pattern, and the certificate is signed by
        # a service CA, its owner will be a "server-component".

        server_component_ou_regex_pattern
        ...
    '''

    # note: for now, a ManageAPI instance is *not* thread-safe
    # (that can change in the future...)
    def __init__(self,
                 manage_api_config_section='manage_api',
                 auth_db_config_section=None,
                 settings=None):
        self._auth_db_connector = self.auth_db_connector(settings=settings,
                                                         config_section=auth_db_config_section)
        self._config = self.get_config_section(settings,
                                               manage_api_config_section=manage_api_config_section)
        self._internal_o_regex = re.compile(self._config['internal_o_regex_pattern'])
        self._server_component_ou_regex = re.compile(
            self._config['server_component_ou_regex_pattern'])
        self._settings = settings
        self._manage_api_config_section = manage_api_config_section

    def _verify_and_get_managing_entity(self, context):
        return ManagingEntity(context, self._internal_o_regex)

    def iter_all_ca_data(self):

        """
        Get an iterator through CA certificates' details.

        Returns:
            An iterator that for each of CA certificates stored in the
            Auth DB yields an opaque object that provides at least the
            following attributes:
            * `ca_label`
              -- the CA's label (i.e., the identifier in the Auth DB),
            * `profile`
              -- the CA's profile ('client' or 'service') or None,
            * `subject_key_identifier`
              -- the CA's Subject Key Identifier (X509v3 extension) or None,
            * `authority_key_identifier`
              -- the CA's Authority Key Identifier (X509v3 extension) or None.
        """

        with self._auth_db_connector as context:
            self._verify_and_get_managing_entity(context)
            return CACertificate.iter_all(context,
                                          self._manage_api_config_section,
                                          self._settings)

    def add_given_cert(self, ca_label, cert_pem, created_on, creator_hostname,
                       adding_owner=False,
                       server_component_login=None):

        """
        Add a new certificate, passed to the method, to Auth DB.

        Args:
            `ca_label` (str):
                Label of an issuer CA certificate.
            `cert_pem` (str):
                Certificate as a string, in the PEM format.
            `created_on` (str or datetime.datetime):
                Datetime of when the certificate was created.
            `creator_hostname` (str):
                Hostname of an entity using the Manage API.
            `adding_owner` (bool; default: False):
                If true, a certificate owner should be added to Auth DB
                (it will succeed only if the owner does not exist
                already in the database).
            `server_component_login` (None or str; default: None):
                Must be specified (as a non-None value) if the
                certificate that is being created belongs to an n6
                public server (the certificate's `kind` is
                "server-component"); otherwise it must be None.
        """

        with self._auth_db_connector as context:
            managing_entity = self._verify_and_get_managing_entity(context)
            self._auth_db_connector.set_manage_api_specific_audit_log_meta_items(managing_entity)
            ca_cert = CACertificate(context,
                                    ca_label,
                                    self._manage_api_config_section,
                                    self._settings,
                                    must_have_profile=True)
            cert = CertificateCreated(context,
                                      ca_repr_obj=ca_cert,
                                      created_on=created_on,
                                      creator_login=managing_entity.login,
                                      creator_type=managing_entity.entity_type,
                                      creator_hostname=creator_hostname,
                                      database_login=managing_entity.database_login,
                                      internal_o_regex=self._internal_o_regex,
                                      server_component_ou_regex=self._server_component_ou_regex,
                                      cert_pem=cert_pem,
                                      adding_owner=adding_owner,
                                      server_component_login=server_component_login)
            cert.add_new_cert_db_obj_to_db()

    def make_new_cert(self, ca_label, csr_pem, creator_hostname,
                      adding_owner=False,
                      server_component_login=None):

        """
        Create a new certificate and add it to Auth DB.

        Args:
            `ca_label` (str):
                Label of an issuer CA certificate.
            `csr_pem` (str):
                Certificate Signing Request as a string, in
                the PEM format.
            `creator_hostname` (str):
                Hostname of an entity using the Manage API.
            `adding_owner` (bool; default: False):
                If true, a certificate owner should be added to Auth DB
                (it will succeed only if the owner does not exist
                already in the database)
            `server_component_login` (None or str; default: None):
                Must be specified (as a non-None value) if the
                certificate that is being created belongs to an n6
                public server (the certificate's `kind` is
                "server-component"); otherwise it must be None.

        Returns:
            A tuple of: a new certificate file, as a string, in
            the PEM format and a filename-and-URL-friendly text
            label of the certificate (a slug).
        """

        with self._auth_db_connector as context:
            managing_entity = self._verify_and_get_managing_entity(context)
            self._auth_db_connector.set_manage_api_specific_audit_log_meta_items(managing_entity)
            csr_file_obj = CSRFile(csr_pem)
            ca_cert = CACertificate(context,
                                    ca_label,
                                    self._manage_api_config_section,
                                    self._settings,
                                    must_have_profile=True)
            cert = CertificateCreated(context,
                                      ca_repr_obj=ca_cert,
                                      created_on=datetime.datetime.utcnow(),
                                      creator_login=managing_entity.login,
                                      creator_type=managing_entity.entity_type,
                                      creator_hostname=creator_hostname,
                                      database_login=managing_entity.database_login,
                                      internal_o_regex=self._internal_o_regex,
                                      server_component_ou_regex=self._server_component_ou_regex,
                                      csr_pem=csr_pem,
                                      adding_owner=adding_owner,
                                      server_component_login=server_component_login)
            csr_file_obj.verify_csr(cert.cert_file)
            cert.add_new_cert_db_obj_to_db()
            return cert.certificate, cert.slug

    def revoke_cert(self, ca_label, serial_number, revocation_comment):

        """
        Revoke a certificate kept in Auth DB.

        Args:
            `ca_label` (str):
                Label of an issuer CA certificate.
            `serial_number` (str):
                Serial number of a certificate to revoke.
            `revocation_comment` (str):
                A reason why the certificate has been revoked.

        Returns:
            A Certificate Revocation List for the CA, whose label
            has been passed as a `ca_label` argument, as a string in
            the PEM format.
        """

        if revocation_comment is None:
            raise ManageAPIError('When revoking a certificate '
                                 '`revocation_comment` must not be None')

        with self._auth_db_connector as context:
            managing_entity = self._verify_and_get_managing_entity(context)
            self._auth_db_connector.set_manage_api_specific_audit_log_meta_items(managing_entity)
            ca_cert = CACertificate(context,
                                    ca_label,
                                    self._manage_api_config_section,
                                    self._settings,
                                    must_have_profile=True)
            cert = CertificateFromDatabase.from_serial_number(context, ca_cert, serial_number)
            if cert.is_revoked:
                raise ManageAPIError(
                    'The certificate with serial number: {!r} has already been revoked.'.format(
                        serial_number))
            try:
                crl_pem = revoke_certificate_and_generate_crl_pem(ca_cert.get_env_configuration(),
                                                                  cert)
            except InvalidSSLConfigError as exc:
                raise ManageAPIError(
                    "SSL config assigned to particular CA certificate (label {!r}) "
                    "is not valid: {}".format(ca_label, exc.actual_reason))
            cert.set_revocation_fields(revoked_on=datetime.datetime.utcnow(),
                                       revoked_by_user=managing_entity.user_db_obj,
                                       revoked_by_component=managing_entity.component_db_obj,
                                       revocation_comment=revocation_comment)
            return crl_pem

    def get_cert_pem_and_slug(self, ca_label, serial_number):

        """
        Get certificate's PEM file and slug from Auth DB.

        Args:
            `ca_label` (str):
                Label of an issuer CA certificate.
            `serial_number` (str):
                Serial number of requested certificate.

        Returns:
            A tuple of: a certificate file, as a string, in
            the PEM format and a filename-and-URL-friendly text
            label of the certificate (a slug).
        """

        with self._auth_db_connector as context:
            managing_entity = self._verify_and_get_managing_entity(context)
            self._auth_db_connector.set_manage_api_specific_audit_log_meta_items(managing_entity)
            ca_cert = CACertificate(context,
                                    ca_label,
                                    self._manage_api_config_section,
                                    self._settings,
                                    must_have_profile=True)
            cert = CertificateFromDatabase.from_serial_number(context, ca_cert, serial_number)
            return cert.certificate, cert.slug

    def get_crl_pem(self, ca_label):

        """
        Get a Certificate Revocation List for a given CA certificate.

        Args:
            `ca_label` (str):
                Label of CA certificate, for which a CRL is searched.

        Returns:
            A Certificate Revocation List PEM file, as a string.
        """

        with self._auth_db_connector as context:
            managing_entity = self._verify_and_get_managing_entity(context)
            self._auth_db_connector.set_manage_api_specific_audit_log_meta_items(managing_entity)
            ca_cert = CACertificate(context,
                                    ca_label,
                                    self._manage_api_config_section,
                                    self._settings,
                                    must_have_profile=True)
            try:
                crl_pem = ca_cert.generate_crl_pem()
            except InvalidSSLConfigError as exc:
                raise ManageAPIError(
                    "SSL config assigned to particular CA certificate (label {!r}) "
                    "is not valid: {}".format(ca_label, exc.actual_reason))
            return crl_pem


class _BaseCertFile(object):

    """
    Base class for classes representing certificate PEM files
    as parsed objects.

    Args:
        `cert_pem` (str):
            A certificate PEM file to be parsed.
        `helper_id` (None or str; default: None):
            Optionally passed value, which may be used to help
            debug problems with parsing of certificate. It should
            be characteristic for the parsed certificate, so it
            can be used within messages for exceptions to specify,
            which certificate caused problems.
    """

    cert_pem_format = FORMAT_PEM

    def __init__(self, cert_pem, helper_id=None):
        # a keyword `helper_id` can be provided to help debug,
        # which certificate's PEM string is invalid
        self._helper_id = helper_id
        self.parsed_cert_file = self._load_pem_string(cert_pem)
        self.subject = get_subject_as_x509_name_obj(self.parsed_cert_file)

    def get_serial_number(self):
        try:
            return get_cert_serial_number_as_hex(
                self.parsed_cert_file,
                CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM)
        except UnexpectedCertificateDataError as exc:
            raise ManageAPIError(
                'Problem with the certificate subject serial number: {}'.format(exc))

    def get_subject_dict(self):
        raise TypeError('Cannot call abstract method')

    def _load_pem_string(self, cert_str):
        """
        Do what n6corelib.x509_helpers.load_cert_string() does but raise
        ManageAPIError on failure.
        """
        try:
            return load_cert_string(cert_str, self.cert_pem_format)
        except Exception as exc:
            if self._helper_id:
                raise ManageAPIError('Not a valid certificate PEM string ({}) '
                                     'for: {}'.format(exc, self._helper_id))
            raise ManageAPIError('Not a valid certificate PEM string ({})'.format(exc))

    def get_valid_from(self):
        return get_cert_not_before(self.parsed_cert_file)

    def get_expires_on(self):
        return get_cert_not_after(self.parsed_cert_file)

    def get_subject_key_identifier(self):
        return get_cert_subject_key_identifier(self.parsed_cert_file)

    def get_authority_key_identifier(self):
        return get_cert_authority_key_identifier(self.parsed_cert_file)


class CACertFile(_BaseCertFile):

    """Class used to wrap a parsed PEM file of a CA certificate."""

    def __init__(self, ca_cert_pem, helper_id=None):
        super(CACertFile, self).__init__(ca_cert_pem, helper_id)
        if not is_ca_cert(self.parsed_cert_file):
            raise TypeError("The {!r} class has to be used for CA "
                            "certificates only".format(self.__class__.__name__))

    def get_subject_dict(self):
        raise NotImplementedError("Getting of certficate's subject dict is not implemented "
                                  "yet for CA certificates")


class ManagingEntityCertFile(_BaseCertFile):

    """
    Class used to wrap a parsed PEM file of a managing entity's
    certificate, extract and store some data about the certificate.
    """

    def __init__(self, cert_pem, helper_id='Managing entity\'s certificate'):
        super(ManagingEntityCertFile, self).__init__(cert_pem, helper_id)
        if is_ca_cert(self.parsed_cert_file):
            raise TypeError("The {!r} class has to be used for regular (not CA) "
                            "certificates only".format(self.__class__.__name__))
        self.serial_number = self.get_serial_number()
        self.subject_dict = self.get_subject_dict()

    def get_subject_dict(self):
        try:
            return get_cert_subject_dict(self.parsed_cert_file, include_ou=True)
        except UnexpectedCertificateDataError as exc:
            raise AccessForbiddenError("Access forbidden for the entity using "
                                       "certificate with subject '{}', which fails to meet "
                                       "the requirements: {}".format(self.subject, ascii_str(exc)))


class CertFile(_BaseCertFile):

    """
    Class used to wrap a parsed PEM file of a regular certificate,
    to extract and store extra data about the certificate.

    This class requires an instance of the certificate's issuer CA
    certificate representation class (`CACertificate` class) as a `ca`
    keyword argument, in order to verify the certificate.
    """

    def __init__(self, cert_pem, ca, helper_id=None):
        super(CertFile, self).__init__(cert_pem, helper_id=helper_id)
        if is_ca_cert(self.parsed_cert_file):
            raise TypeError("The {!r} class has to be used for regular (not CA) "
                            "certificates only".format(self.__class__.__name__))
        ca_cert_pem = ca.certificate
        self._ca_profile = ca.profile
        self._ca_file_obj = CACertFile(ca_cert_pem, helper_id='CA: {!r}'.format(ca.ca_label))
        if not verify_cert(self.parsed_cert_file, self._ca_file_obj.parsed_cert_file):
            raise ManageAPIError(
                    'Verification of certificate of {} failed'
                    .format(self.subject))
        self.is_client_cert = is_client_cert(self.parsed_cert_file)
        self.is_server_cert = is_server_cert(self.parsed_cert_file)
        self.serial_number = self.get_serial_number()
        self.subject_dict = self.get_subject_dict()
        self.valid_from = self.get_valid_from()
        self.expires_on = self.get_expires_on()

    def get_subject_dict(self):
        try:
            return get_cert_subject_dict(self.parsed_cert_file,
                                         include_ou=(self._ca_profile == SERVICE_CA_PROFILE_NAME))
        except UnexpectedCertificateDataError as exc:
            raise ManageAPIError("Certificate's subject ('{}') does not meet "
                                 "the requirements: {}".format(self.subject, ascii_str(exc)))


class _AuthDBInterfaceMixin(object):

    """
    A simple mixin providing references to database models
    and exceptions classes as its attributes.

    Its purpose is to hide implementation details of the
    database interface from Manage API classes. If the
    implementation changes, references to classes may change,
    but it will not make a difference for classes inheriting
    from the mixin - `_AuthDBInterfaceMixin` attribute names
    will stay the same.
    """

    cert_db_model = Cert
    ca_db_model = CACert
    user_db_model = User
    component_db_model = Component
    org_db_model = Org
    system_group_db_model = SystemGroup
    not_found_exception = NoResultFound


class ManagingEntity(_AuthDBInterfaceMixin):

    """
    The class represents an entity using the Manage API
    - it may be a user or a component.

    If the entity does not have permissions to use Manage API,
    the `AccessForbiddenError` will be raised.

    Args:
        `connection_context` (ConnectionContext):
            Instance of a class providing attributes and methods
            necessary for database connection and manipulation.
            See `ManageAPIAuthDBConnector` and `ConnectionContext`
            (a class withing `ManageAPIAuthDBConnector`) docstrings
            for more details.
        `internal_o_regex` (re pattern object):
            A compiled regex pattern object, created to determine,
            if certificate's "O" value matches the pattern for
            an "internal" organization - an organization within
            which its admin users have permission to use Manage API.
    """

    def __init__(self, connection_context, internal_o_regex):
        self._connection_context = connection_context
        self._internal_o_regex = internal_o_regex
        cert_path = connection_context.cert_path
        with open(cert_path, 'rb') as cert_str:
            cert_pem = cert_str.read()
        cert_file_obj = ManagingEntityCertFile(cert_pem)
        cert_subject_dict = cert_file_obj.subject_dict
        cert_serial_nr = cert_file_obj.serial_number
        self._login = _adjust_if_is_legacy_user_login(cert_subject_dict['cn'])
        self._entity_type = self._get_entity_type(cert_subject_dict)
        self._verify_is_o_internal(cert_subject_dict)
        self._user_db_obj = None
        self._component_db_obj = None
        assert self._entity_type in ('user', 'component')
        if self._entity_type == 'user':
            self._user_db_obj = self._get_db_obj(self.user_db_model)
            self._verify_user_not_blocked(self._user_db_obj)
            self._verify_owned_cert(cert_serial_nr, self._user_db_obj, 'owner')
            self._verify_admins_system_group(self._user_db_obj)
        else:
            self._component_db_obj = self._get_db_obj(self.component_db_model)
            self._verify_owned_cert(cert_serial_nr, self._component_db_obj, 'owner_component')

    @staticmethod
    def _get_entity_type(cert_subject_dict):
        ou_value = cert_subject_dict.get('ou')
        if ou_value == ADMIN_OU:
            return 'user'
        elif ou_value == COMPONENT_OU:
            return 'component'
        else:
            raise AccessForbiddenError("Access forbidden for the entity using certificate "
                                       "with unrecognized 'OU': {!r}".format(ou_value))

    def _verify_is_o_internal(self, cert_subject_dict):
        assert 'o' in cert_subject_dict
        o_value = cert_subject_dict['o']
        if self._internal_o_regex.match(o_value) is None:
            raise AccessForbiddenError("Access forbidden for the entity using certificate "
                                       "with 'O' value: {!r}, which does not match the pattern "
                                       "for internal organization".format(o_value))

    def _get_db_obj(self, db_model):
        try:
            return db_model.from_db(self._connection_context, 'login', self.login)
        except self.not_found_exception:
            raise AccessForbiddenError("Access forbidden: managing {} {!r} was not found in "
                                       "Auth DB".format(self._entity_type, self.login))

    def _verify_user_not_blocked(self, user_db_obj):
        if user_db_obj.is_blocked:
            raise AccessForbiddenError("Access forbidden: managing user {!r} "
                                       "is blocked".format(self.login))

    def _verify_owned_cert(self, cert_serial_nr, owner_db_obj, relation_name):
        try:
            cert_db_obj = self.cert_db_model.from_db(self._connection_context,
                                                     'serial_hex',
                                                     cert_serial_nr)
        except self.not_found_exception:
            raise AccessForbiddenError("Access forbidden: managing entity's "
                                       "certificate (serial number: {!r}) was not "
                                       "found in the AuthDB".format(cert_serial_nr))
        cert_owner = getattr(cert_db_obj, relation_name)
        if cert_owner is not owner_db_obj:
            raise AccessForbiddenError("Access forbidden: managing entity is not "
                                       "the owner of used certificate (serial "
                                       "number: {!r})".format(cert_serial_nr))
        # assuming that certificate is revoked, if any field
        # associated with revocation is filled
        if cert_db_obj.is_revoked:
            raise AccessForbiddenError("Access forbidden: managing entity's certificate "
                                       "(serial number: {!r}) is revoked".format(cert_serial_nr))

    def _verify_admins_system_group(self, user_db_obj):
        try:
            admins_system_group = self.system_group_db_model.from_db(self._connection_context,
                                                                     'name',
                                                                     ADMINS_SYSTEM_GROUP_NAME)
        except self.not_found_exception:
            raise ManageAPIError("The {!r} system group was not found "
                                 "in Auth DB".format(ADMINS_SYSTEM_GROUP_NAME))
        # check if the entity is in admins system group
        assert self._entity_type == 'user', "Only users may belong to system groups"
        if not admins_system_group.is_in_relation_with(user_db_obj, 'users'):
            raise AccessForbiddenError("Access forbidden: managing user {!r} does not belong "
                                       "to {!r} system group".format(self.login,
                                                                     ADMINS_SYSTEM_GROUP_NAME))

    @property
    def login(self):
        return self._login

    @property
    def entity_type(self):
        return self._entity_type

    @property
    def database_login(self):
        try:
            return self._connection_context.database_login
        except AttributeError:
            # depending on database interface, there may not be such
            # thing as separate database user login
            return None

    @property
    def user_db_obj(self):
        return self._user_db_obj

    @property
    def component_db_obj(self):
        return self._component_db_obj


class CACertificate(ConfigMixin, _AuthDBInterfaceMixin):

    """
    The class represents CA certificates stored in Auth DB.

    Args:
        `connection_context` (ConnectionContext):
            Instance of a class providing attributes and methods
            necessary for database connection and manipulation.
            See `ManageAPIAuthDBConnector` and `ConnectionContext`
            (a class withing `ManageAPIAuthDBConnector`) docstrings
            for more details.
        `ca_label_or_db_obj` (str or object representing db record):
            Either a string being the label of the represented CA
            certificate or an ORM model instance that represents the CA
            certificate.
        `manage_api_config_section` (str):
            The name of the config section, which specifies paths to CA
            keys PEM files.
        `settings` (None or dict; default: None):
            A Pyramid-style settings dict.
    """

    ca_key_prefix = 'ca_key_'

    config_spec_pattern = '''
        [{manage_api_config_section}]
        {ca_key_config_option_name}  ; <- we are interested in a particular CA key
        ...                          ; <- but probably there are also keys specified for other CAs
    '''

    def __init__(self, connection_context, ca_label_or_db_obj, manage_api_config_section,
                 settings=None,
                 must_have_profile=False):
        self._connection_context = connection_context
        self._settings = settings
        self._manage_api_config_section = manage_api_config_section
        self.ca_db_obj = self._get_ca_db_obj(ca_label_or_db_obj)
        self.ca_file_obj = CACertFile(self.certificate,
                                      helper_id='CA: {!r}'.format(self.ca_label))
        if must_have_profile and self.profile is None:
            raise ValueError(
                '`must_have_profile` set to True but CA {!r} '
                'does not have a profile'.format(self.ca_label))

    def _get_ca_db_obj(self, ca_label_or_db_obj):
        if isinstance(ca_label_or_db_obj, self.ca_db_model):
            return ca_label_or_db_obj
        elif isinstance(ca_label_or_db_obj, basestring):
            ca_label = ca_label_or_db_obj
            try:
                return self.ca_db_model.from_db(self._connection_context, 'ca_label', ca_label)
            except self.not_found_exception:
                raise ManageAPIError('Could not find CA certificate with '
                                     'label: {!r}.'.format(ca_label))
        else:
            raise TypeError('unexpected class {0.__class__!r} of '
                            'the `ca_label_or_db_obj` argument '
                            '({0!r})'.format(ca_label_or_db_obj))

    @classmethod
    def iter_all(cls, connection_context, manage_api_config_section,
                 settings=None,
                 must_have_profile=False):
        for ca_db_obj in list(cls.ca_db_model.get_all_records(connection_context)):
            yield cls(connection_context,
                      ca_db_obj,
                      manage_api_config_section,
                      settings,
                      must_have_profile)

    def get_env_configuration(self):
        ca_key_path = self._get_ca_key_path(
            self._manage_api_config_section,
            self._settings)
        return get_ca_env_configuration(self, ca_key_path)

    def generate_crl_pem(self):
        return generate_crl_pem(self.get_env_configuration())

    def iter_all_certificates(self):
        for cert_db_obj in self.ca_db_obj.certs:
            yield CertificateFromDatabase(self._connection_context, self, cert_db_obj)

    def _ca_label_to_ca_key_config_option_name(self):
        return self.ca_key_prefix + self.ca_label.replace('-', '_')

    def _get_ca_key_path(self, manage_api_config_section, settings):
        try:
            ca_key_config_option_name = self._ca_label_to_ca_key_config_option_name()
            config_section_opts = self.get_config_section(
                settings,
                manage_api_config_section=manage_api_config_section,
                ca_key_config_option_name=ca_key_config_option_name)
            return config_section_opts[ca_key_config_option_name]
        except ConfigError as exc:
            raise ManageAPIError(
                'Problem with getting the CA key path '
                'from the config: {}'.format(ascii_str(exc)))

    @property
    def ca_label(self):
        return self.ca_db_obj.ca_label

    @property
    def certificate(self):
        return self.ca_db_obj.certificate

    @property
    def profile(self):
        return self.ca_db_obj.profile

    @property
    def subject_key_identifier(self):
        return self.ca_file_obj.get_subject_key_identifier()

    @property
    def authority_key_identifier(self):
        return self.ca_file_obj.get_authority_key_identifier()

    @property
    def ssl_config(self):
        return self.ca_db_obj.ssl_config


class _CertificateBase(_AuthDBInterfaceMixin):

    """
    Base class for classes representing certificates stored
    in Auth DB or the ones soon-to-be saved in Auth DB.

    Its properties are decorated by `database_property`.
    It means that when they are accessed, they are
    at first looked for in an object representing the record
    in Auth DB.
    If the object is not created yet (the certificate has
    not been added or committed to be added to database yet),
    the property behaves according to decorated method's
    implementation, usually looking up attributes created
    within constructor.
    """

    database_property = db_property_factory('cert_db_obj')

    def __init__(self, connection_context, ca):
        self.ca = ca
        self._connection_context = connection_context
        self._ca_profile = self.ca.profile
        self.cert_db_obj = None
        self._cert_pem = None
        self._csr_pem = None
        self._kind_of_owner = None
        self._owner_login = None
        self._owner_component_login = None
        self._owner_instance = None
        self._created_on = None
        self._created_by_login = None
        self._created_by_component_login = None
        self._creator_hostname = None
        self._database_login = None

    def set_revocation_fields(self, revoked_on, revoked_by_user, revoked_by_component,
                              revocation_comment):
        assert revoked_on is not None, (
            '`revoked_on` should be specified (got None)')
        assert revocation_comment is not None, (
            '`revocation_comment` should be specified (got None)')
        assert ((revoked_by_user is not None and revoked_by_component is None) or
                (revoked_by_user is None and revoked_by_component is not None)), (
            'exactly one of {{`revoked_by_user`, `revoked_by_component`}} should be '
            'specified (got: {!r} and {!r})'.format(revoked_by_user,
                                                    revoked_by_component))
        self.cert_db_obj.revoked_on = revoked_on
        self.cert_db_obj.revoked_by = revoked_by_user
        self.cert_db_obj.revoked_by_component = revoked_by_component
        self.cert_db_obj.revocation_comment = revocation_comment

    def _set_not_stored_properties(self):
        self.cert_file = self._create_cert_file()
        self.cert_file_obj = self.cert_file.parsed_cert_file
        self.subject = self.cert_file.subject
        self._subject_dict = self.cert_file.subject_dict
        self.slug = self._get_slug()

    def _create_cert_file(self):
        if not self.certificate:
            raise AttributeError("Cannot create a certificate file representation object: "
                                 "a certificate PEM file was not created nor retrieved from "
                                 "database")
        return CertFile(self.certificate, self.ca, helper_id=self._get_helper_id())

    def _get_helper_id(self):
        """
        Get identification data about certificate with its serial
        number, if it is available (depends, whether the certificate
        is just being added to database, or it has been fetched
        from database).

        Returns:
            A description identifying the certificate, as a string.
        """
        try:
            return ('Certificate (serial number: {!r}) '
                    'issued by CA: {!r}'.format(self.serial_hex, self.ca.ca_label))
        except AttributeError:
            return 'Certificate issued by CA: {!r}'.format(self.ca.ca_label)

    @staticmethod
    def _normalize_serial_number(serial_number):
        return normalize_hex_serial_number(serial_number, CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM)

    @staticmethod
    def _validate_serial_number(serial_number):
        if not is_cert_serial_number_valid(serial_number):
            raise ManageAPIError(
                'Certificate serial number {!r} is not valid.'.format(serial_number))

    @staticmethod
    def _compare_ca_certs(created_ca_obj, ca_label_from_db):
        if created_ca_obj.ca_label != ca_label_from_db:
            raise ManageAPIError("CA certificate's label passed as argument ({!r}) does not "
                                 "match a label of CA associated with certificate fetched "
                                 "from database ({!r})".format(ca_label_from_db,
                                                               created_ca_obj.ca_label))

    def _get_slug(self):
        """A filename-and-URL-friendly text label of the certificate"""
        parts = [self.ca_cert_label, self.serial_hex, self._subject_dict['cn']]
        return str('-'.join(parts)).translate(SLUG_TRANS)

    @database_property
    def serial_hex(self):
        return self.cert_file.serial_number

    @database_property
    def ca_cert_label(self):
        return self.ca.ca_label

    @database_property
    def certificate(self):
        return self._cert_pem

    @database_property
    def csr(self):
        return self._csr_pem

    @database_property
    def kind_of_owner(self):
        return self._kind_of_owner

    @database_property
    def owner_login(self):
        return self._owner_login

    @database_property
    def owner_component_login(self):
        return self._owner_component_login

    @database_property
    def is_client_cert(self):
        return self.cert_file.is_client_cert

    @database_property
    def is_server_cert(self):
        return self.cert_file.is_server_cert

    @database_property
    def created_on(self):
        return self._created_on

    @database_property
    def created_by_login(self):
        return self._created_by_login

    @database_property
    def created_by_component_login(self):
        return self._created_by_component_login

    @database_property
    def creator_details(self):
        details = {
            'hostname': self._creator_hostname,
        }
        if self._database_login:
            details['database_login'] = self._database_login
        return details

    @database_property
    def valid_from(self):
        return self.cert_file.valid_from

    @database_property
    def expires_on(self):
        return self.cert_file.expires_on

    @database_property
    def revoked_on(self):
        return None

    @database_property
    def revoked_by_login(self):
        return None

    @database_property
    def revoked_by_component_login(self):
        return None

    @database_property
    def revocation_comment(self):
        return None

    @database_property
    def is_revoked(self):
        return False


class CertificateCreated(ConfigMixin, _CertificateBase):

    """
    The class represents certificates, which are going to be saved
    to Auth DB.

    Args:
        `connection_context` (ConnectionContext):
            An instance of a class defining a context for database
            connection. See `ManageAPIAuthDBConnector` and `ConnectionContext`
            (a class within `ManageAPIAuthDBConnector`) docstrings
            for more details.
        `ca_repr_obj` (CACertificate):
            An instance of `CACertificate` class, created for issuer
            CA certificate.
        `created_on` (str or datetime.datetime):
            Certificate creation datetime.
        `creator_login` (str):
            Login of the managing entity, taken from its certificate.
        `creator_type` (str):
            Type of the managing entity, whether it is user
            or component.
        `creator_hostname` (str):
            Hostname of the managing entity.
        `database_login` (None or str):
            Login of the user that is being used to connect to Auth DB,
            if available, None otherwise.
        `internal_o_regex` (re pattern object):
            A compiled regex pattern object, created to determine,
            if certificate's "O" value matches the pattern for
            an "internal" organization - an organization within
            which its admin users have permission to use Manage API.
        `server_component_ou_regex` (re pattern object):
            A compiled regex pattern object, created to determine,
            if certificate's "OU" value matches the pattern for
            a "server-component" kind of owner (but only if owner's
            certificate is signed by a service CA).
        `cert_pem` (None or str):
            A certificate PEM file as a string. If not None, then
            it is an instruction for class constructor to only add
            the existing certificate's representation to Auth DB,
            not to create a new certificate.
        `csr_pem` (None or str):
            A Certificate Signing Request PEM file as a string.
            If not None, then it instructs class constructor
            to create and sign a new certificate with this CSR.
        `adding_owner` (bool; default: False):
            If True, a certificate owner should be added to Auth DB
            (it will succeed only if the owner does not exist
            already in the database).
        `server_component_login` (None or str; default: None):
            Must be specified (as a non-None value) if the
            certificate that is being created belongs to an n6
            public server (the certificate's `kind` is
            "server-component"); otherwise it must be None.
        `_explicit_owner_login` (None or str; default: None):
            For internal use only: it has the same role as
            `server_component_login`, although it does not raise
            an exception if used for a not "server-component"
            kind of certificate.

    *Important*:
        Notice that `cert_pem` and `csr_pem` args exclude each
        other, so only one of them can be passed as a non-None value.
        Otherwise a TypeError will be raised.
    """

    new_cert_init_kwargs = [
        'serial_hex',
        'certificate',
        'csr',
        'is_client_cert',
        'is_server_cert',
        'created_on',
        'created_by_login',
        'created_by_component_login',
        'creator_details',
        'valid_from',
        'expires_on',
        'ca_cert_label',
        'owner_login',
        'owner_component_login',
    ]

    def __init__(self, connection_context, ca_repr_obj, created_on,
                 creator_login,
                 creator_type,
                 creator_hostname,
                 database_login,
                 internal_o_regex,
                 server_component_ou_regex,
                 cert_pem=None,
                 csr_pem=None,
                 adding_owner=False,
                 server_component_login=None,
                 # the following parameter is for internal use only (it
                 # can be specified for "server-component" certificates
                 # instead of the above `server_component_login`)
                 _explicit_owner_login=None):
        if cert_pem is not None and csr_pem is not None:
            raise TypeError("{!r} class constructor does not accept both "
                            "cert PEM file and CSR PEM file "
                            "simultaneously as its arguments".format(self.__class__.__name__))
        super(CertificateCreated, self).__init__(connection_context, ca_repr_obj)
        self._created_on = created_on
        self._set_created_by_fields(creator_login, creator_type)
        self._creator_hostname = creator_hostname
        self._database_login = database_login
        self._internal_o_regex = internal_o_regex
        self._server_component_ou_regex = server_component_ou_regex
        self._server_component_login = server_component_login
        self._explicit_owner_login = _explicit_owner_login
        if cert_pem is None:
            if csr_pem is None:
                raise ManageAPIError('No CSR PEM file to create a certificate file')
            # PEM file is not passed, assuming it has to be generated
            self._csr_pem = csr_pem
            self._cert_pem = self._make_new_pem()
        else:
            self._cert_pem = cert_pem
        self._set_not_stored_properties()
        self._kind_of_owner = self._get_kind_of_owner()
        self._owner_instance = None
        self._owner_login = None
        self._owner_component_login = None
        self._set_ownership(adding_owner)
        self.cert_db_obj = self.create_new_cert_db_obj()

    def create_new_cert_db_obj(self):
        init_kwargs = {key: getattr(self, key) for key in self.new_cert_init_kwargs}
        return self.cert_db_model.create_new(self._connection_context, **init_kwargs)

    def add_new_cert_db_obj_to_db(self):
        self.cert_db_obj.add_self_to_db(self._connection_context)

    def _set_created_by_fields(self, creator_login, creator_type):
        assert creator_type in ('user', 'component')
        if creator_type == 'user':
            self._created_by_login = creator_login
        else:
            self._created_by_component_login = creator_login

    def _make_new_pem(self):
        ca_env_config = self.ca.get_env_configuration()
        try:
            return generate_certificate_pem(ca_env_config,
                                            self._csr_pem,
                                            self._make_serial_number(self._csr_pem),
                                            self._server_component_login)
        except InvalidSSLConfigError as exc:
            raise ManageAPIError("SSL config assigned to particular CA certificate (label {!r}) "
                                 "is not valid: {}".format(self.ca_cert_label, exc.actual_reason))

    @staticmethod
    def _make_serial_number(arbitrary_input_str):
        serial_number = make_hex_id(
            length=CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM,
            additional_salt=arbitrary_input_str)
        assert is_cert_serial_number_valid(serial_number)
        return serial_number

    def _get_kind_of_owner(self):
        if self._ca_profile == CLIENT_CA_PROFILE_NAME:
            assert self._subject_dict.viewkeys() == {'cn', 'o'}
            return 'app-user'
        if self._ca_profile == SERVICE_CA_PROFILE_NAME:
            assert self._subject_dict.viewkeys() == {'cn', 'o', 'ou'}
            cert_ou = self._subject_dict['ou']
            server_component_ou_match = self._server_component_ou_regex.match(cert_ou)
            if server_component_ou_match is not None:
                return 'server-component'
            elif cert_ou == ADMIN_OU:
                return 'admin'
            elif cert_ou == COMPONENT_OU:
                return 'component'
            else:
                raise ManageAPIError("Unrecognized 'ou' part of certificate's "
                                     "subject: {!r}.".format(cert_ou))
        raise ManageAPIError("Invalid profile of CA certificate.")

    def _get_login(self):
        if self.kind_of_owner == 'server-component':
            if self._server_component_login is not None:
                return self._server_component_login
            elif self._explicit_owner_login:
                return self._explicit_owner_login
            raise ManageAPIError("A 'server_component_login' argument must be specified "
                                 "for a 'server-component' kind of certificate owner.")
        else:
            # in case of every other kind of certificate owner than
            # "server-component", a `server_component_login` argument
            # must not be specified, an `_explicit_owner_login`
            # is ignored
            if self._server_component_login is not None:
                raise ManageAPIError("A `server_component_login` argument is applicable "
                                     "only for a `server-component` kind of certificate owner.")
            return self._subject_dict['cn']

    def _get_validated_o(self):
        o = self._subject_dict['o']
        if self.kind_of_owner in ('admin', 'component'):
            o_match = self._internal_o_regex.match(o)
            if o_match is not None:
                return o_match.group(0)
            else:
                raise ManageAPIError("Illegal value of `o` for {}: {!r} "
                                     "(it should match a regex "
                                     "pattern: {!r}).".format(self.kind_of_owner,
                                                              o,
                                                              self._internal_o_regex.pattern))
        return o

    def _set_ownership(self, adding_owner):
        login = self._get_login()
        org_id = self._get_validated_o()
        if self.kind_of_owner in USER_KINDS_OF_OWNER:
            if adding_owner:
                new_user = self._add_user_to_db(login)
                self._add_user_to_his_organization(org_id, new_user)
                if self.kind_of_owner == 'app-user':
                    assert self._ca_profile == CLIENT_CA_PROFILE_NAME
                else:
                    assert self.kind_of_owner == 'admin'
                    assert self._ca_profile == SERVICE_CA_PROFILE_NAME
                    self._add_user_to_admins_system_group(new_user)
            else:
                try:
                    self._owner_instance = self.user_db_model.from_db(self._connection_context,
                                                                      'login',
                                                                      login)
                except self.not_found_exception:
                    raise ManageAPIError('User with login {!r} was not found in '
                                         'the database.'.format(login))
                self._check_if_user_in_his_org(org_id, self._owner_instance)
                if self.kind_of_owner == 'admin':
                    self._check_if_user_in_admins_system_group(self._owner_instance)
            # connect 'user' and 'cert' table
            self._owner_login = login
        else:
            assert self.kind_of_owner in COMPONENT_KINDS_OF_OWNER
            if adding_owner:
                _ = self._add_component_to_db(login)
            else:
                try:
                    self._owner_instance = self.component_db_model.from_db(
                        self._connection_context, 'login', login)
                except self.not_found_exception:
                    raise ManageAPIError('Component with login {!r} was not found in '
                                         'the database.'.format(login))
            # connect 'component' and 'cert' table
            self._owner_component_login = login

    def _add_user_to_db(self, login):
        return self.user_db_model.create_new(self._connection_context, login=login)

    def _get_org(self, org_id, login):
        try:
            org = self.org_db_model.from_db(self._connection_context, 'org_id', org_id)
        except self.not_found_exception:
            raise ManageAPIError("Cannot find organization with ID: {!r} in database, "
                                 "to which user {!r} belongs to.".format(org_id, login))
        return org

    def _add_user_to_his_organization(self, org_id, user):
        org = self._get_org(org_id, user.login)
        org.users.append(user)

    def _check_if_user_in_his_org(self, org_id, user):
        org = self._get_org(org_id, user.login)
        if not org.is_in_relation_with(user, 'users'):
            raise ManageAPIError("User {!r} does not belong to his "
                                 "organization {!r}".format(user.login, org_id))

    def _add_component_to_db(self, login):
        return self.component_db_model.create_new(self._connection_context, login=login)

    def _fetch_admins_system_group(self):
        try:
            return self.system_group_db_model.from_db(self._connection_context, 'name',
                                                      ADMINS_SYSTEM_GROUP_NAME)
        except self.not_found_exception:
            raise ManageAPIError("Cannot fetch the 'admins' system group from database.")

    def _add_user_to_admins_system_group(self, user):
        admins_system_group = self._fetch_admins_system_group()
        admins_system_group.users.append(user)

    def _check_if_user_in_admins_system_group(self, user):
        admins_system_group = self._fetch_admins_system_group()
        if not admins_system_group.is_in_relation_with(user, 'users'):
            raise ManageAPIError("A user with login: {!r} does not belong to admins' system "
                                 "group".format(user.login))


class CertificateFromDatabase(_CertificateBase):

    """
    The class represents certificates fetched from Auth DB,
    passed as `cert_db_obj` constructor argument.

    Args:
        `connection_context` (ConnectionContext):
            See `ManageAPIAuthDBConnector` and `ConnectionContext`
            (a class withing `ManageAPIAuthDBConnector`) docstrings
            for description.
        `ca_repr_obj` (CACertificate):
            An instance of `CACertificate` class, created for issuer
            CA certificate.
        `cert_db_obj` (n6lib.auth_db.models.Cert):
            An instance of database model class for the certificate.
    """

    def __init__(self, connection_context, ca_repr_obj, cert_db_obj):
        super(CertificateFromDatabase, self).__init__(connection_context, ca_repr_obj)
        self.cert_db_obj = cert_db_obj
        self._compare_ca_certs(ca_repr_obj, self.ca_cert_label)
        self._set_not_stored_properties()

    @classmethod
    def from_serial_number(cls, connection_context, ca_repr_obj, serial_number):
        """
        An alternative class constructor method:
        get a `CertificateFromDatabase` instance by fetching
        a certificate representation object from database first.

        Args:
            `connection_context` (ConnectionContext):
                See `ManageAPIAuthDBConnector` and `ConnectionContext`
                (a class withing `ManageAPIAuthDBConnector`) docstrings
                for description.
            `ca_repr_obj` (CACertificate):
                An instance of `CACertificate` class, created for
                the issuer CA certificate.
            `serial_number` (str):
                Serial number of a sought certificate.
        """
        normalized_serial_number = cls._normalize_serial_number(serial_number)
        cls._validate_serial_number(normalized_serial_number)
        cert_db_obj = cls._get_cert_from_db(connection_context, serial_number)
        return cls(connection_context, ca_repr_obj, cert_db_obj)

    @classmethod
    def _get_cert_from_db(cls, connection_context, serial_number):
        try:
            return cls.cert_db_model.from_db(connection_context,
                                             'serial_hex',
                                             serial_number)
        except cls.not_found_exception:
            raise ManageAPIError('Could not find certificate with '
                                 'serial number: {!r}.'.format(serial_number))


class CSRFile(object):

    """
    The class represents Certificate Signing Requests` parsed
    PEM files.

    Args:
        `csr_pem` (str):
            A CSR PEM file as a string.
    """

    def __init__(self, csr_pem):
        self.parsed_csr = self._load_csr(csr_pem)
        self.csr_pem = csr_pem
        self.subject = get_subject_as_x509_name_obj(self.parsed_csr)

    @staticmethod
    def _load_csr(csr_pem):
        try:
            return load_request_string(csr_pem)
        except Exception as exc:
            raise ManageAPIError('Not a valid CSR in the PEM format ({})'.format(exc))

    def verify_csr(self, cert_file):
        if not verify_request(self.parsed_csr, cert_file.parsed_cert_file):
            raise ManageAPIError(
                'CSR of {} does not match the certificate of {}'.format(self.subject,
                                                                        cert_file.subject))

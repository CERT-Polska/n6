# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

import copy
import datetime
import json
import mock
import re
import unittest
from collections import MutableSequence

from unittest_expander import (
    expand,
    foreach,
)

from n6lib.common_helpers import read_file
from n6corelib.manage_api._manage_api import (
    _AuthDBInterfaceMixin,
    AccessForbiddenError,
    CACertFile,
    CACertificate,
    CertFile,
    CertificateCreated,
    CertificateFromDatabase,
    CSRFile,
    ManageAPI,
    ManageAPIAuthDBConnector,
    ManagingEntityCertFile,
    ManageAPIError,
    ManagingEntity,
)
from n6corelib.pki_related_test_helpers import (
    _load_ca_cert_pem,
    _load_ca_key_pem,
    _load_ca_ssl_config_cnf,
    _load_ca_ssl_config_cnf_by_label_and_ca_label,
    _load_cert_pem,
    _load_csr_pem,
    _parse_crl_pem,
)
from n6lib.unit_test_helpers import DBConnectionPatchMixin
from n6sdk.exceptions import FieldValueError


SERIAL_NUMBER = '12345678abcdef012345'
CERT_DATETIMES_FORMAT = '%b %d %H:%M:%S %Y %Z'
CREATED_ON_DT = datetime.datetime(2018, 1, 1, 12)
CREATOR_HOSTNAME = 'example-host'
CREATOR_CN = 'admin@n6-test.com'
CREATOR_ORG_ID = 'n6-test.com'
CREATOR_DB_LOGIN = 'admin'
SERV_COMP_OU_PATTERN = r'\AInternal[ ]Unit\Z'
INTERNAL_O_PATTERN = r'\Aexample\.com\Z'
ONE_MINUTE_DELTA = datetime.timedelta(seconds=60)
NEW_CERT_VALIDITY_DELTA = datetime.timedelta(days=365)
ADMINS_SYSTEM_GROUP = 'admins'


class _WithMocksMixin(DBConnectionPatchMixin):

    CA_KEY_PATH_SENTINEL_STR = '<some ca_key_path from config>'
    config_patched = {
        'internal_o_regex_pattern': INTERNAL_O_PATTERN,
        'server_component_ou_regex_pattern': SERV_COMP_OU_PATTERN,
    }

    def make_patches(self, collection=None, session_state=None):
        """
        Extend default implementation by defaulting arguments
        to empty state and empty session if none were provided.
        """
        self.context_mock = None
        super(_WithMocksMixin, self).make_patches(
            collection if collection is not None else dict(),
            session_state if session_state is not None else dict())
        self.patch_db_connector(self.session_mock)
        self.get_config_mock = self.patch(
            'n6corelib.manage_api._manage_api.ManageAPI.get_config_section',
            return_value=self.config_patched)
        self.patch_cert_classes()

    @staticmethod
    def get_context_mock(session_mock):
        """
        Get the patched "context" object, which is normally returned
        by the database connector used within ManageAPI.

        The "context" object provides some essential attributes,
        like the current session object.
        """
        m = mock.MagicMock()
        m.db_session = session_mock
        return m

    def patch_db_connector(self, session_mock):
        self.context_mock = self.get_context_mock(self.session_mock)
        self.connector_mock = self.patch(
            'n6corelib.manage_api._manage_api.ManageAPI.auth_db_connector')
        self.connector_mock.return_value.__enter__.return_value = self.context_mock

    @staticmethod
    def patch_session_bind_attr(db_session, database_login):
        """
        Patch a session object mock's `bind` attribute, so a database
        user login value can be retrieved from the session mock.

        Args:
            `db_session` (mock.Mock):
                An object mocking an SQLAlchemy session object.
            `database_login` (str):
                A new user login value.
        """
        bind_mock = mock.Mock()
        db_session.bind = bind_mock
        bind_mock.url.username = database_login

    def patch_managing_entity(self, new_managing_entity=None, user_db_obj=None):
        self.managing_entity_mock = self.patch(
            'n6corelib.manage_api._manage_api.ManageAPI._verify_and_get_managing_entity')
        if new_managing_entity is None:
            self.managing_entity_mock.return_value = mock.MagicMock(hostname=CREATOR_HOSTNAME,
                                                                    cert_cn=CREATOR_CN,
                                                                    database_login=CREATOR_DB_LOGIN,
                                                                    entity_type='user')
        else:
            self.managing_entity_mock.return_value = new_managing_entity
        if user_db_obj is not None:
            self.managing_entity_mock.return_value.user_db_obj = user_db_obj
        self.managing_entity_mock.return_value.component_db_obj = None

    def patch_cert_classes(self):
        self.config_mapping = mock.MagicMock()
        self.ca_get_config_mock = self.patch(
                       'n6corelib.manage_api._manage_api.CACertificate.get_config_section',
                       return_value=self.config_mapping)
        self.config_mapping.__getitem__.return_value = self.CA_KEY_PATH_SENTINEL_STR
        # read CA key file from `ca_key` instance attribute, if file
        # name in config is set to the sentinel string (currently
        # it will be assured by the `config_mapping` __getitem__()
        # magic method's patch
        self.read_file_mock = self.patch(
                       'n6corelib.manage_api._ca_env.read_file', side_effect=lambda file, *a, **kw:
                       (self.ca_key if file == self.CA_KEY_PATH_SENTINEL_STR
                        else read_file(file, *a, **kw)))
        self.ca_key = '<to be set in test cases if needed>'
        self.make_serial_nr_mock = self.patch(
            'n6corelib.manage_api._manage_api.CertificateCreated._make_serial_number',
            return_value=SERIAL_NUMBER)

    def _get_cert_class_mock_helpers(self, cert_class):
        orig_init = cert_class.__init__
        cert_ref = []

        def new_init(self, *args, **kwargs):
            # clear the list with a reference to the current instance,
            # to make sure there is only one reference
            del cert_ref[:]
            cert_ref.append(self)
            orig_init(self, *args, **kwargs)

        return cert_ref, new_init

    def get_certificate_representation_class_inst_ref(self, manage_api_cert_class):
        """
        Get a reference to an instance of a class used to represent
        a certificate, created during a call to one of ManageAPI
        methods.

        Args:
            `manage_api_cert_class`:
                a reference to a class used within tested Manage API
                method to represent a certificate.

        Returns:
            A list, which will be appended with reference to
            certificate representation class instance.
        """
        if manage_api_cert_class == CertificateCreated:
            return self._get_certificate_created_class_inst_ref()
        elif manage_api_cert_class == CertificateFromDatabase:
            return self._get_certificate_from_database_class_inst_ref()
        else:
            self.fail("Unknown Manage API certificate class ({!r}) "
                      "to get a reference to".format(manage_api_cert_class))

    def _get_certificate_created_class_inst_ref(self):
        cert_ref, new_init = self._get_cert_class_mock_helpers(CertificateCreated)
        self.patch('n6corelib.manage_api._manage_api.CertificateCreated.__init__', new=new_init)
        return cert_ref

    def _get_certificate_from_database_class_inst_ref(self):
        cert_ref, new_init = self._get_cert_class_mock_helpers(CertificateFromDatabase)
        self.patch('n6corelib.manage_api._manage_api.CertificateFromDatabase.__init__', new=new_init)
        return cert_ref

    def load_ca_key(self, ca_label):
        self.ca_key = _load_ca_key_pem(ca_label=ca_label)


class _DBInterfaceMixin(_AuthDBInterfaceMixin):

    def load_ca(self, context, ca_label, profile):
        self.ca_pem = _load_ca_cert_pem(ca_label)
        self.ca_config = _load_ca_ssl_config_cnf(ca_label)
        self.ca_db_model.create_new(context, ca_label=ca_label, certificate=self.ca_pem,
                                    profile=profile, ssl_config=self.ca_config)

    def add_user(self, context, login, org=None, admins_group=False):
        new_user = self._add_owner(self.user_db_model, context, login, admins_group)
        if org:
            new_user.org = org
        return new_user

    def add_component(self, context, login):
        return self._add_owner(self.component_db_model, context, login, admins_group=False)

    def add_org(self, context, org_id):
        return self.org_db_model.create_new(context, org_id=org_id)

    def add_cert(self, context, **init_kwargs):
        return self.cert_db_model.create_new(context, **init_kwargs)

    def check_for_user(self, context, login):
        obj = self.user_db_model.from_db(context, 'login', login)
        self.assertTrue(obj)
        return obj

    def check_for_component(self, context, login):
        obj = self.component_db_model.from_db(context, 'login', login)
        self.assertTrue(obj)
        return obj

    def check_in_admins_group(self, context, obj_from_db):
        admins_group = self.system_group_db_model.from_db(context, 'name', ADMINS_SYSTEM_GROUP)
        self.assertTrue(obj_from_db.is_in_relation_with('system_groups', admins_group))

    def _add_owner(self, db_model, context, login, admins_group):
        new_owner = db_model.create_new(context, login=login)
        if admins_group:
            # check first if 'admins' system group exists
            try:
                admins_group = self.system_group_db_model.from_db(context,
                                                                  'name',
                                                                  ADMINS_SYSTEM_GROUP)
            except self.not_found_exception:
                admins_group = self.system_group_db_model.create_new(context,
                                                                     name=ADMINS_SYSTEM_GROUP)
            new_owner.system_groups.append(admins_group)
        return new_owner


class _BaseAPIActionTest(_WithMocksMixin, _DBInterfaceMixin):

    ca_label = NotImplemented
    ca_profile = NotImplemented

    expected_values = None

    def setUp(self):
        self.basic_api_action_specific_setup()

    def basic_api_action_specific_setup(self, manage_api_cert_class=CertificateCreated):
        self.make_patches()
        self._cert_inst_ref = self.get_certificate_representation_class_inst_ref(
            manage_api_cert_class)
        self.load_ca(self.context_mock, self.ca_label, self.ca_profile)
        self.load_ca_key(self.ca_label)
        # add managing entity's organization and user
        managing_user_org = self.add_org(self.context_mock, CREATOR_ORG_ID)
        managing_user = self.add_user(self.context_mock, CREATOR_CN, org=managing_user_org)
        self.patch_managing_entity(user_db_obj=managing_user)
        self.api = ManageAPI()

    def _get_validity_datetimes(self, cert_label):
        try:
            expected_dict = self.expected_values[cert_label]
        except (KeyError, TypeError):
            self.fail("No expected values found for certificate {!r}".format(cert_label))
        try:
            validity_vals = expected_dict['validity']
        except KeyError:
            self.fail("No expected 'validity' datetimes were found for "
                      "certificate {!r}".format(cert_label))
        return (datetime.datetime.strptime(x, CERT_DATETIMES_FORMAT) for x in validity_vals)

    def _make_assertions(self, serial_hex, cert_pem, csr_pem=None, result_slug=None,
                         created_on=None, created_by_login=None, creator_details=None):
        try:
            expected = self.expected_values[serial_hex]
        except KeyError:
            self.fail("Could not find expected values for "
                      "certificate with serial number: {!r}".format(serial_hex))
        orig_serial_hex = serial_hex
        if 'serial_hex' in expected:
            serial_hex = self.expected_values[serial_hex]['serial_hex']
        try:
            cert = self.cert_db_model.from_db(self.context_mock, 'serial_hex', serial_hex)
        except self.not_found_exception:
            self.fail('Certificate with serial number: {!r} was not '
                      'added to database'.format(serial_hex))
        self.assertEqual(cert.serial_hex, serial_hex)
        self.assertEqual(expected.get('owner_login'), cert.owner_login)
        self.assertEqual(expected.get('owner_component_login'),
                         cert.owner_component_login)
        if not created_on:
            # with the kwarg empty/None, assume the certificate was
            # just created, so creation datetime is almost now
            created_on = datetime.datetime.utcnow()
            self.assertAlmostEqual(cert.created_on, created_on, delta=ONE_MINUTE_DELTA)
            days_valid = expected['days_valid']
            self.assertEqual(days_valid, cert.expires_on - cert.valid_from)
        else:
            self.assertEqual(cert.created_on, created_on)
            valid_from, expires_on = self._get_validity_datetimes(orig_serial_hex)
            self.assertEqual(cert.valid_from, valid_from)
            self.assertEqual(cert.expires_on, expires_on)
        self.assertEqual(cert.certificate, cert_pem)
        self.assertEqual(cert.csr, csr_pem)
        if self.ca_profile == 'client':
            self.assertTrue(cert.is_client_cert)
        elif self.ca_profile == 'server':
            self.assertTrue(cert.is_server_cert)
        if created_by_login is None:
            created_by_login = CREATOR_CN
        self.assertEqual(created_by_login, cert.created_by_login)
        if creator_details is None:
            creator_details = {
                'hostname': CREATOR_HOSTNAME,
                'database_login': CREATOR_DB_LOGIN,
            }
        self.assertDictEqual(creator_details, json.loads(cert.creator_details))
        revoked_by_login = expected.get('revoked_by_login')
        revoked_by_component_login = expected.get('revoked_by_component_login')
        revocation_comment = expected.get('revocation_comment')
        self.assertEqual(revoked_by_login, cert.revoked_by_login)
        self.assertEqual(revoked_by_component_login, cert.revoked_by_component_login)
        self.assertEqual(revocation_comment, cert.revocation_comment)
        try:
            cert_ref = self._cert_inst_ref[0]
        except IndexError:
            self.fail('Bug in test: could not get a reference to certificate class')
        assert len(self._cert_inst_ref) == 1, 'Bug in test: too many references'
        if result_slug is not None:
            self.assertEqual(expected['slug'], result_slug)
        self.assertEqual(expected['slug'], cert_ref.slug)
        self.assertEqual(expected['subject'], cert_ref.subject.as_text())


class _AddCertTestHelperMixin(object):

    def _test(self, serial_hex, do_add_user, server_component_login=None):
        cert_pem = _load_cert_pem(self.ca_label, serial_hex)
        self.api.add_given_cert(self.ca_label, cert_pem, CREATED_ON_DT, CREATOR_HOSTNAME,
                                adding_owner=do_add_user,
                                server_component_login=server_component_login)
        self._make_assertions(serial_hex, cert_pem, created_on=CREATED_ON_DT)


class _MakeCertTestHelperMixin(object):

    def _test(self, serial_hex, do_add_user, server_component_login=None):
        csr_pem = _load_csr_pem(self.ca_label, serial_hex)
        cert_pem, slug = self.api.make_new_cert(self.ca_label, csr_pem, CREATOR_HOSTNAME,
                                                adding_owner=do_add_user,
                                                server_component_login=server_component_login)
        self._make_assertions(serial_hex, cert_pem, csr_pem=csr_pem)


class _BaseClientCATestCase(_BaseAPIActionTest):

    """
    A base class for testing the operations through Manage API
    on *client* certificates. It defines general test methods,
    specific tested values will be defined inside its concrete
    subclasses.
    """

    ca_label = 'n6-client-ca'
    ca_profile = 'client'

    def test_valid_app_user(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'app@example.com', org)
        self._test('0000000000000000abcd', do_add_user=False)

    def test_valid_app_user__add_user(self):
        self.add_org(self.context_mock, 'example.com')
        self._test('0000000000000000abcd', do_add_user=True)
        self.check_for_user(self.context_mock, 'app@example.com')

    def test_app_user__add_user_no_org(self):
        with self.assertRaises(ManageAPIError):
            self._test('0000000000000000abcd', do_add_user=True)

    def test_app_user__no_org(self):
        self.add_user(self.context_mock, 'app@example.com')
        with self.assertRaises(ManageAPIError):
            self._test('0000000000000000abcd', do_add_user=False)

    def test_app_user__invalid_user_login(self):
        self.add_org(self.context_mock, 'example.com')
        with self.assertRaises(FieldValueError):
            self._test('000000000000000eabcd', do_add_user=True)



# concrete classes - test cases of unittest


@expand
class TestCertAndCSRFileClasses(_WithMocksMixin, _DBInterfaceMixin, unittest.TestCase):

    def setUp(self):
        self.make_patches()

    def test_cert_file_init_with_ca_pem(self):
        ca_cert_pem = _load_ca_cert_pem('n6-client-ca')
        self.load_ca(self.context_mock, 'n6-service-ca', 'service')
        ca_obj = CACertificate(self.context_mock,
                               'n6-service-ca',
                               mock.sentinel.manage_api_config_section)
        with self.assertRaises(TypeError):
            CertFile(ca_cert_pem, ca=ca_obj)

    def test_managing_entity_cert_file_init_with_ca_pem(self):
        ca_cert_pem = _load_ca_cert_pem('n6-client-ca')
        with self.assertRaises(TypeError):
            ManagingEntityCertFile(ca_cert_pem)

    def test_ca_cert_file_init_with_cert_pem(self):
        cert_pem = _load_cert_pem('n6-client-ca', '0000000000000000abcd')
        with self.assertRaises(TypeError):
            CACertFile(cert_pem)

    def test_cert_file_init_invalid_ca_obj(self):
        ca_cert_pem = _load_ca_cert_pem('n6-client-ca')
        cert_pem = _load_cert_pem('n6-client-ca', '0000000000000000abcd')
        with self.assertRaises(AttributeError):
            CertFile(cert_pem, ca=ca_cert_pem)

    @foreach([
        ('n6-client-ca', 'client', '0000000000000000abcd'),
        ('n6-service-ca', 'service', '765496b0d44901863497'),
    ])
    def test_cert_file_init(self, ca_label, ca_profile, cert_serial_nr):
        inst = self._get_cert_file_instance(ca_label, ca_profile, cert_serial_nr)
        self.assertTrue(inst)

    def test_ou_in_subject(self):
        inst = self._get_cert_file_instance('n6-service-ca', 'service', '765496b0d44901863497')
        self.assertIn('ou', inst.subject_dict)

    def test_ou_not_in_subject(self):
        inst = self._get_cert_file_instance('n6-client-ca', 'client', '0000000000000000abcd')
        self.assertNotIn('ou', inst.subject_dict)

    @foreach([
        'n6-client-ca',
        'n6-service-ca',
    ])
    def test_ca_cert_file_init(self, ca_label):
        inst = self._get_ca_cert_file_instance(ca_label)
        self.assertTrue(inst)
        with self.assertRaises(NotImplementedError):
            inst.get_subject_dict()

    def test_managing_entity_cert_file_init(self):
        cert_pem = _load_cert_pem('n6-service-ca', '765496b0d44901863497')
        inst = ManagingEntityCertFile(cert_pem)
        self.assertTrue(inst)
        self.assertIn('ou', inst.subject_dict)

    def test_managing_entity_not_service_ca_cert(self):
        cert_pem = _load_cert_pem('n6-client-ca', '0000000000000000abcd')
        with self.assertRaises(AccessForbiddenError):
            ManagingEntityCertFile(cert_pem)

    def test_cert_file_init_invalid_ca(self):
        self.load_ca(self.context_mock, 'n6-service-ca', 'service')
        ca_obj = CACertificate(self.context_mock,
                               'n6-service-ca',
                               mock.sentinel.manage_api_config_section)
        cert_pem = _load_cert_pem('n6-client-ca', '0000000000000000abcd')
        with self.assertRaisesRegexp(ManageAPIError,
                                     r'Verification of certificate of '
                                     r'/CN=app@example.com/O=example.com failed'):
            CertFile(cert_pem, ca=ca_obj)

    def test_valid_csr_verification(self):
        serial_nr = '0000000000000000abcd'
        csr_obj, cert_file = self._get_csr_cert_obj(serial_nr, serial_nr, 'n6-client-ca')
        self.assertIsNone(csr_obj.verify_csr(cert_file))

    def test_invalid_csr_verification(self):
        csr_obj, cert_file = self._get_csr_cert_obj('0000000000000000abcd',
                                                    'c55fd65ffe0671c4ba19',
                                                    'n6-client-ca')
        with self.assertRaises(ManageAPIError):
            csr_obj.verify_csr(cert_file)

    def test_cert_created_with_cert_and_csr_pem(self):
        ca_label = 'n6-client-ca'
        self.load_ca(self.context_mock, ca_label, 'client')
        ca_cert = CACertificate(self.context_mock, ca_label, mock.sentinel.config_section)
        cert_pem = _load_cert_pem(ca_label, '0000000000000000abcd')
        csr_pem = _load_csr_pem(ca_label, 'c55fd65ffe0671c4ba19')
        with self.assertRaises(TypeError):
            CertificateCreated(self.context_mock, ca_cert, CREATED_ON_DT, CREATOR_CN, 'user',
                               mock.sentinel.hostname, mock.sentinel.db_login,
                               mock.sentinel.internal_o_regex,
                               mock.sentinel.server_comp_ou_regex,
                               cert_pem,
                               csr_pem)

    def _get_cert_file_instance(self, ca_label, ca_profile, cert_serial_nr):
        self.load_ca(self.context_mock, ca_label, ca_profile)
        cert_pem = _load_cert_pem(ca_label, cert_serial_nr)
        ca_obj = CACertificate(self.context_mock,
                               ca_label,
                               mock.sentinel.manage_api_config_section)
        return CertFile(cert_pem, ca_obj)

    @staticmethod
    def _get_ca_cert_file_instance(ca_label):
        ca_cert_pem = _load_ca_cert_pem(ca_label)
        return CACertFile(ca_cert_pem)

    @staticmethod
    def _get_csr_cert_obj(cert_serial_nr, csr_serial_nr, ca_label):
        ca_pem = _load_ca_cert_pem(ca_label)
        cert_pem = _load_cert_pem(ca_label, cert_serial_nr)
        csr_pem = _load_csr_pem(ca_label, csr_serial_nr)
        ca_mock = mock.MagicMock(certificate=ca_pem)
        cert_file = CertFile(cert_pem, ca=ca_mock)
        csr_obj = CSRFile(csr_pem)
        return csr_obj, cert_file


@expand
class TestManagingEntity(_WithMocksMixin, _DBInterfaceMixin, unittest.TestCase):

    ca_label = 'n6-service-ca'
    user_cert_serial_cn = ('765496b0d44901863497', 'admin-user@example.com')
    component_cert_serial_cn = ('ce0c519c49fd5659271d', 'component-four')
    org_id = 'example.com'
    database_login = 'db_admin'
    ca_path = mock.sentinel.ca_path
    cert_path = mock.sentinel.cert_path
    key_path = mock.sentinel.key_path

    def get_context_mock(self, session_mock):
        """
        Extend the superclass method, so it returns a real
        `ConnectionContext` class, not a mocked one, so
        its attributes, created in constructor, can be tested.
        """
        m = super(TestManagingEntity, self).get_context_mock(session_mock)
        self.patch_session_bind_attr(m.db_session, self.database_login)
        return ManageAPIAuthDBConnector.ConnectionContext(m.db_session,
                                                          self.ca_path,
                                                          self.cert_path,
                                                          self.key_path)

    def setUp(self):
        self.make_patches()
        # set mocks for certificate file read, return value
        # of the `_file_read_mock` should be set later through
        # the `_set_opened_cert()` method
        self._open_mock = self.patch('n6corelib.manage_api._manage_api.open', create=True)
        self._file_read_mock = mock.Mock()
        self._open_mock.return_value.__enter__.return_value.read = self._file_read_mock
        # default values for `ManagingEntity` init args
        self.default_internal_regex = re.compile(INTERNAL_O_PATTERN)

    @foreach([
        (user_cert_serial_cn, 'user'),
        (component_cert_serial_cn, 'component'),
    ])
    def test_managing_entity(self, serial_cn, entity_type):
        serial_hex, cert_cn = serial_cn
        self._set_opened_cert(serial_hex)
        user_db_obj, component_db_obj = self._fill_db_with_entities(in_admins_group=True)
        self._fill_db_with_certs(user_db_obj, component_db_obj)
        instance = ManagingEntity(self.context_mock, self.default_internal_regex)
        self.assertEqual(instance.cert_cn, cert_cn)
        self.assertEqual(instance.database_login, self.database_login)
        self.assertEqual(instance._entity_type, entity_type)
        if entity_type == 'user':
            self.assertIs(instance.user_db_obj, user_db_obj)
            self.assertIsNone(instance.component_db_obj)
        else:
            self.assertIs(instance.component_db_obj, component_db_obj)
            self.assertIsNone(instance.user_db_obj)

    def test_entity_no_admins_group(self):
        self._set_opened_cert('765496b0d44901863497')
        self._fill_db_with_certs(*self._fill_db_with_entities(in_admins_group=False))
        with self.assertRaisesRegexp(ManageAPIError, r'The .+ system group was '
                                                     r'not found in Auth DB'):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    def test_user_not_admin(self):
        serial_hex, cert_cn = self.user_cert_serial_cn
        self._set_opened_cert(serial_hex)
        self._fill_db_with_certs(*self._fill_db_with_entities(in_admins_group=False))
        self.system_group_db_model.create_new(self.context_mock, name='admins')
        with self.assertRaisesRegexp(AccessForbiddenError, r'managing user .*{}. does not '
                                                           r'belong to .*{}. '
                                                           r'system group'.format(cert_cn,
                                                                                  'admins')):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    @foreach([
        user_cert_serial_cn[0],
        component_cert_serial_cn[0],
    ])
    def test_cert_not_found(self, serial_hex):
        self._set_opened_cert(serial_hex)
        self._fill_db_with_entities(in_admins_group=True)
        with self.assertRaisesRegexp(AccessForbiddenError, r"certificate \(serial number: .*{}.*\)"
                                                           r" was not found "
                                                           r"in the AuthDB".format(serial_hex)):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    @foreach([
        user_cert_serial_cn[0],
        component_cert_serial_cn[0],
    ])
    def test_cert_not_owned(self, serial_hex):
        self._set_opened_cert(serial_hex)
        self._fill_db_with_entities(in_admins_group=True)
        owner = self.add_user(self.context_mock, 'other@example.com', admins_group=True)
        owner_component = self.add_component(self.context_mock,
                                             'other-component')
        self._fill_db_with_certs(owner, owner_component)
        with self.assertRaisesRegexp(AccessForbiddenError, r"is not the owner of used certificate "
                                                           r"\(serial number: "
                                                           r".*{}.*\)".format(serial_hex)):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    @foreach([
        user_cert_serial_cn[0],
        component_cert_serial_cn[0],
    ])
    def test_revoked_certs(self, serial_hex):
        self._set_opened_cert(serial_hex)
        user, component = self._fill_db_with_entities(in_admins_group=True)
        user_cert, component_cert = self._fill_db_with_certs(user, component)
        # randomly set some revocation fields for both certificates
        user_cert.revoked_by_component_login = component.login
        component_cert.revoked_on = datetime.datetime(2018, 1, 1, 12)
        with self.assertRaisesRegexp(AccessForbiddenError, r"managing entity's certificate "
                                                           r"\(serial number: .*{}.*\) is "
                                                           r"revoked".format(serial_hex)):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    def test_non_internal_o(self):
        # certificate's 'O' is "some-internal.org", but a regex pattern
        # for internal organization is set to match "example.com"
        self._set_opened_cert('af2f68651a16f6567e07')
        new_org = self.add_org(self.context_mock, 'some-internal.org')
        self.add_user(self.context_mock, 'admin@internal.org', org=new_org, admins_group=True)
        with self.assertRaisesRegexp(AccessForbiddenError, r"Access forbidden for the entity "
                                                           r"using certificate with 'O' value: "
                                                           r".*{}.*".format('some-internal.org')):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    def test_component_with_not_matching_ou(self):
        # test for a component certificate, which has invalid
        # subject 'OU' - 'n6admins', which is used by admin
        # users
        self._set_opened_cert('9956a34b77371f3931c1')
        self.add_component(self.context_mock, 'managing-component')
        with self.assertRaisesRegexp(AccessForbiddenError, r'managing user .*{}.* was not '
                                                           r'found'.format('managing-component')):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    def test_user_with_not_matching_ou(self):
        self._set_opened_cert('a1717cc76c11b4b84faf')
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'manage@example.com', org=org, admins_group=True)
        with self.assertRaisesRegexp(AccessForbiddenError, r'managing component .*{}.* was not '
                                                           r'found'.format('manage@example.com')):
            ManagingEntity(self.context_mock, self.default_internal_regex)

    @foreach([
        (user_cert_serial_cn, 'user'),
        (component_cert_serial_cn, 'component'),
    ])
    def test_creator_details(self, serial_cn, entity_type):
        serial_hex, cert_cn = serial_cn
        self._set_opened_cert(serial_hex)
        ca_label = 'n6-service-ca'
        creator_hostname = 'test.example.com'
        self._fill_db_with_certs(*self._fill_db_with_entities(in_admins_group=True))
        self.load_ca(self.context_mock, ca_label, 'service')
        cert_pem = _load_cert_pem(ca_label, 'f908c0489127701717b4')
        cert_inst_ref_list = self.get_certificate_representation_class_inst_ref(CertificateCreated)
        api = ManageAPI()
        api.add_given_cert(ca_label, cert_pem, CREATED_ON_DT, creator_hostname=creator_hostname,
                           adding_owner=True)
        try:
            cert_ref = cert_inst_ref_list[0]
        except IndexError:
            self.fail('Could not get a reference to certificate class')
        assert len(cert_inst_ref_list) == 1, 'Bug in test: too many references'
        self.assertEqual(json.loads(cert_ref.creator_details),
                         {'hostname': creator_hostname,
                          'database_login': self.database_login})
        if entity_type == 'user':
            self.assertEqual(cert_ref.created_by_login, cert_cn)
            self.assertIsNone(cert_ref.created_by_component_login)
        else:
            self.assertEqual(cert_ref.created_by_component_login, cert_cn)
            self.assertIsNone(cert_ref.created_by_login)

    def _fill_db_with_entities(self, in_admins_group=True):
        internal_org = self.add_org(self.context_mock, self.org_id)
        new_user = self.add_user(self.context_mock,
                                 self.user_cert_serial_cn[1],
                                 org=internal_org,
                                 admins_group=in_admins_group)
        new_component = self.add_component(self.context_mock,
                                           self.component_cert_serial_cn[1])
        return new_user, new_component

    def _fill_db_with_certs(self, user_db_obj, component_db_obj):
        user_cert_pem = _load_cert_pem(self.ca_label, self.user_cert_serial_cn[0])
        component_cert_pem = _load_cert_pem(self.ca_label, self.component_cert_serial_cn[0])
        user_cert = self.add_cert(self.context_mock,
                                  serial_hex=self.user_cert_serial_cn[0],
                                  ca_cert_label=self.ca_label,
                                  certificate=user_cert_pem,
                                  owner=user_db_obj)
        component_cert = self.add_cert(self.context_mock,
                                       serial_hex=self.component_cert_serial_cn[0],
                                       ca_cert_label=self.ca_label,
                                       certificate=component_cert_pem,
                                       owner_component=component_db_obj)
        return user_cert, component_cert

    def _set_opened_cert(self, serial_hex):
        self._file_read_mock.return_value = _load_cert_pem(self.ca_label, serial_hex)


class TestDBInterface(_WithMocksMixin, _DBInterfaceMixin, unittest.TestCase):

    def setUp(self):
        self.make_patches()
        # check if the dict replacing a real database in tests
        # is empty before each test
        self.assertFalse(self.context_mock.db_session.collection)

    def test_create_new(self):
        ca_cert_pem = _load_ca_cert_pem('n6-client-ca')
        self.ca_db_model.create_new(self.context_mock, **{
            'ca_label': 'some_label',
            'certificate': ca_cert_pem,
            'ssl_config': 'some config',
        })
        self.assertTrue(self.context_mock.db_session.collection)
        self.assertIn('ca_cert', self.context_mock.db_session.collection)
        table_replacement = self.context_mock.db_session.collection['ca_cert']
        self.assertTrue(table_replacement)
        created_obj = table_replacement[0]
        self.assertIsInstance(created_obj, self.ca_db_model)
        self.assertEqual(created_obj.ca_label, 'some_label')
        self.assertEqual(created_obj.certificate, ca_cert_pem)
        self.assertEqual(created_obj.ssl_config, 'some config')
        self.assertIsNone(created_obj.profile)
        self.assertIsNone(created_obj.parent_ca_label)

    def test_convert_attr_to_list_if_relationship(self):
        group_obj_one = self.system_group_db_model.create_new(self.context_mock,
                                                              **{'name': 'group one'})
        group_obj_two = self.system_group_db_model.create_new(self.context_mock,
                                                              **{'name': 'group two'})
        self.load_ca(self.context_mock, 'n6-client-ca', 'client')
        cert_pem = _load_cert_pem('n6-client-ca', '0000000000000000abcd')
        some_cert_obj = self.cert_db_model.create_new(self.context_mock,
                                                      **{'serial_hex': '0000000000000000abcd',
                                                         'ca_cert_label': 'n6-client-ca',
                                                         'certificate': cert_pem})
        org_obj = self.org_db_model.create_new(self.context_mock, **{'org_id': 'example.com'})
        tested_init_kwargs = {
            'login': 'user@example.com',
            'org': org_obj,
            'system_groups': [group_obj_one, group_obj_two],
            'created_certs': some_cert_obj,
            'revoked_certs': [some_cert_obj],
        }
        self.user_db_model.create_new(self.context_mock, **tested_init_kwargs)
        collection = self.context_mock.db_session.collection
        self.assertIn('org', collection)
        self.assertIn('cert', collection)
        self.assertIn('ca_cert', collection)
        self.assertIn('system_group', collection)
        self.assertIn('user', collection)
        user_obj_from_db = collection['user'][0]
        self.assertIsInstance(user_obj_from_db.org, self.org_db_model)
        self.assertIsInstance(user_obj_from_db.created_certs, MutableSequence)
        self.assertIsInstance(user_obj_from_db.revoked_certs, MutableSequence)
        self.assertIsInstance(user_obj_from_db.system_groups, MutableSequence)

    def test_from_db(self):
        self.user_db_model.create_new(self.context_mock, **{'login': 'one@example.com'})
        self.user_db_model.create_new(self.context_mock, **{'login': 'two@example.com'})
        self.user_db_model.create_new(self.context_mock, **{'login': 'three@example.com'})
        obj_from_db = self.user_db_model.from_db(self.context_mock, 'login', 'two@example.com')
        self.assertIsInstance(obj_from_db, self.user_db_model)
        self.assertEqual('two@example.com', obj_from_db.login)

    def test_is_in_relation_with(self):
        org = self.org_db_model.create_new(self.context_mock, **{'org_id': 'org.com'})
        user_one = self.user_db_model.create_new(self.context_mock, **{'login': 'one@org.com',
                                                                       'org': org})
        user_two = self.user_db_model.create_new(self.context_mock, **{'login': 'two@org.com',
                                                                       'org': org})
        org_from_db = self.context_mock.db_session.collection['org'][0]
        self.assertIn(user_one, org_from_db.users)
        self.assertIn(user_two, org_from_db.users)
        self.assertTrue(org_from_db.is_in_relation_with(user_one, 'users'))
        self.assertTrue(org_from_db.is_in_relation_with(user_two, 'users'))

    def test_get_all_records(self):
        user_one = self.user_db_model.create_new(self.context_mock, **{'login': 'one@example.com'})
        user_two = self.user_db_model.create_new(self.context_mock, **{'login': 'two@example.com'})
        all_records = self.user_db_model.get_all_records(self.context_mock)
        empty_seq = self.org_db_model.get_all_records(self.context_mock)
        self.assertEqual(len(all_records), 2)
        self.assertIn(user_one, all_records)
        self.assertIn(user_two, all_records)
        self.assertFalse(empty_seq)


class TestAddCertClientCA(_AddCertTestHelperMixin, _BaseClientCATestCase, unittest.TestCase):

    """
    A concrete subclass and a test case. It tests adding of
    a *client* certificate through Manage API - defines expected
    objects, which should be found inside the mocked database after
    the operation.

    The class uses test methods from `_BaseClientCATestCase` class,
    and also defines its own, specific test methods.
    """

    expected_values = {
        '0000000000000000abcd': {
            'validity': ('Dec  3 15:59:51 2018 GMT', 'Feb 19 15:59:51 2027 GMT'),
            'slug': 'n6-client-ca-0000000000000000abcd-app-example.com',
            'subject': 'CN=app@example.com, O=example.com',
            'owner_login': 'app@example.com',
            'kind_of_owner': 'app-user',
        },
    }

    def test_app_user__server_component_login(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'app@example.com', org)
        with self.assertRaises(ManageAPIError):
            self._test('0000000000000000abcd', do_add_user=False,
                       server_component_login='server_comp@example.com')

    def test_no_subject_o(self):
        self.add_org(self.context_mock, 'example.com')
        with self.assertRaises(ManageAPIError):
            self._test('00000000000000001200', do_add_user=True)


class TestMakeCertClientCA(_MakeCertTestHelperMixin, _BaseClientCATestCase, unittest.TestCase):

    """
    A concrete subclass and a test case. It tests making of a new
    *client* certificate through Manage API - defines expected
    objects, which should be found inside the mocked database after
    the operation.

    The class uses test methods from `_BaseClientCATestCase` class,
    and also defines its own, specific test methods.
    """

    expected_values = {
        '0000000000000000abcd': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-client-ca-12345678abcdef012345-app-example.com',
            'subject': 'CN=app@example.com, O=example.com',
            'owner_login': 'app@example.com',
            'kind_of_owner': 'app-user',
        },
    }

    def test_app_user__server_component_login(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'app@example.com', org)
        # if `server_component_login` arg is present, it asserts
        # this is a service certificate
        with self.assertRaises(AssertionError):
            self._test('0000000000000000abcd', do_add_user=False,
                       server_component_login='server_comp@example.com')

    def test_no_subject_o(self):
        self.add_org(self.context_mock, 'example.com')
        with self.assertRaises(RuntimeError):
            self._test('00000000000000001200', do_add_user=True)


class _BaseServiceCATestCase(_BaseAPIActionTest):

    ca_label = 'n6-service-ca'
    ca_profile = 'service'

    def test_valid_server_component(self):
        self.add_component(self.context_mock, login='login-from-args')
        self._test('00000000000000123456', do_add_user=False,
                   server_component_login='login-from-args')

    def test_valid_server_component__add_user(self):
        self._test('00000000000000123456', do_add_user=True,
                   server_component_login='login-from-args')
        self.check_for_component(self.context_mock, 'login-from-args')

    def test_server_component__no_s_arg(self):
        self.add_component(self.context_mock, login='server-component-one')
        with self.assertRaises(ManageAPIError):
            self._test('00000000000000123456', do_add_user=False)

    def test_internal_component(self):
        self.add_component(self.context_mock, login='component-four')
        self._test('ce0c519c49fd5659271d', do_add_user=False)

    def test_internal_component__add_user(self):
        self._test('ce0c519c49fd5659271d', do_add_user=True)
        self.check_for_component(self.context_mock, 'component-four')

    def test_component__wrong_org(self):
        self.add_org(self.context_mock, 'test.org')
        self.add_component(self.context_mock, 'component-four')
        with self.assertRaises(ManageAPIError):
            self._test('f9962d93676e439cdcb5', do_add_user=False)

    def test_admin_user__wrong_login(self):
        with self.assertRaises(FieldValueError):
            self.add_user(self.context_mock, 'admin-user', admins_group=True)

    def test_admin_user(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'admin-user@example.com', org=org, admins_group=True)
        self._test('765496b0d44901863497', do_add_user=False)

    def test_admin_user__add_user_no_org(self):
        with self.assertRaises(ManageAPIError):
            self._test('765496b0d44901863497', do_add_user=True)

    def test_admin_user__no_user(self):
        with self.assertRaises(ManageAPIError):
            self._test('765496b0d44901863497', do_add_user=True)

    def test_admin_user__no_org(self):
        self.add_user(self.context_mock, 'admin-user@example.com', admins_group=True)
        with self.assertRaises(ManageAPIError):
            self._test('765496b0d44901863497', do_add_user=False)

    def test_admin_user__no_admins_sys_group(self):
        self.add_user(self.context_mock, 'admin-user@example.com', admins_group=False)
        with self.assertRaises(ManageAPIError):
            self._test('765496b0d44901863497', do_add_user=False)

    def test_admin_user__other_login(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'admin-user@some.org', org=org, admins_group=True)
        self._test('f908c0489127701717b4', do_add_user=False)

    def _modify_internal_pattern(self):
        # change ManageAPI's attribute value, so the internal
        # organization has a different regex pattern
        self.api._internal_o_regex = re.compile(r'\Asome-internal\.org\Z')

    def test_component__not_matching_internal(self):
        # test whether CA certificate's organization and internal
        # organization may differ
        self._modify_internal_pattern()
        self.add_org(self.context_mock, 'example.com')
        self.add_org(self.context_mock, 'some-internal.org')
        self.add_component(self.context_mock, 'component-fifth')
        self._test('5b2637aaa005c88856d9', do_add_user=False)

    def test_admin__not_matching_internal(self):
        self._modify_internal_pattern()
        self.add_org(self.context_mock, 'example.com')
        org = self.add_org(self.context_mock, 'some-internal.org')
        self.add_user(self.context_mock, 'admin@internal.org', org=org, admins_group=True)
        self._test('af2f68651a16f6567e07', do_add_user=False)


class TestAddCertServiceCA(_AddCertTestHelperMixin, _BaseServiceCATestCase, unittest.TestCase):

    expected_values = {
        '00000000000000123456': {
            'validity': ('Dec 11 15:24:41 2018 GMT', 'Feb 27 15:24:41 2027 GMT'),
            'slug': 'n6-service-ca-00000000000000123456-server-component-one',
            'subject': 'CN=server-component-one, O=example.com, OU=Internal Unit',
            'owner_component_login': 'login-from-args',
            'kind_of_owner': 'server-component',
        },
        'ce0c519c49fd5659271d': {
            'validity': ('Dec 14 12:16:40 2018 GMT', 'Mar 2 12:16:40 2027 GMT'),
            'slug': 'n6-service-ca-ce0c519c49fd5659271d-component-four',
            'subject': 'CN=component-four, O=example.com, OU=n6components',
            'owner_component_login': 'component-four',
            'kind_of_owner': 'component',
        },
        '765496b0d44901863497': {
            'validity': ('Dec 14 12:56:23 2018 GMT', 'Mar 2 12:56:23 2027 GMT'),
            'slug': 'n6-service-ca-765496b0d44901863497-admin-user-example.com',
            'subject': 'CN=admin-user@example.com, O=example.com, OU=n6admins',
            'owner_login': 'admin-user@example.com',
            'kind_of_owner': 'admin',
        },
        'f908c0489127701717b4': {
            'validity': ('Dec 14 13:00:08 2018 GMT', 'Mar  2 13:00:08 2027 GMT'),
            'slug': 'n6-service-ca-f908c0489127701717b4-admin-user-some.org',
            'subject': 'CN=admin-user@some.org, O=example.com, OU=n6admins',
            'owner_login': 'admin-user@some.org',
            'kind_of_owner': 'admin',
        },
        '5b2637aaa005c88856d9': {
            'validity': ('Dec 14 13:30:39 2018 GMT', 'Mar  2 13:30:39 2027 GMT'),
            'slug': 'n6-service-ca-5b2637aaa005c88856d9-component-fifth',
            'subject': 'CN=component-fifth, O=some-internal.org, OU=n6components',
            'owner_component_login': 'component-fifth',
            'kind_of_owner': 'component',
        },
        'af2f68651a16f6567e07': {
            'validity': ('Dec 14 15:43:24 2018 GMT', 'Mar  2 15:43:24 2027 GMT'),
            'slug': 'n6-service-ca-af2f68651a16f6567e07-admin-internal.org',
            'subject': 'CN=admin@internal.org, O=some-internal.org, OU=n6admins',
            'owner_login': 'admin@internal.org',
            'kind_of_owner': 'admin',
        },
    }

    def test_no_ou(self):
        with self.assertRaises(ManageAPIError):
            self._test('1a26b67f5df2e5ba3eba', do_add_user=False)

    def test_internal_component__server_component(self):
        with self.assertRaises(ManageAPIError):
            self._test('ce0c519c49fd5659271d', do_add_user=True,
                       server_component_login='four-server')

    def test_component__no_o(self):
        self.add_component(self.context_mock, login='component-three')
        with self.assertRaises(ManageAPIError):
            self._test('fedcba12345678000000', do_add_user=False)

    def test_admin_user__server_component(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'admin-user@example.com', org=org, admins_group=True)
        with self.assertRaises(ManageAPIError):
            self._test('765496b0d44901863497', do_add_user=False,
                       server_component_login='other-admin@something.org')


class TestMakeCertServiceCA(_MakeCertTestHelperMixin, _BaseServiceCATestCase, unittest.TestCase):

    expected_values = {
        '00000000000000123456': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-server-component-one',
            'subject': 'CN=server-component-one, O=example.com, OU=Internal Unit',
            'owner_component_login': 'login-from-args',
            'kind_of_owner': 'server-component',
        },
        'ce0c519c49fd5659271d': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-component-four',
            'subject': 'CN=component-four, O=example.com, OU=n6components',
            'owner_component_login': 'component-four',
            'kind_of_owner': 'component',
        },
        '765496b0d44901863497': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-admin-user-example.com',
            'subject': 'CN=admin-user@example.com, O=example.com, OU=n6admins',
            'owner_login': 'admin-user@example.com',
            'kind_of_owner': 'admin',
        },
        'f908c0489127701717b4': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-admin-user-some.org',
            'subject': 'CN=admin-user@some.org, O=example.com, OU=n6admins',
            'owner_login': 'admin-user@some.org',
            'kind_of_owner': 'admin',
        },
        '5b2637aaa005c88856d9': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-component-fifth',
            'subject': 'CN=component-fifth, O=some-internal.org, OU=n6components',
            'owner_component_login': 'component-fifth',
            'kind_of_owner': 'component',
        },
        'af2f68651a16f6567e07': {
            'serial_hex': SERIAL_NUMBER,
            'days_valid': NEW_CERT_VALIDITY_DELTA,
            'slug': 'n6-service-ca-12345678abcdef012345-admin-internal.org',
            'subject': 'CN=admin@internal.org, O=some-internal.org, OU=n6admins',
            'owner_login': 'admin@internal.org',
            'kind_of_owner': 'admin',
        },
    }

    def test_no_ou(self):
        with self.assertRaises(RuntimeError):
            self._test('1a26b67f5df2e5ba3eba', do_add_user=False)

    def test_internal_component__server_component(self):
        with self.assertRaises(RuntimeError):
            self._test('ce0c519c49fd5659271d', do_add_user=True,
                       server_component_login='four-server')

    def test_component__no_o(self):
        self.add_component(self.context_mock, login='component-three')
        with self.assertRaises(RuntimeError):
            self._test('fedcba12345678000000', do_add_user=False)

    def test_admin_user__server_component(self):
        org = self.add_org(self.context_mock, 'example.com')
        self.add_user(self.context_mock, 'admin-user@example.com', org=org, admins_group=True)
        with self.assertRaises(RuntimeError):
            self._test('765496b0d44901863497', do_add_user=False,
                       server_component_login='other-admin@something.org')

    def test_server_component__not_match_org(self):
        self.add_org(self.context_mock, 'example.com')
        self.add_org(self.context_mock, 'dudu.com')
        self.add_component(self.context_mock, 'svrc_comp')
        # according to OpenSSL config, in case of a server component,
        # organizationName field has to match that of CA certificate
        with self.assertRaises(RuntimeError):
            self._test('2a64f0eee4ce12a2bdc9', do_add_user=False,
                       server_component_login='svrc_comp')


class _RevokeCertTestBase(_BaseAPIActionTest):

    ca_certs_in_db = {
        'n6-client-ca': 'client',
        'n6-service-ca': 'service',
        'root': None,
    }
    certs_in_db = NotImplemented
    default_tested_cert_serial_nr = NotImplemented
    dummy_openssl_config = 'dummy string'

    def setUp(self):
        self.basic_api_action_specific_setup(manage_api_cert_class=CertificateFromDatabase)
        self._add_certs_to_mock_db()

    def _add_certs_to_mock_db(self):
        for ca_label, profile in self.ca_certs_in_db.iteritems():
            ca_pem = _load_ca_cert_pem(ca_label)
            self.ca_db_model.create_new(self.context_mock, ca_label=ca_label, certificate=ca_pem,
                                        profile=profile, ssl_config=self.dummy_openssl_config)
        for serial_hex, content in self.certs_in_db.iteritems():
            cert_pem = _load_cert_pem(content['ca_cert_label'], serial_hex)
            if content.get('csr'):
                csr_pem = _load_csr_pem(content['ca_cert_label'], serial_hex)
            else:
                csr_pem = None
            init_kwargs = copy.copy(content)
            init_kwargs['serial_hex'] = serial_hex
            init_kwargs['certificate'] = cert_pem
            init_kwargs['csr'] = csr_pem
            self.cert_db_model.create_new(self.context_mock, **init_kwargs)

    def _test(self, serial_hex, revocation_comment):
        crl_pem = self.api.revoke_cert(self.ca_label, serial_hex, revocation_comment)
        self._make_assertions(serial_hex, crl_pem, revocation_comment)
        self._verify_revoked(crl_pem, serial_hex)

    def _make_assertions(self, serial_hex, crl, revocation_comment):
        cert_ref = self._cert_inst_ref[0]
        assert len(self._cert_inst_ref) == 1, 'Bug in test: too many references'
        cert_from_db = self.cert_db_model.from_db(self.context_mock, 'serial_hex', serial_hex)
        self.assertEqual(cert_from_db.revoked_on, cert_ref.revoked_on)
        self.assertAlmostEqual(datetime.datetime.utcnow(), cert_from_db.revoked_on,
                               delta=ONE_MINUTE_DELTA)
        self.assertEqual(cert_from_db.revocation_comment, cert_ref.revocation_comment)
        self.assertEqual(revocation_comment, cert_from_db.revocation_comment)
        self.assertEqual(cert_from_db.revoked_by_login, cert_ref.revoked_by_login)
        self.assertEqual(cert_from_db.revoked_by_component_login,
                         cert_ref.revoked_by_component_login)
        managing_user = self.user_db_model.from_db(self.context_mock, 'login', CREATOR_CN)
        self.assertIs(managing_user, cert_from_db.revoked_by)
        # currently assuming a managing entity can be a user only
        self.assertIs(None, cert_from_db.revoked_by_component)

    def _verify_revoked(self, crl_pem, serial_hex):
        crl, stderr = _parse_crl_pem(crl_pem)
        self.assertFalse(stderr)
        self.assertRegexpMatches(crl, r'\ACertificate Revocation List')
        self.assertRegexpMatches(crl, r'\bSerial Number:[ ]* {}'.format(serial_hex.upper()))

    def _test_revocation(self, first_serial_hex, second_serial_hex):
        self._test(first_serial_hex, 'Some comment on why cert has been revoked.')
        self._test(second_serial_hex, 'Other cert has been revoked')

    def test_no_comment(self):
        with self.assertRaisesRegexp(ManageAPIError,
                                     r'When revoking a certificate '
                                     r'`revocation_comment` must not be None'):
            self._test(self.default_tested_cert_serial_nr, None)

    def test_already_revoked(self):
        serial_nr = self.default_tested_cert_serial_nr
        self._test(serial_nr, 'lsl')
        with self.assertRaisesRegexp(ManageAPIError,
                                     r"The certificate with serial number: '{}' "
                                     r"has already been revoked".format(serial_nr)):
            self._test(serial_nr, 'asf')

    def test_cert_not_found(self):
        serial_nr = 'e06974c8e6'
        with self.assertRaisesRegexp(ManageAPIError, r"Could not find certificate with "
                                                     r"serial number: '{}'".format(serial_nr)):
            self._test(serial_nr, 'revocation comment')

    def _test_with_ca_label(self, tested_ca_label, cert_serial_hex, comment='some_comment'):
        with self.assertRaisesRegexp(ManageAPIError, r'does not match a label of CA '
                                                     r'associated with certificate fetched'):
            self.api.revoke_cert(tested_ca_label, cert_serial_hex, comment)

    def _test_revocation_fields_not_empty(self, serial_hex, key, val):
        # when any field associated with revocation is not empty,
        # it is assumed the certificate has been revoked
        self.add_user(self.context_mock, login='revoker@example.com')
        self.add_component(self.context_mock, login='revoking_component')
        init_kwargs = {
            'serial_hex': serial_hex,
            'certificate': _load_cert_pem(self.ca_label, serial_hex),
            'ca_cert_label': self.ca_label,
            key: val,
        }
        self.add_cert(self.context_mock, **init_kwargs)
        with self.assertRaisesRegexp(ManageAPIError,
                                     r"\AThe certificate with serial number: '{}' has "
                                     r"already been revoked".format(serial_hex)):
            self._test(serial_hex, revocation_comment='Try to revoke already revoked cert')


@expand
class TestRevokeClientCACerts(_RevokeCertTestBase, unittest.TestCase):

    ca_label = 'n6-client-ca'
    ca_profile = 'client'

    default_tested_cert_serial_nr = 'e61753a2f8e887770288'

    certs_in_db = {
        'e61753a2f8e887770288': {
            'ca_cert_label': ca_label,
            'csr': True,
            'created_by_login': 'some@user.com',
            'is_client_cert': True,
        },
        'c55fd65ffe0671c4ba19': {
            'ca_cert_label': ca_label,
            'created_by_login': 'app-user@example.com',
            'is_client_cert': True,
        },
    }

    def test_revocation(self):
        self._test_revocation('e61753a2f8e887770288', 'c55fd65ffe0671c4ba19')

    def test_ca_label_not_match(self):
        self._test_with_ca_label('n6-service-ca', 'c55fd65ffe0671c4ba19')

    @foreach([
        ('revoked_on', '2018-06-04T11:33:00'),
        ('revoked_by_login', 'revoker@example.com'),
        ('revoked_by_component_login', 'revoking_component'),
    ])
    def test_revocation_fields_not_empty(self, key, val):
        self._test_revocation_fields_not_empty('48a43f0059fbc1eb82b2', key, val)


@expand
class TestRevokeServiceCACerts(_RevokeCertTestBase, unittest.TestCase):

    ca_label = 'n6-service-ca'
    ca_profile = 'service'

    default_tested_cert_serial_nr = 'af2f68651a16f6567e07'

    certs_in_db = {
        'f9962d93676e439cdcb5': {
            'ca_cert_label': ca_label,
            'csr': True,
            'owner_component_login': 'component-three',
            'created_by_login': 'some2@user.com',
        },
        'af2f68651a16f6567e07': {
            'ca_cert_label': ca_label,
            'csr': False,
            'owner_login': 'admin@internal.org',
            'created_by_login': 'app-user2@example.com',
        },
    }

    def test_revocation(self):
        self._test_revocation('f9962d93676e439cdcb5', 'af2f68651a16f6567e07')

    def test_ca_label_not_match(self):
        self._test_with_ca_label('n6-client-ca', 'af2f68651a16f6567e07')

    @foreach([
        ('revoked_on', '2018-10-11T14:12:03'),
        ('revoked_by_login', 'revoker2@example.com'),
        ('revoked_by_component_login', 'revoking_component2'),
    ])
    def test_revocation_fields_not_empty(self, key, val):
        self._test_revocation_fields_not_empty('765496b0d44901863497', key, val)


class _SSLConfigTestBase(_BaseAPIActionTest):

    ca_label = NotImplemented
    ca_profile = NotImplemented

    default_serial_hex = NotImplemented

    missing_opt_label = 'missing-{opt_name}-opt'
    missing_sect_label = 'missing-{sect_name}-sect'
    empty_sect_label = 'empty-{sect_name}-sect'

    general_exc_msg_pattern = (r"SSL config assigned to particular CA certificate .*?"
                               r"(?P<label>{ca_label}['\"]\)).*?")
    # the u?['\"] pattern should match the beginning of a string
    # representation, whether it is Unicode or string, and whether
    # it starts with single or double quotation marks (the latter
    # being escaped by backslash)
    missing_opt_pattern = r"the option u?['\"]{opt_name}['\"] is missing.*"
    missing_sect_pattern = r"the section u?['\"]{sect_name}['\"] is missing.*"
    empty_sect_pattern = r"the section u?['\"]{sect_name}['\"] exists, but it is empty.*"

    def _get_expected_exc_pattern(self, general_msg, detailed_msg, **format_kwargs):
        full_msg_pattern = general_msg + detailed_msg
        return full_msg_pattern.format(ca_label=self.ca_label, **format_kwargs)

    def load_ca(self, context, ca_label, profile):
        self.ca_pem = _load_ca_cert_pem(ca_label)

    def finish_loading_of_ca(self, context, ca_config_label):
        self.ca_config = _load_ca_ssl_config_cnf_by_label_and_ca_label(self.ca_label,
                                                                       ca_config_label)
        self.ca_db_model.create_new(context, ca_label=self.ca_label, certificate=self.ca_pem,
                                    profile=self.ca_profile, ssl_config=self.ca_config)


@expand
class TestSSLConfigMakeCertClientCA(_SSLConfigTestBase,
                                    _MakeCertTestHelperMixin,
                                    unittest.TestCase):

    ca_label = 'n6-client-ca'
    ca_profile = 'client'

    default_serial_hex = '0000000000000000abcd'

    ca_sect_name = 'ca'
    policy_sect_name = 'clientCA_policy'
    x509_extensions_sect_name = 'certificate_extensions'

    def _test_missing(self, config_label, expected_exc_pattern):
        self.finish_loading_of_ca(self.context_mock, config_label)
        with self.assertRaisesRegexp(ManageAPIError, expected_exc_pattern):
            self._test(self.default_serial_hex, do_add_user=True)

    @foreach([
        'default_ca',
        'dir',
        'certificate',
        'policy',
        'default_md',
        'default_days',
    ])
    def test_opt_missing(self, opt_name):
        config_label = self.missing_opt_label.format(opt_name=opt_name)
        expected_exc_pattern = self._get_expected_exc_pattern(self.general_exc_msg_pattern,
                                                              self.missing_opt_pattern,
                                                              opt_name=opt_name)
        self._test_missing(config_label, expected_exc_pattern)

    @foreach([
        ca_sect_name,
        policy_sect_name,
        x509_extensions_sect_name,
    ])
    def test_sect_missing(self, sect_name):
        config_label = self.missing_sect_label.format(sect_name=sect_name)
        expected_exc_pattern = self._get_expected_exc_pattern(self.general_exc_msg_pattern,
                                                              self.missing_sect_pattern,
                                                              sect_name=sect_name)
        self._test_missing(config_label, expected_exc_pattern)

    @foreach([
        ca_sect_name,
        policy_sect_name,
    ])
    def test_sect_empty(self, sect_name):
        # the 'certificate_extensions' section is not tested, whether
        # it is empty, because it is not required; exception is not
        # raised, just a message logged
        config_label = self.empty_sect_label.format(sect_name=sect_name)
        expected_exc_pattern = self._get_expected_exc_pattern(self.general_exc_msg_pattern,
                                                              self.empty_sect_pattern,
                                                              sect_name=sect_name)
        self._test_missing(config_label, expected_exc_pattern)


class TestSSLConfigMakeCertServerComponent(_SSLConfigTestBase,
                                           _MakeCertTestHelperMixin,
                                           unittest.TestCase):

    ca_label = 'n6-service-ca'
    ca_profile = 'service'

    default_serial_hex = '00000000000000123456'

    policy_sect_name = 'server_component_serviceCA_policy'

    def _test_policy_section(self, config_label_pattern, exc_reason_pattern, sect_name=None):
        sect_name = sect_name if sect_name is not None else self.policy_sect_name
        config_label = config_label_pattern.format(sect_name=sect_name)
        expected_exc_pattern = self._get_expected_exc_pattern(self.general_exc_msg_pattern,
                                                              exc_reason_pattern,
                                                              sect_name=sect_name)
        self.finish_loading_of_ca(self.context_mock, config_label)
        with self.assertRaisesRegexp(ManageAPIError, expected_exc_pattern):
            self._test(self.default_serial_hex, do_add_user=True, server_component_login=True)

    def test_missing_policy_section(self):
        self._test_policy_section(self.missing_sect_label, self.missing_sect_pattern)

    def test_empty_policy_section(self):
        self._test_policy_section(self.empty_sect_label, self.empty_sect_pattern)


@expand
class TestSSLConfigGenerateCRL(_SSLConfigTestBase, unittest.TestCase):

    ca_label = 'n6-service-ca'
    ca_profile = 'service'

    default_serial_hex = 'f9962d93676e439cdcb5'
    cert_cn = 'component-three'
    revocation_comment = 'Example revocation comment'

    def setUp(self):
        super(TestSSLConfigGenerateCRL, self).setUp()
        cert_pem = _load_cert_pem(self.ca_label, self.default_serial_hex)
        csr_pem = _load_csr_pem(self.ca_label, self.default_serial_hex)
        self.add_component(self.context_mock, self.cert_cn)
        self.add_cert(self.context_mock,
                      ca_cert_label=self.ca_label,
                      serial_hex=self.default_serial_hex,
                      certificate=cert_pem,
                      csr=csr_pem,
                      created_on=CREATED_ON_DT,
                      valid_from=CREATED_ON_DT,
                      expires_on=CREATED_ON_DT+NEW_CERT_VALIDITY_DELTA,
                      owner_component_login=self.cert_cn,
                      created_by_login=CREATOR_CN,
                      is_server_cert=True)

    def _test(self):
        return self.api.revoke_cert(self.ca_label,
                                    self.default_serial_hex,
                                    self.revocation_comment)

    @foreach([
        'default_md',
        'default_crl_days',
    ])
    def test_opt_missing(self, opt_name):
        config_label = self.missing_opt_label.format(opt_name=opt_name)
        expected_exc_pattern = self._get_expected_exc_pattern(self.general_exc_msg_pattern,
                                                              self.missing_opt_pattern,
                                                              opt_name=opt_name)
        self.finish_loading_of_ca(self.context_mock, config_label)
        with self.assertRaisesRegexp(Exception, expected_exc_pattern):
            self._test()


if __name__ == '__main__':
    unittest.main()

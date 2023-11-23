# Copyright (c) 2014-2023 NASK. All rights reserved.

import collections
import contextlib
import datetime
import itertools
import os
import random
import re
import string
import unittest
from unittest.mock import (
    MagicMock,
    Mock,
    call,
    patch,
    sentinel as sen,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.auth_api import (
    AuthAPI,
    _DataPreparer,
    InsideCriteriaResolver,
    cached_basing_on_ldap_root_node,
)
from n6lib.auth_related_test_helpers import (
    EXAMPLE_SEARCH_RAW_RETURN_VALUE,
    EXAMPLE_ORG_IDS_TO_ACCESS_INFOS,
    EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION,
    EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS,
    EXAMPLE_ORG_IDS_TO_ACTUAL_NAMES,
    EXAMPLE_SOURCE_IDS_TO_SUBS_TO_STREAM_API_ACCESS_INFOS,
    EXAMPLE_SOURCE_IDS_TO_NOTIFICATION_ACCESS_INFO_MAPPINGS,
)
from n6lib.common_helpers import (
    ip_network_as_tuple,
    ip_network_tuple_to_min_max_ip,
    ip_str_to_int,
)
from n6lib.record_dict import RecordDict
from n6lib.unit_test_helpers import (
    MethodProxy,
    TestCaseMixin,
)
from n6lib.sqlalchemy_related_test_helpers import (
    sqlalchemy_expr_to_str,
)


# the following variable (+function) make it possible to instrumentalize
# creation of the `LOGGER_error_mock` test method argument...
LOGGER_error_mock_factory = MagicMock
def _make_LOGGER_error_mock():
    return LOGGER_error_mock_factory()


class _AuthAPILdapDataBasedMethodTestMixIn(object):

    @contextlib.contextmanager
    def standard_context(self, search_flat_return_value):
        # Note: considering how this method is implemented, it is
        # usable when testing `AuthAPI` but *not* when testing
        # `AuthAPIWithPrefetching`.  To make use of this class
        # (`_AuthAPILdapDataBasedMethodTestMixIn`) when testing
        # the latter you need to override or patch this method
        # (`standard_context()`).  As an example, refer to the
        # relevant parts of the definition of the function
        # `_patch_AuthAPILdapDataBasedMethodTestMixIn()` in
        # the `./auth_related_quicktest.py` script.
        with patch('n6lib.auth_api.LdapAPI.get_config_section',
                   return_value=collections.defaultdict(lambda: NotImplemented)), \
             patch('n6lib.auth_api.LdapAPI.set_config', create=True), \
             patch('n6lib.auth_api.LdapAPI.configure_db', create=True):
            self.auth_api = AuthAPI()
            self.data_preparer = self.auth_api._data_preparer
            try:
                with patch('n6lib.auth_api.LdapAPI._make_ssl_connection', create=True), \
                     patch('n6lib.auth_api.LdapAPI._db_session_maker', create=True), \
                     patch('n6lib.auth_api.LdapAPI._search_flat',
                           return_value=search_flat_return_value), \
                     self.unmemoized_root_node_getter(auth_api_class=self.auth_api.__class__):
                    yield
            finally:
                self.auth_api = None
                self.data_preparer = None

    @staticmethod
    @contextlib.contextmanager
    def unmemoized_root_node_getter(auth_api_class):
        # noinspection PyProtectedMember
        unmemoized__get_root_node = getattr(auth_api_class._get_root_node, 'func', None)
        if unmemoized__get_root_node:
            with patch.object(auth_api_class, '_get_root_node', unmemoized__get_root_node):
                yield
        else:
            yield

    def assert_problematic_orgs_logged(self, LOGGER_error_mock, problematic_org_ids):
        error_calls_args = [args for _, args, _ in map(tuple, LOGGER_error_mock.mock_calls)]
        self.assertTrue(error_calls_args)
        self.assertTrue(all(
            (isinstance(args[0], str) and
             args[0].startswith('Problem with LDAP data for ') and
             isinstance(args[1], str) and
             isinstance(args[2], str) and
             args[2].startswith('ValueError'))
            for args in error_calls_args))
        self.assertEqual(
            problematic_org_ids,
            set(self._pick_o(args[1]) for args in error_calls_args))

    @staticmethod
    def _pick_o(s):
        [org_name] = re.findall(r'\bo[0-9]+\b', s, re.ASCII)
        return org_name


class TestAuthAPI__context_manager(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    def setUp(self):
        # prepare a standard context (+ its cleanup):
        standard_context = self.standard_context([])
        standard_context.__enter__()
        self.addCleanup(standard_context.__exit__, None, None, None)

        # for brevity:
        self.loc = self.auth_api._root_node_deposit

        # prepare a mock method:
        self.tracer = tracer = Mock()
        silly_method_results = itertools.cycle(string.ascii_lowercase)
        def silly_method(self):
            tracer()
            self.get_ldap_root_node()
            return next(silly_method_results)
        self.silly_method = silly_method

        # cleanup for methods that set AuthAPI.silly_method:
        def _AuthAPI_silly_method_cleanup():
            if hasattr(AuthAPI, 'silly_method'):
                delattr(AuthAPI, 'silly_method')
        self.addCleanup(_AuthAPI_silly_method_cleanup)

    def test_ldap_root_node__with_and_without_context_manager(self):
        self.assertIsNone(self.loc.outermost_context)
        root1 = self.auth_api.get_ldap_root_node()
        self.assertEqual(root1, {'attrs': {}})
        self.assertIsNone(self.loc.outermost_context)
        with self.auth_api:
            root2 = self.loc.outermost_context
            self.assertEqual(root2, {'attrs': {}})
            self.assertIsNot(root2, root1)
            self.assertIs(root2, self.auth_api.get_ldap_root_node())
            with self.auth_api, self.auth_api, self.auth_api:
                # context manager is reentrant (can be freely nested)
                self.assertIs(root2, self.loc.outermost_context)
                self.assertIs(root2, self.auth_api.get_ldap_root_node())
            self.assertIs(root2, self.loc.outermost_context)
            self.assertIs(root2, self.auth_api.get_ldap_root_node())
        self.assertIsNone(self.loc.outermost_context)
        root3 = self.auth_api.get_ldap_root_node()
        self.assertEqual(root3, {'attrs': {}})
        self.assertIsNone(self.loc.outermost_context)
        self.assertIsNot(root3, root2)
        self.assertIsNot(root3, root1)

    def test_decorated_method__with_and_without_context_manager(self):
        AuthAPI.silly_method = cached_basing_on_ldap_root_node(self.silly_method)
        method = self.auth_api.silly_method
        tracer = self.tracer
        self.assertEqual(tracer.call_count, 0)
        self.assertEqual(method(), 'a')
        self.assertEqual(method(), 'b')
        self.assertEqual(method(), 'c')
        self.assertEqual(tracer.call_count, 3)
        with self.auth_api:
            self.assertEqual(method(), 'd')
            self.assertEqual(method(), 'd')
            self.assertEqual(method(), 'd')
            with self.auth_api:
                # context manager is reentrant (can be freely nested)
                self.assertEqual(method(), 'd')
                self.assertEqual(method(), 'd')
            self.assertEqual(method(), 'd')
            self.assertEqual(method(), 'd')
        self.assertEqual(tracer.call_count, 4)
        self.assertEqual(method(), 'e')
        self.assertEqual(method(), 'f')
        self.assertEqual(tracer.call_count, 6)
        with self.auth_api:
            self.assertEqual(method(), 'g')
            self.assertEqual(method(), 'g')
            self.assertEqual(method(), 'g')
        self.assertEqual(tracer.call_count, 7)
        self.assertEqual(method(), 'h')
        self.assertEqual(method(), 'i')
        self.assertEqual(tracer.call_count, 9)

    def test_decorated_method__with_context_manager__forcing_cache_invalidation(self):
        AuthAPI.silly_method = cached_basing_on_ldap_root_node(self.silly_method)
        method = self.auth_api.silly_method
        tracer = self.tracer
        self.assertEqual(tracer.call_count, 0)
        with self.auth_api:
            self.assertEqual(method(), 'a')
            self.assertEqual(method(), 'a')
            self.assertEqual(method(), 'a')
            self.assertEqual(tracer.call_count, 1)

            # forcing cache invalidation:
            self.auth_api._root_node_deposit._unsafe_replace_outermost_context({'attrs': {}})

            self.assertEqual(method(), 'b')
            self.assertEqual(method(), 'b')
            self.assertEqual(method(), 'b')
            self.assertEqual(tracer.call_count, 2)
            with self.auth_api:
                self.assertEqual(method(), 'b')
                with self.auth_api, self.auth_api, self.auth_api:
                    self.assertEqual(method(), 'b')
                self.assertEqual(method(), 'b')
                self.assertEqual(tracer.call_count, 2)

                # forcing cache invalidation:
                self.auth_api._root_node_deposit._unsafe_replace_outermost_context({'attrs': {}})

                self.assertEqual(method(), 'c')
                self.assertEqual(method(), 'c')
            self.assertEqual(tracer.call_count, 3)
            self.assertEqual(method(), 'c')
            self.assertEqual(method(), 'c')
            self.assertEqual(tracer.call_count, 3)

    ## TODO later?: testing for multithreading etc....


class TestAuthAPI__get_user_ids_to_org_ids(_AuthAPILdapDataBasedMethodTestMixIn,
                                           unittest.TestCase):

    search_flat_return_values__and__expected_results = [
        (
            [
                ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o42,ou=orgs,dc=n6,dc=cert,dc=pl', {}),

                ('n6login=login1@foo.bar,o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('n6login=login2@foo.bar,o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('n6login=login3@foo.bar,o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('n6login=login4@foo.bar,o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('n6login=login5@foo.bar,o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('n6login=login6@foo.bar,o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6blocked': ['FALSE'],
                }),
                ('n6login=blocked-guy@foo.bar,o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6blocked': ['TRUE'],
                }),
            ],
            {
                'login1@foo.bar': 'o1',
                'login2@foo.bar': 'o2',
                'login3@foo.bar': 'o3',
                'login4@foo.bar': 'o4',
                'login5@foo.bar': 'o1',
                'login6@foo.bar': 'o4',
            },
        ),
    ]

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_user_ids_to_org_ids()
                self.assertEqual(actual_result, expected_result)
        self.assertEqual(LOGGER_error_mock.call_count, 0)

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test_error_logging(self, LOGGER_error_mock):
        search_flat_return_value = [
            # two user logins will be doubled...
            (dn.replace('login4', 'login3').replace('login6', 'login5'), attrs)
            for dn, attrs in self.search_flat_return_values__and__expected_results[0][0]]
        with self.standard_context(search_flat_return_value):
            self.auth_api.get_user_ids_to_org_ids()
        self.assertEqual(LOGGER_error_mock.call_count, 2)  # <- two error messages logged


class TestAuthAPI__get_org_ids(_AuthAPILdapDataBasedMethodTestMixIn,
                               unittest.TestCase):

    search_flat_return_values__and__expected_results = [
        (
            [
                ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
            ],
            frozenset({
                'o1', 'o2', 'o3', 'o4',
            }),
        ),
    ]

    def test(self):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_org_ids()
                self.assertEqual(actual_result, expected_result)


class TestAuthAPI__get_inside_criteria_resolver(_AuthAPILdapDataBasedMethodTestMixIn,
                                                unittest.TestCase):

    def test(self):
        with self.standard_context([]):
            self.auth_api._data_preparer._get_inside_criteria = Mock(
                return_value=sen.inside_criteria)
            with patch(
                    'n6lib.auth_api.InsideCriteriaResolver',
                    return_value=sen.resolver_instance) as InsideCriteriaResolver_mock:
                actual_result = self.auth_api.get_inside_criteria_resolver()
                self.assertEqual(self.auth_api._data_preparer._get_inside_criteria.mock_calls, [
                    call({'attrs': {}}),
                ])
                self.assertEqual(InsideCriteriaResolver_mock.mock_calls, [
                    call(sen.inside_criteria),
                ])
                self.assertIs(actual_result, sen.resolver_instance)


class TestAuthAPI__get_anonymized_source_mapping(_AuthAPILdapDataBasedMethodTestMixIn,
                                                 unittest.TestCase):

    search_flat_return_values__and__expected_results = [
        (
            [
                ('cn=s1.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6anonymized': ['a1.bar'],
                }),
                ('cn=s2.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6anonymized': ['a2.bar'],
                }),
                ('cn=s3.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6anonymized': ['a3.bar', 'extra.bar'],  # error: too many
                }),
                ('cn=s4.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6anonymized': [],  # error: empty
                }),
                ('cn=s5.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    # error: lack of
                }),
                ('cn=s6.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6anonymized': ['a6.bar'],
                }),
            ],
            {
                'forward_mapping': {
                     's1.foo': 'a1.bar',
                     's2.foo': 'a2.bar',
                     's6.foo': 'a6.bar',
                },
                'reverse_mapping': {
                     'a1.bar': 's1.foo',
                     'a2.bar': 's2.foo',
                     'a6.bar': 's6.foo',
                },
            },
        ),
    ]

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_anonymized_source_mapping()
                self.assertEqual(actual_result, expected_result)
        self.assertEqual(LOGGER_error_mock.call_count, 3)


class TestAuthAPI__get_dip_anonymization_disabled_source_ids(_AuthAPILdapDataBasedMethodTestMixIn,
                                                             unittest.TestCase):

    search_flat_return_values__and__expected_results = [
        (
            [
                ('cn=s1.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['TRUE'],         # ok -> True
                }),
                ('cn=s2.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['FALSE'],        # ok -> False
                }),
                ('cn=s3.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['FALSE', 'FALSE'],  # error: too many -> True
                }),
                ('cn=s4.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['falsE'],        # ok -> False
                }),
                ('cn=s5.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['FALSEE'],       # error: illegal value -> True
                }),
                ('cn=s6.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': [],               # empty -> False
                }),
                ('cn=s7.foo,ou=sources,dc=n6,dc=cert,dc=pl', {       # missing -> False
                }),
                ('cn=s8.foo,ou=sources,dc=n6,dc=cert,dc=pl', {
                    'n6dip-anonymization-enabled': ['true'],         # ok -> True
                }),
            ],
            frozenset(['s2.foo', 's4.foo', 's6.foo', 's7.foo']),  # *disabled* <=> flag is False
        ),
    ]

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_dip_anonymization_disabled_source_ids()
                self.assertEqual(actual_result, expected_result)
        self.assertEqual(LOGGER_error_mock.call_count, 2)


class TestAuthAPI__get_access_info(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=AuthAPI)
        self.meth = MethodProxy(AuthAPI, self.mock)
        self.auth_data = {'user_id': sen.user_id, 'org_id': sen.org_id}

    def test_returns_dict_for_existing_org_id(self):
        example_access_info = {
            'access_zone_conditions': {
                'inside': sen.list_of_conditions,
            },
            'rest_api_resource_limits': {
                '/report/inside': sen.dict_of_res_limits
            },
            'rest_api_full_access': False,
        }
        self.mock.configure_mock(**{
            'get_org_ids_to_access_infos.return_value': {
                sen.org_id: example_access_info,
                sen.another_org_id: sen.another_access_info,
            }
        })
        access_info = self.meth.get_access_info(self.auth_data)
        self.assertIs(access_info, example_access_info)

    def test_returns_None_for_missing_org_id(self):
        self.mock.configure_mock(**{
            'get_org_ids_to_access_infos.return_value': {
                sen.another_org_id: sen.another_access_info,
            }
        })
        access_info = self.meth.get_access_info(self.auth_data)
        self.assertIs(access_info, None)


class TestAuthAPI__get_org_ids_to_access_infos(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_ORG_IDS_TO_ACCESS_INFOS

        _make_converter = _DataPreparer._make_access_filtering_cond_to_sqla_converter

        def _make_wrapped_converter(*args, **kwargs):
            converter = _make_converter(*args, **kwargs)
            return (lambda cond: sqlalchemy_expr_to_str(converter(cond)))

        with patch.object(_DataPreparer, '_make_access_filtering_cond_to_sqla_converter',
                          _make_wrapped_converter), \
             self.standard_context(search_flat_return_value):

            actual_result = self.auth_api.get_org_ids_to_access_infos()

        self.assertEqual(actual_result, expected_result)
        self.assert_problematic_orgs_logged(LOGGER_error_mock, {'o3', 'o4', 'o6'})


class TestAuthAPI__get_org_ids_to_access_infos__without_optimization(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION

        _make_converter = _DataPreparer._make_access_filtering_cond_to_sqla_converter

        def _make_wrapped_converter(*args, **kwargs):
            converter = _make_converter(*args, **kwargs)
            return (lambda cond: sqlalchemy_expr_to_str(converter(cond)))

        with patch.object(_DataPreparer, '_make_access_filtering_cond_to_sqla_converter',
                          _make_wrapped_converter), \
             patch.dict(os.environ,
                        {'N6_SKIP_OPTIMIZATION_OF_ACCESS_FILTERING_CONDITIONS': 'y'}), \
             self.standard_context(search_flat_return_value):

            actual_result = self.auth_api.get_org_ids_to_access_infos()

        self.assertEqual(actual_result, expected_result)
        self.assert_problematic_orgs_logged(LOGGER_error_mock, {'o3', 'o4', 'o6'})


class TestAuthAPI__get_org_ids_to_access_infos__with_legacy_conditions(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    def test(self, LOGGER_error_mock):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS

        _get_condition = _DataPreparer._get_condition_for_subsource_and_full_access_flag

        with patch.object(_DataPreparer, '_get_condition_for_subsource_and_full_access_flag',
                          lambda *a, **kw: sqlalchemy_expr_to_str(_get_condition(*a, **kw))), \
             patch.dict(os.environ,
                        {'N6_USE_LEGACY_VERSION_OF_ACCESS_FILTERING_CONDITIONS': 'y'}), \
             self.standard_context(search_flat_return_value):

            actual_result = self.auth_api.get_org_ids_to_access_infos()

        self.assertEqual(actual_result, expected_result)
        self.assert_problematic_orgs_logged(LOGGER_error_mock, {'o3', 'o4', 'o6'})


class TestAuthAPI__get_org_actual_name(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=AuthAPI)
        self.meth = MethodProxy(AuthAPI, self.mock)
        self.auth_data = {'user_id': sen.user_id, 'org_id': sen.org_id}

    def test_returns_dict_for_existing_org_id(self):
        self.mock.configure_mock(**{
            'get_org_ids_to_actual_names.return_value': {
                sen.org_id: sen.actual_name,
                sen.another_org_id: sen.another_actual_name,
            }
        })
        actual_name = self.meth.get_org_actual_name(self.auth_data)
        self.assertIs(actual_name, sen.actual_name)

    def test_returns_None_for_missing_org_id(self):
        self.mock.configure_mock(**{
            'get_org_ids_to_actual_names.return_value': {
                sen.another_org_id: sen.another_actual_name,
            }
        })
        actual_name = self.meth.get_org_actual_name(self.auth_data)
        self.assertIs(actual_name, None)


class TestAuthAPI__get_org_ids_to_actual_names(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    def test(self):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_ORG_IDS_TO_ACTUAL_NAMES

        with self.standard_context(search_flat_return_value):
            actual_result = self.auth_api.get_org_ids_to_actual_names()

        self.assertEqual(actual_result, expected_result)


class TestAuthAPI__get_source_ids_to_subs_to_stream_api_access_infos(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    @patch('n6lib.db_filtering_abstractions._PredicateCondMixin.predicate',
           property(lambda self: self))
    def test(self, LOGGER_error_mock):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_SOURCE_IDS_TO_SUBS_TO_STREAM_API_ACCESS_INFOS

        with self.standard_context(search_flat_return_value):
            actual_result = self.auth_api.get_source_ids_to_subs_to_stream_api_access_infos()

        self.assertEqual(actual_result, expected_result)
        self.assert_problematic_orgs_logged(LOGGER_error_mock, {'o6', 'o8', 'o9'})


class TestAuthAPI__get_stream_api_enabled_org_ids(_AuthAPILdapDataBasedMethodTestMixIn,
                                                  unittest.TestCase):

    search_flat_return_values__and__expected_results = [
            (
                [
                    ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['TRUE'],
                    }),
                    ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['FALSE'],
                    }),
                    ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['INVALID VALUE'],
                    }),
                    ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {  # does not contain this parameter
                        'n6email-notifications-times': ['12', '9:15'],
                    }),
                    ('o=o5,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['TRUE'],
                    }),
                    ('o=o6,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['FALSE'],
                    }),
                ],
                frozenset(['o1', 'o5'])
            )
        ]

    def test(self):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_stream_api_enabled_org_ids()
                self.assertEqual(actual_result, expected_result)


class TestAuthAPI__get_stream_api_disabled_org_ids(_AuthAPILdapDataBasedMethodTestMixIn,
                                                   unittest.TestCase):

    search_flat_return_values__and__expected_results = [
            (
                [
                    ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['TRUE'],
                    }),
                    ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['FALSE'],
                    }),
                    ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['INVALID VALUE'],
                    }),
                    ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {  # does not contain this parameter
                        'n6email-notifications-times': ['12', '9:15'],
                    }),
                    ('o=o5,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['TRUE'],
                    }),
                    ('o=o6,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6stream-api-enabled': ['FALSE'],
                    }),

                ],
                frozenset(['o2', 'o3', 'o4', 'o6'])
            )
        ]

    def test(self):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_stream_api_disabled_org_ids()
                self.assertEqual(actual_result, expected_result)



class TestAuthAPI__get_source_ids_to_notification_access_info_mappings(
        _AuthAPILdapDataBasedMethodTestMixIn,
        unittest.TestCase):

    @patch('n6lib.auth_api.LOGGER.error', new_callable=_make_LOGGER_error_mock)
    @patch('n6lib.db_filtering_abstractions._PredicateCondMixin.predicate',
           property(lambda self: self))
    def test(self, LOGGER_error_mock):
        # see: n6lib.auth_related_test_helpers
        search_flat_return_value = EXAMPLE_SEARCH_RAW_RETURN_VALUE
        expected_result = EXAMPLE_SOURCE_IDS_TO_NOTIFICATION_ACCESS_INFO_MAPPINGS

        with self.standard_context(search_flat_return_value):
            actual_result = self.auth_api.get_source_ids_to_notification_access_info_mappings()

        self.assertEqual(actual_result, expected_result)
        self.assert_problematic_orgs_logged(LOGGER_error_mock, {'o3', 'o4', 'o8'})


class TestAuthAPI__get_org_ids_to_notification_configs(_AuthAPILdapDataBasedMethodTestMixIn,
                                                       unittest.TestCase):

    search_flat_return_values__and__expected_results = [
            (
                [
                    ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6email-notifications-enabled': ['TRUE'],
                        'n6email-notifications-times': ['12', '9:15'],
                        'n6email-notifications-address': ['address@dn.pl', 'address@x.cn'],
                        'n6stream-api-enabled': ['False'],
                    }),
                ],
                {
                    'o1': {
                        'n6email-notifications-times': [
                            datetime.time(9, 15),
                            datetime.time(12, 0),
                        ],
                        'n6email-notifications-address': ['address@dn.pl', 'address@x.cn'],
                        'name': False,
                        'n6stream-api-enabled': False,
                        'n6email-notifications-business-days-only': False,
                    },
                },
            ),
            (
                [
                    ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6email-notifications-enabled': ['TRUE'],
                        'n6email-notifications-local-tz': ['foo', 'bar'],
                        'n6email-notifications-times': ['09:15', '12:00'],
                        'n6email-notifications-address': ['address@dn2.pl'],
                        'name': ['testname2'],
                        'n6email-notifications-business-days-only': ['FALSE'],
                        'n6email-notifications-language': ['pl'],
                    }),
                    ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6email-notifications-enabled': ['TRUE'],
                        'n6email-notifications-times': ['10:15', '13'],
                        'n6email-notifications-address': ['address@dn32.pl', 'address@dn31.pl'],
                        'name': ['testname3'],
                        'n6stream-api-enabled': ['TRUE'],
                        'n6email-notifications-business-days-only': ['TRUE'],
                        'n6email-notifications-language': ['en'],
                    }),
                ],
                {
                    'o2': {
                        'n6email-notifications-times': [
                            datetime.time(9, 15),
                            datetime.time(12, 0),
                        ],
                        'n6email-notifications-address': ['address@dn2.pl'],
                        'name': 'testname2',
                        'n6stream-api-enabled': False,
                        'n6email-notifications-business-days-only': False,
                        'n6email-notifications-language': 'pl',
                    },
                    'o3': {
                        'n6email-notifications-times': [
                            datetime.time(10, 15),
                            datetime.time(13, 0),
                        ],
                        'n6email-notifications-address': ['address@dn31.pl', 'address@dn32.pl'],
                        'n6stream-api-enabled': True,
                        'name': 'testname3',
                        'n6email-notifications-business-days-only': True,
                        'n6email-notifications-language': 'en',
                    },

                },
            ),
            (
                [
                    ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6email-notifications-enabled': ['FALSE'],
                        'n6email-notifications-local-tz': ['TRUE'],
                        'n6email-notifications-times': ['09:15', '12:00'],
                        'n6email-notifications-address': ['address@dn4.pl'],
                    }),
                ],
                {},
            ),
            (
                [
                    ('o=o5,ou=orgs,dc=n6,dc=cert,dc=pl', {
                        'n6email-notifications-enabled': ['TRUE'],
                        'n6email-notifications-local-tz': ['TRUE'],
                        'n6email-notifications-times': ['12:00', '9.15'],
                        'n6email-notifications-address': ['address@dn5.pl'],
                        'name': ['testname5'],
                        'n6stream-api-enabled': ['true'],
                    }),
                ],
                {
                    'o5': {
                         'n6email-notifications-times': [
                             datetime.time(9, 15),
                             datetime.time(12, 0)
                         ],
                         'n6email-notifications-address': ['address@dn5.pl'],
                         'n6stream-api-enabled': True,
                         'name': 'testname5',
                         'n6email-notifications-business-days-only': False,
                    }
                },
            ),
        ]

    # Let the last case contain the data from all previous cases
    # (needed by the `./auth_related_quicktest.py` script).
    accumulated_search_flat_return_value = []
    accumulated_expected_result = {}
    for (search_flat_return_value,
         expected_result) in search_flat_return_values__and__expected_results:
        assert (isinstance(search_flat_return_value, list) and
                isinstance(expected_result, dict))
        accumulated_search_flat_return_value.extend(search_flat_return_value)
        accumulated_expected_result.update(expected_result)
    search_flat_return_values__and__expected_results.append((
        accumulated_search_flat_return_value,
        accumulated_expected_result,
    ))

    def test(self):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                actual_result = self.auth_api.get_org_ids_to_notification_configs()
                self.assertEqual(actual_result, expected_result)


class TestAuthAPI___get_inside_criteria(_AuthAPILdapDataBasedMethodTestMixIn,
                                        unittest.TestCase):

    search_flat_return_values__and__expected_results = [
        (
            [
                ('o=o1,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6asn': ['12', '34'],
                    'n6cc': ['PL', 'US'],
                    'n6fqdn': ['example.com', 'xyz.example.net'],
                    'n6ip-network': ['0.10.20.30/8', '1.2.3.4/16', '101.102.103.104/32'],
                    'n6url': ['example.info', 'institution.example.pl/auth.php', 'Łódź'],
                }),
                ('o=o2,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6asn': ['1234567'],
                }),
                ('o=o3,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6fqdn': ['example.org'],
                }),
                ('o=o4,ou=orgs,dc=n6,dc=cert,dc=pl', {}),
                ('o=abcdefghijklmnoabcdefghijklmno12,ou=orgs,dc=n6,dc=cert,dc=pl', {
                    'n6fqdn': ['example.org'],
                })
            ],
            [
                {
                    'org_id': 'o1',
                    'asn_seq': [12, 34],
                    'cc_seq': ['PL', 'US'],
                    'fqdn_seq': ['example.com', 'xyz.example.net'],
                    'ip_min_max_seq': [
                        (1, 16777215),  # <- Note: here the minimum IP is 1, not 0 (see: #8861).
                        (16908288, 16973823),
                        (1701209960, 1701209960),
                    ],
                    'url_seq': ['example.info', 'institution.example.pl/auth.php', 'Łódź'],
                },
                {
                    'org_id': 'o2',
                    'asn_seq': [1234567],
                },
                {
                    'org_id': 'o3',
                    'fqdn_seq': ['example.org'],
                },
                {
                    'org_id': 'o4',
                },
                {
                    'org_id': 'abcdefghijklmnoabcdefghijklmno12',
                    'fqdn_seq': ['example.org'],
                }
            ],
        ),
    ]

    def test(self):
        for (search_flat_return_value,
             expected_result) in self.search_flat_return_values__and__expected_results:
            with self.standard_context(search_flat_return_value):
                with patch('n6lib.auth_api._DataPreparer._check_org_length') \
                     as _check_org_length_mock:
                    root_node = self.auth_api.get_ldap_root_node()
                    actual_result = self.auth_api._data_preparer._get_inside_criteria(root_node)
                    self.assertCountEqual(actual_result, expected_result)
                    self.assertTrue(_check_org_length_mock.called)


class TestAuthAPI___make_request_parameters_dict(unittest.TestCase):

    rest_api_resources__and__expected_results = [
        (
            {
                'attrs': {
                    'n6request-parameters': ['foo', 'bar'],
                    'n6request-required-parameters': ['foo'],
                },
            },
            {
                'foo': True,
                'bar': False,
            },
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': ['foo', 'bar'],
                    'n6request-required-parameters': ['foo', 'bar'],
                },
            },
            {
                'foo': True,
                'bar': True,
            },
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': ['foo', 'bar'],
                    'n6request-required-parameters': [],
                },
            },
            {
                'foo': False,
                'bar': False,
            },
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': ['foo', 'bar'],
                },
            },
            {
                'foo': False,
                'bar': False,
            },
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': [],
                    'n6request-required-parameters': [],
                },
            },
            None,
        ),
        (
            {
                'attrs': {
                    'n6request-required-parameters': [],
                },
            },
            None,
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': [],
                },
            },
            None,
        ),
        (
            {
                'attrs': {},
            },
            None,
        ),
    ]

    rest_api_resources__and__expected_exceptions = [
        (
            {
                'attrs': {
                    'n6request-parameters': ['foo', 'bar'],
                    'n6request-required-parameters': ['foo', 'bar', 'another'],
                },
            },
            ValueError
        ),
        (
            {
                'attrs': {
                    'n6request-parameters': [],
                    'n6request-required-parameters': ['foo'],
                },
            },
            ValueError
        ),
        (
            {
                'attrs': {
                    'n6request-required-parameters': ['foo'],
                },
            },
            ValueError
        ),
    ]

    def setUp(self):
        self.mock = Mock(__class__=_DataPreparer)
        self.meth = MethodProxy(_DataPreparer, self.mock)

    def test_for_valid_rest_api_resources(self):
        for rest_api_resource, expected_result in self.rest_api_resources__and__expected_results:
            actual_result = self.meth._make_request_parameters_dict(rest_api_resource)
            self.assertEqual(actual_result, expected_result)
        self.assertEqual(self.mock.mock_calls, [])

    def test_for_invalid_rest_api_resources(self):
        for rest_api_resource, expected_exc in self.rest_api_resources__and__expected_exceptions:
            with self.assertRaises(expected_exc):
                self.meth._make_request_parameters_dict(rest_api_resource)
        self.assertEqual(self.mock.mock_calls, [])


class TestAuthAPI___parse_notification_time(_AuthAPILdapDataBasedMethodTestMixIn,
                                            unittest.TestCase):
    def test(self):
        with self.standard_context([]):
            actual_result = self.data_preparer._parse_notification_time('1')
            self.assertEqual(actual_result, datetime.time(1, 0))
            actual_result = self.data_preparer._parse_notification_time('0')
            self.assertEqual(actual_result, datetime.time(0, 0))
            actual_result = self.data_preparer._parse_notification_time('23')
            self.assertEqual(actual_result, datetime.time(23, 0))
            actual_result = self.data_preparer._parse_notification_time('15:12')
            self.assertEqual(actual_result, datetime.time(15, 12))
            actual_result = self.data_preparer._parse_notification_time(' 23 : 59 ')
            self.assertEqual(actual_result, datetime.time(23, 59))
            actual_result = self.data_preparer._parse_notification_time('3.00 ')
            self.assertEqual(actual_result, datetime.time(3, 0))
            # exceptions
            self.assertRaises(ValueError, self.data_preparer._parse_notification_time, '24')
            self.assertRaises(ValueError, self.data_preparer._parse_notification_time, '12:12:67')
            self.assertRaises(ValueError, self.data_preparer._parse_notification_time, '12,43')


##
## TODO: (maybe later?) tests of the remaining AuthAPI non-public methods
##


#
# InsideCriteriaResolver tests
#

# * shared test data

MAX_IP = 2 ** 32 - 1

VARIOUS_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o0',
        'fqdn_seq': [u'www.xn--examp-n0a00a.net', u'xn--examp-n0a00a.org'],
        'asn_seq': [1, 12, 123],
        'cc_seq': ['UK', 'US'],
        'ip_min_max_seq': [(169090598, 169090599)],  # 10.20.30.39/31
        'url_seq': [u'https://example.pl'],
    },
    {
        'org_id': 'o1',
        'asn_seq': [1, 12, 123, 1234, 12345, 123456],
        'cc_seq': ['UK', 'US'],
        'ip_min_max_seq': [(169090602, 169090602)],  # 10.20.30.42/32
    },
    {
        'org_id': 'o2',
        'asn_seq': [1, 12, 123, 123456, 222333],
        'ip_min_max_seq': [(169090600, 169090601)],  # 10.20.30.40/31
    },
    {
        'org_id': 'o3',
        'cc_seq': ['PL'],
    },
    {
        'org_id': 'o4',
        'fqdn_seq': [u'example.com'],
    },
    {
        'org_id': 'o5',
        'url_seq': [u'http://dns.pl'],
    },
    {
        'org_id': 'o42',
        # (no criteria for this org)
    },
]

EXPECTED_RESULTS_AND_GIVEN_RD_CONTENTS_FOR_VARIOUS_CRITERIA = [
    # list of pairs [corresponds to VARIOUS_CRITERIA]:
    #     (<expected `client_org_ids` set>,
    #      <list of cases: each being a dict containing the relevant items
    #       of the given record dict>)
    #   or:
    #     ((<expected `client_org_ids` set>, <expected `urls_matched` dict>),
    #      <list of cases: each being a dict containing the relevant items
    #       of the given record dict>)
    # NOTE: here we assume that fqdn_only_categories={'leak', 'malurl'}
    # (only for the tests, of course)
    (set(), [
        {
            'category': 'bots',
        },
        {
            'category': 'scanning',
            'fqdn': 'example.pl',
            'address': [
                {
                    'ip': '10.20.30.37',
                    'cc': 'JP',
                },
                {
                    'ip': '10.20.30.43',
                    'asn': 54321,
                },
            ],
            'url_pattern': '*.com',
        },
        {
            'category': 'bots',
            'fqdn': 'xn--examp-n0a00a.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'JP',
                    'asn': 99999,
                },
            ],
            'url_pattern': r'http://\w+\.\w+\.\w+',
        },
        {
            'category': 'scanning',
            'fqdn': 'example.pl',
        },
        {
            'category': 'bots',
            'fqdn': 'xn--examp-n0a00a.com',
        },
        {
            'category': 'scanning',
            'fqdn': 'www.xn--examp-n0a00a.com',
        },
        {
            'category': 'bots',
            'fqdn': 'xn--examp-n0a00a.net',
        },
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'asn': 54321}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'asn': 99999}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'cc': 'JP'}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1'}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '10.20.30.37'}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '10.20.30.43'}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '100.101.102.103'}],
        },
        {
            'category': 'bots',
            'url_pattern': '*.com',
        },
        {
            'category': 'scanning',
            'url_pattern': r'http://\w+\.\w+\.\w+',
        },
        {
            'category': 'leak',
        },
        {
            'category': 'malurl',
            'fqdn': 'example.pl',
            'address': [
                {
                    'ip': '10.20.30.37',
                    'cc': 'JP',
                },
                {
                    'ip': '10.20.30.43',
                    'asn': 54321,
                },
            ],
            'url_pattern': '*.com',
        },
        {
            'category': 'leak',
            'fqdn': 'xn--examp-n0a00a.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'JP',
                    'asn': 99999,
                },
            ],
            'url_pattern': r'http://\w+\.\w+\.\w+',
        },
        {
            'category': 'malurl',
            'fqdn': 'example.pl',
            'address': [
                {
                    'ip': '10.20.30.38',
                    'cc': 'JP',
                },
                {
                    'ip': '10.20.30.43',
                    'asn': 54321,
                },
            ],
            'url_pattern': '*.com',
        },
        {
            'category': 'leak',
            'address': [
                {
                    'ip': '10.20.30.40',
                    'cc': 'US',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'malurl',
            'fqdn': 'example.pl',
        },
        {
            'category': 'leak',
            'fqdn': 'xn--examp-n0a00a.com',
        },
        {
            'category': 'malurl',
            'fqdn': 'www.xn--examp-n0a00a.com',
        },
        {
            'category': 'leak',
            'fqdn': 'xn--examp-n0a00a.net',
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'asn': 1}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'asn': 12}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'asn': 123}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'asn': 1234}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'asn': 12345}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'asn': 54321}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'asn': 99999}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'asn': 222333}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'asn': 123456}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'cc': 'JP'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'cc': 'PL'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1', 'cc': 'UK'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '4.3.2.1', 'cc': 'US'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '4.3.2.1'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '10.20.30.37'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '10.20.30.38'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '10.20.30.39'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '10.20.30.40'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '10.20.30.41'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '10.20.30.42'}],
        },
        {
            'category': 'malurl',
            'address': [{'ip': '10.20.30.43'}],
        },
        {
            'category': 'leak',
            'address': [{'ip': '100.101.102.103'}],
        },
        {
            'category': 'malurl',
            'url_pattern': '*.com',
        },
        {
            'category': 'leak',
            'url_pattern': 'https:*',
        },
        {
            'category': 'malurl',
            'url_pattern': 'https:.*',
        },
        {
            'category': 'leak',
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'malurl',
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'leak',
            'url_pattern': r'http://\w+\.\w+\.\w+',
        },
        {
            'category': 'malurl',
            'url_pattern': '*dns.pl',
        },
        {
            'category': 'leak',
            'url_pattern': r'dns\.pl',
        },
        {
            'category': 'malurl',
            'url_pattern': '*.pl',
        },
        {
            'category': 'leak',
            'url_pattern': r'\.pl',
        },
    ]),

    ({'o0'}, [
        {
            'category': 'bots',
            'fqdn': 'xn--examp-n0a00a.org',
        },
        {
            'category': 'scanning',
            'fqdn': 'spam.ham.1.2.3.5.foo.bar.xn--examp-n0a00a.org',
        },
        {
            'category': 'bots',
            'fqdn': 'www.xn--examp-n0a00a.net',
        },
        {
            'category': 'scanning',
            'fqdn': 'ha-ha-ha.bar.foo.www.xn--examp-n0a00a.net',
        },
        {
            'category': 'bots',
            'address': [{'ip': '10.20.30.38'}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '10.20.30.39'}],
        },
        {
            'category': 'bots',
            'fqdn': 'example.pl',
            'address': [
                {
                    'ip': '10.20.30.38',
                    'cc': 'JP',
                },
                {
                    'ip': '10.20.30.43',
                    'asn': 54321,
                },
            ],
            'url_pattern': '*.com',
        },
        {
            'category': 'malurl',
            'fqdn': 'xn--examp-n0a00a.org',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'leak',
            'fqdn': 'spam.ham.1.2.3.5.foo.bar.xn--examp-n0a00a.org',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123456,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'malurl',
            'fqdn': '1.2.3.4.5.6.7.8.xn--examp-n0a00a.org',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': '*.pl',
        },
        {
            'category': 'leak',
            'fqdn': 'www.xn--examp-n0a00a.net',
            'address': [
                {
                    'ip': '10.20.30.40',
                    'cc': 'US',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'malurl',
            'fqdn': 'ha-ha-ha.bar.foo.www.xn--examp-n0a00a.net',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'leak',
            'fqdn': 'xn--examp-n0a00a.org',
        },
        {
            'category': 'malurl',
            'fqdn': 'spam.ham.1.2.3.5.foo.bar.xn--examp-n0a00a.org',
        },
        {
            'category': 'leak',
            'fqdn': 'www.xn--examp-n0a00a.net',
        },
        {
            'category': 'malurl',
            'fqdn': 'ha-ha-ha.bar.foo.www.xn--examp-n0a00a.net',
        },
    ]),

    (({'o0'}, {
        'o0': [u'https://example.pl'],
     }), [
        {
            'category': 'scanning',
            'url_pattern': 'https:*',
        },
        {
            'category': 'bots',
            'url_pattern': 'https:.*',
        },
    ]),

    ({'o1'}, [
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'asn': 1234}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'asn': 12345}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '10.20.30.42'}],
        },
    ]),

    ({'o2'}, [
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'asn': 222333}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '10.20.30.41'}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '10.20.30.40'}],
        },
    ]),

    ({'o3'}, [
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'cc': 'PL'}],
        },
    ]),

    ({'o4'}, [
        {
            'category': 'bots',
            'fqdn': 'example.com',
        },
        {
            'category': 'scanning',
            'fqdn': 'www.example.com',
        },
        {
            'category': 'bots',
            'fqdn': 'www.example.a_n_d.t-h-e-n.just.www.example.com',
        },
        {
            'category': 'scanning',
            'fqdn': 'do.re.mi.fa.sol.la.si.do.example.com',
        },
        {
            'category': 'bots',
            # (first, it will be IDNA-encoded by RecordDict's fqdn_adjuster)
            'fqdn': u'dó.rę.µi.fą.sól.ła.śi.ðo.example.com',
        },
        {
            'category': 'scanning',
            'fqdn': '1.2.3.4.5.6.7.8.9.example.com',
        },
        {
            'category': 'leak',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'malurl',
            'fqdn': 'example.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123456,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'leak',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': '*.pl',
        },
        {
            'category': 'malurl',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                    'cc': 'US',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'leak',
            'fqdn': 'example.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'malurl',
            'fqdn': 'example.com',
        },
        {
            'category': 'leak',
            'fqdn': 'www.example.com',
        },
        {
            'category': 'malurl',
            'fqdn': 'www.example.a_n_d.t-h-e-n.just.www.example.com',
        },
        {
            'category': 'leak',
            'fqdn': 'do.re.mi.fa.sol.la.si.do.example.com',
        },
        {
            'category': 'malurl',
            # (first, it will be IDNA-encoded by RecordDict's fqdn_adjuster)
            'fqdn': u'dó.rę.µi.fą.sól.ła.śi.ðo.example.com',
        },
        {
            'category': 'leak',
            'fqdn': '1.2.3.4.5.6.7.8.9.example.com',
        },
    ]),

    (({'o5'}, {
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'bots',
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'scanning',
            'url_pattern': r'http://\w+\.\w+',
        },
        {
            'category': 'bots',
            'url_pattern': '*dns.pl',
        },
        {
            'category': 'scanning',
            'url_pattern': r'dns\.pl',
        },
    ]),

    ({'o0', 'o1'}, [
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'cc': 'UK'}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'cc': 'US'}],
        },
    ]),

    (({'o0', 'o5'}, {
        'o0': [u'https://example.pl'],
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'bots',
            'url_pattern': '*.pl',
        },
        {
            'category': 'scanning',
            'url_pattern': r'\.pl',
        },
    ]),

    ({'o1', 'o2'}, [
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'asn': 123456}],
        },
    ]),

    ({'o0', 'o1', 'o2'}, [
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'asn': 1}],
        },
        {
            'category': 'bots',
            'address': [{'ip': '4.3.2.1', 'asn': 12}],
        },
        {
            'category': 'scanning',
            'address': [{'ip': '4.3.2.1', 'asn': 123}],
        },
    ]),

    (({'o0', 'o1', 'o2', 'o3', 'o5'}, {
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'bots',
            'address': [
                {
                    'ip': '10.20.30.40',
                    'cc': 'US',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
    ]),

    (({'o1', 'o2', 'o3', 'o4', 'o5'}, {
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'scanning',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'bots',
            'fqdn': 'example.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123456,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
    ]),

    (({'o0', 'o1', 'o2', 'o3', 'o4', 'o5'}, {
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'bots',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                    'cc': 'US',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': 'http:*.pl',
        },
        {
            'category': 'scanning',
            'fqdn': 'example.com',
            'address': [
                {
                    'ip': '4.3.2.1',
                    'cc': 'PL',
                    'asn': 123,
                },
            ],
            'url_pattern': r'http://\w+\.\w+',
        },
    ]),

    (({'o0', 'o1', 'o2', 'o3', 'o4', 'o5'}, {
        'o0': [u'https://example.pl'],
        'o5': [u'http://dns.pl'],
     }), [
        {
            'category': 'scanning',
            'fqdn': 'www.example.com',
            'address': [
                {
                    'ip': '10.20.30.40',
                },
                {
                    'ip': '100.101.102.103',
                    'cc': 'PL',
                },
                {
                    'ip': '4.3.2.1',
                    'asn': 12345,
                },
            ],
            'url_pattern': '*.pl',
        },
    ]),
]

NO_EXPECTED_RESULTS_AND_IRRELEVANT_RD_CONTENTS = [
    # similar to EXPECTED_RESULTS_AND_GIVEN_RD_CONTENTS_FOR_VARIOUS_CRITERIA
    # but without any relevant record dict contents
    (set(), [
        {},
        {'name': u'Ala ma kota a kot ma alę'},
    ]),
]

FQDN_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o11',
        'fqdn_seq': [u'www.xn--examp-n0a00a.org', u'www.org'],
    },
    {
        'org_id': 'o12',
        'fqdn_seq': [u'www.xn--examp-n0a00a.net', u'www.net'],
    },
    {
        'org_id': 'o13',
        'fqdn_seq': [u'www.xn--examp-n0a00a.org'],
    },
    {
        'org_id': 'o14',
        'fqdn_seq': [u'www.xn--examp-n0a00a.xn--t-0ia2k'],
    },
    {
        'org_id': 'o15',
        'fqdn_seq': [u'xn--examp-n0a00a.org'],
    },
    {
        'org_id': 'o16',
        'fqdn_seq': [u'xn--examp-n0a00a.net'],
    },
    {
        'org_id': 'o17',
        'fqdn_seq': [u'xn--examp-n0a00a.org.pl', u'xn--examp-n0a00a.org.pl'],
    },
    {
        'org_id': 'o18',
        'fqdn_seq': [u'xn--examp-n0a00a.net.pl', u'xn--examp-n0a00a.net.pl'],
    },
    {
        'org_id': 'o19',
        'fqdn_seq': [u'org.xn--examp-n0a00a'],
    },
    {
        'org_id': 'o20',
        'fqdn_seq': [u'xn--examp-n0a00a.www'],
    },
    {
        'org_id': 'o21',
        'fqdn_seq': [u'org', u'net'],
    },
    {
        'org_id': 'o22',
        'fqdn_seq': [u'org'],
    },
    {
        'org_id': 'o23',
        'fqdn_seq': [u'net'],
    },
]

EXPECTED_RESULTS_AND_GIVEN_FQDNS = [
    # list of pairs [corresponds to FQDN_CRITERIA]:
    #     (<expected `client_org_ids` set>,
    #      <list of cases: each being `fqdn` of the given record dict>)
    (set(), [
        '',
        'oorg',
        'orrg',
        'orgg',
        'nnet',
        'neet',
        'nett',
        'www',
        'org.www',
        'net.www',
        'xn--t-0ia2k.www',
        'org.net.www',
        'org.xn--t-0ia2k.www',
        'net.org.www',
        'xn--examp-n0a00a',
        'org.qwerty.xn--examp-n0a00a',
        'org.qwerty',
        'www.xn--examp-n0a00a',
        'org.www.xn--examp-n0a00a',
        'org.qwerty.www.xn--examp-n0a00a',
        'xn--t-0ia2k',
        'www.xn--t-0ia2k',
        'org.www.xn--t-0ia2k',
        'org.xn--t-0ia2k',
        'www.org.xn--t-0ia2k',
        'qwerty.xn--t-0ia2k',
        'xn--t-0ia2k.org.www',
        'xn--t-0ia2k.qwerty',
        'xn--t-0ia2k.qwerty.xn--examp-n0a00a',
        'xn--t-0ia2k.qwerty.www.xn--examp-n0a00a',
        'xn--examp-n0a00a.qwerty.xn--t-0ia2k',
        'xn--examp-n0a00a.www.qwerty.xn--t-0ia2k',
        'org.xn--examp-n0a00a.qwerty.xn--t-0ia2k',
        'org.xn--examp-n0a00a.www.qwerty.xn--t-0ia2k',
        'net.xn--examp-n0a00a.qwerty.xn--t-0ia2k',
        'net.xn--examp-n0a00a.www.qwerty.xn--t-0ia2k',
        'xn--t-0ia2k.xn--examp-n0a00a.qwerty.xn--t-0ia2k',
        'xn--t-0ia2k.xn--examp-n0a00a.www.qwerty.xn--t-0ia2k',
        'org.xn--examp-n0a00a.www.qwerty',
        'org.xn--examp-n0a00a.qwerty',
        'xn--t-0ia2k.xn--examp-n0a00a',
        'xn--t-0ia2k.www.xn--examp-n0a00a',
        'www.xn--t-0ia2k.xn--examp-n0a00a',
        'xn--examp-n0a00a.xn--t-0ia2k',
        'xn--examp-n0a00a.www.xn--t-0ia2k',
        'qwerty.xn--examp-n0a00a.xn--t-0ia2k',
        'org.qwerty.xn--examp-n0a00a.xn--t-0ia2k',
        'www.qwerty.xn--examp-n0a00a.xn--t-0ia2k',
        'org.www.qwerty.xn--examp-n0a00a.xn--t-0ia2k',
        'www.org.qwerty.xn--examp-n0a00a.xn--t-0ia2k',
        'qwerty.www.org.xn--examp-n0a00a.xn--t-0ia2k',
        'org.pl',
        'net.pl',
        'xn--t-0ia2k.pl',
        'xn--t-0ia2k.qwerty.pl',
        'xn--t-0ia2k.qwerty.xn--examp-n0a00a.pl',
        'xn--t-0ia2k.qwerty.www.xn--examp-n0a00a.pl',
        'net.org.pl',
        'org.net.pl',
        'www.org.pl',
        'www.net.pl',
        'www.org.net.pl',
        'www.net.org.pl',
        'org.www.net.pl',
        'net.www.org.pl',
        'org.net.www.pl',
        'net.org.www.pl',
        'www.pl',
        'pl.www',
        'org.pl.www',
        'net.pl.www',
        'net.org.pl.www',
        'org.net.pl.www',
    ]),

    ({'o14'}, [
        'www.xn--examp-n0a00a.xn--t-0ia2k',
        'qwerty.www.xn--examp-n0a00a.xn--t-0ia2k',
        'org.qwerty.www.xn--examp-n0a00a.xn--t-0ia2k',
    ]),

    ({'o17'}, [
        'xn--examp-n0a00a.org.pl',
        'www.xn--examp-n0a00a.org.pl',
        'qwerty.xn--examp-n0a00a.org.pl',
        'qwerty.www.xn--examp-n0a00a.org.pl',
        'www.qwerty.xn--examp-n0a00a.org.pl',
        'net.qwerty.xn--examp-n0a00a.org.pl',
        'net.qwerty.www.xn--examp-n0a00a.org.pl',
        'net.www.qwerty.xn--examp-n0a00a.org.pl',
        'www.net.qwerty.xn--examp-n0a00a.org.pl',
        'xn--t-0ia2k.qwerty.www.xn--examp-n0a00a.org.pl',
        'xn--t-0ia2k.qwerty.xn--examp-n0a00a.org.pl',
    ]),

    ({'o19'}, [
        'org.xn--examp-n0a00a',
        'www.org.xn--examp-n0a00a',
        'qwerty.org.xn--examp-n0a00a',
    ]),

    ({'o20'}, [
        'xn--examp-n0a00a.www',
        'org.xn--examp-n0a00a.www',
        'net.xn--examp-n0a00a.www',
        'xn--t-0ia2k.xn--examp-n0a00a.www',
        'qwerty.xn--examp-n0a00a.www',
    ]),

    ({'o21', 'o22'}, [
        'org',
        'net.org',
        'www.net.org',
        'xn--t-0ia2k.org',
        'www.xn--t-0ia2k.org',
        'qwerty.org',
        'xn--examp-n0a00a.qwerty.org',
        'xn--examp-n0a00a.www.qwerty.org',
        'org.xn--examp-n0a00a.qwerty.org',
        'org.xn--examp-n0a00a.www.qwerty.org',
        'net.xn--examp-n0a00a.qwerty.org',
        'net.xn--examp-n0a00a.www.qwerty.org',
        'xn--t-0ia2k.xn--examp-n0a00a.qwerty.org',
        'xn--t-0ia2k.xn--examp-n0a00a.www.qwerty.org',
        'pl.org',
        'pl.net.org',
        'net.pl.org',
        'www.pl.org',
        'www.pl.net.org',
        'www.net.pl.org',
        'pl.www.net.org',
        'net.www.pl.org',
    ]),

    ({'o21', 'o23'}, [
        'net',
        'org.net',
        'www.org.net',
        'qwerty.net',
        'xn--examp-n0a00a.qwerty.net',
        'xn--examp-n0a00a.www.qwerty.net',
        'org.xn--examp-n0a00a.qwerty.net',
        'org.xn--examp-n0a00a.www.qwerty.net',
        'net.xn--examp-n0a00a.qwerty.net',
        'net.xn--examp-n0a00a.www.qwerty.net',
        'xn--t-0ia2k.xn--examp-n0a00a.qwerty.net',
        'xn--t-0ia2k.xn--examp-n0a00a.www.qwerty.net',
        'pl.net',
        'pl.org.net',
        'org.pl.net',
        'www.pl.net',
        'www.pl.org.net',
        'www.org.pl.net',
        'pl.www.org.net',
        'org.www.pl.net',
    ]),

    ({'o11', 'o21', 'o22'}, [
        'www.org',
        'net.www.org',
        'pl.www.org',
        'pl.net.www.org',
        'net.pl.www.org',
    ]),

    ({'o12', 'o21', 'o23'}, [
        'www.net',
        'org.www.net',
        'pl.www.net',
        'pl.org.www.net',
        'org.pl.www.net',
    ]),

    ({'o15', 'o21', 'o22'}, [
        'xn--examp-n0a00a.org',
        'qwerty.xn--examp-n0a00a.org',
        'net.qwerty.xn--examp-n0a00a.org',
        'xn--t-0ia2k.qwerty.xn--examp-n0a00a.org',
        'www.qwerty.xn--examp-n0a00a.org',
        'www.net.qwerty.xn--examp-n0a00a.org',
        'www.xn--t-0ia2k.qwerty.xn--examp-n0a00a.org',
    ]),

    ({'o16', 'o21', 'o23'}, [
        'xn--examp-n0a00a.net',
        'qwerty.xn--examp-n0a00a.net',
        'org.qwerty.xn--examp-n0a00a.net',
    ]),

    ({'o12', 'o16', 'o21', 'o23'}, [
        'www.xn--examp-n0a00a.net',
        'qwerty.www.xn--examp-n0a00a.net',
        'org.qwerty.www.xn--examp-n0a00a.net',
    ]),

    ({'o11', 'o13', 'o15', 'o21', 'o22'}, [
        'www.xn--examp-n0a00a.org',
        'qwerty.www.xn--examp-n0a00a.org',
        'net.qwerty.www.xn--examp-n0a00a.org',
        'xn--t-0ia2k.qwerty.www.xn--examp-n0a00a.org',
    ]),
]

EXTREME_IP_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o7',
        'ip_min_max_seq': [
            (1, 2),
            (102, MAX_IP),
        ],
    },
    {
        'org_id': 'o6',
        'ip_min_max_seq': [
            (MAX_IP, MAX_IP),
            (3, 100),
            (1, 1),
        ],
    },
]

EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_EXTREME_IP_CRITERIA = [
    # list of pairs [corresponds to EXTREME_IP_CRITERIA]:
    #     (<expected `client_org_ids` set>,
    #      <list of cases: each being a set of integers representing
    #       IP addresses from `address` of the given record dict>)
    (set(), [
        {101},
    ]),

    ({'o6'}, [
        {4},
        {3},
        {50},
        {100},
        {3, 30, 70, 100},
        {30, 40, 50, 60, 70, 101},
    ]),

    ({'o7'}, [
        {2},
        {102},
        {12345},
        {MAX_IP - 1},
        {150, 101, 12345},
        {2, 102, 12345, MAX_IP - 1},
    ]),

    ({'o6', 'o7'}, [
        {1},
        {MAX_IP},
        {1, MAX_IP},
        {1, 2},
        {2, 3},
        {2, 50},
        {2, 100},
        {3, 102},
        {50, 102},
        {100, 102},
        {100, 101, 102},
        {3, 12345},
        {50, 12345},
        {100, 12345},
        {100, 12345, MAX_IP},
        {1, 50, 150, MAX_IP},
    ]),
]

COMPLEX_IP_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o9',
        'ip_min_max_seq': [
            (115, 115),
            (30, 110),
            (140, 170),
        ],
    },
    {
        'org_id': 'o8',
        'ip_min_max_seq': [
            (100, 110),
            (20, 70),
            (82, 82),
            (97, 97),
            (150, 160),
            (40, 60),
            (40, 60),
            (120, 130),
            (84, 84),
            (85, 85),
            (20, 50),
            (190, 190),
            (95, 95),
            (190, 190),
            (86, 86),
        ],
    },
    {
        'org_id': 'o10',
        'ip_min_max_seq': [
            (10, 90),
            (80, 90),
            (95, 98),
            (100, 120),
            (105, 105),
            (139, 139),
            (169, 169),
            (180, 190),
        ],
    },
]

EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_COMPLEX_IP_CRITERIA = [
    # list of pairs [corresponds to COMPLEX_IP_CRITERIA]:
    #     (<expected `client_org_ids` set>,
    #      <list of cases: each being a set of integers representing
    #       IP addresses from `address` of the given record dict>)
    (set(), [
        {1},
        {5},
        {9},
        {1, 5, 9},
        {131},
        {135},
        {138},
        {5, 135},
        {1, 9, 131, 135, 138},
        {171},
        {174, 176},
        {179},
        {191},
        {12345},
        {MAX_IP},
        {1, MAX_IP},
        {5, 134, 175, 192},
        {5, 131, 135, 138, 171, 175, 179, 191, 12345},
        {1, 5, 9, 131, 135, 138, 171, 175, 179, 191, 12345, MAX_IP},
    ]),

    ({'o8'}, [
        {121},
        {130},
        {124, 125},
        {5, 124, 125, 12345},
        {1, 5, 9, 130, 131, 135, 138, 171, 175, 179, 191, 12345, MAX_IP},
    ]),

    ({'o9'}, [
        {91},
        {92},
        {93},
        {94},
        {99},
        {140},
        {144, 145, 146},
        {149},
        {161},
        {168},
        {170},
        {91, 94, 99, 145, 165, 170, MAX_IP},
        {1, 94, 145, 165, 12345},
    ]),

    ({'o10'}, [
        {10},
        {19},
        {10, 11, 15, 17, 18, 19},
        {111},
        {114},
        {116},
        {119},
        {10, 15, 112, 114, 116, 118},
        {139},
        {180},
        {185},
        {189},
        {10, 19, 111, 118, 139, 185, 189, 12345},
    ]),

    ({'o8', 'o9'}, [
        {150},
        {151},
        {152},
        {160},
        {150, 160},
        {4, 154},
        {121, 149},
        {4, 94, 130, 1234},
    ]),

    ({'o8', 'o10'}, [
        {20},
        {21},
        {22},
        {29},
        {120},
        {190},
        {9, 25, 29, 120, 190, 12345},
        {1, 121, 139, MAX_IP},
    ]),

    ({'o9', 'o10'}, [
        {71},
        {80},
        {81},
        {83},
        {87},
        {88},
        {89},
        {90},
        {96},
        {98},
        {115},
        {169},
        {71, 80, 115},
        {2, 71, 81, 169, 12345, MAX_IP},
        {139, 140},
    ]),

    ({'o8', 'o9', 'o10'}, [
        {30},
        {31},
        {39},
        {40},
        {41},
        {49},
        {50},
        {51},
        {59},
        {60},
        {61},
        {70},
        {82},
        {84},
        {85},
        {86},
        {95},
        {97},
        {100},
        {101},
        {104},
        {105},
        {106},
        {110},
        {130, 139, 140},
        {130, 138, 139, 140},
        {130, 169},
        {150, 180},
        {4, 30, 42, 70, 100, 110},
        {5, 10, 120, 125, 155, 170, 185, MAX_IP}
    ]),
]

def _ip_min_max(ip_network):
    return ip_network_tuple_to_min_max_ip(
        ip_network_as_tuple(ip_network),
        force_min_ip_greater_than_zero=True)
_ip = ip_str_to_int

SPECIFIC_IP_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o30',
        'ip_min_max_seq': [
            # all addresses from the `10.10.10.0/24` network *except* `10.10.10.152`
            _ip_min_max('10.10.10.0/25'),
            _ip_min_max('10.10.10.128/28'),
            _ip_min_max('10.10.10.144/29'),
            _ip_min_max('10.10.10.153/32'),
            _ip_min_max('10.10.10.154/31'),
            _ip_min_max('10.10.10.156/30'),
            _ip_min_max('10.10.10.160/27'),
            _ip_min_max('10.10.10.192/26'),
        ],
    },
]

EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_SPECIFIC_IP_CRITERIA = [
    # list of pairs [corresponds to SPECIFIC_IP_CRITERIA]:
    #     (<expected `client_org_ids` set>,
    #      <list of cases: each being a set of integers representing
    #       IP addresses from `address` of the given record dict>)
    (set(), [
        {1},
        {_ip('10.10.9.255')},
        {_ip('10.10.10.152')},
        {_ip('10.10.11.0')},
        {MAX_IP},
        {
            1,
            _ip('10.10.9.255'),
            _ip('10.10.10.152'),
            _ip('10.10.11.0'),
            MAX_IP,
        },
    ]),

    ({'o30'}, [
        {_ip('10.10.10.{}'.format(i))}
        for i in range(256)
        if i != 152
    ] + [
        {
            _ip('10.10.10.{}'.format(i))
            for i in range(256)
            if i != 152
        },
        {
            _ip('10.10.10.{}'.format(i))
            for i in range(256)
            # (here we do not skip `...152`)
        } | {
            1,
            _ip('10.10.9.255'),
            _ip('10.10.11.0'),
            MAX_IP,
        },
    ]),
]

URL_CRITERIA = [
    # list of dicts, as returned by AuthAPI._get_inside_criteria()
    {
        'org_id': 'o24',
        'url_seq': [u'http://cdns.pl'],
    },
    {
        'org_id': 'o25',
        'url_seq': [
            u'http://qwerty.zdns.pl/42?foo=bar',
            u'http://qwerty.zdns.pl/42?ham=spam',
        ],
    },
    {
        'org_id': 'o26',
        'url_seq': [u'https://zdns.pl'],
    },
    {
        'org_id': 'o27',
        'url_seq': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
    },
    {
        'org_id': 'o28',
        'url_seq': [u'http://zoo', u'ftp://foo'],
    },
    {
        'org_id': 'o29',
        'url_seq': [u'ftp://ht/what.json'],
    },
]

EXPECTED_RESULTS_AND_GIVEN_URL_PATTERNS = [
    # list of pairs [corresponds to URL_CRITERIA]:
    #     ((<expected `client_org_ids` set>, <expected `urls_matched` dict>),
    #      <list of cases: each being `url_pattern` of the given record dict>)
    ((set(), {}), [
        r'^http://.*\bk.*\.pl\b',
        r'http://*k???.pl*',
        r'^.*\.oo',
        r'*.oo',
        r'*tp*:/?[!cfhqz]*',
        r'ftp://zażółć.gęślą.jaźń/here/and/there/',
        r'http://ht/what.json',
        r'https://[^.]+$',
        r'^mailto:.*',
        r'mailto:*',
    ]),

    (({'o24'}, {
        'o24': [u'http://cdns.pl'],
     }), [
        r'http://*c???.pl',
        r'http://*c???.pl*',
        r'^http://.*\bc.*\.pl\b',
    ]),

    (({'o25'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar'],
     }), [
        r'*=b*',
        r'=b',
    ]),

    (({'o25'}, {
        'o25': [u'http://qwerty.zdns.pl/42?ham=spam'],
     }), [
        r'*=s*',
        r'=s',
    ]),

    (({'o25'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
     }), [
        r'*=[bs]*',
        r'=[bs]',
        r'42',
        r'\?',
        r'=',
        r'http://*z???.pl*',
        r'^http://.*\bz.*\.pl\b',
        r'//[a-z]+\.[a-z]+\.[a-z]+/',
    ]),

    (({'o26'}, {
        'o26': [u'https://zdns.pl'],
     }), [
        r'https://[^/]+$',
        r'h*://*z???.pl',
    ]),

    (({'o27'}, {
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
     }), [
        r'zażółć',
        r'*zażółć*',
        r'*/',
        r'/$',
        r'*/[!/][!/][!/]/*',
    ]),

    (({'o28'}, {
        'o28': [u'http://zoo'],
     }), [
        r'zoo',
    ]),

    (({'o28'}, {
        'o28': [u'ftp://foo', u'http://zoo'],
     }), [
        r'oo$',
        r'*oo',
    ]),

    (({'o29'}, {
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'tp://\w+/',
        r'*.json',
    ]),

    (({'o24', 'o26'}, {
        'o24': [u'http://cdns.pl'],
        'o26': [u'https://zdns.pl'],
     }), [
        r'^.*\.pl$',
        r'*.pl',
    ]),

    (({'o25', 'o26'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar'],
        'o26': [u'https://zdns.pl'],
     }), [
        r'^http.*\bz.*\.pl\b(?!....ham)',
    ]),

    (({'o25', 'o26'}, {
        'o25': [u'http://qwerty.zdns.pl/42?ham=spam'],
        'o26': [u'https://zdns.pl'],
     }), [
        r'^http.*\bz.*\.pl\b(?!....foo)',
    ]),

    (({'o25', 'o26'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o26': [u'https://zdns.pl'],
     }), [
        r'h*://*z???.pl*',
        r'^http.*\bz.*\.pl\b',
    ]),

    (({'o25', 'o27'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
     }), [
        r'//\w+\.\w+\.\w+/',  # making use of the Unicode-related regex features (for o27)
    ]),

    (({'o25', 'o28'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar'],
        'o28': [u'ftp://foo'],
     }), [
        r'foo',
    ]),

    (({'o25', 'o28'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar'],
        'o28': [u'ftp://foo', u'http://zoo'],
     }), [
        r'oo',
        r'*oo*',
    ]),

    (({'o26', 'o27'}, {
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
     }), [
        r'https://[^?]+$',
        r'https',      # both regex and glob compile and both match the same orgs
        r'tps',        # both regex and glob compile but only regex matches
    ]),

    (({'o27', 'o29'}, {
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'/\w+/',
    ]),

    (({'o28', 'o29'}, {
        'o28': [u'ftp://foo'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'ftp:[/]/*',  # both regex and glob compile and both match the same orgs
    ]),

    (({'o24', 'o25', 'o26'}, {
        'o24': [u'http://cdns.pl'],
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o26': [u'https://zdns.pl'],
     }), [
        r'^.*\.pl',
        r'*.pl*',
    ]),

    (({'o24', 'o26', 'o27'}, {
        'o24': [u'http://cdns.pl'],
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
     }), [
        r'http*[l/]',  # both regex and glob compile but only glob matches
    ]),

    (({'o25', 'o27', 'o29'}, {
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'tps?://[^/]+/\w',
    ]),

    (({'o24', 'o26', 'o27', 'o29'}, {
        'o24': [u'http://cdns.pl'],
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'htt*[l/]',   # both regex and glob compile and each matches different orgs
    ]),

    (({'o24', 'o25', 'o26', 'o27', 'o28'}, {
        'o24': [u'http://cdns.pl'],
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o28': [u'http://zoo'],
     }), [
        r'https*',
        r'http',       # both regex and glob compile and both match the same orgs
    ]),

    (({'o24', 'o26', 'o27', 'o28', 'o29'}, {
        'o24': [u'http://cdns.pl'],
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o28': [u'ftp://foo', u'http://zoo'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'*tp*:/?[!q]*',
    ]),

    (({'o24', 'o25', 'o26', 'o27', 'o28', 'o29'}, {
        'o24': [u'http://cdns.pl'],
        'o25': [u'http://qwerty.zdns.pl/42?foo=bar',
                u'http://qwerty.zdns.pl/42?ham=spam'],
        'o26': [u'https://zdns.pl'],
        'o27': [u'https://zażółć.gęślą.jaźń/here/and/there/'],
        'o28': [u'ftp://foo', u'http://zoo'],
        'o29': [u'ftp://ht/what.json'],
     }), [
        r'*tp*:/?[cfhqz]*',
    ]),
]


# * actual tests

@expand
class TestInsideCriteriaResolver_initialization(TestCaseMixin, unittest.TestCase):

    @foreach(
        param(
            inside_criteria=[],
            expected_content={},
        ),
        param(
            inside_criteria=[{'org_id': 'o42', 'fqdn_seq': []}],
            expected_content={},
        ),
        param(
            inside_criteria=[
                {
                    'org_id': 'o42',
                },
                {
                    'org_id': 'o9',
                    'fqdn_seq': [u'www.xn--exampl-14a.com', u'xn--exampl-14a.org'],
                },
                {
                    'org_id': 'o8',
                    'fqdn_seq': [u'xn--exampl-14a.org'],
                },
                {
                    'org_id': 'o10',
                    'fqdn_seq': [u'foobar.info', u'www.xn--exampl-14a.com'],
                },
            ],
            expected_content={
                'www.xn--exampl-14a.com': ['o9', 'o10'],
                'xn--exampl-14a.org': ['o9', 'o8'],
                'foobar.info': ['o10'],
            },
        ),
    )
    def test___fqdn_suffix_to_ids(self, inside_criteria, expected_content):
        with self.assertStateUnchanged(inside_criteria):
            r = InsideCriteriaResolver(inside_criteria)
            self.assertEqual(r._fqdn_suffix_to_ids, expected_content)


    @foreach(
        param(
            inside_criteria=[],
            expected_content={},
        ),
        param(
            inside_criteria=[{'org_id': 'o42', 'asn_seq': []}],
            expected_content={},
        ),
        param(
            inside_criteria=[
                {
                    'org_id': 'o42',
                },
                {
                    'org_id': 'o9',
                    'asn_seq': [987654321, 12345],
                },
                {
                    'org_id': 'o8',
                    'asn_seq': [12345],
                },
                {
                    'org_id': 'o10',
                    'asn_seq': [42, 987654321],
                },
            ],
            expected_content={
                987654321: ['o9', 'o10'],
                12345: ['o9', 'o8'],
                42: ['o10'],
            },
        ),
    )
    def test___asn_to_ids(self, inside_criteria, expected_content):
        with self.assertStateUnchanged(inside_criteria):
            r = InsideCriteriaResolver(inside_criteria)
            self.assertEqual(r._asn_to_ids, expected_content)


    @foreach(
        param(
            inside_criteria=[],
            expected_content={},
        ),
        param(
            inside_criteria=[{'org_id': 'o42', 'cc_seq': []}],
            expected_content={},
        ),
        param(
            inside_criteria=[
                {
                    'org_id': 'o42',
                },
                {
                    'org_id': 'o9',
                    'cc_seq': ['PL', 'JP'],
                },
                {
                    'org_id': 'o8',
                    'cc_seq': ['JP'],
                },
                {
                    'org_id': 'o10',
                    'cc_seq': ['US', 'PL'],
                },
            ],
            expected_content={
                'PL': ['o9', 'o10'],
                'JP': ['o9', 'o8'],
                'US': ['o10'],
            },
        ),
    )
    def test___cc_to_ids(self, inside_criteria, expected_content):
        with self.assertStateUnchanged(inside_criteria):
            r = InsideCriteriaResolver(inside_criteria)
            self.assertEqual(r._cc_to_ids, expected_content)


    @foreach(
        param(
            inside_criteria=[],
            expected_content=[],
        ),
        param(
            inside_criteria=[{'org_id': 'o42', 'url_seq': []}],
            expected_content=[],
        ),
        param(
            inside_criteria=[
                {
                    'org_id': 'o42',
                },
                {
                    'org_id': 'o9',
                    'url_seq': [u'http://foo.bar', u'https://examplę.pl/?foo'],
                },
                {
                    'org_id': 'o8',
                    'url_seq': [u'https://examplę.pl/?foo'],
                },
                {
                    'org_id': 'o10',
                    'url_seq': [u'http://1.2.3.4/.../', u'http://foo.bar'],
                },
            ],
            expected_content=[
                ('o9', (u'http://foo.bar', u'https://examplę.pl/?foo')),
                ('o8', (u'https://examplę.pl/?foo',)),
                ('o10', (u'http://1.2.3.4/.../', u'http://foo.bar')),
            ],
        ),
    )
    def test___ids_and_urls(self, inside_criteria, expected_content):
        with self.assertStateUnchanged(inside_criteria):
            r = InsideCriteriaResolver(inside_criteria)
            self.assertEqual(r._ids_and_urls, expected_content)


    @foreach(
        param(
            inside_criteria=[],
            expected_content=(
                [
                    -1,           # guard item
                    2 ** 32,      # guard item
                ],
                [
                    frozenset(),  # guard item
                    frozenset(),  # guard item
                ],
            ),
        ),

        param(
            inside_criteria=[
                {
                    'org_id': 'o42',
                    'ip_min_max_seq': [],
                },
            ],
            expected_content=(
                [
                    -1,           # guard item
                    2 ** 32,      # guard item
                ],
                [
                    frozenset(),  # guard item
                    frozenset(),  # guard item
                ],
            ),
        ),

        param(
            inside_criteria=EXTREME_IP_CRITERIA,
            expected_content=(
                [
                    -1,           # guard item
                    1,
                    2,
                    3,
                    101,
                    102,
                    MAX_IP,
                    2 ** 32,      # guard item
                ],
                [
                    frozenset(),  # guard item
                    frozenset(['o6', 'o7']),
                    frozenset(['o7']),
                    frozenset(['o6']),
                    frozenset(),
                    frozenset(['o7']),
                    frozenset(['o6', 'o7']),
                    frozenset(),  # guard item
                ],
            ),
        ),

        param(
            inside_criteria=COMPLEX_IP_CRITERIA,
            expected_content=(
                [
                    -1,           # guard item
                    10,
                    20,
                    30,
                    40,
                    51,
                    61,
                    71,
                    80,
                    82,
                    83,
                    84,
                    85,
                    86,
                    87,
                    91,
                    95,
                    96,
                    97,
                    98,
                    99,
                    100,
                    105,
                    106,
                    111,
                    115,
                    116,
                    120,
                    121,
                    131,
                    139,
                    140,
                    150,
                    161,
                    169,
                    170,
                    171,
                    180,
                    190,
                    191,
                    2 ** 32,      # guard item
                ],
                [
                    frozenset(),  # guard item       # -1
                    frozenset(['o10']),              # 10
                    frozenset(['o8', 'o10']),        # 20
                    frozenset(['o8', 'o9', 'o10']),  # 30
                    frozenset(['o8', 'o9', 'o10']),  # 40
                    frozenset(['o8', 'o9', 'o10']),  # 51
                    frozenset(['o8', 'o9', 'o10']),  # 61
                    frozenset(['o9', 'o10']),        # 71
                    frozenset(['o9', 'o10']),        # 80
                    frozenset(['o8', 'o9', 'o10']),  # 82
                    frozenset(['o9', 'o10']),        # 83
                    frozenset(['o8', 'o9', 'o10']),  # 84
                    frozenset(['o8', 'o9', 'o10']),  # 85
                    frozenset(['o8', 'o9', 'o10']),  # 86
                    frozenset(['o9', 'o10']),        # 87
                    frozenset(['o9']),               # 91
                    frozenset(['o8', 'o9', 'o10']),  # 95
                    frozenset(['o9', 'o10']),        # 96
                    frozenset(['o8', 'o9', 'o10']),  # 97
                    frozenset(['o9', 'o10']),        # 98
                    frozenset(['o9']),               # 99
                    frozenset(['o8', 'o9', 'o10']),  # 100
                    frozenset(['o8', 'o9', 'o10']),  # 105
                    frozenset(['o8', 'o9', 'o10']),  # 106
                    frozenset(['o10']),              # 111
                    frozenset(['o9', 'o10']),        # 115
                    frozenset(['o10']),              # 116
                    frozenset(['o8', 'o10']),        # 120
                    frozenset(['o8']),               # 121
                    frozenset(),                     # 131
                    frozenset(['o10']),              # 139
                    frozenset(['o9']),               # 140
                    frozenset(['o8', 'o9']),         # 150
                    frozenset(['o9']),               # 161
                    frozenset(['o9', 'o10']),        # 169
                    frozenset(['o9']),               # 170
                    frozenset(),                     # 171
                    frozenset(['o10']),              # 180
                    frozenset(['o8', 'o10']),        # 190
                    frozenset(),                     # 191
                    frozenset(),  # guard item       # 2 ** 32
                ],
            ),
        ),

        param(
            inside_criteria=SPECIFIC_IP_CRITERIA,
            expected_content=(
                    [
                        -1,  # guard item
                        _ip('10.10.10.0'),
                        _ip('10.10.10.128'),
                        _ip('10.10.10.144'),
                        _ip('10.10.10.152'),
                        _ip('10.10.10.153'),
                        _ip('10.10.10.154'),
                        _ip('10.10.10.156'),
                        _ip('10.10.10.160'),
                        _ip('10.10.10.192'),
                        _ip('10.10.11.0'),
                        2 ** 32,  # guard item
                    ],
                    [
                        frozenset(),  # guard item
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(),
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(['o30']),
                        frozenset(),
                        frozenset(),  # guard item
                    ],
            ),
        ),
    )
    def test___border_ips_and_corresponding_id_sets(self, inside_criteria, expected_content):
        with self.assertStateUnchanged(inside_criteria):
            r = InsideCriteriaResolver(inside_criteria)
            self.assertEqual(r._border_ips_and_corresponding_id_sets, expected_content)


@expand
class TestInsideCriteriaResolver__get_client_org_ids_and_urls_matched(TestCaseMixin,
                                                                      unittest.TestCase):
    RD_BASE = {
        # these items are obligatory for a RecordDict (though irrelevant
        # for InsideCriteriaResolver.get_client_org_ids_and_urls_matched())
        'confidence': 'medium',
        'id': 'b1b2e7006be3e87195eb4f9d98c80014',
        'restriction': 'public',
        'rid': '7d8e117294f7e499730546d14a98a622',
        'source': 'foo.bar',
        'time': datetime.datetime(2016, 6, 20, 17, 23),
    }

    DEFAULT_CATEGORY = 'bots'
    FQDN_ONLY_CATEGORIES = frozenset({'leak', 'malurl'})


    @paramseq
    def case_params(cls):
        NO_CRITERIA = []
        MANY_CRITERIA = (
            VARIOUS_CRITERIA +
            FQDN_CRITERIA +
            EXTREME_IP_CRITERIA +
            COMPLEX_IP_CRITERIA +
            SPECIFIC_IP_CRITERIA +
            URL_CRITERIA)
        NO_EXPECTED_RESULTS_AND_VARIOUS_RD_CONTENTS = [
            (set(), rdc_cases)
            for _, rdc_cases in EXPECTED_RESULTS_AND_GIVEN_RD_CONTENTS_FOR_VARIOUS_CRITERIA]

        prng = random.Random()
        prng.seed(12345)
        for inside_criteria, expected_results_and_given_data_cases, kind_of_data in [
                (
                    NO_CRITERIA,
                    NO_EXPECTED_RESULTS_AND_IRRELEVANT_RD_CONTENTS,
                    'rd_content',
                ),
                (
                    NO_CRITERIA,
                    NO_EXPECTED_RESULTS_AND_VARIOUS_RD_CONTENTS,
                    'rd_content',
                ),
                (
                    MANY_CRITERIA,
                    NO_EXPECTED_RESULTS_AND_IRRELEVANT_RD_CONTENTS,
                    'rd_content',
                ),
                (
                    VARIOUS_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_RD_CONTENTS_FOR_VARIOUS_CRITERIA,
                    'rd_content',
                ),
                (
                    FQDN_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_FQDNS,
                    'fqdn',
                ),
                (
                    EXTREME_IP_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_EXTREME_IP_CRITERIA,
                    'ip_set',
                ),
                (
                    COMPLEX_IP_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_COMPLEX_IP_CRITERIA,
                    'ip_set',
                ),
                (
                    SPECIFIC_IP_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_IP_SETS_FOR_SPECIFIC_IP_CRITERIA,
                    'ip_set',
                ),
                (
                    URL_CRITERIA,
                    EXPECTED_RESULTS_AND_GIVEN_URL_PATTERNS,
                    'url_pattern',
                )]:
            for expected_results, given_data_cases in expected_results_and_given_data_cases:
                for given_data in given_data_cases:
                    param_kwargs = cls._prepare_param_kwargs(
                        inside_criteria,
                        expected_results,
                        given_data,
                        kind_of_data,
                        prng,
                    )
                    yield param(**param_kwargs)

    @classmethod
    def _prepare_param_kwargs(cls,
                              inside_criteria, expected_results, given_data, kind_of_data, prng):
        if isinstance(expected_results, tuple):
            (expected_org_ids,
             expected_urls_matched) = expected_results
        elif isinstance(expected_results, set):
            expected_org_ids = expected_results
            expected_urls_matched = {}
        else:
            raise RuntimeError(
                'bug in the test: unsupported type of `expected_results` '
                '{!a}'.format(expected_results))

        if kind_of_data == 'rd_content':
            rd_content = given_data
        elif kind_of_data == 'fqdn':
            rd_content = {'fqdn': given_data}
        elif kind_of_data == 'ip_set':
            rd_content = {'address': [{'ip': ip} for ip in given_data]}
        elif kind_of_data == 'url_pattern':
            rd_content = {'url_pattern': given_data}
        else:
            raise RuntimeError(
                'bug in the test: unknown `kind_of_data` '
                '{!a}'.format(kind_of_data))

        param_kwargs = dict(
            inside_criteria=inside_criteria,
            rd_content=rd_content,
            expected_org_ids=expected_org_ids,
            expected_urls_matched=expected_urls_matched)

        if rd_content.get('category') in cls.FQDN_ONLY_CATEGORIES or prng.randint(0, 1):
            param_kwargs['fqdn_only_categories'] = cls.FQDN_ONLY_CATEGORIES

        return param_kwargs


    @foreach(case_params)
    def test(self, inside_criteria, rd_content, expected_org_ids, expected_urls_matched,
             fqdn_only_categories=None):
        resolver = self._make_resolver(inside_criteria)
        record_dict = self._make_record_dict(rd_content)
        (opt_args,
         opt_kwargs) = self._make_optional_arguments(fqdn_only_categories)
        with self.assertStateUnchanged(
              vars(resolver),
              record_dict,
              inside_criteria,
              rd_content,
              fqdn_only_categories):
            (actual_org_ids,
             actual_urls_matched) = resolver.get_client_org_ids_and_urls_matched(
                record_dict,
                *opt_args,
                **opt_kwargs)
        self.assertEqual(actual_org_ids, expected_org_ids)
        self.assertEqual(actual_urls_matched, expected_urls_matched)

    def _make_resolver(self, inside_criteria):
        with self.assertStateUnchanged(inside_criteria):
            return InsideCriteriaResolver(inside_criteria)

    def _make_record_dict(self, rd_content):
        with self.assertStateUnchanged(self.RD_BASE, rd_content):
            actual_rd_content = dict(self.RD_BASE)
            actual_rd_content.update(rd_content)
            actual_rd_content.setdefault('category', self.DEFAULT_CATEGORY)
            return RecordDict(actual_rd_content)

    def _make_optional_arguments(self, fqdn_only_categories):
        opt_args = []
        opt_kwargs = {}
        if fqdn_only_categories is not None:
            if random.randint(0, 1):
                opt_args.append(fqdn_only_categories)
            else:
                opt_kwargs['fqdn_only_categories'] = fqdn_only_categories
        return opt_args, opt_kwargs


if __name__ == '__main__':
    unittest.main()

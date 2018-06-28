# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

"""
This is a -- somewhat quick and dirty but still useful -- standalone
script that tests the n6lib.auth_api.AuthAPI stuff integrated with the
n6lib.ldap_api_replacement module (SQL-auth-db-based) instead of the
legacy n6lib.ldap_api.

To run this script you need:

1) to have Docker installed,
2) to place in your sudoers file (see: the `sudoers` and `visudo`
   man pages) the line:
   <your Linux user name>  ALL = NOPASSWD: /usr/bin/docker
   (where `<your Linux user name>` is your Linux user name --
   who would have thought?).

Note: don't worry about *many* skipped tests and only a few
actually run; all the tests are "borrowed" from our main AuthAPI
test suite (namely: from n6lib.tests.test_auth_api); here we
skip most of them because they are irrelevant when testing
n6lib.ldap_api_replacement-related stuff.  As long as there
are no test failures or errors -- everything is OK. :-)
"""

import contextlib
import logging
import os
import sys
import time
import unittest
from subprocess import (
    call,
    check_call,
    check_output,
)

import sqlalchemy
import sqlalchemy.orm
from mock import ANY, MagicMock, patch

import n6lib.config
from n6lib.auth_db import models
from n6lib.auth_api import (
    LDAP_API_REPLACEMENT,
    AuthAPI,
)
from n6lib.common_helpers import (
    make_hex_id,
    SimpleNamespace,
)
from n6lib.auth_db.config import SimpleSQLAuthDBConnector
from n6lib.tests import test_auth_api


DOCKER_EXECUTABLE = '/usr/bin/docker'

MARIADB_DOCKER_NAME = 'mariadb-n6-auth-test-' + make_hex_id(16)
MARIADB_NAME = 'n6authtest'
MARIADB_PASSWORD = 'n654321'
MARIADB_RUN_COMMAND = [
    DOCKER_EXECUTABLE,
    'run',
    '--name', MARIADB_DOCKER_NAME,
    '-e', 'MYSQL_ROOT_PASSWORD=' + MARIADB_PASSWORD,
    '-d',
    'mariadb:10',
]
MARIADB_GET_IP_COMMAND = [
    DOCKER_EXECUTABLE,
    'inspect',
    '--format', '{{ .NetworkSettings.IPAddress }}',
    MARIADB_DOCKER_NAME,
]
MARIADB_STOP_COMMAND = [
    DOCKER_EXECUTABLE,
    'stop',
    MARIADB_DOCKER_NAME,
]
MARIADB_REMOVE_COMMAND = [
    DOCKER_EXECUTABLE,
    'rm', '-f', '-v',
    MARIADB_DOCKER_NAME,
]

IRRELEVANT_TEST_NAMES = {
    'TestAuthAPI__context_manager',
    'TestAuthAPI__authenticate',
    'TestAuthAPI__get_inside_criteria_resolver',
    'TestAuthAPI__get_access_info',
    'TestAuthAPI___make_request_parameters_dict',
    'TestAuthAPI___parse_notification_time',
}
IRRELEVANT_TEST_NAME_PREFIXES = (
    'TestInsideCriteriaResolver_initialization',
    'TestInsideCriteriaResolver__get_client_org_ids_and_urls_matched',
)


db_host = None

def main():
    global db_host

    if not LDAP_API_REPLACEMENT:
        sys.exit('LDAP_API_REPLACEMENT is not true!  Try setting the '
                 'N6_FORCE_LDAP_API_REPLACEMENT environment variable.')

    monkey_patching()
    logging.basicConfig()

    db_host = run_db()
    try:
        unittest.main(test_auth_api, verbosity=1)
    finally:
        shutdown_db()


def monkey_patching():
    _skip_irrelevant_tests()
    _set_expected_rest_api_resource_limits_to_defaults()
    _patch_AuthAPILdapDataBasedMethodTestMixIn()
    test_auth_api.LOGGER_error_mock_factory = lambda: SimpleNamespace(call_count=ANY)
    n6lib.config.LOGGER = MagicMock()

def _skip_irrelevant_tests():
    for name, obj in vars(test_auth_api).iteritems():
        if name in IRRELEVANT_TEST_NAMES or name.startswith(IRRELEVANT_TEST_NAME_PREFIXES):
            assert isinstance(obj, type) and issubclass(obj, unittest.TestCase)
            skipped = unittest.skip('test case irrelevant to ldap_api_replacement stuff')(obj)
            setattr(test_auth_api, name, skipped)

def _set_expected_rest_api_resource_limits_to_defaults():
    for access_info in test_auth_api.EXAMPLE_ORG_IDS_TO_ACCESS_INFOS.itervalues():
        for res_props in access_info['rest_api_resource_limits'].itervalues():
            res_props.clear()
            res_props.update(
                max_days_old=100,
                queries_limit=None,
                request_parameters=None,
                results_limit=None,
                window=3600,
            )

def _patch_AuthAPILdapDataBasedMethodTestMixIn():
    @contextlib.contextmanager
    def monkey_patched_standard_context(self, search_flat_return_value):
        create_db()
        try:
            populate_db(test_class_name=self.__class__.__name__)
            with self._singleton_off():
                self.auth_api = AuthAPI(settings={
                    'auth_db.url': 'mysql+mysqldb://root:{passwd}@{host}/{name}'.format(
                        passwd=MARIADB_PASSWORD,
                        host=db_host,
                        name=MARIADB_NAME)
                })
                try:
                    with patch.object(AuthAPI, '_get_root_node',
                                      AuthAPI._get_root_node.func):  # unmemoized (not cached)
                        yield
                finally:
                    self.auth_api = None
        finally:
            drop_db()

    def monkey_patched_assert_problematic_orgs_logged(self, *args, **kwargs):
        pass

    test_auth_api._AuthAPILdapDataBasedMethodTestMixIn.standard_context = \
        monkey_patched_standard_context
    test_auth_api._AuthAPILdapDataBasedMethodTestMixIn.assert_problematic_orgs_logged = \
        monkey_patched_assert_problematic_orgs_logged


def run_db():
    shutdown_db()
    with _devnull() as devnull:
        check_call(MARIADB_RUN_COMMAND, stdout=devnull)
        _db_host = check_output(MARIADB_GET_IP_COMMAND).strip()
    return _db_host

def shutdown_db():
    with _devnull() as devnull:
        call(MARIADB_STOP_COMMAND, stdout=devnull, stderr=devnull)
        call(MARIADB_REMOVE_COMMAND, stdout=devnull, stderr=devnull)

@contextlib.contextmanager
def _devnull():
    f = os.open(os.devnull, os.O_RDWR)
    try:
        yield f
    finally:
        os.close(f)


def create_db():
    for i in xrange(20):
        try:
            engine = sqlalchemy.create_engine('mysql+mysqldb://root:{passwd}@{host}'.format(
                passwd=MARIADB_PASSWORD,
                host=db_host))
            try:
                engine.execute('CREATE DATABASE {}'.format(MARIADB_NAME))
            finally:
                engine.dispose()
        except Exception:
            time.sleep(1)
        else:
            break
    else:
        raise RuntimeError('Cannot connect to database...')
    time.sleep(1)

def drop_db():
    engine = sqlalchemy.create_engine('mysql+mysqldb://root:{passwd}@{host}'.format(
        passwd=MARIADB_PASSWORD,
        host=db_host))
    try:
        engine.execute('DROP DATABASE {}'.format(MARIADB_NAME))
    finally:
        engine.dispose()
    time.sleep(1)

def populate_db(test_class_name):
    db = SimpleSQLAuthDBConnector(db_host, MARIADB_NAME, 'root', MARIADB_PASSWORD)
    try:
        models.Base.metadata.create_all(db.engine)
        data_maker = _get_data_maker(test_class_name)
        with db as session:
            session.add_all(data_maker())
    finally:
        db.engine.dispose()
    time.sleep(1)

def _get_data_maker(test_class_name):
    return globals()['data_maker_for____{}'.format(test_class_name)]


def data_maker_for____TestAuthAPI__get_user_ids_to_org_ids():
    yield models.Org(org_id='o1',
                     users=[models.User(login='login1@foo.bar'),
                            models.User(login='login5@foo.bar')])
    yield models.Org(org_id='o2',
                     users=[models.User(login='login2@foo.bar')])
    yield models.Org(org_id='o3',
                     users=[models.User(login='login3@foo.bar')])
    yield models.Org(org_id='o4',
                     users=[models.User(login='login4@foo.bar'),
                            models.User(login='login6@foo.bar')])
    yield models.Org(org_id='o42')

def data_maker_for____TestAuthAPI__get_org_ids():
    yield models.Org(org_id='o1')
    yield models.Org(org_id='o2')
    yield models.Org(org_id='o3')
    yield models.Org(org_id='o4')

def data_maker_for____TestAuthAPI__get_anonymized_source_mapping():
    yield models.Source(source_id='s1.foo', anonymized_source_id='a1.bar')
    yield models.Source(source_id='s2.foo', anonymized_source_id='a2.bar')
    yield models.Source(source_id='s6.foo', anonymized_source_id='a6.bar')

def data_maker_for____TestAuthAPI__get_dip_anonymization_disabled_source_ids():
    yield models.Source(source_id='s1.foo', dip_anonymization_enabled=True)
    yield models.Source(source_id='s2.foo', dip_anonymization_enabled=False)
    yield models.Source(source_id='s3.foo', dip_anonymization_enabled=True)
    yield models.Source(source_id='s4.foo', dip_anonymization_enabled=False)
    yield models.Source(source_id='s5.foo')   # omitted -> True                 [sic!]
    yield models.Source(source_id='s6.foo', dip_anonymization_enabled=False)
    yield models.Source(source_id='s7.foo', dip_anonymization_enabled=False)  # [sic!]
    yield models.Source(source_id='s8.foo', dip_anonymization_enabled=True)

def data_maker_for____TestAuthAPI__get_org_ids_to_access_infos():
    return _data_matching_those_from_auth_related_test_helpers()

def data_maker_for____TestAuthAPI__get_source_ids_to_subs_to_stream_api_access_infos():
    return _data_matching_those_from_auth_related_test_helpers()

def data_maker_for____TestAuthAPI__get_stream_api_enabled_org_ids():
    raise unittest.SkipTest('test not implemented yet')  # TODO later...

def data_maker_for____TestAuthAPI__get_stream_api_disabled_org_ids():
    raise unittest.SkipTest('test not implemented yet')  # TODO later...

def data_maker_for____TestAuthAPI__get_source_ids_to_notification_access_info_mappings():
    return _data_matching_those_from_auth_related_test_helpers()

def data_maker_for____TestAuthAPI__get_org_ids_to_notification_configs():
    raise unittest.SkipTest('test not implemented yet')  # TODO later...

def data_maker_for____TestAuthAPI___get_inside_criteria():
    yield models.Org(org_id='o1',
                     inside_filter_asns=[
                         models.InsideFilterASN(asn=12),
                         models.InsideFilterASN(asn=34)],
                     inside_filter_ccs=[
                         models.InsideFilterCC(cc='PL'),
                         models.InsideFilterCC(cc=u'US')],
                     inside_filter_fqdns=[
                         models.InsideFilterFQDN(fqdn='example.com'),
                         models.InsideFilterFQDN(fqdn=u'xyz.example.net')],
                     inside_filter_ip_networks=[
                         models.InsideFilterIPNetwork(ip_network='1.2.3.4/16'),
                         models.InsideFilterIPNetwork(ip_network=u'101.102.103.104/32')],
                     inside_filter_urls=[
                         models.InsideFilterURL(url='exp.pl'),
                         models.InsideFilterURL(url=u'bank.pl/auth.php'),
                         models.InsideFilterURL(url=u'Łódź')])
    yield models.Org(org_id='o2',
                     inside_filter_asns=[models.InsideFilterASN(asn=1234567)])
    fqdn_example_org = models.InsideFilterFQDN(fqdn='example.org')
    yield models.Org(org_id='o3',
                     inside_filter_fqdns=[fqdn_example_org])
    yield models.Org(org_id='o4')
    yield models.Org(org_id='abcdefghijklmnoabcdefghijklmno12',
                     inside_filter_fqdns=[fqdn_example_org])


def _data_matching_those_from_auth_related_test_helpers():
    ### (see: n6lib.auth_related_test_helpers)
    # criteria containers
    ASN3 = models.CriteriaASN(asn=3)
    cri1 = models.CriteriaContainer(
        label='cri1',
        criteria_asns=[
            models.CriteriaASN(asn=1),
            models.CriteriaASN(asn=2),
            ASN3],
        criteria_ip_networks=[
            models.CriteriaIPNetwork(ip_network='10.0.0.0/8'),
            models.CriteriaIPNetwork(ip_network='192.168.0.0/24')])
    cri2 = models.CriteriaContainer(
        label='cri2',
        criteria_asns=[
            ASN3,
            models.CriteriaASN(asn=4),
            models.CriteriaASN(asn=5)])
    cri3 = models.CriteriaContainer(
        label='cri3',
        criteria_ccs=[models.CriteriaCC(cc='PL')])
    cri4 = models.CriteriaContainer(
        label='cri4',
        criteria_categories=[
            models.CriteriaCategory(category='bots'),
            models.CriteriaCategory(category='cnc')])
    cri5 = models.CriteriaContainer(
        label='cri5',
        criteria_names=[models.CriteriaName(name='foo')])
    cri6 = models.CriteriaContainer(
        label='cri6')
    # sources
    s1 = models.Source(
        source_id='source.one',
        anonymized_source_id='anon-source.one')
    s2 = models.Source(
        source_id='source.two',
        anonymized_source_id='anon-source.two')
    s3 = models.Source(
        source_id='xyz.some-other',
        anonymized_source_id='anon-xyz.some-other')
    # subsources
    p1 = models.Subsource(
        label='p1',
        source=s1,
        inclusion_criteria=[cri1],
        exclusion_criteria=[])
    p2 = models.Subsource(
        label='p2',
        source=s1,
        inclusion_criteria=[cri1, cri2],
        exclusion_criteria=[cri6])
    p3 = models.Subsource(
        label='p3',
        source=s1)
    p4 = models.Subsource(
        label='p4',
        source=s2,
        inclusion_criteria=[cri5],
        exclusion_criteria=[cri3, cri4, cri5, cri6])
    p5 = models.Subsource(
        label='p5',
        source=s2,
        inclusion_criteria=[cri4, cri5, cri6])
    p6 = models.Subsource(
        label='p6',
        source=s2,
        inclusion_criteria=[cri6],
        exclusion_criteria=[])
    p7 = models.Subsource(
        label='p7',
        source=s3,
        exclusion_criteria=[cri3, cri6])
    p8 = models.Subsource(
        label='p8',
        source=s3,
        exclusion_criteria=[cri3, cri6])
    p9 = models.Subsource(
        label='p9',
        source=s3,
        exclusion_criteria=[cri3, cri6])
    # subsource groups
    gp1 = models.SubsourceGroup(label='gp1', subsources=[p1, p2])
    gp2 = models.SubsourceGroup(label='gp2', subsources=[p3, p4])
    gp3 = models.SubsourceGroup(label='gp3', subsources=[p1, p3, p7, p9])
    gp4 = models.SubsourceGroup(label='gp4', subsources=[p6])
    gp5 = models.SubsourceGroup(label='gp5', subsources=[p7])
    gp6 = models.SubsourceGroup(label='gp6', subsources=[p8])
    gp7 = models.SubsourceGroup(label='gp7')
    gp8 = models.SubsourceGroup(label='gp8', subsources=[p9])
    # org groups
    go1 = models.OrgGroup(
        org_group_id='go1',
        inside_subsources=[p2, p5],
        inside_subsource_groups=[gp2],
        search_subsources=[p8],
        search_subsource_groups=[gp6],
        threats_subsources=[p2, p5],
        threats_subsource_groups=[gp2],
    )
    go2 = models.OrgGroup(
        org_group_id='go2',
        inside_subsources=[p1, p3],
        inside_subsource_groups=[gp4],
        search_subsources=[],
        threats_subsources=[p1, p3],
        threats_subsource_groups=[gp4],
    )
    go3 = models.OrgGroup(
        org_group_id='go3',
        inside_subsources=[p6],
        inside_subsource_groups=[],
        threats_subsources=[p6],
    )
    go4 = models.OrgGroup(
        org_group_id='go4',
        search_subsources=[],
        search_subsource_groups=[],
    )
    go5 = models.OrgGroup(
        org_group_id='go5',
        inside_subsources=[p1, p2, p5, p6],
        inside_subsource_groups=[gp2, gp3, gp4, gp7],
        search_subsources=[p1, p2, p5, p6],
        search_subsource_groups=[gp2, gp3, gp4, gp7],
        threats_subsources=[p1, p2, p5, p6],
        threats_subsource_groups=[gp2, gp3, gp4, gp7],
    )
    # orgs
    o1 = models.Org(
        org_id='o1',
        org_groups=[go1],
        full_access=True, stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=True,
        inside_subsources=[],
        inside_subsource_groups=[gp1, gp3, gp7],
        inside_ex_subsources=[],
        inside_ex_subsource_groups=[],

        access_to_search=True,
        search_subsources=[p2],
        search_ex_subsources=[p2],
        search_ex_subsource_groups=[gp2, gp6],

        access_to_threats=True,
        threats_subsources=[],
        threats_subsource_groups=[gp1, gp3, gp7],
        threats_ex_subsources=[],
        threats_ex_subsource_groups=[gp2],
    )
    o2 = models.Org(
        org_id='o2',
        org_groups=[go1, go3],
        full_access=False, stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=False,
        inside_subsources=[p7, p9],
        inside_subsource_groups=[],

        access_to_search=True,
        search_ex_subsources=[p5, p8],
        search_ex_subsource_groups=[gp3],

        access_to_threats=True,
        threats_subsources=[p7, p9],
        threats_subsource_groups=[],
        threats_ex_subsources=[p5],
        threats_ex_subsource_groups=[gp3],
    )
    o3 = models.Org(
        org_id='o3',
        org_groups=[go2, go3],
        full_access=False, stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=True,
        inside_subsources=[p2],

        access_to_search=True,

        access_to_threats=True,
        threats_subsources=[p2],
        threats_ex_subsource_groups=[gp1],
    )
    o4 = models.Org(
        org_id='o4',
        org_groups=[go2],
        full_access=False, stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=True,
        inside_subsources=[p5],
        inside_ex_subsource_groups=[gp8],

        access_to_search=True,
        search_subsources=[p2, p6, p8],
        search_subsource_groups=[gp4, gp5, gp8],
        search_ex_subsources=[p6],
        search_ex_subsource_groups=[gp5, gp6, gp8],

        access_to_threats=True,
        threats_subsources=[p5],
        threats_ex_subsources=[p6],
        threats_ex_subsource_groups=[gp5],
    )
    o5 = models.Org(
        org_id='o5',
        org_groups=[],
        stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_ex_subsource_groups=[gp8],

        access_to_search=True,
        search_subsources=[],
        search_subsource_groups=[],
        search_ex_subsources=[],
        search_ex_subsource_groups=[],

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_ex_subsources=[p2, p6],
        threats_ex_subsource_groups=[gp4, gp5],
    )
    o6 = models.Org(
        org_id='o6',
        org_groups=[go4],
        full_access=True, stream_api_enabled=True, email_notifications_enabled=True,

        access_to_inside=True,

        access_to_search=False,
        search_subsources=[p2, p4, p6],
        search_subsource_groups=[gp4, gp5, gp6, gp8],
        search_ex_subsource_groups=[gp2, gp6],

        access_to_threats=False,
    )
    o7 = models.Org(
        org_id='o7',
        full_access=False, stream_api_enabled=False, email_notifications_enabled=False,

        access_to_inside=True,
        inside_subsources=[p5, p6],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_ex_subsources=[p9],

        access_to_search=True,
        search_subsources=[p5, p6],
        search_subsource_groups=[gp1, gp5, gp6, gp8],
        search_ex_subsource_groups=[gp6],

        access_to_threats=True,
        threats_subsources=[p5, p6],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_ex_subsources=[p1, p7],
        threats_ex_subsource_groups=[gp4],
    )
    o8 = models.Org(
        org_id='o8',
        stream_api_enabled=False, email_notifications_enabled=False,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_ex_subsource_groups=[gp8],

        access_to_search=False,

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_ex_subsources=[p2, p6],
        threats_ex_subsource_groups=[gp4, gp5],
    )
    o9 = models.Org(
        org_id='o9',
        stream_api_enabled=False,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_ex_subsource_groups=[gp8],

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_ex_subsources=[p2, p6],
        threats_ex_subsource_groups=[gp4, gp5],
    )
    o10 = models.Org(
        org_id='o10',

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_ex_subsource_groups=[gp8],

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_ex_subsources=[p2, p6],
        threats_ex_subsource_groups=[gp4, gp5],
    )
    o11 = models.Org(
        org_id='o11',

        access_to_inside=True,

        access_to_threats=True,
    )
    o12 = models.Org(
        org_id='o12',
        org_groups=[go1],
        full_access=False, stream_api_enabled=True, email_notifications_enabled=True,

        inside_subsources=[p1],

        search_subsources=[p1],
        search_ex_subsources=[p8],
        search_ex_subsource_groups=[gp6],

        threats_subsources=[p1],
    )
    return [
        cri1, cri2, cri3, cri4, cri5, cri6,
        s1, s2, s3,
        p1, p2, p3, p4, p5, p6, p7, p8, p9,
        gp1, gp2, gp3, gp4, gp5, gp6, gp7, gp8,
        go1, go2, go3, go4, go5,
        o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12,
    ]


if __name__ == "__main__":
    main()

# Copyright (c) 2018-2025 NASK. All rights reserved.

"""
This is a -- somewhat quick and dirty but still useful -- standalone
script that tests some important portions of auth-related code of *n6*,
mainly the `n6lib.auth_api.AuthAPI` stuff integrated with the
`n6lib.ldap_api_replacement` module (SQL-auth-db-based).

By default, to run this script you need a running MariaDB server (e.g.,
within a docker container) whose `root` password is equal to the value
of the `MARIADB_PASSWORD` constant and whose externally visible hostname
is equal to the value of the `MARIADB_STANDARD_HOSTNAME` constant (both
constants are defined in this module).  However, running by this script
its own MariaDB container is also possible: then `--own-db` flag needs
to be used... (See the comment placed at the beginning of the code of
the `own_db_context()` function.)

Note: don't worry about *many* skipped tests and only a dozen (or
something) of them actually run; many of the tests are "borrowed" from
our main AuthAPI test suite (namely: from `n6lib.tests.test_auth_api`);
here we skip most of them because they are irrelevant when testing
`n6lib.ldap_api_replacement`-related stuff.  As long as there are no
test failures or errors -- everything is OK.
"""

import contextlib
import datetime as dt
import functools
import itertools
import logging
import os
import random
import string
import sys
import tempfile
import unittest
import weakref
from code import interact
from pathlib import Path
from pprint import pprint as pp  # noqa    # (<- convenience for `--interactive-console-after`...)
from subprocess import (
    call,
    check_call,
    check_output,
)
from time import sleep
from typing import Optional
from unittest.mock import (
    ANY,
    MagicMock,
    patch,
)

from sqlalchemy import text as sqla_text

import n6lib.config
from n6lib.auth_db import models
from n6lib.auth_db.api import AuthManageAPI
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.auth_db.scripts import (
    CreateAndInitializeAuthDB,
    DropAuthDB,
)
from n6lib.auth_api import (
    AuthAPI,
    AuthAPIWithPrefetching,
)
from n6lib.auth_related_test_helpers import (
    EXAMPLE_DATABASE_TIMESTAMP,
    EXAMPLE_DATABASE_TIMESTAMP_AS_DATETIME,
    EXAMPLE_DATABASE_VER,
)
from n6lib.class_helpers import (
    all_subclasses,
    attr_required,
)
from n6lib.common_helpers import (
    PlainNamespace,
    ascii_str,
    make_exc_ascii_str,
    make_hex_id,
)
from n6lib.ldap_api_replacement import LdapAPI
from n6lib.tests import test_auth_api


#
# Constants
#

FLAG_OWN_DB = '--own-db'
FLAG_NO_TESTS = '--no-tests'
FLAG_INTERACTIVE_CONSOLE_AFTER = '--interactive-console-after'
FLAG_TEST_AUTH_API_WITH_PREFETCHING = '--test-auth-api-with-prefetching'
FLAG_TEST_AUTH_API_WITH_PREFETCHING_USING_PICKLE_CACHE = (
    '--test-auth-api-with-prefetching-using-pickle-cache')

RECOGNIZED_SCRIPT_FLAGS = [
    FLAG_OWN_DB,
    FLAG_NO_TESTS,
    FLAG_INTERACTIVE_CONSOLE_AFTER,
    FLAG_TEST_AUTH_API_WITH_PREFETCHING,
    FLAG_TEST_AUTH_API_WITH_PREFETCHING_USING_PICKLE_CACHE,
]

MARIADB_STANDARD_HOSTNAME = 'mariadb-n6-auth-test'
MARIADB_NAME = 'n6authtest'
MARIADB_PASSWORD = 'n654321'
MARIADB_ACCESSIBILITY_TIMEOUT = 60

IRRELEVANT_TEST_CLASS_NAMES = {
    'TestAuthAPI__context_manager',
    'TestAuthAPI_get_inside_criteria_resolver',
    'TestAuthAPI_get_ignore_lists_criteria_resolver__mocked',
    'TestAuthAPI_get_access_info',
    'TestAuthAPI_get_org_actual_name',
    'Test_DataPreparer__make_request_parameters_dict',
    'Test_DataPreparer__parse_notification_time',
    'TestInsideCriteriaResolver__init',
    'TestInsideCriteriaResolver_get_client_org_ids_and_urls_matched',
    'Test_IgnoreListsCriteriaResolver',
}


#
# Global variables
#

# These are always set to non-`None` values...
script_flags: set = Optional[None]   # ...in `main()`
db_host: str = Optional[None]        # ...in `external_db_context()`/`own_db_context()`

# This is set *only* for `--test-auth-api-with-prefetching-using-pickle-cache`
# (in `prepare_pickle_cache_dir_if_applicable()`)
pickle_cache_dir: Optional[str] = None

# This is set *only* for `--interactive-console-after` *without* `--own-db`
# (in `main() -> _stuff_prepared_for_interactive_use()`)
aa: Optional[test_auth_api.AuthAPI] = None


#
# Main script stuff
#

def main(argv):
    global script_flags
    script_flags = set(argv[1:])
    _validate_script_flags()

    monkey_patching()
    _configure_logging()

    exit_code = 1
    db_context = _get_db_context()
    with db_context:
        if FLAG_NO_TESTS not in script_flags:
            _ensure_db_server_accessible_and_db_dropped()
            exit_code = run_tests()
        if FLAG_INTERACTIVE_CONSOLE_AFTER in script_flags:
            with _stuff_prepared_for_interactive_use():
                _run_interactive_console()
    sys.exit(exit_code)


def _validate_script_flags():
    unrecognized_script_arguments = script_flags.difference(RECOGNIZED_SCRIPT_FLAGS)
    if unrecognized_script_arguments:
        print('Unrecognized command-line script arguments given: {}. '
              'The following flags are legal ones: {}.'.format(
                  ', '.join(map(ascii, unrecognized_script_arguments)),
                  ', '.join(map(ascii, RECOGNIZED_SCRIPT_FLAGS))),
              file=sys.stderr)
        sys.exit(2)

def _configure_logging():
    logging.basicConfig(
        format='%(levelname) -10s %(asctime)s %(name) -25s: %(message)s',
        level=(logging.INFO if FLAG_INTERACTIVE_CONSOLE_AFTER in script_flags
               else logging.WARNING))
    logging.getLogger('n6lib.threaded_async').setLevel(logging.WARNING)

def _get_db_context():
    if FLAG_OWN_DB in script_flags:
        return own_db_context()
    else:
        return external_db_context()

def _ensure_db_server_accessible_and_db_dropped():
    with creating_and_finally_dropping_db():
        pass

@contextlib.contextmanager
def _stuff_prepared_for_interactive_use():
    global aa
    with contextlib.ExitStack() as es:
        if FLAG_OWN_DB in script_flags:
            prepare_pickle_cache_dir_if_applicable()
            create_and_init_db(timeout=12)
            populate_db_with_test_data(_data_matching_those_from_auth_related_test_helpers)
        else:
            aa = es.enter_context(make_auth_api_testing_context())  # (just a convenience)
        yield

def _run_interactive_console():
    interact(
        local=globals(),
        banner=(
            f'\n----------------------------\n'
            f'Entering INTERACTIVE MODE...\n\n'
            f'* {script_flags=}\n'
            f'* {db_host=}\n'
            f'* {pickle_cache_dir=}\n'
            f'----------------------------\n'),
        exitmsg=(
            f'\n---------------------------\n'
            f'Exiting INTERACTIVE MODE...\n'
            f'---------------------------\n'))


#
# Monkey patching stuff
#

def monkey_patching():
    _skip_irrelevant_tests()
    _set_expected_rest_api_resource_limits_to_defaults()
    _patch_AuthAPILdapDataBasedMethodTestMixIn()
    _patch_TestAuthAPI_get_org_ids_to_notification_configs()
    test_auth_api.LOGGER_error_mock_factory = lambda: PlainNamespace(call_count=ANY)
    n6lib.config.LOGGER = MagicMock()


def _skip_irrelevant_tests():
    for name, obj in vars(test_auth_api).items():
        if name in IRRELEVANT_TEST_CLASS_NAMES:
            assert isinstance(obj, type) and issubclass(obj, unittest.TestCase)
            skipped = unittest.skip('test class irrelevant to ldap_api_replacement stuff')(obj)
            setattr(test_auth_api, name, skipped)

def _set_expected_rest_api_resource_limits_to_defaults():
    for expected_results in [
        test_auth_api.EXAMPLE_ORG_IDS_TO_ACCESS_INFOS,
        test_auth_api.EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITHOUT_OPTIMIZATION,
        test_auth_api.EXAMPLE_ORG_IDS_TO_ACCESS_INFOS_WITH_LEGACY_CONDITIONS,
    ]:
        for access_info in expected_results.values():
            for res_props in access_info['rest_api_resource_limits'].values():
                res_props.clear()
                res_props.update(
                    max_days_old=100,
                    queries_limit=None,
                    request_parameters=None,
                    results_limit=None,
                    window=3600,
                )

def _patch_AuthAPILdapDataBasedMethodTestMixIn():
    test_auth_api._AuthAPILdapDataBasedMethodTestMixIn.standard_context = (
        get_auth_api_testing_context_maker(recreate_populate_and_drop_db=True))
    test_auth_api._AuthAPILdapDataBasedMethodTestMixIn.assert_problematic_orgs_logged = (
        lambda *args, **kwargs: None)

def _patch_TestAuthAPI_get_org_ids_to_notification_configs():
    # (let's delete all cases but the last one; note that
    # it contains the data from all previous cases)
    del (test_auth_api.TestAuthAPI_get_org_ids_to_notification_configs
         ).search_flat_return_values__and__expected_results[:-1]


#
# Tools to collect and execute tests
#

def run_tests():
    loader = unittest.defaultTestLoader
    suite = _make_test_suite(loader)
    exit_code = _run_test_suite(suite)
    return exit_code

def _make_test_suite(loader):
    suite = unittest.TestSuite()
    suite.addTest(loader.loadTestsFromModule(test_auth_api))
    suite.addTests(
        loader.loadTestsFromTestCase(case)
        for case in mixin_for_tests_of__ldap_api_replacement__LdapAPI.iter_test_case_classes())
    suite.addTests(
        loader.loadTestsFromTestCase(case)
        for case in mixin_for_tests_of__auth_db__api__AuthManageAPI.iter_test_case_classes())
    return suite

def _run_test_suite(suite):
    # noinspection PyUnresolvedReferences
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    exit_code = int(not result.wasSuccessful())
    return exit_code


#
# Database-related stuff
#

@contextlib.contextmanager
def external_db_context():
    global db_host

    db_host = os.environ.get('N6_QUICKTEST_EXTERNAL_DB_HOSTNAME') or MARIADB_STANDARD_HOSTNAME
    yield


@contextlib.contextmanager
def own_db_context():
    # To make this script able to create and run the MariaDB docker
    # container automatically (locally, by itself) -- you need to:
    #
    # 1) have your Linux user able to launch Docker by executing
    #    '/usr/bin/docker' file; typically, that means you need to:
    #
    #    * have Docker installed;
    #    * have your Linux user associated with the appropriate system
    #      group, e.g., 'docker';
    #    * place in your sudoers file (see: the `sudoers` and `visudo`
    #      man pages) the line:
    #      ```
    #      <your Linux username>  ALL = NOPASSWD: /usr/bin/docker
    #      ```
    #      (where `<your Linux username>` is, surprisingly, your Linux
    #      username -- who would have thought? `:-O`);
    #
    # 2) run this script with the `--own-db` command-line option.

    DOCKER_EXECUTABLE = '/usr/bin/docker'
    MARIADB_DOCKER_NAME = f'mariadb-n6-auth-test-{make_hex_id(16)}'
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

    @contextlib.contextmanager
    def make_devnull():
        f = os.open(os.devnull, os.O_RDWR)
        try:
            yield f
        finally:
            os.close(f)

    def run_db():
        shutdown_db()
        with make_devnull() as devnull:
            check_call(MARIADB_RUN_COMMAND, stdout=devnull)
            mariadb_host = check_output(MARIADB_GET_IP_COMMAND, universal_newlines=True).strip()
        return mariadb_host

    def shutdown_db():
        with make_devnull() as devnull:
            call(MARIADB_STOP_COMMAND, stdout=devnull, stderr=devnull)
            call(MARIADB_REMOVE_COMMAND, stdout=devnull, stderr=devnull)

    global db_host

    db_host = run_db()
    try:
        yield
    finally:
        shutdown_db()


def prepare_auth_db_settings():
    return {
        'auth_db.url': 'mysql+mysqldb://root:{passwd}@{host}/{name}'.format(
            passwd=MARIADB_PASSWORD,
            host=db_host,
            name=MARIADB_NAME)
    }


@contextlib.contextmanager
def creating_and_finally_dropping_db():
    try:
        create_and_init_db(MARIADB_ACCESSIBILITY_TIMEOUT)
    except RuntimeError as exc:
        raise RuntimeError(
            f'{MARIADB_ACCESSIBILITY_TIMEOUT=} passed and still '
            f'cannot connect to the database! ({ascii_str(exc)})') from exc
    try:
        yield
    finally:
        drop_db()


def create_and_init_db(timeout):
    error_msg = 'no connection attempt made'
    for i in range(timeout):
        try:
            with CreateAndInitializeAuthDB(
                        settings=prepare_auth_db_settings(),
                        drop_db_if_exists=True,
                        assume_yes=True,
                        quiet=True,
                    ) as script:
                script.run()
        except Exception as exc:
            error_msg = make_exc_ascii_str(exc)
            sleep(1)
        else:
            break
    else:
        raise RuntimeError('Cannot connect to database... ({})'.format(error_msg))
    sleep(1)


def drop_db():
    with DropAuthDB(
                settings=prepare_auth_db_settings(),
                assume_yes=True,
                quiet=True,
            ) as script:
        script.run()
    sleep(1)


def populate_db_with_test_data(auth_api_test_class_name__or__data_maker):
    with auth_db_connector() as db:

        data_maker = _get_data_maker(auth_api_test_class_name__or__data_maker)
        with db as session:
            session.add_all(data_maker(session))

        with db.engine.begin() as conn:
            # (we do it this way to ease testing the
            # `recent_write_op_commit`-related stuff...)
            conn.execute(sqla_text('INSERT INTO recent_write_op_commit SET '
                                   'id = :id, made_at = :made_at'),
                         id=EXAMPLE_DATABASE_VER,
                         made_at=EXAMPLE_DATABASE_TIMESTAMP_AS_DATETIME)

    sleep(1)


@contextlib.contextmanager
def auth_db_connector():
    db = SQLAuthDBConnector(db_host, MARIADB_NAME, 'root', MARIADB_PASSWORD)
    try:
        yield db
    finally:
        db.engine.dispose()


def _get_data_maker(auth_api_test_class_name__or__data_maker):
    if isinstance(auth_api_test_class_name__or__data_maker, str):
        auth_api_test_class_name = auth_api_test_class_name__or__data_maker
        data_maker_name = 'data_maker_for__{}'.format(auth_api_test_class_name)
        data_maker = globals()[data_maker_name]
    else:
        data_maker = auth_api_test_class_name__or__data_maker
    assert callable(data_maker)
    return data_maker


#
# Other settings/environment-related stuff
#

def make_auth_api_testing_context(recreate_populate_and_drop_db='auto'):
    # Useful for`--interactive-console-after`.
    auth_api_testing_context = get_auth_api_testing_context_maker(recreate_populate_and_drop_db)
    return auth_api_testing_context()

mc = make_auth_api_testing_context  # (<- convenience alias for `--interactive-console-after`)


def get_auth_api_testing_context_maker(recreate_populate_and_drop_db):
    auth_api_class = (
        AuthAPIWithPrefetching
        if (FLAG_TEST_AUTH_API_WITH_PREFETCHING_USING_PICKLE_CACHE in script_flags
            or FLAG_TEST_AUTH_API_WITH_PREFETCHING in script_flags)
        else AuthAPI)

    if recreate_populate_and_drop_db == 'auto':
        recreate_populate_and_drop_db = FLAG_OWN_DB in script_flags

    if recreate_populate_and_drop_db:
        db_cm = creating_and_finally_dropping_db
    else:
        db_cm = contextlib.ExitStack  # (just a dummy context manager)

    @contextlib.contextmanager
    def auth_api_testing_context(test=None, *_, **__):
        prepare_pickle_cache_dir_if_applicable()
        with db_cm():
            if test is None:
                # (especially for  `--interactive-console-after`)
                test = PlainNamespace()
                if recreate_populate_and_drop_db:
                    populate_db_with_test_data(_data_matching_those_from_auth_related_test_helpers)
            elif recreate_populate_and_drop_db:
                populate_db_with_test_data(test.__class__.__name__)

            with test_auth_api._AuthAPILdapDataBasedMethodTestMixIn.unmemoized_root_node_getter(
                auth_api_class,
            ):
                test.auth_api = auth_api_class(settings=prepare_auth_api_settings())
                test.data_preparer = test.auth_api._data_preparer
                try:
                    yield test.auth_api
                finally:
                    try:
                        if isinstance(test.auth_api, AuthAPIWithPrefetching):
                            test.auth_api._prefetch_task.cancel_and_join()
                    finally:
                        test.auth_api = None
                        test.data_preparer = None

    # It can be used, in particular, as a replacement for the auth api test methods'
    # `standard_context` (defined in `_AuthAPILdapDataBasedMethodTestMixIn`...) --
    # e.g., see `_patch_AuthAPILdapDataBasedMethodTestMixIn()` defined earlier.
    return auth_api_testing_context


def prepare_pickle_cache_dir_if_applicable():
    global pickle_cache_dir, __pickle_cache_dir_obj
    if FLAG_TEST_AUTH_API_WITH_PREFETCHING_USING_PICKLE_CACHE in script_flags:
        pickle_cache_dir = os.environ.get('N6_QUICKTEST_PICKLE_CACHE_DIR')
        if pickle_cache_dir:
            Path(pickle_cache_dir).mkdir(mode=0o700, parents=True, exist_ok=True)
        else:
            __pickle_cache_dir_obj = tempfile.TemporaryDirectory()  # (to be auto-removed...)
            pickle_cache_dir = __pickle_cache_dir_obj.name
__pickle_cache_dir_obj = None


def prepare_auth_api_settings():
    settings = prepare_auth_db_settings()
    if FLAG_TEST_AUTH_API_WITH_PREFETCHING_USING_PICKLE_CACHE in script_flags:
        assert pickle_cache_dir is not None
        settings |= {
            'auth_api_prefetching.max_sleep_between_runs': '12',
            'auth_api_prefetching.tolerance_for_outdated': '300',
            'auth_api_prefetching.tolerance_for_outdated_on_error': '1200',
            'auth_api_prefetching.pickle_cache_dir': pickle_cache_dir,
            'auth_api_prefetching.pickle_cache_signature_secret': (8 * '<just for tests>'),
        }
    return settings


#
# Data related to AuthAPI test cases
#

def data_maker_for__TestAuthAPI_get_user_ids_to_org_ids(session):
    yield models.Org(org_id='o1',
                     users=[models.User(login='login1@foo.bar'),
                            models.User(login='login5@foo.bar')])
    yield models.Org(org_id='o2',
                     users=[models.User(login='login2@foo.bar')])
    yield models.Org(org_id='o3',
                     users=[models.User(login='login3@foo.bar')])
    yield models.Org(org_id='o4',
                     users=[models.User(login='login4@foo.bar'),
                            models.User(login='login6@foo.bar'),
                            models.User(login='blocked-guy@foo.bar', is_blocked=True)])
    yield models.Org(org_id='o42')

def data_maker_for__TestAuthAPI_get_all_user_ids_including_blocked(session):
    yield models.Org(org_id='o1',
                     users=[models.User(login='login1@foo.bar'),
                            models.User(login='login5@foo.bar')])
    yield models.Org(org_id='o2',
                     users=[models.User(login='login2@foo.bar')])
    yield models.Org(org_id='o3',
                     users=[models.User(login='login3@foo.bar')])
    yield models.Org(org_id='o4',
                     users=[models.User(login='login4@foo.bar'),
                            models.User(login='login6@foo.bar'),
                            models.User(login='blocked-guy@foo.bar', is_blocked=True)])
    yield models.Org(org_id='o42')

def data_maker_for__TestAuthAPI_get_org_ids(session):
    yield models.Org(org_id='o1')
    yield models.Org(org_id='o2')
    yield models.Org(org_id='o3')
    yield models.Org(org_id='o4')

def data_maker_for__TestAuthAPI_get_ignore_lists_criteria_resolver__real(session):
    yield models.IgnoreList(
        label='Some inactive list',
        comment='Zażółć\nGęślą\r\nJaźń!',
        active=False,                                           # this *ignore list* is *inactive*
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='1.0.0.0/8'),           # (so these IP network
            models.IgnoredIPNetwork(ip_network='200.201.202.201/31'),  # specs are irrelevant)
        ])
    yield models.IgnoreList(
        label='Some active list',
        comment='Takoż\rZażółć\nGęślą\r\nJaźń!',
        active=True,
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='0.0.0.0/9'),
            models.IgnoredIPNetwork(ip_network='200.201.202.202/31'),
        ])
    yield models.IgnoreList(
        label='Another active list',
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='1.2.3.4/32'),
            models.IgnoredIPNetwork(ip_network='200.201.202.203/32'),
        ])
    yield models.IgnoreList(
        label='Also active list but without any IP network specs',
        ignored_ip_networks=[])
    yield models.IgnoreList(
        label='Another inactive list',
        active=False,                                           # this *ignore list* is *inactive*
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='0.0.0.0/9'),           # (so these IP network
            models.IgnoredIPNetwork(ip_network='200.201.202.202/31'),  # specs are irrelevant)
        ])
    yield models.IgnoreList(
        label='Yet another active list',
        ignored_ip_networks=[
            # (note: this IP network specification includes
            # meaningless *host bits* that will be ignored)
            models.IgnoredIPNetwork(ip_network='10.20.30.123/24'),
        ])
    yield models.IgnoreList(
        label='And again some active list',
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='200.201.202.203/32'),
            models.IgnoredIPNetwork(ip_network='1.2.3.4/32'),
            models.IgnoredIPNetwork(ip_network='0.128.0.0/9'),
        ])
    yield models.IgnoreList(
        label='And yet another inactive list',
        active=False,                                           # this *ignore list* is *inactive*
        ignored_ip_networks=[
            models.IgnoredIPNetwork(ip_network='10.20.29.0/24'),       # (so these IP network
            models.IgnoredIPNetwork(ip_network='200.201.202.202/31'),  # specs are irrelevant)
            models.IgnoredIPNetwork(ip_network='1.2.3.0/24'),
        ])

def data_maker_for__TestAuthAPI_get_anonymized_source_mapping(session):
    yield models.Source(source_id='s1.foo', anonymized_source_id='a1.bar')
    yield models.Source(source_id='s2.foo', anonymized_source_id='a2.bar')
    yield models.Source(source_id='s6.foo', anonymized_source_id='a6.bar')

def data_maker_for__TestAuthAPI_get_dip_anonymization_disabled_source_ids(session):
    yield models.Source(source_id='s1.foo',
                        anonymized_source_id='a1.bar',
                        dip_anonymization_enabled=True)
    yield models.Source(source_id='s2.foo',
                        anonymized_source_id='a2.bar',
                        dip_anonymization_enabled=False)
    yield models.Source(source_id='s3.foo',
                        anonymized_source_id='a3.bar',
                        dip_anonymization_enabled=True)
    yield models.Source(source_id='s4.foo',
                        anonymized_source_id='a4.bar',
                        dip_anonymization_enabled=False)
    yield models.Source(source_id='s5.foo',
                        anonymized_source_id='a5.bar',
                        )  # `dip_anonymization_enabled` not set explicitly -> True
    yield models.Source(source_id='s6.foo',
                        anonymized_source_id='a6.bar',
                        dip_anonymization_enabled=False)
    yield models.Source(source_id='s7.foo',
                        anonymized_source_id='a7.bar',
                        dip_anonymization_enabled=False)
    yield models.Source(source_id='s8.foo',
                        anonymized_source_id='a8.bar',
                        dip_anonymization_enabled=True)

def data_maker_for__TestAuthAPI_get_org_ids_to_access_infos(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_org_ids_to_access_infos__without_optimization(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_org_ids_to_access_infos__with_legacy_conditions(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_org_ids_to_actual_names(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_source_ids_to_subs_to_stream_api_access_infos(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_stream_api_enabled_org_ids(session):
    yield models.Org(org_id='o1', stream_api_enabled=True)
    yield models.Org(org_id='o2', stream_api_enabled=False)
    yield models.Org(org_id='o3', stream_api_enabled=False)
    yield models.Org(org_id='o4', stream_api_enabled=False)
    yield models.Org(org_id='o5')
    yield models.Org(org_id='o6', stream_api_enabled=False)

def data_maker_for__TestAuthAPI_get_stream_api_disabled_org_ids(session):
    yield models.Org(org_id='o1', stream_api_enabled=True)
    yield models.Org(org_id='o2', stream_api_enabled=False)
    yield models.Org(org_id='o3', stream_api_enabled=False)
    yield models.Org(org_id='o4', stream_api_enabled=False)
    yield models.Org(org_id='o5')
    yield models.Org(org_id='o6', stream_api_enabled=False)

def data_maker_for__TestAuthAPI_get_source_ids_to_notification_access_info_mappings(session):
    return _data_matching_those_from_auth_related_test_helpers(session)

def data_maker_for__TestAuthAPI_get_org_ids_to_notification_configs(session):
    yield models.Org(org_id='o1',
                     email_notification_enabled=True,
                     email_notification_addresses=[
                         models.EMailNotificationAddress(email='address@dn.pl'),
                         models.EMailNotificationAddress(email='address@x.cn'),
                     ],
                     email_notification_times=[
                         models.EMailNotificationTime(notification_time=dt.time(12)),
                         models.EMailNotificationTime(notification_time=dt.time(9, 15)),
                     ],
                     stream_api_enabled=False)
    yield models.Org(org_id='o2',
                     actual_name='testname2',
                     email_notification_enabled=True,
                     email_notification_addresses=[
                         models.EMailNotificationAddress(email='address@dn2.pl'),
                     ],
                     email_notification_times=[
                         models.EMailNotificationTime(notification_time=dt.time(9, 15)),
                         models.EMailNotificationTime(notification_time=dt.time(12)),
                     ],
                     email_notification_language='PL',
                     email_notification_business_days_only=False,
                     stream_api_enabled=False)
    yield models.Org(org_id='o3',
                     actual_name='testname3',
                     email_notification_enabled=True,
                     email_notification_addresses=[
                         models.EMailNotificationAddress(email='address@dn32.pl'),
                         models.EMailNotificationAddress(email='address@dn31.pl'),
                     ],
                     email_notification_times=[
                         models.EMailNotificationTime(notification_time=dt.time(10, 15)),
                         models.EMailNotificationTime(notification_time=dt.time(13)),
                     ],
                     email_notification_language='en',
                     email_notification_business_days_only=True)
    yield models.Org(org_id='o4',
                     email_notification_enabled=False,
                     email_notification_times=[
                         models.EMailNotificationTime(notification_time=dt.time(9, 15)),
                         models.EMailNotificationTime(notification_time=dt.time(12)),
                     ],
                     email_notification_addresses=[
                         models.EMailNotificationAddress(email='address@dn4.pl'),
                     ],
                     stream_api_enabled=False)
    yield models.Org(org_id='o5',
                     actual_name='testname5',
                     email_notification_enabled=True,
                     email_notification_addresses=[
                         models.EMailNotificationAddress(email='address@dn5.pl'),
                     ],
                     email_notification_times=[
                         models.EMailNotificationTime(notification_time=dt.time(12)),
                         models.EMailNotificationTime(notification_time=dt.time(9, 15)),
                     ],
                     stream_api_enabled=True)

def data_maker_for__TestAuthAPI__peek_database_ver_and_timestamp(session):
    yield models.Org(org_id='o1')  # (whatever...)

def data_maker_for__Test_DataPreparer__get_inside_criteria(session):
    yield models.Org(org_id='o1',
                     inside_filter_asns=[
                         models.InsideFilterASN(asn=12),
                         models.InsideFilterASN(asn=34)],
                     inside_filter_ccs=[
                         models.InsideFilterCC(cc='PL'),
                         models.InsideFilterCC(cc='US')],
                     inside_filter_fqdns=[
                         models.InsideFilterFQDN(fqdn='example.com'),
                         models.InsideFilterFQDN(fqdn='xyz.example.net')],
                     inside_filter_ip_networks=[
                         models.InsideFilterIPNetwork(ip_network='0.0.0.0/32'),
                         models.InsideFilterIPNetwork(ip_network='0.10.20.30/8'),
                         models.InsideFilterIPNetwork(ip_network='1.2.3.4/16'),
                         models.InsideFilterIPNetwork(ip_network='101.102.103.104/32')],
                     inside_filter_urls=[
                         models.InsideFilterURL(url='example.info'),
                         models.InsideFilterURL(url='institution.example.pl/auth.php'),
                         models.InsideFilterURL(url='Łódź')])
    yield models.Org(org_id='o2',
                     inside_filter_asns=[models.InsideFilterASN(asn=1234567)])
    yield models.Org(org_id='o3',
                     inside_filter_fqdns=[models.InsideFilterFQDN(fqdn='example.org')])
    yield models.Org(org_id='o4')
    yield models.Org(org_id='abcdefghijklmnoabcdefghijklmno12',
                     inside_filter_fqdns=[models.InsideFilterFQDN(fqdn='example.org')])

def _data_matching_those_from_auth_related_test_helpers(session):
    ### (see: n6lib.auth_related_test_helpers)
    # criteria containers
    criteria_category_bots = session.query(models.CriteriaCategory).filter(
        models.CriteriaCategory.category == 'bots').one()
    criteria_category_cnc = session.query(models.CriteriaCategory).filter(
        models.CriteriaCategory.category == 'cnc').one()
    cri1 = models.CriteriaContainer(
        label='cri1',
        criteria_asns=[
            models.CriteriaASN(asn=1),
            models.CriteriaASN(asn=2),
            models.CriteriaASN(asn=3)],
        criteria_ip_networks=[
            models.CriteriaIPNetwork(ip_network='0.0.0.0/30'),
            models.CriteriaIPNetwork(ip_network='10.0.0.0/8'),
            models.CriteriaIPNetwork(ip_network='192.168.0.0/24')])
    cri2 = models.CriteriaContainer(
        label='cri2',
        criteria_asns=[
            models.CriteriaASN(asn=3),
            models.CriteriaASN(asn=4),
            models.CriteriaASN(asn=5)])
    cri3 = models.CriteriaContainer(
        label='cri3',
        criteria_ccs=[models.CriteriaCC(cc='PL')])
    cri4 = models.CriteriaContainer(
        label='cri4',
        criteria_categories=[
            criteria_category_bots,
            criteria_category_cnc])
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
    p10 = models.Subsource(
        label='p10',
        source=s3,
        inclusion_criteria=[cri2, cri5],
        exclusion_criteria=[cri1, cri4])
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
        actual_name='Actual Name Zażółć',
        org_groups=[go1],
        full_access=True, stream_api_enabled=True, email_notification_enabled=True,

        access_to_inside=True,
        inside_subsources=[],
        inside_subsource_groups=[gp1, gp3, gp7],
        inside_off_subsources=[],
        inside_off_subsource_groups=[],

        access_to_search=True,
        search_subsources=[p2],
        search_off_subsources=[p2],
        search_off_subsource_groups=[gp2, gp6],

        access_to_threats=True,
        threats_subsources=[],
        threats_subsource_groups=[gp1, gp3, gp7],
        threats_off_subsources=[],
        threats_off_subsource_groups=[gp2],
    )
    o2 = models.Org(
        org_id='o2',
        org_groups=[go1, go3],
        full_access=False, email_notification_enabled=True,

        access_to_inside=False,
        inside_subsources=[p7, p9],
        inside_subsource_groups=[],

        access_to_search=True,
        search_off_subsources=[p5, p8],
        search_off_subsource_groups=[gp3],

        access_to_threats=True,
        threats_subsources=[p7, p9],
        threats_subsource_groups=[],
        threats_off_subsources=[p5],
        threats_off_subsource_groups=[gp3],
    )
    o3 = models.Org(
        org_id='o3',
        org_groups=[go2, go3],
        full_access=False, stream_api_enabled=True, email_notification_enabled=True,

        access_to_inside=True,
        inside_subsources=[p2],

        access_to_search=True,

        access_to_threats=True,
        threats_subsources=[p2],
        threats_off_subsource_groups=[gp1],
    )
    o4 = models.Org(
        org_id='o4',
        org_groups=[go2],
        full_access=False, email_notification_enabled=True,

        access_to_inside=True,
        inside_subsources=[p5],
        inside_off_subsource_groups=[gp8],

        access_to_search=True,
        search_subsources=[p2, p6, p8],
        search_subsource_groups=[gp4, gp5, gp8],
        search_off_subsources=[p6],
        search_off_subsource_groups=[gp5, gp6, gp8],

        access_to_threats=True,
        threats_subsources=[p5],
        threats_off_subsources=[p6],
        threats_off_subsource_groups=[gp5],
    )
    o5 = models.Org(
        org_id='o5',
        actual_name='Actual Name Five',
        org_groups=[],
        stream_api_enabled=True, email_notification_enabled=True,

        access_to_inside=True,
        inside_subsources=[p4, p10],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_off_subsource_groups=[gp8],

        access_to_search=True,
        search_subsources=[],
        search_subsource_groups=[],
        search_off_subsources=[],
        search_off_subsource_groups=[],

        access_to_threats=True,
        threats_subsources=[p4, p10],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_off_subsources=[p2, p6, p10],
        threats_off_subsource_groups=[gp4, gp5],
    )
    o6 = models.Org(
        org_id='o6',
        org_groups=[go4],
        full_access=True, stream_api_enabled=True, email_notification_enabled=True,

        access_to_inside=True,

        access_to_search=False,
        search_subsources=[p2, p4, p6],
        search_subsource_groups=[gp4, gp5, gp6, gp8],
        search_off_subsource_groups=[gp2, gp6],

        access_to_threats=False,
    )
    o7 = models.Org(
        org_id='o7',
        full_access=False, stream_api_enabled=False, email_notification_enabled=False,

        access_to_inside=True,
        inside_subsources=[p5, p6],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_off_subsources=[p9],

        access_to_search=True,
        search_subsources=[p5, p6],
        search_subsource_groups=[gp1, gp5, gp6, gp8],
        search_off_subsource_groups=[gp6],

        access_to_threats=True,
        threats_subsources=[p5, p6],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_off_subsources=[p1, p7],
        threats_off_subsource_groups=[gp4],
    )
    o8 = models.Org(
        org_id='o8',
        stream_api_enabled=False, email_notification_enabled=False,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_off_subsource_groups=[gp8],

        access_to_search=False,

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_off_subsources=[p2, p6],
        threats_off_subsource_groups=[gp4, gp5],
    )
    o9 = models.Org(
        org_id='o9',
        actual_name='Actual Name Nine',
        stream_api_enabled=False,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_off_subsource_groups=[gp8],

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_off_subsources=[p2, p6],
        threats_off_subsource_groups=[gp4, gp5],
    )
    o10 = models.Org(
        org_id='o10',
        stream_api_enabled=False,

        access_to_inside=True,
        inside_subsources=[p4],
        inside_subsource_groups=[gp1, gp5, gp8],
        inside_off_subsource_groups=[gp8],

        access_to_threats=True,
        threats_subsources=[p4],
        threats_subsource_groups=[gp1, gp5, gp8],
        threats_off_subsources=[p2, p6],
        threats_off_subsource_groups=[gp4, gp5],
    )
    o11 = models.Org(
        org_id='o11',
        stream_api_enabled=False,

        access_to_inside=True,

        access_to_threats=True,
    )
    o12 = models.Org(
        org_id='o12',
        org_groups=[go1],
        full_access=False, email_notification_enabled=True,

        inside_subsources=[p1],

        search_subsources=[p1],
        search_off_subsources=[p8],
        search_off_subsource_groups=[gp6],

        threats_subsources=[p1],
    )
    return [
        cri1, cri2, cri3, cri4, cri5, cri6,
        s1, s2, s3,
        p1, p2, p3, p4, p5, p6, p7, p8, p9, p10,
        gp1, gp2, gp3, gp4, gp5, gp6, gp7, gp8,
        go1, go2, go3, go4, go5,
        o1, o2, o3, o4, o5, o6, o7, o8, o9, o10, o11, o12,
    ]


#
# Some direct tests of n6lib.ldap_api_replacement.LdapAPI
#

class mixin_for_tests_of__ldap_api_replacement__LdapAPI:

    @classmethod
    def iter_test_case_classes(cls):
        for subclass in all_subclasses(cls):
            if isinstance(subclass, type) and issubclass(subclass, unittest.TestCase):
                yield subclass

    # noinspection PyUnresolvedReferences,PyAttributeOutsideInit,PyPep8Naming
    def setUp(self):
        self.addCleanup(drop_db)
        create_and_init_db(timeout=60)
        populate_db_with_test_data(self.data_maker)
        self.ldap_api = LdapAPI(settings=prepare_auth_db_settings())

    @staticmethod
    def data_maker(session):
        raise NotImplementedError

    def run_code_under_test(self):
        raise NotImplementedError

    expected_result = None


    # noinspection PyUnresolvedReferences,PyAttributeOutsideInit
    @attr_required('expected_result')
    def test(self):
        with self.ldap_api:

            self.actual_result = self.run_code_under_test()

        self.assertEqual(self.actual_result, self.expected_result)


    require_covering_full_set_of_write_ops = True

    # noinspection PyUnresolvedReferences
    @attr_required('expected_result')
    def test_also_full_isolation_from_concurrent_write_ops_and_also_audit_log_mechanisms(self):
        # (Yes, here we test not just the `LdapAPI`'s stuff but also --
        # more generally -- important aspects of how the Audit Log
        # mechanisms, including the `recent_write_op_commit`-based
        # mechanism, work...)
        (writing_tick_callback,
         has_covered_required_set_of_write_ops,
         db_ver_seq) = self._prepare_concurrent_write_ops_and_audit_log_related_stuff()
        assert not has_covered_required_set_of_write_ops()
        assert not db_ver_seq
        with patch.object(self.ldap_api, 'tick_callback', writing_tick_callback):

            self.test()

        self.assertTrue(has_covered_required_set_of_write_ops())
        self.assertGreaterEqual(len(db_ver_seq), 1)
        self.assertEqual(db_ver_seq, list(range(
            EXAMPLE_DATABASE_VER + 1,
            EXAMPLE_DATABASE_VER + 1 + len(db_ver_seq))))
        with self.ldap_api:
            last_db_ver, _ = self.ldap_api.peek_database_ver_and_timestamp()
        self.assertEqual(last_db_ver, db_ver_seq[-1])

    def _prepare_concurrent_write_ops_and_audit_log_related_stuff(self):
        test_ref = weakref.ref(self)  # (<- used to avoid cycles of strong refs)

        (db_connector,
         db_audit_log_actual_entries) = self._prepare_extra_db_connector_with_patched_audit_log()

        catching = contextlib.suppress(ValueError)
        def err():
            raise ValueError

        db_ver_seq = []
        previously_seen_db_ver = EXAMPLE_DATABASE_VER

        performed_any_write_ops = False
        performed_full_set_of_write_ops = False

        if self.require_covering_full_set_of_write_ops:
            def has_covered_required_set_of_write_ops():
                return performed_full_set_of_write_ops
        else:
            def has_covered_required_set_of_write_ops():
                return performed_any_write_ops

        def writing_gen_impl():
            nonlocal performed_any_write_ops
            nonlocal performed_full_set_of_write_ops

            # Note: thanks to the full isolation of the `LdapAPI`-related
            # Auth DB transaction from other transactions, the following
            # write operations do *not* affect `actual_result` checked
            # in the `test()` method (note that they would affect it if
            # the isolation was not real).

            _expect_previously_seen_db_ver()
            with db_connector as session:
                # A bunch of example write operations that would affect
                # `actual_result` if the isolation was not real...
                such_a_user = models.User(login='user1@such.an.org.you.know')   # noqa
                such_an_org = models.Org(
                    org_id='such.an.org.you.know',                              # noqa
                    users=[                                                     # noqa
                        such_a_user,
                        models.User(login='user2@such.an.org.you.know'),        # noqa
                        models.User(login='user3@such.an.org.you.know'),        # noqa
                    ],
                )
                session.add_all([such_a_user, such_an_org])
                session.flush()
                with db_connector:  # (nested transaction)
                    such_an_org.actual_name = 'Such An Organization, You Know!'
                    session.delete(such_a_user)
                session.add_all(
                    data_maker_for__TestAuthAPI_get_ignore_lists_criteria_resolver__real(session)
                )
            _expect_new_db_ver()
            _expect_new_audit_log_entries(29)

            performed_any_write_ops = True
            yield

            with db_connector as session:
                # A bunch of example write operations that would affect
                # `actual_result` if the isolation was not real...
                my_org = session.query(models.Org).get('such.an.org.you.know')
                for user in my_org.users:
                    session.delete(user)
                session.delete(my_org)
                session.add_all(
                    _data_matching_those_from_auth_related_test_helpers(session)
                )
            _expect_new_db_ver()
            _expect_new_audit_log_entries(60)
            yield

            with db_connector:
                # Another example write operation that would affect
                # `actual_result` if the isolation was not real...
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with catching, db_connector:
                _write_op()
                err()  # (makes transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                err()
            # (Here no operations have been attempted at all...)
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        pass
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(2)
            yield

            with db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        pass
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(3)
            yield

            with db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        pass
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(2)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(3)
            yield

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                _write_op()
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                _write_op()
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    pass
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        with db_connector:  # (nested savepoint)
                            pass
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes only savepoint be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(2)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with catching, db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only this savepoint be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(3)
            yield

            with db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with catching, db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only this savepoint be rolled back)
                    _write_op()
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(4)
            yield

            with db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with catching, db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only this savepoint be rolled back)
                    err()  # (makes only this savepoint be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(2)
            yield

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes only savepoint be rolled back)
                _write_op()
                err()  # (makes transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                    err()  # (makes only both savepoints be rolled back)
                err()  # (makes transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with catching, db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes savepoint be rolled back)
                    err()  # (makes savepoint be rolled back)
                err()  # (makes transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only both savepoints be rolled back)
                err()  # (makes transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()

            with catching, db_connector:
                _write_op()
                with db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes whole transaction be rolled back)
            # Note: the transaction has been rolled back, so db
            # version has *not* been incremented (i.e., *no* new
            # `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes only savepoint be rolled back)
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)

            with db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                    err()  # (makes only savepoint be rolled back)
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)

            with db_connector:
                _write_op()
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only both savepoints be rolled back)
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes only savepoint be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                    err()  # (makes only savepoint be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes only both savepoints be rolled back)
                _write_op()
            _expect_new_db_ver()
            _expect_new_audit_log_entries(1)
            yield

            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        with db_connector:  # (nested savepoint)
                            err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        with db_connector:  # (nested savepoint)
                            pass
                        err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        with db_connector:  # (nested savepoint)
                            pass
                    err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        with db_connector:  # (nested savepoint)
                            pass
                err()  # (makes whole transaction be rolled back)
            with catching, db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with catching, db_connector:  # (nested savepoint)
                        with catching, db_connector:  # (nested savepoint)
                            err()  # (makes savepoint be rolled back)
                        err()  # (makes savepoint be rolled back)
                    err()  # (makes savepoint be rolled back)
                err()  # (makes transaction be rolled back)
            # Note: each of the last seven transactions has been rolled
            # back, so db version has *not* been incremented (i.e., *no*
            # new `recent_write_op_commit` has been inserted). Also,
            # *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                pass
            with db_connector:
                with db_connector:  # (nested savepoint)
                    pass
            with db_connector:
                with db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        pass
            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    err()  # (makes savepoint be rolled back)
            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        err()  # (makes both savepoints be rolled back)
            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with catching, db_connector:  # (nested savepoint)
                        err()  # (makes savepoint be rolled back)
                    err()  # (makes savepoint be rolled back)
            # Note: formally, *none* of the last six transactions have
            # been rolled back, but there were *no* write ops to be
            # committed, so db version has *not* been incremented (i.e.,
            # *no* new `recent_write_op_commit` has been inserted).
            # Also, *no* audit log entries have been emitted.
            _expect_previously_seen_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    err()  # (makes savepoint be rolled back)
            # Note: this is a *known and tolerable* bug: db version *has*
            # been incremented (i.e., a new `recent_write_op_commit` has
            # been inserted), even though the nested savepoint has been
            # rolled back and *no* other write ops have been performed
            # (note that *no* audit log entries have been emitted).
            _expect_new_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes both savepoints be rolled back)
            # (The same -- known and tolerable -- bug as described above...)
            _expect_new_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        err()  # (makes both savepoints be rolled back)
            # (The same -- known and tolerable -- bug as described above...)
            _expect_new_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        _write_op()
                        err()  # (makes both savepoints be rolled back)
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    _write_op()
                    with db_connector:  # (nested savepoint)
                        _write_op()
                        _write_op()
                        err()  # (makes both savepoints be rolled back)
            # (The same -- known and tolerable -- bug as described above...)
            _expect_new_db_ver()
            _expect_lack_of_new_audit_log_entries()
            yield

            with db_connector:
                with catching, db_connector:  # (nested savepoint)
                    _write_op()
                    with catching, db_connector:  # (nested savepoint)
                        _write_op()
                        err()  # (makes savepoint be rolled back)
                    err()  # (makes savepoint be rolled back)
            # (The same -- known and tolerable -- bug as described above...)
            _expect_new_db_ver()
            _expect_lack_of_new_audit_log_entries()

            performed_full_set_of_write_ops = True
            yield

            while True:
                with db_connector:
                    _write_op()
                _expect_new_db_ver()
                _expect_new_audit_log_entries(1)
                yield

        def _write_op():
            session = db_connector.get_current_session()
            assert session is not None
            op, org = _get_op_and_org(session)
            if op == 'insert':
                session.add(org)
            elif op == 'update':
                new_name_length = random.randint(5, 20)
                org.actual_name = ''.join(random.choices(string.ascii_letters, k=new_name_length))
            else:
                assert op == 'delete'
                session.delete(org)
            session.flush()

        def _get_op_and_org(session):
            while True:
                op = ('insert' if len(_maybe_existing_org_ids) < 3
                      else random.choice(['insert', 'update', 'delete']))
                if op == 'insert':
                    org_id = next(_new_org_id_gen)
                    org = models.Org(org_id=org_id)                             # noqa
                    _maybe_existing_org_ids.append(org_id)
                else:
                    org_id = random.choice(_maybe_existing_org_ids)
                    org = session.query(models.Org).get(org_id)
                    if org is None:
                        _maybe_existing_org_ids.remove(org_id)
                        continue
                return op, org
        _maybe_existing_org_ids = []
        _new_org_id_gen = (f'example.n{i}.org' for i in itertools.count(start=1))

        def _expect_previously_seen_db_ver():
            db_ver = _fetch_current_db_ver()
            test_ref().assertEqual(db_ver, previously_seen_db_ver)

        def _expect_new_db_ver():
            nonlocal previously_seen_db_ver
            db_ver = _fetch_current_db_ver()
            test_ref().assertEqual(db_ver, previously_seen_db_ver + 1)
            db_ver_seq.append(db_ver)
            previously_seen_db_ver = db_ver

        def _fetch_current_db_ver():
            with db_connector as session:
                recent_write_op_commit = session.query(
                    models.RecentWriteOpCommit,
                ).order_by(
                    models.RecentWriteOpCommit.id.desc(),
                ).limit(1).one()
                return recent_write_op_commit.id

        def _expect_lack_of_new_audit_log_entries():
            _expect_new_audit_log_entries(0)

        def _expect_new_audit_log_entries(expected_new_entries_count):
            nonlocal _expected_all_entries_count
            _expected_all_entries_count += expected_new_entries_count
            test_ref().assertEqual(len(db_audit_log_actual_entries), _expected_all_entries_count)
        _expected_all_entries_count = 0

        writing_gen = writing_gen_impl()
        self.addCleanup(writing_gen.close)                                      # noqa
        writing_tick_callback = functools.partial(next, writing_gen, None)

        return (
            writing_tick_callback,
            has_covered_required_set_of_write_ops,
            db_ver_seq,
        )

    def _prepare_extra_db_connector_with_patched_audit_log(self):
        db_connector_context = auth_db_connector()
        db_connector = db_connector_context.__enter__()
        self.addCleanup(db_connector_context.__exit__, None, None, None)        # noqa
        db_audit_log_actual_entries = []
        db_connector._audit_log._logger.info = db_audit_log_actual_entries.append
        return db_connector, db_audit_log_actual_entries


class _test_of__ldap_api_replacement__LdapAPI__search_structured__empty_db(
        mixin_for_tests_of__ldap_api_replacement__LdapAPI,
        unittest.TestCase):

    @staticmethod
    def data_maker(session):
        return []

    def run_code_under_test(self):
        # (we invoke the `search_structured()` method twice so that
        # `writing_tick_callback()` will be called enough times)
        self.ldap_api.search_structured()
        return self.ldap_api.search_structured()

    expected_result = {
        'ou': {
            'orgs': {'attrs': {'ou': [u'orgs']}},
            'org-groups': {'attrs': {'ou': [u'org-groups']}},
            'subsource-groups': {'attrs': {'ou': [u'subsource-groups']}},
            'sources': {'attrs': {'ou': [u'sources']}},
            'criteria': {'attrs': {'ou': [u'criteria']}},
        },
        'attrs': {},
        '_extra_': {
            'ver': EXAMPLE_DATABASE_VER,
            'timestamp': EXAMPLE_DATABASE_TIMESTAMP,
            'ignored_ip_networks': set(),
        },
    }


class _test_of__ldap_api_replacement__LdapAPI__search_structured__example_nonempty_db(
        mixin_for_tests_of__ldap_api_replacement__LdapAPI,
        unittest.TestCase):

    @staticmethod
    def data_maker(session):
        criteria_category_bots = session.query(models.CriteriaCategory).filter(
            models.CriteriaCategory.category == 'bots').one()
        yield models.CriteriaContainer(
            label='my-crit',
            criteria_categories=[criteria_category_bots])
        yield models.Org(
            org_id='my.org',
            actual_name='Actual Name Zażółć',
            email_notification_enabled=True,
            email_notification_addresses=[
                models.EMailNotificationAddress(email='address@x.foo'),
            ],
            stream_api_enabled=False,
            org_groups=[
                models.OrgGroup(org_group_id='og1', comment=u'Oh! Zażółć \U0001f340'),
            ],
            users=[
                models.User(login='foo@example.org'),
                models.User(login='spam@example.org', password='spam'),
                models.User(login='parrot@example.info', is_blocked=True),
            ])
        yield models.IgnoreList(
            label='My list of ignored IP networks',
            comment='Tralala\nZażółć\r\nBumCykCyk',
            ignored_ip_networks=[
                models.IgnoredIPNetwork(ip_network='0.0.0.0/4'),
                models.IgnoredIPNetwork(ip_network='10.20.30.0/24'),
            ])
        yield models.IgnoreList(
            label='Empty list :-|',
            ignored_ip_networks=[])
        yield models.IgnoreList(
            label='Other list of ignored IP networks...',
            ignored_ip_networks=[
                models.IgnoredIPNetwork(ip_network='10.123.0.3/27'),
            ])
        yield models.IgnoreList(
            label='Deactivated list :-O',
            active=False,
            ignored_ip_networks=[
                models.IgnoredIPNetwork(ip_network='192.168.0.0/16'),
                models.IgnoredIPNetwork(ip_network='0.0.0.0/4'),
            ])
        yield models.IgnoreList(
            label='List with some duplicates :-/',
            ignored_ip_networks=[
                models.IgnoredIPNetwork(ip_network='10.123.0.3/27'),
                models.IgnoredIPNetwork(ip_network='0.0.0.0/10'),
                models.IgnoredIPNetwork(ip_network='0.0.0.0/4'),
            ])

    def run_code_under_test(self):
        return self.ldap_api.search_structured()

    expected_result = {
        'ou': {
            'orgs': {
                'attrs': {'ou': [u'orgs']},
                'o': {
                    'my.org': {
                        'attrs': {
                            'o': [u'my.org'],
                            'name': [u'Actual Name Zażółć'],
                            'n6rest-api-full-access': ['FALSE'],
                            'n6stream-api-enabled': ['FALSE'],
                            'n6email-notifications-enabled': ['TRUE'],
                            'n6email-notifications-address': [
                                u'address@x.foo',
                            ],
                            'n6email-notifications-business-days-only': ['FALSE'],
                            'n6org-group-refint': [
                                u'cn=og1,ou=org-groups,dc=n6,dc=cert,dc=pl',
                            ]
                        },
                        'n6login': {
                            'foo@example.org': {
                                'attrs': {
                                    'n6login': [u'foo@example.org'],
                                    'n6blocked': ['FALSE'],
                                }
                            },
                            'spam@example.org': {
                                'attrs': {
                                    'n6login': [u'spam@example.org'],
                                    # note: password is consciously omitted
                                    'n6blocked': ['FALSE'],
                                }
                            },
                            'parrot@example.info': {
                                'attrs': {
                                    'n6login': [u'parrot@example.info'],
                                    'n6blocked': ['TRUE'],
                                }
                            },
                        },
                        'cn': {
                            'inside': {'attrs': {'cn': [u'inside']}},
                            'inside-ex': {'attrs': {'cn': [u'inside-ex']}},
                            'search': {'attrs': {'cn': [u'search']}},
                            'search-ex': {'attrs': {'cn': [u'search-ex']}},
                            'threats': {'attrs': {'cn': [u'threats']}},
                            'threats-ex': {'attrs': {'cn': [u'threats-ex']}},
                        },
                    },
                },
            },
            'org-groups': {
                'attrs': {'ou': [u'org-groups']},
                'cn': {
                    'og1': {
                        'attrs': {
                            'cn': [u'og1'],
                            'description': [u'Oh! Zażółć \U0001f340'],
                        },
                        'cn': {
                            'inside': {'attrs': {'cn': [u'inside']}},
                            'search': {'attrs': {'cn': [u'search']}},
                            'threats': {'attrs': {'cn': [u'threats']}},
                        },
                    },
                }
            },
            'subsource-groups': {'attrs': {'ou': [u'subsource-groups']}},
            'sources': {'attrs': {'ou': [u'sources']}},
            'criteria': {
                'attrs': {'ou': [u'criteria']},
                'cn': {
                    'my-crit': {
                        'attrs': {
                            'cn': [u'my-crit'],
                            'n6category': [u'bots'],
                        }
                    }
                }
            },
        },
        'attrs': {},
        '_extra_': {
            'ver': EXAMPLE_DATABASE_VER,
            'timestamp': EXAMPLE_DATABASE_TIMESTAMP,
            'ignored_ip_networks': {
                '0.0.0.0/4',
                '0.0.0.0/10',
                '10.20.30.0/24',
                '10.123.0.3/27',
            },
        },
    }


class _test_of__ldap_api_replacement__LdapAPI__peek_database_ver_and_timestamp(
        mixin_for_tests_of__ldap_api_replacement__LdapAPI,
        unittest.TestCase):

    data_maker = staticmethod(
        _test_of__ldap_api_replacement__LdapAPI__search_structured__example_nonempty_db.data_maker)

    def run_code_under_test(self):
        return self.ldap_api.peek_database_ver_and_timestamp()

    expected_result = (
        EXAMPLE_DATABASE_VER,
        EXAMPLE_DATABASE_TIMESTAMP,
    )

    require_covering_full_set_of_write_ops = False


#
# Tests of some directly-auth-related methods of n6lib.auth_db.api.AuthManageAPI
#

class mixin_for_tests_of__auth_db__api__AuthManageAPI:

    @classmethod
    def iter_test_case_classes(cls):
        for subclass in all_subclasses(cls):
            if isinstance(subclass, type) and issubclass(subclass, unittest.TestCase):
                yield subclass

    # noinspection PyUnresolvedReferences,PyAttributeOutsideInit,PyPep8Naming
    def setUp(self):
        self.addCleanup(drop_db)
        create_and_init_db(timeout=60)
        populate_db_with_test_data(self.data_maker)
        self.api = api = AuthManageAPI(settings=prepare_auth_db_settings())
        self.addCleanup(lambda: api.__exit__(*sys.exc_info()))
        api.__enter__()

    @staticmethod
    def data_maker(session):
        raise NotImplementedError


class _test_of_authentication_related_methods_of__auth_db__api__AuthManageAPI(
        mixin_for_tests_of__auth_db__api__AuthManageAPI,
        unittest.TestCase):

    @staticmethod
    def data_maker(session):
        o1 = models.Org(org_id='o1')
        o2 = models.Org(org_id='o2')
        o3 = models.Org(org_id='o3')
        u1 = models.User(
            login='some@example.com',
            password=models.User.get_password_hash_or_none('qwe123'),
            org=o1,
        )
        u2 = models.User(
            login='withnull@example.com',
            # `password` omitted -> NULL
            org=o1,
        )
        u3 = models.User(
            login='withnullagain@example.com',
            password=None,  # `password` explicitly specified as NULL
            org=o1,
        )
        u4 = models.User(
            login='withempty@example.com',
            password='',      # `password` empty!
            org=o1,
        )
        u5 = models.User(
            login='withunhashed@example.com',
            password='qwe123',  # `password` unhashed!
            org=o1,
        )
        u6 = models.User(
            login='another@example.com',
            password=models.User.get_password_hash_or_none('qwe123'),
            org=o1,
        )
        u7 = models.User(
            login='yetanother@example.com',
            password=models.User.get_password_hash_or_none('qwe123'),
            org=o2,
        )
        u8 = models.User(
            login='andyetanother@example.com',
            password=models.User.get_password_hash_or_none('kukuRyQu'),
            org=o2,
        )
        u9 = models.User(
            login='blocked-1@example.com',
            password=models.User.get_password_hash_or_none('qwe123'),
            is_blocked=True,
            org=o1,
        )
        u10 = models.User(
            login='blocked-2@example.com',
            password=models.User.get_password_hash_or_none('qwe123'),
            is_blocked=True,
            org=o3,
        )
        return [
            o1, o2, o3,
            u1, u2, u3, u4, u5, u6, u7, u8, u9, u10,
        ]

    def _do_test(self, org_id, login, password,
                 expect_org_fail=False,
                 expect_password_fail=False):
        org_check = self.api.do_nonblocked_user_and_org_exist_and_match(login, org_id)
        password_check = self.api.do_nonblocked_user_and_password_exist_and_match(login, password)
        if expect_org_fail:
            self.assertFalse(org_check)
        else:
            self.assertTrue(org_check)
        if expect_password_fail:
            self.assertFalse(password_check)
        else:
            self.assertTrue(password_check)

    def test__success_1(self):
        self._do_test('o1', 'some@example.com', 'qwe123')

    def test__success_2(self):
        self._do_test(u'o1', 'another@example.com', u'qwe123')

    def test__success_3(self):
        self._do_test(u'o2', u'yetanother@example.com', 'qwe123')

    def test__success_4(self):
        self._do_test('o2', u'andyetanother@example.com', u'kukuRyQu')

    def test__password_wrong_1(self):
        self._do_test(u'o1', u'some@example.com', u'kukuRyQu',
                      expect_password_fail=True)

    def test__password_wrong_2(self):
        self._do_test('o2', 'andyetanother@example.com', 'qwe123',
                      expect_password_fail=True)

    def test__password_empty(self):
        self._do_test('o1', 'some@example.com', '',
                      expect_password_fail=True)

    def test__password_nonempty_against_null_1(self):
        self._do_test('o1', 'withnull@example.com', 'qwe123',
                      expect_password_fail=True)

    def test__password_nonempty_against_null_2(self):
        self._do_test('o1', 'withnullagain@example.com', u'qwe123',
                      expect_password_fail=True)

    def test__password_empty_against_null_1(self):
        self._do_test('o1', 'withnull@example.com', '',
                      expect_password_fail=True)

    def test__password_empty_against_null_2(self):
        self._do_test(u'o1', u'withnullagain@example.com', u'',
                      expect_password_fail=True)

    def test__password_nonempty_against_empty(self):
        self._do_test('o1', 'withempty@example.com', 'qwe123',
                      expect_password_fail=True)

    def test__password_empty_against_empty(self):
        self._do_test('o1', 'withempty@example.com', '',
                      expect_password_fail=True)

    def test__user_not_matching_org_1(self):
        self._do_test(u'o1', u'yetanother@example.com', u'qwe123',
                      expect_org_fail=True)

    def test__user_not_matching_org_2(self):
        self._do_test('o2', 'some@example.com', 'qwe123',
                      expect_org_fail=True)

    def test__user_not_matching_org_3(self):
        self._do_test('o2', u'some@example.com', u'qwe123',
                      expect_org_fail=True)

    def test__blocked_user_1(self):
        self._do_test('o1', 'blocked-1@example.com', u'qwe123',
                      expect_password_fail=True,
                      expect_org_fail=True)

    def test__blocked_user_2(self):
        self._do_test('o3', 'blocked-2@example.com', 'qwe123',
                      expect_password_fail=True,
                      expect_org_fail=True)

    def test__nonexistent_user_1(self):
        self._do_test('o1', 'nonext@example.com', u'qwe123',
                      expect_password_fail=True,
                      expect_org_fail=True)

    def test__nonexistent_user_2(self):
        self._do_test('o3', 'nonext@example.com', 'qwe123',
                      expect_password_fail=True,
                      expect_org_fail=True)

    def test__nonexistent_org(self):
        self._do_test('nonext', 'some@example.com', 'qwe123',
                      expect_org_fail=True)

    # the following 3 tests concern cases related to
    # invalid data in the Auth DB: unhashed `password`

    def test__password_against_unhashed(self):
        self._do_test('o1', 'withunhashed@example.com', 'qwe123',
                      expect_password_fail=True)

    def test__password_wrong_against_unhashed(self):
        self._do_test('o1', u'withunhashed@example.com', 'kukuRyQu',
                      expect_password_fail=True)

    def test__password_empty_against_unhashed(self):
        self._do_test(u'o1', 'withunhashed@example.com', '',
                      expect_password_fail=True)


#
# The actual invocation of the main script
#

if __name__ == "__main__":
    main(sys.argv)

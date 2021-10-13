# Copyright (c) 2018-2021 NASK. All rights reserved.

from __future__ import print_function                                            #3--
from __future__ import absolute_import                                           #3--
                                                                                 #3--
from builtins import input                                                       #3--
import argparse
import ast
import contextlib
import getpass
import os
import os.path as osp
import sys
import textwrap

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm
from alembic import command
from alembic.config import Config
from pkg_resources import (
    Requirement,
    resource_filename,
)

from n6lib.auth_db import (
    ALEMBIC_DB_CONFIGURATOR_SETTINGS_DICT_ENVIRON_VAR_NAME,
    MYSQL_CHARSET,
    MYSQL_COLLATE,
)
from n6lib.auth_db.models import (
    Base,
    CriteriaCategory,
    Org,
    User,
    Source,
    Subsource,
)
from n6lib.auth_db.config import SQLAuthDBConnector
from n6lib.const import CATEGORY_ENUMS
from n6lib.common_helpers import (
    ascii_str,
    make_hex_id,
)
from n6lib.class_helpers import attr_required


#
# Base and mixin classes
#

class BaseAuthDBScript(object):

    # The docstring should be set in subclasses because it
    # is to be used as a part of the script's help text.
    __doc__ = None

    db_connector_factory = SQLAuthDBConnector

    @classmethod
    def run_from_commandline(cls, argv):
        prog = osp.basename(argv[0])
        parser = cls.make_argument_parser(prog)
        arguments = cls.parse_arguments(parser, argv)
        script = cls(**arguments)
        script_descr = "The '{}' script".format(prog)
        script.msg('{} started.'.format(script_descr))
        try:
            with script:
                exit_code = script.run()
        except sqlalchemy.exc.StatementError as exc:
            script.msg_error('Database operation failure: {}.'.format(ascii_str(exc)))
            exit_code = 1
        if exit_code:
            script.msg('{} exits with code {}.'.format(script_descr, exit_code))
            sys.exit(exit_code)
        else:
            script.msg('{} exits gracefully.'.format(script_descr))
            sys.exit(0)

    @classmethod
    @attr_required('__doc__')
    def make_argument_parser(cls, prog):
        parser = argparse.ArgumentParser(
            prog=prog,
            description=textwrap.dedent(cls.__doc__))
        parser.add_argument('-q', '--quiet', action='store_true',
                            help=('suppress most of printed messages'))
        return parser

    @classmethod
    def parse_arguments(cls, parser, argv):
        arguments_namespace = parser.parse_args(args=argv[1:])
        return vars(arguments_namespace)


    def __init__(self, quiet=False, settings=None, config_section=None, **kwargs):
        self.quiet = quiet
        self.settings = settings
        self.config_section = config_section
        self.db_connector = self.db_connector_factory(
            settings=settings,
            config_section=config_section)
        super(BaseAuthDBScript, self).__init__(**kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        self.db_connector.dispose_engine()


    def run(self):
        raise NotImplementedError


    @property
    def db_session(self):
        return self.db_connector.get_current_session()

    @property
    def db_engine(self):
        return self.db_connector.engine

    @property
    def db_name(self):
        return self.db_engine.url.database

    @contextlib.contextmanager
    def secondary_db_engine(self):
        # not bound to any specific MariaDB's database
        engine = self.db_connector.make_db_engine(url_overwrite_attrs={'database': None})
        try:
            yield engine
        finally:
            engine.dispose()


    # Script message printing helpers

    def msg(self, *print_args):
        self._print_info_msg(
            lead='*',
            print_args=print_args)

    def msg_sub(self, *print_args):
        self._print_info_msg(
            lead='  *',
            print_args=print_args)

    def msg_warn(self, *print_args):
        self._print_alarm_msg(
            lead='*** WARNING ***',
            print_args=print_args)

    def msg_error(self, *print_args):
        self._print_alarm_msg(
            lead='*** ERROR ***',
            print_args=print_args)

    def msg_caution(self, *print_args):
        self._print_alarm_msg(
            lead='*** CAUTION ***',
            lead_end='\n\n',
            print_args=print_args)

    def msg_vertical_space(self):
        if self._soft_newline:
            print()
            self._soft_newline = False

    def _print_info_msg(self, lead, print_args=()):
        if not self.quiet:
            print(lead, *print_args)
            self._soft_newline = True

    def _print_alarm_msg(self, lead, lead_end=' ', print_args=()):
        if self._soft_newline:
            print(file=sys.stderr)
        print(lead, file=sys.stderr, end=lead_end)
        print(*print_args, file=sys.stderr, end='\n\n')
        self._soft_newline = False

    _soft_newline = True


    # Script environment manipulation helpers

    @contextlib.contextmanager
    def patched_os_environ_var(self, var_name, value):
        saved_value = os.environ.get(var_name)
        try:
            self._set_or_unset_os_environ_var(var_name, value)
            yield
        finally:
            self._set_or_unset_os_environ_var(var_name, saved_value)

    def _set_or_unset_os_environ_var(self, var_name, value):
        if value is None:
            os.environ.pop(var_name, None)
        else:
            os.environ[var_name] = value

    @contextlib.contextmanager
    def changed_working_dir(self, working_dir):
        saved_working_dir = os.getcwd()
        try:
            os.chdir(working_dir)
            yield
        finally:
            os.chdir(saved_working_dir)

    @contextlib.contextmanager
    def suppressed_stderr(self, suppress_only_if_quiet=False):
        if self.quiet or not suppress_only_if_quiet:
            with self._simpleminded_stderr_patcher():
                yield
        else:
            yield

    class _simpleminded_stderr_patcher(object):
        def __init__(self):
            self._replaced_obj_stack = []
        def __enter__(self):
            self._replaced_obj_stack.append(sys.stderr)
            sys.stderr = self
        def __exit__(self, *exc_info):
            sys.stderr = self._replaced_obj_stack.pop()
        def __get_self(*args, **_):
            return args[0]
        __getattr__ = __get_self
        __call__ = __get_self


class PromptingForYesOrNoMixin(object):

    # noinspection PyUnresolvedReferences
    @classmethod
    def make_argument_parser(cls, prog):
        parser = super(PromptingForYesOrNoMixin, cls).make_argument_parser(prog)
        parser.add_argument('-y', '--yes', '--assume-yes',
                            action='store_true', dest='assume_yes',
                            help=("act non-interactively, assuming "
                                  "'yes' as answers to any prompts"))
        return parser

    def __init__(self, assume_yes=False, **kwargs):
        self.assume_yes = assume_yes
        super(PromptingForYesOrNoMixin, self).__init__(**kwargs)

    # noinspection PyUnresolvedReferences
    def yes_or_no(self, question, caution=None):
        if self.assume_yes:
            return True

        if caution is not None:
            self.msg_caution(caution)
        self.msg_vertical_space()
        answer = input(question + ' [y/N] ')
        print()
        if answer.lower() in ('y', 'yes'):
            self.msg("The 'yes' answer has been given.")
            return True

        if answer.lower() in ('n', 'no', ''):
            self.msg("The 'no' answer has been given.")
        else:
            self.msg("Unrecognized answer: {!r}, assuming 'no'.".format(answer))
        return False


class DropDatabaseIfExistsMixin(PromptingForYesOrNoMixin):

    # noinspection PyUnresolvedReferences
    def drop_db_if_exists(self, secondary_db_engine):
        if self.yes_or_no(
                caution=('The auth database, if it exists, is to be '
                         'dropped, i.e., completely removed!'),
                question='Are you sure you want to drop the auth database?'):
            self.msg('Dropping the auth database if it exists...')
            quoted_db_name = self.db_connector.quote_sql_identifier(self.db_name)
            query_text = 'DROP DATABASE IF EXISTS {}'.format(quoted_db_name)
            with self.suppressed_stderr(suppress_only_if_quiet=True):
                with secondary_db_engine.connect() as connection:
                    connection.execute(query_text)
            return True
        else:
            self.msg('Resigned from dropping the auth database.')
            return False


#
# Actual script classes
#

class CreateAndInitializeAuthDB(DropDatabaseIfExistsMixin, BaseAuthDBScript):

    """
    Create the Auth DB and its tables, and initialize them with the
    minimum content (including all n6 event categories).

    Note: this script, *unless* executed with the -o flag, ensures that
    the schema of the (newly created) auth database will be the most
    fresh one (i.e., just as if all available Alembic migrations had
    already been applied) and, *unless* the -A flag is used, the
    database will be stamped as being at the `head` (i.e., the newest)
    Alembic revision.
    """

    @classmethod
    def make_argument_parser(cls, prog):
        parser = super(CreateAndInitializeAuthDB, cls).make_argument_parser(prog)
        parser.add_argument('-A', '--no-alembic-stuff', action='store_true',
                            help=('do *not* touch the resultant database with '
                                  'any Alembic-specific tools, especially '
                                  'do *not* stamp the database as being at '
                                  'the `head` Alembic revision'))
        parser.add_argument('-D', '--drop-db-if-exists', action='store_true',
                            help=('first, drop (i.e., completely remove!) '
                                  'the existing auth database (if any), '
                                  'and only then create/initialize what '
                                  'is needed...'))
        parser.add_argument('-o', '--only-create-db', action='store_true',
                            help=('*only* create the database, that is, do '
                                  '*not* create/initialize any other things '
                                  '(in particular, do not create any tables)'))
        return parser

    def __init__(self,
                 no_alembic_stuff=False,
                 drop_db_if_exists=False,
                 only_create_db=False,
                 **kwargs):
        self._no_alembic_stuff = no_alembic_stuff
        self._drop_db_if_exists = drop_db_if_exists
        self._only_create_db = only_create_db
        super(CreateAndInitializeAuthDB, self).__init__(**kwargs)

    def run(self):
        with self.secondary_db_engine() as secondary_db_engine:
            if self._drop_db_if_exists:
                dropped = self.drop_db_if_exists(secondary_db_engine)
                if not dropped:
                    self.msg_error(
                        'Without dropping the auth database '
                        'no further actions can be performed.')
                    return 1
            self.create_db(secondary_db_engine)
        if not self._only_create_db:
            self.create_tables()
            with self.db_connector:
                self.insert_criteria_categories()
            if not self._no_alembic_stuff:
                self.stamp_as_alembic_head()
        return 0

    def create_db(self, secondary_db_engine):
        self.msg('Creating the new auth database...')
        quoted_db_name = self.db_connector.quote_sql_identifier(self.db_name)
        sql_raw = ('CREATE DATABASE {} '
                   'CHARACTER SET :charset COLLATE :collate'.format(quoted_db_name))
        sql = sqlalchemy.text(sql_raw).bindparams(
            charset=(MYSQL_CHARSET),
            collate=(MYSQL_COLLATE))
        with secondary_db_engine.connect() as connection:
            connection.execute(sql)

    def create_tables(self):
        self.msg('Creating the new auth database\'s tables...')
        Base.metadata.create_all(self.db_engine)

    def insert_criteria_categories(self):
        self.msg('Inserting new \'criteria_category\' records...')
        for category in CATEGORY_ENUMS:
            criteria_category = self.db_session.query(CriteriaCategory).get(category)
            if criteria_category is None:
                criteria_category = CriteriaCategory(category=category)
                self.msg_sub('{} "{}"'.format(CriteriaCategory.__name__, criteria_category))
                self.db_session.add(criteria_category)

    def stamp_as_alembic_head(self):
        revision = 'head'
        self.msg(
            'Invoking appropriate Alembic tools to stamp the auth database '
            'as being at the `{}` Alembic revision...'.format(revision))
        alembic_ini_path = resource_filename(
            Requirement.parse('n6lib'),
            'n6lib/auth_db/alembic.ini')
        with self.patched_os_environ_var(
                ALEMBIC_DB_CONFIGURATOR_SETTINGS_DICT_ENVIRON_VAR_NAME,
                self._prepare_alembic_db_configurator_settings_dict_raw()), \
             self.changed_working_dir(osp.dirname(alembic_ini_path)), \
             self.suppressed_stderr(suppress_only_if_quiet=True):
            alembic_cfg = Config(alembic_ini_path)
            command.stamp(alembic_cfg, revision)

    def _prepare_alembic_db_configurator_settings_dict_raw(self):
        if self.settings is not None:
            alembic_db_configurator_settings_dict = dict(self.settings)
            alembic_db_configurator_settings_dict_raw = repr(alembic_db_configurator_settings_dict)
            try:
                ast.literal_eval(alembic_db_configurator_settings_dict_raw)
            except Exception:
                self.msg_error(
                    'when none of the -A or -o options are used, the '
                    'auth database configurator settings dict, if '
                    'present (i.e. if it is not None), must contain '
                    'only keys and values representable as pure Python '
                    'literals (got: {!r})'.format(
                        alembic_db_configurator_settings_dict))
                raise ValueError('settings dict not representable as pure literal')
        else:
            alembic_db_configurator_settings_dict_raw = None
        return alembic_db_configurator_settings_dict_raw


class DropAuthDB(DropDatabaseIfExistsMixin, BaseAuthDBScript):

    """
    Just drop (i.e., completely remove!) the Auth DB if it exists.
    """

    def run(self):
        with self.secondary_db_engine() as secondary_db_engine:
            dropped = self.drop_db_if_exists(secondary_db_engine)
            if dropped:
                return 0
        self.msg_error('The main goal of the script has not been achieved.')
        return 1


class PopulateAuthDB(BaseAuthDBScript):

    """
    Populate the Auth DB with some basic/example data:

    * the specified (or default) data sources with appropriate general
      access subsources (if not added yet);
    * a new organization (and a new user associated with it; if you use
      option -p you will also be asked for the password) with granted
      access to the data sources mentioned above; note that you may
      also need to make some REST API resources accessible for this
      organization (see the options: -i, -t and -s);
    * n6 event categories, if not already added.
    """

    ANONYMIZED_SOURCE_PREFIX = 'hidden.'
    DEFAULT_SOURCES = [
        'abuse-ch.spyeye-doms',
        'abuse-ch.spyeye-ips',
        'abuse-ch.zeus-doms',
        'abuse-ch.zeus-ips',
        'abuse-ch.zeustracker',
        'abuse-ch.palevo-doms',
        'abuse-ch.palevo-ips',
        'abuse-ch.feodotracker',
        'abuse-ch.ransomware',
        'abuse-ch.ssl-blacklist',
        'abuse-ch.ssl-blacklist-dyre',
        'abuse-ch.urlhaus-urls',
        'abuse-ch.urlhaus-payloads-urls',
        'abuse-ch.urlhaus-payloads',
        'badips-com.server-exploit-list',
        'circl-lu.misp',
        'dns-bh.malwaredomainscom',
        'greensnow-co.list-txt',
        'packetmail-net.list',
        'packetmail-net.ratware-list',
        'packetmail-net.others-list',
        'spam404-com.scam-list',
        'zoneh.rss',
    ]

    @classmethod
    def make_argument_parser(cls, prog):
        parser = super(PopulateAuthDB, cls).make_argument_parser(prog)
        parser.add_argument('org_id',
                            metavar='ORG_ID',
                            help='organization identifier (domain-name-like)')
        parser.add_argument('login',
                            metavar='USER_LOGIN',
                            help='user login (email address)')
        parser.add_argument('-p', '--set-password',
                            action='store_true',
                            help=('set the user password, after asking for it '
                                  'interactively (do not use this option in '
                                  'batch scripts)'))
        parser.add_argument('-F', '--full-access',
                            action='store_true',
                            help=('grant (to the added organization) privileged '
                                  'data access rights (in particular, to access '
                                  'restricted and deanonymized data); note that '
                                  'you still need to grant access to some access '
                                  'zones (see the options: -i, -t and -s)'))
        parser.add_argument('-S', '--sources',
                            metavar='SOURCE',
                            nargs='*',
                            default=cls.DEFAULT_SOURCES,
                            help=('data source identifiers for whom general '
                                  'access subsources shall be provided, to whom '
                                  'access shall be granted; defaults are: {} '
                                  '(note that by specifying this option you '
                                  'completely override them)'.format(
                                      ' '.join(cls.DEFAULT_SOURCES))))
        parser.add_argument('-i', '--access-to-inside',
                            action='store_true',
                            help=('grant (to the added organization) access to '
                                  'the "inside" access zone (which, in particular, '
                                  'corresponds to the "/report/inside" REST API '
                                  'resource)'))
        parser.add_argument('-t', '--access-to-threats',
                            action='store_true',
                            help=('grant (to the added organization) access to '
                                  'the "threats" access zone (which, in particular, '
                                  'corresponds to the "/report/threats" REST API '
                                  'resource)'))
        parser.add_argument('-s', '--access-to-search',
                            action='store_true',
                            help=('grant (to the added organization) access to '
                                  'the "search" access zone (which, in particular, '
                                  'corresponds to the "/search/events" REST API '
                                  'resource)'))
        return parser

    @classmethod
    def parse_arguments(cls, parser, argv):
        arguments = super(PopulateAuthDB, cls).parse_arguments(parser, argv)
        if arguments.pop('set_password'):
            arguments['password'] = getpass.getpass(
                'Please, type in the password for the new user who '
                'will be identified by the organization id "{org_id}" '
                'and the user login "{login}": '.format(**arguments))
        else:
            arguments['password'] = None
        return arguments

    def __init__(self, org_id, login, password=None, full_access=False,
                 sources=tuple(DEFAULT_SOURCES),
                 access_to_inside=True,
                 access_to_threats=True,
                 access_to_search=False,
                 **kwargs):
        self.org_id = org_id
        self.login = login
        self.password = password
        self.full_access = full_access
        self.source_ids = sources
        self.access_to_inside = access_to_inside
        self.access_to_threats = access_to_threats
        self.access_to_search = access_to_search
        super(PopulateAuthDB, self).__init__(**kwargs)

    def run(self):
        self.msg('Inserting records...')
        with self.db_connector:
            org = Org(org_id=self.org_id,
                      full_access=self.full_access)
            user = User(login=self.login)
            user.password = user.get_password_hash_or_none(self.password)
            org.users.append(user)
            sources = list(self._generate_sources())
            subsources = list(self._generate_subsources(sources, org))
            categories = list(self._generate_criteria_categories())
            self._apply_org_permissions(org)
            self.msg_sub(org)
            self.db_session.add(org)
            self.msg_sub(user)
            self.db_session.add(user)
            self.db_session.add_all(sources)
            self.db_session.add_all(subsources)
            self.db_session.add_all(categories)

    def _generate_sources(self):
        for i, source_id in enumerate(self.source_ids):
            source = self.db_session.query(Source).get(source_id)
            if source is None:
                source = Source(
                    source_id=source_id,
                    anonymized_source_id=self.ANONYMIZED_SOURCE_PREFIX + make_hex_id(16))
            self.msg_sub(source)
            yield source

    def _generate_subsources(self, sources, org):
        for source in sources:
            source_id = source.source_id
            label = 'general access to ' + source_id
            subsource = self.db_session.query(Subsource).get(label)
            if subsource is None:
                subsource = Subsource(label=label, source=source)
            if subsource.source != source:
                raise ValueError('expected that {!r} has source=={!r}'
                                 .format(subsource, source) + '_' + str(subsource.source))
            if self.access_to_inside and org not in subsource.inside_orgs:
                subsource.inside_orgs.append(org)
            if self.access_to_threats and org not in subsource.threats_orgs:
                subsource.threats_orgs.append(org)
            if self.access_to_search and org not in subsource.search_orgs:
                subsource.search_orgs.append(org)
            self.msg_sub(subsource)
            yield subsource

    def _generate_criteria_categories(self):
        for category in CATEGORY_ENUMS:
            criteria_category = self.db_session.query(CriteriaCategory).get(category)
            if criteria_category is None:
                criteria_category = CriteriaCategory(category=category)
                self.msg_sub('[previously not added] {} "{}"'.format(
                    CriteriaCategory.__name__,
                    criteria_category))
                yield criteria_category

    def _apply_org_permissions(self, org):
        org.access_to_inside = self.access_to_inside
        org.access_to_search = self.access_to_search
        org.access_to_threats = self.access_to_threats


def create_and_initialize_auth_db():
    CreateAndInitializeAuthDB.run_from_commandline(sys.argv)


def drop_auth_db():
    DropAuthDB.run_from_commandline(sys.argv)


def populate_auth_db():
    PopulateAuthDB.run_from_commandline(sys.argv)

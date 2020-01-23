# Copyright (c) 2013-2020 NASK. All rights reserved.

from __future__ import print_function

import argparse
import contextlib
import getpass
import sys
import textwrap

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm

from n6lib.auth_db import (
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


class _BaseAuthDBScript(object):

    # The docstring should be set in subclasses because it
    # is to be used as a part of the script's help text.
    __doc__ = None

    @classmethod
    def run_from_commandline(cls):
        parser = cls.make_argument_parser()
        arguments = cls.parse_arguments(parser)
        try:
            script = cls(**arguments)
            script.run()
        except sqlalchemy.exc.StatementError as exc:
            sys.exit(ascii_str(exc))
        else:
            script.msg('Done.')

    @classmethod
    @attr_required('__doc__')
    def make_argument_parser(cls):
        parser = argparse.ArgumentParser(description=textwrap.dedent(cls.__doc__))
        parser.add_argument('-q', '--quiet', action='store_true',
                            help=('suppress most of printed messages'))
        return parser

    @classmethod
    def parse_arguments(cls, parser):
        arguments_namespace = parser.parse_args()
        return vars(arguments_namespace)


    def __init__(self, quiet=False, settings=None, config_section=None):
        self.db_session = None  # to be set in `db_session_set_up()`
        self.quiet = quiet
        self._db_connector = SQLAuthDBConnector(settings=settings, config_section=config_section)

    @property
    def db_engine(self):
        return self._db_connector.engine

    @property
    def db_name(self):
        return self.db_engine.url.database


    def run(self):
        raise NotImplementedError


    @contextlib.contextmanager
    def db_session_set_up(self):
        with self._db_connector as db_session:
            self.db_session = db_session
            try:
                yield db_session
            finally:
                self.db_session = None

    @contextlib.contextmanager
    def secondary_db_engine(self):
        # not bound to any specific MariaDB's database
        engine = self._db_connector.make_db_engine(url_overwrite_attrs={'database': None})
        try:
            yield engine
        finally:
            engine.dispose()

    def quote_sql_identifier(self, sql_identifier):
        return self._db_connector.quote_sql_identifier(sql_identifier)

    def msg(self, *args):
        if not self.quiet:
            print('*', *args)

    def msg_sub(self, *args):
        if not self.quiet:
            print('  *', *args)


class _DropDatabaseMixin(object):

    # noinspection PyUnresolvedReferences
    def drop_db_if_exists(self, secondary_db_engine):
        self.msg('Dropping auth database if it exists...')
        quoted_db_name = self.quote_sql_identifier(self.db_name)
        secondary_db_engine.execute('DROP DATABASE IF EXISTS {}'.format(quoted_db_name))


class CreateAndInitializeAuthDB(_DropDatabaseMixin, _BaseAuthDBScript):

    """
    Create the Auth DB and initialize it with the minimum content
    (including all n6 event categories).
    """

    @classmethod
    def make_argument_parser(cls):
        parser = super(CreateAndInitializeAuthDB, cls).make_argument_parser()
        parser.add_argument('-D', '--drop-db-if-exists', action='store_true',
                            help=('first, drop (i.e., completely remove!) '
                                  'the existing Auth DB (if any)'))
        return parser

    def __init__(self, drop_db_if_exists=False, **kwargs):
        self._drop_db_if_exists = drop_db_if_exists
        super(CreateAndInitializeAuthDB, self).__init__(**kwargs)

    def run(self):
        with self.secondary_db_engine() as secondary_db_engine:
            if self._drop_db_if_exists:
                self.drop_db_if_exists(secondary_db_engine)
            self.create_db(secondary_db_engine)
        self.create_tables()
        with self.db_session_set_up():
            self.insert_criteria_categories()

    def create_db(self, secondary_db_engine):
        self.msg('Creating new auth database...')
        quoted_db_name = self.quote_sql_identifier(self.db_name)
        sql_raw = ('CREATE DATABASE {} '
                   'CHARACTER SET :charset COLLATE :collate'.format(quoted_db_name))
        sql = sqlalchemy.text(sql_raw).bindparams(
            charset=(MYSQL_CHARSET),
            collate=(MYSQL_COLLATE))
        secondary_db_engine.execute(sql)

    def create_tables(self):
        self.msg('Creating new auth database tables...')
        Base.metadata.create_all(self.db_engine)

    def insert_criteria_categories(self):
        self.msg('Inserting `criteria_category` records...')
        for category in CATEGORY_ENUMS:
            self.msg_sub('{} "{}"'.format(CriteriaCategory.__name__, category))
            self.db_session.add(CriteriaCategory(category=category))


class DropAuthDB(_DropDatabaseMixin, _BaseAuthDBScript):

    """
    Just drop (i.e., completely remove!) the Auth DB if it exists.
    """

    def run(self):
        with self.secondary_db_engine() as secondary_db_engine:
            self.drop_db_if_exists(secondary_db_engine)


class PopulateAuthDB(_BaseAuthDBScript):

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
    def make_argument_parser(cls):
        parser = super(PopulateAuthDB, cls).make_argument_parser()
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
    def parse_arguments(cls, parser):
        arguments = super(PopulateAuthDB, cls).parse_arguments(parser)
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
        with self.db_session_set_up():
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
    CreateAndInitializeAuthDB.run_from_commandline()


def drop_auth_db():
    DropAuthDB.run_from_commandline()


def populate_auth_db():
    PopulateAuthDB.run_from_commandline()

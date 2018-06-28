# Copyright (c) 2013-2018 NASK. All rights reserved.

import argparse
import getpass
import textwrap

from n6lib.auth_db.config import SQLAuthDBConfigMixin
from n6lib.auth_db.models import (
    CriteriaCategory,
    Org,
    Source,
    Subsource,
    User,
    db_session,
)
from n6lib.common_helpers import make_hex_id
from n6lib.const import CATEGORY_ENUMS


class PopulateAuthDB(object):

    """
    Populate auth database with some basic data:

    * all n6 event categories (if not added yet);
    * the specified (or default) data sources with appropriate general
      access subsources (if not added yet);
    * a new organization (and a new user associated with it - you will
      be asked for the password!) with granted access to those data
      sources; note that you also need to make some REST API resources
      accessible for this organization (see the options: -i, -t and -s).
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
    def run_from_commandline(cls):
        parser = argparse.ArgumentParser(description=textwrap.dedent(cls.__doc__))
        parser.add_argument('org_id', metavar='ORG_ID',
                            help='organization identifier (domain-name-like)')
        parser.add_argument('login', metavar='USER_LOGIN',
                            help='user login (email address)')
        parser.add_argument('-F', '--full-access', action='store_true',
                            help=('grant (to the added organization) superuser rights '
                                  '(access to restricted and deanonymized data etc.); '
                                  'note that you still need to grant access to some '
                                  'access zones (see the options: -i, -t and -s)'))
        parser.add_argument('-S', '--sources', metavar='SOURCE',
                            nargs='*', default=cls.DEFAULT_SOURCES,
                            help=('data source identifiers for whom general access subsources '
                                  'shall be provided, to whom access shall be granted; '
                                  'defaults are (note that this option overrides them): {}'
                                  .format(' '.join(cls.DEFAULT_SOURCES))))
        parser.add_argument('-i', '--access-to-inside', action='store_true',
                            help=('grant (to the added organization) '
                                  'access to the "inside" access zone '
                                  '(the "/report/inside" REST API resource)'))
        parser.add_argument('-t', '--access-to-threats', action='store_true',
                            help=('grant (to the added organization) '
                                  'access to the "threats" access zone '
                                  '(the "/report/threats" REST API resource)'))
        parser.add_argument('-s', '--access-to-search', action='store_true',
                            help=('grant (to the added organization) '
                                  'access to the "search" access zone '
                                  '(the "/search/events" REST API resource)'))
        arguments = parser.parse_args()
        arguments.password = getpass.getpass(
            'Please, type in the password for the new user who will be'
            'identified by organization id "{}" and user login "{}": '
            .format(arguments.org_id, arguments.login))
        cls(**vars(arguments)).run()

    def __init__(self, org_id, login, password, full_access=False,
                 sources=tuple(DEFAULT_SOURCES),
                 access_to_inside=True,
                 access_to_threats=True,
                 access_to_search=False):
        self.org_id = org_id
        self.login = login
        self.password = password
        self.full_access = full_access
        self.sources = sources
        self.access_to_inside = access_to_inside
        self.access_to_threats = access_to_threats
        self.access_to_search = access_to_search
        engine = SQLAuthDBConfigMixin().engine
        db_session.configure(bind=engine)

    def run(self):
        print '* Creating records...'
        org = Org(org_id=self.org_id,
                  full_access=self.full_access)
        user = User(login=self.login)
        user.password = user.get_password_hash_or_none(self.password)
        org.users.append(user)
        sources = list(self._generate_sources(self.sources))
        subsources = list(self._generate_subsources(sources, org))
        categories = list(self._generate_categories())
        self._apply_org_permissions(org)
        print org
        db_session.add(org)
        print user
        db_session.add(user)
        db_session.add_all(sources)
        db_session.add_all(subsources)
        db_session.add_all(categories)
        db_session.commit()
        print '* Done.'

    def _generate_sources(self, sources):
        for i, source_id in enumerate(sources):
            source = db_session.query(Source).get(source_id)
            if source is None:
                source = Source(
                    source_id=source_id,
                    anonymized_source_id=self.ANONYMIZED_SOURCE_PREFIX + make_hex_id(16))
            print source
            yield source

    def _generate_subsources(self, sources, org):
        for source in sources:
            source_id = source.source_id
            label = 'general access to ' + source_id
            subsource = db_session.query(Subsource).get(label)
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
            print subsource
            yield subsource

    def _generate_categories(self):
        for category in CATEGORY_ENUMS:
            criteria_category = db_session.query(CriteriaCategory).get(category)
            if criteria_category is None:
                criteria_category = CriteriaCategory(category=category)
            yield criteria_category

    def _apply_org_permissions(self, org):
        org.access_to_inside = self.access_to_inside
        org.access_to_search = self.access_to_search
        org.access_to_threats = self.access_to_threats


def main():
    PopulateAuthDB.run_from_commandline()


if __name__ == '__main__':
    main()

# Copyright (c) 2013-2024 NASK. All rights reserved.
# + Some portions of the code in of this module (namely, those methods
#   of the `LdapAPI` class which have a "Copied from: ..." comments in
#   their docstrings) were copied from the *python-ldap* library
#   (distributed under Python-style open source license).
#   Copyright (c) 2008-2017, *python-ldap* Project Team.
#   All rights reserved.

# NOTE: this module is a drop-in replacement for the legacy
# n6lib.ldap_api stuff (at least for the needs of AuthAPI). The plan
# is that we will eventually get rid of this module as well (after
# revamping AuthAPI so that it will no longer depend on LDAP-like
# formed data).

import copy
import datetime
import re
import threading
from collections.abc import Iterator
from typing import (
    Any,
    Union,
)

from pyramid.decorator import reify
from sqlalchemy import text as sqla_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from n6lib.auth_db import models
from n6lib.class_helpers import (
    get_class_name,
    is_seq,
)
from n6lib.common_helpers import (
    EMAIL_OVERRESTRICTED_SIMPLE_REGEX,
    ascii_str,
    as_unicode,
    splitlines_asc,
)
from n6lib.datetime_helpers import (
    datetime_utc_normalize,
    timestamp_from_datetime,
)
from n6lib.log_helpers import get_logger
from n6lib.auth_db.models import User
from n6lib.auth_db.config import SQLAuthDBConfigMixin

__all__ = [
    'LdapAPIReplacementWrongOrgUserAPIKeyIdError',
    'LdapAPI',
    'get_node',
    'get_value_list',
    'get_value',
    'get_dn_segment_value',
    'format_ldap_dt',
]


LOGGER = get_logger(__name__)


LDAP_DATETIME_FORMAT = "%Y%m%d%H%M%SZ"

LDAP_TREE_ROOT_DN = 'dc=n6,dc=cert,dc=pl'


_N6ORG_ID_OFFICIAL_ATTR_REGEX = re.compile(
    r'''
        \A
        (   # kind of official id
            [A-Z]+
        )
        \s*
        (   # separator
            :
        )
        \s*
        (   # actual id number
            [0-9\-]+
        )
        \Z
    ''', re.ASCII | re.IGNORECASE | re.VERBOSE)


class LdapAPIReplacementWrongOrgUserAPIKeyIdError(RuntimeError):
    """Raised when the given credentials are not valid."""


class LdapAPI(SQLAuthDBConfigMixin):

    #
    # Public interface

    def __init__(self, settings=None):
        self._rlock = threading.RLock()
        super(LdapAPI, self).__init__(settings)
        # Can be set by client code to an arbitrary argumentless callable
        # (to be called relatively often during long-lasting operations):
        self.tick_callback = lambda: None

    def __enter__(self):
        self._rlock.acquire()
        try:
            if getattr(self, '_db_session', None) is not None:
                raise RuntimeError(
                    f'{self.__class__.__qualname__} '
                    f'context manager cannot be nested')
            self._db_session = self._db_session_maker()
            return self
        except:
            self._rlock.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            try:
                try:
                    if exc_type is None:
                        self._db_session.commit()
                    else:
                        self._db_session.rollback()
                finally:
                    self._db_session.close()
            finally:
                self._db_session = None
        finally:
            self._rlock.release()

    # TODO later: when refactoring/revamping the *n6*'s authn/authz-related
    #             stuff, let's remember to move whole machinery of API-key-based
    #             authentication to `auth_db.api`...
    def authenticate_with_api_key_id(self, org_id, user_id, api_key_id):
        separate_db_session = self._db_session_maker()
        try:
            user = separate_db_session.query(User).filter(
                User.is_blocked.is_(sqla_text('FALSE')),
                User.login == user_id,
                User.org_id == org_id,
                User.api_key_id == api_key_id,
            ).one_or_none()
            if user is None:
                raise LdapAPIReplacementWrongOrgUserAPIKeyIdError(org_id, user_id, api_key_id)
        finally:
            separate_db_session.close()

    def search_structured(self):
        """
        Get a "structured" representation of the LDAP tree.

        Returns:
            A dict of nested dicts, making a hierarchical structure, such as:

              {'ou': {                              #  * node container
                  'orgs': {                         #    * node (represents LDAP entry)
                      'attrs': {                    #      * dict of LDAP entry's attributes
                          'objectClass': ['top', 'organizationalUnit'],
                          'ou': ['orgs']}},
                  'sources': {                      #    * node (represents LDAP entry)
                      'attrs': {                    #      * dict of LDAP entry's attributes
                          'objectClass': ['top', 'organizationalUnit'],
                          'ou': ['sources']},
                      'cn': {                       #      * node container
                          'some.src': {             #        * node (represents LDAP entry)
                              'attrs': {            #          * dict of LDAP entry's attributes
                                  'cn': ['some_src'],
                                  'objectClass': ['top', 'n6Source'],
                                  'n6anonymized': ['hidden.42']}}}},
                  'system-groups': {                #    * node (represents LDAP entry)
                      'attrs': {},                  #      * dict of LDAP entry's attributes
                      'cn': {                       #      * node container
                          'admins': {               #        * node (represents LDAP entry)
                              'attrs': {            #          * dict of LDAP entry's attributes
                                  'cn': ['admins'],
                                  'n6refint': [
                                      # refint DNs
                                      'n6login=ads-adm,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl',
                                      'n6login=x@cert.pl,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl'],
                                  'objectClass': ['top', 'n6SystemGroup']}}}}},
               ...}

            -- with an additional key: `_extra_` -- the value assigned to
            which is a dict that maps certain keys to some data (which are
            *not* constrained by the legacy LDAP-related convention...).
        """
        extra_items = dict(self._generate_root_node_extra_items())
        search_results = self._search_flat()
        root_node = self._structuralize_search_results(
            search_results,
            tick_callback=self.tick_callback)
        root_node['_extra_'] = extra_items
        return root_node

    def peek_database_ver_and_timestamp(self) -> tuple[int, float]:
        [(_, ver), (_, timestamp)] = self._generate_database_ver_and_timestamp()
        assert isinstance(ver, int)
        assert isinstance(timestamp, float)
        return ver, timestamp

    #
    # Overridden/extended stuff from the superclass

    # Note: within each transaction, we want *consistent reads* throughout
    # the whole transaction. The `SERIALIZABLE` level would actually spoil
    # that (!), as it would enforce using shared locks... (We *confirmed*
    # that behavior experimentally!). That's why, here, we insist on using
    # the `REPEATABLE READ` (rather than `SERIALIZABLE`) isolation level
    # (those *whole-transaction-consistent reads* are especially important
    # for our `recent_write_op_commit`-based database versioning stuff...).
    # See: http://dev.mysql.com/doc/refman/en/innodb-consistent-read.html
    # Also, the reduced use of locks reduces the possibility of deadlocks.
    # Also, note that *consistent non-blocking reads* are most probably
    # better for performance when it comes to concurrent access to Auth DB.
    # So using here `REPEATABLE READ` (not `SERIALIZABLE`) is a triple win!
    isolation_level = 'REPEATABLE READ'

    def configure_db(self):
        super(LdapAPI, self).configure_db()
        self._db_session_maker = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self._db_session = None

    #
    # Non-public helpers

    def _generate_root_node_extra_items(self) -> Iterator[tuple[str, Any]]:
        yield from self._generate_database_ver_and_timestamp()
        yield 'ignored_ip_networks', set(self._generate_ignored_ip_networks())

    def _generate_database_ver_and_timestamp(self) -> Iterator[tuple[str, Union[int, float]]]:
        recent_write_op_commit = self._db_session.query(
            models.RecentWriteOpCommit,
        ).order_by(
            models.RecentWriteOpCommit.id.desc(),
        ).limit(1).one()
        if recent_write_op_commit.id <= 0:
            raise AssertionError(
                f'{recent_write_op_commit.id=}, i.e., is less than '
                f'or equal to 0 (this should never happen!)')
        yield 'ver', recent_write_op_commit.id
        yield 'timestamp', timestamp_from_datetime(recent_write_op_commit.made_at)
        self.tick_callback()

    def _generate_ignored_ip_networks(self) -> Iterator[str]:
        where_cond = models.IgnoreList.active.is_(sqla_text('TRUE'))
        for ignore_list in self._db_session.query(models.IgnoreList).filter(where_cond):
            assert ignore_list.active
            self.tick_callback()
            for ignored in ignore_list.ignored_ip_networks:
                yield ignored.ip_network


    def _search_flat(self):
        """
        Get a flat representation of the LDAP tree.

        Returns:
            A list of pairs, each of the form:
                (<DN>, {<attr name>: <attr value list>, ...})
            -- for example:
              [('o=org1,ou=orgs,dc=n6,dc=cert,dc=pl', {
                  'n6cc': ['PL', 'RU'],
                  'cn': ['org1'],
                  'n6rest-api-full-access': ['TRUE'],
                  'objectClass': ['n6Org', 'top', 'n6Criterion'],
                  'name': ['Organizacja 1'],
                  'n6asn': ['123', '1456777'],
                  'n6ip-network': ['192.168.56.22/28', '192.168.57.1/27'],
                  'n6org-group-refint': [
                      'cn=orgs-group1,ou=org-groups,dc=n6,dc=cert,dc=pl',
                      'cn=orgs-group2,ou=org-groups,dc=n6,dc=cert,dc=pl']}),
               ('o=org2,ou=orgs,dc=n6,dc=cert,dc=pl', {
                  'objectClass': ['n6Org', 'top', 'n6Criterion']}),
               ...]

            For many types of LDAP attributes, attribute values
            are *normalized* using _LdapAttrNormalizer (see the
            _LdapAttrNormalizer class definition for details).
        """
        search_results = list(self._generate_search_results())
        to_be_skipped_dn_seq = []
        self._normalize_search_results(search_results, to_be_skipped_dn_seq)
        return list(self._generate_cleaned_search_results(
            search_results,
            to_be_skipped_dn_seq,
            tick_callback=self.tick_callback))


    def _generate_search_results(self):
        for generator in [
            self._generate_ou_orgs,
            self._generate_ou_org_groups,
            self._generate_ou_subsource_groups,
            self._generate_ou_sources,
            self._generate_ou_criteria,
            self._generate_ou_components,
            self._generate_ou_system_groups,
        ]:
            for dn, coerced_attrs in generator():
                self.tick_callback()
                assert all(isinstance(value, str)
                           for value_list in coerced_attrs.values()
                               for value in value_list), \
                    f'bug in {generator=!a} ({coerced_attrs=!a})'
                yield dn, coerced_attrs

    def _generate_ou_orgs(self):
        ou_orgs_dn, ou_orgs_attrs = self._make_dn_and_coerced_attrs('ou', ou='orgs')
        yield ou_orgs_dn, ou_orgs_attrs
        for org in self._db_session.query(models.Org):
            org_dn, org_attrs = self._make_dn_and_coerced_attrs('o', ou_orgs_dn, **{
                'o': org.org_id,
                'name': org.actual_name,
                'n6rest-api-full-access': org.full_access,
                'n6stream-api-enabled': org.stream_api_enabled,

                'n6email-notifications-enabled': org.email_notification_enabled,
                'n6email-notifications-address': [
                    inst.email
                    for inst in org.email_notification_addresses],
                'n6email-notifications-times': [
                    inst.notification_time
                    for inst in org.email_notification_times],
                'n6email-notifications-language': org.email_notification_language,
                'n6email-notifications-business-days-only':
                    org.email_notification_business_days_only,

                'n6asn': [inst.asn for inst in org.inside_filter_asns],
                'n6cc': [inst.cc for inst in org.inside_filter_ccs],
                'n6fqdn': [inst.fqdn for inst in org.inside_filter_fqdns],
                'n6ip-network': [inst.ip_network for inst in org.inside_filter_ip_networks],
                'n6url': [inst.url for inst in org.inside_filter_urls],

                'n6org-group-refint': [
                    self._make_dn('cn', inst.org_group_id, parent='ou=org-groups')
                    for inst in org.org_groups],
            })
            yield org_dn, org_attrs
            for user in org.users:
                yield self._make_dn_and_coerced_attrs('n6login', org_dn, **{
                    'n6login': user.login,
                    'n6blocked': bool(user.is_blocked),
                    #'password': <for now, it is not needed here>,
                })
            for access_zone in ['inside', 'search', 'threats']:
                for (subentry_dn,
                     subentry_attrs
                     ) in self.__generate_org_az_subentries(org_dn, org, access_zone):
                    yield subentry_dn, subentry_attrs

    def __generate_org_az_subentries(self, org_dn, org, access_zone):
        assert access_zone in {'inside', 'search', 'threats'}
        access_to = getattr(org, 'access_to_'+access_zone)
        if access_to:
            yield self._make_dn_and_coerced_attrs('cn', org_dn, cn='res-'+access_zone)
        for off in [False, True]:
            yield self.__make_search_result_for_org_az_channel(org_dn, org, access_zone, off)

    def __make_search_result_for_org_az_channel(self, org_dn, org, access_zone, off):
        assert access_zone in {'inside', 'search', 'threats'}
        assert isinstance(off, bool)
        if off:
            channel_cn = access_zone + '-ex'
            subsources = getattr(org, access_zone + '_off_subsources')
            subsource_groups = getattr(org, access_zone + '_off_subsource_groups')
        else:
            channel_cn = access_zone
            subsources = getattr(org, access_zone + '_subsources')
            subsource_groups = getattr(org, access_zone + '_subsource_groups')
        return self._make_dn_and_coerced_attrs('cn', org_dn, **{
            'cn': channel_cn,
            'n6subsource-refint': [
                self._make_dn('cn', inst.label,
                              parent=self._make_dn('cn', inst.source_id, parent='ou=sources'))
                for inst in subsources],
            'n6subsource-group-refint': [
                self._make_dn('cn', inst.label, parent='ou=subsource-groups')
                for inst in subsource_groups],
        })

    def _generate_ou_org_groups(self):
        (ou_org_groups_dn,
         ou_org_groups_attrs) = self._make_dn_and_coerced_attrs('ou', ou='org-groups')
        yield ou_org_groups_dn, ou_org_groups_attrs
        for org_group in self._db_session.query(models.OrgGroup):
            (org_group_dn,
             org_group_attrs) = self._make_dn_and_coerced_attrs('cn', ou_org_groups_dn, **{
                'cn': org_group.org_group_id,
                'description': org_group.comment,
            })
            yield org_group_dn, org_group_attrs
            for access_zone in ['inside', 'search', 'threats']:
                yield self.__make_search_result_for_org_group_az_channel(org_group_dn, org_group,
                                                                         access_zone)

    def __make_search_result_for_org_group_az_channel(self, org_group_dn, org_group, access_zone):
        assert access_zone in {'inside', 'search', 'threats'}
        subsources = getattr(org_group, access_zone + '_subsources')
        subsource_groups = getattr(org_group, access_zone + '_subsource_groups')
        return self._make_dn_and_coerced_attrs('cn', org_group_dn, **{
            'cn': access_zone,
            'n6subsource-refint': [
                self._make_dn('cn', inst.label,
                              parent=self._make_dn('cn', inst.source_id, parent='ou=sources'))
                for inst in subsources],
            'n6subsource-group-refint': [
                self._make_dn('cn', inst.label, parent='ou=subsource-groups')
                for inst in subsource_groups],
        })

    def _generate_ou_subsource_groups(self):
        (ou_subsource_groups_dn,
         ou_subsource_groups_attrs) = self._make_dn_and_coerced_attrs('ou', ou='subsource-groups')
        yield ou_subsource_groups_dn, ou_subsource_groups_attrs
        for subsource_group in self._db_session.query(models.SubsourceGroup):
            yield self._make_dn_and_coerced_attrs('cn', ou_subsource_groups_dn, **{
                'cn': subsource_group.label,
                'description': subsource_group.comment,
                'n6subsource-refint': [
                    self._make_dn('cn', inst.label,
                                  parent=self._make_dn('cn', inst.source_id, parent='ou=sources'))
                    for inst in subsource_group.subsources],
            })

    def _generate_ou_sources(self):
        (ou_sources_dn,
         ou_sources_attrs) = self._make_dn_and_coerced_attrs('ou', ou='sources')
        yield ou_sources_dn, ou_sources_attrs
        for source in self._db_session.query(models.Source):
            source_dn, source_attrs = self._make_dn_and_coerced_attrs('cn', ou_sources_dn, **{
                    'cn': source.source_id,
                    'n6anonymized': source.anonymized_source_id,
                    'n6dip-anonymization-enabled': source.dip_anonymization_enabled,
                })
            yield source_dn, source_attrs
            for subsource in source.subsources:
                yield self._make_dn_and_coerced_attrs('cn', source_dn, **{
                    'cn': subsource.label,
                    'n6inclusion-criteria-refint': [
                        self._make_dn('cn', inst.label, parent='ou=criteria')
                        for inst in subsource.inclusion_criteria],
                    'n6exclusion-criteria-refint': [
                        self._make_dn('cn', inst.label, parent='ou=criteria')
                        for inst in subsource.exclusion_criteria],
                })

    def _generate_ou_criteria(self):
        (ou_criteria_dn,
         ou_criteria_attrs) = self._make_dn_and_coerced_attrs('ou', ou='criteria')
        yield ou_criteria_dn, ou_criteria_attrs
        for criteria_container in self._db_session.query(models.CriteriaContainer):
            yield self._make_dn_and_coerced_attrs('cn', ou_criteria_dn, **{
                'cn': criteria_container.label,
                'n6asn': [inst.asn for inst in criteria_container.criteria_asns],
                'n6cc': [inst.cc for inst in criteria_container.criteria_ccs],
                'n6ip-network': [inst.ip_network for inst in criteria_container.criteria_ip_networks],
                'n6category': [inst.category for inst in criteria_container.criteria_categories],
                'n6name': [inst.name for inst in criteria_container.criteria_names],
            })

    def _generate_ou_components(self):
        (ou_components_dn,
         ou_components_attrs) = self._make_dn_and_coerced_attrs('ou', ou='components')
        yield ou_components_dn, ou_components_attrs
        for component in self._db_session.query(models.Component):
            yield self._make_dn_and_coerced_attrs('n6login', ou_components_dn, **{
                'n6login': component.login,
                # 'password': <for now, it is not needed here>,
            })

    def _generate_ou_system_groups(self):
        (ou_system_groups_dn,
         ou_system_groups_attrs) = self._make_dn_and_coerced_attrs('ou', ou='system-groups')
        yield ou_system_groups_dn, ou_system_groups_attrs
        for system_group in self._db_session.query(models.SystemGroup):
            yield self._make_dn_and_coerced_attrs('cn', ou_system_groups_dn, **{
                'cn': system_group.name,
                'n6refint': [
                    self._make_dn('n6login', inst.login,
                                  parent=self._make_dn('o', inst.org_id, parent='ou=orgs'))
                    for inst in system_group.users],
            })

    def _make_dn_and_coerced_attrs(self, rdn_type, parent=None, **attrs):
        coerced_attrs = dict(self._generate_coerced_search_res_attrs(attrs))
        unescaped_rdn_values = coerced_attrs[rdn_type]
        dn = self._make_dn(rdn_type, *unescaped_rdn_values, parent=parent)
        return dn, coerced_attrs

    def _generate_coerced_search_res_attrs(self, attrs):
        for key, value in attrs.items():
            attr_values = list(self._generate_coerced_search_res_attr_values(value))
            if attr_values:
                yield key, attr_values

    def _generate_coerced_search_res_attr_values(self, value_or_seq):
        if isinstance(value_or_seq, (list, tuple)):
            for value in value_or_seq:
                yield self._coerce_search_res_attr_value(value)
        elif value_or_seq is not None:
            yield self._coerce_search_res_attr_value(value_or_seq)

    def _coerce_search_res_attr_value(self, value):
        if isinstance(value, str):
            return value
        elif isinstance(value, bytes):
            #assert False, 'should not happen'    # XXX: remove this execution branch
            return value.decode('utf-8')
        elif isinstance(value, bool):
            return ('TRUE' if value else 'FALSE')
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, datetime.datetime):
            return format_ldap_dt(value)
        elif isinstance(value, datetime.time):
            return value.strftime('%H:%M')
        else:
            raise NotImplementedError(
                f'cannot coerce {value!a} to `str` (unsupported class: '
                f'{get_class_name(value)})')

    def _make_dn(self, rdn_type, *unescaped_rdn_values, parent=None):
        parent_dn = (LDAP_TREE_ROOT_DN if parent is None
                     else (parent if parent.endswith(LDAP_TREE_ROOT_DN)
                           else f'{parent},{LDAP_TREE_ROOT_DN}'))
        rdn = self._make_rdn(rdn_type, *unescaped_rdn_values)
        return f'{rdn},{parent_dn}'

    def _make_rdn(self, rdn_type, *unescaped_rdn_values):
        return self._ava_dn_to_str([
            [(rdn_type, unescaped_val, '')
             for unescaped_val in unescaped_rdn_values]
        ])

    @classmethod
    def _ava_dn_to_str(cls, ava_dn):
        r"""
        Copied from `dn2str()` in:
        https://github.com/python-ldap/python-ldap/blob/python-ldap-2.5.2/Lib/ldap/dn.py
        (and slightly adjusted).

        This function takes a decomposed DN as parameter and returns
        a single `str`. It will always return a DN in LDAPv3 format
        compliant to RFC 4514.

        >>> ava_dn = [
        ...     [('n6login', ' @foo + bar', 1)],
        ...     [('cn', '#spam = ham,albo;i,nie ', 1)],
        ...     [('dc', 'n6', 1)],
        ...     [('dc', 'cert', 1)],
        ...     [('dc', 'pl', 1)],
        ... ]
        >>> LdapAPI._ava_dn_to_str(ava_dn)
        'n6login=\\ @foo \\+ bar,cn=\\#spam \\= ham\\,albo\\;i\\,nie\\ ,dc=n6,dc=cert,dc=pl'
        """
        return ','.join([
            '+'.join([
                '='.join((rdn_type, cls._escape_dn_chars(rdn_val or '')))
                for rdn_type, rdn_val, _ in rdn])
            for rdn in ava_dn
        ])

    @classmethod
    def _str_to_ava_dn(cls, str_dn,
                       _not_escaped_plus_regex=re.compile(r'(?<!\\)(?:\\\\)*[+]'),
                       _not_escaped_comma_regex=re.compile(r'(?<!\\)(?:\\\\)*[,]'),
                       _not_escaped_equal_regex=re.compile(r'(?<!\\)(?:\\\\)*[=]')):
        r"""
        >>> str_dn = (
        ...     'n6login=\\ @foo \\+ bar'
        ...     ',cn=\\#spam \\= ham\\,albo\\;i\\,nie\\ '
        ...     ',dc=n6,dc=cert,dc=pl')
        >>> LdapAPI._str_to_ava_dn(str_dn) == [
        ...     [('n6login', ' @foo + bar', 1)],
        ...     [('cn', '#spam = ham,albo;i,nie ', 1)],
        ...     [('dc', 'n6', 1)],
        ...     [('dc', 'cert', 1)],
        ...     [('dc', 'pl', 1)],
        ... ]
        True
        """
        if _not_escaped_plus_regex.search(str_dn):
            raise NotImplementedError(
                'we do not support multiple-value RDNs (just '
                'for simplicity, we should not need them)')

        rdn_seq = []
        prev_end = 0
        for comma_match in _not_escaped_comma_regex.finditer(str_dn):
            rdn_seq.append(str_dn[prev_end : comma_match.end()-1])
            prev_end = comma_match.end()
        rdn_seq.append(str_dn[prev_end:])

        ava_dn = []
        for rdn in rdn_seq:
            eq_match = _not_escaped_equal_regex.search(rdn)
            if not eq_match:
                raise ValueError(
                    f'invalid RDN: {rdn!a} (whole DN: {str_dn!a})')
            rdn_type = rdn[0 : eq_match.end()-1]
            esc_rdn_val = rdn[eq_match.end():]
            if _not_escaped_equal_regex.search(esc_rdn_val):
                raise ValueError(
                    f'RDN value containing unescaped "=": '
                    f'{rdn!a} (whole DN: {str_dn!a})')
            rdn_val = cls._unescape_dn_chars(esc_rdn_val)
            ava_dn.append([(rdn_type, rdn_val, 1)])
        return ava_dn

    @staticmethod
    def _escape_dn_chars(val):
        r"""
        Copied from `escape_dn_chars()` in:
        https://github.com/python-ldap/python-ldap/blob/python-ldap-2.5.2/Lib/ldap/dn.py
        (and slightly adjusted).

        Escape all DN special characters found in `val`
        with a bac-slash (see RFC 4514, section 2.4).

        >>> LdapAPI._escape_dn_chars('# Ala # "ma" , kota+<psa>; n=42 \\x00 \x00. ')
        '\\# Ala # \\"ma\\" \\, kota\\+\\<psa\\>\\; n\\=42 \\\\x00 \\\x00.\\ '
        """
        if val:
            val = val.replace('\\', '\\\\')
            val = val.replace(',', '\\,')
            val = val.replace('+', '\\+')
            val = val.replace('"', '\\"')
            val = val.replace('<', '\\<')
            val = val.replace('>', '\\>')
            val = val.replace(';', '\\;')
            val = val.replace('=', '\\=')
            val = val.replace('\000', '\\\000')
            if val[0] == '#' or val[0] == ' ':
                val = '\\' + val
            if val[-1] == ' ':
                val = val[:-1] + '\\ '
        return val

    @staticmethod
    def _unescape_dn_chars(val):
        r"""
        >>> val = '\\# Ala # \\"ma\\" \\, kota\\+\\<psa\\>\\; n\\=42 \\\\x00 \\\x00.\\ '
        >>> LdapAPI._unescape_dn_chars(val)
        '# Ala # "ma" , kota+<psa>; n=42 \\x00 \x00. '
        """
        return re.sub(r'\\(.)', r'\1', val)


    # The following methods were copied from the original `LdapAPI`
    # class (then, here and there, slightly adjusted...).

    def _normalize_search_results(self, search_results, to_be_skipped_dn_seq):
        # note: `search_results` and `to_be_skipped_dn_seq` are modified in-place
        for dn, attrs in search_results:
            self.tick_callback()
            try:
                self._normalize_attrs(dn, attrs)
                self._check_dn_rdn_consistency(dn, attrs)
            except _RDNError as exc:
                to_be_skipped_dn_seq.append(dn)
                LOGGER.error('The entry %a and all its subentries '
                             'will be skipped! (%s)', dn, exc)

    @staticmethod
    def _normalize_attrs(dn, attrs):
        for attr_name, value_list in list(attrs.items()):
            if attr_name != ascii_str(attr_name):
                raise ValueError(
                    f'LDAP attribute name {attr_name!a} '
                    f'is not ASCII-only!')
            # TODO: get rid of binary-to-str coercions from the implementation
            #       and tests of this module; NOTE that those coercions are not
            #       needed anymore, because the SQL-related part of this class
            #       already guarantees that only `str` values are contained
            #       in the results generated by `_generate_search_results().`
            #assert all(isinstance(s, str) for s in value_list)        # TODO: uncomment when got rid of the aforementioned coercions...
            ready_value_list = ldap_attr_normalizer.get_ready_value_list(dn, attr_name, value_list)
            #assert all(isinstance(s, str) for s in ready_value_list)  # TODO: uncomment when got rid of the aforementioned coercions...
            if ready_value_list:
                attrs[attr_name] = ready_value_list
            else:
                del attrs[attr_name]

    @classmethod
    def _check_dn_rdn_consistency(cls, dn, normalized_attrs):
        """
        >>> cls = LdapAPI
        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'foo': ['bar']})
        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'foo': ['bar'], 'irrelevant': ['stuff']})

        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'foo': ['barr'], 'irrelevant': ['stuff']})      # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.ldap_api_replacement._RDNError: ... RDN part is inconsistent with ...

        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'fooo': ['bar'], 'irrelevant': ['stuff']})      # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.ldap_api_replacement._RDNError: ... expected exactly one value ...

        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'foo': ['bar', 'x'], 'irrelevant': ['stuff']})  # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.ldap_api_replacement._RDNError: ... expected exactly one value ...

        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'foo': [], 'irrelevant': ['stuff']})            # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.ldap_api_replacement._RDNError: ... expected exactly one value ...

        >>> cls._check_dn_rdn_consistency('foo=bar,dc=n6,dc=cert,dc=pl', {
        ...     'irrelevant': ['stuff']})                       # doctest: +ELLIPSIS
        Traceback (most recent call last):
          ...
        n6lib.ldap_api_replacement._RDNError: ... expected exactly one value ...
        """
        node_key = cls._dn_to_node_key(dn)
        if not node_key:
            assert dn == LDAP_TREE_ROOT_DN
            return
        rdn_attr_name_from_dn, rdn_attr_value_from_dn = node_key[-1]
        try:
            [normalized_rdn_attr_value] = normalized_attrs[rdn_attr_name_from_dn]
        except (KeyError, ValueError):
            val_listing = (
                ', '.join(map(ascii, normalized_attrs.get(rdn_attr_name_from_dn, ())))
                ) or 'no values'
            raise _RDNError(
                f'problem with the LDAP entry whose DN is {dn!a}: '
                f'expected exactly one value of the RDN attribute '
                f'{rdn_attr_name_from_dn!a} (got: {val_listing})')
        if rdn_attr_value_from_dn != normalized_rdn_attr_value:
            raise _RDNError(
                f'problem with the LDAP entry whose DN is {dn!a}: '
                f'its RDN part is inconsistent with the normalized '
                f'RDN attribute value {normalized_rdn_attr_value!a}')

    @classmethod
    def _generate_cleaned_search_results(cls, search_results, to_be_skipped_dn_seq,
                                         tick_callback=None):
        """
        >>> search_results = [
        ... ('ou=orgs,dc=n6,dc=cert,dc=pl', {'ou': ['orgs']}),
        ... ('ou=sources,dc=n6,dc=cert,dc=pl', {'ou': ['sources']}),
        ... ('cn=foo.bar,ou=sources,dc=n6,dc=cert,dc=pl', {'cn': ['foo.bar']}),
        ... ('cn=SomeSub,cn=foo.bar,ou=sources,dc=n6,dc=cert,dc=pl', {'cn': ['SomeSub']}),
        ... ('ou=org-groups,dc=n6,dc=cert,dc=pl', {'ou': ['org-groups']})]
        >>> to_be_skipped_dn_seq = ['cn=foo.bar,ou=sources,dc=n6,dc=cert,dc=pl']
        >>> list(LdapAPI._generate_cleaned_search_results(
        ...     search_results,
        ...     to_be_skipped_dn_seq)) == [
        ... ('ou=orgs,dc=n6,dc=cert,dc=pl', {'ou': ['orgs']}),
        ... ('ou=sources,dc=n6,dc=cert,dc=pl', {'ou': ['sources']}),
        ... ('ou=org-groups,dc=n6,dc=cert,dc=pl', {'ou': ['org-groups']})]
        True
        """
        # Generate all items of `search_results` -- but skip those for whom:
        # * the DN is found in the `to_be_skipped_dn_seq` sequence, or
        # * the DN is a sub-DN of any of DNs from `to_be_skipped_dn_seq`.
        for dn, attrs in search_results:
            if tick_callback is not None:
                tick_callback()
            for to_be_skipped_dn in to_be_skipped_dn_seq:
                if dn == to_be_skipped_dn or dn.endswith(',' + to_be_skipped_dn):
                    LOGGER.warning('Skipping LDAP entry %a (see the '
                                   'related ERROR logged earlier...)', dn)
                    break
            else:
                yield dn, attrs

    @classmethod
    def _structuralize_search_results(cls, search_results, keep_dead_refints=False,
                                      tick_callback=None):
        """
        >>> search_results = [
        ... ('ou=orgs,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'organizationalUnit'],
        ...      'ou': ['orgs']},
        ... ),
        ... ('o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'n6CriteriaContainer', 'n6Org'],
        ...      'o': ['cert.pl']},
        ... ),
        ... ('n6login=x@cert.pl,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'n6User'],
        ...      'n6login': ['x@cert.pl']},
        ... ),
        ... ('ou=subsource-groups,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'organizationalUnit'],
        ...      'ou': ['subsource-groups']},
        ... ),
        ... ('cn=SomeGroup,ou=subsource-groups,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'n6SubsourceGroup'],
        ...      'cn': ['SomeGroup'],
        ...      'description': ['Such a subsource group...'],
        ...      'n6subsource-refint': ['NOT a valid refint!']},
        ... ),
        ... ('cn=AnotherGroup,ou=subsource-groups,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'n6SubsourceGroup'],
        ...      'cn': ['AnotherGroup'],
        ...      'description': ['Another subsource group...'],
        ...      'n6subsource-refint': ['NOT a valid refint!', 'foo=bar,dc=n6,dc=cert,dc=pl']},
        ... ),
        ... ('ou=sources,dc=n6,dc=cert,dc=pl', {
        ...      'objectClass': ['top', 'organizationalUnit'],
        ...      'ou': ['sources']},
        ... ),
        ... # note: intermediate node ou=system-groups,dc=n6,dc=cert,dc=pl is
        ... # not given => its `attrs` dict in the results will be empty
        ... ('cn=admins,ou=system-groups,dc=n6,dc=cert,dc=pl', {
        ...      'cn': ['admins'],
        ...      'n6refint': [
        ...          'n6login=ads-adm,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl',
        ...          'n6login=x@cert.pl,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl'],
        ...      'objectClass': ['top', 'n6SystemGroup']},
        ... )]
        >>> LdapAPI._structuralize_search_results(search_results,
        ...                                       keep_dead_refints=True) == {
        ...  'attrs': {},
        ...  'ou': {
        ...      'orgs': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['orgs']},
        ...          'o': {
        ...              'cert.pl': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6CriteriaContainer', 'n6Org'],
        ...                      'o': ['cert.pl']},
        ...                  'n6login': {
        ...                      'x@cert.pl': {
        ...                          'attrs': {
        ...                              'objectClass': ['top', 'n6User'],
        ...                              'n6login': ['x@cert.pl']}}}}}},
        ...      'subsource-groups': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['subsource-groups']},
        ...          'cn': {
        ...              'SomeGroup': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6SubsourceGroup'],
        ...                      'cn': ['SomeGroup'],
        ...                      'description': ['Such a subsource group...'],
        ...                      'n6subsource-refint': []}},
        ...              'AnotherGroup': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6SubsourceGroup'],
        ...                      'cn': ['AnotherGroup'],
        ...                      'description': ['Another subsource group...'],
        ...                      'n6subsource-refint': ['foo=bar,dc=n6,dc=cert,dc=pl']}}}},
        ...      'sources': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['sources']}},
        ...      'system-groups': {
        ...          'attrs': {},
        ...          'cn': {
        ...              'admins': {
        ...                  'attrs': {
        ...                      'cn': ['admins'],
        ...                      'n6refint': [
        ...                          'n6login=ads-adm,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl',
        ...                          'n6login=x@cert.pl,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl'],
        ...                      'objectClass': ['top', 'n6SystemGroup']}}}}}}
        True
        >>> LdapAPI._structuralize_search_results(search_results) == {
        ...  'attrs': {},
        ...  'ou': {
        ...      'orgs': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['orgs']},
        ...          'o': {
        ...              'cert.pl': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6CriteriaContainer', 'n6Org'],
        ...                      'o': ['cert.pl']},
        ...                  'n6login': {
        ...                      'x@cert.pl': {
        ...                          'attrs': {
        ...                              'objectClass': ['top', 'n6User'],
        ...                              'n6login': ['x@cert.pl']}}}}}},
        ...      'subsource-groups': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['subsource-groups']},
        ...          'cn': {
        ...              'SomeGroup': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6SubsourceGroup'],
        ...                      'cn': ['SomeGroup'],
        ...                      'description': ['Such a subsource group...'],
        ...                      'n6subsource-refint': []}},
        ...              'AnotherGroup': {
        ...                  'attrs': {
        ...                      'objectClass': ['top', 'n6SubsourceGroup'],
        ...                      'cn': ['AnotherGroup'],
        ...                      'description': ['Another subsource group...'],
        ...                      'n6subsource-refint': []}}}},
        ...      'sources': {
        ...          'attrs': {
        ...              'objectClass': ['top', 'organizationalUnit'],
        ...              'ou': ['sources']}},
        ...      'system-groups': {
        ...          'attrs': {},
        ...          'cn': {
        ...              'admins': {
        ...                  'attrs': {
        ...                      'cn': ['admins'],
        ...                      'n6refint': [
        ...                          'n6login=x@cert.pl,o=cert.pl,ou=orgs,dc=n6,dc=cert,dc=pl'],
        ...                      'objectClass': ['top', 'n6SystemGroup']}}}}}}
        True
        """
        dn_to_refint_lists = {}
        root_node = {'attrs': {}}
        for dn, attrs in search_results:
            if tick_callback is not None:
                tick_callback()

            node = root_node

            # traverse/create intermediate nodes and create the target node
            for rdn_type, rdn_val in cls._dn_to_node_key(dn):
                # `rdn_type` -- RDN's attribute name (e.g.: 'n6login')
                # `rdn_val`  -- RDN's attribute value (e.g.: 'user@example.com')
                node_container = node.setdefault(rdn_type, {})
                node = node_container.setdefault(rdn_val, {'attrs': {}})
            assert node == {'attrs': {}}, (dn, node)
            node['attrs'].update(copy.deepcopy(attrs))

            cls._remember_refints(dn, node, dn_to_refint_lists)
        cls._clean_refints(root_node, dn_to_refint_lists, keep_dead_refints,
                           tick_callback=tick_callback)
        return root_node

    @classmethod
    def _remember_refints(cls, dn, node, dn_to_refint_lists):
        for attr_name, value_list in node['attrs'].items():
            if attr_name.endswith('refint'):
                # remember the reference to list of refint DNs
                # (to be *modified in-place* by _clean_refints())
                dn_to_refint_lists.setdefault(dn, []).append(value_list)

    @classmethod
    def _clean_refints(cls, root_node, dn_to_refint_lists, keep_dead_refints,
                       tick_callback=None):
        for dn, lists in dn_to_refint_lists.items():
            if tick_callback is not None:
                tick_callback()

            for refint_list in lists:
                initial_len = len(refint_list)
                for i, refint_dn in enumerate(refint_list[::-1], start=1):
                    # check whether the refint DN exists and ensure that
                    # it can be converted smoothly to a node key
                    try:
                        get_node(root_node, refint_dn)
                    except KeyError:
                        # detected a dead refint (whose DN does not exist)
                        LOGGER.warning('Entry %a contains a dead refint: %a',
                                       dn, refint_dn)
                        if keep_dead_refints:
                            continue
                    except Exception as exc:
                        LOGGER.error('Entry %a contains an '
                                     'erroneous refint: %a (%s: %s)',
                                      dn, refint_dn, get_class_name(exc),
                                      ascii_str(exc))
                    else:
                        continue
                    # let's delete the refint (dead or erroneous)
                    # -- note: modifying the list *in-place*
                    del refint_list[initial_len - i]

    # noinspection PyDefaultArgument
    @classmethod
    def _dn_to_node_key(cls, dn,
                        _const_ava_dn_suffix=[
                            [('dc', 'n6', 1)],
                            [('dc', 'cert', 1)],
                            [('dc', 'pl', 1)]]):
        """
        >>> LdapAPI._dn_to_node_key('spam=ham,foo=bar,dc=n6,dc=cert,dc=pl')
        (('foo', 'bar'), ('spam', 'ham'))
        """
        ava_dn = cls._str_to_ava_dn(dn)
        if ava_dn[-3:] != _const_ava_dn_suffix:
            raise ValueError(
                f'DN {ava_dn!a} does not end with '
                f'the standard *n6*\'s DN suffix')
        assert dn.endswith(LDAP_TREE_ROOT_DN)
        del ava_dn[-3:]
        result = []
        for rdn_components in reversed(ava_dn):
            if len(rdn_components) > 1:
                raise ValueError(
                    f'multi-valued RDNs are not supported '
                    f'(DN {dn!a} contains such RDN)')
            # `rdn_type` -- RDN's attribute name (e.g.: 'n6login')
            # `rdn_val`  -- RDN's attribute value (e.g.: 'user@example.com')
            [(rdn_type, rdn_val, _)] = rdn_components
            result.append((rdn_type, rdn_val))
        return tuple(result)

    @staticmethod
    def _get_node_by_node_key(root_node, node_key):
        node = root_node
        for rdn_type, rdn_val in node_key:
            # `rdn_type` -- RDN's attribute name (e.g.: 'n6login')
            # `rdn_val`  -- RDN's attribute value (e.g.: 'user@example.com')
            node_container = node[rdn_type]
            node = node_container[rdn_val]
        return node



class _LdapAttrNormalizer(object):

    def get_ready_value_list(self, dn, ldap_attr_name, value_list):
        assert ldap_attr_name == ascii_str(ldap_attr_name)
        normalizer_meth = self._get_normalizer_meth(dn, ldap_attr_name)
        if normalizer_meth is None:
            return list(value_list)
        else:
            # NOTE: the following call checks an additional constraint:
            # the value of an attribute must be ASCII-only if it is an
            # RDN one (i.e., being a part of DN) *and* the attribute is
            # one of those whose values are normalized (i.e., for whom
            # `normalizer_meth` is not None); thanks to this constraint
            # we may avoid some corner cases... (Note: after migration
            # to Py3, where we have no `str` vs. `unicode` discrepancy,
            # that may not be necessary -- but just in case...)
            self._check_attr_is_ascii_only_if_rdn(dn, ldap_attr_name)
            return list(self._generate_normalized_values(
                dn,
                ldap_attr_name,
                value_list,
                normalizer_meth))

    def _get_normalizer_meth(self, dn, ldap_attr_name):
        if self._is_regular_n6_attr(ldap_attr_name):
            normalizer_meth_name = '_normalize_' + ldap_attr_name.replace('-', '_')
            normalizer_meth = getattr(self, normalizer_meth_name, None)
            if normalizer_meth is None:
                LOGGER.error(
                    '%s.%s() not implemented!',
                    self.__class__.__qualname__,
                    normalizer_meth_name)
        elif self._is_o_being_client_org_id(dn, ldap_attr_name):
            normalizer_meth = self._clean_client_org_id
        elif self._is_cn_being_source_name(dn, ldap_attr_name):
            normalizer_meth = self._clean_source_name
        else:
            # n6blocked, or
            # o (but not being a client org id), or
            # cn (but not being a source name), or
            # ou, cACertificate;binary, userCertificate;binary, etc.
            normalizer_meth = None
        return normalizer_meth

    def _is_regular_n6_attr(self, ldap_attr_name):
        return (ldap_attr_name.startswith('n6') and
                ldap_attr_name != 'n6blocked' and  # (normalization of `n6blocked` is unnecessary)
                ldap_attr_name != 'n6refint' and
                not ldap_attr_name.endswith('-refint'))

    def _is_o_being_client_org_id(self, dn, ldap_attr_name):
        # whether DN is 'o=<client org id>,ou=orgs,dc=n6,dc=cert,dc=pl'
        # (or equivalent) *and* the LDAP attribute is the corresponding
        # RDN ('o=<client org id>` or equivalent)
        return self.__is_attr_rdn_of_2nd_level_entry_of_specific_kind(
            dn, ldap_attr_name,
            this_attr_names=('o', 'organization', 'organizationName'),
            top_attr_value='orgs')

    def _is_cn_being_source_name(self, dn, ldap_attr_name):
        # whether DN is 'cn=<source name>,ou=sources,dc=n6,dc=cert,dc=pl'
        # (or equivalent) *and* the LDAP attribute is the corresponding
        # RDN ('cn=<source name>` or equivalent)
        return self.__is_attr_rdn_of_2nd_level_entry_of_specific_kind(
            dn, ldap_attr_name,
            this_attr_names=('cn', 'CommonName'),
            top_attr_value='sources')

    def __is_attr_rdn_of_2nd_level_entry_of_specific_kind(
            self, dn, ldap_attr_name,
            this_attr_names,
            top_attr_value,
            top_attr_names=('ou', 'organizationalUnit', 'organizationalUnitName')):
        lowered_top_attr_names = [s.lower() for s in top_attr_names]
        lowered_this_attr_names = [s.lower() for s in this_attr_names]
        if ldap_attr_name.lower() in lowered_this_attr_names:
            node_key = LdapAPI._dn_to_node_key(dn)
            if len(node_key) == 2:
                ((top_attr_name_from_dn, top_attr_value_from_dn),
                 (this_attr_name_from_dn, _)) = node_key
                return (top_attr_name_from_dn.lower() in lowered_top_attr_names and
                        this_attr_name_from_dn.lower() in lowered_this_attr_names and
                        top_attr_value_from_dn == top_attr_value)
        return False

    def _check_attr_is_ascii_only_if_rdn(self, dn, ldap_attr_name):
        node_key = LdapAPI._dn_to_node_key(dn)
        rdn_attr_name_from_dn, rdn_attr_value_from_dn = node_key[-1]
        if (ldap_attr_name == rdn_attr_name_from_dn and
              rdn_attr_value_from_dn != ascii_str(rdn_attr_value_from_dn)):
            raise _RDNError(
                f'problem with the LDAP entry whose DN is {dn!a}: '
                f'the RDN value {rdn_attr_value_from_dn!a} is not '
                f'ASCII-only *and* (at the same time) this RDN '
                f'attribute ({rdn_attr_name_from_dn!a}) is one '
                f'of those normalized by {get_class_name(self)}')

    def _generate_normalized_values(self, dn, ldap_attr_name, value_list, normalizer_meth):
        for val in value_list:
            try:
                yield normalizer_meth(val)
            except Exception as exc:
                LOGGER.error(
                    'Problem with LDAP data: cannot normalize '
                    'a value of the attribute %s of entry %a '
                    '(%s: %s). The problematic value is: %a',
                    ldap_attr_name, dn,
                    get_class_name(exc), ascii_str(exc), val)


    #
    # normalizer helpers

    def _clean_client_org_id(self, val):
        preclean_val = self._ascii_only_to_unicode_stripped(val)
        [val] = self._client_field_spec.clean_result_value([preclean_val])
        return val

    def _clean_source_name(self, val):
        preclean_val = self._to_unicode_stripped(val).lower()
        return self._source_field_spec.clean_result_value(preclean_val)

    def _ascii_only_to_unicode_stripped(self, val):
        if isinstance(val, str):
            val.encode('ascii', 'strict')  # just to check against encoding errors
        else:
            assert isinstance(val, bytes)
            #assert False, 'should not happen'    # XXX: remove this execution branch
            val = val.decode('ascii', 'strict')
        assert isinstance(val, str)
        return val.strip()

    def _to_unicode_stripped(self, val):
        if isinstance(val, bytes):
            #assert False, 'should not happen'    # XXX: remove this execution branch
            val = val.decode('utf-8', 'strict')
        assert isinstance(val, str)
        return val.strip()

    def _pass_unmodified(self, val):
        assert isinstance(val, str) \
               or isinstance(val, bytes)          # XXX: <- this possibility is to be removed...
        return val


    #
    # actual normalizer methods

    _normalize_n6anonymized = _clean_source_name

    _normalize_n6request_parameters = _ascii_only_to_unicode_stripped
    _normalize_n6request_required_parameters = _ascii_only_to_unicode_stripped
    _normalize_n6login = _ascii_only_to_unicode_stripped
    _normalize_n6email_notifications_times = _ascii_only_to_unicode_stripped

    _normalize_n6cert_revocation_comment = _to_unicode_stripped
    _normalize_n6url = _to_unicode_stripped

    # (for LDAP attributes with the 1.3.6.1.4.1.1466.115.121.1.7 SYNTAX, i.e., 'Boolean')
    _normalize_n6rest_api_full_access = _pass_unmodified
    _normalize_n6stream_api_enabled = _pass_unmodified
    _normalize_n6email_notifications_enabled = _pass_unmodified
    _normalize_n6email_notifications_local_tz = _pass_unmodified
    _normalize_n6dip_anonymization_enabled = _pass_unmodified
    _normalize_n6email_notifications_business_days_only = _pass_unmodified

    # (for LDAP attributes with the 1.3.6.1.4.1.1466.115.121.1.27 SYNTAX, i.e., 'Integer')
    _normalize_n6time_window = _pass_unmodified
    _normalize_n6queries_limit = _pass_unmodified
    _normalize_n6results_limit = _pass_unmodified
    _normalize_n6cert_serial = _pass_unmodified
    _normalize_n6cert_usage = _pass_unmodified

    # (for LDAP attributes with the 1.3.6.1.4.1.1466.115.121.1.24 SYNTAX, i.e., 'Generalized Time')
    _normalize_n6cert_created_on = _pass_unmodified
    _normalize_n6cert_valid_from = _pass_unmodified
    _normalize_n6cert_expires_on = _pass_unmodified
    _normalize_n6cert_revoked_on = _pass_unmodified

    def _normalize_n6asn(self, val):
        asn_as_int = self._asn_field_spec.clean_result_value(val)
        # Here we want to have it as a string -- because all other LDAP
        # attr values are *strings* (of the type `str`). It shall be
        # converted to an int at a later stage of processing...
        return str(asn_as_int)

    def _normalize_n6cc(self, val):
        return self._cc_field_spec.clean_result_value(self._to_unicode_stripped(val))

    def _normalize_n6fqdn(self, val):
        return as_unicode(self._to_unicode_stripped(val).encode('idna').lower())

    def _normalize_n6ip_network(self, val):
        val = self._ascii_only_to_unicode_stripped(val)
        self._ip_net_field_spec.clean_result_value(val)  # just to check against errors
        return val

    def _normalize_n6category(self, val):
        val = self._ascii_only_to_unicode_stripped(val)
        return self._category_field_spec.clean_result_value(val)

    def _normalize_n6max_days_old(self, val):
        val = self._ascii_only_to_unicode_stripped(val)
        int(float(val))  # just to check against errors
        return str(val)

    def _normalize_n6name(self, val):
        return self._name_field_spec.clean_result_value(val)

    def _normalize_n6cert_serial_hex(self, val):
        return self._ascii_only_to_unicode_stripped(val).lower()

    def _normalize_n6cert_request(self, val):
        lines = splitlines_asc(self._ascii_only_to_unicode_stripped(val))
        return '\n'.join(lines) + '\n'

    def _normalize_n6email_notifications_language(self, val):
        return self._ascii_only_to_unicode_stripped(val).lower()

    def _normalize_n6email_notifications_address(self, val):
        val = self._ascii_only_to_unicode_stripped(val)
        if EMAIL_OVERRESTRICTED_SIMPLE_REGEX.search(val) is None:
            raise ValueError(
                f'{val!a} does not seem to be a valid e-mail address')
        return val


    #
    # auxiliary stuff

    @reify
    def _client_field_spec(self):
        return self._data_spec.client

    @reify
    def _source_field_spec(self):
        return self._data_spec.source

    @reify
    def _asn_field_spec(self):
        return self._data_spec.address.key_to_subfield['asn']

    @reify
    def _cc_field_spec(self):
        return self._data_spec.address.key_to_subfield['cc']

    @reify
    def _ip_net_field_spec(self):
        return self._data_spec.ip.extra_params['net']

    @reify
    def _category_field_spec(self):
        return self._data_spec.category

    @reify
    def _name_field_spec(self):
        return self._data_spec.name

    @reify
    def _data_spec(self):
        from n6lib.record_dict import RecordDict
        return RecordDict.data_spec


    # Below: normalization of additional LDAP attributes...
    # (XXX: Most probably, the following stuff can be removed,
    #       as the current version of `LdapAPI` does not provide the
    #       corresponding LDAP attributes because `AuthAPI` does not
    #       make use of them).

    _normalize_n6org_location = _to_unicode_stripped
    _normalize_n6org_location_coords = _to_unicode_stripped
    _normalize_n6org_address = _to_unicode_stripped
    _normalize_n6user_name = _to_unicode_stripped
    _normalize_n6user_surname = _to_unicode_stripped
    _normalize_n6user_phone = _to_unicode_stripped
    _normalize_n6user_title = _to_unicode_stripped

    _normalize_n6org_verified = _pass_unmodified
    _normalize_n6org_public = _pass_unmodified
    _normalize_n6user_contact_point = _pass_unmodified

    def _normalize_n6org_id_official(self, val):
        val = self._ascii_only_to_unicode_stripped(val)
        match = _N6ORG_ID_OFFICIAL_ATTR_REGEX.search(val)
        if match is None:
            raise ValueError(f'{val!a} is not a valid official id')
        val = ''.join(match.groups()).upper().replace('-', '')
        return val


ldap_attr_normalizer = _LdapAttrNormalizer()


class _RDNError(Exception):
    """
    Raised to signal that the normalized value of an RDN attribute may
    be inconsistent with the corresponding DN.

    Caught in LdapAPI._normalize_search_results().
    """


#
# Public helpers
# (some of them are related to what is returned by LdapAPI.search_structured())

def get_node(root_node, dn):
    """
    Get the selected node (representing an LDAP entry together with its
    descendants) from the given application-local LDAP tree representation.

    Args:
        `root_node`:
            A dict -- as returned by LdapAPI.search_structured() called
            without arguments.
        `dn`:
            The DN of the LDAP entry we are looking for.

    Returns:
        A node (representing the selected LDAP entry), i.e., a dict that
        contains:

        * the 'attrs' item whose value is a dict that maps entry
          attributes (`str`) to lists of values (`str`);

        * optional items whose keys are RDN attribute names of child
          entries and values are dicts mapping RDN attribute values of
          that child entries to nodes containing data of that child
          entries.

        Illustration:

        {'attrs': {
             <this entry attribute name>: [
                 <attribute value>, <attribute value>, ...],
             <this entry attribute name>: [
                 <attribute value>, <attribute value>, ...],
             ...},
         <child RDN's attribute name>: {
             <child RDN's attribute value>: <child entry node...>,
             <child RDN's attribute value>: <child entry node...>,
             ...}
         <child RDN's attribute name>: {
             <child RDN's attribute value>: <child entry node...>,
             <child RDN's attribute value>: <child entry node...>,
             ...}
         ...}

        (See also the docs of LdapAPI's search_structured()).

    Raises:
        KeyError -- if the LDAP tree (whose content is represented by
        `root_node`) does not contain the entry whose DN is equal to
        `dn`.
    """
    node_key = LdapAPI._dn_to_node_key(dn)
    return LdapAPI._get_node_by_node_key(root_node, node_key)


def get_value_list(node, attr_name):
    """
    Get the value list of the specified attribute of the given node.

    See also: get_node() and LdapAPI.search_structured().

    If there is no attribute -- an empty list is returned.
    """
    value_list = node['attrs'].get(attr_name, [])
    if is_seq(value_list):
        return list(value_list)
    raise TypeError(
        f'expected a sequence not being a `str`, `bytes` '
        f'or `bytearray` (got: {value_list!a})')


__sentinel = object()

def get_value(node, attr_name, default=__sentinel):
    """
    Get exactly one value of the specified attribute of the given node.

    See also: get_value_list(), get_node() and LdapAPI.search_structured().

    Raises: ValueError -- if:

    * there are more values than one, or
    * there is no value and no `default` was specified.
    """
    value_list = get_value_list(node, attr_name)
    if len(value_list) > 1:
        raise ValueError(f'attribute {attr_name!a} has more than 1 value')
    try:
        return value_list[0]
    except IndexError as exc:
        if default is __sentinel:
            raise ValueError(f'attribute {attr_name!a} has no value') from exc
        else:
            return default


def get_dn_segment_value(dn, index=0):
    """
    Get the value of `dn`'s segment, specified with `index` (default: 0).

    >>> get_dn_segment_value('spam=ham,foo=bar,dc=n6,dc=cert,dc=pl')
    'ham'
    >>> get_dn_segment_value('spam=ham,foo=bar,dc=n6,dc=cert,dc=pl', 0)
    'ham'
    >>> get_dn_segment_value('spam=ham,foo=bar,dc=n6,dc=cert,dc=pl', 1)
    'bar'

    Raises:
        IndexError -- if `index` is out of range (note that an index of
        one of the top-level `dc=...` segments is considered out of
        range!), e.g.:

    >>> get_dn_segment_value('spam=ham,foo=bar,dc=n6,dc=cert,dc=pl',
    ...                      2)  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
      ...
    IndexError: ...
    """
    node_key = LdapAPI._dn_to_node_key(dn)
    rev_index = -(index + 1)
    _, value = node_key[rev_index]
    return value


def format_ldap_dt(dt):
    """
    Convert a datetime object into an LDAP-formatted date+time string.

    See: http://tools.ietf.org/html/rfc4517#page-13

    Args:
        `dt`: A datetime.datetime instance (naive or timezone-aware).

    Returns:
        A `str` being `dt` after formatting it for LDAP, first UTC
        normalized (e.g.: '199412161032Z').

    Raises:
        TypeError -- if anything but a datetime.datetime is given.

    >>> naive_dt_1 = datetime.datetime(2013, 6, 6, 12, 13, 57)
    >>> format_ldap_dt(naive_dt_1)
    '20130606121357Z'

    >>> naive_dt_2 = datetime.datetime(2013, 6, 6, 12, 13, 57, 951211)
    >>> format_ldap_dt(naive_dt_2)
    '20130606121357Z'

    >>> from n6lib.datetime_helpers import FixedOffsetTimezone
    >>> tz_aware_dt = datetime.datetime(
    ...     2013, 6, 6, 14, 13, 57, 951211,   # note: 14 instead of 12
    ...     tzinfo=FixedOffsetTimezone(120))
    >>> format_ldap_dt(tz_aware_dt)
    '20130606121357Z'

    >>> format_ldap_dt('2014-08-08 12:01:23')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    TypeError: ...
    >>> format_ldap_dt(None)                   # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    TypeError: ...
    """
    if isinstance(dt, datetime.datetime):
        return datetime_utc_normalize(dt).strftime(LDAP_DATETIME_FORMAT)
    raise TypeError('a datetime.datetime instance is required')


# legacy aliases
get_attr_value = get_value
get_attr_value_list = get_value_list


if __name__ == "__main__":
    import doctest
    doctest.testmod()

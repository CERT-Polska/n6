# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

from passlib.hash import bcrypt
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    Time,
    Unicode,
)
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import (
    backref,
    relationship,
    scoped_session,
    sessionmaker,
    validates,
)

from n6lib.auth_db.validators import AuthDBValidator
from n6lib.data_spec.fields import SourceField


MYSQL_ENGINE = 'InnoDB'
MYSQL_CHARSET = 'utf8mb4'

db_validator = AuthDBValidator()


class CustomDeclarativeMeta(DeclarativeMeta):

    def __init__(cls, *args, **kwargs):
        def new_validator(validator_name):
            def inner(self, key, val):
                meth = getattr(db_validator, validator_name)
                try:
                    return meth(val)
                except Exception as exc:
                    # add an attribute identifying invalid field
                    setattr(exc, 'invalid_field', key)
                    raise
            return inner
        columns_to_validate = getattr(cls, '_columns_to_validate', None)
        if columns_to_validate:
            for name in columns_to_validate:
                table, col = cls._split_name_to_table_column(name)
                if table:
                    validator_name = db_validator.adjuster_prefix + table + '_' + col
                else:
                    validator_name = db_validator.adjuster_prefix + col
                validates_with_args = validates(col)
                validator_func = new_validator(validator_name)
                setattr(cls,
                        validator_name,
                        validates_with_args(validator_func))
        super(CustomDeclarativeMeta, cls).__init__(*args, **kwargs)

    @staticmethod
    def _split_name_to_table_column(name):
        if '.' in name:
            return name.split('.')
        return None, name


Base = declarative_base(metaclass=CustomDeclarativeMeta)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False))


org_notification_email_link = Table(
    'org_notification_email_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('email_notification_address_id',
           ForeignKey('email_notification_address.id'),
           primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_notification_time_link = Table(
    'org_notification_time_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('notification_time_id', ForeignKey('email_notification_time.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_asn_link = Table(
    'org_asn_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('asn_id', ForeignKey('inside_filter_asn.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_cc_link = Table(
    'org_cc_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('cc_id', ForeignKey('inside_filter_cc.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_fqdn_link = Table(
    'org_fqdn_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('fqdn_id', ForeignKey('inside_filter_fqdn.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_ip_network_link = Table(
    'org_ip_network_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('ip_network_id', ForeignKey('inside_filter_ip_network.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_url_link = Table(
    'org_url_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('url_id', ForeignKey('inside_filter_url.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_org_group_link = Table(
    'org_org_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
subsource_group_link = Table(
    'subsource_group_link', Base.metadata,
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)

# `org` to subsources association tables
org_inside_subsource_link = Table(
    'org_inside_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_inside_ex_subsource_link = Table(
    'org_inside_ex_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_inside_subsource_group_link = Table(
    'org_inside_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_inside_ex_subsource_group_link = Table(
    'org_inside_ex_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_search_subsource_link = Table(
    'org_search_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_search_ex_subsource_link = Table(
    'org_search_ex_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_search_subsource_group_link = Table(
    'org_search_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_search_ex_subsource_group_link = Table(
    'org_search_ex_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_threats_subsource_link = Table(
    'org_threats_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_threats_ex_subsource_link = Table(
    'org_threats_ex_subsource_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_threats_subsource_group_link = Table(
    'org_threats_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_threats_ex_subsource_group_link = Table(
    'org_threats_ex_subsource_group_link', Base.metadata,
    Column('org_id', ForeignKey('org.org_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
# `org_groups` to subsources association tables
org_group_inside_subsource_link = Table(
    'org_group_inside_subsource_link', Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_group_inside_subsource_group_link = Table(
    'org_group_inside_subsource_group_link', Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_group_search_subsource_link = Table(
    'org_group_search_subsource_link', Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_group_search_subsource_group_link = Table(
    'org_group_search_subsource_group_link',
    Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_group_threats_subsource_link = Table(
    'org_group_threats_subsource_link', Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
org_group_threats_subsource_group_link = Table(
    'org_group_threats_subsource_group_link', Base.metadata,
    Column('org_group_id', ForeignKey('org_group.org_group_id'), primary_key=True),
    Column('subsource_group_label', ForeignKey('subsource_group.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
user_system_group_link = Table(
    'user_system_group_link', Base.metadata,
    Column('user_login', ForeignKey('user.login'), primary_key=True),
    Column('system_group_name', ForeignKey('system_group.name'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
subsource_inclusion_criteria_link = Table(
    'subsource_inclusion_criteria_link', Base.metadata,
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
subsource_exclusion_criteria_link = Table(
    'subsource_exclusion_criteria_link', Base.metadata,
    Column('subsource_label', ForeignKey('subsource.label'), primary_key=True),
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
criteria_asn_link = Table(
    'criteria_asn_link', Base.metadata,
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    Column('asn_id', ForeignKey('criteria_asn.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
criteria_cc_link = Table(
    'criteria_cc_link', Base.metadata,
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    Column('cc_id', ForeignKey('criteria_cc.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
criteria_ip_network_link = Table(
    'criteria_ip_network_link', Base.metadata,
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    Column('ip_network_id', ForeignKey('criteria_ip_network.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
criteria_category_link = Table(
    'criteria_category_link', Base.metadata,
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    Column('criteria_category_name', ForeignKey('criteria_category.category'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)
criteria_criteria_container_link = Table(
    'criteria_criteria_container_link', Base.metadata,
    Column('criteria_container_label', ForeignKey('criteria_container.label'), primary_key=True),
    Column('criteria_name_id', ForeignKey('criteria_name.id'), primary_key=True),
    mysql_engine=MYSQL_ENGINE,
    mysql_charset=MYSQL_CHARSET)


class _PassEncryptMixin(object):

    # def __init__(self, login=None, password=None):
    #     self.login = login
    #     self.password = self.get_password_hash_or_none(password)

    def get_password_hash_or_none(self, password):
        return bcrypt.encrypt(password) if password else None

    def verify_password(self, password):
        if self.password:
            return bcrypt.verify(password, self.password)
        return None


class Org(Base):

    __tablename__ = 'org'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    org_id = Column(String(32), primary_key=True)
    actual_name = Column(String(255))
    full_access = Column(Boolean, default=False)
    # "Inside" access zone
    access_to_inside = Column(Boolean, default=False)
    # inside_max_days_old = Column(Integer)
    # `{access_zone}_request_parameters` records should store a JSON
    # ({str: bool}) mapping, where keys are parameters' names,
    # mapping to Boolean type. If a value is True - parameter is
    # required, False - not required, but legal; Null or empty
    # container - all available parameters are legal.
    # inside_request_parameters = Column(JSON)
    inside_subsources = relationship('Subsource',
                                     secondary=org_inside_subsource_link,
                                     backref='inside_orgs')
    inside_ex_subsources = relationship('Subsource',
                                        secondary=org_inside_ex_subsource_link,
                                        backref='inside_ex_orgs')
    inside_subsource_groups = relationship('SubsourceGroup',
                                           secondary=org_inside_subsource_group_link,
                                           backref='inside_orgs')
    inside_ex_subsource_groups = relationship('SubsourceGroup',
                                              secondary=org_inside_ex_subsource_group_link,
                                              backref='inside_ex_orgs')
    # "Search" access zone
    access_to_search = Column(Boolean, default=False)
    # search_max_days_old = Column(Integer)
    # search_request_parameters = Column(JSON)
    search_subsources = relationship('Subsource',
                                     secondary=org_search_subsource_link,
                                     backref='search_orgs')
    search_ex_subsources = relationship('Subsource',
                                        secondary=org_search_ex_subsource_link,
                                        backref='search_ex_orgs')
    search_subsource_groups = relationship('SubsourceGroup',
                                           secondary=org_search_subsource_group_link,
                                           backref='search_orgs')
    search_ex_subsource_groups = relationship('SubsourceGroup',
                                              secondary=org_search_ex_subsource_group_link,
                                              backref='search_ex_orgs')
    # "Threats" access zone
    access_to_threats = Column(Boolean, default=False)
    # threats_max_days_old = Column(Integer)
    # threats_request_parameters = Column(JSON)
    threats_subsources = relationship('Subsource',
                                      secondary=org_threats_subsource_link,
                                      backref='threats_orgs')
    threats_ex_subsources = relationship('Subsource',
                                         secondary=org_threats_ex_subsource_link,
                                         backref='threats_ex_orgs')
    threats_subsource_groups = relationship('SubsourceGroup',
                                            secondary=org_threats_subsource_group_link,
                                            backref='threats_orgs')
    threats_ex_subsource_groups = relationship('SubsourceGroup',
                                               secondary=org_threats_ex_subsource_group_link,
                                               backref='threats_ex_orgs')
    # other options, notifications settings
    stream_api_enabled = Column(Boolean, default=False)
    email_notifications_enabled = Column(Boolean, default=False)
    email_notifications_times = relationship('EMailNotificationTime',
                                             secondary=org_notification_time_link,
                                             back_populates='org')
    email_notifications_addresses = relationship('EMailNotificationAddress',
                                                 secondary=org_notification_email_link,
                                                 back_populates='org')
    email_notifications_language = Column(String(2), nullable=True)
    email_notifications_business_days_only = Column(Boolean, default=False)
    inside_filter_asns = relationship('InsideFilterASN',
                                      secondary=org_asn_link,
                                      back_populates='orgs')
    inside_filter_ccs = relationship('InsideFilterCC',
                                     secondary=org_cc_link,
                                     back_populates='orgs')
    inside_filter_fqdns = relationship('InsideFilterFQDN',
                                       secondary=org_fqdn_link,
                                       back_populates='orgs')
    inside_filter_ip_networks = relationship('InsideFilterIPNetwork',
                                             secondary=org_ip_network_link,
                                             back_populates='orgs')
    inside_filter_urls = relationship('InsideFilterURL',
                                      secondary=org_url_link,
                                      back_populates='orgs')
    org_groups = relationship('OrgGroup', secondary=org_org_group_link, back_populates='orgs')
    users = relationship('User', back_populates='org')

    def __repr__(self):
        return '<Org id={!r}>'.format(self.org_id)

    def __str__(self):
        return 'Org "{}"'.format(self.org_id)

    _columns_to_validate = ['org_id', 'email_notifications_language']


class EMailNotificationAddress(Base):

    __tablename__ = 'email_notification_address'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)

    org = relationship('Org',
                       secondary=org_notification_email_link,
                       back_populates='email_notifications_addresses')

    _columns_to_validate = ['email']


class EMailNotificationTime(Base):

    __tablename__ = 'email_notification_time'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    notification_time = Column(Time)

    org = relationship('Org',
                       secondary=org_notification_time_link,
                       back_populates='email_notifications_times')

    _columns_to_validate = ['notification_time']


class InsideFilterASN(Base):

    __tablename__ = 'inside_filter_asn'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    asn = Column(Integer, nullable=False)

    orgs = relationship('Org', secondary=org_asn_link, back_populates='inside_filter_asns')

    _columns_to_validate = ['asn']


class CriteriaASN(Base):

    __tablename__ = 'criteria_asn'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    asn = Column(Integer, nullable=False)

    criteria_containers = relationship('CriteriaContainer',
                                       secondary=criteria_asn_link,
                                       back_populates='criteria_asns')

    _columns_to_validate = ['asn']


class InsideFilterCC(Base):

    __tablename__ = 'inside_filter_cc'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    cc = Column(String(2), nullable=False)

    orgs = relationship('Org', secondary=org_cc_link, back_populates='inside_filter_ccs')

    _columns_to_validate = ['cc']


class CriteriaCC(Base):

    __tablename__ = 'criteria_cc'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    cc = Column(String(2), nullable=False)

    criteria_containers = relationship('CriteriaContainer',
                                       secondary=criteria_cc_link,
                                       back_populates='criteria_ccs')

    _columns_to_validate = ['cc']


class InsideFilterFQDN(Base):

    __tablename__ = 'inside_filter_fqdn'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    fqdn = Column(String(255), nullable=False)

    orgs = relationship('Org', secondary=org_fqdn_link, back_populates='inside_filter_fqdns')

    _columns_to_validate = ['fqdn']


class InsideFilterIPNetwork(Base):

    __tablename__ = 'inside_filter_ip_network'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    ip_network = Column(String(18), nullable=False)

    orgs = relationship('Org',
                        secondary=org_ip_network_link,
                        back_populates='inside_filter_ip_networks')

    _columns_to_validate = ['ip_network']


class CriteriaIPNetwork(Base):

    __tablename__ = 'criteria_ip_network'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    ip_network = Column(String(18), nullable=False)

    criteria_containers = relationship('CriteriaContainer',
                                       secondary=criteria_ip_network_link,
                                       back_populates='criteria_ip_networks')

    _columns_to_validate = ['ip_network']


class InsideFilterURL(Base):

    __tablename__ = 'inside_filter_url'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    url = Column(Unicode(2048), nullable=False)

    orgs = relationship('Org', secondary=org_url_link, back_populates='inside_filter_urls')

    _columns_to_validate = ['url']


class CriteriaCategory(Base):

    __tablename__ = 'criteria_category'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    category = Column(String(255), primary_key=True)

    criteria_containers = relationship('CriteriaContainer',
                                       secondary=criteria_category_link,
                                       back_populates='criteria_categories')

    def __repr__(self):
        return '<Criteria Category name={!r}>'.format(self.category)

    def __str__(self):
        return self.category

    _columns_to_validate = ['criteria_category.category']


class CriteriaName(Base):

    __tablename__ = 'criteria_name'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)

    criteria_containers = relationship('CriteriaContainer',
                                       secondary=criteria_criteria_container_link,
                                       back_populates='criteria_names')

    _columns_to_validate = ['criteria_name.name']


class OrgGroup(Base):

    __tablename__ = 'org_group'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    org_group_id = Column(String(255), primary_key=True)
    comment = Column(Text)

    # "Inside" access zone
    inside_subsources = relationship('Subsource',
                                     secondary=org_group_inside_subsource_link,
                                     backref='inside_org_groups')
    inside_subsource_groups = relationship('SubsourceGroup',
                                           secondary=org_group_inside_subsource_group_link,
                                           backref='inside_org_groups')
    # "Search" access zone
    search_subsources = relationship('Subsource',
                                     secondary=org_group_search_subsource_link,
                                     backref='search_org_groups')
    search_subsource_groups = relationship('SubsourceGroup',
                                           secondary=org_group_search_subsource_group_link,
                                           backref='search_org_groups')
    # "Threats" access zone
    threats_subsources = relationship('Subsource', secondary=org_group_threats_subsource_link,
                                      backref='threats_org_groups')
    threats_subsource_groups = relationship('SubsourceGroup',
                                            secondary=org_group_threats_subsource_group_link,
                                            backref='threats_org_groups')

    orgs = relationship('Org', secondary=org_org_group_link, back_populates='org_groups')

    def __repr__(self):
        return '<Org Group ID={!r}>'.format(self.org_group_id)

    def __str__(self):
        return 'Org group "{}"'.format(self.org_group_id)

    _columns_to_validate = ['org_group_id']


class User(_PassEncryptMixin, Base):

    __tablename__ = 'user'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    login = Column(String(255), primary_key=True)
    password = Column(String(60))
    org_id = Column(String(100), ForeignKey('org.org_id'))

    org = relationship('Org', back_populates='users')
    system_groups = relationship('SystemGroup',
                                 secondary=user_system_group_link,
                                 back_populates='users')
    created_certs = relationship('Cert',
                                 back_populates='created_by',
                                 foreign_keys='Cert.created_by_login')
    owned_certs = relationship('Cert',
                               back_populates='owner',
                               foreign_keys='Cert.owner_login')
    revoked_certs = relationship('Cert',
                                 back_populates='revoked_by',
                                 foreign_keys='Cert.revoked_by_login')
    sent_request_cases = relationship('RequestCase', back_populates='sender')

    def __repr__(self):
        return '<User login={!r}>'.format(self.login)

    def __str__(self):
        return 'User "{}"'.format(self.login)

    _columns_to_validate = ['user.login']


class Component(_PassEncryptMixin, Base):

    __tablename__ = 'component'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    login = Column(String(255), primary_key=True)
    password = Column(String(60))

    created_certs = relationship('Cert',
                                 back_populates='created_by_component',
                                 foreign_keys='Cert.created_by_component_login')
    owned_certs = relationship('Cert',
                               back_populates='owner_component',
                               foreign_keys='Cert.owner_component_login')
    revoked_certs = relationship('Cert',
                                 back_populates='revoked_by_component',
                                 foreign_keys='Cert.revoked_by_component_login')

    def __repr__(self):
        return '<Component login={!r}>'.format(self.login)

    def __str__(self):
        return 'Component "{}"'.format(self.login)

    _columns_to_validate = ['component.login']


class Source(Base):

    __tablename__ = 'source'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }
    _source_id_max_length = SourceField.max_length

    source_id = Column(String(_source_id_max_length), primary_key=True)
    anonymized_source_id = Column(String(_source_id_max_length))
    dip_anonymization_enabled = Column(Boolean, default=True)
    comment = Column(Text)

    # one-to-many relationship
    subsources = relationship('Subsource', back_populates='source')

    def __repr__(self):
        return '<Source ID={!r}>'.format(self.source_id)

    def __str__(self):
        return 'Source "{}"'.format(self.source_id)

    _columns_to_validate = ['source_id', 'anonymized_source_id']


class Subsource(Base):

    __tablename__ = 'subsource'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    label = Column(String(255), primary_key=True)
    comment = Column(Text)
    source_id = Column(String(255), ForeignKey('source.source_id'))

    inclusion_criteria = relationship('CriteriaContainer',
                                      secondary=subsource_inclusion_criteria_link,
                                      back_populates='inclusion_subsources')
    exclusion_criteria = relationship('CriteriaContainer',
                                      secondary=subsource_exclusion_criteria_link,
                                      back_populates='exclusion_subsources')
    source = relationship('Source', back_populates='subsources', uselist=False)
    subsource_groups = relationship('SubsourceGroup',
                                    secondary=subsource_group_link,
                                    back_populates='subsources')

    def __repr__(self):
        return '<Subsource label={!r}>'.format(self.label)

    def __str__(self):
        return 'Subsource "{}"'.format(self.label)

    _columns_to_validate = ['label']


class SubsourceGroup(Base):

    __tablename__ = 'subsource_group'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    label = Column(String(255), primary_key=True)
    comment = Column(Text)

    subsources = relationship('Subsource',
                              secondary=subsource_group_link,
                              back_populates='subsource_groups')

    def __repr__(self):
        return '<SubsourceGroup label={!r}, comment={!r}>'.format(self.label, self.comment)

    def __str__(self):
        return 'Subsource group "{}"'.format(self.label)

    _columns_to_validate = ['label']


class CriteriaContainer(Base):

    __tablename__ = 'criteria_container'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    label = Column(String(100), primary_key=True)

    criteria_asns = relationship('CriteriaASN',
                                 secondary=criteria_asn_link,
                                 back_populates='criteria_containers')
    criteria_ccs = relationship('CriteriaCC',
                                secondary=criteria_cc_link,
                                back_populates='criteria_containers')
    criteria_ip_networks = relationship('CriteriaIPNetwork',
                                        secondary=criteria_ip_network_link,
                                        back_populates='criteria_containers')
    criteria_categories = relationship('CriteriaCategory',
                                       secondary=criteria_category_link,
                                       back_populates='criteria_containers')
    criteria_names = relationship('CriteriaName',
                                  secondary=criteria_criteria_container_link,
                                  back_populates='criteria_containers')

    inclusion_subsources = relationship('Subsource',
                                        secondary=subsource_inclusion_criteria_link,
                                        back_populates='inclusion_criteria')
    exclusion_subsources = relationship('Subsource',
                                        secondary=subsource_exclusion_criteria_link,
                                        back_populates='exclusion_criteria')

    def __repr__(self):
        return '<Criteria Container label={!r}>'.format(self.label)

    def __str__(self):
        return 'Criteria container "{}"'.format(self.label)

    _columns_to_validate = ['label']


class SystemGroup(Base):

    __tablename__ = 'system_group'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    name = Column(String(100), primary_key=True)

    users = relationship('User', secondary=user_system_group_link, back_populates='system_groups')

    def __repr__(self):
        return '<SystemGroup name={!r}>'.format(self.name)

    def __str__(self):
        return 'System group "{}"'.format(self.name)

    _columns_to_validate = ['system_group.name']


class Cert(Base):

    __tablename__ = 'cert'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    serial_hex = Column(String(20), primary_key=True)
    # `LargeBinary` is SQLAlchemy's class used to represent blobs
    certificate = Column(LargeBinary)
    created_by_login = Column(String(255), ForeignKey('user.login'))
    created_by_component_login = Column(String(255), ForeignKey('component.login'))
    # former `n6cert-usage` field has been split into
    # columns for Boolean type: `is_client_cert`, `is_server_cert`
    is_client_cert = Column(Boolean, default=False)
    is_server_cert = Column(Boolean, default=False)
    created_on = Column(DateTime)
    valid_from = Column(DateTime)
    expires_on = Column(DateTime)
    ca_cert_label = Column(String(100), ForeignKey('ca_cert.ca_label'))
    request_case_id = Column(String(28), ForeignKey('request_case.request_case_id'))
    owner_login = Column(String(255), ForeignKey('user.login'))
    owner_component_login = Column(String(255), ForeignKey('component.login'))
    revoked_on = Column(DateTime)
    revoked_by_login = Column(String(255), ForeignKey('user.login'))
    revoked_by_component_login = Column(String(255), ForeignKey('component.login'))
    revocation_comment = Column(Text)

    created_by = relationship('User',
                              back_populates='created_certs',
                              uselist=False,
                              foreign_keys=created_by_login)
    owner = relationship('User',
                         back_populates='owned_certs',
                         uselist=False,
                         foreign_keys=owner_login)
    revoked_by = relationship('User',
                              back_populates='revoked_certs',
                              uselist=False,
                              foreign_keys=revoked_by_login)
    created_by_component = relationship('Component',
                                        back_populates='created_certs',
                                        uselist=False,
                                        foreign_keys=created_by_component_login)
    owner_component = relationship('Component',
                                   back_populates='owned_certs',
                                   uselist=False,
                                   foreign_keys=owner_component_login)
    revoked_by_component = relationship('Component',
                                        back_populates='revoked_certs',
                                        uselist=False,
                                        foreign_keys=revoked_by_component_login)
    ca_cert = relationship('CACert', back_populates='certs', uselist=False)
    request_case = relationship('RequestCase', back_populates='cert', uselist=False)

    _columns_to_validate = ['serial_hex', 'revocation_comment']


class RequestCase(Base):

    __tablename__ = 'request_case'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    request_case_id = Column(String(28), primary_key=True)
    csr = Column(LargeBinary)
    sender_login = Column(String(255), ForeignKey('user.login'))
    status = Column(String(16))
    status_changed_on = Column(DateTime)

    sender = relationship('User', back_populates='sent_request_cases', uselist=False)
    cert = relationship('Cert', back_populates='request_case', uselist=False)

    _columns_to_validate = ['request_case_id', 'status']


class CACert(Base):

    __tablename__ = 'ca_cert'
    __table_args__ = {
        'mysql_engine': MYSQL_ENGINE,
        'mysql_charset': MYSQL_CHARSET,
    }

    ca_label = Column(String(100), primary_key=True)
    certificate = Column(LargeBinary)
    parent_ca_label = Column(String(100), ForeignKey(ca_label))

    children_ca = relationship('CACert', backref=backref('parent_ca', remote_side=ca_label))
    certs = relationship('Cert', back_populates='ca_cert')

    def __repr__(self):
        return '<CACert ca_label={!r}, parent_ca_label={!r}>'.format(self.ca_label,
                                                                     self.parent_ca_label)

    _columns_to_validate = ['ca_label']

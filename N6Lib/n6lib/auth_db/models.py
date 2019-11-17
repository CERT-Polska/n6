# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

from collections import MutableSequence

from passlib.hash import bcrypt
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    Time,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import (
    DeclarativeMeta,
    declarative_base,
)
from sqlalchemy.orm import (
    backref,
    relationship,
    scoped_session,
    sessionmaker,
    validates,
)
from sqlalchemy.orm.relationships import RelationshipProperty

from n6lib.auth_db import (
    MYSQL_ENGINE,
    MYSQL_CHARSET,

    CLIENT_CA_PROFILE_NAME,
    SERVICE_CA_PROFILE_NAME,

    MAX_LEN_OF_ORG_ID,
    MAX_LEN_OF_CERT_SERIAL_HEX,
    MAX_LEN_OF_SOURCE_ID,

    MAX_LEN_OF_OFFICIAL_ACTUAL_NAME,
    MAX_LEN_OF_OFFICIAL_ADDRESS,
    MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL,
    MAX_LEN_OF_OFFICIAL_LOCATION,
    MAX_LEN_OF_OFFICIAL_LOCATION_COORDS,

    MAX_LEN_OF_CA_LABEL,
    MAX_LEN_OF_COUNTRY_CODE,
    MAX_LEN_OF_DOMAIN_NAME,
    MAX_LEN_OF_EMAIL,
    MAX_LEN_OF_GENERIC_SHORT_STRING,
    MAX_LEN_OF_IP_NETWORK,
    MAX_LEN_OF_PASSWORD_HASH,
    MAX_LEN_OF_SYSTEM_GROUP_NAME,
    MAX_LEN_OF_URL,
)
from n6lib.auth_db.validators import AuthDBValidators
from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    formattable_as_str,
    with_dunder_unicode_from_str,
)


_MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY = 736
assert _MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY < MAX_LEN_OF_URL
assert MYSQL_ENGINE == 'InnoDB' and MYSQL_CHARSET == 'utf8mb4'


auth_db_validators = AuthDBValidators()


def mysql_opts():
    return dict(
        mysql_engine=MYSQL_ENGINE,
        mysql_charset=MYSQL_CHARSET,
    )


def is_relation(attr):
    return isinstance(attr.property, RelationshipProperty)


def is_property_list(attr):
    return bool(is_relation(attr) and attr.property.uselist)


class _ExternalInterfaceMixin(object):

    @classmethod
    def create_new(cls, context, **kwargs):
        session = context.db_session
        validated_kwargs = {key: ([val] if (is_property_list(getattr(cls, key)) and
                                            not isinstance(val, MutableSequence))
                                  else val)
                            for key, val in kwargs.iteritems()}
        new_record = cls(**validated_kwargs)
        session.add(new_record)
        return new_record

    @classmethod
    def from_db(cls, context, col_name, val):
        session = context.db_session
        return session.query(cls).filter(getattr(cls, col_name) == val).one()

    def add_self_to_db(self, context):
        session = context.db_session
        session.add(self)

    def is_in_relation_with(self, other_obj, relation_name):
        relation = getattr(self, relation_name)
        return other_obj in relation

    @classmethod
    def get_all_records(cls, context):
        session = context.db_session
        return session.query(cls).all()


class AuthDBCustomDeclarativeMeta(DeclarativeMeta):

    def __init__(cls, *args, **kwargs):
        cls.__provide_validators()
        with_dunder_unicode_from_str(cls)
        super(AuthDBCustomDeclarativeMeta, cls).__init__(*args, **kwargs)

    def __provide_validators(cls):
        for column_name in getattr(cls, '_columns_to_validate', ()):
            cls.__provide_validator_for_column(column_name)

    def __provide_validator_for_column(cls, column_name):
        validator_name, validator_method = cls.__get_validator_name_and_method(column_name)
        validator_func = cls._make_validator_func(column_name, validator_name, validator_method)
        cls.__setup_sqlalchemy_validator(column_name, validator_name, validator_func)

    def __get_validator_name_and_method(cls, column_name):
        for validator_name in cls.__iter_possible_validator_names(column_name):
            validator_method = getattr(auth_db_validators, validator_name, None)
            if validator_method is not None:
                return validator_name, validator_method
        raise AssertionError('no validator found for column {!r}'.format(column_name))

    def __iter_possible_validator_names(cls, column_name):
        # first, try with qualified name (including table name + column name)
        yield auth_db_validators.VALIDATOR_METHOD_PREFIX + cls.__tablename__ + '__' + column_name
        # then, try with unqualified name (including just column name)
        yield auth_db_validators.VALIDATOR_METHOD_PREFIX + column_name

    def _make_validator_func(cls, column_name, validator_name, validator_method):
        column = getattr(cls, column_name)
        column_is_nullable = column.nullable

        def validator_func(self, key, value):
            if value is None and column_is_nullable:
                return None
            try:
                return validator_method(value)
            except Exception as exc:
                setattr(exc, 'invalid_field', key)
                raise

        validator_func.__name__ = validator_name
        return validator_func

    def __setup_sqlalchemy_validator(cls, column_name, validator_name, validator_func):
        sqlalchemy_validator_maker = validates(column_name)
        sqlalchemy_validator = sqlalchemy_validator_maker(validator_func)
        setattr(cls, validator_name, sqlalchemy_validator)


Base = declarative_base(metaclass=AuthDBCustomDeclarativeMeta)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False))


# associative tables (m:n relationships)

# org <-> org_group
org_org_group_link = Table(
    'org_org_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# user <-> system_group
user_system_group_link = Table(
    'user_system_group_link', Base.metadata,
    Column(
        'user_id',
        ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'system_group_name',
        ForeignKey('system_group.name', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# subsource <-> subsource_group
subsource_subsource_group_link = Table(
    'subsource_subsource_group_link', Base.metadata,
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `inside`: org <-> subsource/subsource_group
org_inside_subsource_link = Table(
    'org_inside_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_inside_off_subsource_link = Table(
    'org_inside_off_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_inside_subsource_group_link = Table(
    'org_inside_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_inside_off_subsource_group_link = Table(
    'org_inside_off_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `threats`: org <-> subsource/subsource_group
org_threats_subsource_link = Table(
    'org_threats_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_threats_off_subsource_link = Table(
    'org_threats_off_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_threats_subsource_group_link = Table(
    'org_threats_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_threats_off_subsource_group_link = Table(
    'org_threats_off_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `search`: org <-> subsource/subsource_group
org_search_subsource_link = Table(
    'org_search_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_search_off_subsource_link = Table(
    'org_search_off_subsource_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_search_subsource_group_link = Table(
    'org_search_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_search_off_subsource_group_link = Table(
    'org_search_off_subsource_group_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `inside`: org_group <-> subsource/subsource_group
org_group_inside_subsource_link = Table(
    'org_group_inside_subsource_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_group_inside_subsource_group_link = Table(
    'org_group_inside_subsource_group_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `threats`: org_group <-> subsource/subsource_group
org_group_threats_subsource_link = Table(
    'org_group_threats_subsource_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_group_threats_subsource_group_link = Table(
    'org_group_threats_subsource_group_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# `search`: org_group <-> subsource/subsource_group
org_group_search_subsource_link = Table(
    'org_group_search_subsource_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())
org_group_search_subsource_group_link = Table(
    'org_group_search_subsource_group_link', Base.metadata,
    Column(
        'org_group_id',
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'subsource_group_label',
        ForeignKey('subsource_group.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# subsource <-> criteria_container
subsource_inclusion_criteria_link = Table(
    'subsource_inclusion_criteria_link', Base.metadata,
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'criteria_container_label',
        ForeignKey('criteria_container.label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        primary_key=True),
    **mysql_opts())
subsource_exclusion_criteria_link = Table(
    'subsource_exclusion_criteria_link', Base.metadata,
    Column(
        'subsource_id',
        ForeignKey('subsource.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'criteria_container_label',
        ForeignKey('criteria_container.label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        primary_key=True),
    **mysql_opts())

# criteria_container <-> criteria_category
criteria_category_link = Table(
    'criteria_category_link', Base.metadata,
    Column(
        'criteria_container_label',
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'criteria_category_category',
        ForeignKey('criteria_category.category', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        primary_key=True),
    **mysql_opts())


class _PassEncryptMixin(object):

    @staticmethod
    def get_password_hash_or_none(password):
        return bcrypt.encrypt(password) if password else None

    # noinspection PyUnresolvedReferences
    def verify_password(self, password):
        if self.password:
            return bcrypt.verify(password, self.password)
        return None


class Org(_ExternalInterfaceMixin, Base):

    __tablename__ = 'org'
    __table_args__ = mysql_opts()

    # Basic data
    org_id = Column(String(MAX_LEN_OF_ORG_ID), primary_key=True)
    actual_name = Column(String(MAX_LEN_OF_OFFICIAL_ACTUAL_NAME))
    full_access = Column(Boolean, default=False, nullable=False)
    stream_api_enabled = Column(Boolean, default=False, nullable=False)

    org_groups = relationship('OrgGroup', secondary=org_org_group_link, back_populates='orgs')
    users = relationship('User', back_populates='org')

    # "Inside" access zone
    access_to_inside = Column(Boolean, default=False, nullable=False)
    inside_subsources = relationship(
        'Subsource',
        secondary=org_inside_subsource_link,
        backref='inside_orgs')
    inside_off_subsources = relationship(
        'Subsource',
        secondary=org_inside_off_subsource_link,
        backref='inside_off_orgs')
    inside_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_inside_subsource_group_link,
        backref='inside_orgs')
    inside_off_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_inside_off_subsource_group_link,
        backref='inside_off_orgs')

    # "Threats" access zone
    access_to_threats = Column(Boolean, default=False, nullable=False)
    threats_subsources = relationship(
        'Subsource',
        secondary=org_threats_subsource_link,
        backref='threats_orgs')
    threats_off_subsources = relationship(
        'Subsource',
        secondary=org_threats_off_subsource_link,
        backref='threats_off_orgs')
    threats_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_threats_subsource_group_link,
        backref='threats_orgs')
    threats_off_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_threats_off_subsource_group_link,
        backref='threats_off_orgs')

    # "Search" access zone
    access_to_search = Column(Boolean, default=False, nullable=False)
    search_subsources = relationship(
        'Subsource',
        secondary=org_search_subsource_link,
        backref='search_orgs')
    search_off_subsources = relationship(
        'Subsource',
        secondary=org_search_off_subsource_link,
        backref='search_off_orgs')
    search_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_search_subsource_group_link,
        backref='search_orgs')
    search_off_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_search_off_subsource_group_link,
        backref='search_off_orgs')

    # Email notification settings
    email_notification_enabled = Column(Boolean, default=False, nullable=False)
    email_notification_addresses = relationship(
        'EMailNotificationAddress',
        back_populates='org',
        cascade='all, delete-orphan')
    email_notification_times = relationship(
        'EMailNotificationTime',
        back_populates='org',
        cascade='all, delete-orphan')
    email_notification_language = Column(String(MAX_LEN_OF_COUNTRY_CODE), nullable=True)
    email_notification_business_days_only = Column(Boolean, default=False, nullable=False)

    # "Inside" event criteria checked by n6filter
    inside_filter_asns = relationship(
        'InsideFilterASN',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_ccs = relationship(
        'InsideFilterCC',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_fqdns = relationship(
        'InsideFilterFQDN',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_ip_networks = relationship(
        'InsideFilterIPNetwork',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_urls = relationship(
        'InsideFilterURL',
        back_populates='org',
        cascade='all, delete-orphan')

    # Official entity data
    public_entity = Column(Boolean, default=False, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)

    entity_type_label = Column(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('entity_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    entity_type = relationship('EntityType', back_populates='orgs')

    location_type_label = Column(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('location_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    location_type = relationship('LocationType', back_populates='orgs')

    location = Column(String(MAX_LEN_OF_OFFICIAL_LOCATION))
    location_coords = Column(String(MAX_LEN_OF_OFFICIAL_LOCATION_COORDS))
    address = Column(String(MAX_LEN_OF_OFFICIAL_ADDRESS))

    extra_ids = relationship(
        'ExtraId',
        back_populates='org',
        cascade='all, delete-orphan')

    contact_points = relationship(
        'ContactPoint',
        back_populates='org',
        cascade='all, delete-orphan')

    def __str__(self):
        return 'Org "{}"'.format(formattable_as_str(self.org_id))

    __repr__ = attr_repr('org_id')

    _columns_to_validate = ['org_id', 'email_notification_language']


class EMailNotificationAddress(Base):

    __tablename__ = 'email_notification_address'
    __table_args__ = (
        UniqueConstraint('email', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(MAX_LEN_OF_EMAIL), nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='email_notification_addresses')

    __repr__ = attr_repr('id', 'email', 'org_id')

    _columns_to_validate = ['email']


class EMailNotificationTime(Base):

    __tablename__ = 'email_notification_time'
    __table_args__ = (
        UniqueConstraint('notification_time', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    notification_time = Column(Time, nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='email_notification_times')

    __repr__ = attr_repr('id', 'notification_time', 'org_id')

    _columns_to_validate = ['notification_time']


class InsideFilterASN(Base):

    __tablename__ = 'inside_filter_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    asn = Column(Integer, nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='inside_filter_asns')

    __repr__ = attr_repr('id', 'asn', 'org_id')

    _columns_to_validate = ['asn']


class CriteriaASN(Base):

    __tablename__ = 'criteria_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'criteria_container_label'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    asn = Column(Integer, nullable=False)

    criteria_container_label = Column(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = relationship('CriteriaContainer', back_populates='criteria_asns')

    __repr__ = attr_repr('id', 'asn', 'criteria_container_label')

    _columns_to_validate = ['asn']


class InsideFilterCC(Base):

    __tablename__ = 'inside_filter_cc'
    __table_args__ = (
        UniqueConstraint('cc', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    cc = Column(String(MAX_LEN_OF_COUNTRY_CODE), nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='inside_filter_ccs')

    __repr__ = attr_repr('id', 'cc', 'org_id')

    _columns_to_validate = ['cc']


class CriteriaCC(Base):

    __tablename__ = 'criteria_cc'
    __table_args__ = (
        UniqueConstraint('cc', 'criteria_container_label'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    cc = Column(String(MAX_LEN_OF_COUNTRY_CODE), nullable=False)

    criteria_container_label = Column(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = relationship('CriteriaContainer', back_populates='criteria_ccs')

    __repr__ = attr_repr('id', 'cc', 'criteria_container_label')

    _columns_to_validate = ['cc']


class InsideFilterFQDN(Base):

    __tablename__ = 'inside_filter_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    fqdn = Column(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='inside_filter_fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'org_id')

    _columns_to_validate = ['fqdn']


class InsideFilterIPNetwork(Base):

    __tablename__ = 'inside_filter_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    ip_network = Column(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='inside_filter_ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'org_id')

    _columns_to_validate = ['ip_network']


class CriteriaIPNetwork(Base):

    __tablename__ = 'criteria_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'criteria_container_label'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    ip_network = Column(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    criteria_container_label = Column(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = relationship('CriteriaContainer', back_populates='criteria_ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'criteria_container_label')

    _columns_to_validate = ['ip_network']


class InsideFilterURL(Base):

    __tablename__ = 'inside_filter_url'
    __table_args__ = (
        # Ideally, we'd have just `UniqueConstraint('url', 'org_id')`
        # here (as for other `InsideFilter...` models); but it is
        # impossible because MariaDB -- for the `InnoDB` engine with
        # the `utf8mb4` charset -- does not accept so long `url` as an
        # argument for `UNIQUE(...)`.  So, as a workaround, we must use
        # the following `Index` construct with the `mysql_length`
        # parameter used (note: the key length of 736 used here is, for
        # the `InnoDB` engine with the `utf8mb4` charset, the maximum
        # legal key length).
        Index(
            'unique_url_prefix_and_org_id', 'url', 'org_id',
            unique=True,
            mysql_length=dict(url=_MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY),
        ),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    url = Column(Unicode(MAX_LEN_OF_URL), nullable=False)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='inside_filter_urls')

    __repr__ = attr_repr('id', 'url', 'org_id')

    _columns_to_validate = ['url']


class CriteriaName(Base):

    __tablename__ = 'criteria_name'
    __table_args__ = (
        UniqueConstraint('name', 'criteria_container_label'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), nullable=False)

    criteria_container_label = Column(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = relationship('CriteriaContainer', back_populates='criteria_names')

    __repr__ = attr_repr('id', 'name', 'criteria_container_label')

    _columns_to_validate = ['name']


class CriteriaCategory(Base):

    __tablename__ = 'criteria_category'
    __table_args__ = mysql_opts()

    category = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)

    criteria_containers = relationship(
        'CriteriaContainer',
        secondary=criteria_category_link,
        # we set `passive_deletes` to let secondary's `ondelete='RESTRICT'`
        # do its job... (note, however, that loading this collection -- e.g.,
        # by accessing `criteria_containers` of a CriteriaCategory -- may
        # prevent that, i.e., may make a CriteriaCategory deletable! (even
        # if its `criteria_containers` collection is *not* empty) [because
        # of some SQLAlchemy's auto-delete actions specific to many-to-many/
        # /`secondary`-related stuff...])
        passive_deletes='all',
        back_populates='criteria_categories')

    def __str__(self):
        return str(formattable_as_str(self.category))

    __repr__ = attr_repr('category')

    _columns_to_validate = ['category']


class EntityType(Base):

    __tablename__ = 'entity_type'
    __table_args__ = mysql_opts()

    label = Column(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    orgs = relationship(
        'Org',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='entity_type')

    def __str__(self):
        return str(formattable_as_str(self.label))

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class LocationType(Base):

    __tablename__ = 'location_type'
    __table_args__ = mysql_opts()

    label = Column(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    orgs = relationship(
        'Org',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='location_type')

    def __str__(self):
        return str(formattable_as_str(self.label))

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class ExtraIdType(Base):

    __tablename__ = 'extra_id_type'
    __table_args__ = mysql_opts()

    label = Column(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    extra_ids = relationship('ExtraId', back_populates='id_type')

    def __str__(self):
        return str(formattable_as_str(self.label))

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class ExtraId(Base):

    __tablename__ = 'extra_id'
    __table_args__ = (
        UniqueConstraint('value', 'id_type_label', 'org_id'),
        mysql_opts(),
    )

    id = Column(Integer, primary_key=True)
    value = Column(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), nullable=False)

    id_type_label = Column(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('extra_id_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    id_type = relationship('ExtraIdType', back_populates='extra_ids')

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='extra_ids')

    __repr__ = attr_repr('id', 'value', 'id_type_label', 'org_id')

    _columns_to_validate = ['value']


class ContactPoint(Base):

    __tablename__ = 'contact_point'
    __table_args__ = mysql_opts()

    id = Column(Integer, primary_key=True)

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = relationship('Org', back_populates='contact_points')

    title = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    name = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    surname = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    email = Column(String(MAX_LEN_OF_EMAIL))
    phone = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING))

    __repr__ = attr_repr('id', 'email', 'org_id')

    _columns_to_validate = ['email']


class OrgGroup(Base):

    __tablename__ = 'org_group'
    __table_args__ = mysql_opts()

    org_group_id = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)
    comment = Column(Text)

    # "Inside" access zone
    inside_subsources = relationship(
        'Subsource',
        secondary=org_group_inside_subsource_link,
        backref='inside_org_groups')
    inside_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_group_inside_subsource_group_link,
        backref='inside_org_groups')

    # "Threats" access zone
    threats_subsources = relationship(
        'Subsource',
        secondary=org_group_threats_subsource_link,
        backref='threats_org_groups')
    threats_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_group_threats_subsource_group_link,
        backref='threats_org_groups')

    # "Search" access zone
    search_subsources = relationship(
        'Subsource',
        secondary=org_group_search_subsource_link,
        backref='search_org_groups')
    search_subsource_groups = relationship(
        'SubsourceGroup',
        secondary=org_group_search_subsource_group_link,
        backref='search_org_groups')

    orgs = relationship('Org', secondary=org_org_group_link, back_populates='org_groups')

    def __str__(self):
        return 'Org group "{}"'.format(formattable_as_str(self.org_group_id))

    __repr__ = attr_repr('org_group_id')

    _columns_to_validate = ['org_group_id']


class User(_ExternalInterfaceMixin, _PassEncryptMixin, Base):

    __tablename__ = 'user'
    __table_args__ = mysql_opts()

    # here we use a surrogate key because natural keys do not play well
    # with Admin Panel's "inline" forms (cannot change the key by using
    # such a form...)
    id = Column(Integer, primary_key=True)

    login = Column(String(MAX_LEN_OF_EMAIL), nullable=False, unique=True)
    password = Column(String(MAX_LEN_OF_PASSWORD_HASH))

    org_id = Column(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    org = relationship('Org', back_populates='users')

    system_groups = relationship(
        'SystemGroup',
        secondary=user_system_group_link,
        back_populates='users')

    owned_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='owner',
        foreign_keys='Cert.owner_login')
    created_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='created_by',
        foreign_keys='Cert.created_by_login')
    revoked_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='revoked_by',
        foreign_keys='Cert.revoked_by_login')

    def __str__(self):
        return 'User "{}"'.format(formattable_as_str(self.login))

    __repr__ = attr_repr('id', 'login', 'org_id')

    _columns_to_validate = ['login']


class Component(_ExternalInterfaceMixin, _PassEncryptMixin, Base):

    __tablename__ = 'component'
    __table_args__ = mysql_opts()

    login = Column(String(MAX_LEN_OF_DOMAIN_NAME), primary_key=True)
    password = Column(String(MAX_LEN_OF_PASSWORD_HASH))

    owned_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='owner_component',
        foreign_keys='Cert.owner_component_login')
    created_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='created_by_component',
        foreign_keys='Cert.created_by_component_login')
    revoked_certs = relationship(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='revoked_by_component',
        foreign_keys='Cert.revoked_by_component_login')

    def __str__(self):
        return 'Component "{}"'.format(formattable_as_str(self.login))

    __repr__ = attr_repr('login')

    _columns_to_validate = ['login']


class Source(Base):

    __tablename__ = 'source'
    __table_args__ = mysql_opts()

    source_id = Column(String(MAX_LEN_OF_SOURCE_ID), primary_key=True)
    anonymized_source_id = Column(String(MAX_LEN_OF_SOURCE_ID), nullable=False, unique=True)
    dip_anonymization_enabled = Column(Boolean, default=True, nullable=False)
    comment = Column(Text)

    # one-to-many relationship
    subsources = relationship('Subsource', back_populates='source')

    def __str__(self):
        return 'Source "{}"'.format(formattable_as_str(self.source_id))

    __repr__ = attr_repr('source_id')

    _columns_to_validate = ['source_id', 'anonymized_source_id']


class Subsource(Base):

    __tablename__ = 'subsource'
    __table_args__ = (
        UniqueConstraint('label', 'source_id'),
        mysql_opts(),
    )

    # here we use a surrogate key because:
    # * natural keys do not play well with Admin Panel's "inline" forms
    # * this model is involved in a lot of relationships (it is easier
    #   to cope with them when a surrogate key is in use...)
    id = Column(Integer, primary_key=True)

    label = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), nullable=False)
    comment = Column(Text)

    source_id = Column(
        String(MAX_LEN_OF_SOURCE_ID),
        ForeignKey('source.source_id', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    source = relationship('Source', back_populates='subsources')

    inclusion_criteria = relationship(
        'CriteriaContainer',
        secondary=subsource_inclusion_criteria_link,
        back_populates='inclusion_subsources')
    exclusion_criteria = relationship(
        'CriteriaContainer',
        secondary=subsource_exclusion_criteria_link,
        back_populates='exclusion_subsources')

    subsource_groups = relationship(
        'SubsourceGroup',
        secondary=subsource_subsource_group_link,
        back_populates='subsources')

    def __str__(self):
        return 'Subsource "{}"'.format(formattable_as_str(self.label))

    __repr__ = attr_repr('id', 'label', 'source_id')

    _columns_to_validate = ['label']


class SubsourceGroup(Base):

    __tablename__ = 'subsource_group'
    __table_args__ = mysql_opts()

    label = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)
    comment = Column(Text)

    subsources = relationship(
        'Subsource',
        secondary=subsource_subsource_group_link,
        back_populates='subsource_groups')

    def __str__(self):
        return 'Subsource group "{}"'.format(formattable_as_str(self.label))

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class CriteriaContainer(Base):

    __tablename__ = 'criteria_container'
    __table_args__ = mysql_opts()

    label = Column(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)

    criteria_asns = relationship(
        'CriteriaASN',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_ccs = relationship(
        'CriteriaCC',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_ip_networks = relationship(
        'CriteriaIPNetwork',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_names = relationship(
        'CriteriaName',
        back_populates='criteria_container',
        cascade='all, delete-orphan')

    criteria_categories = relationship(
        'CriteriaCategory',
        secondary=criteria_category_link,
        back_populates='criteria_containers')

    inclusion_subsources = relationship(
        'Subsource',
        secondary=subsource_inclusion_criteria_link,
        # we set `passive_deletes` to let secondary's `ondelete='RESTRICT'`
        # do its job... (note, however, that loading this collection -- e.g.,
        # by accessing `inclusion_subsources` of a CriteriaContainer -- may
        # prevent that, i.e., may make a CriteriaContainer deletable! (even
        # if its `inclusion_subsources` collection is *not* empty) [because
        # of some SQLAlchemy's auto-delete actions specific to many-to-many/
        # /`secondary`-related stuff...])
        passive_deletes='all',
        back_populates='inclusion_criteria')
    exclusion_subsources = relationship(
        'Subsource',
        secondary=subsource_exclusion_criteria_link,
        # we set `passive_deletes` to let secondary's `ondelete='RESTRICT'`
        # do its job... (note, however, that loading this collection -- e.g.,
        # by accessing `exclusion_subsources` of a CriteriaContainer -- may
        # prevent that, i.e., may make a CriteriaContainer deletable! (even
        # if its `exclusion_subsources` collection is *not* empty) [because
        # of some SQLAlchemy's auto-delete actions specific to many-to-many/
        # /`secondary`-related stuff...])
        passive_deletes='all',
        back_populates='exclusion_criteria')

    def __str__(self):
        return 'Criteria container "{}"'.format(formattable_as_str(self.label))

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class SystemGroup(_ExternalInterfaceMixin, Base):

    __tablename__ = 'system_group'
    __table_args__ = mysql_opts()

    name = Column(String(MAX_LEN_OF_SYSTEM_GROUP_NAME), primary_key=True)

    users = relationship(
        'User',
        secondary=user_system_group_link,
        back_populates='system_groups')

    def __str__(self):
        return 'System group "{}"'.format(formattable_as_str(self.name))

    __repr__ = attr_repr('name')

    _columns_to_validate = ['name']


class Cert(_ExternalInterfaceMixin, Base):

    __tablename__ = 'cert'
    __table_args__ = mysql_opts()

    ca_cert_label = Column(
        String(MAX_LEN_OF_CA_LABEL),
        ForeignKey('ca_cert.ca_label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        primary_key=True)
    ca_cert = relationship('CACert', back_populates='certs')
    serial_hex = Column(
        String(MAX_LEN_OF_CERT_SERIAL_HEX),
        primary_key=True)

    # TODO: determine whether certificate records are required
    #       to have their owner users or components; if they are
    #       some mechanism should ensure that *exactly one* of
    #       {`owner_login`,`owner_component_login`} is not null
    owner_login = Column(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    owner = relationship(
        'User',
        back_populates='owned_certs',
        foreign_keys=owner_login)

    owner_component_login = Column(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    owner_component = relationship(
        'Component',
        back_populates='owned_certs',
        foreign_keys=owner_component_login)

    # TODO: some mechanism should ensure that: `certificate` is a valid PEM of a user certificate;
    #       `csr`, if any, is a valid CSR + matches `certificate`; fields that reflect certificate
    #       content really match it (concerns: `serial_hex`, `owner_login`/`owner_component_login`,
    #       `valid_from`, `expires_on`, `is_client_cert`, `is_server_cert`
    #       and related CACert's `certificate`)
    certificate = Column(Text, nullable=False)
    csr = Column(Text, nullable=True)

    valid_from = Column(DateTime, nullable=False)
    expires_on = Column(DateTime, nullable=False)

    is_client_cert = Column(Boolean, default=False, nullable=False)
    is_server_cert = Column(Boolean, default=False, nullable=False)

    created_on = Column(DateTime, nullable=False)
    creator_details = Column(Text)

    # TODO: some mechanism should ensure that *exactly one* of
    #       {`created_by_login`,`created_by_component_login`} is not null
    created_by_login = Column(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    created_by = relationship(
        'User',
        back_populates='created_certs',
        foreign_keys=created_by_login)

    created_by_component_login = Column(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    created_by_component = relationship(
        'Component',
        back_populates='created_certs',
        foreign_keys=created_by_component_login)

    # TODO: some mechanism should ensure that:
    #       *if* certificate is revoked
    #       *then*
    #          * `revoked_on` is not null
    #          * and `revocation_comment` is not null
    #          * and *exactly one* of {`revoked_by_login`,`revoked_by_component_login`} is not null
    #       *else*
    #          * *all* of these four fields are null
    revoked_on = Column(DateTime)
    revocation_comment = Column(Text)

    revoked_by_login = Column(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    revoked_by = relationship(
        'User',
        back_populates='revoked_certs',
        foreign_keys=revoked_by_login)

    revoked_by_component_login = Column(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    revoked_by_component = relationship(
        'Component',
        back_populates='revoked_certs',
        foreign_keys=revoked_by_component_login)

    # the attribute is a reference to `ca_cert.profile`
    ca_profile = association_proxy('ca_cert', 'profile')

    @property
    def is_revoked(self):
        return any((self.revoked_on,
                    self.revoked_by_login,
                    self.revoked_by_component_login,
                    self.revocation_comment))

    def __str__(self):
        revocation_marker_prefix = ('[revoked] ' if self.is_revoked else '')
        return '{}Cert #{} (@{})'.format(revocation_marker_prefix,
                                         formattable_as_str(self.serial_hex),
                                         formattable_as_str(self.ca_cert))

    __repr__ = attr_repr('serial_hex', 'ca_cert_label', 'ca_profile', 'revoked_on')

    _columns_to_validate = [
        'serial_hex',
        'certificate',
        'csr',
        'creator_details',
        'created_on',
        'valid_from',
        'expires_on',
        'revoked_on',
        'revocation_comment',
    ]


class CACert(_ExternalInterfaceMixin, Base):

    __tablename__ = 'ca_cert'
    __table_args__ = mysql_opts()

    ca_label = Column(String(MAX_LEN_OF_CA_LABEL), primary_key=True)
    parent_ca_label = Column(
        String(MAX_LEN_OF_CA_LABEL),
        ForeignKey(ca_label, onupdate='CASCADE',
                   ondelete='RESTRICT'))
    children_ca = relationship(
        'CACert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        backref=backref('parent_ca', remote_side=ca_label))

    profile = Column(mysql.ENUM(CLIENT_CA_PROFILE_NAME, SERVICE_CA_PROFILE_NAME), nullable=True)
    # TODO: add validation ensuring that `certificate` is a valid PEM of a CA certificate
    certificate = Column(Text, nullable=False)
    # TODO: add validation ensuring that `ssl_config` is a valid *.ini-like config
    ssl_config = Column(Text, nullable=False)

    certs = relationship('Cert', back_populates='ca_cert')

    def __str__(self):
        profile_marker_suffix = (' - {}'.format(formattable_as_str(self.profile)) if self.profile
                                 else '')
        return 'CACert "{}"{}'.format(formattable_as_str(self.ca_label),
                                      profile_marker_suffix)

    __repr__ = attr_repr('ca_label', 'profile', 'parent_ca_label')

    _columns_to_validate = ['ca_label', 'certificate', 'ssl_config']

# Copyright (c) 2018-2022 NASK. All rights reserved.

import datetime
import string
from collections.abc import MutableSequence

from passlib.hash import bcrypt
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
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
    column_property,
    relationship,
    validates,
)
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.orm.properties import ColumnProperty
from sqlalchemy.orm.relationships import RelationshipProperty

from n6lib.auth_db._ddl_naming_convention import make_metadata_naming_convention
from n6lib.auth_db._before_alembic import (
    MYSQL_ENGINE,
    MYSQL_CHARSET,
    MYSQL_COLLATE,

    CLIENT_CA_PROFILE_NAME,
    SERVICE_CA_PROFILE_NAME,

    REGISTRATION_REQUEST_STATUS_NEW,
    REGISTRATION_REQUEST_STATUSES,

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
from n6lib.auth_db._before_alembic.legacy_simplified_validators import AuthDBSimplifiedValidators
from n6lib.class_helpers import attr_repr


_MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY = 736
assert _MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY < MAX_LEN_OF_URL
assert (MYSQL_ENGINE == 'InnoDB' and
        MYSQL_CHARSET == 'utf8mb4' and
        MYSQL_COLLATE == 'utf8mb4_nopad_bin')


auth_db_validators = AuthDBSimplifiedValidators()


def mysql_opts():
    return dict(
        mysql_engine=MYSQL_ENGINE,
        mysql_charset=MYSQL_CHARSET,
        mysql_collate=MYSQL_COLLATE,
    )


def col(*args, **kwargs):
    return column_property(Column(*args, **kwargs), active_history=True)

def rel(*args, **kwargs):
    return relationship(*args, active_history=True, **kwargs)


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
                            for key, val in kwargs.items()}
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
        super(AuthDBCustomDeclarativeMeta, cls).__init__(*args, **kwargs)
        if cls.__is_concrete_model_class():
            cls.__verify_assumptions()

    #
    # Providing column validators for a model class

    def __provide_validators(cls):
        for column_name in getattr(cls, '_columns_to_validate', ()):
            cls.__provide_validator_for_column(column_name)

    def __provide_validator_for_column(cls, column_name):
        validator_name, validator_method = cls.__get_validator_name_and_method(column_name)
        validator_func = cls.__make_validator_func(column_name, validator_name, validator_method)
        cls.__setup_sqlalchemy_validator(column_name, validator_name, validator_func)

    def __get_validator_name_and_method(cls, column_name):
        for validator_name in cls.__iter_possible_validator_names(column_name):
            validator_method = getattr(auth_db_validators, validator_name, None)
            if validator_method is not None:
                return validator_name, validator_method
        raise AssertionError('no validator found for column {!a}'.format(column_name))

    def __iter_possible_validator_names(cls, column_name):
        # first, try with qualified name (including table name + column name)
        yield auth_db_validators.VALIDATOR_METHOD_PREFIX + cls.__tablename__ + '__' + column_name
        # then, try with unqualified name (including just column name)
        yield auth_db_validators.VALIDATOR_METHOD_PREFIX + column_name

    def __make_validator_func(cls, column_name, validator_name, validator_method):
        column_prop = getattr(cls, column_name)
        assert (isinstance(column_prop, ColumnProperty) and
                isinstance(column_prop.expression, Column) and
                column_prop.columns == [column_prop.expression])
        column = column_prop.expression
        column_is_nullable = column.nullable

        def validator_func(self, key, value):
            if value is None and column_is_nullable:
                return None
            try:
                return validator_method(value)
            except Exception as exc:
                exc.invalid_field = key
                exc._is_n6_auth_db_validation_error_ = True
                raise

        validator_func.__name__ = validator_name
        return validator_func

    def __setup_sqlalchemy_validator(cls, column_name, validator_name, validator_func):
        sqlalchemy_validator_maker = validates(column_name)
        sqlalchemy_validator = sqlalchemy_validator_maker(validator_func)
        setattr(cls, validator_name, sqlalchemy_validator)

    #
    # Additional checks concerning a concrete model class

    __BASE_MODEL_CLASS_NAME = 'Base'
    __MAPPED_ATTR_NAME_LEGAL_CHARACTERS = frozenset(string.ascii_lowercase + string.digits + '_')

    def __is_concrete_model_class(cls):
        return cls.__name__ != cls.__BASE_MODEL_CLASS_NAME

    def __verify_assumptions(cls):
        mapper = cls.__mapper__
        table = cls.__table__
        if not (isinstance(mapper, Mapper) and
                isinstance(table, Table) and
                isinstance(table.key, str) and
                isinstance(table.name, str) and
                table.name and
                (table.key == table.name or
                 table.key.endswith('.{}'.format(table.name)))):
            raise NotImplementedError(
                'For the {!a} model class, some of our basic '
                'assumptions are not true! Please, check whether it '
                'is a bug or just a result of using some sophisticated '
                'SQLAlchemy\'s features; and, if it is the latter, '
                'whether we really need them! (Let\'s keep things '
                'simple!)'.format(cls))
        for attr_name, column in mapper.columns.items():
            instrumented_attr = getattr(cls, attr_name, None)
            column_prop = getattr(instrumented_attr, 'property', None)
            if not (isinstance(attr_name, str) and
                    isinstance(column, Column) and
                    isinstance(column.key, str) and
                    isinstance(column.name, str) and
                    isinstance(instrumented_attr, InstrumentedAttribute) and
                    isinstance(column_prop, ColumnProperty) and
                    isinstance(column_prop.key, str) and
                    isinstance(column_prop.columns, list) and
                    len(column_prop.columns) == 1 and
                    column is column_prop.columns[0] is column_prop.expression and
                    column_prop is mapper.get_property_by_column(column) and
                    column_prop.key == column.key == attr_name and
                    attr_name and
                    cls.__MAPPED_ATTR_NAME_LEGAL_CHARACTERS.issuperset(attr_name)):
                raise NotImplementedError(
                    'For the {!a} model class and its attribute {!a}, '
                    'some of our basic assumptions are not true! '
                    'Please, check whether it is a bug or just a '
                    'result of using some sophisticated SQLAlchemy\'s '
                    'features; and, if it is the latter, whether we '
                    'really need them! (Let\'s keep things simple!)'
                        .format(cls, attr_name))
            if attr_name != column.name:
                raise NotImplementedError(
                    'The property key (model attribute name) {!a} is '
                    '*not* equal to the corresponding database column '
                    'name {!a}. SQLAlchemy supports such cases but, '
                    'for the sake of simplicity, the n6\'s Auth DB '
                    'does *not*. If you insist that such cases should '
                    'be supported, you need to carefully adjust our '
                    'code (among others, making Audit Log messages '
                    'include info that attribute x refers to column '
                    'y...). But do we really need that?! Let\'s keep '
                    'things simple!'.format(attr_name, column.name))


Base = declarative_base(
    metaclass=AuthDBCustomDeclarativeMeta,
    metadata=MetaData(naming_convention=make_metadata_naming_convention()))

# noinspection PyUnresolvedReferences
assert Base.__name__ == Base._AuthDBCustomDeclarativeMeta__BASE_MODEL_CLASS_NAME


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
        return bcrypt.hash(password) if password else None

    # noinspection PyUnresolvedReferences
    def verify_password(self, password):
        if self.password:
            return bcrypt.verify(password, self.password)
        return None


class Org(_ExternalInterfaceMixin, Base):

    __tablename__ = 'org'
    __table_args__ = mysql_opts()

    # Basic data
    org_id = col(String(MAX_LEN_OF_ORG_ID), primary_key=True)
    actual_name = col(String(MAX_LEN_OF_OFFICIAL_ACTUAL_NAME))
    full_access = col(Boolean, default=False, nullable=False)
    stream_api_enabled = col(Boolean, default=False, nullable=False)

    org_groups = rel('OrgGroup', secondary=org_org_group_link, back_populates='orgs')
    users = rel('User', back_populates='org')

    # "Inside" access zone
    access_to_inside = col(Boolean, default=False, nullable=False)
    inside_subsources = rel(
        'Subsource',
        secondary=org_inside_subsource_link,
        backref='inside_orgs')
    inside_off_subsources = rel(
        'Subsource',
        secondary=org_inside_off_subsource_link,
        backref='inside_off_orgs')
    inside_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_inside_subsource_group_link,
        backref='inside_orgs')
    inside_off_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_inside_off_subsource_group_link,
        backref='inside_off_orgs')

    # "Threats" access zone
    access_to_threats = col(Boolean, default=False, nullable=False)
    threats_subsources = rel(
        'Subsource',
        secondary=org_threats_subsource_link,
        backref='threats_orgs')
    threats_off_subsources = rel(
        'Subsource',
        secondary=org_threats_off_subsource_link,
        backref='threats_off_orgs')
    threats_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_threats_subsource_group_link,
        backref='threats_orgs')
    threats_off_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_threats_off_subsource_group_link,
        backref='threats_off_orgs')

    # "Search" access zone
    access_to_search = col(Boolean, default=False, nullable=False)
    search_subsources = rel(
        'Subsource',
        secondary=org_search_subsource_link,
        backref='search_orgs')
    search_off_subsources = rel(
        'Subsource',
        secondary=org_search_off_subsource_link,
        backref='search_off_orgs')
    search_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_search_subsource_group_link,
        backref='search_orgs')
    search_off_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_search_off_subsource_group_link,
        backref='search_off_orgs')

    # Email notification settings
    email_notification_enabled = col(Boolean, default=False, nullable=False)
    email_notification_addresses = rel(
        'EMailNotificationAddress',
        back_populates='org',
        cascade='all, delete-orphan')
    email_notification_times = rel(
        'EMailNotificationTime',
        back_populates='org',
        cascade='all, delete-orphan')
    email_notification_language = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=True)
    email_notification_business_days_only = col(Boolean, default=False, nullable=False)

    # "Inside" event criteria checked by n6filter
    inside_filter_asns = rel(
        'InsideFilterASN',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_ccs = rel(
        'InsideFilterCC',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_fqdns = rel(
        'InsideFilterFQDN',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_ip_networks = rel(
        'InsideFilterIPNetwork',
        back_populates='org',
        cascade='all, delete-orphan')
    inside_filter_urls = rel(
        'InsideFilterURL',
        back_populates='org',
        cascade='all, delete-orphan')

    # Official entity data
    public_entity = col(Boolean, default=False, nullable=False)
    verified = col(Boolean, default=False, nullable=False)

    entity_type_label = col(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('entity_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    entity_type = rel('EntityType', back_populates='orgs')

    location_type_label = col(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('location_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    location_type = rel('LocationType', back_populates='orgs')

    location = col(String(MAX_LEN_OF_OFFICIAL_LOCATION))
    location_coords = col(String(MAX_LEN_OF_OFFICIAL_LOCATION_COORDS))
    address = col(String(MAX_LEN_OF_OFFICIAL_ADDRESS))

    extra_ids = rel(
        'ExtraId',
        back_populates='org',
        cascade='all, delete-orphan')

    contact_points = rel(
        'ContactPoint',
        back_populates='org',
        cascade='all, delete-orphan')

    def __str__(self):
        return 'Org "{}"'.format(self.org_id)

    __repr__ = attr_repr('org_id')

    _columns_to_validate = ['org_id', 'email_notification_language']


class RegistrationRequest(_ExternalInterfaceMixin, Base):

    __tablename__ = 'registration_request'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)

    submitted_on = col(DateTime, nullable=False)
    modified_on = col(DateTime, nullable=False, onupdate=datetime.datetime.utcnow)
    status = col(
        mysql.ENUM(*REGISTRATION_REQUEST_STATUSES),
        nullable=False,
        default=REGISTRATION_REQUEST_STATUS_NEW)

    org_id = col(String(MAX_LEN_OF_ORG_ID), nullable=False)
    actual_name = col(String(MAX_LEN_OF_OFFICIAL_ACTUAL_NAME), nullable=False)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    submitter_title = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        nullable=False)
    submitter_firstname_and_surname = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        nullable=False)

    csr = col(Text, nullable=False)

    email_notification_language = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=True)
    email_notification_addresses = rel(
        'RegistrationRequestEMailNotificationAddress',
        back_populates='registration_request',
        cascade='all, delete-orphan')

    asns = rel(
        'RegistrationRequestASN',
        back_populates='registration_request',
        cascade='all, delete-orphan')
    fqdns = rel(
        'RegistrationRequestFQDN',
        back_populates='registration_request',
        cascade='all, delete-orphan')
    ip_networks = rel(
        'RegistrationRequestIPNetwork',
        back_populates='registration_request',
        cascade='all, delete-orphan')

    __repr__ = attr_repr('id', 'org_id', 'submitted_on')

    _columns_to_validate = [
        'submitted_on',
        'modified_on',

        'org_id',
        'email',
        'csr',

        'email_notification_language',
    ]


class EMailNotificationAddress(Base):

    __tablename__ = 'email_notification_address'
    __table_args__ = (
        UniqueConstraint('email', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='email_notification_addresses')

    __repr__ = attr_repr('id', 'email', 'org_id')

    _columns_to_validate = ['email']


class RegistrationRequestEMailNotificationAddress(Base):

    __tablename__ = 'registration_request_email_notification_address'
    __table_args__ = (
        UniqueConstraint('email', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    registration_request_id = col(
        Integer,
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel(
        'RegistrationRequest',
        back_populates='email_notification_addresses')

    __repr__ = attr_repr('id', 'email', 'registration_request_id')

    _columns_to_validate = ['email']


class EMailNotificationTime(Base):

    __tablename__ = 'email_notification_time'
    __table_args__ = (
        UniqueConstraint('notification_time', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    notification_time = col(Time, nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='email_notification_times')

    __repr__ = attr_repr('id', 'notification_time', 'org_id')

    _columns_to_validate = ['notification_time']


class InsideFilterASN(Base):

    __tablename__ = 'inside_filter_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='inside_filter_asns')

    __repr__ = attr_repr('id', 'asn', 'org_id')

    _columns_to_validate = ['asn']


class RegistrationRequestASN(Base):

    __tablename__ = 'registration_request_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    registration_request_id = col(
        Integer,
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='asns')

    __repr__ = attr_repr('id', 'asn', 'registration_request_id')

    _columns_to_validate = ['asn']


class CriteriaASN(Base):

    __tablename__ = 'criteria_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_asns')

    __repr__ = attr_repr('id', 'asn', 'criteria_container_label')

    _columns_to_validate = ['asn']


class InsideFilterCC(Base):

    __tablename__ = 'inside_filter_cc'
    __table_args__ = (
        UniqueConstraint('cc', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    cc = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='inside_filter_ccs')

    __repr__ = attr_repr('id', 'cc', 'org_id')

    _columns_to_validate = ['cc']


class CriteriaCC(Base):

    __tablename__ = 'criteria_cc'
    __table_args__ = (
        UniqueConstraint('cc', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    cc = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_ccs')

    __repr__ = attr_repr('id', 'cc', 'criteria_container_label')

    _columns_to_validate = ['cc']


class InsideFilterFQDN(Base):

    __tablename__ = 'inside_filter_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    fqdn = col(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='inside_filter_fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'org_id')

    _columns_to_validate = ['fqdn']


class RegistrationRequestFQDN(Base):

    __tablename__ = 'registration_request_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    fqdn = col(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    registration_request_id = col(
        Integer,
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'registration_request_id')

    _columns_to_validate = ['fqdn']


class InsideFilterIPNetwork(Base):

    __tablename__ = 'inside_filter_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='inside_filter_ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'org_id')

    _columns_to_validate = ['ip_network']


class RegistrationRequestIPNetwork(Base):

    __tablename__ = 'registration_request_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    registration_request_id = col(
        Integer,
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'registration_request_id')

    _columns_to_validate = ['ip_network']


class CriteriaIPNetwork(Base):

    __tablename__ = 'criteria_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_ip_networks')

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

    id = col(Integer, primary_key=True)
    url = col(Unicode(MAX_LEN_OF_URL), nullable=False)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='inside_filter_urls')

    __repr__ = attr_repr('id', 'url', 'org_id')

    _columns_to_validate = ['url']


class CriteriaName(Base):

    __tablename__ = 'criteria_name'
    __table_args__ = (
        UniqueConstraint('name', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    name = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_SHORT_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_names')

    __repr__ = attr_repr('id', 'name', 'criteria_container_label')

    _columns_to_validate = ['name']


class CriteriaCategory(Base):

    __tablename__ = 'criteria_category'
    __table_args__ = mysql_opts()

    category = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)

    criteria_containers = rel(
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
        return str(self.category)

    __repr__ = attr_repr('category')

    _columns_to_validate = ['category']


class EntityType(Base):

    __tablename__ = 'entity_type'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    orgs = rel(
        'Org',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='entity_type')

    def __str__(self):
        return str(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class LocationType(Base):

    __tablename__ = 'location_type'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    orgs = rel(
        'Org',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='location_type')

    def __str__(self):
        return str(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class ExtraIdType(Base):

    __tablename__ = 'extra_id_type'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), primary_key=True)

    extra_ids = rel('ExtraId', back_populates='id_type')

    def __str__(self):
        return str(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class ExtraId(Base):

    __tablename__ = 'extra_id'
    __table_args__ = (
        UniqueConstraint('value', 'id_type_label', 'org_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    value = col(String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL), nullable=False)

    id_type_label = col(
        String(MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL),
        ForeignKey('extra_id_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    id_type = rel('ExtraIdType', back_populates='extra_ids')

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='extra_ids')

    __repr__ = attr_repr('id', 'value', 'id_type_label', 'org_id')

    _columns_to_validate = ['value']


class ContactPoint(Base):

    __tablename__ = 'contact_point'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='contact_points')

    title = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    name = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    surname = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING))
    email = col(String(MAX_LEN_OF_EMAIL))
    phone = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING))

    __repr__ = attr_repr('id', 'email', 'org_id')

    _columns_to_validate = ['email']


class OrgGroup(Base):

    __tablename__ = 'org_group'
    __table_args__ = mysql_opts()

    org_group_id = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)
    comment = col(Text)

    # "Inside" access zone
    inside_subsources = rel(
        'Subsource',
        secondary=org_group_inside_subsource_link,
        backref='inside_org_groups')
    inside_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_group_inside_subsource_group_link,
        backref='inside_org_groups')

    # "Threats" access zone
    threats_subsources = rel(
        'Subsource',
        secondary=org_group_threats_subsource_link,
        backref='threats_org_groups')
    threats_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_group_threats_subsource_group_link,
        backref='threats_org_groups')

    # "Search" access zone
    search_subsources = rel(
        'Subsource',
        secondary=org_group_search_subsource_link,
        backref='search_org_groups')
    search_subsource_groups = rel(
        'SubsourceGroup',
        secondary=org_group_search_subsource_group_link,
        backref='search_org_groups')

    orgs = rel('Org', secondary=org_org_group_link, back_populates='org_groups')

    def __str__(self):
        return 'Org group "{}"'.format(self.org_group_id)

    __repr__ = attr_repr('org_group_id')

    _columns_to_validate = ['org_group_id']


class User(_ExternalInterfaceMixin, _PassEncryptMixin, Base):

    __tablename__ = 'user'
    __table_args__ = mysql_opts()

    # here we use a surrogate key because natural keys do not play well
    # with Admin Panel's "inline" forms (cannot change the key by using
    # such a form...)
    id = col(Integer, primary_key=True)

    login = col(String(MAX_LEN_OF_EMAIL), nullable=False, unique=True)
    password = col(String(MAX_LEN_OF_PASSWORD_HASH))

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    org = rel('Org', back_populates='users')

    system_groups = rel(
        'SystemGroup',
        secondary=user_system_group_link,
        back_populates='users')

    owned_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='owner',
        foreign_keys='Cert.owner_login')
    created_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='created_by',
        foreign_keys='Cert.created_by_login')
    revoked_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='revoked_by',
        foreign_keys='Cert.revoked_by_login')

    def __str__(self):
        return 'User "{}"'.format(self.login)

    __repr__ = attr_repr('id', 'login', 'org_id')

    _columns_to_validate = ['login']


class Component(_ExternalInterfaceMixin, _PassEncryptMixin, Base):

    __tablename__ = 'component'
    __table_args__ = mysql_opts()

    login = col(String(MAX_LEN_OF_DOMAIN_NAME), primary_key=True)
    password = col(String(MAX_LEN_OF_PASSWORD_HASH))

    owned_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='owner_component',
        foreign_keys='Cert.owner_component_login')
    created_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='created_by_component',
        foreign_keys='Cert.created_by_component_login')
    revoked_certs = rel(
        'Cert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='revoked_by_component',
        foreign_keys='Cert.revoked_by_component_login')

    def __str__(self):
        return 'Component "{}"'.format(self.login)

    __repr__ = attr_repr('login')

    _columns_to_validate = ['login']


class Source(Base):

    __tablename__ = 'source'
    __table_args__ = mysql_opts()

    source_id = col(String(MAX_LEN_OF_SOURCE_ID), primary_key=True)
    anonymized_source_id = col(String(MAX_LEN_OF_SOURCE_ID), nullable=False, unique=True)
    dip_anonymization_enabled = col(Boolean, default=True, nullable=False)
    comment = col(Text)

    subsources = rel('Subsource', back_populates='source')

    def __str__(self):
        return 'Source "{}"'.format(self.source_id)

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
    id = col(Integer, primary_key=True)

    label = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), nullable=False)
    comment = col(Text)

    source_id = col(
        String(MAX_LEN_OF_SOURCE_ID),
        ForeignKey('source.source_id', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    source = rel('Source', back_populates='subsources')

    inclusion_criteria = rel(
        'CriteriaContainer',
        secondary=subsource_inclusion_criteria_link,
        back_populates='inclusion_subsources')
    exclusion_criteria = rel(
        'CriteriaContainer',
        secondary=subsource_exclusion_criteria_link,
        back_populates='exclusion_subsources')

    subsource_groups = rel(
        'SubsourceGroup',
        secondary=subsource_subsource_group_link,
        back_populates='subsources')

    def __str__(self):
        return 'Subsource "{}"'.format(self.label)

    __repr__ = attr_repr('id', 'label', 'source_id')

    _columns_to_validate = ['label']


class SubsourceGroup(Base):

    __tablename__ = 'subsource_group'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)
    comment = col(Text)

    subsources = rel(
        'Subsource',
        secondary=subsource_subsource_group_link,
        back_populates='subsource_groups')

    def __str__(self):
        return 'Subsource group "{}"'.format(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class CriteriaContainer(Base):

    __tablename__ = 'criteria_container'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_GENERIC_SHORT_STRING), primary_key=True)

    criteria_asns = rel(
        'CriteriaASN',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_ccs = rel(
        'CriteriaCC',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_ip_networks = rel(
        'CriteriaIPNetwork',
        back_populates='criteria_container',
        cascade='all, delete-orphan')
    criteria_names = rel(
        'CriteriaName',
        back_populates='criteria_container',
        cascade='all, delete-orphan')

    criteria_categories = rel(
        'CriteriaCategory',
        secondary=criteria_category_link,
        back_populates='criteria_containers')

    inclusion_subsources = rel(
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
    exclusion_subsources = rel(
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
        return 'Criteria container "{}"'.format(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']


class SystemGroup(_ExternalInterfaceMixin, Base):

    __tablename__ = 'system_group'
    __table_args__ = mysql_opts()

    name = col(String(MAX_LEN_OF_SYSTEM_GROUP_NAME), primary_key=True)

    users = rel(
        'User',
        secondary=user_system_group_link,
        back_populates='system_groups')

    def __str__(self):
        return 'System group "{}"'.format(self.name)

    __repr__ = attr_repr('name')

    _columns_to_validate = ['name']


class Cert(_ExternalInterfaceMixin, Base):

    __tablename__ = 'cert'
    __table_args__ = mysql_opts()

    ca_cert_label = col(
        String(MAX_LEN_OF_CA_LABEL),
        ForeignKey('ca_cert.ca_label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        primary_key=True)
    ca_cert = rel('CACert', back_populates='certs')
    serial_hex = col(
        String(MAX_LEN_OF_CERT_SERIAL_HEX),
        primary_key=True)

    owner_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    owner = rel(
        'User',
        back_populates='owned_certs',
        foreign_keys=owner_login.expression)

    owner_component_login = col(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    owner_component = rel(
        'Component',
        back_populates='owned_certs',
        foreign_keys=owner_component_login.expression)

    certificate = col(Text, nullable=False)
    csr = col(Text, nullable=True)

    valid_from = col(DateTime, nullable=False)
    expires_on = col(DateTime, nullable=False)

    is_client_cert = col(Boolean, default=False, nullable=False)
    is_server_cert = col(Boolean, default=False, nullable=False)

    created_on = col(DateTime, nullable=False)
    creator_details = col(Text)

    created_by_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    created_by = rel(
        'User',
        back_populates='created_certs',
        foreign_keys=created_by_login.expression)

    created_by_component_login = col(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    created_by_component = rel(
        'Component',
        back_populates='created_certs',
        foreign_keys=created_by_component_login.expression)

    revoked_on = col(DateTime)
    revocation_comment = col(Text)

    revoked_by_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    revoked_by = rel(
        'User',
        back_populates='revoked_certs',
        foreign_keys=revoked_by_login.expression)

    revoked_by_component_login = col(
        String(MAX_LEN_OF_DOMAIN_NAME),
        ForeignKey('component.login', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    revoked_by_component = rel(
        'Component',
        back_populates='revoked_certs',
        foreign_keys=revoked_by_component_login.expression)

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
                                         self.serial_hex,
                                         self.ca_cert)

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

    ca_label = col(String(MAX_LEN_OF_CA_LABEL), primary_key=True)
    parent_ca_label = col(
        String(MAX_LEN_OF_CA_LABEL),
        ForeignKey(ca_label.expression, onupdate='CASCADE',
                   ondelete='RESTRICT'))
    children_ca = rel(
        'CACert',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        backref=backref('parent_ca', remote_side=ca_label.expression))

    profile = col(mysql.ENUM(CLIENT_CA_PROFILE_NAME, SERVICE_CA_PROFILE_NAME), nullable=True)
    certificate = col(Text, nullable=False)
    ssl_config = col(Text, nullable=False)

    certs = rel('Cert', back_populates='ca_cert')

    def __str__(self):
        profile_marker_suffix = (' - {}'.format(self.profile) if self.profile
                                 else '')
        return 'CACert "{}"{}'.format(self.ca_label,
                                      profile_marker_suffix)

    __repr__ = attr_repr('ca_label', 'profile', 'parent_ca_label')

    _columns_to_validate = ['ca_label', 'certificate', 'ssl_config']

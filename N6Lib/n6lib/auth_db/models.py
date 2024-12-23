# Copyright (c) 2018-2024 NASK. All rights reserved.

import datetime
import string
from collections.abc import MutableSequence

from passlib.hash import bcrypt
from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    event as sqla_event,
    text as sqla_text,
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
from sqlalchemy.sql import select

from n6lib.auth_db import (
    MYSQL_ENGINE,
    MYSQL_CHARSET,
    MYSQL_COLLATE,

    CLIENT_CA_PROFILE_NAME,
    SERVICE_CA_PROFILE_NAME,

    ORG_REQUEST_STATUS_NEW,
    ORG_REQUEST_STATUS_BEING_PROCESSED,
    ORG_REQUEST_STATUS_ACCEPTED,
    ORG_REQUEST_STATUS_DISCARDED,
    ORG_REQUEST_STATUSES,
    ORG_REQUEST_PENDING_STATUSES,

    WEB_TOKEN_TYPE_FOR_MFA_CONFIG,
    WEB_TOKEN_TYPES,

    MAX_LEN_OF_CA_LABEL,
    MAX_LEN_OF_CERT_SERIAL_HEX,
    MAX_LEN_OF_COUNTRY_CODE,
    MAX_LEN_OF_DOMAIN_NAME,
    MAX_LEN_OF_EMAIL,
    MAX_LEN_OF_GENERIC_ONE_LINE_STRING,
    MAX_LEN_OF_ID_HEX,
    MAX_LEN_OF_IP_NETWORK,
    MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN,
    MAX_LEN_OF_ORG_ID,
    MAX_LEN_OF_PASSWORD_HASH,
    MAX_LEN_OF_SOURCE_ID,
    MAX_LEN_OF_SYSTEM_GROUP_NAME,
    MAX_LEN_OF_URL,
    MAX_LEN_OF_UUID4,
)
from n6lib.auth_db._ddl_naming_convention import make_metadata_naming_convention
from n6lib.auth_db.validators import AuthDBValidators
from n6lib.class_helpers import attr_repr
from n6lib.common_helpers import (
    make_exc_ascii_str,
    make_hex_id,
)
from n6lib.log_helpers import get_logger


_MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY = 736
assert _MAX_LEGAL_LEN_OF_INNODB_UTF8MB4_INDEX_KEY < MAX_LEN_OF_URL
assert (MYSQL_ENGINE == 'InnoDB' and
        MYSQL_CHARSET == 'utf8mb4' and
        MYSQL_COLLATE == 'utf8mb4_nopad_bin')


LOGGER = get_logger(__name__)


auth_db_validators = AuthDBValidators()


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


_ASCII_ALPHANUM_AND_UNDERSCORE_ONLY_CHARS = frozenset(string.ascii_letters + '0123456789_')

def ascii_alphanum_and_underscore_only(text):
    if isinstance(text, str) and _ASCII_ALPHANUM_AND_UNDERSCORE_ONLY_CHARS.issuperset(text):
        return text
    raise AssertionError('{!a} is not an ASCII-alphanumeric-and-underscore-only string')


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

# noinspection PyUnresolvedReferences,PyProtectedMember
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

# org <-> agreement
org_agreement_link = Table(
    'org_agreement_link', Base.metadata,
    Column(
        'org_id',
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'agreement_label',
        ForeignKey('agreement.label', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    **mysql_opts())

# registration_request <-> agreement
registration_request_agreement_link = Table(
    'registration_request_agreement_link', Base.metadata,
    Column(
        'registration_request_id',
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True),
    Column(
        'agreement_label',
        ForeignKey('agreement.label', onupdate='CASCADE', ondelete='CASCADE'),
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
        # type: (str) -> bool
        if not self.password:
            # No password hash is set in this Auth DB record, so we
            # *reject* the given password, no matter what it is.
            return False
        if not password:
            # When it comes to empty passwords, let's be on a safe side:
            # always *reject* them.
            return False
        if '\0' in password:
            # `bcrypt` does not accept *null* bytes (chars) in passwords
            # -- it raises an exception when it encounters one. Here we
            # do *not* want an exception, so let's just always *reject*
            # such passwords (they can never be correct).
            return False
        # noinspection PyBroadException
        try:
            return bcrypt.verify(password, self.password)
        except Exception as exc:
            LOGGER.error(
                '%a: could not verify password with bcrypt.verify() '
                '(possible cause: invalid password hash in Auth DB) - %s',
                self, make_exc_ascii_str(exc), exc_info=True)
            return False


class Org(_ExternalInterfaceMixin, Base):

    __tablename__ = 'org'
    __table_args__ = mysql_opts()

    # Basic data
    org_id = col(String(MAX_LEN_OF_ORG_ID), primary_key=True)
    actual_name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    full_access = col(Boolean, default=False, nullable=False)
    stream_api_enabled = col(Boolean, default=True, nullable=False)

    org_groups = rel('OrgGroup', secondary=org_org_group_link, back_populates='orgs')
    users = rel('User', back_populates='org')
    agreements = rel('Agreement', secondary=org_agreement_link, back_populates='orgs')

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

    # Optional one-to-one relationship with an entity
    # XXX: prevent from "stealing" entity by another org, or org by another entity...
    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='SET NULL'),
        nullable=True,
        unique=True)
    entity = rel('Entity', back_populates='org')

    config_update_requests = rel(
        'OrgConfigUpdateRequest',
        back_populates='org',
        cascade='all, delete-orphan')

    @property
    def pending_config_update_request(self):
        pending_requests_found = [req for req in self.config_update_requests
                                  if req.pending_marker is not None]
        if pending_requests_found:
            try:
                # For each organization, **at most one** pending
                # (unfinished) config update request should exist
                # (see: the constraints defined in the
                # `OrgConfigUpdateRequest` model)
                [pending_request] = pending_requests_found
            except ValueError:
                raise ValueError(
                    'More than *one* pending (unfinished) organization '
                    'config update requests for {!a} found: {!a}.'.format(
                        self,
                        pending_requests_found))
            return pending_request
        return None

    def __str__(self):
        return 'Org "{}"'.format(self.org_id)

    __repr__ = attr_repr('org_id')

    _columns_to_validate = ['org_id', 'email_notification_language']


class RegistrationRequest(_ExternalInterfaceMixin, Base):

    __tablename__ = 'registration_request'
    __table_args__ = mysql_opts()

    id = col(
        String(MAX_LEN_OF_ID_HEX),
        primary_key=True,
        default=lambda: make_hex_id(length=MAX_LEN_OF_ID_HEX))

    submitted_on = col(DateTime, nullable=False)
    modified_on = col(DateTime, nullable=False, onupdate=datetime.datetime.utcnow)
    status = col(
        mysql.ENUM(*ORG_REQUEST_STATUSES),
        nullable=False,
        default=ORG_REQUEST_STATUS_NEW)

    ticket_id = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    org_group_id = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('org_group.org_group_id', onupdate='CASCADE', ondelete='SET NULL'))
    org_group = rel('OrgGroup', back_populates='registration_requests')

    org_id = col(String(MAX_LEN_OF_ORG_ID), nullable=False)
    actual_name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    submitter_title = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        nullable=False)
    submitter_firstname_and_surname = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        nullable=False)

    # (legacy field, always NULL for new registration requests)
    csr = col(Text, nullable=True)

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

    # (these two fields are nullable, because they
    # can be NULL for legacy registration requests)
    terms_version = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=True)
    terms_lang = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=True)

    agreements = rel(
        'Agreement',
        secondary=registration_request_agreement_link,
        back_populates='registration_requests')

    __repr__ = attr_repr('id', 'org_id', 'submitted_on', 'status')

    _columns_to_validate = [
        'id',

        'submitted_on',
        'modified_on',

        'org_id',
        'email',
        'csr',

        'email_notification_language',
        'terms_lang',
    ]

    # (an attribute used in `n6adminpanel.org_request_helpers`)
    _successful_status_transition = None


class OrgConfigUpdateRequest(Base):

    __CHECK_CONSTRAINT_SQL_TEXT = (
        "status in ('{new}', '{being_processed}') AND pending_marker IS NOT NULL "
        "OR "
        "status in ('{accepted}', '{discarded}') AND pending_marker IS NULL".format(
            new=ascii_alphanum_and_underscore_only(
                ORG_REQUEST_STATUS_NEW),
            being_processed=ascii_alphanum_and_underscore_only(
                ORG_REQUEST_STATUS_BEING_PROCESSED),
            accepted=ascii_alphanum_and_underscore_only(
                ORG_REQUEST_STATUS_ACCEPTED),
            discarded=ascii_alphanum_and_underscore_only(
                ORG_REQUEST_STATUS_DISCARDED)))

    __tablename__ = 'org_config_update_request'
    __table_args__ = (
        # The intended overall effect of these constraints is that --
        # at any point in time -- at most one config update request
        # *per organization* can be in a pending (unfinished) state,
        # i.e., can have `status` equal to 'new' or 'being_processed'.
        # (See also the `on_org_config_update_request_status_change()`
        # listener defined and registered below the definition of this
        # class.)
        UniqueConstraint('org_id', 'pending_marker'),
        CheckConstraint(__CHECK_CONSTRAINT_SQL_TEXT),

        mysql_opts(),
    )

    id = col(
        String(MAX_LEN_OF_ID_HEX),
        primary_key=True,
        default=lambda: make_hex_id(length=MAX_LEN_OF_ID_HEX))

    org_id = col(
        String(MAX_LEN_OF_ORG_ID),
        ForeignKey('org.org_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org = rel('Org', back_populates='config_update_requests')

    requesting_user_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE', ondelete='SET NULL'),
        nullable=True)
    #requesting_user =  TODO?

    submitted_on = col(DateTime, nullable=False)
    modified_on = col(DateTime, nullable=False, onupdate=datetime.datetime.utcnow)

    status = col(
        mysql.ENUM(*ORG_REQUEST_STATUSES),
        nullable=False,
        default=ORG_REQUEST_STATUS_NEW)

    # (See the `on_org_config_update_request_status_change()` listener
    # defined and registered below the definition of this class.)
    _PENDING_MARKER = 'P'
    pending_marker = col(
        mysql.ENUM(_PENDING_MARKER),  # <- yes, it's a singleton
        nullable=True,
        default=_PENDING_MARKER)

    ticket_id = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    additional_comment = col(Text)

    actual_name_upd = col(Boolean, default=False, nullable=False)
    actual_name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=True)

    # Org users settings
    user_addition_or_activation_requests = rel(
        'OrgConfigUpdateRequestUserAdditionOrActivationRequest',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    user_deactivation_requests = rel(
        'OrgConfigUpdateRequestUserDeactivationRequest',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    # Email notification settings
    email_notification_enabled_upd = col(Boolean, default=False, nullable=False)
    email_notification_enabled = col(Boolean, default=False, nullable=False)

    email_notification_language_upd = col(Boolean, default=False, nullable=False)
    email_notification_language = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=True)

    email_notification_addresses_upd = col(Boolean, default=False, nullable=False)
    email_notification_addresses = rel(
        'OrgConfigUpdateRequestEMailNotificationAddress',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    email_notification_times_upd = col(Boolean, default=False, nullable=False)
    email_notification_times = rel(
        'OrgConfigUpdateRequestEMailNotificationTime',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    # "Inside" event criteria checked by n6filter
    asns_upd = col(Boolean, default=False, nullable=False)
    asns = rel(
        'OrgConfigUpdateRequestASN',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    fqdns_upd = col(Boolean, default=False, nullable=False)
    fqdns = rel(
        'OrgConfigUpdateRequestFQDN',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    ip_networks_upd = col(Boolean, default=False, nullable=False)
    ip_networks = rel(
        'OrgConfigUpdateRequestIPNetwork',
        back_populates='org_config_update_request',
        cascade='all, delete-orphan')

    __repr__ = attr_repr('id', 'org_id', 'submitted_on', 'status')

    _columns_to_validate = [
        'id',
        'submitted_on',
        'modified_on',
        'email_notification_language',
    ]

    # (an attribute used in `n6adminpanel.org_request_helpers`)
    _successful_status_transition = None

@sqla_event.listens_for(OrgConfigUpdateRequest.status, 'set')
def on_org_config_update_request_status_change(target, value, oldvalue, initiator):
    # noinspection PyProtectedMember
    target.pending_marker = (OrgConfigUpdateRequest._PENDING_MARKER
                             if value in ORG_REQUEST_PENDING_STATUSES
                             else None)


class OrgConfigUpdateRequestUserAdditionOrActivationRequest(Base):

    __tablename__ = 'org_config_update_request_user_addition_or_activation_request'
    __table_args__ = (
        UniqueConstraint('user_login', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    user_login = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel(
        'OrgConfigUpdateRequest',
        back_populates='user_addition_or_activation_requests')

    __repr__ = attr_repr('id', 'user_login', 'org_config_update_request_id')

    _columns_to_validate = ['user_login']

    @classmethod
    def from_value(cls, value):
        return cls(user_login=value)


class OrgConfigUpdateRequestUserDeactivationRequest(Base):

    __tablename__ = 'org_config_update_request_user_deactivation_request'
    __table_args__ = (
        UniqueConstraint('user_login', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    user_login = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel(
        'OrgConfigUpdateRequest',
        back_populates='user_deactivation_requests')

    __repr__ = attr_repr('id', 'user_login', 'org_config_update_request_id')

    _columns_to_validate = ['user_login']

    @classmethod
    def from_value(cls, value):
        return cls(user_login=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(email=value)


class RegistrationRequestEMailNotificationAddress(Base):

    __tablename__ = 'registration_request_email_notification_address'
    __table_args__ = (
        UniqueConstraint('email', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    registration_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel(
        'RegistrationRequest',
        back_populates='email_notification_addresses')

    __repr__ = attr_repr('id', 'email', 'registration_request_id')

    _columns_to_validate = ['email']

    @classmethod
    def from_value(cls, value):
        return cls(email=value)


class OrgConfigUpdateRequestEMailNotificationAddress(Base):

    __tablename__ = 'org_config_update_request_email_notification_address'
    __table_args__ = (
        UniqueConstraint('email', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    email = col(String(MAX_LEN_OF_EMAIL), nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel(
        'OrgConfigUpdateRequest',
        back_populates='email_notification_addresses')

    __repr__ = attr_repr('id', 'email', 'org_config_update_request_id')

    _columns_to_validate = ['email']

    @classmethod
    def from_value(cls, value):
        return cls(email=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(notification_time=value)


class OrgConfigUpdateRequestEMailNotificationTime(Base):

    __tablename__ = 'org_config_update_request_email_notification_time'
    __table_args__ = (
        UniqueConstraint('notification_time', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    notification_time = col(Time, nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel(
        'OrgConfigUpdateRequest',
        back_populates='email_notification_times')

    __repr__ = attr_repr('id', 'notification_time', 'org_config_update_request_id')

    _columns_to_validate = ['notification_time']

    @classmethod
    def from_value(cls, value):
        return cls(notification_time=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(asn=value)


class RegistrationRequestASN(Base):

    __tablename__ = 'registration_request_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    registration_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='asns')

    __repr__ = attr_repr('id', 'asn', 'registration_request_id')

    _columns_to_validate = ['asn']

    @classmethod
    def from_value(cls, value):
        return cls(asn=value)


class OrgConfigUpdateRequestASN(Base):

    __tablename__ = 'org_config_update_request_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel('OrgConfigUpdateRequest', back_populates='asns')

    __repr__ = attr_repr('id', 'asn', 'org_config_update_request_id')

    _columns_to_validate = ['asn']

    @classmethod
    def from_value(cls, value):
        return cls(asn=value)


class CriteriaASN(Base):

    __tablename__ = 'criteria_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_asns')

    __repr__ = attr_repr('id', 'asn', 'criteria_container_label')

    _columns_to_validate = ['asn']

    @classmethod
    def from_value(cls, value):
        return cls(asn=value)


class EntityASN(Base):

    __tablename__ = 'entity_asn'
    __table_args__ = (
        UniqueConstraint('asn', 'entity_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    asn = col(Integer, nullable=False)

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='asns')

    __repr__ = attr_repr('id', 'asn', 'entity_id')

    _columns_to_validate = ['asn']

    @classmethod
    def from_value(cls, value):
        return cls(asn=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(cc=value)


class CriteriaCC(Base):

    __tablename__ = 'criteria_cc'
    __table_args__ = (
        UniqueConstraint('cc', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    cc = col(String(MAX_LEN_OF_COUNTRY_CODE), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_ccs')

    __repr__ = attr_repr('id', 'cc', 'criteria_container_label')

    _columns_to_validate = ['cc']

    @classmethod
    def from_value(cls, value):
        return cls(cc=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(fqdn=value)


class RegistrationRequestFQDN(Base):

    __tablename__ = 'registration_request_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    fqdn = col(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    registration_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'registration_request_id')

    _columns_to_validate = ['fqdn']

    @classmethod
    def from_value(cls, value):
        return cls(fqdn=value)


class OrgConfigUpdateRequestFQDN(Base):

    __tablename__ = 'org_config_update_request_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    fqdn = col(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel('OrgConfigUpdateRequest', back_populates='fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'org_config_update_request_id')

    _columns_to_validate = ['fqdn']

    @classmethod
    def from_value(cls, value):
        return cls(fqdn=value)


class EntityFQDN(Base):

    __tablename__ = 'entity_fqdn'
    __table_args__ = (
        UniqueConstraint('fqdn', 'entity_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    fqdn = col(String(MAX_LEN_OF_DOMAIN_NAME), nullable=False)

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='fqdns')

    __repr__ = attr_repr('id', 'fqdn', 'entity_id')

    _columns_to_validate = ['fqdn']

    @classmethod
    def from_value(cls, value):
        return cls(fqdn=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


class RegistrationRequestIPNetwork(Base):

    __tablename__ = 'registration_request_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'registration_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    registration_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('registration_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    registration_request = rel('RegistrationRequest', back_populates='ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'registration_request_id')

    _columns_to_validate = ['ip_network']

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


class OrgConfigUpdateRequestIPNetwork(Base):

    __tablename__ = 'org_config_update_request_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'org_config_update_request_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    org_config_update_request_id = col(
        String(MAX_LEN_OF_ID_HEX),
        ForeignKey('org_config_update_request.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    org_config_update_request = rel('OrgConfigUpdateRequest', back_populates='ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'org_config_update_request_id')

    _columns_to_validate = ['ip_network']

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


class CriteriaIPNetwork(Base):

    __tablename__ = 'criteria_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'criteria_container_label')

    _columns_to_validate = ['ip_network']

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


class IgnoredIPNetwork(Base):

    __tablename__ = 'ignored_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'ignore_list_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    ignore_list_label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('ignore_list.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    ignore_list = rel('IgnoreList', back_populates='ignored_ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'ignore_list_label')

    _columns_to_validate = ['ip_network']

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


class EntityIPNetwork(Base):

    __tablename__ = 'entity_ip_network'
    __table_args__ = (
        UniqueConstraint('ip_network', 'entity_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    ip_network = col(String(MAX_LEN_OF_IP_NETWORK), nullable=False)

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='ip_networks')

    __repr__ = attr_repr('id', 'ip_network', 'entity_id')

    _columns_to_validate = ['ip_network']

    @classmethod
    def from_value(cls, value):
        return cls(ip_network=value)


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

    @classmethod
    def from_value(cls, value):
        return cls(url=value)


class CriteriaName(Base):

    __tablename__ = 'criteria_name'
    __table_args__ = (
        UniqueConstraint('name', 'criteria_container_label'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)

    criteria_container_label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        ForeignKey('criteria_container.label', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    criteria_container = rel('CriteriaContainer', back_populates='criteria_names')

    __repr__ = attr_repr('id', 'name', 'criteria_container_label')

    _columns_to_validate = ['name']

    @classmethod
    def from_value(cls, value):
        return cls(name=value)


class CriteriaCategory(Base):

    __tablename__ = 'criteria_category'
    __table_args__ = mysql_opts()

    category = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), primary_key=True)

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


class OrgGroup(Base):

    __tablename__ = 'org_group'
    __table_args__ = mysql_opts()

    org_group_id = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), primary_key=True)
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

    registration_requests = rel(
        'RegistrationRequest',
        back_populates='org_group')

    def __str__(self):
        return 'Org group "{}"'.format(self.org_group_id)

    __repr__ = attr_repr('org_group_id')

    _columns_to_validate = ['org_group_id']


class User(_ExternalInterfaceMixin, _PassEncryptMixin, Base):

    __tablename__ = 'user'
    __table_args__ = (
        CheckConstraint('login = LOWER(login)'),
        mysql_opts(),
    )

    # here we use a surrogate key because natural keys do not play well
    # with Admin Panel's "inline" forms (cannot change the key by using
    # such a form...)
    id = col(Integer, primary_key=True)

    # note: here we specify `server_default` just for pragmatic reasons
    # (without that, introducing this column would require too many
    # changes in test fixtures/auxiliary scripts/etc.)
    is_blocked = col(Boolean, default=False, server_default=sqla_text('0'), nullable=False)

    @property
    def is_active(self):
        return not self.is_blocked

    login = col(String(MAX_LEN_OF_EMAIL), nullable=False, unique=True)
    password = col(String(MAX_LEN_OF_PASSWORD_HASH))

    api_key_id = col(String(MAX_LEN_OF_UUID4), unique=True)
    api_key_id_modified_on = col(DateTime)

    mfa_key_base = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), unique=True)
    mfa_key_base_modified_on = col(DateTime)

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

    tokens = rel(
        'WebToken',
        back_populates='user',
        cascade='all, delete-orphan')
    spent_mfa_codes = rel(
        'UserSpentMFACode',
        back_populates='user',
        cascade='all, delete-orphan')

    def __str__(self):
        return 'User "{}"'.format(self.login)

    __repr__ = attr_repr('id', 'login', 'org_id')

    _columns_to_validate = [
        'login',
        'api_key_id',
        'api_key_id_modified_on',
        'mfa_key_base',
        'mfa_key_base_modified_on',
    ]

@sqla_event.listens_for(User.api_key_id, 'set')
def on_user_api_key_id_change(target, value, oldvalue, initiator):
    target.api_key_id_modified_on = datetime.datetime.utcnow()

@sqla_event.listens_for(User.mfa_key_base, 'set')
def on_user_mfa_key_base_change(target, value, oldvalue, initiator):
    target.mfa_key_base_modified_on = datetime.datetime.utcnow()


class WebToken(Base):

    __tablename__ = 'web_token'
    __table_args__ = mysql_opts()

    token_id = col(String(MAX_LEN_OF_UUID4), primary_key=True)
    token_type = col(mysql.ENUM(*WEB_TOKEN_TYPES), nullable=False)
    created_on = col(DateTime, nullable=False)
    user_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    user = rel('User', back_populates='tokens')

    # Note: the repr does not include `token_id` because we prefer
    # not to disclose it in logs, etc.
    __repr__ = attr_repr('token_type', 'created_on', 'user_login')

    _columns_to_validate = [
        'token_id',
        'created_on',
    ]


class UserProvisionalMFAConfig(Base):

    __tablename__ = 'user_provisional_mfa_config'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)
    mfa_key_base = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), unique=True, nullable=False)
    token_id = col(
        String(MAX_LEN_OF_UUID4),
        ForeignKey('web_token.token_id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    token = rel('WebToken')

    # Note: the repr does not include `mfa_key_base` or `token_id`
    # because we prefer not to disclose them in logs, etc.
    __repr__ = attr_repr('id')

    _columns_to_validate = ['mfa_key_base']

@sqla_event.listens_for(UserProvisionalMFAConfig, 'after_insert')
@sqla_event.listens_for(UserProvisionalMFAConfig, 'after_update')
def sanity_checks_after_user_provisional_mfa_config_insert_or_update(mapper, connection, target):
    my_id = target.id
    token_id = target.token_id
    tab_my = type(target).__table__
    col_my_id = tab_my.c.id
    col_my_token_id = tab_my.c.token_id
    query__all_provisional_mfa_config_ids = select([col_my_id]).where(col_my_token_id == token_id)
    ids = {cfg_id for [cfg_id] in connection.execute(query__all_provisional_mfa_config_ids)}
    if ids != {my_id}:
        other_ids = ids - {my_id}
        raise AssertionError(
            'trying to link {!a} to a WebToken to whom other provisional '
            'MFA configs are linked! (their identifiers: {})'.format(
                target,
                ', '.join(map(str, sorted(other_ids))) or 'no one?!'))
    # noinspection PyUnresolvedReferences
    tab_web_token = WebToken.__table__
    col_token_id = tab_web_token.c.token_id
    col_token_type = tab_web_token.c.token_type
    query__token_type = select([col_token_type]).where(col_token_id == token_id)
    [[token_type]] = connection.execute(query__token_type)
    if token_type != WEB_TOKEN_TYPE_FOR_MFA_CONFIG:
        raise AssertionError(
            'trying to link {!a} to a WebToken whose `token_type` is '
            'not equal to {!a}! (found `token_type`: {!a})'.format(
                target,
                WEB_TOKEN_TYPE_FOR_MFA_CONFIG,
                token_type))


class UserSpentMFACode(Base):

    __tablename__ = 'user_spent_mfa_code'
    __table_args__ = (
        UniqueConstraint('mfa_code', 'user_login'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    mfa_code = col(Integer, nullable=False)
    spent_on = col(DateTime, nullable=False)
    user_login = col(
        String(MAX_LEN_OF_EMAIL),
        ForeignKey('user.login', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    user = rel('User', back_populates='spent_mfa_codes')

    # Note: the repr does not include `mfa_code` because we prefer
    # not to disclose it in logs, etc.
    __repr__ = attr_repr('id', 'spent_on', 'user_login')

    _columns_to_validate = ['spent_on']


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


class IgnoreList(Base):

    __tablename__ = 'ignore_list'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), primary_key=True)
    comment = col(Text)

    # note: here we specify `server_default` just for pragmatic reasons...
    active = col(Boolean, default=True, server_default=sqla_text('1'), nullable=False)

    ignored_ip_networks = rel(
        'IgnoredIPNetwork',
        back_populates='ignore_list',
        cascade='all, delete-orphan')

    def __str__(self):
        text = f'Ignore list "{self.label}"'
        if not self.active:
            text += ' (deactivated)'
        return text

    __repr__ = attr_repr('label', 'active')

    _columns_to_validate = ['label']


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

    label = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)
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

    label = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), primary_key=True)
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

    label = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), primary_key=True)

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


class Agreement(_ExternalInterfaceMixin, Base):

    __tablename__ = 'agreement'
    __table_args__ = mysql_opts()

    label = col(
        String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING),
        primary_key=True,
    )

    default_consent = col(Boolean, default=True, nullable=False)

    en = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)
    pl = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)

    url_en = col(String(MAX_LEN_OF_URL), nullable=True)
    url_pl = col(String(MAX_LEN_OF_URL), nullable=True)

    orgs = rel(
        'Org',
        secondary=org_agreement_link,
        back_populates='agreements')
    registration_requests = rel(
        'RegistrationRequest',
        secondary=registration_request_agreement_link,
        back_populates='agreements')

    def __str__(self):
        return f'Agreement "{self.label}"'

    _columns_to_validate = ['label', 'en', 'pl', 'url_en', 'url_pl']

    __repr__ = attr_repr('label', 'en')


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

    # TODO: determine whether certificate records are required
    #       to have their owner users or components; if they are
    #       some mechanism should ensure that *exactly one* of
    #       {`owner_login`,`owner_component_login`} is not null
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

    # TODO: some mechanism should ensure that: `certificate` is a valid PEM of a user certificate;
    #       `csr`, if any, is a valid CSR + matches `certificate`; fields that reflect certificate
    #       content really match it (concerns: `serial_hex`, `owner_login`/`owner_component_login`,
    #       `valid_from`, `expires_on`, `is_client_cert`, `is_server_cert`
    #       and related CACert's `certificate`)
    certificate = col(Text, nullable=False)
    csr = col(Text, nullable=True)

    valid_from = col(DateTime, nullable=False)
    expires_on = col(DateTime, nullable=False)

    is_client_cert = col(Boolean, default=False, nullable=False)
    is_server_cert = col(Boolean, default=False, nullable=False)

    created_on = col(DateTime, nullable=False)
    creator_details = col(Text)

    # TODO: some mechanism should ensure that *exactly one* of
    #       {`created_by_login`,`created_by_component_login`} is not null
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

    # TODO: some mechanism should ensure that:
    #       *if* certificate is revoked
    #       *then*
    #          * `revoked_on` is not null
    #          * and `revocation_comment` is not null
    #          * and *exactly one* of {`revoked_by_login`,`revoked_by_component_login`} is not null
    #       *else*
    #          * *all* of these four fields are null
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
    # TODO: add validation ensuring that `certificate` is a valid PEM of a CA certificate
    certificate = col(Text, nullable=False)
    # TODO: add validation ensuring that `ssl_config` is a valid *.ini-like config
    ssl_config = col(Text, nullable=False)

    certs = rel('Cert', back_populates='ca_cert')

    def __str__(self):
        profile_marker_suffix = (' - {}'.format(self.profile) if self.profile
                                 else '')
        return 'CACert "{}"{}'.format(self.ca_label,
                                      profile_marker_suffix)

    __repr__ = attr_repr('ca_label', 'profile', 'parent_ca_label')

    _columns_to_validate = ['ca_label', 'certificate', 'ssl_config']


class Entity(Base):

    __tablename__ = 'entity'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)

    full_name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False, unique=True)
    short_name = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN))
    verified = col(Boolean, default=False, nullable=False)

    email = col(String(MAX_LEN_OF_EMAIL))
    address = col(Text)
    city = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN))
    postal_code = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN))

    public_essential_service = col(Boolean, default=False, nullable=False)
    sector_label = col(
        String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN),
        ForeignKey('entity_sector.label', onupdate='CASCADE',
                   ondelete='RESTRICT'))
    sector = rel('EntitySector', back_populates='entities')
    ticket_id = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    internal_id = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    extra_ids = rel(
        'EntityExtraId',
        back_populates='entity',
        cascade='all, delete-orphan')
    additional_information = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))

    asns = rel(
        'EntityASN',
        back_populates='entity',
        cascade='all, delete-orphan')
    fqdns = rel(
        'EntityFQDN',
        back_populates='entity',
        cascade='all, delete-orphan')
    ip_networks = rel(
        'EntityIPNetwork',
        back_populates='entity',
        cascade='all, delete-orphan')

    alert_email = col(String(MAX_LEN_OF_EMAIL))
    contact_points = rel(
        'EntityContactPoint',
        back_populates='entity',
        cascade='all, delete-orphan')

    dependant_entities = rel(
        'DependantEntity',
        back_populates='entity',
        cascade='all, delete-orphan')

    # one-to-one relationship
    org = rel('Org', uselist=False, back_populates='entity')

    __repr__ = attr_repr('id', 'full_name')

    _columns_to_validate = ['full_name', 'email', 'alert_email']


class EntitySector(Base):

    __tablename__ = 'entity_sector'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN), primary_key=True)

    entities = rel(
        'Entity',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='sector')

    def __str__(self):
        return str(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']

    @classmethod
    def from_label(cls, label):
        return cls(label=label)


class EntityExtraIdType(Base):

    __tablename__ = 'entity_extra_id_type'
    __table_args__ = mysql_opts()

    label = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN), primary_key=True)

    extra_ids = rel(
        'EntityExtraId',
        passive_deletes='all',  # let other side's `ondelete='RESTRICT'` do its job...
        back_populates='extra_id_type')

    def __str__(self):
        return str(self.label)

    __repr__ = attr_repr('label')

    _columns_to_validate = ['label']

    @classmethod
    def from_label(cls, label):
        return cls(label=label)


class EntityExtraId(Base):

    __tablename__ = 'entity_extra_id'
    __table_args__ = (
        UniqueConstraint('value', 'extra_id_type_label', 'entity_id'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)
    value = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN), nullable=False)

    extra_id_type_label = col(
        String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN),
        ForeignKey('entity_extra_id_type.label', onupdate='CASCADE',
                   ondelete='RESTRICT'),
        nullable=False)
    extra_id_type = rel('EntityExtraIdType', back_populates='extra_ids')

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='extra_ids')

    __repr__ = attr_repr('id', 'value', 'extra_id_type_label', 'entity_id')

    _columns_to_validate = ['value']


class EntityContactPoint(Base):

    __tablename__ = 'entity_contact_point'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='contact_points')

    name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    position = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN))
    email = col(String(MAX_LEN_OF_EMAIL))

    phones = rel(
        'EntityContactPointPhone',
        back_populates='contact_point',
        cascade='all, delete-orphan')

    external_placement = col(Boolean, default=False, nullable=False)
    external_entity_name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))
    external_entity_address = col(Text)

    __repr__ = attr_repr('id', 'name', 'email', 'entity_id', 'external_entity_name')

    _columns_to_validate = ['email', 'external_entity_name']


class EntityContactPointPhone(Base):

    __tablename__ = 'entity_contact_point_phone'
    __table_args__ = (
        UniqueConstraint('contact_point_id', 'phone_number'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)

    contact_point_id = col(
        Integer,
        ForeignKey('entity_contact_point.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    contact_point = rel('EntityContactPoint', back_populates='phones')

    phone_number = col(String(MAX_LEN_OF_OFFICIAL_OR_CONTACT_TOKEN), nullable=False)
    availability = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING))

    __repr__ = attr_repr('id', 'phone_number', 'contact_point_id')

    _columns_to_validate = ['phone_number']


class DependantEntity(Base):

    __tablename__ = 'dependant_entity'
    __table_args__ = (
        UniqueConstraint('entity_id', 'name'),
        mysql_opts(),
    )

    id = col(Integer, primary_key=True)

    entity_id = col(
        Integer,
        ForeignKey('entity.id', onupdate='CASCADE', ondelete='CASCADE'),
        nullable=False)
    entity = rel('Entity', back_populates='dependant_entities')

    name = col(String(MAX_LEN_OF_GENERIC_ONE_LINE_STRING), nullable=False)
    address = col(Text)

    __repr__ = attr_repr('id', 'name', 'entity_id')

    _columns_to_validate = ['name']


class RecentWriteOpCommit(Base):

    __tablename__ = 'recent_write_op_commit'
    __table_args__ = mysql_opts()

    id = col(Integer, primary_key=True)
    made_at = col(mysql.DATETIME(fsp=6), nullable=False, server_default=sqla_text('NOW(6)'))

    __repr__ = attr_repr('id', 'made_at')

    _columns_to_validate = ['made_at']

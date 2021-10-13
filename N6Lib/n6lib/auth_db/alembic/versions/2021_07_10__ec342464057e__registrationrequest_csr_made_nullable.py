"""RegistrationRequest.csr made nullable

Revision ID: ec342464057e
Revises: 2dc50c28cf4b
Create Date: 2021-07-10 02:43:19.290241+00:00

"""
import logging
import sys

from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import DatabaseError

from n6lib.auth_db.sqlalchemy_helpers import (
    MYSQL_ERROR_CODE_WARN_DATA_TRUNCATED,
    is_specific_db_error,
)
from n6lib.common_helpers import ascii_str


# revision identifiers, used by Alembic.
revision = 'ec342464057e'
down_revision = '2dc50c28cf4b'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'registration_request', 'csr',
        existing_type=mysql.TEXT(collation='utf8mb4_nopad_bin'),
        nullable=True)


def downgrade():
    # Note: before performing this downgrade you need to ensure, by
    # your own (!), that all `registration_request.csr` values are
    # *not* NULL.
    try:
        op.alter_column(
            'registration_request', 'csr',
            existing_type=mysql.TEXT(collation='utf8mb4_nopad_bin'),
            nullable=False)
    except DatabaseError as exc:
        if is_specific_db_error(exc, MYSQL_ERROR_CODE_WARN_DATA_TRUNCATED):
            logging.getLogger(__name__).error(
                'It seems that the `csr` field in some `registration_request` '
                'record(s) is NULL.  You need to set it to non-NULL value(s) '
                'by your own to make it possible for `registration_request.csr` '
                'to become a *NOT NULL* column (error info: %s).', ascii_str(exc))
            sys.exit(
                '\n*** EXITING WITH ERROR ***\nSee the description in the log.'
                '\nTL;DR: probably the `csr` field in some `registration_request` '
                'record(s) is NULL, and needs to be set to non-NULL value(s).')
        raise

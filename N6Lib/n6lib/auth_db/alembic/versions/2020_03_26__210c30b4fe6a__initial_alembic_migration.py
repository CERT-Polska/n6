"""Initial `alembic` migration

Revision ID: 210c30b4fe6a
Revises: 
Create Date: 2020-03-26 23:09:54.646532+00:00

"""
import logging
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import OperationalError

from n6lib.auth_db.sqlalchemy_helpers import (
    MYSQL_ERROR_CODE_BAD_TABLE,
    is_specific_db_error,
)


# revision identifiers, used by Alembic.
revision = '210c30b4fe6a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    table_to_drop = 'legacy_auth_db_prepared_marker'
    try:
        op.drop_table(table_to_drop)
    except OperationalError as exc:
        if is_specific_db_error(exc, MYSQL_ERROR_CODE_BAD_TABLE):
            logging.getLogger(__name__).error(
                'The table %a not found, so the initial Alembic '
                'migration cannot be applied.  It seems that the '
                'auth database has not been prepared with the '
                '`n6prepare_legacy_auth_db_for_alembic` script; '
                'note that only after doing that it is possible to '
                'apply any Alembic migrations.', table_to_drop)
            sys.exit(
                '\n*** EXITING WITH ERROR ***\nSee the description in the log.'
                '\nTL;DR: probably the `n6prepare_legacy_auth_db_for_alembic` '
                'script needs to be run.')
        raise


def downgrade():
    op.create_table('legacy_auth_db_prepared_marker',
                    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')

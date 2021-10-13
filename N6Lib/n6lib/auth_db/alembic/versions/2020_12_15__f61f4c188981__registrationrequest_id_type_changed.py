"""RegistrationRequest.id type changed

Revision ID: f61f4c188981
Revises: bed3681c9298
Create Date: 2020-12-15 12:45:40.071541+00:00

"""
import logging
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import DatabaseError

from n6lib.auth_db.sqlalchemy_helpers import (
    MYSQL_ERROR_CODE_TRUNCATED_WRONG_VALUE,
    is_specific_db_error,
)
from n6lib.common_helpers import ascii_str


# revision identifiers, used by Alembic.
revision = 'f61f4c188981'
down_revision = 'bed3681c9298'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f('fk__rra_c81818__rri_f1f050__rri_edbe17'),
                       'registration_request_asn', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrena_bd9bd9__rri_f1f050__rri_edbe17'),
                       'registration_request_email_notification_address', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrf_e40bb9__rri_f1f050__rri_edbe17'),
                       'registration_request_fqdn', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrin_e414bb__rri_f1f050__rri_edbe17'),
                       'registration_request_ip_network', type_='foreignkey')

    op.alter_column(table_name='registration_request',
                    column_name='id',
                    type_=sa.String(length=36),
                    existing_nullable=False)

    op.alter_column(table_name='registration_request_asn',
                    column_name='registration_request_id',
                    type_=sa.String(length=36),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rra_c81818__rri_f1f050__rri_edbe17'),
                          'registration_request_asn', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_email_notification_address',
                    column_name='registration_request_id',
                    type_=sa.String(length=36),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrena_bd9bd9__rri_f1f050__rri_edbe17'),
                          'registration_request_email_notification_address', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_fqdn',
                    column_name='registration_request_id',
                    type_=sa.String(length=36),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrf_e40bb9__rri_f1f050__rri_edbe17'),
                          'registration_request_fqdn', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_ip_network',
                    column_name='registration_request_id',
                    type_=sa.String(length=36),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrin_e414bb__rri_f1f050__rri_edbe17'),
                          'registration_request_ip_network', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')


def downgrade():
    op.drop_constraint(op.f('fk__rra_c81818__rri_f1f050__rri_edbe17'),
                       'registration_request_asn', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrena_bd9bd9__rri_f1f050__rri_edbe17'),
                       'registration_request_email_notification_address', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrf_e40bb9__rri_f1f050__rri_edbe17'),
                       'registration_request_fqdn', type_='foreignkey')
    op.drop_constraint(op.f('fk__rrin_e414bb__rri_f1f050__rri_edbe17'),
                       'registration_request_ip_network', type_='foreignkey')

    # Note: before performing this downgrade you need to ensure, by
    # your own (!), that all `registration_request.id` values (of
    # type `varchar(64)`) can be converted to integer identifiers.
    try:
        op.alter_column(table_name='registration_request',
                        column_name='id',
                        type_=sa.Integer(),
                        autoincrement=True,
                        existing_nullable=False)
    except DatabaseError as exc:
        if is_specific_db_error(exc, MYSQL_ERROR_CODE_TRUNCATED_WRONG_VALUE):
            logging.getLogger(__name__).error(
                'Some `registration_request.id` value(s) cannot be converted '
                'from VARCHAR to standard integer identifiers.  You need to '
                'adjust those values by your own to ensure that each of them '
                'consists *only* of decimal digits and those digits form an '
                'integer number in the range: 1..2147483647 (error info: %s).',
                ascii_str(exc))
            sys.exit(
                '\n*** EXITING WITH ERROR ***\nSee the description in the log.'
                '\nTL;DR: probably some `registration_request.id` value(s) '
                'need to be adjusted so that they will be able to be '
                'converted to integer ids.')
        raise

    op.alter_column(table_name='registration_request_asn',
                    column_name='registration_request_id',
                    type_=sa.Integer(),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rra_c81818__rri_f1f050__rri_edbe17'),
                          'registration_request_asn', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_email_notification_address',
                    column_name='registration_request_id',
                    type_=sa.Integer(),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrena_bd9bd9__rri_f1f050__rri_edbe17'),
                          'registration_request_email_notification_address', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_fqdn',
                    column_name='registration_request_id',
                    type_=sa.Integer(),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrf_e40bb9__rri_f1f050__rri_edbe17'),
                          'registration_request_fqdn', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

    op.alter_column(table_name='registration_request_ip_network',
                    column_name='registration_request_id',
                    type_=sa.Integer(),
                    existing_nullable=False)
    op.create_foreign_key(op.f('fk__rrin_e414bb__rri_f1f050__rri_edbe17'),
                          'registration_request_ip_network', 'registration_request',
                          ['registration_request_id'], ['id'],
                          onupdate='CASCADE', ondelete='CASCADE')

"""OrgConfigUpdateRequest added + related changes

Revision ID: 542ccb6fc926
Revises: f61f4c188981
Create Date: 2021-03-23 01:57:43.062140+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '542ccb6fc926'
down_revision = 'f61f4c188981'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'org_config_update_request',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=32), nullable=False),
        sa.Column('requesting_user_login', sa.String(length=255), nullable=True),
        sa.Column('submitted_on', sa.DateTime(), nullable=False),
        sa.Column('modified_on', sa.DateTime(), nullable=False),
        sa.Column(
            'status',
            mysql.ENUM('discarded', 'new', 'accepted', 'being_processed'),
            nullable=False),
        sa.Column('pending_marker', mysql.ENUM('P'), nullable=True),
        sa.Column('ticket_id', sa.String(length=255), nullable=True),
        sa.Column('additional_comment', sa.Text(), nullable=True),
        sa.Column('actual_name_upd', sa.Boolean(), nullable=False),
        sa.Column('actual_name', sa.String(length=255), nullable=True),
        sa.Column('email_notification_enabled_upd', sa.Boolean(), nullable=False),
        sa.Column('email_notification_enabled', sa.Boolean(), nullable=False),
        sa.Column('email_notification_language_upd', sa.Boolean(), nullable=False),
        sa.Column('email_notification_language', sa.String(length=2), nullable=True),
        sa.Column('email_notification_addresses_upd', sa.Boolean(), nullable=False),
        sa.Column('email_notification_times_upd', sa.Boolean(), nullable=False),
        sa.Column('asns_upd', sa.Boolean(), nullable=False),
        sa.Column('fqdns_upd', sa.Boolean(), nullable=False),
        sa.Column('ip_networks_upd', sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status in ('new', 'being_processed') AND pending_marker IS NOT NULL "
            "OR status in ('accepted', 'discarded') AND pending_marker IS NULL",
            name=op.f('ck__ocur_771992__s_pm_256d27')),
        sa.ForeignKeyConstraint(
            ['org_id'], ['org.org_id'],
            name=op.f('fk__ocur_771992__oi_092380__ooi_475c58'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['requesting_user_login'], ['user.login'],
            name=op.f('fk__ocur_771992__rul_5ea5bc__ul_aebb81'),
            onupdate='CASCADE',
            ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'org_id', 'pending_marker',
            name=op.f('uq__ocur_771992__oi_pm_7d3497')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_email_notification_address',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('org_config_update_request_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocurena_2480b2__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'email', 'org_config_update_request_id',
            name=op.f('uq__ocurena_2480b2__e_ocuri_7302ae')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_email_notification_time',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('notification_time', sa.Time(), nullable=False),
        sa.Column('org_config_update_request_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocurent_8ac8d7__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'notification_time', 'org_config_update_request_id',
            name=op.f('uq__ocurent_8ac8d7__nt_ocuri_8acc4c')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_asn',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asn', sa.Integer(), nullable=False),
        sa.Column('org_config_update_request_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocura_9cf501__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'asn', 'org_config_update_request_id',
            name=op.f('uq__ocura_9cf501__a_ocuri_3eefb7')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_fqdn',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fqdn', sa.String(length=255), nullable=False),
        sa.Column('org_config_update_request_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocurf_0c241d__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'fqdn', 'org_config_update_request_id',
            name=op.f('uq__ocurf_0c241d__f_ocuri_27ba10')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_ip_network',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_network', sa.String(length=18), nullable=False),
        sa.Column('org_config_update_request_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocurin_c864cc__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'ip_network', 'org_config_update_request_id',
            name=op.f('uq__ocurin_c864cc__in_ocuri_c21426')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')


def downgrade():
    op.drop_table('org_config_update_request_fqdn')
    op.drop_table('org_config_update_request_asn')
    op.drop_table('org_config_update_request_email_notification_address')
    op.drop_table('org_config_update_request_email_notification_time')
    op.drop_table('org_config_update_request_ip_network')
    op.drop_table('org_config_update_request')

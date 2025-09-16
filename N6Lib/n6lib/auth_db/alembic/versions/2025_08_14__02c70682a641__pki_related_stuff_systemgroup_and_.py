"""PKI-related stuff, SystemGroup and Component removed

Revision ID: 02c70682a641
Revises: 2acbcbafb4e3
Create Date: 2025-08-14 17:21:49.709128+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '02c70682a641'
down_revision = '2acbcbafb4e3'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('user_system_group_link')
    op.drop_table('system_group')
    op.drop_table('cert')
    op.drop_table('ca_cert')
    op.drop_table('component')


def downgrade():
    op.create_table('component',
        sa.Column('login', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint('login'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table('ca_cert',
        sa.Column('ca_label', sa.String(length=100), nullable=False),
        sa.Column('parent_ca_label', sa.String(length=100), nullable=True),
        sa.Column('profile', mysql.ENUM('client', 'service'), nullable=True),
        sa.Column('certificate', sa.Text(), nullable=False),
        sa.Column('ssl_config', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ['parent_ca_label'], ['ca_cert.ca_label'],
            name='fk__cc_01cd44__pcl_77ca83__cccl_6a33fd',
            onupdate='CASCADE'),
        sa.PrimaryKeyConstraint('ca_label'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table('cert',
        sa.Column('ca_cert_label', sa.String(length=100), nullable=False),
        sa.Column('serial_hex', sa.String(length=20), nullable=False),
        sa.Column('owner_login', sa.String(length=255), nullable=True),
        sa.Column('owner_component_login', sa.String(length=255), nullable=True),
        sa.Column('certificate', sa.Text(), nullable=False),
        sa.Column('csr', sa.Text(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('expires_on', sa.DateTime(), nullable=False),
        sa.Column('is_client_cert', sa.Boolean(), nullable=False),
        sa.Column('is_server_cert', sa.Boolean(), nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=False),
        sa.Column('creator_details', sa.Text(), nullable=True),
        sa.Column('created_by_login', sa.String(length=255), nullable=True),
        sa.Column('created_by_component_login', sa.String(length=255), nullable=True),
        sa.Column('revoked_on', sa.DateTime(), nullable=True),
        sa.Column('revocation_comment', sa.Text(), nullable=True),
        sa.Column('revoked_by_login', sa.String(length=255), nullable=True),
        sa.Column('revoked_by_component_login', sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            '`is_client_cert` in (0,1)',
            name='ck__c_062984__icc_bf04a6'),
        sa.CheckConstraint(
            '`is_server_cert` in (0,1)',
            name='ck__c_062984__isc_eaa263'),
        sa.ForeignKeyConstraint(
            ['ca_cert_label'], ['ca_cert.ca_label'],
            name='fk__c_062984__ccl_0ec846__cccl_6a33fd',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['created_by_component_login'], ['component.login'],
            name='fk__c_062984__cbcl_135741__cl_49de00',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['created_by_login'], ['user.login'],
            name='fk__c_062984__cbl_66fc0a__ul_aebb81',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['owner_component_login'], ['component.login'],
            name='fk__c_062984__ocl_8405da__cl_49de00',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['owner_login'], ['user.login'],
            name='fk__c_062984__ol_8cd1e6__ul_aebb81',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['revoked_by_component_login'], ['component.login'],
            name='fk__c_062984__rbcl_185ec1__cl_49de00',
            onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['revoked_by_login'], ['user.login'],
            name='fk__c_062984__rbl_94ab8b__ul_aebb81',
            onupdate='CASCADE'),
        sa.PrimaryKeyConstraint('ca_cert_label', 'serial_hex'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table('system_group',
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('name'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table('user_system_group_link',
        sa.Column('user_id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('system_group_name', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ['system_group_name'], ['system_group.name'],
            name='fk__usgl_44d10d__sgn_822aaf__sgn_700f92',
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['user_id'], ['user.id'],
            name='fk__usgl_44d10d__ui_f89d6b__ui_f4f095',
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'system_group_name'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

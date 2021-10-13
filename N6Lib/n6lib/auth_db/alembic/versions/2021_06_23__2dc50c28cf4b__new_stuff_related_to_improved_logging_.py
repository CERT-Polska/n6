"""New stuff related to improved logging-in, 2FA and password reset...

Revision ID: 2dc50c28cf4b
Revises: d3974815f709
Create Date: 2021-06-23 23:10:47.874242+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '2dc50c28cf4b'
down_revision = 'd3974815f709'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_token',
        sa.Column('token_id', sa.String(length=36), nullable=False),
        sa.Column(
            'token_type',
            mysql.ENUM('for_mfa_config', 'for_login', 'for_password_reset'),
            nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=False),
        sa.Column('user_login', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_login'], ['user.login'],
            name=op.f('fk__ut_00bc55__ul_4c395a__ul_aebb81'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token_id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'user_provisional_mfa_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mfa_key_base', sa.String(length=255), nullable=False),
        sa.Column('token_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ['token_id'], ['user_token.token_id'],
            name=op.f('fk__upmc_2108ab__ti_ca8868__utti_13fa09'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'mfa_key_base',
            name=op.f('uq__upmc_2108ab__mkb_b5539f')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'user_spent_mfa_code',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mfa_code', sa.Integer(), nullable=False),
        sa.Column('spent_on', sa.DateTime(), nullable=False),
        sa.Column('user_login', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_login'], ['user.login'],
            name=op.f('fk__usmc_1a1b41__ul_4c395a__ul_aebb81'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'mfa_code', 'user_login',
            name=op.f('uq__usmc_1a1b41__mc_ul_2f130e')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.add_column(
        'user',
        sa.Column('is_blocked', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    op.add_column('user', sa.Column('mfa_key_base', sa.String(length=255), nullable=True))
    op.add_column('user', sa.Column('mfa_key_base_modified_on', sa.DateTime(), nullable=True))
    op.create_unique_constraint(op.f('uq__u_04f899__mkb_b5539f'), 'user', ['mfa_key_base'])


def downgrade():
    op.drop_constraint(op.f('uq__u_04f899__mkb_b5539f'), 'user', type_='unique')
    op.drop_column('user', 'mfa_key_base_modified_on')
    op.drop_column('user', 'mfa_key_base')

    op.drop_column('user', 'is_blocked')

    op.drop_table('user_spent_mfa_code')
    op.drop_table('user_provisional_mfa_config')
    op.drop_table('user_token')

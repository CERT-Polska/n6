"""Table `user_token` replaced with `web_token`

Revision ID: 4f5d01396b61
Revises: ec342464057e
Create Date: 2021-07-16 23:39:43.822462+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '4f5d01396b61'
down_revision = 'ec342464057e'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        op.f('fk__upmc_2108ab__ti_ca8868__utti_13fa09'),
        'user_provisional_mfa_config', type_='foreignkey')
    op.drop_table('user_token')

    op.create_table(
        'web_token',
        sa.Column('token_id', sa.String(length=36), nullable=False),
        sa.Column(
            'token_type',
            mysql.ENUM('for_mfa_config', 'for_login', 'for_password_reset'),
            nullable=False),
        sa.Column('created_on', sa.DateTime(), nullable=False),
        sa.Column('user_login', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_login'], ['user.login'],
            name=op.f('fk__wt_463e1a__ul_4c395a__ul_aebb81'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('token_id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')
    op.create_foreign_key(
        op.f('fk__upmc_2108ab__ti_ca8868__wtti_81a2c0'),
        'user_provisional_mfa_config', 'web_token', ['token_id'], ['token_id'],
        onupdate='CASCADE',
        ondelete='CASCADE')


def downgrade():
    op.drop_constraint(
        op.f('fk__upmc_2108ab__ti_ca8868__wtti_81a2c0'),
        'user_provisional_mfa_config', type_='foreignkey')
    op.drop_table('web_token')

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
    op.create_foreign_key(
        op.f('fk__upmc_2108ab__ti_ca8868__utti_13fa09'),
        'user_provisional_mfa_config', 'user_token', ['token_id'], ['token_id'],
        onupdate='CASCADE',
        ondelete='CASCADE')

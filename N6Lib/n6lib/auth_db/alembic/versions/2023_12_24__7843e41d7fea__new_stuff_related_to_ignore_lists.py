"""New stuff related to ignore lists

Revision ID: 7843e41d7fea
Revises: b70854f93d73
Create Date: 2023-12-24 14:18:26.339130+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7843e41d7fea'
down_revision = 'b70854f93d73'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ignore_list',
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.PrimaryKeyConstraint('label'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'ignored_ip_network',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_network', sa.String(length=18), nullable=False),
        sa.Column('ignore_list_label', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['ignore_list_label'], ['ignore_list.label'],
            name=op.f('fk__iin_3e8790__ill_96d259__ill_d5d315'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'ip_network', 'ignore_list_label',
            name=op.f('uq__iin_3e8790__in_ill_e3fb35')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')


def downgrade():
    op.drop_table('ignored_ip_network')
    op.drop_table('ignore_list')

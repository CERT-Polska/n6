"""New official Entity's fields (alert_email and asns/fqdns/ip_networks) plus related stuff

Revision ID: 1ca02fb79db7
Revises: e6244c2249c9
Create Date: 2021-04-24 19:37:20.415164+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ca02fb79db7'
down_revision = 'e6244c2249c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'entity',
        sa.Column('alert_email', sa.String(length=255), nullable=True))

    op.create_table(
        'entity_asn',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asn', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['entity_id'], ['entity.id'],
            name=op.f('fk__ea_3a6766__ei_5364bf__ei_97d810'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'asn', 'entity_id',
            name=op.f('uq__ea_3a6766__a_ei_250686')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'entity_fqdn',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fqdn', sa.String(length=255), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['entity_id'], ['entity.id'],
            name=op.f('fk__ef_caf6d6__ei_5364bf__ei_97d810'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'fqdn', 'entity_id',
            name=op.f('uq__ef_caf6d6__f_ei_11ba27')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'entity_ip_network',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_network', sa.String(length=18), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['entity_id'], ['entity.id'],
            name=op.f('fk__ein_0f14fb__ei_5364bf__ei_97d810'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'ip_network', 'entity_id',
            name=op.f('uq__ein_0f14fb__in_ei_f5e751')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')


def downgrade():
    op.drop_table('entity_ip_network')
    op.drop_table('entity_fqdn')
    op.drop_table('entity_asn')
    op.drop_column('entity', 'alert_email')

"""Org.org_uuid added

Revision ID: 2acbcbafb4e3
Revises: db38d01774cd
Create Date: 2025-03-13 12:28:24.419178+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2acbcbafb4e3'
down_revision = 'db38d01774cd'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('org', sa.Column('org_uuid', sa.String(length=36), nullable=True))
    op.create_unique_constraint(op.f('uq__o_e87cb4__ou_926cc1'), 'org', ['org_uuid'])


def downgrade():
    op.drop_constraint(op.f('uq__o_e87cb4__ou_926cc1'), 'org', type_='unique')
    op.drop_column('org', 'org_uuid')

"""RegistrationRequest-OrgGroup relation added

Revision ID: bed3681c9298
Revises: 896531976b41
Create Date: 2020-06-04 14:13:40.422073+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bed3681c9298'
down_revision = '896531976b41'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('registration_request',
                  sa.Column('org_group_id', sa.String(length=255), nullable=True))
    op.create_foreign_key(op.f('fk__rr_c932d7__ogi_921b05__ogogi_01498e'),
                          'registration_request', 'org_group',
                          ['org_group_id'], ['org_group_id'],
                          onupdate='CASCADE', ondelete='SET NULL')


def downgrade():
    op.drop_constraint(op.f('fk__rr_c932d7__ogi_921b05__ogogi_01498e'),
                       'registration_request', type_='foreignkey')
    op.drop_column('registration_request', 'org_group_id')

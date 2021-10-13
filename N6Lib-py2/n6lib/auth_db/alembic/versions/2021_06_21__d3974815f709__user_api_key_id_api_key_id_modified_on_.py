"""User.{api_key_id,api_key_id_modified_on} added

Revision ID: d3974815f709
Revises: 1ca02fb79db7
Create Date: 2021-06-21 20:40:05.357705+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3974815f709'
down_revision = '1ca02fb79db7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('api_key_id', sa.String(length=36), nullable=True))
    op.add_column('user', sa.Column('api_key_id_modified_on', sa.DateTime(), nullable=True))
    op.create_unique_constraint(op.f('uq__u_04f899__aki_9dc8c1'), 'user', ['api_key_id'])


def downgrade():
    op.drop_constraint(op.f('uq__u_04f899__aki_9dc8c1'), 'user', type_='unique')
    op.drop_column('user', 'api_key_id_modified_on')
    op.drop_column('user', 'api_key_id')

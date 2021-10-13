"""RegistrationRequest.ticket_id added

Revision ID: 896531976b41
Revises: 9327d279a219
Create Date: 2020-05-28 23:51:47.103127+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '896531976b41'
down_revision = '9327d279a219'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('registration_request',
                  sa.Column('ticket_id', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('registration_request', 'ticket_id')

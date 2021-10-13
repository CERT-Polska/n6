"""RegistrationRequest.terms_{version,lang} added

Revision ID: e6244c2249c9
Revises: 542ccb6fc926
Create Date: 2021-04-21 22:52:42.184514+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6244c2249c9'
down_revision = '542ccb6fc926'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'registration_request',
        sa.Column('terms_lang', sa.String(length=2), nullable=True))
    op.add_column(
        'registration_request',
        sa.Column('terms_version', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('registration_request', 'terms_version')
    op.drop_column('registration_request', 'terms_lang')

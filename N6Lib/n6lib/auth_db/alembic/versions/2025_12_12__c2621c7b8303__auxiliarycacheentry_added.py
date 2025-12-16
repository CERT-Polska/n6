"""AuxiliaryCacheEntry added

Revision ID: c2621c7b8303
Revises: 02c70682a641
Create Date: 2025-12-12 15:15:27.110407+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = 'c2621c7b8303'
down_revision = '02c70682a641'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auxiliary_cache_entry',
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('raw_content', mysql.MEDIUMBLOB(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB'
    )


def downgrade():
    op.drop_table('auxiliary_cache_entry')

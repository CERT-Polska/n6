"""RecentWriteOp added

Revision ID: 51d0ad06f726
Revises: 7843e41d7fea
Create Date: 2023-12-29 20:35:01.752227+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '51d0ad06f726'
down_revision = '7843e41d7fea'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recent_write_op',
        sa.Column(
            'id', sa.Integer(),
            nullable=False),
        sa.Column(
            'performed_at', mysql.DATETIME(fsp=6),
            server_default=sa.text('NOW(6)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    connection = op.get_bind()
    with connection.begin():
        connection.execute('INSERT INTO recent_write_op SET performed_at = DEFAULT')


def downgrade():
    op.drop_table('recent_write_op')

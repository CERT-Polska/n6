"""RecentWriteOpCommit added, RecentWriteOp removed

Revision ID: a95d40241f7c
Revises: 51d0ad06f726
Create Date: 2024-01-13 22:40:51.426355+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = 'a95d40241f7c'
down_revision = '51d0ad06f726'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recent_write_op_commit',
        sa.Column(
            'id', sa.Integer(),
            nullable=False),
        sa.Column(
            'made_at', mysql.DATETIME(fsp=6),
            server_default=sa.text('NOW(6)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    connection = op.get_bind()
    with connection.begin():
        connection.execute('INSERT INTO recent_write_op_commit SET made_at = DEFAULT')

    op.drop_table('recent_write_op')


def downgrade():
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

    op.drop_table('recent_write_op_commit')

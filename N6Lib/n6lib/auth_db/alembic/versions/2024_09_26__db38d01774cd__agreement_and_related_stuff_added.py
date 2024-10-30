"""Agreement and related stuff added

Revision ID: db38d01774cd
Revises: 0b719188755e
Create Date: 2024-09-26 14:26:37.855298+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db38d01774cd'
down_revision = '0b719188755e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agreement',
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('default_consent', sa.Boolean(), nullable=False),
        sa.Column('en', sa.String(length=255), nullable=False),
        sa.Column('pl', sa.String(length=255), nullable=False),
        sa.Column('url_en', sa.String(length=2048), nullable=True),
        sa.Column('url_pl', sa.String(length=2048), nullable=True),
        sa.PrimaryKeyConstraint('label'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'registration_request_agreement_link',
        sa.Column('registration_request_id', sa.String(length=36), nullable=False),
        sa.Column('agreement_label', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['agreement_label'], ['agreement.label'],
            name=op.f('fk__rral_68864e__al_f96f13__al_1aa52d'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['registration_request_id'], ['registration_request.id'],
            name=op.f('fk__rral_68864e__rri_f1f050__rri_edbe17'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('registration_request_id', 'agreement_label'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_agreement_link',
        sa.Column('org_id', sa.String(length=32), nullable=False),
        sa.Column('agreement_label', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['agreement_label'], ['agreement.label'],
            name=op.f('fk__oal_d37fc1__al_f96f13__al_1aa52d'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['org_id'], ['org.org_id'],
            name=op.f('fk__oal_d37fc1__oi_092380__ooi_475c58'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('org_id', 'agreement_label'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')


def downgrade():
    op.drop_table('org_agreement_link')
    op.drop_table('registration_request_agreement_link')
    op.drop_table('agreement')

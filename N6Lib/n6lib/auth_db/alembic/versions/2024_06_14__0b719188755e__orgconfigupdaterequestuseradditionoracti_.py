"""OrgConfigUpdateRequestUserAdditionOrActivationRequest and OrgConfigUpdateRequestUserDeactivationRequest added

Revision ID: 0b719188755e
Revises: a95d40241f7c
Create Date: 2024-06-14 19:30:36.480623+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0b719188755e'
down_revision = 'a95d40241f7c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'org_config_update_request_user_addition_or_activation_request',
        sa.Column(
            'id', sa.Integer(),
            nullable=False),
        sa.Column(
            'user_login', sa.String(length=255),
            nullable=False),
        sa.Column(
            'org_config_update_request_id', sa.String(length=36),
            nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocuruaoar_018002__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_login', 'org_config_update_request_id',
            name=op.f('uq__ocuruaoar_018002__ul_ocuri_95453f')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')

    op.create_table(
        'org_config_update_request_user_deactivation_request',
        sa.Column(
            'id', sa.Integer(),
            nullable=False),
        sa.Column(
            'user_login', sa.String(length=255),
            nullable=False),
        sa.Column(
            'org_config_update_request_id', sa.String(length=36),
            nullable=False),
        sa.ForeignKeyConstraint(
            ['org_config_update_request_id'], ['org_config_update_request.id'],
            name=op.f('fk__ocurudr_3cd1ac__ocuri_cae6e4__ocuri_899a3a'),
            onupdate='CASCADE',
            ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_login', 'org_config_update_request_id',
            name=op.f('uq__ocurudr_3cd1ac__ul_ocuri_95453f')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_nopad_bin',
        mysql_engine='InnoDB')


def downgrade():
    op.drop_table('org_config_update_request_user_deactivation_request')
    op.drop_table('org_config_update_request_user_addition_or_activation_request')

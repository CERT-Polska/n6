"""Official-Entity-related stuff revamped (dropping obsolete tables!)

Revision ID: 9327d279a219
Revises: 210c30b4fe6a
Create Date: 2020-03-27 14:03:18.956491+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = '9327d279a219'
down_revision = '210c30b4fe6a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f('fk__o_e87cb4__etl_213732__etl_95ecc1'), 'org', type_='foreignkey')
    op.drop_constraint(op.f('fk__o_e87cb4__ltl_4a88a8__ltl_0991ed'), 'org', type_='foreignkey')
    op.drop_column('org', 'verified')
    op.drop_column('org', 'entity_type_label')
    op.drop_column('org', 'location')
    op.drop_column('org', 'address')
    op.drop_column('org', 'location_type_label')
    op.drop_column('org', 'public_entity')
    op.drop_column('org', 'location_coords')

    op.drop_index(op.f('uq__ei_e7a97f__v_itl_oi_78f3d2'), table_name='extra_id')
    op.drop_table('extra_id')

    op.drop_table('extra_id_type')
    op.drop_table('contact_point')
    op.drop_table('entity_type')
    op.drop_table('location_type')

    op.create_table('entity_extra_id_type',
                    sa.Column('label', sa.String(length=100), nullable=False),
                    sa.PrimaryKeyConstraint('label'),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('entity_sector',
                    sa.Column('label', sa.String(length=100), nullable=False),
                    sa.PrimaryKeyConstraint('label'),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('entity',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('full_name', sa.String(length=255), nullable=False),
                    sa.Column('short_name', sa.String(length=100), nullable=True),
                    sa.Column('verified', sa.Boolean(), nullable=False),
                    sa.Column('email', sa.String(length=255), nullable=True),
                    sa.Column('address', sa.Text(), nullable=True),
                    sa.Column('city', sa.String(length=100), nullable=True),
                    sa.Column('postal_code', sa.String(length=100), nullable=True),
                    sa.Column('public_essential_service', sa.Boolean(), nullable=False),
                    sa.Column('sector_label', sa.String(length=100), nullable=True),
                    sa.Column('ticket_id', sa.String(length=255), nullable=True),
                    sa.Column('internal_id', sa.String(length=255), nullable=True),
                    sa.Column('additional_information', sa.String(length=255), nullable=True),
                    sa.ForeignKeyConstraint(['sector_label'], ['entity_sector.label'],
                                            name=op.f('fk__e_bca368__sl_c17f41__esl_42f48a'),
                                            onupdate='CASCADE', ondelete='RESTRICT'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('full_name', name=op.f('uq__e_bca368__fn_4f5b8b')),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('entity_extra_id',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('value', sa.String(length=100), nullable=False),
                    sa.Column('extra_id_type_label', sa.String(length=100), nullable=False),
                    sa.Column('entity_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'],
                                            name=op.f('fk__eei_eb4357__ei_5364bf__ei_97d810'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['extra_id_type_label'],
                                            ['entity_extra_id_type.label'],
                                            name=op.f('fk__eei_eb4357__eitl_b8b08d__eeitl_a8d64a'),
                                            onupdate='CASCADE', ondelete='RESTRICT'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('value', 'extra_id_type_label', 'entity_id',
                                        name=op.f('uq__eei_eb4357__v_eitl_ei_042c8c')),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('dependant_entity',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('entity_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=255), nullable=False),
                    sa.Column('address', sa.Text(), nullable=True),
                    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'],
                                            name=op.f('fk__de_12f9f6__ei_5364bf__ei_97d810'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('entity_id', 'name',
                                        name=op.f('uq__de_12f9f6__ei_n_25bdfa')),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('entity_contact_point',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('entity_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=255), nullable=True),
                    sa.Column('position', sa.String(length=100), nullable=True),
                    sa.Column('email', sa.String(length=255), nullable=True),
                    sa.Column('external_placement', sa.Boolean(), nullable=False),
                    sa.Column('external_entity_name', sa.String(length=255), nullable=True),
                    sa.Column('external_entity_address', sa.Text(), nullable=True),
                    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'],
                                            name=op.f('fk__ecp_f4ad7e__ei_5364bf__ei_97d810'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')
    op.create_table('entity_contact_point_phone',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('contact_point_id', sa.Integer(), nullable=False),
                    sa.Column('phone_number', sa.String(length=100), nullable=False),
                    sa.Column('availability', sa.String(length=255), nullable=True),
                    sa.ForeignKeyConstraint(['contact_point_id'], ['entity_contact_point.id'],
                                            name=op.f('fk__ecpp_aa5525__cpi_00e4ec__ecpi_9e5d52'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('contact_point_id', 'phone_number',
                                        name=op.f('uq__ecpp_aa5525__cpi_pn_3ae781')),
                    mysql_charset='utf8mb4',
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_engine='InnoDB')

    op.add_column('org', sa.Column('entity_id', sa.Integer(), nullable=True))
    op.create_unique_constraint(op.f('uq__o_e87cb4__ei_5364bf'), 'org', ['entity_id'])
    op.create_foreign_key(op.f('fk__o_e87cb4__ei_5364bf__ei_97d810'), 'org', 'entity',
                          ['entity_id'], ['id'], onupdate='CASCADE', ondelete='SET NULL')


def downgrade():
    op.drop_constraint(op.f('fk__o_e87cb4__ei_5364bf__ei_97d810'), 'org', type_='foreignkey')
    op.drop_constraint(op.f('uq__o_e87cb4__ei_5364bf'), 'org', type_='unique')
    op.drop_column('org', 'entity_id')

    op.drop_table('entity_contact_point_phone')
    op.drop_table('entity_contact_point')
    op.drop_table('dependant_entity')
    op.drop_table('entity_extra_id')
    op.drop_table('entity')
    op.drop_table('entity_sector')
    op.drop_table('entity_extra_id_type')

    op.add_column('org',
                  sa.Column('location_coords',
                            mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                            nullable=True))
    op.add_column('org',
                  sa.Column('public_entity', mysql.TINYINT(display_width=1), autoincrement=False,
                            nullable=False))
    op.add_column('org',
                  sa.Column('location_type_label',
                            mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                            nullable=True))
    op.add_column('org',
                  sa.Column('address', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                            nullable=True))
    op.add_column('org',
                  sa.Column('location', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                            nullable=True))
    op.add_column('org',
                  sa.Column('entity_type_label',
                            mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                            nullable=True))
    op.add_column('org',
                  sa.Column('verified', mysql.TINYINT(display_width=1), autoincrement=False,
                            nullable=False))

    op.create_table('extra_id_type',
                    sa.Column('label', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                              nullable=False),
                    sa.PrimaryKeyConstraint('label'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')
    op.create_table('extra_id',
                    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
                    sa.Column('value', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                              nullable=False),
                    sa.Column('id_type_label',
                              mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                              nullable=False),
                    sa.Column('org_id', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=32),
                              nullable=False),
                    sa.ForeignKeyConstraint(['id_type_label'], ['extra_id_type.label'],
                                            name=op.f('fk__ei_e7a97f__itl_8e1c9e__eitl_702f4c'),
                                            onupdate='CASCADE'),
                    sa.ForeignKeyConstraint(['org_id'], ['org.org_id'],
                                            name=op.f('fk__ei_e7a97f__oi_092380__ooi_475c58'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')
    op.create_index(op.f('uq__ei_e7a97f__v_itl_oi_78f3d2'), 'extra_id',
                    ['value', 'id_type_label', 'org_id'], unique=True)

    op.create_table('location_type',
                    sa.Column('label', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                              nullable=False),
                    sa.PrimaryKeyConstraint('label'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')
    op.create_table('entity_type',
                    sa.Column('label', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=100),
                              nullable=False),
                    sa.PrimaryKeyConstraint('label'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')
    op.create_table('contact_point',
                    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
                    sa.Column('org_id', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=32),
                              nullable=False),
                    sa.Column('title', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                              nullable=True),
                    sa.Column('name', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                              nullable=True),
                    sa.Column('surname', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                              nullable=True),
                    sa.Column('email', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                              nullable=True),
                    sa.Column('phone', mysql.VARCHAR(collation='utf8mb4_nopad_bin', length=255),
                              nullable=True),
                    sa.ForeignKeyConstraint(['org_id'], ['org.org_id'],
                                            name=op.f('fk__cp_02a618__oi_092380__ooi_475c58'),
                                            onupdate='CASCADE', ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_collate='utf8mb4_nopad_bin',
                    mysql_default_charset='utf8mb4',
                    mysql_engine='InnoDB')

    op.create_foreign_key(op.f('fk__o_e87cb4__ltl_4a88a8__ltl_0991ed'), 'org', 'location_type',
                          ['location_type_label'], ['label'], onupdate='CASCADE')
    op.create_foreign_key(op.f('fk__o_e87cb4__etl_213732__etl_95ecc1'), 'org', 'entity_type',
                          ['entity_type_label'], ['label'], onupdate='CASCADE')

# Copyright (c) 2020-2021 NASK. All rights reserved.

import collections
import sys

import sqlalchemy
from sqlalchemy import (
    Column,
    Integer,
    Table,
)
from sqlalchemy.engine.result import RowProxy
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.schema import MetaData

from n6lib.auth_db._before_alembic import (
    MYSQL_CHARSET,
    MYSQL_COLLATE,
)
from n6lib.auth_db._before_alembic import legacy_models
from n6lib.auth_db.config import SQLAuthDBConfigMixin
from n6lib.auth_db.scripts import (
    BaseAuthDBScript,
    PromptingForYesOrNoMixin,
)
from n6lib.common_helpers import PlainNamespace



class _LegacyAuthDBSimplifiedConnector(SQLAuthDBConfigMixin):

    def __error_because_no_orm_capabilities(self, *args, **kwargs):
        raise TypeError('{!a} has no ORM-related capabilities'.format(self))

    __enter__ = __error_because_no_orm_capabilities
    __exit__ = __error_because_no_orm_capabilities
    get_current_session = __error_because_no_orm_capabilities



class PrepareLegacyAuthDB(PromptingForYesOrNoMixin, BaseAuthDBScript):

    """
    Prepare the Auth DB that uses a legacy (pre-Alembic) schema, so
    that it will be possible to start maintaining the schema with the
    Alembic toolset.  The preparation consists of: collecting all
    relevant content of the database, removing the database completely
    and then re-creating it (ensuring, in particular, that any missing
    tables are added and, what is most important, the new DDL naming
    convention is applied), and finally re-populating it with that old,
    previously collected, content (or at least with the relevant subset
    of it).

    BEWARE that this script acts in an unsafe, non-transactional,
    potentially disruptive way. Therefore, before running it you should
    make a backup of the database (if it contains any valuable data).

    After successful execution of this script you should apply to the
    resultant auth database any existing Alembic migrations (see the
    `N6Lib/n6lib/auth_db/alembic` directory...).

    Note that this script is intended to be executed only once -- for
    some existing auth database with a legacy schema (*not* for a new
    empty auth database, which should be created and prepared with the
    `n6create_and_initialize_auth_db` script).
    """

    LEGACY_AUTH_DB_PREPARED_MARKER_TABLE_NAME = 'legacy_auth_db_prepared_marker'

    db_connector_factory = _LegacyAuthDBSimplifiedConnector


    def __init__(self, **kwargs):
        super(PrepareLegacyAuthDB, self).__init__(**kwargs)
        self.old_db_connector = self.db_connector_factory(
            settings=self.settings,
            config_section=self.config_section)

    @property
    def old_db_engine(self):
        return self.old_db_connector.engine

    @staticmethod
    def iter_sqla_tables(metadata):
        for sqla_table in metadata.sorted_tables:
            assert isinstance(sqla_table, Table)
            if sqla_table.name != sqla_table.key:
                raise NotImplementedError(
                    'differing Table.name and Table.key not supported '
                    '(got: name={!a} and key={!a})'.format(
                        sqla_table.name,
                        sqla_table.key))
            yield sqla_table

    def cleanup(self):
        try:
            self.old_db_connector.dispose_engine()
        finally:
            super(PrepareLegacyAuthDB, self).cleanup()


    def run(self):
        error_code = self.verify_old_db_schema()
        if error_code:
            return error_code
        self.update_old_db_schema()
        records_from_old_db = list(self.generate_records_from_old_db())
        if self.should_drop_and_recreate():
            with self.secondary_db_engine() as secondary_db_engine:
                self.drop_db(secondary_db_engine)
                self.create_db(secondary_db_engine)
            self.create_tables_in_new_db()
            self.insert_into_new_db(records_from_old_db)
            return 0
        self.msg_error('The main goal of the script has not been achieved.')
        return 1


    def verify_old_db_schema(self):
        self.msg('Examining the existing auth database schema...')
        expected = self._get_tabname_to_colnames(legacy_models.Base.metadata)
        reflected = self._get_reflected_tabname_to_colnames()
        self._inform_about_missing_tables(expected, reflected)
        self._warn_about_excessive_tables(expected, reflected)
        self._warn_about_prepared_marker(reflected)
        self._warn_about_alembic_version(reflected)
        error_code = self._error_if_excessive_or_missing_columns(expected, reflected)
        return error_code

    def _get_tabname_to_colnames(self, metadata):
        return {
            sqla_table.name: {
                sql_column.name
                for sql_column in sqla_table.columns}
            for sqla_table in self.iter_sqla_tables(metadata)}

    def _get_reflected_tabname_to_colnames(self):
        reflected_meta = MetaData()
        with self.suppressed_stderr():  # Let's get rid of irrelevant warnings...
            reflected_meta.reflect(bind=self.old_db_engine)
        return self._get_tabname_to_colnames(reflected_meta)

    def _inform_about_missing_tables(self, expected, reflected):
        missing = expected.keys() - reflected.keys()
        if missing:
            self.msg(
                'Note: missing tables in the existing auth database '
                '(to be added automatically): {}.'.format(
                    ', '.join(map(ascii, sorted(map(str, missing))))))

    def _warn_about_excessive_tables(self, expected, reflected):
        excessive = reflected.keys() - expected.keys()
        if excessive:
            self.msg_warn(
                'Excessive tables found in the existing auth database '
                '(BEWARE: any data that are stored in them will be '
                'lost!): {}.'.format(
                    ', '.join(map(ascii, sorted(map(str, excessive))))))

    def _warn_about_prepared_marker(self, reflected):
        if self.LEGACY_AUTH_DB_PREPARED_MARKER_TABLE_NAME in reflected:
            self.msg_warn(
                'It seems that the existing auth database had already '
                'been prepared with this script.  So, maybe, doing '
                'that again is not necessary?')

    def _warn_about_alembic_version(self, reflected):
        if self._any_alembic_version_present(reflected):
            self.msg_warn(
                'This script is intended to prepare the legacy auth '
                'database schema so that it can start to be maintained '
                'with the Alembic toolset.  But it seems that the '
                'schema of the existing auth database is already being '
                'maintained with Alembic!  If that is true, running '
                'this (potentially disruptive!) script is, most '
                'probably, completely unnecessary!')

    def _any_alembic_version_present(self, reflected):
        if 'alembic_version' in reflected:
            with self.old_db_engine.begin() as connection:
                return bool(list(connection.execute('SELECT * from alembic_version')))
        return False

    def _error_if_excessive_or_missing_columns(self, expected, reflected):
        common = expected.keys() & reflected.keys()
        err = False
        for tabname in common:
            excessive_colnames = reflected[tabname] - expected[tabname]
            if excessive_colnames:
                err = True
                self.msg_error(
                    'Excessive columns in the `{}` table of the '
                    'existing auth database: {}.'.format(
                        tabname,
                        ', '.join(map(ascii, sorted(map(str, excessive_colnames))))))
            missing_colnames = expected[tabname] - reflected[tabname]
            if missing_colnames:
                err = True
                self.msg_error(
                    'Missing columns in the `{}` table of the '
                    'existing auth database: {}.'.format(
                        tabname,
                        ', '.join(map(ascii, sorted(map(str, missing_colnames))))))
        if err:
            self.msg_error(
                'Exiting without changing anything - because of the '
                'error(s) printed above; apparently, the schema of the '
                'existing auth database is not compatible with this '
                'script.  Most probably, the schema is either too old '
                '(i.e., older than what was defined in the code published '
                'in the https://github.com/CERT-Polska/n6.git repository '
                'with the `04d0ff7d12cf46e912575aee37d705224be4378a` '
                'commit), or too new.')
            return 1
        return 0


    def update_old_db_schema(self):
        self.msg('Updating the existing auth database schema...')
        legacy_models.Base.metadata.create_all(self.old_db_engine)


    def generate_records_from_old_db(self):
        self.msg('Collecting records from the existing auth database...')
        total_count = 0
        with self.old_db_engine.begin() as connection:
            for sqla_table in self.iter_sqla_tables(legacy_models.Base.metadata):
                count = 0
                for row in connection.execute(sqla_table.select()):
                    assert isinstance(row, RowProxy)
                    attr_dict = dict(row.items())
                    yield sqla_table.name, attr_dict
                    total_count += 1
                    count += 1
                if count > 0:
                    self.msg_sub('{!a}: {} record(s) collected.'.format(
                        str(sqla_table.name),
                        count))
        self.msg_sub('Total: {} record(s) collected.'.format(total_count))
        if total_count == 0:
            self.msg_warn(
                'The existing auth database seems to contain no '
                'records! (at least when it comes to the tables '
                'we are interested in)')


    def should_drop_and_recreate(self):
        if self.yes_or_no(
                caution=(
                    'You should have made a backup of the existing (old) '
                    'auth database! (see: `N6Lib/n6lib/auth_db/alembic/'
                    'README.md`)  Note that this script acts in an unsafe, '
                    'non-transactional, potentially disruptive way: first '
                    'it removes the existing database and only then it '
                    'tries to create and populate a new one.\n\nAlso, '
                    'note the warnings printed above (if any).'),
                question='Are you sure you want to proceed?'):
            return True
        else:
            self.msg('Resigned from the potentially disruptive operations.')
            return False


    def drop_db(self, secondary_db_engine):
        self.msg('Dropping the existing auth database...')
        quoted_db_name = self.db_connector.quote_sql_identifier(self.db_name)
        with secondary_db_engine.connect() as connection:
            connection.execute('DROP DATABASE {}'.format(quoted_db_name))


    def create_db(self, secondary_db_engine):
        self.msg('Creating the new auth database...')
        quoted_db_name = self.db_connector.quote_sql_identifier(self.db_name)
        sql_raw = ('CREATE DATABASE {} '
                   'CHARACTER SET :charset COLLATE :collate'.format(quoted_db_name))
        sql = sqlalchemy.text(sql_raw).bindparams(
            charset=(MYSQL_CHARSET),
            collate=(MYSQL_COLLATE))
        with secondary_db_engine.connect() as connection:
            connection.execute(sql)


    def create_tables_in_new_db(self):
        self.msg('Creating the new auth database\'s tables...')
        self._ensure_prepared_marker_table_in_metadata()
        legacy_models.Base.metadata.create_all(self.db_engine)

    def _ensure_prepared_marker_table_in_metadata(self):
        try:
            Table(self.LEGACY_AUTH_DB_PREPARED_MARKER_TABLE_NAME,
                  legacy_models.Base.metadata,
                  Column('id', Integer, primary_key=True),
                  **legacy_models.mysql_opts())
        except InvalidRequestError as exc:
            if 'already defined' in str(exc):
                return
            raise


    def insert_into_new_db(self, records_from_old_db):
        self.msg('Inserting the previously collected records into the new auth database...')
        tabname_to_sqla_table = {
            sqla_table.name: sqla_table
            for sqla_table in self.iter_sqla_tables(legacy_models.Base.metadata)}
        insert_count = 0
        memo = self._make_inserts_memo()
        with self.db_engine.begin() as connection:
            for tabname, attr_dict in records_from_old_db:
                sqla_table = tabname_to_sqla_table[tabname]
                for rel_attr_dict in self._generate_relevant_attr_dicts(tabname, attr_dict, memo):
                    connection.execute(sqla_table.insert(), rel_attr_dict)
                    insert_count += 1
        self.msg_sub('{} records inserted.'.format(insert_count))

    def _make_inserts_memo(self):
        return PlainNamespace(
            already_inserted_ca_labels=set(),
            parent_ca_label_to_pending_attr_dicts=collections.defaultdict(list),
        )

    def _generate_relevant_attr_dicts(self, tabname, attr_dict, memo):
        if tabname == legacy_models.CACert.__tablename__:
            # CACert is specific: insertions must be ordered in such a
            # way that parent CAs appear always before their children
            # (otherwise `IntegrityError` would be raised).
            parent_ca_label = attr_dict.get('parent_ca_label')
            if self._can_ca_cert_be_inserted_now(parent_ca_label, memo):
                for rel_attr_dict in self._generate_relevant_ca_cert_attr_dicts(attr_dict, memo):
                    yield rel_attr_dict
            else:
                memo.parent_ca_label_to_pending_attr_dicts[parent_ca_label].append(attr_dict)
        else:
            yield attr_dict

    def _can_ca_cert_be_inserted_now(self, parent_ca_label, memo):
        return (parent_ca_label in memo.already_inserted_ca_labels or
                parent_ca_label is None)

    def _generate_relevant_ca_cert_attr_dicts(self, attr_dict, memo):
        own_ca_label = attr_dict['ca_label']
        assert own_ca_label not in memo.already_inserted_ca_labels
        yield attr_dict
        memo.already_inserted_ca_labels.add(own_ca_label)
        for child_attr_dict in memo.parent_ca_label_to_pending_attr_dicts[own_ca_label]:
            for rel_attr_dict in self._generate_relevant_ca_cert_attr_dicts(child_attr_dict, memo):
                yield rel_attr_dict



def prepare_legacy_auth_db_for_alembic():
    PrepareLegacyAuthDB.run_from_commandline(sys.argv)

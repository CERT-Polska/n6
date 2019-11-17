# Copyright (c) 2013-2019 NASK. All rights reserved.

# For some code in this module:
# Copyright (C) 2005-2019 the SQLAlchemy authors and contributors
# (For more information -- see comments...)

import collections

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.pool
from sqlalchemy.engine.url import URL, make_url

from n6lib.auth_db import MYSQL_CHARSET
from n6lib.common_helpers import update_mapping_recursively
from n6lib.config import ConfigMixin



class SQLAuthDBConfigMixin(ConfigMixin):

    SUPPORTED_URL_PREFIXES = (
        'mysql+mysqldb:',
        'mysql:',  # `mysqldb` is the default driver for the `mysql` dialect
    )

    config_spec_pattern = '''
        [{config_section}]

        # connection URL, e.g.: mysql+mysqldb://n6:somepassword@localhost/n6
        # it must start with `mysql+mysqldb:` (or just `mysql:`) because other
        # dialects/drivers are not supported
        url

        # to use SSL the following options must be specified as file paths
        ssl_cacert = none
        ssl_cert = none
        ssl_key = none


        [{config_section_session_variables}]

        # all MySQL variables specified within this section will be set by
        # executing "SET SESSION <var1> = <val1>, SESSION <var2> = <val2>, ..."
        # (without any escaping!)

        # should be significantly greater than `pool_recycle` defined below
        wait_timeout = 7200
        ...


        [{config_section_connection_pool}]

        # (see: SQLAlchemy docs)
        pool_recycle = 3600 :: int
        pool_timeout = 20 :: int
        pool_size = 15 :: int
        max_overflow = 12 :: int
    '''

    default_config_section = 'auth_db'

    # All MySQL variables specified by the following attribute will
    # be set by executing "SET SESSION <var1> = <val1>, SESSION <var2>
    # = <val2>, ..." (without any escaping!).
    #
    # What is important to know is that:
    #
    # * the attribute (as a whole) can be overridden in subclasses;
    #
    # * at runtime, individual variables it defines can be overridden
    #   in the config (see: the `{config_section_session_variables}`
    #   section in the above `config_spec_pattern`);
    #
    # * caution is needed when doing any of the above (i.e., overriding
    #   the attribute or overriding individual variables it defines...)
    #   as the variables it defines are crucial for proper functioning
    #   of the Auth DB.
    constant_session_variables = (
        # each item is a tuple:
        # (<variable name (str)>, <variable value (str)>)

        # see: https://mariadb.com/kb/en/library/sql-mode/
        ('sql_mode', ("'STRICT_ALL_TABLES"  # <- similar, but rather more strict, than default
                                            #    for >= MariaDB 10.2.4 (`STRICT_TRANS_TABLES`)
                      ",ERROR_FOR_DIVISION_BY_ZERO"  # <- default restriction for >= MariaDB 10.2.4
                      ",NO_AUTO_CREATE_USER"         # <- default restriction for >= MariaDB 10.1.7
                      ",NO_ENGINE_SUBSTITUTION"      # <- default restriction for >= MariaDB 10.1.7
                      ",NO_ZERO_DATE"                # <- non-default restriction
                      ",NO_ZERO_IN_DATE"             # <- non-default restriction
                      "'")),
    )

    isolation_level = 'SERIALIZABLE'


    def __init__(self, settings=None, config_section=None):
        self.set_config(settings, config_section)
        self.configure_db()

    def set_config(self, settings, config_section):
        self.set_config_section_names(config_section)
        self.config = self.get_config_full(
            settings,
            config_section=self.config_section,
            config_section_session_variables=self.config_section_session_variables,
            config_section_connection_pool=self.config_section_connection_pool)

    def set_config_section_names(self, config_section):
        if config_section is None:
            config_section = self.default_config_section
        self.config_section = config_section
        self.config_section_session_variables = config_section + '_session_variables'
        self.config_section_connection_pool = config_section + '_connection_pool'

    def configure_db(self):
        self.engine = self.make_db_engine()
        self._dialect_specific_quote = self._make_dialect_specific_quote()
        self._install_session_variables_setter()
        self._install_reconnector()

    def make_db_engine(self, url_overwrite_attrs=None):
        url = self._get_db_url(url_overwrite_attrs)
        create_engine_kwargs = self._get_create_engine_kwargs()
        return sqlalchemy.create_engine(url, **create_engine_kwargs)

    def get_ssl_related_create_engine_kwargs(self):
        opts = self.config[self.config_section]
        return (
            dict(
                connect_args=dict(
                    ssl=dict(
                        ca=opts['ssl_cacert'],
                        cert=opts['ssl_cert'],
                        key=opts['ssl_key'],
                    ),
                ),
            )
            if opts['ssl_key'].lower() != 'none'
            else {})

    # utility method (may be useful in subclasses)
    def quote_sql_identifier(self, sql_identifier):
        return self._dialect_specific_quote(sql_identifier)


    #
    # Private helpers

    def _make_dialect_specific_quote(self):
        dialect = self.engine.dialect
        return dialect.preparer(dialect).quote

    def _get_db_url(self, url_overwrite_attrs):
        url_string = self._get_db_url_string()
        url = self._make_db_url(url_string, url_overwrite_attrs)
        assert isinstance(url, URL)
        return url

    def _get_db_url_string(self):
        url_string = self.config[self.config_section]['url']
        if not url_string.startswith(self.SUPPORTED_URL_PREFIXES):
            raise ValueError(
                'database URL {!r} specifies unsupported '
                'dialect+driver'.format(url_string))
        return url_string

    def _make_db_url(self, url_string, url_overwrite_attrs):
        url = make_url(url_string)
        assert isinstance(url, URL)
        if url_overwrite_attrs is not None:
            for attr_name, attr_value in url_overwrite_attrs.iteritems():
                setattr(url, attr_name, attr_value)
        return url

    def _get_create_engine_kwargs(self):
        create_engine_kwargs = dict(isolation_level=self.isolation_level,
                                    connect_args=dict(use_unicode=0,
                                                      charset=MYSQL_CHARSET),
                                    convert_unicode=True,
                                    encoding='utf-8')
        update_mapping_recursively(create_engine_kwargs,
                                   self.get_ssl_related_create_engine_kwargs(),
                                   self.config[self.config_section_connection_pool])
        return create_engine_kwargs

    def _install_session_variables_setter(self):
        session_variables = collections.OrderedDict(self.constant_session_variables)
        session_variables.update(
            sorted(self.config[self.config_section_session_variables].iteritems()))

        setter_sql = 'SET ' + ' , '.join(
            'SESSION {} = {}'.format(name, value)
            for name, value in session_variables.iteritems())

        @sqlalchemy.event.listens_for(self.engine, 'connect')
        def set_session_variable(dbapi_connection, connection_record):
            """
            Execute "SET SESSION <var1> = <val1>, ..." to set the
            variables specified by the `constant_session_variables`
            attribute and in the appropriate configuration section.

            To be called automatically whenever a new low-level
            connection to the database is established.

            WARNING: for simplicity, the variable names and values are
            inserted "as is", *without* any escaping -- we assume we
            can treat config options (and, even more so, Python-level
            object attributes, of course) as a *trusted* source of
            data.
            """
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(setter_sql)
                cursor.execute('COMMIT')
            finally:
                cursor.close()

    # TODO after SQLAlchemy upgrade to 1.2+:
    # * add `pool_pre_ping = true :: bool` to config
    # * remove this method and the copyright note concerning this method...
    def _install_reconnector(self):
        # copied from:
        # http://docs.sqlalchemy.org/en/rel_0_9/core/pooling.html#disconnect-handling-pessimistic
        # and slightly adjusted
        @sqlalchemy.event.listens_for(sqlalchemy.pool.Pool, "checkout")
        def ping_connection(dbapi_connection, connection_record, connection_proxy):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("SELECT 1")
            except Exception:
                # dispose the whole pool instead of invalidating one at a time
                connection_proxy._pool.dispose()
                # pool will try connecting again up to three times before giving up
                raise sqlalchemy.exc.DisconnectionError()
            cursor.close()


class SimpleSQLAuthDBConnector(SQLAuthDBConfigMixin):

    def __init__(self,
                 db_host=None,
                 db_name=None,
                 db_user=None,
                 db_password=None,
                 settings=None,
                 config_section=None):
        config_section = self.default_config_section if config_section is None else config_section
        if self._verify_args_for_connection(db_host, db_name, db_user, db_password):
            option_key = '{}.url'.format(config_section)
            option_val = 'mysql+mysqldb://{user}:{password}@{host}/{name}'.format(
                user=db_user,
                password=db_password,
                host=db_host,
                name=db_name)
            if settings is None:
                settings = {
                    option_key: option_val,
                }
            else:
                # keep a config from `settings` (it is most likely
                # a Pyramid-style config dict), but config options
                # made with kwargs should have higher priority
                settings = dict(settings, option_key=option_val)
        super(SimpleSQLAuthDBConnector, self).__init__(settings, config_section)

    @staticmethod
    def _verify_args_for_connection(*args):
        if all(args):
            return True
        if any(args):
            raise TypeError('All arguments defining AuthDB connection options have to '
                            'be passed, or none of them.')
        return False

    def configure_db(self):
        super(SimpleSQLAuthDBConnector, self).configure_db()
        self.db_session_maker = sqlalchemy.orm.sessionmaker(bind=self.engine,
                                                            autocommit=False,
                                                            autoflush=False)
    def __enter__(self):
        session = self.db_session_maker()
        self._db_session = session
        return session

    def __exit__(self, exc_type, exc, tb):
        try:
            try:
                if exc_type is None:
                    self._db_session.commit()
                else:
                    self._db_session.rollback()
            except:
                self._db_session.rollback()
                raise
            finally:
                self._db_session.close()
        finally:
            self._db_session = None

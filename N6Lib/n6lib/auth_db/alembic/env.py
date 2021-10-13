import ast
import logging.config
import os

from alembic import context

from n6lib.auth_db import ALEMBIC_DB_CONFIGURATOR_SETTINGS_DICT_ENVIRON_VAR_NAME
from n6lib.auth_db import models
from n6lib.auth_db.config import SQLAuthDBConfigMixin


# This is the Alembic Config object, which provides access to the
# values within the `alembic.ini` file:
config = context.config

# Let's configure logging:
logging.config.fileConfig(config.config_file_name)

# Other values from `alembic.ini`, defined by the needs of `env.py`,
# can be obtained in the following way:
# my_important_option = config.get_main_option('my_important_option')
# ... etc.


class _AuthDBConfiguratorForAlembicEnv(SQLAuthDBConfigMixin):

    def __init__(self):
        super(_AuthDBConfiguratorForAlembicEnv, self).__init__(settings=self._get_settings())

    def _get_settings(self):
        settings_raw = os.environ.get(ALEMBIC_DB_CONFIGURATOR_SETTINGS_DICT_ENVIRON_VAR_NAME)
        if settings_raw:
            return self._parse_settings(settings_raw)
        return None

    def _parse_settings(self, settings_raw):
        try:
            settings = ast.literal_eval(settings_raw)
            if not isinstance(settings, dict):
                raise ValueError
        except Exception:
            raise ValueError(
                'the value of the {} environment variable, if not empty, '
                'should be formatted as a Python dict that consists only '
                'of keys and values formatted as Python literals (got: '
                '{!a})'.format(
                    ALEMBIC_DB_CONFIGURATOR_SETTINGS_DICT_ENVIRON_VAR_NAME,
                    settings_raw))
        return settings


def run_migrations_offline():
    """
    Run migrations in the 'offline' mode.

    Calls to context.execute() here emit the
    given string to the script output.
    """
    db_configurator = _AuthDBConfiguratorForAlembicEnv()
    context.configure(url=db_configurator.get_db_url_string(),
                      target_metadata=models.Base.metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Run migrations in the 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    db_configurator = _AuthDBConfiguratorForAlembicEnv()
    with db_configurator.engine.connect() as connection:
        context.configure(connection=connection,
                          target_metadata=models.Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

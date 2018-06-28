# Copyright (c) 2013-2018 NASK. All rights reserved.

import argparse
import textwrap

from n6lib.auth_db.models import Base
from n6lib.auth_db.config import SQLAuthDBConfigMixin


class InitializeAuthDB(SQLAuthDBConfigMixin):

    """
    Create necessary auth database tables.
    """

    @classmethod
    def run_from_commandline(cls):
        parser = argparse.ArgumentParser(description=textwrap.dedent(cls.__doc__))
        parser.add_argument('-D', '--do-drop-tables', action='store_true',
                            help='first, drop all tables (!) from the auth database')
        arguments = parser.parse_args()
        cls(**vars(arguments)).run()

    def __init__(self, do_drop_tables=False, **kwargs):
        self._do_drop_tables = do_drop_tables
        super(InitializeAuthDB, self).__init__(**kwargs)

    def run(self):
        if self._do_drop_tables:
            self.drop_tables()
        self.create_tables()
        print '* Done.'

    def drop_tables(self):
        print '* Dropping all auth database tables first...'
        Base.metadata.drop_all(self.engine)

    def create_tables(self):
        print '* Creating new auth database tables...'
        Base.metadata.create_all(self.engine)


def main():
    InitializeAuthDB.run_from_commandline()


if __name__ == '__main__':
    main()

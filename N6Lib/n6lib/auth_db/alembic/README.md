# Auth DB schema migrations with Alembic -- the basics

## Backup first!

Make sure to **make a backup** of your Auth DB before running any
migrations -- especially because:

* always something may go wrong;

* some migrations (e.g., the '9327d279a219' one) drop obsolete tables,
  removing any data they contain without any confirmation prompts!

Assuming you have the `mariadb-client` Debian package installed, you
can make a backup of the auth database with the command:

```bash
$ mysqldump -u HERE_MARIADB_USERNAME -p -h HERE_MARIADB_HOST \
            --default-character-set utf8mb4 \
            --add-drop-database \
            --databases HERE_AUTH_DATABASE_NAME \
            > HERE_BACKUP_FILENAME
```

Later, you can restore the database from the backup (dropping the
existing database) by running the command:

```bash
$ mysql -u HERE_MARIADB_USERNAME -p -h HERE_MARIADB_HOST \
         --default-character-set utf8mb4 \
         < HERE_BACKUP_FILENAME
```


## Migration to the newest Alembic revision (applying all pending migrations)

**Prerequisites:**

* appropriate configuration of your Auth DB is placed in some `*.conf`
  file(s) in the `~/.n6/` and/or `/etc/n6/` directory (for a config
  template, see the file `N6Core/n6/data/conf/09_auth_db.conf`);

* a Python *virtualenv* containing your `n6lib` installation is
  activated in the shell that is to be used to run the migration
  commands;

* a backup of your Auth DB has been done, unless you do not care about
  the data stored in it (see the previous section).

**The commands** to be run:

```bash
$ cd N6Lib/n6lib/auth_db  # important!
$ alembic upgrade head
```

That's all!

Note that the `alembic upgrade head` command is idempotent, i.e., you
can safely repeat it without changing anything (until a new Alembic
version file is placed in the `N6Lib/n6lib/auth_db/alembic/versions`
directory).

For **other Alembic commands** and related information -- see:

* `$ alembic --help`
* `$ alembic HERE_PARTICULAR_COMMAND --help`
* https://alembic.sqlalchemy.org/


## Preparing a legacy Auth DB for Alembic migrations

If the schema of your Auth DB is old enough it may be necessary to
prepare the database before you will be able to run successfully any
Alembic migrations.  The `n6prepare_legacy_auth_db_for_alembic` script
is the tool that serves this purpose.

**Prerequisites** are the same as for migration to the newest Alembic
revision (see the previous section).

**The command** to be run (**caution:** please read carefully any
warnings printed by the script, *before* answering with `yes` to the
script's confirmation prompt):

```bash
$ n6prepare_legacy_auth_db_for_alembic
```

See also:

```bash
$ n6prepare_legacy_auth_db_for_alembic --help
```

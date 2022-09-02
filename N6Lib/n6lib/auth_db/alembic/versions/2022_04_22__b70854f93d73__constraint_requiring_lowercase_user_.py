"""Constraint requiring lowercase User.login added

Revision ID: b70854f93d73
Revises: 4f5d01396b61
Create Date: 2022-04-22 15:24:30.137651+00:00

"""
import logging
import operator
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


# revision identifiers, used by Alembic.
revision = 'b70854f93d73'
down_revision = '4f5d01396b61'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    try:
        with connection.begin():
            all_logins = _get_all_logins_from_db(connection)
            _verify_all_logins_are_pure_ascii(all_logins)
            old_to_new = _adjust_logins_in_db(connection, all_logins)
    except _LoginDataError:
        sys.exit(
            '\n*** EXITING WITH ERROR ***\nSee the description in the log.'
            '\nTL;DR: NO CHANGES have been made in the database. Before '
            'trying again you need to take care (manually) of some user '
            'login(s)...')

    _warn_about_changed_logins_if_any(old_to_new)

    op.create_check_constraint(
        op.f('ck__u_04f899__l_428821'),
        'user',
        'login = LOWER(login)')


def downgrade():
    op.drop_constraint(
        op.f('ck__u_04f899__l_428821'),
        'user', type_='check')


_LOGGER = logging.getLogger(__name__)

class _LoginDataError(Exception):
    pass

def _get_all_logins_from_db(connection):
    select_sql = sa.text('SELECT login FROM user')
    return sorted(login for [login] in connection.execute(select_sql).fetchall())

def _verify_all_logins_are_pure_ascii(all_logins):
    wrong_logins = [login for login in all_logins if not login.isascii()]
    if wrong_logins:
        wrong_logins_listing = '\n'.join(map(ascii, wrong_logins))
        _LOGGER.error(
            f'%s non-pure-ASCII user login(s) (i.e., value(s) in '
            f'the `login` column of the `user` table) found:\n%s',
            len(wrong_logins),
            wrong_logins_listing)
        raise _LoginDataError

def _adjust_logins_in_db(connection, all_logins):
    old_to_new = {}
    update_sql = sa.text('UPDATE user SET login = :new_login WHERE login = :old_login')
    for login in all_logins:
        new_login = login.lower()
        if new_login != login:
            try:
                connection.execute(
                    update_sql,
                    new_login=new_login,
                    old_login=login)
            except IntegrityError as exc:
                _LOGGER.error(
                    f'Cannot change user login from %a to %a because '
                    f'of a database integrity error! (most probably the '
                    f'change would violate the uniqueness constraint on '
                    f'the `login` column of the `user` table)',
                    login,
                    new_login,
                    exc_info=True)
                raise _LoginDataError from exc
            old_to_new[login] = new_login
    return old_to_new

def _warn_about_changed_logins_if_any(old_to_new):
    if old_to_new:
        changes_listing = '\n'.join(
            f'{old!a} -> {new!a}'
            for old, new in sorted(old_to_new.items(), key=operator.itemgetter(1)))
        _LOGGER.warning(
            '%s user login(s) (i.e., value(s) in the `login` column '
            'of the `user` table) changed to lowercase-only ones:\n%s',
            len(old_to_new),
            changes_listing)

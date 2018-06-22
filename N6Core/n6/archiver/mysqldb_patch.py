# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.
#
# Copyright (c) 2014 the author(s) of the MySQLdb1 library
# (GPL-licensed), see below... All rights reserved.

"""
This module patches a few MySQLdb library functions -- to enhance
warnings (adding information about the query and its args).

Import this module before the importing sqlalchemy.
"""

### XXX: it would be nice to check if it is possible to patch smaller
### portions of the code to obtain the same effect...

### FIXME: fix indentation in this module


import sys

from MySQLdb import cursors

from n6lib.log_helpers import get_logger
from n6lib.common_helpers import provide_surrogateescape

provide_surrogateescape()
LOGGER = get_logger(__name__)


warning_standard = False
warning_details_to_logs = True

insert_values = cursors.insert_values
ProgrammingError = cursors.ProgrammingError


# modified MySQLdb.cursors.BaseCursor.execute() (changes marked with `###`)
def execute(self, query, args=None):

        """Execute a query.

        query -- string, query to execute on server
        args -- optional sequence or mapping, parameters to use with query.

        Note: If args is a sequence, then %s must be used as the
        parameter placeholder in the query. If a mapping is used,
        %(key)s must be used as the placeholder.

        Returns long integer rows affected, if any

        """
        del self.messages[:]
        db = self._get_db()
        if isinstance(query, unicode):
            query = query.encode(db.unicode_literal.charset)
        if args is not None:
            if isinstance(args, dict):
                query = query % dict((key, db.literal(item))
                                     for key, item in args.iteritems())
            else:
                query = query % tuple([db.literal(item) for item in args])
        try:
            r = None
            r = self._query(query)
        except TypeError, m:
            if m.args[0] in ("not enough arguments for format string",
                             "not all arguments converted"):
                self.messages.append((ProgrammingError, m.args[0]))
                self.errorhandler(self, ProgrammingError, m.args[0])
            else:
                self.messages.append((TypeError, m))
                self.errorhandler(self, TypeError, m)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            exc, value, tb = sys.exc_info()
            del tb
            self.messages.append((exc, value))
            self.errorhandler(self, exc, value)
        self._executed = query
        ### orig: if not self._defer_warnings: self._warning_check()
        if not self._defer_warnings: self._warning_check(query, args=args)
        return r


# modified MySQLdb.cursors.BaseCursor.executemany() (changes marked with `###`)
def executemany(self, query, args):

        """Execute a multi-row query.

        query -- string, query to execute on server

        args

            Sequence of sequences or mappings, parameters to use with
            query.

        Returns long integer rows affected, if any.

        This method improves performance on multiple-row INSERT and
        REPLACE. Otherwise it is equivalent to looping over args with
        execute().

        """
        del self.messages[:]
        db = self._get_db()
        if not args: return
        if isinstance(query, unicode):
            query = query.encode(db.unicode_literal.charset)
        m = insert_values.search(query)
        if not m:
            r = 0
            for a in args:
                r = r + self.execute(query, a)
            return r
        p = m.start(1)
        e = m.end(1)
        qv = m.group(1)
        try:
            q = []
            for a in args:
                if isinstance(a, dict):
                    q.append(qv % dict((key, db.literal(item))
                                       for key, item in a.iteritems()))
                else:
                    q.append(qv % tuple([db.literal(item) for item in a]))
        except TypeError, msg:
            if msg.args[0] in ("not enough arguments for format string",
                               "not all arguments converted"):
                self.errorhandler(self, ProgrammingError, msg.args[0])
            else:
                self.errorhandler(self, TypeError, msg)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            exc, value, tb = sys.exc_info()
            del tb
            self.errorhandler(self, exc, value)
        r = self._query('\n'.join([query[:p], ',\n'.join(q), query[e:]]))
        ### orig: if not self._defer_warnings: self._warning_check()
        if not self._defer_warnings: self._warning_check(query, args=args)
        return r

# modified MySQLdb.cursors.BaseCursor._warning_check() (changes marked with `###`)
def _warning_check(self, query=None, args=None):
    from warnings import warn
    if self._warnings:
        warnings = self._get_db().show_warnings()
        if warnings:
            # This is done in two loops in case
            # Warnings are set to raise exceptions.
            for w in warnings:
                self.messages.append((self.Warning, w))
            for w in warnings:
                ### orig: warn(w[-1], self.Warning, 3)
                if warning_standard:
                    warn(w[-1], self.Warning, 3)
                if warning_details_to_logs:
                        LOGGER.warning(
                            '%s, QUERY_SQL: %r, ARGS: %r',
                            w[-1].encode('utf-8'), query, args)
        elif self._info:
            self.messages.append((self.Warning, self._info))
            warn(self._info, self.Warning, 3)


cursors.BaseCursor.execute = execute
cursors.BaseCursor.executemany = executemany
cursors.BaseCursor._warning_check = _warning_check

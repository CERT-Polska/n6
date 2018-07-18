# Copyright (c) 2013-2018 NASK. All rights reserved.

from collections import MutableSequence

from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import String

from n6adminpanel.tools import (
    get_exception_message,
    unescape_html_attr,
)


def get_patched_get_form(original_func):
    """
    Patch `get_form()` function, so `hidden_pk` keyword
    argument is always set to False.

    Columns with "PRIMARY KEY" constraints are represented
    as non-editable hidden input elements, not as editable
    forms, when argument `hidden_pk` is True.
    """
    def _is_pk_string(model):
        inspection = inspect(model)
        main_pk = inspection.primary_key[0]
        return isinstance(main_pk.type, String)

    def patched_func(model, converter, **kwargs):
        if _is_pk_string(model):
            kwargs['hidden_pk'] = False
        return original_func(model, converter, **kwargs)
    return patched_func


def patched_populate_obj(self, obj, name):
    """
    Patch original method, in order to:
        * Prevent Flask-admin from populating fields with NoneType.
        * Append a list of validation errors, if a models' validator
          raised an exception (not Flask-Admin's validator), to
          highlight invalid field in application's view.
    """
    if self.data is not None:
        try:
            setattr(obj, name, self.data)
        except Exception as exc:
            invalid_field = getattr(exc, 'invalid_field', None)
            if invalid_field and isinstance(self.errors, MutableSequence):
                exc_message = get_exception_message(exc)
                if exc_message is not None:
                    self.errors.append(exc_message)
                else:
                    self.errors.append(u'Failed to create record.')
            raise


def _get_action_meth_wrapper(original_meth):
    def wrapper(ids):
        new_ids = [unescape_html_attr(x) for x in ids]
        return original_meth(new_ids)
    return wrapper


def get_patched_init_actions(original_meth):
    """
    Get a patched flask_admin.actions.ActionsMixin.init_actions().

    Names of records to apply an action to have some of their
    characters escaped inside a form (dots and commas). It causes
    a bug, which causes these records to be ignored. They have to
    be unescaped first. A returned patched method overwrites
    an `_actions_data` dict, which maps action names to corresponding
    methods. Action methods in the overwritten dict are wrapped
    by the function, which reverts their escaped arguments.

    The patch applies to "action" methods globally inside the app.
    """
    def patched_meth(self):
        original_meth(self)
        new_actions_data = {key: (_get_action_meth_wrapper(val[0]), val[1], val[2]) for
                            key, val in self._actions_data.iteritems()}
        setattr(self, '_actions_data', new_actions_data)
    return patched_meth

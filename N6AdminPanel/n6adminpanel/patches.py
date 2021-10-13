# Copyright (c) 2018-2021 NASK. All rights reserved.

from collections.abc import MutableSequence

from flask_admin.contrib.sqla import form
from flask_admin.model.fields import InlineModelFormField
from sqlalchemy import inspect
from sqlalchemy.sql.sqltypes import String

from n6adminpanel.tools import (
    get_exception_message,
    unescape_html_attr,
)


class _PatchedInlineModelFormField(InlineModelFormField):

    """
    The subclass overrides Flask-Admin's behavior, when populating
    fields of inline models, that omits all types of Primary Key
    fields. It is modified to ignore only 'HiddenField' type of fields.
    """

    hidden_field_type = 'HiddenField'

    def populate_obj(self, obj, name):
        for name, field in self.form._fields.items():
            if field.type != self.hidden_field_type:
                field.populate_obj(obj, name)


class _PatchedInlineFieldListType(form.InlineModelFormList):

    form_field_type = _PatchedInlineModelFormField


class PatchedInlineModelConverter(form.InlineModelConverter):

    """
    The subclass of the `InlineModelConverter` should be used as
    an `inline_model_form_converter` in model views, that have
    some of their fields displayed as "inline models" with
    non-integer Primary Keys, that need  to be filled.
    """

    inline_field_list_type = _PatchedInlineFieldListType


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
    A patched version of flask_admin's Field.populate_obj().

    This patch is needed to:

    * treat an empty or whitespace-only string value as NULL (for
      pragmatic reasons: in many cases accepting such a string,
      typically being a result of a GUI user's mistake, would be just
      confusing; at the same time, we do not see any cases when
      accepting such strings could be useful);

    * append a list of validation errors -- if an n6-specific model's
      validator (not a Flask-Admin validator) raised an exception -- to
      highlight invalid fields values in the GUI view.

    """

    # treating empty or whitespace-only text as NULL
    to_be_set = (None if (isinstance(self.data, str)
                          and not self.data.strip())
                 else self.data)

    # handling n6-specific model-level validation errors
    try:
        setattr(obj, name, to_be_set)
    except Exception as exc:
        invalid_field = getattr(exc, 'invalid_field', None)
        if invalid_field and isinstance(self.errors, MutableSequence):
            exc_message = get_exception_message(exc)
            if exc_message is not None:
                self.errors.append(exc_message)
            else:
                self.errors.append(u'Failed to create/update record.')
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
                            key, val in self._actions_data.items()}
        setattr(self, '_actions_data', new_actions_data)
    return patched_meth

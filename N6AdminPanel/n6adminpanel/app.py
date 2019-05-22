# Copyright (c) 2013-2018 NASK. All rights reserved.

from flask import Flask
from flask_admin import (
    Admin,
    AdminIndexView,
    expose,
)
from flask_admin._compat import iteritems
from flask_admin.actions import ActionsMixin
from flask_admin.contrib.sqla import (
    form,
    ModelView,
)
from flask_admin.contrib.sqla.form import InlineModelConverter
from flask_admin.form import (
    TimeField,
    rules,
)
from flask_admin.form.widgets import TimePickerWidget
from flask_admin.model.form import (
    InlineFormAdmin,
    converts,
)
from flask_admin.model.fields import InlineModelFormField
from sqlalchemy import inspect
from wtforms import PasswordField
from wtforms.fields import Field
from wtforms.widgets import PasswordInput

from n6adminpanel.patches import (
    get_patched_get_form,
    get_patched_init_actions,
    patched_populate_obj,
)
from n6lib.auth_db.config import SQLAuthDBConfigMixin
from n6lib.auth_db.models import (
    CACert,
    Cert,
    #Component,
    CriteriaASN,
    CriteriaCC,
    CriteriaContainer,
    CriteriaIPNetwork,
    CriteriaName,
    EMailNotificationAddress,
    EMailNotificationTime,
    InsideFilterASN,
    InsideFilterCC,
    InsideFilterFQDN,
    InsideFilterIPNetwork,
    InsideFilterURL,
    Org,
    OrgGroup,
    RequestCase,
    Source,
    Subsource,
    SubsourceGroup,
    SystemGroup,
    User,
    db_session,
)
from n6lib.config import ConfigMixin
from n6lib.log_helpers import logging_configured


class N6ModelView(ModelView):

    """
    Base n6 view.

    Used to define global parameters in all views.
    """

    can_set_page_size = False
    """
        This property is derived from flask-admin. This property has been
        disabled to use our customized version. If `true` then at `list` view
        will be displayed dropdown with page_size options definied by flask
    """

    can_set_n6_page_size = True
    """
        Custom page size property.
    """

    page_size = None
    """
        Default page size.
        Its tricky to set `no limit` on page size.

        * when `page_size` is class defined number and from dropdown you set
          `page_size = None` or literally option `No limit` then flask
          will switch `page_size` to your here defined number - instead of `None`.

        * when `page_size` is `None` from the start, then option `No Limit` on
          dropdown works as expected.
    """

    list_template = 'list.html'

    @property
    def _template_args(self):
        args = super(N6ModelView, self)._template_args

        custom_args = {
            'can_set_n6_page_size': self.can_set_n6_page_size
        }
        args.update(custom_args)

        return args


class CustomPasswordInput(PasswordInput):

    """
    Subclass of the widget appending a `placeholder` attribute
    to an `input` HTML element.
    """

    def __call__(self, field, **kwargs):
        if field._value():
            kwargs['placeholder'] = 'Edit to change user\'s password.'
        else:
            kwargs['placeholder'] = 'Add password for the user.'
        return super(CustomPasswordInput, self).__call__(field, **kwargs)


class _PasswordFieldHandlerMixin(object):

    form_extra_fields = {
        'password': PasswordField(widget=CustomPasswordInput()),
    }

    def on_model_change(self, form, model, is_created):
        if hasattr(form, 'password') and form.password and form.password.data:
            model.password = model.get_password_hash_or_none(form.password.data)
        elif hasattr(model, 'password'):
            # delete the field from model to avoid overwriting it
            # with an empty value
            del model.password


class PrimaryKeyOnlyFormAdmin(InlineFormAdmin):

    column_display_pk = True

    def _get_form_columns(self, model):
        inspection = inspect(model)
        return [inspection.primary_key[0].name]

    def __init__(self, model, **kwargs):
        self.form_columns = self._get_form_columns(model)
        super(PrimaryKeyOnlyFormAdmin, self).__init__(model, **kwargs)


class InlineMappingFormAdmin(PrimaryKeyOnlyFormAdmin):

    """
    Extended Flask-admin's `InlineFormAdmin` class, that allows
    to define a custom mapping of inline forms inside a view.

    Important: the class has to be used within subclasses of
    the `CustomInlineFormsModelView` class. Otherwise, it will
    not give a desired effect.

    Original class creates only one form from each model listed
    in the `inline_models` attribute. This class overrides the
    behavior, allowing to create more than one inline form
    from a single model.

    Its constructor accepts additional argument - `inline_mapping`,
    which has to be a dict mapping names of model's relationship
    fields to corresponding field names in related models.

    Let us take some example relations (m:n for simplicity):
    ModelOne.rel_with_model_two - ModelTwo.rel_with_model_one
    ModelOne.another_rel_with_model_two - ModelTwo.another_rel_with_model_one
    ModelOne.rel_with_model_three - ModelThree.rel_with_model_one
    Then the `inline_models` attribute of `ModelOne` should be
    created like this:

        inline_models = [
            InlineMappingFormAdmin({
                'rel_with_model_two': 'rel_with_model_one',
                'another_rel_with_model_two': 'another_rel_with_model_one',
                }, ModelTwo),
            InlineMappingFormAdmin({
                'rel_with_model_three': 'rel_with_model_one',
                }, ModelThree),
        ]
    """

    column_display_pk = True

    def __init__(self, inline_mapping, model, **kwargs):
        self.inline_mapping = inline_mapping
        super(InlineMappingFormAdmin, self).__init__(model, **kwargs)


class UserInlineFormAdmin(_PasswordFieldHandlerMixin, InlineFormAdmin):

    column_display_pk = True
    column_descriptions = {
        'login': 'User\'s login (e-mail address)',
    }
    form_columns = ['login', 'password']


class NotificationTimeInlineFormAdmin(InlineFormAdmin):

    form_args = {
        'notification_time': {
            'default_format': '%H:%M',
        },
    }


class SubsourceInlineFormAdmin(InlineFormAdmin):

    column_display_pk = True
    form_columns = [
        'label',
        'inclusion_criteria',
        'exclusion_criteria',
        'subsource_groups',
        'inside_org_groups',
        'threats_org_groups',
        'search_org_groups',
        'inside_orgs',
        'inside_ex_orgs',
        'threats_orgs',
        'threats_ex_orgs',
        'search_orgs',
        'search_ex_orgs',
    ]


class CustomColumnListView(N6ModelView):

    def _set_list_of_form_columns(self, model):
        pk_columns = []
        fk_columns = []
        sorted_columns = []
        inspection = inspect(model)
        for pk in inspection.primary_key:
            pk_columns.append(pk.name)
        fk_constraints = model.__table__.foreign_keys
        for fk in fk_constraints:
            if hasattr(fk, 'constraint') and hasattr(fk.constraint, 'columns'):
                fk_columns.extend([column.name for column in fk.constraint.columns])
        all_columns = inspection.columns.keys()
        regular_columns = list(set(all_columns) - set(fk_columns) - set(pk_columns))
        sorted_columns.extend(pk_columns)
        sorted_columns.extend(regular_columns)
        self.form_columns = sorted_columns
        relationships = inspection.relationships.keys()
        self.form_columns.extend(relationships)

    column_display_pk = True

    def __init__(self, model, session, **kwargs):
        self._set_list_of_form_columns(model)
        super(CustomColumnListView, self).__init__(model, session, **kwargs)


class PatchedInlineModelFormField(InlineModelFormField):

    """
    The subclass overrides Flask-Admin's behavior, when populating
    fields, that omits all types of Primary Key fields. It is modified
    to ignore only 'HiddenField' type of fields.
    """

    hidden_field_type = 'HiddenField'

    def populate_obj(self, obj, name):
        for name, field in iteritems(self.form._fields):
            if field.type != self.hidden_field_type:
                field.populate_obj(obj, name)


class PatchedInlineFieldListType(form.InlineModelFormList):

    form_field_type = PatchedInlineModelFormField


class PatchedInlineModelConverter(InlineModelConverter):

    inline_field_list_type = PatchedInlineFieldListType

    def __init__(self, *args):
        self._calculated_key_pair = None
        self._original_calculate_mapping_meth = self._calculate_mapping_key_pair
        self._calculate_mapping_key_pair = self._new_calculate_mapping_meth
        super(PatchedInlineModelConverter, self).__init__(*args)

    def _new_calculate_mapping_meth(self, *args):
        return self._calculated_key_pair

    def _patched_calculate_mapping_meth(self, model, info):
        if hasattr(info, 'inline_mapping'):
            for forward, reverse in info.inline_mapping.iteritems():
                yield forward, reverse
        else:
            yield self._original_calculate_mapping_meth(model, info)

    def contribute(self, model, form_class, inline_model):
        info = self.get_info(inline_model)
        contribute_result = None
        for calculated_pair in self._patched_calculate_mapping_meth(model, info):
            self._calculated_key_pair = calculated_pair
            contribute_result = super(PatchedInlineModelConverter, self).contribute(model,
                                                                                    form_class,
                                                                                    inline_model)
        return contribute_result


class CustomInlineFormsModelView(N6ModelView):

    """
    This implementation of a `ModelView` class allows to:

        * Populate Primary Key fields, which have to be filled in
          manually (they are not auto-incremented integers and do not
          have default values). Otherwise Flask-Admin omits them,
          raising an error in result.

        * Use an `InlineMappingFormAdmin` class as an inline form
          administration class (by default its superclass,
          `InlineFormAdmin`, is used) inside `inline_models` attribute
          of `ModelView` subclasses. The `InlineMappingFormAdmin`
          accepts a mapping between relation names of two models.
          The mapping forces Flask-Admin to create more than one
          inline form per related model. Check docstring of the
          `InlineMappingFormAdmin` for detailed description.
    """

    inline_model_form_converter = PatchedInlineModelConverter


class ShortTimePickerWidget(TimePickerWidget):

    """
    Widget class extended in order to adjust time format, saved
    into input field by the time picking widget. There is no need
    to save seconds.
    """

    def __call__(self, field, **kwargs):
        kwargs['data-date-format'] = u'HH:mm'
        return super(ShortTimePickerWidget, self).__call__(field, **kwargs)


class ShortTimeField(TimeField):

    widget = ShortTimePickerWidget()


class OrgModelConverter(form.AdminModelConverter):

    @converts('Time')
    def convert_time(self, field_args, **extra):
        return ShortTimeField(**field_args)


class OrgView(CustomInlineFormsModelView):

    # create_modal = True
    # edit_modal = True
    model_form_converter = OrgModelConverter
    column_descriptions = {
        'org_id': 'Organization identifier',
    }
    can_view_details = True
    # essential to display PK column in the "list" view
    column_display_pk = True
    column_searchable_list = ['org_id']
    column_list = [
        'org_id',
        'full_access',
        # 'stream_api_enabled',
        # 'email_notifications_enabled',
        # 'email_notifications_business_days_only',
        'access_to_inside',
        'access_to_threats',
        'access_to_search',
    ]
    form_columns = [
        'org_id',
        'org_groups',
        'users',
        'full_access',
        'access_to_inside',
        # 'inside_max_days_old',
        # 'inside_request_parameters',
        'inside_subsources',
        'inside_ex_subsources',
        'inside_subsource_groups',
        'inside_ex_subsource_groups',
        'access_to_threats',
        # 'threats_max_days_old',
        # 'threats_request_parameters',
        'threats_subsources',
        'threats_ex_subsources',
        'threats_subsource_groups',
        'threats_ex_subsource_groups',
        'access_to_search',
        # 'search_max_days_old',
        # 'search_request_parameters',
        'search_subsources',
        'search_ex_subsources',
        'search_subsource_groups',
        'search_ex_subsource_groups',
        # other options/notifications settings
        # 'stream_api_enabled',
        # 'email_notifications_enabled',
        # 'email_notifications_addresses',
        # 'email_notifications_times',
        # 'email_notifications_language',
        # 'email_notifications_business_days_only',
        'inside_filter_asns',
        'inside_filter_ccs',
        'inside_filter_fqdns',
        'inside_filter_ip_networks',
        'inside_filter_urls',
    ]
    form_rules = [
        rules.Header('Basic options for organization'),
        rules.Field('org_id'),
        rules.Field('org_groups'),
        rules.Field('full_access'),
        rules.Header('Users'),
        rules.Field('users'),
        rules.Header('"Inside" resource'),
        rules.Field('access_to_inside'),
        # rules.Field('inside_max_days_old'),
        # rules.Field('inside_request_parameters'),
        rules.Field('inside_subsources'),
        rules.Field('inside_ex_subsources'),
        rules.Field('inside_subsource_groups'),
        rules.Field('inside_ex_subsource_groups'),
        rules.Header('"Threats" resource'),
        rules.Field('access_to_threats'),
        # rules.Field('threats_max_days_old'),
        # rules.Field('threats_request_parameters'),
        rules.Field('threats_subsources'),
        rules.Field('threats_ex_subsources'),
        rules.Field('threats_subsource_groups'),
        rules.Field('threats_ex_subsource_groups'),
        rules.Header('"Search" resource'),
        rules.Field('access_to_search'),
        # rules.Field('search_max_days_old'),
        # rules.Field('search_request_parameters'),
        rules.Field('search_subsources'),
        rules.Field('search_ex_subsources'),
        rules.Field('search_subsource_groups'),
        rules.Field('search_ex_subsource_groups'),
        # rules.Header('Other options'),
        # rules.Field('stream_api_enabled'),
        # rules.Field('email_notifications_enabled'),
        # rules.Field('email_notifications_addresses'),
        # rules.Field('email_notifications_times'),
        # rules.Field('email_notifications_language'),
        # rules.Field('email_notifications_business_days_only'),
        rules.Header('Criteria for "Inside" (n6filter)'),
        rules.Field('inside_filter_asns'),
        rules.Field('inside_filter_ccs'),
        rules.Field('inside_filter_fqdns'),
        rules.Field('inside_filter_ip_networks'),
        rules.Field('inside_filter_urls'),
    ]
    inline_models = [
        UserInlineFormAdmin(User),
        EMailNotificationAddress,
        NotificationTimeInlineFormAdmin(EMailNotificationTime),
        InsideFilterASN,
        InsideFilterCC,
        InsideFilterFQDN,
        InsideFilterIPNetwork,
        InsideFilterURL,
    ]


class UserView(_PasswordFieldHandlerMixin, N6ModelView):

    column_descriptions = {
        'login': 'User\'s login (e-mail address)',
    }
    column_list = ['login', 'org', 'system_groups']
    form_columns = ['login', 'password', 'org', 'system_groups']
    # column list including certificate-related columns
    # column_list = ['login', 'org', 'system_groups', 'created_certs', 'owned_certs',
    #                'revoked_certs', 'sent_request_cases']


class ComponentView(_PasswordFieldHandlerMixin, N6ModelView):

    column_list = ['login']
    form_columns = ['login', 'password']
    # column list including certificate-related columns
    # column_list = ['login', 'created_certs', 'owned_certs', 'revoked_certs']


class CriteriaContainerView(CustomColumnListView):

    inline_models = [
        CriteriaASN,
        CriteriaCC,
        CriteriaIPNetwork,
        CriteriaName,
    ]


class SourceView(CustomInlineFormsModelView, CustomColumnListView):

    inline_models = [
        SubsourceInlineFormAdmin(Subsource),
    ]


class CustomIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        return self.render('home.html')


class AdminPanel(ConfigMixin):

    config_spec = '''
        [admin_panel]
        app_secret_key
        app_name = n6 Admin Panel
        template_mode = bootstrap3
    '''
    engine_config_prefix = ''
    string_pk_table_models_views = [
        (Org, OrgView),
        (OrgGroup, CustomColumnListView),
        (User, UserView),
        #(Component, ComponentView),
        (CriteriaContainer, CriteriaContainerView),
        (Source, SourceView),
        (Subsource, CustomColumnListView),
        (SubsourceGroup, CustomColumnListView),
        (SystemGroup, CustomColumnListView),
    ]
    # list of models with single, main column, which primary keys
    # are auto-generated integers
    auto_pk_table_classes = [
        CriteriaASN,
        CriteriaCC,
        CriteriaIPNetwork,
        CriteriaName,
        EMailNotificationAddress,
        InsideFilterASN,
        InsideFilterCC,
        InsideFilterFQDN,
        InsideFilterIPNetwork,
        InsideFilterURL,
    ]
    # temporarily disabled in the Flask-Admin view
    certificate_related_models = [
        CACert,
        Cert,
        RequestCase,
    ]

    def __init__(self, engine):
        self.app_config = self.get_config_section()
        self.app = Flask(__name__)
        self.app.secret_key = self.app_config['app_secret_key']
        self.app.teardown_request(self._teardown_request)
        db_session.configure(bind=engine)
        self.admin = Admin(self.app,
                           name=self.app_config['app_name'],
                           template_mode=self.app_config['template_mode'],
                           index_view=CustomIndexView(
                               name='Home',
                               template='home.html',
                               url='/'))
        self._populate_views()

    def run_app(self):
        self.app.run()

    @staticmethod
    def _teardown_request(exception=None):
        db_session.remove()

    def _populate_views(self):
        for model, view in self.string_pk_table_models_views:
            self.admin.add_view(view(model, db_session))


def monkey_patch_flask_admin():
    setattr(form, 'get_form', get_patched_get_form(form.get_form))
    setattr(Field, 'populate_obj', patched_populate_obj)
    setattr(ActionsMixin, 'init_actions', get_patched_init_actions(ActionsMixin.init_actions))


def get_app():
    """
    Configure an SQL engine and return Flask-Admin WSGI application
    object.

    Returns:
        A flask.app.Flask instance.
    """
    with logging_configured():
        monkey_patch_flask_admin()
        engine = SQLAuthDBConfigMixin().engine
        admin_panel = AdminPanel(engine)
        return admin_panel.app


if __name__ == '__main__':
    # run admin panel on development server
    a = get_app()
    a.run()

# Copyright (c) 2013-2019 NASK. All rights reserved.

import os

from flask import (
    Flask,
    request,
)
from flask_admin import (
    Admin,
    AdminIndexView,
    expose,
)
from flask_admin.actions import ActionsMixin
from flask_admin.contrib.sqla import (
    form,
    ModelView,
)
from flask_admin.form import (
    TimeField,
    rules,
)
from flask_admin.form.widgets import TimePickerWidget
from flask_admin.model.form import (
    InlineFormAdmin,
    converts,
)
from sqlalchemy import inspect
from wtforms import PasswordField
from wtforms.fields import Field
from wtforms.widgets import PasswordInput

from n6adminpanel.patches import (
    PatchedInlineModelConverter,
    get_patched_get_form,
    get_patched_init_actions,
    patched_populate_obj,
)
from n6lib.auth_db.audit_log import AuditLog
from n6lib.auth_db.config import SQLAuthDBConfigMixin
from n6lib.auth_db.models import (
    CACert,
    Cert,
    Component,
    ContactPoint,
    CriteriaASN,
    CriteriaCC,
    CriteriaContainer,
    CriteriaIPNetwork,
    CriteriaName,
    EMailNotificationAddress,
    EMailNotificationTime,
    EntityType,
    ExtraId,
    ExtraIdType,
    InsideFilterASN,
    InsideFilterCC,
    InsideFilterFQDN,
    InsideFilterIPNetwork,
    InsideFilterURL,
    LocationType,
    Org,
    OrgGroup,
    Source,
    Subsource,
    SubsourceGroup,
    SystemGroup,
    User,
    db_session,
)
from n6lib.config import ConfigMixin
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)


LOGGER = get_logger(__name__)


### TODO: better error messages on integrity/constraint/etc. errors...


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
            kwargs['placeholder'] = 'Add user\'s password.'
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


class _ExtraCSSMixin(object):

    def render(self, *args, **kwargs):
        custom_css_url = self.get_url('static', filename='custom.css')
        self.extra_css = [custom_css_url]
        return super(_ExtraCSSMixin, self).render(*args, **kwargs)


class UserInlineFormAdmin(_PasswordFieldHandlerMixin, InlineFormAdmin):

    column_display_pk = False
    column_descriptions = {
        'login': 'User\'s login (e-mail address).',
    }
    form_columns = [
        'id',
        'login',
        'password',  # TODO: a button to remove the password (set it to NULL) should be provided
        'system_groups',

        'created_certs',
        'owned_certs',
        'revoked_certs',
    ]


class ContactPointInlineFormAdmin(InlineFormAdmin):

    column_display_pk = False
    form_columns = [
        'id',

        'title',
        'name',
        'surname',
        'email',
        'phone',
    ]


class NotificationTimeInlineFormAdmin(InlineFormAdmin):

    form_args = {
        'notification_time': {
            'default_format': '%H:%M',
        },
    }


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
        if self.can_edit_pk:
            sorted_columns.extend(pk_columns)
        sorted_columns.extend(regular_columns)
        self.form_columns = sorted_columns
        relationships = [key for key in inspection.relationships.keys()
                         if key not in self.excluded_form_columns]
        self.form_columns.extend(relationships)

    column_display_pk = True
    can_edit_pk = True
    excluded_form_columns = ()

    def __init__(self, model, session, **kwargs):
        self._set_list_of_form_columns(model)
        super(CustomColumnListView, self).__init__(model, session, **kwargs)


class CustomColumnAutoPKView(CustomColumnListView):

    can_edit_pk = False


class CustomWithInlineFormsModelView(N6ModelView):

    """
    This implementation of the `ModelView` should be used as a base
    class for model views, that have some of their fields displayed
    as "inline models" with non-integer Primary Keys, that need
    to be filled.
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


class OrgView(CustomWithInlineFormsModelView):

    # create_modal = True
    # edit_modal = True
    model_form_converter = OrgModelConverter
    column_descriptions = {
        'org_id': "Organization's identifier (domain name).",
    }
    can_view_details = True
    # essential to display PK column in the "list" view
    column_display_pk = True
    column_searchable_list = ['org_id']
    column_list = [
        'org_id',
        'actual_name',
        'full_access',
        # 'stream_api_enabled',
        # 'email_notification_enabled',
        # 'email_notification_business_days_only',
        'access_to_inside',
        'access_to_threats',
        'access_to_search',
        'public_entity',
        'verified',
    ]
    form_columns = [
        'org_id',
        'actual_name',
        'org_groups',
        'users',
        'full_access',
        'stream_api_enabled',
        # authorization:
        'access_to_inside',
        'inside_subsources',
        'inside_off_subsources',
        'inside_subsource_groups',
        'inside_off_subsource_groups',
        'access_to_threats',
        'threats_subsources',
        'threats_off_subsources',
        'threats_subsource_groups',
        'threats_off_subsource_groups',
        'access_to_search',
        'search_subsources',
        'search_off_subsources',
        'search_subsource_groups',
        'search_off_subsource_groups',
        # notification settings:
        'email_notification_enabled',
        'email_notification_addresses',
        'email_notification_times',
        'email_notification_language',
        'email_notification_business_days_only',
        # filter-related options:
        'inside_filter_asns',
        'inside_filter_ccs',
        'inside_filter_fqdns',
        'inside_filter_ip_networks',
        'inside_filter_urls',
        # official data:
        'public_entity',
        'verified',
        'entity_type',
        'location_type',
        'location',
        'location_coords',
        'address',
        'extra_ids',
        'contact_points',
    ]
    form_rules = [
        rules.Header('Organization basic data'),
        rules.Field('org_id'),
        rules.Field('actual_name'),
        rules.Field('full_access'),
        rules.Field('stream_api_enabled'),
        rules.Field('org_groups'),

        rules.Header('Users'),
        rules.Field('users'),

        rules.Header('"Inside" access zone'),
        rules.Field('access_to_inside'),
        rules.Field('inside_subsources'),
        rules.Field('inside_off_subsources'),
        rules.Field('inside_subsource_groups'),
        rules.Field('inside_off_subsource_groups'),

        rules.Header('"Threats" access zone'),
        rules.Field('access_to_threats'),
        rules.Field('threats_subsources'),
        rules.Field('threats_off_subsources'),
        rules.Field('threats_subsource_groups'),
        rules.Field('threats_off_subsource_groups'),

        rules.Header('"Search" access zone'),
        rules.Field('access_to_search'),
        rules.Field('search_subsources'),
        rules.Field('search_off_subsources'),
        rules.Field('search_subsource_groups'),
        rules.Field('search_off_subsource_groups'),

        rules.Header('E-mail notification settings'),
        rules.Field('email_notification_enabled'),
        rules.Field('email_notification_addresses'),
        rules.Field('email_notification_times'),
        rules.Field('email_notification_language'),
        rules.Field('email_notification_business_days_only'),

        rules.Header('"Inside" event criteria (checked by n6filter)'),
        rules.Field('inside_filter_asns'),
        rules.Field('inside_filter_ccs'),
        rules.Field('inside_filter_fqdns'),
        rules.Field('inside_filter_ip_networks'),
        rules.Field('inside_filter_urls'),

        rules.Header('Official data'),
        rules.Field('public_entity'),
        rules.Field('verified'),
        rules.Field('entity_type'),
        rules.Field('location_type'),
        rules.Field('location'),
        rules.Field('location_coords'),
        rules.Field('address'),
        rules.Field('extra_ids'),

        rules.Header('Official contact points'),
        rules.Field('contact_points'),
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
        ExtraId,
        ContactPointInlineFormAdmin(ContactPoint),
    ]


class UserView(_PasswordFieldHandlerMixin, N6ModelView):

    column_descriptions = {
        'login': 'User\'s login (e-mail address).',
    }
    column_list = ['login', 'org', 'system_groups']
    form_columns = [
        'login',
        'password',  # TODO: a button to remove the password (set it to NULL) should be provided
        'org',
        'system_groups',

        'created_certs',
        'owned_certs',
        'revoked_certs',
    ]


class ComponentView(_PasswordFieldHandlerMixin, N6ModelView):

    column_list = ['login']
    form_columns = [
        'login',
        'password',  # TODO: a button to remove the password (set it to NULL) should be provided
        'created_certs',
        'owned_certs',
        'revoked_certs',
    ]


class CriteriaContainerView(CustomColumnListView):

    column_list = [
        'label',
        'inclusion_subsources',
        'exclusion_subsources',
    ]
    column_descriptions = {
        'inclusion_subsources': ('Subsources that use this container as a part '
                                 'of their inclusion criteria specification.'),
        'exclusion_subsources': ('Subsources that use this container as a part '
                                 'of their exclusion criteria specification.'),
    }
    excluded_form_columns = [
        'inclusion_subsources',
        'exclusion_subsources',
    ]
    inline_models = [
        CriteriaASN,
        CriteriaCC,
        CriteriaIPNetwork,
        CriteriaName,
    ]


class SourceView(CustomWithInlineFormsModelView, CustomColumnListView):

    inline_models = [
        Subsource,
    ]


class CertView(_ExtraCSSMixin, N6ModelView):

    list_template = 'wrapped_list.html'

    column_searchable_list = ['owner_login', 'owner_component_login']

    column_list = [
        'ca_cert',
        'serial_hex',

        'owner',
        'owner_component',

        'is_client_cert',
        'is_server_cert',

        'valid_from',
        'expires_on',
        'revoked_on',
    ]
    form_columns = [
        'ca_cert',
        'serial_hex',

        'owner',
        'owner_component',

        'certificate',
        'csr',

        'valid_from',
        'expires_on',

        'is_client_cert',
        'is_server_cert',

        'created_on',
        'created_by',
        'created_by_component',
        'creator_details',

        'revoked_by',
        'revoked_by_component',
        'revoked_on',
        'revocation_comment',
    ]


class CACertView(_ExtraCSSMixin, CustomColumnListView):

    column_searchable_list = ['ca_label', 'profile']

    column_list = [
        'ca_label',
        'profile',
        'parent_ca',
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
    table_views = [
        (Org, OrgView),
        (User, UserView),
        (Source, SourceView),
        (Subsource, CustomColumnAutoPKView),
        (CriteriaContainer, CriteriaContainerView),
        (OrgGroup, CustomColumnListView),
        (SystemGroup, CustomColumnListView),
        (SubsourceGroup, CustomColumnListView),
        (Component, ComponentView),
        (CACert, CACertView),
        (Cert, CertView),
        (EntityType, CustomColumnListView),
        (LocationType, CustomColumnListView),
        (ExtraIdType, CustomColumnListView),
    ]

    def __init__(self, engine):
        self.app_config = self.get_config_section()
        self.app = Flask(__name__)
        self.app.secret_key = self.app_config['app_secret_key']
        self.app.before_request(self._before_request)
        self.app.teardown_request(self._teardown_request)
        db_session.configure(bind=engine)
        self._audit_log = AuditLog(db_session)
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

    def _before_request(self):
        db_session.info['remote_addr'] = request.remote_addr

    @staticmethod
    def _teardown_request(exception=None):
        db_session.remove()

    def _populate_views(self):
        for model, view in self.table_views:
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
    # (note: you can set FLASK_ENV to '' -- to turn off the
    # development-specific stuff, such as debug messages...)
    os.environ.setdefault('FLASK_ENV', 'development')
    a = get_app()
    a.run()

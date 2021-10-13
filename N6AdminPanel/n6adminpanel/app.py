# Copyright (c) 2013-2021 NASK. All rights reserved.

import ast
import os
import uuid

from flask import (
    Flask,
    flash,
    request,
    g,
)
from flask_admin import (
    Admin,
    AdminIndexView,
    expose,
)
from flask_admin.actions import ActionsMixin
from flask_admin.contrib.sqla import (
    ModelView,
    form as fa_sqla_form,
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
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
)
from wtforms import (
    BooleanField,
    PasswordField,
    StringField,
)
from wtforms.fields import Field
from wtforms.widgets import PasswordInput

from n6adminpanel import org_request_helpers
from n6adminpanel.mail_notices_helpers import MailNoticesMixin
from n6adminpanel.patches import (
    PatchedInlineModelConverter,
    get_patched_get_form,
    get_patched_init_actions,
    patched_populate_obj,
)
from n6lib.auth_db.api import AuthManageAPI
from n6lib.auth_db.audit_log import AuditLog
from n6lib.auth_db.config import SQLAuthDBConfigMixin
from n6lib.auth_db.models import (
    CACert,
    Cert,
    Component,
    CriteriaASN,
    CriteriaCC,
    CriteriaContainer,
    CriteriaIPNetwork,
    CriteriaName,
    DependantEntity,
    EMailNotificationAddress,
    EMailNotificationTime,
    Entity,
    EntityASN,
    EntityContactPoint,
    EntityContactPointPhone,
    EntityExtraId,
    EntityExtraIdType,
    EntityFQDN,
    EntityIPNetwork,
    EntitySector,
    InsideFilterASN,
    InsideFilterCC,
    InsideFilterFQDN,
    InsideFilterIPNetwork,
    InsideFilterURL,
    Org,
    OrgConfigUpdateRequest,
    OrgConfigUpdateRequestASN,
    OrgConfigUpdateRequestEMailNotificationAddress,
    OrgConfigUpdateRequestEMailNotificationTime,
    OrgConfigUpdateRequestFQDN,
    OrgConfigUpdateRequestIPNetwork,
    OrgGroup,
    RegistrationRequest,
    RegistrationRequestASN,
    RegistrationRequestEMailNotificationAddress,
    RegistrationRequestFQDN,
    RegistrationRequestIPNetwork,
    Source,
    Subsource,
    SubsourceGroup,
    SystemGroup,
    User,
)
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import ThreadLocalNamespace
from n6lib.config import ConfigMixin
from n6lib.const import (
    WSGI_SSL_ORG_ID_FIELD,
    WSGI_SSL_USER_ID_FIELD,
)
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.mail_notices_api import MailNoticesAPI


LOGGER = get_logger(__name__)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False))


### TODO: better error messages on integrity/constraint/etc. errors...


class N6ModelView(ModelView):

    """
    Base n6 view.

    Used to define global parameters in all views.
    """

    fast_mass_delete = False
    """
        This property is derived from flask-admin's ModelView which
        sets the default value to `False`. So this assignment (here, in
        `N6ModelView`) is redundant; we do it here just to be explicit
        about the desired value of this option (we really do *not* want
        to use bulk operations -- for various reasons, among others: we
        want all benefits the SQLAlchemy's relationship-cleaning
        machinery gives us; but also because of some AuditLog-related
        stuff...).
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
        if field.data:
            kwargs['placeholder'] = 'Edit to change user\'s password.'
        else:
            kwargs['placeholder'] = 'Add user\'s password.'
        return super(CustomPasswordInput, self).__call__(field, **kwargs)


class CustomPasswordField(PasswordField):

    widget = CustomPasswordInput()

    def populate_obj(self, obj, name):
        # Here we do nothing; the object will be populated
        # in `_PasswordFieldHandlerMixin.on_model_change()`.
        pass


class _PasswordFieldHandlerMixin(object):

    @property
    def form_extra_fields(self):
        sup = super(_PasswordFieldHandlerMixin, self)
        from_super = getattr(sup, 'form_extra_fields', None) or {}
        return dict(from_super,
                    password=CustomPasswordField(),
                    delete_password=BooleanField('Delete Password'))

    def on_model_change(self, form, model, is_created):
        # noinspection PyUnresolvedReferences
        super(_PasswordFieldHandlerMixin, self).on_model_change(form, model, is_created)
        if hasattr(form, 'delete_password') and form.delete_password and form.delete_password.data:
            model.password = None
        elif hasattr(form, 'password') and form.password and form.password.data:
            model.password = model.get_password_hash_or_none(form.password.data)


class _APIKeyFieldHandlerMixin(object):

    @property
    def form_extra_fields(self):
        sup = super(_APIKeyFieldHandlerMixin, self)
        from_super = getattr(sup, 'form_extra_fields', None) or {}
        return dict(from_super,
                    api_key_id=StringField(),
                    delete_api_key_id=BooleanField('Delete Api Key Id'),
                    generate_new_api_key_id=BooleanField('Generate New Api Key Id'))

    @property
    def form_widget_args(self):
        sup = super(_APIKeyFieldHandlerMixin, self)
        from_super = getattr(sup, 'form_widget_args', None) or {}
        return dict(from_super,
                    api_key_id={'readonly': True},
                    api_key_id_modified_on={'disabled': True})

    def on_model_change(self, form, model, is_created):
        # noinspection PyUnresolvedReferences
        super(_APIKeyFieldHandlerMixin, self).on_model_change(form, model, is_created)
        if hasattr(form, 'generate_new_api_key_id') and (form.generate_new_api_key_id
                                                         and form.generate_new_api_key_id.data):
            model.api_key_id = str(uuid.uuid4())
        elif hasattr(form, 'delete_api_key_id') and (form.delete_api_key_id
                                                     and form.delete_api_key_id.data):
            model.api_key_id = None


class _MFAKeyBaseFieldHandlerMixin(MailNoticesMixin):

    @property
    def form_extra_fields(self):
        sup = super(_MFAKeyBaseFieldHandlerMixin, self)
        from_super = getattr(sup, 'form_extra_fields', None) or {}
        return dict(from_super,
                    mfa_key_base=StringField(),
                    delete_mfa_key_base=BooleanField('Delete Mfa Key Base'))

    @property
    def form_widget_args(self):
        sup = super(_MFAKeyBaseFieldHandlerMixin, self)
        from_super = getattr(sup, 'form_widget_args', None) or {}
        return dict(from_super,
                    mfa_key_base={'readonly': True},
                    mfa_key_base_modified_on={'disabled': True})

    def on_model_change(self, form, model, is_created):
        # noinspection PyUnresolvedReferences
        super(_MFAKeyBaseFieldHandlerMixin, self).on_model_change(form, model, is_created)
        if hasattr(form, 'delete_mfa_key_base') and (form.delete_mfa_key_base
                                                     and form.delete_mfa_key_base.data):
            model.mfa_key_base = None
            if isinstance(model, User) and not is_created:
                g.n6_user_mfa_key_base_erased = True

    def after_model_change(self, form, model, is_created):
        if g.n6_user_mfa_key_base_erased:
            assert isinstance(model, User)
            self.try_to_send_mail_notices(
                notice_key='mfa_config_erased',
                user_login=model.login)
        # noinspection PyUnresolvedReferences
        super(_MFAKeyBaseFieldHandlerMixin, self).after_model_change(form, model, is_created)


class _ExtraCSSMixin(object):

    def render(self, *args, **kwargs):
        custom_css_url = self.get_url('static', filename='custom.css')
        self.extra_css = [custom_css_url]
        return super(_ExtraCSSMixin, self).render(*args, **kwargs)


class UserInlineFormAdmin(_PasswordFieldHandlerMixin,
                          _APIKeyFieldHandlerMixin,
                          _MFAKeyBaseFieldHandlerMixin,
                          InlineFormAdmin):

    column_display_pk = False
    column_descriptions = {
        'login': 'User\'s login (e-mail address).',
    }
    form_columns = [
        'id',

        'is_blocked',
        'login',

        'password',
        'delete_password',

        'mfa_key_base',
        'mfa_key_base_modified_on',
        'delete_mfa_key_base',

        'api_key_id',
        'api_key_id_modified_on',
        'delete_api_key_id',
        'generate_new_api_key_id',

        'system_groups',

        'created_certs',
        'owned_certs',
        'revoked_certs',
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


class ModelWithShortTimeFieldConverter(fa_sqla_form.AdminModelConverter):

    @converts('Time')
    def convert_time(self, field_args, **extra):
        return ShortTimeField(**field_args)


class OrgView(CustomWithInlineFormsModelView):

    # create_modal = True
    # edit_modal = True
    model_form_converter = ModelWithShortTimeFieldConverter
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
    ]
    form_columns = [
        'org_id',
        'actual_name',
        'org_groups',
        'users',
        'entity',
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
    ]
    form_rules = [
        rules.Header('Organization basic data'),
        rules.Field('org_id'),
        rules.Field('actual_name'),
        rules.Field('full_access'),
        rules.Field('stream_api_enabled'),

        rules.Header('Groups and users'),
        rules.Field('org_groups'),
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

        rules.Header('Related entity'),
        rules.Field('entity'),
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


class OrgRequestViewMixin(object):

    can_create = False
    can_view_details = True

    # essential to display PK column in the "list" view
    column_display_pk = True

    # to be set in subclasses to one of the handler kits
    # defined in `n6adminpanel.org_request_helpers`
    org_request_handler_kit = None

    @attr_required('org_request_handler_kit')
    def on_model_change(self, form, model, is_created):
        assert not is_created, "isn't `can_create` set to False?!"
        # (The handler called here makes use of `ACTIONS_FIELD...`)
        self.org_request_handler_kit.just_before_commit(form, model)
        # noinspection PyUnresolvedReferences
        return super(OrgRequestViewMixin, self).on_model_change(form, model, is_created)

    @attr_required('org_request_handler_kit')
    def after_model_change(self, form, model, is_created):
        assert not is_created, "isn't `can_create` set to False?!"
        self.org_request_handler_kit.just_after_commit(model)
        # noinspection PyUnresolvedReferences
        return super(OrgRequestViewMixin, self).after_model_change(form, model, is_created)


class RegistrationRequestView(OrgRequestViewMixin, CustomWithInlineFormsModelView):

    column_searchable_list = ['status', 'ticket_id', 'org_id', 'actual_name', 'email']
    column_list = [
        'id',
        'submitted_on',
        'modified_on',
        'status',
        'ticket_id',

        'org_id',
        'actual_name',
        'email',

        'email_notification_language',
    ]

    column_descriptions = {
        'terms_version': 'The version of the legal terms accepted by the client.',
        'terms_lang': 'The language variant of the legal terms accepted by the client.',
    }

    form_extra_fields = {
        org_request_helpers.ACTIONS_FIELD_NAME:
            org_request_helpers.ACTIONS_FIELD_FOR_REGISTRATION,
    }
    form_columns = [
        'id',
        'submitted_on',
        'modified_on',

        'status',
        'ticket_id',
        'org_group',
        org_request_helpers.ACTIONS_FIELD_NAME,

        'org_id',
        'actual_name',
        'email',
        'submitter_title',
        'submitter_firstname_and_surname',
        'csr',

        'email_notification_language',
        'email_notification_addresses',

        'asns',
        'fqdns',
        'ip_networks',

        'terms_version',
        'terms_lang',
    ]
    form_widget_args = {
        # Let it be visible but inactive. (State changes
        # can be made only with the custom buttons which
        # fill out the target-status-dedicated invisible
        # input; that input and those buttons are provided
        # by `org_request_helpers.ACTIONS_FIELD...`
        # -- see `form_extra_fields` below.)
        'status': {'disabled': True},

        'terms_version': {'readonly': True},
        'terms_lang': {'readonly': True},
    }
    form_rules = [
        rules.Header('Registration request consideration'),
        rules.Field('status'),
        rules.Field('ticket_id'),
        rules.Field('org_group'),
        rules.Field(org_request_helpers.ACTIONS_FIELD_NAME),

        rules.Header('Basic and access-related data'),
        rules.Field('org_id'),
        rules.Field('actual_name'),
        rules.Field('email'),
        rules.Field('submitter_title'),
        rules.Field('submitter_firstname_and_surname'),
        rules.Field('csr'),

        rules.Header('"Inside" event criteria'),
        rules.Field('asns'),
        rules.Field('fqdns'),
        rules.Field('ip_networks'),

        rules.Header('E-mail notifications preferences'),
        rules.Field('email_notification_language'),
        rules.Field('email_notification_addresses'),

        rules.Header('Legal information'),
        rules.Field('terms_version'),
        rules.Field('terms_lang'),
    ]
    org_request_handler_kit = org_request_helpers.registration_request_handler_kit
    inline_models = [
        RegistrationRequestEMailNotificationAddress,
        RegistrationRequestASN,
        RegistrationRequestFQDN,
        RegistrationRequestIPNetwork,
    ]


class OrgConfigUpdateRequestView(OrgRequestViewMixin, CustomWithInlineFormsModelView):

    column_searchable_list = ['status', 'ticket_id', 'org_id']
    column_list = [
        'id',
        'submitted_on',
        'modified_on',
        'status',
        'ticket_id',
        'org_id',
    ]

    form_extra_fields = {
        org_request_helpers.ACTIONS_FIELD_NAME:
            org_request_helpers.ACTIONS_FIELD_FOR_ORG_CONFIG_UPDATE,
    }
    form_columns = [
        'id',
        'submitted_on',
        'modified_on',

        'status',
        'ticket_id',
        'org_id',
        'requesting_user_login',
        'additional_comment',
        org_request_helpers.ACTIONS_FIELD_NAME,

        'actual_name_upd',
        'actual_name',

        'email_notification_enabled_upd',
        'email_notification_enabled',

        'email_notification_language_upd',
        'email_notification_language',

        'email_notification_addresses_upd',
        'email_notification_addresses',

        'email_notification_times_upd',
        'email_notification_times',

        'asns_upd',
        'asns',

        'fqdns_upd',
        'fqdns',

        'ip_networks_upd',
        'ip_networks',
    ]
    form_widget_args = {
        # Let it be visible but inactive. (State changes
        # can be made only with the custom buttons which
        # fill out the target-status-dedicated invisible
        # input; that input and those buttons are provided
        # by `org_request_helpers.ACTIONS_FIELD...`
        # -- see `form_extra_fields` below.)
        'status': {'disabled': True},

        'org_id': {'readonly': True},
        'requesting_user_login': {'readonly': True},
        'additional_comment': {'readonly': True},
    }
    form_rules = [
        rules.Header('Org config update request consideration'),
        rules.Field('status'),
        rules.Field('ticket_id'),
        rules.Field('org_id'),
        rules.Field('requesting_user_login'),
        rules.Field('additional_comment'),
        rules.Field(org_request_helpers.ACTIONS_FIELD_NAME),

        rules.Header('Updates of basic data'),
        rules.Field('actual_name_upd'),
        rules.Field('actual_name'),

        rules.Header('Updates of "Inside" event criteria'),
        rules.Field('asns_upd'),
        rules.Field('asns'),
        rules.Field('fqdns_upd'),
        rules.Field('fqdns'),
        rules.Field('ip_networks_upd'),
        rules.Field('ip_networks'),

        rules.Header('Updates of e-mail notifications preferences'),
        rules.Field('email_notification_enabled_upd'),
        rules.Field('email_notification_enabled'),
        rules.Field('email_notification_language_upd'),
        rules.Field('email_notification_language'),
        rules.Field('email_notification_addresses_upd'),
        rules.Field('email_notification_addresses'),
        rules.Field('email_notification_times_upd'),
        rules.Field('email_notification_times'),
    ]
    org_request_handler_kit = org_request_helpers.org_config_update_request_handler_kit
    inline_models = [
        OrgConfigUpdateRequestEMailNotificationAddress,
        OrgConfigUpdateRequestEMailNotificationTime,
        OrgConfigUpdateRequestASN,
        OrgConfigUpdateRequestFQDN,
        OrgConfigUpdateRequestIPNetwork,
    ]


class UserView(_PasswordFieldHandlerMixin,
               _APIKeyFieldHandlerMixin,
               _MFAKeyBaseFieldHandlerMixin,
               N6ModelView):

    column_descriptions = {
        'login': 'User\'s login (e-mail address).',
    }
    column_list = ['login', 'org', 'system_groups']
    form_columns = [
        'is_blocked',
        'login',

        'password',
        'delete_password',

        'mfa_key_base',
        'mfa_key_base_modified_on',
        'delete_mfa_key_base',

        'api_key_id',
        'api_key_id_modified_on',
        'delete_api_key_id',
        'generate_new_api_key_id',

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
        'password',
        'delete_password',
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


class EntityContactPointPhoneInlineFormAdmin(InlineFormAdmin):

    form_columns = [
        'id',
        'phone_number',
        'availability',
    ]


class EntityContactPointInlineFormAdmin(CustomWithInlineFormsModelView):

    form_columns = [
        'id',

        'name',
        'position',
        'email',

        'phones',

        'external_placement',
        'external_entity_name',
        'external_entity_address',
    ]
    inline_models = [
        EntityContactPointPhoneInlineFormAdmin(EntityContactPointPhone),
    ]


class EntityView(CustomWithInlineFormsModelView):

    model_form_converter = ModelWithShortTimeFieldConverter
    can_view_details = True
    # essential to display PK column in the "list" view
    column_display_pk = True
    column_searchable_list = [
        'full_name', 'short_name', 'email', 'city', 'sector_label', 'ticket_id',
    ]
    column_list = [
        'full_name', 'short_name', 'email', 'city', 'sector_label', 'ticket_id',
    ]
    form_columns = [
        # official data:
        'id',
        'full_name',
        'short_name',
        'verified',
        'email',
        'address',
        'city',
        'postal_code',
        'public_essential_service',
        'sector',
        'ticket_id',
        'internal_id',
        'extra_ids',
        'additional_information',
        'asns',
        'fqdns',
        'ip_networks',
        'alert_email',
        'contact_points',
        'dependant_entities',
        'org',
    ]
    form_rules = [
        rules.Header('Basic data'),
        rules.Field('full_name'),
        rules.Field('short_name'),
        rules.Field('verified'),
        rules.Field('email'),
        rules.Field('address'),
        rules.Field('city'),
        rules.Field('postal_code'),

        rules.Header('Supplementary data'),
        rules.Field('public_essential_service'),
        rules.Field('sector'),
        rules.Field('ticket_id'),
        rules.Field('internal_id'),
        rules.Field('extra_ids'),
        rules.Field('additional_information'),

        rules.Header('Own network data'),
        rules.Field('asns'),
        rules.Field('fqdns'),
        rules.Field('ip_networks'),

        rules.Header('Contact data'),
        rules.Field('alert_email'),
        rules.Field('contact_points'),

        rules.Header('Dependant entities'),
        rules.Field('dependant_entities'),

        rules.Header('Related n6 client Org'),
        rules.Field('org'),
    ]
    inline_models = [
        EntityExtraId,
        EntityASN,
        EntityFQDN,
        EntityIPNetwork,
        EntityContactPointInlineFormAdmin(EntityContactPoint, db_session),
        DependantEntity,
    ]


class CustomIndexView(AdminIndexView):

    @expose('/')
    def index(self):
        return self.render('home.html')


class _AuthManageAPIAdapter(AuthManageAPI):

    class _DBConnectorReplacement(object):
        def get_current_session(self):
            return db_session()
        def __enter__(self): pass
        def __exit__(self, exc_type, exc_value, tb): pass
        def set_audit_log_external_meta_items(self, **_):
            raise AssertionError('method invocation not expected')

    # noinspection PyMissingConstructor
    def __init__(self):
        self._db_connector = self._DBConnectorReplacement()

    def _try_to_get_client_error(self, *args, **kwargs):
        err = super(_AuthManageAPIAdapter, self)._try_to_get_client_error(*args, **kwargs)
        if err is not None:
            flash(err.public_message, 'error')
        return err


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
        (OrgConfigUpdateRequest, OrgConfigUpdateRequestView),
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
        (RegistrationRequest, RegistrationRequestView),
        (Entity, EntityView),
        (EntitySector, CustomColumnListView),
        (EntityExtraIdType, CustomColumnListView),
    ]

    def __init__(self, engine):
        self._mail_notices_api = MailNoticesAPI()
        self._auth_manage_api_adapter = _AuthManageAPIAdapter()
        self.app_config = self.get_config_section()
        self.app = Flask(__name__)
        self.app.secret_key = self.app_config['app_secret_key']
        self.app.before_request(self._before_request)
        self.app.teardown_request(self._teardown_request)
        db_session.configure(bind=engine)
        self._thread_local = thread_local = ThreadLocalNamespace(attr_factories={
            'audit_log_external_meta_items': dict,
        })
        self._audit_log = AuditLog(
            session_factory=db_session,
            external_meta_items_getter=lambda: thread_local.audit_log_external_meta_items)
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
        self._thread_local.audit_log_external_meta_items = {
            key: value for key, value in [
                ('n6_module', __name__),
                ('request_environ_remote_addr', request.environ.get("REMOTE_ADDR")),
                ('request_org_id', request.environ.get(WSGI_SSL_ORG_ID_FIELD)),
                ('request_user_id', request.environ.get(WSGI_SSL_USER_ID_FIELD)),
            ]
            if value is not None}
        # Attributes used by the `org_request_helpers` and/or `mail_notices_helpers` stuff:
        g.n6_mail_notices_api = self._mail_notices_api
        g.n6_auth_manage_api_adapter = self._auth_manage_api_adapter
        g.n6_org_config_info = None
        # Attributes used by the `_MFAKeyBaseFieldHandlerMixin` stuff:
        g.n6_user_mfa_key_base_erased = False

    @staticmethod
    def _teardown_request(exception=None):
        db_session.remove()

    def _populate_views(self):
        for model, view in self.table_views:
            self.admin.add_view(view(model, db_session))


def monkey_patch_flask_admin():
    setattr(fa_sqla_form, 'get_form', get_patched_get_form(fa_sqla_form.get_form))
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


def dev_server_main():
    """
    Run the n6 Admin Panel using the Flask development server.

    (*Not* for production!)
    """
    # (note: you can set the FLASK_ENV environment variable to '' -- to
    # turn off the development-specific stuff, such as debug messages...)
    os.environ.setdefault('FLASK_ENV', 'development')
    a = get_app()
    # (note: you can set the N6_ADMIN_PANEL_DEV_RUN_KWARGS environment
    # variable to customize the keyword arguments to be passed to the
    # application's `run()` method, e.g.: '{"host": "0.0.0.0"}')
    run_kwargs = ast.literal_eval(os.environ.get('N6_ADMIN_PANEL_DEV_RUN_KWARGS', '{}'))
    a.run(**run_kwargs)


if __name__ == '__main__':
    dev_server_main()

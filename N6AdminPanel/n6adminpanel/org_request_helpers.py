# Copyright (c) 2020-2021 NASK. All rights reserved.

from collections.abc import Iterable
import html
import re
import string
from typing import Union

from flask import (
    flash,
    g,
)
from sqlalchemy import inspect as sqla_inspect
from wtforms import StringField
from wtforms.widgets import (
    HTMLString,
    TextInput,
)

import n6lib.auth_db.models as models
from n6adminpanel.mail_notices_helpers import MailNoticesMixin
from n6lib.auth_db import (
    ORG_REQUEST_STATUS_ACCEPTED as _STATUS_ACCEPTED,
    ORG_REQUEST_STATUS_DISCARDED as _STATUS_DISCARDED,
    ORG_REQUEST_STATUS_BEING_PROCESSED as _STATUS_BEING_PROCESSED,
    ORG_REQUEST_STATUS_NEW as _STATUS_NEW,
)
from n6lib.common_helpers import ascii_str
from n6lib.log_helpers import get_logger


#
# Non-public stuff (to be used in this module only)
#

LOGGER = get_logger(__name__)


_ID_NAME_OF_TARGET_STATUS_INPUT = 'org_request_form_input_target_status'

_ID_NAME_OF_ACCEPT_BUTTON = 'org_request_form_button_accept'
_ID_NAME_OF_PROC_BUTTON = 'org_request_form_button_proc'
_ID_NAME_OF_DISCARD_BUTTON = 'org_request_form_button_discard'


_HTML_AND_JS_SAFE_CONSTANTS = {
    constant_name: globals()[constant_name]
    for constant_name in [
        '_ID_NAME_OF_TARGET_STATUS_INPUT',
        '_ID_NAME_OF_ACCEPT_BUTTON',
        '_ID_NAME_OF_PROC_BUTTON',
        '_ID_NAME_OF_DISCARD_BUTTON',
        '_STATUS_ACCEPTED',
        '_STATUS_DISCARDED',
        '_STATUS_BEING_PROCESSED',
        '_STATUS_NEW',
    ]}

_OBVIOUSLY_SAFE_CHARACTERS_SUBSET = frozenset(string.ascii_letters + '_')
for _constant_value in _HTML_AND_JS_SAFE_CONSTANTS.values():
    # To make some details of the implementation simpler,
    # we guarantee that these string constants consist only
    # of HTML-and-JS-safe characters -- so that there will
    # be no need to worry about escaping-related matters.
    assert _constant_value == html.escape(_constant_value)
    assert _OBVIOUSLY_SAFE_CHARACTERS_SUBSET.issuperset(_constant_value)


class _OrgRequestActionsWidget(TextInput):

    # Note: we consciously use `TextInput`, and *not* `HiddenInput`,
    # as the base class.  One reason is that, although our text input
    # needs to be invisible, some other visible elements (buttons)
    # are needed; another reason is that widgets whose `input_type` is
    # "hidden" do not cooperate well with `rules.Field`: the problem
    # with them is that the `render_form_fields` Jinja macro (from the
    # Bootstrap template provided by Flask-Admin) renders such fields
    # twice (redundantly): once near the beginning of the form and
    # then within a `div` corresponding to the `rules.Field` instance
    # (such redundancy seems a bug).  That's why we prefer to base on a
    # widget whose `input_type` is "text", and simply to place the input
    # text element in a `div` with the `display:none` style property.
    #
    # The whole rendered HTML includes also other necessary elements:
    # the "Accept...", "Mark as being processed" and "Mark as
    # discarded" buttons, and the JS script that sets things up.

    __PATTERN_OF_BUTTON_HTML = '''
        <input
            id="{id_and_name}"
            name="{id_and_name}"
            value="{button_text}"
            class="btn {button_class}"
            style="visibility: hidden;"
            type="submit"
        >'''

    __PATTERN_OF_INVISIBLE_DIV_HTML = '''
        <div style="display: none;">
            {}
        </div>'''

    __SCRIPT_HTML = '''
        <script>
            document.body.onload = function() {
                var target_status_input = document.getElementById(
                        "%(_ID_NAME_OF_TARGET_STATUS_INPUT)s");

                var accept_button = document.getElementById("%(_ID_NAME_OF_ACCEPT_BUTTON)s");
                var proc_button = document.getElementById("%(_ID_NAME_OF_PROC_BUTTON)s");
                var discard_button = document.getElementById("%(_ID_NAME_OF_DISCARD_BUTTON)s");

                var status;
                try {
                    /*
                        Let's try to get the initial (old) status,
                        i.e., the value of the visible input element
                        `status` (depending on this value, only the
                        relevant buttons will be displayed -- see below).
                    */
                    status = document.querySelectorAll(
                        "form.admin-form")[0].elements["status"].value;
                } catch(err) {
                    /*
                        `null` as the last-resort fallback value, in
                        case of compatibility problems etc. (then all
                        three buttons will be displayed, regardless
                        of the initial status; the backend guards
                        against illegal status transitions anyway).
                    */
                    status = null;
                }

                if (status === "%(_STATUS_ACCEPTED)s") {
                    accept_button.remove();
                    proc_button.remove();
                    discard_button.remove();
                } else {
                    if (status === "%(_STATUS_NEW)s"
                          || status === "%(_STATUS_DISCARDED)s"
                          || status === null) {
                        proc_button.onclick = function() {
                            target_status_input.value = "%(_STATUS_BEING_PROCESSED)s";
                        };
                        proc_button.style.visibility = "visible";
                    } else {
                        proc_button.remove();
                    }
                    if (status === "%(_STATUS_NEW)s"
                          || status === "%(_STATUS_BEING_PROCESSED)s"
                          || status === null) {
                        accept_button.onclick = function() {
                            target_status_input.value = "%(_STATUS_ACCEPTED)s";
                        };
                        discard_button.onclick = function() {
                            target_status_input.value = "%(_STATUS_DISCARDED)s";
                        };
                        accept_button.style.visibility = "visible";
                        discard_button.style.visibility = "visible";
                    } else {
                        accept_button.remove();
                        discard_button.remove();
                    }
                }
            };
        </script>''' % _HTML_AND_JS_SAFE_CONSTANTS

    def __init__(self, *args, **kwargs):
        self.__accept_button_text = kwargs.pop('accept_button_text')
        self.__proc_button_text = kwargs.pop('proc_button_text', 'Mark as being processed')
        self.__discard_button_text = kwargs.pop('discard_button_text', 'Mark as discarded')
        super(_OrgRequestActionsWidget, self).__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        target_status_input_html = super(_OrgRequestActionsWidget, self).__call__(*args, **kwargs)
        self.__verify_id_and_name_have_supported_values(target_status_input_html)
        all_html = self.__assemble_all_html(
            target_status_input_html,
            accept_button_html=self.__make_accept_button_html(),
            proc_button_html=self.__make_proc_button_html(),
            discard_button_html=self.__make_discard_button_html())
        return HTMLString(all_html)

    def __verify_id_and_name_have_supported_values(self, target_status_input_html):
        # The `id` and `name` of the target-status-dedicated
        # text input are required to be equal to the constant
        # `_ID_NAME_OF_TARGET_STATUS_INPUT`.  We constraint them
        # in this way just for simplicity of the implementation
        # (something more general is not needed here).
        id_values = self.__extract_html_attr_values(target_status_input_html, 'id')
        name_values = self.__extract_html_attr_values(target_status_input_html, 'name')
        all_ok = (id_values and all(v == _ID_NAME_OF_TARGET_STATUS_INPUT for v in id_values) and
                  name_values and all(v == _ID_NAME_OF_TARGET_STATUS_INPUT for v in name_values))
        if not all_ok:
            raise AssertionError(
                'both `id` and `name` of the text input rendered with '
                '{} are expected to be equal to {!a} (detected values '
                '- `id`: {}; `name`: {})'.format(
                    self.__class__.__qualname__,
                    _ID_NAME_OF_TARGET_STATUS_INPUT,
                    ', '.join(map(ascii, id_values)) or '<no value>',
                    ', '.join(map(ascii, name_values)) or '<no value>'))

    def __extract_html_attr_values(self, element_html, attr_name):
        """
        >>> inst = _OrgRequestActionsWidget(accept_button_text='Accept...')
        >>> this_method = inst._OrgRequestActionsWidget__extract_html_attr_values
        >>> element_html = '''
        ...     <input id="foo" spam="ham" name="42"  name="y"id"Wrong"id="Good" spam='Bad'>
        ... '''
        >>> this_method(element_html, attr_name='id')
        ['foo', 'Good']
        >>> this_method(element_html, attr_name='name')
        ['42', 'y']
        >>> this_method(element_html, attr_name='spam')
        ['ham']
        >>> this_method(element_html, attr_name='foo')
        []
        """
        regex_pattern = r'\b{0}="([^"]*)"'.format(attr_name)
        return re.findall(regex_pattern, element_html, re.ASCII)

    def __make_accept_button_html(self):
        return self.__format_button_html(
            id_and_name=_ID_NAME_OF_ACCEPT_BUTTON,
            button_text=self.__accept_button_text,
            button_class='btn-primary')

    def __make_proc_button_html(self):
        return self.__format_button_html(
            id_and_name=_ID_NAME_OF_PROC_BUTTON,
            button_text=self.__proc_button_text,
            button_class='btn-default')

    def __make_discard_button_html(self):
        return self.__format_button_html(
            id_and_name=_ID_NAME_OF_DISCARD_BUTTON,
            button_text=self.__discard_button_text,
            button_class='btn-danger')

    def __format_button_html(self, **kwargs):
        return self.__PATTERN_OF_BUTTON_HTML.format(**{
            key: html.escape(value)
            for key, value in kwargs.items()})

    def __assemble_all_html(self,
                            target_status_input_html,
                            accept_button_html,
                            proc_button_html,
                            discard_button_html):
        return (accept_button_html +
                proc_button_html +
                discard_button_html +
                self.__PATTERN_OF_INVISIBLE_DIV_HTML.format(target_status_input_html) +
                self.__SCRIPT_HTML)


class _BaseStatusTransitionHandlerKit(MailNoticesMixin):

    #
    # Public methods

    def just_before_commit(self, form, org_request):
        assert isinstance(org_request, (models.RegistrationRequest,
                                        models.OrgConfigUpdateRequest))

        org_request._successful_status_transition = None

        # Note: we get the old value of the 'status' attribute from the
        # backend (using the SQLAlchemy's *history* facility) because
        # we *must not* trust the old value provided by the frontend
        # (even though, typically, they are the same, because the
        # visible 'status' input element of the form is non-editable).
        old_status = self._get_old_value_of_scalar_attr(org_request, 'status')
        assert old_status, "isn't view's `can_create` set to False?!"

        # Note: we get the new (target) value of 'status' from the form's
        # invisible input element whose name is defined by the constant
        # `_ID_NAME_OF_TARGET_STATUS_INPUT`, *not* from the visible input
        # element whose name is 'status' (the latter typically keeps the
        # old value that we do *not* use -- see the comment above...).
        target_status = form[_ID_NAME_OF_TARGET_STATUS_INPUT].data

        if target_status:
            # Status transition is to be performed...
            self._before_status_transition(org_request, old_status, target_status)
            org_request.status = target_status
            org_request._successful_status_transition = (old_status,
                                                         target_status,
                                                         org_request.org_id)
        else:
            # The old status is to be kept.  To be sure that it is *not*
            # overwritten with a different value from the frontend (that is,
            # from the visible 'status' input element of the form -- see the
            # comments above) let us explicitly set the real old value here.
            org_request.status = old_status

    # noinspection PyProtectedMember
    def just_after_commit(self, org_request):
        assert isinstance(org_request, (models.RegistrationRequest,
                                        models.OrgConfigUpdateRequest))
        if org_request._successful_status_transition:
            (old_status,
             target_status,
             concerned_org_id) = org_request._successful_status_transition
            self._after_status_transition(org_request,
                                          old_status,
                                          target_status,
                                          concerned_org_id)

    #
    # Non-public methods

    def __setattr__(self, name, value):
        raise TypeError(
            '{!a} should be treated as an immutable object (cannot set '
            'the `{!a}` attribute to `{!a}'.format(self, name, value))

    def _get_sqla_session(self, org_request):
        return sqla_inspect(org_request).session

    def _get_old_value_of_scalar_attr(self, org_request, attr_name):
        deleted_or_unchanged = sqla_inspect(org_request).attrs[attr_name].history.non_added()
        if deleted_or_unchanged:
            [old_value] = deleted_or_unchanged
            return old_value
        return None

    def _before_status_transition(self, org_request, old_status, target_status):
        _TARGET_STATUS_TO_HANDLER = {
            _STATUS_NEW: self._before_status_transition_to_new,
            _STATUS_BEING_PROCESSED: self._before_status_transition_to_being_processed,
            _STATUS_DISCARDED: self._before_status_transition_to_discarded,
            _STATUS_ACCEPTED: self._before_status_transition_to_accepted,
        }
        try:
            handler = _TARGET_STATUS_TO_HANDLER[target_status]
        except KeyError:
            raise ValueError('Illegal status tag: "{}".'.format(target_status))
        else:
            # noinspection PyArgumentList
            handler(org_request, old_status, target_status)

    # noinspection PyUnusedLocal
    def _before_status_transition_to_new(self, org_request, old_status, target_status):
        assert target_status == _STATUS_NEW
        self._validate_status_transition(old_status, target_status,
                                         legal_old_statuses=())  # (yes, it'll always fail here)

    # noinspection PyUnusedLocal
    def _before_status_transition_to_being_processed(self, org_request, old_status, target_status):
        assert target_status == _STATUS_BEING_PROCESSED
        self._validate_status_transition(old_status, target_status,
                                         legal_old_statuses=(_STATUS_NEW, _STATUS_DISCARDED))

    # noinspection PyUnusedLocal
    def _before_status_transition_to_discarded(self, org_request, old_status, target_status):
        assert target_status == _STATUS_DISCARDED
        self._validate_status_transition(old_status, target_status,
                                         legal_old_statuses=(_STATUS_NEW, _STATUS_BEING_PROCESSED))

    # noinspection PyUnusedLocal
    def _before_status_transition_to_accepted(self, org_request, old_status, target_status):
        assert target_status == _STATUS_ACCEPTED
        self._validate_status_transition(old_status, target_status,
                                         legal_old_statuses=(_STATUS_NEW, _STATUS_BEING_PROCESSED))

    def _validate_status_transition(self, old_status, target_status, legal_old_statuses):
        if old_status not in legal_old_statuses:
            raise ValueError(
                'Changing status from "{}" to "{}" is not allowed.'.format(
                    old_status,
                    target_status))
        if __debug__:
            # Assertions regarding conditions whose veracity has already been guaranteed:
            assert old_status in (_STATUS_NEW, _STATUS_BEING_PROCESSED, _STATUS_DISCARDED)
            assert target_status in (_STATUS_BEING_PROCESSED, _STATUS_DISCARDED, _STATUS_ACCEPTED)
            if old_status == _STATUS_NEW:
                assert target_status in (_STATUS_BEING_PROCESSED, _STATUS_DISCARDED, _STATUS_ACCEPTED)
            elif old_status == _STATUS_BEING_PROCESSED:
                assert target_status in (_STATUS_DISCARDED, _STATUS_ACCEPTED)
            elif old_status == _STATUS_DISCARDED:
                assert target_status == _STATUS_BEING_PROCESSED

    def _after_status_transition(self,
                                 org_request,
                                 old_status,
                                 target_status,
                                 concerned_org_id):
        if target_status == _STATUS_ACCEPTED:
            # Note: for the sake of strictness, we consciously
            # use `concerned_org_id`, *not* the current value of
            # `org_request.org_id` -- because we want to be sure we
            # report the value it obtained within the transaction
            # (which has already finished), and the current value
            # may not be the same (even though typically is).
            self._after_status_transition_to_accepted(
                org_request,
                old_status,
                target_status,
                concerned_org_id)
        else:
            self._after_status_transition_to_other(
                org_request,
                old_status,
                target_status,
                concerned_org_id)

    def _after_status_transition_to_accepted(self,
                                             org_request,
                                             old_status,
                                             target_status,
                                             concerned_org_id):
        raise NotImplementedError

    def _after_status_transition_to_other(self,
                                          org_request,
                                          old_status,
                                          target_status,
                                          concerned_org_id):
        raise NotImplementedError


class _RegistrationRequestStatusTransitionHandlerKit(_BaseStatusTransitionHandlerKit):

    def _before_status_transition_to_accepted(self, org_request, old_status, target_status):
        assert isinstance(org_request, models.RegistrationRequest)
        super(_RegistrationRequestStatusTransitionHandlerKit,
              self)._before_status_transition_to_accepted(org_request, old_status, target_status)
        session = self._get_sqla_session(org_request)
        self._verify_org_group_specified(org_request)
        self._verify_org_does_not_exist(session, org_request)
        self._create_org_according_to_request(session, org_request)

    def _verify_org_group_specified(self, org_request):
        assert isinstance(org_request, models.RegistrationRequest)
        if org_request.org_group is None:
            raise ValueError(
                'Acceptation of a registration request cannot be '
                'done when its `Org Group` field is unspecified.')
        assert isinstance(org_request.org_group, models.OrgGroup)
        assert sqla_inspect(org_request.org_group).persistent

    def _verify_org_does_not_exist(self, session, org_request):
        assert isinstance(org_request, models.RegistrationRequest)
        if session.query(models.Org).get(org_request.org_id) is not None:
            raise ValueError(
                'Organization "{}" already exists.'.format(org_request.org_id))

    def _create_org_according_to_request(self, session, org_request):
        assert isinstance(org_request, models.RegistrationRequest)
        assert org_request.id is not None
        assert org_request.org_id is not None
        with g.n6_auth_manage_api_adapter as api:
            api.create_org_and_user_according_to_registration_request(req_id=org_request.id)
        created_org = session.query(models.Org).get(org_request.org_id)
        assert isinstance(created_org, models.Org)
        assert (len(created_org.users) == 1
                and isinstance(created_org.users[0], models.User))
        assert created_org.org_id == org_request.org_id
        assert created_org.users[0].login == org_request.email

    def _after_status_transition_to_accepted(self,
                                             org_request,
                                             old_status,
                                             target_status,
                                             concerned_org_id):
        assert isinstance(org_request, models.RegistrationRequest)
        flash('Registration request accepted. Organization '
              '"{}" created.'.format(concerned_org_id))
        LOGGER.info('Successfully changed status of %a - from %a to %a. '
                    'Successfully added organization %a.',
                    org_request,
                    ascii_str(old_status),
                    ascii_str(target_status),
                    ascii_str(concerned_org_id))
        self.try_to_send_mail_notices(notice_key='new_org_and_user_created',
                                      user_login=org_request.email)

    def _after_status_transition_to_other(self,
                                          org_request,
                                          old_status,
                                          target_status,
                                          concerned_org_id):
        assert isinstance(org_request, models.RegistrationRequest)
        flash('Status of the registration request changed from '
              '"{}" to "{}".'.format(old_status, target_status))
        LOGGER.info('Successfully changed status of %a - from %a to %a',
                    org_request,
                    ascii_str(old_status),
                    ascii_str(target_status))


class _OrgConfigUpdateRequestStatusTransitionHandlerKit(_BaseStatusTransitionHandlerKit):

    def _before_status_transition_to_being_processed(self, org_request, old_status, target_status):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        super(_OrgConfigUpdateRequestStatusTransitionHandlerKit,
              self)._before_status_transition_to_being_processed(org_request,
                                                                 old_status,
                                                                 target_status)
        self._verify_no_other_pending_update_request(org_request)

    def _verify_no_other_pending_update_request(self, org_request):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        pending_update_request = org_request.org.pending_config_update_request
        if pending_update_request is not None and pending_update_request is not org_request:
            raise ValueError(
                'An organization config update request cannot be '
                'made the pending one (by switching its status to '
                '"being processed") when another config update '
                'request related to the same organization is already '
                'the pending one (i.e., has its status set to "new" '
                'or "being processed").')

    def _before_status_transition_to_discarded(self, org_request, old_status, target_status):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        super(_OrgConfigUpdateRequestStatusTransitionHandlerKit,
              self)._before_status_transition_to_discarded(org_request,
                                                           old_status,
                                                           target_status)
        self._verify_update_request_is_the_pending_one(org_request)
        self._remember_org_config_info(org_request)

    def _before_status_transition_to_accepted(self, org_request, old_status, target_status):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        super(_OrgConfigUpdateRequestStatusTransitionHandlerKit,
              self)._before_status_transition_to_accepted(org_request,
                                                          old_status,
                                                          target_status)
        self._verify_update_request_is_the_pending_one(org_request)
        self._remember_org_config_info(org_request)
        self._update_org_according_to_request(org_request)

    def _verify_update_request_is_the_pending_one(self, org_request):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        if org_request.org.pending_config_update_request is not org_request:
            raise AssertionError(
                'The active organization config update request {!a} '
                'is not the currently pending update request of the '
                '{!a} organization!'.format(org_request,
                                            org_request.org))

    def _remember_org_config_info(self, org_request):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        with g.n6_auth_manage_api_adapter as api:
            g.n6_org_config_info = oc_info = api.get_org_config_info(org_id=org_request.org_id)
            assert oc_info.get('update_info') is not None

    def _update_org_according_to_request(self, org_request):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        assert org_request.id is not None
        with g.n6_auth_manage_api_adapter as api:
            api.update_org_according_to_org_config_update_request(req_id=org_request.id)

    def _after_status_transition_to_accepted(self,
                                             org_request,
                                             old_status,
                                             target_status,
                                             concerned_org_id):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        flash('Organization config update request accepted. '
              'Organization "{}" updated.'.format(concerned_org_id))
        LOGGER.info('Successfully changed status of %a - from %a to %a. '
                    'Successfully updated organization %a.',
                    org_request,
                    ascii_str(old_status),
                    ascii_str(target_status),
                    ascii_str(concerned_org_id))
        assert org_request.id is not None
        assert g.n6_org_config_info is not None
        assert g.n6_org_config_info['org_id'] == concerned_org_id
        self.try_to_send_mail_notices(notice_key='org_config_update_applied',
                                      req_id=org_request.id)

    def _after_status_transition_to_other(self,
                                          org_request,
                                          old_status,
                                          target_status,
                                          concerned_org_id):
        assert isinstance(org_request, models.OrgConfigUpdateRequest)
        flash('Status of the organization config update request changed '
              'from "{}" to "{}".'.format(old_status, target_status))
        LOGGER.info('Successfully changed status of %a - from %a to %a',
                    org_request,
                    ascii_str(old_status),
                    ascii_str(target_status))
        if target_status == _STATUS_DISCARDED:
            assert org_request.id is not None
            assert g.n6_org_config_info is not None
            assert g.n6_org_config_info['org_id'] == concerned_org_id
            self.try_to_send_mail_notices(notice_key='org_config_update_rejected',
                                          req_id=org_request.id)

    def get_notice_data(self, req_id) -> dict:
        notice_data = g.n6_org_config_info
        notice_data['update_info']['update_request_id'] = req_id
        return notice_data

    def get_notice_recipients(self, notice_data: dict) -> Iterable[str]:
        with g.n6_auth_manage_api_adapter as api:
            return api.get_org_user_logins(org_id=notice_data['org_id'],
                                           only_nonblocked=True)

    def get_notice_lang(self, notice_data: dict) -> Union[str, None]:
        return notice_data['notification_language']  # TODO?: separate per-user setting?...


#
# Public stuff (used in `n6adminpanel.app`)
#

ACTIONS_FIELD_NAME = _ID_NAME_OF_TARGET_STATUS_INPUT

ACTIONS_FIELD_FOR_REGISTRATION = StringField(
    label='',
    id=_ID_NAME_OF_TARGET_STATUS_INPUT,
    widget=_OrgRequestActionsWidget(
        accept_button_text='Accept and create the organization'))

ACTIONS_FIELD_FOR_ORG_CONFIG_UPDATE = StringField(
    label='',
    id=_ID_NAME_OF_TARGET_STATUS_INPUT,
    widget=_OrgRequestActionsWidget(
        accept_button_text='Accept and apply the organization config update',
        discard_button_text='Reject the organization config update'))

registration_request_handler_kit = _RegistrationRequestStatusTransitionHandlerKit()
org_config_update_request_handler_kit = _OrgConfigUpdateRequestStatusTransitionHandlerKit()

#  Copyright (c) 2021 NASK. All rights reserved.

from collections.abc import Iterable
from typing import Union

from flask import (
    flash,
    g,
)

from n6lib.auth_db.api import AuthDatabaseAPILookupError
from n6lib.common_helpers import ascii_str


class NoRecipients(Exception):
    pass


class MailNoticesMixin(object):

    def try_to_send_mail_notices(self, notice_key, **get_notice_data_kwargs):
        if not g.n6_mail_notices_api.is_active(notice_key):
            msg = ('No e-mail notices sent as they are not configured '
                   'for notice_key={!a}.'.format(ascii_str(notice_key)))
            flash(msg, 'warning')
            return
        try:
            notice_data = self.get_notice_data(**get_notice_data_kwargs)
            notice_recipients = list(self.get_notice_recipients(notice_data))
            if not notice_recipients:
                raise NoRecipients('no matching non-blocked user(s) could be found')
        except NoRecipients as exc:
            flash(f'No e-mail notices could be sent because {exc}!', 'error')
            return
        notice_lang = self.get_notice_lang(notice_data)
        assert notice_lang is None or isinstance(notice_lang, str) and len(notice_lang) == 2
        gathered_ok_recipients = []
        with g.n6_mail_notices_api.dispatcher(notice_key,
                                              suppress_and_log_smtp_exc=True) as dispatch:
            for email in notice_recipients:
                ok_recipients, _ = dispatch(email, notice_data, notice_lang)
                if ok_recipients:
                    gathered_ok_recipients.extend(ok_recipients)
                else:
                    msg = 'Failed to send an e-mail notice to {}!'.format(ascii_str(email))
                    flash(msg, 'warning')
        if gathered_ok_recipients:
            recipients_str = ', '.join(map(ascii_str, gathered_ok_recipients))
            flash('E-mail notices sent to: {}.'.format(recipients_str))
        else:
            flash('No e-mail notices could be sent!', 'error')

    # (The following hooks can be overridden in subclasses.)

    def get_notice_data(self, user_login) -> dict:
        try:
            with g.n6_auth_manage_api_adapter as api:
                if api.is_user_blocked(user_login):
                    raise NoRecipients('the user {user_login!a} is blocked')
                user_and_org_basic_info = api.get_user_and_org_basic_info(user_login)
        except AuthDatabaseAPILookupError:
            raise NoRecipients('the user {user_login!a} does not exist')
        return dict(
            user_and_org_basic_info,
            user_login=user_login)

    def get_notice_recipients(self, notice_data: dict) -> Iterable[str]:
        return [notice_data['user_login']]

    def get_notice_lang(self, notice_data: dict) -> Union[str, None]:
        return notice_data['lang']

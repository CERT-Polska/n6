# Copyright (c) 2015-2025 NASK. All rights reserved.

import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from math import trunc

import redis
from dateutil.easter import easter
from jinja2 import (
    Environment,
    FileSystemLoader,
)

from n6lib.auth_api import AuthAPI
from n6lib.config import ConfigMixin
from n6lib.datetime_helpers import parse_python_formatted_datetime
from n6lib.log_helpers import get_logger, logging_configured

LOGGER = get_logger(__name__)


class NotifierTemplateError(Exception):
     """Raised when render template failed."""


def raise_helper(msg):
    raise NotifierTemplateError(msg)


class Notifier(ConfigMixin):

    config_spec = '''
    [notifier]
    templates_dir_path
    server_smtp_host
    fromaddr
    regular_days_off = :: list_of_str
    movable_days_off_by_easter_offset = :: list_of_int
    default_notifications_language = EN

    [notifier_redis]
    redis_host
    redis_port
    redis_db
    redis_save
    '''

    def __init__(self):
        LOGGER.info("Starting...")
        config_full = self.get_config_full()
        self.config_redis = config_full['notifier_redis']
        self.config = config_full['notifier']
        redis_host = self.config_redis['redis_host']
        redis_port = int(self.config_redis['redis_port'])
        redis_db_number = int(self.config_redis['redis_db'])
        LOGGER.info("Starting Redis connection...")
        self.pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=redis_db_number, decode_responses=True)
        self.redis_db = redis.StrictRedis(connection_pool=self.pool)
        self.redis_db.config_set('save', self.config_redis['redis_save'])
        self.template_work_dir = self.config['templates_dir_path']
        self.env = Environment(
            loader=FileSystemLoader(self.template_work_dir),
            extensions=['jinja2.ext.do'],
        )
        self.template_name = 'notifier_template'
        self.server_smtp_host = self.config['server_smtp_host']
        self.fromaddr = self.config['fromaddr']
        self.auth_api = AuthAPI()
        with self.auth_api:
            self.clients_notification_config = self.auth_api.get_org_ids_to_notification_configs()
        self.is_business_day = self.get_is_business_day(datetime.now().date())

    def run(self):
        for client_org_name, client_params in self.clients_notification_config.items():
            if not self.noti_today(client_params['n6email-notifications-business-days-only']):
                continue
            client_noti_times = client_params.get('n6email-notifications-times')
            client_email_address = client_params.get('n6email-notifications-address')
            if not client_noti_times or not client_email_address:
                LOGGER.warning(
                    'n6email-notifications-times and/or n6email-notifications-address'
                    'for %a is empty.', client_org_name)
                continue
            last_send_dt = self.get_last_send_time(client_org_name)
            current_state_db = self.get_raw_counter(client_org_name)
            if not current_state_db:
                LOGGER.info("Did not send a message, no %a data in database.", client_org_name)
                continue
            now_dt = datetime.now().replace(microsecond=0)
            if not last_send_dt:  # only first run
                self.set_last_send_time(client_org_name, now_dt)
                LOGGER.info("Did not send a message, this is first run for %a.", client_org_name)
            elif self.notify_client(client_org_name, client_noti_times, now_dt):
                last_state_db = self.get_last_send_counter(client_org_name)
                counter_to_send = self.get_counter_to_send(current_state_db, last_state_db)
                if counter_to_send:
                    client_name = client_params['name']
                    client_n6stream_api_enabled = client_params['n6stream-api-enabled']
                    notifications_language = client_params.get(
                        'n6email-notifications-language',
                        self.config['default_notifications_language']
                    ).lower()
                    try:
                        message = self.get_template(counter_to_send,
                                                    last_send_dt,
                                                    now_dt,
                                                    client_name,
                                                    client_org_name,
                                                    client_n6stream_api_enabled,
                                                    notifications_language)
                        self.send_message(html_message=message, client_emails=client_email_address)
                        self.set_last_send_counter(client_org_name, current_state_db)
                        self.set_time_min(client_org_name, current_state_db)
                        self.set_last_send_time(client_org_name, now_dt)
                        self.redis_db.hdel(client_org_name, '_time')
                        LOGGER.info('Successfully sent a message to %a.', client_org_name)
                    except NotifierTemplateError as exc:
                        LOGGER.warning(exc)
                        continue
        LOGGER.info("Exiting...")

    def set_time_min(self, client, current_state_db):
        _tmin = current_state_db['_tmax']
        self.redis_db.hset(client, '_tmin', _tmin)

    def notify_client(self, client, hours_list, now_dt):
        last_send = self.get_last_send_time(client)
        inc_date = now_dt.date()
        reverse_hours_list = hours_list[::-1]
        while True:
            for noti_time in reverse_hours_list:
                noti_time_dt = datetime.combine(inc_date, noti_time)
                if last_send > noti_time_dt:
                    LOGGER.info("This is not %a notification time.", client)
                    return None
                elif last_send < noti_time_dt <= now_dt:
                    return True
            inc_date = self.get_previous_business_day_from_date(inc_date)

    def get_previous_business_day_from_date(self, date_obj: datetime.date):
        while True:
            date_obj = date_obj - timedelta(days=1)
            if self.get_is_business_day(date_obj):
                return date_obj

    def get_counter_to_send(self, raw_dict, tmp_dict):
        _to_int = self._to_int
        result_dict = {}
        if tmp_dict:
            for key, raw_item in raw_dict.items():
                if key.startswith('_'):
                    result_dict[key] = raw_item
                    continue
                raw_item = _to_int(raw_item)
                tmp_item = tmp_dict.get(key)
                if tmp_item is None:
                    result_dict[key] = raw_item
                else:
                    item_diff = raw_item - _to_int(tmp_item)
                    if item_diff > 0:
                        result_dict[key] = item_diff
        else:
            for key, raw_item in raw_dict.items():
                if key.startswith('_'):
                    result_dict[key] = raw_item
                else:
                    result_dict[key] = _to_int(raw_item)
        for key in result_dict.keys():
            if result_dict and not key.startswith('_'):
                return result_dict

    @staticmethod
    def _to_int(item):
        # XXX: What the actual type of `item` is? (This check and one of
        #      the following branches may be unnecessary as never used...)
        if isinstance(item, (bytes, bytearray, str)):
            # If it's a string, let's parse it as an integer.
            return int(item)     # type: int
        else:
            # If it's a number, let's be explicit that we truncate, not
            # round up or what... (see the fragment: "Conversion from
            # floating point to integer may round or truncate as in C"
            # of the document: https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex)
            return trunc(item)   # type: int

    def get_last_send_time(self, client):
        client_dt_name = client + '_last_send_dt'
        last_send_time = self.redis_db.get(client_dt_name)
        if last_send_time:
            return datetime.strptime(last_send_time, "%Y-%m-%d %H:%M:%S")
        return None

    def set_last_send_time(self, client, now_dt):
        client_dt_name = client + '_last_send_dt'
        self.redis_db.set(client_dt_name, now_dt)

    def set_last_send_counter(self, client, raw_data):
        client_ls = client + '_last_send_counter'
        self.redis_db.hmset(client_ls, raw_data)

    def get_last_send_counter(self, client):
        client_ls = client + '_last_send_counter'
        return self.redis_db.hgetall(client_ls)

    def get_raw_counter(self, client):
        client_data = self.redis_db.hgetall(client)
        if client_data:
            return client_data
        return None

    def get_template(self, msg, last_send_time_dt, now_dt, client_name, client_org_name,
                     client_n6stream_api_enabled, notifications_language):
        template = self.env.get_template(self.template_name, globals=self._get_template_globals())
        tmin = self.get_iso_format_time(msg.pop('_tmin'))
        tmax = self.get_iso_format_time(msg.pop('_tmax'))
        time = self.get_iso_format_time(msg.pop('_time'))
        output_from_parsed_template = template.render(
            counter=msg,
            last_send_time_dt=last_send_time_dt,
            now_dt=now_dt,
            modified_min=tmin,
            modified_max=tmax,
            time_min=time,
            client_name=client_name,
            client_org_name=client_org_name,
            client_n6stream_api_enabled=client_n6stream_api_enabled,
            notifications_language=notifications_language,
        )
        return output_from_parsed_template

    def get_iso_format_time(self, _time):
        return datetime.isoformat(parse_python_formatted_datetime(_time).replace(microsecond=0))

    def send_message(self, html_message, client_emails):
        for client_address in client_emails:
            LOGGER.info("Sending email notification to address: %a ...", client_address)
            subject, body = self.get_subject_and_body(html_message)
            msg = MIMEText(body, _charset="UTF-8")
            msg['To'] = client_address
            msg['From'] = self.fromaddr
            msg['Subject'] = subject
            server = smtplib.SMTP(self.server_smtp_host)
            server.sendmail(self.fromaddr, client_address, msg.as_string())
            server.quit()

    def get_subject_and_body(self, html):
        body_pattern = "<body>(.*)</body>"
        msg_body = re.findall(body_pattern, html, re.DOTALL)[0].strip()
        subject_pattern = '<subject>(.*)</subject>'
        msg_title = re.findall(subject_pattern, html, re.DOTALL)[0].strip()
        return msg_title, msg_body

    def get_is_business_day(self, date_obj: datetime.date):
        if date_obj.isoweekday() in (6, 7):
            return False
        all_day_off = self.get_all_day_off_as_dt_list(date_obj)
        if date_obj in all_day_off:
            return False
        return True

    def get_all_day_off_as_dt_list(self, today):
        all_days_off = []
        _year = today.year
        for day_off in self.config['regular_days_off']:
            try:
                day_off_dt = datetime.strptime('-'.join([str(_year), day_off]), "%Y-%m-%d").date()
            except ValueError:
                LOGGER.critical('Looks like provided time: %a does not match "mm-dd" format. '
                                'Check configuration file.', day_off)
                sys.exit(1)
            all_days_off.append(day_off_dt)
        movable_days_off = list(
            easter(_year) + timedelta(days=offset)
            for offset in self.config['movable_days_off_by_easter_offset']
        )
        all_days_off += movable_days_off
        return all_days_off

    def noti_today(self, notifications_business_days_only):
        if self.is_business_day:
            return True
        elif not notifications_business_days_only:
            return True
        else:
            return False

    def prepare_and_send_sample_email(self, recipient, notifications_language, template_name):
        """
        Use this function only to prepare and send a **sample** message(s).

        Args/kwargs:

            `recipient` (str):
                The email address of the recipient (e.g. username@localhost).

            `notifications_language` (str):
                The language code for notifications.

            `template_name` (str):
                The name of the template that will be tested.

        Requirements:

            - Auth DB must be running.
            - Redis must be running.

        **Note:** this method (tool) is intended for developer use only.
        To test the template, use the `notifier_templates_renderer`
        (N6DataPipeline/n6datapipeline/aux/notifier_templates_renderer.py).
        """
        tmp_last_dt = "2015-11-23 15:17:01"
        tmp_now_dt = "2015-11-23 12:17:01"
        msg = {
            "_tmin": "2015-11-19 12:15:17",
            "_tmax": "2015-11-19 12:15:17",
            "_time": "2015-11-19 12:15:17",
            "bots": 100,
            "cnc": 100,
            "malurl": 100,
            "phish": 100,
            "tst": 100,
            "tor": 100,
            "empty": 555,
        }
        toaddrs = [recipient]
        self.template_name = template_name
        name = 'TEST ORG'
        name_org = 'test.org'
        client_n6stream_api_enabled = True
        tmp_msg = self.get_template(msg=msg,
                                    last_send_time_dt=tmp_last_dt,
                                    now_dt=tmp_now_dt,
                                    client_name=name,
                                    client_org_name=name_org,
                                    client_n6stream_api_enabled=client_n6stream_api_enabled,
                                    notifications_language=notifications_language)
        self.send_message(tmp_msg, client_emails=toaddrs)

    @staticmethod
    def _get_template_globals():
        return {
            'template_raise': raise_helper,
        }


def main():
    with logging_configured():
        n = Notifier()
        n.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Use this only to prepare and send sample message.')
    parser.add_argument('recipient', help='Sample email message recipient (e.g: user@localhost)')
    parser.add_argument('-l', default='EN', help='Language version (default: EN).')
    parser.add_argument('-t', default='test_template', help='Template name (default: test_template).')
    args = parser.parse_args()
    recipient = args.recipient.strip()
    notifications_language = args.l.lower()
    template_name = args.t
    with logging_configured():
        n = Notifier()
        n.prepare_and_send_sample_email(recipient, notifications_language, template_name)

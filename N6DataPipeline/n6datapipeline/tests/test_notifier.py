# Copyright (c) 2015-2025 NASK. All rights reserved.

import unittest
from datetime import datetime

from unittest import mock
from unittest.mock import patch
import n6datapipeline.notifier as notifier
from n6datapipeline.notifier import Notifier


class TestNotifier(unittest.TestCase):

    @patch('n6datapipeline.notifier.AuthAPI')
    @patch('n6datapipeline.notifier.redis', return_value=None)
    @patch('n6datapipeline.notifier.redis.StrictRedis', return_value={'config_set': None})
    @patch('n6datapipeline.notifier.ConfigMixin.get_config_full', return_value={
        'notifier_redis': {
            'redis_host': 'host_my',
            'redis_port': 6379,
            'redis_db': 4,
            'redis_save': '900 1 60 200',
        },
        'notifier': {
            'templates_dir_path': 'dfsdfsd',
            'server_smtp_host': 'host4',
            'fromaddr': 'email@example.com',
            'regular_days_off': ['01-01', '01-06', '05-01', '05-03', '08-15', '11-01', '11-11', '12-25', '12-26'],
            'movable_days_off_by_easter_offset': [1, 60],
            'default_notifications_language': 'EN'
        },
    })
    def setUp(self, *args):
        self.datetime_patcher = mock.patch.object(
            notifier, 'datetime',
            mock.Mock(wraps=datetime)
        )
        self.notifi_ob = Notifier()

    def test_get_last_send_time(self):
        # normal
        self.notifi_ob.redis_db.get = mock.MagicMock(return_value='1234-01-11 12:12:12')
        actual = self.notifi_ob.get_last_send_time('cli_1')
        self.notifi_ob.redis_db.get.assert_called_once_with('cli_1_last_send_dt')
        self.assertEqual(actual, datetime(1234, 1, 11, 12, 12, 12))
        self.assertEqual(self.notifi_ob.redis_db.get.call_count, 1)
        # Non exists
        self.notifi_ob.redis_db.get = mock.MagicMock(return_value=None)
        actual = self.notifi_ob.get_last_send_time('cli_1')
        self.notifi_ob.redis_db.get.assert_called_once_with('cli_1_last_send_dt')
        self.assertEqual(actual, None)
        self.assertEqual(self.notifi_ob.redis_db.get.call_count, 1)

    def test_get_raw_counter(self):
        # Non exist
        client = 'c10'
        self.notifi_ob.redis_db.hgetall = mock.MagicMock(return_value=None)
        result = self.notifi_ob.get_raw_counter(client)
        self.assertEqual(result, None)
        # Exist
        client = 'c11'
        cont_dict = {'e1': '10', 'e3': '100'}
        self.notifi_ob.redis_db.hgetall = mock.MagicMock(return_value=cont_dict)
        result = self.notifi_ob.get_raw_counter(client)
        self.assertDictEqual(result, {'e3': '100', 'e1': '10'})

    def test_set_last_send_counter(self):
        cli = 'c11'
        cli_ls = cli + '_last_send_counter'
        tmp_dict = {'e1': '100', 'e20': '200'}
        self.notifi_ob.redis_db.hmset = mock.MagicMock()
        self.notifi_ob.set_last_send_counter(cli, tmp_dict)
        self.notifi_ob.redis_db.hmset.assert_called_once_with(cli_ls, tmp_dict)

    def test_get_last_send_counter(self):
        cli = 'c100'
        cli_ls = cli + '_last_send_counter'
        tmp_dic = {'e11': '2', 'kk': '12'}
        self.notifi_ob.redis_db.hgetall = mock.MagicMock(return_value=tmp_dic)
        result = self.notifi_ob.get_last_send_counter(cli)
        self.notifi_ob.redis_db.hgetall.assert_called_once_with(cli_ls)
        self.assertEqual(result, tmp_dic)

    def test_notify_client(self):
        # normal, it is notification time
        client = 'cli1'
        ldap_list = self._get_datetime_time('6:00', '12:00', '20:00')
        now_string = "2015-11-17 12:03:00"
        self.notifi_ob.redis_db.get = mock.MagicMock(return_value='2015-11-17 06:03:00')
        now_dt = datetime.strptime(now_string, "%Y-%m-%d %H:%M:%S")
        result = self.notifi_ob.notify_client(client, ldap_list, now_dt)
        self.assertTrue(result)
        # normal, it is not notification time
        client = 'cli2'
        client_dt = client + '_last_send_dt'
        ldap_list = self._get_datetime_time('6:00', '12:00', '20:00')
        now_string = "2015-11-17 4:03:00"
        now_dt = datetime.strptime(now_string, "%Y-%m-%d %H:%M:%S")
        self.notifi_ob.redis_db.get = mock.MagicMock(return_value="2015-11-16 20:03:00")
        result = self.notifi_ob.notify_client(client, ldap_list, now_dt)
        self.notifi_ob.redis_db.get.assert_called_once_with(client_dt)
        self.assertIsNone(result, None)
        # it is notification time (20:00 yesterday), last send time 15:03 yesterday, now it is 6:00
        client = 'cli2'
        client_dt = client + '_last_send_dt'
        ldap_list = self._get_datetime_time('6:00', '12:00', '20:00')
        now_string = "2015-11-17 4:03:00"
        now_dt = datetime.strptime(now_string, "%Y-%m-%d %H:%M:%S")
        self.notifi_ob.redis_db.get = mock.MagicMock(return_value="2015-11-16 15:03:00")
        result = self.notifi_ob.notify_client(client, ldap_list, now_dt)
        self.notifi_ob.redis_db.get.assert_called_once_with(client_dt)
        self.assertTrue(result)

    def test_get_counter_to_send(self):
        raw_dict = {'c1': '12', 'c2': '34', 'c3': '40', 'c4': '666', '_tmin': 'tmin',
                    '_tmax': 'tmax'}
        tmp_dict = {'c1': '6', 'c2': '10', 'c3': '32'}
        expected_dict = {'c1': 6, 'c2': 24, 'c3': 8, 'c4': 666, '_tmin': 'tmin', '_tmax': 'tmax'}
        result = self.notifi_ob.get_counter_to_send(raw_dict, tmp_dict)
        self.assertEqual(expected_dict, result)

        raw_dict = {'c1': '12', 'c2': '34', 'c3': '40', 'c4': '666', '_tmin': 'tmin',
                    '_tmax': 'tmax'}
        tmp_dict = None
        expected_dict = {'c1': 12, 'c2': 34, 'c3': 40, 'c4': 666, '_tmin': 'tmin', '_tmax': 'tmax'}
        result = self.notifi_ob.get_counter_to_send(raw_dict, tmp_dict)
        self.assertEqual(expected_dict, result)

        raw_dict = {'c1': '12', 'c2': '34', 'c3': '40', 'c4': '666', '_tmin': 'tmin',
                    '_tmax': 'tmax'}
        tmp_dict = {'c1': '12', 'c2': '34', 'c3': '40', 'c4': '666', '_tmin': 'tmin',
                    '_tmax': 'tmax'}
        expected_dict = None
        result = self.notifi_ob.get_counter_to_send(raw_dict, tmp_dict)
        self.assertEqual(expected_dict, result)

    def test_run_missing_ldap_client_info(self):
        ldap_config = {
            'cli1': {
                'n6email-notifications-times': [],
                'n6email-notifications-address': ['dd'],
                'n6email-notifications-business-days-only': False,
            },
        }
        self.notifi_ob.clients_notification_config = ldap_config
        self.notifi_ob.get_last_send_time = mock.MagicMock()
        result_call = self.notifi_ob.get_last_send_time.called
        self.notifi_ob.run()
        self.assertFalse(result_call)

        ldap_config = {
            'cli1': {
                'n6email-notifications-times': ['a'],
                'n6email-notifications-address': [],
                'n6email-notifications-business-days-only': False
            },
        }
        self.notifi_ob.clients_notification_config = ldap_config
        self.notifi_ob.get_last_send_time = mock.MagicMock()
        result_call = self.notifi_ob.get_last_send_time.called
        self.notifi_ob.run()
        self.assertFalse(result_call)

        ldap_config = {
            'cli1': {
                'n6email-notifications-times': [],
                'n6email-notifications-address': [],
                'n6email-notifications-business-days-only': False,
            },
        }
        self.notifi_ob.clients_notification_config = ldap_config
        self.notifi_ob.get_last_send_time = mock.MagicMock()
        result_call = self.notifi_ob.get_last_send_time.called
        self.notifi_ob.run()
        self.assertFalse(result_call)

    def test_run_empty_last_send_time(self):
        # first run, last send time is empty
        noti_times_list = self._get_datetime_time('12:12', '15:00')
        emails_list = ['mail@mail.mail']
        ldap_config = {
            'cli1': {
                'n6email-notifications-times': noti_times_list,
                'n6email-notifications-address': emails_list,
                'n6email-notifications-business-days-only': False,
            },
        }
        self.notifi_ob.clients_notification_config = ldap_config
        with self.datetime_patcher as self.mocked_datetime:
            now_dt = datetime(2015, 12, 7, 6, 0, 0)
            self.mocked_datetime.now.return_value = now_dt
            self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=None)
            self.notifi_ob.set_last_send_time = mock.MagicMock()
            self.notifi_ob.notify_client = mock.MagicMock()
            result_call_notify_client = self.notifi_ob.notify_client.called
            result_call_set_last_send_time = self.notifi_ob.set_last_send_time.called
            self.notifi_ob.run()
            self.assertFalse(result_call_notify_client)
            self.assertFalse(result_call_set_last_send_time)

    def test_run_normal(self):
        # normal, it is notification time
        with self.datetime_patcher as self.mocked_datetime:
            now_dt = datetime(2015, 12, 7, 12, 15, 0)
            self.mocked_datetime.now.return_value = now_dt
            last_send_dt = datetime(2015, 12, 6, 17, 15, 0)
            noti_times_list = self._get_datetime_time('12:12', '15:00')
            emails_list = ['mail@mail.mail']
            ldap_config = {
                'cli1': {
                    'n6email-notifications-times': noti_times_list,
                    'n6email-notifications-address': emails_list,
                    'name': 'ExampleOrg',
                    'n6stream-api-enabled': True,
                    'n6email-notifications-business-days-only': False,
                    'n6email-notifications-language': 'pl',
                },
            }
            self.notifi_ob.clients_notification_config = ldap_config
            self.mocked_datetime.now.return_value = now_dt
            self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=last_send_dt)
            current_state_db = {'_tmin': 'tmin', '_tmax': 'tmax', 'tor': '222', 'spam': '333'}
            self.notifi_ob.get_raw_counter = mock.MagicMock(return_value=current_state_db)
            self.notifi_ob.set_last_send_time = mock.MagicMock()
            self.notifi_ob.get_last_send_counter = mock.MagicMock(return_value={})
            self.notifi_ob.get_template = mock.MagicMock(return_value="test message")
            self.notifi_ob.send_message = mock.MagicMock()
            self.notifi_ob.set_last_send_counter = mock.MagicMock()
            self.notifi_ob.set_time_min = mock.MagicMock()
            self.notifi_ob.run()
            self.notifi_ob.get_raw_counter.assert_called_once_with('cli1')
            msg = {'_tmin': 'tmin', '_tmax': 'tmax', 'tor': 222, 'spam': 333}
            self.notifi_ob.get_template.assert_called_once_with(
                msg, last_send_dt, now_dt, 'ExampleOrg', 'cli1', True, 'pl')
            self.notifi_ob.send_message.assert_called_once_with(
                html_message='test message', client_emails=emails_list)
            self.notifi_ob.set_last_send_counter.assert_called_once_with('cli1', current_state_db)
            self.notifi_ob.set_time_min.assert_called_once_with('cli1', current_state_db)
            self.notifi_ob.set_last_send_time.assert_called_once_with('cli1', now_dt)

    def test_run_not_notificatin_time(self):
        # normal, it is not notification time
        with self.datetime_patcher as self.mocked_datetime:
            noti_times_list = self._get_datetime_time('12:12', '15:00')
            now_dt = datetime(2015, 12, 7, 12, 15, 0)
            last_send_dt = datetime(2015, 12, 7, 12, 13, 0)
            self.mocked_datetime.now.return_value = now_dt
            emails_list = ['mail@mail.mail']
            ldap_config = {
                'cli1': {
                    'n6email-notifications-times': noti_times_list,
                    'n6email-notifications-address': emails_list,
                    'n6email-notifications-business-days-only': False,
                },
            }
            self.notifi_ob.clients_notification_config = ldap_config
            self.mocked_datetime.now.return_value = now_dt
            self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=last_send_dt)
            self.notifi_ob.get_raw_counter = mock.MagicMock()
            self.notifi_ob.set_last_send_time = mock.MagicMock()
            self.notifi_ob.get_template = mock.MagicMock()
            self.notifi_ob.send_message = mock.MagicMock()
            self.notifi_ob.set_last_send_counter = mock.MagicMock()
            self.notifi_ob.set_time_min = mock.MagicMock()
            result_call_get_raw_counter = self.notifi_ob.get_raw_counter.called
            result_call_send_message = self.notifi_ob.send_message.called
            result_call_set_last_send_counter = self.notifi_ob.set_last_send_counter.called
            result_call_set_time_min = self.notifi_ob.set_time_min.called
            result_call_set_last_send_time = self.notifi_ob.set_last_send_time.called
            self.notifi_ob.run()
            self.assertFalse(result_call_get_raw_counter)
            self.assertFalse(result_call_send_message)
            self.assertFalse(result_call_set_last_send_counter)
            self.assertFalse(result_call_set_time_min)
            self.assertFalse(result_call_set_last_send_time)

    def test_run_empty_current_state_db(self):
        with self.datetime_patcher as self.mocked_datetime:
            noti_times_list = self._get_datetime_time('12:12', '15:00')
            now_dt = datetime(2015, 12, 7, 12, 15, 0)
            last_send_dt = datetime(2015, 12, 7, 12, 13, 0)
            self.mocked_datetime.now.return_value = now_dt
            emails_list = ['mail@mail.mail']
            ldap_config = {
                'cli1': {
                    'n6email-notifications-times': noti_times_list,
                    'n6email-notifications-address': emails_list,
                    'n6email-notifications-business-days-only': True,
                },
            }
            self.notifi_ob.clients_notification_config = ldap_config
            self.mocked_datetime.now.return_value = now_dt
            self.notifi_ob.get_raw_counter = mock.MagicMock(return_value=None)
            self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=last_send_dt)
            self.notifi_ob.set_last_send_time = mock.MagicMock()
            self.notifi_ob.notify_client = mock.MagicMock()
            result_call_set_last_send_time = self.notifi_ob.set_last_send_time.called
            result_call_notify_client = self.notifi_ob.notify_client.called
            self.notifi_ob.run()
            self.assertFalse(result_call_set_last_send_time)
            self.assertFalse(result_call_notify_client)

    def test_run_business_day_noti_today_yes(self):
        # business day
        # cli business day only
        emails_list = ['mail@mail.mail']
        noti_times_list = self._get_datetime_time('12:12', '15:00')
        ldap_config = {
            'cli1': {
                'n6email-notifications-times': noti_times_list,
                'n6email-notifications-address': emails_list,
                'n6email-notifications-business-days-only': True,
            },
        }
        # is business day - monday
        self.notifi_ob.clients_notification_config = ldap_config
        self.notifi_ob.noti_today = mock.MagicMock(return_value=True)
        self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=None)
        self.notifi_ob.run()
        self.notifi_ob.get_last_send_time.assert_called_once_with('cli1')

    def test_run_business_day_noti_today_no(self):
        # business day
        # cli business day only
        emails_list = ['mail@mail.mail']
        noti_times_list = self._get_datetime_time('12:12', '15:00')
        ldap_config = {
            'cli1': {
                'n6email-notifications-times': noti_times_list,
                'n6email-notifications-address': emails_list,
                'n6email-notifications-business-days-only': True,
            },
        }
        # is business day - monday
        self.notifi_ob.clients_notification_config = ldap_config
        self.notifi_ob.noti_today = mock.MagicMock(return_value=False)
        self.notifi_ob.get_last_send_time = mock.MagicMock(return_value=None)
        result_call = self.notifi_ob.get_last_send_time.called
        self.notifi_ob.run()
        expected_call = False
        self.assertEqual(result_call, expected_call)

    def test_get_iso_format_time(self):
        # _time without microseconds
        time_str = '2012-01-01 11:55:12'
        result = self.notifi_ob.get_iso_format_time(time_str)
        exppect_dt = datetime.strptime('2012-01-01 11:55:12', '%Y-%m-%d %H:%M:%S')
        expect_iso = datetime.isoformat(exppect_dt)
        self.assertEqual(expect_iso, result)

        # _time with microseconds
        time_str = '2015-11-25 23:11:45.784'
        result = self.notifi_ob.get_iso_format_time(time_str)
        expect_dt = datetime.strptime('2015-11-25 23:11:45', '%Y-%m-%d %H:%M:%S')
        expect_iso = datetime.isoformat(expect_dt)
        self.assertEqual(expect_iso, result)

    def test__is_business_day_monday_yes(self):
        # is business day - monday
        now_dt = datetime(2016, 12, 5, 12, 15, 0)
        result = self.notifi_ob.get_is_business_day(now_dt.date())
        expect = True
        self.assertEqual(result, expect)

    def test__is_business_day_easter_monday_no(self):
        # is day off Easter monday
        now_dt = datetime(2016, 3, 28, 12, 15, 0)
        result = self.notifi_ob.get_is_business_day(now_dt.date())
        expect = False
        self.assertEqual(result, expect)

    def test__is_business_day_off_from_config_no(self):
        # is day off from config
        now_dt = datetime(2011, 12, 25, 12, 15, 0)
        result = self.notifi_ob.get_is_business_day(now_dt.date())
        expect = False
        self.assertEqual(result, expect)

    def test__is_business_day_sunday_no(self):
        # is day off sunday
        now_dt = datetime(2016, 6, 26, 12, 15, 0)
        result = self.notifi_ob.get_is_business_day(now_dt.date())
        expect = False
        self.assertEqual(result, expect)

    def test_noti_today_is_business_day_notification_every_day(self):
        # it is workday - all cli receive notifications
        self.notifi_ob.is_business_day = True  # business day
        notifications_business_days_only = False  # notification every day
        expected = True  # notification
        result = self.notifi_ob.noti_today(notifications_business_days_only)
        self.assertEqual(result, expected)

    def test_noti_today_is_business_day_notification_only_business_day(self):
        self.notifi_ob.is_business_day = True  # business day
        notifications_business_days_only = True  # notification only business day
        expected = True  # notification
        result = self.notifi_ob.noti_today(notifications_business_days_only)
        self.assertEqual(result, expected)

    def test_noti_today_is_not_business_day_and_noti_every_day(self):
        # it is day off but cli receive notifications every day
        self.notifi_ob.is_business_day = False  # day off
        notifications_business_days_only = False  # notification every day
        expected = True  # notification
        result = self.notifi_ob.noti_today(notifications_business_days_only)
        self.assertEqual(result, expected)

    def test_noti_today_is_not_business_day_and_noti_only_business_day(self):
        self.notifi_ob.is_business_day = False  # day off
        notifications_business_days_only = True  # notification only business day
        expected = False  # pass
        result = self.notifi_ob.noti_today(notifications_business_days_only)
        self.assertEqual(result, expected)

    def _get_datetime_time(self, *args):
        hours_list = []
        for time_ in args:
            t = datetime.strptime(time_, '%H:%M')
            hours_list.append(t.time())
        return hours_list


if __name__ == '__main__':
    unittest.main()

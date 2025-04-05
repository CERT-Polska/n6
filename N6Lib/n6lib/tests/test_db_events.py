# Copyright (c) 2013-2025 NASK. All rights reserved.

import copy
import datetime
import socket
import unittest
from unittest.mock import (
    MagicMock,
    call,
    patch,
    sentinel as sen,
)

import sqlalchemy.orm.attributes
import sqlalchemy.orm.collections
from sqlalchemy import Column
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.common_helpers import PlainNamespace
from n6lib.db_events import (
    _IP_COLUMN_NAMES,
    _NO_IP_PLACEHOLDERS,
    n6ClientToEvent,
    n6NormalizedData,
    make_raw_result_dict,
)
from n6lib.sqlalchemy_related_test_helpers import sqlalchemy_type_to_str
from n6lib.unit_test_helpers import (
    MethodProxy,
    TestCaseMixin,
)


class TestAuxiliaryConstants(unittest.TestCase):

    def test(self):
        self.assertEqual(_IP_COLUMN_NAMES, ('dip', 'ip'))
        self.assertEqual(_NO_IP_PLACEHOLDERS, {'0.0.0.0', 0, -1})


class _SqlaModelTestMixin:

    def _get_column_sql_repr(self, col):
        assert isinstance(self, unittest.TestCase)
        assert isinstance(col, Column)
        assert isinstance(col.nullable, bool)
        r = f'{col.name} {sqlalchemy_type_to_str(col.type)}'
        if not col.nullable:
            r += ' NOT NULL'
        return r


class Test_n6ClientToEvent(_SqlaModelTestMixin, unittest.TestCase):

    def test_class_attrs(self):
        instrumented_attr_names = {
            name for name, obj in vars(n6ClientToEvent).items()
            if isinstance(obj, sqlalchemy.orm.attributes.InstrumentedAttribute)}
        column_names_to_sql_reprs = {
            name: self._get_column_sql_repr(col)
            for name in instrumented_attr_names
            if isinstance(col := getattr(n6ClientToEvent, name).expression, Column)}
        self.assertEqual(
            n6ClientToEvent.__tablename__,
            'client_to_event')
        self.assertEqual(
            instrumented_attr_names,
            {'id', 'time', 'client', 'events'})
        self.assertEqual(
            instrumented_attr_names - {'events'},
            column_names_to_sql_reprs.keys())
        self.assertEqual(
            column_names_to_sql_reprs, {
                'id': 'id BINARY(16) NOT NULL',
                'time': 'time DATETIME NOT NULL',
                'client': 'client VARCHAR(32) NOT NULL',
            })

    def test_init_and_attrs_1(self):
        obj = n6ClientToEvent(
            id=sen.event_id,
            client=sen.some_client_id,
            time='2014-04-01 01:07:42+02:00',                           # noqa
            arbitrary_ignored_keyword_argument=sen.whatever,            # noqa
        )
        self.assertEqual(obj.id, sen.event_id)
        self.assertEqual(obj.client, sen.some_client_id)
        self.assertEqual(obj.time, datetime.datetime(2014, 3, 31, 23, 7, 42))
        self.assertFalse(hasattr(obj, 'arbitrary_ignored_keyword_argument'))

    def test_init_and_attrs_2(self):
        obj = n6ClientToEvent(
            time=datetime.datetime(2014, 3, 31, 23, 7, 42),
        )
        self.assertIsNone(obj.id)
        self.assertIsNone(obj.client)
        self.assertEqual(obj.time, datetime.datetime(2014, 3, 31, 23, 7, 42))

    def test_init_and_attrs_3(self):
        obj = n6ClientToEvent(
            id=None,
            client=None,                                                # noqa
            time=datetime.datetime(
                2014, 4, 1, 1, 7, 42,
                tzinfo=datetime.timezone(datetime.timedelta(hours=2))),
        )
        self.assertIsNone(obj.id)
        self.assertIsNone(obj.client)
        self.assertEqual(obj.time, datetime.datetime(2014, 3, 31, 23, 7, 42))


@expand
class Test_n6NormalizedData(_SqlaModelTestMixin, unittest.TestCase):

    def setUp(self):
        self.mock = MagicMock()
        self.meth = MethodProxy(n6NormalizedData, self.mock)

    def test_class_attrs(self):
        instrumented_attr_names = {
            name for name, obj in vars(n6NormalizedData).items()
            if isinstance(obj, sqlalchemy.orm.attributes.InstrumentedAttribute)}
        column_names_to_sql_reprs = {
            name: self._get_column_sql_repr(obj)
            for name, obj in n6NormalizedData._n6columns.items()}
        self.assertEqual(
            n6NormalizedData.__tablename__,
            'event')
        self.assertEqual(
            instrumented_attr_names, {
                'clients',

                'address',
                'ip',
                'asn',
                'cc',
                ###'ipv6',
                ###'rdns',
                ###'dir',

                'category',
                'confidence',
                'count',
                'custom',
                'dip',
                'dport',
                ###'email',
                'expires',
                'fqdn',
                ###'iban',
                'id',
                'ignored',
                ###'injects',
                'md5',
                'modified',
                'name',
                'origin',
                ###'phone',
                'proto',
                ###'registrar',
                'replaces',
                'restriction',
                'rid',
                'sha1',
                'sha256',
                'source',
                'sport',
                'status',
                'target',
                'time',
                'until',
                'url',
                ###'url_pattern',
                ###'username',
                ###'x509fp_sha1',
            })
        self.assertEqual(
            instrumented_attr_names - {'clients'},
            column_names_to_sql_reprs.keys())
        self.assertEqual(
            column_names_to_sql_reprs, {
                'address': 'address MEDIUMTEXT',
                'ip': 'ip INTEGER UNSIGNED NOT NULL',
                'asn': 'asn INTEGER UNSIGNED',
                'cc': 'cc CHAR(2)',
                'category': (
                    "category ENUM('amplifier','bots','backdoor','cnc',"
                    "'deface','dns-query','dos-attacker','dos-victim','flow',"
                    "'flow-anomaly','fraud','leak','malurl','malware-action','other','phish',"
                    "'proxy','sandbox-url','scam','scanning','server-exploit','spam',"
                    "'spam-url','tor','vulnerable','webinject') NOT NULL"),
                'confidence': "confidence ENUM('low','medium','high') NOT NULL",
                'count': 'count INTEGER UNSIGNED',
                'custom': 'custom MEDIUMTEXT',
                'dip': 'dip INTEGER UNSIGNED NOT NULL',
                'dport': 'dport SMALLINT UNSIGNED',
                'expires': 'expires DATETIME',
                'fqdn': 'fqdn VARCHAR(255)',
                'id': 'id BINARY(16) NOT NULL',
                'ignored': 'ignored BOOL',
                'md5': 'md5 BINARY(16)',
                'modified': 'modified DATETIME NOT NULL',
                'name': 'name VARCHAR(255)',
                'origin': (
                    "origin ENUM('c2','dropzone','proxy','p2p-crawler',"
                    "'p2p-drone','sinkhole','sandbox','honeypot',"
                    "'darknet','av','ids','waf')"),
                'proto': "proto ENUM('tcp','udp','icmp')",
                'replaces': 'replaces BINARY(16)',
                'restriction': "restriction ENUM('public','need-to-know','internal') NOT NULL",
                'rid': 'rid BINARY(16) NOT NULL',
                'sha1': 'sha1 BINARY(20)',
                'sha256': 'sha256 BINARY(32)',
                'source': 'source VARCHAR(32) NOT NULL',
                'sport': 'sport SMALLINT UNSIGNED',
                'status': "status ENUM('active','delisted','expired','replaced')",
                'target': (
                    'target VARCHAR(100) '
                    'CHARACTER SET utf8mb4 '
                    'COLLATE utf8mb4_unicode_520_ci'),
                'time': 'time DATETIME NOT NULL',
                'until': 'until DATETIME',
                'url': (
                    'url VARCHAR(2048) '
                    'CHARACTER SET utf8mb4 '
                    'COLLATE utf8mb4_bin'),
            })

    def test_init_and_attrs_1(self):
        # noinspection PyArgumentList
        obj = self.obj = n6NormalizedData(
            id=sen.event_id,
            ip=sen.some_ip_addr,
            dip=sen.some_other_ip_addr,
            dport=sen.some_port_number,
            time='2014-04-01 01:07:42+02:00',
            modified='2014-04-02 01:02:03+02:00',
            ignored=True,
        )
        self.assertEqual(obj.id, sen.event_id)
        self.assertEqual(obj.ip, sen.some_ip_addr)
        self.assertEqual(obj.dip, sen.some_other_ip_addr)
        self.assertEqual(obj.dport, sen.some_port_number)
        self.assertEqual(
            obj.time,
            datetime.datetime(2014, 3, 31, 23, 7, 42))
        self.assertEqual(
            obj.modified,
            datetime.datetime(2014, 4, 1, 23, 2, 3))
        self.assertIs(obj.ignored, True)

        for name in n6NormalizedData._n6columns:
            if name in ('id', 'ip', 'dip', 'dport', 'time', 'modified', 'ignored'):
                continue
            val = getattr(obj, name)
            self.assertIsNone(val)

        self.assertIsInstance(
            obj.clients,
            sqlalchemy.orm.collections.InstrumentedList)
        self.assertEqual(obj.clients, [])
        self.client1 = MagicMock()
        self.client1.client = 'c1'
        self.client2 = MagicMock()
        self.client2.client = 'c2'
        obj.clients.append(self.client2)
        obj.clients.append(self.client1)
        self.assertEqual(obj.clients, [self.client2, self.client1])

    def test_init_and_attrs_2(self):
        # noinspection PyArgumentList
        obj = self.obj = n6NormalizedData(
            time='2014-04-01 01:07:42+02:00',
            modified='2014-04-02 01:02:03+02:00',
            expires='2015-04-01 01:07:43+02:00',
            until='2015-04-01 01:07:43+02:00',
            ignored=False,
        )
        self.assertIsNone(obj.id)
        self.assertEqual(obj.ip, '0.0.0.0')  # "no IP" placeholder
        self.assertEqual(obj.dip, '0.0.0.0')  # "no IP" placeholder
        self.assertEqual(
            obj.time,
            datetime.datetime(2014, 3, 31, 23, 7, 42))
        self.assertEqual(
            obj.modified,
            datetime.datetime(2014, 4, 1, 23, 2, 3))
        self.assertEqual(
            obj.expires,
            datetime.datetime(2015, 3, 31, 23, 7, 43))
        self.assertEqual(
            obj.until,
            datetime.datetime(2015, 3, 31, 23, 7, 43))
        self.assertIs(obj.ignored, False)

    def test_init_and_attrs_3(self):
        # noinspection PyArgumentList
        obj = self.obj = n6NormalizedData(
            id=None,
            ip=None,
            dip=None,
            time=datetime.datetime(
                2014, 4, 1, 1, 7, 42,
                tzinfo=datetime.timezone(datetime.timedelta(hours=2))),
            modified=datetime.datetime(2014, 4, 1, 23, 2, 3),
            expires=datetime.datetime(2015, 3, 31, 23, 7, 43),
            until=datetime.datetime(
                2015, 4, 1, 1, 7, 43,
                tzinfo=datetime.timezone(datetime.timedelta(hours=2))),
            ignored=None,
        )
        self.assertIsNone(obj.id)
        self.assertEqual(obj.ip, '0.0.0.0')  # "no IP" placeholder
        self.assertEqual(obj.dip, '0.0.0.0')  # "no IP" placeholder
        self.assertEqual(
            obj.time,
            datetime.datetime(2014, 3, 31, 23, 7, 42))
        self.assertEqual(
            obj.modified,
            datetime.datetime(2014, 4, 1, 23, 2, 3))
        self.assertEqual(
            obj.expires,
            datetime.datetime(2015, 3, 31, 23, 7, 43))
        self.assertEqual(
            obj.until,
            datetime.datetime(2015, 3, 31, 23, 7, 43))
        self.assertIsNone(obj.ignored)

    def test__key_query(self):
        self.mock.some_key.in_.return_value = sen.result
        act_result = self.meth.key_query('some_key', sen.value)
        self.assertIs(act_result, sen.result)
        self.mock.some_key.in_.assert_called_once_with(sen.value)


    @foreach(
        param(
            key='url.sub',
            mapped_to='url',
            result=sen.or_result),
        param(
            key='fqdn.sub',
            mapped_to='fqdn',
            result=sen.or_result),
        param(
            key='fqdn.illegal',
            exc_type=KeyError),
        param(
            key='illegal',
            exc_type=KeyError),
    )
    @patch('n6lib.db_events.or_', return_value=sen.or_result)
    def test__like_query(self, or_mock, key, mapped_to=None,
                         result=None, exc_type=None, **kwargs):
        value = [
            u'val',
            u'ążź',  # (ticket #8043 - `UnicodeEncodeError: 'ascii' codec can't encode...`)
        ]
        if exc_type is None:
            assert result is not None
            getattr(self.mock, mapped_to).contains.side_effect = [sen.term1, sen.term2]
            act_result = self.meth.like_query(key, value)
            self.assertIs(act_result, result)
            or_mock.assert_called_once_with(sen.term1, sen.term2)
            self.assertEqual(self.mock.mock_calls, [
                getattr(call, mapped_to).contains('val', autoescape=True),
                getattr(call, mapped_to).contains('ążź', autoescape=True),
            ])
        else:
            with self.assertRaises(exc_type):
                self.meth.like_query(key, value)


    @patch('n6lib.db_events.sqla_text', return_value=sen.sqla_true)
    def test__single_flag_query__for_true(self, sqla_text_mock):
        self.mock.some_key.is_.return_value = sen.is_result

        act_result = self.meth.single_flag_query('some_key', [True])

        self.assertEqual(sqla_text_mock.mock_calls, [
            call('TRUE'),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.some_key.is_(sen.sqla_true),
        ])
        self.assertIs(act_result, sen.is_result)


    @patch('n6lib.db_events.sqla_text', return_value=sen.sqla_true)
    def test__single_flag_query__for_false(self, sqla_text_mock):
        self.mock.some_key.isnot.return_value = sen.isnot_result

        act_result = self.meth.single_flag_query('some_key', [False])

        self.assertEqual(sqla_text_mock.mock_calls, [
            call('TRUE'),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.some_key.isnot(sen.sqla_true),
        ])
        self.assertIs(act_result, sen.isnot_result)


    @foreach(
        param(
            value=[('10.20.30.41', 24), ('10.20.30.41', 32)],
            min_max_ips=[(169090560, 169090815), (169090601, 169090601)],
            result=sen.or_result),
        param(
            value=[('10.20.30.41', 24)],
            min_max_ips=[(169090560, 169090815)],
            result=sen.or_result),
        param(
            value=[('0.0.0.123', 24)],
            min_max_ips=[(1, 255)],  # <- Note: here the minimum IP is 1, not 0 (see: #8861).
            result=sen.or_result),
        param(
            value=[('10.20.30.441', 24), ('10.20.30.41', 32)],
            exc_type=socket.error),
        param(
            value=[('10.20.30.441', 24)],
            exc_type=socket.error),
        param(
            value=[None],
            exc_type=TypeError),
        param(
            value=('10.20.30.41', 24),
            exc_type=ValueError),
        param(
            value=None,
            exc_type=TypeError),
    )
    @patch('n6lib.db_events.and_', return_value=sen.and_result)
    @patch('n6lib.db_events.or_', return_value=sen.or_result)
    def test__ip_net_query(self, or_mock, and_mock, value=None, min_max_ips=None,
                           result=None, exc_type=None, **kwargs):
        key = MagicMock()
        key.__ne__.side_effect = (lambda k: k != 'ip.net')
        if exc_type is None:
            assert result is not None
            self.mock.ip.__ge__.side_effect = (lambda min_ip: (sen.term_ge, min_ip))
            self.mock.ip.__le__.side_effect = (lambda max_ip: (sen.term_le, max_ip))
            act_result = self.meth.ip_net_query(key, value)
            self.assertIs(act_result, result)
            or_mock.assert_called_once_with(*(len(value) * [sen.and_result]))
            self.assertEqual(
                and_mock.mock_calls,
                [call(
                    (sen.term_ge, min_ip),
                    (sen.term_le, max_ip))
                 for min_ip, max_ip in min_max_ips])
        else:
            with self.assertRaises(exc_type):
                self.meth.ip_net_query(key, value)
        # the only operation on the key was one unequality test (against 'ip.net')
        key.__ne__.assert_called_once_with('ip.net')                    # noqa


    @foreach(
        param(key='active.min', cmp_meth_name='__ge__'),
        param(key='active.max', cmp_meth_name='__le__'),
        param(key='active.until', cmp_meth_name='__lt__'),
        param(key='active.illegal', exc_type=AssertionError),
        param(key='illegal', exc_type=AssertionError),
    )
    @patch('n6lib.db_events.null', return_value=sen.Null)
    @patch('n6lib.db_events.or_', return_value=sen.or_result)
    @patch('n6lib.db_events.and_', return_value=sen.and_result)
    def test__active_bl_query(self, and_mock, or_mock, null_mock,
                              key, cmp_meth_name=None, exc_type=None,
                              **kwargs):
        value = [sen.val]
        if exc_type is None:
            self.mock.expires.is_.return_value = sen.expires_is_result
            self.mock.expires.isnot.return_value = sen.expires_isnot_result
            getattr(self.mock.expires, cmp_meth_name).return_value = sen.expires_cmp_result
            getattr(self.mock.time, cmp_meth_name).return_value = sen.time_cmp_result
            act_result = self.meth.active_bl_query(key, value)
            self.assertIs(act_result, sen.or_result)
            if key == 'active.min':
                assert cmp_meth_name == '__ge__'
                or_mock.assert_called_once_with(sen.expires_cmp_result, sen.time_cmp_result)
                self.assertEqual(self.mock.expires.is_.mock_calls, [])
                self.assertEqual(self.mock.expires.isnot.mock_calls, [])
            else:
                assert (
                    (key == 'active.max' and cmp_meth_name == '__le__') or
                    (key == 'active.until' and cmp_meth_name == '__lt__'))
                or_mock.assert_called_once_with(sen.and_result, sen.and_result)
                self.assertEqual(and_mock.mock_calls, [
                    call(sen.expires_isnot_result, sen.expires_cmp_result),
                    call(sen.expires_is_result, sen.time_cmp_result),
                ])
                self.mock.expires.is_.assert_called_once_with(sen.Null)
                self.mock.expires.isnot.assert_called_once_with(sen.Null)
            getattr(self.mock.expires, cmp_meth_name).assert_called_once_with(sen.val)
            getattr(self.mock.time, cmp_meth_name).assert_called_once_with(sen.val)
        else:
            with self.assertRaises(exc_type):
                self.meth.active_bl_query(key, value)


    @foreach(
        param('modified.min', cmp_meth_name='__ge__'),
        param('modified.max', cmp_meth_name='__le__'),
        param('modified.until', cmp_meth_name='__lt__'),
        param('modified.illegal', exc_type=AssertionError),
        param('illegal', exc_type=AssertionError),
    )
    def test__modified_query(self, key, cmp_meth_name=None, exc_type=None):
        value = [sen.val]
        if exc_type is None:
            getattr(self.mock.modified, cmp_meth_name).return_value = sen.result
            act_result = self.meth.modified_query(key, value)
            self.assertIs(act_result, sen.result)
            getattr(self.mock.modified, cmp_meth_name).assert_called_once_with(sen.val)
        else:
            with self.assertRaises(exc_type):
                self.meth.modified_query(key, value)


@expand
class Test_make_raw_result_dict(TestCaseMixin, unittest.TestCase):

    @foreach(
        param(
            colum_to_value=dict(),  # <- All columns set to None...
            expected_result_dict=dict(),  # (skipped all None values)
        ),

        param(
            colum_to_value=dict(
                custom={
                    'client': ['o1', 'o2', 'o3'],
                },
            ),
            expected_result_dict=dict(
                # (moved `client`, removed empty `custom`
                # skipped all None values)
                client=['o1', 'o2', 'o3']
            ),
        ),

        param(
            colum_to_value=dict(
                dip='1.2.3.4',
                dport=0,
            ),
            expected_result_dict=dict(
                # (skipped all None values)
                dip='1.2.3.4',
                dport=0,
            ),
        ),

        param(
            colum_to_value=dict(
                id=sen.event_id,
                ip='1.2.3.4',
                dip='0.0.0.0',   # "no IP" placeholder
                dport=42,
                time=sen.some_dt,
                modified=sen.some_other_dt,
                extra_noncolumn=sen.WHATEVER,
                another_extra_noncolumn=sen.WHAAATEVER,
            ),
            expected_result_dict=dict(
                # (skipped all None values and non-column keys,
                # skipped `dip` set to "no IP" placeholder)
                id=sen.event_id,
                ip='1.2.3.4',
                dport=42,
                time=sen.some_dt,
                modified=sen.some_other_dt,
            ),
        ),

        param(
            colum_to_value=dict(
                id=sen.event_id,
                ip='0.0.0.0',    # "no IP" placeholder
                time=sen.some_dt,
                modified=sen.some_other_dt,
                custom={
                    'client': ['o3', 'o2', 'o1'],
                    'foo': sen.WHATEVER,
                },
                extra_noncolumn=None,
            ),
            expected_result_dict=dict(
                # (moved `client`, kept non-empty `custom`,
                # skipped all None values and non-column keys,
                # skipped `ip` set to "no IP" placeholder)
                client=['o3', 'o2', 'o1'],
                id=sen.event_id,
                time=sen.some_dt,
                modified=sen.some_other_dt,
                custom={'foo': sen.WHATEVER},
            ),
        ),

        param(
            colum_to_value=dict(
                ip=0,    # "no IP" placeholder
                dip=-1,  # "no IP" placeholder (legacy)
                address=sen.some_address,
                time=sen.some_dt,
                modified=sen.some_other_dt,
                custom={
                    'client': ['o1'],
                },
            ),
            expected_result_dict=dict(
                # (moved `client`, removed empty `custom`,
                # skipped all None values,
                # skipped `ip` and `dip` set to "no IP" placeholders)
                client=['o1'],
                address=sen.some_address,
                time=sen.some_dt,
                modified=sen.some_other_dt,
            ),
        ),
    )
    def test(self, colum_to_value, expected_result_dict):
        column_values_source_object = self._make_row_fake(colum_to_value)
        result_dict = make_raw_result_dict(column_values_source_object)
        self.assertEqualIncludingTypes(result_dict, expected_result_dict)

    def _make_row_fake(self, colum_to_value):
        column_to_none = dict.fromkeys(n6NormalizedData._n6columns)
        row = PlainNamespace(**(column_to_none | copy.deepcopy(colum_to_value)))
        assert row.fqdn is None  # (example of column with no value)
        return row


### TODO:
#class Test_...

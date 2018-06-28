# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import socket
import unittest

import sqlalchemy.orm.attributes
import sqlalchemy.orm.collections
from mock import (
    MagicMock,
    call,
    patch,
    sentinel as sen,
)
from unittest_expander import expand, foreach, param

from n6lib.db_events import IPAddress, n6NormalizedData
from n6lib.unit_test_helpers import MethodProxy


### TODO:
#class Test__n6ClientToEventunittest.TestCase):

### TODO:
#class Test__...


@expand
class Test__n6NormalizedData(unittest.TestCase):

    def setUp(self):
        self.mock = MagicMock()
        self.meth = MethodProxy(n6NormalizedData, self.mock)

    def test_class_attrs(self):
        instrumented_attr_names = {
            name for name, obj in vars(n6NormalizedData).items()
            if isinstance(obj, sqlalchemy.orm.attributes.InstrumentedAttribute)}
        column_names_to_sql_reprs = {
            str(name): str(self._get_sql_repr(obj))
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
            set(n6NormalizedData._n6columns))
        self.assertEqual(
            column_names_to_sql_reprs, {
                'address': 'address TEXT',  # note: in actual db it is MEDIUMTEXT
                'ip': 'ip INTEGER UNSIGNED NOT NULL',
                'asn': 'asn INTEGER UNSIGNED',
                'cc': 'cc VARCHAR(2)',
                ###'ipv6': '',
                ###'rdns': '',
                ###'dir': '',

                'category': (
                    "category ENUM('amplifier','bots','backdoor','cnc',"
                    "'deface','dns-query','dos-attacker','dos-victim','flow',"
                    "'flow-anomaly','fraud','leak','malurl','malware-action','other','phish',"
                    "'proxy','sandbox-url','scam','scanning','server-exploit','spam',"
                    "'spam-url','tor','vulnerable','webinject') NOT NULL"),
                'confidence': "confidence ENUM('low','medium','high') NOT NULL",
                'count': 'count SMALLINT',
                'custom': 'custom TEXT',  # note: in actual db it is MEDIUMTEXT
                'dip': 'dip INTEGER UNSIGNED',
                'dport': 'dport INTEGER',
                ###'email': '',
                'expires': 'expires DATETIME',
                'fqdn': 'fqdn VARCHAR(255)',
                ###'iban': '',
                'id': 'id BINARY(16) NOT NULL',
                ###'injects': '',
                'md5': 'md5 BINARY(16)',
                'modified': 'modified DATETIME',
                'name': 'name VARCHAR(255)',
                'origin': (
                    "origin ENUM('c2','dropzone','proxy','p2p-crawler',"
                    "'p2p-drone','sinkhole','sandbox','honeypot',"
                    "'darknet','av','ids','waf')"),
                ###'phone': '',
                'proto': "proto ENUM('tcp','udp','icmp')",
                ###'registrar': '',
                'replaces': 'replaces BINARY(16)',
                'restriction': "restriction ENUM('public','need-to-know','internal') NOT NULL",
                'rid': 'rid BINARY(16) NOT NULL',
                'sha1': 'sha1 BINARY(20)',
                'source': 'source VARCHAR(32) NOT NULL',
                'sport': 'sport INTEGER',
                'status': "status ENUM('active','delisted','expired','replaced')",
                'target': 'target VARCHAR(100)',
                'time': 'time DATETIME NOT NULL',
                'until': 'until DATETIME',
                'url': 'url VARCHAR(2048)',
                ###'url_pattern': '',
                ###'username': '',
                ###'x509fp_sha1': '',
            })
        self.assertEqual(n6NormalizedData._ip_column_names, ('dip', 'ip'))
        self.assertEqual(n6NormalizedData._no_ip_placeholders, {'0.0.0.0', 0, -1})

    def _get_sql_repr(self, col):
        type_name = (
            str(col.type) if not isinstance(col.type, sqlalchemy.types.Enum)
            else 'ENUM({0})'.format(','.join(
                    "'{0}'".format(e) for e in col.type.enums)))
        r = '{0} {1}'.format(col.name, type_name)
        if isinstance(col.type, IPAddress):
            self.assertTrue(col.type.impl.mapping['mysql'].unsigned)
            r += ' UNSIGNED'
        self.assertIsInstance(col.nullable, bool)
        if not col.nullable:
            r += ' NOT NULL'
        return r

    def test_init_and_attrs_1(self):
        obj = self.obj = n6NormalizedData(
            id=sen.event_id,
            ip=sen.some_ip_addr,
            dport=sen.some_port_number,
            time='2014-04-01 01:07:42+02:00',
        )
        self.assertEqual(obj.id, sen.event_id)
        self.assertEqual(obj.ip, sen.some_ip_addr)
        self.assertEqual(obj.dport, sen.some_port_number)
        self.assertEqual(
            obj.time,
            datetime.datetime(2014, 3, 31, 23, 7, 42))

        for name in n6NormalizedData._n6columns:
            if name in ('id', 'ip', 'dport', 'time'):
                continue
            val = getattr(obj, name)
            self.assertIsNone(val)

        self.assertIsInstance(
            obj.clients,
            sqlalchemy.orm.collections.InstrumentedList)
        self.assertEqual(obj.clients, [])
        self.client1 = MagicMock()
        self.client1.client = sen.c1
        self.client2 = MagicMock()
        self.client2.client = sen.c2
        obj.clients.append(self.client1)
        obj.clients.append(self.client2)
        self.assertEqual(obj.clients, [self.client1, self.client2])

    def test_init_and_attrs_2(self):
        obj = self.obj = n6NormalizedData(
            time='2014-04-01 01:07:42+02:00',
            expires='2015-04-01 01:07:43+02:00',
            until='2015-04-01 01:07:43+02:00',
        )
        self.assertIsNone(obj.id)
        self.assertEqual(obj.ip, '0.0.0.0')  # "no IP" placeholder
        self.assertEqual(
            obj.time,
            datetime.datetime(2014, 3, 31, 23, 7, 42))
        self.assertEqual(
            obj.expires,
            datetime.datetime(2015, 3, 31, 23, 7, 43))
        ### THIS IS A PROBLEM -- TO BE SOLVED IN #3113:
        self.assertEqual(
            obj.until,
            '2015-04-01 01:07:43+02:00')

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
        value = ['val1', 'val2']
        if exc_type is None:
            assert result is not None
            getattr(self.mock, mapped_to).like.side_effect = [sen.term1, sen.term2]
            act_result = self.meth.like_query(key, value)
            self.assertIs(act_result, result)
            or_mock.assert_called_once_with(sen.term1, sen.term2)
            self.assertEqual(self.mock.mock_calls, [
                getattr(call, mapped_to).like('%val1%'),
                getattr(call, mapped_to).like('%val2%'),
            ])
        else:
            with self.assertRaises(exc_type):
                self.meth.like_query(key, value)

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
        key.__ne__.assert_called_once_with('ip.net')

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

    def test__to_raw_result_dict__1(self):
        self.test_init_and_attrs_1()
        d = self.obj.to_raw_result_dict()
        self.assertEqual(d, {
            'id': sen.event_id,
            'ip': sen.some_ip_addr,
            'dport': sen.some_port_number,
            'time': datetime.datetime(2014, 3, 31, 23, 7, 42),
            'client': [sen.c1, sen.c2],
        })

    def test__to_raw_result_dict__2(self):
        self.test_init_and_attrs_2()
        d = self.obj.to_raw_result_dict()
        self.assertEqual(d, {
            # note that ip='0.0.0.0' has been removed
            'time': datetime.datetime(2014, 3, 31, 23, 7, 42),
            'expires': datetime.datetime(2015, 3, 31, 23, 7, 43),
            ### THIS IS A PROBLEM -- TO BE SOLVED IN #3113:
            'until': '2015-04-01 01:07:43+02:00',
        })

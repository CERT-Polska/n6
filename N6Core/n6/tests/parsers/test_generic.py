# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import hashlib
import json
import unittest

from mock import ANY, Mock, MagicMock, call, patch, sentinel
from unittest_expander import expand, foreach, param

from n6lib.common_helpers import (
    FilePagedSequence,
    SimpleNamespace,
    concat_reducing_indent,
)
from n6lib.config import (
    Config,
    ConfigSection,
    parse_config_spec,
)
from n6lib.record_dict import (
    AdjusterError,
    RecordDict,
)
from n6lib.unit_test_helpers import (
    MethodProxy,
    patch_always,
)
from n6.base.queue import QueuedBase
from n6.parsers.generic import (
    MAX_IPS_IN_ADDRESS,
    BaseParser,
    AggregatedEventParser,
    BlackListParser,
    #TabDataParser,
    #BlackListTabDataParser,
)


@expand
class TestBaseParser(unittest.TestCase):

    def setUp(self):
        self.mock = Mock(__class__=BaseParser, allow_empty_results=False)
        self.meth = MethodProxy(BaseParser, self.mock)

    def _asserts_of_proper__new__instance_adjustment(self, instance):
        # BaseQueued.__new__() ensures that
        self.assertIsNot(instance.input_queue, BaseParser.input_queue)

    def _asserts_of_proper_preinit_hook_instance_adjustment(self, instance,
                                                            binding_key):
        # for classes with `default_binding_key`
        # BaseParser.preinit_hook() ensures that
        self.assertEqual(instance.input_queue, {
            'exchange': 'raw',
            'exchange_type': 'topic',
            'queue_name': binding_key,
            'binding_keys': [binding_key],
        })
        self.assertEqual(BaseParser.input_queue, {
            'exchange': 'raw',
            'exchange_type': 'topic',
        })

    def _basic_init_related_asserts(self,
                                    instance,
                                    subclass,
                                    super_mock,
                                    super_cls_mock,
                                    expected_config,
                                    expected_config_full):
        # assert that an instance of the proper type has been returned
        self.assertIsInstance(instance, subclass)
        # assert that super used properly
        super_mock.assert_called_once_with(BaseParser, instance)
        super_cls_mock.__init__.assert_called_once_with(a=sentinel.a,
                                                        bb=sentinel.bb)
        # assert that configuration stuff has been obtained properly
        self.assertEqual(instance.config, expected_config)
        self.assertIsInstance(instance.config, ConfigSection)
        self.assertEqual(instance.config_full, expected_config_full)
        self.assertIsInstance(instance.config_full, Config)

    def test_basics(self):
        self.assertTrue(issubclass(BaseParser, QueuedBase))
        self.assertTrue(hasattr(BaseParser, 'default_binding_key'))
        self.assertTrue(hasattr(BaseParser, 'config_spec_pattern'))
        self.assertTrue(hasattr(BaseParser, 'constant_items'))
        self.assertTrue(hasattr(BaseParser, 'record_dict_class'))
        self.assertTrue(hasattr(BaseParser, 'event_type'))

    def test_config_spec_pattern(self):
        config_spec = BaseParser.config_spec_pattern.format(parser_class_name='example_foo')
        config_spec_parsed = parse_config_spec(config_spec)
        prefetch_count_opt_spec = config_spec_parsed.get_opt_spec('example_foo.prefetch_count')
        self.assertEqual(prefetch_count_opt_spec.name, 'prefetch_count')
        self.assertEqual(prefetch_count_opt_spec.converter_spec, 'int')

    def test_initialization_without_default_binding_key(self):
        class SomeParser(BaseParser):
            pass  # no `default_binding_key` defined => it's an abstract class
        with self.assertRaises(NotImplementedError):
            SomeParser()

        unready_instance = SomeParser.__new__(SomeParser)
        self._asserts_of_proper__new__instance_adjustment(unready_instance)
        # for classes without `default_binding_key`
        # `queue_name` and `binding_keys` items are *not* added...
        self.assertEqual(unready_instance.input_queue,
                         BaseParser.input_queue)
        self.assertEqual(BaseParser.input_queue, {
            'exchange': 'raw',
            'exchange_type': 'topic',
        })

    @foreach(
        param(
            mocked_conf_from_files={},
            expected_config=ConfigSection('SomeParser', {'prefetch_count': 1}),
            expected_config_full=Config.make({'SomeParser': {'prefetch_count': 1}}),
        ),
        param(
            mocked_conf_from_files={
                'SomeParser': {
                    'prefetch_count': '42'
                },
                'another_section': {
                    'another_opt': '123.456'
                },
            },
            expected_config=ConfigSection('SomeParser', {'prefetch_count': 42}),
            expected_config_full=Config.make({'SomeParser': {'prefetch_count': 42}}),
        ),
        param(
            custom_config_spec_pattern=concat_reducing_indent(
                BaseParser.config_spec_pattern,
                '''
                    some_opt = [-3, null] :: json
                    [another_section]
                    another_opt :: float
                    yet_another_opt = Foo Bar Spam Ham
                ''',
            ),
            mocked_conf_from_files={
                'SomeParser': {
                    'prefetch_count': '42'
                },
                'another_section': {
                    'another_opt': '123.456'
                },
            },
            expected_config=ConfigSection('SomeParser', {
                'prefetch_count': 42,
                'some_opt': [-3, None],
            }),
            expected_config_full=Config.make({
                'SomeParser': {
                    'prefetch_count': 42,
                    'some_opt': [-3, None],
                },
                'another_section': {
                    'another_opt': 123.456,
                    'yet_another_opt': 'Foo Bar Spam Ham',
                },
            }),
        ),
    )
    @foreach(
        param(binding_key='foo.bar'),
        param(binding_key='foo.bar.33'),
    )
    def test_initialization_with_default_binding_key(self,
                                                     binding_key,
                                                     mocked_conf_from_files,
                                                     expected_config,
                                                     expected_config_full,
                                                     custom_config_spec_pattern=None):
        class SomeParser(BaseParser):
            default_binding_key = binding_key  # => it's a concrete class

        if custom_config_spec_pattern is not None:
            SomeParser.config_spec_pattern = custom_config_spec_pattern

        unready_instance = SomeParser.__new__(SomeParser)
        self._asserts_of_proper__new__instance_adjustment(unready_instance)
        self._asserts_of_proper_preinit_hook_instance_adjustment(unready_instance, binding_key)

        super_cls_mock = SimpleNamespace(__init__=Mock())
        with patch_always('n6.parsers.generic.super',
                          return_value=super_cls_mock) as super_mock, \
             patch('n6.parsers.generic.Config._load_n6_config_files',
                   return_value=mocked_conf_from_files):
            # instantiation
            instance = SomeParser(a=sentinel.a, bb=sentinel.bb)
            self._asserts_of_proper__new__instance_adjustment(instance)
            self._asserts_of_proper_preinit_hook_instance_adjustment(instance, binding_key)
            self._basic_init_related_asserts(
                instance,
                SomeParser,
                super_mock,
                super_cls_mock,
                expected_config,
                expected_config_full)

    def test__make_binding_keys(self):
        self.mock.default_binding_key = 'fooo.barr'
        binding_keys = self.meth.make_binding_keys()
        self.assertEqual(binding_keys, ['fooo.barr'])
        self.assertEqual(self.mock.mock_calls, [])

    def test__make_binding_keys_with_raw_format_version_tag(self):
        self.mock.default_binding_key = 'fooo.barr.33'
        binding_keys = self.meth.make_binding_keys()
        self.assertEqual(binding_keys, ['fooo.barr.33'])
        self.assertEqual(self.mock.mock_calls, [])

    def test__get_script_init_kwargs(self):
        self.assertIsInstance(vars(BaseParser)['get_script_init_kwargs'],
                              classmethod)
        init_kwargs = BaseParser.get_script_init_kwargs.__func__(self.mock)
        self.assertEqual(init_kwargs, {})
        self.assertEqual(self.mock.mock_calls, [])

    def test__run_handling__interrupted(self):
        self.mock.configure_mock(**{'run.side_effect': KeyboardInterrupt})
        self.meth.run_handling()
        self.mock.run.assert_called_once_with()
        self.mock.stop.assert_called_once_with()

    def test__run_handling__not_interrupted(self):
        self.meth.run_handling()
        self.mock.run.assert_called_once_with()
        self.assertEqual(self.mock.stop.mock_calls, [])

    @patch('n6.parsers.generic.FilePagedSequence')
    def test__input_callback(self, FilePagedSequence_mock):
        FilePagedSequence_mock.return_value = MagicMock()
        FilePagedSequence_mock.return_value.__enter__.return_value = sentinel.working_seq
        data = MagicMock(**{'get.return_value': sentinel.rid})
        self.mock.configure_mock(**{
            '_fix_body.return_value': sentinel.body,
            'prepare_data.return_value': data,
            'setting_error_event_info': MagicMock(),
            'get_output_rk.return_value': sentinel.output_rk,
            'get_output_bodies.return_value': [sentinel.output_body1,
                                               sentinel.output_body2],
        })
        self.meth.input_callback(sentinel.routing_key,
                                 sentinel.body,
                                 sentinel.properties)
        self.assertEqual(self.mock.mock_calls, [
            call._fix_body(sentinel.body),
            call.prepare_data(sentinel.routing_key,
                              sentinel.body,
                              sentinel.properties),
            call.prepare_data().get('properties.message_id'),
            call.setting_error_event_info(sentinel.rid),
            call.setting_error_event_info().__enter__(),
            call.get_output_rk(data),
            call.get_output_bodies(data, sentinel.working_seq),
            call.publish_output(routing_key=sentinel.output_rk,
                                body=sentinel.output_body1),
            call.publish_output(routing_key=sentinel.output_rk,
                                body=sentinel.output_body2),
            call.setting_error_event_info().__exit__(None, None, None),
        ])
        self.assertEqual(FilePagedSequence_mock.mock_calls, [
            call(page_size=1000),
            call().__enter__(),
            call().__exit__(None, None, None),
        ])

    def test__prepare_data(self):
        data = self.meth.prepare_data(
            routing_key='ham.spam',
            body=sentinel.body,
            properties=SimpleNamespace(foo=sentinel.foo,
                                       bar=sentinel.bar,
                                       timestamp=1389348840,
                                       headers={'a': sentinel.a}))
        self.assertEqual(data, {
            'a': sentinel.a,
            'properties.foo': sentinel.foo,
            'properties.bar': sentinel.bar,
            'source': 'ham.spam',
            'properties.timestamp': '2014-01-10 10:14:00',
            'raw_format_version_tag': None,
            'raw': sentinel.body,
        })

    def test__prepare_data__rk__with_raw_format_version_tag(self):
        data = self.meth.prepare_data(
            routing_key='ham.spam.33',
            body=sentinel.body,
            properties=SimpleNamespace(foo=sentinel.foo,
                                       bar=sentinel.bar,
                                       timestamp=1389348840,
                                       headers={'a': sentinel.a}))
        self.assertEqual(data, {
            'a': sentinel.a,
            'properties.foo': sentinel.foo,
            'properties.bar': sentinel.bar,
            'source': 'ham.spam',
            'properties.timestamp': '2014-01-10 10:14:00',
            'raw_format_version_tag': '33',
            'raw': sentinel.body,
        })

    def test__get_output_rk(self):
        self.mock.configure_mock(**{
            'event_type': 'foobar',
        })
        data = {'source': 'ham.spam'}
        output_rk = self.meth.get_output_rk(data)
        self.assertEqual(output_rk, 'foobar.parsed.ham.spam')

    def test__get_output_bodies(self):
        parsed = [MagicMock(**{'__class__': RecordDict,
                               'used_as_context_manager': True,
                               'get_ready_json.return_value':
                                   getattr(sentinel,
                                           'output_body{}'.format(i))})
                  for i in (1, 2)]
        self.mock.configure_mock(**{
            'parse.return_value': parsed,
            'get_output_message_id.side_effect': [
                sentinel.msg_A,
                sentinel.msg_B,
            ],
            'setting_error_event_info': MagicMock(),
            'postprocess_parsed.side_effect': (
                lambda data, parsed, total, item_no: parsed
            ),
        })
        seq_mock = FilePagedSequence._instance_mock()
        output_bodies = self.meth.get_output_bodies(sentinel.data, seq_mock)
        self.assertIs(output_bodies, seq_mock)
        self.assertEqual(seq_mock._list, [
            sentinel.output_body1,
            sentinel.output_body2,
        ])
        self.assertEqual(parsed[0].mock_calls, [
            call.__setitem__('id', sentinel.msg_A),
            call.get_ready_json(),
        ])
        self.assertEqual(parsed[1].mock_calls, [
            call.__setitem__('id', sentinel.msg_B),
            call.get_ready_json(),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.parse(sentinel.data),
            call.get_output_message_id(parsed[0]),
            call.delete_too_long_address(parsed[0]),
            call.get_output_message_id(parsed[1]),
            call.delete_too_long_address(parsed[1]),

            call.setting_error_event_info(parsed[0]),
            call.setting_error_event_info().__enter__(),
            call.postprocess_parsed(sentinel.data,
                                    parsed[0],
                                    2,
                                    item_no=1),
            call.setting_error_event_info().__exit__(None, None, None),

            call.setting_error_event_info(parsed[1]),
            call.setting_error_event_info().__enter__(),
            call.postprocess_parsed(sentinel.data,
                                    parsed[1],
                                    2,
                                    item_no=2),
            call.setting_error_event_info().__exit__(None, None, None),
        ])

    def test__get_output_bodies__record_dict_not_used_as_context_manager(self):
        parsed = [MagicMock(**{'__class__': RecordDict,
                               'used_as_context_manager': False})
                  for i in (1, 2)]
        self.mock.configure_mock(**{'parse.return_value': parsed})
        with self.assertRaises(AssertionError):
            self.meth.get_output_bodies(sentinel.data,
                                        FilePagedSequence._instance_mock())
        self.assertEqual(self.mock.method_calls, [
            call.parse(sentinel.data),
        ])

    def test__get_output_bodies__parse_yielded_no_items(self):
        self.mock.configure_mock(**{'parse.return_value': iter([])})
        with self.assertRaises(ValueError):
            self.meth.get_output_bodies(sentinel.data,
                                        FilePagedSequence._instance_mock())
        self.assertEqual(self.mock.method_calls, [
            call.parse(sentinel.data),
        ])

    def test__get_output_bodies__parse_yielded_no_items__allow_empty_results(self):
        self.mock.configure_mock(**{'parse.return_value': iter([]),
                                    'allow_empty_results': True})
        seq_mock = FilePagedSequence._instance_mock()
        output_bodies = self.meth.get_output_bodies(sentinel.data, seq_mock)
        self.assertIs(output_bodies, seq_mock)
        self.assertEqual(seq_mock._list, [])  # just empty
        self.assertEqual(self.mock.mock_calls, [
            call.parse(sentinel.data),
        ])

    def test__delete_too_long_address__address_is_ok(self):
        parsed = RecordDict()
        parsed['address'] = [{'ip': i+1} for i in xrange(MAX_IPS_IN_ADDRESS)]
        expected = RecordDict()
        expected['address'] = [{'ip': i+1} for i in xrange(MAX_IPS_IN_ADDRESS)]
        self.meth.delete_too_long_address(parsed)
        self.assertEqual(parsed, expected)

    def test__delete_too_long_address__address_is_too_long(self):
        ips = MAX_IPS_IN_ADDRESS + 1
        parsed = RecordDict()
        parsed['id'] = '0123456789abcdef0123456789abcdef'
        parsed['address'] = [{'ip': i+1} for i in xrange(ips)]
        expected = RecordDict()
        expected['id'] = '0123456789abcdef0123456789abcdef'
        self.meth.delete_too_long_address(parsed)
        self.assertEqual(parsed, expected)

    def test__delete_too_long_address__address_is_empty(self):
        parsed = RecordDict()
        parsed.update({'source': 'foo.bar'})
        expected = RecordDict()
        expected.update({'source': 'foo.bar'})
        self.meth.delete_too_long_address(parsed)
        self.assertEqual(parsed, expected)

    def test__get_output_message_id(self):
        inputs_and_resultant_hash_bases = [
            # basics
            (
                {'source': 'foo.bar'},
                'source,foo.bar'
            ),
            (
                {u'source': u'foo.bar'},
                'source,foo.bar'
            ),
            # proper sorting of multiple values
            (
                {'key1': 2, 'key2': ['value2', 'value3', 'value1']},
                'key1,2\nkey2,value1,value2,value3'
            ),
            # ...and of keys + proper encoding of unicode keys/values
            (
                {u'key2': [u'value3', u'value1', u'value2'], u'key1': 2L},
                'key1,2\nkey2,value1,value2,value3'
            ),
            # ...as well as proper int/long normalization/representation
            (
                {u'key2': [30, 10, 20L], u'key1': 9000111222333444555666777888999000L},
                'key1,9000111222333444555666777888999000\nkey2,10,20,30'
            ),
            # non-ascii values
            (
                {'target': 'zażółć', u'client': [u'jaźń', u'gęślą']},
                'client,gęślą,jaźń\ntarget,zażółć'
            ),
            (
                {u'target': u'zażółć', 'client': ['jaźń', 'gęślą']},
                'client,gęślą,jaźń\ntarget,zażółć'
            ),
            # subdicts
            (
                {'dip': u'3.3.3.3', u'address': [{'ip': '255.255.255.0'}, {'ip': '127.0.0.1'}]},
                "address,{'ip': '127.0.0.1'},{'ip': '255.255.255.0'}\ndip,3.3.3.3"
            ),
            # non-ascii subdict keys/values
            (
                {u'key2': [{'ką2': 'vą2'}, {'ką1': 'vą1'}], 'key1': {'ką': 'vą'}},
                "key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n" +
                "key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            # proper encoding of unicode keys/values + proper sorting of whole subdicts
            (
                {'key1': {u'ką': u'vą'}, 'key2': [{u'ką2': 'vą2'}, {'ką1': u'vą1'}]},
                "key1,{'k\\xc4\\x85': 'v\\xc4\\x85'}\n" +
                "key2,{'k\\xc4\\x851': 'v\\xc4\\x851'},{'k\\xc4\\x852': 'v\\xc4\\x852'}"
            ),
            # ...as well as proper int/long normalization/representation
            (
                {'key1': {u'k': 2L}, 'key2': [{'k2': 2L}, {u'k1': 1}]},
                "key1,{'k': 2}\nkey2,{'k1': 1},{'k2': 2}"
            ),
            (
                {u'key2': [{'k2': 2}, {'k1': 1}], 'key1': {'k': 3}},
                "key1,{'k': 3}\nkey2,{'k1': 1},{'k2': 2}"
            ),
            (
                {u'key2': [{'k2': 2L}, {'k1': 1L}], 'key1': {'k': 9000111222333444555666777888999000L}},
                "key1,{'k': 9000111222333444555666777888999000}\nkey2,{'k1': 1},{'k2': 2}"
            ),
            # proper sorting of multiple items in subdicts
            (
                {'key1': {'c': 2, u'a': 3L, u'b': 1L},
                 'key2': [{'c': 2, u'a': 3L, u'b': 1L}, {'d': 3, u'a': 2L, u'b': 1L}]},
                "key1,{'a': 3, 'b': 1, 'c': 2}\n" +
                "key2,{'a': 2, 'b': 1, 'd': 3},{'a': 3, 'b': 1, 'c': 2}"
            ),
        ]
        class _RecordDict(RecordDict):
            adjust_key1 = adjust_key2 = None
            optional_keys = RecordDict.optional_keys | {'key1', 'key2'}
        parser = BaseParser.__new__(BaseParser)
        for input_dict, expected_base in inputs_and_resultant_hash_bases:
            record_dict = _RecordDict(input_dict)
            expected_result = hashlib.md5(expected_base).hexdigest()
            result = parser.get_output_message_id(record_dict)
            self.assertIsInstance(result, str)
            self.assertEqual(result, expected_result)

    def test__get_output_message_id__errors(self):
        inputs_and_exc_classes = [
            # bad subdict key type
            (
                {'key1': {32: 2}},
                TypeError,
            ),
            (
                {'key1': [{32: 2}]},
                TypeError,
            ),
            # bad subdict value type
            (
                {'key1': {'k': 2.3}},
                TypeError,
            ),
            (
                {'key1': [{'k': 2.3}]},
                TypeError,
            ),
            (
                {'key1': {'k': {'k': 2}}},  # nesting is illegal
                TypeError,
            ),
            (
                {'key1': [{'k': {'k': 2}}]},  # nesting is illegal
                TypeError,
            ),
            # bad value type
            (
                {'key1': 2.3},
                TypeError,
            ),
            (
                {'key1': [2.3]},
                TypeError,
            ),
            (
                {'key1': [[2]]},  # nesting is illegal
                TypeError,
            ),
        ]
        class _RecordDict(RecordDict):
            adjust_key1 = adjust_key2 = None
            optional_keys = RecordDict.optional_keys | {'key1', 'key2'}
        parser = BaseParser.__new__(BaseParser)
        for input_dict, exc_class in inputs_and_exc_classes:
            record_dict = _RecordDict(input_dict)
            with self.assertRaises(exc_class):
                parser.get_output_message_id(record_dict)

    def test__postprocess_parsed__without__do_not_resolve_fqdn_to_ip(self):
        data = {}
        parsed = RecordDict()
        self.meth.postprocess_parsed(data, parsed, 1, item_no=1)
        self.assertEqual(parsed, {})

    def test__postprocess_parsed__with__do_not_resolve_fqdn_to_ip__False(self):
        data = {'_do_not_resolve_fqdn_to_ip': False}
        parsed = RecordDict()
        self.meth.postprocess_parsed(data, parsed, 1, item_no=1)
        self.assertEqual(parsed, {})

    def test__postprocess_parsed__with__do_not_resolve_fqdn_to_ip__True(self):
        data = {'_do_not_resolve_fqdn_to_ip': True}
        parsed = RecordDict()
        self.meth.postprocess_parsed(data, parsed, 1, item_no=1)
        self.assertEqual(parsed, {'_do_not_resolve_fqdn_to_ip': True})


    ## TODO:
    #def test__
    #def test__
    #def test__
    # ...


class Test__get_output_bodies__results_for_concrete_parsers(unittest.TestCase):

    def setUp(self):
        class MyError(Exception):
            pass

        class MyParserMixIn(object):
            constant_items = {
                'restriction': 'need-to-know',
                'confidence': 'low',
                'category': 'malurl',
            }
            def parse(self, data):
                for dport in data['raw'].split(' '):
                    with self.new_record_dict(data) as parsed:
                        if dport == 'NON-ADJUSTER-ERROR':
                            raise MyError('NON-ADJUSTER-ERROR')
                        parsed['dport'] = dport
                        parsed['time'] = '2014-01-10 10:14:00'
                        yield parsed

        self.MyError = MyError
        self.MyParserMixIn = MyParserMixIn

        self.base_data = {
            'properties.message_id': '0123456789abcdef0123456789abcdef',  # like an md5 hash,
            'source': 'foo.bar',
            # 'created': '2014-01-09 23:01:02',
            'properties.timestamp': '2014-01-10 10:14:00',
            # 'properties.timestamp': 1389348840
        }
        self.common_output_items = dict(
            self.MyParserMixIn.constant_items,
            rid='0123456789abcdef0123456789abcdef',
            time='2014-01-10 10:14:00',
            source='foo.bar',
        )

    def _asserts_for_dport_80_1024(self, parser_base_cls, raw,
                                   extra_parser_attrs=None,
                                   extra_input_items={},
                                   extra_output_items1={},
                                   extra_output_items2={}):
        class MyParser(self.MyParserMixIn, parser_base_cls):
            constant_items = dict(self.MyParserMixIn.constant_items,
                                  **extra_input_items)
        if extra_parser_attrs is not None:
            for k, v in extra_parser_attrs.items():
                setattr(MyParser, k, v)
        parser = MyParser.__new__(MyParser)
        data = dict(self.base_data, raw=raw)
        seq_mock = FilePagedSequence._instance_mock()
        output_bodies = parser.get_output_bodies(data, seq_mock)
        self.assertIs(output_bodies, seq_mock)
        output_data = [json.loads(body)
                       for body in seq_mock._list]
        for d in output_data:
            # check that d['id'] looks like an md5 hash...
            self.assertIsInstance(d.get('id'), basestring)
            self.assertEqual(len(d['id']), 32)
            self.assertTrue(set('0123456789abcdef').issuperset(d['id']))
            # ...then omit d['id'] for simplicity of the test
            del d['id']
        self.assertEqual(output_data, [
            dict(self.common_output_items, dport=80, **extra_output_items1),
            dict(self.common_output_items, dport=1024, **extra_output_items2),
        ])

    def _asserts_for_loud_error(self, parser_base_cls, error_cls, raw,
                                extra_parser_attrs=None,
                                required_error_attrs=None):
        class MyParser(self.MyParserMixIn, parser_base_cls):
            pass
        if extra_parser_attrs is not None:
            for k, v in extra_parser_attrs.items():
                setattr(MyParser, k, v)
        parser = MyParser.__new__(MyParser)
        data = dict(self.base_data, raw=raw)
        with self.assertRaises(error_cls) as cm:
            parser.get_output_bodies(data, FilePagedSequence._instance_mock())
        if required_error_attrs is not None:
            self.assertTrue(vars(cm.exception).viewitems() >=
                            required_error_attrs.viewitems())

    # BaseParser subclasses

    def test_BaseParser_subclass(self, *args):
        # normal (no error)
        self._asserts_for_dport_80_1024(
            BaseParser,
            raw='80 1024')

        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        # NOTE: it's *silenced* for non-blacklist events
        self._asserts_for_dport_80_1024(
            BaseParser,
            raw='80 ADJUSTER-ERROR 1024')

    def test_BaseParser_subclass__not_silenced_error(self, *args):
        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._asserts_for_loud_error(
            BaseParser,
            error_cls=self.MyError,
            raw='80 NON-ADJUSTER-ERROR 1024')

    # AggregatedEventParser subclasses

    def test_AggregatedEventParser_subclass(self, *args):
        # normal (no error)
        self._asserts_for_dport_80_1024(
            AggregatedEventParser,
            raw='80 1024',
            extra_parser_attrs={
                'group_id_components': ['dport', 'time', 'not-found'],
            },
            extra_output_items1={
                '_group': '80_2014-01-10 10:14:00_None',
            },
            extra_output_items2={
                '_group': '1024_2014-01-10 10:14:00_None',
            })

        self._asserts_for_dport_80_1024(
            AggregatedEventParser,
            raw='80 1024',
            extra_parser_attrs={
                'group_id_components': 'dport',  # single string is also OK
            },
            extra_output_items1={
                '_group': '80',
            },
            extra_output_items2={
                '_group': '1024',
            })

        self._asserts_for_dport_80_1024(
            AggregatedEventParser,
            raw='80 1024',
            extra_parser_attrs={
                'group_id_components': ('ip', 'dport'),  # 'ip' means address[0]['ip']
            },
            extra_input_items={
                'address': {'ip': '11.22.33.44'},
            },
            extra_output_items1={
                'address': [{'ip': '11.22.33.44'}],
                '_group': '11.22.33.44_80',
            },
            extra_output_items2={
                'address': [{'ip': '11.22.33.44'}],
                '_group': '11.22.33.44_1024',
            })

        self._asserts_for_dport_80_1024(
            AggregatedEventParser,
            raw='80 1024',
            extra_parser_attrs={
                'group_id_components': ('ip', 'dport'),
            },
            # ip not given
            extra_output_items1={
                '_group': 'None_80',
            },
            extra_output_items2={
                '_group': 'None_1024',
            })

        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        # NOTE: it's *silenced* for non-blacklist events
        self._asserts_for_dport_80_1024(
            AggregatedEventParser,
            raw='80 ADJUSTER-ERROR 1024',
            extra_parser_attrs={
                'group_id_components': ['ip', 'dport'],
            },
            extra_output_items1={
                '_group': 'None_80',
            },
            extra_output_items2={
                '_group': 'None_1024',
            })

    def test_AggregatedEventParser_subclass__not_silenced_error(self, *args):
        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._asserts_for_loud_error(
            AggregatedEventParser,
            error_cls=self.MyError,
            raw='80 NON-ADJUSTER-ERROR 1024')

        # error raised in postprocess_data() due to lack of values
        # the '_group' value could be made of
        self._asserts_for_loud_error(
            AggregatedEventParser,
            error_cls=ValueError,
            raw='80 1024',
            extra_parser_attrs={
                'group_id_components': ['not-found', 'dip'],
            },
            required_error_attrs={
                '_n6_event_rid': '0123456789abcdef0123456789abcdef',
                '_n6_event_id': ANY,
            })

    # BlackListParser subclasses

    def test_BlackListParser_subclass(self, *args):
        # normal (no error)
        self._asserts_for_dport_80_1024(
            BlackListParser,
            raw='80 1024',
            extra_input_items={'expires': '2014-02-28 10:00:00'},  # obligatory for blacklists
            extra_output_items1={
                '_bl-series-id': '0123456789abcdef0123456789abcdef',
                '_bl-series-total': 2,
                '_bl-series-no': 1,
                '_bl-time': '2014-01-10 10:14:00',
                '_bl-current-time': self.base_data['properties.timestamp'],
                'expires': '2014-02-28 10:00:00',
            },
            extra_output_items2={
                '_bl-series-id': '0123456789abcdef0123456789abcdef',
                '_bl-series-total': 2,
                '_bl-series-no': 2,
                '_bl-time': '2014-01-10 10:14:00',
                '_bl-current-time': self.base_data['properties.timestamp'],
                'expires': '2014-02-28 10:00:00',
            })

    def test_BlackListParser_subclass__not_silenced_error(self, *args):
        # data error in an event (AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block)
        self._asserts_for_loud_error(
            BlackListParser,
            error_cls=AdjusterError,
            raw='80 ADJUSTER-ERROR 1024')

        # non-AdjusterError exception within
        # `with self.new_record_dict(data) as parsed: ...` block
        self._asserts_for_loud_error(
            BlackListParser,
            error_cls=self.MyError,
            raw='80 NON-ADJUSTER-ERROR 1024')

    # some wrong BaseParser/AggregatedEventParser/BlackListParser subclasses...

    def test_record_dict_context_manager_not_used(self, *args):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    for dport in data['raw'].split(' '):
                        # lacking 'with...' statement:
                        parsed = self.new_record_dict(data)
                        parsed['dport'] = dport
                        parsed['time'] = '2014-01-10 11:14:00.248114'
                        yield parsed
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw='80 1024')
            with self.assertRaises(AssertionError):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())

    def test_record_dict_context_manager_used_more_than_once(self, *args):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    for dport in data['raw'].split(' '):
                        # two 'with...' statements for the same record dict:
                        with self.new_record_dict(data) as parsed:
                            parsed['dport'] = dport
                        with parsed:
                            parsed['time'] = '2014-01-10 11:14:00.248114'
                            yield parsed
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw='80 1024')
            with self.assertRaises(TypeError):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())

    # some other errors...

    def test__parse__yielded_no_items(self, *args):
        for base_parser_cls in (BaseParser,
                                AggregatedEventParser,
                                BlackListParser):
            class MyParser(self.MyParserMixIn, base_parser_cls):
                def parse(self, data):
                    return  # "empty" generator
                    yield
            parser = MyParser.__new__(MyParser)
            data = dict(self.base_data, raw='80 1024')
            with self.assertRaises(ValueError):
                parser.get_output_bodies(data, FilePagedSequence._instance_mock())


## TODO:
# * more BaseParser tests
# * TabDataParser and BlackListTabDataParser tests

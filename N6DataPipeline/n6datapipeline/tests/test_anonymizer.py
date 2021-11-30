# Copyright (c) 2013-2021 NASK. All rights reserved.

import datetime
import json
import unittest
from unittest.mock import (
    ANY,
    MagicMock,
    call,
    patch,
    sentinel as sen,
)

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6datapipeline.aux.anonymizer import Anonymizer
from n6lib.const import TYPE_ENUMS
from n6lib.data_spec import N6DataSpec
from n6lib.db_filtering_abstractions import RecordFacadeForPredicates
from n6lib.unit_test_helpers import TestCaseMixin, MethodProxy
from n6sdk.exceptions import (
    ResultKeyCleaningError,
    ResultValueCleaningError,
)



@expand
class TestAnonymizer__input_callback(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.event_type = 'bl-update'
        self.event_data = {'some...': 'content...', 'id': 'some id...'}
        self.routing_key = self.event_type + '.filtered.*.*'
        self.body = json.dumps(self.event_data)
        self.resource_to_org_ids = {}

        self.mock = MagicMock(__class__=Anonymizer)
        self.meth = MethodProxy(Anonymizer, self.mock, '_process_input')

        self.mock._get_resource_to_org_ids.return_value = self.resource_to_org_ids
        self.mock._get_result_dicts_and_output_body.return_value = (
            sen.raw_result_dict,
            sen.cleaned_result_dict,
            sen.output_body,
        )
        self.force_exit_on_any_remaining_entered_contexts_mock = self.patch(
            'n6datapipeline.aux.anonymizer.force_exit_on_any_remaining_entered_contexts')


    @foreach(
        param(resource_to_org_ids_items={
            'foo': [sen.o1, sen.o2],
        }),
        param(resource_to_org_ids_items={
            'foo': [sen.o1, sen.o2],
            'bar': [],
        }),
        param(resource_to_org_ids_items={
            'foo': [],
            'bar': [sen.o3, sen.o4, sen.o5],
        }),
        param(resource_to_org_ids_items={
            'foo': [sen.o1, sen.o2],
            'bar': [sen.o3, sen.o4, sen.o5],
        }),
    )
    def test_with_some_org_ids(self, resource_to_org_ids_items):
        self.resource_to_org_ids.update(resource_to_org_ids_items)

        self.meth.input_callback(
            self.routing_key,
            self.body,
            sen.properties)

        self.assertEqual(self.force_exit_on_any_remaining_entered_contexts_mock.mock_calls, [
            call(self.mock.auth_api),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.setting_error_event_info(self.event_data),
            call.setting_error_event_info().__enter__(),
            call._check_event_type(
                self.event_type,
                self.event_data),
            call.auth_api.__enter__(),
            call._get_resource_to_org_ids(
                self.event_type,
                self.event_data),
            call._get_result_dicts_and_output_body(
                self.event_type,
                self.event_data,
                self.resource_to_org_ids),
            call._publish_output_data(
                self.event_type,
                self.resource_to_org_ids,
                sen.raw_result_dict,
                sen.cleaned_result_dict,
                sen.output_body),
            call.auth_api.__exit__(None, None, None),
            call.setting_error_event_info().__exit__(None, None, None),
        ])


    @foreach(
        param(resource_to_org_ids_items={}),
        param(resource_to_org_ids_items={
            'foo': [],
        }),
        param(resource_to_org_ids_items={
            'foo': [],
            'bar': [],
        }),
    )
    def test_without_org_ids(self, resource_to_org_ids_items):
        self.resource_to_org_ids.update(resource_to_org_ids_items)

        self.meth.input_callback(
            self.routing_key,
            self.body,
            sen.properties)

        self.assertEqual(self.force_exit_on_any_remaining_entered_contexts_mock.mock_calls, [
            call(self.mock.auth_api),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.setting_error_event_info(self.event_data),
            call.setting_error_event_info().__enter__(),
            call._check_event_type(
                self.event_type,
                self.event_data),
            call.auth_api.__enter__(),
            call._get_resource_to_org_ids(
                self.event_type,
                self.event_data),
            call.auth_api.__exit__(None, None, None),
            call.setting_error_event_info().__exit__(None, None, None),
        ])


    def test_with_some_error(self):
        self.resource_to_org_ids.update({
            'foo': [sen.o1, sen.o2],
            'bar': [sen.o3, sen.o4, sen.o5],
        })
        exc_type = ZeroDivisionError  # (just an example exception class)
        self.mock._get_result_dicts_and_output_body.side_effect = exc_type

        with self.assertRaises(exc_type) as exc_context:
            self.meth.input_callback(
                self.routing_key,
                self.body,
                sen.properties)

        self.assertEqual(self.force_exit_on_any_remaining_entered_contexts_mock.mock_calls, [
            call(self.mock.auth_api),
        ])
        self.assertEqual(self.mock.mock_calls, [
            call.setting_error_event_info(self.event_data),
            call.setting_error_event_info().__enter__(),
            call._check_event_type(
                self.event_type,
                self.event_data),
            call.auth_api.__enter__(),
            call._get_resource_to_org_ids(
                self.event_type,
                self.event_data),
            call._get_result_dicts_and_output_body(
                self.event_type,
                self.event_data,
                self.resource_to_org_ids),
            call.auth_api.__exit__(exc_type, exc_context.exception, ANY),
            call.setting_error_event_info().__exit__(exc_type, exc_context.exception, ANY),
        ])



@expand
class TestAnonymizer___check_event_type(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.mock = MagicMock(__class__=Anonymizer)
        self.meth = MethodProxy(Anonymizer, self.mock, '_VALID_EVENT_TYPES')


    @foreach(
        param(
            event_type='event',
            event_data={
                'some_key': sen.some_value,
            },
        ).label('no type in event data'),
        param(
            event_type='event',
            event_data={
                'type': 'event',
                'some_key': sen.some_value,
            },
        ).label('type "event" in event data'),
        param(
            event_type='bl-update',
            event_data={
                'type': 'bl-update',
                'some_key': sen.some_value,
            },
        ).label('another type in event data'),
    )
    def test_matching_and_valid(self, event_type, event_data):
        assert (event_type == event_data.get('type', 'event') and
                event_type in TYPE_ENUMS)  # (test case self-test)

        self.meth._check_event_type(event_type, event_data)

        # the _check_event_type() method is called outside the AuthAPI
        # context (outside its `with` statement) -- so we want to ensure
        # that no AuthAPI methods are called:
        self.assertEqual(self.mock.auth_api.mock_calls, [])


    @foreach(
        param(
            event_type='event',
            event_data={
                'type': 'bl-update',
                'some_key': sen.some_value,
            },
        ).label('type "event" does not match another one'),
        param(
            event_type='bl-update',
            event_data={
                'type': 'event',
                'some_key': sen.some_value,
            },
        ).label('another type does not match "event"'),
    )
    def test_not_matching(self, event_type, event_data):
        assert (event_type != event_data.get('type', 'event') and
                event_type in TYPE_ENUMS)  # (test case self-test)

        with self.assertRaises(ValueError):
            self.meth._check_event_type(event_type, event_data)

        # the _check_event_type() method is called outside the AuthAPI
        # context (outside its `with` statement) -- so we want to ensure
        # that no AuthAPI methods are called:
        self.assertEqual(self.mock.auth_api.mock_calls, [])


    def test_matching_but_not_valid(self):
        event_type = 'illegal'
        event_data = {
            'type': event_type,
            'some_key': sen.some_value,
        }
        assert event_type not in TYPE_ENUMS  # (test case self-test)

        with self.assertRaises(ValueError):
            self.meth._check_event_type(event_type, event_data)

        # the _check_event_type() method is called outside the AuthAPI
        # context (outside its `with` statement) -- so we want to ensure
        # that no AuthAPI methods are called:
        self.assertEqual(self.mock.auth_api.mock_calls, [])


@expand
class TestAnonymizer___get_resource_to_org_ids(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.event_type = 'bl-update'

        def YES_predicate(record):
            self.assertIsInstance(record, RecordFacadeForPredicates)
            return True

        def NO_predicate(record):
            self.assertIsInstance(record, RecordFacadeForPredicates)
            return False

        self.mock = MagicMock(__class__=Anonymizer)
        self.meth = MethodProxy(Anonymizer, self.mock)

        self.mock.data_spec = N6DataSpec()
        self.mock.auth_api.get_source_ids_to_subs_to_stream_api_access_infos.return_value = \
            self.s_to_s_to_saai = {
                'src.empty': {},
                'src.some-1': {
                    sen.something_1: (
                        YES_predicate,
                        {
                            'inside': set(),
                            'threats': set(),
                            'search': set(),
                        }
                    ),
                    sen.something_2: (
                        YES_predicate,
                        {
                            'inside': {'o4'},
                            'threats': set(),
                            'search': {'o1', 'o2', 'o3', 'o4', 'o5', 'o6'},
                        }
                    ),
                    sen.something_3: (
                        NO_predicate,
                        {
                            'inside': {'o2'},
                            'threats': {'o3'},
                            'search': set(),
                        }
                    ),
                    sen.something_4: (
                        NO_predicate,
                        {
                            'inside': {'o1', 'o3', 'o9'},
                            'threats': {'o3', 'o5', 'o6'},
                            'search': {'o3', 'o4', 'o5', 'o6'},
                        }
                    ),
                },
                'src.some-2': {
                    sen.something_5: (
                        YES_predicate,
                        {
                            'inside': {'o1', 'o3', 'o9'},
                            'threats': {'o3', 'o5', 'o6'},
                            'search': {'o3', 'o4', 'o5', 'o6'},
                        }
                    ),
                    sen.something_6: (
                        YES_predicate,
                        {
                            'inside': {'o2'},
                            'threats': {'o2'},
                            'search': set(),
                        }
                    ),
                    sen.something_7: (
                        YES_predicate,
                        {
                            'inside': set(),
                            'threats': {'o8'},
                            'search': set(),
                        }
                    ),
                    sen.something_8: (
                        YES_predicate,
                        {
                            'inside': set(),
                            'threats': set(),
                            'search': set(),
                        }
                    ),
                    sen.something_9: (
                        NO_predicate,
                        {
                            'inside': {'o1', 'o5', 'o4', 'o9'},
                            'threats': {'o3', 'o4', 'o5', 'o9'},
                            'search': {'o1', 'o2', 'o3', 'o4'},
                        }
                    ),
                },
            }


    @foreach(
        param(
            event_data=dict(
                source='src.not-found',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=dict(
                inside=[],
                threats=[],
            ),
        ).label('no such source'),
        param(
            event_data=dict(
                source='src.empty',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=dict(
                inside=[],
                threats=[],
            ),
        ).label('no subsources'),
        param(
            event_data=dict(
                source='src.some-1',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=dict(
                inside=[],
                threats=[],
            ),
        ).label('no matching subsources/organizations'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=dict(
                inside=['o1', 'o2', 'o3'],
                threats=['o2', 'o3', 'o5', 'o6', 'o8'],
            ),
        ).label('some matching subsources and organizations (1)'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o2', 'o4', 'o9'],
            ),
            expected_result=dict(
                inside=['o2', 'o9'],
                threats=['o2', 'o3', 'o5', 'o6', 'o8'],
            ),
        ).label('some matching subsources and organizations (2)'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o4'],
            ),
            expected_result=dict(
                inside=[],
                threats=['o2', 'o3', 'o5', 'o6', 'o8'],
            ),
        ).label('some matching subsources and organizations (only "threats")'),
    )
    def test_normal(self, event_data, expected_result):
        expected_mock_calls = [
            call.auth_api.get_source_ids_to_subs_to_stream_api_access_infos(),
        ]

        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock:
            result = self.meth._get_resource_to_org_ids(self.event_type, event_data)

        self.assertEqual(result, expected_result)
        self.assertEqual(self.mock.mock_calls, expected_mock_calls)
        self.assertFalse(LOGGER_mock.error.mock_calls)


    def test_error(self):
        event_data = dict(
            source='src.some-2',
            client=['o5', 'o1', 'o3', 'o2'],
        )
        res_to_org_ids = {
            'inside': set(),
            'threats': {'o8'},
            'search': set(),
        }
        exc_type = ZeroDivisionError  # (just an example exception class)
        def raise_exc(rec):
            raise exc_type('blablabla')
        self.s_to_s_to_saai['src.some-2'][sen.something_7] = raise_exc, res_to_org_ids

        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock, \
             self.assertRaises(exc_type):
            self.meth._get_resource_to_org_ids(self.event_type, event_data)

        self.assertEqual(len(LOGGER_mock.error.mock_calls), 1)



@expand
class TestAnonymizer___get_result_dicts_and_output_body(TestCaseMixin, unittest.TestCase):

    forward_source_mapping = {
        'some.source': 'hidden.42',
    }

    event_raw_base = dict(
        id=(32 * '3'),
        rid=(32 * '4'),        # (restricted - to be skipped before *value* cleaning)
        source='some.source',  # (to be anonymized)
        restriction='public',  # (restricted - to be skipped before *value* cleaning)
        confidence='low',
        category='malurl',
        time='2013-07-12 11:30:00',
    )

    cleaned_base = dict(
        id=(32 * '3'),
        source='hidden.42',    # (after anonymization)
        confidence='low',
        category='malurl',
        time=datetime.datetime(2013, 7, 12, 11, 30, 00),
        type=sen.TO_BE_SET,
    )


    def setUp(self):
        self.mock = MagicMock(__class__=Anonymizer)
        self.meth = MethodProxy(Anonymizer, self.mock)

        self.mock.data_spec = N6DataSpec()
        self.mock.auth_api.get_anonymized_source_mapping.return_value = {
            'forward_mapping': self.forward_source_mapping,
        }
        self.mock.auth_api.get_dip_anonymization_disabled_source_ids.return_value = frozenset()


    @foreach(
        param(
            event_type='event',
            event_data=dict(
                event_raw_base,
                client=[],           # (empty `client` -- to be skipped before *any* cleaning)
            ),
            expected_raw=dict(
                event_raw_base,
            ),
            expected_cleaned=dict(
                cleaned_base,
                type='event',        # (event_type value set *after* cleaning)
            ),
        ),
        param(
            event_type='event',
            event_data=dict(
                event_raw_base,
                client=['o1', 'o3', 'o2'],
                address=[],          # (empty `address` -- to be skipped before *any* cleaning)
                dip='192.168.0.1',
                fqdn='www.example.com',
                type='foobar',       # (not a result key -- to be skipped before *any* cleaning)
                blabla='foooo',      # (not a result key -- to be skipped before *any* cleaning)
                until='spamspam',
                min_amplification=4000*'foo bar',
                rid='xxxxx',
            ),
            expected_raw=dict(
                event_raw_base,
                client=['o1', 'o3', 'o2'],  # (restricted -- to be skipped before *value* cleaning)
                dip='192.168.0.1',   # (to be anonymized -> as 'adip')
                fqdn='www.example.com',
                until='spamspam',    # (restricted -- to be skipped before *value* cleaning)
                min_amplification=4000*'foo bar',   # (restricted [custom]      -- as above)
                rid='xxxxx',                        # (restricted [+required]   -- as above)
            ),
            expected_cleaned=dict(
                cleaned_base,
                adip='x.x.0.1',      # ('dip' value after anonymization)
                fqdn='www.example.com',
                type='event',        # (event_type value set *after* cleaning)
            ),
        ),
        param(
            event_type='bl-update',
            event_data=dict(event_raw_base, **{
                'client': [],         # (empty `client` -- to be skipped before *any* cleaning)
                'address': [{'ip': '1.2.3.4', 'cc': 'pl', 'asn': '1.1'}],
                'adip': 'x.10.20.30',
                'dip': '192.168.0.1',
                '_bl-series-no': 42,  # (not a result field -- to be skipped before *any* cleaning)
                'type': 'barfoo',     # (not a result field -- to be skipped before *any* cleaning)
            }),
            expected_raw=dict(event_raw_base, **{
                'address': [{'ip': '1.2.3.4', 'cc': 'pl', 'asn': '1.1'}],
                'adip': 'x.10.20.30',
                'dip': '192.168.0.1',  # (to be just omitted -- 'adip' is explicitly specified)
            }),
            expected_cleaned=dict(
                cleaned_base,
                address=[{'ip': '1.2.3.4', 'cc': 'PL', 'asn': 65537}],
                adip='x.10.20.30',    # (just given 'adip')
                type='bl-update',     # (event_type value set *after* cleaning)
            ),
        ),
        # below -- the same two as above but with dip anonymization disabled
        param(
            event_type='event',
            event_data=dict(
                event_raw_base,
                client=['o1', 'o3', 'o2'],
                address=[],          # (empty `address` -- to be skipped before *any* cleaning)
                dip='192.168.0.1',
                fqdn='www.example.com',
                type='foobar',       # (not a result key -- to be skipped before *any* cleaning)
                blabla='foooo',      # (not a result key -- to be skipped before *any* cleaning)
                until='spamspam',
                min_amplification=4000*'foo bar',
                rid='xxxxx',
            ),
            expected_raw=dict(
                event_raw_base,
                client=['o1', 'o3', 'o2'],  # (restricted -- to be skipped before *value* cleaning)
                dip='192.168.0.1',   # (to be *not* anonymized [sic])
                fqdn='www.example.com',
                until='spamspam',    # (restricted -- to be skipped before *value* cleaning)
                min_amplification=4000*'foo bar',   # (restricted [custom]      -- as above)
                rid='xxxxx',                        # (restricted [+required]   -- as above)
            ),
            expected_cleaned=dict(
                cleaned_base,
                dip='192.168.0.1',   # (*not* anonymized [sic])
                fqdn='www.example.com',
                type='event',        # (event_type value set *after* cleaning)
            ),
            dip_anonymization_disabled_source_ids=frozenset(['some.source']),
        ),
        param(
            event_type='bl-update',
            event_data=dict(event_raw_base, **{
                'client': [],         # (empty `client` -- to be skipped before *any* cleaning)
                'address': [{'ip': '1.2.3.4', 'cc': 'pl', 'asn': '1.1'}],
                'adip': 'x.10.20.30',
                'dip': '192.168.0.1',
                '_bl-series-no': 42,  # (not a result field -- to be skipped before *any* cleaning)
                'type': 'barfoo',     # (not a result field -- to be skipped before *any* cleaning)
            }),
            expected_raw=dict(event_raw_base, **{
                'address': [{'ip': '1.2.3.4', 'cc': 'pl', 'asn': '1.1'}],
                'adip': 'x.10.20.30',
                'dip': '192.168.0.1',
            }),
            expected_cleaned=dict(
                cleaned_base,
                address=[{'ip': '1.2.3.4', 'cc': 'PL', 'asn': 65537}],
                adip='x.10.20.30',    # (just given 'adip')
                dip='192.168.0.1',    # (just given 'dip' [sic])
                type='bl-update',     # (event_type value set *after* cleaning)
            ),
            dip_anonymization_disabled_source_ids=frozenset(['some.source']),
        ),
    )
    def test_normal(self, event_type, event_data, expected_raw, expected_cleaned,
                    dip_anonymization_disabled_source_ids=frozenset()):
        expected_auth_api_calls = [call.get_anonymized_source_mapping()]
        if 'dip' in event_data:
            expected_auth_api_calls.append(call.get_dip_anonymization_disabled_source_ids())
        self.mock.auth_api.get_dip_anonymization_disabled_source_ids.return_value = (
            dip_anonymization_disabled_source_ids)

        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock:
            (raw_result_dict,
             cleaned_result_dict,
             output_body) = self.meth._get_result_dicts_and_output_body(
                event_type,
                event_data,
                sen.resource_to_org_ids)

        self.assertEqual(raw_result_dict, expected_raw)
        self.assertEqual(cleaned_result_dict, expected_cleaned)
        self.assertEqual(
            json.loads(output_body),
            self._get_expected_body_content(expected_cleaned))
        self.assertCountEqual(self.mock.auth_api.mock_calls, expected_auth_api_calls)
        self.assertFalse(LOGGER_mock.error.mock_calls)

    @staticmethod
    def _get_expected_body_content(expected_cleaned):
        formatted_time = expected_cleaned['time'].isoformat() + 'Z'
        assert formatted_time[10] == 'T' and formatted_time[-1] == 'Z'
        return dict(
            expected_cleaned,
            time=formatted_time)


    @foreach(
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
            ),
            without_keys={'id'},
            exc_type=ResultKeyCleaningError,
        ).label('missing key: required and unrestricted'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
            ),
            without_keys={'source'},
            exc_type=ResultKeyCleaningError,
        ).label('missing key: required and anonymized'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
            ),
            without_keys={'rid'},
            exc_type=ResultKeyCleaningError,
        ).label('missing key: required and restricted'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
                id='spam',
            ),
            exc_type=ResultValueCleaningError,
        ).label('illegal value for required and unrestricted key'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
                fqdn='foo..bar',
            ),
            exc_type=ResultValueCleaningError,
        ).label('illegal value for optional and unrestricted key'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
                dip='spam',
            ),
            exc_type=ResultValueCleaningError,
        ).label('illegal value for optional and anonymized-source key'),
        param(
            event_data=dict(
                event_raw_base,
                client=['o3', 'o1', 'o2'],
                adip='spam',
            ),
            exc_type=ResultValueCleaningError,
        ).label('illegal value for optional and anonymized-target key'),
    )
    def test_error(self, event_data, exc_type, without_keys=()):
        event_type = 'event'
        event_data = event_data.copy()
        for key in without_keys:
            del event_data[key]
        resource_to_org_ids = {'foo': {'bar'}, 'baz': {'spam', 'ham'}}
        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock, \
             self.assertRaises(exc_type):
            self.meth._get_result_dicts_and_output_body(
                event_type,
                event_data,
                resource_to_org_ids)
        self.assertEqual(len(LOGGER_mock.error.mock_calls), 1)



@expand
class TestAnonymizer___publish_output_data(TestCaseMixin, unittest.TestCase):

    def setUp(self):
        self.cleaned_result_dict = {
            'category': 'bots',
            'source': 'hidden.42',
        }
        self.mock = MagicMock(__class__=Anonymizer)
        self.meth = MethodProxy(Anonymizer, self.mock, 'OUTPUT_RK_PATTERN')


    @foreach(
        param(
            resource_to_org_ids={
                'inside': ['o2', 'o3'],
                'threats': ['o3', 'o5', 'o8'],
            },
            expected_publish_output_calls=[
                call(
                    routing_key='inside.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o3'}},
                ),
                call(
                    routing_key='inside.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o2'}},
                ),
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o8'}},
                ),
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o5'}},
                ),
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o3'}},
                ),
            ],
        ).label('for both resources'),
        param(
            resource_to_org_ids={
                'inside': ['o2', 'o3'],
                'threats': [],
            },
            expected_publish_output_calls=[
                call(
                    routing_key='inside.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o3'}},
                ),
                call(
                    routing_key='inside.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o2'}},
                ),
            ],
        ).label('for "inside" only'),
        param(
            resource_to_org_ids={
                'inside': [],
                'threats': ['o3', 'o5', 'o8'],
            },
            expected_publish_output_calls=[
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o8'}},
                ),
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o5'}},
                ),
                call(
                    routing_key='threats.bots.hidden.42',
                    body=sen.output_body,
                    prop_kwargs={'headers': {'n6-client-id': 'o3'}},
                ),
            ],
        ).label('for "threats" only'),
        param(
            resource_to_org_ids={
                'inside': [],
                'threats': [],
            },
            expected_publish_output_calls=[],
        ).label('for no resources'),
    )
    def test_normal(self, resource_to_org_ids, expected_publish_output_calls):
        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock:
            self.meth._publish_output_data(
                sen.event_type,
                resource_to_org_ids,
                sen.raw_result_dict,
                self.cleaned_result_dict,
                sen.output_body)

        self.assertEqual(
            self.mock.publish_output.mock_calls,
            expected_publish_output_calls)
        self.assertFalse(LOGGER_mock.error.mock_calls)


    def test_error(self):
        resource_to_org_ids = {
            'inside': ['o2', 'o3'],
            'threats': ['o3', 'o5', 'o8'],
        }
        expected_publish_output_calls = [
            call(
                routing_key='inside.bots.hidden.42',
                body=sen.output_body,
                prop_kwargs={'headers': {'n6-client-id': 'o3'}},
            ),
            call(
                routing_key='inside.bots.hidden.42',
                body=sen.output_body,
                prop_kwargs={'headers': {'n6-client-id': 'o2'}},
            ),
            call(
                routing_key='threats.bots.hidden.42',
                body=sen.output_body,
                prop_kwargs={'headers': {'n6-client-id': 'o8'}},
            ),
        ]
        exc_type = ZeroDivisionError  # (just an example exception class)
        self.mock.publish_output.side_effect = [
            None,
            None,
            exc_type,
        ]

        with patch('n6datapipeline.aux.anonymizer.LOGGER') as LOGGER_mock, \
             self.assertRaises(exc_type):
            self.meth._publish_output_data(
                sen.event_type,
                resource_to_org_ids,
                sen.raw_result_dict,
                self.cleaned_result_dict,
                sen.output_body)

        self.assertEqual(
            self.mock.publish_output.mock_calls,
            expected_publish_output_calls)
        self.assertEqual(LOGGER_mock.error.mock_calls, [
            call(
                ANY,
                'threats',
                'o8',
                sen.event_type,
                sen.raw_result_dict,
                'threats.bots.hidden.42',
                sen.output_body,
                (
                    "for the resource 'inside' -- "
                    "* skipped for the org ids: none; "
                    "* done for the org ids: 'o3', 'o2';  "
                    "for the resource 'threats' -- "
                    "* skipped for the org ids: 'o3', 'o5', 'o8'; "
                    "* done for the org ids: none"
                ),
            ),
        ])



if __name__ == '__main__':
    unittest.main()

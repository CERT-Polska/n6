# Copyright (c) 2015-2025 NASK. All rights reserved.

import unittest

from unittest.mock import (
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

from n6datapipeline.counter import Counter
from n6lib.const import RESTRICTION_ENUMS
from n6lib.db_filtering_abstractions import RecordFacadeForPredicates
from n6lib.data_spec import N6DataSpec
from n6lib.unit_test_helpers import (
    TestCaseMixin,
    MethodProxy,
)


@expand
class TestCounter__get_clients_list(TestCaseMixin, unittest.TestCase):
    def setUp(self):
        self.event_type = 'bl-change'
        self.mock = MagicMock(__class__=Counter)
        self.meth = MethodProxy(Counter, self.mock)
        self.mock.data_spec = N6DataSpec()

    def _get_return_value(self, full_access):
        def YES_predicate(record):
            self.assertIsInstance(record, RecordFacadeForPredicates)
            return True
        def NO_predicate(record):
            self.assertIsInstance(record, RecordFacadeForPredicates)
            return False
        return {
            'src.empty': {},
            'src.some-1': {
                (sen.something_1, full_access): (
                    YES_predicate,
                    set(),
                ),
                (sen.something_2, full_access): (
                    YES_predicate,
                    {'o4'},
                ),
                (sen.something_3, full_access): (
                    NO_predicate,
                    {'o2'},
                ),
                (sen.something_4, full_access): (
                    NO_predicate,
                    {'o1', 'o3', 'o9'},
                ),
            },
            'src.some-2': {
                (sen.something_5, full_access): (
                    YES_predicate,
                    {'o1', 'o3', 'o9'},
                ),
                (sen.something_6, full_access): (
                    YES_predicate,
                    {'o2'},
                ),
                (sen.something_7, full_access): (
                    YES_predicate,
                    set(),
                ),
                (sen.something_8, full_access): (
                    NO_predicate,
                    {'o1', 'o5', 'o4', 'o9'},
                ),
            },
        }

    @foreach(
        param(
            event_data=dict(
                source='src.not-found',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=[],
        ).label('no such source'),
        param(
            event_data=dict(
                source='src.empty',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=[],
        ).label('no subsources'),
        param(
            event_data=dict(
                source='src.some-1',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=[],
        ).label('no matching subsources/organizations (1)'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o4'],
            ),
            expected_result=[],
        ).label('no matching subsources/organizations (2)'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o5', 'o1', 'o3', 'o2'],
            ),
            expected_result=['o1', 'o2', 'o3'],
        ).label('some matching subsources and organizations (1)'),
        param(
            event_data=dict(
                source='src.some-2',
                client=['o2', 'o4', 'o9'],
            ),
            expected_result=['o2', 'o9'],
        ).label('some matching subsources and organizations (2)'),
    )
    @foreach(
        # the `full_access` flag got by _get_clients_list() from
        # auth.get_source_ids_to_notification_access_info_mappings()
        # should be irrelevant (note that predicates are supposed to
        # incorporate checks related to the `full_access` flag)
        param(full_access=False),
        param(full_access=True),
    )
    @foreach(
        # **For this test** the value of `ignored` should be
        # irrelevant because we have only two predicates here:
        # `YES_predicate()` and `NO_predicate()` (they are test-only,
        # "mocked" predicates, i.e., they return just fixed values,
        # without any inspection of given event data records).
        param(ignored=sen.ABSENT),
        param(ignored=False),
        param(ignored=True),
    )
    @foreach([
        # **For this test** the value of `restriction` should be
        # irrelevant because we have only two predicates here:
        # `YES_predicate()` and `NO_predicate()` (they are test-only,
        # "mocked" predicates, i.e., they return just fixed values,
        # without any inspection of given event data records).
        param(restriction=restriction)
        for restriction in RESTRICTION_ENUMS
    ])
    def test_normal(self, restriction, ignored, full_access, event_data, expected_result):
        event_data = dict(event_data, restriction=restriction)
        if ignored is not sen.ABSENT:
            event_data['ignored'] = ignored
        self.mock.auth_api.get_source_ids_to_notification_access_info_mappings.return_value = (
            self._get_return_value(full_access))
        expected_mock_calls = [
            call.auth_api.__enter__(),
            call.auth_api.get_source_ids_to_notification_access_info_mappings(),
            call.auth_api.__exit__(None, None, None)
        ]
        with patch('n6datapipeline.counter.LOGGER') as LOGGER_mock:
            result = self.meth._get_clients_list(self.event_type, event_data)
        self.assertEqual(result, expected_result)
        self.assertEqual(self.mock.mock_calls, expected_mock_calls)
        self.assertFalse(LOGGER_mock.error.mock_calls)

    def test_error(self):
        exc_type = ZeroDivisionError  # (just an example exception class)
        self.mock.auth_api.get_source_ids_to_notification_access_info_mappings.\
            side_effect = exc_type
        event_data = dict(
            source='src.some-32',
            client=['o5', 'o1', 'o3', 'o2'],
        )
        with patch('n6datapipeline.counter.LOGGER') as LOGGER_mock, \
             self.assertRaises(exc_type):
            self.meth._get_clients_list(self.event_type, event_data)
        self.assertEqual(len(LOGGER_mock.error.mock_calls), 1)


if __name__ == '__main__':
    unittest.main()

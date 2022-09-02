# Copyright (c) 2019-2022 NASK. All rights reserved.

from unittest.mock import (
    call,
    sentinel,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.abuse_ch import AbuseChFeodoTrackerCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
)


class _TestAbuseChDownloadingTimeOrderedRowsCollectorBase(BaseCollectorTestCase):

    COLLECTOR_CLASS = None   # to be set in concrete test classes

    EXAMPLE_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {},
    }

    def _perform_test(
            self,
            config_content,
            initial_state,
            orig_data,
            expected_publish_output_calls,
            expected_saved_state,
            label,                 # argument irrelevant here (passed in by `@foreach`)   # noqa
            context_targets):      # argument irrelevant here (passed in by `@foreach`)   # noqa

        collector = self.prepare_collector(self.COLLECTOR_CLASS,
                                           config_content=config_content,
                                           initial_state=initial_state)

        def obtain_orig_data():
            return orig_data

        collector.obtain_orig_data = obtain_orig_data
        collector.run_collection()
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)


@expand
class TestAbuseChFeodoTrackerCollector(_TestAbuseChDownloadingTimeOrderedRowsCollectorBase):

    COLLECTOR_CLASS = AbuseChFeodoTrackerCollector

    EXAMPLE_ORIG_DATA = (
        b'# row which should be ignored by collector\n'
        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5\n'
        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3\n'
        b'2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2\n'
        b'2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1\n'
        b'2019-08-20 00:00:00,0.0.0.0,447,online,2019-08-20,ExampleName0'
    )

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state={
                'newest_row_time': '2019-08-20 01:00:00',
                'newest_rows': {
                    '2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1',
                    '2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2',
                },
                'rows_count': 3
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5\n'
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
                        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3'
                    ),

                    # prop_kwargs
                    cls.EXAMPLE_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5'},
                'rows_count': 6
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                    ),

                    # prop_kwargs
                    cls.EXAMPLE_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

        yield param(
            config_content='''
                [AbuseChFeodoTrackerCollector]
                row_count_mismatch_is_fatal = no
                url = https://www.example.com
                download_retries = 5
            ''',
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'abuse-ch.feodotracker.202110',

                    # body
                    (
                        b'2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5\n'
                        b'2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4\n'
                        b'2019-08-20 02:00:00,3.3.3.3,447,online,2019-08-20,ExampleName3\n'
                        b'2019-08-20 01:00:00,2.2.2.2,447,online,2019-08-20,ExampleName2\n'
                        b'2019-08-20 01:00:00,1.1.1.1,447,online,2019-08-20,ExampleName1\n'
                        b'2019-08-20 00:00:00,0.0.0.0,447,online,2019-08-20,ExampleName0'
                    ),

                    # prop_kwargs
                    cls.EXAMPLE_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2019-08-20 03:00:00',
                'newest_rows': {
                    '2019-08-20 03:00:00,5.5.5.5,447,online,2019-08-20,ExampleName5',
                    '2019-08-20 03:00:00,4.4.4.4,447,online,2019-08-20,ExampleName4'
                },
                'rows_count': 6,
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

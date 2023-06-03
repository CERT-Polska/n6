# Copyright (c) 2020-2023 NASK. All rights reserved.

from unittest.mock import (
    ANY,
    call,
    sentinel,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.cert_pl import CertPlShieldCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestCertPlShieldCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = CertPlShieldCollector

    EXAMPLE_ORIG_DATA = (
        b'invalid\trow\twhich\tshould\tbe\tskipped\n'
        b'6\texample_6.com\t2020-06-03T14:00:00\n'
        b'5\texample_5.com\t2020-06-03T13:00:00\n'
        b'4\texample_4.com\t2020-06-03T12:00:00\n'
        b'3\texample_3.com\t2020-06-02T13:00:00\n'
        b'2\texample_2.com\t2020-06-01T14:00:00\n'
        b'1\texample_1.com\t2020-06-01T13:00:00'
    ),

    EXPECTED_PROP_KWARGS = {
        'timestamp': ANY,
        'message_id': ANY,
        'type': 'file',
        'content_type': 'text/csv',
        'headers': {},
    }

    def _perform_test(self,
                      config_content,
                      initial_state,
                      orig_data,
                      expected_publish_output_calls,
                      expected_saved_state,
                      label,                # arg (added by @foreach) irrelevant here
                      context_targets):     # arg (added by @foreach) irrelevant here

        collector = self.prepare_collector(self.COLLECTOR_CLASS,
                                           config_content=config_content,
                                           initial_state=initial_state)

        def prepare_orig_data():
            return b"".join(orig_data)

        collector.obtain_orig_data = prepare_orig_data
        collector.run_collection()
        self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)
        self.assertEqual(self.saved_state, expected_saved_state)

    @paramseq
    def cases(cls):
        yield param(
            config_content='''
                [CertPlShieldCollector]
                row_count_mismatch_is_fatal = False
                url=https://www.example.com
                download_retries=3
            ''',
            initial_state={
                'newest_row_time': '2020-06-03 12:00:00',
                'newest_rows': {
                    '3\texample_3.com\t2020-06-03T12:00:00',
                },
            },
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'cert-pl.shield',

                    # body
                    (
                        b'4\texample_4.com\t2020-06-03T12:00:00\n'
                        b'5\texample_5.com\t2020-06-03T13:00:00\n'
                        b'6\texample_6.com\t2020-06-03T14:00:00'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2020-06-03 14:00:00',
                'newest_rows': {
                    '6\texample_6.com\t2020-06-03T14:00:00'
                },
                'rows_count': 6
            },
        )

        yield param(
            config_content='''
                [CertPlShieldCollector]
                row_count_mismatch_is_fatal = False
                url=https://www.example.com
                download_retries=3
           ''',
            initial_state=sentinel.NO_STATE,
            orig_data=cls.EXAMPLE_ORIG_DATA,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'cert-pl.shield',

                    # body
                    (
                        b'1\texample_1.com\t2020-06-01T13:00:00\n'
                        b'2\texample_2.com\t2020-06-01T14:00:00\n'
                        b'3\texample_3.com\t2020-06-02T13:00:00\n'
                        b'4\texample_4.com\t2020-06-03T12:00:00\n'
                        b'5\texample_5.com\t2020-06-03T13:00:00\n'
                        b'6\texample_6.com\t2020-06-03T14:00:00'
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            expected_saved_state={
                'newest_row_time': '2020-06-03 14:00:00',
                'newest_rows': {
                    '6\texample_6.com\t2020-06-03T14:00:00'
                },
                'rows_count': 6
            },
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

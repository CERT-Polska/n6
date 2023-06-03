# Copyright (c) 2023 NASK. All rights reserved.

import gzip
from unittest.mock import call, patch, mock_open

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)
from n6datasources.collectors.manual import ManualCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import AnyInstanceOf


@expand
class TestManualCollector(BaseCollectorTestCase):

    COLLECTOR_CLASS = ManualCollector

    @patch('n6datasources.collectors.manual.existing_file', return_value='/path/to_file.txt')
    def _perform_test(self,
                      mock_existing_file,
                      orig_data,
                      cmdline_args,
                      expected_output,
                      **kwargs):

        with patch("builtins.open", mock_open(read_data=orig_data)) as mock_file:
            collector = self.prepare_collector(
                    self.COLLECTOR_CLASS,
                    cmdline_args=cmdline_args)

            collector.run_collection()

            self.assertEqual(self.publish_output_mock.mock_calls, expected_output)


    @paramseq
    def cases():
        orig_data=(
                b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain'
                b'2015-04-08 15:55:21,4.4.4.4,AS11,CA,1.1.1.1,example1.com'
                b'2015-04-08 14:52:49,5.5.5.5,AS22,SE,2.2.2.2,example2.com'
                b'2015-04-08 15:09:13,6.6.6.6,AS33,US,3.3.3.3,example3.com'
            )
        yield param(
            orig_data=orig_data,
            cmdline_args = [
                '--source_channel', 'unrestricted',
                '--category', 'bots',
                '--confidence', 'low', 
                '--restriction', 'public',
                '--origin', 'c2', 
                '--field_sep', ',',
                '--comment_prefix', '#', 
                '--column_spec', 'time,ip,-,-,dip,fqdn',
                './test.txt'
            ],
            expected_output=[
                call(
                    'manual.unrestricted',
                    (
                        b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain'
                        b'2015-04-08 15:55:21,4.4.4.4,AS11,CA,1.1.1.1,example1.com'
                        b'2015-04-08 14:52:49,5.5.5.5,AS22,SE,2.2.2.2,example2.com'
                        b'2015-04-08 15:09:13,6.6.6.6,AS33,US,3.3.3.3,example3.com'
                    ),
                    {
                        'message_id': AnyInstanceOf(str), 
                        'timestamp': AnyInstanceOf(int), 
                        'type': 'file', 
                        'content_type': 'text/plain',
                        'headers': {
                            '_do_not_resolve_fqdn_to_ip': False,
                            'meta': {
                                'event_base': {
                                    'category': 'bots', 
                                    'confidence': 'low', 
                                    'restriction': 'public', 
                                    'name': None, 
                                    'origin': 'c2', 
                                    'dataset': None, 
                                    'time': None}, 
                                    'dry_run': True,
                                    'parsing_info': {
                                        'field_separator': ',', 
                                        'comment_prefix': '#', 
                                        'column_spec': 'time,ip,-,-,dip,fqdn', 
                                        'time_format': None
                                        }, 
                                    }, 
                            }, 
                    }
                ),
            ],
        )
        yield param(
            orig_data=gzip.compress(orig_data),
            cmdline_args = [
                '--source_channel', 'pl',
                '--category', 'scam',
                '--confidence', 'medium', 
                '--restriction', 'public',
                '--origin', 'c2', 
                '--field_sep', ';',
                '--comment_prefix', '$', 
                '--column_spec', 'time,ip,-,-,dip,fqdn',
                './test.txt'
            ],
            expected_output=[
                call(
                    'manual.pl',
                    (
                        b'# TimestampUTC,ClientIP,ASnumber,CountryCode,DstIP,DstDomain'
                        b'2015-04-08 15:55:21,4.4.4.4,AS11,CA,1.1.1.1,example1.com'
                        b'2015-04-08 14:52:49,5.5.5.5,AS22,SE,2.2.2.2,example2.com'
                        b'2015-04-08 15:09:13,6.6.6.6,AS33,US,3.3.3.3,example3.com'
                    ),
                    {
                        'message_id': AnyInstanceOf(str), 
                        'timestamp': AnyInstanceOf(int), 
                        'type': 'file', 
                        'content_type': 'text/plain',
                        'headers': {
                            '_do_not_resolve_fqdn_to_ip': False,
                            'meta': {
                                'event_base': {
                                    'category': 'scam', 
                                    'confidence': 'medium', 
                                    'restriction': 'public', 
                                    'name': None, 
                                    'origin': 'c2', 
                                    'dataset': None, 
                                    'time': None}, 
                                    'dry_run': True,
                                    'parsing_info': {
                                        'field_separator': ';', 
                                        'comment_prefix': '$', 
                                        'column_spec': 'time,ip,-,-,dip,fqdn', 
                                        'time_format': None
                                        }, 
                                    }, 
                            }, 
                    }
                ),
            ],
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

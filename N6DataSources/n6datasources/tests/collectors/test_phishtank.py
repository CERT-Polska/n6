# Copyright (c) 2023-2025 NASK. All rights reserved.

from unittest.mock import (
    call,
    Mock,
    patch,
)

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6datasources.collectors.phishtank import PhishtankVerifiedCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.unit_test_helpers import AnyInstanceOf


@expand
class TestPhishtankVerifiedCollector(BaseCollectorTestCase):
    COLLECTOR_CLASS = PhishtankVerifiedCollector
    expected_source_channel = 'verified'
    EXPECTED_PROP_KWARGS = {
        'timestamp': AnyInstanceOf(int),
        'message_id': AnyInstanceOf(str),
        'type': 'blacklist',
        'content_type': 'text/csv',
        'headers': {},
    }

    def cases(cls):
        yield param(
            config_content='''
            [PhishtankVerifiedCollector]
            link_source=http://www.example.com/data/
            api_key=123456789abcdefghij
            format_options = data-example-valid.csv.bz2
            url=%(link_source)s%(api_key)s%(format_options)s
            period=60
            ''',
            headers={
                'Last-Modified': 'Thu, 9 Feb 2023 09:09:09 GMT',
                'Content-Type': 'text/csv'
            },
            data_example=
                    b"""phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target
                    1111111,http://example-phish1.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111111,
                    2023-02-09T06:00:00+00:00,yes,2023-02-09T06:06:06+00:00,yes,Other
                    1111112,http://example-phish2.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111112,
                    2023-02-09T07:00:00+00:00,yes,2023-02-09T07:07:07+00:00,yes,Other
                    1111113,https://example-phish3.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111113,
                    2023-02-09T08:00:00+00:00,yes,2023-02-09T08:08:08+00:00,yes,Other
                    """,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'phishtank.verified',

                    # body
                    (
                    b"""phish_id,url,phish_detail_url,submission_time,verified,verification_time,online,target
                    1111111,http://example-phish1.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111111,
                    2023-02-09T06:00:00+00:00,yes,2023-02-09T06:06:06+00:00,yes,Other
                    1111112,http://example-phish2.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111112,
                    2023-02-09T07:00:00+00:00,yes,2023-02-09T07:07:07+00:00,yes,Other
                    1111113,https://example-phish3.com,
                    http://www.phishtank.com/phish_detail.php?phish_id=1111113,
                    2023-02-09T08:00:00+00:00,yes,2023-02-09T08:08:08+00:00,yes,Other
                    """
                    ),

                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS
                )
            ]
        ).label('csv')
        yield param(
            config_content='''
            [PhishtankVerifiedCollector]
            link_source=http://www.example.com/data/
            api_key=123456789abcdefghij
            format_options = data-example-valid.csv.bz2
            url=%(link_source)s%(api_key)s%(format_options)s
            period=60
            ''',
            headers={
                'Last-Modified': 'Sun, 12 Feb 2023 12:12:12 GMT',
                'Content-Type': 'application/x-bzip2'
            },
            data_example=b"BZh91AY&SYs\x16\xdc\x16\x00\x00\xe7_\x80\x10\x10\x00\x0f\xff\xd2\x80\x00"
                         b"\x84\x00\xbf\xef\xdf\xe00\x00\xf8\x03\r\x0c\x86\x994\x03\x10\xd3M\x1a"
                         b"\x1a0\xc3C!\xa6M\x00\xc44\xd3F\x86\x8c\x11H\x88\xc1&\xc9\x1bSe\x1a44\xc4"
                         b"\xdaJ\x87\xafB\xc7m\xf8_\xd7tS\x019\xf3h\xf8\xe6G\xc9\x16\x0e#\x88\xcd"
                         b"\xae\xba\xb9\xbd\xdb\x1c\x87'c\r\xc8L\x1cG\x80\xec\x19\xf1\x88\x88\x88"
                         b"\x88\x88\xa5\x0cD=\xb2\x88\x88\xd64\x0ec\x03H\xd49\x9c\xe0\x8a$JJv8C$<"
                         b"\xf3\xceD\x89\x19\xb4\xb6\xb6\r`u7\xf1\r\x18\x0f\xde\xff\xdfc\x1c\xa1"
                         b"\xfd\x0e6E\x8d\x16\x9a\x11\xe0t\xdc\x1c\x9dGL\x94\xc1\xde\x81'x\xe9xF"
                         b"\xa3\xb8k6\xc6\xbf!o\xc1\xd6\\\x173\xf03<Z\xcc\x9c\x99z\x8c\xcd\xb7%"
                         b"\xaf'\x06\x8b\xb4x\x0e\xd6\xae\x06\xc82!p\xd8.\xe8\xb6\x84\xf2e\xe1\xc4"
                         b"\xae\xc1\xa4j\xd5L\x1d\x86\xf6\xb6c\xfe.\xe4\x8ap\xa1 \xe6-\xb8,"
            ,
            expected_publish_output_calls=[
                call(
                    # routing_key
                    'phishtank.verified',
                    # body
                    (
                    b'phish_id,url,phish_detail_url,submission_time,verified,verification_time,'
                    b'online,target\n'
                    b'1111114,http://example-phish4.com,'
                    b'http://www.phishtank.com/phish_detail.php?phish_id=1111114,'
                    b'2023-02-12T06:00:00+00:00,yes,2023-02-12T06:06:06+00:00,yes,Other\n'
                    b'1111115,http://example-phish5.com,'
                    b'http://www.phishtank.com/phish_detail.php?phish_id=1111115,'
                    b'2023-02-12T07:00:00+00:00,yes,2023-02-12T07:07:07+00:00,yes,Other\n'
                    b'1111116,https://example-phish6.com,'
                    b'http://www.phishtank.com/phish_detail.php?phish_id=1111116,'
                    b'2023-02-12T08:00:00+00:00,yes,2023-02-12T08:08:08+00:00,yes,Other'
                     ),
                    # prop_kwargs
                    cls.EXPECTED_PROP_KWARGS
                )
            ]
        ).label('csv.bz2')

    @foreach(cases)
    def test(self,
             config_content,
             headers,
             data_example,
             expected_publish_output_calls,
             *args,
             **kwargs):
        with patch('n6datasources.collectors.phishtank.LOGGER'):
            self.patch('n6datasources.collectors.phishtank.PhishtankVerifiedCollector._get_headers', return_value=None)
            self.patch('n6datasources.collectors.phishtank.PhishtankVerifiedCollector.download', return_value=data_example)
            collector = self.prepare_collector(self.COLLECTOR_CLASS,
                                               config_content=config_content)
            collector._verify_period = Mock(return_value=True)
            collector.response_content_type = headers['Content-Type']
            collector.run_collection()
            self.assertEqual(self.publish_output_mock.mock_calls, expected_publish_output_calls)

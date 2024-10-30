# Copyright (c) 2024 NASK. All rights reserved.

import json
from datetime import datetime
from unittest.mock import (
    ANY,
    call,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.withaname import WithanameDdosiaCollector
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase


@expand
class TestWithanameDdosiaCollector(BaseCollectorTestCase):
    COLLECTOR_CLASS = WithanameDdosiaCollector

    EXPECTED_PROP_KWARGS = {
        "message_id": ANY,
        "type": "file",
        "timestamp": ANY,
        "headers": {},
        "content_type": "text/csv",
    }

    EMPTY_RAW_HTML_DATA = [""]

    ONE_ENTRY_RAW_HTML_DATA = [
        """
        <a href="2024-08-25_07-43-15_DDoSia-target-list-full.json">2024-08-25_07-43-15_DDoSia-target-list-full.json</a>
        26-Aug-2024 09:55    233K
        <a href="2024-08-25_07-43-15_DDoSia-target-list.csv">2024-08-25_07-43-15_DDoSia-target-list.csv</a>
        26-Aug-2024 09:55     15K
        """,
    ]

    RAW_HTML_DATA_NOT_SORTED = [
        """
        <a href="last.json">last.json</a>
        26-Aug-2024 09:55    153K
        <a href="last.csv">last.csv</a>
        26-Aug-2024 09:55     11K
        <a href="2024-08-26_09-55-03_DDoSia-target-list-full.json">2024-08-26_09-55-03_DDoSia-target-list-full.json</a>
        26-Aug-2024 09:55    153K
        <a href="2024-08-26_09-55-03_DDoSia-target-list.csv">2024-08-26_09-55-03_DDoSia-target-list.csv</a>
        26-Aug-2024 09:55     11K
        <a href="2024-08-25_07-43-15_DDoSia-target-list-full.json">2024-08-25_07-43-15_DDoSia-target-list-full.json</a>
        26-Aug-2024 09:55    233K
        <a href="2024-08-25_07-43-15_DDoSia-target-list.csv">2024-08-25_07-43-15_DDoSia-target-list.csv</a>
        26-Aug-2024 09:55     15K
        """,
    ]

    DATA_BODY_EVENT = {
        'csv_file': (
            "host,ip,type,method,port,use_ssl,path\r\n"
            "www.example1.com,1.1.1.1,http2,GET,443,True,/example?example-s=1\r\n"
            "www.example2.com,2.2.2.2,http,GET,443,True,/example/page/2/\r\n"
            "www.example3.com,3.3.3.3,http,GET,443,True,example/\r\n"
            "www.example4.com,4.4.4.4,tcp,PING,443,True,\r\n"
        ),
        'datetime': '2024-08-25T07:43:15',
    }

    DATA_BODY_EVENT_2 = {
        'csv_file': (
            "host,ip,type,method,port,use_ssl,path\r\n"
            "www.example1.com,5.5.5.5,http2,GET,443,True,/example?example-s=1\r\n"
            "www.example2.com,6.6.6.6,http,GET,443,True,/example/page/2/\r\n"
            "www.example3.com,7.7.7.7,http,GET,443,True,example/\r\n"
            "www.example4.com,8.8.8.8,tcp,PING,443,True,\r\n"
        ),
        'datetime': '2024-08-26T09:55:03',
    }

    RAW_CSV_FILE = [
        (
            "host,ip,type,method,port,use_ssl,path\r\n"
            "www.example1.com,1.1.1.1,http2,GET,443,True,/example?example-s=1\r\n"
            "www.example2.com,2.2.2.2,http,GET,443,True,/example/page/2/\r\n"
            "www.example3.com,3.3.3.3,http,GET,443,True,example/\r\n"
            "www.example4.com,4.4.4.4,tcp,PING,443,True,\r\n"
        ),
    ]

    RAW_CSV_FILE_2 = [
        (
            "host,ip,type,method,port,use_ssl,path\r\n"
            "www.example1.com,5.5.5.5,http2,GET,443,True,/example?example-s=1\r\n"
            "www.example2.com,6.6.6.6,http,GET,443,True,/example/page/2/\r\n"
            "www.example3.com,7.7.7.7,http,GET,443,True,example/\r\n"
            "www.example4.com,8.8.8.8,tcp,PING,443,True,\r\n"
        ),
    ]

    NON_CSV_FILE = [""]

    def _mocked_csv_file_fetcher(self, mocked_csv_files: list[str]):
        if type(mocked_csv_files) != list:
            mocked_csv_files = [mocked_csv_files]
        iterator = iter(mocked_csv_files)

        def _mocked_fetch_csv_file(*args, **kwargs):
            return next(iterator, None)

        return _mocked_fetch_csv_file

    def _perform_test(
            self,
            *,
            config_content,
            expected_publish_output_calls,
            mocked_raw_data,
            mocked_csv_file="",
            initial_state="",
            expected_saved_state="",
            expected_error=None,
            label,  # arg (added by @foreach) irrelevant here
            context_targets,  # arg (added by @foreach) irrelevant here
    ):
        collector = self._mocked_collector(config_content,
                                           mocked_raw_data,
                                           mocked_csv_file,
                                           initial_state,
                                           )

        if expected_error:
            with self.assertRaises(expected_error):
                collector.run_collection()
        else:
            collector.run_collection()

        self.assertEqual(self.publish_output_mock.mock_calls,
                         expected_publish_output_calls,
                         )
        self.assertEqual(self.saved_state, expected_saved_state)

    def _mocked_collector(
            self,
            config_content,
            mocked_raw_data,
            mocked_csv_file,
            initial_state,
    ):
        self.patch_object(
            WithanameDdosiaCollector,
            "_fetch_raw_data",
            side_effect=mocked_raw_data,
        )
        self.patch_object(
            WithanameDdosiaCollector,
            "_fetch_csv_file",
            side_effect=self._mocked_csv_file_fetcher(mocked_csv_file),
        )

        return self.prepare_collector(
            self.COLLECTOR_CLASS,
            config_content=config_content,
            initial_state=initial_state,
        )

    @paramseq
    def cases(cls):
        config_content = """
            [WithanameDdosiaCollector]
            url=https://www.example.com
            download_retries=3
        """
        yield param(
            config_content=config_content,
            mocked_raw_data=cls.RAW_HTML_DATA_NOT_SORTED,
            mocked_csv_file=cls.NON_CSV_FILE,
            expected_publish_output_calls=[],
            initial_state=datetime(1970, 1, 1, 00, 00, 00),
            expected_saved_state=datetime(2024, 8, 26, 9, 55, 3),
        )

        yield param(
            config_content=config_content,
            mocked_raw_data=cls.EMPTY_RAW_HTML_DATA,
            expected_publish_output_calls=[],
        )

        yield param(
            config_content=config_content,
            mocked_raw_data=cls.ONE_ENTRY_RAW_HTML_DATA,
            mocked_csv_file=cls.RAW_CSV_FILE,
            expected_publish_output_calls=[
                call(
                    "withaname.ddosia",
                    bytes(json.dumps(cls.DATA_BODY_EVENT), "utf-8"),
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            initial_state=datetime(1970, 1, 1, 00, 00, 00),
            expected_saved_state=datetime(2024, 8, 25, 7, 43, 15),
        )

        yield param(
            config_content=config_content,
            mocked_raw_data=cls.RAW_HTML_DATA_NOT_SORTED,
            mocked_csv_file=cls.RAW_CSV_FILE + cls.RAW_CSV_FILE_2,
            expected_publish_output_calls=[
                call(
                    "withaname.ddosia",
                    bytes(json.dumps(cls.DATA_BODY_EVENT), "utf-8"),
                    cls.EXPECTED_PROP_KWARGS,
                ),
                call(
                    "withaname.ddosia",
                    bytes(json.dumps(cls.DATA_BODY_EVENT_2), "utf-8"),
                    cls.EXPECTED_PROP_KWARGS,
                ),
            ],
            initial_state=datetime(1970, 1, 1, 00, 00, 00),
            expected_saved_state=datetime(2024, 8, 26, 9, 55, 3),
        )

    @foreach(cases)
    def test(self, **kwargs):
        self._perform_test(**kwargs)

# Copyright (c) 2022-2023 NASK. All rights reserved.

"""
Collector: `cesnet-cz.warden`.
"""

import json
import os
from typing import Optional

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    BaseDownloadingCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class CesnetCzWardenCollector(BaseDownloadingCollector, BaseSimpleCollector):

    raw_type = 'file'
    content_type = 'application/json'
    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
        download_retries = 1 :: int
        cert_file_path :: path
        key_file_path :: path
    ''')

    def get_source(self, **processed_data) -> str:
        return 'cesnet-cz.warden'

    def obtain_data_body(self) -> Optional[bytes]:
        LOGGER.info('Events download started...')
        events = self._get_events()
        num_of_events = len(events)
        LOGGER.info('%s events downloaded in total.', num_of_events)
        return json.dumps(events).encode('utf-8')

    def _get_events(self):
        events = []
        while True:
            partial_events = self._download_data()['events']
            num_of_events = len(partial_events)
            LOGGER.info('Downloaded %s events...', num_of_events)
            events.extend(partial_events)
            if 0 <= num_of_events <= 999:
                break
            if num_of_events > 1000:
                raise ValueError('unexpected number of events: {} (> 1000)'.format(num_of_events))
        return events

    def _download_data(self):
        data_str = self.download(
            self.config['url'],
            cert=(
                os.fspath(self.config['cert_file_path']),
                os.fspath(self.config['key_file_path'])))
        return json.loads(data_str)


add_collector_entry_point_functions(__name__)

# Copyright (c) 2020-2023 NASK. All rights reserved.

"""
Collector: `sblam.spam`.
"""

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    BaseDownloadingCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class SblamSpamCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'blacklist'
    content_type = 'text/plain'

    def obtain_data_body(self) -> bytes:
        return self.download(self.config['url'])

    def get_source(self, **processed_data):
        return 'sblam.spam'


add_collector_entry_point_functions(__name__)

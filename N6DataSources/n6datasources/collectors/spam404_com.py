# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Collector: `spam404-com.scam-list-bl`.
"""

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec


class Spam404ComScamListBlCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'blacklist'
    content_type = 'text/csv'

    def get_source(self, **kwargs):
        return 'spam404-com.scam-list-bl'

    def obtain_data_body(self) -> bytes:
        return self.download(self.config['url'])


add_collector_entry_point_functions(__name__)

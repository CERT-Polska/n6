# Copyright (c) 2016-2024 NASK. All rights reserved.

"""
Collector: turris-cz.greylist-csv
"""

from typing import Optional

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec


class TurrisCzGreylistCsvCollector(BaseDownloadingCollector, BaseSimpleCollector):

    raw_format_version_tag = '202401'
    raw_type = 'blacklist'
    content_type = 'text/csv'
    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    def get_source(self, **processed_data) -> str:
        return 'turris-cz.greylist-csv'
    

    def obtain_data_body(self) -> Optional[bytes]:
        return self.download(self.config['url'])


add_collector_entry_point_functions(__name__)

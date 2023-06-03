# Copyright (c) 2015-2023 NASK. All rights reserved.

"""
Collector: `openphish.web`.
"""

from n6datasources.collectors.base import(
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class OpenphishWebBlCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'blacklist'
    content_type = 'text/plain'

    def get_source(self, **kwargs) -> str:
        return "openphish.web-bl"

    def obtain_data_body(self) -> bytes:
        return self.download(self.config["url"])


add_collector_entry_point_functions(__name__)

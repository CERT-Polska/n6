# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Collector: `stopforum.spam`.
"""

import zipfile
from io import BytesIO

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class StopForumSpamCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'file'
    content_type = 'text/plain'

    def get_source(self, **kwargs):
        return 'stopforum.spam'

    def obtain_data_body(self) -> bytes:
        data = self.download(self.config["url"])
        with zipfile.ZipFile(BytesIO(data)) as zipped:
            return zipped.read(zipped.namelist()[0])


add_collector_entry_point_functions(__name__)

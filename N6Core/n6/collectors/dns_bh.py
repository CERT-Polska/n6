# Copyright (c) 2013-2018 NASK. All rights reserved.

"""
Collector: dns-bh.malwaredomainscom
"""

import sys

from n6.collectors.generic import (
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    entry_point_factory,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class DnsBhMalwaredomainscomCollector(BaseUrlDownloaderCollector, BaseOneShotCollector):

    raw_format_version_tag = '201412'

    type = 'blacklist'
    config_group = "malwaredomainscom"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "malwaredomainscom"

    def process_data(self, data):
        return data


entry_point_factory(sys.modules[__name__])

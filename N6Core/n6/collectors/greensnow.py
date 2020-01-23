# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Collector: greensnow-co.list-txt
"""

import sys

from n6.collectors.generic import (
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    entry_point_factory,
)

from n6lib.log_helpers import get_logger

LOGGER = get_logger(__name__)


class GreenSnowCollector(BaseUrlDownloaderCollector, BaseOneShotCollector):

    type = 'blacklist'
    config_group = 'greensnow_co'
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return 'list-txt'

    def process_data(self, data):
        return data


entry_point_factory(sys.modules[__name__])

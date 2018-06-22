# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

"""
Collector: spam404-com.scam-list
"""

import sys

from n6.collectors.generic import (
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    entry_point_factory,
)


class Spam404Collector(BaseUrlDownloaderCollector, BaseOneShotCollector):

    type = 'file'
    config_group = 'spam404_com'
    content_type = 'text/csv'

    def get_source_channel(self, **kwargs):
        return "scam-list"

    def process_data(self, data):
        return data


entry_point_factory(sys.modules[__name__])

# Copyright (c) 2013-2018 NASK. All rights reserved.

"""
Collector: zoneh.rss
"""

import sys

from n6.collectors.generic import (
    BaseRSSCollector,
    entry_point_factory,
)


class ZoneHRSSCollector(BaseRSSCollector):

    config_group = "zoneh_rss"

    def rss_item_to_relevant_data(self, item):
        title, description, pubdate = None, None, None

        for i in item:
            if i.tag == 'title':
                title = i.text
            elif i.tag == 'description':
                description = i.text
            elif i.tag == 'pubDate':
                pubdate = i.text

        return title, description, pubdate

    def get_source_channel(self, **kwargs):
        return "rss"


entry_point_factory(sys.modules[__name__])

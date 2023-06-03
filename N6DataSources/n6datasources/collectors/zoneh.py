# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Collector: `zoneh.rss`.
"""

import json
from typing import Optional

from lxml import (
    etree,
    html,
)

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    BaseDownloadingCollector,
    StatefulCollectorMixin,
    add_collector_entry_point_functions,
)
from n6lib.common_helpers import OPSet
from n6lib.config import combined_config_spec


class ZonehRssCollector(StatefulCollectorMixin,
                        BaseDownloadingCollector,
                        BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'stream'

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)
        self._state: Optional[OPSet[tuple]] = None   # to be set in `obtain_data_body()`

    def obtain_data_body(self) -> Optional[bytes]:
        old_state = self.load_state()
        current_rss = self._process_rss(self.download(self.config['url']))
        self._state = current_rss
        if old_state is not None:
            diff = current_rss - old_state
        else:
            diff = current_rss
        if diff:
            return json.dumps(list(diff)).encode('ascii')
        return None

    def get_source(self, **kwargs):
        return "zoneh.rss"

    def _process_rss(self, rss_data: bytes) -> OPSet[tuple]:
        try:
            document = etree.fromstring(rss_data)
        except etree.XMLSyntaxError:
            document = html.fromstring(rss_data)
        data_xpath = "//item"
        items = document.xpath(data_xpath)
        return OPSet(map(self.extract_relevant_data_from_rss_item, items))

    def extract_relevant_data_from_rss_item(self, item) -> tuple:
        title, description, pubdate = None, None, None
        for i in item:
            if i.tag == 'title':
                title = i.text
            elif i.tag == 'description':
                description = i.text
            elif i.tag == 'pubDate':
                pubdate = i.text
        return title, description, pubdate

    def after_completed_publishing(self) -> None:
        super().after_completed_publishing()
        self.save_state(self._state)


add_collector_entry_point_functions(__name__)

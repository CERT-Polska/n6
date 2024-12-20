# Copyright (c) 2014-2023 NASK. All rights reserved.

"""
Collectors: `spamhaus.bots`, `spamhaus.drop`, `spamhaus.edrop`.
"""

from requests import PreparedRequest

from n6datasources.collectors.base import (
    BaseSimpleCollector,
    BaseDownloadingCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class SpamhausBotsCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
        cert :: str
        api_key :: str
    ''')

    raw_type = 'file'
    content_type = 'text/csv'

    def _create_url(self):
        base = self.config['url']
        params = {
            'cert': self.config['cert'],
            'key': self.config['api_key']
        }
        req = PreparedRequest()
        req.prepare_url(base, params)  # XXX: why this way???
        return req.url

    def get_source(self, **kwargs):
        return 'spamhaus.bots'

    def obtain_data_body(self) -> bytes:
        url = self._create_url()
        return self.download(url)


class SpamhausDropCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'blacklist'
    content_type = 'text/csv'

    def get_source(self, **kwargs) -> str:
        return "spamhaus.drop"

    def obtain_data_body(self) -> bytes:
        return self.download(self.config['url'])


class SpamhausEdropCollector(BaseDownloadingCollector, BaseSimpleCollector):

    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
    ''')

    raw_type = 'blacklist'
    content_type = 'text/csv'

    def get_source(self, **kwargs):
        return "spamhaus.edrop"

    def obtain_data_body(self) -> bytes:
        return self.download(self.config['url'])


add_collector_entry_point_functions(__name__)

# Copyright (c) 2015-2023 NASK. All rights reserved.

"""
Collector: `blueliv.map`.
"""

import json
from urllib.parse import urljoin

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class BluelivMapCollector(BaseDownloadingCollector, BaseSimpleCollector):

    raw_type = 'blacklist'
    content_type = 'application/json'

    config_spec_pattern = combined_config_spec('''
        [BluelivMapCollector]
        base_url :: str
        endpoint_name :: str
        token :: str
    ''')


    def get_source(self, **processed_data):
        return 'blueliv.map'

    def obtain_data_body(self, **kwargs):
        base_url = self.config['base_url']
        endpoint_name = self.config['endpoint_name']
        token = self.config['token']

        # TODO: verify these headers; some of them might be obsolete
        # (see: #8706)
        headers = {
            'Content-Type': 'application/json',
            "Authorization": f"bearer {token}",
            "User-Agent": 'SDK v2',
            "X-API-CLIENT": f"{token}",
            'Accept-Encoding': 'gzip, deflate',
        }
        url = urljoin(base_url, endpoint_name)
        endpoint_key = endpoint_name.split('/')[-1]
        raw_response = json.loads(self.download(method='GET',
                                                url=url,
                                                custom_request_headers=headers))
        response = raw_response.get(endpoint_key)
        if response:
            return json.dumps(response).encode('utf-8')
        return None


add_collector_entry_point_functions(__name__)

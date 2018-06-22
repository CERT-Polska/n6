# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

"""
Collector: badips-com.server-exploit-list
"""

import json
import sys

from n6.collectors.generic import (
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    entry_point_factory,
    n6CollectorException,
)


class BadipsServerExploitCollector(BaseUrlDownloaderCollector, BaseOneShotCollector):

    type = 'blacklist'
    content_type = 'text/csv'
    config_group = "badips_server_exploit_list"

    @staticmethod
    def _add_fields_name(ips, category_root, category_leaf):
        formatted_ips_and_name_list = ('{};{} {} attack'.format(ip, category_leaf, category_root)
                                       for ip in ips.rstrip('\n').split('\n'))
        return '\n'.join(formatted_ips_and_name_list)


    def get_source_channel(self, **kwargs):
        return "server-exploit-list"

    def get_output_data_body(self, **kwargs):
        ips_string = None
        categories_json = self._download_retry(self.config['url'])
        if categories_json is None:
            raise n6CollectorException("Categories download failure")
        categories_list = json.loads(categories_json).get('categories', [])
        for category in categories_list:
            if 'Parent' in category:
                category_name = category.get('Name')
                category_ips = self._download_retry(self.config['category_details_url'].format(
                    category=category_name))
                if not category_ips:
                    continue
                formatted_category_ips = self._add_fields_name(category_ips,
                                                               category.get('Parent'),
                                                               category_name)
                if ips_string is not None:
                    ips_string = '\n'.join([ips_string, formatted_category_ips])
                else:
                    ips_string = formatted_category_ips
        return ips_string


entry_point_factory(sys.modules[__name__])

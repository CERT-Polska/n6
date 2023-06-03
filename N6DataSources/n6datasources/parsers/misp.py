# Copyright (c) 2016-2023 NASK. All rights reserved.

"""
Generic MISP parser.
"""

import copy
import datetime
import json
import re

from n6lib.log_helpers import get_logger
from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions,
)


LOGGER = get_logger(__name__)


TLP_RESTRICTION = {
    'red': 'internal',
    'amber': 'internal',
    'green': 'need-to-know',
    'white': 'public'
}

RESTRICTION_LEVEL = {
    'internal': 3,
    'need-to-know': 2,
    'public': 1,
}

TO_IDS_DEPENDENT_CATEGORY_MARKER = 'cnc-OR-other'

MISP_MAP_KEYS = {
    'Network activity': {
        'hostname': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'fqdn': 'value', 'dport': 'comment'},
        'domain': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'fqdn': 'value', 'dport': 'comment'},
        'ip-dst': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'ip': 'value', 'dport': 'comment'},
        'ip-src': {'category': 'bots', 'ip': 'value'},
        'email-dst': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'email': 'value'},
        'email-src': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'email': 'value'},
        'url': {'category': TO_IDS_DEPENDENT_CATEGORY_MARKER, 'url': 'value'},
        'domain|ip': {'category': 'malurl', 'fqdn': 'value', 'ip': 'value'},
    },
    'Payload delivery': {
        'url': {'category': 'malurl', 'url': 'value'},
        'domain': {'category': 'malurl', 'fqdn': 'value'},
        'ip-dst': {'category': 'malurl', 'ip': 'value'},
        'ip-src': {'category': 'malurl', 'ip': 'value'},
        'hostname': {'category': 'malurl', 'fqdn': 'value'},
    },
}


class MispParser(BaseParser):

    default_binding_key = "*.misp"
    constant_items = {'confidence': 'medium'}

    def parse(self, data):
        min_restriction = self._get_min_restriction(data)
        for raw_data_item in json.loads(data['raw']):
            misp_event = raw_data_item['Event']
            misp_restriction = self.get_restriction(misp_event, min_restriction)
            misp_name = misp_event['info']
            misp_event_uuid = misp_event.get('uuid')
            for event in misp_event['Attribute']:
                misp_category = event['category']
                misp_parama_dict = MISP_MAP_KEYS.get(misp_category)
                misp_event_type = event['type']
                if not misp_parama_dict:
                    continue
                if not misp_parama_dict.get(misp_event_type):
                    continue
                n6event_dict = self.get_event(event, misp_category, misp_event_type)
                if not n6event_dict:
                    continue
                with self.new_record_dict(data) as parsed:
                    parsed.update(n6event_dict)
                    parsed['restriction'] = misp_restriction
                    parsed['name'] = misp_name
                    parsed['misp_event_uuid'] = misp_event_uuid
                    parsed['misp_attr_uuid'] = event.get('uuid')
                    yield parsed

    @staticmethod
    def _get_min_restriction(data):
        meta_headers = data.get('meta')
        if meta_headers and 'minimum_tlp' in meta_headers:
            minimum_tlp = meta_headers['minimum_tlp']
            try:
                return TLP_RESTRICTION[minimum_tlp]
            except KeyError:
                LOGGER.warning("Invalid minimal TLP value: %a.", minimum_tlp)
        return None

    def get_event(self, misp_attribute, misp_category, misp_event_type):
        n6event_dict = {}
        misp_map_dict = copy.deepcopy(MISP_MAP_KEYS[misp_category])
        event_params = misp_map_dict[misp_event_type]
        n6_category = event_params.pop('category')

        # avoiding false positives for misp_category == 'Network activity' & n6_category == 'cnc'
        if n6_category == TO_IDS_DEPENDENT_CATEGORY_MARKER:
            to_ids = misp_attribute.get('to_ids')
            if to_ids and str(to_ids).lower() != 'false':
                n6_category = 'cnc'
            else:
                n6_category = 'other'

        for n6_key, misp_key in event_params.items():
            event_param = misp_attribute.get(misp_key)
            if event_param:
                # parse the parameter's value first if the event
                # is of 'domain|ip' type
                if misp_event_type == 'domain|ip':
                    if n6_key == 'fqdn':
                        event_param = event_param.split('|')[0]
                    elif n6_key == 'ip':
                        try:
                            event_param = event_param.split('|')[1]
                        except IndexError:
                            LOGGER.warning('The "value" attribute of the event of type '
                                           '"domain|ip" does not contain both FQDN and IP '
                                           'address, separated by the "|" sign. Assuming that '
                                           'the attribute contains an FQDN only.')
                            continue
                if n6_key == 'ip':
                    n6event_dict['address'] = [{n6_key: event_param}]
                elif n6_key == 'dport':
                    self.get_dport(event_param, n6event_dict)
                else:
                    n6event_dict[n6_key] = event_param
        if not n6event_dict:
            return None
        n6event_dict['category'] = n6_category
        n6event_dict['time'] = self.get_time(misp_attribute['timestamp'])
        return n6event_dict

    @staticmethod
    def get_dport(comment, n6event_dict):
        dport_pattern = r'(^port|.*? port) .*?(\d+).*'
        _dport = re.search(dport_pattern, comment, re.IGNORECASE | re.ASCII)
        if _dport:
            n6event_dict['dport'] = _dport.groups()[1]

    @staticmethod
    def get_time(misp_ts):
        return datetime.datetime.utcfromtimestamp(int(misp_ts))

    def get_restriction(self, misp_event, min_restriction):
        initial_restriction = self._get_initial_restriction(misp_event)
        if min_restriction and self._is_min_restriction_greater(min_restriction,
                                                                initial_restriction):
            return min_restriction
        return initial_restriction

    @staticmethod
    def _get_initial_restriction(misp_event):
        misp_event_tag = misp_event.get('Tag')
        if misp_event_tag:
            for tag in misp_event_tag:
                _name = tag['name']
                if 'tlp' in _name:
                    tlp = _name.split(':')[1]
                    return TLP_RESTRICTION[tlp]
        return 'need-to-know'

    @staticmethod
    def _is_min_restriction_greater(min_restriction, initial_restriction):
        return RESTRICTION_LEVEL[min_restriction] > RESTRICTION_LEVEL[initial_restriction]


add_parser_entry_point_functions(__name__)

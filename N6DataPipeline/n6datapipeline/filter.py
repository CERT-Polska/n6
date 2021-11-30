# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
The Filter component, responsible for assigning events to the right
client organizations -- by adding the `client` item (and also
`urls_matched` if needed) to each processed record dict.
"""

from n6datapipeline.base import LegacyQueuedBase
from n6lib.auth_api import AuthAPI
from n6lib.common_helpers import replace_segment
from n6lib.config import ConfigMixin
from n6lib.log_helpers import get_logger, logging_configured
from n6lib.record_dict import RecordDict


LOGGER = get_logger(__name__)


class Filter(ConfigMixin, LegacyQueuedBase):

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'filter',
        'accepted_event_types': [
            'event',
            'bl-new',
            'bl-update',
            'bl-change',
            'bl-delist',
            'bl-expire',
            'suppressed',
        ],
    }

    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    config_spec = '''
        [filter]
        categories_filtered_through_fqdn_only = :: list_of_str
    '''

    single_instance = False

    def __init__(self, **kwargs):
        LOGGER.info("Filter Start")
        self.auth_api = AuthAPI()
        self.config = self.get_config_section()
        self.fqdn_only_categories = frozenset(self.config['categories_filtered_through_fqdn_only'])
        super(Filter, self).__init__(**kwargs)

    def input_callback(self, routing_key, body, properties):
        record_dict = RecordDict.from_json(body)
        with self.setting_error_event_info(record_dict):
            client, urls_matched = self.get_client_and_urls_matched(
                record_dict,
                self.fqdn_only_categories)
            record_dict['client'] = client
            if urls_matched:
                record_dict['urls_matched'] = urls_matched
            self.publish_event(record_dict, routing_key)

    def get_client_and_urls_matched(self, record_dict, fqdn_only_categories):
        resolver = self.auth_api.get_inside_criteria_resolver()
        client_org_ids, urls_matched = resolver.get_client_org_ids_and_urls_matched(
            record_dict,
            fqdn_only_categories)
        return sorted(client_org_ids), urls_matched

    def publish_event(self, data, rk):
        """
        Push the given event into the output queue.

        Args:
            `data` (RecordDict instance):
                The event data.
            `rk` (string):
                The *input* routing key.
        """
        output_rk = replace_segment(rk, 1, 'filtered')
        body = data.get_ready_json()
        self.publish_output(routing_key=output_rk, body=body)


def main():
    with logging_configured():
        d = Filter()
        try:
            d.run()
        except KeyboardInterrupt:
            d.stop()


if __name__ == "__main__":
    main()

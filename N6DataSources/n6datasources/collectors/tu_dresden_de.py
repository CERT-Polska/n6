# Copyright (c) 2025 NASK. All rights reserved.

"""
Collector: `tu-dresden-de.resolvers`.
"""

import json
from typing import Optional
from dateutil.parser import parse
from n6datasources.collectors.base import (
    StatefulCollectorMixin,
    BaseDownloadingCollector,
    BaseSimpleCollector,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec


class TuDresdenDeResolversCollector(StatefulCollectorMixin, BaseSimpleCollector, BaseDownloadingCollector):

    API_KEY_HEADER_NAME = "X-API-KEY"
    _NEWEST_EVENT_TIME_STATE_KEY = 'newest_event_stored_time'
    SORT_ORDER = 'desc'

    raw_type = 'file'
    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        url :: str
        api_key :: str
        entries_per_page :: int
        queried_protocol :: str
        quired_ip_country :: str
        sort_field :: str
    ''')

    content_type = 'application/json'

    def __init__(self, /, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state: Optional[dict] = None # to be set in `get_only_new_events`

    def get_source(self, **kwargs):
        return 'tu-dresden-de.resolvers'

    def obtain_data_body(self, **_kwargs) -> Optional[list[dict]]:
        dns_entries = self.obtain_orig_data()
        new_dns_entries = self.get_only_new_events(dns_entries)
        new_events = json.dumps(new_dns_entries, ensure_ascii=True).encode('utf-8')
        if new_events:
            return new_events
        return None

    def obtain_orig_data(self) -> bytes:
        page = 1
        dns_entries = []
        while True:
            orig_data_per_page = self._download_page(page=page)
            json_data = json.loads(orig_data_per_page)
            dns_entries.extend(json_data["dnsEntries"])
            events_count = self._extract_events_count(json_data)
            if events_count <= len(dns_entries):
                return dns_entries
            else:
                page += 1

    def get_only_new_events(self, dns_entries):
        self._state = self.load_state()
        newest_event_index = 0 if self.SORT_ORDER == 'desc' else -1
        oldest_event_index = -1 if self.SORT_ORDER == 'desc' else 0
        newest_event_time_in_run = self.extract_event_time(dns_entries[newest_event_index])
        if self._state:
            prev_newest_event_time = self._state[self._NEWEST_EVENT_TIME_STATE_KEY]
            if prev_newest_event_time >= newest_event_time_in_run:
                return None
            else:
                if prev_newest_event_time > self.extract_event_time(dns_entries[oldest_event_index]):
                    self._update_state(newest_event_time_in_run)
                    return [event for event in dns_entries if prev_newest_event_time<self.extract_event_time(event)]

                self._update_state(newest_event_time_in_run)
                return dns_entries
        return dns_entries

    def _download_page(self, page) -> bytes:
        custom_request_headers = self._make_custom_header()
        custom_payload = self._make_custom_payload(page=page)
        url = self.config['url']
        return self.download(method='POST',
                             url=url,
                             custom_request_headers=custom_request_headers,
                             json=custom_payload
                             )

    def _make_custom_header(self) -> dict[str, any]:
        return {
            "Content-Type": "application/json",
            "accept": "text/plain",
            self.API_KEY_HEADER_NAME: self.config["api_key"],
        }

    def _make_custom_payload(self, page=1) -> dict[str, dict[str, any]]:
        return {
            'pagination': {
                'page': page,
                'per_page': self.config['entries_per_page']
            },
            'filter': {
                'protocol': self.config['queried_protocol'],
                'queried_ip_country': self.config['quired_ip_country'],
            },
            'sort': {
                'field': self.config['sort_field'],
                'order': self.SORT_ORDER
                }
        }

    def _extract_events_count(self, json_data) -> any:
        return json_data["metaData"]["total"]

    def _update_state(self, newest_event_time):
        self._state.update({
            self._NEWEST_EVENT_TIME_STATE_KEY: newest_event_time,
        })

    def extract_event_time(self, event: dict) -> str:
        raw_event_time = self.pick_entry_time(event)
        if raw_event_time is None:
            return None
        return self.clean_entry_time(raw_event_time)

    def pick_entry_time(self, event: dict) -> str:
        raw_event_time = event["timestamp_request"]
        return raw_event_time

    def clean_entry_time(self, raw_event_time: str) -> str:
        parsed_raw_event_time = parse(raw_event_time)
        return str(parsed_raw_event_time.strftime('%Y-%m-%dT%H:%M:%S'))

    def after_completed_publishing(self):
        super().after_completed_publishing()
        self.save_state(self._state)


add_collector_entry_point_functions(__name__)

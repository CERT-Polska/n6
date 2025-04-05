# Copyright (c) 2013-2025 NASK. All rights reserved.

import bz2
import datetime

from n6datasources.collectors.base import (
    add_collector_entry_point_functions,
    BaseDownloadingCollector,
    BaseSimpleCollector,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class PhishtankVerifiedCollector(BaseDownloadingCollector, BaseSimpleCollector):

    csv_content_type = 'text/csv'
    bz2_content_type = 'application/x-bzip2'
    raw_type = "blacklist"
    content_type = "text/csv"
    config_spec_pattern = combined_config_spec('''
        [{collector_class_name}]
        link_source :: str
        api_key :: str
        format_options :: str
        url :: str
        period :: int
    ''')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url = self.config['url']
        self.period = self.config['period']  # a number of minutes
        self.response_content_type = None

    def get_source(self, **kwargs):
        return 'phishtank.verified'

    def get_content(self, response):
        if not response:
            return None
        if self.response_content_type == self.csv_content_type:
            return response
        if self.response_content_type == self.bz2_content_type:
            return self._bz2_uncompress(response)
        # if file format is unknown, try to decompress it first
        try:
            return self._bz2_uncompress(response)
        except IOError:
            # if file is not a compressed bzip2, return its raw content
            return response

    def obtain_data_body(self, **kwargs):
        response = self.download(self.url, allow_redirects=True)
        output = self.get_content(response)
        return output

    def start_publishing(self):
        self._get_headers()
        if self._verify_period(minutes=self.period):
            super().start_publishing()
        else:
            self.inner_stop()

    def _get_headers(self):
        """
        Get and check only the header, so that they will not
        download the same file.
        """
        self.download(url=self.url, method='HEAD', allow_redirects=True)
        self.response_content_type = self.http_response.headers.get('Content-Type')

    def _verify_period(self, minutes=60):
        """
        Verify, whether a file was modified within a given time period.

        Kwargs:
            `minutes` (default: 60):
                A timespan back from now, which time of file's
                last modification should not exceed.

        Returns:
            True if a file was modified within given time
            or if "Last-Modified" datetime was not fetched,
            False otherwise.
        """
        if not self.http_last_modified:
            return True
        now_utc = datetime.datetime.utcnow()
        if now_utc - self.http_last_modified <= datetime.timedelta(minutes=minutes):
            return True
        LOGGER.warning("Last modified earlier than %s minutes ago.", minutes)
        return False

    @staticmethod
    def _bz2_uncompress(data):
        """Decompress data."""
        return bz2.decompress(data)


add_collector_entry_point_functions(__name__)

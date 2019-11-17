# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Collectors: abuse-ch.spyeye-doms, abuse-ch.spyeye-ips,
abuse-ch.zeus-doms, abuse-ch.zeus-ips, abuse-ch.zeustracker,
abuse-ch.palevo-doms, abuse-ch.palevo-ips, abuse-ch.feodotracker,
abuse-ch.ransomware, abuse-ch.ssl-blacklist, abuse-ch.ssl-blacklist-dyre,
abuse-ch.urlhaus-urls
"""

import json
import operator
import os
import re
import shutil
import sys
import tempfile
import zipfile

from bs4 import BeautifulSoup
from lxml import html
from lxml.etree import (
    ParserError,
    XMLSyntaxError,
)

from n6.collectors.generic import (
    BaseCollector,
    BaseDownloadingTimeOrderedRowsCollector,
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    BaseRSSCollector,
    CollectorWithStateMixin,
    entry_point_factory,
)
from n6lib.common_helpers import (
    make_exc_ascii_str,
    read_file,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import get_logger



LOGGER = get_logger(__name__)



class NoNewDataException(Exception):

    """
    Exception raised when the source does not provide any new data.
    """



class _BaseAbuseChRealBlacklist201406Mixin(object):

    raw_format_version_tag = '201406'
    type = 'blacklist'

    def process_data(self, data):
        return data


class AbuseChSpyeyeDomsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                                 BaseUrlDownloaderCollector,
                                 BaseOneShotCollector):

    config_group = "abusech_spyeye_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "spyeye-doms"


class AbuseChSpyeyeIpsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                                BaseUrlDownloaderCollector,
                                BaseOneShotCollector):

    config_group = "abusech_spyeye_ips"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "spyeye-ips"


class AbuseChZeusDomsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                               BaseUrlDownloaderCollector,
                               BaseOneShotCollector):

    config_group = "abusech_zeus_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "zeus-doms"


class AbuseChZeusIpsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                              BaseUrlDownloaderCollector,
                              BaseOneShotCollector):

    config_group = "abusech_zeus_ips"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "zeus-ips"


class AbuseChPalevoDomsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                                 BaseUrlDownloaderCollector,
                                 BaseOneShotCollector):

    config_group = "abusech_palevo_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "palevo-doms"


class AbuseChPalevoIpsCollector(_BaseAbuseChRealBlacklist201406Mixin,
                                BaseUrlDownloaderCollector,
                                BaseOneShotCollector):

    config_group = "abusech_palevo_ips"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "palevo-ips"



class AbuseChZeusTrackerCollector(BaseRSSCollector):

    config_group = "abusech_zeustracker"

    def get_source_channel(self, **kwargs):
        return 'zeustracker'

    def rss_item_to_relevant_data(self, item):
        title, description = None, None
        for i in item:
            if i.tag == 'title':
                title = i.text
            elif i.tag == 'description':
                description = i.text
        return (title, description)



class AbuseChSSLBlacklistDyreCollector(CollectorWithStateMixin, BaseRSSCollector):
    # Note that, contrary to its name, it is an *event-based* source

    config_spec = '''
        [abusech_ssl_blacklist_dyre]
        source :: str
        url :: str
        cache_dir :: str
        download_timeout :: int
        retry_timeout :: int
        details_download_timeout = 12 :: int
        details_retry_timeout = 4 :: int
    '''

    # XPath to main table's records.
    details_xpath = "//table[@class='tlstable']//th[text()='{field}']/following-sibling::td"

    # In order to get 'td' elements from the 'tbody' of a table only,
    # select 'tr' tags NOT containing 'th' elements. LXML's parser does
    # not get the exact tree, so XPath cannot search through 'tbody'.
    binaries_xpath = "//table[@class='sortable']//tr[not(child::th)]"

    # The dict maps output JSON's field names to table labels.
    tls_table_labels = {
        'subject': 'Subject:',
        'issuer': 'Issuer:',
        'fingerprint': 'Fingerprint (SHA1):',
        'status': 'Status:',
    }

    # regex for the 'Reason' part of a 'Status' row
    reason_regex = re.compile(r'''
        (?:Reason:[ ]*)
        (?P<reason>.*)      # match a text between 'Reason:'
        (?=,[ ]*Listing)    # and ', Listing'
        ''', re.VERBOSE)

    # regex for the 'Listing date' part of a 'Status' row
    datetime_regex = re.compile(r'''
        (?:Listing[ ]date:[ ]*)
        (?P<dt>\d{4}-\d{2}-\d{2}[ ]     # match a date
        (?:\d{2}:){2}\d{2})             # match time
        ''', re.VERBOSE)


    def __init__(self, *args, **kwargs):
        super(AbuseChSSLBlacklistDyreCollector, self).__init__(*args, **kwargs)
        self._rss_feed_url = self.config['url']
        # separate timeouts for downloading detail pages
        self._details_download_timeout = self.config['details_download_timeout']
        self._details_retry_timeout = self.config['details_retry_timeout']
        # attribute to store data created from
        # detail pages, before deduplication
        self._complete_data = None

    def run_handling(self):
        try:
            self._output_components = self.get_output_components(**self.input_data)
        except NoNewDataException:
            LOGGER.info('No new data from the Abuse.CH SSL Blacklist Dyre source.')
        else:
            self.run()
        self.save_state(self._complete_data)
        LOGGER.info('Stopped')

    def get_source_channel(self, **kwargs):
        return "ssl-blacklist-dyre"

    def get_output_data_body(self, **kwargs):
        """
        Overridden method returns newly created data structure.

        Returns:
            JSON object describing new and updated elements from
            the RSS feed.

        Raises:
            NoNewDataException: if the source provides no new data.

        Output data structure is a dict of which keys are URLs to
        elements' detail pages and values are dicts containing items
        extracted from those pages.
        """
        old_data = self.load_state()
        downloaded_rss = self._download_retry(self._rss_feed_url)
        new_links = self._process_rss(downloaded_rss)
        new_data = self._get_rss_items_details(new_links)
        # *Copy* downloaded data before deduplication, to be saved later.
        self._complete_data = dict(new_data)
        if old_data:
            # Get keys of a newly created dict and of a dict created
            # during previous run. Keys are URLs to elements' detail
            # pages.
            downloaded_links = set(new_data.iterkeys())
            old_links = set(old_data.iterkeys())
            common_links = old_links & downloaded_links
            # If there are any URLs common to new and previous RSS,
            # there is a risk of duplication of data.
            if common_links:
                self._deduplicate_data(old_data, new_data, common_links)
        if not new_data:
            raise NoNewDataException
        return json.dumps(new_data)

    def rss_item_to_relevant_data(self, item):
        """
        Overridden method: create a URL to a detail page from an RSS
        element.

        Args:
            `item`: a single item from the RSS feed.

        Returns:
            URL to item's detail page.
        """
        url = None
        for i in item:
            if i.tag == 'link':
                url = i.text
                break
        if url is None:
            LOGGER.warning("RSS item without a link to its detail page occurred.")
        return url

    def _get_rss_items_details(self, urls):
        """
        Create a dict mapping elements' detail pages URLs to dicts
        describing these elements.

        Args:
            `urls` (list): URLs to RSS feed's elements' detail pages.

        Returns:
            A dict created from fetched data.
        """
        items = {}
        for url in urls:
            if url is None:
                continue
            details_page = self._download_retry_external(
                url, self._details_download_timeout, self._details_retry_timeout)
            if not details_page:
                LOGGER.warning("Could not download details page with URL: %s", url)
                continue
            try:
                parsed_page = html.fromstring(details_page)
            except (ParserError, XMLSyntaxError):
                LOGGER.warning("Could not parse event's details page with URL: %s", url)
                continue
            items[url] = self._get_main_details(parsed_page)
            binaries_table_body = parsed_page.xpath(self.binaries_xpath)
            if binaries_table_body:
                items[url]['binaries'] = [tuple(x) for x in
                                          self._get_binaries_details(binaries_table_body)]
        return items

    def _get_main_details(self, parsed_page):
        """
        Extract data from the main table of a detail page.

        Args:
            `parsed_page` (:class:`lxml.html.HtmlElement`):
                detail page after HTML parsing.

        Returns:
            A dict containing items extracted from the parsed page.
        """
        items = {}
        for header, text_value in self.tls_table_labels.iteritems():
            table_records = parsed_page.xpath(self.details_xpath.format(field=text_value))
            if table_records and header == 'status':
                status = table_records[0].text_content()
                matched_datetime = self.datetime_regex.search(status)
                matched_reason = self.reason_regex.search(status)
                if matched_datetime:
                    items['timestamp'] = matched_datetime.group('dt')
                if matched_reason:
                    items['name'] = matched_reason.group('reason')
            elif table_records:
                items[header] = table_records[0].text_content().strip()
        return items

    def _get_binaries_details(self, table_body):
        """
        Extract data from the table with associated binaries.

        Args:
            `table_body` (list): 'tr' elements of the table.

        Yields:
            Text content of the table's records for every binary.
        """
        for tr in table_body:
            yield (td.text_content().strip() for td in tr)

    def _deduplicate_data(self, old_data_body, new_data_body, common_links):
        """
        Delete already published data from the output data body.

        Args:
            `old_data_body` (dict):
                data body from the previous run of the collector.
            `new_data_body` (dict):
                data body created during this run of the collector.
            `common_links` (set):
                URLs occurring in old and new data body.

        Returns:
            New data body after deduplication process.

        The method checks elements common to previously and currently
        fetched RSS feed. If there are any new associated binaries
        inside of an element - it means new events can be created.

        Then it removes already published binaries records, or a whole
        element - if no new binaries have been added on website.
        """
        for url in common_links:
            if 'binaries' not in new_data_body[url]:
                new_data_body.pop(url)
            elif 'binaries' in old_data_body[url]:
                new_binaries = set(new_data_body[url]['binaries'])
                old_binaries = set(old_data_body[url]['binaries'])
                diff = new_binaries - old_binaries
                if diff:
                    new_data_body[url]['binaries'] = list(diff)
                else:
                    new_data_body.pop(url)



class _BaseAbuseChDownloadingTimeOrderedRowsCollector(BaseDownloadingTimeOrderedRowsCollector):

    row_time_legacy_state_key = None
    time_field_index = None

    @property
    def source_config_section(self):
        return 'abusech_{}'.format(self.get_source_channel().replace('-', '_'))

    def load_state(self):
        state = super(_BaseAbuseChDownloadingTimeOrderedRowsCollector, self).load_state()
        if self.row_time_legacy_state_key and self.row_time_legacy_state_key in state:
            # got `state` is a legacy form
            row_time = self._normalize_row_time(state[self.row_time_legacy_state_key])
            state = {
                # note: one or a few rows (those containing this "boundary"
                # time value) will be duplicated, but we can live with that
                self._NEWEST_ROW_TIME_STATE_KEY: row_time,
                self._NEWEST_ROWS_STATE_KEY: set(),
            }
        return state

    def extract_row_time(self, row):
        row_time = self._extract_time_from_row(row)
        return self._normalize_row_time(row_time)

    def _extract_time_from_row(self, row):
        fields = row.split(',')
        time_field = fields[self.time_field_index]
        row_time = time_field.strip().strip('"')
        return row_time

    def _normalize_row_time(self, row_time):
        return str(parse_iso_datetime_to_utc(row_time))


class AbuseChRansomwareTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    row_time_legacy_state_key = 'timestamp'
    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'ransomware'


class AbuseChFeodoTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '201908'

    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'feodotracker'


class AbuseChSSLBlacklistCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):
    # Note that, contrary to its name, it is an *event-based* source

    raw_format_version_tag = '201902'

    row_time_legacy_state_key = 'time'
    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'ssl-blacklist'


class AbuseChUrlhausUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    row_time_legacy_state_key = 'time'
    time_field_index = 1

    def get_source_channel(self, **processed_data):
        return 'urlhaus-urls'



entry_point_factory(sys.modules[__name__])
